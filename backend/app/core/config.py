"""Typed runtime configuration with production fail-closed rules."""

from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class RuntimeEnvironment(StrEnum):
    """Supported runtime environments."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class DatabaseSslMode(StrEnum):
    """Supported libpq TLS modes."""

    DISABLE = "disable"
    REQUIRE = "require"
    VERIFY_FULL = "verify-full"


class Settings(BaseSettings):
    """Validated runtime settings with secrets kept out of string URLs."""

    model_config = SettingsConfigDict(
        env_prefix="F2S_",
        case_sensitive=False,
        extra="forbid",
        frozen=True,
    )

    environment: RuntimeEnvironment = RuntimeEnvironment.LOCAL
    debug: bool = False
    docs_enabled: bool = False
    database_host: str = Field(min_length=1, max_length=253)
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=63, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    database_user: str = Field(min_length=1, max_length=63, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    database_password: SecretStr
    database_sslmode: DatabaseSslMode = DatabaseSslMode.DISABLE

    @field_validator("database_host")
    @classmethod
    def reject_padded_database_host(cls, value: str) -> str:
        """Reject whitespace that can silently redirect a connection."""
        if value != value.strip():
            raise ValueError("database host must not contain surrounding whitespace")
        return value

    @field_validator("database_password")
    @classmethod
    def reject_empty_database_password(cls, value: SecretStr) -> SecretStr:
        """Require an explicit non-empty database credential."""
        if not value.get_secret_value():
            raise ValueError("database password must not be empty")
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self) -> Self:
        """Reject debug and documentation surfaces in production."""
        if self.environment is RuntimeEnvironment.PRODUCTION and self.debug:
            raise ValueError("debug mode must be disabled in production")
        if self.environment is RuntimeEnvironment.PRODUCTION and self.docs_enabled:
            raise ValueError("API documentation must be disabled in production")
        if (
            self.environment is RuntimeEnvironment.PRODUCTION
            and self.database_sslmode is not DatabaseSslMode.VERIFY_FULL
        ):
            raise ValueError("database SSL mode must be verify-full in production")
        return self

    @property
    def database_url(self) -> URL:
        """Build a typed SQLAlchemy URL without storing a raw secret URL."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"sslmode": self.database_sslmode.value},
        )
