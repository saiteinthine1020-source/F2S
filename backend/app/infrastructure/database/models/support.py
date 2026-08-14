"""Application Support persistence mappings."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class IdempotencyRecord(Base):
    """Digest-only replay evidence; request and response bodies are never stored."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        CheckConstraint("operation_code ~ '^[A-Z][A-Z0-9_]{2,63}$'", name="valid_operation_code"),
        CheckConstraint("key_digest ~ '^[0-9a-f]{64}$'", name="valid_key_digest"),
        CheckConstraint("request_fingerprint ~ '^[0-9a-f]{64}$'", name="valid_request_fingerprint"),
        CheckConstraint("state IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')", name="valid_state"),
        CheckConstraint(
            "outcome_code IS NULL OR outcome_code ~ '^[A-Z][A-Z0-9_]{2,63}$'",
            name="valid_outcome_code",
        ),
        CheckConstraint(
            "resource_type_code IS NULL OR resource_type_code ~ '^[A-Z][A-Z0-9_]{2,63}$'",
            name="valid_resource_type_code",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "(resource_type_code IS NULL AND resource_id IS NULL AND resource_version IS NULL) "
            "OR (resource_type_code IS NOT NULL AND resource_id IS NOT NULL "
            "AND resource_version > 0)",
            name="complete_resource_reference",
        ),
        CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599", name="valid_http_status"
        ),
        CheckConstraint(
            "expires_at IS NULL OR (completed_at IS NOT NULL AND expires_at > completed_at)",
            name="valid_expiry",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "actor_membership_id"],
            ["workspace_memberships.workspace_id", "workspace_memberships.id"],
            name="fk_idempotency_actor",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "operation_id", name="uq_idempotency_operation_id"),
        UniqueConstraint(
            "workspace_id",
            "operation_code",
            "key_digest",
            name="uq_idempotency_scope_key",
        ),
        Index("ix_idempotency_expiry", "expires_at", "id"),
        Index("ix_idempotency_workspace_state", "workspace_id", "state", "updated_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    operation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    lease_token: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_code: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    resource_type_code: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    resource_version: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
