"""Order-book reconstruction: delta application, continuity, consistency, point-in-time."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

import pytest

from pmv.market_data.books import BookFault, BookSet, OrderBook, reconstruct, reconstruct_as_of
from pmv.market_data.contracts import ContractSpec, Underlying, Verification, YesRegion
from pmv.market_data.events import (
    RESETS_BOOK_STATE,
    BookDelta,
    BookLevel,
    BookSnapshot,
    Observation,
    Outcome,
    Side,
    StreamEvent,
    StreamEventKind,
    Trade,
)
from pmv.market_data.point_in_time import ObservationLog
from pmv.market_data.timing import Provenance, Timing
from pmv.protected_scope import Provider

OPEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLOSE = OPEN + timedelta(minutes=15)
CAPTURE = "20260101T120000.000000Z_" + "0" * 32
CAPTURE_B = "20260101T120500.000000Z_" + "1" * 32
ZERO = timedelta(0)
AUTO: Final = -1
"""Default sequence argument: the next number in the stream's sequence."""


def make_spec(market_id: str) -> ContractSpec:
    return ContractSpec(
        venue=Provider.PMV_SYNTHETIC,
        market_id=market_id,
        event_id=None,
        series_id=None,
        underlying=Underlying.SYNTHETIC,
        resolution_source_id="synthetic_reference",
        resolution_rule_id="synthetic_rule_v1",
        yes_region=YesRegion(Decimal(100), False, None, False),
        open_time=OPEN,
        close_time=CLOSE,
        outcome_reference_time=CLOSE,
        rule_timezone="UTC",
        rounding_rule_id="synthetic_no_rounding",
        void_rule_id="synthetic_void_v1",
        fee_schedule_id="synthetic_fees_v1",
        fee_schedule_effective_from=OPEN,
        price_units_per_payout=100,
        quantity_units_per_contract=1,
        verification=Verification.SYNTHETIC,
        rules_source_sha256=None,
    )


SPEC = make_spec("syn-1")
OTHER = make_spec("syn-2")
KEY = SPEC.spec_key
SPECS = {KEY: SPEC, OTHER.spec_key: OTHER}


def at(seconds: float) -> datetime:
    return OPEN + timedelta(seconds=seconds)


class Stream:
    """A capture-ordered synthetic stream; each call is the next raw frame."""

    def __init__(self, capture: str = CAPTURE) -> None:
        self.capture = capture
        self.frame = 0
        self.seq = 0
        self.items: list[Observation] = []

    def _next(self) -> Provenance:
        provenance = Provenance(self.capture, self.frame, 0, "test_parser", 1)
        self.frame += 1
        return provenance

    def _seq(self, seq: int | None, scope: str) -> tuple[int | None, str | None]:
        if seq == AUTO:
            self.seq += 1
            return self.seq, scope
        if seq is not None:
            self.seq = max(self.seq, seq)
        return seq, None if seq is None else scope

    def snapshot(
        self,
        received: float,
        seq: int | None = AUTO,
        bids: Sequence[tuple[int, int]] = ((40, 5), (39, 7)),
        asks: Sequence[tuple[int, int]] = ((60, 5), (61, 2)),
        key: str = KEY,
        outcome: Outcome = Outcome.YES,
        scope: str = "book",
    ) -> "Stream":
        sequence, sequence_scope = self._seq(seq, scope)
        self.items.append(
            BookSnapshot(
                key,
                outcome,
                tuple(BookLevel(p, q) for p, q in bids),
                tuple(BookLevel(p, q) for p, q in asks),
                sequence,
                sequence_scope,
                Timing(at(received), None),
                self._next(),
            )
        )
        return self

    def delta(
        self,
        received: float,
        seq: int | None = AUTO,
        side: Side = Side.BID,
        price: int = 45,
        quantity: int = 3,
        key: str = KEY,
        outcome: Outcome = Outcome.YES,
        scope: str = "book",
    ) -> "Stream":
        sequence, sequence_scope = self._seq(seq, scope)
        self.items.append(
            BookDelta(
                key,
                outcome,
                side,
                price,
                quantity,
                sequence,
                sequence_scope,
                Timing(at(received), None),
                self._next(),
            )
        )
        return self

    def trade(self, received: float) -> "Stream":
        self.items.append(
            Trade(KEY, Outcome.YES, 50, 1, None, None, Timing(at(received), None), self._next())
        )
        return self

    def event(self, received: float, kind: StreamEventKind) -> "Stream":
        self.items.append(StreamEvent(kind, at(received), self._next()))
        return self

    def books(self) -> BookSet:
        return reconstruct(ObservationLog(self.items), SPECS)

    def book(self, key: str = KEY, outcome: Outcome = Outcome.YES) -> OrderBook:
        book = self.books().get(self.capture, key, outcome)
        assert book is not None
        return book


