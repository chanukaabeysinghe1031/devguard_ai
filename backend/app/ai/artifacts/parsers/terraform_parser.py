"""Regex-based Terraform HCL structured parser (no HCL library)."""

from __future__ import annotations

import re

from app.ai.artifacts.parsers.base import StructuredArtifactParser
from app.domain.artifacts.enums import ArtifactKind, ParseStatus
from app.domain.artifacts.models import (
    EvidenceCandidate,
    GraphEntityPreview,
    GraphRelationshipPreview,
    SourceLocation,
    StructuredParseResult,
)

PARSER_VERSION = "1.0.0"

_BLOCK_RE = re.compile(
    r"^(?P<kind>resource|module|variable|output|data|provider)\s+"
    r'(?:"(?P<type>[^"]+)"\s+)?'
    r'(?:"(?P<name>[^"]+)"|(?P<bare>[A-Za-z0-9_-]+))',
    re.MULTILINE,
)
_DEPENDS_ON_RE = re.compile(
    r"depends_on\s*=\s*\[(?P<body>[^\]]*)\]",
    re.DOTALL,
)
_REF_RE = re.compile(
    r"\b(?P<ref>(?:var|local|module|data)\.[A-Za-z0-9_\.]+|"
    r"(?:aws|azurerm|google|google-beta|helm|kubernetes|null|random|"
    r"tls|archive|external|time|cloudflare|datadog)_[A-Za-z0-9_]+\.[A-Za-z0-9_\.]+)\b"
)
_QUOTED_REF_RE = re.compile(r'"([A-Za-z0-9_\.]+)"')


