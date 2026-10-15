"""Decision-time views expose only information PMV had received; outcomes never enter them."""

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pmv.market_data.contracts import ContractSpec, Underlying, Verification, YesRegion
from pmv.market_data.events import (
    BookLevel,
    BookSnapshot,
    Observation,
    Outcome,
    ReferenceTick,
    StreamEvent,
    StreamEventKind,
    Trade,
)
from pmv.market_data.labels import Label, OfficialResolution, ResolutionRecord
from pmv.market_data.point_in_time import (
    AsOfView,
    FeatureRow,
    FutureInformationError,
    ObservationLog,
    build_feature_row,
)
from pmv.market_data.timing import Provenance, Timing
from pmv.protected_scope import Family, Provider

OPEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLOSE = OPEN + timedelta(minutes=15)
CAPTURE = "20260101T120000.000000Z_" + "0" * 32
OTHER_CAPTURE = "20260101T120000.000000Z_" + "1" * 32
ZERO = timedelta(0)

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


def at(seconds: float) -> datetime:
    return OPEN + timedelta(seconds=seconds)


def prov(frame: int, item: int = 0, capture: str = CAPTURE) -> Provenance:
    return Provenance(capture, frame, item, "test_parser", 1)


def trade(frame: int, received: float, source: float | None = None) -> Trade:
    timing = Timing(at(received), None if source is None else at(source))
    return Trade(SPEC.spec_key, Outcome.YES, 50, 1, None, None, timing, prov(frame))


def test_the_view_uses_receipt_time_not_source_time() -> None:
    # Stamped by the source well before the decision, but received after it.
    late = trade(0, received=120, source=10)
    log = ObservationLog([late])
    assert len(log.as_of(at(60), min_latency=ZERO)) == 0
    assert len(log.as_of(at(120), min_latency=ZERO)) == 1


def test_receipt_exactly_at_decision_time_is_included_and_latency_excludes_it() -> None:
    log = ObservationLog([trade(0, received=60)])
    assert len(log.as_of(at(60), min_latency=ZERO)) == 1
    assert len(log.as_of(at(60), min_latency=timedelta(microseconds=1))) == 0
    assert len(log.as_of(at(60.5), min_latency=timedelta(milliseconds=500))) == 1


def test_latency_is_required_and_non_negative() -> None:
    log = ObservationLog([])
    with pytest.raises(ValueError, match="min_latency"):
        log.as_of(at(0), min_latency=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="timezone-aware"):
        log.as_of(datetime(2026, 1, 1), min_latency=ZERO)  # noqa: DTZ001 - testing the refusal


def test_outcomes_and_labels_cannot_enter_an_observation_log() -> None:
    resolution = ResolutionRecord(SPEC.spec_key, OfficialResolution.YES, at(900), prov(9))
    label = Label(SPEC.spec_key, at(60), Outcome.YES, at(900))
    for item in (resolution, label, "text", None):
        with pytest.raises(TypeError, match="canonical observations"):
            ObservationLog([trade(0, 1), item])  # type: ignore[list-item]


def test_a_view_refuses_future_items_even_when_built_directly() -> None:
    with pytest.raises(FutureInformationError):
        AsOfView(at(10), ZERO, (trade(0, received=11),))
    with pytest.raises(FutureInformationError):
        AsOfView(at(10), timedelta(seconds=2), (trade(0, received=9),))


def test_duplicate_provenance_positions_are_refused() -> None:
    with pytest.raises(ValueError, match="provenance"):
        ObservationLog([trade(0, 1), trade(0, 2)])


def test_order_is_deterministic_with_capture_tie_breaks() -> None:
    same_time = at(5)
    a = Trade(SPEC.spec_key, Outcome.YES, 50, 1, None, None, Timing(same_time, None), prov(3, 0))
    b = Trade(
        SPEC.spec_key,
        Outcome.YES,
        51,
        1,
        None,
        None,
        Timing(same_time, None),
        prov(0, 0, OTHER_CAPTURE),
    )
    c = StreamEvent(StreamEventKind.RECONNECT, at(1), prov(1))
    orders: list[list[Observation]] = [[a, b, c], [c, b, a], [b, a, c]]
    for order in orders:
        assert list(ObservationLog(order)) == [c, a, b]