def both(*streams: Stream) -> BookSet:
    return reconstruct(ObservationLog(item for s in streams for item in s.items), SPECS)


def prices(levels: tuple[BookLevel, ...]) -> list[tuple[int, int]]:
    return [(level.price, level.quantity) for level in levels]


def test_a_snapshot_establishes_a_usable_book() -> None:
    book = Stream().snapshot(1).book()
    assert book.usable
    assert book.faults == frozenset()
    assert book.two_sided
    assert prices(book.bids) == [(40, 5), (39, 7)]
    assert prices(book.asks) == [(60, 5), (61, 2)]
    assert book.best_bid == BookLevel(40, 5)
    assert book.best_ask == BookLevel(60, 5)
    assert book.established_at == book.updated_at == at(1)
    assert book.faulted_at is None
    assert book.key == (CAPTURE, KEY, Outcome.YES)


def test_deltas_replace_insert_and_remove_levels() -> None:
    book = (
        Stream()
        .snapshot(1)
        .delta(2, price=45, quantity=3)  # insert a new best bid
        .delta(3, price=39, quantity=0)  # remove a level
        .delta(4, side=Side.ASK, price=60, quantity=9)  # replace a level
        .book()
    )
    assert book.usable
    assert prices(book.bids) == [(45, 3), (40, 5)]
    assert prices(book.asks) == [(60, 9), (61, 2)]
    assert book.established_at == at(1)
    assert book.updated_at == at(4)
    assert book.age(at(7)) == timedelta(seconds=3)
    with pytest.raises(ValueError, match="before the book's last update"):
        book.age(at(3))


def test_empty_and_one_sided_books_are_reported() -> None:
    empty = Stream().snapshot(1, bids=(), asks=()).book()
    assert empty.usable
    assert not empty.two_sided
    assert empty.best_bid is None
    assert empty.best_ask is None
    assert not Stream().snapshot(1, asks=()).book().two_sided


def test_a_delta_before_any_snapshot_creates_no_book() -> None:
    books = Stream().delta(1).books()
    assert len(books) == 0
    assert books.get(CAPTURE, KEY, Outcome.YES) is None


def test_books_are_kept_per_outcome_and_contract() -> None:
    stream = (
        Stream()
        .snapshot(1, bids=((30, 1),), asks=((35, 1),), outcome=Outcome.NO)
        .snapshot(2, key=OTHER.spec_key)
        .snapshot(3)
        .delta(4, price=33, quantity=4, outcome=Outcome.NO)
    )
    books = stream.books()
    assert len(books) == 3
    no_book = books.get(CAPTURE, KEY, Outcome.NO)
    assert no_book is not None
    assert prices(no_book.bids) == [(33, 4), (30, 1)]
    yes_book = books.get(CAPTURE, KEY, Outcome.YES)
    assert yes_book is not None
    assert prices(yes_book.bids) == [(40, 5), (39, 7)]


