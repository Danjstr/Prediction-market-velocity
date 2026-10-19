"""Refusal checks for prohibited live market-data hosts (owner decisions B10-D10 and DR-11).

The Claude development sandbox must not reach live market-data API or WebSocket hosts. B10
showed that the wildcard F-09 denies (``api.*``, ``ws.*``) do not stop a host once it is on
the allowlist, so the allowlist itself must exclude these hosts. Two layers enforce egress:

- Layer A: Claude Code managed settings, ``sandbox.network.allowedDomains`` in
  ``/etc/claude-code/managed-settings.json`` (enforced by the Claude Code sandbox proxy).
- Layer B: the PMV egress proxy outside the container (owner-administered).

The static Layer A check and the behavioral CONNECT probes run only with
``PMV_EGRESS_PROBE=1``, because they read host configuration and attempt network
connections, which ordinary test runs and CI must not do. A probe sends only an HTTP
``CONNECT`` and never completes TLS or sends an application request, so no market data can be
received even if a host were reachable. Proving Layer B alone requires the owner's run outside
the Claude sandbox (docs/owner_actions/README.md, section 3).

Proxy handling (owner decisions DR-10 and DR-16, 2026-10-19; ``docs/conventions.md``). PMV
code never reads or parses the runtime proxy variables, in upper or lower case, not even to
extract a host or port, because they may hold a credential-bearing URL. It never constructs a
proxy authorization header. The probe destination comes only from the credential-free
settings ``PMV_EGRESS_PROXY_HOST`` (a bare hostname or IPv4 address) and
``PMV_EGRESS_PROXY_PORT``. Failure messages never repeat those values. If they are unset, or
the proxy demands authentication (status 407), the combined probe is not applicable and is
skipped, never passed. The pre-``T0 - m`` evidence is then the Layer A static check plus the
owner's unauthenticated Layer B CONNECT check. The probes refuse to run with local-variable
tracebacks
(``-l``/``--showlocals``) enabled.

The applicable checks are required to pass before any cycle's ``T0 - m`` (START_HERE.md
pre-T0 checklist P-5).
"""

import fnmatch
import json
import os
import re
import socket
from pathlib import Path

import pytest

PROHIBITED_LIVE_HOSTS = ("api.kraken.com", "ws.kraken.com", "api.exchange.coinbase.com")
# Documentation hosts that B10-D10 preserves; also the positive control for the probe.
PRESERVED_DOC_HOSTS = ("docs.kraken.com", "docs.cdp.coinbase.com")
MANAGED_SETTINGS = Path("/etc/claude-code/managed-settings.json")
PROXY_HOST_SETTING = "PMV_EGRESS_PROXY_HOST"
PROXY_PORT_SETTING = "PMV_EGRESS_PROXY_PORT"
# A bare DNS name or IPv4 address: no scheme, userinfo, port, path, or whitespace.
SAFE_PROXY_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
# A proxy policy refusal is 403. Anything else fails, and 5xx (DNS or upstream failure) does
# not prove a policy denial (review API3-B10-04). 407 means the proxy requires authentication,
# which PMV code must not supply (owner decision DR-10): the combined probe is then skipped.
REFUSAL_STATUS = re.compile(r"^HTTP/1\.[01] 403\b")
ESTABLISHED_STATUS = re.compile(r"^HTTP/1\.[01] 200\b")
AUTH_REQUIRED_STATUS = re.compile(r"^HTTP/1\.[01] 407\b")
NOT_CONFIGURED = (
    "combined CONNECT probe not applicable: PMV_EGRESS_PROXY_HOST and PMV_EGRESS_PROXY_PORT "
    "are not set (PMV code never reads runtime proxy variables, owner decision DR-16); rely on "
    "the Layer A static check and the owner's Layer B CONNECT check"
)
NOT_APPLICABLE = (
    "combined CONNECT probe not applicable: the proxy requires authentication, which PMV code "
    "must not supply (owner decision DR-10); rely on the Layer A static check and the owner's "
    "Layer B CONNECT check"
)

probe = pytest.mark.skipif(
    os.environ.get("PMV_EGRESS_PROBE") != "1",
    reason="set PMV_EGRESS_PROBE=1 to run the egress refusal checks",
)


def _proxy_address() -> tuple[str, int] | None:
    """Return the credential-free probe destination, or None if it is not configured."""
    host = os.environ.get(PROXY_HOST_SETTING, "")
    port = os.environ.get(PROXY_PORT_SETTING, "")
    if not host and not port:
        return None
    if not SAFE_PROXY_HOST.fullmatch(host):
        pytest.fail(
            "PMV_EGRESS_PROXY_HOST must be a bare hostname or IPv4 address "
            "(no scheme, userinfo, port, or path)",
            pytrace=False,
        )
    if not (port.isascii() and port.isdigit() and 1 <= int(port) <= 65535):
        pytest.fail("PMV_EGRESS_PROXY_PORT must be an integer from 1 to 65535", pytrace=False)
    return host, int(port)


def _connect_status(host: str, address: tuple[str, int]) -> str:
    """Return the proxy's status line for a credential-free CONNECT host:443."""
    try:
        with socket.create_connection(address, timeout=15) as sock:
            sock.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode())
            reply = sock.recv(4096)
    except OSError as exc:
        return f"connection-error: {type(exc).__name__}"
    return reply.split(b"\r\n", 1)[0].decode("latin-1")


