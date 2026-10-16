"""Filesystem raw capture store: immutable capture bundles with provenance, outside Git.

Layout under the explicitly configured root (there is no default)::

    .capture_ids/<capture_id>                       permanent ID reservations
    .inprogress/<capture_id>/                       active or interrupted captures
    quarantine/<capture_id>/                        quarantined captures
    raw/v1/<source>/<feed>/YYYY/MM/DD/<capture_id>/ finalized captures
    catalog/captures.v1.jsonl                       rebuildable index of finalized captures
    catalog/storage-events.v1.jsonl                 authoritative post-finalization facts

Every path is opened relative to an already-open directory, one component at a time,
without following symlinks. Moves use ``renameat2(RENAME_NOREPLACE)`` and never fall back
to a plain rename. A capture enters ``raw/`` only after its raw object and manifest are
complete, verified, and synced. A capture's directory is locked with ``flock`` for its whole
active life, and the locked directory's identity is checked before every move.

These are process-crash guarantees. Durability across host power loss depends on the
filesystem and virtualization stack honoring fsync. Permissions are defense in depth, not
write-once storage, and a free-space check cannot prevent the disk from filling.
"""

import contextlib
import errno
import fcntl
import hashlib
import os
import platform
import re
import secrets
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from types import TracebackType
from typing import Final

from pmv import safe_fs
from pmv.config import AppConfig, Environment, RawStorageConfig
from pmv.log import fields, get_logger
from pmv.raw_format import (
    MAGIC,
    MAX_PAYLOAD_BYTES,
    EventType,
    ObjectSummary,
    RawFormatError,
    canonical_json,
    encode_event_frame,
    encode_payload_frame,
    format_timestamp,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
    summarize_object,
    to_utc,
)
from pmv.raw_manifest import (
    CAPTURE_ID,
    MAX_MANIFEST_BYTES,
    OBJECT_NAME,
    BackupStatus,
    CapturePolicy,
    CaptureTimes,
    ManifestError,
    Observations,
    RawManifest,
    RawObjectMetadata,
    RuntimeProvenance,
    SourceIdentity,
    expected_relative_path,
    parse_manifest,
    validate_capture_id,
    validate_identifier,
)

_log = get_logger(__name__)

RESERVATIONS: Final = ".capture_ids"
IN_PROGRESS: Final = ".inprogress"
QUARANTINE: Final = "quarantine"
RAW: Final = "raw"
CATALOG: Final = "catalog"
LAYOUT_VERSION: Final = "v1"
PARTIAL_NAME: Final = "records.pmvraw.partial"
MANIFEST_NAME: Final = "manifest.json"
MANIFEST_TMP_NAME: Final = "manifest.json.tmp"
QUARANTINE_RECORD: Final = "quarantine.json"
CATALOG_NAME: Final = "captures.v1.jsonl"
EVENTS_NAME: Final = "storage-events.v1.jsonl"
MAX_RECORD_BYTES: Final = 65_536

_LEDGER_FLAGS: Final = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC
_DIGITS: Final = {4: re.compile(r"[0-9]{4}"), 2: re.compile(r"[0-9]{2}")}

_RenameAt2 = safe_fs.RenameAt2


class RawStorageError(Exception):
    """A raw storage operation failed. Messages never contain payloads or file contents."""


class RawStorageNotConfiguredError(RawStorageError):
    """Required raw storage policy is unset."""


class UnsupportedFilesystemError(RawStorageError):
    """The filesystem lacks a capability the store requires (fail closed)."""


class RawIntegrityError(RawStorageError):
    """Stored data or metadata is inconsistent, unsafe, or unexpected."""


class DuplicateCaptureIdError(RawIntegrityError):
    """A capture ID was already reserved."""


class CaptureClosedError(RawStorageError):
    """The capture no longer accepts this operation."""


class CaptureOversizeError(RawStorageError):
    """A payload exceeded MAX_PAYLOAD_BYTES; the capture was stopped and quarantined."""


class DiskHardStopError(RawStorageError):
    """Free space reached the hard-stop threshold.

    ``manifest`` is the finalized captured prefix, or None if nothing was finalized.
    """

    def __init__(self, message: str, manifest: RawManifest | None) -> None:
        super().__init__(message)
        self.manifest = manifest


class LegacyFormatRefusedError(RawStorageError):
    """Raw format v1 may not start a capture outside the test environment (F-12, B08)."""


class CatalogIndexError(RawStorageError):
    """A capture was finalized but its rebuildable catalog entry was not appended."""

    def __init__(self, message: str, manifest: RawManifest) -> None:
        super().__init__(message)
        self.manifest = manifest


class QuarantineReason(StrEnum):
    REQUESTED = "requested"
    ORPHANED_IN_PROGRESS = "orphaned_in_progress"
    OVERSIZE_PAYLOAD = "oversize_payload"
    WRITE_FAILURE = "write_failure"


class RecoveryOutcome(StrEnum):
    QUARANTINED = "quarantined"
    ACTIVE = "active"
    MOVED_CONCURRENTLY = "moved_concurrently"
    RESERVED_NO_DATA = "reserved_no_data"
    UNEXPECTED_ENTRY = "unexpected_entry"


class StorageEventType(StrEnum):
    BACKUP_VERIFIED = "backup_verified"
    RESTORE_VERIFIED = "restore_verified"


_CALLER_EVENTS: Final = frozenset({EventType.RECONNECT, EventType.RATE_LIMIT, EventType.GAP})


@dataclass(frozen=True, slots=True)
class CaptureEvent:
    """An operational event a caller may record: reconnect, rate_limit, or gap."""

    event_type: EventType

    def __post_init__(self) -> None:
        if self.event_type not in _CALLER_EVENTS:
            raise ValueError("callers may record only reconnect, rate_limit, or gap events")


