# ruff: noqa: E501
"""Migration 012 — Phase 6A.2 temporal localisation and evidence graph.

Additive only. No historical backfill. Feature flags default off.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "012_phase6a2_temporal_graph"
down_revision: str | None = "011_phase6a_artifact_bundle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "temporal_localisation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_bundle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("primary_failure_event_id", sa.String(length=64), nullable=True),
        sa.Column("primary_failure_type", sa.String(length=64), nullable=True),
        sa.Column("primary_failure_summary", sa.Text(), nullable=True),
        sa.Column("ordering_method", sa.String(length=40), nullable=True),
        sa.Column("timestamp_quality", sa.String(length=40), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("heuristic_version", sa.String(length=40), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("downstream_symptom_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("upstream_context_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["artifact_bundle_id"], ["analysis_artifact_bundles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_temporal_localisation_analysis",
        "temporal_localisation_results",
        ["organization_id", "analysis_run_id"],
        unique=True,
    )

    op.create_table(
        "temporal_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("localisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workflow_name", sa.String(length=255), nullable=True),
        sa.Column("job_name", sa.String(length=255), nullable=True),
        sa.Column("step_name", sa.String(length=255), nullable=True),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("parser_entity_id", sa.String(length=255), nullable=True),
        sa.Column("parent_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_failure", sa.Boolean(), nullable=False),
        sa.Column("is_candidate_primary_failure", sa.Boolean(), nullable=False),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["localisation_id"], ["temporal_localisation_results.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["analysis_artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "localisation_id", "event_key", name="uq_temporal_events_localisation_key"
        ),
    )
    op.create_index("ix_temporal_events_analysis", "temporal_events", ["analysis_run_id"])
    op.create_index("ix_temporal_events_org", "temporal_events", ["organization_id"])
    op.create_index("ix_temporal_events_type", "temporal_events", ["event_type"])
    op.create_index(
        "ix_temporal_events_primary",
        "temporal_events",
        ["is_candidate_primary_failure"],
    )

    op.create_table(
        "temporal_event_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("localisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_event_key", sa.String(length=64), nullable=False),
        sa.Column("target_event_key", sa.String(length=64), nullable=False),
        sa.Column("link_type", sa.String(length=64), nullable=False),
        sa.Column("derivation", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("supporting_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_id", sa.String(length=80), nullable=False),
        sa.Column("rule_version", sa.String(length=40), nullable=False),
        sa.Column("proven_causality", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["localisation_id"], ["temporal_localisation_results.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "localisation_id",
            "source_event_key",
            "target_event_key",
            "link_type",
            "rule_id",
            name="uq_temporal_event_links_stable",
        ),
    )
    op.create_index("ix_temporal_event_links_analysis", "temporal_event_links", ["analysis_run_id"])

    op.create_table(
        "evidence_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_bundle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("builder_version", sa.String(length=40), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_link_diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["artifact_bundle_id"], ["analysis_artifact_bundles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_graphs_org_analysis",
        "evidence_graphs",
        ["organization_id", "analysis_run_id"],
        unique=True,
    )

    op.create_table(
        "evidence_graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stable_key", sa.String(length=500), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("parser_entity_id", sa.String(length=255), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("extraction_method", sa.String(length=80), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("node_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["graph_id"], ["evidence_graphs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["analysis_artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("graph_id", "stable_key", name="uq_evidence_graph_nodes_stable"),
    )
    op.create_index("ix_evidence_graph_nodes_analysis", "evidence_graph_nodes", ["analysis_run_id"])
    op.create_index("ix_evidence_graph_nodes_org", "evidence_graph_nodes", ["organization_id"])
    op.create_index("ix_evidence_graph_nodes_type", "evidence_graph_nodes", ["node_type"])
    op.create_index("ix_evidence_graph_nodes_artifact", "evidence_graph_nodes", ["artifact_id"])

    op.create_table(
        "evidence_graph_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stable_key", sa.String(length=700), nullable=False),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("derivation_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.String(length=80), nullable=True),
        sa.Column("rule_version", sa.String(length=40), nullable=True),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["graph_id"], ["evidence_graphs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["evidence_graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["evidence_graph_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("graph_id", "stable_key", name="uq_evidence_graph_edges_stable"),
    )
    op.create_index("ix_evidence_graph_edges_analysis", "evidence_graph_edges", ["analysis_run_id"])
    op.create_index("ix_evidence_graph_edges_type", "evidence_graph_edges", ["edge_type"])
    op.create_index("ix_evidence_graph_edges_source", "evidence_graph_edges", ["source_node_id"])
    op.create_index("ix_evidence_graph_edges_target", "evidence_graph_edges", ["target_node_id"])
    op.create_index(
        "ix_evidence_graph_edges_derivation", "evidence_graph_edges", ["derivation_type"]
    )

    op.create_table(
        "graph_consistency_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("valid_node_count", sa.Integer(), nullable=False),
        sa.Column("valid_edge_count", sa.Integer(), nullable=False),
        sa.Column("consistency_score", sa.Float(), nullable=False),
        sa.Column("invalid_edge_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("orphan_nodes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_expected_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflicting_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["graph_id"], ["evidence_graphs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_graph_consistency_org_analysis",
        "graph_consistency_reports",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index("ix_graph_consistency_status", "graph_consistency_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_graph_consistency_status", table_name="graph_consistency_reports")
    op.drop_index("ix_graph_consistency_org_analysis", table_name="graph_consistency_reports")
    op.drop_table("graph_consistency_reports")
    op.drop_index("ix_evidence_graph_edges_derivation", table_name="evidence_graph_edges")
    op.drop_index("ix_evidence_graph_edges_target", table_name="evidence_graph_edges")
    op.drop_index("ix_evidence_graph_edges_source", table_name="evidence_graph_edges")
    op.drop_index("ix_evidence_graph_edges_type", table_name="evidence_graph_edges")
    op.drop_index("ix_evidence_graph_edges_analysis", table_name="evidence_graph_edges")
    op.drop_table("evidence_graph_edges")
    op.drop_index("ix_evidence_graph_nodes_artifact", table_name="evidence_graph_nodes")
    op.drop_index("ix_evidence_graph_nodes_type", table_name="evidence_graph_nodes")
    op.drop_index("ix_evidence_graph_nodes_org", table_name="evidence_graph_nodes")
    op.drop_index("ix_evidence_graph_nodes_analysis", table_name="evidence_graph_nodes")
    op.drop_table("evidence_graph_nodes")
    op.drop_index("ix_evidence_graphs_org_analysis", table_name="evidence_graphs")
    op.drop_table("evidence_graphs")
    op.drop_index("ix_temporal_event_links_analysis", table_name="temporal_event_links")
    op.drop_table("temporal_event_links")
    op.drop_index("ix_temporal_events_primary", table_name="temporal_events")
    op.drop_index("ix_temporal_events_type", table_name="temporal_events")
    op.drop_index("ix_temporal_events_org", table_name="temporal_events")
    op.drop_index("ix_temporal_events_analysis", table_name="temporal_events")
    op.drop_table("temporal_events")
    op.drop_index("ix_temporal_localisation_analysis", table_name="temporal_localisation_results")
    op.drop_table("temporal_localisation_results")
