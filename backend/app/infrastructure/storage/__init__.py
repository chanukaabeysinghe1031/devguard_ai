"""Storage provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.domain.exceptions.upload import StorageConfigurationError
from app.domain.interfaces.storage_provider import FileStorage
from app.infrastructure.storage.local_storage import LocalFileStorage


@lru_cache
def get_file_storage() -> FileStorage:
    settings = get_settings()
    return build_file_storage(settings)


def build_file_storage(settings: Settings) -> FileStorage:
    backend = (settings.file_storage_backend or "local").strip().lower()
    if backend == "local":
        path = (settings.file_storage_path or "").strip()
        if not path:
            raise StorageConfigurationError(
                "FILE_STORAGE_PATH is required when FILE_STORAGE_BACKEND=local."
            )
        return LocalFileStorage(path)
    if backend in {"s3", "object", "minio"}:
        from app.infrastructure.storage.object_storage import ObjectFileStorage

        return ObjectFileStorage()
    raise StorageConfigurationError(f"Unsupported FILE_STORAGE_BACKEND '{backend}'.")


def reset_file_storage_cache() -> None:
    get_file_storage.cache_clear()
