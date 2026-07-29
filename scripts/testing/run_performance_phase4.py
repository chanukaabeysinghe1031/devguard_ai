#!/usr/bin/env python3
"""Phase 4 performance micro-benchmark (warm/cold, local, no paid OpenAI)."""

from __future__ import annotations

import json
import os
import statistics
import time
import uuid
from pathlib import Path

REPO = (
    Path(os.environ["DEVGUARD_REPO_ROOT"]).resolve()
    if os.environ.get("DEVGUARD_REPO_ROOT")
    else Path(__file__).resolve().parents[2]
)
import sys

sys.path.insert(0, str(REPO / "backend" if (REPO / "backend").exists() else REPO))

from app.ai.classification.hybrid_classifier import HybridClassifier  # noqa: E402
from app.ai.orchestration.analysis_context import AnalysisContext  # noqa: E402
from app.ai.rag.hybrid_query_builder import HybridDiagnosticQueryBuilder  # noqa: E402
from app.ai.rag.signals import DiagnosticSignalExtractor  # noqa: E402
from app.domain.services.secret_masker import mask_secrets  # noqa: E402

LOGS = {
    "small": "AccessDenied User is not authorized to perform: sts:AssumeRole",
    "medium": ("ERROR deploy\n" * 40)
    + "AccessDenied not authorized to perform sts:AssumeRole\n"
    + "aws iam get-user\n",
}


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[idx]


def _bench(name: str, fn, repeats: int = 30, *, warm: bool = True) -> dict:
    samples: list[float] = []
    if warm:
        fn()
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "name": name,
        "warm": warm,
        "n": repeats,
        "min_ms": min(samples),
        "max_ms": max(samples),
        "mean_ms": statistics.fmean(samples),
        "median_ms": statistics.median(samples),
        "p50_ms": _pct(samples, 50),
        "p95_ms": _pct(samples, 95),
        "stdev_ms": statistics.pstdev(samples) if len(samples) > 1 else 0.0,
    }


