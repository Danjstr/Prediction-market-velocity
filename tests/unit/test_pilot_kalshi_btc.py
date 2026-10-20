"""B12 Kalshi BTC pilot profiler: deterministic behavior on synthetic fixtures only.

Every value below is invented. No real Kalshi observation is in this file.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

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
