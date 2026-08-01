"""Registry for Phase 6A structured artifact parsers."""

from __future__ import annotations

from app.ai.artifacts.parsers.aws_policy_parser import AwsPolicyParser
from app.ai.artifacts.parsers.base import StructuredArtifactParser
from app.ai.artifacts.parsers.change_parser import ChangeParser
from app.ai.artifacts.parsers.log_parser import LogParser
from app.ai.artifacts.parsers.terraform_parser import TerraformParser
from app.ai.artifacts.parsers.terraform_plan_parser import TerraformPlanParser
from app.ai.artifacts.parsers.workflow_parser import WorkflowParser
from app.domain.artifacts.enums import ArtifactKind, ParseStatus
from app.domain.artifacts.models import DiagnosticMessage, StructuredParseResult


class ParserRegistry:
    """Name-indexed registry of structured artifact parsers."""

    def __init__(self) -> None:
        self._parsers: dict[str, StructuredArtifactParser] = {}

    def register(self, parser: StructuredArtifactParser) -> None:
        self._parsers[parser.name] = parser

    def get(self, name: str) -> StructuredArtifactParser | None:
        return self._parsers.get(name)

    def list_parsers(self) -> list[StructuredArtifactParser]:
        return list(self._parsers.values())

    def parsers_for(self, kind: ArtifactKind) -> list[StructuredArtifactParser]:
        return [p for p in self._parsers.values() if p.supports(kind)]

    def parse_all(
        self,
        content: str,
        *,
        filename: str,
        kind: ArtifactKind,
    ) -> list[StructuredParseResult]:
        """Run every registered parser that supports ``kind``."""
        supported = self.parsers_for(kind)
        if not supported:
            return [
                StructuredParseResult(
                    parser_name="registry",
                    parser_version="1.0.0",
                    status=ParseStatus.SKIPPED,
                    diagnostics=[
                        DiagnosticMessage(
                            severity="info",
                            code="no_parser",
                            message=f"No parser registered for kind {kind.value}",
                        )
                    ],
                    warnings=[f"No parser registered for kind {kind.value}"],
                    extraction_quality=0.0,
                    raw_summary={"filename": filename, "kind": kind.value},
                )
            ]
        return [parser.parse(content, filename=filename, kind=kind) for parser in supported]


def build_default_parser_registry() -> ParserRegistry:
    """Construct the default Phase 6A parser set."""
    registry = ParserRegistry()
    for parser in (
        WorkflowParser(),
        LogParser(),
        TerraformParser(),
        TerraformPlanParser(),
        AwsPolicyParser(),
        ChangeParser(),
    ):
        registry.register(parser)
    return registry
