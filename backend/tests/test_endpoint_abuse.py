"""Credential-endpoint fixed-window control tests."""

import asyncio
from datetime import UTC, datetime, timedelta

from app.modules.identity_security import (
    AbuseSubject,
    DevelopmentDualSubjectAbuseControl,
    DevelopmentSubjectAbuseControl,
    KeyedDigest,
)


def _subject(character: str) -> AbuseSubject:
    return AbuseSubject(KeyedDigest(character * 64))


def test_subject_window_blocks_after_limit_and_resets() -> None:
    async def exercise() -> None:
        control = DevelopmentSubjectAbuseControl(limit=2, window=timedelta(minutes=5))
        subject = _subject("a")
        now = datetime(2026, 8, 12, tzinfo=UTC)

        assert (await control.permit(subject, now=now)).allowed
        assert (await control.permit(subject, now=now)).allowed
        blocked = await control.permit(subject, now=now)
        assert not blocked.allowed
        assert blocked.retry_after == timedelta(minutes=5)
        assert (await control.permit(subject, now=now + timedelta(minutes=5))).allowed
        assert "a" * 64 not in repr(control)

    asyncio.run(exercise())


def test_dual_window_enforces_subject_and_network_limits() -> None:
    async def exercise() -> None:
        control = DevelopmentDualSubjectAbuseControl(
            subject_limit=2,
            network_limit=2,
            window=timedelta(hours=1),
        )
        now = datetime(2026, 8, 12, tzinfo=UTC)
        network = _subject("n")

        assert (await control.permit(_subject("a"), network, now=now)).allowed
        assert (await control.permit(_subject("b"), network, now=now)).allowed
        network_blocked = await control.permit(_subject("c"), network, now=now)
        assert not network_blocked.allowed

        other_network = _subject("m")
        assert (await control.permit(_subject("d"), other_network, now=now)).allowed
        assert (await control.permit(_subject("d"), other_network, now=now)).allowed
        subject_blocked = await control.permit(_subject("d"), _subject("z"), now=now)
        assert not subject_blocked.allowed
        assert "n" * 64 not in repr(control)

    asyncio.run(exercise())
