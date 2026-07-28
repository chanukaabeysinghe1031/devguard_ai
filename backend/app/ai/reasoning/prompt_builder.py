"""Versioned prompt templates for grounded LLM reasoning."""

from __future__ import annotations

import json
from typing import Any

PROMPT_NAME = "root_cause_prompt"
PROMPT_VERSION = "v1"
SCHEMA_VERSION = "1.0"

SAFETY_RULES = [
    "Never invent evidence IDs or documentation chunk IDs.",
    "Cite only IDs provided in the context.",
    "Do not include secrets, tokens, or credentials.",
    "Do not recommend destructive commands such as terraform destroy or rm -rf /.",
    "If uncertain, lower confidence and list alternative causes.",
    "Return valid JSON only matching the schema.",
]


ROOT_CAUSE_SCHEMA: dict[str, Any] = {
    "summary": "string",
    "root_cause": {
        "category": "string",
        "explanation": "string",
        "confidence": "number",
    },
    "supporting_evidence_ids": ["string"],
    "documentation_chunk_ids": ["string"],
    "alternative_causes": ["string"],
    "impact": "string",
}


def build_root_cause_prompt(payload: dict[str, Any]) -> str:
    return (
        f"Prompt: {PROMPT_NAME} {PROMPT_VERSION}\n"
        f"Schema version: {SCHEMA_VERSION}\n"
        "You are DevGuard AI. Produce grounded root-cause analysis as JSON.\n"
        f"Safety rules:\n- " + "\n- ".join(SAFETY_RULES) + "\n"
        f"Expected schema:\n{json.dumps(ROOT_CAUSE_SCHEMA, indent=2)}\n"
        f"Context:\n{json.dumps(payload, indent=2)}\n"
    )


def build_recommendation_prompt(payload: dict[str, Any]) -> str:
    return (
        f"Prompt: recommendation_prompt {PROMPT_VERSION}\n"
        "Adapt template remediation using evidence and documentation. Return JSON with key "
        "'steps' (array of step objects with step_number, title, action, explanation, "
        "expected_result, risk_level, difficulty, command_template).\n"
        f"Safety rules:\n- " + "\n- ".join(SAFETY_RULES) + "\n"
        f"Context:\n{json.dumps(payload, indent=2)}\n"
    )
