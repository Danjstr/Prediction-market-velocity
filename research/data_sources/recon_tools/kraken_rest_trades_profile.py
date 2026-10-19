"""B10 reconnaissance: profile a Kraken REST trade sample written by kraken_rest_trades_sample.py.

Prints structure, value sets, counts, timestamp precision, spacing, and identifier continuity.
With --show it also prints head(10) and tail(10) rows for the operator; those values are
development-exposed and must not be copied into Git.

Usage: python3 -I kraken_rest_trades_profile.py DIR [--show]
"""

# ruff: noqa: T201  (CLI recon tools: printed manifests and profiles are their output)
from __future__ import annotations

import argparse
import json
import pathlib
import re
import statistics
from collections import Counter
from decimal import Decimal
from itertools import pairwise

FIELDS = ["price", "volume", "time", "side", "ord_type", "misc", "trade_id"]


def quantiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    pick = {"min": 0.0, "p10": 0.10, "p50": 0.50, "p90": 0.90, "p99": 0.99, "max": 1.0}
    return {
        k: round(ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))], 6)
        for k, q in pick.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    rows: list[list[object]] = []
    raw_time_texts: list[str] = []
    page_bounds = []
    lasts = []
    for path in sorted(pathlib.Path(args.directory).glob("page_*.json")):
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text, parse_float=Decimal)
        keys = sorted(doc["result"].keys())
        pair_keys = [k for k in keys if k != "last"]
        page = doc["result"][pair_keys[0]]
        lasts.append(doc["result"]["last"])
        page_bounds.append((page[0][6], page[-1][6]))
        rows.extend(page)
        # raw textual time tokens (3rd element) to measure the digits actually sent
        raw_time_texts.extend(re.findall(r'\["[^"]*","[^"]*",([0-9.]+),', text))
        print(
            "page",
            path.name,
            "top-level keys",
            sorted(doc.keys()),
            "result keys",
            keys,
            "last type",
            type(doc["result"]["last"]).__name__,
        )
    print("rows", len(rows), "row arity", Counter(len(r) for r in rows))
    for i, name in enumerate(FIELDS):
        col = [r[i] for r in rows]
        types = Counter(type(v).__name__ for v in col)
        nulls = sum(1 for v in col if v is None or v == "")
        print(
            f"field[{i}] {name}: json types {dict(types)} null_or_empty {nulls} "
            f"unique {len(set(map(str, col)))}"
        )
    for i, name in ((0, "price"), (1, "volume")):
        print(name, "decimal places", Counter(len(str(r[i]).split(".")[1]) for r in rows))
    print(
        "raw time token decimals",
        Counter(len(t.split(".")[1]) if "." in t else 0 for t in raw_time_texts),
    )
    for i, name in ((3, "side"), (4, "ord_type"), (5, "misc")):
        print(name, "value set", dict(Counter(str(r[i]) for r in rows)))
    times = [Decimal(str(r[2])) for r in rows]
    ids = [int(str(r[6])) for r in rows]
    print("time monotonic non-decreasing", all(b >= a for a, b in pairwise(times)))
    print("time min/max (unix s)", min(times), max(times))
    print(
        "trade_id strictly increasing",
        all(b > a for a, b in pairwise(ids)),
        "gaps (id step != 1)",
        sum(1 for a, b in pairwise(ids) if b - a != 1),
        "duplicates",
        len(ids) - len(set(ids)),
    )
    for (_, last_id), (first_id, _) in pairwise(page_bounds):
        print("page boundary id step", first_id - last_id)
    for last in lasts:
        print("page last (ns)", last, "-> cursor is a time in ns, not a trade_id")
    # Spacing statistics on unique trades only (page boundaries repeat one trade; B10 review).
    unique: dict[int, list[object]] = {}
    for r in rows:
        unique.setdefault(int(str(r[6])), r)
    rows = list(unique.values())
    times = [Decimal(str(r[2])) for r in rows]
    print("unique trades", len(rows))
    gaps = [float(b - a) for a, b in pairwise(times)]
    print("inter-trade seconds", quantiles(gaps))
    print("share of zero inter-trade gaps", round(sum(1 for g in gaps if g == 0) / len(gaps), 4))
    minutes: dict[int, list[list[object]]] = {}
    for r in rows:
        minutes.setdefault(int(Decimal(str(r[2])) // 60), []).append(r)
    counts = [len(v) for v in minutes.values()]
    print(
        "1-min buckets",
        len(minutes),
        "trades per minute",
        quantiles([float(c) for c in counts]),
        "mean",
        round(statistics.mean(counts), 2),
    )
    # Deterministic OHLCV + VWAP + count from trades (structure only, values not printed).
    bar = next(iter(minutes.values()))
    o, c = Decimal(str(bar[0][0])), Decimal(str(bar[-1][0]))
    h = max(Decimal(str(t[0])) for t in bar)
    lo = min(Decimal(str(t[0])) for t in bar)
    v = sum(Decimal(str(t[1])) for t in bar)
    vwap = sum(Decimal(str(t[0])) * Decimal(str(t[1])) for t in bar) / v
    print(
        "derived first-minute bar fields computed:",
        ["open", "high", "low", "close", "vwap", "volume", "count"],
        "consistency h>=o,c>=l:",
        h >= max(o, c) and lo <= min(o, c),
        "vwap within [l,h]:",
        lo <= vwap <= h,
    )
    if args.show:
        print("HEAD10")
        for r in rows[:10]:
            print(r)
        print("TAIL10")
        for r in rows[-10:]:
            print(r)


if __name__ == "__main__":
    main()
