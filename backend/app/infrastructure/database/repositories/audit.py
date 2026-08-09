"""Transaction-bound SQLAlchemy adapter for append-only audit evidence."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.audit import AuditEvent
from app.modules.audit.events import AuditEventIntent
from app.modules.audit.ports import AuditWriter


class SqlAlchemyAuditWriter(AuditWriter):
    """Append through the supplied session; transaction ownership stays with the caller."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, intent: AuditEventIntent) -> UUID:
        """Flush one event so persistence failure aborts the surrounding use case."""
        event_id = uuid4()
        self._session.add(
            AuditEvent(
                id=event_id,
                scope_code=intent.scope.value,
                workspace_id=intent.workspace_id,
                actor_type_code=intent.actor.type.value,
                actor_user_account_id=intent.actor.account_id,
                actor_membership_id=intent.actor.membership_id,
                action_code=intent.action.value,
                module_code=intent.module.value,
                resource_type_code=(
                    intent.resource_type.value if intent.resource_type is not None else None
                ),
                resource_id=intent.resource_id,
                result_code=intent.result.value,
                reason_code=intent.reason.value if intent.reason is not None else None,
                source_code=intent.source.value if intent.source is not None else None,
                context_code=intent.context.value if intent.context is not None else None,
                correlation_id=intent.correlation_id,
            )
        )
        await self._session.flush()
        return event_id
