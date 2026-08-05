"""FastAPI application factory and ASGI entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import Settings

APP_TITLE = "F2S API"
APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application from validated settings."""
    effective_settings = settings or Settings()
    documentation_url = "/docs" if effective_settings.docs_enabled else None
    openapi_url = "/openapi.json" if effective_settings.docs_enabled else None

    application = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        debug=effective_settings.debug,
        docs_url=documentation_url,
        redoc_url=None,
        openapi_url=openapi_url,
    )
    application.state.settings = effective_settings
    application.include_router(health_router)
    return application


app = create_app()
