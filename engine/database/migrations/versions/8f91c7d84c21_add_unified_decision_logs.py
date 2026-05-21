"""add unified decision logs

Revision ID: 8f91c7d84c21
Revises: 4a5725f42fb2
Create Date: 2026-05-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8f91c7d84c21"
down_revision: Union[str, None] = "4a5725f42fb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unified_decision_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("overall_risk_score", sa.Integer(), nullable=False),
        sa.Column("decision_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("signature", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "idx_unified_decision_tenant_created",
        "unified_decision_logs",
        ["tenant_id", "created_at"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "idx_unified_decision_tenant_request",
        "unified_decision_logs",
        ["tenant_id", "request_id"],
        unique=True,
        schema="public",
    )
    op.create_index(
        "idx_unified_decision_tenant_outcome",
        "unified_decision_logs",
        ["tenant_id", "outcome"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_unified_decision_tenant_outcome",
        table_name="unified_decision_logs",
        schema="public",
    )
    op.drop_index(
        "idx_unified_decision_tenant_request",
        table_name="unified_decision_logs",
        schema="public",
    )
    op.drop_index(
        "idx_unified_decision_tenant_created",
        table_name="unified_decision_logs",
        schema="public",
    )
    op.drop_table("unified_decision_logs", schema="public")