@pytest.mark.parametrize(
    ("sequences", "fault"),
    [
        ((1, 3), BookFault.SEQUENCE_GAP),
        ((2, 1), BookFault.SEQUENCE_REGRESSION),
        ((1, 1), BookFault.DUPLICATE_SEQUENCE),
    ],
)
def test_a_sequence_break_invalidates_every_book_in_the_capture(
    sequences: tuple[int, int], fault: BookFault
) -> None:
    first, second = sequences
    stream = (
        Stream()
        .snapshot(1, seq=100, key=OTHER.spec_key, scope="other")
        .snapshot(2, seq=first)
        .delta(3, seq=second, price=41, quantity=1)
    )
    books = stream.books()
    for key in (KEY, OTHER.spec_key):
        book = books.get(CAPTURE, key, Outcome.YES)
        assert book is not None
        assert book.faults == frozenset({fault})
        assert book.faulted_at == at(3)
    yes = books.get(CAPTURE, KEY, Outcome.YES)
    assert yes is not None
    # the delta that arrived with the break was not applied
    assert prices(yes.bids) == [(40, 5), (39, 7)]
    assert yes.updated_at == at(2)


@pytest.mark.parametrize(
    ("second", "fault"),
    [(5, BookFault.SEQUENCE_GAP), (1, BookFault.SEQUENCE_REGRESSION)],
)
def test_a_break_in_another_scope_invalidates_this_book(second: int, fault: BookFault) -> None:
    stream = (
        Stream()
        .snapshot(1, seq=10)
        .snapshot(2, seq=2, key=OTHER.spec_key, scope="other")
        .snapshot(3, seq=second, key=OTHER.spec_key, scope="other")
    )
    assert stream.book().faults == frozenset({fault})


def test_deltas_are_not_applied_while_broken_and_a_snapshot_restores_only_its_book() -> None:
    stream = (
        Stream()
        .snapshot(1, seq=1, key=OTHER.spec_key)
        .snapshot(2, seq=2)
        .delta(3, seq=5)  # gap
        .delta(4, seq=6, price=44, quantity=2)
    )
    broken = stream.book()
    assert broken.faults == frozenset({BookFault.SEQUENCE_GAP})
    assert prices(broken.bids) == [(40, 5), (39, 7)]
    assert broken.faulted_at == at(3)  # a later delta does not move the fault time
    stream.snapshot(5, seq=7, bids=((20, 1),), asks=((80, 1),)).delta(6, seq=8, price=21)
    books = stream.books()
    restored = books.get(CAPTURE, KEY, Outcome.YES)
    assert restored is not None
    assert restored.usable
    assert restored.faulted_at is None
    assert prices(restored.bids) == [(21, 3), (20, 1)]
    assert restored.established_at == at(5)
    other = books.get(CAPTURE, OTHER.spec_key, Outcome.YES)
    assert other is not None
    assert other.faults == frozenset({BookFault.SEQUENCE_GAP})


def test_a_snapshot_arriving_with_a_gap_is_itself_usable() -> None:
    books = Stream().snapshot(1, seq=1, key=OTHER.spec_key).snapshot(2, seq=4).books()
    yes = books.get(CAPTURE, KEY, Outcome.YES)
    other = books.get(CAPTURE, OTHER.spec_key, Outcome.YES)
    assert yes is not None
    assert yes.usable
    assert other is not None
    assert other.faults == frozenset({BookFault.SEQUENCE_GAP})


def test_a_snapshot_duplicating_a_delta_sequence_restores_only_itself() -> None:
    books = (
        Stream()
        .snapshot(1, seq=1, key=OTHER.spec_key)
        .snapshot(2, seq=2)
        .delta(3, seq=3)
        .snapshot(4, seq=3)
        .books()
    )
    yes = books.get(CAPTURE, KEY, Outcome.YES)
    other = books.get(CAPTURE, OTHER.spec_key, Outcome.YES)
    assert yes is not None
    assert yes.usable
    assert other is not None
    assert other.faults == frozenset({BookFault.DUPLICATE_SEQUENCE})