@dataclass(frozen=True, slots=True)
class VerificationResult:
    capture_id: str
    manifest: RawManifest
    manifest_sha256: str
    directory_read_only: bool


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    capture_id: str | None
    outcome: RecoveryOutcome


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    capture_id: str
    manifest_path: str
    manifest_sha256: str
    finalized_at: str

    def to_json(self) -> dict[str, object]:
        return {
            "capture_id": self.capture_id,
            "finalized_at": self.finalized_at,
            "manifest_path": self.manifest_path,
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class CatalogReport:
    entries: Mapping[str, CatalogEntry]
    invalid_lines: tuple[int, ...]
    conflicting_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    added: tuple[str, ...]
    mode_tightened: tuple[str, ...]
    integrity_failures: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class StorageEvent:
    """A post-finalization fact for the authoritative storage-events ledger."""

    event_type: StorageEventType
    capture_id: str
    occurred_at: datetime
    backup_policy_id: str | None = None
    object_sha256: str | None = None
    restored_sha256: str | None = None

    def __post_init__(self) -> None:
        validate_capture_id(self.capture_id)
        to_utc(self.occurred_at)
        if self.event_type is StorageEventType.BACKUP_VERIFIED:
            validate_identifier(self.backup_policy_id, "backup_policy_id")
            if not is_sha256(self.object_sha256) or self.restored_sha256 is not None:
                raise ValueError("backup_verified needs object_sha256 and no restored_sha256")
        elif self.event_type is StorageEventType.RESTORE_VERIFIED:
            if not is_sha256(self.restored_sha256):
                raise ValueError("restore_verified needs restored_sha256")
            if self.backup_policy_id is not None or self.object_sha256 is not None:
                raise ValueError("restore_verified takes only restored_sha256")
        else:
            raise ValueError("unknown storage event type")

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {
            "capture_id": self.capture_id,
            "event_type": self.event_type.value,
            "occurred_at": format_timestamp(self.occurred_at),
        }
        if self.event_type is StorageEventType.BACKUP_VERIFIED:
            body["backup_policy_id"] = self.backup_policy_id
            body["object_sha256"] = self.object_sha256
        else:
            body["restored_sha256"] = self.restored_sha256
        return body


@dataclass(frozen=True, slots=True)
class RecordedStorageEvent:
    ledger_seq: int
    prev_entry_sha256: str | None
    entry_sha256: str
    body: Mapping[str, object]


_EVENT_BODY_KEYS: Final = {
    StorageEventType.BACKUP_VERIFIED.value: frozenset(
        {"capture_id", "event_type", "occurred_at", "backup_policy_id", "object_sha256"}
    ),
    StorageEventType.RESTORE_VERIFIED.value: frozenset(
        {"capture_id", "event_type", "occurred_at", "restored_sha256"}
    ),
}
_CHAIN_KEYS: Final = frozenset({"ledger_seq", "prev_entry_sha256", "entry_sha256"})


# ----- filesystem primitives (pmv.safe_fs), mapped to raw-storage errors -----
#
# These module-level names are what the rest of this module calls, so tests can replace
# them. Primitive errors become this module's error types with unchanged messages.


@contextlib.contextmanager
def _fs_errors() -> Iterator[None]:
    try:
        yield
    except safe_fs.FsUnsupportedError as exc:
        raise UnsupportedFilesystemError(str(exc)) from None
    except safe_fs.FsIntegrityError as exc:
        raise RawIntegrityError(str(exc)) from None


_renameat2: _RenameAt2 | None = safe_fs.RENAMEAT2


def rename_noreplace(src_dir_fd: int, src_name: str, dst_dir_fd: int, dst_name: str) -> None:
    """Atomically move ``src_name`` to ``dst_name`` only if the destination does not exist.

    Raises FileExistsError if it exists, UnsupportedFilesystemError if the kernel or
    filesystem cannot honor RENAME_NOREPLACE, and OSError (for example EXDEV) otherwise.
    There is no fallback to a plain rename.
    """
    with _fs_errors():
        safe_fs.rename_noreplace(src_dir_fd, src_name, dst_dir_fd, dst_name, renameat2=_renameat2)


def _component(name: str) -> bytes:
    with _fs_errors():
        return safe_fs.component(name)


def _open_dir(parent_fd: int, name: str) -> int:
    with _fs_errors():
        return safe_fs.open_dir(parent_fd, name)


def _open_file(parent_fd: int, name: str) -> int:
    with _fs_errors():
        return safe_fs.open_file(parent_fd, name)


def _check_dir(fd: int, device: int, uid: int, name: str) -> None:
    with _fs_errors():
        safe_fs.check_dir(fd, device, uid, name)


def _ensure_dir(parent_fd: int, name: str, device: int, uid: int) -> int:
    """Open ``name`` under ``parent_fd``, creating it (0700, parent synced) if missing."""
    with _fs_errors():
        return safe_fs.ensure_dir(parent_fd, name, device, uid)


def _write_all(fd: int, data: bytes) -> None:
    safe_fs.write_all(fd, data)


def _read_all(fd: int, limit: int) -> bytes:
    with _fs_errors():
        return safe_fs.read_all(fd, limit)


def _read_small(parent_fd: int, name: str, limit: int) -> bytes:
    fd = _open_file(parent_fd, name)
    try:
        return _read_all(fd, limit)
    finally:
        os.close(fd)


def _write_new_file(parent_fd: int, name: str, data: bytes) -> None:
    _component(name)
    fd = os.open(name, safe_fs.NEW_FILE_FLAGS, 0o600, dir_fd=parent_fd)
    try:
        _write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _same_entry(parent_fd: int, name: str, identity: os.stat_result) -> bool:
    """Return whether ``name`` still names the directory whose identity was recorded."""
    return safe_fs.same_entry(parent_fd, name, identity)


def _summarize_file(parent_fd: int, name: str) -> ObjectSummary:
    fd = _open_file(parent_fd, name)
    size = os.fstat(fd).st_size
    with os.fdopen(fd, "rb") as stream:
        return summarize_object(stream, size)


def _record(document: Mapping[str, object]) -> bytes:
    return canonical_json(document) + b"\n"


def _parse_record(data: bytes, what: str) -> dict[str, object]:
    if not data.endswith(b"\n"):
        raise RawIntegrityError(f"{what} is incomplete")
    try:
        return parse_canonical_json(data[:-1])
    except RawFormatError:
        raise RawIntegrityError(f"{what} is not canonical JSON") from None


def new_capture_id(started_at: datetime, token: str) -> str:
    """Build a capture ID from the UTC start time and a 128-bit random hex token."""
    started = to_utc(started_at)
    return validate_capture_id(f"{started:%Y%m%dT%H%M%S.%f}Z_{token}")


def _date_components(capture_id: str) -> tuple[str, str, str]:
    return capture_id[0:4], capture_id[4:6], capture_id[6:8]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _random_token() -> str:
    return secrets.token_hex(16)


# ----- ledgers -----

# Indirections so tests can simulate short writes and failed rollbacks.
_ledger_write: Callable[[int, bytes], int] = os.write
_ledger_truncate: Callable[[int, int], None] = os.ftruncate


def _locked_append(
    dir_fd: int, name: str, build_line: Callable[[bytes], bytes], *, authoritative: bool
) -> None:
    """Append one line under an exclusive flock, rolling back any short or failed write.

    A file that does not end with a newline has a torn tail. For the authoritative ledger
    that is an integrity failure and the append is refused; for the rebuildable catalog
    the tail is isolated with a newline and reported.
    """
    created = False
    try:
        fd = os.open(name, _LEDGER_FLAGS | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=dir_fd)
        created = True
    except FileExistsError:
        fd = os.open(name, _LEDGER_FLAGS, dir_fd=dir_fd)
    try:
        if created:
            os.fsync(dir_fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RawIntegrityError(f"{name} is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        size = os.fstat(fd).st_size
        existing = _pread_all(fd, size)
        if existing and not existing.endswith(b"\n"):
            if authoritative:
                raise RawIntegrityError(
                    f"{name} ends with an incomplete entry; appends are refused until it is "
                    "recovered by an explicit procedure"
                )
            _append_exact(fd, b"\n", size)
            _log.warning("raw.catalog_torn_tail_isolated", extra=fields(offset=size))
            size += 1
            existing += b"\n"
        _append_exact(fd, build_line(existing), size)
    finally:
        os.close(fd)


def _pread_all(fd: int, size: int) -> bytes:
    with _fs_errors():
        return safe_fs.pread_all(fd, size)


def _append_exact(fd: int, data: bytes, size_before: int) -> None:
    with _fs_errors():
        safe_fs.append_exact(fd, data, size_before, write=_ledger_write, truncate=_ledger_truncate)


def _ledger_lines(data: bytes, name: str) -> list[bytes]:
    if data and not data.endswith(b"\n"):
        raise RawIntegrityError(f"{name} ends with an incomplete entry")
    return data.split(b"\n")[:-1] if data else []


def parse_storage_events(data: bytes) -> list[RecordedStorageEvent]:
    """Verify the authoritative ledger completely; any defect is an integrity failure.

    Detects altered entries, reordering, duplicated or missing sequence numbers, and
    deleted interior entries. It cannot detect complete entries removed from the end,
    because Step 5 has no separately anchored ledger head.
    """
    events: list[RecordedStorageEvent] = []
    previous: str | None = None
    for number, line in enumerate(_ledger_lines(data, EVENTS_NAME), start=1):
        try:
            entry = parse_canonical_json(line)
        except RawFormatError:
            raise RawIntegrityError(f"storage event line {number} is not canonical JSON") from None
        event_type = entry.get("event_type")
        allowed = _EVENT_BODY_KEYS.get(event_type) if isinstance(event_type, str) else None
        if allowed is None or set(entry) != allowed | _CHAIN_KEYS:
            raise RawIntegrityError(f"storage event line {number} does not match the v1 schema")
        sequence = entry["ledger_seq"]
        if isinstance(sequence, bool) or sequence != len(events):
            raise RawIntegrityError(f"storage event line {number} breaks ledger_seq continuity")
        if entry["prev_entry_sha256"] != previous:
            raise RawIntegrityError(f"storage event line {number} breaks the hash chain")
        digest = entry["entry_sha256"]
        body = {key: value for key, value in entry.items() if key != "entry_sha256"}
        if not is_sha256(digest) or hashlib.sha256(canonical_json(body)).hexdigest() != digest:
            raise RawIntegrityError(f"storage event line {number} has an invalid entry_sha256")
        _validate_event_body(entry, number)
        entry_digest = digest
        events.append(
            RecordedStorageEvent(
                ledger_seq=len(events),
                prev_entry_sha256=previous,
                entry_sha256=entry_digest,
                body={key: entry[key] for key in allowed},
            )
        )
        previous = entry_digest
    return events


def _validate_event_body(entry: Mapping[str, object], number: int) -> None:
    try:
        validate_capture_id(entry["capture_id"])
    except ValueError:
        raise RawIntegrityError(f"storage event line {number} has a malformed capture_id") from None
    if not is_timestamp(entry["occurred_at"]):
        raise RawIntegrityError(f"storage event line {number} has a malformed occurred_at")
    for key in ("object_sha256", "restored_sha256"):
        if key in entry and not is_sha256(entry[key]):
            raise RawIntegrityError(f"storage event line {number} has a malformed {key}")
    if "backup_policy_id" in entry:
        try:
            validate_identifier(entry["backup_policy_id"], "backup_policy_id")
        except ValueError:
            raise RawIntegrityError(
                f"storage event line {number} has a malformed backup_policy_id"
            ) from None


# ----- provenance -----


def collect_runtime_provenance(
    app_config: AppConfig,
    *,
    repo_root: Path,
    machine_label: str | None = None,
    parents: Sequence[str] = (),
) -> RuntimeProvenance:
    """Describe this runtime. Call before starting captures (it runs Git in a subprocess)."""
    commit, dirty = _git_identity(repo_root)
    return RuntimeProvenance(
        code_commit=commit,
        code_tree_dirty=dirty,
        config_source_sha256=app_config.source_sha256,
        raw_config_sha256=app_config.raw_storage.canonical_sha256(),
        environment=app_config.environment,
        python_version=platform.python_version(),
        platform=f"{sys.platform}-{platform.machine().lower()}",
        machine_label=machine_label,
        parents=tuple(parents),
    )


def _git_identity(repo_root: Path) -> tuple[str | None, bool | None]:
    """Return (commit, tree_dirty), or (None, None) if they cannot be determined safely.

    Git replace objects are never honored, and a repository with any replace ref, an
    info/grafts file, or a shallow history yields (None, None): those can make a recorded
    commit name content other than what runs (Step 11 F-20, as in collect_git_identity).
    """
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    base = ["/usr/bin/git", "-C", str(repo_root)]

    def git(*arguments: str) -> bytes | None:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
                [*base, *arguments], capture_output=True, env=environment, timeout=30, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout if completed.returncode == 0 else None

    head = git("rev-parse", "--verify", "HEAD")
    replace_refs = git("for-each-ref", "--format=%(refname)", "refs/replace/")
    shallow = git("rev-parse", "--is-shallow-repository")
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    if (
        replace_refs is None
        or replace_refs.strip()
        or shallow is None
        or shallow.strip() != b"false"
        or common is None
        or os.path.lexists(Path(os.fsdecode(common.strip())) / "info" / "grafts")
    ):
        return None, None
    status = git("status", "--porcelain", "--untracked-files=normal")
    if head is None or status is None:
        return None, None
    commit = head.decode("ascii", errors="replace").strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        return None, None
    return commit, bool(status.strip())


# ----- the store -----


class RawCaptureStore:
    """Raw capture store rooted at an explicitly configured directory outside Git."""

    def __init__(
        self,
        config: RawStorageConfig,
        provenance: RuntimeProvenance,
        *,
        repo_root: Path,
        clock: Callable[[], datetime] = _utc_now,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        free_bytes: Callable[[], int] | None = None,
        random_token: Callable[[], str] = _random_token,
        fault_hook: Callable[[str], None] | None = None,
    ) -> None:
        if config.root is None:
            raise RawStorageNotConfiguredError("raw storage root is not configured")
        if provenance.raw_config_sha256 != config.canonical_sha256():
            raise RawStorageError("provenance does not describe this raw storage configuration")
        self._config = config
        self._provenance = provenance
        self._clock = clock
        self._monotonic_ns = monotonic_ns
        self._free_bytes_source = free_bytes
        self._random_token = random_token
        self._fault_hook = fault_hook
        self._fds: dict[str, int] = {}
        self._root_fd = _open_root(config.root, repo_root)
        try:
            root_status = os.fstat(self._root_fd)
            self._device = root_status.st_dev
            self._uid = os.geteuid()
            _check_dir(self._root_fd, self._device, self._uid, "raw storage root")
            for name in (RESERVATIONS, IN_PROGRESS, QUARANTINE, RAW, CATALOG):
                self._fds[name] = _ensure_dir(self._root_fd, name, self._device, self._uid)
            self._root_path = config.root
            self._identities: dict[str, safe_fs.Identity] = {
                "": safe_fs.identity(os.fstat(self._root_fd)),
                **{name: safe_fs.identity(os.fstat(fd)) for name, fd in self._fds.items()},
            }
            self._probe_capabilities()
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

    def __enter__(self) -> "RawCaptureStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # ----- capture lifecycle -----

    def start_capture(self, source: SourceIdentity, started_at: datetime) -> "RawCapture":
        """Reserve a new capture ID and open an in-progress capture for ``source``.

        Raw format v1 has no monotonic receipt time and no message direction (Step 11 F-12),
        so it never starts a capture outside the ``test`` environment: real collection uses
        the segmented v2 store (``pmv.capture_store``). Reading and verifying existing v1
        captures is unaffected.
        """
        if self._provenance.environment is not Environment.TEST:
            raise LegacyFormatRefusedError(
                "raw format v1 starts captures only in the test environment; real collection "
                "uses pmv.capture_store (frame format v2)"
            )
        warning, hard_stop = self._thresholds()
        self._check_namespace(RESERVATIONS, IN_PROGRESS)
        free = self.free_bytes()
        if free <= hard_stop:
            _log.error("raw.disk_hard_stop", extra=fields(free_bytes=free, stage="start"))
            raise DiskHardStopError("free space is at or below the hard-stop threshold", None)
        if not isinstance(source, SourceIdentity):
            raise TypeError("source must be a SourceIdentity")
        started = to_utc(started_at)
        capture_id = new_capture_id(started, self._random_token())
        self._reserve(capture_id, source)
        self._fault("start.reserved")
        in_progress = self._fds[IN_PROGRESS]
        os.mkdir(capture_id, 0o700, dir_fd=in_progress)
        os.fsync(in_progress)
        self._fault("start.in_progress_created")
        capture_fd = _open_dir(in_progress, capture_id)
        raw_fd = -1
        try:
            self._fault("start.opened")
            os.fchmod(capture_fd, 0o700)
            _check_dir(capture_fd, self._device, self._uid, capture_id)
            try:
                fcntl.flock(capture_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RawIntegrityError(
                    "another process holds the new capture's lock; start aborted"
                ) from None
            identity = os.fstat(capture_fd)
            if not _same_entry(in_progress, capture_id, identity):
                raise RawIntegrityError("the new capture directory was moved; start aborted")
            self._fault("start.locked")
            raw_fd = os.open(PARTIAL_NAME, safe_fs.NEW_FILE_FLAGS, 0o600, dir_fd=capture_fd)
            _write_all(raw_fd, MAGIC)
        except BaseException:
            if raw_fd >= 0:
                os.close(raw_fd)
            os.close(capture_fd)
            raise
        _log.info("raw.capture_started", extra=fields(capture_id=capture_id))
        return RawCapture(
            store=self,
            capture_id=capture_id,
            source=source,
            started=started,
            capture_fd=capture_fd,
            identity=identity,
            raw_fd=raw_fd,
            warning_free_bytes=warning,
            hard_stop_free_bytes=hard_stop,
        )

    def verify_capture(self, capture_id: str) -> VerificationResult:
        """Fully verify a finalized capture. Never repairs or deletes anything."""
        manifest, digest, capture_fd, read_only = self._open_finalized(capture_id)
        try:
            try:
                summary = _summarize_file(capture_fd, OBJECT_NAME)
            except RawFormatError as exc:
                raise RawIntegrityError(f"raw object failed verification: {exc}") from None
            _check_summary_against_manifest(summary, manifest)
        finally:
            os.close(capture_fd)
        return VerificationResult(capture_id, manifest, digest, read_only)

    def read_manifest(self, capture_id: str) -> RawManifest:
        """Return a finalized capture's validated manifest (without re-hashing the object)."""
        manifest, _digest, capture_fd, _read_only = self._open_finalized(capture_id)
        os.close(capture_fd)
        return manifest

    def recover_incomplete(self) -> list[RecoveryResult]:
        """Quarantine orphaned in-progress captures; never touch active or moved ones."""
        self._check_namespace(RESERVATIONS, IN_PROGRESS, QUARANTINE)
        results: list[RecoveryResult] = []
        in_progress = self._fds[IN_PROGRESS]
        for name in sorted(os.listdir(in_progress)):
            results.append(self._recover_one(in_progress, name))
        quarantine = self._fds[QUARANTINE]
        for name in sorted(os.listdir(self._fds[RESERVATIONS])):
            if CAPTURE_ID.fullmatch(name) is None:
                results.append(RecoveryResult(None, RecoveryOutcome.UNEXPECTED_ENTRY))
                continue
            present = any(
                _exists(parent, name) for parent in (in_progress, quarantine)
            ) or self._finalized_exists(name)
            if not present:
                results.append(RecoveryResult(name, RecoveryOutcome.RESERVED_NO_DATA))
        for result in results:
            _log.info(
                "raw.recovery_result",
                extra=fields(capture_id=result.capture_id, outcome=result.outcome.value),
            )
        return results

    def reconcile(self) -> ReconcileResult:
        """Rebuild missing catalog entries from verified manifests and tighten 0700 captures.

        Conflicting catalog entries are an integrity failure. Captures that fail
        verification are reported, never deleted or repaired.
        """
        self._check_namespace(RAW, CATALOG)
        report = self.read_catalog()
        if report.conflicting_ids:
            raise RawIntegrityError("the catalog has conflicting entries for a capture ID")
        added: list[str] = []
        tightened: list[str] = []
        failures: list[str] = []
        for capture_id in self._finalized_ids(failures):
            try:
                result = self.verify_capture(capture_id)
            except (RawStorageError, OSError, ValueError):
                failures.append(capture_id)
                continue
            if not result.directory_read_only:
                self._tighten(capture_id, result.manifest)
                tightened.append(capture_id)
            entry = _catalog_entry(result.manifest, result.manifest_sha256)
            existing = report.entries.get(capture_id)
            if existing is None:
                self._append_catalog(entry)
                added.append(capture_id)
            elif existing != entry:
                raise RawIntegrityError("a catalog entry conflicts with its authoritative manifest")
        return ReconcileResult(tuple(added), tuple(tightened), tuple(failures))

    def read_catalog(self) -> CatalogReport:
        """Read the rebuildable catalog; malformed lines are reported and skipped."""
        data = self._read_ledger(CATALOG_NAME)
        entries: dict[str, CatalogEntry] = {}
        invalid: list[int] = []
        conflicts: set[str] = set()
        lines = data.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        for number, line in enumerate(lines, start=1):
            entry = _parse_catalog_line(line)
            if entry is None:
                invalid.append(number)
                continue
            existing = entries.get(entry.capture_id)
            if existing is not None and existing != entry:
                conflicts.add(entry.capture_id)
            entries.setdefault(entry.capture_id, entry)
        return CatalogReport(entries, tuple(invalid), tuple(sorted(conflicts)))

    def append_storage_event(self, event: StorageEvent) -> RecordedStorageEvent:
        """Append to the authoritative ledger after verifying it completely."""
        recorded: list[RecordedStorageEvent] = []

        def build(existing: bytes) -> bytes:
            events = parse_storage_events(existing)
            body = event.body()
            body["ledger_seq"] = len(events)
            body["prev_entry_sha256"] = events[-1].entry_sha256 if events else None
            digest = hashlib.sha256(canonical_json(body)).hexdigest()
            recorded.append(
                RecordedStorageEvent(
                    ledger_seq=len(events),
                    prev_entry_sha256=events[-1].entry_sha256 if events else None,
                    entry_sha256=digest,
                    body=event.body(),
                )
            )
            return _record({**body, "entry_sha256": digest})

        self._check_namespace(CATALOG)
        _locked_append(self._fds[CATALOG], EVENTS_NAME, build, authoritative=True)
        self._check_namespace(CATALOG)
        _log.info(
            "raw.storage_event_appended",
            extra=fields(capture_id=event.capture_id, event_type=event.event_type.value),
        )
        return recorded[0]

    def read_storage_events(self) -> list[RecordedStorageEvent]:
        return parse_storage_events(self._read_ledger(EVENTS_NAME))

    def free_bytes(self) -> int:
        if self._free_bytes_source is not None:
            return self._free_bytes_source()
        status = os.statvfs(self._root_fd)
        return status.f_bavail * status.f_frsize

    # ----- internals shared with RawCapture -----

    @property
    def config(self) -> RawStorageConfig:
        return self._config

    @property
    def provenance(self) -> RuntimeProvenance:
        return self._provenance

    def _now(self) -> datetime:
        return to_utc(self._clock())

    def _fault(self, point: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(point)

    def _thresholds(self) -> tuple[int, int]:
        warning = self._config.warning_free_bytes
        hard_stop = self._config.hard_stop_free_bytes
        if warning is None or hard_stop is None:
            raise RawStorageNotConfiguredError("raw storage disk thresholds are not configured")
        return warning, hard_stop

    def _reserve(self, capture_id: str, source: SourceIdentity) -> None:
        record = _record(
            {
                "capture_id": capture_id,
                "feed_id": source.feed_id,
                "schema": "pmv.raw.reservation",
                "schema_version": 1,
                "source_id": source.source_id,
            }
        )
        reservations = self._fds[RESERVATIONS]
        try:
            _write_new_file(reservations, capture_id, record)
        except FileExistsError:
            raise DuplicateCaptureIdError("the capture ID is already reserved") from None
        os.fsync(reservations)

    def _read_reservation(self, capture_id: str) -> tuple[str, str]:
        validate_capture_id(capture_id)
        try:
            data = _read_small(self._fds[RESERVATIONS], capture_id, MAX_RECORD_BYTES)
        except FileNotFoundError:
            raise RawIntegrityError("the capture ID has no reservation") from None
        record = _parse_record(data, "reservation")
        keys = {"capture_id", "feed_id", "schema", "schema_version", "source_id"}
        if (
            set(record) != keys
            or record["schema"] != "pmv.raw.reservation"
            or record["schema_version"] != 1
            or record["capture_id"] != capture_id
        ):
            raise RawIntegrityError("the capture reservation is malformed")
        try:
            source_id = validate_identifier(record["source_id"], "source_id")
            feed_id = validate_identifier(record["feed_id"], "feed_id")
        except ValueError:
            raise RawIntegrityError("the capture reservation is malformed") from None
        return source_id, feed_id

    def _final_components(self, capture_id: str) -> list[str]:
        source_id, feed_id = self._read_reservation(capture_id)
        return [LAYOUT_VERSION, source_id, feed_id, *_date_components(capture_id)]

    def _open_final_parent(self, components: Sequence[str], *, create: bool) -> int:
        fd = self._fds[RAW]
        opened: list[int] = []
        try:
            for component in components:
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

    def _finalized_exists(self, capture_id: str) -> bool:
        try:
            parent = self._open_final_parent(self._final_components(capture_id), create=False)
        except (FileNotFoundError, RawIntegrityError):
            return False
        try:
            return _exists(parent, capture_id)
        finally:
            os.close(parent)

    def _open_finalized(self, capture_id: str) -> tuple[RawManifest, str, int, bool]:
        validate_capture_id(capture_id)
        components = self._final_components(capture_id)
        try:
            parent = self._open_final_parent(components, create=False)
        except FileNotFoundError:
            raise RawIntegrityError("the capture is not finalized") from None
        try:
            try:
                capture_fd = _open_dir(parent, capture_id)
            except FileNotFoundError:
                raise RawIntegrityError("the capture is not finalized") from None
        finally:
            os.close(parent)
        try:
            status = os.fstat(capture_fd)
            if status.st_dev != self._device or status.st_uid != self._uid:
                raise RawIntegrityError("the finalized capture is not on the raw root or not owned")
            mode = stat.S_IMODE(status.st_mode)
            if mode not in (0o500, 0o700):
                raise RawIntegrityError(
                    "the finalized capture directory has unexpected permissions"
                )
            if sorted(os.listdir(capture_fd)) != [MANIFEST_NAME, OBJECT_NAME]:
                raise RawIntegrityError("the finalized capture contains unexpected entries")
            for name in (MANIFEST_NAME, OBJECT_NAME):
                file_fd = _open_file(capture_fd, name)
                file_mode = stat.S_IMODE(os.fstat(file_fd).st_mode)
                os.close(file_fd)
                if file_mode != 0o400:
                    raise RawIntegrityError("a finalized file is not read-only")
            data = _read_small(capture_fd, MANIFEST_NAME, MAX_MANIFEST_BYTES)
            try:
                manifest = parse_manifest(data)
            except ManifestError as exc:
                raise RawIntegrityError(f"the manifest is invalid: {exc}") from None
            source_id, feed_id = components[1], components[2]
            if (
                manifest.capture_id != capture_id
                or manifest.source.source_id != source_id
                or manifest.source.feed_id != feed_id
                or manifest.raw_object.relative_path
                != expected_relative_path(manifest.source, capture_id)
            ):
                raise RawIntegrityError("the manifest does not match its capture location")
        except BaseException:
            os.close(capture_fd)
            raise
        return manifest, hashlib.sha256(data).hexdigest(), capture_fd, mode == 0o500

    def _finalized_ids(self, failures: list[str]) -> Iterator[str]:
        patterns: list[re.Pattern[str]] = [
            re.compile(LAYOUT_VERSION),
            re.compile(r"[a-z][a-z0-9_]{0,63}"),
            re.compile(r"[a-z][a-z0-9_]{0,63}"),
            _DIGITS[4],
            _DIGITS[2],
            _DIGITS[2],
            CAPTURE_ID,
        ]
        yield from self._walk(self._fds[RAW], patterns, failures)

    def _walk(
        self, parent: int, patterns: list[re.Pattern[str]], failures: list[str]
    ) -> Iterator[str]:
        pattern, rest = patterns[0], patterns[1:]
        for name in sorted(os.listdir(parent)):
            if pattern.fullmatch(name) is None:
                failures.append("unexpected entry in raw/")
                continue
            if not rest:
                yield name
                continue
            try:
                child = _open_dir(parent, name)
            except RawIntegrityError:
                failures.append("unexpected entry in raw/")
                continue
            try:
                yield from self._walk(child, rest, failures)
            finally:
                os.close(child)

    def _tighten(self, capture_id: str, manifest: RawManifest) -> None:
        components = self._final_components(capture_id)
        parent = self._open_final_parent(components, create=False)
        try:
            capture_fd = _open_dir(parent, capture_id)
            try:
                self._check_namespace(RAW)
                os.fchmod(capture_fd, 0o500)
                os.fsync(capture_fd)
            finally:
                os.close(capture_fd)
            os.fsync(parent)
        finally:
            os.close(parent)
        _log.warning("raw.capture_mode_tightened", extra=fields(capture_id=manifest.capture_id))

    def _append_catalog(self, entry: CatalogEntry) -> None:
        self._check_namespace(CATALOG)
        _locked_append(
            self._fds[CATALOG],
            CATALOG_NAME,
            lambda _existing: _record(entry.to_json()),
            authoritative=False,
        )
        self._check_namespace(CATALOG)

    def _check_namespace(self, *names: str) -> None:
        """Re-walk the configured root; require it and ``names`` to be the directories in use.

        A long-lived process holds directory handles opened at startup. If the root or a
        managed directory was moved or replaced since, operations through those handles
        would land in a detached tree, so any change fails closed.
        """
        message = "the raw storage root or a managed directory was moved or replaced"
        for name in names:
            try:
                found = safe_fs.path_identities(self._root_path, [name])
            except safe_fs.FsIntegrityError:
                raise RawIntegrityError(message) from None
            if found != [self._identities[""], self._identities[name]]:
                raise RawIntegrityError(message)

    def _read_ledger(self, name: str) -> bytes:
        try:
            fd = _open_file(self._fds[CATALOG], name)
        except FileNotFoundError:
            return b""
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            return _pread_all(fd, os.fstat(fd).st_size)
        finally:
            os.close(fd)

    def _quarantine_locked(
        self,
        capture_fd: int,
        capture_id: str,
        identity: os.stat_result,
        reason: QuarantineReason,
        oversize: tuple[int, str] | None = None,
    ) -> None:
        """Move a locked in-progress capture into quarantine/. The caller holds the lock."""
        record = _record(
            {
                "capture_id": capture_id,
                "oversize_payload_bytes": None if oversize is None else oversize[0],
                "oversize_payload_sha256": None if oversize is None else oversize[1],
                "quarantined_at": format_timestamp(self._now()),
                "reason": reason.value,
                "schema": "pmv.raw.quarantine",
                "schema_version": 1,
            }
        )
        try:
            _write_new_file(capture_fd, QUARANTINE_RECORD, record)
        except FileExistsError:
            # An earlier interrupted quarantine wrote its record; keep that record if valid.
            _validate_quarantine_record(
                _read_small(capture_fd, QUARANTINE_RECORD, MAX_RECORD_BYTES), capture_id
            )
        os.fsync(capture_fd)
        self._fault("quarantine.record_written")
        in_progress = self._fds[IN_PROGRESS]
        quarantine = self._fds[QUARANTINE]
        self._check_namespace(IN_PROGRESS, QUARANTINE)
        if not _same_entry(in_progress, capture_id, identity):
            raise RawIntegrityError("the capture directory was moved concurrently")
        rename_noreplace(in_progress, capture_id, quarantine, capture_id)
        os.fsync(quarantine)
        os.fsync(in_progress)
        self._check_namespace(IN_PROGRESS, QUARANTINE)
        self._fault("quarantine.moved")
        _log.warning(
            "raw.capture_quarantined", extra=fields(capture_id=capture_id, reason=reason.value)
        )

    def _recover_one(self, in_progress: int, name: str) -> RecoveryResult:
        if CAPTURE_ID.fullmatch(name) is None:
            return RecoveryResult(None, RecoveryOutcome.UNEXPECTED_ENTRY)
        try:
            fd = _open_dir(in_progress, name)
        except FileNotFoundError:
            return RecoveryResult(name, RecoveryOutcome.MOVED_CONCURRENTLY)
        except RawIntegrityError:
            return RecoveryResult(name, RecoveryOutcome.UNEXPECTED_ENTRY)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return RecoveryResult(name, RecoveryOutcome.ACTIVE)
            identity = os.fstat(fd)
            self._fault("recovery.locked")
            if not _same_entry(in_progress, name, identity):
                return RecoveryResult(name, RecoveryOutcome.MOVED_CONCURRENTLY)
            self._quarantine_locked(fd, name, identity, QuarantineReason.ORPHANED_IN_PROGRESS)
            return RecoveryResult(name, RecoveryOutcome.QUARANTINED)
        finally:
            os.close(fd)

    def _probe_capabilities(self) -> None:
        """Fail closed unless RENAME_NOREPLACE and flock behave correctly under the root."""
        name = f".probe-{secrets.token_hex(8)}"
        probe = _ensure_dir(self._root_fd, name, self._device, self._uid)
        lock_fds: list[int] = []
        try:
            for file_name in ("a", "b"):
                _write_new_file(probe, file_name, b"")
            try:
                rename_noreplace(probe, "a", probe, "b")
            except FileExistsError:
                pass
            else:
                raise UnsupportedFilesystemError("RENAME_NOREPLACE replaced an existing file")
            rename_noreplace(probe, "a", probe, "c")
            lock_fds = [_open_file(probe, "c"), _open_file(probe, "c")]
            fcntl.flock(lock_fds[0], fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                fcntl.flock(lock_fds[1], fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise UnsupportedFilesystemError("flock does not provide exclusive locks here")
        finally:
            for fd in lock_fds:
                os.close(fd)
            for file_name in ("a", "b", "c"):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(file_name, dir_fd=probe)
            os.close(probe)
            os.rmdir(name, dir_fd=self._root_fd)
            os.fsync(self._root_fd)


def _open_root(root: Path, repo_root: Path) -> int:
    if not root.is_absolute():
        raise RawStorageError("raw storage root must be an absolute path")
    # realpath is used only to check nesting; every later access is fd-relative.
    root_real = Path(os.path.realpath(root))
    repo_real = Path(os.path.realpath(repo_root))
    if root_real.is_relative_to(repo_real) or repo_real.is_relative_to(root_real):
        raise RawStorageError("raw storage root must be outside the Git working tree")
    try:
        return os.open(root, safe_fs.DIR_FLAGS)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RawIntegrityError("raw storage root is not a plain directory") from None
        raise


def _exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _validate_quarantine_record(data: bytes, capture_id: str) -> None:
    record = _parse_record(data, "quarantine record")
    keys = {
        "capture_id",
        "oversize_payload_bytes",
        "oversize_payload_sha256",
        "quarantined_at",
        "reason",
        "schema",
        "schema_version",
    }
    if (
        set(record) != keys
        or record["schema"] != "pmv.raw.quarantine"
        or record["schema_version"] != 1
        or record["capture_id"] != capture_id
        or record["reason"] not in {reason.value for reason in QuarantineReason}
        or not is_timestamp(record["quarantined_at"])
    ):
        raise RawIntegrityError("an existing quarantine record is malformed")


def _catalog_entry(manifest: RawManifest, manifest_sha256: str) -> CatalogEntry:
    manifest_path = manifest.raw_object.relative_path.removesuffix(OBJECT_NAME) + MANIFEST_NAME
    return CatalogEntry(
        capture_id=manifest.capture_id,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
        finalized_at=manifest.times.finalized_at,
    )


def _parse_catalog_line(line: bytes) -> CatalogEntry | None:
    try:
        document = parse_canonical_json(line)
    except RawFormatError:
        return None
    if set(document) != {"capture_id", "finalized_at", "manifest_path", "manifest_sha256"}:
        return None
    capture_id, path = document["capture_id"], document["manifest_path"]
    digest, finalized_at = document["manifest_sha256"], document["finalized_at"]
    if not (
        isinstance(capture_id, str)
        and CAPTURE_ID.fullmatch(capture_id)
        and isinstance(path, str)
        and path.endswith(f"/{capture_id}/{MANIFEST_NAME}")
        and isinstance(digest, str)
        and is_sha256(digest)
        and isinstance(finalized_at, str)
        and is_timestamp(finalized_at)
    ):
        return None
    return CatalogEntry(capture_id, path, digest, finalized_at)


def _check_summary_against_manifest(summary: ObjectSummary, manifest: RawManifest) -> None:
    obj, observations, times = manifest.raw_object, manifest.observations, manifest.times
    counts = summary.event_counts
    expected = (
        obj.size_bytes,
        obj.sha256,
        obj.record_count,
        observations.payload_count,
        observations.event_count,
        observations.malformed_message_count,
        observations.reconnect_count,
        observations.gap_event_count,
        observations.rate_limit_event_count,
        observations.source_clock_regression_count,
        observations.local_clock_regression_count,
        times.first_received_at,
        times.last_received_at,
        times.first_source_timestamp,
        times.last_source_timestamp,
    )
    actual = (
        summary.size_bytes,
        summary.sha256,
        summary.record_count,
        summary.payload_count,
        summary.event_count,
        summary.malformed_count,
        counts.get(EventType.RECONNECT, 0),
        counts.get(EventType.GAP, 0),
        counts.get(EventType.RATE_LIMIT, 0),
        counts.get(EventType.SOURCE_CLOCK_REGRESSION, 0),
        counts.get(EventType.LOCAL_CLOCK_REGRESSION, 0),
        summary.first_received_at,
        summary.last_received_at,
        summary.first_source_timestamp,
        summary.last_source_timestamp,
    )
    if expected != actual:
        raise RawIntegrityError("the raw object does not match its manifest")


class _State(Enum):
    OPEN = "open"
    POISONED = "poisoned"
    FINALIZED = "finalized"
    QUARANTINED = "quarantined"
    ABANDONED = "abandoned"


class RawCapture:
    """One in-progress capture. Single writer; not thread-safe; do not fork while open."""

    def __init__(
        self,
        *,
        store: RawCaptureStore,
        capture_id: str,
        source: SourceIdentity,
        started: datetime,
        capture_fd: int,
        identity: os.stat_result,
        raw_fd: int,
        warning_free_bytes: int,
        hard_stop_free_bytes: int,
    ) -> None:
        self._store = store
        self._capture_id = capture_id
        self._source = source
        self._started = started
        self._capture_fd = capture_fd
        self._identity = identity
        self._raw_fd = raw_fd
        self._warning = warning_free_bytes
        self._hard_stop = hard_stop_free_bytes
        self._state = _State.OPEN
        self._monotonic_start = store._monotonic_ns()
        self._hash = hashlib.sha256(MAGIC)
        self._size = len(MAGIC)
        self._sequence = 0
        self._payload_count = 0
        self._event_count = 0
        self._malformed_count = 0
        self._event_counts: dict[EventType, int] = {}
        self._warned = False
        self._last_received: datetime | None = None
        self._last_source: datetime | None = None
        self._last_written: datetime | None = None

    @property
    def capture_id(self) -> str:
        return self._capture_id

    def append_payload(
        self,
        payload: bytes,
        *,
        received_at: datetime,
        source_timestamp: datetime | None = None,
        malformed: bool = False,
    ) -> None:
        """Append the exact ``payload`` bytes. The raw layer never parses them."""
        self._require_open()
        if type(payload) is not bytes:
            raise TypeError("payload must be bytes")
        if not isinstance(malformed, bool):
            raise TypeError("malformed must be a bool")
        received = to_utc(received_at)
        source = None if source_timestamp is None else to_utc(source_timestamp)
        if len(payload) > MAX_PAYLOAD_BYTES:
            size, digest = len(payload), hashlib.sha256(payload).hexdigest()
            self._quarantine(QuarantineReason.OVERSIZE_PAYLOAD, (size, digest))
            raise CaptureOversizeError(
                f"a {size}-byte payload exceeds the {MAX_PAYLOAD_BYTES}-byte limit; "
                "the capture was stopped and quarantined"
            )
        self._check_disk()
        written, written_regressed = self._written_at()
        self._write_frame(
            encode_payload_frame(
                sequence=self._sequence,
                payload=payload,
                received_at=received,
                written_at=written,
                source_timestamp=source,
                malformed=malformed,
            )
        )
        self._payload_count += 1
        self._malformed_count += int(malformed)
        local_regressed = written_regressed or (
            self._last_received is not None and received < self._last_received
        )
        source_regressed = (
            source is not None and self._last_source is not None and source < self._last_source
        )
        self._last_received = received
        if source is not None:
            self._last_source = source
        if source_regressed:
            self._write_event(EventType.SOURCE_CLOCK_REGRESSION)
        if local_regressed:
            self._write_event(EventType.LOCAL_CLOCK_REGRESSION)

    def record_event(self, event: CaptureEvent) -> None:
        """Record a caller-observed operational event (reconnect, rate_limit, gap)."""
        self._require_open()
        if not isinstance(event, CaptureEvent):
            raise TypeError("event must be a CaptureEvent")
        self._check_disk()
        self._write_event(event.event_type)

    def finalize(self) -> RawManifest:
        """Verify, describe, and atomically move the capture into raw/."""
        if self._state is _State.POISONED:
            raise CaptureClosedError("the capture had a write failure; quarantine it")
        self._require_open()
        free = self._store.free_bytes()
        if free <= self._hard_stop:
            _log.warning(
                "raw.finalize_below_hard_stop",
                extra=fields(capture_id=self._capture_id, free_bytes=free),
            )
        return self._finalize_now()

    def quarantine(self, reason: QuarantineReason) -> None:
        """Stop the capture and move it into quarantine/ with a closed-schema record."""
        if self._state not in (_State.OPEN, _State.POISONED):
            raise CaptureClosedError("the capture is no longer in progress")
        self._quarantine(QuarantineReason(reason), None)

    # ----- internals -----

    def _require_open(self) -> None:
        if self._state is not _State.OPEN:
            raise CaptureClosedError(f"the capture is {self._state.value}")

    def _written_at(self) -> tuple[datetime, bool]:
        written = self._store._now()
        regressed = self._last_written is not None and written < self._last_written
        self._last_written = written
        return written, regressed

    def _check_disk(self) -> None:
        free = self._store.free_bytes()
        if free <= self._hard_stop:
            _log.error(
                "raw.disk_hard_stop", extra=fields(capture_id=self._capture_id, free_bytes=free)
            )
            try:
                self._write_event(EventType.DISK_HARD_STOP)
            except OSError:
                self._abandon()
                raise DiskHardStopError(
                    "hard stop reached and the capture could not be finalized; "
                    "it stays in progress",
                    None,
                ) from None
            try:
                manifest = self._finalize_now()
            except CatalogIndexError as exc:
                manifest = exc.manifest
            except (OSError, RawStorageError, RawFormatError):
                raise DiskHardStopError(
                    "hard stop reached and finalization failed; the capture stays in progress",
                    None,
                ) from None
            raise DiskHardStopError(
                "hard stop reached; the captured prefix was finalized", manifest
            )
        if free <= self._warning and not self._warned:
            self._warned = True
            _log.warning(
                "raw.disk_warning", extra=fields(capture_id=self._capture_id, free_bytes=free)
            )
            self._write_event(EventType.DISK_WARNING)

    def _write_event(self, event_type: EventType) -> None:
        self._write_frame(
            encode_event_frame(
                sequence=self._sequence, event_type=event_type, written_at=self._written_at()[0]
            )
        )
        self._event_count += 1
        self._event_counts[event_type] = self._event_counts.get(event_type, 0) + 1

    def _write_frame(self, frame: bytes) -> None:
        try:
            _write_all(self._raw_fd, frame)
        except OSError:
            self._state = _State.POISONED
            _log.error("raw.write_failed", extra=fields(capture_id=self._capture_id))
            raise
        self._hash.update(frame)
        self._size += len(frame)
        self._sequence += 1

    def _finalize_now(self) -> RawManifest:
        try:
            return self._finalize_steps()
        except BaseException:
            if self._state is not _State.FINALIZED:
                self._abandon()
            raise

    def _finalize_steps(self) -> RawManifest:
        store, capture_fd, capture_id = self._store, self._capture_fd, self._capture_id
        ended = store._now()
        duration = max(0, store._monotonic_ns() - self._monotonic_start)
        os.fsync(self._raw_fd)
        os.close(self._raw_fd)
        self._raw_fd = -1
        store._fault("finalize.raw_synced")
        try:
            summary = _summarize_file(capture_fd, PARTIAL_NAME)
        except RawFormatError as exc:
            raise RawIntegrityError(f"re-read verification failed: {exc}") from None
        if (summary.size_bytes, summary.sha256, summary.record_count) != (
            self._size,
            self._hash.hexdigest(),
            self._sequence,
        ):
            raise RawIntegrityError("re-read verification does not match the written frames")
        store._fault("finalize.raw_verified")
        rename_noreplace(capture_fd, PARTIAL_NAME, capture_fd, OBJECT_NAME)
        os.fsync(capture_fd)
        store._fault("finalize.raw_renamed")
        manifest = self._build_manifest(summary, ended, duration)
        manifest_bytes = manifest.to_bytes()
        _write_new_file(capture_fd, MANIFEST_TMP_NAME, manifest_bytes)
        store._fault("finalize.manifest_written")
        rename_noreplace(capture_fd, MANIFEST_TMP_NAME, capture_fd, MANIFEST_NAME)
        os.fsync(capture_fd)
        store._fault("finalize.manifest_renamed")
        for name in (OBJECT_NAME, MANIFEST_NAME):
            file_fd = _open_file(capture_fd, name)
            try:
                os.fchmod(file_fd, 0o400)
            finally:
                os.close(file_fd)
        os.fsync(capture_fd)
        store._fault("finalize.files_read_only")
        components = [LAYOUT_VERSION, self._source.source_id, self._source.feed_id]
        components.extend(_date_components(capture_id))
        store._check_namespace(IN_PROGRESS, RAW)
        destination = store._open_final_parent(components, create=True)
        try:
            store._fault("finalize.destination_ready")
            in_progress = store._fds[IN_PROGRESS]
            store._check_namespace(IN_PROGRESS, RAW)
            if not _same_entry(in_progress, capture_id, self._identity):
                raise RawIntegrityError("the capture directory was moved concurrently")
            rename_noreplace(in_progress, capture_id, destination, capture_id)
            self._state = _State.FINALIZED
            os.fsync(destination)
            os.fsync(in_progress)
            store._check_namespace(IN_PROGRESS, RAW)
            store._fault("finalize.moved")
            os.fchmod(capture_fd, 0o500)
            os.fsync(capture_fd)
            os.fsync(destination)
        finally:
            os.close(destination)
            os.close(capture_fd)
            self._capture_fd = -1
        store._fault("finalize.read_only")
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        _log.info(
            "raw.capture_finalized",
            extra=fields(
                capture_id=capture_id,
                size_bytes=manifest.raw_object.size_bytes,
                sha256=manifest.raw_object.sha256,
                record_count=manifest.raw_object.record_count,
            ),
        )
        try:
            store._fault("finalize.before_catalog")
            store._append_catalog(_catalog_entry(manifest, digest))
        except (OSError, RawStorageError):
            _log.error("raw.catalog_append_failed", extra=fields(capture_id=capture_id))
            raise CatalogIndexError(
                "the capture was finalized but its catalog entry was not appended; run reconcile()",
                manifest,
            ) from None
        return manifest

    def _build_manifest(
        self, summary: ObjectSummary, ended: datetime, duration: int
    ) -> RawManifest:
        store = self._store
        counts = summary.event_counts
        config = store.config
        return RawManifest(
            capture_id=self._capture_id,
            source=self._source,
            raw_object=RawObjectMetadata(
                relative_path=expected_relative_path(self._source, self._capture_id),
                size_bytes=summary.size_bytes,
                sha256=summary.sha256,
                record_count=summary.record_count,
            ),
            times=CaptureTimes(
                capture_started_at=format_timestamp(self._started),
                capture_ended_at=format_timestamp(ended),
                first_received_at=summary.first_received_at,
                last_received_at=summary.last_received_at,
                first_source_timestamp=summary.first_source_timestamp,
                last_source_timestamp=summary.last_source_timestamp,
                finalized_at=format_timestamp(store._now()),
                monotonic_duration_ns=duration,
            ),
            observations=Observations(
                payload_count=summary.payload_count,
                event_count=summary.event_count,
                malformed_message_count=summary.malformed_count,
                reconnect_count=counts.get(EventType.RECONNECT, 0),
                gap_event_count=counts.get(EventType.GAP, 0),
                rate_limit_event_count=counts.get(EventType.RATE_LIMIT, 0),
                source_clock_regression_count=counts.get(EventType.SOURCE_CLOCK_REGRESSION, 0),
                local_clock_regression_count=counts.get(EventType.LOCAL_CLOCK_REGRESSION, 0),
            ),
            provenance=store.provenance,
            policy=CapturePolicy(
                retention_class=config.retention_class,
                backup_policy_id=config.backup_policy_id,
                backup_status_at_finalization=(
                    BackupStatus.NOT_CONFIGURED
                    if config.backup_policy_id is None
                    else BackupStatus.PENDING
                ),
            ),
        )

    def _quarantine(self, reason: QuarantineReason, oversize: tuple[int, str] | None) -> None:
        if self._raw_fd >= 0:
            with contextlib.suppress(OSError):
                os.fsync(self._raw_fd)
            os.close(self._raw_fd)
            self._raw_fd = -1
        try:
            self._store._quarantine_locked(
                self._capture_fd, self._capture_id, self._identity, reason, oversize
            )
        except BaseException:
            self._abandon()
            raise
        os.close(self._capture_fd)
        self._capture_fd = -1
        self._state = _State.QUARANTINED

    def _abandon(self) -> None:
        """Release everything and leave the capture in .inprogress for recovery."""
        for attribute in ("_raw_fd", "_capture_fd"):
            fd = getattr(self, attribute)
            if fd >= 0:
                os.close(fd)
                setattr(self, attribute, -1)
        if self._state not in (_State.FINALIZED, _State.QUARANTINED):
            self._state = _State.ABANDONED
            _log.error("raw.capture_left_in_progress", extra=fields(capture_id=self._capture_id))
