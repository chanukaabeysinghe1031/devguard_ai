"""Build markdown knowledge docs and chunk them for embedding."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.rag.chunker import chunk_markdown  # noqa: E402


def knowledge_to_markdown(record: dict[str, Any]) -> str:
    parts = [
        f"# {record.get('title') or record.get('knowledge_id')}",
        "",
        f"- technology: {record.get('technology')}",
        f"- failure_category: {record.get('failure_category')}",
        f"- repository: {record.get('repository')}",
        f"- issue_url: {record.get('issue_url')}",
        f"- knowledge_id: {record.get('knowledge_id')}",
        f"- incident_id: {record.get('incident_id')}",
        "",
        "## Symptoms",
        str(record.get("symptoms") or "").strip() or "(not provided)",
        "",
    ]
    if record.get("root_cause"):
        parts.extend(["## Root cause", str(record["root_cause"]).strip(), ""])
    if record.get("resolution"):
        parts.extend(["## Resolution", str(record["resolution"]).strip(), ""])
    return "\n".join(parts).strip() + "\n"


def chunk_knowledge_record(
    record: dict[str, Any],
    *,
    max_chars: int = 900,
) -> list[dict[str, Any]]:
    markdown = knowledge_to_markdown(record)
    text_chunks = chunk_markdown(markdown, max_chars=max_chars)
    out: list[dict[str, Any]] = []
    for chunk in text_chunks:
        chunk_id = f"{record['knowledge_id']}-c{chunk.index:03d}"
        out.append(
            {
                "chunk_id": chunk_id,
                "knowledge_id": record.get("knowledge_id"),
                "incident_id": record.get("incident_id"),
                "text": chunk.content,
                "section": chunk.heading,
                "char_count": len(chunk.content),
                "technology": record.get("technology"),
                "failure_category": record.get("failure_category"),
                "repository": record.get("repository"),
                "issue_url": record.get("issue_url"),
                "issue_number": _issue_number(record.get("issue_url"), record.get("incident_id")),
                "source_type": "public_github_issue",
                "extraction_confidence": record.get("extraction_confidence"),
                "secrets_masked": True,
            }
        )
    return out


def official_document_to_markdown(document: dict[str, Any]) -> str:
    """Wrap an official documentation record as heading-aware markdown."""
    title = document.get("title") or document.get("document_id")
    parts = [
        f"# {title}",
        "",
        f"- vendor: {document.get('vendor')}",
        f"- technology: {document.get('technology')}",
        f"- category: {document.get('category')}",
        f"- version: {document.get('version')}",
        f"- url: {document.get('url')}",
        f"- document_id: {document.get('document_id')}",
        f"- source_type: official_documentation",
        "",
        str(document.get("markdown") or "").strip(),
        "",
    ]
    return "\n".join(parts).strip() + "\n"


def chunk_official_document(
    document: dict[str, Any],
    *,
    max_chars: int = 900,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    """Chunk official docs via the shared ``chunk_markdown`` algorithm."""
    from official_docs_metadata import build_chunk_records

    if max_chars < 600 or max_chars > 1000:
        raise ValueError("official documentation max_chars must be in 600–1000")
    markdown = official_document_to_markdown(document)
    text_chunks = chunk_markdown(markdown, max_chars=max_chars, overlap=overlap)
    return build_chunk_records(document=document, text_chunks=text_chunks)


def _issue_number(issue_url: Any, incident_id: Any) -> int | None:
    if isinstance(issue_url, str):
        match = re.search(r"/issues/(\d+)", issue_url)
        if match:
            return int(match.group(1))
    if isinstance(incident_id, str):
        match = re.search(r"-(\d+)$", incident_id)
        if match:
            return int(match.group(1))
    return None
