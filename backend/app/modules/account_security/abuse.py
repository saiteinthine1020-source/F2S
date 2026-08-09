"""Concealed recovery-request abuse controls for local and test environments."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.modules.identity_security import AbuseSubject, RateLimitDecision


class RecoveryAbuseControl(Protocol):
    async def permit(
        self, recipient: AbuseSubject, network: AbuseSubject, *, now: datetime
    ) -> RateLimitDecision: ...


class DevelopmentRecoveryAbuseControl(RecoveryAbuseControl):
    """Atomic one-hour windows using keyed subjects only."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._recipients: dict[str, _Window] = {}
        self._networks: dict[str, _Window] = {}

    async def permit(
        self, recipient: AbuseSubject, network: AbuseSubject, *, now: datetime
    ) -> RateLimitDecision:
        async with self._lock:
            recipient_decision = self._consume(
                self._recipients, recipient.digest.for_persistence(), now, 5
            )
            network_decision = self._consume(
                self._networks, network.digest.for_persistence(), now, 20
            )
            if not recipient_decision.allowed:
                return recipient_decision
            return network_decision

    @staticmethod
    def _consume(
        windows: dict[str, "_Window"], key: str, now: datetime, limit: int
    ) -> RateLimitDecision:
        window = windows.get(key)
        if window is None or now >= window.reset_at:
            window = _Window(0, now + timedelta(hours=1))
        if window.attempts >= limit:
            return RateLimitDecision(False, window.reset_at - now)
        windows[key] = _Window(window.attempts + 1, window.reset_at)
        return RateLimitDecision(True)


class RejectingRecoveryAbuseControl(RecoveryAbuseControl):
    """Fail closed where a distributed production limiter is unavailable."""

    async def permit(
        self, recipient: AbuseSubject, network: AbuseSubject, *, now: datetime
    ) -> RateLimitDecision:
        del recipient, network, now
        return RateLimitDecision(False, timedelta(minutes=5))


@dataclass(frozen=True, slots=True)
class _Window:
    attempts: int
    reset_at: datetime
