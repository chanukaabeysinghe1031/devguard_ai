"""Unit tests for official documentation research corpus helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.ai.rag.chunker import chunk_markdown

REPO_ROOT = Path(__file__).resolve().parents[2]
for _candidate in (
    Path(__file__).resolve().parents[2],
    Path(__file__).resolve().parents[1].parent,
    Path("/workspace"),
):
    if (_candidate / "scripts" / "dataset").exists():
        REPO_ROOT = _candidate
        break
SCRIPT_DIR = REPO_ROOT / "scripts" / "dataset"
if not SCRIPT_DIR.exists():
    pytest.skip("dataset scripts not mounted in this environment", allow_module_level=True)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from chunk_utils import chunk_official_document  # noqa: E402
from official_docs_duplicates import DuplicateTracker  # noqa: E402
from official_docs_metadata import (  # noqa: E402
    build_chunk_records,
    build_document_record,
    chroma_metadata_from_chunk,
    document_hash,
)
from official_docs_parser import html_to_markdown  # noqa: E402

SAMPLE_HTML = """
<html>
<head><title>IAM Access Denied</title></head>
<body>
<nav class="navbar">Home</nav>
<main>
  <h1>Troubleshoot access denied</h1>
  <p>An AccessDenied error means the principal lacks permission.</p>
  <h2>Check IAM policies</h2>
  <ul>
    <li>Verify Allow statements</li>
    <li>Check Deny statements</li>
  </ul>
  <pre><code>aws sts get-caller-identity</code></pre>
  <table><tr><th>Code</th><th>Meaning</th></tr>
  <tr><td>AccessDenied</td><td>Missing permission</td></tr></table>
