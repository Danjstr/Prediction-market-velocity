"""A normalizer for PMV's own synthetic fixture messages.

The format is defined here, by PMV, for tests and replay fixtures. It is not, and does not
imitate, any venue's wire format. Every message is one JSON object with a ``type``:

- ``book_snapshot``: ``spec_key``, ``outcome``, ``bids``/``asks`` (lists of
  ``[price, quantity]`` integers), optional ``seq`` with ``scope``, optional ``ts``;
- ``book_delta``: ``spec_key``, ``outcome``, ``side``, ``price``, ``quantity``, optional
  ``seq`` with ``scope``, optional ``ts``;
- ``trade``: ``spec_key``, ``outcome``, ``price``, ``quantity``, optional ``taker_side``,
  optional ``trade_id``, optional ``ts``;
- ``status``: ``spec_key``, ``status``, optional ``ts``;
- ``reference``: ``price`` (decimal string), optional ``ts``; always the catalogued
  ``pmv_synthetic``/``synthetic_fixture`` pair;
- ``resolution``: ``spec_key``, ``result`` (``yes``, ``no``, ``void``);
- ``heartbeat``: skipped.

``ts`` is the synthetic source time (canonical PMV timestamp). Unknown keys, wrong types,
floats, and unknown message types are rejected with an enumerated reason.
"""

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Final

from pmv.integrity import is_decimal_text, is_int, is_timestamp
from pmv.market_data.events import (
    BookDelta,
    BookLevel,
    BookSnapshot,
    Observation,
    Outcome,
    ReferenceTick,
    Side,
    Trade,
    TradingStatus,
    TradingStatusUpdate,
)
from pmv.market_data.labels import OfficialResolution, ResolutionRecord
from pmv.market_data.replay import NormalizeContext, Parsed, PayloadRejectedError, Skipped
from pmv.market_data.timing import Timing, parse_timestamp
from pmv.protected_scope import Family, Provider

__all__ = ["PARSER_ID", "PARSER_VERSION", "SyntheticNormalizer"]

PARSER_ID: Final = "pmv_synthetic_v1"
PARSER_VERSION: Final = 1

_KEYS: Final[Mapping[str, tuple[frozenset[str], frozenset[str]]]] = {
    # type: (required keys, optional keys)
    "book_snapshot": (
        frozenset({"type", "spec_key", "outcome", "bids", "asks"}),
        frozenset({"seq", "scope", "ts"}),
    ),
    "book_delta": (
        frozenset({"type", "spec_key", "outcome", "side", "price", "quantity"}),
        frozenset({"seq", "scope", "ts"}),
    ),
    "trade": (
        frozenset({"type", "spec_key", "outcome", "price", "quantity"}),
        frozenset({"taker_side", "trade_id", "ts"}),
    ),
    "status": (frozenset({"type", "spec_key", "status"}), frozenset({"ts"})),
    "reference": (frozenset({"type", "price"}), frozenset({"ts"})),
    "resolution": (frozenset({"type", "spec_key", "result"}), frozenset()),
    "heartbeat": (frozenset({"type"}), frozenset()),
}


class SyntheticNormalizer:
    """Normalizes the synthetic fixture format above."""

    @property
    def parser_id(self) -> str:
        return PARSER_ID

    @property
    def parser_version(self) -> int:
        return PARSER_VERSION

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped:
        message = _decode(payload)
        kind = message.get("type")
        if not isinstance(kind, str) or kind not in _KEYS:
            raise PayloadRejectedError("unknown_message_type")
        required, optional = _KEYS[kind]
        keys = set(message)
        if not required <= keys or not keys <= required | optional:
            raise PayloadRejectedError("unexpected_fields")
        if kind == "heartbeat":
            return Skipped("heartbeat")
        if kind == "resolution":
            result = _enum(OfficialResolution, message["result"])
            try:
                record = ResolutionRecord(
                    _text(message["spec_key"]), result, context.received_at, context.provenance(0)
                )
            except (TypeError, ValueError) as error:
                raise PayloadRejectedError("invalid_resolution") from error
            return Parsed((record,))
        return Parsed((_observation(kind, message, context),))


