"""Concealed local/test login abuse-control tests."""

import asyncio
from datetime import UTC, datetime, timedelta

from app.modules.identity_security import AbuseSubject, KeyedDigest
from app.modules.sessions import DevelopmentLoginAbuseControl


def _subject(value: str) -> AbuseSubject:
    return AbuseSubject(KeyedDigest(value * 64))


def test_progressive_account_delay_starts_after_five_failures_and_resets() -> None:
    async def exercise() -> None:
        control = DevelopmentLoginAbuseControl()
        account, network = _subject("a"), _subject("n")
        now = datetime(2026, 8, 9, tzinfo=UTC)
        for _ in range(4):
            await control.failed(account, now=now)
        assert (await control.permit(account, network, now=now)).allowed

        await control.failed(account, now=now)
        delayed = await control.permit(account, network, now=now)
        assert not delayed.allowed
        assert delayed.retry_after == timedelta(seconds=1)
        assert (await control.permit(account, network, now=now + timedelta(seconds=1))).allowed

        await control.succeeded(account)
        assert (await control.permit(account, network, now=now)).allowed

    asyncio.run(exercise())


def test_network_window_rejects_the_thirty_first_attempt_without_raw_subjects() -> None:
    async def exercise() -> None:
        control = DevelopmentLoginAbuseControl()
        account, network = _subject("b"), _subject("m")
        now = datetime(2026, 8, 9, tzinfo=UTC)
        for _ in range(30):
            assert (await control.permit(account, network, now=now)).allowed
        blocked = await control.permit(account, network, now=now)
        assert not blocked.allowed
        assert blocked.retry_after == timedelta(minutes=15)
        assert "b" * 64 not in repr(control)
        assert "m" * 64 not in repr(control)

    asyncio.run(exercise())
