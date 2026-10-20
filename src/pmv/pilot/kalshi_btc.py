"""B12 Kalshi BTC 15-minute historical pilot: deterministic profiling of a bounded raw sample.

Development-time research code (owner B12 charter, 2026-10-19; PMV 2.0 amendment, owner
decision record ``docs/decisions/2026-10-20_b12_pmv2_strategy_pivot.md``). It reads a raw
pilot directory written by ``research/data_sources/recon_tools/kalshi_pilot_sample.py`` and
produces a derived, aggregate-only JSON report:

- a native field profile per object (types, nulls, numeric strings, decimals, timestamp
  precision), with ordering, duplicate, and pagination checks;
- label integrity per settled market (result, settlement value, strike re-derivation);
- 1-minute candle coverage (missing minutes, null and sentinel quotes, unchanged quotes);
- the late-window table (remaining-time band x executable-ask band, YES and NO sides);
- trade activity by remaining-time band;
- trade <-> candle minute reconciliation under each boundary convention and offset;
- the PMV 2.0 descriptive measurements P10 to P16 of the B12 protocol
  (``research/kalshi/b12_btc_kalshi_pilot.md`` §5): minute-boundary spread, quote
  staleness, trade arrival, trade timestamps and taker-side population, sub-minute print
  dispersion, the cost-hurdle / perfect-foresight ceiling, and Kalshi-side lead/lag
  measurability; plus early-close and pause incidence;
- the old-strategy settlement control C1 (market tail calibration by ask band x remaining
  time, with day-blocked intervals).

Nothing here decides a trade or produces a feature. Settlement and result fields are read
only to check label integrity and, in the old-strategy control, as the label; they are
never inputs to anything else. Observations within one contract are not independent: every
table reports distinct contracts and distinct settlement instants next to row counts. At
pilot scale (about 12 markets) every table is descriptive; none is an edge, profitability,
or calibration claim.

Fee scenarios are labelled scenarios, never the authoritative Kalshi schedule (owner
decision DR-9: no economics claim before the fee schedule is versioned). The default is
spread-only (no fee), which is the most generous cost floor.

Parsing is strict and fail-visible: a value that cannot be parsed is counted as
malformed, never repaired or dropped silently.
"""

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "ASK_BANDS",
    "FULL_TIME_BANDS",
    "PRICE_BANDS",
    "TIME_BANDS",
    "Candle",
    "FeeScenario",
    "PilotError",
    "Trade",
    "ask_band",
    "build_report",
    "candle_coverage",
    "cost_hurdle_table",
    "field_profile",
    "full_time_band",
    "label_integrity",
    "late_window_table",
    "lead_lag_measurability",
    "lifecycle_incidence",
    "load_pilot",
    "old_strategy_control",
    "parse_candle",
    "parse_decimal",
    "parse_fee_scenario",
    "parse_rfc3339",
    "parse_trade",
    "price_band",
    "print_dispersion",
    "quote_staleness_table",
    "reconcile",
    "spread_table",
    "stop_screen",
    "time_band",
    "trade_activity",
    "trade_arrival",
    "trade_timestamps",
]

ONE: Final = Decimal(1)
ZERO: Final = Decimal(0)
TIME_BANDS: Final = ("post_close", "<=1m", ">1-2m", ">2-3m", ">3-5m", ">5m")
ASK_BANDS: Final = ("<0.85", "0.85-0.89", "0.90-0.92", "0.93-0.95", "0.96-0.97", ">0.97")
# PMV 2.0 strata (development hypotheses, owner-amendable before the pilot runs).
FULL_TIME_BANDS: Final = ("post_close", "<=1m", ">1-2m", ">2-3m", ">3-5m", ">5-10m", ">10m")
PRICE_BANDS: Final = ("<0.10", "0.10-0.29", "0.30-0.69", "0.70-0.89", "0.90-0.96", ">=0.97")
HORIZONS_SECONDS: Final = (60, 120)  # the minute grid cannot represent 30 s (protocol P15)
TAIL_FLOOR: Final = Decimal("0.85")  # old-strategy control: candidate region only
BOOTSTRAP_SEED: Final = 20261020
BOOTSTRAP_RESAMPLES: Final = 2000
_RFC3339: Final = re.compile(
    r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})"
)
_NUMERIC: Final = re.compile(r"-?\d+(?:\.(\d+))?")


class PilotError(ValueError):
    """A raw pilot file is structurally unusable (missing, wrong type, or wrong wrapper)."""


