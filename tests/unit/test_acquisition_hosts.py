"""Host-class and URL-allowlist enforcement for acquisition (A-1; external_access §1.1).

Every host here is a reserved ``example`` name or a hypothetical. Nothing is contacted.
"""

import pytest

from pmv.acquisition.hosts import (
    HostPolicyError,
    UrlAllowlist,
    host_restriction,
    path_restriction,
    validate_host,
)

DECISION = "docs/decisions/2099-01-01_hypothetical_host_class.md"
FILES = "https://files.example.com/history/"


@pytest.fixture
def allowlist() -> UrlAllowlist:
    return UrlAllowlist.build([FILES, "https://docs.example.org/x"], {FILES: DECISION})


@pytest.mark.parametrize(
    "url",
    [
        "https://files.example.com/history/2024/a.csv",
        "https://files.example.com:443/history/a.parquet",
        "https://docs.example.org/x",
        "https://docs.example.org/x/y.txt",
    ],
)
def test_allowed_urls(allowlist: UrlAllowlist, url: str) -> None:
    assert allowlist.check(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://files.example.com/history/a.csv",
        "https://files.example.com:8443/history/a.csv",
        "https://user@files.example.com/history/a.csv",
        "https://user:pw@files.example.com/history/a.csv",
        "https://files.example.com/history/a.csv?x=1",
        "https://files.example.com/history/a.csv#frag",
        "https://files.example.com/other/a.csv",
        "https://files.example.com/history",
        "https://docs.example.org/xy",
        "https://cdn.files.example.com/history/a.csv",
        "https://example.com/history/a.csv",
        "https://FILES.example.com/history/a.csv",
        "https://files.example.com/history/../secret.csv",
        "https://files.example.com/history/%2e%2e/secret.csv",
        "https://files.example.com/history/%252e%252e/secret.csv",
        "https://files.example.com/history/%u002e/secret.csv",
        "https://files.example.com/history/..;/secret.csv",
        "https://files.example.com/history/a.csv;jsessionid=1",
        "https://files.example.com/history//a.csv",
        "https://files.example.com/history/a\\b.csv",
        "https://files.example.com/history/a b.csv",
        "https://files.example.com/history/é.csv",
        "https://files.example.com./history/a.csv",
        "https://93.184.216.34/history/a.csv",
        "https://[::1]/history/a.csv",
        "https://xn--fles-9qa.example.com/history/a.csv",
        "wss://files.example.com/history/a.csv",
        "ftp://files.example.com/history/a.csv",
        "https://files.example.com@evil.example.net/history/a.csv",
    ],
)
def test_refused_urls(allowlist: UrlAllowlist, url: str) -> None:
    with pytest.raises(HostPolicyError):
        allowlist.check(url)


@pytest.mark.parametrize(
    "host",
    [
        "api.example.com",
        "api2.example.com",
        "apis.example.com",
        "api.exchange.bullish.com",
        "trading-api.example.com",
        "gamma-api.example.com",
        "feed.example.com",
        "quotes.example.com",
        "ticker.example.com",
        "prices.example.com",
        "marketdata.example.com",
        "md.example.com",
        "ws1.example.com",
        "streamer.example.com",
        "rpc2.example.com",
        "polygon-rpc.example.com",
        "clob.example.com",
        "clob-staging.example.com",
        "data.example.com",
        "data2.example.com",
        "assets.example.com",
        "trading.example.com",
    ],
)
def test_restricted_hosts(host: str) -> None:
    assert host_restriction(host) is not None


@pytest.mark.parametrize("host", ["docs.example.com", "files.example.com", "www.example.org"])
def test_unrestricted_hosts(host: str) -> None:
    assert host_restriction(host) is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/trades",
        "/x/v1/y",
        "/graphql",
        "/ws",
        "/stream/btc",
        "/history/a.json",
        "/history/a.jsonl",
        "/history/A.CSV",
    ],
)
def test_restricted_paths(path: str) -> None:
    assert path_restriction(path) is not None


@pytest.mark.parametrize("path", ["/history/", "/history/a.parquet", "/docs/vintage/x.txt"])
def test_unrestricted_paths(path: str) -> None:
    assert path_restriction(path) is None


def test_restricted_prefix_needs_a_decision_for_that_exact_prefix() -> None:
    with pytest.raises(HostPolicyError, match="owner host-class decision"):
        UrlAllowlist.build(["https://api.example.com/historical/"])
    with pytest.raises(HostPolicyError, match="owner host-class decision"):
        UrlAllowlist.build(["https://files.example.com/api/history/"])
    prefix = "https://api.example.com/historical/"
    allowlist = UrlAllowlist.build([prefix], {prefix: DECISION})
    assert allowlist.check("https://api.example.com/historical/a.parquet")
    with pytest.raises(HostPolicyError):
        allowlist.check("https://api.example.com/markets/live")


def test_restricted_url_under_an_unclassified_prefix_is_refused() -> None:
    allowlist = UrlAllowlist.build([FILES])
    assert allowlist.check("https://files.example.com/history/a.parquet")
    with pytest.raises(HostPolicyError, match="no owner host-class decision"):
        allowlist.check("https://files.example.com/history/a.csv")
    with pytest.raises(HostPolicyError, match="no owner host-class decision"):
        allowlist.check("https://files.example.com/history/api/x.parquet")


def test_host_class_decision_must_name_a_listed_prefix_and_a_record() -> None:
    with pytest.raises(HostPolicyError, match="outside the allowlist"):
        UrlAllowlist.build([FILES], {"https://files.example.com/": DECISION})
    with pytest.raises(HostPolicyError, match="docs/decisions"):
        UrlAllowlist.build([FILES], {FILES: "trust me"})
    with pytest.raises(HostPolicyError, match="docs/decisions"):
        UrlAllowlist.build([FILES], {FILES: "docs/decisions/../../etc/x.md"})


def test_empty_and_duplicate_allowlists_are_refused() -> None:
    with pytest.raises(HostPolicyError, match="at least one"):
        UrlAllowlist.build([])
    with pytest.raises(HostPolicyError, match="duplicate"):
        UrlAllowlist.build([FILES, FILES])


@pytest.mark.parametrize(
    "host", ["", "localhost", "a..b", "-a.example.com", "a.123", "A.example", "xn--a.example"]
)
def test_invalid_hosts(host: str) -> None:
    with pytest.raises(HostPolicyError):
        validate_host(host)
