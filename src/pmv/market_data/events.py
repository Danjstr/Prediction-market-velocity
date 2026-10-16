"""Canonical normalized observations.

Every observation is something PMV could see at ``available_at`` (its receipt time, see
``timing``). None of them carries an official outcome or settlement result: those are
``labels.ResolutionRecord`` and can never enter an observation log.

Contract prices and quantities are integers in the contract's units
(``ContractSpec.price_units_per_payout`` and ``quantity_units_per_contract``); reference
prices of underlying assets are ``Decimal``. Book prices are for one outcome of a binary
contract (``Outcome``); an adapter maps venue-specific books (for example separate YES and
NO books) explicitly, never by assumption.

``venue_sequence`` is the source's own sequence number, scoped by ``sequence_scope`` within
one capture. Adapters set the scope from the verified venue semantics; validation checks
continuity per ``(capture_id, sequence_scope)``.

Construction checks types and structure only (an observation must be representable).
Economic anomalies such as crossed books or out-of-range prices are flagged by
``validation``, never rejected or repaired here, so malformed market states are preserved.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pmv.integrity import is_identifier, is_int, is_non_negative_int, is_sha256
from pmv.market_data.timing import Provenance, Timing, ensure_utc
from pmv.protected_scope import Family, Provider

__all__ = [
    "RESETS_BOOK_STATE",
    "BookDelta",
    "BookLevel",
    "BookSnapshot",
    "MarketObservation",
    "Observation",
    "Outcome",
    "ReferenceTick",
    "Side",
    "StreamEvent",
    "StreamEventKind",
    "Trade",
    "TradingStatus",
    "TradingStatusUpdate",
    "is_observation",
]


class Outcome(StrEnum):
    YES = "yes"
    NO = "no"


class Side(StrEnum):
    BID = "bid"
    ASK = "ask"


class TradingStatus(StrEnum):
    """Trading state only. Settlement results are outcomes, not observations."""

    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class StreamEventKind(StrEnum):
    """PMV-originated stream events.

    Most mirror raw event types (v1 ``raw_format.EventType``, v3 ``capture_format.EventType``).
    ``frame_rejected`` is emitted by the normalization driver, never by a parser: a payload
    frame was rejected (flagged malformed by the collector, or refused by the parser), so
    whatever it carried is unknown.
    """

    RECONNECT = "reconnect"
    RATE_LIMIT = "rate_limit"
    GAP = "gap"
    DISK_WARNING = "disk_warning"
    DISK_HARD_STOP = "disk_hard_stop"
    SOURCE_CLOCK_REGRESSION = "source_clock_regression"
    LOCAL_CLOCK_REGRESSION = "local_clock_regression"
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    MONOTONIC_REGRESSION = "monotonic_regression"
    FRAME_REJECTED = "frame_rejected"


# After these, messages may have been lost or left uninterpretable without the loss being
# visible in venue sequences, so every book in the capture must be re-established from a
# snapshot and sequence expectations restart. A rejected frame may have been a snapshot or a
# delta for any book, so it breaks them all (B08; Step 11 order-book continuity).
RESETS_BOOK_STATE: Final = frozenset(
    {
        StreamEventKind.RECONNECT,
        StreamEventKind.GAP,
        StreamEventKind.RATE_LIMIT,
        StreamEventKind.DISK_HARD_STOP,
        StreamEventKind.CONNECTION_OPENED,
        StreamEventKind.CONNECTION_CLOSED,
        StreamEventKind.FRAME_REJECTED,
    }
)


def _check_common(spec_key: object, timing: object, provenance: object) -> None:
    if not is_sha256(spec_key):
        raise ValueError("spec_key must be a ContractSpec key")
    if not isinstance(timing, Timing):
        raise TypeError("timing must be a Timing")
    if not isinstance(provenance, Provenance):
        raise TypeError("provenance must be a Provenance")


def _check_sequence(venue_sequence: object, sequence_scope: object) -> None:
    if (venue_sequence is None) != (sequence_scope is None):
        raise ValueError("venue_sequence and sequence_scope are set together or not at all")
    if venue_sequence is not None and not is_non_negative_int(venue_sequence):
        raise ValueError("venue_sequence must be a non-negative int")
    if sequence_scope is not None and not is_identifier(sequence_scope):
        raise ValueError("sequence_scope must be a lowercase identifier")


@dataclass(frozen=True, slots=True)
class BookLevel:
    """One price level. Values are kept as observed; ``validation`` flags bad ones."""

    price: int
    quantity: int

    def __post_init__(self) -> None:
        if not is_int(self.price) or not is_int(self.quantity):
            raise TypeError("book level price and quantity must be int")


@dataclass(frozen=True, slots=True)
class BookSnapshot:
    """A full book for one outcome. Bids best-first (descending), asks best-first.

    ``solicited`` marks a snapshot sent in reply to a PMV command (for example a venue's
    "get snapshot" reply) rather than as the start of a subscription. Such a reply may not
    be sequence-consistent with updates still in flight, so it never establishes or
    recovers a usable book until a recorded test proves otherwise (Red-Team RT-B2-03).
    """

    spec_key: str
    outcome: Outcome
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    venue_sequence: int | None
    sequence_scope: str | None
    timing: Timing
    provenance: Provenance
    solicited: bool = False

    def __post_init__(self) -> None:
        _check_common(self.spec_key, self.timing, self.provenance)
        if not isinstance(self.solicited, bool):
            raise TypeError("solicited must be a bool")
        if not isinstance(self.outcome, Outcome):
            raise TypeError("outcome must be an Outcome")
        for levels in (self.bids, self.asks):
            if not isinstance(levels, tuple) or not all(
                isinstance(level, BookLevel) for level in levels
            ):
                raise TypeError("book sides must be tuples of BookLevel")
        _check_sequence(self.venue_sequence, self.sequence_scope)

    @property
    def available_at(self) -> datetime:
        return self.timing.available_at


@dataclass(frozen=True, slots=True)
class BookDelta:
    """An absolute replacement of one level: ``new_quantity`` 0 removes the level."""

    spec_key: str
    outcome: Outcome
    side: Side
    price: int
    new_quantity: int
    venue_sequence: int | None
    sequence_scope: str | None
    timing: Timing
    provenance: Provenance

    def __post_init__(self) -> None:
        _check_common(self.spec_key, self.timing, self.provenance)
        if not isinstance(self.outcome, Outcome) or not isinstance(self.side, Side):
            raise TypeError("outcome and side must be enums")
        if not is_int(self.price) or not is_int(self.new_quantity):
            raise TypeError("delta price and quantity must be int")
        _check_sequence(self.venue_sequence, self.sequence_scope)

    @property
    def available_at(self) -> datetime:
        return self.timing.available_at


@dataclass(frozen=True, slots=True)
class Trade:
    """A public trade print. ``taker_side`` is None when the source does not state it."""

    spec_key: str
    outcome: Outcome
    price: int
    quantity: int
    taker_side: Side | None
    venue_trade_id: str | None
    timing: Timing
    provenance: Provenance

    def __post_init__(self) -> None:
        _check_common(self.spec_key, self.timing, self.provenance)
        if not isinstance(self.outcome, Outcome):
            raise TypeError("outcome must be an Outcome")
        if self.taker_side is not None and not isinstance(self.taker_side, Side):
            raise TypeError("taker_side must be a Side or None")
        if not is_int(self.price) or not is_int(self.quantity):
            raise TypeError("trade price and quantity must be int")
        if self.venue_trade_id is not None and (
            not isinstance(self.venue_trade_id, str)
            or not 1 <= len(self.venue_trade_id) <= 128
            or not self.venue_trade_id.isascii()
            or not self.venue_trade_id.isprintable()
        ):
            raise ValueError("venue_trade_id must be printable ASCII of 1-128 characters")

    @property
    def available_at(self) -> datetime:
        return self.timing.available_at


@dataclass(frozen=True, slots=True)
class TradingStatusUpdate:
    spec_key: str
    status: TradingStatus
    timing: Timing
    provenance: Provenance

    def __post_init__(self) -> None:
        _check_common(self.spec_key, self.timing, self.provenance)
        if not isinstance(self.status, TradingStatus):
            raise TypeError("status must be a TradingStatus")

    @property
    def available_at(self) -> datetime:
        return self.timing.available_at


@dataclass(frozen=True, slots=True)
class ReferenceTick:
    """A price of an underlying or reference instrument from a catalogued source."""

    provider: Provider
    family: Family
    price: Decimal
    timing: Timing
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.provider, Provider) or not isinstance(self.family, Family):
            raise TypeError("provider and family must be catalogued enums")
        if not isinstance(self.price, Decimal) or not self.price.is_finite():
            raise ValueError("reference price must be a finite Decimal")
        if not isinstance(self.timing, Timing) or not isinstance(self.provenance, Provenance):
            raise TypeError("timing and provenance are required")

    @property
    def available_at(self) -> datetime:
        return self.timing.available_at


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """An operational event PMV recorded in the raw capture (reconnect, gap, ...).

    It is PMV-originated, so it has no source time and no receipt: ``recorded_at`` is the
    raw event frame's ``written_at``, and that is when it became available.
    """

    kind: StreamEventKind
    recorded_at: datetime
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.kind, StreamEventKind):
            raise TypeError("kind must be a StreamEventKind")
        object.__setattr__(self, "recorded_at", ensure_utc(self.recorded_at, "recorded_at"))
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")

    @property
    def available_at(self) -> datetime:
        return self.recorded_at


MarketObservation = BookSnapshot | BookDelta | Trade | TradingStatusUpdate
Observation = MarketObservation | ReferenceTick | StreamEvent
_OBSERVATION_TYPES = (
    BookSnapshot,
    BookDelta,
    Trade,
    TradingStatusUpdate,
    ReferenceTick,
    StreamEvent,
)


def is_observation(value: object) -> bool:
    """Exactly the canonical observation types; outcomes and labels are not observations."""
    return type(value) in _OBSERVATION_TYPES