def parse_decimal(value: object) -> Decimal | None:
    """A strict numeric parse: a numeric string or an int. Floats and bools are refused,
    because a binary float has already lost the venue's fixed-point value."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str) and _NUMERIC.fullmatch(value):
        try:
            return Decimal(value)
        except InvalidOperation:  # pragma: no cover - the pattern already excludes this
            return None
    return None


def parse_rfc3339(value: object) -> tuple[datetime, int] | None:
    """An RFC 3339 time with an explicit offset, and its fractional-second digit count.

    A missing offset is refused (no timezone is assumed). Digits beyond microseconds are
    counted for the precision profile and truncated for the value.
    """
    if not isinstance(value, str):
        return None
    match = _RFC3339.fullmatch(value)
    if match is None:
        return None
    date, clock, fraction, offset = match.groups()
    digits = len(fraction or "")
    micro = (fraction or "").ljust(6, "0")[:6]
    text = f"{date}T{clock}.{micro}{'+00:00' if offset == 'Z' else offset}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.astimezone(UTC), digits


def _epoch(value: datetime) -> float:
    return value.timestamp()


# ---------------------------------------------------------------- native field profile


def _native_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        if parse_rfc3339(value) is not None:
            return "str:rfc3339"
        if _NUMERIC.fullmatch(value):
            return "str:numeric"
        return "str:empty" if value == "" else "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _flatten(row: Mapping[str, object], prefix: str = "") -> dict[str, object]:
    flat: dict[str, object] = {}
    for key, value in row.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat[name] = value
            flat.update(_flatten(value, f"{name}."))
        else:
            flat[name] = value
    return flat


def field_profile(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    """Per field: present count, native types, nulls, numeric-string decimals, and
    timestamp fractional-digit counts. Values themselves are never reported."""
    profile: dict[str, dict[str, Any]] = {}
    for row in rows:
        for name, value in _flatten(row).items():
            entry = profile.setdefault(
                name,
                {"present": 0, "types": Counter(), "decimals": Counter(), "ts_digits": Counter()},
            )
            entry["present"] += 1
            kind = _native_type(value)
            entry["types"][kind] += 1
            if kind == "str:numeric" and isinstance(value, str):
                match = _NUMERIC.fullmatch(value)
                entry["decimals"][len(match.group(1) or "") if match else -1] += 1
            if kind == "str:rfc3339":
                parsed = parse_rfc3339(value)
                if parsed is not None:
                    entry["ts_digits"][parsed[1]] += 1
    total = len(rows)
    result: dict[str, dict[str, object]] = {}
    for name in sorted(profile):
        entry = profile[name]
        result[name] = {
            "present": entry["present"],
            "absent": total - entry["present"],
            "types": dict(sorted(entry["types"].items())),
            "numeric_string_decimals": {str(k): v for k, v in sorted(entry["decimals"].items())},
            "timestamp_fraction_digits": {str(k): v for k, v in sorted(entry["ts_digits"].items())},
        }
    return result


def order_and_duplicates(keys: Sequence[str], times: Sequence[float | None]) -> dict[str, object]:
    """Ordering of a returned sequence and duplicate identifiers, in returned order."""
    known = [t for t in times if t is not None]
    pairs = list(pairwise(known))
    if not pairs:
        order = "trivial"
    elif all(a <= b for a, b in pairs):
        order = "ascending"
    elif all(a >= b for a, b in pairs):
        order = "descending"
    else:
        order = "unsorted"
    counts = Counter(keys)
    return {
        "rows": len(keys),
        "order_by_time": order,
        "equal_adjacent_times": sum(1 for a, b in pairs if a == b),
        "duplicate_ids": sum(c - 1 for c in counts.values() if c > 1),
        "unparsed_times": len(times) - len(known),
    }


# ---------------------------------------------------------------- typed observations


@dataclass(frozen=True)
class Trade:
    trade_id: str
    ticker: str
    time: float
    count: Decimal
    yes_price: Decimal
    taker_outcome_side: str | None  # None: absent or null (field added 2026-05-06)
    is_block: bool


@dataclass(frozen=True)
class Candle:
    ticker: str
    end_ts: int
    yes_bid_close: Decimal | None
    yes_ask_close: Decimal | None
    yes_bid_open: Decimal | None
    yes_ask_open: Decimal | None
    price_open: Decimal | None
    price_high: Decimal | None
    price_low: Decimal | None
    price_close: Decimal | None
    volume: Decimal | None
    open_interest: Decimal | None
    yes_bid_high: Decimal | None = None
    yes_bid_low: Decimal | None = None
    yes_ask_high: Decimal | None = None
    yes_ask_low: Decimal | None = None


def parse_trade(row: Mapping[str, object]) -> Trade | None:
    """A historical REST trade, or None if any required field is malformed.

    ``taker_outcome_side`` is optional: Kalshi added it on 2026-05-06 (changelog), so an
    older trade may lack it. Absent or null gives ``None`` and is counted by
    ``trade_timestamps`` (protocol P13). A present value other than yes/no is malformed.
    """
    when = parse_rfc3339(row.get("created_time"))
    count = parse_decimal(row.get("count_fp", row.get("count")))
    price = parse_decimal(row.get("yes_price_dollars"))
    trade_id, ticker = row.get("trade_id"), row.get("ticker")
    block = row.get("is_block_trade")
    side = row.get("taker_outcome_side")
    if (
        when is None
        or count is None
        or price is None
        or not isinstance(trade_id, str)
        or not isinstance(ticker, str)
        or not isinstance(block, bool)
        or side not in ("yes", "no", None)
    ):
        return None
    return Trade(
        trade_id, ticker, _epoch(when[0]), count, price, None if side is None else str(side), block
    )


def _ohlc(row: Mapping[str, object], group: str, part: str) -> Decimal | None:
    block = row.get(group)
    if not isinstance(block, dict):
        return None
    # Historical schema: open/low/high/close; live schema: open_dollars/...
    return parse_decimal(block.get(part, block.get(f"{part}_dollars")))


def parse_candle(ticker: str, row: Mapping[str, object]) -> Candle | None:
    end = row.get("end_period_ts")
    if isinstance(end, bool) or not isinstance(end, int):
        return None
    return Candle(
        ticker=ticker,
        end_ts=end,
        yes_bid_close=_ohlc(row, "yes_bid", "close"),
        yes_ask_close=_ohlc(row, "yes_ask", "close"),
        yes_bid_open=_ohlc(row, "yes_bid", "open"),
        yes_ask_open=_ohlc(row, "yes_ask", "open"),
        price_open=_ohlc(row, "price", "open"),
        price_high=_ohlc(row, "price", "high"),
        price_low=_ohlc(row, "price", "low"),
        price_close=_ohlc(row, "price", "close"),
        volume=parse_decimal(row.get("volume", row.get("volume_fp"))),
        open_interest=parse_decimal(row.get("open_interest", row.get("open_interest_fp"))),
        yes_bid_high=_ohlc(row, "yes_bid", "high"),
        yes_bid_low=_ohlc(row, "yes_bid", "low"),
        yes_ask_high=_ohlc(row, "yes_ask", "high"),
        yes_ask_low=_ohlc(row, "yes_ask", "low"),
    )


# ---------------------------------------------------------------- bands


def time_band(remaining_seconds: float) -> str:
    if remaining_seconds <= 0:
        return "post_close"
    if remaining_seconds <= 60:
        return "<=1m"
    if remaining_seconds <= 120:
        return ">1-2m"
    if remaining_seconds <= 180:
        return ">2-3m"
    if remaining_seconds <= 300:
        return ">3-5m"
    return ">5m"


def ask_band(ask: Decimal) -> str:
    if ask < Decimal("0.85"):
        return "<0.85"
    if ask < Decimal("0.90"):
        return "0.85-0.89"
    if ask < Decimal("0.93"):
        return "0.90-0.92"
    if ask < Decimal("0.96"):
        return "0.93-0.95"
    if ask <= Decimal("0.97"):
        return "0.96-0.97"
    return ">0.97"


def full_time_band(remaining_seconds: float) -> str:
    """PMV 2.0 remaining-time strata: the settlement bands plus >5-10m and >10m."""
    band = time_band(remaining_seconds)
    if band != ">5m":
        return band
    return ">5-10m" if remaining_seconds <= 600 else ">10m"


def price_band(price: Decimal) -> str:
    """PMV 2.0 full-range price strata (a reporting stratum, never an entry rule)."""
    if price < Decimal("0.10"):
        return "<0.10"
    if price < Decimal("0.30"):
        return "0.10-0.29"
    if price < Decimal("0.70"):
        return "0.30-0.69"
    if price < Decimal("0.90"):
        return "0.70-0.89"
    if price < Decimal("0.97"):
        return "0.90-0.96"
    return ">=0.97"


def _usable(price: Decimal | None) -> bool:
    """Strictly inside (0, 1). 0, 1, and null are counted as empty-book or sentinel cases."""
    return price is not None and ZERO < price < ONE


def _quantiles(values: Iterable[Decimal]) -> dict[str, str] | None:
    ordered = sorted(values)
    if not ordered:
        return None
    picks = {"min": 0.0, "p10": 0.1, "p50": 0.5, "p90": 0.9, "max": 1.0}
    top = len(ordered) - 1
    return {k: str(ordered[round(q * top)]) for k, q in picks.items()}


# ---------------------------------------------------------------- market-level checks


@dataclass(frozen=True)
class MarketWindow:
    ticker: str
    open_ts: float
    close_ts: float


def market_window(market: Mapping[str, object]) -> MarketWindow | None:
    ticker = market.get("ticker")
    opened = parse_rfc3339(market.get("open_time"))
    closed = parse_rfc3339(market.get("close_time"))
    if not isinstance(ticker, str) or opened is None or closed is None:
        return None
    return MarketWindow(ticker, _epoch(opened[0]), _epoch(closed[0]))


def _derive_result(market: Mapping[str, object]) -> str | None:
    """Re-derive yes/no from expiration_value and strikes for the simple strike types.

    INFERENCE: the strict-or-not meaning of each strike type is taken from its name; the
    contract terms govern (research/kalshi/api_documentation_findings.md §3.3).
    """
    value = parse_decimal(market.get("expiration_value"))
    floor = parse_decimal(market.get("floor_strike"))
    cap = parse_decimal(market.get("cap_strike"))
    kind = market.get("strike_type")
    if value is None:
        return None
    rules: dict[object, Callable[[], bool | None]] = {
        "greater": lambda: None if floor is None else value > floor,
        "greater_or_equal": lambda: None if floor is None else value >= floor,
        "less": lambda: None if cap is None else value < cap,
        "less_or_equal": lambda: None if cap is None else value <= cap,
        "between": lambda: None if floor is None or cap is None else floor <= value <= cap,
    }
    rule = rules.get(kind)
    outcome = None if rule is None else rule()
    return None if outcome is None else ("yes" if outcome else "no")


def label_integrity(markets: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Whether each settled market carries a deterministic, internally consistent label."""
    counts: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    strike_types: Counter[str] = Counter()
    for market in markets:
        result = market.get("result")
        statuses[str(market.get("status"))] += 1
        strike_types[str(market.get("strike_type"))] += 1
        counts[f"result={result!s}"] += 1
        if market.get("is_provisional") is True:
            counts["is_provisional"] += 1
        settle = parse_decimal(market.get("settlement_value_dollars"))
        expected = {"yes": ONE, "no": ZERO}.get(str(result))
        if settle is None:
            counts["settlement_value_missing"] += 1
        elif expected is None:
            counts["settlement_value_not_checkable"] += 1
        else:
            counts["settlement_value_" + ("consistent" if settle == expected else "conflict")] += 1
        derived = _derive_result(market)
        if derived is None:
            counts["strike_rederivation_not_checkable"] += 1
        else:
            agree = derived == result
            counts["strike_rederivation_" + ("agrees" if agree else "disagrees")] += 1
        times = {
            name: parse_rfc3339(market.get(name))
            for name in (
                "open_time",
                "close_time",
                "expected_expiration_time",
                "settlement_ts",
                "updated_time",
            )
        }
        opened, closed = times["open_time"], times["close_time"]
        settled, updated = times["settlement_ts"], times["updated_time"]
        if opened is None or closed is None:
            counts["open_or_close_unparsed"] += 1
        else:
            counts["open_before_close" if opened[0] < closed[0] else "open_not_before_close"] += 1
            if settled is not None:
                counts[
                    "settled_at_or_after_close"
                    if settled[0] >= closed[0]
                    else "settled_before_close"
                ] += 1
            if updated is not None and updated[0] > closed[0]:
                # Metadata changed after close: current REST metadata may be post hoc.
                counts["metadata_updated_after_close"] += 1
    return {
        "markets": len(markets),
        "status": dict(sorted(statuses.items())),
        "strike_type": dict(sorted(strike_types.items())),
        "checks": dict(sorted(counts.items())),
    }


def candle_coverage(window: MarketWindow, candles: Sequence[Candle]) -> dict[str, object]:
    """Minute coverage of one market's 1-minute candles over (open_time, close_time]."""
    ends = [c.end_ts for c in candles]
    inside = [c for c in candles if window.open_ts < c.end_ts <= window.close_ts]
    expected = max(0, round((window.close_ts - window.open_ts) / 60))
    present = {c.end_ts for c in inside}
    misaligned = sum(1 for e in ends if e % 60 != 0)
    last_minute = window.close_ts in present
    unchanged = 0
    for prev, cur in pairwise(inside):
        if (prev.yes_ask_close, prev.yes_bid_close) == (cur.yes_ask_close, cur.yes_bid_close) and (
            cur.volume in (None, ZERO)
        ):
            unchanged += 1
    return {
        "candles": len(candles),
        "inside_window": len(inside),
        "expected_minutes": expected,
        "missing_minutes": max(0, expected - len(present)),
        "duplicate_end_ts": len(ends) - len(set(ends)),
        "not_minute_aligned": misaligned,
        "outside_window": len(candles) - len(inside),
        "final_minute_present": last_minute,
        "unchanged_quote_no_volume": unchanged,
        "ask_close": _quote_states(c.yes_ask_close for c in inside),
        "bid_close": _quote_states(c.yes_bid_close for c in inside),
    }


