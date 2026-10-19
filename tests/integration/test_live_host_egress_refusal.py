"""Refusal checks for prohibited live market-data hosts (owner decision B10-D10, 2026-10-19).

The Claude development sandbox must not reach live market-data API or WebSocket hosts. B10
showed that the wildcard F-09 denies (``api.*``, ``ws.*``) do not stop a host once it is on
the allowlist, so the allowlist itself must exclude these hosts. Two layers enforce egress:

- Layer A: Claude Code managed settings, ``sandbox.network.allowedDomains`` in
  ``/etc/claude-code/managed-settings.json`` (enforced by the Claude Code sandbox proxy).
- Layer B: the PMV egress proxy outside the container (owner-administered).

The static Layer A check and the behavioral end-to-end check run only with
``PMV_EGRESS_PROBE=1`` inside the Claude Code sandbox, because they read host configuration
and attempt network connections, which ordinary test runs and CI must not do. The behavioral
check sends only an HTTP ``CONNECT`` to the configured proxy and never completes TLS or sends
an application request, so no market data can be received even if a host were reachable.
A refusal from inside the sandbox proves the combined path refuses; proving Layer B alone
requires the owner's run outside the Claude sandbox (docs/owner_actions/README.md, §3).

Never run this file with ``-l``/``--showlocals``: the proxy credential is read from the
environment at runtime, and a traceback with locals could print it. The credential is never
written, logged, or included in an assertion message.

This check is required to pass before any cycle's ``T0 - m`` (pre-T0 checklist).
"""

import base64
import fnmatch
import json
import os
import re
import socket
import urllib.parse
from pathlib import Path

import pytest

PROHIBITED_LIVE_HOSTS = ("api.kraken.com", "ws.kraken.com", "api.exchange.coinbase.com")
# Documentation hosts that B10-D10 preserves; also the positive control for the probe.
PRESERVED_DOC_HOSTS = ("docs.kraken.com", "docs.cdp.coinbase.com")
MANAGED_SETTINGS = Path("/etc/claude-code/managed-settings.json")
# A proxy refusal: any 4xx/5xx except 407 (407 means the probe failed to authenticate).
REFUSAL_STATUS = re.compile(r"^HTTP/1\.[01] (?!407)[45]\d\d\b")
ESTABLISHED_STATUS = re.compile(r"^HTTP/1\.[01] 200\b")

probe = pytest.mark.skipif(
    os.environ.get("PMV_EGRESS_PROBE") != "1",
    reason="set PMV_EGRESS_PROBE=1 inside the Claude Code sandbox to probe egress refusal",
)


def _proxy_auth_header(parsed: urllib.parse.SplitResult) -> str:
    if not parsed.username:
        return ""
    raw = f"{urllib.parse.unquote(parsed.username)}:{urllib.parse.unquote(parsed.password or '')}"
    return f"Proxy-Authorization: Basic {base64.b64encode(raw.encode()).decode()}\r\n"


def _connect_status(host: str) -> str:
    """Return the proxy's status line for CONNECT host:443, or a connection-error marker."""
    parsed = urllib.parse.urlsplit(
        os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    )
    assert parsed.hostname, "no HTTPS proxy configured: not running inside the sandbox"
    address = (parsed.hostname, parsed.port or 3128)
    try:
        with socket.create_connection(address, timeout=15) as sock:
            sock.sendall(
                (
                    f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n"
                    + _proxy_auth_header(parsed)
                    + "\r\n"
                ).encode()
            )
            reply = sock.recv(4096)
    except OSError as exc:
        return f"connection-error: {type(exc).__name__}"
    return reply.split(b"\r\n", 1)[0].decode("latin-1")


def _allows(entry: str, host: str) -> bool:
    """True if an allowedDomains entry admits host (exact, bare '*', '*.suffix', '.suffix')."""
    entry = entry.strip().lower()
    if entry in ("*", host):
        return True
    if entry.startswith("*."):
        return host.endswith(entry[1:])
    if entry.startswith("."):
        return host.endswith(entry)
    # Any other wildcard form (for example "*kraken.com"): treat a glob match as admitting.
    return "*" in entry and fnmatch.fnmatchcase(host, entry)


def test_prohibited_host_list_is_exact() -> None:
    assert set(PROHIBITED_LIVE_HOSTS) == {
        "api.kraken.com",
        "ws.kraken.com",
        "api.exchange.coinbase.com",
    }


def test_allowlist_matcher_covers_wildcards() -> None:
    assert _allows("api.kraken.com", "api.kraken.com")
    assert _allows("*.kraken.com", "ws.kraken.com")
    assert _allows(".coinbase.com", "api.exchange.coinbase.com")
    assert _allows("*", "api.kraken.com")
    assert _allows("*kraken.com", "api.kraken.com")
    assert not _allows("docs.kraken.com", "api.kraken.com")


@probe
def test_layer_a_managed_allowlist_excludes_prohibited_hosts() -> None:
    assert MANAGED_SETTINGS.is_file(), "managed settings not found"
    settings = json.loads(MANAGED_SETTINGS.read_text(encoding="utf-8"))
    allowed = settings.get("sandbox", {}).get("network", {}).get("allowedDomains", [])
    present = sorted({h for h in PROHIBITED_LIVE_HOSTS for e in allowed if _allows(e, h)})
    assert not present, f"Layer A still admits prohibited live hosts: {present}"


@probe
@pytest.mark.parametrize("host", PROHIBITED_LIVE_HOSTS)
def test_sandbox_egress_refuses_prohibited_host(host: str) -> None:
    # Control inside each probe, so a subset run cannot pass on a broken proxy path.
    control = _connect_status(PRESERVED_DOC_HOSTS[0])
    assert ESTABLISHED_STATUS.match(control), f"proxy path broken (control): {control!r}"
    status = _connect_status(host)
    assert REFUSAL_STATUS.match(status), f"{host} not refused by the proxy: {status!r}"


@probe
@pytest.mark.parametrize("host", PRESERVED_DOC_HOSTS)
def test_documentation_hosts_stay_reachable(host: str) -> None:
    """Positive control: B10-D10 preserves documentation hosts."""
    status = _connect_status(host)
    assert ESTABLISHED_STATUS.match(status), f"documentation host {host} not reachable: {status!r}"