</main>
<footer>Cookie banner ignore me</footer>
</body>
</html>
"""


def test_parser_extracts_main_content_and_structure() -> None:
    parsed = html_to_markdown(SAMPLE_HTML)
    md = parsed["markdown"]
    assert parsed["title"] == "IAM Access Denied"
    assert "AccessDenied" in md
    assert "Check IAM policies" in md
    assert "```" in md
    assert "Cookie banner" not in md


def test_parser_extracts_aws_style_content_id() -> None:
    html = """
    <html><head><title>AWS IAM</title></head><body>
    <div id="sidebar" class="sidebar">nav junk</div>
    <div id="main-col-body">
      <h1>Troubleshoot access denied</h1>
      <p>An AccessDenied error means the IAM principal lacks permission for the action.</p>
      <p>Check the resource-based policy and identity-based policy.</p>
    </div>
    </body></html>
    """
    parsed = html_to_markdown(html)
    assert "AccessDenied" in parsed["markdown"]
    assert len(parsed["markdown"]) > 80
    assert "nav junk" not in parsed["markdown"]


def test_metadata_and_version_fields() -> None:
    source = {
        "document_id": "doc-aws-iam-access-denied",
        "vendor": "AWS",
        "title": "Troubleshoot access denied",
        "url": "https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html",
        "version": "IAM User Guide",
        "licence": "Amazon Web Services Documentation",
        "technology": "aws",
        "category": "aws_permission_failure",
        "language": "en",
    }
    parsed = html_to_markdown(SAMPLE_HTML)
    record = build_document_record(
        source=source,
        markdown=parsed["markdown"],
        headings=parsed["headings"],
        retrieved_at="2026-07-28T00:00:00+00:00",
    )
    assert record["source_type"] == "official_documentation"
    assert record["document_hash"] == document_hash(parsed["markdown"])
    assert record["vendor"] == "AWS"
    assert record["technology"] == "aws"
    assert "Troubleshoot" in record["title"] or record["title"]


def test_chunking_reuses_shared_chunker_bounds() -> None:
    source = {
        "document_id": "doc-docker-test",
        "vendor": "Docker",
        "title": "Dockerfile COPY",
        "url": "https://docs.docker.com/reference/dockerfile/",
        "version": "Docker Docs",
        "technology": "docker",
        "category": "docker_failure",
        "language": "en",
    }
    body = "# COPY\n\n" + ("The COPY instruction fails when the source is missing.\n\n" * 40)
    record = build_document_record(source=source, markdown=body, headings=[])
    chunks = chunk_official_document(record, max_chars=900, overlap=100)
    assert chunks
    assert all(c["source_type"] == "official_documentation" for c in chunks)
    assert all(c["vendor"] == "Docker" for c in chunks)
    assert all(c["url"] == source["url"] for c in chunks)
    assert all(600 <= c["char_count"] <= 1000 or c["char_count"] < 600 for c in chunks)
    # Shared algorithm also exposed directly.
    direct = chunk_markdown(body, max_chars=900, overlap=100)
    assert direct


def test_duplicate_detection_skip_update_reject() -> None:
    tracker = DuplicateTracker()
    chunk = {
        "chunk_id": "doc-a-c000",
        "text": "hello world",
        "chunk_hash": "abc",
        "document_hash": "doc",
        "url": "https://example.com/a",
    }
    assert tracker.classify_chunk(chunk) == "index"
    assert tracker.classify_chunk(chunk, existing_ids={"doc-a-c000"}) == "skip"
    updated = dict(chunk)
    updated["chunk_hash"] = "changed"
    assert tracker.classify_chunk(updated, existing_ids={"doc-a-c000"}) == "update"
    assert tracker.classify_chunk({"chunk_id": "", "text": ""}) == "reject"
    summary = tracker.summary()
    assert summary["indexed"] == 1
    assert summary["skipped"] == 1
    assert summary["updated"] == 1
    assert summary["rejected"] == 1


def test_chroma_metadata_contract() -> None:
    meta = chroma_metadata_from_chunk(
        {
            "document_id": "doc-x",
            "chunk_id": "doc-x-c000",
            "vendor": "AWS",
            "technology": "aws",
            "category": "aws_permission_failure",
            "section": "IAM",
            "url": "https://docs.aws.amazon.com/x",
            "version": "1",
            "document_hash": "h1",
            "chunk_hash": "h2",
        }
    )
    assert meta["source_type"] == "official_documentation"
    assert meta["vendor"] == "AWS"
    assert meta["document_id"] == "doc-x"


def test_source_lists_are_official_hosts_only() -> None:
    docs_root = REPO_ROOT / "datasets" / "raw" / "docs"
    allowed_suffixes = (
        "docs.aws.amazon.com",
        "docs.docker.com",
        "developer.hashicorp.com",
        "docs.github.com",
        "kubernetes.io",
        "docs.python.org",
        "docs.oracle.com",
        "maven.apache.org",
        "docs.gradle.org",
        "nodejs.org",
        "docs.npmjs.com",
    )
    for vendor_dir in docs_root.iterdir():
        if not vendor_dir.is_dir():
            continue
        source_list = vendor_dir / "source_list.json"
        if not source_list.exists():
            continue
        for item in json.loads(source_list.read_text(encoding="utf-8")):
            host = item["url"].split("/")[2]
            assert any(host == s or host.endswith("." + s) for s in allowed_suffixes), item["url"]
            assert item["document_id"]
            assert item["vendor"]
            assert item.get("licence")


def test_corpus_version_constant() -> None:
    # Pipeline module defines the frozen research corpus version for this phase.
    import run_official_docs_pipeline as pipeline

    assert pipeline.CORPUS_VERSION == "0.5.0-official-docs"
    assert pipeline.DEFAULT_COLLECTION == "devguard_research_knowledge"
    assert pipeline.PRODUCT_COLLECTION == "devguard_knowledge"


def test_build_chunk_records_inherit_metadata() -> None:
    from app.ai.rag.chunker import TextChunk

    document = {
        "document_id": "doc-t",
        "vendor": "Terraform",
        "technology": "terraform",
        "category": "terraform_failure",
        "failure_category": "terraform_failure",
        "version": "1",
        "url": "https://developer.hashicorp.com/terraform/language/resources/syntax",
        "document_hash": "dhash",
        "heading_hierarchy": ["Resources"],
        "section": "documentation",
    }
    chunks = build_chunk_records(
        document=document,
        text_chunks=[
            TextChunk(index=0, heading="Resources", content="# Resources\n\nbody", token_count=2)
        ],
    )
    assert chunks[0]["chunk_id"] == "doc-t-c000"
    assert chunks[0]["source_type"] == "official_documentation"


def test_downloader_rejects_unapproved_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import download_official_docs as downloader

    vendor = tmp_path / "aws"
    vendor.mkdir()
    (vendor / "manifest.json").write_text(
        json.dumps({"approved_hosts": ["docs.aws.amazon.com"]}),
        encoding="utf-8",
    )
    (vendor / "source_list.json").write_text(
        json.dumps(
            [
                {
                    "document_id": "doc-bad",
                    "vendor": "AWS",
                    "title": "Bad",
                    "url": "https://medium.com/not-allowed",
                    "technology": "aws",
                    "category": "aws_permission_failure",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(downloader, "DOCS_ROOT", tmp_path)
    result = downloader.process_vendor("aws")
    assert result["entries"][0]["status"] == "rejected_host"
