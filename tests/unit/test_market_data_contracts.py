"""Canonical contract identity: every semantic field is explicit, hashed, and validated."""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pmv.market_data.contracts import (
    ContractSpec,
    ContractSpecError,
    OutsideTradingWindowError,
    Underlying,
    Verification,
    YesRegion,
)
from pmv.market_data.kalshi import normalize_tickers
from pmv.protected_scope import Provider

OPEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLOSE = OPEN + timedelta(minutes=15)
SHA = "a" * 64


def region() -> YesRegion:
    return YesRegion(Decimal("100.5"), False, None, False)


def synthetic(**changes: object) -> ContractSpec:
    spec = ContractSpec(
        venue=Provider.PMV_SYNTHETIC,
        market_id="syn-btc-15m-0001",
        event_id="syn-event-0001",
        series_id=None,
        underlying=Underlying.SYNTHETIC,
        resolution_source_id="synthetic_reference",
        resolution_rule_id="synthetic_rule_v1",
        yes_region=region(),
        open_time=OPEN,
        close_time=CLOSE,
        outcome_reference_time=CLOSE,
        rule_timezone="America/New_York",
        rounding_rule_id="synthetic_no_rounding",
        void_rule_id="synthetic_void_v1",
        fee_schedule_id="synthetic_fees_v1",
        fee_schedule_effective_from=OPEN - timedelta(days=1),
        price_units_per_payout=100,
        quantity_units_per_contract=1,
        verification=Verification.SYNTHETIC,
        rules_source_sha256=None,
    )
    return dataclasses.replace(spec, **changes) if changes else spec  # type: ignore[arg-type]


def kalshi(**changes: object) -> ContractSpec:
    # Synthetic tickers in the documented form only; no real Kalshi contract is described.
    base: dict[str, object] = {
        "venue": Provider.KALSHI,
        "market_id": "PMVTEST-MARKET-1",
        "event_id": "PMVTEST-EVENT",
        "series_id": "PMVTEST",
        "underlying": Underlying.BTC,
        "verification": Verification.UNVERIFIED,
    }
    base.update(changes)
    return synthetic(**base)


def test_a_synthetic_spec_is_valid_and_its_key_is_stable() -> None:
    assert synthetic().spec_key == synthetic().spec_key
    assert len(synthetic().spec_key) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"yes_region": YesRegion(Decimal("100.5"), True, None, False)},
        {"close_time": CLOSE - timedelta(minutes=1)},
        {"outcome_reference_time": CLOSE + timedelta(seconds=1)},
        {"fee_schedule_id": "synthetic_fees_v2"},
        {"fee_schedule_effective_from": OPEN},
        {"void_rule_id": "synthetic_void_v2"},
        {"rounding_rule_id": "synthetic_round_cents"},
        {"resolution_source_id": "synthetic_reference_b"},
        {"rule_timezone": "UTC"},
        {"price_units_per_payout": 1000},
    ],
)
def test_every_semantic_field_is_part_of_the_identity(change: dict[str, object]) -> None:
    assert synthetic(**change).spec_key != synthetic().spec_key


def test_times_are_normalized_to_utc() -> None:
    eastern = timezone(timedelta(hours=-5))
    spec = synthetic(open_time=OPEN.astimezone(eastern))
    assert spec.open_time == OPEN
    assert spec.open_time.tzinfo is UTC
    assert spec.spec_key == synthetic().spec_key


