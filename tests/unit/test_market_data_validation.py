"""Deterministic anomaly flags: ordering, duplicates, gaps, staleness, malformed books."""

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pmv.market_data.contracts import ContractSpec, Underlying, Verification, YesRegion
from pmv.market_data.events import (
    BookDelta,
    BookLevel,
    BookSnapshot,
    Observation,
    Outcome,
    ReferenceTick,
    Side,
    StreamEvent,
    StreamEventKind,
    Trade,
    TradingStatus,
    TradingStatusUpdate,
)
from pmv.market_data.timing import Provenance, Timing
from pmv.market_data.validation import (
    SEVERITY,
    Anomaly,
    AnomalyKind,
    Severity,
    ValidationPolicy,
    ValidationReport,
    capture_order,
    validate,
)
from pmv.protected_scope import Family, Provider

OPEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLOSE = OPEN + timedelta(minutes=15)
CAPTURE = "20260101T120000.000000Z_" + "0" * 32
CAPTURE_B = "20260101T120500.000000Z_" + "0" * 32
POLICY = ValidationPolicy(
    max_source_lead=timedelta(milliseconds=500),
    max_receipt_delay=timedelta(seconds=2),
    max_feed_silence=timedelta(seconds=30),
    policy_id="test_validation_v1",
)
SPEC = ContractSpec(
    venue=Provider.PMV_SYNTHETIC,
    market_id="syn-1",
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
KEY = SPEC.spec_key
SPECS = {KEY: SPEC}


class Stream:
    """Builds a capture-ordered synthetic stream; each call is the next raw frame."""

    def __init__(self, capture: str = CAPTURE) -> None:
        self.capture = capture
        self.frame = 0
        self.items: list[Observation] = []

    def _next(self) -> Provenance:
        provenance = Provenance(self.capture, self.frame, 0, "test_parser", 1)
        self.frame += 1
        return provenance

    def timing(self, received: float, source: float | None) -> Timing:
        return Timing(
            OPEN + timedelta(seconds=received),
            None if source is None else OPEN + timedelta(seconds=source),
        )

    def snapshot(
        self,
        received: float,
        seq: int | None = None,
        bids: Sequence[tuple[int, int]] = ((40, 5),),
        asks: Sequence[tuple[int, int]] = ((60, 5),),
        source: float | None = None,
    ) -> "Stream":
        self.items.append(
            BookSnapshot(
                KEY,
                Outcome.YES,
                tuple(BookLevel(p, q) for p, q in bids),
                tuple(BookLevel(p, q) for p, q in asks),
                seq,
                None if seq is None else "book",
                self.timing(received, source),
                self._next(),
            )
        )
        return self

    def delta(
        self, received: float, seq: int | None, price: int = 45, quantity: int = 3
    ) -> "Stream":
        self.items.append(
            BookDelta(
                KEY,
                Outcome.YES,
                Side.BID,
                price,
                quantity,
                seq,
                None if seq is None else "book",
                self.timing(received, None),
                self._next(),
            )
        )
        return self

    def trade(
        self,
        received: float,
        source: float | None = None,
        price: int = 50,
        quantity: int = 1,
        trade_id: str | None = None,
        key: str = KEY,
    ) -> "Stream":
        self.items.append(
            Trade(
                key,
                Outcome.YES,
                price,
                quantity,
                Side.BID,
                trade_id,
                self.timing(received, source),
                self._next(),
            )
        )
        return self

    def tick(self, received: float, price: str, source: float | None = None) -> "Stream":
        self.items.append(
            ReferenceTick(
                Provider.PMV_SYNTHETIC,
                Family.SYNTHETIC_FIXTURE,
                Decimal(price),
                self.timing(received, source),
                self._next(),
            )
        )
        return self

    def event(self, received: float, kind: StreamEventKind) -> "Stream":
        self.items.append(StreamEvent(kind, OPEN + timedelta(seconds=received), self._next()))
        return self

    def status(self, received: float) -> "Stream":
        self.items.append(
            TradingStatusUpdate(KEY, TradingStatus.OPEN, self.timing(received, None), self._next())
        )
        return self

    def report(self) -> ValidationReport:
        return validate(self.items, SPECS, POLICY)


def kinds(report: ValidationReport) -> list[AnomalyKind]:
    return [anomaly.kind for anomaly in report.anomalies]


def test_a_clean_stream_has_no_anomalies() -> None:
    stream = (
        Stream()
        .status(0)
        .snapshot(1, seq=1, source=0.9)
        .delta(2, 2)
        .delta(3, 3, quantity=0)
        .trade(4, source=3.9, trade_id="t1")
        .tick(5, "101.25", source=4.95)
    )
    report = stream.report()
    assert report.anomalies == ()
    assert report.observation_count == 6
    assert not report.has_blocking


def test_every_kind_has_a_severity() -> None:
    assert set(SEVERITY) == set(AnomalyKind)


def test_policy_values_are_explicit_and_non_negative() -> None:
    with pytest.raises(ValueError, match="max_feed_silence"):
        dataclasses.replace(POLICY, max_feed_silence=timedelta(seconds=-1))


def test_input_must_be_in_strict_capture_order() -> None:
    stream = Stream().trade(1).trade(2)
    with pytest.raises(ValueError, match="capture order"):
        validate(list(reversed(stream.items)), SPECS, POLICY)
    with pytest.raises(ValueError, match="capture order"):
        validate([stream.items[0], stream.items[0]], SPECS, POLICY)
    assert capture_order(reversed(stream.items)) == stream.items


def test_nothing_is_dropped_or_changed() -> None:
    stream = Stream().trade(1, price=0).trade(2, price=50)
    before = list(stream.items)
    report = stream.report()
    assert stream.items == before
    assert report.observation_count == 2
    assert kinds(report) == [AnomalyKind.PRICE_OUT_OF_RANGE]


def test_anomalies_carry_positions_and_kinds_only() -> None:
    report = Stream().trade(1, price=101).report()
    assert [field.name for field in dataclasses.fields(Anomaly)] == [
        "kind",
        "severity",
        "index",
        "position",
    ]
    assert report.anomalies[0].position == (CAPTURE, 0, 0)
    assert report.for_index(0) == report.anomalies


def test_unknown_contracts_are_blocking() -> None:
    report = Stream().trade(1, key="d" * 64).report()
    assert kinds(report) == [AnomalyKind.UNKNOWN_CONTRACT]
    assert report.has_blocking


def test_venue_sequence_duplicates_gaps_and_regressions() -> None:
    report = (
        Stream()
        .snapshot(1, seq=10)
        .delta(2, 11)
        .delta(3, 11)  # duplicate
        .delta(4, 13)  # gap
        .delta(5, 12)  # regression
        .report()
    )
    assert kinds(report) == [
        AnomalyKind.DUPLICATE_VENUE_SEQUENCE,
        AnomalyKind.VENUE_SEQUENCE_GAP,
        AnomalyKind.DELTA_WITHOUT_SNAPSHOT,
        AnomalyKind.VENUE_SEQUENCE_REGRESSION,
        AnomalyKind.DELTA_WITHOUT_SNAPSHOT,
    ]


def test_a_gap_invalidates_the_book_until_a_new_snapshot() -> None:
    report = (
        Stream()
        .snapshot(1, seq=1)
        .delta(2, 3)  # gap: book now invalid
        .delta(3, 4)  # still invalid
        .snapshot(4, seq=5)  # re-established
        .delta(5, 6)
        .report()
    )
    assert kinds(report) == [
        AnomalyKind.VENUE_SEQUENCE_GAP,
        AnomalyKind.DELTA_WITHOUT_SNAPSHOT,
        AnomalyKind.DELTA_WITHOUT_SNAPSHOT,
    ]


@pytest.mark.parametrize(
    "kind",
    [
        StreamEventKind.RECONNECT,
        StreamEventKind.GAP,
        StreamEventKind.RATE_LIMIT,
        StreamEventKind.DISK_HARD_STOP,
    ],
)
def test_reconnects_and_stream_gaps_require_a_new_snapshot(kind: StreamEventKind) -> None:
    report = Stream().snapshot(1, seq=1).event(2, kind).delta(3, 2).snapshot(4, seq=3).report()
    assert AnomalyKind.DELTA_WITHOUT_SNAPSHOT in kinds(report)
    assert AnomalyKind.VENUE_SEQUENCE_REGRESSION not in kinds(report)


def test_a_new_capture_has_its_own_sequence_and_book_state() -> None:
    first = Stream().snapshot(1, seq=1)
    second = Stream(CAPTURE_B).delta(2, 2)
    report = validate(first.items + second.items, SPECS, POLICY)
    assert kinds(report) == [AnomalyKind.DELTA_WITHOUT_SNAPSHOT]


def test_delta_without_any_snapshot() -> None:
    assert kinds(Stream().delta(1, None).report()) == [AnomalyKind.DELTA_WITHOUT_SNAPSHOT]


def test_duplicate_trade_ids_are_flagged_across_captures() -> None:
    first = Stream().trade(1, trade_id="t1")
    second = Stream(CAPTURE_B).trade(2, trade_id="t1").trade(3, trade_id="t2")
    report = validate(first.items + second.items, SPECS, POLICY)
    assert kinds(report) == [AnomalyKind.DUPLICATE_TRADE_ID]


def test_receive_clock_regression_is_flagged_not_reordered() -> None:
    report = Stream().trade(5).trade(4).trade(6).report()
    assert kinds(report) == [AnomalyKind.RECEIVE_TIME_REGRESSION]
    assert report.anomalies[0].index == 1


def test_source_clock_checks() -> None:
    report = (
        Stream()
        .trade(10, source=10.6)  # source ahead of receipt beyond tolerance
        .trade(11, source=8.5)  # stale on receipt, and source regression
        .trade(12, source=11.9)
        .report()
    )
    assert kinds(report) == [
        AnomalyKind.SOURCE_TIME_AFTER_RECEIPT,
        AnomalyKind.STALE_ON_RECEIPT,
        AnomalyKind.SOURCE_TIME_REGRESSION,
    ]


def test_tolerances_are_inclusive() -> None:
    assert Stream().trade(10, source=10.5).trade(11, source=10.5).report().anomalies == ()
    assert Stream().trade(12, source=10).report().anomalies == ()


def test_feed_silence() -> None:
    report = Stream().trade(1).trade(31).trade(61.5).report()
    assert kinds(report) == [AnomalyKind.FEED_SILENCE]
    assert report.anomalies[0].index == 2


@pytest.mark.parametrize(
    ("bids", "asks", "expected"),
    [
        (((60, 1),), ((60, 1),), [AnomalyKind.CROSSED_BOOK]),
        (((61, 1),), ((60, 1),), [AnomalyKind.CROSSED_BOOK]),
        (((40, 1), (45, 1)), ((60, 1),), [AnomalyKind.MALFORMED_BOOK]),
        (((40, 1), (40, 2)), ((60, 1),), [AnomalyKind.MALFORMED_BOOK]),
        (((40, 1),), ((70, 1), (60, 1)), [AnomalyKind.MALFORMED_BOOK]),
        (((0, 1),), ((60, 1),), [AnomalyKind.PRICE_OUT_OF_RANGE]),
        (((40, 1),), ((100, 1),), [AnomalyKind.PRICE_OUT_OF_RANGE]),
        (((40, 0),), ((60, 1),), [AnomalyKind.INVALID_QUANTITY]),
        ((), (), []),
    ],
)
def test_book_shape_checks(
    bids: tuple[tuple[int, int], ...],
    asks: tuple[tuple[int, int], ...],
    expected: list[AnomalyKind],
) -> None:
    assert kinds(Stream().snapshot(1, bids=bids, asks=asks).report()) == expected


def test_delta_and_trade_value_checks() -> None:
    report = (
        Stream()
        .snapshot(1)
        .delta(2, None, price=100)
        .delta(3, None, quantity=-1)
        .trade(4, quantity=0)
        .tick(5, "0")
        .report()
    )
    assert kinds(report) == [
        AnomalyKind.PRICE_OUT_OF_RANGE,
        AnomalyKind.INVALID_QUANTITY,
        AnomalyKind.INVALID_QUANTITY,
        AnomalyKind.NON_POSITIVE_REFERENCE_PRICE,
    ]


def test_trades_outside_the_trading_window() -> None:
    stream = Stream().trade(-1).trade(899, source=899.4).trade(901, source=900)
    report = validate(
        stream.items, SPECS, dataclasses.replace(POLICY, max_feed_silence=CLOSE - OPEN)
    )
    assert kinds(report) == [
        AnomalyKind.TRADE_OUTSIDE_TRADING_WINDOW,
        AnomalyKind.TRADE_OUTSIDE_TRADING_WINDOW,
    ]
    assert [a.index for a in report.anomalies] == [0, 2]


@pytest.mark.parametrize(
    ("kind", "expected", "severity"),
    [
        (StreamEventKind.RECONNECT, AnomalyKind.STREAM_RECONNECT, Severity.INFO),
        (StreamEventKind.GAP, AnomalyKind.STREAM_GAP, Severity.BLOCKING),
        (StreamEventKind.RATE_LIMIT, AnomalyKind.STREAM_RATE_LIMIT, Severity.WARNING),
        (
            StreamEventKind.LOCAL_CLOCK_REGRESSION,
            AnomalyKind.STREAM_CLOCK_REGRESSION,
            Severity.WARNING,
        ),
        (StreamEventKind.DISK_HARD_STOP, AnomalyKind.STREAM_HARD_STOP, Severity.BLOCKING),
        (StreamEventKind.DISK_WARNING, AnomalyKind.STREAM_STORAGE_PRESSURE, Severity.WARNING),
    ],
)
def test_stream_events_are_reported(
    kind: StreamEventKind, expected: AnomalyKind, severity: Severity
) -> None:
    report = Stream().event(1, kind).report()
    assert report.anomalies[0].kind is expected
    assert report.anomalies[0].severity is severity


def test_counts() -> None:
    report = Stream().trade(1, price=0).trade(2, price=0).trade(3, quantity=0).report()
    assert report.counts() == {
        AnomalyKind.PRICE_OUT_OF_RANGE: 2,
        AnomalyKind.INVALID_QUANTITY: 1,
    }


def other_spec() -> ContractSpec:
    return dataclasses.replace(SPEC, market_id="syn-2")


def test_a_gap_seen_on_a_snapshot_invalidates_every_book_in_the_capture() -> None:
    # Review M2(a): seq 3 is missing and may have belonged to the other book.
    other = other_spec()
    stream = Stream().snapshot(1, seq=1)
    stream.items.append(
        BookSnapshot(
            other.spec_key,
            Outcome.YES,
            (BookLevel(40, 1),),
            (BookLevel(60, 1),),
            2,
            "book",
            stream.timing(2, None),
            stream._next(),
        )
    )
    stream.snapshot(3, seq=4)
    stream.items.append(
        BookDelta(
            other.spec_key,
            Outcome.YES,
            Side.BID,
            45,
            1,
            5,
            "book",
            stream.timing(4, None),
            stream._next(),
        )
    )
    report = validate(stream.items, {KEY: SPEC, other.spec_key: other}, POLICY)
    assert kinds(report) == [AnomalyKind.VENUE_SEQUENCE_GAP, AnomalyKind.DELTA_WITHOUT_SNAPSHOT]
    assert [a.index for a in report.anomalies] == [2, 3]


def test_feed_silence_is_per_stream_and_ignores_stream_events() -> None:
    # Review M4: contract A is silent while reference ticks keep arriving.
    stream = Stream().snapshot(0)
    for second in range(10, 200, 10):
        stream.tick(second, "100")
    stream.event(195, StreamEventKind.DISK_WARNING)
    stream.trade(200)
    report = stream.report()
    assert AnomalyKind.FEED_SILENCE in kinds(report)
    silent = [a for a in report.anomalies if a.kind is AnomalyKind.FEED_SILENCE]
    assert [a.index for a in silent] == [len(stream.items) - 1]


def test_specs_must_be_keyed_by_their_own_key() -> None:
    # Review m2.
    with pytest.raises(ValueError, match="own spec_key"):
        validate([], {KEY: other_spec()}, POLICY)
