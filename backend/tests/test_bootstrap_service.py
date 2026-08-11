"""One-time bootstrap validation and safe API boundary tests."""

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import RuntimeEnvironment, Settings
from app.main import create_app
from app.modules.bootstrap.service import (
    BootstrapCommand,
    BootstrapRepository,
    BootstrapResult,
    BootstrapService,
    ModuleCode,
    PreparedBootstrap,
    WorkspaceType,
)
from app.modules.identity_security import Argon2idPasswordService, SecretText


class CapturingRepository(BootstrapRepository):
    def __init__(self) -> None:
        self.prepared: PreparedBootstrap | None = None

    async def is_available(self) -> bool:
        return True

    async def complete(self, command: PreparedBootstrap) -> BootstrapResult:
        self.prepared = command
        return BootstrapResult(uuid4(), uuid4(), uuid4())


def command(**overrides: object) -> BootstrapCommand:
    values: dict[str, object] = {
        "display_name": "  First Admin  ",
        "email": "  FIRST.ADMIN@Example.Invalid  ",
        "password": SecretText("synthetic-bootstrap-password"),
        "account_language": "en",
        "account_timezone": "UTC",
        "workspace_name": "  First Workspace  ",
        "workspace_type": WorkspaceType.FARM,
        "base_currency_code": "USD",
        "workspace_language": "en",
        "workspace_timezone": "Asia/Tokyo",
        "correlation_id": uuid4(),
    }
    values.update(overrides)
    return BootstrapCommand(**values)  # type: ignore[arg-type]


def test_service_normalizes_hashes_and_selects_bounded_module_defaults() -> None:
    repository = CapturingRepository()
    service = BootstrapService(repository, Argon2idPasswordService())

    asyncio.run(service.complete(command()))

    assert repository.prepared is not None
    assert repository.prepared.normalized_email == "first.admin@example.invalid"
    assert repository.prepared.display_name == "First Admin"
    assert repository.prepared.workspace_name == "First Workspace"
    assert repository.prepared.password_digest.for_persistence().startswith("$argon2id$")
    assert repository.prepared.enabled_modules == frozenset(ModuleCode)
    assert "synthetic-bootstrap-password" not in repr(repository.prepared)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("email", "not-an-email", "INVALID_EMAIL"),
        ("account_timezone", "Invalid/Timezone", "INVALID_TIMEZONE"),
        ("workspace_timezone", "", "INVALID_TIMEZONE"),
        ("base_currency_code", "usd", "INVALID_CURRENCY"),
        ("account_language", "fr", "INVALID_LANGUAGE"),
        ("display_name", "   ", "INVALID_DISPLAY_NAME"),
    ],
)
def test_service_rejects_invalid_bootstrap_fields(field: str, value: object, code: str) -> None:
    service = BootstrapService(CapturingRepository(), Argon2idPasswordService())
    with pytest.raises(ValueError, match=code):
        asyncio.run(service.complete(command(**{field: value})))


def test_api_validation_and_correlation_errors_are_safe() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    payload = {
        "display_name": "Synthetic Admin",
        "email": "admin@example.invalid",
        "password": "short-secret",
        "account_language": "en",
        "account_timezone": "UTC",
        "workspace_name": "Synthetic Workspace",
        "workspace_type": "HOUSEHOLD",
        "base_currency_code": "USD",
        "workspace_language": "en",
        "workspace_timezone": "UTC",
    }
    with TestClient(create_app(settings)) as client:
        validation = client.post(
            "/api/v1/setup/bootstrap",
            json=payload,
            headers={"Origin": settings.frontend_origin},
        )
        correlation = client.post(
            "/api/v1/setup/bootstrap",
            json=payload,
            headers={
                "Origin": settings.frontend_origin,
                "X-Correlation-ID": "unsafe malformed correlation",
            },
        )

    assert validation.status_code == 422
    assert validation.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "short-secret" not in validation.text
    assert validation.headers["X-Correlation-ID"] == validation.json()["error"]["correlation_id"]
    assert correlation.status_code == 400
    assert correlation.json()["error"]["code"] == "INVALID_CORRELATION_ID"
    assert "unsafe malformed" not in correlation.text
    assert correlation.headers["Cache-Control"] == "no-store"
    assert correlation.headers["X-Correlation-ID"] == correlation.json()["error"]["correlation_id"]


def test_bootstrap_mutation_requires_exact_origin_and_json() -> None:
    settings = Settings(environment=RuntimeEnvironment.TEST, debug=False, docs_enabled=False)
    with TestClient(create_app(settings)) as client:
        hostile = client.post(
            "/api/v1/setup/bootstrap",
            headers={"Origin": "https://hostile.example"},
            json={},
        )
        form = client.post(
            "/api/v1/setup/bootstrap",
            headers={"Origin": settings.frontend_origin},
            data={"display_name": "Synthetic Admin"},
        )

    assert hostile.status_code == 403
    assert hostile.json()["error"]["code"] == "ORIGIN_DENIED"
    assert form.status_code == 415
    assert form.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
