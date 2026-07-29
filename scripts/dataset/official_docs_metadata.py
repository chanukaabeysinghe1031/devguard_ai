"""Metadata builders for official documentation records and chunks."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any


def document_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned[:80] or "doc"


def build_document_record(
    *,
    source: dict[str, Any],
    markdown: str,
    retrieved_at: str | None = None,
    title_override: str | None = None,
    headings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    title = title_override or source.get("title") or source.get("document_id")
    body_hash = document_hash(markdown)
    retrieved = retrieved_at or datetime.now(UTC).isoformat()
    hierarchy = [h.get("text") for h in (headings or []) if h.get("text")]
    return {
        "document_id": source["document_id"],
        "vendor": source.get("vendor"),
        "technology": source.get("technology"),
        "category": source.get("category"),
        "failure_category": source.get("category"),
        "version": source.get("version"),
        "url": source.get("url"),
        "title": title,
        "language": source.get("language") or "en",
        "licence": source.get("licence"),
        "section": "documentation",
        "heading_hierarchy": hierarchy,
        "document_hash": body_hash,
        "source_type": "official_documentation",
        "retrieved_at": retrieved,
        "markdown": markdown,
        "char_count": len(markdown),
        "secrets_masked": True,
    }


def build_chunk_records(
    *,
    document: dict[str, Any],
    text_chunks: list[Any],
) -> list[dict[str, Any]]:
    """Map ``chunk_markdown`` TextChunk objects into research chunk JSON."""
    out: list[dict[str, Any]] = []
    doc_id = document["document_id"]
    for chunk in text_chunks:
        text = chunk.content
        chunk_id = f"{doc_id}-c{chunk.index:03d}"
        out.append(
            {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "knowledge_id": doc_id,
                "incident_id": doc_id,
                "text": text,
                "section": chunk.heading or document.get("section") or "documentation",
                "heading_hierarchy": document.get("heading_hierarchy") or [],
                "char_count": len(text),
                "chunk_hash": chunk_hash(text),
                "document_hash": document.get("document_hash"),
                "vendor": document.get("vendor"),
                "technology": document.get("technology"),
                "category": document.get("category"),
                "failure_category": document.get("failure_category") or document.get("category"),
                "version": document.get("version"),
                "url": document.get("url"),
                "language": document.get("language") or "en",
                "source_type": "official_documentation",
                "secrets_masked": True,
            }
        )
    return out


def chroma_metadata_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": chunk.get("document_id") or "",
        "knowledge_id": chunk.get("knowledge_id") or "",
        "incident_id": chunk.get("incident_id") or "",
        "vendor": chunk.get("vendor") or "",
        "technology": chunk.get("technology") or "",
        "category": chunk.get("category") or "",
        "failure_category": chunk.get("failure_category") or "",
        "section": chunk.get("section") or "",
        "url": chunk.get("url") or "",
        "version": chunk.get("version") or "",
        "document_status": "active",
        "source_type": "official_documentation",
        "document_hash": chunk.get("document_hash") or "",
        "chunk_hash": chunk.get("chunk_hash") or "",
    }