def _quote_states(values: Iterable[Decimal | None]) -> dict[str, int]:
    states: Counter[str] = Counter()
    for value in values:
        if value is None:
            states["null"] += 1
        elif value <= ZERO:
            states["zero_or_less"] += 1
        elif value >= ONE:
            states["one_or_more"] += 1
        else:
            states["usable"] += 1
    return dict(sorted(states.items()))


def late_window_table(
    windows: Mapping[str, MarketWindow],
    candles: Mapping[str, Sequence[Candle]],
    trades: Mapping[str, Sequence[Trade]],
) -> list[dict[str, object]]:
    """Remaining-time band x executable-ask band, for the YES ask and the NO ask.

    Decision instant = the candle's inclusive end (``end_period_ts``); the minute's quote
    is the bar close. The NO ask is 1 - YES bid close (OFFICIAL DOCUMENTATION: a NO bid at
    Y is a YES ask at 1 - Y). A quote is "unchanged" when both closes equal the previous
    bar's and the bar had no volume. Rows within a contract are not independent.
    """
    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    for ticker, window in windows.items():
        minute_trades: Counter[int] = Counter()
        for trade in trades.get(ticker, ()):
            minute_trades[-(-int(trade.time) // 60) * 60] += 1
        previous: Candle | None = None
        for candle in sorted(candles.get(ticker, ()), key=lambda c: c.end_ts):
            remaining = window.close_ts - candle.end_ts
            band = time_band(remaining)
            unchanged = (
                previous is not None
                and (previous.yes_ask_close, previous.yes_bid_close)
                == (candle.yes_ask_close, candle.yes_bid_close)
                and candle.volume in (None, ZERO)
            )
            sides = {
                "yes": candle.yes_ask_close,
                "no": None if candle.yes_bid_close is None else ONE - candle.yes_bid_close,
            }
            spread = (
                candle.yes_ask_close - candle.yes_bid_close
                if _usable(candle.yes_ask_close)
                and _usable(candle.yes_bid_close)
                and candle.yes_ask_close is not None
                and candle.yes_bid_close is not None
                else None
            )
            for side, ask in sides.items():
                usable = _usable(ask) and (side == "yes" or _usable(candle.yes_bid_close))
                key = (side, band, ask_band(ask) if usable and ask is not None else "no_usable_ask")
                cell = cells.setdefault(
                    key,
                    {
                        "rows": 0,
                        "contracts": set(),
                        "instants": set(),
                        "unchanged": 0,
                        "spreads": [],
                        "volume": ZERO,
                        "trades": 0,
                    },
                )
                cell["rows"] += 1
                cell["contracts"].add(ticker)
                cell["instants"].add(window.close_ts)
                cell["unchanged"] += int(unchanged)
                if spread is not None:
                    cell["spreads"].append(spread)
                cell["volume"] += candle.volume or ZERO
                cell["trades"] += minute_trades.get(candle.end_ts, 0)
            previous = candle
    table = []
    for (side, band, a_band), cell in sorted(cells.items()):
        table.append(
            {
                "side": side,
                "time_band": band,
                "ask_band": a_band,
                "rows": cell["rows"],
                "contracts": len(cell["contracts"]),
                "settlement_instants": len(cell["instants"]),
                "unchanged_quote_rows": cell["unchanged"],
                "spread_quantiles": _quantiles(cell["spreads"]),
                "candle_volume": str(cell["volume"]),
                "trades": cell["trades"],
            }
        )
    return table


def trade_activity(
    windows: Mapping[str, MarketWindow], trades: Mapping[str, Sequence[Trade]]
) -> dict[str, object]:
    """Trades per market, per remaining-time band, and seconds from last trade to close."""
    per_market: list[Decimal] = []
    last_gap: list[Decimal] = []
    by_band: Counter[str] = Counter()
    inactive_minutes = 0
    life_minutes = 0
    blocks = 0
    for ticker, window in windows.items():
        rows = [t for t in trades.get(ticker, ()) if window.open_ts <= t.time <= window.close_ts]
        per_market.append(Decimal(len(rows)))
        blocks += sum(1 for t in rows if t.is_block)
        for trade in rows:
            by_band[time_band(window.close_ts - trade.time)] += 1
        if rows:
            gap = window.close_ts - max(t.time for t in rows)
            last_gap.append(Decimal(round(gap * 1000)) / 1000)
        minutes = max(0, round((window.close_ts - window.open_ts) / 60))
        active = {int((window.close_ts - t.time) // 60) for t in rows}
        life_minutes += minutes
        inactive_minutes += max(0, minutes - len(active))
    return {
        "markets": len(windows),
        "trades_per_market": _quantiles(per_market),
        "trades_by_time_band": {b: by_band.get(b, 0) for b in TIME_BANDS},
        "block_trades": blocks,
        "seconds_last_trade_before_close": _quantiles(last_gap),
        "markets_without_trades": sum(1 for n in per_market if n == 0),
        "inactive_minute_fraction": (
            None if life_minutes == 0 else round(inactive_minutes / life_minutes, 4)
        ),
    }


# ---------------------------------------------------------------- reconciliation

CONVENTIONS: Final = ("end_inclusive", "end_exclusive")
OFFSETS: Final = (-60, 0, 60)


def _bucket(time: float, convention: str, offset: int) -> int:
    """The candle ``end_period_ts`` a trade at ``time`` belongs to, under a convention.

    end_inclusive: a bar ending at E covers (E-60, E]; end_exclusive: [E-60, E).
    """
    end = -(-time // 60) * 60 if convention == "end_inclusive" else time // 60 * 60 + 60
    return int(end) + offset


def reconcile(
    candles: Mapping[str, Sequence[Candle]],
    trades: Mapping[str, Sequence[Trade]],
    *,
    include_block: bool = True,
) -> list[dict[str, object]]:
    """Compare per-minute trade aggregates with candle volume and price OHLC.

    Each (convention, offset) is reported, so a boundary or off-by-one-minute convention is
    visible rather than chosen silently. Only minutes with candle volume or trades count.
    """
    results: list[dict[str, object]] = []
    for convention in CONVENTIONS:
        for offset in OFFSETS:
            stats: Counter[str] = Counter()
            abs_error = ZERO
            candle_volume = ZERO
            for ticker, bars in candles.items():
                buckets: dict[int, list[Trade]] = defaultdict(list)
                for trade in sorted(trades.get(ticker, ()), key=lambda t: (t.time, t.trade_id)):
                    if include_block or not trade.is_block:
                        buckets[_bucket(trade.time, convention, offset)].append(trade)
                seen: set[int] = set()
                for bar in bars:
                    seen.add(bar.end_ts)
                    group = buckets.get(bar.end_ts, [])
                    volume = sum((t.count for t in group), ZERO)
                    if bar.volume is None:
                        stats["candle_volume_null"] += 1
                        continue
                    if bar.volume == ZERO and not group:
                        continue
                    stats["minutes_compared"] += 1
                    candle_volume += bar.volume
                    abs_error += abs(bar.volume - volume)
                    stats["volume_exact" if bar.volume == volume else "volume_mismatch"] += 1
                    if group:
                        prices = [t.yes_price for t in group]
                        checks = {
                            "open": (bar.price_open, prices[0]),
                            "close": (bar.price_close, prices[-1]),
                            "high": (bar.price_high, max(prices)),
                            "low": (bar.price_low, min(prices)),
                        }
                        for part, (candle_price, trade_price) in checks.items():
                            if candle_price is not None:
                                same = candle_price == trade_price
                                stats[f"price_{part}_{'exact' if same else 'mismatch'}"] += 1
                orphan = [e for e in buckets if e not in seen]
                stats["trade_minutes_without_candle"] += len(orphan)
            results.append(
                {
                    "convention": convention,
                    "offset_seconds": offset,
                    "include_block_trades": include_block,
                    **dict(sorted(stats.items())),
                    "candle_volume_total": str(candle_volume),
                    "abs_volume_error_total": str(abs_error),
                    "relative_volume_error": (
                        None if candle_volume == ZERO else str(round(abs_error / candle_volume, 6))
                    ),
                }
            )
    return results


# ---------------------------------------------------------------- PMV 2.0 measurements
#
# Protocol P10 to P16 (research/kalshi/b12_btc_kalshi_pilot.md §5.4). Every table is a
# descriptive aggregate on the minute grid. None is an edge or profitability claim: the
# intra-minute executable path is unknown, a touch is not a fill, and no depth is known.


@dataclass(frozen=True)
class FeeScenario:
    """A labelled per-leg fee scenario: ``coefficient x P x (1 - P)`` per contract.

    A scenario, never the authoritative Kalshi schedule (DR-9). No rounding is applied:
    the documented rounding rules are not verified at one-contract size
    (research/kalshi/api_documentation_findings.md §3.8).
    """

    name: str
    coefficient: Decimal

    def fee(self, price: Decimal) -> Decimal:
        return self.coefficient * price * (ONE - price)


SPREAD_ONLY: Final = FeeScenario("spread_only", ZERO)
_SCENARIO_NAME: Final = re.compile(r"[a-z0-9_]{1,40}")


def parse_fee_scenario(text: str) -> FeeScenario:
    """``NAME=COEFFICIENT``, with a coefficient in [0, 1] (for example ``s1=0.035``)."""
    name, separator, raw = text.partition("=")
    value = parse_decimal(raw)
    if not separator or not _SCENARIO_NAME.fullmatch(name) or value is None:
        raise ValueError(f"fee scenario must be NAME=COEFFICIENT, got {text!r}")
    if not ZERO <= value <= ONE:
        raise ValueError(f"fee coefficient must be in [0, 1], got {raw!r}")
    return FeeScenario(name, value)


def _two_sided(candle: Candle) -> tuple[str, tuple[Decimal, Decimal] | None]:
    """The minute-boundary quote state: two-sided (usable bid < ask), one-sided or empty,
    or crossed/locked (bid >= ask, counted, never repaired)."""
    bid, ask = candle.yes_bid_close, candle.yes_ask_close
    if bid is None or ask is None or not _usable(bid) or not _usable(ask):
        return "one_sided_or_empty", None
    if bid >= ask:
        return "crossed_or_locked", None
    return "two_sided", (bid, ask)


def _in_window(window: MarketWindow, candles: Iterable[Candle]) -> list[Candle]:
    return sorted(
        (c for c in candles if window.open_ts < c.end_ts <= window.close_ts),
        key=lambda c: c.end_ts,
    )


def _share(part: int, whole: int) -> float | None:
    return None if whole == 0 else round(part / whole, 4)


def _seconds(value: float) -> Decimal:
    return Decimal(round(value * 1000)) / 1000


def spread_table(
    windows: Mapping[str, MarketWindow], candles: Mapping[str, Sequence[Candle]]
) -> dict[str, object]:
    """P10: minute-boundary spread by remaining-time band x YES-mid price band."""
    states: Counter[str] = Counter()
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for ticker, window in windows.items():
        for candle in _in_window(window, candles.get(ticker, ())):
            state, quote = _two_sided(candle)
            states[state] += 1
            if quote is None:
                continue
            bid, ask = quote
            key = (full_time_band(window.close_ts - candle.end_ts), price_band((bid + ask) / 2))
            cell = cells.setdefault(
                key, {"rows": 0, "contracts": set(), "instants": set(), "spreads": []}
            )
            cell["rows"] += 1
            cell["contracts"].add(ticker)
            cell["instants"].add(window.close_ts)
            cell["spreads"].append(ask - bid)
    table = [
        {
            "time_band": band,
            "mid_band": mid_band,
            "rows": cell["rows"],
            "contracts": len(cell["contracts"]),
            "settlement_instants": len(cell["instants"]),
            "spread_quantiles": _quantiles(cell["spreads"]),
            "rows_spread_le_0.01": sum(1 for s in cell["spreads"] if s <= Decimal("0.01")),
            "rows_spread_le_0.02": sum(1 for s in cell["spreads"] if s <= Decimal("0.02")),
        }
        for (band, mid_band), cell in sorted(cells.items())
    ]
    return {"quote_states": dict(sorted(states.items())), "cells": table}


def quote_staleness_table(
    windows: Mapping[str, MarketWindow], candles: Mapping[str, Sequence[Candle]]
) -> list[dict[str, object]]:
    """P11: share of adjacent minutes with an unchanged close quote, and with a zero
    bid and ask OHLC range, by remaining-time band x YES-mid band of the later minute."""
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    for ticker, window in windows.items():
        for prev, cur in pairwise(_in_window(window, candles.get(ticker, ()))):
            if cur.end_ts - prev.end_ts != 60:
                continue  # a missing minute is reported by candle_coverage, not bridged
            _, quote = _two_sided(cur)
            mid_band = (
                "no_two_sided_quote" if quote is None else price_band((quote[0] + quote[1]) / 2)
            )
            key = (full_time_band(window.close_ts - cur.end_ts), mid_band)
            cell = cells.setdefault(
                key,
                {"pairs": 0, "contracts": set(), "unchanged": 0, "quiet": 0, "flat": 0, "known": 0},
            )
            cell["pairs"] += 1
            cell["contracts"].add(ticker)
            same = (prev.yes_bid_close, prev.yes_ask_close) == (
                cur.yes_bid_close,
                cur.yes_ask_close,
            )
            cell["unchanged"] += int(same)
            cell["quiet"] += int(same and cur.volume in (None, ZERO))
            ranges = (cur.yes_bid_high, cur.yes_bid_low, cur.yes_ask_high, cur.yes_ask_low)
            if all(r is not None for r in ranges):
                cell["known"] += 1
                bid_flat = cur.yes_bid_high == cur.yes_bid_low
                ask_flat = cur.yes_ask_high == cur.yes_ask_low
                cell["flat"] += int(bid_flat and ask_flat)
    return [
        {
            "time_band": band,
            "mid_band": mid_band,
            "adjacent_minute_pairs": cell["pairs"],
            "contracts": len(cell["contracts"]),
            "unchanged_close_quote_share": _share(cell["unchanged"], cell["pairs"]),
            "unchanged_close_quote_no_volume_share": _share(cell["quiet"], cell["pairs"]),
            "zero_bid_and_ask_range_share": _share(cell["flat"], cell["known"]),
            "minutes_with_known_range": cell["known"],
        }
        for (band, mid_band), cell in sorted(cells.items())
    ]


_BAND_REMAINING: Final = {
    "<=1m": (0.0, 60.0),
    ">1-2m": (60.0, 120.0),
    ">2-3m": (120.0, 180.0),
    ">3-5m": (180.0, 300.0),
    ">5-10m": (300.0, 600.0),
    ">10m": (600.0, float("inf")),
}


def trade_arrival(
    windows: Mapping[str, MarketWindow], trades: Mapping[str, Sequence[Trade]]
) -> dict[str, object]:
    """P12: trades per contract-minute and inter-trade gaps by remaining-time band, plus
    the block-trade share. A gap is assigned to the band of the later trade."""
    acc: dict[str, dict[str, Any]] = {
        band: {"trades": 0, "blocks": 0, "contracts": set(), "seconds": 0.0, "gaps": []}
        for band in _BAND_REMAINING
    }
    for ticker, window in windows.items():
        life = window.close_ts - window.open_ts
        for band, (low, high) in _BAND_REMAINING.items():
            acc[band]["seconds"] += max(0.0, min(high, life) - low)
        rows = sorted(
            (t for t in trades.get(ticker, ()) if window.open_ts <= t.time <= window.close_ts),
            key=lambda t: (t.time, t.trade_id),
        )
        previous: Trade | None = None
        for trade in rows:
            band = full_time_band(window.close_ts - trade.time)
            if band == "post_close":  # a trade exactly at close_time
                band = "<=1m"
            cell = acc[band]
            cell["trades"] += 1
            cell["blocks"] += int(trade.is_block)
            cell["contracts"].add(ticker)
            if previous is not None:
                cell["gaps"].append(_seconds(trade.time - previous.time))
            previous = trade
    return {
        band: {
            "trades": cell["trades"],
            "block_trades": cell["blocks"],
            "block_share": _share(cell["blocks"], cell["trades"]),
            "contracts_with_trades": len(cell["contracts"]),
            "contract_minutes": round(cell["seconds"] / 60, 2),
            "trades_per_contract_minute": (
                None if cell["seconds"] == 0 else round(cell["trades"] / (cell["seconds"] / 60), 4)
            ),
            "inter_trade_gap_seconds": _quantiles(cell["gaps"]),
        }
        for band, cell in acc.items()
    }


def trade_timestamps(trades_raw: Mapping[str, Sequence[Mapping[str, object]]]) -> dict[str, object]:
    """P13: ``created_time`` precision, same-timestamp multi-print frequency, and the
    population of ``taker_outcome_side`` by UTC month of the trade.

    ``whole_minute_share`` is the share of parsed times that fall exactly on a minute. It is
    about 1/60 for whole-second stamps of continuous arrivals; a much larger share means
    the stamps are coarser than one second (stop condition S-2).

    Formatting is not resolution: ``12:00:01.000`` has fractional digits but no sub-second
    information. ``fraction_class`` therefore separates stamps with no fractional part,
    with an all-zero fractional part, and with a non-zero one. For non-zero fractions,
    ``nonzero_fraction_significant_digits`` counts the digits left after trailing zeros
    are stripped (``.100`` -> 1, a 100 ms grid; ``.123456`` -> 6). ``same_timestamp_cluster
    sizes`` gives the size distribution of groups of prints sharing an identical stamp
    within one market. ``observed_resolution`` summarizes all of this (see
    ``_resolution_class``)."""
    digits: Counter[int] = Counter()
    classes: Counter[str] = Counter()
    significant: Counter[int] = Counter()
    clusters: Counter[int] = Counter()
    whole_minute = 0
    by_month: dict[str, Counter[str]] = defaultdict(Counter)
    unparsed = 0
    groups = 0
    grouped_prints = 0
    for rows in trades_raw.values():
        stamps: Counter[str] = Counter()
        for row in rows:
            raw = row.get("created_time")
            parsed = parse_rfc3339(raw)
            if parsed is None or not isinstance(raw, str):
                unparsed += 1
                continue
            digits[parsed[1]] += 1
            match = _RFC3339.fullmatch(raw)
            fraction = (match.group(3) if match else None) or ""
            if not fraction:
                classes["no_fraction"] += 1
            elif not fraction.strip("0"):
                classes["fraction_all_zero"] += 1
            else:
                classes["fraction_nonzero"] += 1
                significant[len(fraction.rstrip("0"))] += 1
            whole_minute += int(parsed[0].second == 0 and parsed[0].microsecond == 0)
            stamps[raw] += 1
            side = row.get("taker_outcome_side")
            state = (
                "absent_or_null"
                if side is None
                else (str(side) if side in ("yes", "no") else "invalid")
            )
            by_month[parsed[0].strftime("%Y-%m")][state] += 1
        multi = [n for n in stamps.values() if n > 1]
        groups += len(multi)
        grouped_prints += sum(multi)
        clusters.update(multi)
    parsed_total = sum(digits.values())
    whole_minute_share = _share(whole_minute, parsed_total)
    nonzero_share = _share(classes["fraction_nonzero"], parsed_total)
    return {
        "created_time_fraction_digits": {str(k): v for k, v in sorted(digits.items())},
        "created_time_unparsed": unparsed,
        "fraction_class": {
            k: classes[k] for k in ("no_fraction", "fraction_all_zero", "fraction_nonzero")
        },
        "nonzero_fraction_share": nonzero_share,
        "nonzero_fraction_significant_digits": {str(k): v for k, v in sorted(significant.items())},
        "observed_resolution": _resolution_class(nonzero_share, whole_minute_share),
        "whole_minute_share": whole_minute_share,
        "same_timestamp_cluster_sizes": {str(k): v for k, v in sorted(clusters.items())},
        "same_timestamp_groups": groups,
        "prints_in_same_timestamp_groups": grouped_prints,
        "taker_outcome_side_by_month": {
            m: dict(sorted(c.items())) for m, c in sorted(by_month.items())
        },
    }


# Pre-registered resolution thresholds (protocol §5.4, P13; development hypotheses).
RESOLUTION_SUBSECOND_MIN_NONZERO: Final = 0.50
RESOLUTION_WHOLE_SECOND_MAX_NONZERO: Final = 0.01


def _resolution_class(nonzero_share: float | None, whole_minute_share: float | None) -> str:
    """The timing resolution actually observed, not the formatting.

    - ``coarser_than_second``: at least half the stamps fall exactly on a minute;
    - ``sub_second``: at least half the stamps carry a non-zero fraction (genuinely
      sub-second stamps of continuous arrivals are almost never exactly whole seconds);
    - ``whole_second``: under 1% carry a non-zero fraction, however many digits are shown;
    - ``mixed``: anything in between, which the owner reviews (S-2 UNDETERMINED);
    - ``unknown``: no parsed stamp.
    """
    if nonzero_share is None or whole_minute_share is None:
        return "unknown"
    if whole_minute_share >= S2_MAX_WHOLE_MINUTE_SHARE:
        return "coarser_than_second"
    if nonzero_share >= RESOLUTION_SUBSECOND_MIN_NONZERO:
        return "sub_second"
    if nonzero_share < RESOLUTION_WHOLE_SECOND_MAX_NONZERO:
        return "whole_second"
    return "mixed"


def print_dispersion(
    windows: Mapping[str, MarketWindow], trades: Mapping[str, Sequence[Trade]]
) -> dict[str, object]:
    """P14: print-to-print price change and gap for consecutive non-block prints less than
    60 s apart, by remaining-time band of the later print. Block trades are negotiated
    and excluded (counted). Same-timestamp pairs are counted separately."""
    acc: dict[str, dict[str, Any]] = defaultdict(lambda: {"moves": [], "gaps": []})
    same_time = 0
    blocks = 0
    minutes_with_prints = 0
    minutes_multi = 0
    for ticker, window in windows.items():
        rows = sorted(
            (t for t in trades.get(ticker, ()) if window.open_ts <= t.time <= window.close_ts),
            key=lambda t: (t.time, t.trade_id),
        )
        blocks += sum(1 for t in rows if t.is_block)
        rows = [t for t in rows if not t.is_block]
        per_minute = Counter(-(-int(t.time) // 60) for t in rows)
        minutes_with_prints += len(per_minute)
        minutes_multi += sum(1 for n in per_minute.values() if n > 1)
        for prev, cur in pairwise(rows):
            gap = cur.time - prev.time
            if gap == 0:
                same_time += 1
            elif gap < 60:
                band = full_time_band(window.close_ts - cur.time)
                band = "<=1m" if band == "post_close" else band
                acc[band]["moves"].append(abs(cur.yes_price - prev.yes_price))
                acc[band]["gaps"].append(_seconds(gap))
    return {
        "block_trades_excluded": blocks,
        "same_timestamp_pairs": same_time,
        "minutes_with_prints": minutes_with_prints,
        "minutes_with_two_or_more_prints_share": _share(minutes_multi, minutes_with_prints),
        "by_time_band": {
            band: {
                "pairs": len(acc[band]["moves"]),
                "abs_price_change": _quantiles(acc[band]["moves"]),
                "gap_seconds": _quantiles(acc[band]["gaps"]),
            }
            for band in _BAND_REMAINING
            if band in acc
        },
    }


def cost_hurdle_table(
    windows: Mapping[str, MarketWindow],
    candles: Mapping[str, Sequence[Candle]],
    scenarios: Sequence[FeeScenario],
    horizons: Sequence[int] = HORIZONS_SECONDS,
) -> dict[str, object]:
    """P15: the cost-hurdle / perfect-foresight ceiling on the minute grid.

    Decision point: an in-window minute boundary E with a two-sided quote. For horizon h
    the exit quote is the boundary E + h, which must lie inside the window (a horizon that
    crosses close_time is counted, never scored, because settlement is not an exit).

    - close-to-close: YES = bid(E+h) - ask(E); NO = bid(E) - ask(E+h) (a NO bid at Y is a
      YES ask at 1 - Y); minus the scenario fee on both legs at each leg's price.
    - generous: as close-to-close, but the exit uses the best bid high (YES) or ask low
      (NO) over the bars in (E, E+h], an intra-minute extreme of unknown size and timing.
    - mid diagnostic: |mid(E+h) - mid(E)| > spread(E) + 2 x fee(mid(E)).

    Perfect foresight takes the better side. A positive ceiling is necessary, never
    sufficient: it ignores latency, depth, queue position, and adverse selection.
    """
    names = [s.name for s in scenarios]
    if len(set(names)) != len(names) or not scenarios:
        raise ValueError("fee scenarios must be non-empty with unique names")
    counts: Counter[str] = Counter()
    cells: dict[tuple[int, str, str], dict[str, Any]] = {}
    for ticker, window in windows.items():
        bars: dict[int, Candle] = {}
        for candle in _in_window(window, candles.get(ticker, ())):
            if candle.end_ts in bars:
                counts["duplicate_end_ts_ignored"] += 1
                continue
            bars[candle.end_ts] = candle
        for end, candle in bars.items():
            _, entry = _two_sided(candle)
            if entry is None:
                continue
            bid_e, ask_e = entry
            for horizon in horizons:
                exit_end = end + horizon
                if exit_end > window.close_ts:
                    counts[f"h{horizon}_crosses_close"] += 1
                    continue
                exit_bar = bars.get(exit_end)
                exit_quote = None if exit_bar is None else _two_sided(exit_bar)[1]
                if exit_quote is None:
                    counts[f"h{horizon}_exit_quote_unavailable"] += 1
                    continue
                bid_x, ask_x = exit_quote
                path = [bars[t] for t in range(end + 60, exit_end + 1, 60) if t in bars]
                highs = [b.yes_bid_high for b in path if _usable(b.yes_bid_high)]
                lows = [b.yes_ask_low for b in path if _usable(b.yes_ask_low)]
                best_bid = max([bid_x, *[h for h in highs if h is not None]])
                best_ask = min([ask_x, *[low for low in lows if low is not None]])
                mid_e, mid_x = (bid_e + ask_e) / 2, (bid_x + ask_x) / 2
                key = (horizon, full_time_band(window.close_ts - end), price_band(mid_e))
                cell = cells.setdefault(
                    key,
                    {
                        "points": 0,
                        "contracts": set(),
                        "instants": set(),
                        "by": {
                            s.name: {"close": 0, "generous": 0, "mid": 0, "nets": [], "won": set()}
                            for s in scenarios
                        },
                    },
                )
                cell["points"] += 1
                cell["contracts"].add(ticker)
                cell["instants"].add(window.close_ts)
                for scenario in scenarios:
                    fee = scenario.fee
                    yes_net = bid_x - ask_e - fee(ask_e) - fee(bid_x)
                    no_net = bid_e - ask_x - fee(ONE - bid_e) - fee(ONE - ask_x)
                    yes_gen = best_bid - ask_e - fee(ask_e) - fee(best_bid)
                    no_gen = bid_e - best_ask - fee(ONE - bid_e) - fee(ONE - best_ask)
                    best, generous = max(yes_net, no_net), max(yes_gen, no_gen)
                    mid_cost = (ask_e - bid_e) + 2 * fee(mid_e)
                    tally = cell["by"][scenario.name]
                    tally["close"] += int(best > 0)
                    tally["generous"] += int(generous > 0)
                    tally["mid"] += int(abs(mid_x - mid_e) > mid_cost)
                    tally["nets"].append(best)
                    if generous > 0:
                        tally["won"].add(ticker)
    table = []
    for (horizon, band, mid_band), cell in sorted(cells.items()):
        points = cell["points"]
        table.append(
            {
                "horizon_seconds": horizon,
                "time_band": band,
                "mid_band": mid_band,
                "decision_points": points,
                "contracts": len(cell["contracts"]),
                "settlement_instants": len(cell["instants"]),
                "scenarios": {
                    name: {
                        "close_to_close_positive_share": _share(t["close"], points),
                        "generous_positive_share": _share(t["generous"], points),
                        "mid_move_exceeds_cost_share": _share(t["mid"], points),
                        "contracts_with_generous_positive": len(t["won"]),
                        "best_close_to_close_net": _quantiles(t["nets"]),
                    }
                    for name, t in cell["by"].items()
                },
            }
        )
    return {
        "fee_scenarios": {
            s.name: {"coefficient": str(s.coefficient), "status": "SCENARIO_NOT_AUTHORITATIVE"}
            for s in scenarios
        },
        "horizons_seconds": list(horizons),
        "counts": dict(sorted(counts.items())),
        "cells": table,
    }


def lead_lag_measurability(
    windows: Mapping[str, MarketWindow],
    trades: Mapping[str, Sequence[Trade]],
    timestamps: Mapping[str, Any],
    late_seconds: int = 300,
) -> dict[str, object]:
    """P16a: Kalshi-side measurability of a lead/lag estimate from trade prints.

    Uses the **observed** timing resolution from P13 (never the digit count alone) and the
    dispersion of events: over the last ``late_seconds`` of each contract, the share of
    whole seconds with at least one non-block print, the share of distinct non-block print
    times among non-block prints (identical stamps carry no ordering information), and the
    inter-print gaps. The smallest lag a historical estimate could resolve is 0 s for
    ``sub_second`` stamps and 2 s for ``whole_second`` stamps (two-second granularity is
    the minimum that separates a lead from a same-second print); it is undefined
    otherwise. The aligned Kraken cross-correlation (P16b) needs Kraken trades and is not
    computed here.
    """
    resolution = str(timestamps.get("observed_resolution", "unknown"))
    late_prints = 0
    distinct_late_times = 0
    seconds_with_print = 0
    seconds_observed = 0
    gaps: list[Decimal] = []
    for ticker, window in windows.items():
        start = max(window.open_ts, window.close_ts - late_seconds)
        rows = sorted(
            t.time
            for t in trades.get(ticker, ())
            if not t.is_block and start < t.time <= window.close_ts
        )
        seconds_observed += round(window.close_ts - start)
        seconds_with_print += len({int(-(-t // 1)) for t in rows})
        late_prints += len(rows)
        distinct_late_times += len(set(rows))
        gaps.extend(_seconds(b - a) for a, b in pairwise(rows))
    return {
        "observed_resolution": resolution,
        "nonzero_fraction_share": timestamps.get("nonzero_fraction_share"),
        "minimum_resolvable_lag_seconds": {"sub_second": 0, "whole_second": 2}.get(resolution),
        "late_window_seconds": late_seconds,
        "late_window_prints": late_prints,
        "late_window_distinct_time_share": _share(distinct_late_times, late_prints),
        "late_window_seconds_with_print_share": _share(seconds_with_print, seconds_observed),
        "late_window_inter_print_gap_seconds": _quantiles(gaps),
        "kraken_alignment": "NOT_COMPUTED: P16b needs the DR-3 Kraken archive file",
    }


_PAUSE_ZONE: Final = "America/New_York"


def _pause_overlap(window: MarketWindow, zone: ZoneInfo) -> tuple[float, float] | None:
    """The overlap of a market window with the documented Thursday 03:00-05:00 ET
    trading pause (research/kalshi/api_documentation_findings.md §8), if any."""
    opened = datetime.fromtimestamp(window.open_ts, zone)
    closed = datetime.fromtimestamp(window.close_ts, zone)
    day = opened.date() - timedelta(days=1)
    while day <= closed.date():
        if day.weekday() == 3:
            start = datetime(day.year, day.month, day.day, 3, tzinfo=zone).timestamp()
            end = datetime(day.year, day.month, day.day, 5, tzinfo=zone).timestamp()
            low, high = max(start, window.open_ts), min(end, window.close_ts)
            if low < high:
                return low, high
        day += timedelta(days=1)
    return None


def lifecycle_incidence(
    markets: Sequence[Mapping[str, object]],
    windows: Mapping[str, MarketWindow],
    candles: Mapping[str, Sequence[Candle]],
    trades: Mapping[str, Sequence[Trade]],
) -> dict[str, object]:
    """Early-close and pause incidence: window durations, close times off the 15-minute
    grid or different from ``expected_expiration_time``, and overlaps with the documented
    Thursday pause, with the candles and trades seen inside each overlap."""
    durations: Counter[str] = Counter()
    checks: Counter[str] = Counter()
    for market in markets:
        window = windows.get(str(market.get("ticker")))
        if window is None:
            continue
        durations[str(round(window.close_ts - window.open_ts))] += 1
        checks["close_on_15_minute_grid" if window.close_ts % 900 == 0 else "close_off_grid"] += 1
        expected = parse_rfc3339(market.get("expected_expiration_time"))
        if expected is None:
            checks["expected_expiration_unparsed_or_absent"] += 1
        elif _epoch(expected[0]) == window.close_ts:
            checks["close_equals_expected_expiration"] += 1
        else:
            checks["close_differs_from_expected_expiration"] += 1
        if market.get("can_close_early") is True:
            checks["can_close_early_true"] += 1
    pause: dict[str, object]
    try:
        zone = ZoneInfo(_PAUSE_ZONE)
    except ZoneInfoNotFoundError:
        pause = {"status": "UNAVAILABLE: no time-zone database"}
    else:
        overlapping = []
        for ticker, window in sorted(windows.items()):
            overlap = _pause_overlap(window, zone)
            if overlap is None:
                continue
            low, high = overlap
            overlapping.append(
                {
                    "overlap_minutes": round((high - low) / 60, 2),
                    "candles_in_overlap": sum(
                        1 for c in candles.get(ticker, ()) if low < c.end_ts <= high
                    ),
                    "trades_in_overlap": sum(
                        1 for t in trades.get(ticker, ()) if low < t.time <= high
                    ),
                }
            )
        pause = {
            "zone": _PAUSE_ZONE,
            "markets_overlapping": len(overlapping),
            "overlaps": overlapping,
        }
    return {
        "window_duration_seconds": dict(sorted(durations.items())),
        "checks": dict(sorted(checks.items())),
        "thursday_pause": pause,
    }


# ---------------------------------------------------------------- stop-condition screen

# Pre-registered thresholds (protocol §5.6, 2026-10-20). Development hypotheses, amendable by
# the owner only before the pilot runs.
LIQUID_MIN_CONTRACTS: Final = 3
LIQUID_MIN_POINTS: Final = 20
LIQUID_MIN_TRADES_PER_CONTRACT_MINUTE: Final = 1.0
LIQUID_MAX_UNCHANGED_SHARE: Final = 0.80
S1_MIN_GENEROUS_SHARE: Final = 0.05
S2_MAX_WHOLE_MINUTE_SHARE: Final = 0.50
S2_MIN_LATE_SECONDS_WITH_PRINT: Final = 0.05
S1_FAILED: Final = "HISTORICAL COST-HURDLE SCREEN FAILED — OWNER NO-GO REVIEW REQUIRED"
S1_PASSED: Final = "SCREEN NOT FAILED — NOT EVIDENCE OF EDGE; OWNER APPROVAL STILL REQUIRED"


def stop_screen(
    staleness: Sequence[Mapping[str, Any]],
    arrival: Mapping[str, Any],
    timestamps: Mapping[str, Any],
    hurdle: Mapping[str, Any],
    measurability: Mapping[str, Any],
    scenario: str = SPREAD_ONLY.name,
) -> dict[str, object]:
    """The mechanical part of stop conditions S-1, S-2, and S-3 (protocol §5.6).

    S-4, S-5, and S-6 rest on label, metadata, terms, and fee checks that are evaluated
    from P1-P9 and the owner's documents; they are reported as ``MANUAL``. The scenario
    is ``spread_only`` for S-1a, or the authoritative DR-9 schedule for S-1b.
    """
    unchanged = {(c["time_band"], c["mid_band"]): c for c in staleness}
    liquid: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for cell in hurdle["cells"]:
        key = (cell["time_band"], cell["mid_band"])
        rate = arrival.get(cell["time_band"], {}).get("trades_per_contract_minute")
        share = unchanged.get(key, {}).get("unchanged_close_quote_share")
        failed = [
            reason
            for reason, bad in (
                ("contracts", cell["contracts"] < LIQUID_MIN_CONTRACTS),
                ("decision_points", cell["decision_points"] < LIQUID_MIN_POINTS),
                ("trade_rate", rate is None or rate < LIQUID_MIN_TRADES_PER_CONTRACT_MINUTE),
                ("unchanged_quotes", share is None or share > LIQUID_MAX_UNCHANGED_SHARE),
            )
            if bad
        ]
        summary = {
            "horizon_seconds": cell["horizon_seconds"],
            "time_band": key[0],
            "mid_band": key[1],
            "generous_positive_share": cell["scenarios"][scenario]["generous_positive_share"],
        }
        if failed:
            removed.append({**summary, "failed": failed})
        else:
            liquid.append(summary)
    cleared = [c for c in liquid if (c["generous_positive_share"] or 0) >= S1_MIN_GENEROUS_SHARE]
    # S-1 never advances automatically to prospective capture, and never terminates PMV 2.0
    # by itself: a failure is strong negative evidence that goes to an owner NO-GO review.
    s1_reason: str | None = None
    if not liquid:
        s1, s1_reason = S1_FAILED, "no_liquid_cell"
    elif not cleared:
        s1, s1_reason = S1_FAILED, "generous_ceiling_below_threshold_in_every_liquid_cell"
    else:
        s1 = S1_PASSED
    resolution = timestamps.get("observed_resolution", "unknown")
    late = measurability.get("late_window_seconds_with_print_share")
    if resolution == "coarser_than_second" or (
        late is not None and late < S2_MIN_LATE_SECONDS_WITH_PRINT
    ):
        s2 = "STOP_HISTORICAL_LEAD_LAG"
    elif resolution in ("mixed", "unknown") or late is None:
        s2 = "UNDETERMINED"
    else:
        s2 = "CONTINUE"
    return {
        "scenario": scenario,
        "thresholds": {
            "liquid_min_contracts": LIQUID_MIN_CONTRACTS,
            "liquid_min_decision_points": LIQUID_MIN_POINTS,
            "liquid_min_trades_per_contract_minute": LIQUID_MIN_TRADES_PER_CONTRACT_MINUTE,
            "liquid_max_unchanged_share": LIQUID_MAX_UNCHANGED_SHARE,
            "s1_min_generous_share": S1_MIN_GENEROUS_SHARE,
            "s2_max_whole_minute_share": S2_MAX_WHOLE_MINUTE_SHARE,
            "s2_min_late_seconds_with_print": S2_MIN_LATE_SECONDS_WITH_PRINT,
        },
        "s1": s1,
        "s1_reason": s1_reason,
        "s1_liquid_cells": liquid,
        "s2": s2,
        "s3_removed_cells": removed,
        "s4_s5_s6": "MANUAL: P1-P9, terms (AR-B12-2), and the DR-9 fee schedule",
    }


# ---------------------------------------------------------------- old-strategy control

_Z95: Final = 1.959964


def _wilson(wins: int, n: int) -> list[float] | None:
    if n == 0:
        return None
    p = wins / n
    denominator = 1 + _Z95**2 / n
    centre = (p + _Z95**2 / (2 * n)) / denominator
    half = _Z95 * ((p * (1 - p) / n + _Z95**2 / (4 * n * n)) ** 0.5) / denominator
    return [round(centre - half, 4), round(centre + half, 4)]


def _day_block_interval(
    rows: Sequence[tuple[str, float, int]], resamples: int, seed: int
) -> list[float] | None:
    """A 95% percentile interval for (win frequency - mean ask), resampling whole UTC
    close dates with replacement. Deterministic for a given seed. None below 2 days."""
    by_day: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for day, ask, won in rows:
        by_day[day].append((ask, won))
    days = sorted(by_day)
    if len(days) < 2:
        return None
    rng = random.Random(seed)  # noqa: S311 - reproducible resampling, not security
    stats: list[float] = []
    for _ in range(resamples):
        sample = [item for _ in days for item in by_day[rng.choice(days)]]
        stats.append(
            sum(w for _, w in sample) / len(sample) - sum(a for a, _ in sample) / len(sample)
        )
    stats.sort()
    return [
        round(stats[int(0.025 * (resamples - 1))], 4),
        round(stats[int(0.975 * (resamples - 1))], 4),
    ]


def _tail_sides(candle: Candle) -> list[tuple[str, Decimal]]:
    """The sides whose executable ask at this minute is usable and at least 0.85."""
    bid = candle.yes_bid_close
    asks = {
        "yes": candle.yes_ask_close,
        "no": None if bid is None or not _usable(bid) else ONE - bid,
    }
    return [
        (side, ask)
        for side, ask in asks.items()
        if ask is not None and _usable(ask) and ask >= TAIL_FLOOR
    ]


def old_strategy_control(
    markets: Sequence[Mapping[str, object]],
    windows: Mapping[str, MarketWindow],
    candles: Mapping[str, Sequence[Candle]],
    scenarios: Sequence[FeeScenario],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, object]:
    """C1: market tail calibration of the old settlement strategy, as a nested control.

    Preregistered selection rule (amended 2026-10-20, before any data was seen): for each
    settled market with result yes or no and each remaining-time band up to 5 minutes, take
    the **earliest** in-window minute in that band at which either side's executable ask is
    usable and at least 0.85 (YES ask = ask close; NO ask = 1 - bid close). If both sides
    qualify in that same minute, take the side with the higher ask, and YES on a tie. That
    gives **at most one row per contract x band**, so no contract contributes two rows to
    any (band, ask band) cell, even when the price flips far enough for the other side to
    qualify later in the band. Such contracts are counted, and the later side is not used.
    The row wins when ``result`` equals the chosen side.

    Reported per (band, ask band): contracts, wins, mean ask, win frequency with a Wilson
    interval, the gap (win frequency - mean ask) with a day-block bootstrap interval, and
    the gap net of each fee scenario's mean fee. Descriptive only: at pilot scale every
    cell is far below the power needed for a calibration claim.
    """
    rows: dict[tuple[str, str], list[tuple[str, float, int, Decimal]]] = defaultdict(list)
    sides: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    excluded = 0
    same_minute_ties = 0
    other_side_later = 0
    bands = ("<=1m", ">1-2m", ">2-3m", ">3-5m")
    for market in markets:
        window = windows.get(str(market.get("ticker")))
        result = market.get("result")
        if window is None:
            continue
        if result not in ("yes", "no"):
            excluded += 1
            continue
        day = datetime.fromtimestamp(window.close_ts, UTC).date().isoformat()
        minutes = _in_window(window, candles.get(window.ticker, ()))
        for band in bands:
            chosen: tuple[str, Decimal] | None = None
            for candle in minutes:
                if time_band(window.close_ts - candle.end_ts) != band:
                    continue
                qualifying = _tail_sides(candle)
                if chosen is None and qualifying:
                    chosen = max(qualifying, key=lambda pair: (pair[1], pair[0] == "yes"))
                    if len(qualifying) == 2:
                        same_minute_ties += 1
                elif chosen is not None and any(side != chosen[0] for side, _ in qualifying):
                    other_side_later += 1
                    break
            if chosen is not None:
                side, ask = chosen
                rows[(band, ask_band(ask))].append((day, float(ask), int(result == side), ask))
                sides[(band, ask_band(ask))][side] += 1
    cells = []
    for (band, a_band), items in sorted(rows.items()):
        n = len(items)
        wins = sum(won for _, _, won, _ in items)
        mean_ask = sum((ask for _, _, _, ask in items), ZERO) / n
        frequency = Decimal(wins) / n
        cells.append(
            {
                "time_band": band,
                "ask_band": a_band,
                "contracts": n,
                "sides": dict(sorted(sides[(band, a_band)].items())),
                "distinct_close_dates": len({day for day, _, _, _ in items}),
                "wins": wins,
                "mean_ask": str(round(mean_ask, 4)),
                "win_frequency": str(round(frequency, 4)),
                "win_frequency_wilson95": _wilson(wins, n),
                "gap_frequency_minus_ask": str(round(frequency - mean_ask, 4)),
                "gap_day_block95": _day_block_interval(
                    [(d, a, w) for d, a, w, _ in items], resamples, seed
                ),
                "gap_net_of_mean_fee": {
                    s.name: str(
                        round(
                            frequency - mean_ask - sum((s.fee(a) for *_, a in items), ZERO) / n, 4
                        )
                    )
                    for s in scenarios
                },
            }
        )
    return {
        "status": "DESCRIPTIVE_ONLY",
        "selection_rule": (
            "earliest minute per contract x band where either side's ask >= 0.85; "
            "both in that minute: higher ask, YES on a tie; at most one row per contract x band"
        ),
        "markets_excluded_result_not_yes_no": excluded,
        "both_sides_qualified_same_minute": same_minute_ties,
        "other_side_qualified_later_in_band_not_used": other_side_later,
        "bootstrap": {"unit": "UTC close date", "resamples": resamples, "seed": seed},
        "cells": cells,
        "deferred": {
            "C2_b0_fair_value_vs_ask": "needs Kraken prices and a knowable strike (P5)",
            "C3_implied_vs_realized_volatility": "needs Kraken prices and a knowable strike (P5)",
        },
    }


# ---------------------------------------------------------------- loading and report


@dataclass(frozen=True)
class Pilot:
    markets: list[dict[str, Any]]
    candles_raw: dict[str, list[dict[str, Any]]]
    trades_raw: dict[str, list[dict[str, Any]]]
    trade_pages: dict[str, list[dict[str, object]]]
    other: dict[str, object]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PilotError(f"{path.name}: unreadable or not JSON ({type(error).__name__})") from None


def _wrapped_list(document: object, key: str, name: str) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or not isinstance(document.get(key), list):
        raise PilotError(f"{name}: expected an object with a '{key}' list")
    rows: list[dict[str, Any]] = document[key]
    if not all(isinstance(row, dict) for row in rows):
        raise PilotError(f"{name}: '{key}' holds a non-object row")
    return rows


def load_pilot(directory: Path) -> Pilot:
    """Load the raw layout written by the pilot sample tool (``markets/<ticker>/...``)."""
    root = directory / "markets"
    if not root.is_dir():
        raise PilotError("no markets/ directory")
    markets: list[dict[str, Any]] = []
    candles: dict[str, list[dict[str, Any]]] = {}
    trades: dict[str, list[dict[str, Any]]] = {}
    pages: dict[str, list[dict[str, object]]] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        market_doc = _read_json(folder / "market.json")
        if not isinstance(market_doc, dict) or not isinstance(market_doc.get("market"), dict):
            raise PilotError(f"{folder.name}/market.json: expected a 'market' object")
        market = market_doc["market"]
        markets.append(market)
        ticker = str(market.get("ticker"))
        candles[ticker] = _wrapped_list(
            _read_json(folder / "candles.json"), "candlesticks", f"{folder.name}/candles.json"
        )
        trades[ticker] = []
        pages[ticker] = []
        for page in sorted(folder.glob("trades_p*.json")):
            document = _read_json(page)
            rows = _wrapped_list(document, "trades", f"{folder.name}/{page.name}")
            trades[ticker].extend(rows)
            cursor = document.get("cursor")
            pages[ticker].append(
                {
                    "rows": len(rows),
                    "cursor": "null" if cursor is None else ("empty" if cursor == "" else "token"),
                }
            )
    other: dict[str, object] = {}
    for name in ("cutoff.json", "series.json", "fee_changes.json"):
        path = directory / name
        if path.is_file():
            other[name] = _read_json(path)
    return Pilot(markets, candles, trades, pages, other)


def build_report(
    pilot: Pilot, fee_scenarios: Sequence[FeeScenario] = (SPREAD_ONLY,)
) -> dict[str, object]:
    """The aggregate-only pilot report. ``spread_only`` is always the first scenario."""
    scenarios = [SPREAD_ONLY, *(s for s in fee_scenarios if s != SPREAD_ONLY)]
    windows: dict[str, MarketWindow] = {}
    unusable_markets = 0
    for market in pilot.markets:
        window = market_window(market)
        if window is None:
            unusable_markets += 1
        else:
            windows[window.ticker] = window
    candles: dict[str, list[Candle]] = {}
    trades: dict[str, list[Trade]] = {}
    malformed: Counter[str] = Counter()
    for ticker, rows in pilot.candles_raw.items():
        parsed_candles = [parse_candle(ticker, row) for row in rows]
        malformed["candles"] += sum(1 for c in parsed_candles if c is None)
        candles[ticker] = [c for c in parsed_candles if c is not None]
    trade_order: dict[str, object] = {}
    for ticker, rows in pilot.trades_raw.items():
        parsed_trades = [parse_trade(row) for row in rows]
        malformed["trades"] += sum(1 for t in parsed_trades if t is None)
        trades[ticker] = [t for t in parsed_trades if t is not None]
        times: list[float | None] = []
        for row in rows:
            parsed_time = parse_rfc3339(row.get("created_time"))
            times.append(None if parsed_time is None else _epoch(parsed_time[0]))
        trade_order[ticker] = order_and_duplicates([str(r.get("trade_id")) for r in rows], times)
    all_candle_rows = [row for rows in pilot.candles_raw.values() for row in rows]
    all_trade_rows = [row for rows in pilot.trades_raw.values() for row in rows]
    candle_order = {
        ticker: order_and_duplicates(
            [str(r.get("end_period_ts")) for r in rows],
            [
                float(r["end_period_ts"]) if isinstance(r.get("end_period_ts"), int) else None
                for r in rows
            ],
        )
        for ticker, rows in pilot.candles_raw.items()
    }
    closes = sorted(w.close_ts for w in windows.values())
    timestamps = trade_timestamps(pilot.trades_raw)
    staleness = quote_staleness_table(windows, candles)
    arrival = trade_arrival(windows, trades)
    hurdle = cost_hurdle_table(windows, candles, scenarios)
    measurability = lead_lag_measurability(windows, trades, timestamps)
    return {
        "report": "b12_kalshi_btc_pilot_profile",
        "report_version": 2,
        "protocol": "research/kalshi/b12_btc_kalshi_pilot.md §5 (P1-P16, C1)",
        "markets": len(pilot.markets),
        "markets_unusable_window": unusable_markets,
        "rows": {"candles": len(all_candle_rows), "trades": len(all_trade_rows)},
        "close_time_span_utc": (
            None
            if not closes
            else [
                datetime.fromtimestamp(closes[0], UTC).isoformat(),
                datetime.fromtimestamp(closes[-1], UTC).isoformat(),
            ]
        ),
        "distinct_close_dates_utc": len(
            {datetime.fromtimestamp(c, UTC).date().isoformat() for c in closes}
        ),
        "malformed": dict(malformed),
        "field_profile": {
            "market": field_profile(pilot.markets),
            "candle": field_profile(all_candle_rows),
            "trade": field_profile(all_trade_rows),
        },
        "trade_ordering": trade_order,
        "trade_pagination": pilot.trade_pages,
        "candle_ordering": candle_order,
        "label_integrity": label_integrity(pilot.markets),
        "candle_coverage": {
            t: candle_coverage(windows[t], candles.get(t, [])) for t in sorted(windows)
        },
        "late_window": late_window_table(windows, candles, trades),
        "trade_activity": trade_activity(windows, trades),
        "reconciliation": reconcile(candles, trades, include_block=True)
        + reconcile(candles, trades, include_block=False),
        "metadata_files_present": sorted(pilot.other),
        "p10_spread": spread_table(windows, candles),
        "p11_quote_staleness": staleness,
        "p12_trade_arrival": arrival,
        "p13_trade_timestamps": timestamps,
        "p14_print_dispersion": print_dispersion(windows, trades),
        "p15_cost_hurdle": hurdle,
        "p16a_lead_lag_measurability": measurability,
        "lifecycle_incidence": lifecycle_incidence(pilot.markets, windows, candles, trades),
        "c1_old_strategy_control": old_strategy_control(pilot.markets, windows, candles, scenarios),
        "stop_screen": stop_screen(staleness, arrival, timestamps, hurdle, measurability),
    }


def _show(pilot: Pilot, out: Any) -> None:
    """Head/tail raw rows for the operator's terminal only. Never written to Git."""
    for market in pilot.markets[:2]:
        ticker = str(market.get("ticker"))
        out.write(f"--- market {ticker}\n{json.dumps(market, indent=1, sort_keys=True)}\n")
        for name, rows in (
            ("candles", pilot.candles_raw.get(ticker, [])),
            ("trades", pilot.trades_raw.get(ticker, [])),
        ):
            out.write(f"--- {name} head(3)/tail(3) of {len(rows)}\n")
            for row in [*rows[:3], {"...": "..."}, *rows[-3:]]:
                out.write(json.dumps(row, sort_keys=True) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--show", action="store_true", help="print raw head/tail rows (terminal)")
    parser.add_argument(
        "--fee-scenario",
        action="append",
        default=[],
        type=_fee_scenario_arg,
        metavar="NAME=COEFFICIENT",
        help="an extra labelled fee scenario (never authoritative; DR-9); repeatable",
    )
    args = parser.parse_args(argv)
    try:
        pilot = load_pilot(args.directory)
    except PilotError as error:
        sys.stderr.write(f"kalshi_btc pilot: {error}\n")
        return 2
    names = [s.name for s in args.fee_scenario]
    if len(set(names)) != len(names) or SPREAD_ONLY.name in names:
        sys.stderr.write("kalshi_btc pilot: fee scenario names must be unique, not spread_only\n")
        return 2
    if args.show:
        _show(pilot, sys.stderr)
    report = build_report(pilot, args.fee_scenario)
    sys.stdout.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return 0


def _fee_scenario_arg(text: str) -> FeeScenario:
    try:
        return parse_fee_scenario(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


if __name__ == "__main__":
    raise SystemExit(main())
