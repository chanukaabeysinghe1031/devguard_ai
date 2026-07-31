"""Deterministic retrieval cache key builder and optional in-memory cache."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any


def build_retrieval_cache_key(
    *,
    organization_id: str,
    project_id: str | None,
    knowledge_base_version: str,
    embedding_model_version: str,
    adapter_name: str,
    adapter_version: str,
    normalized_query: str,
    source_filters: list[str],
    repository_commit: str | None,
    artifact_constraints: dict[str, Any] | None,
    top_k: int,
    plan_version: str,
) -> str:
    """Build a stable SHA-256 cache key. Never include secret values."""
    payload = {
        "organization_id": organization_id,
        "project_id": project_id or "",
        "knowledge_base_version": knowledge_base_version,
        "embedding_model_version": embedding_model_version,
        "adapter_name": adapter_name,
        "adapter_version": adapter_version,
        "normalized_query": normalized_query,
        "source_filters": sorted(source_filters),
        "repository_commit": repository_commit or "",
        "artifact_constraints": artifact_constraints or {},
        "top_k": int(top_k),
        "plan_version": plan_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class InMemoryRetrievalCache:
    """Process-local optional cache keyed by :func:`build_retrieval_cache_key`."""

    def __init__(self, *, max_entries: int = 256, ttl_seconds: float = 600.0) -> None:
        self._max = max(1, max_entries)
        self._ttl = max(1.0, ttl_seconds)
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < now:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._store) >= self._max:
                # Evict oldest by expiry.
                oldest_key = min(self._store.items(), key=lambda kv: kv[1][0])[0]
                del self._store[oldest_key]
            self._store[key] = (now + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
