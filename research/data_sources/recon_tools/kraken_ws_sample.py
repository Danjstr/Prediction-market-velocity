"""B10 reconnaissance: capture a few consecutive Kraken spot WebSocket v2 public messages.

Development-time research tool only; not the PMV collector (src/pmv/capture governs real
capture). Standard library only: an HTTP CONNECT tunnel through the PMV egress proxy route
(PMV_EGRESS_PROXY_HOST / PMV_EGRESS_PROXY_PORT; owner decisions DR-10 and DR-16),
TLS, and a minimal RFC 6455 client (text frames, ping/pong, close). Each received text frame
is written unmodified with the local receipt time (time.time_ns()) to a JSONL file in a
git-ignored directory. Caps: --max-messages (<= 400) and --seconds (<= 60).

Usage: python3 -I kraken_ws_sample.py [--out FILE] [--max-messages N] [--seconds S]
"""

# ruff: noqa: T201  (CLI recon tools: printed manifests and profiles are their output)
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import socket
import ssl
import struct
import time
from datetime import UTC, datetime

HOST = "ws.kraken.com"
RECON_ROOT = pathlib.Path("/workspace/.recon_tmp")  # git-ignored; raw samples only here
# A bare DNS name or IPv4 address: no scheme, userinfo, port, path, or whitespace.
SAFE_PROXY_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
MAX_BYTES = 10 * 1024 * 1024  # owner B10 charter: <= 10 MB per source/schema
MAX_FRAME_BYTES = 1024 * 1024
PATH = "/v2"
SUBSCRIPTIONS = [
    {
        "method": "subscribe",
        "params": {"channel": "book", "symbol": ["BTC/USD"], "depth": 10, "snapshot": True},
        "req_id": 1,
    },
    {
        "method": "subscribe",
        "params": {"channel": "trade", "symbol": ["BTC/USD"], "snapshot": True},
        "req_id": 2,
    },
]


def confined(path: str) -> pathlib.Path:
    resolved = pathlib.Path(path).resolve()
    if not resolved.is_relative_to(RECON_ROOT):
        raise SystemExit(f"--out must resolve under {RECON_ROOT}")
    return resolved


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


def open_tunnel() -> ssl.SSLSocket:
    sock = socket.create_connection(proxy_address(), 20)
    # Owner decision DR-10 (2026-10-19): PMV code never builds proxy credentials. The CONNECT
    # carries no credential; a proxy that demands authentication (407) stops the tool.
    headers = f"CONNECT {HOST}:443 HTTP/1.1\r\nHost: {HOST}:443\r\n"
    sock.sendall((headers + "\r\n").encode())
    reply = b""
    while b"\r\n\r\n" not in reply:
        chunk = sock.recv(4096)
        if not chunk:
            raise SystemExit("proxy closed the tunnel")
        reply += chunk
    status = reply.split(b"\r\n", 1)[0]
    if b" 407" in status:
        raise SystemExit("proxy requires authentication; PMV code must not supply it (DR-10)")
    if b" 200" not in status:
        raise SystemExit(f"proxy refused: {status.decode(errors='replace')}")
    context = ssl.create_default_context()
    return context.wrap_socket(sock, server_hostname=HOST)


def read_exact(sock: ssl.SSLSocket, n: int, buffer: bytearray) -> bytes:
    while len(buffer) < n:
        chunk = sock.recv(65536)
        if not chunk:
            raise EOFError("connection closed")
        buffer.extend(chunk)
    out = bytes(buffer[:n])
    del buffer[:n]
    return out


def send_frame(sock: ssl.SSLSocket, opcode: int, payload: bytes) -> None:
    mask = os.urandom(4)
    header = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header += bytes([0x80 | length])
    elif length < 65536:
        header += bytes([0x80 | 126]) + struct.pack("!H", length)
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", length)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(header + mask + masked)


def handshake(sock: ssl.SSLSocket, buffer: bytearray) -> None:
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET {PATH} HTTP/1.1\r\nHost: {HOST}\r\nUpgrade: websocket\r\n"
        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\nUser-Agent: pmv-b10-recon/1\r\n\r\n"
    )
    sock.sendall(request.encode())
    while b"\r\n\r\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise SystemExit("closed during handshake")
        buffer.extend(chunk)
    head, _, rest = bytes(buffer).partition(b"\r\n\r\n")
    buffer[:] = rest
    if b" 101" not in head.split(b"\r\n", 1)[0]:
        raise SystemExit(f"handshake failed: {head[:200]!r}")
    accept = base64.b64encode(
        hashlib.sha1(  # RFC 6455 accept-key derivation, not a security use
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode(), usedforsecurity=False
        ).digest()
    ).decode()
    if accept.encode() not in head:
        raise SystemExit("bad Sec-WebSocket-Accept")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="/workspace/.recon_tmp/kraken_ws/ws_v2_sample.jsonl")
    parser.add_argument("--max-messages", type=int, default=200)
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    if not (1 <= args.max_messages <= 400 and 0 < args.seconds <= 60):
        raise SystemExit("caps: --max-messages <= 400, --seconds <= 60")
    out = confined(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    buffer = bytearray()
    sock = open_tunnel()
    started = datetime.now(UTC).isoformat(timespec="milliseconds")
    count = 0
    total = 0
    try:
        handshake(sock, buffer)
        for sub in SUBSCRIPTIONS:
            send_frame(sock, 0x1, json.dumps(sub).encode())
        deadline = time.monotonic() + args.seconds
        sock.settimeout(5)
        fragments = b""
        with out.open("w", encoding="utf-8") as handle:
            while count < args.max_messages and time.monotonic() < deadline:
                try:
                    b0, b1 = read_exact(sock, 2, buffer)
                except TimeoutError:
                    continue
                fin, opcode, length = b0 & 0x80, b0 & 0x0F, b1 & 0x7F
                if b1 & 0x80 or b0 & 0x70:
                    raise SystemExit("masked server frame or RSV bits set (RFC 6455 5.1/5.2)")
                if length == 126:
                    (length,) = struct.unpack("!H", read_exact(sock, 2, buffer))
                elif length == 127:
                    (length,) = struct.unpack("!Q", read_exact(sock, 8, buffer))
                if length > MAX_FRAME_BYTES:
                    raise SystemExit("frame exceeds the per-frame cap")
                total += length
                if total > MAX_BYTES:
                    raise SystemExit("capture exceeds the per-source byte limit")
                payload = read_exact(sock, length, buffer)
                recv_ns = time.time_ns()
                if opcode == 0x9:
                    send_frame(sock, 0xA, payload)
                    continue
                if opcode == 0x8:
                    break
                if opcode in (0x1, 0x0):
                    fragments += payload
                    if fin:
                        text = fragments.decode("utf-8")
                        handle.write(json.dumps({"recv_ns": recv_ns, "frame": text}) + "\n")
                        fragments = b""
                        count += 1
                else:
                    raise SystemExit(f"unexpected opcode {opcode}")
        send_frame(sock, 0x8, struct.pack("!H", 1000))
    finally:
        sock.close()
    body = out.read_bytes()
    print(
        json.dumps(
            {
                "endpoint": f"wss://{HOST}{PATH}",
                "started_utc": started,
                "messages": count,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "file": str(out),
            }
        )
    )


if __name__ == "__main__":
    main()
