"""Deterministic anomaly detection for normalized observations.

``validate`` inspects observations in capture order and returns a report of anomalies. It
never removes, reorders, or repairs anything (CLAUDE.md "Data": do not silently repair or
drop). Downstream code decides what an anomaly means for a decision; this layer only states
the facts.

Every threshold is explicit in ``ValidationPolicy``; there are no defaults, because what is
"stale" depends on the feed and must be recorded with the experiment that relies on it.

Anomalies carry the observation index, provenance position, and an enumerated kind. They
never carry prices, quantities, identifiers, or other values.

Capture order is ``(capture_id, frame_sequence, item_index)``: the order PMV received and
recorded the data. Sequence and clock checks run per capture, because a new capture starts
a new connection.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from pmv.integrity import is_identifier
from pmv.market_data.contracts import ContractSpec
from pmv.market_data.events import (
    RESETS_BOOK_STATE,
    BookDelta,
    BookLevel,
    BookSnapshot,
    MarketObservation,
    Observation,
    ReferenceTick,
    StreamEvent,
    StreamEventKind,
    Trade,
    is_observation,
)

__all__ = [
    "Anomaly",
    "AnomalyKind",
    "Severity",
    "ValidationPolicy",
    "ValidationReport",
    "capture_order",
    "validate",
]

_ZERO: Final = timedelta(0)


class Severity(StrEnum):
    """``BLOCKING``: the observation or its stream state cannot be trusted as-is.
    ``WARNING``: usable, but a data-quality fact downstream code must see.
    ``INFO``: an operational event worth recording."""

    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class AnomalyKind(StrEnum):
    UNKNOWN_CONTRACT = "unknown_contract"
    DUPLICATE_VENUE_SEQUENCE = "duplicate_venue_sequence"
    VENUE_SEQUENCE_GAP = "venue_sequence_gap"
    VENUE_SEQUENCE_REGRESSION = "venue_sequence_regression"
    DELTA_WITHOUT_SNAPSHOT = "delta_without_snapshot"
    DUPLICATE_TRADE_ID = "duplicate_trade_id"
    RECEIVE_TIME_REGRESSION = "receive_time_regression"
    SOURCE_TIME_REGRESSION = "source_time_regression"
    SOURCE_TIME_AFTER_RECEIPT = "source_time_after_receipt"
    STALE_ON_RECEIPT = "stale_on_receipt"
    FEED_SILENCE = "feed_silence"
    CROSSED_BOOK = "crossed_book"
    MALFORMED_BOOK = "malformed_book"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    INVALID_QUANTITY = "invalid_quantity"
    TRADE_OUTSIDE_TRADING_WINDOW = "trade_outside_trading_window"
    NON_POSITIVE_REFERENCE_PRICE = "non_positive_reference_price"
    STREAM_RECONNECT = "stream_reconnect"
    STREAM_GAP = "stream_gap"
    STREAM_RATE_LIMIT = "stream_rate_limit"
    STREAM_CLOCK_REGRESSION = "stream_clock_regression"
    STREAM_STORAGE_PRESSURE = "stream_storage_pressure"
    STREAM_HARD_STOP = "stream_hard_stop"


SEVERITY: Final[Mapping[AnomalyKind, Severity]] = {
    AnomalyKind.UNKNOWN_CONTRACT: Severity.BLOCKING,
    AnomalyKind.DUPLICATE_VENUE_SEQUENCE: Severity.WARNING,
    AnomalyKind.VENUE_SEQUENCE_GAP: Severity.BLOCKING,
    AnomalyKind.VENUE_SEQUENCE_REGRESSION: Severity.BLOCKING,
    AnomalyKind.DELTA_WITHOUT_SNAPSHOT: Severity.BLOCKING,
    AnomalyKind.DUPLICATE_TRADE_ID: Severity.WARNING,
    AnomalyKind.RECEIVE_TIME_REGRESSION: Severity.BLOCKING,
    AnomalyKind.SOURCE_TIME_REGRESSION: Severity.WARNING,
    AnomalyKind.SOURCE_TIME_AFTER_RECEIPT: Severity.WARNING,
    AnomalyKind.STALE_ON_RECEIPT: Severity.WARNING,
    AnomalyKind.FEED_SILENCE: Severity.WARNING,
    AnomalyKind.CROSSED_BOOK: Severity.BLOCKING,
    AnomalyKind.MALFORMED_BOOK: Severity.BLOCKING,
    AnomalyKind.PRICE_OUT_OF_RANGE: Severity.BLOCKING,
    AnomalyKind.INVALID_QUANTITY: Severity.BLOCKING,
    AnomalyKind.TRADE_OUTSIDE_TRADING_WINDOW: Severity.WARNING,
    AnomalyKind.NON_POSITIVE_REFERENCE_PRICE: Severity.BLOCKING,
    AnomalyKind.STREAM_RECONNECT: Severity.INFO,
    AnomalyKind.STREAM_GAP: Severity.BLOCKING,
    AnomalyKind.STREAM_RATE_LIMIT: Severity.WARNING,
    AnomalyKind.STREAM_CLOCK_REGRESSION: Severity.WARNING,
    AnomalyKind.STREAM_STORAGE_PRESSURE: Severity.WARNING,
    AnomalyKind.STREAM_HARD_STOP: Severity.BLOCKING,
}

_STREAM_KINDS: Final[Mapping[StreamEventKind, AnomalyKind]] = {
    StreamEventKind.RECONNECT: AnomalyKind.STREAM_RECONNECT,
    StreamEventKind.GAP: AnomalyKind.STREAM_GAP,
    StreamEventKind.RATE_LIMIT: AnomalyKind.STREAM_RATE_LIMIT,
    StreamEventKind.SOURCE_CLOCK_REGRESSION: AnomalyKind.STREAM_CLOCK_REGRESSION,
    StreamEventKind.LOCAL_CLOCK_REGRESSION: AnomalyKind.STREAM_CLOCK_REGRESSION,
    StreamEventKind.DISK_WARNING: AnomalyKind.STREAM_STORAGE_PRESSURE,
    StreamEventKind.DISK_HARD_STOP: AnomalyKind.STREAM_HARD_STOP,
}


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Explicit tolerances.

    - ``max_source_lead``: how far ``source_time`` may be after ``received_at`` (clock skew)
      before it is flagged.
    - ``max_receipt_delay``: how far ``received_at`` may trail ``source_time`` before the
      observation is flagged stale on receipt.
    - ``max_feed_silence``: the longest gap between consecutive receipts of one stream (a
      contract, or a reference provider and family) within one capture before the stream
      is flagged silent. PMV-originated stream events are not feed activity. Silence after
      a stream's last receipt is not detected here (no end time is known).
    - ``policy_id``: identifies these tolerances; record it with every experiment.
    """

    max_source_lead: timedelta
    max_receipt_delay: timedelta
    max_feed_silence: timedelta
    policy_id: str

    def __post_init__(self) -> None:
        if not is_identifier(self.policy_id):
            raise ValueError("policy_id must be a lowercase identifier")
        for name in ("max_source_lead", "max_receipt_delay", "max_feed_silence"):
            value = getattr(self, name)
            if not isinstance(value, timedelta) or value < _ZERO:
                raise ValueError(f"{name} must be a non-negative timedelta")


