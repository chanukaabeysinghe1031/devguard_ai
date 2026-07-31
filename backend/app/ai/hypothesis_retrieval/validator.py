"""Retrieval result validation (not causal adjudication)."""

from __future__ import annotations

import math

from app.ai.hypothesis_retrieval.plan_builder import is_secret_like_query
from app.ai.hypothesis_retrieval.versions import RETRIEVAL_RESULT_VALIDATOR_VERSION
from app.domain.hypothesis_retrieval.enums import RetrievalValidationStatus
from app.domain.hypothesis_retrieval.models import (
    HypothesisRetrievalContext,
    HypothesisRetrievedItem,
    RetrievalValidationResult,
)


class RetrievalResultValidator:
    """Validate retrieval candidates for scope/safety — never decides support."""

    def __init__(self, *, max_items: int = 50) -> None:
        self._max_items = max(1, max_items)

    def validate_many(
        self,
        items: list[HypothesisRetrievedItem],
        context: HypothesisRetrievalContext,
        *,
        seen_keys: set[str] | None = None,
    ) -> list[RetrievalValidationResult]:
        results: list[RetrievalValidationResult] = []
        seen = seen_keys if seen_keys is not None else set()
        for item in items[: self._max_items]:
            results.append(self.validate(item, context, seen_keys=seen))
        return results

    def validate(
        self,
        item: HypothesisRetrievedItem,
        context: HypothesisRetrievalContext,
        *,
        seen_keys: set[str] | None = None,
    ) -> RetrievalValidationResult:
        key = self._item_key(item)
        warnings: list[str] = []
        reasons: list[str] = []

        if not (item.text_excerpt or "").strip():
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_EMPTY,
                reasons=["empty_excerpt"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        if is_secret_like_query(item.text_excerpt):
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_SECRET_RISK,
                reasons=["secret_like_excerpt"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        meta = item.metadata or {}
        org = str(meta.get("organization_id") or meta.get("organisation_id") or "")
        if org and context.organization_id and org != context.organization_id:
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_SCOPE,
                reasons=["organization_mismatch"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        if not math.isfinite(float(item.retrieval_score)):
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_MALFORMED,
                reasons=["non_finite_score"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        if str(meta.get("document_status") or "").lower() in {"archived", "deleted"}:
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_ARCHIVED,
                reasons=["archived_or_deleted"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        if str(meta.get("history_trust") or "").lower() == "untrusted":
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_UNTRUSTED_HISTORY,
                reasons=["untrusted_history"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        if not item.source_system and not item.adapter_name:
            return RetrievalValidationResult(
                item_key=key,
                status=RetrievalValidationStatus.REJECTED_INVALID_PROVENANCE,
                reasons=["missing_provenance"],
                validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
            )

        if seen_keys is not None:
            if key in seen_keys:
                return RetrievalValidationResult(
                    item_key=key,
                    status=RetrievalValidationStatus.REJECTED_DUPLICATE,
                    reasons=["duplicate_identity"],
                    validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
                )
            seen_keys.add(key)

        if item.redaction_status not in {"masked", "applied", "none"}:
            warnings.append("unusual_redaction_status")

        status = (
            RetrievalValidationStatus.ACCEPTED_WITH_WARNINGS
            if warnings
            else RetrievalValidationStatus.ACCEPTED
        )
        return RetrievalValidationResult(
            item_key=key,
            status=status,
            warnings=warnings,
            reasons=reasons,
            validator_version=RETRIEVAL_RESULT_VALIDATOR_VERSION,
        )

    @staticmethod
    def _item_key(item: HypothesisRetrievedItem) -> str:
        return "|".join(
            [
                item.source_type.value,
                item.source_id or "",
                item.chunk_id or "",
                item.document_id or "",
                item.normalized_text_hash or "",
            ]
        )

    @staticmethod
    def is_accepted(status: RetrievalValidationStatus) -> bool:
        return status in {
            RetrievalValidationStatus.ACCEPTED,
            RetrievalValidationStatus.ACCEPTED_WITH_WARNINGS,
        }
