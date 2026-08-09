"""Digest-only Identity security persistence mappings introduced by Issue #44."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AuthSession(Base):
    """One opaque credential generation in a rotating, revocable session family."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ROTATED', 'REVOKED', 'EXPIRED', 'REUSE_DETECTED')",
            name="valid_status",
        ),
        CheckConstraint("digest_algorithm_code = 'SHA256'", name="valid_digest_algorithm"),
        CheckConstraint("access_expires_at > issued_at", name="access_expiry_after_issue"),
        CheckConstraint("refresh_idle_expires_at > issued_at", name="idle_expiry_after_issue"),
        CheckConstraint("absolute_expires_at > issued_at", name="absolute_expiry_after_issue"),
        CheckConstraint(
            "access_expires_at <= absolute_expires_at", name="access_within_absolute_expiry"
        ),
        CheckConstraint(
            "refresh_idle_expires_at <= absolute_expires_at", name="idle_within_absolute_expiry"
        ),
        CheckConstraint(
            "(status IN ('ROTATED', 'REUSE_DETECTED')) = (last_rotated_at IS NOT NULL)",
            name="rotation_evidence",
        ),
        CheckConstraint(
            "(status IN ('REVOKED', 'REUSE_DETECTED')) = "
            "(revoked_at IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="revocation_evidence",
        ),
        CheckConstraint(
            "(status = 'REUSE_DETECTED') = (reuse_detected_at IS NOT NULL)",
            name="reuse_evidence",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint("rotated_from_session_id", name="uq_session_single_rotation_child"),
        Index("ix_session_account_status", "user_account_id", "status"),
        Index("ix_session_family_status", "family_id", "status"),
        Index("ix_session_account_absolute_expiry", "user_account_id", "absolute_expires_at"),
        Index("ix_session_idle_expiry", "refresh_idle_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_accounts.id"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    rotated_from_session_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("auth_sessions.id")
    )
    access_credential_digest: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    refresh_credential_digest: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    csrf_credential_digest: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    digest_algorithm_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SHA256", server_default="SHA256"
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason_code: Mapped[str | None] = mapped_column(String(64))
    reuse_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")


class ActivationChallenge(Base):
    """Single-use membership activation evidence with no recoverable bearer value."""

    __tablename__ = "activation_challenges"
    __table_args__ = (
        CheckConstraint("status IN ('ISSUED', 'USED', 'REVOKED', 'EXPIRED')", name="valid_status"),
        CheckConstraint("digest_algorithm_code = 'SHA256'", name="valid_digest_algorithm"),
        CheckConstraint("expires_at > issued_at", name="expiry_after_issue"),
        CheckConstraint("(status = 'USED') = (used_at IS NOT NULL)", name="use_evidence"),
        CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="revocation_evidence",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        ForeignKeyConstraint(
            ["workspace_id", "membership_id", "user_account_id"],
            [
                "workspace_memberships.workspace_id",
                "workspace_memberships.id",
                "workspace_memberships.user_account_id",
            ],
            name="fk_activation_membership_identity",
        ),
        Index("ix_activation_membership_status", "workspace_id", "membership_id", "status"),
        Index("ix_activation_account_expiry", "user_account_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    user_account_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    challenge_digest: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    digest_algorithm_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SHA256", server_default="SHA256"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")


class RecoveryChallenge(Base):
    """Concealed, expiring account recovery evidence stored only as a digest."""

    __tablename__ = "recovery_challenges"
    __table_args__ = (
        CheckConstraint("status IN ('ISSUED', 'USED', 'REVOKED', 'EXPIRED')", name="valid_status"),
        CheckConstraint("digest_algorithm_code = 'SHA256'", name="valid_digest_algorithm"),
        CheckConstraint("expires_at > issued_at", name="expiry_after_issue"),
        CheckConstraint("(status = 'USED') = (used_at IS NOT NULL)", name="use_evidence"),
        CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="revocation_evidence",
        ),
        CheckConstraint("attempt_count >= 0", name="nonnegative_attempt_count"),
        CheckConstraint("version > 0", name="positive_version"),
        Index("ix_recovery_account_status", "user_account_id", "status"),
        Index("ix_recovery_account_expiry", "user_account_id", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_accounts.id"), nullable=False
    )
    challenge_digest: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    digest_algorithm_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="SHA256", server_default="SHA256"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")
