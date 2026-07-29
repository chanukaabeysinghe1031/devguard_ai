#!/usr/bin/env python3
"""Download approved official documentation pages into datasets/raw/docs/.

Respects robots.txt where applicable, retries transient failures, skips unchanged
files (hash / ETag / Last-Modified), and never scrapes non-approved hosts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "datasets" / "raw" / "docs"
VENDOR_DIRS = (
    "aws",
    "docker",
    "terraform",
    "github_actions",
    "kubernetes",
    "python",
    "java",
    "node",
)

USER_AGENT = "DevGuardAI-ResearchBot/0.5 (+https://github.com/devguard-ai; academic corpus)"
MAX_RETRIES = 3
RETRY_BACKOFF_S = 1.5

logger = logging.getLogger("download_official_docs")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _approved_hosts(manifest: dict[str, Any]) -> set[str]:
    hosts = {str(h).lower() for h in (manifest.get("approved_hosts") or [])}
    return hosts


def _robots_allowed(url: str, *, cache: dict[str, RobotFileParser]) -> bool:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base not in cache:
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:  # noqa: BLE001 - treat unread robots as allow-with-caution
            logger.warning("robots.txt unreadable for %s — proceeding cautiously", base)
            cache[base] = rp
            return True
        cache[base] = rp
    return bool(cache[base].can_fetch(USER_AGENT, url))


def _download_once(url: str, *, etag: str | None, last_modified: str | None) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read()
            return {
                "status": int(getattr(response, "status", 200) or 200),
                "body": body,
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "content_type": response.headers.get("Content-Type"),
            }
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return {
                "status": 304,
                "body": b"",
                "etag": etag,
                "last_modified": last_modified,
                "content_type": None,
            }
        raise


def download_source(
    source: dict[str, Any],
    *,
    vendor_dir: Path,
    prior: dict[str, Any] | None,
    robots_cache: dict[str, RobotFileParser],
) -> dict[str, Any]:
    url = str(source["url"])
    document_id = str(source["document_id"])
    prior = prior or {}
    entry: dict[str, Any] = {
        "url": url,
        "title": source.get("title"),
        "vendor": source.get("vendor"),
        "document_id": document_id,
        "version": source.get("version"),
        "licence": source.get("licence"),
        "retrieved": None,
        "etag": prior.get("etag"),
        "last_modified": prior.get("last_modified"),
        "hash": prior.get("hash"),
        "status": "pending",
        "path": None,
        "error": None,
    }

    host = urlparse(url).netloc.lower()
    if not _robots_allowed(url, cache=robots_cache):
        entry["status"] = "rejected_robots"
        entry["error"] = f"robots.txt disallows fetch for {url}"
        logger.error("%s", entry["error"])
        return entry

    html_path = vendor_dir / "downloads" / f"{document_id}.html"
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _download_once(
                url,
                etag=prior.get("etag"),
                last_modified=prior.get("last_modified"),
            )
            if result["status"] == 304 and html_path.exists():
                entry["status"] = "unchanged"
                entry["retrieved"] = prior.get("retrieved") or datetime.now(UTC).isoformat()
                entry["path"] = str(html_path.relative_to(REPO_ROOT))
                logger.info("unchanged %s", document_id)
                return entry

            body: bytes = result["body"]
            digest = _sha256_bytes(body)
            if html_path.exists() and prior.get("hash") == digest:
                entry["status"] = "unchanged"
                entry["hash"] = digest
                entry["etag"] = result.get("etag") or prior.get("etag")
                entry["last_modified"] = result.get("last_modified") or prior.get("last_modified")
                entry["retrieved"] = prior.get("retrieved") or datetime.now(UTC).isoformat()
                entry["path"] = str(html_path.relative_to(REPO_ROOT))
                logger.info("unchanged-hash %s", document_id)
                return entry

            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_bytes(body)
            entry["status"] = "downloaded"
            entry["hash"] = digest
            entry["etag"] = result.get("etag")
            entry["last_modified"] = result.get("last_modified")
            entry["retrieved"] = datetime.now(UTC).isoformat()
            entry["path"] = str(html_path.relative_to(REPO_ROOT))
            entry["content_type"] = result.get("content_type")
            logger.info("downloaded %s (%s bytes)", document_id, len(body))
            return entry
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "download failed %s attempt %s/%s: %s",
                document_id,
                attempt,
                MAX_RETRIES,
                exc,
            )
            time.sleep(RETRY_BACKOFF_S * attempt)

    entry["status"] = "failed"
    entry["error"] = str(last_error) if last_error else "unknown error"
    logger.error("failed %s: %s", document_id, entry["error"])
    return entry


def load_prior_entries(vendor_dir: Path) -> dict[str, dict[str, Any]]:
    path = vendor_dir / "download_manifest.json"
    if not path.exists():
        return {}
    data = _load_json(path)
    if isinstance(data, list):
        return {str(item.get("document_id")): item for item in data if item.get("document_id")}
    return {}


def process_vendor(vendor: str) -> dict[str, Any]:
    vendor_dir = DOCS_ROOT / vendor
    source_list = vendor_dir / "source_list.json"
    manifest_path = vendor_dir / "manifest.json"
    if not source_list.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Missing source_list/manifest for {vendor}")

    manifest = _load_json(manifest_path)
    approved = _approved_hosts(manifest)
    sources = _load_json(source_list)
    prior = load_prior_entries(vendor_dir)
    robots_cache: dict[str, RobotFileParser] = {}

    results: list[dict[str, Any]] = []
    for source in sources:
        url = str(source.get("url") or "")
        host = urlparse(url).netloc.lower()
        if approved and host not in approved and not any(host.endswith("." + h) for h in approved):
            results.append(
                {
                    "document_id": source.get("document_id"),
                    "url": url,
                    "vendor": source.get("vendor"),
                    "status": "rejected_host",
                    "error": f"host {host} not in approved_hosts",
                    "retrieved": None,
                    "hash": None,
                    "etag": None,
                    "last_modified": None,
                    "title": source.get("title"),
                }
            )
            logger.error("rejected host %s for %s", host, source.get("document_id"))
            continue
        results.append(
            download_source(
                source,
                vendor_dir=vendor_dir,
                prior=prior.get(str(source["document_id"])),
                robots_cache=robots_cache,
            )
        )

    _write_json(vendor_dir / "download_manifest.json", results)
    counts = {
        "downloaded": sum(1 for r in results if r.get("status") == "downloaded"),
        "unchanged": sum(1 for r in results if r.get("status") == "unchanged"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "rejected": sum(1 for r in results if str(r.get("status", "")).startswith("rejected")),
        "total": len(results),
    }
    return {"vendor": vendor, "counts": counts, "entries": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vendor",
        action="append",
        choices=list(VENDOR_DIRS),
        help="Limit to one or more vendor directories (default: all)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    vendors = args.vendor or list(VENDOR_DIRS)
    summary = []
    failures = 0
    for vendor in vendors:
        result = process_vendor(vendor)
        summary.append({"vendor": vendor, "counts": result["counts"]})
        failures += int(result["counts"]["failed"]) + int(result["counts"]["rejected"])

    out = DOCS_ROOT / "download_summary.json"
    _write_json(
        out,
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "vendors": summary,
        },
    )
    print(json.dumps({"summary": summary, "report": str(out.relative_to(REPO_ROOT))}, indent=2))
    return 1 if failures and all(s["counts"]["downloaded"] + s["counts"]["unchanged"] == 0 for s in summary) else 0


if __name__ == "__main__":
    sys.exit(main())
