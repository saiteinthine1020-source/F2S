"""Exact decimal parsing, validation, formatting, and boundary quantisation."""

import re
from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    FloatOperation,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum


class NumericErrorCode(StrEnum):
    """Stable, bounded failures for authoritative numeric boundaries."""

    INVALID_DECIMAL_TYPE = "INVALID_DECIMAL_TYPE"
    INVALID_DECIMAL_FORMAT = "INVALID_DECIMAL_FORMAT"
    INVALID_SCALE = "INVALID_SCALE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    AMOUNT_MUST_BE_POSITIVE = "AMOUNT_MUST_BE_POSITIVE"
    INVALID_CURRENCY = "INVALID_CURRENCY"
    UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"


class NumericValueError(ValueError):
    """Numeric validation failure that never includes submitted material."""

    def __init__(self, code: NumericErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class DecimalSpec:
    """Precision and scale envelope for one authoritative decimal category."""

    precision: int
    scale: int

    @property
    def maximum_integer_digits(self) -> int:
        return self.precision - self.scale


MONEY_STORAGE = DecimalSpec(precision=24, scale=4)
EXCHANGE_RATE = DecimalSpec(precision=24, scale=12)
RATIO = DecimalSpec(precision=18, scale=10)
QUANTITY = DecimalSpec(precision=24, scale=8)
UNIT_PRICE = DecimalSpec(precision=24, scale=8)

_UNSIGNED_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]+))?", re.ASCII)
_SIGNED_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.([0-9]+))?", re.ASCII)
_CALCULATION_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
for _signal in (InvalidOperation, DivisionByZero, Overflow, FloatOperation):
    _CALCULATION_CONTEXT.traps[_signal] = True


def _scale(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise NumericValueError(NumericErrorCode.NON_FINITE_VALUE)
    return max(0, -exponent)


def _integer_digits(value: Decimal) -> int:
    if value.is_zero():
        return 1
    return max(1, value.copy_abs().adjusted() + 1)


def validate_decimal(value: Decimal, *, spec: DecimalSpec) -> Decimal:
    """Validate an exact Decimal against a storage envelope."""
    if type(value) is not Decimal:
        raise NumericValueError(NumericErrorCode.INVALID_DECIMAL_TYPE)
    if not value.is_finite():
        raise NumericValueError(NumericErrorCode.NON_FINITE_VALUE)
    if _scale(value) > spec.scale:
        raise NumericValueError(NumericErrorCode.INVALID_SCALE)
    if _integer_digits(value) > spec.maximum_integer_digits:
        raise NumericValueError(NumericErrorCode.OUT_OF_RANGE)
    return Decimal(0) if value.is_zero() else value


def parse_exact_decimal(
    text: str,
    *,
    spec: DecimalSpec,
    maximum_input_scale: int | None = None,
    signed: bool = False,
) -> Decimal:
    """Parse only an ASCII, non-exponent decimal string without coercion."""
    if type(text) is not str:
        raise NumericValueError(NumericErrorCode.INVALID_DECIMAL_TYPE)
    match = (_SIGNED_DECIMAL if signed else _UNSIGNED_DECIMAL).fullmatch(text)
    if match is None:
        raise NumericValueError(NumericErrorCode.INVALID_DECIMAL_FORMAT)
    fractional_digits = len(match.group(1) or "")
    accepted_scale = spec.scale if maximum_input_scale is None else maximum_input_scale
    if fractional_digits > accepted_scale:
        raise NumericValueError(NumericErrorCode.INVALID_SCALE)
    return validate_decimal(Decimal(text), spec=spec)


def quantize_exact(value: Decimal, *, scale: int, spec: DecimalSpec) -> Decimal:
    """Apply round-half-even once at an explicit calculated-value boundary."""
    if type(value) is not Decimal:
        raise NumericValueError(NumericErrorCode.INVALID_DECIMAL_TYPE)
    if not value.is_finite():
        raise NumericValueError(NumericErrorCode.NON_FINITE_VALUE)
    quantum = Decimal(1).scaleb(-scale)
    try:
        with localcontext(_CALCULATION_CONTEXT):
            result = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    except (InvalidOperation, Overflow) as error:
        raise NumericValueError(NumericErrorCode.OUT_OF_RANGE) from error
    return validate_decimal(result, spec=spec)


def add_exact(left: Decimal, right: Decimal, *, spec: DecimalSpec) -> Decimal:
    """Add exact values under the guarded calculation context."""
    validate_decimal(left, spec=spec)
    validate_decimal(right, spec=spec)
    with localcontext(_CALCULATION_CONTEXT):
        return validate_decimal(left + right, spec=spec)


def subtract_exact(left: Decimal, right: Decimal, *, spec: DecimalSpec) -> Decimal:
    """Subtract exact values under the guarded calculation context."""
    validate_decimal(left, spec=spec)
    validate_decimal(right, spec=spec)
    with localcontext(_CALCULATION_CONTEXT):
        return validate_decimal(left - right, spec=spec)


def canonical_decimal(value: Decimal, *, scale: int, spec: DecimalSpec) -> str:
    """Return fixed-scale plain text, never exponent or negative zero notation."""
    validated = validate_decimal(value, spec=spec)
    if _scale(validated) > scale:
        raise NumericValueError(NumericErrorCode.INVALID_SCALE)
    normalized = Decimal(0) if validated.is_zero() else validated
    return format(normalized, f".{scale}f")
