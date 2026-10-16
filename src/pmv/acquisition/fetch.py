"""Deterministic acquisition fetcher behind an injectable transport (G-4).

``Fetcher.fetch`` downloads one approved URL into a quarantine directory. It never opens
a network connection itself: every request goes through a ``Transport``, so the fetch
semantics are fully testable with synthetic transports. **No production transport
exists.** A reviewed network transport (TLS verification, DNS and IP pinning, refusal of
private and link-local addresses) is a separate, governed component, and acquisition
refuses to run in real mode without one (``pipeline``).

Rules, each fail-closed:
- **Before any request:** the URL must pass the approval's allowlist (``hosts.UrlAllowlist``:
  exact host and path prefix, ``https`` only, no user information, query, fragment,
  percent-encoding, dot segments, or IP literal, and §1.1 rules 1 and 8). A refused URL
  never reaches the transport.
- **Redirects** (301, 302, 303, 307, 308): exactly one ``Location``. The target is
  resolved, then classified again from scratch by the same allowlist, including the
  restricted host and path classes. A redirect to another host is never followed, even
  to an approved host (§1.1 rule 10). A repeated URL is a loop. At most
  ``max_redirects`` are followed. Each refusal happens before the next request.
- **Sensitive headers** (a credential) are sent only on the first request, only to the
  credential's exact host, and never after a redirect.
- **Response:** status 200 only. No content encoding other than ``identity``, and no
  transfer encoding other than ``chunked``. ``Content-Length`` is required by default,
  must be one plain decimal, and must not exceed the cap. The body may not exceed the cap
  or ``Content-Length``, and must not stop short of it. An expected size and a provider
  SHA-256, where known, must match.
- **Time:** one deadline for the whole fetch, checked before each request and each chunk.
- **Disk:** free space is checked before the body is read; ``ENOSPC`` is a failure.
- **Transport:** a timeout, a transport error, or anything the transport does outside its
  contract (wrong types, unexpected exceptions) is a failure. A failure never counts as a
  successful acquisition.

The body is written into an unnamed ``O_TMPFILE`` inode in the quarantine directory and
hashed as it is written. Only after every check passes is the inode given its name
(``linkat``, which never overwrites). On any failure nothing is named, so no partial file
can reach quarantine, let alone release.
"""

import contextlib
import errno
import hashlib
import os
import stat
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol
from urllib.parse import urljoin, urlsplit

from pmv.acquisition.hosts import HostPolicyError, UrlAllowlist
from pmv.acquisition.quarantine import _TMPFILE_FLAGS, _link_fd
from pmv.integrity import is_sha256
from pmv.safe_fs import component

USER_AGENT: Final = "pmv-acquisition/1"
REDIRECT_STATUSES: Final = frozenset({301, 302, 303, 307, 308})
_CONTENT_LENGTH_DIGITS: Final = 19
_HEADER_LIMIT: Final = 8192
Clock = Callable[[], float]
DiskFree = Callable[[int], int]


class TransportTimeoutError(Exception):
    """The transport gave up waiting. Raised by a Transport."""


class TransportFailureError(Exception):
    """The transport failed (connection, TLS, protocol). Raised by a Transport."""


@dataclass(frozen=True, slots=True)
class TransportRequest:
    url: str
    headers: tuple[tuple[str, str], ...]
    timeout_seconds: float


