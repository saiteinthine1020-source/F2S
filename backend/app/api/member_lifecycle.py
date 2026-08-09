"""Admin-only membership listing and versioned lifecycle HTTP boundary."""

import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import correlation_for, safe_error
from app.api.security import AuthenticatedAccountId
from app.api.workspace_settings import PreconditionRequired
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.member_lifecycle import (
    SqlAlchemyMemberLifecycleRepository,
)
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.modules.audit import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditReason,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.member_lifecycle import (
    InvalidMembershipTransition,
    MemberLifecycleService,
    MemberReference,
    MembershipStatus,
    MemberVersionMismatch,
    OwnershipInvariantViolation,
)
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    WorkspaceRole,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["members"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')


class MemberRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str
    display_name: str
    role: WorkspaceRole
    status: MembershipStatus
    account_status: str
    preferred_language: Literal["en", "ja", "my", "shn"]
    timezone: str
    last_login_at: datetime | None
    created_at: datetime
    version: int


class MemberEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: MemberRepresentation


class MemberListEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: tuple[MemberRepresentation, ...]


class MemberUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: WorkspaceRole | None = None
    status: Literal[MembershipStatus.SUSPENDED] | None = None


class EmptyCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def service_for(session: AsyncSession) -> MemberLifecycleService:
    return MemberLifecycleService(SqlAlchemyMemberLifecycleRepository(session))


def _representation(member: MemberReference) -> MemberRepresentation:
    return MemberRepresentation(
        id=member.id,
        email=member.email,
        display_name=member.display_name,
        role=member.role,
        status=member.status,
        account_status=member.account_status,
        preferred_language=member.preferred_language,
        timezone=member.timezone,
        last_login_at=member.last_login_at,
        created_at=member.created_at,
        version=member.version,
    )


def _etag(version: int) -> str:
    return f'"v{version}"'


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise MemberVersionMismatch
    return int(match.group(1))


def authorization_error(request: Request, error: AuthorizationDenied) -> Response:
    not_found = error.code is DenialCode.RESOURCE_NOT_FOUND
    return safe_error(
        status_code=404 if not_found else 403,
        code="RESOURCE_NOT_FOUND" if not_found else "PERMISSION_DENIED",
        message=(
            "The requested resource was not found."
            if not_found
            else "The operation is not permitted."
        ),
        correlation_id=correlation_for(request),
    )


async def _resolve_context(
    session: AsyncSession,
    *,
    actor_account_id: UUID,
    workspace_id: UUID,
    correlation_id: UUID,
) -> AuthorizationContext:
    try:
        return await SqlAlchemyWorkspaceAccessRepository(session).resolve_context(
            actor_account_id=actor_account_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
        )
    except AuthorizationDenied as error:
        reason = {
            DenialCode.ACCOUNT_INACTIVE: AuditReason.ACCOUNT_INACTIVE,
            DenialCode.MEMBERSHIP_INACTIVE: AuditReason.MEMBERSHIP_INACTIVE,
            DenialCode.WORKSPACE_INACTIVE: AuditReason.WORKSPACE_INACTIVE,
            DenialCode.PERMISSION_DENIED: AuditReason.PERMISSION_DENIED,
        }.get(error.code, AuditReason.RESOURCE_NOT_FOUND)
        await SqlAlchemyAuditWriter(session).append(
            AuditEventIntent(
                scope=AuditScope.GLOBAL,
                actor=AuditActor.user(actor_account_id),
                action=AuditAction.CROSS_WORKSPACE_ACCESS_DENIED,
                module=AuditModule.WORKSPACE_ACCESS,
                result=AuditResult.DENIED,
                correlation_id=correlation_id,
                resource_type=AuditResourceType.WORKSPACE,
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.MEMBERSHIP_ADMINISTRATION,
            )
        )
        raise


async def audit_denial(
    session: AsyncSession,
    context: AuthorizationContext,
    action: AuditAction,
    reason: AuditReason,
) -> None:
    await SqlAlchemyAuditWriter(session).append(
        AuditEventIntent(
            scope=AuditScope.WORKSPACE,
            workspace_id=context.workspace_id,
            actor=AuditActor.user(context.actor_account_id, context.membership_id),
            action=action,
            module=AuditModule.WORKSPACE_ACCESS,
            result=AuditResult.DENIED,
            correlation_id=context.correlation_id,
            resource_type=AuditResourceType.WORKSPACE_MEMBERSHIP,
            reason=reason,
            source=AuditSource.API,
            context=AuditContext.MEMBERSHIP_ADMINISTRATION,
        )
    )


async def context_or_error(
    request: Request,
    session: AsyncSession,
    account_id: UUID,
    workspace_id: UUID,
) -> AuthorizationContext | Response:
    try:
        return await _resolve_context(
            session,
            actor_account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
    except AuthorizationDenied as error:
        return authorization_error(request, error)


async def _mutation_error(
    request: Request,
    session: AsyncSession,
    context: AuthorizationContext,
    action: AuditAction,
    error: Exception,
) -> Response:
    if isinstance(error, AuthorizationDenied):
        await audit_denial(
            session,
            context,
            action,
            (
                AuditReason.RESOURCE_NOT_FOUND
                if error.code is DenialCode.RESOURCE_NOT_FOUND
                else AuditReason.PERMISSION_DENIED
            ),
        )
        return authorization_error(request, error)
    if isinstance(error, MemberVersionMismatch):
        return safe_error(
            status_code=412,
            code="VERSION_MISMATCH",
            message="The resource version is no longer current.",
            correlation_id=correlation_for(request),
        )
    if isinstance(error, OwnershipInvariantViolation):
        await audit_denial(session, context, action, AuditReason.OWNERSHIP_INVARIANT)
        return safe_error(
            status_code=409,
            code="OWNERSHIP_TRANSFER_REQUIRED",
            message="Workspace ownership requires the dedicated transfer flow.",
            correlation_id=correlation_for(request),
        )
    if isinstance(error, InvalidMembershipTransition):
        return safe_error(
            status_code=409,
            code="INVALID_STATE_TRANSITION",
            message="The membership cannot make that state transition.",
            correlation_id=correlation_for(request),
        )
    raise error


@router.get("/{workspace_id}/members", response_model=MemberListEnvelope)
async def list_members(
    workspace_id: UUID,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> MemberListEnvelope | Response:
    context = await context_or_error(request, session, account_id, workspace_id)
    if isinstance(context, Response):
        return context
    try:
        members = await service_for(session).list_members(context)
    except AuthorizationDenied as error:
        return authorization_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    return MemberListEnvelope(data=tuple(_representation(member) for member in members))


@router.patch("/{workspace_id}/members/{membership_id}", response_model=MemberEnvelope)
async def update_member(
    workspace_id: UUID,
    membership_id: UUID,
    payload: MemberUpdateRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> MemberEnvelope | Response:
    del browser
    expected_version = _expected_version(if_match)
    context = await context_or_error(request, session, account_id, workspace_id)
    if isinstance(context, Response):
        return context
    fields = payload.model_fields_set
    if (
        fields not in ({"role"}, {"status"})
        or ("role" in fields and payload.role is None)
        or ("status" in fields and payload.status is None)
    ):
        await audit_denial(
            session, context, AuditAction.MEMBER_ROLE_CHANGED, AuditReason.VALIDATION_FAILED
        )
        return safe_error(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The request contains invalid fields.",
            correlation_id=correlation_for(request),
        )
    service = service_for(session)
    action = AuditAction.MEMBER_ROLE_CHANGED if "role" in fields else AuditAction.MEMBER_SUSPENDED
    try:
        member = (
            await service.change_role(
                context,
                membership_id=membership_id,
                expected_version=expected_version,
                role=payload.role,
                now=datetime.now(UTC),
            )
            if payload.role is not None
            else await service.suspend(
                context,
                membership_id=membership_id,
                expected_version=expected_version,
                now=datetime.now(UTC),
            )
        )
    except (
        AuthorizationDenied,
        MemberVersionMismatch,
        OwnershipInvariantViolation,
        InvalidMembershipTransition,
    ) as error:
        return await _mutation_error(request, session, context, action, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(member.version)
    return MemberEnvelope(data=_representation(member))


@router.post(
    "/{workspace_id}/members/{membership_id}/reactivate",
    response_model=MemberEnvelope,
)
async def reactivate_member(
    workspace_id: UUID,
    membership_id: UUID,
    payload: EmptyCommandRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> MemberEnvelope | Response:
    del payload, browser
    return await _command(
        workspace_id=workspace_id,
        membership_id=membership_id,
        request=request,
        response=response,
        account_id=account_id,
        session=session,
        if_match=if_match,
        action=AuditAction.MEMBER_REACTIVATED,
    )


@router.delete(
    "/{workspace_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_member(
    workspace_id: UUID,
    membership_id: UUID,
    payload: EmptyCommandRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> None | Response:
    del payload, browser
    result = await _command(
        workspace_id=workspace_id,
        membership_id=membership_id,
        request=request,
        response=response,
        account_id=account_id,
        session=session,
        if_match=if_match,
        action=AuditAction.MEMBER_REVOKED,
    )
    if isinstance(result, Response):
        return result
    response.headers["Cache-Control"] = "no-store"
    return None


async def _command(
    *,
    workspace_id: UUID,
    membership_id: UUID,
    request: Request,
    response: Response,
    account_id: UUID,
    session: AsyncSession,
    if_match: str | None,
    action: AuditAction,
) -> MemberEnvelope | Response:
    expected_version = _expected_version(if_match)
    context = await context_or_error(request, session, account_id, workspace_id)
    if isinstance(context, Response):
        return context
    try:
        member = (
            await service_for(session).reactivate(
                context,
                membership_id=membership_id,
                expected_version=expected_version,
                now=datetime.now(UTC),
            )
            if action is AuditAction.MEMBER_REACTIVATED
            else await service_for(session).revoke(
                context,
                membership_id=membership_id,
                expected_version=expected_version,
                now=datetime.now(UTC),
            )
        )
    except (
        AuthorizationDenied,
        MemberVersionMismatch,
        OwnershipInvariantViolation,
        InvalidMembershipTransition,
    ) as error:
        return await _mutation_error(request, session, context, action, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(member.version)
    return MemberEnvelope(data=_representation(member))
