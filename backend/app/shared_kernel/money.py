"""Currency-labelled exact money values for authoritative finance paths."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Self, TypedDict

from app.shared_kernel.currency import (
    INITIAL_CURRENCY_REGISTRY,
    Currency,
    CurrencyRegistry,
)
from app.shared_kernel.decimals import (
    MONEY_STORAGE,
    NumericErrorCode,
    NumericValueError,
    add_exact,
    canonical_decimal,
    parse_exact_decimal,
    quantize_exact,
    subtract_exact,
    validate_decimal,
)


class MoneyApiValue(TypedDict):
    """Transport-neutral API representation with no JSON numeric token."""

    amount: str
    currency_code: str


@dataclass(frozen=True, slots=True)
class Money:
    """Exact amount and immutable currency metadata."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", validate_decimal(self.amount, spec=MONEY_STORAGE))

    @classmethod
    def parse_ordinary(
        cls,
        amount: str,
        currency_code: str,
        *,
        registry: CurrencyRegistry = INITIAL_CURRENCY_REGISTRY,
    ) -> Self:
        """Parse a strictly positive ordinary input without silent rounding."""
        currency = registry.require(currency_code)
        parsed = parse_exact_decimal(
            amount,
            spec=MONEY_STORAGE,
            maximum_input_scale=currency.accounting_scale,
        )
        if parsed <= Decimal(0):
            raise NumericValueError(NumericErrorCode.AMOUNT_MUST_BE_POSITIVE)
        return cls(parsed, currency)

    @classmethod
    def from_calculated(cls, amount: Decimal, currency: Currency) -> Self:
        """Quantise a signed calculated result at the currency boundary."""
        return cls(
            quantize_exact(amount, scale=currency.accounting_scale, spec=MONEY_STORAGE),
            currency,
        )

    def to_api(self) -> MoneyApiValue:
        return {
            "amount": canonical_decimal(
                self.amount,
                scale=self.currency.accounting_scale,
                spec=MONEY_STORAGE,
            ),
            "currency_code": self.currency.code,
        }

    def to_storage_amount(self) -> Decimal:
        """Return the exact Decimal for a NUMERIC(24,4) adapter."""
        return quantize_exact(self.amount, scale=MONEY_STORAGE.scale, spec=MONEY_STORAGE)

    def _require_same_currency(self, other: Self) -> None:
        if self.currency != other.currency:
            raise NumericValueError(NumericErrorCode.CURRENCY_MISMATCH)

    def add(self, other: Self) -> Self:
        self._require_same_currency(other)
        return type(self).from_calculated(
            add_exact(self.amount, other.amount, spec=MONEY_STORAGE), self.currency
        )

    def subtract(self, other: Self) -> Self:
        self._require_same_currency(other)
        return type(self).from_calculated(
            subtract_exact(self.amount, other.amount, spec=MONEY_STORAGE), self.currency
        )
