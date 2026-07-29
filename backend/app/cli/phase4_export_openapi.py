"""Phase 4B helper CLIs that write under /app/_phase4_out (bind-mounted)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path("/app/_phase4_out")
OUT.mkdir(parents=True, exist_ok=True)


def export_openapi() -> None:
    from app.main import create_app

    schema = create_app().openapi()
    path = OUT / "openapi.json"
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"paths={len(schema.get('paths', {}))} -> {path}")


if __name__ == "__main__":
    export_openapi()
