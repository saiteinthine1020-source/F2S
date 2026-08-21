"""Financial-event cursor integrity and expiry tests."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from app.api.financial_event_cursors import (
    InvalidFinancialEventCursor,
    decode_financial_event_cursor,
    encode_financial_event_cursor,
)
from app.modules.household_finance import FinancialEventCursorPosition
from app.modules.identity_security import KeyedDigestService, SecretBytes


def _digests() -> KeyedDigestService:
    return KeyedDigestService(SecretBytes(b"synthetic-cursor-test-key-material-0001"))


def test_cursor_round_trip_is_scope_bound_and_opaque() -> None:
    now = datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC)
    position = FinancialEventCursorPosition(
        date(2026, 8, 14),
        datetime(2026, 8, 14, 4, 5, 6, tzinfo=UTC),
        UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    )
    cursor = encode_financial_event_cursor(position, scope="a" * 64, digests=_digests(), now=now)

    assert cursor != str(position.event_id)
    assert (
        decode_financial_event_cursor(cursor, expected_scope="a" * 64, digests=_digests(), now=now)
        == position
    )


def test_cursor_rejects_tampering_scope_change_and_expiry() -> None:
    now = datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC)
    position = FinancialEventCursorPosition(
        date(2026, 8, 14), now, UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    )
    cursor = encode_financial_event_cursor(position, scope="b" * 64, digests=_digests(), now=now)

    for candidate, scope, checked_at in (
        (cursor[:-1] + ("0" if cursor[-1] != "0" else "1"), "b" * 64, now),
        (cursor, "c" * 64, now),
        (cursor, "b" * 64, now + timedelta(hours=24)),
        ("not-a-cursor", "b" * 64, now),
    ):
        with pytest.raises(InvalidFinancialEventCursor):
            decode_financial_event_cursor(
                candidate,
                expected_scope=scope,
                digests=_digests(),
                now=checked_at,
            )
