"""Provider interfaces for extensible platform support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedPipelineMetadata:
    """Normalised metadata extracted from any CI/CD platform."""

    platform: str
    pipeline_name: str | None = None
    job_name: str | None = None
    workflow_file: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedIaCResource:
    """Normalised IaC resource representation."""

    resource_type: str
    resource_name: str
    file_path: str
    attributes: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)


class CICDProvider(ABC):
    """Abstract CI/CD log and workflow parser."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique platform identifier (e.g. github_actions)."""

    @abstractmethod
    def parse_log(self, log_content: str) -> ParsedPipelineMetadata:
        """Extract pipeline metadata from raw log content."""

    @abstractmethod
    def parse_workflow(self, workflow_content: str) -> dict[str, Any]:
        """Parse workflow definition into normalised structure."""

    @abstractmethod
    def extract_failure_context(self, log_content: str) -> list[str]:
        """Extract lines relevant to failure analysis."""


class IaCProvider(ABC):
    """Abstract Infrastructure-as-Code parser."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique IaC provider identifier (e.g. terraform)."""

    @abstractmethod
    def parse_files(self, file_contents: dict[str, str]) -> list[ParsedIaCResource]:
        """Parse one or more IaC files."""

    @abstractmethod
    def validate_syntax(self, content: str, filename: str) -> list[str]:
        """Return syntax error messages; empty if valid."""


class CloudProvider(ABC):
    """Abstract cloud platform analyser."""

    @property
    @abstractmethod
    def cloud_name(self) -> str:
        """Unique cloud identifier (e.g. aws)."""

    @abstractmethod
    def detect_services(self, log_content: str) -> list[str]:
        """Detect referenced cloud services from logs."""

    @abstractmethod
    def extract_permission_errors(self, log_content: str) -> list[str]:
        """Extract IAM/permission-related error messages."""
