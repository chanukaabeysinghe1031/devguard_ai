"""Research evaluation metrics read API (Phase 5A)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps.access import require_org_reader

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

_REPO_ROOT = Path(__file__).resolve().parents[5]
_LATEST_METRICS = _REPO_ROOT / "datasets" / "benchmark" / "results" / "latest_metrics.json"


@router.get("/latest-metrics")
async def get_latest_metrics(
    _ctx: tuple = Depends(require_org_reader),
) -> dict[str, Any]:
    """Return the latest versioned benchmark metrics file when present."""
    if not _LATEST_METRICS.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evaluation metrics file is available yet.",
        )
    try:
        return json.loads(_LATEST_METRICS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read evaluation metrics.",
        ) from exc
