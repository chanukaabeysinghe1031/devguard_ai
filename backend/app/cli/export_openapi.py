"""Export the live FastAPI OpenAPI schema to docs/openapi.json."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    candidates = [
        Path("/workspace/docs/openapi.json"),
        Path(__file__).resolve().parents[3] / "docs" / "openapi.json",
        Path("/tmp/openapi.json"),
    ]
    out = candidates[-1]
    for path in candidates:
        if path.parent.exists() or path.parent == Path("/tmp"):
            out = path
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
