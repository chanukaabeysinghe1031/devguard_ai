"""Hypothesis query intent generation (deterministic, no LLM)."""

from __future__ import annotations

from app.ai.hypothesis_retrieval.versions import HYPOTHESIS_QUERY_INTENTS_VERSION
from app.domain.hypothesis_retrieval.enums import (
    EstimatedCostClass,
    HypothesisRetrievalSourceType,
    QueryIntentType,
)
from app.domain.hypothesis_retrieval.models import (
    HypothesisQueryIntent,
    HypothesisRetrievalContext,
)


class HypothesisQueryIntentGenerator:
    """Convert hypothesis gaps into explicit retrieval intents."""

    def generate(
        self,
        context: HypothesisRetrievalContext,
        *,
        session_id: str | None = None,
    ) -> list[HypothesisQueryIntent]:
        intents: list[HypothesisQueryIntent] = []
        hid = context.hypothesis_id
        category = (context.category_code or "").upper()
        claim = (context.causal_claim or "").strip()
        claim_l = claim.lower()

        if claim:
            intents.append(
                self._intent(
                    intent_id=f"{hid}:confirm_claim",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.CONFIRM_CAUSAL_CLAIM,
                    objective=f"Find evidence supporting: {claim[:240]}",
                    priority=10,
                    required=True,
                    reason="causal_claim_present",
                    preferred=[
                        HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.GRAPH,
                    ],
                )
            )

        if context.error_signature or "unknown" in claim_l or not category:
            intents.append(
                self._intent(
                    intent_id=f"{hid}:exact_signature",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.FIND_EXACT_FAILURE_SIGNATURE,
                    objective=(
                        f"Locate exact failure signature {context.error_signature or claim[:160]}"
                    ),
                    priority=15,
                    reason="exact_signature_search",
                    preferred=[
                        HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.TEMPORAL,
                    ],
                )
            )

        if self._looks_iam_missing(claim_l, category, context):
            intents.extend(
                [
                    self._intent(
                        intent_id=f"{hid}:iam_confirm",
                        hypothesis_id=hid,
                        session_id=session_id,
                        intent_type=QueryIntentType.FIND_PERMISSION_RELATIONSHIP,
                        objective=(
                            "Find evidence that the active deployment role lacks "
                            "the claimed permission"
                        ),
                        priority=12,
                        required=True,
                        reason="iam_missing_permission_pattern",
                        preferred=[
                            HypothesisRetrievalSourceType.ARTIFACT,
                            HypothesisRetrievalSourceType.GRAPH,
                            HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                            HypothesisRetrievalSourceType.DOCUMENTATION,
                        ],
                        identifiers=list(context.permission_actions[:4]),
                    ),
                    self._intent(
                        intent_id=f"{hid}:iam_contradict",
                        hypothesis_id=hid,
                        session_id=session_id,
                        intent_type=QueryIntentType.FIND_CONTRADICTION_CANDIDATE,
                        objective=(
                            "Find evidence that an identity policy already allows "
                            "the claimed action"
                        ),
                        priority=18,
                        reason="iam_contradiction_candidate",
                        preferred=[
                            HypothesisRetrievalSourceType.ARTIFACT,
                            HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                        ],
                        identifiers=list(context.permission_actions[:4]),
                    ),
                    self._intent(
                        intent_id=f"{hid}:iam_policy",
                        hypothesis_id=hid,
                        session_id=session_id,
                        intent_type=QueryIntentType.FIND_POLICY_BEHAVIOR,
                        objective=(
                            "Determine whether an explicit deny overrides the identity allow"
                        ),
                        priority=22,
                        reason="iam_policy_behavior",
                        preferred=[
                            HypothesisRetrievalSourceType.DOCUMENTATION,
                            HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                            HypothesisRetrievalSourceType.ARTIFACT,
                        ],
                    ),
                ]
            )

        if self._looks_wrong_role(claim_l, context):
            intents.extend(
                [
                    self._intent(
                        intent_id=f"{hid}:role_artifact",
                        hypothesis_id=hid,
                        session_id=session_id,
                        intent_type=QueryIntentType.VERIFY_ARTIFACT_RELATIONSHIP,
                        objective="Confirm which role ARN the workflow actually assumes",
                        priority=14,
                        required=True,
                        reason="wrong_role_pattern",
                        preferred=[
                            HypothesisRetrievalSourceType.ARTIFACT,
                            HypothesisRetrievalSourceType.GRAPH,
                            HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
                        ],
                        artifacts=(
                            [context.affected_artifact_id] if context.affected_artifact_id else []
                        ),
                    ),
                    self._intent(
                        intent_id=f"{hid}:role_diff",
                        hypothesis_id=hid,
                        session_id=session_id,
                        intent_type=QueryIntentType.FIND_PRIOR_SUCCESS_DIFFERENCE,
                        objective=("Compare assumed role against previous successful run"),
                        priority=24,
                        reason="wrong_role_prior_success",
                        preferred=[
                            HypothesisRetrievalSourceType.TEMPORAL,
                            HypothesisRetrievalSourceType.REPOSITORY_CHANGE,
                            HypothesisRetrievalSourceType.HISTORICAL_INCIDENT,
                        ],
                    ),
                ]
            )

        for idx, gap in enumerate(context.missing_evidence[:3]):
            intents.append(
                self._intent(
                    intent_id=f"{hid}:missing_{idx}",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.RESOLVE_MISSING_EVIDENCE,
                    objective=f"Resolve missing evidence: {gap[:200]}",
                    evidence_gap=gap,
                    priority=30 + idx,
                    reason="missing_evidence",
                    preferred=[
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.GRAPH,
                        HypothesisRetrievalSourceType.TEMPORAL,
                    ],
                )
            )

        for idx, obs in enumerate(context.expected_observations[:2]):
            intents.append(
                self._intent(
                    intent_id=f"{hid}:expected_{idx}",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.CONFIRM_CAUSAL_CLAIM,
                    objective=f"Seek expected observation: {obs[:200]}",
                    expected_observation=obs,
                    priority=40 + idx,
                    reason="expected_observation",
                    preferred=[
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.TEMPORAL,
                    ],
                )
            )

        for idx, obs in enumerate(context.falsifying_observations[:2]):
            intents.append(
                self._intent(
                    intent_id=f"{hid}:falsify_{idx}",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.FIND_CONTRADICTION_CANDIDATE,
                    objective=f"Seek falsifying observation: {obs[:200]}",
                    falsifying_observation=obs,
                    priority=45 + idx,
                    reason="falsifying_observation",
                    preferred=[
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.TEMPORAL,
                        HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                    ],
                )
            )

        if context.affected_artifact_id or context.affected_path:
            intents.append(
                self._intent(
                    intent_id=f"{hid}:artifact_rel",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.VERIFY_ARTIFACT_RELATIONSHIP,
                    objective="Verify affected artifact relationships",
                    priority=35,
                    reason="affected_artifact",
                    preferred=[
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.GRAPH,
                    ],
                    artifacts=(
                        [context.affected_artifact_id] if context.affected_artifact_id else []
                    ),
                    paths=[context.affected_path] if context.affected_path else [],
                )
            )

        if context.root_cause_node_id or context.observed_failure_node_id:
            intents.append(
                self._intent(
                    intent_id=f"{hid}:resource_graph",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.FIND_RESOURCE_RELATIONSHIP,
                    objective="Explore graph neighborhood around causal path",
                    priority=38,
                    reason="graph_seed_nodes",
                    preferred=[HypothesisRetrievalSourceType.GRAPH],
                    entities=_seed_nodes(context),
                )
            )

        if "terraform" in claim_l or "terraform" in category.lower():
            intents.append(
                self._intent(
                    intent_id=f"{hid}:tf_config",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.FIND_CONFIGURATION_REQUIREMENT,
                    objective="Find Terraform configuration requirements",
                    priority=28,
                    reason="terraform_category",
                    preferred=[
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.GRAPH,
                        HypothesisRetrievalSourceType.DOCUMENTATION,
                    ],
                )
            )

        if "depend" in claim_l or "package" in claim_l:
            intents.append(
                self._intent(
                    intent_id=f"{hid}:dep",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.FIND_CONFIGURATION_REQUIREMENT,
                    objective="Find dependency conflict configuration evidence",
                    priority=29,
                    reason="dependency_pattern",
                    preferred=[
                        HypothesisRetrievalSourceType.ARTIFACT,
                        HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                        HypothesisRetrievalSourceType.HISTORICAL_INCIDENT,
                    ],
                )
            )

        intents.append(
            self._intent(
                intent_id=f"{hid}:history",
                hypothesis_id=hid,
                session_id=session_id,
                intent_type=QueryIntentType.FIND_HISTORICAL_ANALOGUE,
                objective="Find similar resolved historical incidents",
                priority=80,
                reason="historical_analogue",
                preferred=[HypothesisRetrievalSourceType.HISTORICAL_INCIDENT],
                cost=EstimatedCostClass.MEDIUM,
            )
        )

        if (context.open_set_status or "").upper() in {"UNKNOWN", "OPEN", "NOVEL"}:
            intents.append(
                self._intent(
                    intent_id=f"{hid}:novel",
                    hypothesis_id=hid,
                    session_id=session_id,
                    intent_type=QueryIntentType.EXPLORE_NOVEL_SIGNATURE,
                    objective="Explore novel failure signature without forcing category",
                    priority=20,
                    reason="open_set_unknown",
                    preferred=[
                        HypothesisRetrievalSourceType.LEXICAL_KNOWLEDGE,
                        HypothesisRetrievalSourceType.VECTOR_KNOWLEDGE,
                        HypothesisRetrievalSourceType.DOCUMENTATION,
                    ],
                )
            )

        intents.append(
            self._intent(
                intent_id=f"{hid}:official",
                hypothesis_id=hid,
                session_id=session_id,
                intent_type=QueryIntentType.FIND_OFFICIAL_CONSTRAINT,
                objective="Retrieve official constraint documentation",
                priority=70,
                reason="official_docs",
                preferred=[
                    HypothesisRetrievalSourceType.DOCUMENTATION,
                    HypothesisRetrievalSourceType.STATIC_KNOWLEDGE,
                ],
            )
        )

        intents.sort(key=lambda i: (i.priority, i.intent_id))
        return intents

    def _intent(
        self,
        *,
        intent_id: str,
        hypothesis_id: str,
        session_id: str | None,
        intent_type: QueryIntentType,
        objective: str,
        priority: int,
        reason: str,
        preferred: list[HypothesisRetrievalSourceType],
        required: bool = False,
        evidence_gap: str | None = None,
        expected_observation: str | None = None,
        falsifying_observation: str | None = None,
        identifiers: list[str] | None = None,
        artifacts: list[str] | None = None,
        paths: list[str] | None = None,
        entities: list[str] | None = None,
        cost: EstimatedCostClass = EstimatedCostClass.LOW,
    ) -> HypothesisQueryIntent:
        return HypothesisQueryIntent(
            intent_id=intent_id,
            hypothesis_id=hypothesis_id,
            session_id=session_id,
            intent_type=intent_type,
            objective=objective,
            evidence_gap=evidence_gap,
            expected_observation=expected_observation,
            falsifying_observation=falsifying_observation,
            target_identifiers=list(identifiers or []),
            target_artifact_ids=list(artifacts or []),
            target_source_paths=list(paths or []),
            target_entity_ids=list(entities or []),
            preferred_source_types=list(preferred),
            required_source_types=list(preferred[:1]) if required else [],
            priority=priority,
            estimated_cost_class=cost,
            required=required,
            reason=reason,
            generating_rule_id=reason,
            generating_rule_version=HYPOTHESIS_QUERY_INTENTS_VERSION,
        )

    @staticmethod
    def _looks_iam_missing(
        claim_l: str,
        category: str,
        context: HypothesisRetrievalContext,
    ) -> bool:
        if context.permission_actions:
            return True
        tokens = ("iam", "permission", "accessdenied", "access denied", "missing", "deny")
        if any(t in claim_l for t in tokens):
            return True
        return "IAM" in category or "PERMISSION" in category

    @staticmethod
    def _looks_wrong_role(claim_l: str, context: HypothesisRetrievalContext) -> bool:
        if any(t in claim_l for t in ("wrong role", "assumed role", "role arn", "assume-role")):
            return True
        return any("role" in (a or "").lower() for a in context.resource_identifiers)


def _seed_nodes(context: HypothesisRetrievalContext) -> list[str]:
    nodes: list[str] = []
    for value in (
        context.root_cause_node_id,
        context.observed_failure_node_id,
        *context.causal_path_node_ids,
    ):
        if value and value not in nodes:
            nodes.append(value)
    return nodes
