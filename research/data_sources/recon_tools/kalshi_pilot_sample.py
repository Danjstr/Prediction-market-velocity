"""B12 pilot: fetch a bounded historical Kalshi BTC 15-minute sample (owner B12 charter).

Development-time research tool only. It is not part of the PMV runtime and is not the bulk
acquisition tool: the acquisition gate (docs/external_access.md §2) still governs bulk
history. Every row it fetches is DEVELOPMENT-EXPOSED and must be registered in
docs/exposure_register.md after the run.

Raw response bytes are written, unmodified, under /workspace/.recon_tmp/kalshi_pilot
(git-ignored), with one manifest line per request. The B12 ceilings are enforced
cumulatively across invocations from that manifest: <= 10 MB raw and <= 10,000 rows. A
response that would cross a ceiling is not written, and the tool stops.

Scope guards:
- only fixed public endpoint templates on the production REST host, with validated
  parameters; no authenticated, portfolio, order, WebSocket, or live-quote endpoint;
- markets must belong to the KXBTC15M family (ticker prefix used as a scope guard only,
  never to infer relationships) and must be settled before the historical cutoff
  (``market_settled_ts`` from ``discover``), so only the historical tier is read.

Routing (owner decisions DR-10 and DR-16): either a credential-free CONNECT tunnel to
PMV_EGRESS_PROXY_HOST / PMV_EGRESS_PROXY_PORT, or ``--direct`` (owner-run, no proxy). The
runtime proxy variables are never read, and the default urllib opener is never used.

Usage (python3 -I, from any directory):
  kalshi_pilot_sample.py discover
  kalshi_pilot_sample.py depth --close-date YYYY-MM-DD
  kalshi_pilot_sample.py markets-page [--cursor C]
  kalshi_pilot_sample.py market --ticker KXBTC15M-...
"""

# ruff: noqa: T201  (CLI recon tools: printed manifests are their output)
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import pathlib
import re
import ssl
import time
import urllib.parse
from datetime import UTC, datetime

HOST = "external-api.kalshi.com"  # docs: recommended production REST host
BASE = "/trade-api/v2"
SERIES = "KXBTC15M"
RECON_ROOT = pathlib.Path("/workspace/.recon_tmp")  # git-ignored; raw samples only here
DEFAULT_OUT = RECON_ROOT / "kalshi_pilot"
MAX_BYTES = 10 * 1024 * 1024  # owner B12 charter: <= 10 MB raw
MAX_ROWS = 10_000  # owner B12 charter: <= 10,000 observation rows/messages
MAX_TRADE_PAGES = 10
SAFE_PROXY_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
SAFE_TICKER = re.compile(rf"{SERIES}-[A-Z0-9-]{{1,60}}")
SAFE_CURSOR = re.compile(r"[A-Za-z0-9_=+/-]{1,512}")
ROW_KEYS = ("markets", "events", "trades", "candlesticks", "series", "series_fee_change_arr")


def proxy_address() -> tuple[str, int]:
    """The credential-free PMV egress route (DR-16). Values are never echoed."""
    host = os.environ.get("PMV_EGRESS_PROXY_HOST", "")
    port = os.environ.get("PMV_EGRESS_PROXY_PORT", "")
    if not SAFE_PROXY_HOST.fullmatch(host):
        raise SystemExit("set PMV_EGRESS_PROXY_HOST to a bare hostname or IPv4 address")
    if not (port.isascii() and port.isdigit() and 1 <= int(port) <= 65535):
        raise SystemExit("set PMV_EGRESS_PROXY_PORT to an integer from 1 to 65535")
    return host, int(port)


def build_path(endpoint: str, params: dict[str, str]) -> str:
    """One of the fixed templates; parameters are validated by the callers."""
    allowed = {
        "cutoff": "/historical/cutoff",
        "series": f"/series/{SERIES}",
        "series_list": "/series",
        "fee_changes": "/series/fee_changes",
        "events": "/events",
        "historical_markets": "/historical/markets",
        "historical_market": "/historical/markets/{ticker}",
        "historical_candles": "/historical/markets/{ticker}/candlesticks",
        "historical_trades": "/historical/trades",
    }
    template = allowed[endpoint]
    path = template.format(ticker=params.pop("ticker")) if "{ticker}" in template else template
    query = urllib.parse.urlencode(sorted(params.items()))
    return f"{BASE}{path}" + (f"?{query}" if query else "")


def fetch(path: str, direct: bool) -> bytes:
    context = ssl.create_default_context()
    if direct:
        conn = http.client.HTTPSConnection(HOST, 443, timeout=30, context=context)
    else:
        proxy_host, proxy_port = proxy_address()
        # DR-10: no proxy credential is ever built. A 407 stops the tool.
        conn = http.client.HTTPSConnection(proxy_host, proxy_port, timeout=30, context=context)
        conn.set_tunnel(HOST, 443)
    try:
        conn.request("GET", path, headers={"User-Agent": "pmv-b12-pilot/1"})
        response = conn.getresponse()
        if response.status != 200:
            raise SystemExit(f"HTTP status {response.status}")
        body: bytes = response.read(MAX_BYTES + 1)
    except OSError as exc:
        raise SystemExit(f"request failed: {type(exc).__name__}") from None
    finally:
        conn.close()
    return body


