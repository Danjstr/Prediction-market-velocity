"""B10 reconnaissance: fetch a tiny, old Kraken public REST trade sample.

Development-time research tool only. It is not part of the PMV runtime and is not an
acquisition tool (the acquisition gate in docs/external_access.md §2 still governs bulk
history). It writes the raw response bytes, unmodified, into a git-ignored directory
(default /workspace/.recon_tmp/kraken_rest_trades) and prints one manifest line per page.

Requests go through an HTTP CONNECT tunnel to the PMV egress proxy route
(PMV_EGRESS_PROXY_HOST / PMV_EGRESS_PROXY_PORT; owner decisions DR-10 and DR-16). The default
urllib opener is not used: it reads the runtime proxy variables and builds a proxy
authorization header from them.

Usage: python3 -I kraken_rest_trades_sample.py --since-ns <ns> --pages <n> [--out DIR]
"""

# ruff: noqa: T201  (CLI recon tools: printed manifests and profiles are their output)
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
from datetime import UTC, datetime

HOST = "api.kraken.com"
ENDPOINT = f"https://{HOST}/0/public/Trades"
RECON_ROOT = pathlib.Path("/workspace/.recon_tmp")  # git-ignored; raw samples only here
# A bare DNS name or IPv4 address: no scheme, userinfo, port, path, or whitespace.
SAFE_PROXY_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
MAX_PAGES = 5  # owner B10 charter: <= 5,000 rows per source/schema
MAX_BYTES = 10 * 1024 * 1024  # owner B10 charter: <= 10 MB per source/schema


def proxy_address() -> tuple[str, int]:
    """Read the credential-free PMV egress proxy route (owner decision DR-16).

    The runtime proxy variables are never read or parsed, even for a host or port, because
    they may hold a credential-bearing URL. Values are not echoed in error messages.
    """
    host = os.environ.get("PMV_EGRESS_PROXY_HOST", "")
    port = os.environ.get("PMV_EGRESS_PROXY_PORT", "")
    if not SAFE_PROXY_HOST.fullmatch(host):
        raise SystemExit("set PMV_EGRESS_PROXY_HOST to a bare hostname or IPv4 address")
    if not (port.isascii() and port.isdigit() and 1 <= int(port) <= 65535):
        raise SystemExit("set PMV_EGRESS_PROXY_PORT to an integer from 1 to 65535")
    return host, int(port)


def fetch(url: str) -> bytes:
    if not url.startswith(ENDPOINT + "?"):
        raise SystemExit("only the fixed Kraken Trades endpoint is allowed")
    proxy_host, proxy_port = proxy_address()
    # Owner decision DR-10 (2026-10-19): PMV code never builds proxy credentials. The CONNECT
    # carries no credential; a proxy that demands authentication (407) stops the tool.
    conn = http.client.HTTPSConnection(
        proxy_host, proxy_port, timeout=30, context=ssl.create_default_context()
    )
    conn.set_tunnel(HOST, 443)
    try:
        path = url.removeprefix(f"https://{HOST}")
        conn.request("GET", path, headers={"User-Agent": "pmv-b10-recon/1"})
        response = conn.getresponse()
        if response.status != 200:
            raise SystemExit(f"HTTP status {response.status}")
        body: bytes = response.read(MAX_BYTES + 1)
    except OSError as exc:
        raise SystemExit(f"request failed: {type(exc).__name__}") from None
    finally:
        conn.close()
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
