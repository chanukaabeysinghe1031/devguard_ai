"""Matplotlib charts for benchmark evaluation reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_charts(report: dict[str, Any], out_dir: Path) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "matplotlib is required for --save-charts. "
            "Install with: pip install matplotlib"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    categories = report.get("category_reports") or {}
    if categories:
        names = list(categories.keys())
        p5 = [categories[n]["precision@5"] for n in names]
        r5 = [categories[n]["recall@5"] for n in names]
        mrr = [categories[n]["mrr"] for n in names]
        fig, ax = plt.subplots(figsize=(12, 5))
        x = range(len(names))
        width = 0.25
        ax.bar([i - width for i in x], p5, width=width, label="P@5")
        ax.bar(list(x), r5, width=width, label="R@5")
        ax.bar([i + width for i in x], mrr, width=width, label="MRR")
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=35, ha="right")
        ax.set_ylim(0, 1.05)
        ax.set_title("Category retrieval performance")
        ax.legend()
        fig.tight_layout()
        path = out_dir / "category_performance_bar.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

        # Radar for aggregate-like category nDCG
        ndcg = [categories[n]["ndcg@5"] for n in names]
        if len(names) >= 3:
            import math

            angles = [2 * math.pi * i / len(names) for i in range(len(names))]
            angles.append(angles[0])
            values = ndcg + [ndcg[0]]
            fig, ax = plt.subplots(figsize=(6, 6), subplot_kw={"polar": True})
            ax.plot(angles, values)
            ax.fill(angles, values, alpha=0.25)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(names)
            ax.set_yticklabels([])
            ax.set_title("nDCG@5 by category")
            fig.tight_layout()
            path = out_dir / "category_ndcg_radar.png"
            fig.savefig(path, dpi=140)
            plt.close(fig)
            written.append(str(path))

        # Latency bars
        lat = [categories[n]["average_latency_ms"] for n in names]
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(names, lat)
        ax.set_ylabel("ms")
        ax.set_title("Average retrieval latency by category")
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        path = out_dir / "latency_by_category.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

        # Success rate (hit_rate) from per_query
        success = []
        for name in names:
            subset = [
                q
                for q in report.get("per_query") or []
                if q.get("category_group") == name
            ]
            if not subset:
                success.append(0.0)
            else:
                success.append(
                    sum(q["metrics"]["hit_rate"] for q in subset) / len(subset)
                )
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(names, success)
        ax.set_ylim(0, 1.05)
        ax.set_title("Hit-rate success by category")
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        path = out_dir / "success_rate_by_category.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

    # Simple confusion-style matrix from error analysis technology pairs
    err = report.get("error_analysis") or {}
    pairs = err.get("technology_confusion_top") or []
    if pairs:
        labels = sorted(
            {p[0].split("->")[0] for p in pairs} | {p[0].split("->")[1] for p in pairs}
        )
        index = {label: i for i, label in enumerate(labels)}
        matrix = [[0.0 for _ in labels] for _ in labels]
        for key, count in pairs:
            src, dst = key.split("->", 1)
            if src in index and dst in index:
                matrix[index[src]][index[dst]] = float(count)
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(matrix, cmap="Blues")
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticklabels(labels)
        ax.set_xlabel("Retrieved technology")
        ax.set_ylabel("Query technology")
        ax.set_title("Technology confusion (false positives)")
        fig.colorbar(im, ax=ax, fraction=0.046)
        fig.tight_layout()
        path = out_dir / "technology_confusion_matrix.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))

    return written
