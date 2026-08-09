"""Eligible workspace retrieval and Admin-only optimistic settings API."""

import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bootstrap import Session
from app.api.browser_security import BrowserRequest, require_browser_request
from app.api.errors import correlation_for, safe_error
from app.api.security import AuthenticatedAccountId
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.infrastructure.database.repositories.workspace_access import (
    SqlAlchemyWorkspaceAccessRepository,
)
from app.infrastructure.database.repositories.workspace_directory import (
    SqlAlchemyWorkspaceDirectoryRepository,
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
from app.modules.workspace_access import (
    AuthorizationContext,
    AuthorizationDenied,
    DenialCode,
    ModuleCode,
    ModuleSetting,
    WorkspaceDirectoryService,
    WorkspaceRole,
    WorkspaceSettingsPatch,
    WorkspaceSettingsService,
    WorkspaceType,
    WorkspaceVersionMismatch,
)

router = APIRouter(prefix="/api/v1", tags=["workspaces"])
BrowserBoundary = Annotated[BrowserRequest, Depends(require_browser_request)]
IfMatch = Annotated[str | None, Header(alias="If-Match")]
_ETAG = re.compile(r'^"v([1-9][0-9]*)"$')


class PreconditionRequired(Exception):
    """A mutation omitted its required opaque version precondition."""


class WorkspaceReferenceRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    type: WorkspaceType
    base_currency_code: str
    timezone: str
    preferred_language: Literal["en", "ja", "my", "shn"]
    version: int


class WorkspaceMembershipRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    membership_id: UUID
    role: WorkspaceRole
    workspace: WorkspaceReferenceRepresentation


class WorkspaceListEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: tuple[WorkspaceMembershipRepresentation, ...]


class ModuleRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: ModuleCode
    enabled: bool
    version: int


class WorkspaceAdministrationRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    description: str | None
    address: str | None
    business_category_code: str | None
    farm_type_code: str | None


class SelectedWorkspaceRepresentation(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace: WorkspaceReferenceRepresentation
    modules: tuple[ModuleRepresentation, ...]
    administration: WorkspaceAdministrationRepresentation | None = None


class SelectedWorkspaceEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: SelectedWorkspaceRepresentation


class ModuleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ModuleCode
    enabled: bool


class WorkspaceSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str | None = Field(default=None, min_length=1, max_length=160)
    workspace_type: WorkspaceType | None = Field(default=None, alias="type")
    base_currency_code: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    preferred_language: Literal["en", "ja", "my", "shn"] | None = None
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=1000)
    business_category_code: str | None = Field(default=None, max_length=64)
    farm_type_code: str | None = Field(default=None, max_length=64)
    modules: tuple[ModuleUpdateRequest, ...] | None = None


def service_for(session: AsyncSession) -> WorkspaceSettingsService:
    return WorkspaceSettingsService(SqlAlchemyWorkspaceAccessRepository(session))


def directory_service_for(session: AsyncSession) -> WorkspaceDirectoryService:
    return WorkspaceDirectoryService(SqlAlchemyWorkspaceDirectoryRepository(session))


def _reference(value: object) -> WorkspaceReferenceRepresentation:
    from app.modules.workspace_access import WorkspaceReference

    assert isinstance(value, WorkspaceReference)
    return WorkspaceReferenceRepresentation(
        id=value.id,
        name=value.name,
        type=WorkspaceType(value.type_code),
        base_currency_code=value.base_currency_code,
        timezone=value.timezone,
        preferred_language=value.preferred_language,
        version=value.version,
    )


def _etag(version: int) -> str:
    return f'"v{version}"'


def _expected_version(value: str | None) -> int:
    if value is None:
        raise PreconditionRequired
    match = _ETAG.fullmatch(value)
    if match is None:
        raise WorkspaceVersionMismatch
    return int(match.group(1))


def _authorization_error(request: Request, error: AuthorizationDenied) -> Response:
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
                context=AuditContext.WORKSPACE_SETTINGS,
            )
        )
        raise


async def _audit_settings_denial(
    session: AsyncSession, context: AuthorizationContext, reason: AuditReason
) -> None:
    await SqlAlchemyAuditWriter(session).append(
        AuditEventIntent(
            scope=AuditScope.WORKSPACE,
            workspace_id=context.workspace_id,
            actor=AuditActor.user(context.actor_account_id, context.membership_id),
            action=AuditAction.WORKSPACE_SETTINGS_UPDATED,
            module=AuditModule.WORKSPACE_ACCESS,
            result=AuditResult.DENIED,
            correlation_id=context.correlation_id,
            resource_type=AuditResourceType.WORKSPACE,
            reason=reason,
            source=AuditSource.API,
            context=AuditContext.WORKSPACE_SETTINGS,
        )
    )


