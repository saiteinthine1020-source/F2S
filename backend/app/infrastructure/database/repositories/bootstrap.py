"""Serialized PostgreSQL adapter for one-time installation bootstrap."""

from collections.abc import Callable
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.identity import BootstrapState, UserAccount
from app.infrastructure.database.models.workspace_access import (
    Workspace,
    WorkspaceMembership,
    WorkspaceModule,
)
from app.infrastructure.database.repositories.audit import SqlAlchemyAuditWriter
from app.modules.audit.events import (
    AuditAction,
    AuditActor,
    AuditContext,
    AuditEventIntent,
    AuditModule,
    AuditResourceType,
    AuditResult,
    AuditScope,
    AuditSource,
)
from app.modules.audit.ports import AuditWriter
from app.modules.bootstrap.service import (
    BootstrapRepository,
    BootstrapResult,
    BootstrapUnavailable,
    PreparedBootstrap,
)
from app.modules.workspace_access.configuration import ModuleCode


class SqlAlchemyBootstrapRepository(BootstrapRepository):
    """Create every bootstrap record inside the caller-owned transaction."""

    def __init__(
        self,
        session: AsyncSession,
        audit_writer_factory: Callable[[AsyncSession], AuditWriter] = SqlAlchemyAuditWriter,
    ) -> None:
        self._session = session
        self._audit_writer_factory = audit_writer_factory

    async def is_available(self) -> bool:
        completed_at = await self._session.scalar(
            select(BootstrapState.completed_at).where(
                BootstrapState.singleton_key == "INSTALLATION"
            )
        )
        return completed_at is None

    async def complete(self, command: PreparedBootstrap) -> BootstrapResult:
        guard_id = uuid4()
        await self._session.execute(
            insert(BootstrapState)
            .values(id=guard_id, singleton_key="INSTALLATION")
            .on_conflict_do_nothing(index_elements=[BootstrapState.singleton_key])
        )
        guard = await self._session.scalar(
            select(BootstrapState)
            .where(BootstrapState.singleton_key == "INSTALLATION")
            .with_for_update()
        )
        if guard is None or guard.completed_at is not None:
            raise BootstrapUnavailable

        account_id, workspace_id, membership_id = uuid4(), uuid4(), uuid4()
        self._session.add(
            UserAccount(
                id=account_id,
                normalized_email=command.normalized_email,
                display_name=command.display_name,
                password_digest=command.password_digest.for_persistence(),
                status="ACTIVE",
                preferred_language=command.account_language,
                timezone=command.account_timezone,
            )
        )
        self._session.add(
            Workspace(
                id=workspace_id,
                name=command.workspace_name,
                type=command.workspace_type.value,
                base_currency_code=command.base_currency_code,
                timezone=command.workspace_timezone,
                preferred_language=command.workspace_language,
                owner_membership_id=membership_id,
                owner_role="ADMIN",
                owner_membership_status="ACTIVE",
                status="ACTIVE",
            )
        )
        self._session.add(
            WorkspaceMembership(
                id=membership_id,
                workspace_id=workspace_id,
                user_account_id=account_id,
                role="ADMIN",
                status="ACTIVE",
            )
        )
        for module_code in ModuleCode:
            self._session.add(
                WorkspaceModule(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    module_code=module_code.value,
                    enabled=module_code in command.enabled_modules,
                )
            )
        await self._session.flush()

        writer = self._audit_writer_factory(self._session)
        actor = AuditActor.user(account_id, membership_id)
        for action, module in (
            (AuditAction.WORKSPACE_CREATED, AuditModule.WORKSPACE_ACCESS),
            (AuditAction.BOOTSTRAP_COMPLETED, AuditModule.IDENTITY_SECURITY),
        ):
            await writer.append(
                AuditEventIntent(
                    scope=AuditScope.WORKSPACE,
                    workspace_id=workspace_id,
                    actor=actor,
                    action=action,
                    module=module,
                    result=AuditResult.SUCCEEDED,
                    correlation_id=command.correlation_id,
                    resource_type=AuditResourceType.WORKSPACE,
                    resource_id=workspace_id,
                    source=AuditSource.API,
                    context=AuditContext.BOOTSTRAP,
                )
            )
        await self._session.execute(
            update(BootstrapState)
            .where(BootstrapState.id == guard.id)
            .values(completed_at=func.current_timestamp(), version=BootstrapState.version + 1)
        )
        return BootstrapResult(account_id, workspace_id, membership_id)
