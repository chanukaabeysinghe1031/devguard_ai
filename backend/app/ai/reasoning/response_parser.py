"""Parse and lightly normalize provider JSON responses."""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_response(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = raw.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(text)
    if not match:
        raise ValueError("LLM response did not contain JSON object.")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("LLM JSON payload must be an object.")
    return value
