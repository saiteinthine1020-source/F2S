"""Safe request-correlation validation and generation."""

from enum import StrEnum
from uuid import UUID, uuid4


class CorrelationIdErrorCode(StrEnum):
    """Stable public failure codes for malformed request correlation."""

    INVALID_CORRELATION_ID = "INVALID_CORRELATION_ID"


class CorrelationIdError(ValueError):
    """Safe error carrying a fresh support correlation without echoing input."""

    def __init__(self, correlation_id: UUID) -> None:
        self.code = CorrelationIdErrorCode.INVALID_CORRELATION_ID
        self.correlation_id = correlation_id
        super().__init__(self.code.value)


def resolve_correlation_id(value: str | None) -> UUID:
    """Validate a canonical UUID request value or generate a UUIDv4 when absent."""
    if value is None:
        return uuid4()
    try:
        correlation_id = UUID(value)
    except (ValueError, AttributeError, TypeError) as error:
        raise CorrelationIdError(uuid4()) from error
    if len(value) != 36 or str(correlation_id) != value.lower():
        raise CorrelationIdError(uuid4())
    return correlation_id
