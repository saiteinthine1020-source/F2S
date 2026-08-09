"""Append-only Audit persistence mapping introduced by Issue #44."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AuditEvent(Base):
    """Minimal structured action/result evidence without secret-bearing payloads."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("scope_code IN ('GLOBAL', 'WORKSPACE')", name="valid_scope"),
        CheckConstraint(
            "(scope_code = 'GLOBAL' AND workspace_id IS NULL) OR "
            "(scope_code = 'WORKSPACE' AND workspace_id IS NOT NULL)",
            name="scope_workspace_consistency",
        ),
        CheckConstraint("actor_type_code IN ('SYSTEM', 'USER')", name="valid_actor_type"),
        CheckConstraint(
            "(actor_type_code = 'SYSTEM' AND actor_user_account_id IS NULL "
            "AND actor_membership_id IS NULL) OR "
            "(actor_type_code = 'USER' AND actor_user_account_id IS NOT NULL)",
            name="actor_identity_consistency",
        ),
        CheckConstraint(
            "actor_membership_id IS NULL OR workspace_id IS NOT NULL",
            name="membership_requires_workspace",
        ),
        CheckConstraint("action_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="valid_action_code"),
        CheckConstraint("module_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="valid_module_code"),
        CheckConstraint("result_code IN ('SUCCEEDED', 'FAILED', 'DENIED')", name="valid_result"),
        ForeignKeyConstraint(
            ["workspace_id", "actor_membership_id", "actor_user_account_id"],
            [
                "workspace_memberships.workspace_id",
                "workspace_memberships.id",
                "workspace_memberships.user_account_id",
            ],
            name="fk_audit_actor_membership_identity",
        ),
        Index("ix_audit_workspace_occurred", "workspace_id", "occurred_at", "id"),
        Index("ix_audit_action_occurred", "action_code", "occurred_at"),
        Index("ix_audit_actor_occurred", "actor_user_account_id", "occurred_at"),
        Index("ix_audit_resource", "resource_type_code", "resource_id", "occurred_at"),
        Index("ix_audit_correlation", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    scope_code: Mapped[str] = mapped_column(String(16), nullable=False)
    workspace_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workspaces.id")
    )
    actor_type_code: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_account_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_accounts.id")
    )
    actor_membership_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    action_code: Mapped[str] = mapped_column(String(64), nullable=False)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type_code: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    result_code: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    source_code: Mapped[str | None] = mapped_column(String(64))
    context_code: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
