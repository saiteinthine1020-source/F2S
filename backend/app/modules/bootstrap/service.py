"""Framework-free validation and orchestration for one-time bootstrap."""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.identity_security import (
    Argon2idPasswordService,
    PasswordDigest,
    SecretText,
    normalize_email,
)

_CURRENCY_PATTERN: Final = re.compile(r"^[A-Z]{3}$")
SUPPORTED_LANGUAGES: Final = frozenset({"en", "ja", "my", "shn"})


class WorkspaceType(StrEnum):
    HOUSEHOLD = "HOUSEHOLD"
    FARM = "FARM"
    MICROBUSINESS = "MICROBUSINESS"
    SMALL_BUSINESS = "SMALL_BUSINESS"
    COMBINED = "COMBINED"
    CUSTOM = "CUSTOM"


class ModuleCode(StrEnum):
    HOUSEHOLD_FINANCE = "HOUSEHOLD_FINANCE"
    FARMING_INVESTMENTS = "FARMING_INVESTMENTS"


MODULE_DEFAULTS: Final = {
    WorkspaceType.HOUSEHOLD: frozenset({ModuleCode.HOUSEHOLD_FINANCE}),
    WorkspaceType.FARM: frozenset({ModuleCode.HOUSEHOLD_FINANCE, ModuleCode.FARMING_INVESTMENTS}),
    WorkspaceType.MICROBUSINESS: frozenset({ModuleCode.HOUSEHOLD_FINANCE}),
    WorkspaceType.SMALL_BUSINESS: frozenset({ModuleCode.HOUSEHOLD_FINANCE}),
    WorkspaceType.COMBINED: frozenset(
        {ModuleCode.HOUSEHOLD_FINANCE, ModuleCode.FARMING_INVESTMENTS}
    ),
    WorkspaceType.CUSTOM: frozenset(),
}


class BootstrapUnavailable(Exception):
    """Stable concealed outcome after installation bootstrap is complete."""

    def __init__(self) -> None:
        super().__init__("BOOTSTRAP_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class BootstrapCommand:
    display_name: str
    email: str
    password: SecretText
    account_language: str
    account_timezone: str
    workspace_name: str
    workspace_type: WorkspaceType
    base_currency_code: str
    workspace_language: str
    workspace_timezone: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class PreparedBootstrap:
    display_name: str
    normalized_email: str
    password_digest: PasswordDigest
    account_language: str
    account_timezone: str
    workspace_name: str
    workspace_type: WorkspaceType
    base_currency_code: str
    workspace_language: str
    workspace_timezone: str
    enabled_modules: frozenset[ModuleCode]
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    account_id: UUID
    workspace_id: UUID
    membership_id: UUID


class BootstrapRepository(Protocol):
    async def is_available(self) -> bool: ...

    async def complete(self, command: PreparedBootstrap) -> BootstrapResult: ...


class BootstrapService:
    def __init__(
        self, repository: BootstrapRepository, password_service: Argon2idPasswordService
    ) -> None:
        self._repository = repository
        self._password_service = password_service

    async def is_available(self) -> bool:
        return await self._repository.is_available()

    async def complete(self, command: BootstrapCommand) -> BootstrapResult:
        prepared = PreparedBootstrap(
            display_name=_bounded_text(
                command.display_name, maximum=120, code="INVALID_DISPLAY_NAME"
            ),
            normalized_email=normalize_email(command.email),
            password_digest=self._password_service.hash(command.password),
            account_language=validate_language(command.account_language),
            account_timezone=validate_timezone(command.account_timezone),
            workspace_name=_bounded_text(
                command.workspace_name, maximum=160, code="INVALID_WORKSPACE_NAME"
            ),
            workspace_type=command.workspace_type,
            base_currency_code=validate_currency(command.base_currency_code),
            workspace_language=validate_language(command.workspace_language),
            workspace_timezone=validate_timezone(command.workspace_timezone),
            enabled_modules=MODULE_DEFAULTS[command.workspace_type],
            correlation_id=command.correlation_id,
        )
        return await self._repository.complete(prepared)


def validate_currency(value: str) -> str:
    if not _CURRENCY_PATTERN.fullmatch(value):
        raise ValueError("INVALID_CURRENCY")
    return value


def validate_language(value: str) -> str:
    if value not in SUPPORTED_LANGUAGES:
        raise ValueError("INVALID_LANGUAGE")
    return value


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("INVALID_TIMEZONE") from error
    return value


def _bounded_text(value: str, *, maximum: int, code: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(code)
    return normalized
