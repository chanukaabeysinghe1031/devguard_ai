"""Local filesystem storage for development."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.domain.exceptions.upload import StorageConfigurationError
from app.domain.interfaces.storage_provider import FileStorage, assert_safe_relative_path


class LocalFileStorage(FileStorage):
    """Stores files under a configured root directory using opaque relative keys."""

    def __init__(self, root_path: str | Path) -> None:
        root = Path(root_path).expanduser().resolve()
        if not str(root):
            raise StorageConfigurationError("FILE_STORAGE_PATH is required for local storage.")
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        safe = assert_safe_relative_path(relative_path)
        full = (self._root / Path(*safe.parts)).resolve()
        try:
            full.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("Resolved storage path escapes storage root.") from exc
        return full

    async def save(self, *, relative_path: str, data: bytes) -> str:
        path = self._resolve(relative_path)
        await asyncio.to_thread(self._write, path, data)
        return relative_path

    async def read(self, *, relative_path: str) -> bytes:
        path = self._resolve(relative_path)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, *, relative_path: str) -> None:
        path = self._resolve(relative_path)

        def _unlink() -> None:
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_unlink)

    async def exists(self, *, relative_path: str) -> bool:
        path = self._resolve(relative_path)
        return await asyncio.to_thread(path.exists)

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".partial")
        try:
            tmp.write_bytes(data)
            tmp.replace(path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
