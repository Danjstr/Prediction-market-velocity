"""Trusted parent for isolated parsing and extraction (G-1).

``run_worker`` starts the parse worker (``parse_worker``) as a separate process:
- the same interpreter, run with ``-I`` (no environment variables, user site, or working
  directory on the import path);
- an empty environment, ``/`` as working directory, and a new session (its own process
  group, no controlling terminal);
- only three descriptors: the input file on fd 0, opened read-only by this process, the
  output pipe on fd 1, and ``/dev/null`` on fd 2. The worker never gets a path;
- resource limits (``confinement.WorkerLimits``) applied between ``fork`` and ``exec``.

The worker confines itself with seccomp before reading input (``confinement``). This
parent then enforces, outside the worker:
- a wall-clock deadline (the whole process group is killed when it passes);
- an output-size cap, and per-frame payload caps checked before a payload is buffered;
- the protocol: magic first, then ``HELLO`` with the expected protocol, version, and code
  identity, and ``confined: true``; frames only of the types the operation allows; one
  ``RESULT`` last; nothing after it, and no truncation;
- a clean exit: status 0. A signal, a CPU-limit kill, or any other status is a failure.

A result is returned only after all of that holds, so a partial result is never accepted.
Failures raise ``IsolationError`` with a closed ``IsolationFailure`` code. A worker refusal
of its input raises ``WorkerRefusedError`` with the worker's closed ``RefusalCode``.
Neither carries file content.

``verify_file`` checks that the worker reports the SHA-256 of every input byte it read and
that it equals the expected hash. That is a consistency check on the worker's own report,
not an independent proof (RT-B7-10). The stored bytes are protected by the parent's own
hashes at receipt, integrity check, backup, and store copy. ``isolated_extract`` lets
the worker decompress and walk an archive while this process is the only writer: it
re-validates every member name, re-applies every count, size, total, ratio, and
case-collision limit itself, checks each member's hash, and rolls back everything on any
failure.
"""

import contextlib
import errno
import hashlib
import os
import select
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Final

from pmv.acquisition import archive, readers
from pmv.acquisition import worker_protocol as wp
from pmv.acquisition.confinement import (
    ConfinementError,
    WorkerLimits,
    harden_parent,
    probe_names,
    supported,
)
from pmv.acquisition.formats import (
    EXTENSIONS,
    FileFormat,
    FormatRefusedError,
    check_format,
    extension_of,
)
from pmv.integrity import (
    FormatError,
    canonical_json,
    is_sha256,
    parse_canonical_json,
    sha256_hex,
)
from pmv.safe_fs import NEW_FILE_FLAGS, READ_FLAGS

_READ_SIZE: Final = 256 * 1024
_FRAME_OVERHEAD: Final = wp.HEADER.size
_SMALL_OUTPUT: Final = 1024 * 1024
_FORMAT_BY_EXTENSION: Final = {
    extension: file_format for file_format, names in EXTENSIONS.items() for extension in names
}

FrameHandler = Callable[[bytes, bytes], None]
DiskFree = Callable[[Path], int]


class IsolationFailure(StrEnum):
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    SPAWN_FAILED = "spawn_failed"
    TIMEOUT = "timeout"
    SIGNALED = "signaled"
    CPU_LIMIT = "cpu_limit"
    ABNORMAL_EXIT = "abnormal_exit"
    MALFORMED_OUTPUT = "malformed_output"
    TRUNCATED_OUTPUT = "truncated_output"
    TRAILING_OUTPUT = "trailing_output"
    OVERSIZED_OUTPUT = "oversized_output"
    PROTOCOL_MISMATCH = "protocol_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    NOT_CONFINED = "not_confined"
    PROBE_FAILED = "probe_failed"
    INPUT_MISMATCH = "input_mismatch"


class IsolationError(Exception):
    """The isolated run failed or misbehaved. Nothing from it is used."""

    def __init__(self, failure: IsolationFailure) -> None:
        super().__init__(failure.value)
        self.failure = failure


