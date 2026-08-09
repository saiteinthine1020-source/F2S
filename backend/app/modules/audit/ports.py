"""Append-only audit persistence port."""

from typing import Protocol
from uuid import UUID

from app.modules.audit.events import AuditEventIntent


class AuditWriter(Protocol):
    """Write required evidence inside the caller-owned transaction."""

    async def append(self, intent: AuditEventIntent) -> UUID:
        """Append one event without committing the transaction."""
        ...
