"""Concealed in-process login abuse controls for local and test environments."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.modules.identity_security import (
    AbuseSubject,
    ProgressiveLoginLockoutPolicy,
    RateLimitDecision,
)


class LoginAbuseControl(Protocol):
    async def permit(
        self,
        account: AbuseSubject,
        network: AbuseSubject,
        *,
        now: datetime,
    ) -> RateLimitDecision: ...

    async def failed(self, account: AbuseSubject, *, now: datetime) -> None: ...

    async def succeeded(self, account: AbuseSubject) -> None: ...


class DevelopmentLoginAbuseControl(LoginAbuseControl):
    """Atomic process-local counters; production must provide a distributed adapter."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._accounts: dict[str, _AccountFailures] = {}
        self._networks: dict[str, _NetworkWindow] = {}
        self._policy = ProgressiveLoginLockoutPolicy()

    async def permit(
        self,
        account: AbuseSubject,
        network: AbuseSubject,
        *,
        now: datetime,
    ) -> RateLimitDecision:
        account_key = account.digest.for_persistence()
        network_key = network.digest.for_persistence()
        async with self._lock:
            network_window = self._networks.get(network_key)
            if network_window is None or now >= network_window.reset_at:
                network_window = _NetworkWindow(0, now + timedelta(minutes=15))
            if network_window.attempts >= 30:
                return RateLimitDecision(False, network_window.reset_at - now)
            self._networks[network_key] = _NetworkWindow(
                network_window.attempts + 1,
                network_window.reset_at,
            )

            failures = self._accounts.get(account_key)
            if failures is None or now >= failures.reset_at:
                return RateLimitDecision(True)
            decision = self._policy.evaluate(failed_attempts=failures.count)
            if decision.allowed or failures.last_failure_at + decision.delay <= now:
                return RateLimitDecision(True)
            return RateLimitDecision(
                False,
                failures.last_failure_at + decision.delay - now,
            )

    async def failed(self, account: AbuseSubject, *, now: datetime) -> None:
        key = account.digest.for_persistence()
        async with self._lock:
            current = self._accounts.get(key)
            count = 1 if current is None or now >= current.reset_at else current.count + 1
            self._accounts[key] = _AccountFailures(
                count=count,
                last_failure_at=now,
                reset_at=now + timedelta(minutes=15),
            )

    async def succeeded(self, account: AbuseSubject) -> None:
        async with self._lock:
            self._accounts.pop(account.digest.for_persistence(), None)


class RejectingLoginAbuseControl(LoginAbuseControl):
    """Fail closed where a production distributed abuse adapter is unavailable."""

    async def permit(
        self,
        account: AbuseSubject,
        network: AbuseSubject,
        *,
        now: datetime,
    ) -> RateLimitDecision:
        del account, network, now
        return RateLimitDecision(False, timedelta(minutes=5))

    async def failed(self, account: AbuseSubject, *, now: datetime) -> None:
        del account, now

    async def succeeded(self, account: AbuseSubject) -> None:
        del account


@dataclass(frozen=True, slots=True)
class _AccountFailures:
    count: int
    last_failure_at: datetime
    reset_at: datetime


@dataclass(frozen=True, slots=True)
class _NetworkWindow:
    attempts: int
    reset_at: datetime