class WorkerRefusedError(Exception):
    """The worker ran correctly and refused its input with a closed code."""

    def __init__(self, code: wp.RefusalCode, record: int | None) -> None:
        super().__init__(code.value if record is None else f"{code.value} at record {record}")
        self.code = code
        self.record = record


@dataclass(frozen=True, slots=True)
class WorkerRun:
    identity: Mapping[str, object]
    result: Mapping[str, object]

    @property
    def identity_sha256(self) -> str:
        return sha256_hex(canonical_json(dict(self.identity)))


@cache
def expected_identity() -> dict[str, object]:
    """The identity this parent expects the worker to report (same code, same runtime)."""
    from pmv.acquisition.parse_worker import worker_identity  # deferred: heavy import

    return worker_identity()


def _command(parameters: Mapping[str, object]) -> list[str]:
    return [
        sys.executable,
        "-I",
        "-m",
        "pmv.acquisition.parse_worker",
        canonical_json(dict(parameters)).decode("ascii"),
    ]


class _Stream:
    """Incremental parser of the worker's output, enforcing the generic protocol."""

    def __init__(self, on_frame: FrameHandler | None, max_output: int) -> None:
        self._buffer = b""
        self._total = 0
        self._max = max_output
        self._magic = False
        self._on_frame = on_frame
        self.hello: dict[str, object] | None = None
        self.result: dict[str, object] | None = None

    def feed(self, data: bytes) -> None:
        self._total += len(data)
        if self._total > self._max:
            raise IsolationError(IsolationFailure.OVERSIZED_OUTPUT)
        if self.result is not None and data:
            raise IsolationError(IsolationFailure.TRAILING_OUTPUT)
        self._buffer += data
        if not self._magic:
            if len(self._buffer) < len(wp.MAGIC):
                if not wp.MAGIC.startswith(self._buffer):
                    raise IsolationError(IsolationFailure.PROTOCOL_MISMATCH)
                return
            if not self._buffer.startswith(wp.MAGIC):
                raise IsolationError(IsolationFailure.PROTOCOL_MISMATCH)
            self._buffer = self._buffer[len(wp.MAGIC) :]
            self._magic = True
        while len(self._buffer) >= _FRAME_OVERHEAD:
            kind, length = wp.HEADER.unpack_from(self._buffer)
            if kind not in wp.FRAME_TYPES or length > wp.payload_limit(kind):
                raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
            if len(self._buffer) < _FRAME_OVERHEAD + length:
                return
            payload = self._buffer[_FRAME_OVERHEAD : _FRAME_OVERHEAD + length]
            self._buffer = self._buffer[_FRAME_OVERHEAD + length :]
            self._dispatch(kind, payload)
            if self.result is not None and self._buffer:
                raise IsolationError(IsolationFailure.TRAILING_OUTPUT)

    def _dispatch(self, kind: bytes, payload: bytes) -> None:
        if self.hello is None:
            if kind != wp.HELLO:
                raise IsolationError(IsolationFailure.PROTOCOL_MISMATCH)
            self.hello = _json(payload)
            _check_hello(self.hello)  # before any other frame is acted on (RT-B7-10)
            return
        if kind == wp.HELLO:
            raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
        if kind == wp.RESULT:
            self.result = _json(payload)
            return
        if self._on_frame is None or self.hello.get("confined") is not True:
            raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
        self._on_frame(kind, payload)

    def finish(self) -> None:
        if not self._magic or self.hello is None or self.result is None or self._buffer:
            raise IsolationError(IsolationFailure.TRUNCATED_OUTPUT)


def _json(payload: bytes) -> dict[str, object]:
    try:
        return parse_canonical_json(payload)
    except FormatError:
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT) from None