def _probe_address() -> tuple[str, int]:
    address = _proxy_address()
    if address is None:
        pytest.skip(NOT_CONFIGURED)
    return address


@pytest.fixture(autouse=True)
def _refuse_local_variable_tracebacks(request: pytest.FixtureRequest) -> None:
    if os.environ.get("PMV_EGRESS_PROBE") == "1" and request.config.getoption("showlocals"):
        pytest.fail("egress probes refuse to run with local-variable tracebacks", pytrace=False)


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


def test_refusal_pattern_accepts_only_policy_denial() -> None:
    assert REFUSAL_STATUS.match("HTTP/1.1 403 Forbidden")
    for line in ("HTTP/1.1 407 Proxy Authentication Required", "HTTP/1.1 503 Unavailable"):
        assert not REFUSAL_STATUS.match(line)
    assert not REFUSAL_STATUS.match("HTTP/1.1 200 Connection Established")


class _RecordingEnviron(dict[str, str]):
    """An environment stand-in that records every key the code under test looks up."""

    def __init__(self, values: dict[str, str]) -> None:
        super().__init__(values)
        self.looked_up: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.looked_up.append(key)
        return super().__getitem__(key)

    def get(self, key: str, default: str | None = None) -> str | None:  # type: ignore[override]
        self.looked_up.append(key)
        return super().get(key, default)

    def __contains__(self, key: object) -> bool:
        self.looked_up.append(str(key))
        return super().__contains__(key)


def test_runtime_proxy_variables_are_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner decision DR-16: the runtime proxy variables are never looked up, in any case.

    The environment is a stand-in holding dummy values built from fragments; nothing leaves
    the process.
    """
    sentinel = "dummy" + "-sentinel-" + "5b7e"
    runtime_names = [p + "_" + "PROXY" for p in ("HTTP", "HTTPS", "ALL")]
    runtime_names += [name.lower() for name in runtime_names]
    values = {name: "http://u:" + sentinel + "@proxy.invalid:3128" for name in runtime_names}
    for configured in (False, True):
        fake = _RecordingEnviron(dict(values))
        if configured:
            fake.update({PROXY_HOST_SETTING: "proxy.invalid", PROXY_PORT_SETTING: "3128"})
        monkeypatch.setattr(os, "environ", fake)
        expected = ("proxy.invalid", 3128) if configured else None
        assert _proxy_address() == expected
        looked_up = {key.lower() for key in fake.looked_up}
        assert not looked_up & {name.lower() for name in runtime_names}


def test_proxy_settings_reject_userinfo_without_echoing(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = "dummy" + "-sentinel-" + "c41d"
    for host in ("u:" + sentinel + "@proxy.invalid", "http://proxy.invalid", "proxy.invalid:3128"):
        monkeypatch.setenv(PROXY_HOST_SETTING, host)
        monkeypatch.setenv(PROXY_PORT_SETTING, "3128")
        with pytest.raises(pytest.fail.Exception) as excinfo:
            _proxy_address()
        assert sentinel not in str(excinfo.value)
        assert "proxy.invalid" not in str(excinfo.value)
    monkeypatch.setenv(PROXY_HOST_SETTING, "proxy.invalid")
    monkeypatch.setenv(PROXY_PORT_SETTING, "31x8")
    with pytest.raises(pytest.fail.Exception):
        _proxy_address()


def test_connect_request_carries_no_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe sends a bare CONNECT (owner decision DR-10); the socket is a local stub."""
    sent: list[bytes] = []

    class _Stub:
        def __enter__(self) -> "_Stub":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def sendall(self, data: bytes) -> None:
            sent.append(data)

        def recv(self, _n: int) -> bytes:
            return b"HTTP/1.1 403 Forbidden\r\n\r\n"

    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: _Stub())
    status = _connect_status("example.invalid", ("proxy.invalid", 3128))
    assert status == "HTTP/1.1 403 Forbidden"
    request = b"".join(sent)
    assert request == b"CONNECT example.invalid:443 HTTP/1.1\r\nHost: example.invalid:443\r\n\r\n"
    assert b"authoriz" not in request.lower()


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
def test_egress_refuses_prohibited_host(host: str) -> None:
    address = _probe_address()
    # Control inside each probe, so a subset run cannot pass on a broken proxy path.
    control = _connect_status(PRESERVED_DOC_HOSTS[0], address)
    if AUTH_REQUIRED_STATUS.match(control):
        pytest.skip(NOT_APPLICABLE)
    assert ESTABLISHED_STATUS.match(control), f"proxy path broken (control): {control!r}"
    status = _connect_status(host, address)
    assert REFUSAL_STATUS.match(status), f"{host} not refused by the proxy: {status!r}"


@probe
@pytest.mark.parametrize("host", PRESERVED_DOC_HOSTS)
def test_documentation_hosts_stay_reachable(host: str) -> None:
    """Positive control: B10-D10 preserves documentation hosts."""
    status = _connect_status(host, _probe_address())
    if AUTH_REQUIRED_STATUS.match(status):
        pytest.skip(NOT_APPLICABLE)
    assert ESTABLISHED_STATUS.match(status), f"documentation host {host} not reachable: {status!r}"
