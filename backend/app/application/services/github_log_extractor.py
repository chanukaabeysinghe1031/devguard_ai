"""Safe extraction of GitHub Actions workflow log archives (ADR-005 §6).

Defends against archive bombs, path traversal, symlinks, and executable
payloads. Only plain-text log entries are returned; everything else is skipped.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import PurePosixPath

import structlog

from app.core.config import Settings
from app.domain.exceptions.integration import LogArchiveError

logger = structlog.get_logger(__name__)

_ALLOWED_SUFFIXES = frozenset({".log", ".txt"})
_EXECUTABLE_SUFFIXES = frozenset(
    {
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bat",
        ".cmd",
        ".ps1",
        ".sh",
        ".bin",
        ".com",
        ".msi",
        ".dmg",
        ".apk",
        ".jar",
        ".wasm",
    }
)
# Unix mode bits stored in the ZIP external attributes.
_S_IFLNK = 0o120000
_S_IFMT = 0o170000


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return bool(mode) and (mode & _S_IFMT) == _S_IFLNK


def _is_unsafe_path(name: str) -> bool:
    normalised = name.replace("\\", "/")
    if normalised.startswith("/") or normalised.startswith("~"):
        return True
    if ":" in normalised.split("/")[0] and len(normalised.split("/")[0]) == 2:
        return True  # Windows drive letter, e.g. C:/
    return any(part == ".." for part in PurePosixPath(normalised).parts)


def _safe_entry_name(name: str) -> str:
    """Flatten a ZIP entry path into a single safe filename."""
    normalised = name.replace("\\", "/").strip("/")
    parts = [part for part in normalised.split("/") if part not in ("", ".")]
    joined = "_".join(parts) or "workflow.log"
    cleaned = "".join(char if char.isalnum() or char in "._- " else "_" for char in joined)
    cleaned = cleaned.strip().replace(" ", "_")[:180]
    return cleaned or "workflow.log"


def extract_log_files(
    archive_bytes: bytes,
    *,
    settings: Settings,
) -> list[tuple[str, bytes]]:
    """Return ``(safe_name, content)`` pairs for text log entries in the archive."""
    if not archive_bytes:
        raise LogArchiveError("Workflow log archive is empty.", error_code="LOG_ARCHIVE_EMPTY")
    if len(archive_bytes) > settings.github_max_log_archive_bytes:
        raise LogArchiveError(
            "Workflow log archive exceeds the compressed size limit.",
            error_code="LOG_ARCHIVE_TOO_LARGE",
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise LogArchiveError(
            "Workflow log archive is not a valid ZIP file.",
            error_code="LOG_ARCHIVE_INVALID",
        ) from exc

    declared_total = sum(max(info.file_size, 0) for info in archive.infolist())
    if declared_total > settings.github_max_extracted_bytes:
        raise LogArchiveError(
            "Workflow log archive expands beyond the extraction limit.",
            error_code="LOG_ARCHIVE_TOO_LARGE",
        )

    results: list[tuple[str, bytes]] = []
    used_names: set[str] = set()
    extracted_total = 0

    with archive:
        for info in archive.infolist():
            if len(results) >= settings.github_max_log_files:
                logger.info("github_log_archive_truncated", limit=settings.github_max_log_files)
                break
            if info.is_dir():
                continue
            if _is_unsafe_path(info.filename):
                raise LogArchiveError(
                    "Workflow log archive contains an unsafe entry path.",
                    error_code="LOG_ARCHIVE_UNSAFE_PATH",
                )
            if _is_symlink(info):
                raise LogArchiveError(
                    "Workflow log archive contains a symbolic link.",
                    error_code="LOG_ARCHIVE_SYMLINK",
                )

            suffix = PurePosixPath(info.filename.lower()).suffix
            if suffix in _EXECUTABLE_SUFFIXES:
                raise LogArchiveError(
                    "Workflow log archive contains an executable entry.",
                    error_code="LOG_ARCHIVE_EXECUTABLE",
                )
            if suffix not in _ALLOWED_SUFFIXES:
                continue
            if info.file_size > settings.github_max_single_log_bytes:
                logger.info("github_log_entry_skipped", reason="entry_too_large")
                continue

            with archive.open(info) as handle:
                content = handle.read(settings.github_max_single_log_bytes + 1)
            if len(content) > settings.github_max_single_log_bytes:
                logger.info("github_log_entry_skipped", reason="entry_too_large")
                continue

            extracted_total += len(content)
            if extracted_total > settings.github_max_extracted_bytes:
                raise LogArchiveError(
                    "Workflow log archive expands beyond the extraction limit.",
                    error_code="LOG_ARCHIVE_TOO_LARGE",
                )
            if not content.strip():
                continue

            name = _safe_entry_name(info.filename)
            if not PurePosixPath(name).suffix:
                name = f"{name}.log"
            candidate = name
            counter = 1
            while candidate in used_names:
                stem = PurePosixPath(name).stem
                candidate = f"{stem}_{counter}{PurePosixPath(name).suffix}"
                counter += 1
            used_names.add(candidate)
            results.append((candidate, content))

    if not results:
        raise LogArchiveError(
            "Workflow log archive contains no readable log files.",
            error_code="LOG_ARCHIVE_EMPTY",
        )
    return results