def _kill(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def _exit_failure(returncode: int) -> IsolationFailure | None:
    if returncode == 0:
        return None
    if returncode == -signal.SIGXCPU:
        return IsolationFailure.CPU_LIMIT
    if returncode < 0:
        return IsolationFailure.SIGNALED
    return IsolationFailure.ABNORMAL_EXIT


def _check_hello(hello: Mapping[str, object]) -> None:
    if set(hello) != {"protocol", "version", "confined", "identity"}:
        raise IsolationError(IsolationFailure.PROTOCOL_MISMATCH)
    if hello["protocol"] != wp.PROTOCOL or hello["version"] != wp.PROTOCOL_VERSION:
        raise IsolationError(IsolationFailure.PROTOCOL_MISMATCH)
    if hello["identity"] != expected_identity():
        raise IsolationError(IsolationFailure.IDENTITY_MISMATCH)


def _check_result(result: Mapping[str, object]) -> None:
    status = result.get("status")
    if status == "ok":
        return
    if status != "refused" or set(result) != {"status", "code", "record"}:
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    record = result["record"]
    if record is not None and (type(record) is not int or record < 0):
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    try:
        wp.RefusalCode(str(result["code"]))
    except ValueError:
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT) from None


def run_worker(
    operation: wp.Operation,
    parameters: Mapping[str, object],
    *,
    input_fd: int | None,
    limits: WorkerLimits,
    max_output_bytes: int = _SMALL_OUTPUT,
    on_frame: FrameHandler | None = None,
    command: Sequence[str] | None = None,
) -> WorkerRun:
    """Run one isolated operation and return its validated outcome.

    ``command`` replaces the worker command line; it exists only so tests can substitute
    a misbehaving worker. Raises IsolationError or WorkerRefusedError.
    """
    if not supported():
        raise IsolationError(IsolationFailure.UNSUPPORTED_PLATFORM)
    try:
        harden_parent()
    except (OSError, ConfinementError):
        raise IsolationError(IsolationFailure.SPAWN_FAILED) from None
    document = {"operation": operation.value, "limits": limits.as_parameters(), **parameters}
    argv = list(command) if command is not None else _command(document)
    deadline = time.monotonic() + limits.wall_clock_seconds
    try:
        process = subprocess.Popen(  # noqa: S603 - fixed interpreter and module, no shell
            argv,
            stdin=input_fd if input_fd is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            cwd="/",
            close_fds=True,
            start_new_session=True,
            preexec_fn=limits.apply,  # limits bind before exec
        )
    except OSError:
        raise IsolationError(IsolationFailure.SPAWN_FAILED) from None
    assert process.stdout is not None  # noqa: S101 - stdout=PIPE above
    stream = _Stream(on_frame, max_output_bytes)
    output = process.stdout.fileno()
    poller = select.poll()
    poller.register(output, select.POLLIN | select.POLLHUP | select.POLLERR)
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise IsolationError(IsolationFailure.TIMEOUT)
            if not poller.poll(min(remaining, 1.0) * 1000):
                continue
            chunk = os.read(output, _READ_SIZE)
            if not chunk:
                break
            stream.feed(chunk)
        try:
            returncode = process.wait(timeout=max(deadline - time.monotonic(), 0.01))
        except subprocess.TimeoutExpired:
            raise IsolationError(IsolationFailure.TIMEOUT) from None
    except BaseException:
        _kill(process)
        process.stdout.close()
        raise
    process.stdout.close()
    failure = _exit_failure(returncode)
    if failure is not None:
        raise IsolationError(failure)
    stream.finish()
    assert stream.hello is not None  # noqa: S101 - checked by finish()
    assert stream.result is not None  # noqa: S101 - checked by finish()
    _check_hello(stream.hello)
    _check_result(stream.result)
    if stream.hello["confined"] is not True:
        raise IsolationError(IsolationFailure.NOT_CONFINED)
    if stream.result["status"] == "refused":
        record = stream.result["record"]
        raise WorkerRefusedError(
            wp.RefusalCode(str(stream.result["code"])),
            record if isinstance(record, int) else None,
        )
    identity = stream.hello["identity"]
    assert isinstance(identity, dict)  # noqa: S101 - equals expected_identity()
    return WorkerRun(identity=identity, result=stream.result)


