"""Deterministic order-book reconstruction from normalized snapshots and deltas.

A book is kept per ``(capture_id, spec_key, outcome)``: a new capture is a new connection,
so books never carry over between captures. Within a capture, observations are applied in
capture order ``(frame_sequence, item_index)``, which is the ordering authority
(``docs/raw_data.md``), never wall-clock order.

Input is an ``ObservationLog`` or an ``AsOfView``, never an arbitrary list: a filtered list
(for example ``AsOfView.for_contract``) would silently drop the stream events and other
scopes' sequence breaks that invalidate a book.

A book is **usable** only when both hold:

- **continuity**: it was established by a snapshot, and nothing since then could have lost
  or corrupted an update. Continuity faults persist until the book's own next snapshot:
  - a stream reset (``events.RESETS_BOOK_STATE``) in the capture;
  - a venue-sequence gap, regression, or duplicate anywhere in the capture. As in
    ``validation``, which books share a sequence scope is unverified venue semantics, so a
    break invalidates every book in the capture. A duplicate is treated more strictly than
    in ``validation`` (a warning there): two messages claiming one sequence number cannot
    both be applied with confidence;
  - an unsequenced snapshot or delta for the book: without a sequence, a lost or rejected
    message cannot be detected, so continuity cannot be shown;
  - a snapshot with unsorted or repeated prices;
  - a delta at a price outside ``(0, price_units_per_payout)``, or one removing a level the
    book does not hold (a sign the book is out of step with the source);
  - an unknown contract.
  A delta that arrives while a book has a continuity fault is not applied.
- **consistency**: the current levels are well formed. Prices are strictly inside
  ``(0, price_units_per_payout)``, quantities are positive, and the best bid is below the
  best ask. An inconsistent book is still maintained, because a later delta can make it
  consistent again, but it is not usable meanwhile.

``usable`` does not mean fresh. ``BookSet.last_seen`` gives the latest availability of any
observation in a capture, and ``BookSet.latest`` requires an explicit maximum silence, so a
capture that died without recording a reset is not preferred over a live one. A quiet
market and a dead feed still look alike within that silence window.

These are conservative project rules, not venue facts. Nothing is repaired or dropped: the
reason a book is not usable is reported as an enumerated ``BookFault``.

``reconstruct_as_of`` takes an ``AsOfView``, so a reconstructed book can only reflect
information observable at the view's decision time. Because a view holds a capture-order
prefix of every capture, the book it yields is exactly the book PMV could have held at that
moment (given the view's ``min_latency``).

Book levels refer to one ``Outcome`` of a binary contract. No YES/NO complement mapping is
assumed, so crossing is checked within one outcome's book only. ``BookDelta`` is an
absolute level replacement; whether a venue's deltas are absolute or relative is verified
before an adapter maps them (``kalshi.REQUIRED_VERIFICATIONS``).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from pmv.market_data.contracts import ContractSpec
from pmv.market_data.events import (
    RESETS_BOOK_STATE,
    BookDelta,
    BookLevel,
    BookSnapshot,
    Observation,
    Outcome,
    Side,
    StreamEvent,
)
from pmv.market_data.point_in_time import AsOfView, ObservationLog, effective_availability
from pmv.market_data.timing import ensure_utc

__all__ = [
    "BookFault",
    "BookKey",
    "BookSet",
    "OrderBook",
    "reconstruct",
    "reconstruct_as_of",
]

_ZERO: Final = timedelta(0)

BookKey = tuple[str, str, Outcome]
"""``(capture_id, spec_key, outcome)``."""


class BookFault(StrEnum):
    """Why a book is not usable."""

    # continuity: persists until the book's next snapshot
    STREAM_RESET = "stream_reset"
    SEQUENCE_GAP = "sequence_gap"
    SEQUENCE_REGRESSION = "sequence_regression"
    DUPLICATE_SEQUENCE = "duplicate_sequence"
    UNSEQUENCED = "unsequenced"
    MALFORMED_SNAPSHOT = "malformed_snapshot"
    DELTA_PRICE_OUT_OF_RANGE = "delta_price_out_of_range"
    ABSENT_LEVEL_REMOVED = "absent_level_removed"
    UNKNOWN_CONTRACT = "unknown_contract"
    # consistency: follows the current levels
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    INVALID_QUANTITY = "invalid_quantity"
    CROSSED_OR_LOCKED = "crossed_or_locked"


@dataclass(frozen=True, slots=True)
class OrderBook:
    """One reconstructed book at one point in its capture.

    ``bids`` are best-first (descending price), ``asks`` best-first (ascending price).
    Times are effective availabilities: ``established_at`` of the snapshot the book was
    last established from, ``updated_at`` of the last change to its levels, and
    ``faulted_at`` of the last change to its continuity faults (None if never). ``faults``
    is empty exactly when the book is usable.
    """

    capture_id: str
    spec_key: str
    outcome: Outcome
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    faults: frozenset[BookFault]
    established_at: datetime
    updated_at: datetime
    faulted_at: datetime | None

    @property
    def key(self) -> BookKey:
        return (self.capture_id, self.spec_key, self.outcome)

    @property
    def usable(self) -> bool:
        return not self.faults

    @property
    def two_sided(self) -> bool:
        """Both sides have at least one level. A usable book may be empty or one-sided."""
        return bool(self.bids) and bool(self.asks)

    @property
    def best_bid(self) -> BookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> BookLevel | None:
        return self.asks[0] if self.asks else None

    def age(self, decision_time: datetime) -> timedelta:
        """Time since the levels last changed; refuses a decision time before that change.

        A quiet market and a dead feed both age; see ``BookSet.last_seen`` for liveness.
        """
        moment = ensure_utc(decision_time, "decision_time")
        if moment < self.updated_at:
            raise ValueError("decision time is before the book's last update")
        return moment - self.updated_at


class BookSet:
    """Books keyed by ``(capture_id, spec_key, outcome)``, with per-capture liveness."""

    __slots__ = ("_books", "_last_seen")

    def __init__(
        self, books: Mapping[BookKey, OrderBook], last_seen: Mapping[str, datetime]
    ) -> None:
        self._books = dict(books)
        self._last_seen = dict(last_seen)

    def __len__(self) -> int:
        return len(self._books)

    def keys(self) -> tuple[BookKey, ...]:
        return tuple(sorted(self._books))

    def get(self, capture_id: str, spec_key: str, outcome: Outcome) -> OrderBook | None:
        return self._books.get((capture_id, spec_key, outcome))

    def last_seen(self, capture_id: str) -> datetime | None:
        """Latest effective availability of any observation in the capture (any type)."""
        return self._last_seen.get(capture_id)

    def latest(
        self,
        spec_key: str,
        outcome: Outcome,
        *,
        decision_time: datetime,
        max_silence: timedelta,
        usable_only: bool = True,
    ) -> OrderBook | None:
        """The most recently updated book for a contract outcome across live captures.

        A capture is live at ``decision_time`` when it delivered any observation within
        ``max_silence`` before it. ``max_silence`` is an explicit assumption with no default.
        Ties are broken by capture ID, deterministically but without any claim about which
        capture saw the market first. With ``usable_only`` (the default), books with faults
        are skipped.
        """
        moment = ensure_utc(decision_time, "decision_time")
        if not isinstance(max_silence, timedelta) or max_silence < _ZERO:
            raise ValueError("max_silence must be a non-negative timedelta")
        if any(seen > moment for seen in self._last_seen.values()):
            raise ValueError("the book set holds observations after the decision time")
        candidates = [
            book
            for (capture_id, key, side), book in self._books.items()
            if key == spec_key
            and side is outcome
            and (book.usable or not usable_only)
            and moment - self._last_seen[capture_id] <= max_silence
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda book: (book.updated_at, book.capture_id))


def reconstruct(source: ObservationLog | AsOfView, specs: Mapping[str, ContractSpec]) -> BookSet:
    """Replay a log or view into books. Each capture is replayed in its own capture order,
    stamped with effective availability."""
    if not isinstance(source, ObservationLog | AsOfView):
        raise TypeError("books are reconstructed from an ObservationLog or AsOfView")
    for key, spec in specs.items():
        if not isinstance(spec, ContractSpec) or spec.spec_key != key:
            raise ValueError("specs must be keyed by their own spec_key")
    paired = effective_availability(source)
    paired.sort(key=lambda pair: pair[1].provenance.position)
    builder = _Builder(specs)
    for effective, item in paired:
        builder.apply(effective, item)
    return BookSet(builder.render_all(), builder.last_seen)


def reconstruct_as_of(view: AsOfView, specs: Mapping[str, ContractSpec]) -> BookSet:
    """Books as PMV could have held them at ``view.decision_time``."""
    if not isinstance(view, AsOfView):
        raise TypeError("books at a decision time are reconstructed from an AsOfView")
    return reconstruct(view, specs)


@dataclass(slots=True)
class _State:
    bids: dict[int, int]
    asks: dict[int, int]
    continuity: set[BookFault]
    established_at: datetime
    updated_at: datetime
    faulted_at: datetime | None


class _Builder:
    def __init__(self, specs: Mapping[str, ContractSpec]) -> None:
        self.specs = specs
        self.states: dict[BookKey, _State] = {}
        # (capture_id, sequence_scope) -> highest venue sequence seen
        self.sequences: dict[tuple[str, str], int] = {}
        self.last_seen: dict[str, datetime] = {}

    def render_all(self) -> dict[BookKey, OrderBook]:
        return {key: self.render(key, state) for key, state in self.states.items()}

    def render(self, key: BookKey, state: _State) -> OrderBook:
        bids = tuple(BookLevel(p, q) for p, q in sorted(state.bids.items(), reverse=True))
        asks = tuple(BookLevel(p, q) for p, q in sorted(state.asks.items()))
        faults = set(state.continuity)
        spec = self.specs.get(key[1])
        if spec is not None:
            faults |= _consistency(bids, asks, spec.price_units_per_payout)
        return OrderBook(
            key[0],
            key[1],
            key[2],
            bids,
            asks,
            frozenset(faults),
            state.established_at,
            state.updated_at,
            state.faulted_at,
        )

    @staticmethod
    def add_fault(state: _State, fault: BookFault, effective: datetime) -> None:
        if fault not in state.continuity:
            state.continuity.add(fault)
            state.faulted_at = effective

    def break_capture(self, capture_id: str, fault: BookFault, effective: datetime) -> None:
        for key, state in self.states.items():
            if key[0] == capture_id:
                self.add_fault(state, fault, effective)

    def apply(self, effective: datetime, item: Observation) -> None:
        capture_id = item.provenance.capture_id
        self.last_seen[capture_id] = effective
        if isinstance(item, StreamEvent):
            if item.kind in RESETS_BOOK_STATE:
                self.break_capture(capture_id, BookFault.STREAM_RESET, effective)
                self.sequences = {
                    key: value for key, value in self.sequences.items() if key[0] != capture_id
                }
            return
        if not isinstance(item, BookSnapshot | BookDelta):
            return
        self.check_sequence(effective, item)
        key: BookKey = (capture_id, item.spec_key, item.outcome)
        spec = self.specs.get(item.spec_key)
        if isinstance(item, BookSnapshot):
            continuity: set[BookFault] = set()
            if spec is None:
                continuity.add(BookFault.UNKNOWN_CONTRACT)
            if item.venue_sequence is None:
                continuity.add(BookFault.UNSEQUENCED)
            if not _levels_ok(item.bids, descending=True) or not _levels_ok(
                item.asks, descending=False
            ):
                continuity.add(BookFault.MALFORMED_SNAPSHOT)
            self.states[key] = _State(
                {level.price: level.quantity for level in item.bids},
                {level.price: level.quantity for level in item.asks},
                continuity,
                effective,
                effective,
                effective if continuity else None,
            )
            return
        state = self.states.get(key)
        if state is None:
            # No snapshot in this capture yet: nothing to apply the delta to. The delta is
            # still in the raw store and flagged by validation as delta_without_snapshot.
            return
        if state.continuity:
            return
        side = state.bids if item.side is Side.BID else state.asks
        if item.venue_sequence is None:
            self.add_fault(state, BookFault.UNSEQUENCED, effective)
        elif spec is not None and not 0 < item.price < spec.price_units_per_payout:
            self.add_fault(state, BookFault.DELTA_PRICE_OUT_OF_RANGE, effective)
        elif item.new_quantity == 0 and item.price not in side:
            self.add_fault(state, BookFault.ABSENT_LEVEL_REMOVED, effective)
        elif item.new_quantity == 0:
            del side[item.price]
            state.updated_at = effective
        else:
            # A negative quantity is kept as observed and makes the book inconsistent.
            side[item.price] = item.new_quantity
            state.updated_at = effective

    def check_sequence(self, effective: datetime, item: BookSnapshot | BookDelta) -> None:
        if item.venue_sequence is None or item.sequence_scope is None:
            return
        capture_id = item.provenance.capture_id
        scope = (capture_id, item.sequence_scope)
        previous = self.sequences.get(scope)
        if previous is not None:
            if item.venue_sequence == previous:
                self.break_capture(capture_id, BookFault.DUPLICATE_SEQUENCE, effective)
            elif item.venue_sequence < previous:
                self.break_capture(capture_id, BookFault.SEQUENCE_REGRESSION, effective)
            elif item.venue_sequence > previous + 1:
                self.break_capture(capture_id, BookFault.SEQUENCE_GAP, effective)
        if previous is None or item.venue_sequence > previous:
            self.sequences[scope] = item.venue_sequence


def _levels_ok(levels: tuple[BookLevel, ...], *, descending: bool) -> bool:
    prices = [level.price for level in levels]
    return len(set(prices)) == len(prices) and prices == sorted(prices, reverse=descending)


def _consistency(
    bids: tuple[BookLevel, ...], asks: tuple[BookLevel, ...], top: int
) -> set[BookFault]:
    faults: set[BookFault] = set()
    levels = bids + asks
    if any(not 0 < level.price < top for level in levels):
        faults.add(BookFault.PRICE_OUT_OF_RANGE)
    if any(level.quantity <= 0 for level in levels):
        faults.add(BookFault.INVALID_QUANTITY)
    if bids and asks and bids[0].price >= asks[0].price:
        faults.add(BookFault.CROSSED_OR_LOCKED)
    return faults
