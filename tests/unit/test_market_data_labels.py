"""Labels come from official resolution only and never from information at decision time."""

import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pmv.market_data.contracts import ContractSpec, Underlying, Verification, YesRegion
from pmv.market_data.events import Outcome, TradingStatus, TradingStatusUpdate
from pmv.market_data.labels import (
    Label,
    LabelExclusion,
    LabelPolicy,
    OfficialResolution,
    ResolutionRecord,
    TrainingExample,
    UnverifiedContractSpecError,
    label_for,
    training_example,
)
from pmv.market_data.point_in_time import (
    AsOfView,
    FeatureRow,
    FutureInformationError,
    ObservationLog,
    build_feature_row,
)
from pmv.market_data.timing import Provenance, Timing
from pmv.protected_scope import Provider

OPEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLOSE = OPEN + timedelta(minutes=15)
SETTLED = CLOSE + timedelta(minutes=2)
CAPTURE = "20260101T120000.000000Z_" + "0" * 32

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
DECISION = OPEN + timedelta(minutes=8)
POLICY = LabelPolicy("test_labels_v1", timedelta(seconds=2))
OPEN_STATUS = TradingStatus.OPEN


def resolution(result: OfficialResolution, received: datetime = SETTLED) -> ResolutionRecord:
    return ResolutionRecord(SPEC.spec_key, result, received, Provenance(CAPTURE, 0, 0, "p", 1))


def row(decision: datetime = DECISION, cutoff: datetime | None = None) -> FeatureRow:
    return FeatureRow(
        SPEC.spec_key,
        decision,
        cutoff,
        SPEC.time_remaining(decision),
        SPEC.time_to_reference(decision),
        "test_features_v1",
        {},
    )


def lab(
    record: ResolutionRecord | None,
    moment: datetime = DECISION,
    status: TradingStatus | None = OPEN_STATUS,
    spec: ContractSpec = SPEC,
) -> Label | LabelExclusion:
    return label_for(spec, record, moment, status=status, policy=POLICY)


def view_at(
    decision: datetime = DECISION, statuses: tuple[TradingStatus, ...] = (OPEN_STATUS,)
) -> AsOfView:
    updates = [
        TradingStatusUpdate(
            SPEC.spec_key,
            status,
            Timing(OPEN + timedelta(seconds=index + 1), None),
            Provenance(CAPTURE, index, 0, "p", 1),
        )
        for index, status in enumerate(statuses)
    ]
    return ObservationLog(updates).as_of(decision, min_latency=timedelta(0))


def example(
    record: ResolutionRecord | None, view: AsOfView | None = None
) -> TrainingExample | LabelExclusion:
    view = view_at() if view is None else view
    features = build_feature_row(view, SPEC, "test_features_v1", {})
    return training_example(SPEC, view, features, record, POLICY)


@pytest.mark.parametrize(
    ("result", "outcome"),
    [(OfficialResolution.YES, Outcome.YES), (OfficialResolution.NO, Outcome.NO)],
)
def test_official_results_become_labels(result: OfficialResolution, outcome: Outcome) -> None:
    assert lab(resolution(result)) == Label(SPEC.spec_key, DECISION, outcome, SETTLED)


def test_void_is_excluded_never_coerced() -> None:
    assert lab(resolution(OfficialResolution.VOID)) is LabelExclusion.VOID


def test_a_missing_resolution_is_an_explicit_exclusion() -> None:
    assert lab(None) is LabelExclusion.RESOLUTION_MISSING
    assert example(None) is LabelExclusion.RESOLUTION_MISSING


def test_decisions_outside_the_trading_window_are_excluded() -> None:
    for moment in (OPEN - timedelta(seconds=1), CLOSE):
        assert lab(resolution(OfficialResolution.YES), moment) is (
            LabelExclusion.DECISION_OUTSIDE_TRADING_WINDOW
        )


def test_decisions_within_the_clock_error_of_close_are_excluded() -> None:
    record = resolution(OfficialResolution.YES)
    edge = CLOSE - POLICY.max_clock_error
    assert lab(record, edge) is LabelExclusion.WITHIN_CLOCK_ERROR_OF_CLOSE
    assert lab(record, CLOSE - timedelta(milliseconds=1)) is (
        LabelExclusion.WITHIN_CLOCK_ERROR_OF_CLOSE
    )
    assert isinstance(lab(record, edge - timedelta(microseconds=1)), Label)


@pytest.mark.parametrize(
    "status", [None, TradingStatus.PAUSED, TradingStatus.CLOSED, TradingStatus.UNKNOWN]
)
def test_decisions_not_known_to_be_open_are_excluded(status: TradingStatus | None) -> None:
    assert lab(resolution(OfficialResolution.YES), status=status) is (
        LabelExclusion.NOT_OPEN_AT_DECISION
    )


def test_training_examples_take_the_status_from_the_view() -> None:
    record = resolution(OfficialResolution.YES)
    assert example(record, view_at(statuses=())) is LabelExclusion.NOT_OPEN_AT_DECISION
    halted = view_at(statuses=(TradingStatus.OPEN, TradingStatus.PAUSED))
    assert example(record, halted) is LabelExclusion.NOT_OPEN_AT_DECISION
    resumed = view_at(statuses=(TradingStatus.PAUSED, TradingStatus.OPEN))
    built = example(record, resumed)
    assert isinstance(built, TrainingExample)
    assert built.status_at_decision is TradingStatus.OPEN
    # a halt received after the decision is not visible to it
    later = ObservationLog(
        [
            TradingStatusUpdate(
                SPEC.spec_key,
                TradingStatus.OPEN,
                Timing(OPEN + timedelta(seconds=1), None),
                Provenance(CAPTURE, 0, 0, "p", 1),
            ),
            TradingStatusUpdate(
                SPEC.spec_key,
                TradingStatus.CLOSED,
                Timing(DECISION + timedelta(seconds=1), None),
                Provenance(CAPTURE, 1, 0, "p", 1),
            ),
        ]
    ).as_of(DECISION, min_latency=timedelta(0))
    assert isinstance(example(record, later), TrainingExample)