class TransportResponse(Protocol):
    status: int
    headers: Sequence[tuple[str, str]]

    def iter_body(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...


class Transport(Protocol):
    """Sends one request and returns its response, without following redirects."""

    synthetic: bool

    def send(self, request: TransportRequest) -> TransportResponse: ...


class FetchFailure(StrEnum):
    URL_REFUSED = "url_refused"
    CREDENTIAL_REFUSED = "credential_refused"
    REDIRECT_MALFORMED = "redirect_malformed"
    REDIRECT_OUT_OF_SCOPE = "redirect_out_of_scope"
    CROSS_HOST_REDIRECT = "cross_host_redirect"
    REDIRECT_LOOP = "redirect_loop"
    TOO_MANY_REDIRECTS = "too_many_redirects"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    AMBIGUOUS_TRANSPORT_OUTCOME = "ambiguous_transport_outcome"
    HTTP_STATUS = "http_status"
    CONTENT_ENCODING = "content_encoding"
    CONTENT_LENGTH_MISSING = "content_length_missing"
    CONTENT_LENGTH_MALFORMED = "content_length_malformed"
    OVERSIZED = "oversized"
    LENGTH_MISMATCH = "length_mismatch"
    TRUNCATED = "truncated"
    SIZE_MISMATCH = "size_mismatch"
    HASH_MISMATCH = "hash_mismatch"
    INSUFFICIENT_DISK = "insufficient_disk"
    DISK_FULL = "disk_full"
    WRITE_FAILED = "write_failed"
    NAME_EXISTS = "name_exists"


class FetchError(Exception):
    """A fetch failed. Nothing was named in quarantine. Carries a closed code only."""

    def __init__(self, failure: FetchFailure) -> None:
        super().__init__(failure.value)
        self.failure = failure


@dataclass(frozen=True, slots=True)
class Credential:
    """One sensitive request header for one exact host. Its value is never printed."""

    host: str
    header: str
    value: str = field(repr=False)

    def __repr__(self) -> str:
        return f"Credential(host={self.host!r}, header={self.header!r}, value=<redacted>)"


@dataclass(frozen=True, slots=True)
class FetchPolicy:
    max_redirects: int = 3
    require_content_length: bool = True
    deadline_seconds: float = 3600.0
    request_timeout_seconds: float = 60.0
    free_space_margin_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        if not (0 <= self.max_redirects <= 10):
            raise ValueError("max_redirects must be between 0 and 10")
        if self.deadline_seconds <= 0 or self.request_timeout_seconds <= 0:
            raise ValueError("timeouts must be positive")
        if self.free_space_margin_bytes < 0:
            raise ValueError("free_space_margin_bytes must not be negative")


@dataclass(frozen=True, slots=True)
class FetchRequest:
    url: str
    name: str
    max_bytes: int
    expected_size: int | None = None
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        component(self.name)
        if type(self.max_bytes) is not int or self.max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if self.expected_size is not None and (
            type(self.expected_size) is not int or not 0 <= self.expected_size <= self.max_bytes
        ):
            raise ValueError("expected_size must be an integer within max_bytes")
        if self.expected_sha256 is not None and not is_sha256(self.expected_sha256):
            raise ValueError("expected_sha256 must be a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class FetchedFile:
    name: str
    size: int
    sha256: str
    final_url: str
    redirects: tuple[str, ...]
    content_length: int | None
    hash_source: str


def statvfs_free(fd: int) -> int:
    status = os.fstatvfs(fd)
    return status.f_bavail * status.f_frsize


def _headers(response: TransportResponse) -> dict[str, list[str]]:
    """Validate and index response headers by lower-case name."""
    raw = response.headers
    if not isinstance(raw, list | tuple) or len(raw) > 256:
        raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
    result: dict[str, list[str]] = {}
    for item in raw:
        if not isinstance(item, tuple) or len(item) != 2:
            raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
        name, value = item
        if not isinstance(name, str) or not isinstance(value, str):
            raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
        if not name.isascii() or not value.isascii() or len(name) + len(value) > _HEADER_LIMIT:
            raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
        if any(char in name + value for char in "\r\n\x00"):
            raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
        result.setdefault(name.strip().lower(), []).append(value.strip())
    return result


def _status(response: TransportResponse) -> int:
    status = getattr(response, "status", None)
    if type(status) is not int or not 100 <= status <= 599:
        raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
    return status


def _content_length(headers: dict[str, list[str]], required: bool) -> int | None:
    values = headers.get("content-length")
    if not values:
        if required:
            raise FetchError(FetchFailure.CONTENT_LENGTH_MISSING)
        return None
    if len(set(values)) != 1:
        raise FetchError(FetchFailure.CONTENT_LENGTH_MALFORMED)
    text = values[0]
    if not text.isdigit() or not text.isascii() or len(text) > _CONTENT_LENGTH_DIGITS:
        raise FetchError(FetchFailure.CONTENT_LENGTH_MALFORMED)
    return int(text)


def _check_encoding(headers: dict[str, list[str]]) -> None:
    for value in headers.get("content-encoding", []):
        if value.lower() != "identity":
            raise FetchError(FetchFailure.CONTENT_ENCODING)
    for value in headers.get("transfer-encoding", []):
        if value.lower() != "chunked":
            raise FetchError(FetchFailure.CONTENT_ENCODING)


class Fetcher:
    """Fetches approved URLs into one quarantine directory through a Transport."""

    def __init__(
        self,
        allowlist: UrlAllowlist,
        transport: Transport,
        *,
        policy: FetchPolicy | None = None,
        clock: Clock = time.monotonic,
        disk_free: DiskFree = statvfs_free,
        credential: Credential | None = None,
    ) -> None:
        self._allowlist = allowlist
        self._transport = transport
        self._policy = policy or FetchPolicy()
        self._clock = clock
        self._disk_free = disk_free
        self._credential = credential

    def _check(self, url: str, failure: FetchFailure) -> tuple[str, str]:
        try:
            self._allowlist.check(url)
        except HostPolicyError:
            raise FetchError(failure) from None
        parts = urlsplit(url)
        return parts.hostname or "", url

    def _request(self, url: str, first: bool, deadline: float) -> TransportResponse:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise FetchError(FetchFailure.TIMEOUT)
        headers: list[tuple[str, str]] = [
            ("Accept-Encoding", "identity"),
            ("User-Agent", USER_AGENT),
        ]
        if first and self._credential is not None:
            headers.append((self._credential.header, self._credential.value))
        request = TransportRequest(
            url=url,
            headers=tuple(headers),
            timeout_seconds=min(self._policy.request_timeout_seconds, remaining),
        )
        try:
            return self._transport.send(request)
        except TransportTimeoutError:
            raise FetchError(FetchFailure.TIMEOUT) from None
        except TransportFailureError:
            raise FetchError(FetchFailure.TRANSPORT_ERROR) from None
        except Exception:  # noqa: BLE001 - outside the transport contract: fail closed
            raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME) from None

    def _redirect_target(self, current: str, headers: dict[str, list[str]]) -> str:
        locations = headers.get("location", [])
        if len(locations) != 1 or not locations[0]:
            raise FetchError(FetchFailure.REDIRECT_MALFORMED)
        location = locations[0]
        if any(ord(char) < 0x21 or ord(char) == 0x7F for char in location):
            raise FetchError(FetchFailure.REDIRECT_MALFORMED)
        return urljoin(current, location)

    def fetch(self, request: FetchRequest, directory_fd: int) -> FetchedFile:
        """Fetch ``request.url`` into ``directory_fd`` under ``request.name``."""
        deadline = self._clock() + self._policy.deadline_seconds
        host, url = self._check(request.url, FetchFailure.URL_REFUSED)
        if self._credential is not None and self._credential.host != host:
            raise FetchError(FetchFailure.CREDENTIAL_REFUSED)
        visited = [url]
        redirects: list[str] = []
        first = True
        while True:
            response = self._request(url, first, deadline)
            first = False
            try:
                status = _status(response)
                headers = _headers(response)
                if status in REDIRECT_STATUSES:
                    target = self._redirect_target(url, headers)
                    target_host, target = self._check(target, FetchFailure.REDIRECT_OUT_OF_SCOPE)
                    if target_host != host:
                        raise FetchError(FetchFailure.CROSS_HOST_REDIRECT)
                    if target in visited:
                        raise FetchError(FetchFailure.REDIRECT_LOOP)
                    if len(redirects) >= self._policy.max_redirects:
                        raise FetchError(FetchFailure.TOO_MANY_REDIRECTS)
                    redirects.append(target)
                    visited.append(target)
                    url = target
                    continue
                if status != 200:
                    raise FetchError(FetchFailure.HTTP_STATUS)
                return self._receive(
                    request, response, headers, directory_fd, deadline, url, redirects
                )
            finally:
                _close(response)

    def _receive(
        self,
        request: FetchRequest,
        response: TransportResponse,
        headers: dict[str, list[str]],
        directory_fd: int,
        deadline: float,
        final_url: str,
        redirects: list[str],
    ) -> FetchedFile:
        _check_encoding(headers)
        length = _content_length(headers, self._policy.require_content_length)
        if length is not None and length > request.max_bytes:
            raise FetchError(FetchFailure.OVERSIZED)
        if length is not None and request.expected_size not in (None, length):
            raise FetchError(FetchFailure.SIZE_MISMATCH)
        needed = (length if length is not None else request.max_bytes) + (
            self._policy.free_space_margin_bytes
        )
        if self._disk_free(directory_fd) < needed:
            raise FetchError(FetchFailure.INSUFFICIENT_DISK)
        try:
            fd = os.open(".", _TMPFILE_FLAGS, 0o400, dir_fd=directory_fd)
        except OSError:
            raise FetchError(FetchFailure.WRITE_FAILED) from None
        try:
            size, digest = self._write_body(request, response, fd, length, deadline)
            if length is not None and size != length:
                raise FetchError(FetchFailure.TRUNCATED)
            if request.expected_size is not None and size != request.expected_size:
                raise FetchError(FetchFailure.SIZE_MISMATCH)
            if request.expected_sha256 is not None and digest != request.expected_sha256:
                raise FetchError(FetchFailure.HASH_MISMATCH)
            try:
                os.fsync(fd)
                _link_fd(fd, directory_fd, request.name)
                os.fsync(directory_fd)
            except FileExistsError:
                raise FetchError(FetchFailure.NAME_EXISTS) from None
            except OSError as error:
                raise _write_failure(error) from None
            linked = os.stat(request.name, dir_fd=directory_fd, follow_symlinks=False)
            mine = os.fstat(fd)
            if not stat.S_ISREG(linked.st_mode) or (linked.st_dev, linked.st_ino) != (
                mine.st_dev,
                mine.st_ino,
            ):
                raise FetchError(FetchFailure.WRITE_FAILED)
        finally:
            os.close(fd)
        return FetchedFile(
            name=request.name,
            size=size,
            sha256=digest,
            final_url=final_url,
            redirects=tuple(redirects),
            content_length=length,
            hash_source="provider" if request.expected_sha256 is not None else "receipt",
        )

    def _write_body(
        self,
        request: FetchRequest,
        response: TransportResponse,
        fd: int,
        length: int | None,
        deadline: float,
    ) -> tuple[int, str]:
        digest = hashlib.sha256()
        size = 0
        body = _call_transport(response.iter_body)
        while True:
            chunk = _call_transport(lambda: next(body, None))
            if chunk is None:
                break
            if not isinstance(chunk, bytes):
                raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME)
            if self._clock() > deadline:
                raise FetchError(FetchFailure.TIMEOUT)
            size += len(chunk)
            if size > request.max_bytes:
                raise FetchError(FetchFailure.OVERSIZED)
            if length is not None and size > length:
                raise FetchError(FetchFailure.LENGTH_MISMATCH)
            digest.update(chunk)
            view = memoryview(chunk)
            try:
                while view:
                    view = view[os.write(fd, view) :]
            except OSError as error:
                raise _write_failure(error) from None
        return size, digest.hexdigest()


def _call_transport[T](call: Callable[[], T]) -> T:
    """Run one transport call, mapping every outcome outside its contract to a failure."""
    try:
        return call()
    except FetchError:
        raise
    except TransportTimeoutError:
        raise FetchError(FetchFailure.TIMEOUT) from None
    except TransportFailureError:
        raise FetchError(FetchFailure.TRANSPORT_ERROR) from None
    except Exception:  # noqa: BLE001 - outside the transport contract: fail closed
        raise FetchError(FetchFailure.AMBIGUOUS_TRANSPORT_OUTCOME) from None


def _write_failure(error: OSError) -> FetchError:
    if error.errno == errno.ENOSPC:
        return FetchError(FetchFailure.DISK_FULL)
    return FetchError(FetchFailure.WRITE_FAILED)


def _close(response: TransportResponse) -> None:
    with contextlib.suppress(Exception):  # closing never changes the outcome
        response.close()


def quarantine_dir_fd(path: Path) -> int:
    """Open a quarantine directory for fetching (no symlink at the final component)."""
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
