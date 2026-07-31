"""Graph neighborhood extraction for hypothesis generation (Phase 6A.4)."""

from __future__ import annotations

from typing import Any


class HypothesisGraphContextExtractor:
    """Bounded BFS around primary failure / temporal event nodes."""

    def __init__(
        self,
        *,
        max_depth: int = 4,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> None:
        self._max_depth = max(1, max_depth)
        self._max_nodes = max(10, max_nodes)
        self._max_edges = max(10, max_edges)

    def extract(
        self,
        *,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        seed_keys: list[str],
        consistency_warnings: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        notes: list[str] = []
        if not nodes:
            return [], [], ["no_graph_nodes"]

        by_key: dict[str, dict[str, Any]] = {}
        for n in nodes:
            key = str(n.get("stable_key") or n.get("id") or "")
            if key:
                by_key[key] = n

        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {k: [] for k in by_key}
        for e in edges:
            src = str(e.get("source_node_id") or e.get("source") or "")
            tgt = str(e.get("target_node_id") or e.get("target") or "")
            if src in by_key and tgt in by_key:
                adjacency[src].append((tgt, e))
                adjacency[tgt].append((src, e))

        seeds = [s for s in seed_keys if s in by_key]
        if not seeds:
            # Fall back to failure-like nodes.
            for key, n in by_key.items():
                label = f"{n.get('node_type', '')} {n.get('label', '')}".lower()
                if any(tok in label for tok in ("fail", "error", "denied", "exception")):
                    seeds.append(key)
            if not seeds:
                seeds = list(by_key.keys())[:3]
            notes.append("seed_fallback_used")

        selected_nodes: dict[str, dict[str, Any]] = {}
        selected_edges: dict[str, dict[str, Any]] = {}
        frontier = [(s, 0) for s in seeds]
        seen = set(seeds)
        while frontier and len(selected_nodes) < self._max_nodes:
            current, depth = frontier.pop(0)
            selected_nodes[current] = by_key[current]
            if depth >= self._max_depth:
                continue
            for neighbor, edge in adjacency.get(current, []):
                edge_key = str(
                    edge.get("id")
                    or edge.get("stable_key")
                    or (
                        f"{edge.get('source_node_id')}-"
                        f"{edge.get('edge_type')}-"
                        f"{edge.get('target_node_id')}"
                    )
                )
                if len(selected_edges) < self._max_edges:
                    selected_edges[edge_key] = edge
                if neighbor not in seen and len(selected_nodes) < self._max_nodes:
                    seen.add(neighbor)
                    frontier.append((neighbor, depth + 1))

        if len(by_key) > len(selected_nodes):
            notes.append(
                f"truncated_nodes:{len(by_key)}->{len(selected_nodes)}_depth_{self._max_depth}"
            )
        if len(edges) > len(selected_edges):
            notes.append(f"truncated_edges:{len(edges)}->{len(selected_edges)}")
        if consistency_warnings:
            notes.extend(f"consistency:{w}" for w in consistency_warnings[:5])
        return list(selected_nodes.values()), list(selected_edges.values()), notes
