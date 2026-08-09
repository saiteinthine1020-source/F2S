"""Workspace-scoped SQLAlchemy repository foundation for protected operations."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import UserAccount
from app.infrastructure.database.models.workspace_access import (
    Workspace,
    WorkspaceMembership,
    WorkspaceModule,
)
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
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
from app.modules.workspace_access.authorization import (
    AuthorizationContext,
    AuthorizationDenied,
    Capability,
    DenialCode,
    WorkspaceRole,
    require_capability,
)
from app.modules.workspace_access.repositories import (
    DesiredWorkspaceSettings,
    WorkspaceAccessRepository,
    WorkspaceAdministration,
    WorkspaceModuleReference,
    WorkspaceReference,
    WorkspaceSettingsSnapshot,
    WorkspaceVersionMismatch,
)


class SqlAlchemyWorkspaceAccessRepository(WorkspaceAccessRepository):
    """Resolve authority and enforce it again on every protected SQL operation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_context(
        self, *, actor_account_id: UUID, workspace_id: UUID, correlation_id: UUID
    ) -> AuthorizationContext:
        """Derive current role and authority from account and membership persistence."""
        statement = (
            select(
                UserAccount.status.label("account_status"),
                Workspace.status.label("workspace_status"),
                WorkspaceMembership.id.label("membership_id"),
                WorkspaceMembership.role.label("role"),
                WorkspaceMembership.status.label("membership_status"),
            )
            .select_from(WorkspaceMembership)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_account_id == actor_account_id,
                Workspace.id == workspace_id,
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if row.account_status != "ACTIVE":
            raise AuthorizationDenied(DenialCode.ACCOUNT_INACTIVE)
        if row.workspace_status != "ACTIVE":
            raise AuthorizationDenied(DenialCode.WORKSPACE_INACTIVE)
        if row.membership_status != "ACTIVE":
            raise AuthorizationDenied(DenialCode.MEMBERSHIP_INACTIVE)

        return AuthorizationContext(
            actor_account_id=actor_account_id,
            workspace_id=workspace_id,
            membership_id=row.membership_id,
            role=WorkspaceRole(row.role),
            correlation_id=correlation_id,
        )

    async def get_workspace(self, context: AuthorizationContext) -> WorkspaceReference:
        """Load only the selected workspace's non-administrative reference fields."""
        await self._revalidate(context, Capability.ACCESS_WORKSPACE)
        statement = select(
            Workspace.id,
            Workspace.name,
            Workspace.type,
            Workspace.base_currency_code,
            Workspace.timezone,
            Workspace.preferred_language,
            Workspace.version,
        ).where(Workspace.id == context.workspace_id)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        return WorkspaceReference(
            id=row.id,
            name=row.name,
            type_code=row.type,
            base_currency_code=row.base_currency_code,
            timezone=row.timezone,
            preferred_language=row.preferred_language,
            version=row.version,
        )

    async def get_workspace_administration(
        self, context: AuthorizationContext
    ) -> WorkspaceAdministration:
        """Load restricted profile fields only for workspace-settings authority."""
        await self._revalidate(context, Capability.MANAGE_WORKSPACE_SETTINGS)
        statement = select(
            Workspace.id,
            Workspace.description,
            Workspace.address,
            Workspace.business_category_code,
            Workspace.farm_type_code,
            Workspace.version,
        ).where(Workspace.id == context.workspace_id)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        return WorkspaceAdministration(
            id=row.id,
            description=row.description,
            address=row.address,
            business_category_code=row.business_category_code,
            farm_type_code=row.farm_type_code,
            version=row.version,
        )

    async def list_modules(
        self, context: AuthorizationContext
    ) -> tuple[WorkspaceModuleReference, ...]:
        """List module flags for the selected workspace and no other workspace."""
        await self._revalidate(context, Capability.ACCESS_WORKSPACE)
        statement = (
            select(
                WorkspaceModule.id,
                WorkspaceModule.module_code,
                WorkspaceModule.enabled,
                WorkspaceModule.version,
            )
            .where(WorkspaceModule.workspace_id == context.workspace_id)
            .order_by(WorkspaceModule.module_code, WorkspaceModule.id)
        )
        rows = (await self._session.execute(statement)).all()
        return tuple(
            WorkspaceModuleReference(
                id=row.id,
                module_code=row.module_code,
                enabled=row.enabled,
                version=row.version,
            )
            for row in rows
        )

    async def set_module_enabled(
        self, context: AuthorizationContext, *, module_id: UUID, enabled: bool
    ) -> WorkspaceModuleReference:
        """Apply one settings mutation with capability and workspace predicates."""
        await self._revalidate(context, Capability.MANAGE_WORKSPACE_SETTINGS)
        statement = (
            update(WorkspaceModule)
            .where(
                WorkspaceModule.workspace_id == context.workspace_id,
                WorkspaceModule.id == module_id,
            )
            .values(
                enabled=enabled,
                version=WorkspaceModule.version + 1,
                updated_at=func.current_timestamp(),
            )
            .returning(
                WorkspaceModule.id,
                WorkspaceModule.module_code,
                WorkspaceModule.enabled,
                WorkspaceModule.version,
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        return WorkspaceModuleReference(
            id=row.id,
            module_code=row.module_code,
            enabled=row.enabled,
            version=row.version,
        )

    async def update_settings(
        self,
        context: AuthorizationContext,
        *,
        expected_version: int,
        desired: DesiredWorkspaceSettings,
    ) -> WorkspaceSettingsSnapshot:
        await self._revalidate(context, Capability.MANAGE_WORKSPACE_SETTINGS)
        workspace = await self._session.scalar(
            select(Workspace)
            .where(Workspace.id == context.workspace_id, Workspace.status == "ACTIVE")
            .with_for_update()
        )
        if workspace is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        if workspace.version != expected_version:
            await self._audit_settings(
                context,
                AuditAction.WORKSPACE_SETTINGS_UPDATED,
                AuditResult.DENIED,
                AuditReason.STALE_VERSION,
            )
            raise WorkspaceVersionMismatch

        modules = list(
            (
                await self._session.scalars(
                    select(WorkspaceModule)
                    .where(WorkspaceModule.workspace_id == context.workspace_id)
                    .order_by(WorkspaceModule.module_code)
                    .with_for_update()
                )
            ).all()
        )
        desired_modules = {code.value: enabled for code, enabled in desired.modules}
        if {module.module_code for module in modules} != set(desired_modules):
            raise ValueError("INCOMPLETE_MODULE_CONFIGURATION")

        renamed = workspace.name != desired.name
        modules_changed = False
        workspace.name = desired.name
        workspace.type = desired.workspace_type.value
        workspace.base_currency_code = desired.base_currency_code
        workspace.timezone = desired.timezone
        workspace.preferred_language = desired.preferred_language
        workspace.description = desired.description
        workspace.address = desired.address
        workspace.business_category_code = desired.business_category_code
        workspace.farm_type_code = desired.farm_type_code
        workspace.version += 1
        for module in modules:
            enabled = desired_modules[module.module_code]
            if module.enabled != enabled:
                module.enabled = enabled
                module.version += 1
                modules_changed = True
        await self._session.flush()
        await self._audit_settings(
            context,
            AuditAction.WORKSPACE_SETTINGS_UPDATED,
            AuditResult.SUCCEEDED,
        )
        if renamed:
            await self._audit_settings(
                context,
                AuditAction.WORKSPACE_RENAMED,
                AuditResult.SUCCEEDED,
            )
        if modules_changed:
            await self._audit_settings(
                context,
                AuditAction.WORKSPACE_MODULES_UPDATED,
                AuditResult.SUCCEEDED,
            )
        return self._snapshot(workspace, modules)

    @staticmethod
    def _snapshot(
        workspace: Workspace, modules: list[WorkspaceModule]
    ) -> WorkspaceSettingsSnapshot:
        return WorkspaceSettingsSnapshot(
            workspace=WorkspaceReference(
                id=workspace.id,
                name=workspace.name,
                type_code=workspace.type,
                base_currency_code=workspace.base_currency_code,
                timezone=workspace.timezone,
                preferred_language=workspace.preferred_language,
                version=workspace.version,
            ),
            administration=WorkspaceAdministration(
                id=workspace.id,
                description=workspace.description,
                address=workspace.address,
                business_category_code=workspace.business_category_code,
                farm_type_code=workspace.farm_type_code,
                version=workspace.version,
            ),
            modules=tuple(
                WorkspaceModuleReference(
                    id=module.id,
                    module_code=module.module_code,
                    enabled=module.enabled,
                    version=module.version,
                )
                for module in modules
            ),
        )

    async def _audit_settings(
        self,
        context: AuthorizationContext,
        action: AuditAction,
        result: AuditResult,
        reason: AuditReason | None = None,
    ) -> None:
        await SqlAlchemyAuditWriter(self._session).append(
            AuditEventIntent(
                scope=AuditScope.WORKSPACE,
                workspace_id=context.workspace_id,
                actor=AuditActor.user(context.actor_account_id, context.membership_id),
                action=action,
                module=AuditModule.WORKSPACE_ACCESS,
                result=result,
                correlation_id=context.correlation_id,
                resource_type=AuditResourceType.WORKSPACE,
                resource_id=(context.workspace_id if result is not AuditResult.DENIED else None),
                reason=reason,
                source=AuditSource.API,
                context=AuditContext.WORKSPACE_SETTINGS,
            )
        )

    async def _revalidate(self, context: AuthorizationContext, capability: Capability) -> None:
        """Reject fabricated, stale, inactive, or role-mismatched authority."""
        statement = (
            select(WorkspaceMembership.id)
            .select_from(WorkspaceMembership)
            .join(UserAccount, UserAccount.id == WorkspaceMembership.user_account_id)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.workspace_id == context.workspace_id,
                WorkspaceMembership.id == context.membership_id,
                WorkspaceMembership.user_account_id == context.actor_account_id,
                WorkspaceMembership.role == context.role.value,
                WorkspaceMembership.status == "ACTIVE",
                UserAccount.id == context.actor_account_id,
                UserAccount.status == "ACTIVE",
                Workspace.id == context.workspace_id,
                Workspace.status == "ACTIVE",
            )
        )
        if (await self._session.execute(statement)).scalar_one_or_none() is None:
            raise AuthorizationDenied(DenialCode.RESOURCE_NOT_FOUND)
        require_capability(context, capability)
