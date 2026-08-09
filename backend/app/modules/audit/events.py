"""Bounded, framework-free audit intent vocabulary and invariants."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AuditScope(StrEnum):
    GLOBAL = "GLOBAL"
    WORKSPACE = "WORKSPACE"


class AuditActorType(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"


class AuditResult(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"


class AuditModule(StrEnum):
    IDENTITY_SECURITY = "IDENTITY_SECURITY"
    WORKSPACE_ACCESS = "WORKSPACE_ACCESS"


class AuditAction(StrEnum):
    BOOTSTRAP_COMPLETED = "BOOTSTRAP_COMPLETED"
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_ROTATED = "SESSION_ROTATED"
    SESSION_REUSE_DETECTED = "SESSION_REUSE_DETECTED"
    SESSION_REVOKED = "SESSION_REVOKED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    RECOVERY_REQUESTED = "RECOVERY_REQUESTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_RENAMED = "WORKSPACE_RENAMED"
    MEMBER_CREATED = "MEMBER_CREATED"
    MEMBER_ACTIVATED = "MEMBER_ACTIVATED"
    MEMBER_ROLE_CHANGED = "MEMBER_ROLE_CHANGED"
    MEMBER_SUSPENDED = "MEMBER_SUSPENDED"
    MEMBER_REACTIVATED = "MEMBER_REACTIVATED"
    MEMBER_REVOKED = "MEMBER_REVOKED"
    ACTIVATION_RESTARTED = "ACTIVATION_RESTARTED"
    OWNERSHIP_TRANSFER_INITIATED = "OWNERSHIP_TRANSFER_INITIATED"
    OWNERSHIP_TRANSFER_CONFIRMED = "OWNERSHIP_TRANSFER_CONFIRMED"
    OWNERSHIP_TRANSFER_CANCELLED = "OWNERSHIP_TRANSFER_CANCELLED"
    OWNERSHIP_TRANSFER_EXPIRED = "OWNERSHIP_TRANSFER_EXPIRED"
    OWNERSHIP_TRANSFER_COMPLETED = "OWNERSHIP_TRANSFER_COMPLETED"
    CROSS_WORKSPACE_ACCESS_DENIED = "CROSS_WORKSPACE_ACCESS_DENIED"


class AuditResourceType(StrEnum):
    USER_ACCOUNT = "USER_ACCOUNT"
    SESSION = "SESSION"
    WORKSPACE = "WORKSPACE"
    WORKSPACE_MEMBERSHIP = "WORKSPACE_MEMBERSHIP"
    OWNERSHIP_TRANSFER = "OWNERSHIP_TRANSFER"


class AuditReason(StrEnum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    MEMBERSHIP_INACTIVE = "MEMBERSHIP_INACTIVE"
    WORKSPACE_INACTIVE = "WORKSPACE_INACTIVE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    EXPIRED = "EXPIRED"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    REVOKED = "REVOKED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class AuditSource(StrEnum):
    API = "API"
    BACKGROUND_JOB = "BACKGROUND_JOB"
    SYSTEM = "SYSTEM"


class AuditContext(StrEnum):
    BOOTSTRAP = "BOOTSTRAP"
    AUTHENTICATION = "AUTHENTICATION"
    ACTIVATION = "ACTIVATION"
    RECOVERY = "RECOVERY"
    MEMBERSHIP_ADMINISTRATION = "MEMBERSHIP_ADMINISTRATION"
    OWNERSHIP_TRANSFER = "OWNERSHIP_TRANSFER"
    WORKSPACE_SETTINGS = "WORKSPACE_SETTINGS"


@dataclass(frozen=True, slots=True)
class AuditActor:
    """System or safely referenced user actor."""

    type: AuditActorType
    account_id: UUID | None = None
    membership_id: UUID | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.type, AuditActorType):
            raise ValueError("INVALID_ACTOR_TYPE")
        if self.account_id is not None and not isinstance(self.account_id, UUID):
            raise ValueError("INVALID_ACTOR_ACCOUNT_ID")
        if self.membership_id is not None and not isinstance(self.membership_id, UUID):
            raise ValueError("INVALID_ACTOR_MEMBERSHIP_ID")
        if self.type is AuditActorType.SYSTEM and (
            self.account_id is not None or self.membership_id is not None
        ):
            raise ValueError("SYSTEM_ACTOR_MUST_NOT_HAVE_IDENTITY")
        if self.type is AuditActorType.USER and self.account_id is None:
            raise ValueError("USER_ACTOR_REQUIRES_ACCOUNT")
        if self.membership_id is not None and self.account_id is None:
            raise ValueError("MEMBERSHIP_REQUIRES_ACCOUNT")

    @classmethod
    def system(cls) -> "AuditActor":
        return cls(type=AuditActorType.SYSTEM)

    @classmethod
    def user(cls, account_id: UUID, membership_id: UUID | None = None) -> "AuditActor":
        return cls(
            type=AuditActorType.USER,
            account_id=account_id,
            membership_id=membership_id,
        )


@dataclass(frozen=True, slots=True)
class AuditEventIntent:
    """Validated evidence intent containing only bounded safe metadata."""

    scope: AuditScope
    actor: AuditActor
    action: AuditAction
    module: AuditModule
    result: AuditResult
    correlation_id: UUID
    workspace_id: UUID | None = None
    resource_type: AuditResourceType | None = None
    resource_id: UUID | None = None
    reason: AuditReason | None = None
    source: AuditSource | None = None
    context: AuditContext | None = None

    def __post_init__(self) -> None:
        bounded_values = (
            (self.scope, AuditScope, "INVALID_AUDIT_SCOPE"),
            (self.action, AuditAction, "INVALID_AUDIT_ACTION"),
            (self.module, AuditModule, "INVALID_AUDIT_MODULE"),
            (self.result, AuditResult, "INVALID_AUDIT_RESULT"),
            (self.resource_type, AuditResourceType, "INVALID_AUDIT_RESOURCE_TYPE"),
            (self.reason, AuditReason, "INVALID_AUDIT_REASON"),
            (self.source, AuditSource, "INVALID_AUDIT_SOURCE"),
            (self.context, AuditContext, "INVALID_AUDIT_CONTEXT"),
        )
        for value, expected_type, error_code in bounded_values:
            if value is not None and not isinstance(value, expected_type):
                raise ValueError(error_code)
        if not isinstance(self.actor, AuditActor):
            raise ValueError("INVALID_AUDIT_ACTOR")
        if not isinstance(self.correlation_id, UUID):
            raise ValueError("INVALID_CORRELATION_ID")
        if self.workspace_id is not None and not isinstance(self.workspace_id, UUID):
            raise ValueError("INVALID_WORKSPACE_ID")
        if self.resource_id is not None and not isinstance(self.resource_id, UUID):
            raise ValueError("INVALID_RESOURCE_ID")
        if self.scope is AuditScope.GLOBAL and self.workspace_id is not None:
            raise ValueError("GLOBAL_EVENT_MUST_NOT_REFERENCE_WORKSPACE")
        if self.scope is AuditScope.WORKSPACE and self.workspace_id is None:
            raise ValueError("WORKSPACE_EVENT_REQUIRES_WORKSPACE")
        if self.actor.membership_id is not None and self.scope is not AuditScope.WORKSPACE:
            raise ValueError("MEMBERSHIP_ACTOR_REQUIRES_WORKSPACE_SCOPE")
        if self.resource_id is not None and self.resource_type is None:
            raise ValueError("RESOURCE_ID_REQUIRES_TYPE")
        if self.result is AuditResult.DENIED and self.resource_id is not None:
            raise ValueError("DENIED_EVENT_MUST_NOT_DISCLOSE_RESOURCE_ID")

    @classmethod
    def denied_cross_workspace(
        cls, *, actor_account_id: UUID, correlation_id: UUID, source: AuditSource
    ) -> "AuditEventIntent":
        """Build concealed denial evidence without accepting a foreign identifier."""
        return cls(
            scope=AuditScope.GLOBAL,
            actor=AuditActor.user(actor_account_id),
            action=AuditAction.CROSS_WORKSPACE_ACCESS_DENIED,
            module=AuditModule.WORKSPACE_ACCESS,
            result=AuditResult.DENIED,
            correlation_id=correlation_id,
            resource_type=AuditResourceType.WORKSPACE,
            reason=AuditReason.RESOURCE_NOT_FOUND,
            source=source,
        )
