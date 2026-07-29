#!/usr/bin/env python3
"""Collect closed GitHub issues via the official REST API (no HTML scraping).

Writes sanitised incident JSON under datasets/raw/github/<owner>_<repo>/ and
appends a JSONL manifest. Does not embed, ingest to Chroma, or call OpenAI.

Usage (from repo root):

  export GITHUB_TOKEN=ghp_...   # optional but recommended
  python scripts/dataset/collect_github_issues.py \\
    --repo actions/runner --labels bug --max-issues 20

  python scripts/dataset/collect_github_issues.py --from-targets
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.services.secret_masker import mask_secrets  # noqa: E402

DEFAULT_TARGETS = REPO_ROOT / "datasets" / "manifests" / "collection_targets.json"
DEFAULT_OPEN_TARGETS = REPO_ROOT / "datasets" / "manifests" / "collection_targets_open.json"
DEFAULT_OUT = REPO_ROOT / "datasets" / "raw" / "github"
DEFAULT_OPEN_OUT = REPO_ROOT / "datasets" / "raw" / "github_open"
DATASET_VERSION_PATH = REPO_ROOT / "datasets" / "VERSION"
USER_AGENT = "DevGuardAI-DatasetCollector/0.1 (MSc research; +https://github.com/)"

# Noise lines often useless for RAG (kept conservative).
_NOISE_LINE = re.compile(
    r"^\s*(\+1|thanks!?|thank you!?|same (here|issue)|me too)\s*$",
    re.IGNORECASE,
)


def _read_dataset_version() -> str:
    if DATASET_VERSION_PATH.exists():
        return DATASET_VERSION_PATH.read_text(encoding="utf-8").strip() or "0.1.0-phase1"
    return "0.1.0-phase1"


def _clean_body(text: str | None) -> str:
    if not text:
        return ""
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if _NOISE_LINE.match(line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _incident_id(repository: str, issue_number: int) -> str:
    slug = repository.replace("/", "-").lower()
    return f"gh-{slug}-{issue_number}"


def _guess_category(technology: str, suggested: str | None) -> str:
    if suggested:
        return suggested
    mapping = {
        "terraform": "terraform_failure",
        "docker": "docker_failure",
        "aws": "aws_permission_failure",
        "python": "test_failure",
        "java": "build_failure",
        "node": "dependency_failure",
        "npm": "dependency_failure",
        "maven": "build_failure",
        "gradle": "build_failure",
        "kubernetes": "deployment_failure",
        "github_actions": "configuration_failure",
        "networking": "network_failure",
        "authentication": "security_misconfiguration",
    }
    return mapping.get(technology, "unknown_failure")


def _github_get(
    url: str,
    *,
    token: str | None,
    timeout_s: float = 30.0,
) -> tuple[Any, dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
            header_map = {k.lower(): v for k, v in response.headers.items()}
            return json.loads(body), header_map
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {detail}") from exc


def _rate_limit_sleep(headers: dict[str, str]) -> None:
    remaining = headers.get("x-ratelimit-remaining")
    reset = headers.get("x-ratelimit-reset")
    if remaining is None:
        return
    try:
        left = int(remaining)
    except ValueError:
        return
    if left > 5:
        return
    wait_s = 5.0
    if reset:
        try:
            wait_s = max(5.0, int(reset) - int(time.time()) + 1)
        except ValueError:
            wait_s = 5.0
    print(f"Rate limit low ({left}); sleeping {wait_s:.0f}s", file=sys.stderr)
    time.sleep(min(wait_s, 120.0))


def fetch_issues(
    repository: str,
    *,
    token: str | None,
    state: str,
    labels: list[str],
    max_issues: int,
    per_page: int = 50,
) -> list[dict[str, Any]]:
    owner, _, name = repository.partition("/")
    if not owner or not name:
        raise ValueError(f"Invalid repository {repository!r}; expected owner/name")

    collected: list[dict[str, Any]] = []
    page = 1
    while len(collected) < max_issues:
        params: dict[str, str] = {
            "state": state,
            "per_page": str(min(per_page, 100)),
            "page": str(page),
            "sort": "updated",
            "direction": "desc",
        }
        if labels:
            params["labels"] = ",".join(labels)
        query = urllib.parse.urlencode(params)
        url = f"https://api.github.com/repos/{owner}/{name}/issues?{query}"
        payload, headers = _github_get(url, token=token)
        _rate_limit_sleep(headers)
        if not isinstance(payload, list) or not payload:
            break
        for item in payload:
            if "pull_request" in item:
                continue
            collected.append(item)
            if len(collected) >= max_issues:
                break
        if len(payload) < min(per_page, 100):
            break
        page += 1
        time.sleep(0.35)
    return collected[:max_issues]


def issue_to_incident(
    item: dict[str, Any],
    *,
    repository: str,
    technology: str,
    suggested_failure_category: str | None,
    dataset_version: str,
) -> dict[str, Any]:
    number = int(item["number"])
    title = str(item.get("title") or "").strip() or f"Issue {number}"
    body_raw = _clean_body(item.get("body"))
    masked_title, title_hits = mask_secrets(title)
    masked_body, body_hits = mask_secrets(body_raw)
    labels = [
        str(label.get("name"))
        for label in (item.get("labels") or [])
        if isinstance(label, dict) and label.get("name")
    ]
    html_url = str(item.get("html_url") or "")
    masked_count = title_hits + body_hits
    return {
        "incident_id": _incident_id(repository, number),
        "source_type": "public_github_issue",
        "repository": repository,
        "issue_number": number,
        "issue_url": html_url,
        "title": masked_title,
        "description": masked_body,
        "labels": labels,
        "symptoms": None,
        "root_cause": None,
        "resolution": None,
        "technology": technology,
        "failure_category": _guess_category(technology, suggested_failure_category),
        "severity": None,
        "state": item.get("state"),
        "resolved": str(item.get("state") or "").lower() == "closed",
        "secrets_masked": masked_count > 0,
        "secrets_masked_count": masked_count,
        "provenance": {
            "source_url": html_url,
            "collection_date": datetime.now(UTC).isoformat(),
            "license_or_usage_basis": (
                "Public GitHub issue content; usage subject to repository license "
                "and GitHub Terms of Service; collected for academic research."
            ),
            "modified": False,
            "collector": "scripts/dataset/collect_github_issues.py",
            "github_created_at": item.get("created_at"),
            "github_closed_at": item.get("closed_at"),
            "github_updated_at": item.get("updated_at"),
        },
        "collection": {
            "dataset_version": dataset_version,
            "status": "raw_collected",
            "curation_notes": None,
            "reject_reason": None,
        },
        "raw_metadata": {
            "github_node_id": item.get("node_id"),
            "author_association": item.get("author_association"),
            "comments": item.get("comments"),
            "reactions_total": (item.get("reactions") or {}).get("total_count"),
        },
    }


def write_incidents(
    incidents: list[dict[str, Any]],
    *,
    out_dir: Path,
    repository: str,
) -> Path:
    slug = repository.replace("/", "_")
    repo_dir = out_dir / slug
    repo_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"{slug}_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for incident in incidents:
            path = repo_dir / f"{incident['incident_id']}.json"
            path.write_text(json.dumps(incident, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            manifest.write(json.dumps({"path": str(path.relative_to(REPO_ROOT)), **{
                k: incident[k]
                for k in (
                    "incident_id",
                    "repository",
                    "issue_number",
                    "issue_url",
                    "technology",
                    "failure_category",
                    "resolved",
                )
            }}, ensure_ascii=False) + "\n")
    return manifest_path


def load_targets(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    targets = data.get("targets")
    if not isinstance(targets, list):
        raise ValueError("collection_targets.json missing targets[]")
    return sorted(targets, key=lambda t: int(t.get("priority", 99)))


def collect_one(
    *,
    repository: str,
    technology: str,
    suggested_failure_category: str | None,
    state: str,
    labels: list[str],
    max_issues: int,
    token: str | None,
    out_dir: Path,
    dry_run: bool,
) -> int:
    print(f"Collecting {repository} (max={max_issues}, labels={labels or '-'})")
    issues = fetch_issues(
        repository,
        token=token,
        state=state,
        labels=labels,
        max_issues=max_issues,
    )
    version = _read_dataset_version()
    incidents = [
        issue_to_incident(
            item,
            repository=repository,
            technology=technology,
            suggested_failure_category=suggested_failure_category,
            dataset_version=version,
        )
        for item in issues
    ]
    print(f"  fetched_issues={len(issues)} incidents={len(incidents)}")
    if dry_run:
        for incident in incidents[:3]:
            print(f"  sample: {incident['incident_id']} | {incident['title'][:80]}")
        return len(incidents)
    manifest = write_incidents(incidents, out_dir=out_dir, repository=repository)
    print(f"  wrote={len(incidents)} manifest={manifest.relative_to(REPO_ROOT)}")
    return len(incidents)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="owner/name (single repository mode)")
    parser.add_argument("--technology", default="other")
    parser.add_argument("--failure-category", default=None)
    parser.add_argument("--state", default="closed", choices=["open", "closed", "all"])
    parser.add_argument("--labels", default="", help="Comma-separated GitHub labels")
    parser.add_argument("--max-issues", type=int, default=50)
    parser.add_argument("--from-targets", action="store_true")
    parser.add_argument(
        "--open-eval-set",
        action="store_true",
        help=(
            "Collect the bounded open-issue evaluation set into datasets/raw/github_open "
            "(uses collection_targets_open.json)."
        ),
    )
    parser.add_argument("--targets-file", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--token", default=None, help="Override GITHUB_TOKEN")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print(
            "Warning: no GITHUB_TOKEN set; unauthenticated rate limits are low.",
            file=sys.stderr,
        )

    if args.open_eval_set and args.from_targets:
        build_parser().error("Use either --from-targets or --open-eval-set, not both")

    targets_file = args.targets_file
    out_dir = args.out_dir
    if args.open_eval_set:
        targets_file = targets_file or DEFAULT_OPEN_TARGETS
        out_dir = out_dir or DEFAULT_OPEN_OUT
    else:
        targets_file = targets_file or DEFAULT_TARGETS
        out_dir = out_dir or DEFAULT_OUT

    total = 0
    if args.open_eval_set or args.from_targets:
        targets = load_targets(targets_file)
        for target in targets:
            total += collect_one(
                repository=str(target["repository"]),
                technology=str(target.get("technology") or "other"),
                suggested_failure_category=target.get("suggested_failure_category"),
                state=str(target.get("state") or ("open" if args.open_eval_set else "closed")),
                labels=list(target.get("labels") or []),
                max_issues=int(target.get("max_issues") or 20),
                token=token,
                out_dir=out_dir,
                dry_run=args.dry_run,
            )
    elif args.repo:
        labels = [part.strip() for part in args.labels.split(",") if part.strip()]
        total = collect_one(
            repository=args.repo,
            technology=args.technology,
            suggested_failure_category=args.failure_category,
            state=args.state,
            labels=labels,
            max_issues=args.max_issues,
            token=token,
            out_dir=out_dir,
            dry_run=args.dry_run,
        )
    else:
        build_parser().error("Provide --repo, --from-targets, or --open-eval-set")

    print(f"Done. total_incidents={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
