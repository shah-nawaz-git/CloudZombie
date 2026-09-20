"""Add observation cost confidence.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "finding_observations",
        sa.Column(
            "cost_confidence_at_observation",
            sa.String(length=16),
            nullable=False,
            server_default="UNAVAILABLE",
        ),
    )


def downgrade() -> None:
    op.drop_column("finding_observations", "cost_confidence_at_observation")