def test_views_match_a_brute_force_filter_on_random_logs() -> None:
    rng = random.Random(20261015)  # noqa: S311 - seeded test data, not cryptography
    items = []
    for frame in range(300):
        received = rng.uniform(0, 900)
        source = received - rng.uniform(-1, 5)
        items.append(trade(frame, received, source))
    log = ObservationLog(items)
    for _ in range(200):
        decision = at(rng.uniform(-10, 910))
        latency = timedelta(milliseconds=rng.choice([0, 1, 250, 2000]))
        view = log.as_of(decision, min_latency=latency)
        # Effective availability: running maximum of receipt time in capture order.
        expected = set()
        running = None
        for item in items:
            running = item.available_at if running is None else max(running, item.available_at)
            if running + latency <= decision:
                expected.add(item.provenance.position)
        assert {i.provenance.position for i in view} == expected
        frames = sorted(position[1] for position in expected)
        assert frames == list(range(len(frames)))  # always a capture-order prefix
        cutoff = view.information_cutoff
        assert cutoff is None or cutoff <= decision - latency


def test_feature_rows_carry_time_remaining_and_refuse_future_cutoffs() -> None:
    log = ObservationLog([trade(0, received=100), trade(1, received=500)])
    view = log.as_of(at(480), min_latency=ZERO)
    row = build_feature_row(view, SPEC, "test_features_v1", {"last_price": 0.5})
    assert row.information_cutoff == at(100)
    assert row.time_remaining == timedelta(minutes=7)
    assert row.time_to_reference == timedelta(minutes=7)
    with pytest.raises(TypeError):
        row.values["last_price"] = 1.0  # type: ignore[index]
    with pytest.raises(FutureInformationError):
        FeatureRow(
            SPEC.spec_key,
            at(480),
            at(481),
            timedelta(minutes=7),
            timedelta(minutes=7),
            "test_features_v1",
            {},
        )


@pytest.mark.parametrize(
    "values",
    [
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": 1},
        {"Bad Name": 1.0},
    ],
)
def test_feature_values_must_be_named_finite_floats(values: dict[str, float]) -> None:
    view = ObservationLog([]).as_of(at(60), min_latency=ZERO)
    with pytest.raises(ValueError, match="feature"):
        build_feature_row(view, SPEC, "test_features_v1", values)


def test_feature_rows_outside_the_trading_window_are_refused() -> None:
    view = ObservationLog([]).as_of(CLOSE, min_latency=ZERO)
    with pytest.raises(ValueError, match="trading window"):
        build_feature_row(view, SPEC, "test_features_v1", {})


def test_type_and_contract_filters() -> None:
    tick = ReferenceTick(
        Provider.PMV_SYNTHETIC,
        Family.SYNTHETIC_FIXTURE,
        Decimal("101.5"),
        Timing(at(2), None),
        prov(2),
    )
    snapshot = BookSnapshot(
        SPEC.spec_key,
        Outcome.YES,
        (BookLevel(40, 1),),
        (BookLevel(60, 1),),
        None,
        None,
        Timing(at(3), None),
        prov(3),
    )
    view = ObservationLog([trade(1, 1), tick, snapshot]).as_of(at(10), min_latency=ZERO)
    assert view.of_type(ReferenceTick) == (tick,)
    assert len(view.for_contract(SPEC.spec_key)) == 2


def test_a_view_is_a_capture_order_prefix_across_clock_regressions() -> None:
    # Review M1: a later frame received "earlier" (local clock regression) must not appear
    # before the frames recorded ahead of it, including a stream gap event.
    snapshot = BookSnapshot(
        SPEC.spec_key, Outcome.YES, (), (), None, None, Timing(at(10), None), prov(0)
    )
    gap = StreamEvent(StreamEventKind.GAP, at(20), prov(1))
    log = ObservationLog([snapshot, gap, trade(2, received=19), trade(3, received=5)])
    assert len(log.as_of(at(6), min_latency=ZERO)) == 0
    assert list(log.as_of(at(19.5), min_latency=ZERO)) == [snapshot]
    assert len(log.as_of(at(20), min_latency=ZERO)) == 4


def test_direct_views_validate_latency_and_compute_the_true_cutoff() -> None:
    # Review m1.
    with pytest.raises(ValueError, match="min_latency"):
        AsOfView(at(1), timedelta(seconds=-10), (trade(0, received=5),))
    view = AsOfView(at(10), ZERO, (trade(1, received=9), trade(0, received=1)))
    assert view.information_cutoff == at(9)
    with pytest.raises(FutureInformationError):
        AsOfView(at(10), ZERO, (trade(0, received=11), trade(1, received=2)))
