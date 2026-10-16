"""Segmented prospective-capture store (Step 11 F-11, F-12, F-33; frame format v2).

A capture **session** is one collector run against one source endpoint. It is written as
a chain of bounded, immutable **segments** (``pmv.capture_format`` v2 objects). A segment
rolls over when it reaches the session's explicit size, frame-count, or duration bound, so
no stream is ever an indefinitely open mutable file, and a crash can damage at most the
open segment.

Layout under the configured raw storage root (beside the v1 store, which it never
touches)::

    capture/v2/sessions/<session_id>                    permanent session reservation
    capture/v2/open/<segment_id>/                       the open segment (locked while live)
    capture/v2/quarantine/<segment_id>/                 interrupted or stopped segments
    capture/v2/salvage/<segment_id>/                    salvaged valid prefixes (F-11)
    capture/v2/segments/<source>/<feed>/YYYY/MM/DD/<session_id>/<index>/
        segment.pmvraw, manifest.json                   finalized segments (0400, dir 0500)
    capture/v2/normalized/<session_id>/<key>/           normalized artifacts (content-addressed)

``segment_id`` is ``<session_id>.<index>``, with a six-digit index.

**Segment finalization order** (each step synced before the next; crash points are named
in ``FAULT_POINTS``): sync the object; re-read and fully verify it; rename the partial
object (no-replace); write and rename the manifest (no-replace); make both files 0400;
create the destination path; confirm the open directory's identity; move it into
``segments/`` with ``RENAME_NOREPLACE``; make it 0500. A segment is accepted **exactly
when its directory is in** ``segments/``. Before that move it is never accepted.

**Recovery** (``recover``) never resumes a segment (``docs/raw_data.md``: interrupted
captures are quarantined, never resumed). Every unlocked directory in ``open/`` is moved
to ``quarantine/`` with a closed-schema record, whatever it contains. A session whose
open segment was quarantined has ended; the collector starts a new session.

**Salvage** (``salvage``) is explicit and deterministic: rule
``longest_valid_frame_prefix_v1``. It copies the longest prefix of the quarantined object
made only of complete, fully valid frames into ``salvage/<segment_id>/``, with a record of
the original object's size and SHA-256, the prefix, and what followed it. The quarantined
bytes are never modified, nothing is repaired, and a salvaged segment always ends its
session's readable chain: whatever follows it is uncertain.

**Reading** (``read_session``) follows the hash chain from segment 0 and stops at the first
segment that is not finalized. It never bridges a missing, quarantined, or unsalvaged
segment, and reports exactly why the readable chain ends.

These are process-crash guarantees, demonstrated by killing real processes at every named
boundary. Durability across power loss depends on the filesystem and virtualization stack
honoring ``fsync``. Permissions are defense in depth, not write-once storage. Storing is
not releasing (A-7, A-8): nothing here is agent-visible.
"""

import contextlib
import errno
import fcntl
import hashlib
import os
import re
import secrets
import stat
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Final

from pmv import safe_fs
from pmv.capture_environment import CaptureAuthorization, CaptureEnvironmentError
from pmv.capture_format import (
    MAGIC,
    MAX_PAYLOAD_BYTES,
    CaptureFormatError,
    Direction,
    EventType,
    Frame,
    PayloadFrame,
    SegmentHeader,
    SegmentReader,
    SegmentSummary,
    TailDisposition,
    VenueEnvironment,
    encode_event,
    encode_payload,
    encode_segment_header,
    scan_prefix,
    summarize_segment,
)
from pmv.config import RawStorageConfig
from pmv.integrity import (
    FormatError,
    canonical_json,
    format_timestamp,
    is_sha256,
    is_timestamp,
    is_timestamp_id,
    parse_canonical_json,
    to_utc,
)
from pmv.log import fields, get_logger
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport

__all__ = [
    "FAULT_POINTS",
    "CaptureClosedError",
    "CaptureIntegrityError",
    "CaptureSession",
    "CaptureStore",
    "CaptureStoreError",
    "DiskHardStopError",
    "OversizePayloadError",
    "QuarantineReason",
    "RecoveryOutcome",
    "RecoveryResult",
    "SalvageRecord",
    "SalvageRefusedError",
    "SegmentEnd",
    "SegmentKind",
    "SegmentManifest",
    "SegmentPolicy",
    "SegmentRef",
    "SessionRead",
    "SessionStatus",
    "read_clock_domain",
    "segment_id",
]

_log = get_logger(__name__)

CAPTURE: Final = "capture"
LAYOUT: Final = "v2"
SESSIONS: Final = "sessions"
OPEN: Final = "open"
QUARANTINE: Final = "quarantine"
SALVAGE: Final = "salvage"
SEGMENTS: Final = "segments"
NORMALIZED: Final = "normalized"
MANAGED: Final = (SESSIONS, OPEN, QUARANTINE, SALVAGE, SEGMENTS, NORMALIZED)

PARTIAL_NAME: Final = "segment.pmvraw.partial"
OBJECT_NAME: Final = "segment.pmvraw"
MANIFEST_NAME: Final = "manifest.json"
MANIFEST_TMP_NAME: Final = "manifest.json.tmp"
QUARANTINE_RECORD: Final = "quarantine.json"
SALVAGE_OBJECT: Final = "salvaged.pmvraw"
SALVAGE_RECORD: Final = "salvage.json"
SALVAGE_RULE: Final = "longest_valid_frame_prefix_v1"
MAX_RECORD_BYTES: Final = 1_048_576
# A segment rolls over before it exceeds MAX_SEGMENT_BYTES, plus at most one frame, so a
# whole segment always fits the salvage reader's bound (it is read into memory).
MAX_SEGMENT_BYTES: Final = 128 * 1024 * 1024
MAX_SALVAGE_INPUT_BYTES: Final = MAX_SEGMENT_BYTES + MAX_PAYLOAD_BYTES + 2 * 1024 * 1024
MAX_ARTIFACT_FILE_BYTES: Final = 1024 * 1024 * 1024
SEGMENT_ID: Final = re.compile(r"([0-9]{8}T[0-9]{6}\.[0-9]{6}Z_[0-9a-f]{32})\.([0-9]{6})")
_INDEX: Final = re.compile(r"[0-9]{6}")
MAX_SEGMENT_INDEX: Final = 999_999

FAULT_POINTS: Final = (
    "session.reserved",
    "segment.dir_created",
    "segment.locked",
    "segment.header_written",
    "frame.written",
    "finalize.synced",
    "finalize.verified",
    "finalize.object_renamed",
    "finalize.manifest_written",
    "finalize.manifest_renamed",
    "finalize.files_read_only",
    "finalize.destination_ready",
    "finalize.moved",
    "finalize.read_only",
    "rollover.previous_finalized",
    "quarantine.record_written",
    "quarantine.moved",
    "salvage.staged",
    "salvage.record_written",
    "salvage.moved",
    "artifact.staged",
    "artifact.moved",
)

_RenameAt2 = safe_fs.RenameAt2
_renameat2: _RenameAt2 | None = safe_fs.RENAMEAT2


class CaptureStoreError(Exception):
    """A capture store operation failed. Messages never contain payloads or file contents."""


class CaptureIntegrityError(CaptureStoreError):
    """Stored data or metadata is inconsistent, unsafe, or unexpected."""


class CaptureClosedError(CaptureStoreError):
    """The session no longer accepts this operation."""


class OversizePayloadError(CaptureStoreError):
    """A payload exceeded the frame limit; the open segment was quarantined."""


class SalvageRefusedError(CaptureStoreError):
    """No valid prefix could be salvaged, or the quarantined segment is unusable."""


class DiskHardStopError(CaptureStoreError):
    """Free space reached the hard stop. ``manifest`` is the closing segment, if finalized."""

    def __init__(self, message: str, manifest: "SegmentManifest | None") -> None:
        super().__init__(message)
        self.manifest = manifest


class QuarantineReason(StrEnum):
    REQUESTED = "requested"
    ORPHANED_OPEN_SEGMENT = "orphaned_open_segment"
    OVERSIZE_PAYLOAD = "oversize_payload"
    WRITE_FAILURE = "write_failure"


class RecoveryOutcome(StrEnum):
    QUARANTINED = "quarantined"
    ACTIVE = "active"
    MOVED_CONCURRENTLY = "moved_concurrently"
    UNEXPECTED_ENTRY = "unexpected_entry"
    TIGHTENED = "tightened"
    STALE_STAGING = "stale_staging"


class SegmentEnd(StrEnum):
    ROLLOVER = "rollover"
    SESSION_CLOSED = "session_closed"
    DISK_HARD_STOP = "disk_hard_stop"


class SegmentKind(StrEnum):
    FINALIZED = "finalized"
    SALVAGED = "salvaged"


