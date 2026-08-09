"""Framework-free validation and orchestration for one-time bootstrap."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.identity_security import (
    Argon2idPasswordService,
    PasswordDigest,
    SecretText,
    normalize_email,
)
from app.modules.workspace_access.configuration import (
    MODULE_DEFAULTS,
    bounded_text,
    validate_currency,
    validate_language,
    validate_timezone,
)
from app.modules.workspace_access.configuration import (
    ModuleCode as ModuleCode,
)
from app.modules.workspace_access.configuration import (
    WorkspaceType as WorkspaceType,
)


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
            display_name=bounded_text(
                command.display_name, maximum=120, code="INVALID_DISPLAY_NAME"
            ),
            normalized_email=normalize_email(command.email),
            password_digest=self._password_service.hash(command.password),
            account_language=validate_language(command.account_language),
            account_timezone=validate_timezone(command.account_timezone),
            workspace_name=bounded_text(
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