@router.get("/me/workspaces", response_model=WorkspaceListEnvelope)
async def list_workspaces(
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> WorkspaceListEnvelope:
    memberships = await directory_service_for(session).list_for_account(account_id)
    response.headers["Cache-Control"] = "no-store"
    return WorkspaceListEnvelope(
        data=tuple(
            WorkspaceMembershipRepresentation(
                membership_id=item.membership_id,
                role=WorkspaceRole(item.role),
                workspace=_reference(item.workspace),
            )
            for item in memberships
        )
    )


@router.get(
    "/workspaces/{workspace_id}",
    response_model=SelectedWorkspaceEnvelope,
    response_model_exclude_none=True,
)
async def get_workspace(
    workspace_id: UUID,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
) -> SelectedWorkspaceEnvelope | Response:
    try:
        context = await _resolve_context(
            session,
            actor_account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
    except AuthorizationDenied as error:
        return _authorization_error(request, error)
    selected = await service_for(session).get_selected(context)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(selected.workspace.version)
    administration = (
        WorkspaceAdministrationRepresentation(
            description=selected.administration.description,
            address=selected.administration.address,
            business_category_code=selected.administration.business_category_code,
            farm_type_code=selected.administration.farm_type_code,
        )
        if selected.administration is not None
        else None
    )
    return SelectedWorkspaceEnvelope(
        data=SelectedWorkspaceRepresentation(
            workspace=_reference(selected.workspace),
            modules=tuple(
                ModuleRepresentation(
                    code=ModuleCode(module.module_code),
                    enabled=module.enabled,
                    version=module.version,
                )
                for module in selected.modules
            ),
            administration=administration,
        )
    )


@router.patch(
    "/workspaces/{workspace_id}",
    response_model=SelectedWorkspaceEnvelope,
)
async def update_workspace(
    workspace_id: UUID,
    payload: WorkspaceSettingsUpdateRequest,
    request: Request,
    response: Response,
    account_id: AuthenticatedAccountId,
    session: Session,
    browser: BrowserBoundary,
    if_match: IfMatch = None,
) -> SelectedWorkspaceEnvelope | Response:
    del browser
    expected_version = _expected_version(if_match)
    try:
        context = await _resolve_context(
            session,
            actor_account_id=account_id,
            workspace_id=workspace_id,
            correlation_id=request.state.correlation_id,
        )
    except AuthorizationDenied as error:
        return _authorization_error(request, error)
    provided = frozenset(payload.model_fields_set)
    try:
        updated = await service_for(session).update(
            context,
            expected_version=expected_version,
            patch=WorkspaceSettingsPatch(
                provided=provided,
                name=payload.name,
                workspace_type=payload.workspace_type,
                base_currency_code=payload.base_currency_code,
                timezone=payload.timezone,
                preferred_language=payload.preferred_language,
                description=payload.description,
                address=payload.address,
                business_category_code=payload.business_category_code,
                farm_type_code=payload.farm_type_code,
                modules=(
                    tuple(ModuleSetting(item.code, item.enabled) for item in payload.modules)
                    if payload.modules is not None
                    else None
                ),
            ),
        )
    except AuthorizationDenied as error:
        await _audit_settings_denial(
            session,
            context,
            AuditReason.PERMISSION_DENIED,
        )
        return _authorization_error(request, error)
    except WorkspaceVersionMismatch:
        return safe_error(
            status_code=412,
            code="VERSION_MISMATCH",
            message="The resource version is no longer current.",
            correlation_id=correlation_for(request),
        )
    except ValueError:
        await _audit_settings_denial(
            session,
            context,
            AuditReason.VALIDATION_FAILED,
        )
        return safe_error(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The request contains invalid fields.",
            correlation_id=correlation_for(request),
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(updated.workspace.version)
    return SelectedWorkspaceEnvelope(
        data=SelectedWorkspaceRepresentation(
            workspace=_reference(updated.workspace),
            modules=tuple(
                ModuleRepresentation(
                    code=ModuleCode(module.module_code),
                    enabled=module.enabled,
                    version=module.version,
                )
                for module in updated.modules
            ),
            administration=WorkspaceAdministrationRepresentation(
                description=updated.administration.description,
                address=updated.administration.address,
                business_category_code=updated.administration.business_category_code,
                farm_type_code=updated.administration.farm_type_code,
            ),
        )
    )