class TerraformParser(StructuredArtifactParser):
    name = "terraform_parser"
    version = PARSER_VERSION

    def supports(self, kind: ArtifactKind) -> bool:
        return kind in {ArtifactKind.TERRAFORM_FILE, ArtifactKind.VARIABLE_FILE}

    def parse(
        self,
        content: str,
        *,
        filename: str,
        kind: ArtifactKind,
    ) -> StructuredParseResult:
        entities: list[GraphEntityPreview] = []
        relationships: list[GraphRelationshipPreview] = []
        evidence: list[EvidenceCandidate] = []
        warnings: list[str] = []
        errors: list[str] = []

        declared_ids: dict[str, str] = {}

        for match in _BLOCK_RE.finditer(content):
            block_kind = match.group("kind")
            type_name = match.group("type")
            name = match.group("name") or match.group("bare") or "unnamed"
            line_no = content[: match.start()].count("\n") + 1

            if block_kind == "resource" and type_name:
                entity_id = f"resource:{type_name}.{name}"
                address = f"{type_name}.{name}"
                label = address
                meta = {"block": block_kind, "type": type_name, "name": name}
            elif block_kind == "data" and type_name:
                entity_id = f"data:{type_name}.{name}"
                address = f"data.{type_name}.{name}"
                label = address
                meta = {"block": block_kind, "type": type_name, "name": name}
            elif block_kind == "module":
                entity_id = f"module:{name}"
                address = f"module.{name}"
                label = address
                meta = {"block": block_kind, "name": name}
            elif block_kind == "variable":
                entity_id = f"var:{name}"
                address = f"var.{name}"
                label = address
                meta = {"block": block_kind, "name": name}
            elif block_kind == "output":
                entity_id = f"output:{name}"
                address = f"output.{name}"
                label = address
                meta = {"block": block_kind, "name": name}
            else:  # provider
                entity_id = f"provider:{name}"
                address = f"provider.{name}"
                label = address
                meta = {"block": block_kind, "name": name}

            declared_ids[address] = entity_id
            entities.append(
                GraphEntityPreview(
                    id=entity_id,
                    type=block_kind.upper(),
                    label=label,
                    location=SourceLocation(path=filename, line_start=line_no),
                    metadata=meta,
                )
            )
            relationships.append(
                GraphRelationshipPreview(
                    source_id=f"file:{filename}",
                    target_id=entity_id,
                    type="DECLARES",
                    confidence=1.0,
                    explanation=f"File declares {address}",
                    deterministic=True,
                )
            )

        # File entity for DECLARES source
        entities.insert(
            0,
            GraphEntityPreview(
                id=f"file:{filename}",
                type="TERRAFORM_FILE",
                label=filename,
                location=SourceLocation(path=filename, line_start=1),
                metadata={"kind": kind.value},
            ),
        )

        # depends_on (quoted or bare addresses)
        for dep_match in _DEPENDS_ON_RE.finditer(content):
            body = dep_match.group("body")
            prefix = content[: dep_match.start()]
            owner_address = _nearest_address(prefix)
            owner_id = declared_ids.get(owner_address or "", "")
            if not owner_id:
                continue
            deps = _QUOTED_REF_RE.findall(body)
            if not deps:
                deps = [
                    token.strip().rstrip(",")
                    for token in body.replace("\n", " ").split(",")
                    if token.strip().rstrip(",")
                ]
            for dep in deps:
                target_id = declared_ids.get(dep) or f"ref:{dep}"
                if not any(e.id == target_id for e in entities):
                    entities.append(
                        GraphEntityPreview(
                            id=target_id,
                            type="REFERENCE",
                            label=dep,
                            location=SourceLocation(path=filename),
                            metadata={"address": dep},
                        )
                    )
                relationships.append(
                    GraphRelationshipPreview(
                        source_id=owner_id,
                        target_id=target_id,
                        type="DEPENDS_ON",
                        confidence=1.0,
                        explanation=f"{owner_address} depends_on {dep}",
                        deterministic=True,
                    )
                )

        # Reference scan (skip declaration lines themselves loosely)
        seen_refs: set[tuple[str, str]] = set()
        for ref_match in _REF_RE.finditer(content):
            ref = ref_match.group("ref")
            # Skip provider bare names mistaken as refs — keep aws_xxx.yyy style
            owner_address = _nearest_address(content[: ref_match.start()])
            owner_id = declared_ids.get(owner_address or "", "")
            if not owner_id:
                continue
            if ref == owner_address:
                continue
            target_id = declared_ids.get(ref) or f"ref:{ref}"
            key = (owner_id, target_id)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            if not any(e.id == target_id for e in entities):
                entities.append(
                    GraphEntityPreview(
                        id=target_id,
                        type="REFERENCE",
                        label=ref,
                        location=SourceLocation(
                            path=filename,
                            line_start=content[: ref_match.start()].count("\n") + 1,
                        ),
                        metadata={"address": ref},
                    )
                )
            relationships.append(
                GraphRelationshipPreview(
                    source_id=owner_id,
                    target_id=target_id,
                    type="REFERENCES",
                    confidence=0.85,
                    explanation=f"{owner_address} references {ref}",
                    deterministic=True,
                )
            )

        if not declared_ids:
            warnings.append("No Terraform blocks detected")
            status = ParseStatus.PARTIAL
            quality = 0.2
        else:
            status = ParseStatus.SUCCESS
            quality = min(1.0, 0.4 + 0.1 * len(declared_ids))

        if any(r.type == "DEPENDS_ON" for r in relationships):
            evidence.append(
                EvidenceCandidate(
                    kind="terraform_depends_on",
                    text="Explicit depends_on relationships detected",
                    location=SourceLocation(path=filename),
                    importance=0.6,
                    metadata={
                        "depends_on_count": sum(1 for r in relationships if r.type == "DEPENDS_ON")
                    },
                )
            )

        return StructuredParseResult(
            parser_name=self.name,
            parser_version=self.version,
            status=status,
            entities=entities,
            relationships=relationships,
            evidence_candidates=evidence,
            warnings=warnings,
            errors=errors,
            extraction_quality=quality,
            raw_summary={
                "filename": filename,
                "kind": kind.value,
                "declared_count": len(declared_ids),
                "addresses": sorted(declared_ids.keys()),
                "relationship_counts": {
                    "DECLARES": sum(1 for r in relationships if r.type == "DECLARES"),
                    "DEPENDS_ON": sum(1 for r in relationships if r.type == "DEPENDS_ON"),
                    "REFERENCES": sum(1 for r in relationships if r.type == "REFERENCES"),
                },
            },
        )


def _nearest_address(prefix: str) -> str | None:
    last: str | None = None
    for match in _BLOCK_RE.finditer(prefix):
        block_kind = match.group("kind")
        type_name = match.group("type")
        name = match.group("name") or match.group("bare") or "unnamed"
        if block_kind == "resource" and type_name:
            last = f"{type_name}.{name}"
        elif block_kind == "data" and type_name:
            last = f"data.{type_name}.{name}"
        elif block_kind == "module":
            last = f"module.{name}"
        elif block_kind == "variable":
            last = f"var.{name}"
        elif block_kind == "output":
            last = f"output.{name}"
        else:
            last = f"provider.{name}"
    return last