def _observation(
    kind: str, message: Mapping[str, object], context: NormalizeContext
) -> Observation:
    source = message.get("ts")
    if source is not None and not is_timestamp(source):
        raise PayloadRejectedError("bad_timestamp")
    timing = Timing(context.received_at, None if source is None else parse_timestamp(source))
    provenance = context.provenance(0)
    try:
        if kind == "reference":
            return ReferenceTick(
                Provider.PMV_SYNTHETIC,
                Family.SYNTHETIC_FIXTURE,
                _decimal(message["price"]),
                timing,
                provenance,
            )
        spec_key = _text(message["spec_key"])
        if kind == "status":
            return TradingStatusUpdate(
                spec_key, _enum(TradingStatus, message["status"]), timing, provenance
            )
        outcome = _enum(Outcome, message["outcome"])
        if kind == "trade":
            taker = message.get("taker_side")
            trade_id = message.get("trade_id")
            if trade_id is not None and not isinstance(trade_id, str):
                raise PayloadRejectedError("bad_field_type")
            return Trade(
                spec_key,
                outcome,
                _int(message["price"]),
                _int(message["quantity"]),
                None if taker is None else _enum(Side, taker),
                trade_id,
                timing,
                provenance,
            )
        sequence, scope = message.get("seq"), message.get("scope")
        if sequence is not None and not is_int(sequence):
            raise PayloadRejectedError("bad_field_type")
        if scope is not None and not isinstance(scope, str):
            raise PayloadRejectedError("bad_field_type")
        if kind == "book_delta":
            return BookDelta(
                spec_key,
                outcome,
                _enum(Side, message["side"]),
                _int(message["price"]),
                _int(message["quantity"]),
                sequence,
                scope,
                timing,
                provenance,
            )
        return BookSnapshot(
            spec_key,
            outcome,
            _levels(message["bids"]),
            _levels(message["asks"]),
            sequence,
            scope,
            timing,
            provenance,
        )
    except (TypeError, ValueError) as error:
        raise PayloadRejectedError("invalid_observation") from error


def _decode(payload: bytes) -> dict[str, object]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_float=_refuse_float,
            parse_constant=_refuse_float,
            object_pairs_hook=_no_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayloadRejectedError("undecodable_payload") from error
    if not isinstance(value, dict):
        raise PayloadRejectedError("not_an_object")
    return value


def _refuse_float(_text: str) -> object:
    raise PayloadRejectedError("float_not_allowed")


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PayloadRejectedError("duplicate_key")
        result[key] = value
    return result


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise PayloadRejectedError("bad_field_type")
    return value


def _int(value: object) -> int:
    if not is_int(value):
        raise PayloadRejectedError("bad_field_type")
    return value


def _decimal(value: object) -> Decimal:
    if not is_decimal_text(value):
        raise PayloadRejectedError("bad_field_type")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise PayloadRejectedError("bad_field_type") from error


def _enum[E: (Outcome, Side, TradingStatus, OfficialResolution)](kind: type[E], value: object) -> E:
    if not isinstance(value, str):
        raise PayloadRejectedError("bad_field_type")
    try:
        return kind(value)
    except ValueError as error:
        raise PayloadRejectedError("bad_enum_value") from error


def _levels(value: object) -> tuple[BookLevel, ...]:
    if not isinstance(value, list):
        raise PayloadRejectedError("bad_field_type")
    levels = []
    for entry in value:
        if not isinstance(entry, list) or len(entry) != 2:
            raise PayloadRejectedError("bad_field_type")
        levels.append(BookLevel(_int(entry[0]), _int(entry[1])))
    return tuple(levels)
