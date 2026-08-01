"""Prompt text and JSON schema constants for LLM remediation generation."""

from __future__ import annotations

import json
from typing import Any

from app.domain.counterfactual_remediation.generation_versions import (
    COUNTERFACTUAL_REMEDIATION_PROMPT_VERSION,
    COUNTERFACTUAL_REMEDIATION_SCHEMA_VERSION,
)

COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["candidates"],
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": [
                    "candidate_key",
                    "title",
                    "summary",
                    "hypothesis_id",
                    "artifact_changes",
                    "assumptions",
                    "limitations",
                ],
                "additionalProperties": False,
                "properties": {
                    "candidate_key": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "hypothesis_id": {"type": "string"},
                    "template_id": {"type": "string"},
                    "artifact_changes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "required": [
                                "artifact_id",
                                "change_type",
                                "original_fragment",
                                "proposed_fragment",
                            ],
                            "additionalProperties": False,
                            "properties": {
                                "artifact_id": {"type": "string"},
                                "source_path": {"type": "string"},
                                "artifact_type": {"type": "string"},
                                "change_type": {"type": "string"},
                                "target_property": {"type": "string"},
                                "original_fragment": {"type": "string"},
                                "proposed_fragment": {"type": "string"},
                                "expected_effect": {"type": "string"},
                                "evidence_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "graph_node_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                    "expected_failure_condition_status": {"type": "string"},
                    "expected_effects": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "expected_preserved_behaviors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                    "limitations": {"type": "array", "items": {"type": "string"}},
                    "verification_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "rollback_strategy": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"type": "string"},
                            "steps": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "risk_notes": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def build_remediation_prompt(context_payload: dict[str, Any]) -> str:
    """Build hypothesis-unverified remediation prompt (masked context only)."""
    instructions = [
        "The causal hypothesis is UNVERIFIED. Do not claim it is proven.",
        "Produce minimal structured remediation CANDIDATES only — never applied or verified.",
        "Use only supplied artifact IDs, graph node IDs, evidence IDs, and template IDs.",
        "Do not invent file paths, ARNs, secrets, principals, or artifact IDs.",
        "Do not broaden permissions with wildcards or admin actions.",
        "Do not embed secret values; correct reference names only.",
        "Do not disable tests, scanners, encryption, or approvals.",
        "Distinguish assumptions from evidence.",
        "Return no candidates if unsafe or insufficient information.",
        "Return JSON only matching the schema.",
    ]
    payload = {
        "prompt_version": COUNTERFACTUAL_REMEDIATION_PROMPT_VERSION,
        "schema_version": COUNTERFACTUAL_REMEDIATION_SCHEMA_VERSION,
        "instructions": instructions,
        "prohibited_changes": [
            "wildcard_permissions",
            "admin_grants",
            "plaintext_secrets",
            "disable_security_controls",
            "unrelated_artifact_rewrites",
            "shell_commands",
            "claim_verified_or_fixed",
        ],
        "context": context_payload,
        "schema": COUNTERFACTUAL_REMEDIATION_JSON_SCHEMA,
    }
    return (
        f"PROMPT_VERSION={COUNTERFACTUAL_REMEDIATION_PROMPT_VERSION}\n"
        f"SCHEMA_VERSION={COUNTERFACTUAL_REMEDIATION_SCHEMA_VERSION}\n"
        'Return JSON: {"candidates":[...]}.\n'
        + json.dumps(payload, ensure_ascii=True, default=str)
    )
