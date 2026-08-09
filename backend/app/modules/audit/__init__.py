"""Public append-only audit and request-correlation contracts."""

from app.modules.audit.correlation import (
    CorrelationIdError,
    CorrelationIdErrorCode,
    resolve_correlation_id,
)
from app.modules.audit.events import (
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
from app.modules.audit.ports import AuditWriter

__all__ = [
    "AuditAction",
    "AuditActor",
    "AuditContext",
    "AuditEventIntent",
    "AuditModule",
    "AuditReason",
    "AuditResourceType",
    "AuditResult",
    "AuditScope",
    "AuditSource",
    "AuditWriter",
    "CorrelationIdError",
    "CorrelationIdErrorCode",
    "resolve_correlation_id",
]
