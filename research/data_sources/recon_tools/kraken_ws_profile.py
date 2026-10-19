"""B10 reconnaissance: profile a Kraken WebSocket v2 sample written by kraken_ws_sample.py.

Reports message types, field sets, JSON types, timestamp precision, spacing, trade-id
continuity, and whether a local top-10 book maintained from snapshot + updates reproduces
every server CRC32 checksum. Prints no prices or sizes unless --show is given (operator
inspection only; values are development-exposed and must not be copied into Git).

Usage: python3 -I kraken_ws_profile.py FILE [--show N]
"""

# ruff: noqa: T201  (CLI recon tools: printed manifests and profiles are their output)
from __future__ import annotations

import argparse
import json
import zlib
from collections import Counter
from datetime import datetime
from decimal import Decimal
from itertools import pairwise

PRICE_DP = 1  # BTC/USD price_precision (instrument channel); see profile for evidence
QTY_DP = 8  # BTC/USD qty_precision


def fmt(value: Decimal, dp: int) -> str:
    text = f"{value:.{dp}f}".replace(".", "").lstrip("0")
    return text or "0"


def checksum(bids: dict[Decimal, Decimal], asks: dict[Decimal, Decimal]) -> int:
    a = "".join(fmt(p, PRICE_DP) + fmt(asks[p], QTY_DP) for p in sorted(asks)[:10])
    b = "".join(fmt(p, PRICE_DP) + fmt(bids[p], QTY_DP) for p in sorted(bids, reverse=True)[:10])
    return zlib.crc32((a + b).encode()) & 0xFFFFFFFF


def parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--show", type=int, default=0)
    args = parser.parse_args()
    with open(args.file, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle]
    kinds: Counter[str] = Counter()
    field_sets: dict[str, set[str]] = {}
    json_types: dict[str, Counter[str]] = {}
    bids: dict[Decimal, Decimal] = {}
    asks: dict[Decimal, Decimal] = {}
    checks = Counter[str]()
    book_ts_prec: Counter[int] = Counter()
    trade_ids: list[int] = []
    trade_batch: Counter[int] = Counter()
    sides: Counter[str] = Counter()
    ord_types: Counter[str] = Counter()
    lag_ms: list[float] = []
    book_updates_levels: Counter[int] = Counter()
    order: list[str] = []
    recv_book: list[int] = []
    for rec in lines:
        msg = json.loads(rec["frame"], parse_float=Decimal)
        kind = f"{msg.get('channel', msg.get('method'))}:{msg.get('type', '')}"
        kinds[kind] += 1
        order.append(kind)
        field_sets.setdefault(kind, set()).update(msg.keys())
        for item in msg.get("data", []) if isinstance(msg.get("data"), list) else []:
            if isinstance(item, dict):
                for k, v in item.items():
                    json_types.setdefault(f"{kind}.{k}", Counter())[type(v).__name__] += 1
        if msg.get("channel") == "book":
            recv_book.append(rec["recv_ns"])
            for item in msg["data"]:
                if msg["type"] == "snapshot":
                    bids.clear()
                    asks.clear()
                book_updates_levels[len(item["bids"]) + len(item["asks"])] += 1
                for side, levels in (("bids", item["bids"]), ("asks", item["asks"])):
                    book = bids if side == "bids" else asks
                    for level in levels:
                        if level["qty"] == 0:
                            book.pop(level["price"], None)
                        else:
                            book[level["price"]] = level["qty"]
                for book, rev in ((bids, True), (asks, False)):
                    for p in sorted(book, reverse=rev)[10:]:
                        del book[p]
                ok = checksum(bids, asks) == item["checksum"]
                checks["match" if ok else "mismatch"] += 1
                ts = item["timestamp"]
                book_ts_prec[len(ts.split(".")[1].rstrip("Z")) if "." in ts else 0] += 1
                exch = parse_ts(ts).timestamp()
                lag_ms.append(rec["recv_ns"] / 1e6 - exch * 1e3)
        if msg.get("channel") == "trade":
            trade_batch[len(msg["data"])] += 1
            for t in msg["data"]:
                trade_ids.append(t["trade_id"])
                sides[t["side"]] += 1
                ord_types[t["ord_type"]] += 1
                if msg["type"] == "update":
                    lag_ms.append(rec["recv_ns"] / 1e6 - parse_ts(t["timestamp"]).timestamp() * 1e3)
    print("messages", len(lines), "kinds", dict(kinds))
    print("first 8 message kinds in order", order[:8])
    for k, v in field_sets.items():
        print("top-level fields", k, sorted(v))
    for k, v in sorted(json_types.items()):
        print("data field JSON type", k, dict(v))
    print("book checksum verification", dict(checks))
    print("book level-updates per message", dict(sorted(book_updates_levels.items())))
    print("book timestamp fractional digits", dict(book_ts_prec))
    print(
        "trade messages per batch size",
        dict(sorted(trade_batch.items())),
        "sides",
        dict(sides),
        "ord_types",
        dict(ord_types),
    )
    steps = Counter(b - a for a, b in pairwise(trade_ids))
    print("trade_id steps", dict(steps))
    gaps = sorted((b - a) / 1e6 for a, b in pairwise(recv_book))
    if gaps:
        print(
            "book message local spacing ms p10/p50/p90/max",
            [round(gaps[int(q * (len(gaps) - 1))], 1) for q in (0.1, 0.5, 0.9, 1.0)],
        )
    if lag_ms:
        s = sorted(lag_ms)
        print(
            "local receipt minus exchange timestamp ms (clock-skew caveat) p10/p50/p90",
            [round(s[int(q * (len(s) - 1))], 1) for q in (0.1, 0.5, 0.9)],
        )
    for rec in lines[: args.show]:
        print(rec["frame"][:400])


if __name__ == "__main__":
    main()
