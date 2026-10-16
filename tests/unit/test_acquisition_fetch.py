"""G-4 fetcher semantics with a synthetic transport only. No real request is ever made."""

import errno
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from pmv.acquisition.fetch import (
    Credential,
    Fetcher,
    FetchError,
    FetchFailure,
    FetchPolicy,
    FetchRequest,
    TransportFailureError,
    TransportTimeoutError,
)
from pmv.acquisition.hosts import UrlAllowlist
from pmv.acquisition.synthetic import (
    DECISION,
    HOST,
    PREFIX,
    ScriptedResponse,
    SyntheticTransport,
    ok,
    redirect,
    sha256,
)

DATA = b"row,value\n0,1\n"
URL = PREFIX + "a.csv"
ALLOW = UrlAllowlist.build([PREFIX], {PREFIX: DECISION})
POLICY = FetchPolicy(free_space_margin_bytes=0)


@pytest.fixture
def quarantine(tmp_path: Path) -> Iterator[tuple[Path, int]]:
    directory = tmp_path / "q"
    directory.mkdir()
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield directory, fd
    finally:
        os.close(fd)


def _fetcher(transport: SyntheticTransport, **kwargs: object) -> Fetcher:
    kwargs.setdefault("policy", POLICY)
    return Fetcher(ALLOW, transport, **kwargs)  # type: ignore[arg-type]


def _fails(
    transport: SyntheticTransport,
    quarantine: tuple[Path, int],
    failure: FetchFailure,
    request: FetchRequest | None = None,
    **kwargs: object,
) -> None:
    directory, fd = quarantine
    with pytest.raises(FetchError) as caught:
        _fetcher(transport, **kwargs).fetch(request or FetchRequest(URL, "a.csv", 1024), fd)
    assert caught.value.failure is failure
    assert list(directory.iterdir()) == []  # nothing partial is ever named


def test_approved_url_is_fetched_hashed_and_named(quarantine: tuple[Path, int]) -> None:
    directory, fd = quarantine
    transport = SyntheticTransport({URL: ok(DATA)})
    fetched = _fetcher(transport).fetch(
        FetchRequest(URL, "a.csv", 1024, expected_size=len(DATA), expected_sha256=sha256(DATA)),
        fd,
    )
    assert (fetched.size, fetched.sha256, fetched.hash_source) == (
        len(DATA),
        sha256(DATA),
        "provider",
    )
    assert (directory / "a.csv").read_bytes() == DATA
    assert (directory / "a.csv").stat().st_mode & 0o777 == 0o400
    assert [request.url for request in transport.requests] == [URL]
    headers = dict(transport.requests[0].headers)
    assert headers["Accept-Encoding"] == "identity"


@pytest.mark.parametrize(
    "url",
    [
        "https://other.example/synthetic/a.csv",
        f"https://{HOST}/elsewhere/a.csv",
        f"http://{HOST}/synthetic/a.csv",
        f"https://user:pw@{HOST}/synthetic/a.csv",
        f"https://{HOST}/synthetic/a.csv?x=1",
        f"https://{HOST}/synthetic/a.csv#frag",
        f"https://{HOST}/synthetic/%2e%2e/a.csv",
        f"https://{HOST}/synthetic/../live/a.csv",
        f"https://{HOST}/synthetic//a.csv",
        f"https://{HOST}:8443/synthetic/a.csv",
        "https://127.0.0.1/synthetic/a.csv",
        "not a url",
        f"https://{HOST}/synthetic/a\\b.csv",
    ],
)
def test_refused_urls_never_reach_the_transport(url: str, quarantine: tuple[Path, int]) -> None:
    transport = SyntheticTransport({url: ok(DATA)})
    _fails(transport, quarantine, FetchFailure.URL_REFUSED, FetchRequest(url, "a.csv", 1024))
    assert transport.requests == []


