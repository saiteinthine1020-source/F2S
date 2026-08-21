"""Integrity-protected, scope-bound cursors for financial-event keyset pagination."""

import base64
import binascii
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Final
from uuid import UUID

from app.modules.household_finance import FinancialEventCursorPosition
from app.modules.identity_security import (
    DigestPurpose,
    KeyedDigest,
    KeyedDigestService,
    SecretText,
)

_CURSOR_VERSION: Final = 1
_CURSOR_LIFETIME: Final = timedelta(hours=24)
_MAXIMUM_CURSOR_LENGTH: Final = 1024
_PAYLOAD_KEYS: Final = frozenset({"v", "scope", "occurred_on", "created_at", "id", "exp"})


class InvalidFinancialEventCursor(Exception):
    """The cursor is malformed, expired, tampered with, or scope-incompatible."""


def encode_financial_event_cursor(
    position: FinancialEventCursorPosition,
    *,
    scope: str,
    digests: KeyedDigestService,
    now: datetime | None = None,
) -> str:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("CURSOR_TIMEZONE_REQUIRED")
    if re.fullmatch(r"[0-9a-f]{64}", scope, re.ASCII) is None:
        raise ValueError("INVALID_CURSOR_SCOPE")
    payload = {
        "v": _CURSOR_VERSION,
        "scope": scope,
        "occurred_on": position.occurred_on.isoformat(),
        "created_at": position.created_at.astimezone(UTC).isoformat(),
        "id": str(position.event_id),
        "exp": int((current + _CURSOR_LIFETIME).timestamp()),
    }
    encoded_payload = _encode_payload(payload)
    signature = digests.digest(
        DigestPurpose.FINANCIAL_EVENT_CURSOR, SecretText(encoded_payload)
    ).for_persistence()
    return f"{encoded_payload}.{signature}"


def decode_financial_event_cursor(
    value: str,
    *,
    expected_scope: str,
    digests: KeyedDigestService,
    now: datetime | None = None,
) -> FinancialEventCursorPosition:
    try:
        if type(value) is not str or not 1 <= len(value) <= _MAXIMUM_CURSOR_LENGTH:
            raise InvalidFinancialEventCursor
        value.encode("ascii")
        encoded_payload, signature = value.split(".", maxsplit=1)
        if len(signature) != 64:
            raise InvalidFinancialEventCursor
        int(signature, 16)
        if not digests.verify(
            DigestPurpose.FINANCIAL_EVENT_CURSOR,
            SecretText(encoded_payload),
            KeyedDigest(signature),
        ):
            raise InvalidFinancialEventCursor
        payload = _decode_payload(encoded_payload)
        if set(payload) != _PAYLOAD_KEYS:
            raise InvalidFinancialEventCursor
        current = now or datetime.now(UTC)
        if current.tzinfo is None or current.utcoffset() is None:
            raise InvalidFinancialEventCursor
        if (
            type(payload["v"]) is not int
            or payload["v"] != _CURSOR_VERSION
            or type(payload["scope"]) is not str
            or payload["scope"] != expected_scope
        ):
            raise InvalidFinancialEventCursor
        expiry = payload["exp"]
        if type(expiry) is not int or int(current.timestamp()) >= expiry:
            raise InvalidFinancialEventCursor
        occurred_on = date.fromisoformat(_require_string(payload["occurred_on"]))
        created_at = datetime.fromisoformat(_require_string(payload["created_at"]))
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise InvalidFinancialEventCursor
        event_id = UUID(_require_string(payload["id"]))
        return FinancialEventCursorPosition(occurred_on, created_at, event_id)
    except (
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise InvalidFinancialEventCursor from error


def _encode_payload(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_payload(value: str) -> dict[str, object]:
    padding = "=" * (-len(value) % 4)
    raw = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    decoded = json.loads(raw.decode("ascii"))
    if type(decoded) is not dict:
        raise InvalidFinancialEventCursor
    return decoded


def _require_string(value: object) -> str:
    if type(value) is not str:
        raise InvalidFinancialEventCursor
    return value
