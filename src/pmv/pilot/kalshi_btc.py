"""B12 Kalshi BTC 15-minute historical pilot: deterministic profiling of a bounded raw sample.

Development-time research code (owner B12 charter, 2026-10-19). It reads a raw pilot
directory written by ``research/data_sources/recon_tools/kalshi_pilot_sample.py`` and
produces a derived, aggregate-only JSON report:

- a native field profile per object (types, nulls, numeric strings, decimals, timestamp
  precision), with ordering, duplicate, and pagination checks;
- label integrity per settled market (result, settlement value, strike re-derivation);
- 1-minute candle coverage (missing minutes, null and sentinel quotes, unchanged quotes);
- the late-window table (remaining-time band x executable-ask band, YES and NO sides);
- trade activity by remaining-time band;
- trade <-> candle minute reconciliation under each boundary convention and offset.

Nothing here decides a trade or produces a feature. Settlement and result fields are read
only to check label integrity; they are never inputs to anything else. Observations within
one contract are not independent: every table reports distinct contracts and distinct
settlement instants next to row counts.

Parsing is strict and fail-visible: a value that cannot be parsed is counted as
malformed, never repaired or dropped silently.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

__all__ = [
    "ASK_BANDS",
    "TIME_BANDS",
    "Candle",
    "PilotError",
    "Trade",
    "ask_band",
    "build_report",
    "candle_coverage",
    "field_profile",
    "label_integrity",
    "late_window_table",
    "load_pilot",
    "parse_candle",
    "parse_decimal",
    "parse_rfc3339",
    "parse_trade",
    "reconcile",
    "time_band",
    "trade_activity",
]

ONE: Final = Decimal(1)
ZERO: Final = Decimal(0)
TIME_BANDS: Final = ("post_close", "<=1m", ">1-2m", ">2-3m", ">3-5m", ">5m")
ASK_BANDS: Final = ("<0.85", "0.85-0.89", "0.90-0.92", "0.93-0.95", "0.96-0.97", ">0.97")
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
    taker_outcome_side: str
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


def parse_trade(row: Mapping[str, object]) -> Trade | None:
    """A historical REST trade, or None if any required field is malformed."""
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
        or side not in ("yes", "no")
    ):
        return None
    return Trade(trade_id, ticker, _epoch(when[0]), count, price, str(side), block)


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


def build_report(pilot: Pilot) -> dict[str, object]:
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
    return {
        "report": "b12_kalshi_btc_pilot_profile",
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
    args = parser.parse_args(argv)
    try:
        pilot = load_pilot(args.directory)
    except PilotError as error:
        sys.stderr.write(f"kalshi_btc pilot: {error}\n")
        return 2
    if args.show:
        _show(pilot, sys.stderr)
    sys.stdout.write(json.dumps(build_report(pilot), indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
