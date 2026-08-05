"""Typed runtime configuration with production fail-closed rules."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeEnvironment(StrEnum):
    """Supported runtime environments."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Validated non-secret settings for the initial skeleton."""

    model_config = SettingsConfigDict(
        env_prefix="F2S_",
        case_sensitive=False,
        extra="forbid",
        frozen=True,
    )

    environment: RuntimeEnvironment = RuntimeEnvironment.LOCAL
    debug: bool = False
    docs_enabled: bool = False

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> Self:
        """Reject debug and documentation surfaces in production."""
        if self.environment is RuntimeEnvironment.PRODUCTION and self.debug:
            raise ValueError("debug mode must be disabled in production")
        if self.environment is RuntimeEnvironment.PRODUCTION and self.docs_enabled:
            raise ValueError("API documentation must be disabled in production")
        return self