class SessionStatus(StrEnum):
    """Why the readable chain of a session ends where it does."""

    COMPLETE = "complete"
    OPEN = "open"
    ENDS_WITH_SALVAGE = "ends_with_salvage"
    TRUNCATED = "truncated"


def segment_id(session_id: str, index: int) -> str:
    if not is_timestamp_id(session_id):
        raise ValueError("session_id is malformed")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index <= MAX_SEGMENT_INDEX:
        raise ValueError("segment index is out of range")
    return f"{session_id}.{index:06d}"


def read_clock_domain(path: Path = Path("/proc/sys/kernel/random/boot_id")) -> str:
    """This boot's identity, as 32 lowercase hex digits: the domain of CLOCK_MONOTONIC."""
    text = path.read_text(encoding="ascii").strip().replace("-", "").lower()
    if re.fullmatch(r"[0-9a-f]{32}", text) is None:
        raise CaptureStoreError("the boot identity is not available; monotonic times need it")
    return text


@dataclass(frozen=True, slots=True)
class SegmentPolicy:
    """Explicit rollover bounds for one session. There are no defaults."""

    max_segment_bytes: int
    max_segment_frames: int
    max_segment_duration_ns: int

    def __post_init__(self) -> None:
        for name in ("max_segment_bytes", "max_segment_frames", "max_segment_duration_ns"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_segment_frames < 2:
            raise ValueError("max_segment_frames must allow the header and one frame")
        if self.max_segment_bytes > MAX_SEGMENT_BYTES:
            raise ValueError("max_segment_bytes exceeds the store's segment bound")

    def to_json(self) -> dict[str, object]:
        return {
            "max_segment_bytes": self.max_segment_bytes,
            "max_segment_duration_ns": self.max_segment_duration_ns,
            "max_segment_frames": self.max_segment_frames,
        }


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    name: str | None
    outcome: RecoveryOutcome


@dataclass(frozen=True, slots=True)
class SegmentManifest:
    """The authoritative description of one finalized segment (closed schema)."""

    document: Mapping[str, object]

    @property
    def session_id(self) -> str:
        return _as_str(self.document["session_id"])

    @property
    def segment_index(self) -> int:
        return _as_int(self.document["segment_index"])

    @property
    def end(self) -> SegmentEnd:
        return SegmentEnd(_as_str(self.document["end"]))

    @property
    def object_sha256(self) -> str:
        return _as_str(_mapping(self.document["object"])["sha256"])

    @property
    def object_size(self) -> int:
        return _as_int(_mapping(self.document["object"])["size_bytes"])

    @property
    def last_sequence(self) -> int:
        return _as_int(_mapping(self.document["object"])["last_sequence"])

    @property
    def first_sequence(self) -> int:
        return _as_int(_mapping(self.document["object"])["first_sequence"])

    def to_bytes(self) -> bytes:
        return canonical_json(self.document) + b"\n"


@dataclass(frozen=True, slots=True)
class SalvageRecord:
    document: Mapping[str, object]

    @property
    def prefix_sha256(self) -> str:
        return _as_str(_mapping(self.document["prefix"])["sha256"])

    @property
    def prefix_size(self) -> int:
        return _as_int(_mapping(self.document["prefix"])["size_bytes"])

    @property
    def tail(self) -> TailDisposition:
        return TailDisposition(_as_str(_mapping(self.document["tail"])["disposition"]))

    def to_bytes(self) -> bytes:
        return canonical_json(self.document) + b"\n"


@dataclass(frozen=True, slots=True)
class SegmentRef:
    """One segment in a session's readable chain, with the exact bytes it contributes."""

    index: int
    kind: SegmentKind
    sha256: str
    size_bytes: int
    first_sequence: int
    last_sequence: int
    header: SegmentHeader
    path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionRead:
    session_id: str
    source: SourceIdentity
    venue_environment: VenueEnvironment
    deployment_environment: str
    clock_domain: str
    segments: tuple[SegmentRef, ...]
    status: SessionStatus
    unreachable_indices: tuple[int, ...]


# ----- small helpers -----


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise CaptureIntegrityError("a record field has the wrong type")
    return value


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CaptureIntegrityError("a record field has the wrong type")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CaptureIntegrityError("a record field has the wrong type")
    return value


@contextlib.contextmanager
def _fs_errors() -> Iterator[None]:
    try:
        yield
    except safe_fs.FsUnsupportedError as exc:
        raise CaptureStoreError(str(exc)) from None
    except safe_fs.FsIntegrityError as exc:
        raise CaptureIntegrityError(str(exc)) from None


def _rename_noreplace(src_fd: int, src: str, dst_fd: int, dst: str) -> None:
    with _fs_errors():
        safe_fs.rename_noreplace(src_fd, src, dst_fd, dst, renameat2=_renameat2)


def _open_dir(parent: int, name: str) -> int:
    with _fs_errors():
        return safe_fs.open_dir(parent, name)


def _open_file(parent: int, name: str) -> int:
    with _fs_errors():
        return safe_fs.open_file(parent, name)


def _ensure_dir(parent: int, name: str, device: int, uid: int) -> int:
    with _fs_errors():
        return safe_fs.ensure_dir(parent, name, device, uid)


def _check_dir(fd: int, device: int, uid: int, name: str) -> None:
    with _fs_errors():
        safe_fs.check_dir(fd, device, uid, name)


def _read_small(parent: int, name: str, limit: int = MAX_RECORD_BYTES) -> bytes:
    with _fs_errors():
        return safe_fs.read_small(parent, name, limit)


def _write_new_file(parent: int, name: str, data: bytes) -> None:
    with _fs_errors():
        safe_fs.write_new_file(parent, name, data)


def _record(document: Mapping[str, object]) -> bytes:
    return canonical_json(document) + b"\n"


def _parse_record(data: bytes, what: str) -> dict[str, object]:
    if not data.endswith(b"\n"):
        raise CaptureIntegrityError(f"the {what} is incomplete")
    try:
        return parse_canonical_json(data[:-1])
    except FormatError:
        raise CaptureIntegrityError(f"the {what} is not canonical JSON") from None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _random_token() -> str:
    return secrets.token_hex(16)


def _date_components(session_id: str) -> tuple[str, str, str]:
    return session_id[0:4], session_id[4:6], session_id[6:8]


def _event_counts(counts: Mapping[EventType, int]) -> dict[str, int]:
    return {item.value: counts.get(item, 0) for item in EventType}


def _provenance_json(provenance: RuntimeProvenance) -> dict[str, object]:
    return {
        "code_commit": provenance.code_commit,
        "code_tree_dirty": provenance.code_tree_dirty,
        "config_source_sha256": provenance.config_source_sha256,
        "environment": provenance.environment.value,
        "machine_label": provenance.machine_label,
        "platform": provenance.platform,
        "python_version": provenance.python_version,
        "raw_config_sha256": provenance.raw_config_sha256,
        "software": "pmv",
    }


def _source_json(source: SourceIdentity) -> dict[str, object]:
    return {
        "endpoint_id": source.endpoint_id,
        "feed_id": source.feed_id,
        "source_id": source.source_id,
        "transport": source.transport.value,
    }


def _source_from(document: Mapping[str, object]) -> SourceIdentity:
    try:
        return SourceIdentity(
            source_id=_as_str(document["source_id"]),
            feed_id=_as_str(document["feed_id"]),
            transport=Transport(_as_str(document["transport"])),
            endpoint_id=_as_str(document["endpoint_id"]),
        )
    except (KeyError, ValueError):
        raise CaptureIntegrityError("a record names an invalid source") from None


_SESSION_KEYS: Final = frozenset(
    {
        "clock_domain",
        "deployment_environment",
        "schema",
        "schema_version",
        "segment_policy",
        "session_id",
        "session_started_at",
        "source",
        "venue_environment",
    }
)
_MANIFEST_KEYS: Final = frozenset(
    {
        "chain",
        "clock_domain",
        "counts",
        "deployment_environment",
        "end",
        "object",
        "policy_at_capture",
        "provenance",
        "schema",
        "schema_version",
        "segment_id",
        "segment_index",
        "segment_policy",
        "session_id",
        "source",
        "status",
        "time",
        "venue_environment",
    }
)
_QUARANTINE_KEYS: Final = frozenset(
    {
        "oversize_payload_bytes",
        "oversize_payload_sha256",
        "quarantined_at",
        "reason",
        "schema",
        "schema_version",
        "segment_id",
    }
)
_SALVAGE_KEYS: Final = frozenset(
    {
        "chain",
        "clock_domain",
        "prefix",
        "quarantine_reason",
        "rule",
        "salvaged_at",
        "schema",
        "schema_version",
        "segment_id",
        "segment_index",
        "session_id",
        "source_object",
        "tail",
        "tool",
        "venue_environment",
    }
)
# Fields of a salvage record that are re-derived and compared when salvage is repeated.
_SALVAGE_DERIVED: Final = _SALVAGE_KEYS - {"salvaged_at", "tool"}


# ----- the store -----


class CaptureStore:
    """Segmented capture store under an explicitly configured root outside Git."""

    def __init__(
        self,
        config: RawStorageConfig,
        provenance: RuntimeProvenance,
        *,
        repo_root: Path,
        clock_domain: str,
        clock: Callable[[], datetime] = _utc_now,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        free_bytes: Callable[[], int] | None = None,
        random_token: Callable[[], str] = _random_token,
        fault_hook: Callable[[str], None] | None = None,
    ) -> None:
        if config.root is None:
            raise CaptureStoreError("raw storage root is not configured")
        if provenance.raw_config_sha256 != config.canonical_sha256():
            raise CaptureStoreError("provenance does not describe this raw storage configuration")
        if re.fullmatch(r"[0-9a-f]{32}", clock_domain or "") is None:
            raise CaptureStoreError("clock_domain must be 32 lowercase hex digits")
        self._config = config
        self._provenance = provenance
        self._clock_domain = clock_domain
        self._clock = clock
        self._monotonic = monotonic_ns
        self._free_source = free_bytes
        self._random_token = random_token
        self._fault_hook = fault_hook
        self._fds: dict[str, int] = {}
        self._root_path = config.root
        self._root_fd = _open_root(config.root, repo_root)
        try:
            status = os.fstat(self._root_fd)
            self._device, self._uid = status.st_dev, os.geteuid()
            _check_dir(self._root_fd, self._device, self._uid, "raw storage root")
            capture = _ensure_dir(self._root_fd, CAPTURE, self._device, self._uid)
            try:
                layout = _ensure_dir(capture, LAYOUT, self._device, self._uid)
            finally:
                os.close(capture)
            self._fds[""] = layout
            for name in MANAGED:
                self._fds[name] = _ensure_dir(layout, name, self._device, self._uid)
            self._identities = {
                name: safe_fs.identity(os.fstat(fd)) for name, fd in self._fds.items()
            }
            self._root_identity = safe_fs.identity(status)
            with _fs_errors():
                safe_fs.probe_capabilities(layout, self._device, self._uid, renameat2=_renameat2)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        for fd in self._fds.values():
            os.close(fd)
        self._fds.clear()
        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def __enter__(self) -> "CaptureStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def provenance(self) -> RuntimeProvenance:
        return self._provenance

    @property
    def config(self) -> RawStorageConfig:
        return self._config

    # ----- sessions -----

    def start_session(
        self,
        authorization: CaptureAuthorization,
        source: SourceIdentity,
        policy: SegmentPolicy,
        started_at: datetime,
    ) -> "CaptureSession":
        """Reserve a new session and open its first segment."""
        if not isinstance(authorization, CaptureAuthorization):
            raise CaptureEnvironmentError("a capture session needs a CaptureAuthorization")
        if authorization.deployment_environment is not self._provenance.environment:
            raise CaptureEnvironmentError("the authorization is for another deployment environment")
        if authorization.store_root != self._root_path:
            raise CaptureEnvironmentError("the authorization is for another store root")
        if not isinstance(source, SourceIdentity):
            raise TypeError("source must be a SourceIdentity")
        if authorization.endpoint_id != source.endpoint_id:
            raise CaptureEnvironmentError("the authorization is for another endpoint")
        if not isinstance(policy, SegmentPolicy):
            raise TypeError("policy must be a SegmentPolicy")
        warning, hard_stop = self._thresholds()
        self._check_namespace(SESSIONS, OPEN)
        if self.free_bytes() <= hard_stop:
            raise DiskHardStopError("free space is at or below the hard-stop threshold", None)
        started = to_utc(started_at)
        session_id = f"{started:%Y%m%dT%H%M%S.%f}Z_{self._random_token()}"
        if not is_timestamp_id(session_id):
            raise CaptureStoreError("could not build a session identifier")
        record = {
            "clock_domain": self._clock_domain,
            "deployment_environment": authorization.deployment_environment.value,
            "schema": "pmv.capture.session",
            "schema_version": 1,
            "segment_policy": policy.to_json(),
            "session_id": session_id,
            "session_started_at": format_timestamp(started),
            "source": _source_json(source),
            "venue_environment": authorization.venue_environment.value,
        }
        sessions = self._fds[SESSIONS]
        try:
            _write_new_file(sessions, session_id, _record(record))
        except FileExistsError:
            raise CaptureIntegrityError("the session identifier is already reserved") from None
        os.fsync(sessions)
        self._fault("session.reserved")
        _log.info("capture.session_started", extra=fields(session_id=session_id))
        session = CaptureSession(
            store=self,
            session_id=session_id,
            source=source,
            venue_environment=authorization.venue_environment,
            deployment_environment=authorization.deployment_environment.value,
            policy=policy,
            started=started,
            warning_free_bytes=warning,
            hard_stop_free_bytes=hard_stop,
        )
        session._open_segment(0, None, None)
        return session

    def read_session_record(self, session_id: str) -> Mapping[str, object]:
        if not is_timestamp_id(session_id):
            raise ValueError("session_id is malformed")
        try:
            data = _read_small(self._fds[SESSIONS], session_id)
        except FileNotFoundError:
            raise CaptureIntegrityError("the session has no reservation") from None
        record = _parse_record(data, "session reservation")
        if (
            set(record) != _SESSION_KEYS
            or record["schema"] != "pmv.capture.session"
            or record["schema_version"] != 1
            or record["session_id"] != session_id
            or record["clock_domain"] is None
            or not is_timestamp(record["session_started_at"])
        ):
            raise CaptureIntegrityError("the session reservation is malformed")
        try:
            VenueEnvironment(_as_str(record["venue_environment"]))
        except ValueError:
            raise CaptureIntegrityError("the session reservation is malformed") from None
        _source_from(_mapping(record["source"]))
        return record

    # ----- recovery and reconciliation -----

    def recover(self) -> list[RecoveryResult]:
        """Quarantine every orphaned open segment; never touch a live one."""
        self._check_namespace(OPEN, QUARANTINE)
        results: list[RecoveryResult] = []
        opened = self._fds[OPEN]
        for name in sorted(os.listdir(opened)):
            results.append(self._recover_one(opened, name))
        # An interrupted salvage or artifact write leaves a staging directory. It is never
        # read, renamed, or deleted by the tool; it is reported for the owner.
        for name in sorted(os.listdir(self._fds[SALVAGE])):
            if name.startswith(".staging-"):
                results.append(RecoveryResult(name, RecoveryOutcome.STALE_STAGING))
        normalized = self._fds[NORMALIZED]
        for session in sorted(os.listdir(normalized)):
            if not is_timestamp_id(session):
                results.append(RecoveryResult(None, RecoveryOutcome.UNEXPECTED_ENTRY))
                continue
            session_fd = _open_dir(normalized, session)
            try:
                for name in sorted(os.listdir(session_fd)):
                    if name.startswith(".staging-"):
                        results.append(RecoveryResult(name, RecoveryOutcome.STALE_STAGING))
            finally:
                os.close(session_fd)
        for result in results:
            _log.info(
                "capture.recovery_result",
                extra=fields(name=result.name, outcome=result.outcome.value),
            )
        return results

    def reconcile(self) -> list[RecoveryResult]:
        """Verify every finalized segment and tighten any left 0700 by a crash."""
        self._check_namespace(SEGMENTS)
        results: list[RecoveryResult] = []
        for session_id in self._finalized_sessions():
            record = self.read_session_record(session_id)
            source = _source_from(_mapping(record["source"]))
            for index in self._finalized_indices(session_id, source):
                _manifest, read_only = self._verify_finalized(session_id, source, index)
                if not read_only:
                    self._tighten(session_id, source, index)
                    results.append(
                        RecoveryResult(segment_id(session_id, index), RecoveryOutcome.TIGHTENED)
                    )
        return results

    def _recover_one(self, opened: int, name: str) -> RecoveryResult:
        if SEGMENT_ID.fullmatch(name) is None:
            return RecoveryResult(None, RecoveryOutcome.UNEXPECTED_ENTRY)
        try:
            fd = _open_dir(opened, name)
        except FileNotFoundError:
            return RecoveryResult(name, RecoveryOutcome.MOVED_CONCURRENTLY)
        except CaptureIntegrityError:
            return RecoveryResult(name, RecoveryOutcome.UNEXPECTED_ENTRY)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return RecoveryResult(name, RecoveryOutcome.ACTIVE)
            identity = os.fstat(fd)
            if not safe_fs.same_entry(opened, name, identity):
                return RecoveryResult(name, RecoveryOutcome.MOVED_CONCURRENTLY)
            self._quarantine_locked(fd, name, identity, QuarantineReason.ORPHANED_OPEN_SEGMENT)
            return RecoveryResult(name, RecoveryOutcome.QUARANTINED)
        finally:
            os.close(fd)

    def _quarantine_locked(
        self,
        segment_fd: int,
        name: str,
        identity: os.stat_result,
        reason: QuarantineReason,
        oversize: tuple[int, str] | None = None,
    ) -> None:
        record = _record(
            {
                "oversize_payload_bytes": None if oversize is None else oversize[0],
                "oversize_payload_sha256": None if oversize is None else oversize[1],
                "quarantined_at": format_timestamp(self._now()),
                "reason": reason.value,
                "schema": "pmv.capture.quarantine",
                "schema_version": 1,
                "segment_id": name,
            }
        )
        try:
            _write_new_file(segment_fd, QUARANTINE_RECORD, record)
        except FileExistsError:
            _validate_quarantine(_read_small(segment_fd, QUARANTINE_RECORD), name)
        os.fsync(segment_fd)
        self._fault("quarantine.record_written")
        opened, quarantine = self._fds[OPEN], self._fds[QUARANTINE]
        self._check_namespace(OPEN, QUARANTINE)
        if not safe_fs.same_entry(opened, name, identity):
            raise CaptureIntegrityError("the segment directory was moved concurrently")
        _rename_noreplace(opened, name, quarantine, name)
        os.fsync(quarantine)
        os.fsync(opened)
        self._check_namespace(OPEN, QUARANTINE)
        self._fault("quarantine.moved")
        _log.warning("capture.segment_quarantined", extra=fields(name=name, reason=reason.value))

    # ----- salvage (F-11) -----

    def salvage(self, name: str) -> SalvageRecord:
        """Salvage the longest valid frame prefix of a quarantined segment.

        Deterministic and repeatable: a second call verifies and returns the existing
        salvage. The quarantined bytes are never changed.
        """
        match = SEGMENT_ID.fullmatch(name)
        if match is None:
            raise ValueError("segment_id is malformed")
        session_id, index = match.group(1), int(match.group(2))
        self._check_namespace(QUARANTINE, SALVAGE)
        try:
            quarantined = _open_dir(self._fds[QUARANTINE], name)
        except FileNotFoundError:
            raise SalvageRefusedError("the segment is not quarantined") from None
        try:
            reason = _validate_quarantine(_read_small(quarantined, QUARANTINE_RECORD), name)
            present = [n for n in (PARTIAL_NAME, OBJECT_NAME) if safe_fs.exists(quarantined, n)]
            if len(present) != 1:
                raise SalvageRefusedError("the quarantined segment has no single object file")
            object_name = present[0]
            data = _read_object(quarantined, object_name)
        finally:
            os.close(quarantined)
        scan = scan_prefix(data)
        if scan.header is None or scan.frame_count < 1:
            raise SalvageRefusedError("no valid segment header: nothing can be salvaged")
        header = scan.header
        if header.session_id != session_id or header.segment_index != index:
            raise CaptureIntegrityError("the quarantined object belongs to another segment")
        prefix = data[: scan.valid_bytes]
        if scan.last_sequence is None:
            raise SalvageRefusedError("no valid frame: nothing can be salvaged")
        document: dict[str, object] = {
            "chain": {
                "previous_last_sequence": header.previous_last_sequence,
                "previous_segment_sha256": header.previous_segment_sha256,
            },
            "clock_domain": header.clock_domain,
            "prefix": {
                "first_sequence": header.sequence,
                "frame_count": scan.frame_count,
                "last_sequence": scan.last_sequence,
                "session_closed": scan.session_closed,
                "sha256": hashlib.sha256(prefix).hexdigest(),
                "size_bytes": len(prefix),
            },
            "quarantine_reason": reason,
            "rule": SALVAGE_RULE,
            "salvaged_at": format_timestamp(self._now()),
            "schema": "pmv.capture.salvage",
            "schema_version": 1,
            "segment_id": name,
            "segment_index": index,
            "session_id": session_id,
            "source_object": {
                "name": object_name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            },
            "tail": {"bytes": len(data) - len(prefix), "disposition": scan.tail.value},
            "tool": {
                "code_commit": self._provenance.code_commit,
                "code_tree_dirty": self._provenance.code_tree_dirty,
            },
            "venue_environment": header.venue_environment.value,
        }
        salvage = self._fds[SALVAGE]
        if safe_fs.exists(salvage, name):
            existing = self._read_salvage(name)
            if any(existing.document[key] != document[key] for key in _SALVAGE_DERIVED):
                raise CaptureIntegrityError(
                    "an existing salvage differs from its quarantined input"
                )
            return existing
        staging = f".staging-{name}-{secrets.token_hex(8)}"
        stage_fd = _ensure_dir(salvage, staging, self._device, self._uid)
        try:
            _write_new_file(stage_fd, SALVAGE_OBJECT, prefix)
            self._fault("salvage.staged")
            _write_new_file(stage_fd, SALVAGE_RECORD, _record(document))
            for file_name in (SALVAGE_OBJECT, SALVAGE_RECORD):
                file_fd = _open_file(stage_fd, file_name)
                try:
                    os.fchmod(file_fd, 0o400)
                finally:
                    os.close(file_fd)
            os.fsync(stage_fd)
            self._fault("salvage.record_written")
            self._check_namespace(SALVAGE)
            _rename_noreplace(salvage, staging, salvage, name)
            os.fchmod(stage_fd, 0o500)
            os.fsync(stage_fd)
            os.fsync(salvage)
            self._fault("salvage.moved")
        finally:
            os.close(stage_fd)
        _log.warning(
            "capture.segment_salvaged",
            extra=fields(name=name, prefix_bytes=len(prefix), tail=scan.tail.value),
        )
        return SalvageRecord(document)

    def _read_salvage(self, name: str) -> SalvageRecord:
        directory = _open_dir(self._fds[SALVAGE], name)
        try:
            entries = sorted(os.listdir(directory))
            if entries != [SALVAGE_RECORD, SALVAGE_OBJECT]:
                raise CaptureIntegrityError("a salvage directory has unexpected entries")
            record = _parse_record(_read_small(directory, SALVAGE_RECORD), "salvage record")
            if (
                set(record) != _SALVAGE_KEYS
                or record["schema"] != "pmv.capture.salvage"
                or record["schema_version"] != 1
                or record["segment_id"] != name
                or record["rule"] != SALVAGE_RULE
            ):
                raise CaptureIntegrityError("a salvage record is malformed")
            salvage = SalvageRecord(record)
            data = _read_object(directory, SALVAGE_OBJECT)
        finally:
            os.close(directory)
        if (
            len(data) != salvage.prefix_size
            or hashlib.sha256(data).hexdigest() != salvage.prefix_sha256
        ):
            raise CaptureIntegrityError("a salvaged object does not match its record")
        return salvage

    # ----- reading -----

    def read_session(self, session_id: str) -> SessionRead:
        """Follow the session's hash chain from segment 0 and report where it ends."""
        record = self.read_session_record(session_id)
        source = _source_from(_mapping(record["source"]))
        venue = VenueEnvironment(_as_str(record["venue_environment"]))
        domain = _as_str(record["clock_domain"])
        finalized = set(self._finalized_indices(session_id, source))
        salvaged = {
            int(m.group(2))
            for n in os.listdir(self._fds[SALVAGE])
            if (m := SEGMENT_ID.fullmatch(n)) is not None and m.group(1) == session_id
        }
        if finalized & salvaged:
            raise CaptureIntegrityError("a segment is both finalized and salvaged")
        refs: list[SegmentRef] = []
        previous: SegmentRef | None = None
        index = 0
        status: SessionStatus
        while True:
            if index in finalized:
                manifest, _read_only = self._verify_finalized(session_id, source, index)
                header = self._finalized_header(session_id, source, index)
                ref = SegmentRef(
                    index,
                    SegmentKind.FINALIZED,
                    manifest.object_sha256,
                    manifest.object_size,
                    manifest.first_sequence,
                    manifest.last_sequence,
                    header,
                    (*self._segment_path(session_id, source), f"{index:06d}", OBJECT_NAME),
                )
                _check_chain(previous, ref, record)
                refs.append(ref)
                previous = ref
                if manifest.end is not SegmentEnd.ROLLOVER:
                    status = SessionStatus.COMPLETE
                    break
                index += 1
                continue
            name = segment_id(session_id, index)
            if index in salvaged:
                salvage = self._read_salvage(name)
                header = self._salvaged_header(name)
                prefix = _mapping(salvage.document["prefix"])
                ref = SegmentRef(
                    index,
                    SegmentKind.SALVAGED,
                    salvage.prefix_sha256,
                    salvage.prefix_size,
                    _as_int(prefix["first_sequence"]),
                    _as_int(prefix["last_sequence"]),
                    header,
                    (SALVAGE, name, SALVAGE_OBJECT),
                )
                _check_chain(previous, ref, record)
                refs.append(ref)
                status = SessionStatus.ENDS_WITH_SALVAGE
                break
            status = (
                SessionStatus.OPEN
                if safe_fs.exists(self._fds[OPEN], name)
                else SessionStatus.TRUNCATED
            )
            break
        reached = {ref.index for ref in refs}
        unreachable = tuple(sorted((finalized | salvaged) - reached))
        if status is SessionStatus.COMPLETE and unreachable:
            raise CaptureIntegrityError("segments exist after a session's closing segment")
        return SessionRead(
            session_id=session_id,
            source=source,
            venue_environment=venue,
            deployment_environment=_as_str(record["deployment_environment"]),
            clock_domain=domain,
            segments=tuple(refs),
            status=status,
            unreachable_indices=unreachable,
        )

    def iter_frames(self, session: SessionRead) -> Iterator[tuple[int, Frame]]:
        """Yield ``(segment_index, frame)`` for the session's readable chain, re-verified.

        Every segment is re-read and checked against its recorded SHA-256 and size, and
        cross-segment rules are enforced: one session, one clock domain, continuous
        sequences, and connection discipline (a payload only on an open connection;
        connections opened in order, closed at most once). A defect raises
        ``CaptureIntegrityError``, possibly after earlier frames were yielded, so callers
        must consume the whole iterator before using any result.
        """
        expected_sequence = 0
        opened: set[int] = set()
        next_connection = 0
        for ref in session.segments:
            fd = self._open_path(ref.path)
            try:
                size = os.fstat(fd).st_size
                if size != ref.size_bytes:
                    raise CaptureIntegrityError("a segment's size changed since it was read")
                with os.fdopen(os.dup(fd), "rb") as stream:
                    reader = SegmentReader(stream, size)
                    try:
                        for frame in reader.frames():
                            if frame.sequence != expected_sequence:
                                raise CaptureIntegrityError("session sequence is not continuous")
                            expected_sequence += 1
                            if isinstance(frame, SegmentHeader):
                                if (
                                    frame.session_id != session.session_id
                                    or frame.segment_index != ref.index
                                    or frame.clock_domain != session.clock_domain
                                    or frame.venue_environment is not session.venue_environment
                                ):
                                    raise CaptureIntegrityError("a segment header does not match")
                            elif isinstance(frame, PayloadFrame):
                                if frame.connection not in opened:
                                    raise CaptureIntegrityError("a payload on a closed connection")
                            elif frame.event_type is EventType.CONNECTION_OPENED:
                                if frame.connection != next_connection:
                                    raise CaptureIntegrityError("connections opened out of order")
                                opened.add(frame.connection)
                                next_connection += 1
                            elif frame.event_type is EventType.CONNECTION_CLOSED:
                                if frame.connection not in opened:
                                    raise CaptureIntegrityError("closing a connection not open")
                                opened.discard(frame.connection)
                            yield ref.index, frame
                    except CaptureFormatError as exc:
                        raise CaptureIntegrityError(
                            f"a segment failed verification: {exc}"
                        ) from None
                    if reader.sha256 != ref.sha256:
                        raise CaptureIntegrityError("a segment's bytes changed since it was read")
            finally:
                os.close(fd)

    # ----- normalized artifacts (content-addressed, never replaced) -----

    def write_artifact(self, session_id: str, key: str, files: Mapping[str, bytes]) -> bool:
        """Store ``files`` at ``normalized/<session_id>/<key>/``. Idempotent.

        Returns True if written now, False if an identical artifact already existed. A
        different artifact under the same key is an integrity failure, never replaced.
        """
        if not is_timestamp_id(session_id) or not is_sha256(key):
            raise ValueError("artifact keys are a session identifier and a SHA-256")
        names = sorted(files)
        for name in names:
            with _fs_errors():
                safe_fs.component(name)
        self._check_namespace(NORMALIZED)
        normalized = self._fds[NORMALIZED]
        session_fd = _ensure_dir(normalized, session_id, self._device, self._uid)
        try:
            if safe_fs.exists(session_fd, key):
                existing = self._read_artifact_files(session_fd, key)
                if existing != dict(files):
                    raise CaptureIntegrityError("a different artifact exists under this key")
                return False
            staging = f".staging-{key}-{secrets.token_hex(8)}"
            stage_fd = _ensure_dir(session_fd, staging, self._device, self._uid)
            try:
                for name in names:
                    _write_new_file(stage_fd, name, files[name])
                    file_fd = _open_file(stage_fd, name)
                    try:
                        os.fchmod(file_fd, 0o400)
                    finally:
                        os.close(file_fd)
                os.fsync(stage_fd)
                self._fault("artifact.staged")
                _rename_noreplace(session_fd, staging, session_fd, key)
                os.fchmod(stage_fd, 0o500)
                os.fsync(stage_fd)
                os.fsync(session_fd)
                self._fault("artifact.moved")
            finally:
                os.close(stage_fd)
        finally:
            os.close(session_fd)
        return True

    def read_artifact(self, session_id: str, key: str) -> dict[str, bytes]:
        if not is_timestamp_id(session_id) or not is_sha256(key):
            raise ValueError("artifact keys are a session identifier and a SHA-256")
        self._check_namespace(NORMALIZED)
        try:
            session_fd = _open_dir(self._fds[NORMALIZED], session_id)
        except FileNotFoundError:
            raise CaptureIntegrityError("no artifact exists for this session") from None
        try:
            if not safe_fs.exists(session_fd, key):
                raise CaptureIntegrityError("no artifact exists under this key")
            return self._read_artifact_files(session_fd, key)
        finally:
            os.close(session_fd)

    def _read_artifact_files(self, session_fd: int, key: str) -> dict[str, bytes]:
        directory = _open_dir(session_fd, key)
        try:
            return {
                name: _read_object(directory, name, MAX_ARTIFACT_FILE_BYTES)
                for name in sorted(os.listdir(directory))
            }
        finally:
            os.close(directory)

    # ----- internals shared with CaptureSession -----

    def free_bytes(self) -> int:
        if self._free_source is not None:
            return self._free_source()
        status = os.statvfs(self._root_fd)
        return status.f_bavail * status.f_frsize

    def _now(self) -> datetime:
        return to_utc(self._clock())

    def _fault(self, point: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(point)

    def _thresholds(self) -> tuple[int, int]:
        warning, hard_stop = self._config.warning_free_bytes, self._config.hard_stop_free_bytes
        if warning is None or hard_stop is None:
            raise CaptureStoreError("raw storage disk thresholds are not configured")
        return warning, hard_stop

    def _check_namespace(self, *names: str) -> None:
        """Re-walk the configured root; require the managed directories still in use."""
        message = "the capture root or a managed directory was moved or replaced"
        for name in names:
            try:
                found = safe_fs.path_identities(self._root_path, [CAPTURE, LAYOUT, name])
            except safe_fs.FsIntegrityError:
                raise CaptureIntegrityError(message) from None
            if found[0] != self._root_identity or found[2:] != [
                self._identities[""],
                self._identities[name],
            ]:
                raise CaptureIntegrityError(message)

    def _segment_path(self, session_id: str, source: SourceIdentity) -> tuple[str, ...]:
        return (
            SEGMENTS,
            source.source_id,
            source.feed_id,
            *_date_components(session_id),
            session_id,
        )

    def _open_path(self, path: Sequence[str]) -> int:
        """Open a managed file by components below the layout directory."""
        fd = self._fds[path[0]]
        opened: list[int] = []
        try:
            for component in path[1:-1]:
                fd = _open_dir(fd, component)
                opened.append(fd)
            return _open_file(fd, path[-1])
        finally:
            for item in opened:
                os.close(item)

    def _open_session_dir(self, session_id: str, source: SourceIdentity, *, create: bool) -> int:
        fd = self._fds[SEGMENTS]
        opened: list[int] = []
        try:
            for component in self._segment_path(session_id, source)[1:]:
                if create:
                    fd = _ensure_dir(fd, component, self._device, self._uid)
                else:
                    fd = _open_dir(fd, component)
                    _check_dir(fd, self._device, self._uid, component)
                opened.append(fd)
        except BaseException:
            for item in opened:
                os.close(item)
            raise
        for item in opened[:-1]:
            os.close(item)
        return opened[-1]

    def _finalized_sessions(self) -> list[str]:
        found: list[str] = []
        root = self._fds[SEGMENTS]
        patterns = (
            re.compile(r"[a-z][a-z0-9_]{0,63}"),
            re.compile(r"[a-z][a-z0-9_]{0,63}"),
            re.compile(r"[0-9]{4}"),
            re.compile(r"[0-9]{2}"),
            re.compile(r"[0-9]{2}"),
        )

        def walk(fd: int, depth: int) -> None:
            for name in sorted(os.listdir(fd)):
                if depth == len(patterns):
                    if not is_timestamp_id(name):
                        raise CaptureIntegrityError("unexpected entry in segments/")
                    found.append(name)
                    continue
                if patterns[depth].fullmatch(name) is None:
                    raise CaptureIntegrityError("unexpected entry in segments/")
                child = _open_dir(fd, name)
                try:
                    walk(child, depth + 1)
                finally:
                    os.close(child)

        walk(root, 0)
        return found

    def _finalized_indices(self, session_id: str, source: SourceIdentity) -> list[int]:
        try:
            directory = self._open_session_dir(session_id, source, create=False)
        except FileNotFoundError:
            return []
        try:
            names = sorted(os.listdir(directory))
        finally:
            os.close(directory)
        if any(_INDEX.fullmatch(name) is None for name in names):
            raise CaptureIntegrityError("unexpected entry in a session's segment directory")
        return [int(name) for name in names]

    def _verify_finalized(
        self, session_id: str, source: SourceIdentity, index: int
    ) -> tuple[SegmentManifest, bool]:
        directory = self._open_session_dir(session_id, source, create=False)
        try:
            segment_fd = _open_dir(directory, f"{index:06d}")
        finally:
            os.close(directory)
        try:
            status = os.fstat(segment_fd)
            if status.st_dev != self._device or status.st_uid != self._uid:
                raise CaptureIntegrityError("a finalized segment is not on the root or not owned")
            mode = stat.S_IMODE(status.st_mode)
            if mode not in (0o500, 0o700):
                raise CaptureIntegrityError("a finalized segment has unexpected permissions")
            if sorted(os.listdir(segment_fd)) != [MANIFEST_NAME, OBJECT_NAME]:
                raise CaptureIntegrityError("a finalized segment has unexpected entries")
            for name in (MANIFEST_NAME, OBJECT_NAME):
                file_fd = _open_file(segment_fd, name)
                file_mode = stat.S_IMODE(os.fstat(file_fd).st_mode)
                os.close(file_fd)
                if file_mode != 0o400:
                    raise CaptureIntegrityError("a finalized file is not read-only")
            manifest = _parse_manifest(_read_small(segment_fd, MANIFEST_NAME))
            object_fd = _open_file(segment_fd, OBJECT_NAME)
            size = os.fstat(object_fd).st_size
            with os.fdopen(object_fd, "rb") as stream:
                try:
                    summary = summarize_segment(stream, size)
                except CaptureFormatError as exc:
                    raise CaptureIntegrityError(f"a segment failed verification: {exc}") from None
        finally:
            os.close(segment_fd)
        if manifest.session_id != session_id or manifest.segment_index != index:
            raise CaptureIntegrityError("a manifest does not match its location")
        expected = _manifest_object_and_counts(summary)
        if any(manifest.document[key] != value for key, value in expected.items()):
            raise CaptureIntegrityError("a segment does not match its manifest")
        if (manifest.end is not SegmentEnd.ROLLOVER) != summary.session_closed:
            raise CaptureIntegrityError("a segment's end does not match its frames")
        return manifest, mode == 0o500

    def _finalized_header(
        self, session_id: str, source: SourceIdentity, index: int
    ) -> SegmentHeader:
        fd = self._open_path((*self._segment_path(session_id, source), f"{index:06d}", OBJECT_NAME))
        with os.fdopen(fd, "rb") as stream:
            return _first_header(stream, os.fstat(stream.fileno()).st_size)

    def _salvaged_header(self, name: str) -> SegmentHeader:
        fd = self._open_path((SALVAGE, name, SALVAGE_OBJECT))
        with os.fdopen(fd, "rb") as stream:
            return _first_header(stream, os.fstat(stream.fileno()).st_size)

    def _tighten(self, session_id: str, source: SourceIdentity, index: int) -> None:
        directory = self._open_session_dir(session_id, source, create=False)
        try:
            segment_fd = _open_dir(directory, f"{index:06d}")
            try:
                os.fchmod(segment_fd, 0o500)
                os.fsync(segment_fd)
            finally:
                os.close(segment_fd)
            os.fsync(directory)
        finally:
            os.close(directory)
        _log.warning("capture.segment_mode_tightened", extra=fields(index=index))


def _open_root(root: Path, repo_root: Path) -> int:
    if not root.is_absolute():
        raise CaptureStoreError("raw storage root must be an absolute path")
    root_real = Path(os.path.realpath(root))
    repo_real = Path(os.path.realpath(repo_root))
    if root_real.is_relative_to(repo_real) or repo_real.is_relative_to(root_real):
        raise CaptureStoreError("raw storage root must be outside the Git working tree")
    try:
        return os.open(root, safe_fs.DIR_FLAGS)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise CaptureIntegrityError("raw storage root is not a plain directory") from None
        raise


def _read_object(parent: int, name: str, limit: int = MAX_SALVAGE_INPUT_BYTES) -> bytes:
    fd = _open_file(parent, name)
    try:
        size = os.fstat(fd).st_size
        if size > limit:
            raise CaptureIntegrityError("an object is larger than the store reads into memory")
        with _fs_errors():
            return safe_fs.pread_all(fd, size)
    finally:
        os.close(fd)


def _first_header(stream: BinaryIO, size: int) -> SegmentHeader:
    reader = SegmentReader(stream, size)
    try:
        first = next(iter(reader.frames()))
    except (CaptureFormatError, StopIteration):
        raise CaptureIntegrityError("a segment has no valid header") from None
    if not isinstance(first, SegmentHeader):
        raise CaptureIntegrityError("a segment has no valid header")
    return first


def _check_chain(
    previous: SegmentRef | None, ref: SegmentRef, record: Mapping[str, object]
) -> None:
    header = ref.header
    if (
        header.session_id != record["session_id"]
        or header.segment_index != ref.index
        or header.clock_domain != record["clock_domain"]
        or header.venue_environment.value != record["venue_environment"]
        or header.deployment_environment != record["deployment_environment"]
        or header.session_started_at != record["session_started_at"]
    ):
        raise CaptureIntegrityError("a segment header does not match its session")
    source = _mapping(record["source"])
    if (header.source_id, header.feed_id, header.endpoint_id, header.transport) != (
        source["source_id"],
        source["feed_id"],
        source["endpoint_id"],
        source["transport"],
    ):
        raise CaptureIntegrityError("a segment header names another source")
    if previous is None:
        if ref.index != 0:
            raise CaptureIntegrityError("a session's chain does not start at segment 0")
        return
    if previous.kind is not SegmentKind.FINALIZED:
        raise CaptureIntegrityError("a salvaged segment cannot be followed")
    if (
        header.previous_segment_sha256 != previous.sha256
        or header.previous_last_sequence != previous.last_sequence
        or ref.first_sequence != previous.last_sequence + 1
    ):
        raise CaptureIntegrityError("a segment does not chain to its predecessor")


def _validate_quarantine(data: bytes, name: str) -> str:
    record = _parse_record(data, "quarantine record")
    if (
        set(record) != _QUARANTINE_KEYS
        or record["schema"] != "pmv.capture.quarantine"
        or record["schema_version"] != 1
        or record["segment_id"] != name
        or record["reason"] not in {reason.value for reason in QuarantineReason}
        or not is_timestamp(record["quarantined_at"])
    ):
        raise CaptureIntegrityError("a quarantine record is malformed")
    return _as_str(record["reason"])


def _manifest_object_and_counts(summary: SegmentSummary) -> dict[str, object]:
    return {
        "object": {
            "first_sequence": summary.first_sequence,
            "format": "pmv.raw.frames",
            "format_version": 2,
            "frame_count": summary.frame_count,
            "last_sequence": summary.last_sequence,
            "sha256": summary.sha256,
            "size_bytes": summary.size_bytes,
        },
        "counts": {
            "events": _event_counts(summary.event_counts),
            "inbound": summary.inbound_count,
            "malformed": summary.malformed_count,
            "outbound": summary.outbound_count,
        },
        "chain": {
            "previous_last_sequence": summary.header.previous_last_sequence,
            "previous_segment_sha256": summary.header.previous_segment_sha256,
        },
    }


def _parse_manifest(data: bytes) -> SegmentManifest:
    record = _parse_record(data, "segment manifest")
    if (
        set(record) != _MANIFEST_KEYS
        or record["schema"] != "pmv.capture.segment_manifest"
        or record["schema_version"] != 1
        or record["status"] != "finalized"
    ):
        raise CaptureIntegrityError("a segment manifest is malformed")
    try:
        SegmentEnd(_as_str(record["end"]))
        VenueEnvironment(_as_str(record["venue_environment"]))
    except ValueError:
        raise CaptureIntegrityError("a segment manifest is malformed") from None
    manifest = SegmentManifest(record)
    if segment_id(manifest.session_id, manifest.segment_index) != record["segment_id"]:
        raise CaptureIntegrityError("a segment manifest is malformed")
    return manifest


class _State(Enum):
    OPEN = "open"
    POISONED = "poisoned"
    CLOSED = "closed"
    QUARANTINED = "quarantined"
    ABANDONED = "abandoned"


class CaptureSession:
    """One capture session. Single writer; not thread-safe; do not fork while open."""

    def __init__(
        self,
        *,
        store: CaptureStore,
        session_id: str,
        source: SourceIdentity,
        venue_environment: VenueEnvironment,
        deployment_environment: str,
        policy: SegmentPolicy,
        started: datetime,
        warning_free_bytes: int,
        hard_stop_free_bytes: int,
    ) -> None:
        self._store = store
        self._session_id = session_id
        self._source = source
        self._venue = venue_environment
        self._deployment = deployment_environment
        self._policy = policy
        self._started = started
        self._warning = warning_free_bytes
        self._hard_stop = hard_stop_free_bytes
        self._state = _State.OPEN
        self._sequence = 0
        self._index = 0
        self._segment_fd = -1
        self._object_fd = -1
        self._identity: os.stat_result | None = None
        self._hash = hashlib.sha256()
        self._size = 0
        self._frames = 0
        self._segment_opened_at = started
        self._segment_monotonic = 0
        self._open_connections: set[int] = set()
        self._next_connection = 0
        self._warned = False
        self._last_monotonic: int | None = None
        self._last_observed: datetime | None = None
        self._last_source: datetime | None = None
        self._last_written: datetime | None = None
        self.manifests: list[SegmentManifest] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def segment_index(self) -> int:
        return self._index

    @property
    def open_connections(self) -> frozenset[int]:
        return frozenset(self._open_connections)

    # ----- public operations -----

    def open_connection(self) -> int:
        """Record a new connection and return its index (0, 1, ... within the session)."""
        self._require_open()
        self._check_disk()
        index = self._next_connection
        self._write_event(EventType.CONNECTION_OPENED, index)
        self._next_connection += 1
        self._open_connections.add(index)
        self._maybe_rollover()
        return index

    def close_connection(self, connection: int) -> None:
        self._require_open()
        if connection not in self._open_connections:
            raise ValueError("the connection is not open")
        self._check_disk()
        self._write_event(EventType.CONNECTION_CLOSED, connection)
        self._open_connections.discard(connection)
        self._maybe_rollover()

    def append_inbound(
        self,
        payload: bytes,
        *,
        connection: int,
        observed_at: datetime,
        monotonic_ns: int,
        source_timestamp: datetime | None = None,
        malformed: bool = False,
    ) -> None:
        """Append bytes received from the source, exactly as delivered."""
        self._append(
            payload,
            Direction.INBOUND,
            connection,
            observed_at,
            monotonic_ns,
            source_timestamp,
            malformed,
        )

    def append_outbound(
        self, payload: bytes, *, connection: int, observed_at: datetime, monotonic_ns: int
    ) -> None:
        """Append an application-level message PMV sent (for example a subscription).

        Handshake and authentication material never passes through here (F-03).
        """
        self._append(
            payload, Direction.OUTBOUND, connection, observed_at, monotonic_ns, None, False
        )

    def record_event(self, event_type: EventType, connection: int | None = None) -> None:
        """Record a caller-observed gap or rate limit."""
        self._require_open()
        if event_type not in (EventType.GAP, EventType.RATE_LIMIT):
            raise ValueError("callers may record only gap or rate_limit events")
        if connection is not None and connection not in self._open_connections:
            raise ValueError("the connection is not open")
        self._check_disk()
        self._write_event(event_type, connection)
        self._maybe_rollover()

    def sync(self) -> None:
        """Make every frame written so far durable (a checkpoint; does not finalize)."""
        self._require_open()
        try:
            os.fsync(self._object_fd)
        except OSError:
            self._state = _State.POISONED
            raise

    def close(self) -> SegmentManifest:
        """Write ``session_closed`` and finalize the last segment."""
        if self._state is _State.POISONED:
            raise CaptureClosedError("the session had a write failure; quarantine it")
        self._require_open()
        self._write_event(EventType.SESSION_CLOSED, None)
        manifest = self._finalize(SegmentEnd.SESSION_CLOSED)
        self._state = _State.CLOSED
        return manifest

    def quarantine(self, reason: QuarantineReason) -> None:
        """Stop the session and quarantine its open segment."""
        if self._state not in (_State.OPEN, _State.POISONED):
            raise CaptureClosedError("the session is no longer open")
        self._quarantine(QuarantineReason(reason), None)

    # ----- internals -----

    def _require_open(self) -> None:
        if self._state is not _State.OPEN:
            raise CaptureClosedError(f"the session is {self._state.value}")

    def _append(
        self,
        payload: bytes,
        direction: Direction,
        connection: int,
        observed_at: datetime,
        monotonic_ns: int,
        source_timestamp: datetime | None,
        malformed: bool,
    ) -> None:
        self._require_open()
        if type(payload) is not bytes:
            raise TypeError("payload must be bytes")
        if not isinstance(malformed, bool):
            raise TypeError("malformed must be a bool")
        if connection not in self._open_connections:
            raise ValueError("the connection is not open")
        if isinstance(monotonic_ns, bool) or not isinstance(monotonic_ns, int) or monotonic_ns < 0:
            raise ValueError("monotonic_ns must be a non-negative integer")
        observed = to_utc(observed_at)
        source = None if source_timestamp is None else to_utc(source_timestamp)
        if len(payload) > MAX_PAYLOAD_BYTES:
            size, digest = len(payload), hashlib.sha256(payload).hexdigest()
            self._quarantine(QuarantineReason.OVERSIZE_PAYLOAD, (size, digest))
            raise OversizePayloadError(
                "a payload exceeds the frame limit; the open segment was quarantined and the "
                "session ended"
            )
        self._check_disk()
        written, written_regressed = self._written_at()
        self._write_frame(
            encode_payload(
                sequence=self._sequence,
                payload=payload,
                direction=direction,
                connection=connection,
                observed_at=format_timestamp(observed),
                monotonic_ns=monotonic_ns,
                source_timestamp=None if source is None else format_timestamp(source),
                malformed=malformed,
                written_at=format_timestamp(written),
            )
        )
        monotonic_regressed = (
            self._last_monotonic is not None and monotonic_ns < self._last_monotonic
        )
        local_regressed = written_regressed or (
            self._last_observed is not None and observed < self._last_observed
        )
        source_regressed = (
            source is not None and self._last_source is not None and source < self._last_source
        )
        self._last_monotonic = (
            monotonic_ns
            if self._last_monotonic is None
            else max(self._last_monotonic, monotonic_ns)
        )
        self._last_observed = (
            observed if self._last_observed is None else max(self._last_observed, observed)
        )
        if source is not None:
            self._last_source = (
                source if self._last_source is None else max(self._last_source, source)
            )
        if monotonic_regressed:
            self._write_event(EventType.MONOTONIC_REGRESSION, connection)
        if source_regressed:
            self._write_event(EventType.SOURCE_CLOCK_REGRESSION, connection)
        if local_regressed:
            self._write_event(EventType.LOCAL_CLOCK_REGRESSION, connection)
        self._maybe_rollover()

    def _written_at(self) -> tuple[datetime, bool]:
        written = self._store._now()
        regressed = self._last_written is not None and written < self._last_written
        self._last_written = written
        return written, regressed

    def _check_disk(self) -> None:
        free = self._store.free_bytes()
        if free <= self._hard_stop:
            _log.error("capture.disk_hard_stop", extra=fields(session_id=self._session_id))
            try:
                self._write_event(EventType.DISK_HARD_STOP, None)
                self._write_event(EventType.SESSION_CLOSED, None)
                manifest = self._finalize(SegmentEnd.DISK_HARD_STOP)
            except (OSError, CaptureStoreError, FormatError):
                self._abandon()
                raise DiskHardStopError(
                    "hard stop reached and the closing segment could not be finalized; it stays "
                    "open for recovery",
                    None,
                ) from None
            self._state = _State.CLOSED
            raise DiskHardStopError("hard stop reached; the session was closed", manifest)
        if free <= self._warning and not self._warned:
            self._warned = True
            self._write_event(EventType.DISK_WARNING, None)

    def _write_event(self, event_type: EventType, connection: int | None) -> None:
        self._write_frame(
            encode_event(
                sequence=self._sequence,
                event_type=event_type,
                connection=connection,
                written_at=format_timestamp(self._written_at()[0]),
                monotonic_ns=self._store._monotonic(),
            )
        )

    def _write_frame(self, frame: bytes) -> None:
        try:
            safe_fs.write_all(self._object_fd, frame)
        except OSError:
            self._state = _State.POISONED
            _log.error("capture.write_failed", extra=fields(session_id=self._session_id))
            raise
        self._hash.update(frame)
        self._size += len(frame)
        self._frames += 1
        self._sequence += 1
        self._store._fault("frame.written")

    def _maybe_rollover(self) -> None:
        policy = self._policy
        elapsed = self._store._monotonic() - self._segment_monotonic
        if (
            self._size >= policy.max_segment_bytes
            or self._frames >= policy.max_segment_frames
            or elapsed >= policy.max_segment_duration_ns
        ):
            manifest = self._finalize(SegmentEnd.ROLLOVER)
            self._store._fault("rollover.previous_finalized")
            if self._index >= MAX_SEGMENT_INDEX:
                self._state = _State.CLOSED
                raise CaptureClosedError("the session reached its maximum segment count")
            self._open_segment(self._index + 1, manifest.object_sha256, manifest.last_sequence)

    def _open_segment(
        self, index: int, previous_sha256: str | None, previous_last: int | None
    ) -> None:
        store = self._store
        name = segment_id(self._session_id, index)
        opened = store._fds[OPEN]
        try:
            store._check_namespace(OPEN)
            os.mkdir(name, 0o700, dir_fd=opened)
            os.fsync(opened)
            store._fault("segment.dir_created")
            segment_fd = _open_dir(opened, name)
        except BaseException:
            self._state = _State.ABANDONED
            raise
        object_fd = -1
        try:
            os.fchmod(segment_fd, 0o700)
            _check_dir(segment_fd, store._device, store._uid, name)
            try:
                fcntl.flock(segment_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CaptureIntegrityError(
                    "another process holds the new segment's lock"
                ) from None
            identity = os.fstat(segment_fd)
            if not safe_fs.same_entry(opened, name, identity):
                raise CaptureIntegrityError("the new segment directory was moved")
            store._fault("segment.locked")
            object_fd = os.open(PARTIAL_NAME, safe_fs.NEW_FILE_FLAGS, 0o600, dir_fd=segment_fd)
            os.fsync(segment_fd)
            now = store._now()
            monotonic = store._monotonic()
            header = SegmentHeader(
                sequence=self._sequence,
                session_id=self._session_id,
                segment_index=index,
                previous_segment_sha256=previous_sha256,
                previous_last_sequence=previous_last,
                source_id=self._source.source_id,
                feed_id=self._source.feed_id,
                endpoint_id=self._source.endpoint_id,
                transport=self._source.transport.value,
                deployment_environment=self._deployment,
                venue_environment=self._venue,
                clock_domain=store._clock_domain,
                session_started_at=format_timestamp(self._started),
                written_at=format_timestamp(now),
                monotonic_ns=monotonic,
            )
            data = MAGIC + encode_segment_header(header)
            safe_fs.write_all(object_fd, data)
            os.fsync(object_fd)
        except BaseException:
            if object_fd >= 0:
                os.close(object_fd)
            os.close(segment_fd)
            self._state = _State.ABANDONED
            raise
        self._index = index
        self._segment_fd = segment_fd
        self._object_fd = object_fd
        self._identity = identity
        self._hash = hashlib.sha256(data)
        self._size = len(data)
        self._frames = 1
        self._sequence += 1
        self._segment_opened_at = now
        self._segment_monotonic = monotonic
        store._fault("segment.header_written")
        _log.info("capture.segment_opened", extra=fields(name=name))

    def _finalize(self, end: SegmentEnd) -> SegmentManifest:
        try:
            return self._finalize_steps(end)
        except BaseException:
            self._abandon()
            raise

    def _finalize_steps(self, end: SegmentEnd) -> SegmentManifest:
        store = self._store
        name = segment_id(self._session_id, self._index)
        segment_fd = self._segment_fd
        if self._identity is None:
            raise CaptureClosedError("the session has no open segment")
        os.fsync(self._object_fd)
        os.close(self._object_fd)
        self._object_fd = -1
        store._fault("finalize.synced")
        object_fd = _open_file(segment_fd, PARTIAL_NAME)
        size = os.fstat(object_fd).st_size
        with os.fdopen(object_fd, "rb") as stream:
            try:
                summary = summarize_segment(stream, size)
            except CaptureFormatError as exc:
                raise CaptureIntegrityError(f"re-read verification failed: {exc}") from None
        if (summary.size_bytes, summary.sha256, summary.frame_count) != (
            self._size,
            self._hash.hexdigest(),
            self._frames,
        ):
            raise CaptureIntegrityError("re-read verification does not match the written frames")
        if summary.session_closed != (end is not SegmentEnd.ROLLOVER):
            raise CaptureIntegrityError("the segment's end does not match its frames")
        store._fault("finalize.verified")
        _rename_noreplace(segment_fd, PARTIAL_NAME, segment_fd, OBJECT_NAME)
        os.fsync(segment_fd)
        store._fault("finalize.object_renamed")
        closed_at = store._now()
        manifest = SegmentManifest(self._manifest_document(name, summary, end, closed_at))
        _write_new_file(segment_fd, MANIFEST_TMP_NAME, manifest.to_bytes())
        store._fault("finalize.manifest_written")
        _rename_noreplace(segment_fd, MANIFEST_TMP_NAME, segment_fd, MANIFEST_NAME)
        os.fsync(segment_fd)
        store._fault("finalize.manifest_renamed")
        for file_name in (OBJECT_NAME, MANIFEST_NAME):
            file_fd = _open_file(segment_fd, file_name)
            try:
                os.fchmod(file_fd, 0o400)
            finally:
                os.close(file_fd)
        os.fsync(segment_fd)
        store._fault("finalize.files_read_only")
        store._check_namespace(OPEN, SEGMENTS)
        destination = store._open_session_dir(self._session_id, self._source, create=True)
        try:
            store._fault("finalize.destination_ready")
            opened = store._fds[OPEN]
            store._check_namespace(OPEN, SEGMENTS)
            if not safe_fs.same_entry(opened, name, self._identity):
                raise CaptureIntegrityError("the segment directory was moved concurrently")
            _rename_noreplace(opened, name, destination, f"{self._index:06d}")
            os.fsync(destination)
            os.fsync(opened)
            store._fault("finalize.moved")
            os.fchmod(segment_fd, 0o500)
            os.fsync(segment_fd)
            os.fsync(destination)
        finally:
            os.close(destination)
            os.close(segment_fd)
            self._segment_fd = -1
        store._fault("finalize.read_only")
        self.manifests.append(manifest)
        _log.info(
            "capture.segment_finalized",
            extra=fields(name=name, size_bytes=summary.size_bytes, sha256=summary.sha256),
        )
        return manifest

    def _manifest_document(
        self, name: str, summary: SegmentSummary, end: SegmentEnd, closed_at: datetime
    ) -> dict[str, object]:
        store = self._store
        config = store.config
        document: dict[str, object] = {
            "clock_domain": store._clock_domain,
            "deployment_environment": self._deployment,
            "end": end.value,
            "policy_at_capture": {
                "backup_policy_id": config.backup_policy_id,
                "backup_status_at_finalization": (
                    "not_configured" if config.backup_policy_id is None else "pending"
                ),
                "retention_class": config.retention_class,
            },
            "provenance": _provenance_json(store.provenance),
            "schema": "pmv.capture.segment_manifest",
            "schema_version": 1,
            "segment_id": name,
            "segment_index": self._index,
            "segment_policy": self._policy.to_json(),
            "session_id": self._session_id,
            "source": _source_json(self._source),
            "status": "finalized",
            "time": {
                "first_observed_at": summary.first_observed_at,
                "last_observed_at": summary.last_observed_at,
                "segment_closed_at": format_timestamp(closed_at),
                "segment_opened_at": format_timestamp(self._segment_opened_at),
                "segment_monotonic_duration_ns": max(
                    0, store._monotonic() - self._segment_monotonic
                ),
                "session_started_at": format_timestamp(self._started),
            },
            "venue_environment": self._venue.value,
        }
        document.update(_manifest_object_and_counts(summary))
        return document

    def _quarantine(self, reason: QuarantineReason, oversize: tuple[int, str] | None) -> None:
        if self._object_fd >= 0:
            with contextlib.suppress(OSError):
                os.fsync(self._object_fd)
            os.close(self._object_fd)
            self._object_fd = -1
        if self._identity is None:
            raise CaptureClosedError("the session has no open segment")
        try:
            self._store._quarantine_locked(
                self._segment_fd,
                segment_id(self._session_id, self._index),
                self._identity,
                reason,
                oversize,
            )
        except BaseException:
            self._abandon()
            raise
        os.close(self._segment_fd)
        self._segment_fd = -1
        self._state = _State.QUARANTINED

    def _abandon(self) -> None:
        """Release everything; an unfinished segment stays in open/ for recovery."""
        for attribute in ("_object_fd", "_segment_fd"):
            fd = getattr(self, attribute)
            if fd >= 0:
                os.close(fd)
                setattr(self, attribute, -1)
        if self._state not in (_State.CLOSED, _State.QUARANTINED):
            self._state = _State.ABANDONED
            _log.error("capture.segment_left_open", extra=fields(session_id=self._session_id))
