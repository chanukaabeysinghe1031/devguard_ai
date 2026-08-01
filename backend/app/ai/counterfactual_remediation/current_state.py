"""Build RemediationCurrentState from parser entity dicts / artifact metadata."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.ai.counterfactual_remediation.model_types import RemediationCurrentState
from app.ai.counterfactual_remediation.safety import (
    contains_secret_material,
    mask_for_context,
    sanitize_untrusted_instructions,
)
from app.ai.counterfactual_remediation.versions import REMEDIATION_CURRENT_STATE_VERSION
from app.domain.counterfactual_remediation.enums import RemediationArtifactType

logger = logging.getLogger(__name__)

_MAX_FRAGMENT_CHARS = 8_000
_MAX_ENTITIES = 200
_MAX_RELATIONSHIPS = 300


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _entity_dict(entity: Any) -> dict[str, Any]:
    if isinstance(entity, dict):
        return dict(entity)
    if hasattr(entity, "to_dict"):
        payload = entity.to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    # GraphEntityPreview-like objects
    return {
        "id": getattr(entity, "id", None),
        "type": getattr(entity, "type", None),
        "label": getattr(entity, "label", None),
        "metadata": dict(getattr(entity, "metadata", None) or {}),
    }


def map_artifact_type(raw: str | None) -> RemediationArtifactType:
    if not raw:
        return RemediationArtifactType.UNKNOWN
    key = raw.strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "WORKFLOW": RemediationArtifactType.GITHUB_WORKFLOW,
        "GITHUB_ACTIONS_WORKFLOW": RemediationArtifactType.GITHUB_WORKFLOW,
        "WORKFLOW_YAML": RemediationArtifactType.GITHUB_WORKFLOW,
        "REUSABLE_WORKFLOW_YAML": RemediationArtifactType.REUSABLE_WORKFLOW,
        "TERRAFORM": RemediationArtifactType.TERRAFORM_CONFIGURATION,
        "TERRAFORM_FILE": RemediationArtifactType.TERRAFORM_CONFIGURATION,
        "TF": RemediationArtifactType.TERRAFORM_CONFIGURATION,
        "VARIABLE_FILE": RemediationArtifactType.TERRAFORM_VARIABLES,
        "IAM": RemediationArtifactType.IAM_POLICY,
        "AWS_POLICY": RemediationArtifactType.IAM_POLICY,
        "POLICY": RemediationArtifactType.IAM_POLICY,
        "DOCKERFILE": RemediationArtifactType.DOCKERFILE,
        "COMPOSE": RemediationArtifactType.DOCKER_COMPOSE,
        "K8S": RemediationArtifactType.KUBERNETES_MANIFEST,
        "PACKAGE_JSON": RemediationArtifactType.DEPENDENCY_MANIFEST,
        "REQUIREMENTS_TXT": RemediationArtifactType.DEPENDENCY_MANIFEST,
        "LOCKFILE": RemediationArtifactType.LOCK_FILE,
    }
    if key in aliases:
        return aliases[key]
    try:
        return RemediationArtifactType(key)
    except ValueError:
        return RemediationArtifactType.UNKNOWN


class RemediationCurrentStateBuilder:
    """Deterministic current-state snapshot builder (bounded fragments + hashes)."""

    def __init__(self, *, max_fragment_chars: int = _MAX_FRAGMENT_CHARS) -> None:
        self._max_fragment_chars = max(256, max_fragment_chars)

    def build(
        self,
        *,
        entities: list[Any] | None = None,
        relationships: list[Any] | None = None,
        artifact_metadata: dict[str, Any] | None = None,
        source_fragment: str | None = None,
        failure_condition: str | None = None,
        organization_id: str | None = None,
    ) -> RemediationCurrentState:
        del organization_id  # reserved for org-scoped future enrichment
        meta = _as_dict(artifact_metadata)
        entity_dicts = [_entity_dict(e) for e in (entities or [])][:_MAX_ENTITIES]
        entity_dicts = sorted(
            entity_dicts,
            key=lambda e: (
                str(e.get("type") or ""),
                str(e.get("id") or ""),
                str(e.get("label") or ""),
            ),
        )
        rel_dicts: list[dict[str, Any]] = []
        for rel in relationships or []:
            if isinstance(rel, dict):
                rel_dicts.append(dict(rel))
            elif hasattr(rel, "to_dict"):
                payload = rel.to_dict()
                if isinstance(payload, dict):
                    rel_dicts.append(dict(payload))
            else:
                rel_dicts.append(
                    {
                        "source_id": getattr(rel, "source_id", None),
                        "target_id": getattr(rel, "target_id", None),
                        "type": getattr(rel, "type", None),
                    }
                )
        rel_dicts = sorted(
            rel_dicts,
            key=lambda r: (
                str(r.get("type") or ""),
                str(r.get("source_id") or ""),
                str(r.get("target_id") or ""),
            ),
        )[:_MAX_RELATIONSHIPS]

        fragment = (
            source_fragment
            or meta.get("source_fragment")
            or meta.get("current_configuration_fragment")
        )
        content_hash: str | None
        if isinstance(fragment, str):
            fragment = sanitize_untrusted_instructions(fragment)
            if contains_secret_material(fragment):
                fragment = mask_for_context(fragment)
            if len(fragment) > self._max_fragment_chars:
                fragment = fragment[: self._max_fragment_chars]
            content_hash = _sha256(fragment)
        else:
            fragment = None
            raw_hash = meta.get("content_hash")
            if isinstance(raw_hash, str) and raw_hash:
                content_hash = raw_hash
            elif entity_dicts:
                content_hash = _sha256(
                    str(
                        sorted(
                            (str(e.get("id")), str(e.get("type")), str(e.get("label")))
                            for e in entity_dicts
                        )
                    )
                )
            else:
                content_hash = None

        values, references, dependencies, permissions = self._extract_from_entities(entity_dicts)
        region = _first_str(
            meta.get("region"),
            values.get("region"),
            values.get("provider_region"),
        )
        environment = _first_str(meta.get("environment"), values.get("environment"))
        account = _first_str(meta.get("account"), values.get("account"))

        missing: list[str] = []
        if not fragment:
            missing.append("source_fragment")
        if not entity_dicts:
            missing.append("structured_entities")

        artifact_type = map_artifact_type(
            _first_str(meta.get("artifact_type"), meta.get("kind"), meta.get("type"))
        )

        security_findings: list[dict[str, Any]] = []
        for finding in _as_list(meta.get("security_findings")):
            if isinstance(finding, dict):
                security_findings.append(dict(finding))
            else:
                security_findings.append({"finding": str(finding)})

        state = RemediationCurrentState(
            artifact_id=_first_str(meta.get("artifact_id"), meta.get("id")),
            artifact_type=artifact_type,
            source_path=_first_str(meta.get("source_path"), meta.get("path")),
            commit_sha=_first_str(meta.get("commit_sha"), meta.get("sha")),
            content_hash=content_hash,
            source_fragment=fragment,
            structured_entities=entity_dicts,
            structured_relationships=rel_dicts,
            current_values=values,
            current_references={str(i): ref for i, ref in enumerate(sorted(set(references)))},
            current_dependencies=[{"dependency": d} for d in sorted(set(dependencies))],
            current_permissions=permissions,
            current_conditions=[
                {"condition": str(c)}
                for c in sorted(
                    {
                        str(c)
                        for e in entity_dicts
                        for c in _as_list(
                            (e.get("metadata") or {}).get("condition")
                            or (e.get("metadata") or {}).get("conditions")
                        )
                        if c
                    }
                )
            ],
            current_region=region,
            current_account_context=account,
            current_environment=environment,
            current_versions={
                str(k): str(v)
                for k, v in _as_dict(meta.get("versions") or values.get("versions")).items()
            },
            current_security_findings=security_findings,
            current_plan_changes=[
                dict(c) for c in _as_list(meta.get("plan_changes")) if isinstance(c, dict)
            ],
            current_failure_condition=failure_condition,
            parser_version=_first_str(meta.get("parser_version")),
            extraction_quality=(
                None
                if _optional_float(meta.get("extraction_quality") or meta.get("quality")) is None
                else str(_optional_float(meta.get("extraction_quality") or meta.get("quality")))
            ),
            missing_fields=missing,
            redaction_status="masked",
            state_version=REMEDIATION_CURRENT_STATE_VERSION,
        )
        logger.debug(
            "current_state_built artifact_id=%s entities=%s missing=%s",
            state.artifact_id,
            len(entity_dicts),
            missing,
        )
        return state

    def _extract_from_entities(
        self,
        entities: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[str], list[str], list[dict[str, Any]]]:
        values: dict[str, Any] = {}
        references: list[str] = []
        dependencies: list[str] = []
        permissions: list[dict[str, Any]] = []

        for entity in entities:
            etype = str(entity.get("type") or "").upper()
            meta = _as_dict(entity.get("metadata"))
            eid = str(entity.get("id") or entity.get("label") or "")

            if "permissions" in meta:
                permissions.append(
                    {
                        "entity_id": eid or "permissions",
                        "permissions": meta.get("permissions"),
                    }
                )
            if etype in {"JOB", "WORKFLOW"} and "needs" in meta:
                needs = meta.get("needs")
                if isinstance(needs, list):
                    dependencies.extend(str(n) for n in needs)
                elif needs is not None:
                    dependencies.append(str(needs))
            if etype in {"RESOURCE", "MODULE", "DATA", "OUTPUT", "VARIABLE", "PROVIDER"}:
                address = meta.get("address") or entity.get("label")
                if address:
                    values.setdefault("addresses", [])
                    if isinstance(values["addresses"], list):
                        values["addresses"].append(str(address))
                if meta.get("type"):
                    values[f"type:{eid}"] = meta.get("type")
                if "region" in meta:
                    values["provider_region"] = meta.get("region")
                if meta.get("prevent_destroy") is True or meta.get("lifecycle_prevent_destroy"):
                    values[f"prevent_destroy:{eid}"] = True
                if meta.get("sensitive") is True:
                    values[f"sensitive:{eid}"] = True
            if etype in {"POLICY_STATEMENT", "IAM_POLICY"}:
                effect = meta.get("Effect") or meta.get("effect")
                actions = meta.get("Action") or meta.get("actions") or []
                resources = meta.get("Resource") or meta.get("resources") or []
                permissions.append(
                    {
                        "entity_id": eid or f"statement:{len(permissions)}",
                        "Effect": effect,
                        "Action": actions,
                        "Resource": resources,
                    }
                )
                if str(effect).lower() == "deny":
                    values.setdefault("explicit_denies", [])
                    if isinstance(values["explicit_denies"], list):
                        values["explicit_denies"].append(eid)
            if etype == "SECRET_REFERENCE":
                references.append(str(entity.get("label") or eid))
            for key in ("role", "role_arn", "principal", "resource"):
                if meta.get(key):
                    values[key] = meta.get(key)
                    references.append(str(meta.get(key)))

        return values, references, dependencies, permissions


def _first_str(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_remediation_current_state(
    *,
    entities: list[Any] | None = None,
    relationships: list[Any] | None = None,
    artifact_metadata: dict[str, Any] | None = None,
    source_fragment: str | None = None,
    failure_condition: str | None = None,
) -> RemediationCurrentState:
    """Module-level helper matching the brief naming style."""
    return RemediationCurrentStateBuilder().build(
        entities=entities,
        relationships=relationships,
        artifact_metadata=artifact_metadata,
        source_fragment=source_fragment,
        failure_condition=failure_condition,
    )