@pytest.mark.parametrize("kind", sorted(RESETS_BOOK_STATE))
def test_stream_resets_invalidate_and_restart_sequence_expectations(
    kind: StreamEventKind,
) -> None:
    stream = Stream().snapshot(1, seq=10).event(2, kind)
    book = stream.book()
    assert book.faults == frozenset({BookFault.STREAM_RESET})
    assert book.faulted_at == at(2)
    assert book.updated_at == at(1)
    # after a reset the venue may restart its sequence: a lower sequence is not a regression
    stream.snapshot(3, seq=1).delta(4, seq=2)
    assert stream.book().usable


def test_a_reset_before_any_snapshot_does_not_block_the_first_book() -> None:
    assert Stream().event(1, StreamEventKind.RECONNECT).snapshot(2).book().usable


@pytest.mark.parametrize("kind", sorted(set(StreamEventKind) - RESETS_BOOK_STATE))
def test_other_stream_events_leave_books_usable(kind: StreamEventKind) -> None:
    assert Stream().snapshot(1).event(2, kind).delta(3).book().usable


def test_resets_and_breaks_are_scoped_to_their_capture() -> None:
    a = Stream(CAPTURE).snapshot(1)
    b = Stream(CAPTURE_B).snapshot(1).event(2, StreamEventKind.GAP)
    books = both(a, b)
    book_a = books.get(CAPTURE, KEY, Outcome.YES)
    book_b = books.get(CAPTURE_B, KEY, Outcome.YES)
    assert book_a is not None
    assert book_a.usable
    assert book_b is not None
    assert book_b.faults == frozenset({BookFault.STREAM_RESET})
    # a delta in capture B never applies to capture A's book
    b.delta(3)
    assert both(a, b).get(CAPTURE, KEY, Outcome.YES) == book_a


def test_unsequenced_books_are_never_usable() -> None:
    assert Stream().snapshot(1, seq=None).book().faults == frozenset({BookFault.UNSEQUENCED})
    # a lost or rejected message before an unsequenced delta could not be detected
    book = Stream().snapshot(1).delta(2, seq=None).book()
    assert book.faults == frozenset({BookFault.UNSEQUENCED})
    assert prices(book.bids) == [(40, 5), (39, 7)]
    assert book.faulted_at == at(2)


@pytest.mark.parametrize("price", [0, 100])
@pytest.mark.parametrize("quantity", [0, 3])
def test_a_delta_price_out_of_range_breaks_the_book(price: int, quantity: int) -> None:
    book = Stream().snapshot(1).delta(2, price=price, quantity=quantity).book()
    assert book.faults == frozenset({BookFault.DELTA_PRICE_OUT_OF_RANGE})
    assert prices(book.bids) == [(40, 5), (39, 7)]


def test_removing_an_absent_level_breaks_the_book_until_a_snapshot() -> None:
    stream = Stream().snapshot(1).delta(2, side=Side.ASK, price=70, quantity=0)
    assert stream.book().faults == frozenset({BookFault.ABSENT_LEVEL_REMOVED})
    stream.snapshot(3)
    assert stream.book().usable


@pytest.mark.parametrize(
    ("bids", "asks", "fault"),
    [
        (((40, 5), (40, 1)), ((60, 1),), BookFault.MALFORMED_SNAPSHOT),
        (((39, 5), (40, 1)), ((60, 1),), BookFault.MALFORMED_SNAPSHOT),
        (((40, 5),), ((61, 1), (60, 1)), BookFault.MALFORMED_SNAPSHOT),
        (((0, 5),), ((60, 1),), BookFault.PRICE_OUT_OF_RANGE),
        (((40, 5),), ((100, 1),), BookFault.PRICE_OUT_OF_RANGE),
        (((40, 0),), ((60, 1),), BookFault.INVALID_QUANTITY),
        (((60, 5),), ((60, 1),), BookFault.CROSSED_OR_LOCKED),
        (((61, 5),), ((60, 1),), BookFault.CROSSED_OR_LOCKED),
    ],
)
def test_inconsistent_snapshots_are_kept_but_not_usable(
    bids: tuple[tuple[int, int], ...], asks: tuple[tuple[int, int], ...], fault: BookFault
) -> None:
    book = Stream().snapshot(1, bids=bids, asks=asks).book()
    assert fault in book.faults
    assert not book.usable


