"""Strict JSON, JSONL, CSV, and decimal parsing for untrusted acquired files (A-4).

Text must be strict UTF-8 with no NUL bytes and no byte-order mark. JSON numbers parse to
``int`` or ``Decimal``, never ``float``. NaN, Infinity, exponents beyond ±1000, integers
longer than 100 digits, lone surrogates, duplicate object keys, and excessive nesting are
rejected, never coerced.

Parsed JSON costs far more memory than its text (around 50 times for small objects), so
whole-document JSON and CSV are capped at 4 MiB by default. Larger files use
``iter_jsonl``, which bounds each line and keeps only one document in memory at a time.
Process-level memory limits for the parser are part of the A-4 isolation work
(``docs/acquisition_readiness.md``). Blank JSONL lines, ragged CSV rows, and
duplicate CSV headers are errors, never silently dropped. Error messages give a location,
never the offending content.
"""

import csv
import io
import json
import re
from collections.abc import Iterator, Sequence
from decimal import Decimal, InvalidOperation
from typing import IO, Final

DEFAULT_MAX_BYTES: Final = 4 * 1024 * 1024
DEFAULT_MAX_LINE_BYTES: Final = 1024 * 1024
_MAX_EXPONENT: Final = 1000
_MAX_INT_DIGITS: Final = 100
DEFAULT_MAX_DEPTH: Final = 64
_DECIMAL_FIELD: Final = re.compile(r"[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?|[+-]?\.[0-9]+")


class StrictParseError(Exception):
    """Untrusted content failed strict parsing. Messages never include the content."""


def decode_text(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    if len(data) > max_bytes:
        raise StrictParseError("content exceeds the size limit")
    if data.startswith(b"\xef\xbb\xbf"):
        raise StrictParseError("byte-order mark is not allowed")
    if b"\x00" in data:
        raise StrictParseError("content contains NUL bytes")
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise StrictParseError("content is not valid UTF-8") from None


def _reject_constant(_text: str) -> object:
    raise StrictParseError("NaN and Infinity are not allowed")


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise StrictParseError("duplicate object key")
        result[key] = value
    return result


def _parse_float(text: str) -> Decimal:
    try:
        value = Decimal(text)
    except ArithmeticError:
        raise StrictParseError("number is out of range") from None
    if abs(value.adjusted()) > _MAX_EXPONENT:
        raise StrictParseError("number exponent is out of range")
    return value


def _parse_int(text: str) -> int:
    if len(text.lstrip("-")) > _MAX_INT_DIGITS:
        raise StrictParseError("integer has too many digits")
    return int(text)


def _check_text(text: str) -> None:
    try:
        text.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise StrictParseError("string contains a lone surrogate") from None


def _depth(value: object, limit: int) -> None:
    stack: list[tuple[object, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            _check_text(item)
        elif isinstance(item, dict):
            for key in item:
                _check_text(key)
        if isinstance(item, dict | list):
            if depth > limit:
                raise StrictParseError("nesting exceeds the depth limit")
            children = item.values() if isinstance(item, dict) else item
            stack.extend((child, depth + 1) for child in children)


def _loads(text: str, max_depth: int) -> object:
    # Bound nesting before json recurses: count brackets outside strings cheaply.
    if _max_bracket_depth(text) > max_depth:
        raise StrictParseError("nesting exceeds the depth limit")
    try:
        value = json.loads(
            text,
            parse_float=_parse_float,
            parse_int=_parse_int,
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicates,
        )
    except StrictParseError:
        raise
    except (ValueError, RecursionError):
        raise StrictParseError("content is not valid JSON") from None
    _depth(value, max_depth)
    return value


def _max_bracket_depth(text: str) -> int:
    depth = deepest = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            deepest = max(deepest, depth)
        elif char in "]}":
            depth -= 1
    return deepest


def parse_json(
    data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES, max_depth: int = DEFAULT_MAX_DEPTH
) -> object:
    """Parse one JSON document strictly."""
    return _loads(decode_text(data, max_bytes=max_bytes), max_depth)


def parse_jsonl(
    data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES, max_depth: int = DEFAULT_MAX_DEPTH
) -> list[object]:
    """Parse newline-delimited JSON. Every line, including the last, must be a document."""
    if len(data) > max_bytes:
        raise StrictParseError("content exceeds the size limit")
    return list(iter_jsonl(io.BytesIO(data), max_line_bytes=max_bytes, max_depth=max_depth))


def iter_jsonl(
    stream: IO[bytes],
    *,
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Iterator[object]:
    """Yield one strictly parsed document per newline-terminated line of ``stream``."""
    number = 0
    while True:
        raw = stream.readline(max_line_bytes + 1)
        if not raw:
            return
        number += 1
        if len(raw) > max_line_bytes:
            raise StrictParseError(f"line {number}: exceeds the line size limit")
        if not raw.endswith(b"\n"):
            raise StrictParseError(f"line {number}: final JSONL line is not newline-terminated")
        try:
            line = decode_text(raw[:-1], max_bytes=max_line_bytes)
        except StrictParseError as error:
            raise StrictParseError(f"line {number}: {error}") from None
        if line.endswith("\r"):
            raise StrictParseError(f"line {number}: carriage returns are not allowed")
        if not line.strip():
            raise StrictParseError(f"line {number}: blank line")
        try:
            yield _loads(line, max_depth)
        except StrictParseError as error:
            raise StrictParseError(f"line {number}: {error}") from None


def parse_csv(
    data: bytes, *, required_columns: Sequence[str] = (), max_bytes: int = DEFAULT_MAX_BYTES
) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    """Parse CSV with a unique header and a constant column count. Values stay text."""
    text = decode_text(data, max_bytes=max_bytes)
    if "\r" in text.replace("\r\n", ""):
        raise StrictParseError("CSV contains a bare carriage return")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        rows = [tuple(row) for row in reader]
    except csv.Error as error:
        raise StrictParseError(f"line {reader.line_num}: malformed CSV") from error
    if not rows:
        raise StrictParseError("CSV has no header")
    header = rows[0]
    if any(not name or name != name.strip() for name in header) or len(set(header)) != len(header):
        raise StrictParseError("CSV header has empty, padded, or duplicate column names")
    missing = [name for name in required_columns if name not in header]
    if missing:
        raise StrictParseError(f"CSV header lacks {len(missing)} required column(s)")
    body = rows[1:]
    for number, row in enumerate(body, start=2):
        if len(row) != len(header):
            raise StrictParseError(f"row {number}: expected {len(header)} fields")
    return header, body


def parse_decimal_field(text: str) -> Decimal:
    """Parse a plain decimal such as ``-0.25``. Exponents, NaN, and Infinity are rejected."""
    if not isinstance(text, str) or _DECIMAL_FIELD.fullmatch(text) is None:
        raise StrictParseError("field is not a plain decimal")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise StrictParseError("field is not a plain decimal") from None
    if not value.is_finite():
        raise StrictParseError("field is not finite")
    return value
