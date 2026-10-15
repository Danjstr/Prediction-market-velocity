"""Canonical observations: structural checks and the receipt-time availability rule."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pmv.market_data.events import (
    BookDelta,
    BookLevel,
    BookSnapshot,
    Outcome,
    ReferenceTick,
    Side,
    StreamEvent,
    StreamEventKind,
    Trade,
    is_observation,
)
from pmv.market_data.labels import OfficialResolution, ResolutionRecord
from pmv.market_data.timing import Provenance, Timing, parse_timestamp
from pmv.protected_scope import Family, Provider
from pmv.raw_format import EventType

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CAPTURE = "20260101T120000.000000Z_" + "0" * 32
KEY = "c" * 64
PROV = Provenance(CAPTURE, 0, 0, "test_parser", 1)


@pytest.mark.parametrize("offset", [timedelta(seconds=-5), timedelta(0), timedelta(seconds=5)])
def test_available_at_is_receipt_time_whatever_the_source_clock_says(offset: timedelta) -> None:
    timing = Timing(T0, T0 + offset)
    assert timing.available_at == T0


def test_timing_refuses_naive_times() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Timing(datetime(2026, 1, 1), None)  # noqa: DTZ001 - testing the refusal
    with pytest.raises(ValueError, match="timezone-aware"):
        Timing(T0, datetime(2026, 1, 1))  # noqa: DTZ001 - testing the refusal


@pytest.mark.parametrize(
    "fields",
    [
        {"capture_id": "not-a-capture"},
        {"frame_sequence": -1},
        {"frame_sequence": True},
        {"item_index": -1},
        {"parser_id": "Bad"},
        {"parser_version": 0},
    ],
)
def test_invalid_provenance_is_refused(fields: dict[str, object]) -> None:
    base: dict[str, object] = {
        "capture_id": CAPTURE,
        "frame_sequence": 0,
        "item_index": 0,
        "parser_id": "p",
        "parser_version": 1,
    }
    base.update(fields)
    with pytest.raises(ValueError):  # noqa: PT011 - each field has its own message
        Provenance(**base)  # type: ignore[arg-type]


def test_timestamps_parse_only_in_canonical_form() -> None:
    assert parse_timestamp("2026-01-01T12:00:00.000000Z") == T0
    for text in (
        "2026-01-01T12:00:00Z",
        "2026-01-01 12:00:00.000000Z",
        "2026-13-01T00:00:00.000000Z",
    ):
        with pytest.raises(ValueError, match="canonical"):
            parse_timestamp(text)


def test_out_of_range_values_are_kept_for_validation_not_rejected() -> None:
    level = BookLevel(-5, 0)
    snapshot = BookSnapshot(KEY, Outcome.YES, (level,), (), None, None, Timing(T0, None), PROV)
    assert snapshot.bids == (level,)


@pytest.mark.parametrize("bad", [True, 1.5, "1", None])
def test_prices_and_quantities_must_be_int(bad: object) -> None:
    with pytest.raises(TypeError):
        BookLevel(bad, 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Trade(KEY, Outcome.YES, bad, 1, None, None, Timing(T0, None), PROV)  # type: ignore[arg-type]


def test_venue_sequence_and_scope_are_set_together() -> None:
    timing = Timing(T0, None)
    with pytest.raises(ValueError, match="together"):
        BookDelta(KEY, Outcome.YES, Side.BID, 50, 1, 7, None, timing, PROV)
    with pytest.raises(ValueError, match="together"):
        BookDelta(KEY, Outcome.YES, Side.BID, 50, 1, None, "book", timing, PROV)
    delta = BookDelta(KEY, Outcome.YES, Side.BID, 50, 1, 7, "book", timing, PROV)
    assert delta.available_at == T0


def test_spec_keys_and_trade_ids_are_checked() -> None:
    timing = Timing(T0, None)
    with pytest.raises(ValueError, match="spec_key"):
        Trade("x", Outcome.YES, 50, 1, None, None, timing, PROV)
    for trade_id in ("", "a\nb", "é", "x" * 129):
        with pytest.raises(ValueError, match="venue_trade_id"):
            Trade(KEY, Outcome.YES, 50, 1, None, trade_id, timing, PROV)


@pytest.mark.parametrize("price", [Decimal("NaN"), Decimal("Infinity")])
def test_reference_prices_must_be_finite(price: Decimal) -> None:
    with pytest.raises(ValueError, match="finite"):
        ReferenceTick(
            Provider.PMV_SYNTHETIC, Family.SYNTHETIC_FIXTURE, price, Timing(T0, None), PROV
        )


def test_stream_event_kinds_mirror_raw_event_types() -> None:
    assert {kind.value for kind in StreamEventKind} == {kind.value for kind in EventType}
    event = StreamEvent(StreamEventKind.GAP, T0, PROV)
    assert event.available_at == T0


def test_resolutions_are_not_observations() -> None:
    record = ResolutionRecord(KEY, OfficialResolution.NO, T0, PROV)
    assert not is_observation(record)
    assert is_observation(StreamEvent(StreamEventKind.GAP, T0, PROV))