@dataclass(frozen=True, slots=True)
class Anomaly:
    kind: AnomalyKind
    severity: Severity
    index: int
    position: tuple[str, int, int]


@dataclass(frozen=True, slots=True)
class ValidationReport:
    observation_count: int
    anomalies: tuple[Anomaly, ...]

    @property
    def has_blocking(self) -> bool:
        return any(item.severity is Severity.BLOCKING for item in self.anomalies)

    def counts(self) -> dict[AnomalyKind, int]:
        result: dict[AnomalyKind, int] = {}
        for item in self.anomalies:
            result[item.kind] = result.get(item.kind, 0) + 1
        return result

    def for_index(self, index: int) -> tuple[Anomaly, ...]:
        return tuple(item for item in self.anomalies if item.index == index)


def capture_order(observations: Iterable[Observation]) -> list[Observation]:
    """Observations in the order PMV recorded them."""
    return sorted(observations, key=lambda item: item.provenance.position)


def validate(
    observations: Sequence[Observation],
    specs: Mapping[str, ContractSpec],
    policy: ValidationPolicy,
) -> ValidationReport:
    """Flag anomalies in ``observations``, which must be in capture order."""
    if not isinstance(policy, ValidationPolicy):
        raise TypeError("policy must be a ValidationPolicy")
    for key, spec in specs.items():
        if not isinstance(spec, ContractSpec) or spec.spec_key != key:
            raise ValueError("specs must be keyed by their own spec_key")
    for item in observations:
        if not is_observation(item):
            raise TypeError("only canonical observations can be validated")
    positions = [item.provenance.position for item in observations]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise ValueError("observations must be in strict capture order")
    checker = _Checker(specs, policy)
    for index, item in enumerate(observations):
        checker.check(index, item)
    return ValidationReport(len(observations), tuple(checker.anomalies))


