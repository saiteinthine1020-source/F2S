"""Add workspace-owned financial-event comments and flags.

Revision ID: 20260822_0005
Revises: 20260815_0004

Owner: Household Finance module
Issue: #87
Compatibility: PostgreSQL 18; additive upgrade from durable idempotency evidence
Validation: clean/incremental migration, lifecycle, audit, role, and isolation tests
Rollback: removes only review sidecars; canonical financial events remain unchanged
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260822_0005"
down_revision: str | None = "20260815_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _actor_foreign_key(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["workspace_id", column],
        ["workspace_memberships.workspace_id", "workspace_memberships.id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "financial_event_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_kind", sa.String(length=16), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("flag_status", sa.String(length=16), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("review_kind IN ('COMMENT', 'FLAG')", name="valid_kind"),
        sa.CheckConstraint("char_length(btrim(body_text)) BETWEEN 1 AND 2000", name="valid_body"),
        sa.CheckConstraint(
            "reason_code IS NULL OR reason_code IN "
            "('MISSING_EVIDENCE', 'POSSIBLE_DUPLICATE', 'POSSIBLE_INCORRECT_AMOUNT', "
            "'POSSIBLE_INCORRECT_CATEGORY', 'POSSIBLE_INCORRECT_DATE', 'OTHER')",
            name="valid_reason",
        ),
        sa.CheckConstraint(
            "resolution_code IS NULL OR resolution_code IN "
            "('REVIEWED_NO_CHANGE', 'CORRECTION_REQUIRED', 'DUPLICATE_CONFIRMED', 'OTHER')",
            name="valid_resolution",
        ),
        sa.CheckConstraint(
            "(review_kind = 'COMMENT' AND reason_code IS NULL AND flag_status IS NULL "
            "AND resolved_by_membership_id IS NULL AND resolved_at IS NULL "
            "AND resolution_code IS NULL) OR "
            "(review_kind = 'FLAG' AND reason_code IS NOT NULL AND "
            "((flag_status = 'OPEN' AND resolved_by_membership_id IS NULL "
            "AND resolved_at IS NULL AND resolution_code IS NULL) OR "
            "(flag_status = 'RESOLVED' AND resolved_by_membership_id IS NOT NULL "
            "AND resolved_at IS NOT NULL AND resolution_code IS NOT NULL)))",
            name="valid_lifecycle",
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        _actor_foreign_key("created_by_membership_id", "fk_financial_review_creator"),
        _actor_foreign_key("resolved_by_membership_id", "fk_financial_review_resolver"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_review_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_financial_review_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_financial_event_reviews"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_financial_review_workspace_id"),
        sa.UniqueConstraint("workspace_id", "operation_id", name="uq_financial_review_operation"),
    )
    op.create_index(
        "ix_financial_review_workspace_event_created",
        "financial_event_reviews",
        ["workspace_id", "financial_event_id", "created_at", "id"],
    )
    op.create_index(
        "ix_financial_review_open_flags",
        "financial_event_reviews",
        ["workspace_id", "financial_event_id", "created_at"],
        postgresql_where=sa.text("review_kind = 'FLAG' AND flag_status = 'OPEN'"),
    )
    op.execute(
        """
        CREATE FUNCTION f2s_guard_financial_review_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'FINANCIAL_REVIEW_HARD_DELETE_PROHIBITED'
              USING ERRCODE = 'integrity_constraint_violation';
          END IF;
          IF OLD.id IS DISTINCT FROM NEW.id
             OR OLD.workspace_id IS DISTINCT FROM NEW.workspace_id
             OR OLD.financial_event_id IS DISTINCT FROM NEW.financial_event_id
             OR OLD.review_kind IS DISTINCT FROM NEW.review_kind
             OR OLD.body_text IS DISTINCT FROM NEW.body_text
             OR OLD.reason_code IS DISTINCT FROM NEW.reason_code
             OR OLD.operation_id IS DISTINCT FROM NEW.operation_id
             OR OLD.created_by_membership_id IS DISTINCT FROM NEW.created_by_membership_id
             OR OLD.created_at IS DISTINCT FROM NEW.created_at
             OR OLD.review_kind IS DISTINCT FROM 'FLAG'
             OR OLD.flag_status IS DISTINCT FROM 'OPEN'
             OR NEW.flag_status IS DISTINCT FROM 'RESOLVED'
             OR NEW.version IS DISTINCT FROM OLD.version + 1 THEN
            RAISE EXCEPTION 'FINANCIAL_REVIEW_IMMUTABLE'
              USING ERRCODE = 'integrity_constraint_violation';
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_financial_review_history_guard
        BEFORE UPDATE OR DELETE ON financial_event_reviews
        FOR EACH ROW EXECUTE FUNCTION f2s_guard_financial_review_history()
        """
    )


def downgrade() -> None:
    op.drop_table("financial_event_reviews")
    op.execute("DROP FUNCTION f2s_guard_financial_review_history()")