# --- probe --------------------------------------------------------------------------------


def verify_isolation(limits: WorkerLimits | None = None) -> WorkerRun:
    """Run the worker's confinement self-test. Every probed syscall must be denied."""
    run = run_worker(wp.Operation.PROBE, {}, input_fd=None, limits=limits or WorkerLimits())
    probe = run.result.get("probe")
    if set(run.result) != {"status", "probe"} or not isinstance(probe, dict):
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    if set(probe) != set(probe_names()) or not all(value is True for value in probe.values()):
        raise IsolationError(IsolationFailure.PROBE_FAILED)
    return run


# --- verification -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FileSpec:
    """What one file must be: name, format, compression, schema, and parser limits."""

    name: str
    file_format: FileFormat
    compression: readers.Compression
    schema: readers.RecordSchema
    decode: readers.DecodeLimits = field(default_factory=readers.DecodeLimits)
    reader_limits: readers.VerifyLimits = field(default_factory=readers.VerifyLimits)

    def __post_init__(self) -> None:
        if self.schema.file_format is not self.file_format:
            raise readers.SpecError("schema format does not match the file format")
        readers.check_name(self.name, self.file_format, self.compression)

    def parameters(self) -> dict[str, object]:
        return {
            "name": self.name,
            "format": self.file_format.value,
            "compression": self.compression.value,
            "schema": self.schema.document(),
            "decode": self.decode.document(),
            "reader_limits": self.reader_limits.document(),
        }


@dataclass(frozen=True, slots=True)
class Verification:
    """A completed, validated, isolated verification of exact bytes."""

    summary: Mapping[str, object]
    input_bytes: int
    input_sha256: str
    worker_identity_sha256: str

    def document(self) -> dict[str, object]:
        return {
            "summary": dict(self.summary),
            "input_bytes": self.input_bytes,
            "input_sha256": self.input_sha256,
            "worker_identity_sha256": self.worker_identity_sha256,
        }


_SUMMARY_KEYS: Final = frozenset(
    {
        "format",
        "records",
        "decoded_bytes",
        "decoded_sha256",
        "schema_sha256",
        "reader",
        "limits",
    }
)


def _validated_verification(spec: FileSpec, run: WorkerRun) -> Verification:
    result = run.result
    keys = {"status", "summary", "compression", "decode", "input_bytes", "input_sha256"}
    summary = result.get("summary")
    if set(result) != keys or not isinstance(summary, dict) or set(summary) != _SUMMARY_KEYS:
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    expected = {
        "format": spec.file_format.value,
        "schema_sha256": spec.schema.sha256(),
        "reader": readers.READERS[spec.file_format].identity(),
        "limits": spec.reader_limits.document(),
    }
    if any(summary[key] != value for key, value in expected.items()):
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    for key in ("records", "decoded_bytes"):
        value = summary[key]
        if type(value) is not int or value < 0:
            raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    size, digest = result["input_bytes"], result["input_sha256"]
    if (
        result["compression"] != spec.compression.value
        or result["decode"] != spec.decode.document()
        or not is_sha256(summary["decoded_sha256"])
        or type(size) is not int
        or size < 0
        or not is_sha256(digest)
    ):
        raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
    return Verification(
        summary=summary,
        input_bytes=size,
        input_sha256=digest,
        worker_identity_sha256=run.identity_sha256,
    )


def verify_file(
    fd: int,
    spec: FileSpec,
    *,
    expected_size: int,
    expected_sha256: str,
    limits: WorkerLimits | None = None,
    command: Sequence[str] | None = None,
) -> Verification:
    """Verify the file open on ``fd`` in the isolated worker; bind the result to its hash."""
    status = os.fstat(fd)
    if not stat.S_ISREG(status.st_mode):
        raise IsolationError(IsolationFailure.INPUT_MISMATCH)
    run = run_worker(
        wp.Operation.VERIFY,
        spec.parameters(),
        input_fd=fd,
        limits=limits or WorkerLimits(),
        command=command,
    )
    verification = _validated_verification(spec, run)
    if (verification.input_bytes, verification.input_sha256) != (expected_size, expected_sha256):
        raise IsolationError(IsolationFailure.INPUT_MISMATCH)
    return verification


