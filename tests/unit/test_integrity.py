"""Tests for the shared integrity primitives."""

from decimal import Decimal

import pytest

from pmv.integrity import (
    FormatError,
    canonical_json,
    canonical_line,
    chain_entry_sha256,
    decimal_text,
    is_decimal_text,
    is_identifier,
    is_int,
    is_non_negative_int,
    is_timestamp,
    is_timestamp_id,
    parse_canonical_json,
    sha256_hex,
)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (0.1, "0.1"),
        (1e-07, "1e-07"),
        (3.0, "3.0"),
        (-2.5, "-2.5"),
        (Decimal("0.10"), "0.10"),
        (Decimal("1E+2"), "1e+2"),
        (Decimal("-0"), "-0"),
    ],
)
def test_decimal_text_is_exact(value: float | Decimal, text: str) -> None:
    assert decimal_text(value) == text
    assert is_decimal_text(text)


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), float("-inf"), Decimal("NaN"), Decimal("Infinity")]
)
def test_non_finite_values_are_rejected(value: float | Decimal) -> None:
    with pytest.raises(ValueError, match="NaN and infinite"):
        decimal_text(value)


def test_booleans_are_not_decimals() -> None:
    with pytest.raises(TypeError):
        decimal_text(True)


@pytest.mark.parametrize("text", ["01", "1.", ".5", "+1", "1E5", "nan", "1e", ""])
def test_noncanonical_decimal_text_is_rejected(text: str) -> None:
    assert not is_decimal_text(text)


def test_identifier_and_timestamp_id_validation() -> None:
    assert is_identifier("study_a1")
    for bad in ("", "A", "1a", "a-b", "a" * 65):
        assert not is_identifier(bad)
    assert is_timestamp_id("20261013T034021.123456Z_" + "0" * 32)
    assert not is_timestamp_id("20261013T034021Z_" + "0" * 32)


def test_canonical_encoding_and_chain_hash() -> None:
    body = {"b": 1, "a": [True, None, "x"]}
    assert canonical_json(body) == b'{"a":[true,null,"x"],"b":1}'
    assert canonical_line(body).endswith(b"}\n")
    assert chain_entry_sha256(body) == sha256_hex(canonical_json(body))
    assert parse_canonical_json(canonical_json(body)) == body
    with pytest.raises(FormatError, match="not canonical"):
        parse_canonical_json(b'{"b":1,"a":2}')
    with pytest.raises(FormatError, match="floats"):
        canonical_json({"a": 0.5})


def test_only_ascii_digits_and_real_integers_are_accepted() -> None:
    assert is_timestamp("2026-10-13T03:40:21.123456Z")
    assert not is_timestamp("2026-10-13T03:40:21.12345\u0666Z")
    assert not is_timestamp_id("2026101\u06633T034021.123456Z_" + "0" * 32)
    assert is_int(0)
    assert is_non_negative_int(0)
    for value in (True, False, 1.0, "1"):
        assert not is_int(value)
    assert not is_non_negative_int(-1)
