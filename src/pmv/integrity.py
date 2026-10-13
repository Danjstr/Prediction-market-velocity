"""Generic integrity primitives shared by raw storage and experiment tracking.

Canonical JSON, canonical UTC timestamps, SHA-256 and exact-decimal validation, and the
low-level hash used by hash-chained ledgers. This module holds no domain schema and no
state rule; each ledger defines and validates its own entries.
"""

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, TypeGuard

_TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.%fZ"
_TIMESTAMP: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_DECIMAL: Final = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?(e[+-]?[0-9]+)?")
_IDENTIFIER: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")
_TIMESTAMP_ID: Final = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z_[0-9a-f]{32}")


class FormatError(Exception):
    """Canonical metadata is malformed. Messages never include the document's content."""


def to_utc(moment: datetime) -> datetime:
    """Return ``moment`` in UTC. Naive datetimes are rejected."""
    if not isinstance(moment, datetime):
        raise TypeError("timestamps must be datetime objects")
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return moment.astimezone(UTC)


def format_timestamp(moment: datetime) -> str:
    """Serialize as ``YYYY-MM-DDTHH:MM:SS.ffffffZ`` in UTC."""
    text = to_utc(moment).strftime(_TIMESTAMP_FORMAT)
    if _TIMESTAMP.fullmatch(text) is None:
        raise ValueError("timestamp is outside the representable range")
    return text


def is_timestamp(value: object) -> TypeGuard[str]:
    """Return whether ``value`` is a canonical PMV UTC timestamp string."""
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return False
    return True


def is_sha256(value: object) -> TypeGuard[str]:
    """Return whether ``value`` is a lowercase 64-character SHA-256 hex string."""
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def is_decimal_text(value: object) -> TypeGuard[str]:
    """Return whether ``value`` is an exact decimal string such as ``-0.25`` or ``1.5e-7``."""
    return isinstance(value, str) and _DECIMAL.fullmatch(value) is not None


def decimal_text(value: Decimal | float) -> str:
    """Return the exact decimal text of a finite Decimal or float.

    A float is written with Python's shortest round-trip representation, so the exact
    binary value it holds is preserved. NaN and infinities are rejected.
    """
    if isinstance(value, bool):
        raise TypeError("booleans are not decimal values")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NaN and infinite values are not allowed")
        text = repr(value)
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("NaN and infinite values are not allowed")
        text = str(value)
    else:
        raise TypeError("decimal values must be Decimal or float")
    text = text.lower()
    if not is_decimal_text(text):
        raise ValueError("value has no exact decimal representation")
    return text


def is_int(value: object) -> TypeGuard[int]:
    """Return whether ``value`` is an integer and not a bool (``True == 1`` in Python)."""
    return type(value) is int


def is_non_negative_int(value: object) -> TypeGuard[int]:
    return type(value) is int and value >= 0


def is_identifier(value: object) -> TypeGuard[str]:
    """Return whether ``value`` is a lowercase symbolic identifier ``[a-z][a-z0-9_]{0,63}``."""
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def is_timestamp_id(value: object) -> TypeGuard[str]:
    """Return whether ``value`` is a ``YYYYMMDDTHHMMSS.ffffffZ_<32 hex>`` identifier."""
    return isinstance(value, str) and _TIMESTAMP_ID.fullmatch(value) is not None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Mapping[str, object]) -> bytes:
    """Encode as canonical ASCII JSON (sorted keys, no spaces). Floats are not allowed."""
    _reject_floats(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def canonical_line(value: Mapping[str, object]) -> bytes:
    """Canonical JSON followed by exactly one newline."""
    return canonical_json(value) + b"\n"


def parse_canonical_json(data: bytes) -> dict[str, object]:
    """Parse a canonical JSON object, rejecting duplicates, floats, and noncanonical bytes."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise FormatError("metadata is not ASCII") from None
    try:
        value = json.loads(
            text,
            object_pairs_hook=_without_duplicates,
            parse_float=_reject_float_text,
            parse_constant=_reject_float_text,
        )
    except (ValueError, RecursionError):
        raise FormatError("metadata is not valid JSON") from None
    if not isinstance(value, dict):
        raise FormatError("metadata is not a JSON object")
    if canonical_json(value) != data:
        raise FormatError("metadata is not canonical JSON")
    return value


def chain_entry_sha256(body: Mapping[str, object]) -> str:
    """SHA-256 of a ledger entry's canonical JSON, computed without its own hash field."""
    return sha256_hex(canonical_json(body))


def _reject_floats(value: object) -> None:
    if isinstance(value, float):
        raise FormatError("floats are not allowed in PMV metadata")
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_floats(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_floats(item)


def _without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FormatError("metadata has duplicate keys")
        result[key] = value
    return result


def _reject_float_text(_text: str) -> object:
    raise FormatError("floats are not allowed in PMV metadata")