class Store:
    """The raw directory and its manifest; enforces the cumulative B12 ceilings."""

    def __init__(self, out: pathlib.Path) -> None:
        out = out.resolve()
        if not out.is_relative_to(RECON_ROOT):
            raise SystemExit(f"--out must resolve under {RECON_ROOT}")
        out.mkdir(parents=True, exist_ok=True)
        self.out = out
        self.manifest = out / "manifest.jsonl"
        self.bytes = 0
        self.rows = 0
        if self.manifest.exists():
            for line in self.manifest.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                self.bytes += int(entry["bytes"])
                self.rows += int(entry["rows"])

    def get(
        self, endpoint: str, params: dict[str, str], name: str, direct: bool
    ) -> dict[str, object]:
        path = build_path(endpoint, dict(params))
        retrieved = datetime.now(UTC).isoformat(timespec="milliseconds")
        body = fetch(path, direct)
        document = json.loads(body)
        if not isinstance(document, dict):
            raise SystemExit(f"{endpoint}: response is not a JSON object")
        rows = sum(len(v) for k, v in document.items() if k in ROW_KEYS and isinstance(v, list))
        rows += 1 if endpoint == "historical_market" else 0
        if self.bytes + len(body) > MAX_BYTES or self.rows + rows > MAX_ROWS:
            raise SystemExit("B12 pilot ceiling reached; response not written")
        target = (self.out / name).resolve()
        if not target.is_relative_to(self.out):
            raise SystemExit("refusing to write outside the pilot directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        self.bytes += len(body)
        self.rows += rows
        entry = {
            "file": name,
            "endpoint": endpoint,
            "path": path,
            "retrieved_utc": retrieved,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "rows": rows,
            "cumulative_bytes": self.bytes,
            "cumulative_rows": self.rows,
        }
        with self.manifest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        print(json.dumps(entry, sort_keys=True))
        time.sleep(0.5)
        return document


def _utc_seconds(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def _settled_cutoff(store: Store) -> int:
    path = store.out / "cutoff.json"
    if not path.exists():
        raise SystemExit("run 'discover' first: the historical cutoff is required")
    value = json.loads(path.read_text(encoding="utf-8")).get("market_settled_ts")
    if not isinstance(value, str):
        raise SystemExit("cutoff.json has no market_settled_ts string")
    return _utc_seconds(value)


def cmd_discover(store: Store, direct: bool) -> None:
    store.get("cutoff", {}, "cutoff.json", direct)
    store.get("series", {}, "series.json", direct)
    store.get(
        "fee_changes",
        {"series_ticker": SERIES, "show_historical": "true"},
        "fee_changes.json",
        direct,
    )
    store.get(
        "series_list",
        {"category": "Crypto", "include_product_metadata": "true"},
        "series_list_crypto.json",
        direct,
    )


def cmd_depth(store: Store, close_date: str, direct: bool) -> None:
    day = datetime.strptime(close_date, "%Y-%m-%d").replace(tzinfo=UTC)
    store.get(
        "events",
        {"series_ticker": SERIES, "min_close_ts": str(int(day.timestamp())), "limit": "5"},
        f"depth_events_{close_date}.json",
        direct,
    )


def cmd_markets_page(store: Store, cursor: str | None, direct: bool) -> None:
    params = {"series_ticker": SERIES, "limit": "200"}
    if cursor is not None:
        if not SAFE_CURSOR.fullmatch(cursor):
            raise SystemExit("malformed cursor")
        params["cursor"] = cursor
    index = len(list(store.out.glob("historical_markets_p*.json")))
    store.get("historical_markets", params, f"historical_markets_p{index:02d}.json", direct)


def cmd_market(store: Store, ticker: str, direct: bool) -> None:
    if not SAFE_TICKER.fullmatch(ticker):
        raise SystemExit(f"ticker must match {SAFE_TICKER.pattern}")
    cutoff = _settled_cutoff(store)
    folder = f"markets/{ticker}"
    document = store.get("historical_market", {"ticker": ticker}, f"{folder}/market.json", direct)
    market = document.get("market")
    if not isinstance(market, dict):
        raise SystemExit("market response has no market object")
    opened, closed = market.get("open_time"), market.get("close_time")
    if not isinstance(opened, str) or not isinstance(closed, str):
        raise SystemExit("market has no open_time/close_time strings")
    open_ts, close_ts = _utc_seconds(opened), _utc_seconds(closed)
    if close_ts >= cutoff:
        raise SystemExit("market closes at or after the historical cutoff; not sampled")
    store.get(
        "historical_candles",
        {
            "ticker": ticker,
            "start_ts": str(open_ts - 60),
            "end_ts": str(close_ts + 120),
            "period_interval": "1",
        },
        f"{folder}/candles.json",
        direct,
    )
    cursor: str | None = None
    for page in range(MAX_TRADE_PAGES):
        params = {"ticker": ticker, "limit": "1000"}
        if cursor:
            params["cursor"] = cursor
        trades = store.get("historical_trades", params, f"{folder}/trades_p{page:02d}.json", direct)
        next_cursor = trades.get("cursor")
        if not next_cursor:  # null and "" are both terminal (docs conflict)
            return
        if not isinstance(next_cursor, str) or not SAFE_CURSOR.fullmatch(next_cursor):
            raise SystemExit("malformed cursor in trades response")
        cursor = next_cursor
    raise SystemExit(f"more than {MAX_TRADE_PAGES} trade pages; stopped (pilot bound)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--direct", action="store_true", help="owner-run: no proxy tunnel")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    depth = sub.add_parser("depth")
    depth.add_argument("--close-date", required=True)
    page = sub.add_parser("markets-page")
    page.add_argument("--cursor")
    one = sub.add_parser("market")
    one.add_argument("--ticker", required=True)
    args = parser.parse_args()
    store = Store(pathlib.Path(args.out))
    if args.command == "discover":
        cmd_discover(store, args.direct)
    elif args.command == "depth":
        cmd_depth(store, args.close_date, args.direct)
    elif args.command == "markets-page":
        cmd_markets_page(store, args.cursor, args.direct)
    else:
        cmd_market(store, args.ticker, args.direct)


if __name__ == "__main__":
    main()
