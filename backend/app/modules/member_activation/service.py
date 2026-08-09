"""Framework-free member provisioning and single-use activation orchestration."""

import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.identity_security import (
    DEFAULT_CHALLENGE_LIFETIME,
    Argon2idPasswordService,
    IssuedOpaqueCredential,
    OpaqueCredentialPurpose,
    OpaqueCredentialService,
    PasswordDigest,
    SecretText,
    normalize_email,
)
from app.modules.workspace_access import AuthorizationContext


class MemberRole(StrEnum):
    CONTRIBUTOR = "CONTRIBUTOR"
    ADVISOR = "ADVISOR"


class DuplicateMembership(Exception):
    def __init__(self) -> None:
        super().__init__("DUPLICATE_MEMBERSHIP")


@dataclass(frozen=True, slots=True)
class ProvisionMemberCommand:
    context: AuthorizationContext
    email: str
    display_name: str
    role: MemberRole
    preferred_language: str
    timezone: str


@dataclass(frozen=True, slots=True)
class MemberProvisioning:
    context: AuthorizationContext
    normalized_email: str
    display_name: str
    role: MemberRole
    preferred_language: str
    timezone: str


@dataclass(frozen=True, slots=True)
class ProvisionedMember:
    membership_id: UUID
    role: MemberRole
    status: str = "PENDING"


@dataclass(frozen=True, slots=True)
class ActivationDelivery:
    recipient: str
    value: SecretText
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ActivationAttempt:
    value: SecretText
    password: SecretText | None
    correlation_id: UUID
    now: datetime


@dataclass(frozen=True, slots=True)
class ActivationOutcome:
    activated: bool


class ActivationDeliveryPort(Protocol):
    async def deliver(self, delivery: ActivationDelivery) -> None: ...


class MemberActivationRepository(Protocol):
    async def provision(
        self, command: MemberProvisioning, credential: IssuedOpaqueCredential
    ) -> ProvisionedMember: ...

    async def restart(
        self,
        context: AuthorizationContext,
        membership_id: UUID,
        credential: IssuedOpaqueCredential,
    ) -> str: ...

    async def activate(
        self,
        attempt: ActivationAttempt,
        password_digest: PasswordDigest | None,
    ) -> ActivationOutcome: ...


class DevelopmentActivationOutbox(ActivationDeliveryPort):
    """Non-production, process-local one-time delivery capture."""

    def __init__(self) -> None:
        self._deliveries: list[ActivationDelivery] = []

    async def deliver(self, delivery: ActivationDelivery) -> None:
        self._deliveries.append(delivery)

    def drain(self) -> tuple[ActivationDelivery, ...]:
        deliveries = tuple(self._deliveries)
        self._deliveries.clear()
        return deliveries


class RejectingActivationDelivery(ActivationDeliveryPort):
    """Fail closed until a durable production delivery adapter is configured."""

    async def deliver(self, delivery: ActivationDelivery) -> None:
        del delivery
        raise RuntimeError("ACTIVATION_DELIVERY_UNAVAILABLE")


class MemberActivationService:
    def __init__(
        self,
        repository: MemberActivationRepository,
        credentials: OpaqueCredentialService,
        passwords: Argon2idPasswordService,
        delivery: ActivationDeliveryPort,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._passwords = passwords
        self._delivery = delivery

    async def provision(
        self, command: ProvisionMemberCommand, *, now: datetime | None = None
    ) -> ProvisionedMember:
        issued_at = now or datetime.now(UTC)
        issued = self._credentials.issue(
            OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
            now=issued_at,
            lifetime=DEFAULT_CHALLENGE_LIFETIME,
        )
        prepared = MemberProvisioning(
            context=command.context,
            normalized_email=normalize_email(command.email),
            display_name=_display_name(command.display_name),
            role=command.role,
            preferred_language=_language(command.preferred_language),
            timezone=_timezone(command.timezone),
        )
        result = await self._repository.provision(prepared, issued)
        await self._delivery.deliver(
            ActivationDelivery(
                recipient=prepared.normalized_email,
                value=issued.value,
                expires_at=issued.record.expires_at,
            )
        )
        return result

    async def restart(
        self,
        context: AuthorizationContext,
        membership_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        issued_at = now or datetime.now(UTC)
        issued = self._credentials.issue(
            OpaqueCredentialPurpose.ACTIVATION_CHALLENGE,
            now=issued_at,
            lifetime=DEFAULT_CHALLENGE_LIFETIME,
        )
        recipient = await self._repository.restart(context, membership_id, issued)
        await self._delivery.deliver(
            ActivationDelivery(recipient, issued.value, issued.record.expires_at)
        )

    async def activate(self, attempt: ActivationAttempt) -> ActivationOutcome:
        password_digest = (
            self._passwords.hash(attempt.password) if attempt.password is not None else None
        )
        return await self._repository.activate(attempt, password_digest)


def _display_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or len(normalized) > 120:
        raise ValueError("INVALID_DISPLAY_NAME")
    return normalized


def _language(value: str) -> str:
    if value not in {"en", "ja", "my", "shn"}:
        raise ValueError("INVALID_LANGUAGE")
    return value


def _timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("INVALID_TIMEZONE") from error
    return value
