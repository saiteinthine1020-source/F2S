"""Exact money, currency, range, scale, and rounding boundary tests."""

from decimal import Decimal, getcontext

import pytest

from app.shared_kernel import (
    INITIAL_CURRENCY_REGISTRY,
    MONEY_STORAGE,
    Money,
    NumericErrorCode,
    NumericValueError,
    quantize_exact,
)


def assert_error(code: NumericErrorCode, operation: object) -> None:
    """Assert a callable fails with one bounded code and no submitted material."""
    assert callable(operation)
    with pytest.raises(NumericValueError) as failure:
        operation()
    assert failure.value.code is code
    assert str(failure.value) == code.value


def test_initial_registry_is_versioned_immutable_and_exact() -> None:
    assert INITIAL_CURRENCY_REGISTRY.supported_codes == ("MMK", "JPY", "USD")
    assert INITIAL_CURRENCY_REGISTRY.require("MMK").accounting_scale == 0
    assert INITIAL_CURRENCY_REGISTRY.require("JPY").standard_minor_unit_scale == 0
    assert INITIAL_CURRENCY_REGISTRY.require("USD").accounting_scale == 2


@pytest.mark.parametrize("code", ["EUR", "GBP", "ZZZ"])
def test_registry_rejects_unsupported_currency(code: str) -> None:
    assert_error(
        NumericErrorCode.UNSUPPORTED_CURRENCY,
        lambda: INITIAL_CURRENCY_REGISTRY.require(code),
    )


@pytest.mark.parametrize("code", ["usd", " USD", "USD ", "US", "USDD", "ＵＳＤ", 1, True])
def test_registry_rejects_malformed_or_non_string_currency(code: object) -> None:
    assert_error(
        NumericErrorCode.INVALID_CURRENCY,
        lambda: INITIAL_CURRENCY_REGISTRY.require(code),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("amount", "currency", "canonical", "storage"),
    [
        ("125000", "MMK", "125000", Decimal("125000.0000")),
        ("4500", "JPY", "4500", Decimal("4500.0000")),
        ("10", "USD", "10.00", Decimal("10.0000")),
        ("10.5", "USD", "10.50", Decimal("10.5000")),
        ("10.50", "USD", "10.50", Decimal("10.5000")),
        ("0.01", "USD", "0.01", Decimal("0.0100")),
    ],
)
def test_ordinary_money_parses_and_serializes_canonically(
    amount: str,
    currency: str,
    canonical: str,
    storage: Decimal,
) -> None:
    money = Money.parse_ordinary(amount, currency)
    assert money.to_api() == {"amount": canonical, "currency_code": currency}
    assert money.to_storage_amount() == storage
    assert type(money.to_api()["amount"]) is str


@pytest.mark.parametrize(
    "amount",
    [
        "1e2",
        "1E+2",
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        ".5",
        "1.",
        "+1",
        "-1",
        "-0",
        " 1",
        "1 ",
        "1,000",
        "1 000",
        "1_000",
        "01",
        "１",
        "",
    ],
)
def test_ordinary_money_rejects_noncanonical_decimal_text(amount: str) -> None:
    assert_error(
        NumericErrorCode.INVALID_DECIMAL_FORMAT,
        lambda: Money.parse_ordinary(amount, "USD"),
    )


@pytest.mark.parametrize(
    "amount",
    [Decimal("1"), 1, True, None, b"1", 0.1, float("nan"), float("inf")],
)
def test_ordinary_money_rejects_every_non_string_amount(amount: object) -> None:
    assert_error(
        NumericErrorCode.INVALID_DECIMAL_TYPE,
        lambda: Money.parse_ordinary(amount, "USD"),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("amount", "currency"),
    [("1.0", "MMK"), ("1.00", "JPY"), ("10.001", "USD")],
)
def test_ordinary_money_rejects_excess_currency_scale(amount: str, currency: str) -> None:
    assert_error(
        NumericErrorCode.INVALID_SCALE,
        lambda: Money.parse_ordinary(amount, currency),
    )


