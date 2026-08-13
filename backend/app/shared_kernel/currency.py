"""Immutable approved currency registry for exact money boundaries."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.shared_kernel.decimals import NumericErrorCode, NumericValueError


@dataclass(frozen=True, slots=True)
class Currency:
    """Versioned currency metadata retained by every Money value."""

    code: str
    accounting_scale: int
    standard_minor_unit_scale: int
    registry_version: str


class CurrencyRegistry:
    """Read-only registry with strict, non-normalizing lookup."""

    __slots__ = ("_currencies", "version")

    def __init__(self, version: str, currencies: tuple[Currency, ...]) -> None:
        self.version = version
        self._currencies: Mapping[str, Currency] = MappingProxyType(
            {currency.code: currency for currency in currencies}
        )

    @property
    def supported_codes(self) -> tuple[str, ...]:
        return tuple(self._currencies)

    def require(self, code: str) -> Currency:
        if type(code) is not str or re.fullmatch(r"[A-Z]{3}", code, re.ASCII) is None:
            raise NumericValueError(NumericErrorCode.INVALID_CURRENCY)
        try:
            return self._currencies[code]
        except KeyError as error:
            raise NumericValueError(NumericErrorCode.UNSUPPORTED_CURRENCY) from error


CURRENCY_REGISTRY_VERSION = "2026-08-04"
INITIAL_CURRENCY_REGISTRY = CurrencyRegistry(
    CURRENCY_REGISTRY_VERSION,
    (
        Currency("MMK", 0, 0, CURRENCY_REGISTRY_VERSION),
        Currency("JPY", 0, 0, CURRENCY_REGISTRY_VERSION),
        Currency("USD", 2, 2, CURRENCY_REGISTRY_VERSION),
    ),
)
