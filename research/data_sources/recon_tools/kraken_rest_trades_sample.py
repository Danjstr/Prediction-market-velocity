"""B10 reconnaissance: fetch a tiny, old Kraken public REST trade sample.

Development-time research tool only. It is not part of the PMV runtime and is not an
acquisition tool (the acquisition gate in docs/external_access.md §2 still governs bulk
history). It writes the raw response bytes, unmodified, into a git-ignored directory
(default /workspace/.recon_tmp/kraken_rest_trades) and prints one manifest line per page.

Usage: python3 -I kraken_rest_trades_sample.py --since-ns <ns> --pages <n> [--out DIR]
"""

# ruff: noqa: T201  (CLI recon tools: printed manifests and profiles are their output)
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
import urllib.request
from datetime import UTC, datetime

ENDPOINT = "https://api.kraken.com/0/public/Trades"
RECON_ROOT = pathlib.Path("/workspace/.recon_tmp")  # git-ignored; raw samples only here
MAX_PAGES = 5  # owner B10 charter: <= 5,000 rows per source/schema
MAX_BYTES = 10 * 1024 * 1024  # owner B10 charter: <= 10 MB per source/schema


def fetch(url: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 (fixed https endpoint)
        url, headers={"User-Agent": "pmv-b10-recon/1"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        body: bytes = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise SystemExit("response exceeds the per-source byte limit")
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", default="XBTUSD")
    parser.add_argument("--since-ns", required=True, type=int)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--out", default="/workspace/.recon_tmp/kraken_rest_trades")
    args = parser.parse_args()
    if not 1 <= args.pages <= MAX_PAGES:
        raise SystemExit(f"--pages must be between 1 and {MAX_PAGES}")
    out = pathlib.Path(args.out).resolve()
    if not out.is_relative_to(RECON_ROOT):
        raise SystemExit(f"--out must resolve under {RECON_ROOT}")
    out.mkdir(parents=True, exist_ok=True)
    since = str(args.since_ns)
    total = 0
    for page in range(args.pages):
        url = f"{ENDPOINT}?pair={args.pair}&since={since}&count=1000"
        retrieved = datetime.now(UTC).isoformat(timespec="milliseconds")
        body = fetch(url)
        total += len(body)
        if total > MAX_BYTES:
            raise SystemExit("cumulative sample exceeds the per-source byte limit")
        path = out / f"page_{page:02d}.json"
        path.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        parsed = json.loads(body)
        if parsed.get("error"):
            raise SystemExit(f"API error: {parsed['error']}")
        rows = sum(len(v) for k, v in parsed["result"].items() if k != "last")
        print(
            json.dumps(
                {
                    "page": page,
                    "url": url,
                    "retrieved_utc": retrieved,
                    "bytes": len(body),
                    "sha256": digest,
                    "rows": rows,
                }
            )
        )
        since = str(parsed["result"]["last"])
        time.sleep(2.0)  # Kraken guide: 1-2 s between Trades calls


if __name__ == "__main__":
    main()