def test_same_host_redirect_in_scope_is_rechecked_and_followed(
    quarantine: tuple[Path, int],
) -> None:
    _, fd = quarantine
    target = PREFIX + "v/a.csv"
    transport = SyntheticTransport({URL: redirect("v/a.csv"), target: ok(DATA)})
    fetched = _fetcher(transport).fetch(FetchRequest(URL, "a.csv", 1024), fd)
    assert fetched.final_url == target
    assert fetched.redirects == (target,)


@pytest.mark.parametrize(
    ("location", "failure"),
    [
        ("https://evil.example/synthetic/a.csv", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        (f"https://{HOST}/outside/a.csv", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        (f"https://api.{HOST[6:]}/synthetic/a.csv", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        (
            "https://api.elections.kalshi.com/trade-api/v2/markets",
            FetchFailure.REDIRECT_OUT_OF_SCOPE,
        ),
        ("https://clob.polymarket.com/book", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        (f"http://{HOST}/synthetic/b.csv", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        (f"https://{HOST}/synthetic/b.csv?token=1", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        ("https://127.0.0.1/synthetic/a.csv", FetchFailure.REDIRECT_OUT_OF_SCOPE),
        ("https://169.254.169.254/latest/meta-data", FetchFailure.REDIRECT_OUT_OF_SCOPE),
    ],
)
def test_redirect_out_of_scope_is_refused_before_a_second_request(
    location: str, failure: FetchFailure, quarantine: tuple[Path, int]
) -> None:
    transport = SyntheticTransport({URL: redirect(location), location: ok(DATA)})
    _fails(transport, quarantine, failure)
    assert [request.url for request in transport.requests] == [URL]


def test_cross_host_redirect_is_refused_even_to_an_approved_host(
    quarantine: tuple[Path, int],
) -> None:
    second = "https://mirror.vendor.example/synthetic/"
    allow = UrlAllowlist.build([PREFIX, second], {PREFIX: DECISION, second: DECISION})
    target = second + "a.csv"
    transport = SyntheticTransport({URL: redirect(target), target: ok(DATA)})
    directory, fd = quarantine
    with pytest.raises(FetchError) as caught:
        Fetcher(allow, transport, policy=POLICY).fetch(FetchRequest(URL, "a.csv", 1024), fd)
    assert caught.value.failure is FetchFailure.CROSS_HOST_REDIRECT
    assert len(transport.requests) == 1
    assert list(directory.iterdir()) == []


def test_redirect_loop(quarantine: tuple[Path, int]) -> None:
    other = PREFIX + "b.csv"
    transport = SyntheticTransport({URL: redirect(other), other: redirect(URL)})
    _fails(transport, quarantine, FetchFailure.REDIRECT_LOOP)
    assert len(transport.requests) == 2


def test_maximum_redirect_count(quarantine: tuple[Path, int]) -> None:
    routes = {PREFIX + f"{i}.csv": redirect(PREFIX + f"{i + 1}.csv") for i in range(5)}
    routes[URL] = redirect(PREFIX + "0.csv")
    transport = SyntheticTransport(routes)
    _fails(
        transport,
        quarantine,
        FetchFailure.TOO_MANY_REDIRECTS,
        policy=FetchPolicy(max_redirects=2, free_space_margin_bytes=0),
    )
    assert len(transport.requests) == 3


@pytest.mark.parametrize(
    "headers",
    [
        (),
        (("Location", PREFIX + "b.csv"), ("Location", PREFIX + "c.csv")),
        (("Location", PREFIX + "b .csv"),),
        (("Location", ""),),
    ],
)
def test_malformed_redirects(
    headers: tuple[tuple[str, str], ...], quarantine: tuple[Path, int]
) -> None:
    transport = SyntheticTransport({URL: ScriptedResponse(status=301, headers=headers)})
    _fails(transport, quarantine, FetchFailure.REDIRECT_MALFORMED)


def test_credential_goes_only_to_its_host_and_never_past_a_redirect(
    quarantine: tuple[Path, int],
) -> None:
    _, fd = quarantine
    target = PREFIX + "v/a.csv"
    transport = SyntheticTransport({URL: redirect(target), target: ok(DATA)})
    credential = Credential(HOST, "Authorization", "synthetic-not-a-secret")
    _fetcher(transport, credential=credential).fetch(FetchRequest(URL, "a.csv", 1024), fd)
    first, second = (dict(request.headers) for request in transport.requests)
    assert first["Authorization"] == "synthetic-not-a-secret"
    assert "Authorization" not in second
    assert "synthetic-not-a-secret" not in repr(credential)


def test_credential_for_another_host_is_refused(quarantine: tuple[Path, int]) -> None:
    transport = SyntheticTransport({URL: ok(DATA)})
    credential = Credential("other.example", "Authorization", "synthetic-not-a-secret")
    _fails(transport, quarantine, FetchFailure.CREDENTIAL_REFUSED, credential=credential)
    assert transport.requests == []


@pytest.mark.parametrize(
    ("error", "failure"),
    [
        (TransportTimeoutError(), FetchFailure.TIMEOUT),
        (TransportFailureError(), FetchFailure.TRANSPORT_ERROR),
        (ConnectionResetError(), FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME),
        (RuntimeError("surprise"), FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME),
    ],
)
def test_transport_errors_are_failures(
    error: Exception, failure: FetchFailure, quarantine: tuple[Path, int]
) -> None:
    _fails(SyntheticTransport({URL: ScriptedResponse(error=error)}), quarantine, failure)


@pytest.mark.parametrize(
    ("error", "failure"),
    [
        (TransportTimeoutError(), FetchFailure.TIMEOUT),
        (TransportFailureError(), FetchFailure.TRANSPORT_ERROR),
        (ConnectionResetError(), FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME),
    ],
)
def test_errors_mid_body_are_failures_and_leave_nothing(
    error: Exception, failure: FetchFailure, quarantine: tuple[Path, int]
) -> None:
    response = ok(DATA, chunk=4)
    response.body_error = error
    response.body_error_after = 2
    _fails(SyntheticTransport({URL: response}), quarantine, failure)
    assert response.closed


@pytest.mark.parametrize("status", [201, 204, 206, 304, 400, 403, 404, 429, 500, 503])
def test_non_success_status(status: int, quarantine: tuple[Path, int]) -> None:
    response = ok(DATA)
    response.status = status
    _fails(SyntheticTransport({URL: response}), quarantine, FetchFailure.HTTP_STATUS)


@pytest.mark.parametrize(
    "response",
    [
        ScriptedResponse(status=True),
        ScriptedResponse(status=99),
        ScriptedResponse(headers=[("Content-Length", 4)]),  # type: ignore[list-item]
        ScriptedResponse(headers=[("X\r\nInjected", "1")]),
        ScriptedResponse(headers=[("Content-Length", "4")], chunks=["text"]),  # type: ignore[list-item]
    ],
)
def test_responses_outside_the_contract_are_ambiguous(
    response: ScriptedResponse, quarantine: tuple[Path, int]
) -> None:
    _fails(
        SyntheticTransport({URL: response}), quarantine, FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME
    )


@pytest.mark.parametrize(
    ("headers", "failure"),
    [
        ((("Content-Encoding", "gzip"),), FetchFailure.CONTENT_ENCODING),
        ((("Content-Encoding", "br"),), FetchFailure.CONTENT_ENCODING),
        ((("Transfer-Encoding", "gzip, chunked"),), FetchFailure.CONTENT_ENCODING),
    ],
)
def test_unexpected_encodings(
    headers: tuple[tuple[str, str], ...], failure: FetchFailure, quarantine: tuple[Path, int]
) -> None:
    _fails(SyntheticTransport({URL: ok(DATA, headers=headers)}), quarantine, failure)


@pytest.mark.parametrize(
    ("headers", "failure"),
    [
        ((), FetchFailure.CONTENT_LENGTH_MISSING),
        ((("Content-Length", "-1"),), FetchFailure.CONTENT_LENGTH_MALFORMED),
        ((("Content-Length", "1e3"),), FetchFailure.CONTENT_LENGTH_MALFORMED),
        (
            (("Content-Length", "14"), ("Content-Length", "15")),
            FetchFailure.CONTENT_LENGTH_MALFORMED,
        ),
        ((("Content-Length", "9" * 25),), FetchFailure.CONTENT_LENGTH_MALFORMED),
        ((("Content-Length", "99999"),), FetchFailure.OVERSIZED),
        ((("Content-Length", "20"),), FetchFailure.TRUNCATED),
        ((("Content-Length", "5"),), FetchFailure.LENGTH_MISMATCH),
    ],
)
def test_content_length_rules(
    headers: tuple[tuple[str, str], ...], failure: FetchFailure, quarantine: tuple[Path, int]
) -> None:
    response = ScriptedResponse(status=200, headers=headers, chunks=[DATA])
    _fails(SyntheticTransport({URL: response}), quarantine, failure)


def test_missing_content_length_allowed_only_by_policy_and_still_capped(
    quarantine: tuple[Path, int],
) -> None:
    lax = FetchPolicy(require_content_length=False, free_space_margin_bytes=0)
    response = ScriptedResponse(status=200, headers=(), chunks=[DATA] * 100)
    _fails(
        SyntheticTransport({URL: response}),
        quarantine,
        FetchFailure.OVERSIZED,
        FetchRequest(URL, "a.csv", 1000),
        policy=lax,
    )


@pytest.mark.parametrize(
    ("request_kwargs", "failure"),
    [
        ({"expected_size": len(DATA) - 1}, FetchFailure.SIZE_MISMATCH),
        ({"expected_sha256": "0" * 64}, FetchFailure.HASH_MISMATCH),
    ],
)
def test_expected_size_and_provider_hash(
    request_kwargs: dict[str, object], failure: FetchFailure, quarantine: tuple[Path, int]
) -> None:
    request = FetchRequest(URL, "a.csv", 1024, **request_kwargs)  # type: ignore[arg-type]
    _fails(SyntheticTransport({URL: ok(DATA)}), quarantine, failure, request)


def test_deadline_applies_between_chunks(quarantine: tuple[Path, int]) -> None:
    ticks = iter(range(0, 10_000, 100))
    _fails(
        SyntheticTransport({URL: ok(DATA, chunk=2)}),
        quarantine,
        FetchFailure.TIMEOUT,
        policy=FetchPolicy(deadline_seconds=250, free_space_margin_bytes=0),
        clock=lambda: float(next(ticks)),
    )


def test_insufficient_disk_is_checked_before_the_body(quarantine: tuple[Path, int]) -> None:
    response = ok(DATA)
    _fails(
        SyntheticTransport({URL: response}),
        quarantine,
        FetchFailure.INSUFFICIENT_DISK,
        disk_free=lambda _fd: 10,
    )


def test_disk_full_mid_write_leaves_nothing(
    quarantine: tuple[Path, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write = os.write
    calls = {"n": 0}

    def full(fd: int, data: bytes) -> int:
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_write(fd, data)

    monkeypatch.setattr("pmv.acquisition.fetch.os.write", full)
    _fails(SyntheticTransport({URL: ok(DATA, chunk=3)}), quarantine, FetchFailure.DISK_FULL)


def test_existing_name_is_never_overwritten(quarantine: tuple[Path, int]) -> None:
    directory, fd = quarantine
    (directory / "a.csv").write_bytes(b"earlier")
    with pytest.raises(FetchError) as caught:
        _fetcher(SyntheticTransport({URL: ok(DATA)})).fetch(FetchRequest(URL, "a.csv", 1024), fd)
    assert caught.value.failure is FetchFailure.NAME_EXISTS
    assert (directory / "a.csv").read_bytes() == b"earlier"


@pytest.mark.parametrize("name", ["../a.csv", "a/b.csv", "", "."])
def test_request_names_are_plain_components(name: str) -> None:
    with pytest.raises(Exception, match="unsafe path component"):
        FetchRequest(URL, name, 1024)
