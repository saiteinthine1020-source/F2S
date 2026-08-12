"""Stable cross-module primitives with no workflow or framework dependencies."""

from app.shared_kernel.currency import (
    CURRENCY_REGISTRY_VERSION,
    INITIAL_CURRENCY_REGISTRY,
    Currency,
    CurrencyRegistry,
)
from app.shared_kernel.decimals import (
    EXCHANGE_RATE,
    MONEY_STORAGE,
    QUANTITY,
    RATIO,
    UNIT_PRICE,
    DecimalSpec,
    NumericErrorCode,
    NumericValueError,
    add_exact,
    canonical_decimal,
    parse_exact_decimal,
    quantize_exact,
    subtract_exact,
)
from app.shared_kernel.money import Money, MoneyApiValue

__all__ = [
    "CURRENCY_REGISTRY_VERSION",
    "EXCHANGE_RATE",
    "INITIAL_CURRENCY_REGISTRY",
    "MONEY_STORAGE",
    "QUANTITY",
    "RATIO",
    "UNIT_PRICE",
    "Currency",
    "CurrencyRegistry",
    "DecimalSpec",
    "Money",
    "MoneyApiValue",
    "NumericErrorCode",
    "NumericValueError",
    "add_exact",
    "canonical_decimal",
    "parse_exact_decimal",
    "quantize_exact",
    "subtract_exact",
]