def test_a_malformed_snapshot_stays_broken_until_the_next_snapshot() -> None:
    stream = Stream().snapshot(1, bids=((40, 5), (40, 1))).delta(2, price=40, quantity=0)
    assert stream.book().faults == frozenset({BookFault.MALFORMED_SNAPSHOT})
    stream.snapshot(3)
    assert stream.book().usable


def test_consistency_faults_follow_the_current_levels() -> None:
    stream = Stream().snapshot(1).delta(2, price=60, quantity=1)  # bid at the ask
    assert stream.book().faults == frozenset({BookFault.CROSSED_OR_LOCKED})
    stream.delta(3, price=60, quantity=0)
    assert stream.book().usable
    stream.delta(4, price=45, quantity=-2)
    assert stream.book().faults == frozenset({BookFault.INVALID_QUANTITY})
    stream.delta(5, price=45, quantity=0)
    assert stream.book().usable


def test_an_unknown_contract_book_is_never_usable() -> None:
    stray = make_spec("syn-unknown")
    stream = Stream().snapshot(1, key=stray.spec_key).delta(2, key=stray.spec_key)
    book = stream.book(key=stray.spec_key)
    assert book.faults == frozenset({BookFault.UNKNOWN_CONTRACT})
    assert prices(book.bids) == [(40, 5), (39, 7)]


def test_trades_do_not_change_books() -> None:
    assert Stream().snapshot(1).trade(2).book() == Stream().snapshot(1).book()


def test_capture_order_governs_application_across_a_clock_regression() -> None:
    # The delta was recorded after the snapshot but stamped earlier by a regressed clock.
    book = Stream().snapshot(5).delta(3, price=45, quantity=3).book()
    assert prices(book.bids)[0] == (45, 3)
    # its effective availability is raised to the snapshot's, never lowered
    assert book.updated_at == at(5)


def test_last_seen_counts_every_observation_kind() -> None:
    books = Stream().snapshot(1).trade(4).event(6, StreamEventKind.DISK_WARNING).books()
    assert books.last_seen(CAPTURE) == at(6)
    assert books.last_seen(CAPTURE_B) is None


def test_latest_prefers_the_most_recent_usable_book_among_live_captures() -> None:
    a = Stream(CAPTURE).snapshot(1, bids=((10, 1),))
    b = Stream(CAPTURE_B).snapshot(2, bids=((20, 1),))
    moment, silence = at(3), timedelta(seconds=5)
    latest = both(a, b).latest(KEY, Outcome.YES, decision_time=moment, max_silence=silence)
    assert latest is not None
    assert latest.capture_id == CAPTURE_B
    b.event(3, StreamEventKind.RECONNECT)
    books = both(a, b)
    usable = books.latest(KEY, Outcome.YES, decision_time=moment, max_silence=silence)
    assert usable is not None
    assert usable.capture_id == CAPTURE
    newest = books.latest(
        KEY, Outcome.YES, decision_time=moment, max_silence=silence, usable_only=False
    )
    assert newest is not None
    assert newest.capture_id == CAPTURE_B
    assert books.latest(KEY, Outcome.NO, decision_time=moment, max_silence=silence) is None


def test_latest_skips_a_capture_that_went_silent() -> None:
    # Capture A updated more recently but then died without recording a reset.
    a = Stream(CAPTURE).snapshot(1).delta(100)
    b = Stream(CAPTURE_B).snapshot(50).trade(300)
    books = both(a, b)
    silence = timedelta(seconds=30)
    latest = books.latest(KEY, Outcome.YES, decision_time=at(301), max_silence=silence)
    assert latest is not None
    assert latest.capture_id == CAPTURE_B
    assert books.latest(KEY, Outcome.YES, decision_time=at(400), max_silence=silence) is None


