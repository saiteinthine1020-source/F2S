"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.account_security import router as account_security_router
from app.api.bootstrap import router as bootstrap_router
from app.api.browser_security import BrowserSecurityDenied
from app.api.errors import correlation_for, safe_error
from app.api.health import router as health_router
from app.api.member_activation import router as member_activation_router
from app.api.security import Unauthenticated
from app.api.sessions import router as sessions_router
from app.api.workspace_settings import PreconditionRequired
from app.api.workspace_settings import router as workspace_settings_router
from app.core.config import RuntimeEnvironment, Settings
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.account_security import (
    DevelopmentRecoveryAbuseControl,
    DevelopmentRecoveryOutbox,
    RecoveryDeliveryUnavailable,
    RejectingRecoveryAbuseControl,
    RejectingRecoveryDelivery,
)
from app.modules.audit.correlation import CorrelationIdError, resolve_correlation_id
from app.modules.bootstrap.service import BootstrapUnavailable
from app.modules.identity_security import (
    Argon2idPasswordService,
    KeyedDigestService,
    OpaqueCredentialService,
    PasswordPolicyError,
    SecretBytes,
    SecretText,
)
from app.modules.member_activation import (
    DevelopmentActivationOutbox,
    DuplicateMembership,
    RejectingActivationDelivery,
)
from app.modules.sessions import DevelopmentLoginAbuseControl, RejectingLoginAbuseControl
from app.modules.workspace_access import (
    AuthorizationDenied,
    DenialCode,
    WorkspaceVersionMismatch,
)

APP_TITLE = "F2S API"
APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application from validated settings."""
    effective_settings = settings or Settings()
    documentation_url = "/docs" if effective_settings.docs_enabled else None
    openapi_url = "/openapi.json" if effective_settings.docs_enabled else None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_database_engine(effective_settings)
        application.state.session_factory = create_session_factory(engine)
        yield
        await engine.dispose()

    application = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        debug=effective_settings.debug,
        docs_url=documentation_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    application.state.settings = effective_settings
    digest_key = SecretBytes(
        effective_settings.identity_digest_key.get_secret_value().encode("utf-8")
    )
    application.state.keyed_digests = KeyedDigestService(digest_key)
    application.state.opaque_credentials = OpaqueCredentialService(application.state.keyed_digests)
    application.state.password_service = Argon2idPasswordService()
    application.state.dummy_password_digest = application.state.password_service.hash(
        SecretText("synthetic-dummy-login-verifier")
    )
    application.state.activation_delivery = (
        RejectingActivationDelivery()
        if effective_settings.environment is RuntimeEnvironment.PRODUCTION
        else DevelopmentActivationOutbox()
    )
    application.state.login_abuse = (
        RejectingLoginAbuseControl()
        if effective_settings.environment is RuntimeEnvironment.PRODUCTION
        else DevelopmentLoginAbuseControl()
    )
    application.state.recovery_delivery = (
        RejectingRecoveryDelivery()
        if effective_settings.environment is RuntimeEnvironment.PRODUCTION
        else DevelopmentRecoveryOutbox()
    )
    application.state.recovery_abuse = (
        RejectingRecoveryAbuseControl()
        if effective_settings.environment is RuntimeEnvironment.PRODUCTION
        else DevelopmentRecoveryAbuseControl()
    )
    application.include_router(health_router)
    application.include_router(bootstrap_router)
    application.include_router(member_activation_router)
    application.include_router(sessions_router)
    application.include_router(account_security_router)
    application.include_router(workspace_settings_router)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[effective_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-CSRF-Token",
        ],
        max_age=600,
    )

    @application.middleware("http")
    async def correlation_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            request.state.correlation_id = resolve_correlation_id(
                request.headers.get("X-Correlation-ID")
            )
        except CorrelationIdError as error:
            return safe_error(
                status_code=400,
                code=error.code.value,
                message="The correlation identifier is invalid.",
                correlation_id=error.correlation_id,
            )
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(request.state.correlation_id)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> Response:
        del error
        return safe_error(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The request contains invalid fields.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(BootstrapUnavailable)
    async def bootstrap_unavailable(request: Request, error: BootstrapUnavailable) -> Response:
        del error
        return safe_error(
            status_code=409,
            code="CONFLICT",
            message="Bootstrap is unavailable.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(Unauthenticated)
    async def unauthenticated(request: Request, error: Unauthenticated) -> Response:
        del error
        return safe_error(
            status_code=401,
            code="UNAUTHENTICATED",
            message="Authentication is required.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(BrowserSecurityDenied)
    async def browser_security_denied(request: Request, error: BrowserSecurityDenied) -> Response:
        return safe_error(
            status_code=error.status_code,
            code=error.code,
            message="The browser request is not permitted.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(AuthorizationDenied)
    async def authorization_denied(request: Request, error: AuthorizationDenied) -> Response:
        not_found = error.code is DenialCode.RESOURCE_NOT_FOUND
        return safe_error(
            status_code=404 if not_found else 403,
            code="RESOURCE_NOT_FOUND" if not_found else "PERMISSION_DENIED",
            message=(
                "The requested resource was not found."
                if not_found
                else "The operation is not permitted."
            ),
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(PreconditionRequired)
    async def precondition_required(request: Request, error: PreconditionRequired) -> Response:
        del error
        return safe_error(
            status_code=428,
            code="PRECONDITION_REQUIRED",
            message="A current resource version is required.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(WorkspaceVersionMismatch)
    async def workspace_version_mismatch(
        request: Request, error: WorkspaceVersionMismatch
    ) -> Response:
        del error
        return safe_error(
            status_code=412,
            code="VERSION_MISMATCH",
            message="The resource version is no longer current.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(DuplicateMembership)
    async def duplicate_membership(request: Request, error: DuplicateMembership) -> Response:
        del error
        return safe_error(
            status_code=409,
            code="DUPLICATE_RESOURCE",
            message="The member already belongs to this workspace.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(RecoveryDeliveryUnavailable)
    async def recovery_delivery_unavailable(
        request: Request, error: RecoveryDeliveryUnavailable
    ) -> Response:
        del error
        return safe_error(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Recovery delivery is unavailable.",
            correlation_id=correlation_for(request),
        )

    @application.exception_handler(ValueError)
    @application.exception_handler(PasswordPolicyError)
    async def domain_validation_error(request: Request, error: Exception) -> Response:
        del error
        return safe_error(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The request contains invalid fields.",
            correlation_id=correlation_for(request),
        )

    return application


app = create_app()
