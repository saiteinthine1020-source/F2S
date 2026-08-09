"""Identity-owned persistence mappings introduced by Issue #43."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class BootstrapState(Base):
    """Serialized installation bootstrap state; exactly one key may exist."""

    __tablename__ = "bootstrap_state"
    __table_args__ = (
        CheckConstraint("singleton_key = 'INSTALLATION'", name="singleton_installation"),
        CheckConstraint("version > 0", name="positive_version"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    singleton_key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class UserAccount(Base):
    """Global login identity; credentials and challenges are intentionally separate."""

    __tablename__ = "user_accounts"
    __table_args__ = (
        CheckConstraint(
            "normalized_email = lower(btrim(normalized_email))",
            name="normalized_email_canonical",
        ),
        CheckConstraint("position('@' in normalized_email) > 1", name="normalized_email_shape"),
        CheckConstraint(
            "status IN ('PENDING_ACTIVATION', 'ACTIVE', 'SUSPENDED', 'LOCKED', 'CLOSED')",
            name="valid_status",
        ),
        CheckConstraint("char_length(btrim(display_name)) > 0", name="display_name_not_blank"),
        CheckConstraint("version > 0", name="positive_version"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_digest: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
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
