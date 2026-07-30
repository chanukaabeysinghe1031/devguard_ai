"""Safe extraction of GitHub Actions log archives (Phase 5B, ADR-005 §6)."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.application.services.github_log_extractor import extract_log_files
from app.core.config import Settings
from app.domain.exceptions.integration import LogArchiveError


def _settings(**overrides) -> Settings:
    base = {
        "JWT_SECRET_KEY": "test-jwt-secret-key-with-at-least-32-characters",
        "GITHUB_MAX_LOG_ARCHIVE_BYTES": 1_000_000,
        "GITHUB_MAX_EXTRACTED_BYTES": 2_000_000,
        "GITHUB_MAX_LOG_FILES": 3,
        "GITHUB_MAX_SINGLE_LOG_BYTES": 100_000,
    }
    base.update(overrides)
    return Settings(**base)


def _archive(entries: list[tuple[str, bytes]], *, symlinks: set[str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            info = zipfile.ZipInfo(name)
            if symlinks and name in symlinks:
                info.external_attr = (0o120777 & 0xFFFF) << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def test_extracts_text_log_entries() -> None:
    archive = _archive(
        [
            ("1_build.log", b"error: build failed\n"),
            ("build/2_Set up job.txt", b"job started\n"),
        ]
    )
    results = extract_log_files(archive, settings=_settings())

    assert len(results) == 2
    names = [name for name, _ in results]
    assert "1_build.log" in names
    assert "build_2_Set_up_job.txt" in names
    assert results[0][1] == b"error: build failed\n"


def test_path_traversal_entry_rejected() -> None:
    archive = _archive([("../../etc/passwd.log", b"root:x:0:0\n")])
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_UNSAFE_PATH"


def test_absolute_path_entry_rejected() -> None:
    archive = _archive([("/etc/shadow.log", b"secret\n")])
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_UNSAFE_PATH"


def test_symlink_entry_rejected() -> None:
    archive = _archive([("link.log", b"/etc/passwd")], symlinks={"link.log"})
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_SYMLINK"


def test_executable_entry_rejected() -> None:
    archive = _archive([("1_build.log", b"ok\n"), ("payload.sh", b"rm -rf /\n")])
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_EXECUTABLE"


def test_non_text_entries_are_skipped_not_returned() -> None:
    archive = _archive([("1_build.log", b"failure\n"), ("report.json", b"{}")])
    results = extract_log_files(archive, settings=_settings())
    assert [name for name, _ in results] == ["1_build.log"]


def test_file_count_limit_enforced() -> None:
    archive = _archive([(f"{index}_step.log", b"line\n") for index in range(10)])
    results = extract_log_files(archive, settings=_settings(GITHUB_MAX_LOG_FILES=3))
    assert len(results) == 3


def test_compressed_size_limit_enforced() -> None:
    archive = _archive([("1_build.log", b"x" * 5_000)])
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings(GITHUB_MAX_LOG_ARCHIVE_BYTES=10))
    assert exc.value.error_code == "LOG_ARCHIVE_TOO_LARGE"


def test_archive_bomb_expansion_limit_enforced() -> None:
    archive = _archive([("1_build.log", b"a" * 500_000)])
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings(GITHUB_MAX_EXTRACTED_BYTES=1_000))
    assert exc.value.error_code == "LOG_ARCHIVE_TOO_LARGE"


def test_invalid_zip_rejected() -> None:
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(b"not a zip file", settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_INVALID"


def test_empty_archive_rejected() -> None:
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(b"", settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_EMPTY"


def test_archive_without_log_entries_rejected() -> None:
    archive = _archive([("metadata.json", b"{}")])
    with pytest.raises(LogArchiveError) as exc:
        extract_log_files(archive, settings=_settings())
    assert exc.value.error_code == "LOG_ARCHIVE_EMPTY"


def test_fake_provider_archive_is_extractable() -> None:
    from app.infrastructure.integrations.fake_github_provider import build_fake_log_archive

    results = extract_log_files(build_fake_log_archive(), settings=_settings())
    assert any(b"COPY failed" in content for _, content in results)
