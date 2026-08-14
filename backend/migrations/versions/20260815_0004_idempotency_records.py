"""Add durable workspace-scoped idempotency evidence.

Revision ID: 20260815_0004
Revises: 20260814_0003

Owner: Application Support
Issue: #81
Compatibility: PostgreSQL 18; additive upgrade from the Phase 2 finance foundation
Validation: clean/incremental migration, replay, concurrency, retention, and isolation tests
Rollback: removes only idempotency evidence; never changes canonical financial events
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0004"
down_revision: str | None = "20260814_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_code", sa.String(length=64), nullable=False),
        sa.Column("key_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_code", sa.String(length=64), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("resource_type_code", sa.String(length=64), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "operation_code ~ '^[A-Z][A-Z0-9_]{2,63}$'", name="valid_operation_code"
        ),
        sa.CheckConstraint("key_digest ~ '^[0-9a-f]{64}$'", name="valid_key_digest"),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'", name="valid_request_fingerprint"
        ),
        sa.CheckConstraint("state IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')", name="valid_state"),
        sa.CheckConstraint(
            "outcome_code IS NULL OR outcome_code ~ '^[A-Z][A-Z0-9_]{2,63}$'",
            name="valid_outcome_code",
        ),
        sa.CheckConstraint(
            "resource_type_code IS NULL OR resource_type_code ~ '^[A-Z][A-Z0-9_]{2,63}$'",
            name="valid_resource_type_code",
        ),
        sa.CheckConstraint(
            "(state = 'IN_PROGRESS' AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND completed_at IS NULL "
            "AND expires_at IS NULL AND outcome_code IS NULL AND http_status IS NULL "
            "AND resource_type_code IS NULL AND resource_id IS NULL "
            "AND resource_version IS NULL) OR "
            "(state IN ('COMPLETED', 'FAILED') AND lease_token IS NULL "
            "AND lease_expires_at IS NULL AND completed_at IS NOT NULL "
            "AND expires_at IS NOT NULL AND outcome_code IS NOT NULL "
            "AND http_status IS NOT NULL)",
            name="valid_lifecycle",
        ),
        sa.CheckConstraint(
            "(resource_type_code IS NULL AND resource_id IS NULL AND resource_version IS NULL) "
            "OR (resource_type_code IS NOT NULL AND resource_id IS NOT NULL "
            "AND resource_version > 0)",
            name="complete_resource_reference",
        ),
        sa.CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599", name="valid_http_status"
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR (completed_at IS NOT NULL AND expires_at > completed_at)",
            name="valid_expiry",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_idempotency_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "actor_membership_id"],
            ["workspace_memberships.workspace_id", "workspace_memberships.id"],
            name="fk_idempotency_actor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint("workspace_id", "operation_id", name="uq_idempotency_operation_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "operation_code",
            "key_digest",
            name="uq_idempotency_scope_key",
        ),
    )
    op.create_index(
        "ix_idempotency_expiry", "idempotency_records", ["expires_at", "id"], unique=False
    )
    op.create_index(
        "ix_idempotency_workspace_state",
        "idempotency_records",
        ["workspace_id", "state", "updated_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_workspace_state", table_name="idempotency_records")
    op.drop_index("ix_idempotency_expiry", table_name="idempotency_records")
    op.drop_table("idempotency_records")