@pytest.mark.parametrize("amount", ["0", "0.0", "0.00"])
def test_ordinary_money_requires_positive_magnitude(amount: str) -> None:
    assert_error(
        NumericErrorCode.AMOUNT_MUST_BE_POSITIVE,
        lambda: Money.parse_ordinary(amount, "USD"),
    )


def test_money_precision_and_range_boundaries() -> None:
    mmk_max = Money.parse_ordinary("99999999999999999999", "MMK")
    usd_max = Money.parse_ordinary("99999999999999999999.99", "USD")
    assert mmk_max.to_api()["amount"] == "99999999999999999999"
    assert usd_max.to_api()["amount"] == "99999999999999999999.99"

    for amount, currency in (
        ("100000000000000000000", "MMK"),
        ("100000000000000000000.00", "USD"),
    ):
        assert_error(
            NumericErrorCode.OUT_OF_RANGE,
            lambda amount=amount, currency=currency: Money.parse_ordinary(amount, currency),
        )


@pytest.mark.parametrize(
    ("source", "currency", "expected"),
    [
        ("2.345", "USD", "2.34"),
        ("2.355", "USD", "2.36"),
        ("2.365", "USD", "2.36"),
        ("-2.345", "USD", "-2.34"),
        ("2.5", "JPY", "2"),
        ("3.5", "JPY", "4"),
        ("15427.5", "JPY", "15428"),
    ],
)
def test_calculated_money_quantizes_half_even_once(
    source: str, currency: str, expected: str
) -> None:
    definition = INITIAL_CURRENCY_REGISTRY.require(currency)
    assert Money.from_calculated(Decimal(source), definition).to_api()["amount"] == expected


def test_exact_arithmetic_and_currency_mismatch() -> None:
    one_tenth = Money.parse_ordinary("0.10", "USD")
    two_tenths = Money.parse_ordinary("0.20", "USD")
    assert one_tenth.add(two_tenths).to_api()["amount"] == "0.30"
    assert one_tenth.add(two_tenths).subtract(two_tenths) == one_tenth

    jpy = Money.parse_ordinary("1", "JPY")
    assert_error(NumericErrorCode.CURRENCY_MISMATCH, lambda: one_tenth.add(jpy))
    assert_error(NumericErrorCode.CURRENCY_MISMATCH, lambda: one_tenth.subtract(jpy))


def test_quantization_rejects_float_non_finite_and_rounding_overflow() -> None:
    invalid_values: tuple[object, ...] = (0.1, 1, True)
    for value in invalid_values:
        assert_error(
            NumericErrorCode.INVALID_DECIMAL_TYPE,
            lambda value=value: Money.from_calculated(
                value,
                INITIAL_CURRENCY_REGISTRY.require("USD"),
            ),
        )
    non_finite_values = (Decimal("NaN"), Decimal("Infinity"))
    for value in non_finite_values:
        assert_error(
            NumericErrorCode.NON_FINITE_VALUE,
            lambda value=value: Money.from_calculated(
                value, INITIAL_CURRENCY_REGISTRY.require("USD")
            ),
        )
    assert_error(
        NumericErrorCode.OUT_OF_RANGE,
        lambda: Money.from_calculated(
            Decimal("99999999999999999999.995"),
            INITIAL_CURRENCY_REGISTRY.require("USD"),
        ),
    )


def test_quantization_does_not_depend_on_mutated_global_decimal_context() -> None:
    original_precision = getcontext().prec
    try:
        getcontext().prec = 6
        result = quantize_exact(Decimal("2.355"), scale=2, spec=MONEY_STORAGE)
        assert result == Decimal("2.36")
    finally:
        getcontext().prec = original_precision


def test_generated_valid_values_round_trip_without_binary_arithmetic() -> None:
    for code in INITIAL_CURRENCY_REGISTRY.supported_codes:
        scale = INITIAL_CURRENCY_REGISTRY.require(code).accounting_scale
        for coefficient in (1, 2, 3, 7, 10, 99, 101, 999_999):
            amount = Decimal(coefficient).scaleb(-scale)
            text = format(amount, f".{scale}f")
            first = Money.parse_ordinary(text, code)
            second = Money.parse_ordinary(first.to_api()["amount"], code)
            assert second == first
