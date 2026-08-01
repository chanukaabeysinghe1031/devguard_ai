"""Temporary counterfactual workspace manager (never mutates the git repo)."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.ai.counterfactual_remediation.verification._helpers import (
    bound_int,
    original_content,
    proposed_content,
)
from app.domain.counterfactual_remediation.verification_versions import TEMP_WORKSPACE_VERSION

logger = logging.getLogger(__name__)


class PathTraversalError(ValueError):
    """Raised when a candidate path escapes the temporary workspace."""


class TempWorkspaceError(ValueError):
    """Raised when workspace limits or path safety checks fail."""


class TempWorkspaceManager:
    """
    Isolated temp tree for verifier execution.

    Patches are applied ONLY inside tempfile.TemporaryDirectory.
    Never writes under the repository root. Always cleanup().
    """

    version = TEMP_WORKSPACE_VERSION

    def __init__(
        self,
        *,
        max_files: int = 20,
        max_bytes: int = 5_000_000,
        settings: Any | None = None,
        prefix: str = "devguard_cf_verify_",
    ) -> None:
        self._max_files = bound_int(settings, "max_temp_workspace_files", max_files)
        self._max_bytes = bound_int(settings, "max_temp_workspace_bytes", max_bytes)
        self._prefix = prefix
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self.root: Path | None = None
        self.files_written: list[str] = []
        self.bytes_written: int = 0
        self.warnings: list[str] = []
        self._cleaned = False

    def create(self) -> Path:
        self.cleanup()
        self._tmpdir = tempfile.TemporaryDirectory(prefix=self._prefix)
        self.root = Path(self._tmpdir.name).resolve()
        self.files_written = []
        self.bytes_written = 0
        self.warnings = []
        self._cleaned = False
        return self.root

    def cleanup(self) -> None:
        if self._cleaned and self._tmpdir is None and self.root is None:
            return
        self._cleaned = True
        root = self.root
        tmp = self._tmpdir
        self.root = None
        self._tmpdir = None
        self.files_written = []
        self.bytes_written = 0
        if tmp is not None:
            try:
                tmp.cleanup()
            except OSError as exc:
                logger.warning("temp workspace cleanup failed: %s", exc)
        if root is not None and root.exists():
            shutil.rmtree(root, ignore_errors=True)

    def resolve_safe_relative(self, relative_path: str) -> Path:
        if self.root is None:
            raise TempWorkspaceError("workspace not created")
        cleaned = relative_path.strip().lstrip("/").replace("\\", "/")
        if not cleaned or cleaned in {".", "./"}:
            raise PathTraversalError(f"empty relative path: {relative_path}")
        if ".." in Path(cleaned).parts:
            raise PathTraversalError(f"path traversal rejected: {relative_path}")
        if cleaned.startswith("~") or os.path.isabs(cleaned):
            raise PathTraversalError(f"absolute path rejected: {relative_path}")
        target = (self.root / cleaned).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PathTraversalError(f"path escapes workspace: {relative_path}") from exc
        return target

    # Alias used by some callers.
    resolve_safe = resolve_safe_relative

    def write_file(self, relative_path: str, content: str) -> Path:
        if self.root is None:
            raise TempWorkspaceError("workspace not created")
        data = content if isinstance(content, str) else str(content)
        encoded = data.encode("utf-8")
        if len(self.files_written) >= self._max_files:
            raise TempWorkspaceError(f"max files exceeded ({self._max_files})")
        if self.bytes_written + len(encoded) > self._max_bytes:
            raise TempWorkspaceError(f"max bytes exceeded ({self._max_bytes})")
        target = self.resolve_safe_relative(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
        rel = str(target.relative_to(self.root))
        self.files_written.append(rel)
        self.bytes_written += len(encoded)
        return target

    write_text = write_file

    def materialize_candidate(
        self,
        candidate: Any,
        *,
        apply_proposed: bool = True,
        default_name: str = "candidate.txt",
    ) -> list[str]:
        """
        Write candidate fragments into the temp workspace.

        When apply_proposed is True, writes proposed_fragment (counterfactual state).
        Simple full-file write — no repo mutation.
        """
        if self.root is None:
            self.create()

        paths = list(getattr(candidate, "target_paths", None) or [])
        changes = list(getattr(candidate, "changes", None) or [])
        written: list[str] = []

        if changes:
            for index, change in enumerate(changes):
                if isinstance(change, dict):
                    source_path = change.get("source_path") or change.get("target_path")
                    proposed = change.get("proposed_fragment")
                    original = change.get("original_fragment")
                else:
                    source_path = getattr(change, "source_path", None) or getattr(
                        change, "target_path", None
                    )
                    proposed = getattr(change, "proposed_fragment", None)
                    original = getattr(change, "original_fragment", None)

                rel = self._pick_relative_path(
                    source_path=source_path,
                    target_paths=paths,
                    index=index,
                    candidate=candidate,
                    default_name=default_name,
                )
                content = proposed if apply_proposed else original
                if not isinstance(content, str) or not content.strip():
                    content = original if apply_proposed else proposed
                if not isinstance(content, str) or not content.strip():
                    self.warnings.append(f"empty_fragment_for_{rel}")
                    continue
                self.write_file(rel, content)
                written.append(rel)
            return written

        rel = self._pick_relative_path(
            source_path=None,
            target_paths=paths,
            index=0,
            candidate=candidate,
            default_name=default_name,
        )
        content = proposed_content(candidate) if apply_proposed else original_content(candidate)
        if not content.strip():
            content = original_content(candidate) if apply_proposed else proposed_content(candidate)
        if content.strip():
            self.write_file(rel, content)
            written.append(rel)
        else:
            self.warnings.append("no_fragment_content_to_materialize")
            self.write_file(rel, "# empty_counterfactual_candidate\n")
            written.append(rel)
        return written

    # British spelling alias used by earlier draft callers.
    materialise_candidate = materialize_candidate

    def list_files(self) -> list[str]:
        if self.root is None:
            return []
        out: list[str] = []
        for dirpath, _, filenames in os.walk(self.root):
            for name in filenames:
                full = Path(dirpath) / name
                out.append(str(full.relative_to(self.root)))
        return out

    def _pick_relative_path(
        self,
        *,
        source_path: str | None,
        target_paths: list[str],
        index: int,
        candidate: Any,
        default_name: str,
    ) -> str:
        if source_path and str(source_path).strip():
            return self._sanitize_name(str(source_path))
        if index < len(target_paths) and target_paths[index]:
            return self._sanitize_name(str(target_paths[index]))
        if target_paths:
            return self._sanitize_name(str(target_paths[0]))
        artifact = str(getattr(candidate, "artifact_type", None) or "fragment").lower()
        if default_name and default_name != "candidate.txt":
            return self._sanitize_name(default_name)
        return f"candidate_{index}.{_default_extension(artifact)}"

    @staticmethod
    def _sanitize_name(path: str) -> str:
        cleaned = path.strip().lstrip("/").replace("\\", "/")
        while cleaned.startswith("../"):
            cleaned = cleaned[3:]
        if ".." in Path(cleaned).parts:
            cleaned = Path(cleaned).name or "fragment.txt"
        if not cleaned or cleaned in {".", "./"}:
            return "fragment.txt"
        return cleaned

    def __enter__(self) -> TempWorkspaceManager:
        self.create()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.cleanup()


# Alias retained for callers that used the draft name.
TempCounterfactualWorkspace = TempWorkspaceManager


def _default_extension(artifact_type: str) -> str:
    upper = artifact_type.upper()
    if "WORKFLOW" in upper:
        return "yml"
    if "TERRAFORM" in upper or "HCL" in upper:
        return "tf"
    if "IAM" in upper or "POLICY" in upper or "JSON" in upper:
        return "json"
    if "DEPENDENCY" in upper or "LOCK" in upper:
        return "txt"
    return "txt"
