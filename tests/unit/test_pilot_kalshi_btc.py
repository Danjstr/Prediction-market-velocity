"""B12 Kalshi BTC pilot profiler: deterministic behavior on synthetic fixtures only.

Every value below is invented. No real Kalshi observation is in this file.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from pmv.pilot import kalshi_btc as kb

OPEN = "2030-01-01T00:00:00Z"
CLOSE = "2030-01-01T00:15:00Z"
OPEN_TS = int(datetime(2030, 1, 1, tzinfo=UTC).timestamp())
CLOSE_TS = OPEN_TS + 900
TICKER = "SYNTH-30JAN010015-T1"


def market(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ticker": TICKER,
        "event_ticker": "SYNTH-30JAN010015",
        "status": "finalized",
        "result": "yes",
        "open_time": OPEN,
        "close_time": CLOSE,
        "settlement_ts": "2030-01-01T00:16:00Z",
        "updated_time": "2030-01-01T00:00:00Z",
        "strike_type": "greater_or_equal",
        "floor_strike": "100",
        "expiration_value": "101.5",
        "settlement_value_dollars": "1.0000",
        "is_provisional": False,
    }
    base.update(overrides)
    return base


def candle_row(end: int, bid: str | None, ask: str | None, volume: int = 0) -> dict[str, object]:
    def ohlc(value: str | None) -> dict[str, object]:
        return {"open": value, "high": value, "low": value, "close": value}

    return {
        "end_period_ts": end,
        "yes_bid": ohlc(bid),
        "yes_ask": ohlc(ask),
        "price": {"open": "0.5", "high": "0.5", "low": "0.5", "close": "0.5", "mean": None},
        "volume": volume,
        "open_interest": 10,
    }


def trade_row(
    trade_id: str, when: str, count: str = "1.00", price: str = "0.5000", block: bool = False
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "ticker": TICKER,
        "count_fp": count,
        "yes_price_dollars": price,
        "no_price_dollars": str(Decimal(1) - Decimal(price)),
        "taker_outcome_side": "yes",
        "taker_book_side": "bid",
        "created_time": when,
        "is_block_trade": block,
    }


# ------------------------------------------------------------------ parsing


def test_parse_decimal_refuses_floats_bools_and_junk() -> None:
    assert kb.parse_decimal("0.9700") == Decimal("0.9700")
    assert kb.parse_decimal(3) == Decimal(3)
    assert kb.parse_decimal(0.97) is None
    assert kb.parse_decimal(True) is None
    assert kb.parse_decimal("") is None
    assert kb.parse_decimal("1e3") is None
    assert kb.parse_decimal(None) is None


def test_parse_rfc3339_requires_offset_and_counts_digits() -> None:
    parsed = kb.parse_rfc3339("2030-01-01T00:00:01.123456789Z")
    assert parsed is not None
    assert parsed[1] == 9
    assert parsed[0].microsecond == 123456
    offset = kb.parse_rfc3339("2030-01-01T01:00:00+01:00")
    assert offset is not None
    assert offset[0] == datetime(2030, 1, 1, tzinfo=UTC)
    assert kb.parse_rfc3339("2030-01-01T00:00:00") is None
    assert kb.parse_rfc3339(1_700_000_000) is None


def test_parse_trade_rejects_any_malformed_required_field() -> None:
    good = trade_row("a", "2030-01-01T00:14:30Z")
    assert kb.parse_trade(good) is not None
    for key, bad in (
        ("created_time", "2030-01-01 00:14:30"),
        ("count_fp", 1.0),
        ("yes_price_dollars", None),
        ("is_block_trade", "false"),
        ("taker_outcome_side", "buy"),
    ):
        assert kb.parse_trade({**good, key: bad}) is None, key


def test_parse_candle_accepts_historical_and_live_names() -> None:
    historical = kb.parse_candle(TICKER, candle_row(OPEN_TS + 60, "0.90", "0.92", 3))
    assert historical is not None
    assert historical.yes_ask_close == Decimal("0.92")
    assert historical.volume == Decimal(3)
    live = kb.parse_candle(
        TICKER,
        {
            "end_period_ts": OPEN_TS + 60,
            "yes_ask": {"close_dollars": "0.9100"},
            "volume_fp": "2.00",
        },
    )
    assert live is not None
    assert live.yes_ask_close == Decimal("0.9100")
    assert live.volume == Decimal("2.00")
    assert kb.parse_candle(TICKER, {"end_period_ts": "60"}) is None


# ------------------------------------------------------------------ bands


@pytest.mark.parametrize(
    ("seconds", "band"),
    [
        (0, "post_close"),
        (-5, "post_close"),
        (1, "<=1m"),
        (60, "<=1m"),
        (61, ">1-2m"),
        (120, ">1-2m"),
        (180, ">2-3m"),
        (300, ">3-5m"),
        (301, ">5m"),
    ],
)
def test_time_band_edges(seconds: float, band: str) -> None:
    assert kb.time_band(seconds) == band


@pytest.mark.parametrize(
    ("ask", "band"),
    [
        ("0.84", "<0.85"),
        ("0.85", "0.85-0.89"),
        ("0.8999", "0.85-0.89"),
        ("0.90", "0.90-0.92"),
        ("0.93", "0.93-0.95"),
        ("0.96", "0.96-0.97"),
        ("0.97", "0.96-0.97"),
        ("0.9701", ">0.97"),
    ],
)
def test_ask_band_edges(ask: str, band: str) -> None:
    assert kb.ask_band(Decimal(ask)) == band


# ------------------------------------------------------------------ profiles


def test_field_profile_reports_types_not_values() -> None:
    rows: list[dict[str, object]] = [
        {"a": "0.10", "t": "2030-01-01T00:00:00.5Z", "n": None, "o": {"x": 1}},
        {"a": 3},
    ]
    profile = kb.field_profile(rows)
    assert profile["a"]["types"] == {"int": 1, "str:numeric": 1}
    assert profile["a"]["numeric_string_decimals"] == {"2": 1}
    assert profile["t"]["timestamp_fraction_digits"] == {"1": 1}
    assert profile["n"]["absent"] == 1
    assert profile["o.x"]["types"] == {"int": 1}
    assert "0.10" not in json.dumps(profile)


def test_order_and_duplicates() -> None:
    result = kb.order_and_duplicates(["a", "b", "b"], [3.0, 2.0, 2.0])
    assert result["order_by_time"] == "descending"
    assert result["duplicate_ids"] == 1
    assert result["equal_adjacent_times"] == 1
    assert kb.order_and_duplicates(["a", "b"], [1.0, None])["unparsed_times"] == 1


def test_label_integrity_detects_conflicts() -> None:
    markets = [
        market(),
        market(ticker="B", result="no", settlement_value_dollars="1.0000"),
        market(ticker="C", strike_type="custom"),
        market(ticker="D", updated_time="2030-01-01T00:20:00Z", is_provisional=True),
    ]
    checks = kb.label_integrity(markets)["checks"]
    assert isinstance(checks, dict)
    assert checks["settlement_value_consistent"] == 3
    assert checks["settlement_value_conflict"] == 1
    assert checks["strike_rederivation_agrees"] == 2
    assert checks["strike_rederivation_disagrees"] == 1  # B: value >= strike but result no
    assert checks["strike_rederivation_not_checkable"] == 1
    assert checks["metadata_updated_after_close"] == 1
    assert checks["is_provisional"] == 1


def test_candle_coverage_counts_missing_and_final_minute() -> None:
    window = kb.MarketWindow(TICKER, OPEN_TS, CLOSE_TS)
    bars = [
        kb.parse_candle(TICKER, candle_row(OPEN_TS + 60 * i, "0.90", "0.92"))
        for i in range(1, 14)  # minutes 14 and 15 missing
    ]
    coverage = kb.candle_coverage(window, [b for b in bars if b is not None])
    assert coverage["expected_minutes"] == 15
    assert coverage["missing_minutes"] == 2
    assert coverage["final_minute_present"] is False
    assert coverage["unchanged_quote_no_volume"] == 12
    assert coverage["ask_close"] == {"usable": 13}


def test_late_window_table_bands_sides_and_contracts() -> None:
    window = kb.MarketWindow(TICKER, OPEN_TS, CLOSE_TS)
    rows = [
        candle_row(CLOSE_TS - 60, "0.95", "0.97", 2),  # remaining 60 -> <=1m
        candle_row(CLOSE_TS, None, "1.00"),  # remaining 0 -> post_close; sentinel ask
    ]
    bars = [b for b in (kb.parse_candle(TICKER, r) for r in rows) if b is not None]
    trades = [kb.parse_trade(trade_row("t1", "2030-01-01T00:13:30Z"))]
    table = kb.late_window_table(
        {TICKER: window}, {TICKER: bars}, {TICKER: [t for t in trades if t is not None]}
    )
    by_key = {(r["side"], r["time_band"], r["ask_band"]): r for r in table}
    yes = by_key[("yes", "<=1m", "0.96-0.97")]
    assert yes["contracts"] == 1
    assert yes["settlement_instants"] == 1
    assert yes["trades"] == 1
    assert yes["spread_quantiles"] == {k: "0.02" for k in ("min", "p10", "p50", "p90", "max")}
    assert by_key[("no", "<=1m", "<0.85")]["rows"] == 1  # NO ask = 1 - 0.95
    assert by_key[("yes", "post_close", "no_usable_ask")]["rows"] == 1
    assert by_key[("no", "post_close", "no_usable_ask")]["rows"] == 1


def test_trade_activity_last_trade_and_inactive_minutes() -> None:
    window = kb.MarketWindow(TICKER, OPEN_TS, CLOSE_TS)
    trades = [
        kb.parse_trade(trade_row("a", "2030-01-01T00:14:50Z")),
        kb.parse_trade(trade_row("b", "2030-01-01T00:01:00Z", block=True)),
    ]
    activity = kb.trade_activity({TICKER: window}, {TICKER: [t for t in trades if t]})
    assert activity["block_trades"] == 1
    assert activity["seconds_last_trade_before_close"] == {
        k: "10" for k in ("min", "p10", "p50", "p90", "max")
    }
    assert activity["trades_by_time_band"] == {
        "post_close": 0,
        "<=1m": 1,
        ">1-2m": 0,
        ">2-3m": 0,
        ">3-5m": 0,
        ">5m": 1,
    }
    assert activity["inactive_minute_fraction"] == round(13 / 15, 4)


# ------------------------------------------------------------------ reconciliation


def test_reconcile_finds_the_matching_convention_and_excludes_blocks() -> None:
    end = OPEN_TS + 120
    bar = kb.parse_candle(
        TICKER,
        {
            **candle_row(end, "0.4", "0.6", 3),
            "price": {"open": "0.40", "high": "0.60", "low": "0.40", "close": "0.60"},
        },
    )
    assert bar is not None
    trades = [
        kb.parse_trade(trade_row("a", "2030-01-01T00:01:10Z", "1.00", "0.4000")),
        kb.parse_trade(trade_row("b", "2030-01-01T00:02:00Z", "2.00", "0.6000")),  # on the edge
        kb.parse_trade(trade_row("c", "2030-01-01T00:01:30Z", "5.00", "0.5000", block=True)),
    ]
    parsed = [t for t in trades if t is not None]
    no_block = kb.reconcile({TICKER: [bar]}, {TICKER: parsed}, include_block=False)
    best = {(r["convention"], r["offset_seconds"]): r for r in no_block}
    inclusive = best[("end_inclusive", 0)]
    assert inclusive["volume_exact"] == 1
    assert inclusive["price_close_exact"] == 1
    assert inclusive["price_open_exact"] == 1
    assert inclusive["relative_volume_error"] == "0.000000"
    exclusive = best[("end_exclusive", 0)]
    assert exclusive["volume_mismatch"] == 1  # the edge trade falls in the next bar
    assert exclusive["trade_minutes_without_candle"] == 1
    with_block = kb.reconcile({TICKER: [bar]}, {TICKER: parsed}, include_block=True)
    assert {(r["convention"], r["offset_seconds"]): r for r in with_block}[("end_inclusive", 0)][
        "volume_mismatch"
    ] == 1


# ------------------------------------------------------------------ loader and report


def write_pilot(root: Path) -> None:
    folder = root / "markets" / TICKER
    folder.mkdir(parents=True)
    (folder / "market.json").write_text(json.dumps({"market": market()}))
    (folder / "candles.json").write_text(
        json.dumps(
            {
                "ticker": TICKER,
                "candlesticks": [
                    candle_row(OPEN_TS + 60 * i, "0.90", "0.94", 1) for i in range(1, 16)
                ],
            }
        )
    )
    (folder / "trades_p00.json").write_text(
        json.dumps(
            {
                "trades": [
                    trade_row("b", "2030-01-01T00:14:30Z"),
                    trade_row("a", "2030-01-01T00:10:30Z"),
                ],
                "cursor": "",
            }
        )
    )


def test_build_report_end_to_end(tmp_path: Path) -> None:
    write_pilot(tmp_path)
    report = kb.build_report(kb.load_pilot(tmp_path))
    assert report["markets"] == 1
    assert report["rows"] == {"candles": 15, "trades": 2}
    assert report["malformed"] == {"candles": 0, "trades": 0}
    assert report["trade_pagination"] == {TICKER: [{"rows": 2, "cursor": "empty"}]}
    ordering = report["trade_ordering"]
    assert isinstance(ordering, dict)
    assert ordering[TICKER]["order_by_time"] == "descending"
    coverage = report["candle_coverage"]
    assert isinstance(coverage, dict)
    assert coverage[TICKER]["missing_minutes"] == 0
    assert coverage[TICKER]["final_minute_present"] is True
    json.dumps(report)  # serializable


def test_main_reports_structural_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert kb.main([str(tmp_path)]) == 2
    assert "no markets/ directory" in capsys.readouterr().err
    folder = tmp_path / "markets" / "X"
    folder.mkdir(parents=True)
    (folder / "market.json").write_text("[]")
    assert kb.main([str(tmp_path)]) == 2


def test_main_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_pilot(tmp_path)
    assert kb.main([str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["report"] == "b12_kalshi_btc_pilot_profile"


# ------------------------------------------------------------------ PMV 2.0 (P10-P16, C1)


def bar(
    end: int,
    bid: str | None,
    ask: str | None,
    volume: int = 0,
    *,
    bid_high: str | None = None,
    ask_low: str | None = None,
) -> kb.Candle:
    row: dict[str, object] = {
        "end_period_ts": end,
        "yes_bid": {"open": bid, "high": bid_high or bid, "low": bid, "close": bid},
        "yes_ask": {"open": ask, "high": ask, "low": ask_low or ask, "close": ask},
        "price": {"open": None, "high": None, "low": None, "close": None},
        "volume": volume,
        "open_interest": 0,
    }
    parsed = kb.parse_candle(TICKER, row)
    assert parsed is not None
    return parsed


def window(ticker: str = TICKER, open_ts: int = OPEN_TS) -> kb.MarketWindow:
    return kb.MarketWindow(ticker, open_ts, open_ts + 900)


def test_parse_trade_accepts_absent_taker_side_but_not_invalid() -> None:
    row = trade_row("a", "2030-01-01T00:14:30Z")
    del row["taker_outcome_side"]
    parsed = kb.parse_trade(row)
    assert parsed is not None
    assert parsed.taker_outcome_side is None
    assert kb.parse_trade({**row, "taker_outcome_side": None}) is not None
    assert kb.parse_trade({**row, "taker_outcome_side": "buy"}) is None


@pytest.mark.parametrize(
    ("seconds", "band"),
    [
        (0, "post_close"),
        (60, "<=1m"),
        (300, ">3-5m"),
        (301, ">5-10m"),
        (600, ">5-10m"),
        (601, ">10m"),
    ],
)
def test_full_time_band_edges(seconds: float, band: str) -> None:
    assert kb.full_time_band(seconds) == band


@pytest.mark.parametrize(
    ("price", "band"),
    [
        ("0.0999", "<0.10"),
        ("0.10", "0.10-0.29"),
        ("0.30", "0.30-0.69"),
        ("0.70", "0.70-0.89"),
        ("0.90", "0.90-0.96"),
        ("0.9699", "0.90-0.96"),
        ("0.97", ">=0.97"),
    ],
)
def test_price_band_edges(price: str, band: str) -> None:
    assert kb.price_band(Decimal(price)) == band


def test_fee_scenarios_are_parsed_strictly() -> None:
    scenario = kb.parse_fee_scenario("s1=0.07")
    assert scenario.fee(Decimal("0.5")) == Decimal("0.0175")
    assert kb.SPREAD_ONLY.fee(Decimal("0.5")) == 0
    for bad in ("s1", "S1=0.07", "s1=0.07.1", "s1=1.5", "s1=-0.1", "=0.1", "s1=0.07e0"):
        with pytest.raises(ValueError, match="fee"):
            kb.parse_fee_scenario(bad)


def test_spread_table_counts_states_and_bands() -> None:
    bars = [
        bar(CLOSE_TS - 60, "0.48", "0.50"),  # <=1m, mid 0.49
        bar(CLOSE_TS - 120, "0.50", "0.50"),  # locked
        bar(CLOSE_TS - 180, None, "0.50"),  # one-sided
        bar(CLOSE_TS - 660, "0.95", "0.98"),  # >10m, mid 0.965
    ]
    result: Any = kb.spread_table({TICKER: window()}, {TICKER: bars})
    assert result["quote_states"] == {
        "crossed_or_locked": 1,
        "one_sided_or_empty": 1,
        "two_sided": 2,
    }
    cells = {(c["time_band"], c["mid_band"]): c for c in result["cells"]}
    near = cells[("<=1m", "0.30-0.69")]
    assert near["rows"] == 1
    assert near["rows_spread_le_0.02"] == 1
    assert near["rows_spread_le_0.01"] == 0
    assert cells[(">10m", "0.90-0.96")]["spread_quantiles"]["p50"] == "0.03"


def test_quote_staleness_unchanged_and_zero_range() -> None:
    bars = [
        bar(CLOSE_TS - 180, "0.40", "0.42"),
        bar(CLOSE_TS - 120, "0.40", "0.42"),  # unchanged, no volume, flat range
        bar(CLOSE_TS - 60, "0.40", "0.42", 5, bid_high="0.41"),  # unchanged close, traded
        bar(CLOSE_TS + 0, "0.50", "0.52"),  # changed
    ]
    table: Any = kb.quote_staleness_table({TICKER: window()}, {TICKER: bars})
    cells = {(c["time_band"], c["mid_band"]): c for c in table}
    two = cells[(">1-2m", "0.30-0.69")]
    assert two["unchanged_close_quote_share"] == 1.0
    assert two["unchanged_close_quote_no_volume_share"] == 1.0
    assert two["zero_bid_and_ask_range_share"] == 1.0
    one = cells[("<=1m", "0.30-0.69")]
    assert one["unchanged_close_quote_share"] == 1.0
    assert one["unchanged_close_quote_no_volume_share"] == 0.0
    assert one["zero_bid_and_ask_range_share"] == 0.0
    assert cells[("post_close", "0.30-0.69")]["unchanged_close_quote_share"] == 0.0


def test_quote_staleness_does_not_bridge_missing_minutes() -> None:
    bars = [bar(CLOSE_TS - 240, "0.40", "0.42"), bar(CLOSE_TS - 60, "0.40", "0.42")]
    assert kb.quote_staleness_table({TICKER: window()}, {TICKER: bars}) == []


def test_trade_arrival_rates_gaps_and_blocks() -> None:
    rows = [
        kb.parse_trade(trade_row("a", "2030-01-01T00:14:10Z")),
        kb.parse_trade(trade_row("b", "2030-01-01T00:14:40Z", block=True)),
        kb.parse_trade(trade_row("c", "2030-01-01T00:02:00Z")),
    ]
    arrival: Any = kb.trade_arrival({TICKER: window()}, {TICKER: [t for t in rows if t]})
    last = arrival["<=1m"]
    assert isinstance(last, dict)
    assert last["trades"] == 2
    assert last["block_share"] == 0.5
    assert last["contract_minutes"] == 1.0
    assert last["trades_per_contract_minute"] == 2.0
    assert last["inter_trade_gap_seconds"]["min"] == "30"
    early = arrival[">10m"]
    assert isinstance(early, dict)
    assert early["contract_minutes"] == 5.0
    assert early["inter_trade_gap_seconds"] is None  # first trade of the market


def test_trade_timestamps_precision_groups_and_taker_population() -> None:
    absent = trade_row("c", "2030-02-01T00:00:01Z")
    del absent["taker_outcome_side"]
    rows: list[dict[str, object]] = [
        trade_row("a", "2030-01-01T00:00:01.250Z"),
        trade_row("b", "2030-01-01T00:00:01.250Z"),
        absent,
        {**trade_row("d", "2030-02-01T00:00:02Z"), "taker_outcome_side": "buy"},
        {**trade_row("e", "x"), "created_time": "not a time"},
    ]
    result: Any = kb.trade_timestamps({TICKER: rows})
    assert result["created_time_fraction_digits"] == {"0": 2, "3": 2}
    assert result["created_time_unparsed"] == 1
    assert result["whole_minute_share"] == 0.0
    assert result["same_timestamp_groups"] == 1
    assert result["prints_in_same_timestamp_groups"] == 2
    assert result["taker_outcome_side_by_month"] == {
        "2030-01": {"yes": 2},
        "2030-02": {"absent_or_null": 1, "invalid": 1},
    }


def test_print_dispersion_excludes_blocks_and_counts_same_time() -> None:
    rows = [
        kb.parse_trade(trade_row("a", "2030-01-01T00:14:10Z", price="0.40")),
        kb.parse_trade(trade_row("b", "2030-01-01T00:14:10Z", price="0.41")),
        kb.parse_trade(trade_row("c", "2030-01-01T00:14:40Z", price="0.45")),
        kb.parse_trade(trade_row("d", "2030-01-01T00:14:45Z", price="0.90", block=True)),
    ]
    result: Any = kb.print_dispersion({TICKER: window()}, {TICKER: [t for t in rows if t]})
    assert result["block_trades_excluded"] == 1
    assert result["same_timestamp_pairs"] == 1
    assert result["minutes_with_two_or_more_prints_share"] == 1.0
    band = result["by_time_band"]["<=1m"]
    assert band["pairs"] == 1
    assert band["abs_price_change"]["max"] == "0.04"
    assert band["gap_seconds"]["max"] == "30"


def hurdle_cell(result: dict[str, object], horizon: int, band: str) -> dict[str, Any]:
    cells = result["cells"]
    assert isinstance(cells, list)
    (cell,) = [c for c in cells if c["horizon_seconds"] == horizon and c["time_band"] == band]
    return cast("dict[str, Any]", cell)


def test_cost_hurdle_close_to_close_generous_and_fees() -> None:
    bars = [
        bar(CLOSE_TS - 240, "0.48", "0.50"),  # entry: >3-5m, mid 0.49
        bar(CLOSE_TS - 180, "0.49", "0.51", bid_high="0.60"),  # intra-minute bid spike
        bar(CLOSE_TS - 120, "0.53", "0.55"),  # YES +0.03 net of spread at h=120
        bar(CLOSE_TS - 60, "0.40", "0.42"),
        bar(CLOSE_TS, "0.30", "0.32"),
    ]
    heavy = kb.FeeScenario("heavy", Decimal("0.2"))
    result: Any = kb.cost_hurdle_table({TICKER: window()}, {TICKER: bars}, [kb.SPREAD_ONLY, heavy])
    assert result["fee_scenarios"]["heavy"]["status"] == "SCENARIO_NOT_AUTHORITATIVE"
    entry60 = hurdle_cell(result, 60, ">3-5m")["scenarios"]
    # h=60: YES 0.49 - 0.50 < 0; NO 0.48 - 0.51 < 0; generous YES 0.60 - 0.50 > 0.
    assert entry60["spread_only"]["close_to_close_positive_share"] == 0.0
    assert entry60["spread_only"]["generous_positive_share"] == 1.0
    assert entry60["spread_only"]["contracts_with_generous_positive"] == 1
    entry120 = hurdle_cell(result, 120, ">3-5m")["scenarios"]
    assert entry120["spread_only"]["close_to_close_positive_share"] == 1.0
    assert Decimal(entry120["spread_only"]["best_close_to_close_net"]["max"]) == Decimal("0.03")
    # 0.2 x P(1-P) on each leg: about 0.05 at entry and exit, so the 0.03 move fails.
    assert entry120["heavy"]["close_to_close_positive_share"] == 0.0
    # The falling path makes NO positive from the 2-minute boundary: bid(E) 0.53 - ask 0.32.
    assert (
        hurdle_cell(result, 120, ">1-2m")["scenarios"]["spread_only"][
            "close_to_close_positive_share"
        ]
        == 1.0
    )
    counts = result["counts"]
    assert counts["h60_crosses_close"] == 1  # the entry at close_time itself
    assert counts["h120_crosses_close"] == 2


def test_cost_hurdle_counts_missing_exit_and_refuses_bad_scenarios() -> None:
    bars = [bar(CLOSE_TS - 240, "0.48", "0.50"), bar(CLOSE_TS - 180, None, "0.50")]
    result: Any = kb.cost_hurdle_table({TICKER: window()}, {TICKER: bars}, [kb.SPREAD_ONLY])
    assert result["counts"] == {"h120_exit_quote_unavailable": 1, "h60_exit_quote_unavailable": 1}
    assert result["cells"] == []
    with pytest.raises(ValueError, match="unique"):
        kb.cost_hurdle_table({}, {}, [kb.SPREAD_ONLY, kb.SPREAD_ONLY])
    with pytest.raises(ValueError, match="unique"):
        kb.cost_hurdle_table({}, {}, [])


def test_lead_lag_measurability_kalshi_side_only() -> None:
    rows = [
        kb.parse_trade(trade_row("a", "2030-01-01T00:14:10.5Z")),
        kb.parse_trade(trade_row("b", "2030-01-01T00:14:12Z")),
        kb.parse_trade(trade_row("c", "2030-01-01T00:14:13Z", block=True)),
        kb.parse_trade(trade_row("d", "2030-01-01T00:05:00Z")),  # before the late window
    ]
    result: Any = kb.lead_lag_measurability(
        {TICKER: window()},
        {TICKER: [t for t in rows if t]},
        {"observed_resolution": "whole_second", "nonzero_fraction_share": 0.0},
    )
    assert result["observed_resolution"] == "whole_second"
    assert result["minimum_resolvable_lag_seconds"] == 2
    assert result["late_window_prints"] == 2
    assert result["late_window_distinct_time_share"] == 1.0
    assert result["late_window_seconds_with_print_share"] == round(2 / 300, 4)
    assert result["late_window_inter_print_gap_seconds"]["max"] == "1.5"
    assert str(result["kraken_alignment"]).startswith("NOT_COMPUTED")


def test_lifecycle_incidence_grid_expiration_and_thursday_pause() -> None:
    # 2030-01-03 is a Thursday; 03:00 EST = 08:00 UTC.
    thursday = int(datetime(2030, 1, 3, 8, tzinfo=UTC).timestamp())
    markets = [
        market(),
        market(
            ticker="P",
            open_time="2030-01-03T08:00:00Z",
            close_time="2030-01-03T08:15:00Z",
            expected_expiration_time="2030-01-03T08:20:00Z",
            can_close_early=True,
        ),
        market(ticker="Q", close_time="2030-01-01T00:14:00Z"),
    ]
    windows = {
        TICKER: window(),
        "P": window("P", thursday),
        "Q": kb.MarketWindow("Q", OPEN_TS, OPEN_TS + 840),
    }
    candles = {"P": [bar(thursday + 60, "0.4", "0.5")]}
    result: Any = kb.lifecycle_incidence(markets, windows, candles, {})
    assert result["window_duration_seconds"] == {"840": 1, "900": 2}
    checks = result["checks"]
    assert isinstance(checks, dict)
    assert checks["close_off_grid"] == 1
    assert checks["close_on_15_minute_grid"] == 2
    assert checks["close_differs_from_expected_expiration"] == 1
    assert checks["expected_expiration_unparsed_or_absent"] == 2
    assert checks["can_close_early_true"] == 1
    pause = result["thursday_pause"]
    assert isinstance(pause, dict)
    assert pause["markets_overlapping"] == 1
    assert pause["overlaps"] == [
        {"overlap_minutes": 15.0, "candles_in_overlap": 1, "trades_in_overlap": 0}
    ]


def test_old_strategy_control_selection_and_intervals() -> None:
    day2 = OPEN_TS + 86_400
    markets = [
        market(),  # result yes
        market(
            ticker="N",
            result="no",
            open_time="2030-01-02T00:00:00Z",
            close_time="2030-01-02T00:15:00Z",
        ),
        market(ticker="S", result="scalar"),
    ]
    windows = {TICKER: window(), "N": window("N", day2), "S": window("S")}
    candles = {
        # earliest qualifying minute in <=1m is the only one; the later post-close bar is out.
        TICKER: [bar(CLOSE_TS - 60, "0.93", "0.95"), bar(CLOSE_TS - 240, "0.80", "0.84")],
        "N": [bar(day2 + 840, "0.94", "0.96")],
    }
    first: Any = kb.old_strategy_control(markets, windows, candles, [kb.SPREAD_ONLY], resamples=200)
    again: Any = kb.old_strategy_control(markets, windows, candles, [kb.SPREAD_ONLY], resamples=200)
    assert first == again  # deterministic
    assert first["markets_excluded_result_not_yes_no"] == 1
    cells = {(c["time_band"], c["ask_band"]): c for c in first["cells"]}
    yes_tail = cells[("<=1m", "0.93-0.95")]
    assert yes_tail["contracts"] == 1  # the YES market wins at 0.95
    assert yes_tail["wins"] == 1
    other = cells[("<=1m", "0.96-0.97")]
    assert other["contracts"] == 1  # the NO market's YES ask 0.96 loses
    assert other["wins"] == 0
    assert other["win_frequency_wilson95"][0] == 0.0
    assert other["gap_day_block95"] is None  # one close date only
    assert (">3-5m", "<0.85") not in cells  # below the 0.85 candidate floor
    pooled: Any = kb.old_strategy_control(
        [markets[0], markets[1]],
        windows,
        {TICKER: [bar(CLOSE_TS - 60, "0.93", "0.95")], "N": [bar(day2 + 840, "0.93", "0.95")]},
        [kb.SPREAD_ONLY],
        resamples=200,
    )
    (cell,) = pooled["cells"]
    assert cell["contracts"] == 2
    assert cell["distinct_close_dates"] == 2
    assert cell["gap_day_block95"] is not None


def test_build_report_includes_pmv2_sections(tmp_path: Path) -> None:
    write_pilot(tmp_path)
    report: Any = kb.build_report(kb.load_pilot(tmp_path), [kb.FeeScenario("s1", Decimal("0.01"))])
    for key in (
        "p10_spread",
        "p11_quote_staleness",
        "p12_trade_arrival",
        "p13_trade_timestamps",
        "p14_print_dispersion",
        "p15_cost_hurdle",
        "p16a_lead_lag_measurability",
        "lifecycle_incidence",
        "c1_old_strategy_control",
        "stop_screen",
    ):
        assert key in report, key
    scenarios = report["p15_cost_hurdle"]["fee_scenarios"]
    assert list(scenarios) == ["spread_only", "s1"]
    json.dumps(report)


def test_main_fee_scenario_arguments(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_pilot(tmp_path)
    assert kb.main([str(tmp_path), "--fee-scenario", "s1=0.02"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "s1" in out["p15_cost_hurdle"]["fee_scenarios"]
    assert kb.main([str(tmp_path), "--fee-scenario", "spread_only=0.1"]) == 2
    assert kb.main([str(tmp_path), "--fee-scenario", "a=0.1", "--fee-scenario", "a=0.2"]) == 2
    with pytest.raises(SystemExit):
        kb.main([str(tmp_path), "--fee-scenario", "bad"])


def screen_inputs(
    generous: float, rate: float = 2.0, unchanged: float = 0.5, contracts: int = 3
) -> dict[str, Any]:
    return {
        "staleness": [
            {"time_band": "<=1m", "mid_band": "0.30-0.69", "unchanged_close_quote_share": unchanged}
        ],
        "arrival": {"<=1m": {"trades_per_contract_minute": rate}},
        "timestamps": {"observed_resolution": "whole_second", "whole_minute_share": 0.02},
        "hurdle": {
            "cells": [
                {
                    "horizon_seconds": 60,
                    "time_band": "<=1m",
                    "mid_band": "0.30-0.69",
                    "contracts": contracts,
                    "decision_points": 30,
                    "scenarios": {"spread_only": {"generous_positive_share": generous}},
                }
            ]
        },
        "measurability": {"late_window_seconds_with_print_share": 0.2},
    }


def test_stop_screen_s1_and_s3() -> None:
    passed: Any = kb.stop_screen(**screen_inputs(0.10))
    assert passed["s1"] == kb.S1_PASSED
    assert "NOT EVIDENCE OF EDGE" in passed["s1"]
    assert passed["s1_reason"] is None
    failed: Any = kb.stop_screen(**screen_inputs(0.04))
    assert failed["s1"] == "HISTORICAL COST-HURDLE SCREEN FAILED — OWNER NO-GO REVIEW REQUIRED"
    assert failed["s1_reason"] == "generous_ceiling_below_threshold_in_every_liquid_cell"
    illiquid: Any = kb.stop_screen(**screen_inputs(0.5, rate=0.5, unchanged=0.9, contracts=2))
    assert illiquid["s1"] == kb.S1_FAILED
    assert illiquid["s1_reason"] == "no_liquid_cell"
    assert illiquid["s3_removed_cells"][0]["failed"] == [
        "contracts",
        "trade_rate",
        "unchanged_quotes",
    ]
    assert illiquid["s4_s5_s6"].startswith("MANUAL")


def test_stop_screen_s2() -> None:
    inputs = screen_inputs(0.1)
    assert kb.stop_screen(**inputs)["s2"] == "CONTINUE"
    coarse = {**inputs, "timestamps": {"observed_resolution": "coarser_than_second"}}
    assert kb.stop_screen(**coarse)["s2"] == "STOP_HISTORICAL_LEAD_LAG"
    sparse = {**inputs, "measurability": {"late_window_seconds_with_print_share": 0.01}}
    assert kb.stop_screen(**sparse)["s2"] == "STOP_HISTORICAL_LEAD_LAG"
    for resolution in ("mixed", "unknown"):
        unclear = {**inputs, "timestamps": {"observed_resolution": resolution}}
        assert kb.stop_screen(**unclear)["s2"] == "UNDETERMINED"
    fine = {**inputs, "timestamps": {"observed_resolution": "sub_second"}}
    assert kb.stop_screen(**fine)["s2"] == "CONTINUE"


# ------------------------------------------------------------------ final-review additions


def stamped(trade_id: str, when: str) -> dict[str, object]:
    return trade_row(trade_id, when)


@pytest.mark.parametrize(
    ("stamp", "fraction_class", "significant"),
    [
        ("2030-01-01T00:00:01Z", "no_fraction", {}),
        ("2030-01-01T00:00:01.000Z", "fraction_all_zero", {}),
        ("2030-01-01T00:00:01.100Z", "fraction_nonzero", {"1": 1}),
        ("2030-01-01T00:00:01.123456Z", "fraction_nonzero", {"6": 1}),
        ("2030-01-01T00:00:01.000250Z", "fraction_nonzero", {"5": 1}),  # a 10 us grid
    ],
)
def test_trade_timestamps_separate_formatting_from_resolution(
    stamp: str, fraction_class: str, significant: dict[str, int]
) -> None:
    result: Any = kb.trade_timestamps({TICKER: [stamped("a", stamp)]})
    classes = result["fraction_class"]
    assert classes[fraction_class] == 1
    assert sum(classes.values()) == 1
    assert result["nonzero_fraction_significant_digits"] == significant
    assert result["created_time_fraction_digits"] == {
        "2030-01-01T00:00:01Z": {"0": 1},
        "2030-01-01T00:00:01.000Z": {"3": 1},
        "2030-01-01T00:00:01.100Z": {"3": 1},
    }.get(stamp, {"6": 1})  # the raw-string precision profile is preserved


def test_observed_resolution_classes() -> None:
    zeros = [stamped(str(i), f"2030-01-01T00:00:{i:02d}.000Z") for i in range(1, 30)]
    whole: Any = kb.trade_timestamps({TICKER: zeros})
    assert whole["observed_resolution"] == "whole_second"  # ".000" is not sub-second
    millis = [stamped(str(i), f"2030-01-01T00:00:{i:02d}.{i:03d}Z") for i in range(1, 30)]
    fine: Any = kb.trade_timestamps({TICKER: millis})
    assert fine["observed_resolution"] == "sub_second"
    assert fine["nonzero_fraction_share"] == 1.0
    minutes = [stamped(str(i), f"2030-01-01T00:{i:02d}:00Z") for i in range(1, 30)]
    coarse: Any = kb.trade_timestamps({TICKER: minutes})
    assert coarse["observed_resolution"] == "coarser_than_second"
    mixed_rows = zeros[:20] + millis[:5]
    mixed: Any = kb.trade_timestamps({TICKER: mixed_rows})
    assert mixed["observed_resolution"] == "mixed"
    assert kb.trade_timestamps({})["observed_resolution"] == "unknown"


def test_same_timestamp_clusters() -> None:
    rows = [
        stamped("a", "2030-01-01T00:00:01.250Z"),
        stamped("b", "2030-01-01T00:00:01.250Z"),
        stamped("c", "2030-01-01T00:00:01.250Z"),
        stamped("d", "2030-01-01T00:00:02Z"),
        stamped("e", "2030-01-01T00:00:02Z"),
        stamped("f", "2030-01-01T00:00:03Z"),
    ]
    result: Any = kb.trade_timestamps({TICKER: rows})
    assert result["same_timestamp_groups"] == 2
    assert result["prints_in_same_timestamp_groups"] == 5
    assert result["same_timestamp_cluster_sizes"] == {"2": 1, "3": 1}
    parsed = [kb.parse_trade(r) for r in rows]
    late = kb.MarketWindow(TICKER, OPEN_TS - 900, OPEN_TS + 60)
    measured: Any = kb.lead_lag_measurability(
        {TICKER: late}, {TICKER: [t for t in parsed if t]}, result
    )
    assert measured["late_window_prints"] == 6
    assert measured["late_window_distinct_time_share"] == 0.5  # 3 distinct of 6


def test_old_strategy_control_one_row_per_contract_and_band_when_price_flips() -> None:
    # Inside >3-5m (remaining 300 and 240 s): YES ask 0.90 first, then a flip to bid 0.05
    # (NO ask 0.95). Both would qualify; only the earliest (YES at 0.90) is used.
    flip = [bar(CLOSE_TS - 300, "0.88", "0.90"), bar(CLOSE_TS - 240, "0.05", "0.07")]
    result: Any = kb.old_strategy_control(
        [market()], {TICKER: window()}, {TICKER: flip}, [kb.SPREAD_ONLY], resamples=50
    )
    (cell,) = result["cells"]
    assert (cell["time_band"], cell["ask_band"]) == (">3-5m", "0.90-0.92")
    assert cell["contracts"] == 1
    assert cell["sides"] == {"yes": 1}
    assert result["other_side_qualified_later_in_band_not_used"] == 1
    # Both sides qualify in one minute and fall in the same ask band: still one row.
    same_band = [bar(CLOSE_TS - 300, "0.06", "0.93"), bar(CLOSE_TS - 240, "0.07", "0.09")]
    again: Any = kb.old_strategy_control(
        [market()], {TICKER: window()}, {TICKER: same_band}, [kb.SPREAD_ONLY], resamples=50
    )
    assert [c["contracts"] for c in again["cells"]] == [1]
    # Same minute, both sides qualify (a very wide book): higher ask wins, YES on a tie.
    wide = [bar(CLOSE_TS - 240, "0.10", "0.86")]  # YES ask 0.86, NO ask 0.90
    tie: Any = kb.old_strategy_control(
        [market()], {TICKER: window()}, {TICKER: wide}, [kb.SPREAD_ONLY], resamples=50
    )
    (wide_cell,) = tie["cells"]
    assert wide_cell["sides"] == {"no": 1}
    assert wide_cell["wins"] == 0  # result yes, chosen side no
    assert tie["both_sides_qualified_same_minute"] == 1
    even = [bar(CLOSE_TS - 240, "0.12", "0.88")]  # YES ask 0.88, NO ask 0.88
    tied: Any = kb.old_strategy_control(
        [market()], {TICKER: window()}, {TICKER: even}, [kb.SPREAD_ONLY], resamples=50
    )
    assert tied["cells"][0]["sides"] == {"yes": 1}


def test_cli_emits_exactly_one_report_with_custom_scenarios(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_pilot(tmp_path)
    args = [str(tmp_path), "--fee-scenario", "s1=0.02", "--fee-scenario", "s2=0.05"]
    assert kb.main(args) == 0
    out = capsys.readouterr().out
    decoder = json.JSONDecoder()
    report, end = decoder.raw_decode(out)
    assert out[end:].strip() == ""  # nothing after the single document
    assert out.count('"report": "b12_kalshi_btc_pilot_profile"') == 1
    assert set(report["p15_cost_hurdle"]["fee_scenarios"]) == {"spread_only", "s1", "s2"}
    assert report["p15_cost_hurdle"]["fee_scenarios"]["spread_only"]["coefficient"] == "0"
    assert report["stop_screen"]["scenario"] == "spread_only"
    assert kb.main([str(tmp_path)]) == 0
    default, end = decoder.raw_decode(capsys.readouterr().out)
    assert list(default["p15_cost_hurdle"]["fee_scenarios"]) == ["spread_only"]