class _Checker:
    def __init__(self, specs: Mapping[str, ContractSpec], policy: ValidationPolicy) -> None:
        self.specs = specs
        self.policy = policy
        self.anomalies: list[Anomaly] = []
        # capture_id -> latest received_at seen in capture order
        self.last_received: dict[str, datetime] = {}
        # (capture_id, stream) -> latest received_at of that stream
        self.stream_received: dict[tuple[str, str], datetime] = {}
        # (capture_id, sequence_scope) -> last venue sequence seen
        self.sequences: dict[tuple[str, str], int] = {}
        # (capture_id, spec_key, outcome) books established by a snapshot and not since
        # invalidated by a stream reset or a venue sequence break
        self.books: set[tuple[str, str, str]] = set()
        # (spec_key, venue_trade_id) pairs seen in any capture
        self.trade_ids: set[tuple[str, str]] = set()
        self.source_times: dict[tuple[str, str], datetime] = {}

    def flag(self, kind: AnomalyKind, index: int, item: Observation) -> None:
        self.anomalies.append(Anomaly(kind, SEVERITY[kind], index, item.provenance.position))

    def invalidate_capture(self, capture_id: str) -> None:
        self.books = {book for book in self.books if book[0] != capture_id}

    def check(self, index: int, item: Observation) -> None:
        capture_id = item.provenance.capture_id
        if isinstance(item, StreamEvent):
            self.flag(_STREAM_KINDS[item.kind], index, item)
            if item.kind in RESETS_BOOK_STATE:
                self.invalidate_capture(capture_id)
                self.sequences = {
                    key: value for key, value in self.sequences.items() if key[0] != capture_id
                }
            return
        received = item.timing.received_at
        previous = self.last_received.get(capture_id)
        if previous is not None and received < previous:
            self.flag(AnomalyKind.RECEIVE_TIME_REGRESSION, index, item)
        self.last_received[capture_id] = received if previous is None else max(previous, received)
        stream = _source_stream(item)
        last = self.stream_received.get(stream)
        if last is not None and received - last > self.policy.max_feed_silence:
            self.flag(AnomalyKind.FEED_SILENCE, index, item)
        self.stream_received[stream] = received if last is None else max(last, received)
        self.check_timing(index, item, stream)
        if isinstance(item, ReferenceTick):
            if item.price <= 0:
                self.flag(AnomalyKind.NON_POSITIVE_REFERENCE_PRICE, index, item)
            return
        spec = self.specs.get(item.spec_key)
        if spec is None:
            self.flag(AnomalyKind.UNKNOWN_CONTRACT, index, item)
            return
        if isinstance(item, BookSnapshot):
            self.check_snapshot(index, item, spec)
        elif isinstance(item, BookDelta):
            self.check_delta(index, item, spec)
        elif isinstance(item, Trade):
            self.check_trade(index, item, spec)
        # A TradingStatusUpdate has no checks beyond timing and contract identity.

    def check_timing(
        self, index: int, item: MarketObservation | ReferenceTick, stream: tuple[str, str]
    ) -> None:
        source = item.timing.source_time
        if source is None:
            return
        received = item.timing.received_at
        if source - received > self.policy.max_source_lead:
            self.flag(AnomalyKind.SOURCE_TIME_AFTER_RECEIPT, index, item)
        if received - source > self.policy.max_receipt_delay:
            self.flag(AnomalyKind.STALE_ON_RECEIPT, index, item)
        previous = self.source_times.get(stream)
        if previous is not None and source < previous:
            self.flag(AnomalyKind.SOURCE_TIME_REGRESSION, index, item)
        self.source_times[stream] = source if previous is None else max(previous, source)

    def check_sequence(self, index: int, item: BookSnapshot | BookDelta) -> None:
        """Check venue sequence continuity within ``(capture, scope)``.

        Which books share a scope is venue semantics that is not yet verified, so a gap or
        regression, on a snapshot or a delta, conservatively invalidates every book in the
        capture until each is re-established by its own snapshot.
        """
        if item.venue_sequence is None or item.sequence_scope is None:
            return
        key = (item.provenance.capture_id, item.sequence_scope)
        previous = self.sequences.get(key)
        if previous is not None:
            if item.venue_sequence == previous:
                self.flag(AnomalyKind.DUPLICATE_VENUE_SEQUENCE, index, item)
            elif item.venue_sequence < previous:
                self.flag(AnomalyKind.VENUE_SEQUENCE_REGRESSION, index, item)
                self.invalidate_capture(item.provenance.capture_id)
            elif item.venue_sequence > previous + 1:
                self.flag(AnomalyKind.VENUE_SEQUENCE_GAP, index, item)
                self.invalidate_capture(item.provenance.capture_id)
        if previous is None or item.venue_sequence > previous:
            self.sequences[key] = item.venue_sequence

    def check_snapshot(self, index: int, item: BookSnapshot, spec: ContractSpec) -> None:
        self.check_sequence(index, item)
        top = spec.price_units_per_payout
        if not _levels_ok(item.bids, descending=True) or not _levels_ok(
            item.asks, descending=False
        ):
            self.flag(AnomalyKind.MALFORMED_BOOK, index, item)
        levels = item.bids + item.asks
        if any(not 0 < level.price < top for level in levels):
            self.flag(AnomalyKind.PRICE_OUT_OF_RANGE, index, item)
        if any(level.quantity <= 0 for level in levels):
            self.flag(AnomalyKind.INVALID_QUANTITY, index, item)
        if item.bids and item.asks and item.bids[0].price >= item.asks[0].price:
            self.flag(AnomalyKind.CROSSED_BOOK, index, item)
        self.books.add((item.provenance.capture_id, item.spec_key, item.outcome.value))

    def check_delta(self, index: int, item: BookDelta, spec: ContractSpec) -> None:
        self.check_sequence(index, item)
        if (item.provenance.capture_id, item.spec_key, item.outcome.value) not in self.books:
            self.flag(AnomalyKind.DELTA_WITHOUT_SNAPSHOT, index, item)
        if not 0 < item.price < spec.price_units_per_payout:
            self.flag(AnomalyKind.PRICE_OUT_OF_RANGE, index, item)
        if item.new_quantity < 0:
            self.flag(AnomalyKind.INVALID_QUANTITY, index, item)

    def check_trade(self, index: int, item: Trade, spec: ContractSpec) -> None:
        if not 0 < item.price < spec.price_units_per_payout:
            self.flag(AnomalyKind.PRICE_OUT_OF_RANGE, index, item)
        if item.quantity <= 0:
            self.flag(AnomalyKind.INVALID_QUANTITY, index, item)
        if not spec.tradable_at(item.timing.source_time or item.timing.received_at):
            self.flag(AnomalyKind.TRADE_OUTSIDE_TRADING_WINDOW, index, item)
        if item.venue_trade_id is not None:
            key = (item.spec_key, item.venue_trade_id)
            if key in self.trade_ids:
                self.flag(AnomalyKind.DUPLICATE_TRADE_ID, index, item)
            self.trade_ids.add(key)


def _levels_ok(levels: tuple[BookLevel, ...], *, descending: bool) -> bool:
    prices = [level.price for level in levels]
    if len(set(prices)) != len(prices):
        return False
    return prices == sorted(prices, reverse=descending)


def _source_stream(item: MarketObservation | ReferenceTick) -> tuple[str, str]:
    """The (capture, stream) a market observation belongs to, for silence and clocks."""
    capture_id = item.provenance.capture_id
    if isinstance(item, ReferenceTick):
        return (capture_id, f"{item.provider.value}:{item.family.value}")
    return (capture_id, item.spec_key)