def test_latest_refuses_bad_arguments() -> None:
    books = Stream().snapshot(5).books()
    with pytest.raises(ValueError, match="after the decision time"):
        books.latest(KEY, Outcome.YES, decision_time=at(4), max_silence=ZERO)
    with pytest.raises(ValueError, match="max_silence"):
        books.latest(KEY, Outcome.YES, decision_time=at(5), max_silence=timedelta(-1))


def test_latest_breaks_ties_by_capture_id() -> None:
    books = both(Stream(CAPTURE_B).snapshot(1), Stream(CAPTURE).snapshot(1))
    latest = books.latest(KEY, Outcome.YES, decision_time=at(1), max_silence=ZERO)
    assert latest is not None
    assert latest.capture_id == max(CAPTURE, CAPTURE_B)


def test_reconstruction_as_of_a_view_ignores_later_observations() -> None:
    stream = Stream().snapshot(1, seq=1).delta(2, seq=2).delta(4, seq=4)  # gap arrives later
    log = ObservationLog(stream.items)
    early = reconstruct_as_of(log.as_of(at(3), min_latency=ZERO), SPECS)
    book = early.get(CAPTURE, KEY, Outcome.YES)
    assert book is not None
    assert book.usable
    assert prices(book.bids)[0] == (45, 3)
    late = reconstruct_as_of(log.as_of(at(4), min_latency=ZERO), SPECS)
    late_book = late.get(CAPTURE, KEY, Outcome.YES)
    assert late_book is not None
    assert late_book.faults == frozenset({BookFault.SEQUENCE_GAP})


def test_min_latency_delays_what_a_book_reflects() -> None:
    log = ObservationLog(Stream().snapshot(1).delta(2).items)
    view = log.as_of(at(2.5), min_latency=timedelta(seconds=1))
    book = reconstruct_as_of(view, SPECS).get(CAPTURE, KEY, Outcome.YES)
    assert book is not None
    assert prices(book.bids)[0] == (40, 5)


def test_every_prefix_view_matches_incremental_reconstruction() -> None:
    stream = (
        Stream()
        .snapshot(1, seq=1)
        .delta(2, seq=2)
        .delta(3, seq=3, side=Side.ASK, price=55, quantity=1)
        .event(4, StreamEventKind.RECONNECT)
        .delta(5, seq=1)
        .snapshot(6, seq=2, bids=((30, 2),))
        .delta(7, seq=3, price=31, quantity=1)
    )
    log = ObservationLog(stream.items)
    for count in range(1, len(stream.items) + 1):
        view = log.as_of(at(count), min_latency=ZERO)
        assert len(view) == count
        incremental = reconstruct(ObservationLog(stream.items[:count]), SPECS)
        assert _same(reconstruct_as_of(view, SPECS), incremental)


def _same(left: BookSet, right: BookSet) -> bool:
    keys = left.keys()
    return keys == right.keys() and all(left.get(*key) == right.get(*key) for key in keys)


def test_filtered_inputs_are_refused() -> None:
    # A list (for example AsOfView.for_contract) can silently lose stream resets.
    stream = Stream().snapshot(1).event(2, StreamEventKind.RECONNECT)
    view = ObservationLog(stream.items).as_of(at(2), min_latency=ZERO)
    with pytest.raises(TypeError, match="ObservationLog or AsOfView"):
        reconstruct(view.for_contract(KEY), SPECS)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="AsOfView"):
        reconstruct_as_of(ObservationLog(stream.items), SPECS)  # type: ignore[arg-type]
    book = reconstruct_as_of(view, SPECS).get(CAPTURE, KEY, Outcome.YES)
    assert book is not None
    assert book.faults == frozenset({BookFault.STREAM_RESET})


def test_specs_must_be_keyed_by_their_own_key() -> None:
    with pytest.raises(ValueError, match="own spec_key"):
        reconstruct(ObservationLog([]), {"0" * 64: SPEC})
