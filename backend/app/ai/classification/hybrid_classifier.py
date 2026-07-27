"""Hybrid classifier: rules-first with keyword scoring (deterministic, no LLM)."""

from __future__ import annotations

from collections import defaultdict

from app.ai.classification.rule_based_classifier import score_text
from app.ai.orchestration.analysis_context import AnalysisContext, ClassificationCandidate

_KEYWORD_BOOSTS: dict[str, tuple[str, ...]] = {
    "aws_permission_failure": ("iam", "accessdenied", "sts", "unauthorized", "policy"),
    "terraform_failure": ("terraform", "provider", "resource", "state", "plan", "apply"),
    "docker_failure": ("docker", "dockerfile", "image", "container", "registry"),
    "dependency_failure": ("npm", "pip", "yarn", "dependency", "package", "requirements"),
    "test_failure": ("pytest", "junit", "assertion", "failed test", "spec"),
    "build_failure": ("compile", "build", "webpack", "gradle", "maven", "tsc"),
    "configuration_failure": ("config", "yaml", "env", "missing required", "settings"),
    "deployment_failure": ("deploy", "rollout", "helm", "kubernetes", "ecs", "release"),
    "network_failure": ("timeout", "dns", "connection", "refused", "unreachable"),
    "security_misconfiguration": ("tls", "certificate", "secret", "insecure", "cors"),
}


def _keyword_scores(text: str) -> dict[str, float]:
    lowered = text.lower()
    scores: dict[str, float] = defaultdict(float)
    for code, keywords in _KEYWORD_BOOSTS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits:
            scores[code] = min(0.75, 0.15 * hits)
    return scores


class HybridClassifier:
    """Combine rule matches with keyword boosts; always returns at least one label."""

    def classify(self, context: AnalysisContext) -> list[ClassificationCandidate]:
        text = context.combined_text
        rule_hits = score_text(text)
        keyword_hits = _keyword_scores(text)

        aggregated: dict[str, dict] = {}
        for code, matches in rule_hits.items():
            best = max(matches, key=lambda item: item[1])
            rule, weight = best
            aggregated[code] = {
                "confidence": weight,
                "matched_rules": [m.name for m, _ in matches],
                "root_cause": rule.root_cause,
                "technical": rule.technical,
                "impact": rule.impact,
            }

        for code, boost in keyword_hits.items():
            if code in aggregated:
                aggregated[code]["confidence"] = min(
                    0.99,
                    aggregated[code]["confidence"] + boost * 0.15,
                )
            else:
                aggregated[code] = {
                    "confidence": boost,
                    "matched_rules": [f"keyword:{code}"],
                    "root_cause": f"Signals suggest a {code.replace('_', ' ')}.",
                    "technical": "Keyword and metadata signals indicate this category.",
                    "impact": "The pipeline step associated with this category likely failed.",
                }

        if not aggregated:
            aggregated["unknown_failure"] = {
                "confidence": 0.35,
                "matched_rules": ["fallback:unknown"],
                "root_cause": "Insufficient signals to classify the failure confidently.",
                "technical": "No high-confidence rule or keyword pattern matched the inputs.",
                "impact": "Manual review is required to determine the failure cause.",
            }

        ordered = sorted(
            aggregated.items(),
            key=lambda item: item[1]["confidence"],
            reverse=True,
        )[: context.top_k]

        if ordered and ordered[0][1]["confidence"] < 0.40:
            codes = {code for code, _ in ordered}
            if "unknown_failure" not in codes:
                ordered = list(ordered[:-1]) + [
                    (
                        "unknown_failure",
                        {
                            "confidence": 0.40,
                            "matched_rules": ["policy:low_confidence"],
                            "root_cause": (
                                "Classification confidence is below the decision threshold."
                            ),
                            "technical": (
                                "Top candidate confidence was insufficient for a firm label."
                            ),
                            "impact": "Treat results as provisional until reviewed.",
                        },
                    )
                ]

        candidates: list[ClassificationCandidate] = []
        for rank, (code, payload) in enumerate(ordered, start=1):
            candidates.append(
                ClassificationCandidate(
                    category_code=code,
                    confidence=round(float(payload["confidence"]), 4),
                    rank=rank,
                    matched_rules=list(payload["matched_rules"]),
                    root_cause_summary=str(payload["root_cause"]),
                    technical_explanation=str(payload["technical"]),
                    impact_summary=str(payload["impact"]),
                )
            )
        context.classifications = candidates
        context.model_name = "rules-hybrid"
        context.model_version = "1.0.0"
        return candidates
