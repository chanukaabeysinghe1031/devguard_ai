#!/usr/bin/env python3
"""Validate collected incident JSON files against datasets/schemas/incident.schema.json.

Uses a lightweight required-field checker so Phase 1 has no extra pip dependency.
If the ``jsonschema`` package is installed, full Draft 2020-12 validation is used.

Usage (from repo root):

  python scripts/dataset/validate_incidents.py
  python scripts/dataset/validate_incidents.py datasets/raw/github/actions_runner
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "datasets" / "schemas" / "incident.schema.json"
DEFAULT_ROOT = REPO_ROOT / "datasets" / "raw" / "github"
DEFAULT_OPEN_ROOT = REPO_ROOT / "datasets" / "raw" / "github_open"

REQUIRED = (
    "incident_id",
    "source_type",
    "title",
    "description",
    "technology",
    "failure_category",
    "provenance",
    "collection",
)

FROZEN_CATEGORIES = {
    "build_failure",
    "test_failure",
    "dependency_failure",
    "configuration_failure",
    "terraform_failure",
    "docker_failure",
    "deployment_failure",
    "aws_permission_failure",
    "network_failure",
    "security_misconfiguration",
    "unknown_failure",
}


def _lightweight_validate(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED:
        if key not in doc:
            errors.append(f"missing required field: {key}")
    if doc.get("failure_category") not in FROZEN_CATEGORIES:
        errors.append(f"invalid failure_category: {doc.get('failure_category')!r}")
    provenance = doc.get("provenance")
    if isinstance(provenance, dict):
        for key in ("source_url", "collection_date", "license_or_usage_basis", "modified"):
            if key not in provenance:
                errors.append(f"missing provenance.{key}")
    else:
        errors.append("provenance must be an object")
    collection = doc.get("collection")
    if isinstance(collection, dict):
        for key in ("dataset_version", "status"):
            if key not in collection:
                errors.append(f"missing collection.{key}")
    else:
        errors.append("collection must be an object")
    return errors


def _jsonschema_validate(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return _lightweight_validate(doc)
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(doc)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[DEFAULT_ROOT, DEFAULT_OPEN_ROOT],
        help="Files or directories of incident JSON",
    )
    args = parser.parse_args(argv)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    files: list[Path] = []
    for path in args.paths:
        path = path.expanduser()
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        else:
            path = path.resolve()
        if path.is_file() and path.suffix == ".json":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.json")))
        else:
            print(f"skip missing path: {path}", file=sys.stderr)

    if not files:
        print("No incident JSON files found.")
        return 0

    failed = 0
    for file_path in files:
        if file_path.name.endswith("_manifest.jsonl") or "manifest" in file_path.name:
            continue
        try:
            rel = file_path.relative_to(REPO_ROOT)
        except ValueError:
            rel = file_path
        try:
            doc = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"FAIL {rel}: invalid JSON ({exc})")
            failed += 1
            continue
        if not isinstance(doc, dict):
            print(f"FAIL {rel}: root must be object")
            failed += 1
            continue
        errors = _jsonschema_validate(doc, schema)
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for err in errors[:8]:
                print(f"  - {err}")
        else:
            print(f"OK   {rel}")

    print(f"Validated={len(files)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
