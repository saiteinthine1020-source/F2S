"""Typed runtime configuration with production fail-closed rules."""

from enum import StrEnum
from ipaddress import ip_address
from typing import Self
from urllib.parse import urlsplit

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
    identity_digest_key: SecretStr
    frontend_origin: str = "http://127.0.0.1:5173"
    api_allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")

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

    @field_validator("identity_digest_key")
    @classmethod
    def require_strong_identity_digest_key(cls, value: SecretStr) -> SecretStr:
        """Require sufficient HMAC key material without exposing it."""
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("identity digest key must contain at least 32 bytes")
        return value

    @field_validator("frontend_origin")
    @classmethod
    def require_exact_frontend_origin(cls, value: str) -> str:
        """Accept one exact HTTP(S) origin without credentials, path, query, or fragment."""
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or "*" in parsed.hostname
        ):
            raise ValueError("frontend origin must be one exact HTTP(S) origin")
        return value.rstrip("/")

    @field_validator("api_allowed_hosts")
    @classmethod
    def require_exact_allowed_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Require bounded exact Host values without ports, schemes, or wildcards."""
        if not value or len(value) > 16:
            raise ValueError("one through 16 API allowed hosts are required")
        normalized: list[str] = []
        for host in value:
            candidate = host.strip().lower()
            if (
                not candidate
                or candidate != host
                or "*" in candidate
                or ":" in candidate
                or "://" in candidate
                or "/" in candidate
                or candidate.endswith(".")
            ):
                raise ValueError("API allowed hosts must be exact hostnames or IP addresses")
            normalized.append(candidate)
        if len(set(normalized)) != len(normalized):
            raise ValueError("API allowed hosts must be unique")
        return tuple(normalized)

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
        if (
            self.environment is RuntimeEnvironment.PRODUCTION
            and not self.frontend_origin.startswith("https://")
        ):
            raise ValueError("frontend origin must use HTTPS in production")
        if self.environment is RuntimeEnvironment.PRODUCTION:
            frontend_host = urlsplit(self.frontend_origin).hostname
            if frontend_host is None or _is_local_or_placeholder_host(frontend_host):
                raise ValueError("frontend origin must use a production hostname")
            if any(_is_local_or_placeholder_host(host) for host in self.api_allowed_hosts):
                raise ValueError("API allowed hosts must be explicit production hostnames")
            if _looks_like_placeholder(self.database_password.get_secret_value()):
                raise ValueError("database password must not be placeholder material")
            if _looks_like_placeholder(self.identity_digest_key.get_secret_value()):
                raise ValueError("identity digest key must not be placeholder material")
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


def _is_local_or_placeholder_host(host: str) -> bool:
    candidate = host.lower()
    if candidate in {"localhost", "testserver"} or candidate.endswith(".invalid"):
        return True
    try:
        return ip_address(candidate).is_loopback
    except ValueError:
        return False


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    markers = ("changeme", "change-me", "placeholder", "replace-with", "synthetic")
    return any(marker in normalized for marker in markers)
