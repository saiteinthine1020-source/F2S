"""Injectable concealed rate-limit and progressive lockout policy contracts."""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Protocol

from app.modules.identity_security.values import KeyedDigest


class AbuseScope(StrEnum):
    """Bounded counter scopes that never encode whether an account exists."""

    LOGIN_ACCOUNT = "LOGIN_ACCOUNT"
    LOGIN_NETWORK = "LOGIN_NETWORK"
    ACTIVATION_RECIPIENT = "ACTIVATION_RECIPIENT"
    RECOVERY_RECIPIENT = "RECOVERY_RECIPIENT"
    RECOVERY_NETWORK = "RECOVERY_NETWORK"


@dataclass(frozen=True, slots=True)
class AbuseSubject:
    """A keyed subject digest suitable for an external counter key."""

    digest: KeyedDigest


@dataclass(frozen=True, slots=True)
class RateLimitRequest:
    """One purpose-scoped, concealed counter request."""

    scope: AbuseScope
    subject: AbuseSubject
    cost: int = 1

    def __post_init__(self) -> None:
        if self.cost <= 0:
            raise ValueError("RATE_LIMIT_COST_INVALID")


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Safe limiter outcome without subject, count, or account-existence detail."""

    allowed: bool
    retry_after: timedelta | None = None

    def __post_init__(self) -> None:
        if self.allowed and self.retry_after is not None:
            raise ValueError("ALLOWED_DECISION_HAS_RETRY")
        if self.retry_after is not None and self.retry_after <= timedelta(0):
            raise ValueError("RETRY_AFTER_INVALID")


class RateLimiter(Protocol):
    """Port for a future distributed, atomic rate-limit adapter."""

    async def consume(self, request: RateLimitRequest) -> RateLimitDecision:
        """Atomically consume cost and return a concealed decision."""
        ...


class RateLimitPolicy(Protocol):
    """Pure threshold policy shared by distributed counter adapters."""

    def evaluate(self, *, consumed: int, cost: int, reset_after: timedelta) -> RateLimitDecision:
        """Evaluate bounded counter metadata without an account-existence input."""
        ...


@dataclass(frozen=True, slots=True)
class FixedWindowRateLimitPolicy:
    """Deterministic threshold policy; storage and atomicity remain adapter concerns."""

    limit: int

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("RATE_LIMIT_INVALID")

    def evaluate(self, *, consumed: int, cost: int, reset_after: timedelta) -> RateLimitDecision:
        """Allow within the limit or return one safe retry interval."""
        if consumed < 0 or cost <= 0:
            raise ValueError("RATE_LIMIT_USAGE_INVALID")
        if reset_after <= timedelta(0):
            raise ValueError("RATE_LIMIT_RESET_INVALID")
        if consumed + cost <= self.limit:
            return RateLimitDecision(allowed=True)
        return RateLimitDecision(allowed=False, retry_after=reset_after)


@dataclass(frozen=True, slots=True)
class LockoutDecision:
    """Increasing delay without a revealing permanent account lock."""

    delay: timedelta

    @property
    def allowed(self) -> bool:
        """Return whether expensive credential verification may proceed now."""
        return self.delay == timedelta(0)


class LockoutPolicy(Protocol):
    """Port for deterministic failure-count delay policy."""

    def evaluate(self, *, failed_attempts: int) -> LockoutDecision:
        """Return the same decision regardless of account existence."""
        ...


@dataclass(frozen=True, slots=True)
class ProgressiveLoginLockoutPolicy:
    """Provisional five-attempt exponential delay with a bounded ceiling."""

    threshold: int = 5
    initial_delay: timedelta = timedelta(seconds=1)
    maximum_delay: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.threshold <= 0:
            raise ValueError("LOCKOUT_THRESHOLD_INVALID")
        if self.initial_delay <= timedelta(0) or self.maximum_delay < self.initial_delay:
            raise ValueError("LOCKOUT_DELAY_INVALID")

    def evaluate(self, *, failed_attempts: int) -> LockoutDecision:
        """Apply increasing delay after the provisional failure threshold."""
        if failed_attempts < 0:
            raise ValueError("FAILED_ATTEMPTS_INVALID")
        if failed_attempts < self.threshold:
            return LockoutDecision(delay=timedelta(0))
        multiplier = 1 << min(failed_attempts - self.threshold, 30)
        delay = min(self.initial_delay * multiplier, self.maximum_delay)
        return LockoutDecision(delay=delay)
