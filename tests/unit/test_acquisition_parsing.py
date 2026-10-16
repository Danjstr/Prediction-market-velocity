from decimal import Decimal

import pytest

from pmv.acquisition.formats import FileFormat, FormatRefusedError, check_format
from pmv.acquisition.strict_parse import (
    StrictParseError,
    parse_csv,
    parse_decimal_field,
    parse_json,
    parse_jsonl,
)


@pytest.mark.parametrize(
    ("name", "declared", "head", "tail"),
    [
        ("a.csv", FileFormat.CSV, b"x,y\n1,2", b"1,2\n"),
        ("a.json", FileFormat.JSON, b'{"a":1}', b":1}\n"),
        ("a.ndjson", FileFormat.JSONL, b'{"a":1}', b":1}\n"),
        ("a.parquet", FileFormat.PARQUET, b"PAR1\x15\x04", b"PAR1"),
        ("a.dbn", FileFormat.DBN, b"DBN\x02abcd", b"abcd"),
        ("A.TXT", FileFormat.TEXT, b"hello", b"llo\n"),
    ],
)
def test_allowed_formats(name: str, declared: FileFormat, head: bytes, tail: bytes) -> None:
    assert check_format(name, declared, head, tail) is declared


@pytest.mark.parametrize(
    ("name", "declared", "head", "tail", "match"),
    [
        ("a.parquet", FileFormat.CSV, b"x", b"x", "extension"),
        ("a.npy", FileFormat.TEXT, b"x", b"x", "refused"),
        ("a.ipynb", FileFormat.JSON, b"{", b"}", "refused"),
        ("a.pkl", FileFormat.TEXT, b"x", b"x", "refused"),
        ("a.csv.gz", FileFormat.CSV, b"\x1f\x8b", b"x", "refused"),
        ("a.csv", FileFormat.CSV, b"\x93NUMPY\x01\x00", b"x", "NumPy"),
        ("a.csv", FileFormat.CSV, b"PK\x03\x04", b"x", "zip"),
        ("a.csv", FileFormat.CSV, b"\x7fELF\x02", b"x", "ELF"),
        ("a.txt", FileFormat.TEXT, b"#!/bin/sh", b"x", "script"),
        ("a.csv", FileFormat.CSV, b"\xef\xbb\xbfa,b", b"x", "byte-order"),
        ("a.csv", FileFormat.CSV, b"a\x00b", b"x", "NUL"),
        ("a.parquet", FileFormat.PARQUET, b"PAR1", b"XXXX", "not a Parquet"),
        ("a.dbn", FileFormat.DBN, b"XYZ", b"x", "not a DBN"),
        ("noext", FileFormat.TEXT, b"x", b"x", "extension"),
    ],
)
def test_refused_formats(
    name: str, declared: FileFormat, head: bytes, tail: bytes, match: str
) -> None:
    with pytest.raises(FormatRefusedError, match=match):
        check_format(name, declared, head, tail)


def test_declared_format_must_be_an_enum_member() -> None:
    with pytest.raises(FormatRefusedError):
        check_format("a.csv", "csv", b"x", b"x")  # type: ignore[arg-type]


def test_csv_parses_with_required_columns() -> None:
    header, rows = parse_csv(b'a,b\n1,"x,y"\n', required_columns=["a"])
    assert header == ("a", "b")
    assert rows == [("1", "x,y")]


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b"", "no header"),
        (b"a,a\n1,2\n", "duplicate"),
        (b"a,\n1,2\n", "empty"),
        (b"a,b\n1\n", "expected 2 fields"),
        (b'a,b\n"1,2\n', "malformed"),
        (b"\xef\xbb\xbfa\n1\n", "byte-order"),
        (b"a\n\xff\n", "UTF-8"),
        (b"a\n\x00\n", "NUL"),
    ],
)
def test_csv_strictness(data: bytes, match: str) -> None:
    with pytest.raises(StrictParseError, match=match):
        parse_csv(data)


def test_csv_required_column_missing() -> None:
    with pytest.raises(StrictParseError, match="required column"):
        parse_csv(b"a\n1\n", required_columns=["b"])


def test_size_limit() -> None:
    with pytest.raises(StrictParseError, match="size limit"):
        parse_json(b"[1,2,3]", max_bytes=3)


def test_depth_limit_without_recursion_error() -> None:
    deep = b"[" * 10_000 + b"]" * 10_000
    with pytest.raises(StrictParseError, match="depth"):
        parse_json(deep)
    with pytest.raises(StrictParseError, match="depth"):
        parse_json(b"[[[1]]]", max_depth=2)
    assert parse_json(b'["[[[[", 1]', max_depth=1) == ["[[[[", 1]


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b'{"a":1}\n\n{"a":2}\n', "blank line"),
        (b'{"a":1}', "newline-terminated"),
        (b'{"a":1}\r\n', "carriage"),
        (b"{bad}\n", "not valid JSON"),
    ],
)
def test_jsonl_strictness(data: bytes, match: str) -> None:
    with pytest.raises(StrictParseError, match=match):
        parse_jsonl(data)


def test_jsonl_parses() -> None:
    assert parse_jsonl(b"") == []
    assert parse_jsonl(b'{"a":1}\n[2]\n') == [{"a": 1}, [2]]


@pytest.mark.parametrize("text", ["0", "-0.25", "+12.5", ".5", "100"])
def test_plain_decimals(text: str) -> None:
    assert parse_decimal_field(text) == Decimal(text)


@pytest.mark.parametrize("text", ["", "NaN", "inf", "1e5", "1.", "01", "1,000", " 1", "0x10"])
def test_non_plain_decimals(text: str) -> None:
    with pytest.raises(StrictParseError):
        parse_decimal_field(text)