def test_naive_times_are_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        synthetic(open_time=datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001 - testing the refusal


@pytest.mark.parametrize(
    "change",
    [
        {"close_time": OPEN},
        {"outcome_reference_time": CLOSE - timedelta(seconds=1)},
        {"rule_timezone": "Not/AZone"},
        {"price_units_per_payout": 1},
        {"price_units_per_payout": True},
        {"quantity_units_per_contract": 0},
        {"fee_schedule_id": "Bad Id"},
        {"market_id": "UPPER"},
        {"underlying": Underlying.BTC},
        {"verification": Verification.VERIFIED_OFFICIAL, "rules_source_sha256": SHA},
        {"rules_source_sha256": "not-a-hash"},
    ],
)
def test_invalid_synthetic_specs_are_refused(change: dict[str, object]) -> None:
    with pytest.raises(ContractSpecError):
        synthetic(**change)


def test_polymarket_is_deferred() -> None:
    with pytest.raises(ContractSpecError, match="not supported"):
        synthetic(venue=Provider.POLYMARKET)


def test_a_kalshi_spec_requires_normalized_explicit_tickers() -> None:
    assert kalshi().market_id == "PMVTEST-MARKET-1"
    for change in (
        {"market_id": "pmvtest-market-1"},
        {"event_id": None},
        {"series_id": None},
        {"series_id": "has space"},
        {"underlying": Underlying.SYNTHETIC},
    ):
        with pytest.raises(ContractSpecError):
            kalshi(**change)


def test_kalshi_verification_rules() -> None:
    with pytest.raises(ContractSpecError, match="SHA-256"):
        kalshi(verification=Verification.VERIFIED_OFFICIAL)
    with pytest.raises(ContractSpecError, match="synthetic venue"):
        kalshi(verification=Verification.SYNTHETIC)
    verified = kalshi(verification=Verification.VERIFIED_OFFICIAL, rules_source_sha256=SHA)
    assert verified.verification is Verification.VERIFIED_OFFICIAL


def test_kalshi_ticker_normalization_uses_the_guard_rules() -> None:
    assert normalize_tickers("pmvtest-m", "pmvtest-e", "pmvtest") == (
        "PMVTEST-M",
        "PMVTEST-E",
        "PMVTEST",
    )
    assert normalize_tickers("bad ticker", "E", "S") is None
    assert normalize_tickers("M", "E", "Sé") is None


@pytest.mark.parametrize(
    ("lower", "lower_inclusive", "upper", "upper_inclusive"),
    [
        (None, False, None, False),
        (None, True, Decimal(1), False),
        (Decimal(1), False, None, True),
        (Decimal(2), False, Decimal(1), False),
        (Decimal(1), True, Decimal(1), False),
        (Decimal("NaN"), False, None, False),
    ],
)
def test_invalid_yes_regions_are_refused(
    lower: Decimal | None, lower_inclusive: bool, upper: Decimal | None, upper_inclusive: bool
) -> None:
    with pytest.raises(ContractSpecError):
        YesRegion(lower, lower_inclusive, upper, upper_inclusive)


def test_time_remaining_is_first_class_and_bounded_by_the_window() -> None:
    spec = synthetic(outcome_reference_time=CLOSE + timedelta(seconds=30))
    assert spec.window_length == timedelta(minutes=15)
    assert spec.time_remaining(OPEN) == timedelta(minutes=15)
    eight_in = OPEN + timedelta(minutes=8)
    assert spec.time_remaining(eight_in) == timedelta(minutes=7)
    assert spec.time_to_reference(eight_in) == timedelta(minutes=7, seconds=30)
    assert spec.elapsed(eight_in) == timedelta(minutes=8)
    assert spec.time_remaining(CLOSE - timedelta(microseconds=1)) == timedelta(microseconds=1)
    for outside in (OPEN - timedelta(microseconds=1), CLOSE):
        assert not spec.tradable_at(outside)
        with pytest.raises(OutsideTradingWindowError):
            spec.time_remaining(outside)


def test_equal_decimal_thresholds_share_one_identity() -> None:
    # Review m4: 100 and 1E+2 are the same threshold.
    a = synthetic(yes_region=YesRegion(Decimal("100"), False, None, False))
    b = synthetic(yes_region=YesRegion(Decimal("1E+2"), False, None, False))
    c = synthetic(yes_region=YesRegion(Decimal("100.00"), False, None, False))
    assert a.spec_key == b.spec_key == c.spec_key
