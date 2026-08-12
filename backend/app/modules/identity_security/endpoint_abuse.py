"""Keyed fixed-window controls for credential-bearing endpoints."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.modules.identity_security.abuse import AbuseSubject, RateLimitDecision


class SubjectAbuseControl(Protocol):
    async def permit(self, subject: AbuseSubject, *, now: datetime) -> RateLimitDecision: ...


class DualSubjectAbuseControl(Protocol):
    async def permit(
        self, subject: AbuseSubject, network: AbuseSubject, *, now: datetime
    ) -> RateLimitDecision: ...


class DevelopmentSubjectAbuseControl(SubjectAbuseControl):
    """Process-local fixed window for local and test environments only."""

    def __init__(self, *, limit: int, window: timedelta) -> None:
        if limit <= 0 or window <= timedelta(0):
            raise ValueError("RATE_LIMIT_POLICY_INVALID")
        self._limit = limit
        self._window = window
        self._lock = asyncio.Lock()
        self._windows: dict[str, _Window] = {}

    async def permit(self, subject: AbuseSubject, *, now: datetime) -> RateLimitDecision:
        async with self._lock:
            return _consume(
                self._windows,
                subject.digest.for_persistence(),
                now,
                self._limit,
                self._window,
            )


class DevelopmentDualSubjectAbuseControl(DualSubjectAbuseControl):
    """Process-local credential and network windows using keyed subjects only."""

    def __init__(self, *, subject_limit: int, network_limit: int, window: timedelta) -> None:
        if subject_limit <= 0 or network_limit <= 0 or window <= timedelta(0):
            raise ValueError("RATE_LIMIT_POLICY_INVALID")
        self._subject_limit = subject_limit
        self._network_limit = network_limit
        self._window = window
        self._lock = asyncio.Lock()
        self._subjects: dict[str, _Window] = {}
        self._networks: dict[str, _Window] = {}

    async def permit(
        self, subject: AbuseSubject, network: AbuseSubject, *, now: datetime
    ) -> RateLimitDecision:
        async with self._lock:
            subject_key = subject.digest.for_persistence()
            network_key = network.digest.for_persistence()
            subject_decision, subject_window = _preview(
                self._subjects,
                subject_key,
                now,
                self._subject_limit,
                self._window,
            )
            network_decision, network_window = _preview(
                self._networks,
                network_key,
                now,
                self._network_limit,
                self._window,
            )
            if not subject_decision.allowed:
                return subject_decision
            if not network_decision.allowed:
                return network_decision
            self._subjects[subject_key] = subject_window
            self._networks[network_key] = network_window
            return RateLimitDecision(True)


class RejectingSubjectAbuseControl(SubjectAbuseControl):
    """Fail closed until production has a reviewed distributed adapter."""

    async def permit(self, subject: AbuseSubject, *, now: datetime) -> RateLimitDecision:
        del subject, now
        return RateLimitDecision(False, timedelta(minutes=5))


class RejectingDualSubjectAbuseControl(DualSubjectAbuseControl):
    """Fail closed until production has a reviewed distributed adapter."""

    async def permit(
        self, subject: AbuseSubject, network: AbuseSubject, *, now: datetime
    ) -> RateLimitDecision:
        del subject, network, now
        return RateLimitDecision(False, timedelta(minutes=5))


@dataclass(frozen=True, slots=True)
class _Window:
    attempts: int
    reset_at: datetime


def _consume(
    windows: dict[str, _Window], key: str, now: datetime, limit: int, duration: timedelta
) -> RateLimitDecision:
    decision, next_window = _preview(windows, key, now, limit, duration)
    if decision.allowed:
        windows[key] = next_window
    return decision


def _preview(
    windows: dict[str, _Window], key: str, now: datetime, limit: int, duration: timedelta
) -> tuple[RateLimitDecision, _Window]:
    window = windows.get(key)
    if window is None or now >= window.reset_at:
        window = _Window(0, now + duration)
    if window.attempts >= limit:
        return RateLimitDecision(False, window.reset_at - now), window
    return RateLimitDecision(True), _Window(window.attempts + 1, window.reset_at)