def main() -> None:
    clf = HybridClassifier()
    large = ("build line %d failed\n" % i for i in range(2000))
    large_text = "".join(large)
    medium = LOGS["medium"] + " token=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    results: list[dict] = []

    def classify_small() -> None:
        ctx = AnalysisContext(
            analysis_run_id=uuid.uuid4(),
            incident_id=uuid.uuid4(),
            combined_text=LOGS["small"],
        )
        clf.classify(ctx)

    def classify_large() -> None:
        ctx = AnalysisContext(
            analysis_run_id=uuid.uuid4(),
            incident_id=uuid.uuid4(),
            combined_text=large_text,
        )
        clf.classify(ctx)

    def mask_medium() -> None:
        mask_secrets(medium)

    query_builder = HybridDiagnosticQueryBuilder()

    def signals_and_query() -> None:
        ctx = AnalysisContext(
            analysis_run_id=uuid.uuid4(),
            incident_id=uuid.uuid4(),
            combined_text=LOGS["medium"],
        )
        query_builder.build(ctx)

    # Cold first classification (no prior warm call of this path).
    results.append(_bench("classification_small_cold", classify_small, repeats=5, warm=False))
    results.append(_bench("classification_small_warm", classify_small, repeats=40))
    results.append(_bench("classification_large_warm", classify_large, repeats=15))
    results.append(_bench("secret_masking_medium", mask_medium, repeats=40))
    results.append(_bench("signals_and_query_construction", signals_and_query, repeats=30))

    # Optional live embedding / retrieval stages.
    retrieval_note = "skipped"
    try:
        from app.ai.factory import (  # noqa: WPS433
            _build_configured_vector_store,
            _provider_embedding_identity,
            build_embedding_provider_from_settings,
        )
        from app.core.config import get_settings

        settings = get_settings()
        emb = build_embedding_provider_from_settings(settings)
        identity = _provider_embedding_identity(emb)
        store = _build_configured_vector_store(settings, embedding_identity=identity)
        secondary_name = (settings.chroma_secondary_collection_name or "").strip()
        secondary = None
        if secondary_name and secondary_name != settings.chroma_collection_name:
            secondary = _build_configured_vector_store(
                settings,
                embedding_identity=identity,
                collection_name=secondary_name,
            )

        sample_q = "AWS AccessDenied sts:AssumeRole deployment failure"

        def embed_query() -> None:
            emb.embed_query(sample_q)

        def primary_retrieval() -> None:
            vector = emb.embed_query(sample_q)
            store.query(embedding=vector, top_k=5)

        results.append(_bench("embedding_query_warm", embed_query, repeats=15))
        results.append(_bench("primary_retrieval_warm", primary_retrieval, repeats=10))

        if secondary is not None:

            def secondary_retrieval() -> None:
                vector = emb.embed_query(sample_q)
                secondary.query(embedding=vector, top_k=5)

            def federated_merge() -> None:
                vector = emb.embed_query(sample_q)
                a = store.query(embedding=vector, top_k=5)
                b = secondary.query(embedding=vector, top_k=5)
                merged = {h.chunk_id: h for h in list(a) + list(b)}
                sorted(merged.values(), key=lambda h: h.score, reverse=True)[:5]

            results.append(_bench("secondary_retrieval_warm", secondary_retrieval, repeats=10))
            results.append(_bench("federated_merge_dedupe_warm", federated_merge, repeats=10))
            retrieval_note = f"primary={settings.chroma_collection_name}; secondary={secondary_name}"
        else:
            retrieval_note = (
                f"primary={settings.chroma_collection_name}; secondary unset "
                "(federated stages skipped)"
            )
    except Exception as exc:  # noqa: BLE001
        retrieval_note = f"retrieval stages unavailable: {type(exc).__name__}: {exc}"

    # Local fallback reasoner (no OpenAI).
    try:
        import asyncio

        from app.ai.reasoning.prompt_builder import SAFETY_RULES
        from app.ai.reasoning.reasoning_provider import LocalGroundedReasoningProvider
        from app.domain.interfaces.ai_providers import RootCauseRequest

        reasoner = LocalGroundedReasoningProvider()

        def local_reason() -> None:
            asyncio.run(
                reasoner.generate_root_cause(
                    RootCauseRequest(
                        classification_category="aws_permission_failure",
                        classification_confidence=0.8,
                        root_cause_summary="IAM permission denied",
                        technical_explanation=LOGS["small"],
                        evidence=[{"id": "e1", "excerpt": LOGS["small"]}],
                        retrieved_docs=[],
                        signals={},
                        safety_rules=list(SAFETY_RULES),
                    )
                )
            )

        results.append(_bench("local_fallback_reasoning", local_reason, repeats=20))
    except Exception as exc:  # noqa: BLE001
        results.append({"name": "local_fallback_reasoning", "error": str(exc)})

    out_dir = REPO / "reports" / "performance" / "phase4"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "environment": {
            "repo": str(REPO),
            "retrieval_note": retrieval_note,
            "openai_mode": "not_measured_no_paid_calls",
            "hardware_note": "Docker backend container on host machine",
        },
        "stages": results,
    }
    (out_dir / "stage_latency.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = [
        "# Performance Report — Phase 4 Final",
        "",
        "Environment: Docker backend / warm+cold local stages / no paid OpenAI calls.",
        "",
        f"Retrieval note: {retrieval_note}",
        "",
        "| Stage | n | mean ms | p50 ms | p95 ms | stdev |",
        "|-------|---|---------|--------|--------|-------|",
    ]
    for row in results:
        if "error" in row:
            md.append(f"| {row['name']} | - | error | - | - | {row['error']} |")
            continue
        md.append(
            f"| {row['name']} | {row['n']} | {row['mean_ms']:.3f} | "
            f"{row['p50_ms']:.3f} | {row['p95_ms']:.3f} | {row['stdev_ms']:.3f} |"
        )
    md.extend(
        [
            "",
            "## Limitations",
            "",
            "- OpenAI reasoning latency is not measured in the default suite (avoids paid calls).",
            "- Cold sentence-transformers model download is excluded; first embed may still warm caches.",
            "- Database persistence and full HTTP request duration require the optional live harness.",
            "- Federated stages run only when `CHROMA_SECONDARY_COLLECTION_NAME` is set.",
            "",
        ]
    )
    docs = REPO / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "PERFORMANCE_REPORT_PHASE4_FINAL.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(results, indent=2)[:2000])


if __name__ == "__main__":
    main()
