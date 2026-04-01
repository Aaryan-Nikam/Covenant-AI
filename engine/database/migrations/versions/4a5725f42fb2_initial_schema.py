"""Initial schema

Revision ID: 4a5725f42fb2
Revises: 
Create Date: 2026-04-01 18:50:15.921597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a5725f42fb2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    # ------------------ PUBLIC SCHEMA ------------------
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('active_rulesets', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='public'
    )

    op.create_table(
        'tenant_api_keys',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('scope', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoke_reason', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['public.tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='public'
    )
    op.create_index('idx_apikey_hash', 'tenant_api_keys', ['key_hash'], unique=True, schema='public')
    op.create_index('idx_apikey_tenant', 'tenant_api_keys', ['tenant_id'], unique=False, schema='public')

    # ------------------ AUDIT SCHEMA ------------------
    # Create the audit schema if it does not exist
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('agent_id', sa.String(length=128), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('rulesets_used', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('detections', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('actions_taken', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('was_blocked', sa.Boolean(), nullable=False),
        sa.Column('target_url', sa.String(length=512), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('hmac_signature', sa.String(length=128), nullable=False),
        sa.Column('prev_entry_hash', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='audit'
    )
    op.create_index('idx_audit_agent', 'audit_log', ['agent_id', 'timestamp'], unique=False, schema='audit')
    op.create_index('idx_audit_outcome', 'audit_log', ['outcome', 'timestamp'], unique=False, schema='audit')
    op.create_index('idx_audit_rulesets', 'audit_log', ['rulesets_used'], unique=False, schema='audit', postgresql_using='gin')


def downgrade() -> None:
    # ------------------ AUDIT SCHEMA ------------------
    op.drop_index('idx_audit_rulesets', table_name='audit_log', schema='audit', postgresql_using='gin')
    op.drop_index('idx_audit_outcome', table_name='audit_log', schema='audit')
    op.drop_index('idx_audit_agent', table_name='audit_log', schema='audit')
    op.drop_table('audit_log', schema='audit')
    op.execute("DROP SCHEMA IF EXISTS audit")

    # ------------------ PUBLIC SCHEMA ------------------
    op.drop_index('idx_apikey_tenant', table_name='tenant_api_keys', schema='public')
    op.drop_index('idx_apikey_hash', table_name='tenant_api_keys', schema='public')
    op.drop_table('tenant_api_keys', schema='public')
    op.drop_table('tenants', schema='public')
