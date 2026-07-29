"""Duplicate detection helpers for official documentation indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DuplicateTracker:
    """Track document / chunk / URL / embedding identity duplicates."""

    seen_document_hashes: set[str] = field(default_factory=set)
    seen_chunk_hashes: set[str] = field(default_factory=set)
    seen_urls: set[str] = field(default_factory=set)
    seen_chunk_ids: set[str] = field(default_factory=set)
    indexed: int = 0
    skipped: int = 0
    updated: int = 0
    rejected: int = 0

    def register_existing(self, chunks: list[dict[str, Any]]) -> None:
        for chunk in chunks:
            if chunk.get("chunk_id"):
                self.seen_chunk_ids.add(str(chunk["chunk_id"]))
            if chunk.get("chunk_hash"):
                self.seen_chunk_hashes.add(str(chunk["chunk_hash"]))
            if chunk.get("document_hash"):
                self.seen_document_hashes.add(str(chunk["document_hash"]))
            if chunk.get("url"):
                self.seen_urls.add(str(chunk["url"]))

    def classify_chunk(
        self,
        chunk: dict[str, Any],
        *,
        existing_ids: set[str] | None = None,
    ) -> str:
        """Return one of: index, skip, update, reject."""
        chunk_id = str(chunk.get("chunk_id") or "")
        text = str(chunk.get("text") or "").strip()
        if not chunk_id or not text:
            self.rejected += 1
            return "reject"

        url = str(chunk.get("url") or "")
        doc_hash = str(chunk.get("document_hash") or "")
        c_hash = str(chunk.get("chunk_hash") or "")

        existing = existing_ids or set()
        if chunk_id in self.seen_chunk_ids or chunk_id in existing:
            if c_hash and c_hash in self.seen_chunk_hashes:
                self.skipped += 1
                return "skip"
            self.updated += 1
            self.seen_chunk_ids.add(chunk_id)
            if c_hash:
                self.seen_chunk_hashes.add(c_hash)
            if doc_hash:
                self.seen_document_hashes.add(doc_hash)
            if url:
                self.seen_urls.add(url)
            return "update"

        if c_hash and c_hash in self.seen_chunk_hashes:
            self.skipped += 1
            return "skip"

        self.indexed += 1
        self.seen_chunk_ids.add(chunk_id)
        if c_hash:
            self.seen_chunk_hashes.add(c_hash)
        if doc_hash:
            self.seen_document_hashes.add(doc_hash)
        if url:
            self.seen_urls.add(url)
        return "index"

    def summary(self) -> dict[str, int]:
        return {
            "indexed": self.indexed,
            "skipped": self.skipped,
            "updated": self.updated,
            "rejected": self.rejected,
        }
