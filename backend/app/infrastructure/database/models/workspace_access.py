"""Workspace Access-owned persistence mappings introduced by Issue #43."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Workspace(Base):
    """Stable tenant boundary with a database-enforced Active Admin owner."""

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "type IN ('HOUSEHOLD', 'FARM', 'MICROBUSINESS', 'SMALL_BUSINESS', "
            "'COMBINED', 'CUSTOM')",
            name="valid_type",
        ),
        CheckConstraint("base_currency_code ~ '^[A-Z]{3}$'", name="valid_currency_code"),
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')", name="valid_status"),
        CheckConstraint("owner_role = 'ADMIN'", name="owner_role_admin"),
        CheckConstraint("owner_membership_status = 'ACTIVE'", name="owner_status_active"),
        CheckConstraint("version > 0", name="positive_version"),
        ForeignKeyConstraint(
            ["id", "owner_membership_id", "owner_role", "owner_membership_status"],
            [
                "workspace_memberships.workspace_id",
                "workspace_memberships.id",
                "workspace_memberships.role",
                "workspace_memberships.status",
            ],
            name="fk_workspaces_owner_membership_workspace_memberships",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    business_category_code: Mapped[str | None] = mapped_column(String(64))
    farm_type_code: Mapped[str | None] = mapped_column(String(64))
    owner_membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(16), nullable=False, default="ADMIN")
    owner_membership_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE"
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
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


class WorkspaceMembership(Base):
    """Account access, role, and lifecycle within one workspace."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'CONTRIBUTOR', 'ADVISOR')", name="valid_role"),
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'REVOKED')", name="valid_status"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint("workspace_id", "user_account_id", name="uq_membership_workspace_user"),
        UniqueConstraint("workspace_id", "id", name="uq_membership_workspace_id"),
        UniqueConstraint(
            "workspace_id", "id", "role", "status", name="uq_membership_owner_reference"
        ),
        Index("ix_membership_workspace_status", "workspace_id", "status"),
        Index("ix_membership_user_status", "user_account_id", "status"),
        Index(
            "uq_membership_one_active_admin",
            "workspace_id",
            unique=True,
            postgresql_where=text("role = 'ADMIN' AND status = 'ACTIVE'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    user_account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_accounts.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
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


class WorkspaceModule(Base):
    """Explicit per-workspace module enablement state."""

    __tablename__ = "workspace_modules"
    __table_args__ = (
        CheckConstraint("module_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="valid_module_code"),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint("workspace_id", "module_code", name="uq_module_workspace_code"),
        UniqueConstraint("workspace_id", "id", name="uq_module_workspace_id"),
        Index("ix_module_workspace_enabled", "workspace_id", "enabled"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
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
