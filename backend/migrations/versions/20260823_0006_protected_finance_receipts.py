# ruff: noqa: E501
"""Add private protected-file metadata and finance receipt associations.

Revision ID: 20260823_0006
Revises: 20260822_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0006"
down_revision: str | None = "20260822_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _actor(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["workspace_id", column],
        ["workspace_memberships.workspace_id", "workspace_memberships.id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "protected_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose_code", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("declared_media_type", sa.String(64), nullable=False),
        sa.Column("detected_media_type", sa.String(64), nullable=True),
        sa.Column("sanitized_filename", sa.String(128), nullable=False),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("actual_size", sa.BigInteger(), nullable=True),
        sa.Column("expected_sha256", sa.String(64), nullable=False),
        sa.Column("actual_sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.String(64), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("purpose_code = 'FINANCIAL_RECEIPT'", name="valid_purpose"),
        sa.CheckConstraint(
            "state IN ('PENDING','QUARANTINED','AVAILABLE','FAILED','EXPIRED','DELETED')",
            name="valid_state",
        ),
        sa.CheckConstraint(
            "declared_media_type IN ('application/pdf','image/jpeg','image/png')",
            name="valid_declared_media_type",
        ),
        sa.CheckConstraint(
            "detected_media_type IS NULL OR detected_media_type IN ('application/pdf','image/jpeg','image/png')",
            name="valid_detected_media_type",
        ),
        sa.CheckConstraint("expected_size BETWEEN 1 AND 10485760", name="valid_expected_size"),
        sa.CheckConstraint(
            "actual_size IS NULL OR actual_size BETWEEN 1 AND 10485760", name="valid_actual_size"
        ),
        sa.CheckConstraint("expected_sha256 ~ '^[0-9a-f]{64}$'", name="valid_expected_sha256"),
        sa.CheckConstraint(
            "actual_sha256 IS NULL OR actual_sha256 ~ '^[0-9a-f]{64}$'", name="valid_actual_sha256"
        ),
        sa.CheckConstraint("storage_key ~ '^[0-9a-f]{64}$'", name="valid_storage_key"),
        sa.CheckConstraint(
            "char_length(sanitized_filename) BETWEEN 1 AND 128", name="valid_filename"
        ),
        sa.CheckConstraint(
            "(state = 'PENDING' AND uploaded_at IS NULL AND scanned_at IS NULL AND available_at IS NULL AND deleted_at IS NULL AND failure_code IS NULL) OR "
            "(state = 'QUARANTINED' AND uploaded_at IS NOT NULL AND scanned_at IS NULL AND available_at IS NULL AND deleted_at IS NULL AND failure_code IS NULL) OR "
            "(state = 'AVAILABLE' AND uploaded_at IS NOT NULL AND scanned_at IS NOT NULL AND available_at IS NOT NULL AND deleted_at IS NULL AND failure_code IS NULL) OR "
            "(state IN ('FAILED','EXPIRED') AND available_at IS NULL AND deleted_at IS NULL AND failure_code IS NOT NULL) OR "
            "(state = 'DELETED' AND deleted_at IS NOT NULL)",
            name="valid_lifecycle",
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        _actor("created_by_membership_id", "fk_protected_file_creator"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_protected_file_workspace",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_protected_files"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_protected_file_workspace_id"),
        sa.UniqueConstraint("workspace_id", "operation_id", name="uq_protected_file_operation"),
        sa.UniqueConstraint("storage_key", name="uq_protected_file_storage_key"),
    )
    op.create_index(
        "ix_protected_file_workspace_state_created",
        "protected_files",
        ["workspace_id", "state", "created_at"],
    )
    op.create_index(
        "ix_protected_file_cleanup",
        "protected_files",
        ["state", "cleanup_after"],
        postgresql_where=sa.text("cleanup_after IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table(
        "financial_event_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("protected_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attachment_role", sa.String(32), nullable=False),
        sa.Column("attached_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "attached_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("removed_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removal_reason", sa.String(64), nullable=True),
        sa.Column("removal_operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("attachment_role = 'RECEIPT'", name="valid_role"),
        sa.CheckConstraint(
            "(removed_at IS NULL AND removed_by_membership_id IS NULL AND removal_reason IS NULL AND removal_operation_id IS NULL) OR (removed_at IS NOT NULL AND removed_by_membership_id IS NOT NULL AND removal_reason IS NOT NULL AND removal_operation_id IS NOT NULL)",
            name="valid_removal",
        ),
        _actor("attached_by_membership_id", "fk_financial_event_file_attacher"),
        _actor("removed_by_membership_id", "fk_financial_event_file_remover"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "financial_event_id"],
            ["financial_events.workspace_id", "financial_events.id"],
            name="fk_financial_event_file_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "protected_file_id"],
            ["protected_files.workspace_id", "protected_files.id"],
            name="fk_financial_event_file_file",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_financial_event_files"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_financial_event_file_workspace_id"),
    )
    op.create_index(
        "uq_financial_event_file_active",
        "financial_event_files",
        ["workspace_id", "financial_event_id", "protected_file_id"],
        unique=True,
        postgresql_where=sa.text("removed_at IS NULL"),
    )
    op.create_index(
        "ix_financial_event_file_workspace_event_attached",
        "financial_event_files",
        ["workspace_id", "financial_event_id", "attached_at", "id"],
    )

    op.execute("""
    CREATE FUNCTION f2s_guard_protected_file_history() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'PROTECTED_FILE_HARD_DELETE_PROHIBITED' USING ERRCODE='integrity_constraint_violation'; END IF;
      IF OLD.id IS DISTINCT FROM NEW.id OR OLD.workspace_id IS DISTINCT FROM NEW.workspace_id
         OR OLD.purpose_code IS DISTINCT FROM NEW.purpose_code OR OLD.declared_media_type IS DISTINCT FROM NEW.declared_media_type
         OR OLD.sanitized_filename IS DISTINCT FROM NEW.sanitized_filename OR OLD.expected_size IS DISTINCT FROM NEW.expected_size
         OR OLD.expected_sha256 IS DISTINCT FROM NEW.expected_sha256 OR OLD.storage_key IS DISTINCT FROM NEW.storage_key
         OR OLD.operation_id IS DISTINCT FROM NEW.operation_id OR OLD.created_by_membership_id IS DISTINCT FROM NEW.created_by_membership_id
         OR OLD.created_at IS DISTINCT FROM NEW.created_at OR OLD.reservation_expires_at IS DISTINCT FROM NEW.reservation_expires_at
         OR (OLD.state <> 'PENDING' AND (OLD.detected_media_type IS DISTINCT FROM NEW.detected_media_type
              OR OLD.actual_size IS DISTINCT FROM NEW.actual_size OR OLD.actual_sha256 IS DISTINCT FROM NEW.actual_sha256
              OR OLD.uploaded_at IS DISTINCT FROM NEW.uploaded_at))
         OR NEW.version IS DISTINCT FROM OLD.version + 1
         OR NOT ((OLD.state='PENDING' AND NEW.state IN ('QUARANTINED','FAILED','EXPIRED'))
              OR (OLD.state='QUARANTINED' AND NEW.state IN ('AVAILABLE','FAILED'))
              OR (OLD.state IN ('FAILED','EXPIRED','AVAILABLE') AND NEW.state='DELETED')) THEN
        RAISE EXCEPTION 'PROTECTED_FILE_INVALID_TRANSITION' USING ERRCODE='integrity_constraint_violation';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER tr_protected_file_history_guard BEFORE UPDATE OR DELETE ON protected_files
    FOR EACH ROW EXECUTE FUNCTION f2s_guard_protected_file_history();
    """)
    op.execute("""
    CREATE FUNCTION f2s_guard_financial_event_file_history() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'FINANCIAL_EVENT_FILE_HARD_DELETE_PROHIBITED' USING ERRCODE='integrity_constraint_violation'; END IF;
      IF OLD.id IS DISTINCT FROM NEW.id OR OLD.workspace_id IS DISTINCT FROM NEW.workspace_id
         OR OLD.financial_event_id IS DISTINCT FROM NEW.financial_event_id OR OLD.protected_file_id IS DISTINCT FROM NEW.protected_file_id
         OR OLD.attachment_role IS DISTINCT FROM NEW.attachment_role OR OLD.attached_by_membership_id IS DISTINCT FROM NEW.attached_by_membership_id
         OR OLD.attached_at IS DISTINCT FROM NEW.attached_at OR OLD.removed_at IS NOT NULL OR NEW.removed_at IS NULL THEN
        RAISE EXCEPTION 'FINANCIAL_EVENT_FILE_IMMUTABLE' USING ERRCODE='integrity_constraint_violation';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER tr_financial_event_file_history_guard BEFORE UPDATE OR DELETE ON financial_event_files
    FOR EACH ROW EXECUTE FUNCTION f2s_guard_financial_event_file_history();
    """)


def downgrade() -> None:
    op.drop_table("financial_event_files")
    op.execute("DROP FUNCTION f2s_guard_financial_event_file_history()")
    op.drop_table("protected_files")
    op.execute("DROP FUNCTION f2s_guard_protected_file_history()")
