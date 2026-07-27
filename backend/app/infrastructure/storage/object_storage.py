"""Object-storage compatible stub for future production backends."""

from __future__ import annotations

from app.domain.interfaces.storage_provider import FileStorage


class ObjectFileStorage(FileStorage):
    """Placeholder for S3-compatible storage. Not used in the MSc MVP."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise NotImplementedError(
            "Object storage is not enabled in the MVP. Use FILE_STORAGE_BACKEND=local."
        )

    async def save(self, *, relative_path: str, data: bytes) -> str:
        raise NotImplementedError

    async def read(self, *, relative_path: str) -> bytes:
        raise NotImplementedError

    async def delete(self, *, relative_path: str) -> None:
        raise NotImplementedError

    async def exists(self, *, relative_path: str) -> bool:
        raise NotImplementedError
