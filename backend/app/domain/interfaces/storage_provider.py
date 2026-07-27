"""File storage provider contract (domain boundary)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import PurePosixPath


class FileStorage(ABC):
    """Abstract file storage. Implementations must never execute uploaded content."""

    @abstractmethod
    async def save(self, *, relative_path: str, data: bytes) -> str:
        """Persist bytes and return an opaque storage key (not a filesystem URL)."""

    @abstractmethod
    async def read(self, *, relative_path: str) -> bytes:
        """Read stored bytes by opaque key."""

    @abstractmethod
    async def delete(self, *, relative_path: str) -> None:
        """Delete stored object if present. Idempotent."""

    @abstractmethod
    async def exists(self, *, relative_path: str) -> bool:
        """Return True when the object exists."""


def assert_safe_relative_path(relative_path: str) -> PurePosixPath:
    """Reject path traversal and absolute paths in storage keys."""
    if not relative_path or relative_path.strip() != relative_path:
        raise ValueError("Storage path must be a non-empty relative key.")
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or path.parts[0] == "":
        raise ValueError("Storage path must not contain traversal or absolute segments.")
    return path
