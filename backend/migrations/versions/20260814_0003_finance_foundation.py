"""Add workspace-scoped canonical Household Finance records.

Revision ID: 20260814_0003
Revises: 20260809_0002

Owner: Household Finance module
Issue: #79
Compatibility: PostgreSQL 18; forward migration from the Phase 1 security head
Validation: clean/incremental migration, constraint, index, history, and isolation tests
Rollback: removes only the two Issue #79 tables and their private trigger functions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0003"
down_revision: str | None = "20260809_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def actor_foreign_key(column_name: str, constraint_name: str) -> sa.ForeignKeyConstraint:
    """Return a same-workspace membership reference with restrictive history semantics."""
    return sa.ForeignKeyConstraint(
        ["workspace_id", column_name],
        ["workspace_memberships.workspace_id", "workspace_memberships.id"],
        name=constraint_name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    """Create finance categories, canonical events, and database invariants."""
    op.create_table(
        "finance_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("normalized_name", sa.String(length=128), nullable=False),
        sa.Column("applicability_code", sa.String(length=16), nullable=False),
        sa.Column("activity_classification_code", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archived_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive_reason_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 128", name="valid_display_name"
        ),
        sa.CheckConstraint(
            "char_length(normalized_name) BETWEEN 1 AND 128 "
            "AND normalized_name = lower(btrim(normalized_name))",
            name="valid_normalized_name",
        ),
        sa.CheckConstraint(
            "applicability_code IN ('INCOME', 'EXPENSE', 'BOTH')",
            name="valid_applicability",
        ),
        sa.CheckConstraint(
            "activity_classification_code IS NULL OR "
            "activity_classification_code IN ('HOUSEHOLD', 'FARM', 'BUSINESS')",
            name="valid_activity_classification",
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="valid_status"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND archived_at IS NULL "
            "AND archived_by_membership_id IS NULL AND archive_reason_code IS NULL) OR "
            "(status = 'ARCHIVED' AND archived_at IS NOT NULL "
            "AND archived_by_membership_id IS NOT NULL AND archive_reason_code IS NOT NULL)",
            name="archive_evidence",
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        actor_foreign_key("created_by_membership_id", "fk_finance_category_creator"),
        actor_foreign_key("updated_by_membership_id", "fk_finance_category_updater"),
        actor_foreign_key("archived_by_membership_id", "fk_finance_category_archiver"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_finance_category_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_finance_categories"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_finance_category_workspace_id"),
    )
    op.create_index(
        "uq_finance_category_active_scope_name",
        "finance_categories",
        [
            "workspace_id",
            "normalized_name",
            "applicability_code",
            sa.text("COALESCE(activity_classification_code, '')"),
        ],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_finance_category_workspace_status_name",
        "finance_categories",
        ["workspace_id", "status", "normalized_name", "id"],
    )

    op.create_table(
        "financial_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column("cash_direction", sa.String(length=8), nullable=False),
        sa.Column("activity_classification_code", sa.String(length=16), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("finance_category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=24, scale=4), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("payment_method_code", sa.String(length=32), nullable=False),
        sa.Column("counterparty_text", sa.String(length=256), nullable=True),
        sa.Column("reference_text", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(length=16), nullable=False),
        sa.Column("posting_status", sa.String(length=16), nullable=False),
        sa.Column("reviewed_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason_code", sa.String(length=64), nullable=True),
        sa.Column("decision_explanation", sa.String(length=512), nullable=True),
        sa.Column("reverses_financial_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "replacement_for_financial_event_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("archived_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive_reason_code", sa.String(length=64), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "event_kind IN ('MANUAL_INCOME', 'MANUAL_EXPENSE')", name="valid_event_kind"
        ),
        sa.CheckConstraint("cash_direction IN ('INFLOW', 'OUTFLOW')", name="valid_direction"),
        sa.CheckConstraint(
            "(event_kind = 'MANUAL_INCOME' AND cash_direction = 'INFLOW') OR "
            "(event_kind = 'MANUAL_EXPENSE' AND cash_direction = 'OUTFLOW')",
            name="manual_kind_direction",
        ),
        sa.CheckConstraint(
            "activity_classification_code IN ('HOUSEHOLD', 'FARM', 'BUSINESS')",
            name="valid_activity_classification",
        ),
        sa.CheckConstraint("amount > 0", name="positive_amount"),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="valid_currency_code"),
        sa.CheckConstraint(
            "payment_method_code IN "
            "('CASH', 'BANK_TRANSFER', 'MOBILE_MONEY', 'CARD', 'CHEQUE', 'OTHER')",
            name="valid_payment_method",
        ),
        sa.CheckConstraint(
            "counterparty_text IS NULL OR char_length(counterparty_text) BETWEEN 1 AND 256",
            name="valid_counterparty",
        ),
        sa.CheckConstraint(
            "reference_text IS NULL OR char_length(reference_text) BETWEEN 1 AND 128",
            name="valid_reference",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) BETWEEN 1 AND 2000", name="valid_notes"
        ),
        sa.CheckConstraint(
            "(approval_status = 'PENDING' AND posting_status = 'NOT_EFFECTIVE') OR "
            "(approval_status = 'REJECTED' AND posting_status = 'NOT_EFFECTIVE') OR "
            "(approval_status = 'APPROVED' AND posting_status IN ('EFFECTIVE', 'REVERSED'))",
            name="valid_approval_posting_state",
        ),
        sa.CheckConstraint(
            "(approval_status = 'PENDING' AND reviewed_by_membership_id IS NULL "
            "AND reviewed_at IS NULL AND decision_reason_code IS NULL "
            "AND decision_explanation IS NULL) OR "
            "(approval_status = 'APPROVED' AND reviewed_by_membership_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND decision_reason_code IS NOT NULL "
            "AND decision_explanation IS NULL) OR "
            "(approval_status = 'REJECTED' AND reviewed_by_membership_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND decision_reason_code IS NOT NULL "
            "AND decision_explanation IS NOT NULL)",
            name="decision_evidence",
        ),
        sa.CheckConstraint(
            "reverses_financial_event_id IS NULL OR reverses_financial_event_id <> id",
            name="reversal_not_self",
        ),
        sa.CheckConstraint(
            "replacement_for_financial_event_id IS NULL OR "
            "replacement_for_financial_event_id <> id",
            name="replacement_not_self",
        ),
        sa.CheckConstraint(
            "reverses_financial_event_id IS NULL OR "
            "(approval_status = 'APPROVED' AND posting_status = 'EFFECTIVE')",
            name="reversal_is_effective",
        ),
        sa.CheckConstraint(
            "(archived_at IS NULL AND archived_by_membership_id IS NULL "
            "AND archive_reason_code IS NULL) OR "
            "(archived_at IS NOT NULL AND archived_by_membership_id IS NOT NULL "
            "AND archive_reason_code IS NOT NULL)",
            name="archive_evidence",
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        actor_foreign_key("created_by_membership_id", "fk_financial_event_creator"),
        actor_foreign_key("updated_by_membership_id", "fk_financial_event_updater"),
        actor_foreign_key("reviewed_by_membership_id", "fk_financial_event_reviewer"),
        actor_foreign_key("archived_by_membership_id", "fk_financial_event_archiver"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "finance_category_id"],
            ["finance_categories.workspace_id", "finance_categories.id"],
            name="fk_financial_event_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "reverses_financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_event_reversal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "replacement_for_financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_event_replacement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_financial_event_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_financial_events"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_financial_event_workspace_id"),
        sa.UniqueConstraint("workspace_id", "operation_id", name="uq_financial_event_operation"),
    )
    op.create_index(
        "uq_financial_event_effective_reversal",
        "financial_events",
        ["workspace_id", "reverses_financial_event_id"],
        unique=True,
        postgresql_where=sa.text(
            "reverses_financial_event_id IS NOT NULL "
            "AND approval_status = 'APPROVED' AND posting_status = 'EFFECTIVE'"
        ),
    )
    op.create_index(
        "ix_financial_event_workspace_occurred",
        "financial_events",
        ["workspace_id", sa.text("occurred_on DESC"), "id"],
    )
    op.create_index(
        "ix_financial_event_workspace_state_kind_date",
        "financial_events",
        ["workspace_id", "approval_status", "posting_status", "event_kind", "occurred_on"],
    )
    op.create_index(
        "ix_financial_event_category_date",
        "financial_events",
        ["workspace_id", "finance_category_id", "occurred_on"],
    )
    op.create_index(
        "ix_financial_event_payment_date",
        "financial_events",
        ["workspace_id", "payment_method_code", "occurred_on"],
    )
    op.create_index(
        "ix_financial_event_reversal_link",
        "financial_events",
        ["workspace_id", "reverses_financial_event_id"],
    )
    op.create_index(
        "ix_financial_event_replacement_link",
        "financial_events",
        ["workspace_id", "replacement_for_financial_event_id"],
    )

    op.execute(
        """
        CREATE FUNCTION f2s_guard_financial_event_history() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE target financial_events%ROWTYPE;
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'FINANCIAL_EVENT_HARD_DELETE_PROHIBITED'
              USING ERRCODE = 'integrity_constraint_violation';
          END IF;
          IF TG_OP = 'UPDATE' AND OLD.approval_status = 'APPROVED' AND (
            NEW.amount IS DISTINCT FROM OLD.amount OR
            NEW.currency_code IS DISTINCT FROM OLD.currency_code OR
            NEW.cash_direction IS DISTINCT FROM OLD.cash_direction OR
            NEW.occurred_on IS DISTINCT FROM OLD.occurred_on OR
            NEW.event_kind IS DISTINCT FROM OLD.event_kind OR
            NEW.activity_classification_code IS DISTINCT FROM OLD.activity_classification_code OR
            NEW.finance_category_id IS DISTINCT FROM OLD.finance_category_id OR
            NEW.operation_id IS DISTINCT FROM OLD.operation_id
          ) THEN
            RAISE EXCEPTION 'APPROVED_FINANCIAL_FACT_IMMUTABLE'
              USING ERRCODE = 'integrity_constraint_violation';
          END IF;
          IF NEW.reverses_financial_event_id IS NOT NULL THEN
            SELECT * INTO target FROM financial_events
             WHERE workspace_id = NEW.workspace_id
               AND id = NEW.reverses_financial_event_id;
            IF NOT FOUND OR target.approval_status <> 'APPROVED'
               OR target.posting_status <> 'EFFECTIVE'
               OR target.reverses_financial_event_id IS NOT NULL
               OR target.currency_code <> NEW.currency_code
               OR target.amount <> NEW.amount
               OR target.cash_direction = NEW.cash_direction THEN
              RAISE EXCEPTION 'INVALID_FINANCIAL_EVENT_REVERSAL'
                USING ERRCODE = 'integrity_constraint_violation';
            END IF;
          END IF;
          RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_financial_event_history_guard
        BEFORE INSERT OR UPDATE OR DELETE ON financial_events
        FOR EACH ROW EXECUTE FUNCTION f2s_guard_financial_event_history()
        """
    )
    op.execute(
        """
        CREATE FUNCTION f2s_guard_finance_category_delete() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'FINANCE_CATEGORY_HARD_DELETE_PROHIBITED'
            USING ERRCODE = 'integrity_constraint_violation';
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_finance_category_delete_guard
        BEFORE DELETE ON finance_categories
        FOR EACH ROW EXECUTE FUNCTION f2s_guard_finance_category_delete()
        """
    )


def downgrade() -> None:
    """Remove the Issue #79 schema in reverse dependency order."""
    op.drop_table("financial_events")
    op.execute("DROP FUNCTION f2s_guard_financial_event_history()")
    op.drop_table("finance_categories")
    op.execute("DROP FUNCTION f2s_guard_finance_category_delete()")
