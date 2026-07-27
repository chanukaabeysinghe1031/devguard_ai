"""Upload validation helpers. Never trust client filenames or MIME types alone."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.domain.enums import FileType
from app.domain.exceptions.upload import EmptyFileError, UnsupportedFileTypeError

# MASTER_ARCHITECTURE §14.1 — ZIP deferred (ADR-011).
_EXTENSION_TO_TYPE: dict[str, FileType] = {
    ".log": FileType.LOG,
    ".txt": FileType.LOG,
    ".yaml": FileType.WORKFLOW_YAML,
    ".yml": FileType.WORKFLOW_YAML,
    ".tf": FileType.TERRAFORM,
    ".tfvars": FileType.TERRAFORM,
    ".json": FileType.JSON,
}

_DEFERRED_EXTENSIONS = frozenset({".zip"})

_EXECUTABLE_EXTENSIONS = frozenset(
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

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._\-]+")


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    original_filename: str
    extension: str
    file_type: FileType


def sanitize_original_filename(filename: str | None) -> str:
    """Strip path components and unsafe characters from a client filename."""
    raw = (filename or "upload").replace("\\", "/")
    name = PurePosixPath(raw).name.strip() or "upload"
    if name in {".", ".."}:
        name = "upload"
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", name)
    return cleaned[:200]


def detect_file_type(filename: str) -> tuple[str, FileType]:
    """Map extension to FileType. Rejects ZIP and executables."""
    path = PurePosixPath(filename.lower())
    suffix = path.suffix.lower()
    if suffix in _DEFERRED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            "ZIP uploads are deferred (ADR-011). Upload individual log/YAML/Terraform/JSON files."
        )
    if suffix in _EXECUTABLE_EXTENSIONS:
        raise UnsupportedFileTypeError("Executable file types are not allowed.")
    file_type = _EXTENSION_TO_TYPE.get(suffix)
    if file_type is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file extension '{suffix or '(none)'}'. "
            "Allowed: .log, .txt, .yaml, .yml, .tf, .tfvars, .json"
        )
    return suffix, file_type


def ensure_non_empty(data: bytes) -> None:
    if not data:
        raise EmptyFileError()


def looks_like_binary(data: bytes) -> bool:
    """Heuristic: null bytes or high ratio of non-text bytes."""
    if b"\x00" in data[:8192]:
        return True
    sample = data[:4096]
    if not sample:
        return False
    non_text = sum(1 for b in sample if b < 9 or (13 < b < 32) or b == 127)
    return (non_text / len(sample)) > 0.30


def decode_text_content(data: bytes) -> str:
    """Decode as UTF-8; reject clearly binary payloads."""
    if looks_like_binary(data):
        raise UnsupportedFileTypeError("Binary content is not allowed for this file type.")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedFileTypeError(
            "File content must be valid UTF-8 text."
        ) from exc
