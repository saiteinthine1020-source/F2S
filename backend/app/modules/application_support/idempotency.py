"""Durable idempotency state and orchestration contracts."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.workspace_access import AuthorizationContext, Capability
from app.shared_kernel import IdempotencyKey, OperationCode, RequestFingerprint

if TYPE_CHECKING:
    from app.modules.application_support.repositories import IdempotencyRepository

_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


class IdempotencyState(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ClaimDisposition(StrEnum):
    STARTED = "STARTED"
    REPLAY = "REPLAY"
    IN_PROGRESS = "IN_PROGRESS"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class IdempotencyKeyReused(Exception):
    """The key already identifies a different canonical request."""


class IdempotencyStateConflict(Exception):
    """A claim is no longer owned by the supplied execution lease."""


@dataclass(frozen=True, slots=True)
class SafeOutcome:
    code: str
    http_status: int
    resource_type: str | None = None
    resource_id: UUID | None = None
    resource_version: int | None = None

    def __post_init__(self) -> None:
        if _CODE.fullmatch(self.code) is None:
            raise ValueError("INVALID_OUTCOME_CODE")
        if not 100 <= self.http_status <= 599:
            raise ValueError("INVALID_SAFE_OUTCOME")
        resource_fields = (self.resource_type, self.resource_id, self.resource_version)
        if any(value is not None for value in resource_fields) and not all(
            value is not None for value in resource_fields
        ):
            raise ValueError("INCOMPLETE_RESOURCE_OUTCOME")
        if self.resource_type is not None and (_CODE.fullmatch(self.resource_type) is None):
            raise ValueError("INVALID_RESOURCE_TYPE")
        if self.resource_version is not None and self.resource_version <= 0:
            raise ValueError("INVALID_RESOURCE_VERSION")


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    id: UUID
    disposition: ClaimDisposition
    state: IdempotencyState
    lease_token: UUID | None
    outcome: SafeOutcome | None


class IdempotencyService:
    """Coordinate claims without owning the caller's database transaction."""

    def __init__(self, repository: "IdempotencyRepository") -> None:
        self._repository = repository

    async def begin(
        self,
        context: AuthorizationContext,
        *,
        operation_id: UUID,
        required_capability: Capability,
        operation: OperationCode,
        key: IdempotencyKey,
        fingerprint: RequestFingerprint,
    ) -> IdempotencyClaim:
        return await self._repository.claim(
            context,
            operation_id=operation_id,
            required_capability=required_capability,
            operation=operation,
            key=key,
            fingerprint=fingerprint,
        )

    async def complete(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim: IdempotencyClaim,
        outcome: SafeOutcome,
    ) -> IdempotencyClaim:
        if claim.disposition is not ClaimDisposition.STARTED or claim.lease_token is None:
            raise IdempotencyStateConflict
        return await self._repository.complete(
            context,
            required_capability=required_capability,
            claim_id=claim.id,
            lease_token=claim.lease_token,
            outcome=outcome,
        )

    async def fail(
        self,
        context: AuthorizationContext,
        *,
        required_capability: Capability,
        claim: IdempotencyClaim,
        outcome: SafeOutcome,
    ) -> IdempotencyClaim:
        if claim.disposition is not ClaimDisposition.STARTED or claim.lease_token is None:
            raise IdempotencyStateConflict
        return await self._repository.fail(
            context,
            required_capability=required_capability,
            claim_id=claim.id,
            lease_token=claim.lease_token,
            outcome=outcome,
        )
