"""Recovery abuse-control threshold and subject-safety tests."""

import asyncio
from datetime import UTC, datetime

from app.modules.account_security import DevelopmentRecoveryAbuseControl
from app.modules.identity_security import AbuseSubject, KeyedDigest


def test_recovery_limits_recipient_and_network_without_raw_subjects() -> None:
    async def exercise() -> None:
        control = DevelopmentRecoveryAbuseControl()
        now = datetime(2026, 8, 9, tzinfo=UTC)
        recipient = AbuseSubject(KeyedDigest("a" * 64))
        network = AbuseSubject(KeyedDigest("b" * 64))
        for _ in range(5):
            assert (await control.permit(recipient, network, now=now)).allowed
        denied = await control.permit(recipient, AbuseSubject(KeyedDigest("c" * 64)), now=now)
        assert not denied.allowed
        assert denied.retry_after is not None
        assert "member@example" not in repr(control)

        separate = DevelopmentRecoveryAbuseControl()
        for index in range(20):
            subject = AbuseSubject(KeyedDigest(f"{index:064x}"))
            assert (await separate.permit(subject, network, now=now)).allowed
        assert not (
            await separate.permit(AbuseSubject(KeyedDigest("f" * 64)), network, now=now)
        ).allowed

    asyncio.run(exercise())