# --- isolated extraction ------------------------------------------------------------------


def _disk_free(path: Path) -> int:
    return os.statvfs(path).f_bavail * os.statvfs(path).f_frsize


class _ExtractionSink:
    """Parent-side writer for an isolated extraction. Trusts nothing the worker says."""

    def __init__(
        self,
        destination: Path,
        limits: archive.ExtractionLimits,
        archive_size: int,
        disk_free: DiskFree,
    ) -> None:
        self.destination = destination
        self.limits = limits
        self.budget = archive._Budget(limits, archive_size)
        self.disk_free = disk_free
        self.extracted: list[archive.ExtractedFile] = []
        self.directories = 0
        self._fd = -1
        self._name = ""
        self._size = 0
        self._written = 0
        self._digest = hashlib.sha256()

    def __call__(self, kind: bytes, payload: bytes) -> None:
        if kind == wp.DIR:
            self._directory(payload)
        elif kind == wp.FILE:
            self._begin(payload)
        elif kind == wp.DATA:
            self._data(payload)
        elif kind == wp.END_FILE:
            self._end(payload)
        else:
            raise archive.ArchiveRefusedError("unexpected frame from the worker")

    def _name_of(self, raw: str, *, is_dir: bool) -> str:
        name = archive.safe_member_name(raw, is_dir=is_dir, max_depth=self.limits.max_depth)
        if name != raw:
            raise archive.ArchiveRefusedError("worker sent a non-normalized member name")
        return name

    def _directory(self, payload: bytes) -> None:
        if self._fd >= 0:
            raise archive.ArchiveRefusedError("directory frame inside a file")
        try:
            raw = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise archive.ArchiveRefusedError("member name is not valid UTF-8") from None
        name = self._name_of(raw, is_dir=True)
        self.budget.admit(name, is_dir=True, size=0)
        self.destination.joinpath(*name.split("/")).mkdir(parents=True, exist_ok=True)
        self.directories += 1

    def _begin(self, payload: bytes) -> None:
        if self._fd >= 0:
            raise archive.ArchiveRefusedError("file frame inside a file")
        header = _json(payload)
        if set(header) != {"name", "size"} or not isinstance(header["name"], str):
            raise archive.ArchiveRefusedError("malformed file frame")
        size = header["size"]
        if type(size) is not int or size < 0:
            raise archive.ArchiveRefusedError("malformed file frame")
        name = self._name_of(header["name"], is_dir=False)
        self.budget.admit(name, is_dir=False, size=size)
        if self.disk_free(self.destination) < size + self.limits.free_space_margin_bytes:
            raise archive.ArchiveRefusedError("insufficient free disk space for extraction")
        target = self.destination.joinpath(*name.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(target, NEW_FILE_FLAGS, 0o600)
        self._name, self._size, self._written = name, size, 0
        self._digest = hashlib.sha256()

    def _data(self, payload: bytes) -> None:
        if self._fd < 0:
            raise archive.ArchiveRefusedError("data frame outside a file")
        self._written += len(payload)
        if self._written > self._size:
            raise archive.ArchiveRefusedError("member data exceeds its declared size")
        self._digest.update(payload)
        view = memoryview(payload)
        while view:
            written = os.write(self._fd, view)
            if written <= 0:
                raise OSError(errno.EIO, "short write")
            view = view[written:]

    def _end(self, payload: bytes) -> None:
        if self._fd < 0:
            raise archive.ArchiveRefusedError("end frame outside a file")
        claimed = _json(payload)
        digest = self._digest.hexdigest()
        if set(claimed) != {"sha256"} or claimed["sha256"] != digest:
            raise archive.ArchiveRefusedError("member hash disagrees with the worker")
        if self._written != self._size:
            raise archive.ArchiveRefusedError("member data is shorter than its declared size")
        self.close()
        self.extracted.append(archive.ExtractedFile(self._name, self._size, digest))

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def check_result(self, result: Mapping[str, object]) -> None:
        if self._fd >= 0:
            raise archive.ArchiveRefusedError("worker ended inside a file")
        expected = {
            "files": len(self.extracted),
            "directories": self.directories,
            "total_bytes": sum(item.size for item in self.extracted),
        }
        keys = {"status", *expected}
        if set(result) not in (keys, keys | {"archive_sha256"}):
            raise IsolationError(IsolationFailure.MALFORMED_OUTPUT)
        if any(result[key] != value for key, value in expected.items()):
            raise archive.ArchiveRefusedError("worker summary disagrees with what was written")


def _check_member_signature(destination: Path, item: archive.ExtractedFile) -> None:
    """Byte-signature check only. Content is validated later by the isolated verifier."""
    declared = _FORMAT_BY_EXTENSION.get(extension_of(item.name))
    if declared is None:
        raise archive.ArchiveRefusedError("archive member has no allowlisted parse format")
    fd = os.open(destination.joinpath(*item.name.split("/")), READ_FLAGS)
    try:
        head = os.pread(fd, 8, 0)
        tail = os.pread(fd, 4, max(item.size - 4, 0))
    finally:
        os.close(fd)
    try:
        check_format(item.name.rsplit("/", 1)[-1], declared, head, tail)
    except FormatRefusedError as error:
        raise archive.ArchiveRefusedError(f"archive member refused: {error}") from None


def isolated_extract(
    archive_path: Path,
    destination: Path,
    *,
    limits: archive.ExtractionLimits | None = None,
    worker_limits: WorkerLimits | None = None,
    disk_free: DiskFree = _disk_free,
    expected_sha256: str | None = None,
    command: Sequence[str] | None = None,
) -> list[archive.ExtractedFile]:
    """Extract ``archive_path`` into the empty ``destination`` through the isolated worker.

    Raises ArchiveRefusedError (the archive or a member was refused, or the worker refused
    it) or IsolationError. Either way the destination is left empty.
    """
    limits = limits or archive.ExtractionLimits()
    archive._check_destination(destination)
    fd = os.open(archive_path, READ_FLAGS)
    try:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode):
            raise archive.ArchiveRefusedError("archive is not a regular file")
        if expected_sha256 is not None and _fd_sha256(fd) != expected_sha256:
            raise archive.ArchiveRefusedError("archive does not match its expected hash")
        kind = archive.archive_kind_of(os.pread(fd, 512, 0))
        sink = _ExtractionSink(destination, limits, status.st_size, disk_free)
        parameters = {
            "kind": kind,
            "extraction": {
                "max_members": limits.max_members,
                "max_member_bytes": limits.max_member_bytes,
                "max_total_bytes": limits.max_total_bytes,
                "max_ratio": limits.max_ratio,
                "max_depth": limits.max_depth,
            },
        }
        max_output = (
            min(limits.max_total_bytes, limits.max_ratio * max(status.st_size, 1))
            + (limits.max_members + 2) * (wp.MAX_NAME_PAYLOAD + 256)
            + _SMALL_OUTPUT
        )
        try:
            run = run_worker(
                wp.Operation.EXTRACT,
                parameters,
                input_fd=fd,
                limits=worker_limits or WorkerLimits(),
                max_output_bytes=max_output,
                on_frame=sink,
                command=command,
            )
            sink.check_result(run.result)
            for item in sink.extracted:
                _check_member_signature(destination, item)
        except WorkerRefusedError as refused:
            raise archive.ArchiveRefusedError(f"worker refused the archive: {refused}") from None
        finally:
            sink.close()
    except BaseException:
        os.close(fd)
        archive._rollback(destination)
        raise
    os.close(fd)
    return sink.extracted


def _fd_sha256(fd: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while chunk := os.pread(fd, _READ_SIZE, offset):
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()