def test_a_resolution_received_by_the_decision_time_is_excluded() -> None:
    early = resolution(OfficialResolution.YES, received=DECISION)
    assert lab(early) is LabelExclusion.RESOLUTION_AVAILABLE_AT_DECISION


def test_unverified_contracts_cannot_be_labelled() -> None:
    unverified = dataclasses.replace(
        SPEC,
        venue=Provider.KALSHI,
        market_id="PMVTEST-M",
        event_id="PMVTEST-E",
        series_id="PMVTEST",
        underlying=Underlying.BTC,
        verification=Verification.UNVERIFIED,
    )
    record = ResolutionRecord(
        unverified.spec_key, OfficialResolution.YES, SETTLED, Provenance(CAPTURE, 0, 0, "p", 1)
    )
    with pytest.raises(UnverifiedContractSpecError):
        lab(record, spec=unverified)


def test_a_resolution_for_another_contract_is_refused() -> None:
    other = dataclasses.replace(SPEC, market_id="syn-2")
    with pytest.raises(ValueError, match="different contract"):
        lab(resolution(OfficialResolution.YES), spec=other)


def test_label_policies_are_explicit() -> None:
    with pytest.raises(ValueError, match="policy_id"):
        LabelPolicy("Bad Id", timedelta(0))
    with pytest.raises(ValueError, match="max_clock_error"):
        LabelPolicy("labels_v1", timedelta(seconds=-1))
    with pytest.raises(TypeError, match="LabelPolicy"):
        label_for(
            SPEC,
            resolution(OfficialResolution.YES),
            DECISION,
            status=OPEN_STATUS,
            policy=object(),  # type: ignore[arg-type]
        )


def test_training_examples_are_built_from_the_official_resolution() -> None:
    built = example(resolution(OfficialResolution.YES))
    assert isinstance(built, TrainingExample)
    assert built.label.outcome is Outcome.YES
    assert built.policy == POLICY
    assert example(resolution(OfficialResolution.VOID)) is LabelExclusion.VOID
    other = dataclasses.replace(SPEC, market_id="syn-2")
    view = view_at()
    with pytest.raises(ValueError, match="different contracts"):
        training_example(
            other,
            view,
            build_feature_row(view, SPEC, "test_features_v1", {}),
            resolution(OfficialResolution.YES),
            POLICY,
        )


def test_a_feature_row_must_come_from_the_view() -> None:
    view = view_at()
    record = resolution(OfficialResolution.YES)
    with pytest.raises(ValueError, match="not built from this view"):
        training_example(SPEC, view, row(), record, POLICY)  # cutoff differs
    with pytest.raises(TypeError, match="AsOfView"):
        training_example(SPEC, object(), row(), record, POLICY)  # type: ignore[arg-type]


def test_a_hand_built_label_cannot_bypass_the_rules() -> None:
    # Review M5: a Label built directly must match what the resolution determines.
    record = resolution(OfficialResolution.NO)
    forged = Label(SPEC.spec_key, DECISION, Outcome.YES, SETTLED)
    with pytest.raises(ValueError, match="official resolution"):
        TrainingExample(SPEC, POLICY, row(), OPEN_STATUS, record, forged)
    voided = resolution(OfficialResolution.VOID)
    with pytest.raises(ValueError, match="official resolution"):
        TrainingExample(
            SPEC,
            POLICY,
            row(),
            OPEN_STATUS,
            voided,
            Label(SPEC.spec_key, DECISION, Outcome.NO, SETTLED),
        )
    honest = Label(SPEC.spec_key, DECISION, Outcome.NO, SETTLED)
    with pytest.raises(ValueError, match="official resolution"):
        TrainingExample(SPEC, POLICY, row(), TradingStatus.PAUSED, record, honest)
    leaked = Label(SPEC.spec_key, DECISION, Outcome.NO, DECISION)
    with pytest.raises(FutureInformationError, match="outcome"):
        TrainingExample(SPEC, POLICY, row(), OPEN_STATUS, record, leaked)


def test_feature_time_fields_must_match_the_spec() -> None:
    # Review M5 (repro 7): time remaining unrelated to the contract.
    record = resolution(OfficialResolution.YES)
    label = lab(record)
    assert isinstance(label, Label)
    wrong = dataclasses.replace(
        row(), time_remaining=timedelta(days=9), time_to_reference=timedelta(days=9)
    )
    with pytest.raises(ValueError, match="time fields"):
        TrainingExample(SPEC, POLICY, wrong, OPEN_STATUS, record, label)
    with pytest.raises(FutureInformationError):
        TrainingExample(
            SPEC, POLICY, row(cutoff=DECISION + timedelta(seconds=1)), OPEN_STATUS, record, label
        )


def test_a_resolution_received_before_the_reference_time_is_excluded() -> None:
    # Review m5.
    early = resolution(OfficialResolution.YES, received=CLOSE - timedelta(seconds=1))
    assert lab(early) is LabelExclusion.RESOLUTION_BEFORE_REFERENCE_TIME
