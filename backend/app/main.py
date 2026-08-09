"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError

from app.api.bootstrap import router as bootstrap_router
from app.api.errors import correlation_for, safe_error
from app.api.health import router as health_router
from app.core.config import Settings
from app.infrastructure.database.session import create_database_engine, create_session_factory
from app.modules.audit.correlation import CorrelationIdError, resolve_correlation_id
from app.modules.bootstrap.service import BootstrapUnavailable
from app.modules.identity_security import PasswordPolicyError

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
    application.include_router(health_router)
    application.include_router(bootstrap_router)

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
