"""Initial portable schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.persistence.types import UtcDateTime

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("account_id", sa.String(32), nullable=True),
        sa.Column("principal_arn", sa.String(512), nullable=True),
        sa.Column("seeded", sa.Boolean(), nullable=False),
        sa.Column("started_at", UtcDateTime(), nullable=False),
        sa.Column("finished_at", UtcDateTime(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_regions", sa.JSON(), nullable=False),
        sa.Column("completed_regions", sa.JSON(), nullable=False),
        sa.Column("partial_regions", sa.JSON(), nullable=False),
        sa.Column("failed_regions", sa.JSON(), nullable=False),
        sa.Column("skipped_regions", sa.JSON(), nullable=False),
        sa.Column("coverage", sa.JSON(), nullable=False),
        sa.Column("new_findings", sa.Integer(), nullable=False),
        sa.Column("persistent_findings", sa.Integer(), nullable=False),
        sa.Column("resolved_findings", sa.Integer(), nullable=False),
        sa.Column("ignored_findings", sa.Integer(), nullable=False),
        sa.Column("estimated_exposure", sa.Numeric(12, 4), nullable=False),
        sa.Column("potential_exposure_low_confidence", sa.Numeric(12, 4), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pricing_cache",
        sa.Column("cache_key", sa.String(512), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", UtcDateTime(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.String(32), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("detector_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("resource_created_at", UtcDateTime(), nullable=True),
        sa.Column("first_observed_at", UtcDateTime(), nullable=False),
        sa.Column("last_observed_at", UtcDateTime(), nullable=False),
        sa.Column("streak_started_at", UtcDateTime(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("consecutive_observations", sa.Integer(), nullable=False),
        sa.Column("persistence_state", sa.String(32), nullable=False),
        sa.Column("detection_confidence", sa.String(16), nullable=False),
        sa.Column("remediation_risk", sa.String(16), nullable=False),
        sa.Column("cost_confidence", sa.String(16), nullable=False),
        sa.Column("estimated_monthly_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("cost_explanation", sa.Text(), nullable=False),
        sa.Column("pricing_source", sa.String(64), nullable=False),
        sa.Column("pricing_timestamp", UtcDateTime(), nullable=True),
        sa.Column("cost_line_items", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("known_dependencies", sa.JSON(), nullable=False),
        sa.Column("ownership", sa.JSON(), nullable=False),
        sa.Column("related_resource_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("resolved_at", UtcDateTime(), nullable=True),
        sa.Column("dismissed_at", UtcDateTime(), nullable=True),
        sa.Column("dismiss_reason", sa.Text(), nullable=True),
        sa.Column("ignore_reason", sa.Text(), nullable=True),
        sa.Column("first_scan_id", sa.Uuid(), nullable=False),
        sa.Column("last_scan_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.Column("updated_at", UtcDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["first_scan_id"], ["scans.id"]),
        sa.ForeignKeyConstraint(["last_scan_id"], ["scans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "region",
            "resource_type",
            "resource_id",
            "detector_type",
            name="uq_finding_identity",
        ),
    )
    op.create_index("ix_findings_region", "findings", ["region"])
    op.create_index("ix_findings_status", "findings", ["status"])
    op.create_table(
        "finding_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("finding_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("observed_at", UtcDateTime(), nullable=False),
        sa.Column("status_at_observation", sa.String(16), nullable=False),
        sa.Column("persistence_state_at_observation", sa.String(32), nullable=False),
        sa.Column("remediation_risk_at_observation", sa.String(16), nullable=False),
        sa.Column("estimated_monthly_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id", "scan_id", name="uq_finding_observation_scan"),
    )
    op.create_index(
        "ix_finding_observations_finding_scan",
        "finding_observations",
        ["finding_id", "scan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_finding_observations_finding_scan", table_name="finding_observations")
    op.drop_table("finding_observations")
    op.drop_index("ix_findings_status", table_name="findings")
    op.drop_index("ix_findings_region", table_name="findings")
    op.drop_table("findings")
    op.drop_table("pricing_cache")
    op.drop_table("settings")
    op.drop_table("scans")
