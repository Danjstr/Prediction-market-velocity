"""Tamper-evident experiment tracking store (Phase 0 Step 6).

Layout under the explicitly configured root (no default; outside Git and the raw root)::

    .run_ids/<run_id>                 permanent run-ID reservation (closed metadata)
    runs/<run_id>/run_spec.json       immutable spec; spec_sha256 = SHA-256 of its bytes
    runs/<run_id>/environment.json    canonical environment document (pmv.reproducibility);
                                      its SHA-256 is the v2 identity's installed_environment_sha256
    runs/<run_id>/artifacts/<name>    registered artifacts (0400)
    runs/<run_id>/.staging/           private temporary files, never trusted
    runs/<run_id>/manifest.json       completed runs only; hash recorded in run_completed
    ledger/experiments.v1.jsonl       AUTHORITATIVE global hash-chained ledger
    ledger/repair/torn-*.bin          immutable torn-tail repair evidence
    ledger/repair-pending-<store_id>-<evidence>
                                      durable pending-repair marker (copy of the torn bytes)
    store.v1.json                     permanent store identity, bound by ledger entry 0

The ledger is created (with its ledger_created genesis entry) only in a pristine store,
and its identity is pinned when the store opens. Every authoritative append takes an
exclusive flock, re-walks the configured root to confirm the root, ledger directory, and
ledger file (and, for run events, the run directory) are the ones in use, verifies the
entire ledger from byte 0 (with checkpoints and repair evidence), appends one canonical
line with rollback on any short or failed write, reads it back, and re-checks identity
before reporting success. Run directories are locked for their active life and their
identity is re-checked after every run-local durable step and around every run event.

Limits: tamper evidence is detection, not prevention; complete entries removed from the
end are detectable only before the latest committed checkpoint; durability across power
loss depends on the filesystem and virtualization stack. An evidence_candidate start is
refused unless pmv.reproducibility.verify passes; its environment fingerprint is recorded in
a v2 execution identity and re-checked at completion (a change fails the run with
environment_changed). What a fingerprint does not prove: docs/reproducibility.md.
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
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from importlib import metadata
from pathlib import Path
from types import TracebackType
from typing import Final

from pmv import experiment_ledger as ledger
from pmv import reproducibility, safe_fs
from pmv.experiment_ledger import (
    Checkpoint,
    Entry,
    EvidenceFile,
    LedgerEvent,
    LedgerState,
    RunState,
)
from pmv.experiment_spec import (
    SECTION_NAMES,
    AbortReason,
    ArtifactType,
    ExecutionIdentity,
    FailureCode,
    InputRef,
    MediaType,
    RawCaptureInput,
    RunArtifactInput,
    RunClass,
    RunSpec,
    SpecError,
    SupersedeReason,
    WarningCode,
    metric_value,
    parse_run_spec,
    require_artifact_name,
    require_identifier,
    require_run_id,
    require_split,
)
from pmv.integrity import (
    FormatError,
    canonical_line,
    format_timestamp,
    is_non_negative_int,
    parse_canonical_json,
    sha256_hex,
    to_utc,
)
from pmv.log import fields, get_logger
from pmv.raw_storage import RawCaptureStore, RawStorageError

_log = get_logger(__name__)

RUN_IDS: Final = ".run_ids"
RUNS: Final = "runs"
LEDGER_DIR: Final = "ledger"
REPAIR_DIR: Final = "repair"
LEDGER_NAME: Final = "experiments.v1.jsonl"
STORE_NAME: Final = "store.v1.json"
STORE_SCHEMA: Final = "pmv.experiment.store"
SPEC_NAME: Final = "run_spec.json"
ENVIRONMENT_NAME: Final = "environment.json"
MANIFEST_NAME: Final = "manifest.json"
ARTIFACTS: Final = "artifacts"
STAGING: Final = ".staging"
CHECKPOINT_RELATIVE: Final = Path("research") / "experiment-ledger-checkpoints.v1.jsonl"
PACKAGE_NAME: Final = "prediction-market-velocity"
MAX_EVIDENCE_BYTES: Final = 16_777_216
_STAGED_NAME: Final = re.compile(r"part-[0-9a-f]{32}")

# Test seams: simulated short writes and failed rollbacks, and the RENAME_NOREPLACE function.
_ledger_write: Callable[[int, bytes], int] = os.write
_ledger_truncate: Callable[[int, int], None] = os.ftruncate
_renameat2: safe_fs.RenameAt2 | None = safe_fs.RENAMEAT2


class ExperimentError(Exception):
    """An experiment-tracking operation failed. Messages never contain contents."""


class ExperimentIntegrityError(ExperimentError):
    """Authoritative evidence is inconsistent, unsafe, moved, or replaced."""


class ExperimentUnsupportedError(ExperimentError):
    """The filesystem lacks a required capability (fail closed)."""


class TornLedgerError(ExperimentIntegrityError):
    """The ledger ends with an incomplete entry; only repair_torn_tail() may proceed."""


class PendingRepairEvidenceError(ExperimentIntegrityError):
    """Repair evidence is not yet referenced; only repair_torn_tail() may proceed."""


class DuplicateRunIdError(ExperimentIntegrityError):
    """A run ID was already reserved."""


class LedgerBusyError(ExperimentError):
    """The ledger lock could not be acquired within the time limit."""


class RunStateError(ExperimentError):
    """The operation is not allowed in the run's current state."""


class InputVerificationError(ExperimentError):
    """An input reference could not be verified exactly."""


class RecoveryOutcome(StrEnum):
    INTERRUPTED = "interrupted"
    ACTIVE = "active"
    MOVED_CONCURRENTLY = "moved_concurrently"
    MISSING_DIRECTORY = "missing_directory"
    RESERVED_UNRECORDED = "reserved_unrecorded"


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    run_id: str
    outcome: RecoveryOutcome


@dataclass(frozen=True, slots=True)
class RunVerification:
    run_id: str
    state: RunState
    unregistered_files: tuple[str, ...]
    staging_files: tuple[str, ...]
    orphan_manifest: bool


@dataclass(frozen=True, slots=True)
class RepairReport:
    evidence_written: str | None
    truncated_bytes: int
    events_appended: tuple[str, ...]
    evidence_restored: tuple[str, ...] = ()
    markers_retired: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PendingMarker:
    """A durable pending-repair marker: its name binds the store and every repair fact,
    and its content is an exact copy of the torn bytes."""

    name: str
    evidence_name: str
    content: bytes


@dataclass(frozen=True, slots=True)
class CheckpointStatus:
    checkpoint: Checkpoint
    committed_in_git: bool


@dataclass(frozen=True, slots=True)
class GitIdentity:
    commit: str | None
    dirty: bool | None
    dirty_sha256: str | None


UNKNOWN_GIT: Final = GitIdentity(None, None, None)


@contextlib.contextmanager
def _fs_errors() -> Iterator[None]:
    try:
        yield
    except safe_fs.FsUnsupportedError as exc:
        raise ExperimentUnsupportedError(str(exc)) from None
    except safe_fs.FsIntegrityError as exc:
        raise ExperimentIntegrityError(str(exc)) from None


@contextlib.contextmanager
def _ledger_errors() -> Iterator[None]:
    try:
        yield
    except ledger.TornTailError as exc:
        raise TornLedgerError(str(exc)) from None
    except ledger.PendingRepairError as exc:
        raise PendingRepairEvidenceError(str(exc)) from None
    except ledger.LedgerError as exc:
        raise ExperimentIntegrityError(str(exc)) from None


def _rename(src_fd: int, src: str, dst_fd: int, dst: str) -> None:
    with _fs_errors():
        safe_fs.rename_noreplace(src_fd, src, dst_fd, dst, renameat2=_renameat2)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _random_token() -> str:
    return secrets.token_hex(16)


# ----- code identity -----


def collect_git_identity(repo_root: Path) -> GitIdentity:
    """Collect the commit and a deterministic dirty-tree fingerprint, or UNKNOWN_GIT.

    Git runs with a clean environment and fixed options. Skip-worktree and
    assume-unchanged entries count as dirty. Untracked, non-ignored paths are identified
    by their raw bytes; symlinks are recorded by target and never followed; any other
    non-regular untracked object makes the identity unknown. Repository-local Git
    configuration and attributes still apply.
    """
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    base = [
        "/usr/bin/git",
        "-C",
        str(repo_root),
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
    ]

    def git(*arguments: str) -> bytes | None:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
                [*base, *arguments], capture_output=True, env=environment, timeout=120, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout if completed.returncode == 0 else None

    head = git("rev-parse", "--verify", "HEAD")
    status = git(
        "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"
    )
    flags = git("ls-files", "-v", "-z")
    if head is None or status is None or flags is None:
        return UNKNOWN_GIT
    commit = head.decode("ascii", errors="replace").strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        return UNKNOWN_GIT
    special = any(entry[:1].islower() or entry[:1] == b"S" for entry in flags.split(b"\0") if entry)
    if not status and not special:
        return GitIdentity(commit, False, None)
    diff = git(
        "diff",
        "HEAD",
        "--binary",
        "--full-index",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "--diff-algorithm=myers",
    )
    untracked = git("ls-files", "-z", "--others", "--exclude-standard")
    if diff is None or untracked is None:
        return UNKNOWN_GIT
    entries: list[dict[str, object]] = []
    for raw_path in sorted(path for path in untracked.split(b"\0") if path):
        path = repo_root / os.fsdecode(raw_path)
        try:
            status_info = os.lstat(path)
            if stat.S_ISLNK(status_info.st_mode):
                kind, digest = "symlink", sha256_hex(os.fsencode(os.readlink(path)))
            elif stat.S_ISREG(status_info.st_mode):
                kind, digest = "file", _hash_path(path)
            else:
                return UNKNOWN_GIT
        except OSError:
            return UNKNOWN_GIT
        entries.append({"path_hex": raw_path.hex(), "sha256": digest, "type": kind})
    fingerprint = canonical_line({"diff_sha256": sha256_hex(diff), "untracked": entries})
    return GitIdentity(commit, True, sha256_hex(fingerprint))


def _hash_path(path: Path) -> str:
    fd = os.open(path, safe_fs.READ_FLAGS)
    try:
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1_048_576):
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(fd)


def capture_environment(
    repo_root: Path, *, verify_conformance: bool
) -> reproducibility.EnvironmentCapture:
    """The running environment's canonical document and fingerprint; with
    ``verify_conformance`` it must first conform to the approved project (a test seam)."""
    if verify_conformance:
        return reproducibility.verify(repo_root)
    return reproducibility.capture()


def _uv_lock_sha256(repo_root: Path) -> str | None:
    try:
        return _hash_path(repo_root / "uv.lock")
    except OSError:
        return None


def _package_version() -> str:
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return "0.0.0"


# ----- the store -----


class ExperimentStore:
    """Experiment tracking store rooted at an explicitly configured directory."""

    def __init__(
        self,
        root: Path,
        *,
        repo_root: Path,
        app_config_sha256: str,
        raw_root: Path | None = None,
        raw_store: RawCaptureStore | None = None,
        checkpoint_file: Path | None = None,
        clock: Callable[[], datetime] = _utc_now,
        random_token: Callable[[], str] = _random_token,
        fault_hook: Callable[[str], None] | None = None,
        lock_timeout_seconds: float = 30.0,
    ) -> None:
        if not root.is_absolute():
            raise ExperimentError("the experiment root must be an absolute path")
        root_real = Path(os.path.realpath(root))
        for other in (repo_root, raw_root):
            if other is None:
                continue
            other_real = Path(os.path.realpath(other))
            if root_real.is_relative_to(other_real) or other_real.is_relative_to(root_real):
                raise ExperimentError(
                    "the experiment root must not be nested with the repository or raw root"
                )
        self._root_path = root
        self._repo_root = repo_root
        self._app_config_sha256 = app_config_sha256
        self._raw_store = raw_store
        self._checkpoint_file = checkpoint_file or repo_root / CHECKPOINT_RELATIVE
        self._clock = clock
        self._random_token = random_token
        self._fault_hook = fault_hook
        self._lock_timeout = lock_timeout_seconds
        self._sync_failed = False
        self._fds: dict[str, int] = {}
        try:
            self._root_fd = os.open(root, safe_fs.DIR_FLAGS)
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise ExperimentIntegrityError(
                    "the experiment root is not a plain directory"
                ) from None
            raise
        try:
            self._device = os.fstat(self._root_fd).st_dev
            self._uid = os.geteuid()
            with _fs_errors():
                safe_fs.check_dir(self._root_fd, self._device, self._uid, "experiment root")
                for name in (RUN_IDS, RUNS, LEDGER_DIR):
                    self._fds[name] = safe_fs.ensure_dir(
                        self._root_fd, name, self._device, self._uid
                    )
                self._fds[REPAIR_DIR] = safe_fs.ensure_dir(
                    self._fds[LEDGER_DIR], REPAIR_DIR, self._device, self._uid
                )
                safe_fs.probe_capabilities(
                    self._root_fd, self._device, self._uid, renameat2=_renameat2
                )
            self._identities = {
                name: safe_fs.identity(os.fstat(fd)) for name, fd in self._fds.items()
            }
            self._identities[""] = safe_fs.identity(os.fstat(self._root_fd))
            self._identities[LEDGER_NAME] = self._open_or_create_ledger()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        for fd in self._fds.values():
            os.close(fd)
        self._fds.clear()
        if getattr(self, "_root_fd", -1) >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def __enter__(self) -> "ExperimentStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # ----- runs -----

    def reserve_run(self, study_id: str, run_class: RunClass) -> "RunHandle":
        """Reserve a new run ID, lock its directory, and record run_reserved."""
        require_identifier(study_id, "study_id")
        requested = RunClass(run_class)
        self._require_not_latched()
        self._check_namespace()
        run_id = f"{to_utc(self._clock()):%Y%m%dT%H%M%S.%f}Z_{self._random_token()}"
        require_run_id(run_id)
        record = canonical_line(
            {
                "run_id": run_id,
                "schema": "pmv.experiment.run_reservation",
                "schema_version": 1,
                "study_id": study_id,
            }
        )
        with _fs_errors():
            try:
                safe_fs.write_new_file(self._fds[RUN_IDS], run_id, record)
            except FileExistsError:
                raise DuplicateRunIdError("the run ID is already reserved") from None
        os.fsync(self._fds[RUN_IDS])
        self._fault("reserve.reserved")
        runs = self._fds[RUNS]
        os.mkdir(run_id, 0o700, dir_fd=runs)
        os.fsync(runs)
        with _fs_errors():
            run_fd = safe_fs.open_dir(runs, run_id)
        try:
            os.fchmod(run_fd, 0o700)
            try:
                fcntl.flock(run_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ExperimentIntegrityError("another process holds the new run's lock") from None
            identity = os.fstat(run_fd)
            if not safe_fs.same_entry(runs, run_id, identity):
                raise ExperimentIntegrityError(
                    "the new run directory was moved; reservation aborted"
                )
            for name in (ARTIFACTS, STAGING):
                os.mkdir(name, 0o700, dir_fd=run_fd)
            os.fsync(run_fd)
            self._fault("reserve.locked")

            def run_check() -> None:
                self._check_namespace()
                if not safe_fs.same_entry(runs, run_id, identity):
                    raise ExperimentIntegrityError("the run directory was moved or replaced")

            self._append(
                lambda _state: (
                    LedgerEvent.RUN_RESERVED,
                    run_id,
                    {"run_class": requested.value, "study_id": study_id},
                ),
                run_check=run_check,
            )
        except BaseException:
            os.close(run_fd)
            raise
        _log.info("experiments.run_reserved", extra=fields(run_id=run_id))
        return RunHandle(self, run_id, study_id, requested, run_fd, identity)

    def supersede(self, run_id: str, superseded_by: str, reason: SupersedeReason) -> Entry:
        require_run_id(run_id)
        require_run_id(superseded_by, "superseded_by")
        why = SupersedeReason(reason)
        return self._append(
            lambda _state: (
                LedgerEvent.RUN_SUPERSEDED,
                run_id,
                {"reason": why.value, "superseded_by": superseded_by},
            )
        )

    def snapshot(self) -> LedgerState:
        """Fully verify the ledger (with checkpoints and repair evidence) under a shared lock."""
        with self._locked_ledger(exclusive=False) as (_fd, data):
            return self._verify(data)[0]

    def ledger_head(self) -> tuple[int, str | None]:
        state = self.snapshot()
        return state.head_seq, state.head_sha256

    def eligibility_as_of(self, run_id: str, ledger_seq: int | None = None) -> bool:
        """Derived evidence eligibility of a run and its transitive inputs at a ledger head."""
        state = self.snapshot()
        seq = state.head_seq if ledger_seq is None else ledger_seq
        if seq > state.head_seq:
            raise ExperimentError("the requested ledger_seq is beyond the verified head")
        return ledger.eligibility_as_of(state, run_id, seq)

    def recover(self) -> list[RecoveryResult]:
        """Append run_interrupted for unlocked RESERVED/STARTED runs; never touch active runs."""
        self._check_namespace()
        state = self.snapshot()
        results: list[RecoveryResult] = []
        runs = self._fds[RUNS]
        for run in sorted(state.runs.values(), key=lambda item: item.reserved_seq):
            if run.state not in (RunState.RESERVED, RunState.STARTED):
                continue
            results.append(self._recover_one(runs, run.run_id, run.state))
        known = set(state.runs)
        for name in sorted(os.listdir(self._fds[RUN_IDS])):
            if name not in known:
                results.append(RecoveryResult(name, RecoveryOutcome.RESERVED_UNRECORDED))
        for result in results:
            _log.info(
                "experiments.recovery_result",
                extra=fields(run_id=result.run_id, outcome=result.outcome.value),
            )
        return results

    def verify_run(self, run_id: str) -> RunVerification:
        """Verify a run's spec, artifacts, and (if completed) its exact completion manifest."""
        require_run_id(run_id)
        state = self.snapshot()
        run = state.runs.get(run_id)
        if run is None:
            raise ExperimentIntegrityError("the run is not in the ledger")
        self._check_namespace()
        with _fs_errors():
            run_fd = safe_fs.open_dir(self._fds[RUNS], run_id)
        try:
            unregistered: tuple[str, ...] = ()
            staging: tuple[str, ...] = ()
            orphan = False
            if run.started_seq is not None:
                self._verify_spec(run_fd, run)
                self._verify_environment(run_fd, run)
            with _fs_errors():
                artifacts_fd = safe_fs.open_dir(run_fd, ARTIFACTS)
                staging_fd = safe_fs.open_dir(run_fd, STAGING)
            try:
                present = set(os.listdir(artifacts_fd))
                for name, (item, _seq) in run.artifacts.items():
                    if name not in present:
                        raise ExperimentIntegrityError("a registered artifact is missing")
                    _verify_artifact_file(artifacts_fd, name, item)
                unregistered = tuple(sorted(present - set(run.artifacts)))
                staging = tuple(sorted(os.listdir(staging_fd)))
            finally:
                os.close(artifacts_fd)
                os.close(staging_fd)
            has_manifest = safe_fs.exists(run_fd, MANIFEST_NAME)
            if run.state is RunState.COMPLETED:
                with _ledger_errors():
                    expected = ledger.completion_manifest_bytes(state, run_id)
                with _fs_errors():
                    actual = safe_fs.read_small(run_fd, MANIFEST_NAME, len(expected) + 1)
                if actual != expected or sha256_hex(actual) != run.manifest_sha256:
                    raise ExperimentIntegrityError("the completion manifest does not match")
            else:
                orphan = has_manifest
        finally:
            os.close(run_fd)
        return RunVerification(run_id, run.state, unregistered, staging, orphan)

    # ----- checkpoints -----

    def append_checkpoint(self) -> Checkpoint:
        """Append the verified ledger head to the checkpoint file. Never commits."""
        with self._locked_ledger(exclusive=True) as (_fd, data):
            state = self._verify(data)[0]
            if state.head_seq < 0 or state.head_sha256 is None:
                raise ExperimentError("the ledger is empty")
            existing = self._checkpoints()
            if existing and existing[-1].ledger_seq >= state.head_seq:
                raise ExperimentError("the ledger head is already checkpointed")
            checkpoint = Checkpoint(
                state.head_seq, state.head_sha256, format_timestamp(self._now())
            )
            line = ledger.checkpoint_line(
                checkpoint.ledger_seq, checkpoint.entry_sha256, checkpoint.recorded_at
            )
            self._append_checkpoint_line(line)
        _log.info("experiments.checkpoint_appended", extra=fields(ledger_seq=checkpoint.ledger_seq))
        return checkpoint

    def checkpoint_status(self) -> list[CheckpointStatus]:
        """Report which local checkpoint entries are also present in the committed HEAD."""
        local = self._checkpoints()
        committed_lines: set[bytes] = set()
        try:
            relative = self._checkpoint_file.relative_to(self._repo_root)
        except ValueError:
            return [CheckpointStatus(item, False) for item in local]
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
                [
                    "/usr/bin/git",
                    "-C",
                    str(self._repo_root),
                    "--no-optional-locks",
                    "show",
                    f"HEAD:{relative.as_posix()}",
                ],
                capture_output=True,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": "/nonexistent",
                    "LC_ALL": "C",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
                timeout=60,
                check=False,
            )
            if completed.returncode == 0:
                committed_lines = set(completed.stdout.split(b"\n"))
        except (OSError, subprocess.TimeoutExpired):
            committed_lines = set()
        return [
            CheckpointStatus(
                item,
                ledger.checkpoint_line(item.ledger_seq, item.entry_sha256, item.recorded_at)[:-1]
                in committed_lines,
            )
            for item in local
        ]

    # ----- torn-tail repair -----

    def repair_torn_tail(self) -> RepairReport:
        """Operator-invoked repair: preserve a torn tail as evidence, then remove it.

        Never automatic. Refuses on any checkpoint contradiction, on malformed complete
        entries, and on evidence that cannot be proven consistent with the ledger. Torn
        bytes are preserved durably before the ledger is truncated, and every evidence
        file ends up referenced by exactly one ledger_tail_repaired event.
        """
        self._require_not_latched()
        with self._locked_ledger(exclusive=True) as (fd, data):
            with _ledger_errors():
                state, torn = ledger.verify_ledger(data, allow_torn_tail=True)
                ledger.verify_checkpoints(state, self._checkpoints())
                pending = ledger.pending_evidence(state, self._evidence_files())
            self._check_store_binding(state)
            written: str | None = None
            truncated = 0
            if torn is not None:
                torn_bytes = data[torn:]
                name = ledger.evidence_name(
                    offset=torn,
                    length=len(torn_bytes),
                    original_size=len(data),
                    last_seq=state.head_seq,
                    last_sha256=state.head_sha256,
                    torn_sha256=sha256_hex(torn_bytes),
                )
                for item in pending:
                    if item.name != name:
                        with _ledger_errors():
                            ledger.check_pending_matches_head(state, item)
                evidence_identity: safe_fs.Identity | None = None
                if name not in {item.name for item in pending}:
                    evidence_identity = self._write_evidence(name, torn_bytes)
                    written = name
                self._fault("repair.evidence_written")
                # The pending state is durable before truncation, outside ledger/repair/.
                marker_identity = self._write_marker(name, torn_bytes)
                self._fault("repair.marker_written")
                self._confirm_before_truncation(
                    fd, data, name, torn_bytes, evidence_identity, marker_identity
                )
                self._fault("repair.before_truncate")
                try:
                    os.ftruncate(fd, torn)
                    os.fsync(fd)
                except OSError:
                    self._sync_failed = True
                    raise
                truncated = len(torn_bytes)
                data = data[:torn]
                self._fault("repair.truncated")
                _log.warning(
                    "experiments.torn_tail_preserved",
                    extra=fields(torn_byte_length=truncated, ledger_seq=state.head_seq),
                )
            restored = self._restore_evidence_from_markers(data)
            appended: list[str] = []
            while True:
                with _ledger_errors():
                    state, _torn = ledger.verify_ledger(data)
                    remaining = ledger.pending_evidence(state, self._evidence_files())
                if not remaining:
                    break
                item = remaining[0]
                with _ledger_errors():
                    ledger.check_pending_matches_head(state, item)
                facts = ledger.parse_evidence_name(item.name)
                if facts is None:
                    raise ExperimentIntegrityError("repair evidence name is malformed")
                event_fields: dict[str, object] = {**facts, "repair_evidence_name": item.name}
                entry_line = self._append_locked(
                    fd, data, _repair_builder(event_fields), allow_pending=True
                )
                data += entry_line
                appended.append(item.name)
                self._fault("repair.event_appended")
            retired = self._retire_markers(data)
            return RepairReport(written, truncated, tuple(appended), restored, retired)

    def _restore_evidence_from_markers(self, data: bytes) -> tuple[str, ...]:
        """Re-create evidence missing from ledger/repair/ from its durable pending marker.

        This covers a repair directory moved or replaced after truncation: the marker holds
        the exact torn bytes, so the repair event can still be recorded.
        """
        with _ledger_errors():
            state, _torn = ledger.verify_ledger(data)
        restored: list[str] = []
        for marker in self._pending_markers():
            if marker.evidence_name in state.repairs:
                continue
            if safe_fs.exists(self._fds[REPAIR_DIR], marker.evidence_name):
                continue
            self._write_evidence(marker.evidence_name, marker.content)
            restored.append(marker.evidence_name)
            _log.warning("experiments.repair_evidence_restored")
        return tuple(restored)

    def _retire_markers(self, data: bytes) -> tuple[str, ...]:
        """Remove a pending marker only after its ledger_tail_repaired event is durable.

        The event (already read back and identity-checked) is the permanent record; a crash
        before or during removal leaves the marker, and repair_torn_tail() finishes it.
        """
        with _ledger_errors():
            state, _torn = ledger.verify_ledger(data)
        retired: list[str] = []
        ledger_dir = self._fds[LEDGER_DIR]
        for marker in self._pending_markers():
            entry = state.repairs.get(marker.evidence_name)
            if entry is None:
                raise ExperimentIntegrityError(
                    "a pending-repair marker has no matching ledger_tail_repaired event"
                )
            os.unlink(marker.name, dir_fd=ledger_dir)
            self._fault("repair.marker_unlinked")
            os.fsync(ledger_dir)
            retired.append(marker.evidence_name)
        return tuple(retired)

    # ----- internals -----

    def _require_not_latched(self) -> None:
        if self._sync_failed:
            raise ExperimentIntegrityError(
                "a ledger write failed earlier; open a new store to re-verify before appending"
            )

    def _fault(self, point: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(point)

    def _now(self) -> datetime:
        return to_utc(self._clock())

    def _check_namespace(self) -> None:
        """Re-walk the configured root; every managed directory must be the one in use."""
        expected_root = self._identities[""]
        message = "the experiment root or a managed directory was moved or replaced"
        for components, name in (
            ([RUN_IDS], RUN_IDS),
            ([RUNS], RUNS),
            ([LEDGER_DIR, REPAIR_DIR], REPAIR_DIR),
        ):
            try:
                found = safe_fs.path_identities(self._root_path, components)
            except safe_fs.FsIntegrityError:
                raise ExperimentIntegrityError(message) from None
            expected = [expected_root]
            if name == REPAIR_DIR:
                expected.append(self._identities[LEDGER_DIR])
            expected.append(self._identities[name])
            if found != expected:
                raise ExperimentIntegrityError(message)

    def _check_ledger_file(self, fd: int) -> None:
        """The configured path and ``fd`` must both be the ledger file pinned at open."""
        expected = [
            self._identities[""],
            self._identities[LEDGER_DIR],
            self._identities[LEDGER_NAME],
        ]
        message = "the experiment ledger was moved or replaced"
        try:
            found = safe_fs.path_identities(self._root_path, [LEDGER_DIR, LEDGER_NAME])
        except safe_fs.FsIntegrityError:
            raise ExperimentIntegrityError(message) from None
        if found != expected or safe_fs.identity(os.fstat(fd)) != expected[-1]:
            raise ExperimentIntegrityError(message)

    def _open_or_create_ledger(self) -> safe_fs.Identity:
        """Return the ledger's identity, creating it only in a pristine store.

        A missing ledger is never recreated in a store with prior history: a reservation,
        a run directory, repair evidence, or a checkpoint. Creation is atomic: the
        ledger_created genesis line is staged, synced, and moved into place with
        RENAME_NOREPLACE, so a ledger never exists without entry 0. An empty ledger is an
        integrity failure.
        """
        ledger_dir = self._fds[LEDGER_DIR]
        store_id = self._read_store_id()
        try:
            status = os.stat(LEDGER_NAME, dir_fd=ledger_dir, follow_symlinks=False)
        except FileNotFoundError:
            store_id = self._create_ledger(ledger_dir, store_id)
            status = os.stat(LEDGER_NAME, dir_fd=ledger_dir, follow_symlinks=False)
        if store_id is None:
            raise ExperimentIntegrityError("the experiment store identity record is missing")
        self._store_id = store_id
        if stat.S_ISLNK(status.st_mode):
            raise ExperimentIntegrityError("the experiment ledger is a symlink")
        if not stat.S_ISREG(status.st_mode):
            raise ExperimentIntegrityError("the experiment ledger is not a regular file")
        if status.st_size == 0:
            raise ExperimentIntegrityError(
                "the experiment ledger is empty; it has no ledger_created entry"
            )
        return safe_fs.identity(status)

    def _create_ledger(self, ledger_dir: int, store_id: str | None) -> str:
        used = any(os.listdir(self._fds[name]) for name in (RUN_IDS, RUNS, REPAIR_DIR))
        markers = any(
            name.startswith(ledger.PENDING_MARKER_PREFIX) for name in os.listdir(ledger_dir)
        )
        if used or markers or self._checkpoints():
            raise ExperimentIntegrityError(
                "the experiment ledger is missing but the store has prior history; "
                "it was not recreated"
            )
        if store_id is None:
            store_id = self._create_store_record()
        line = ledger.encode_entry(
            LedgerState(),
            LedgerEvent.LEDGER_CREATED,
            None,
            format_timestamp(self._now()),
            {"store_id": store_id},
        )
        stage = f".create-{self._random_token()}"
        with _fs_errors():
            safe_fs.write_new_file(ledger_dir, stage, line)
        try:
            _rename(ledger_dir, stage, ledger_dir, LEDGER_NAME)
        except FileExistsError:
            # Another process created the ledger first; ours was never visible.
            os.unlink(stage, dir_fd=ledger_dir)
        os.fsync(ledger_dir)
        _log.info("experiments.ledger_created")
        return store_id

    def _create_store_record(self) -> str:
        """Create the permanent, read-only store identity record (pristine stores only)."""
        store_id = self._random_token()
        if not ledger.is_store_id(store_id):
            raise ExperimentError("the store identity token is malformed")
        record = canonical_line({"schema": STORE_SCHEMA, "schema_version": 1, "store_id": store_id})
        stage = f".store-{self._random_token()}"
        with _fs_errors():
            safe_fs.write_new_file(self._root_fd, stage, record)
            fd = safe_fs.open_file(self._root_fd, stage)
        try:
            os.fchmod(fd, 0o400)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            _rename(self._root_fd, stage, self._root_fd, STORE_NAME)
        except FileExistsError:
            os.unlink(stage, dir_fd=self._root_fd)
        os.fsync(self._root_fd)
        existing = self._read_store_id()
        if existing is None:
            raise ExperimentIntegrityError("the experiment store identity record is missing")
        return existing

    def _read_store_id(self) -> str | None:
        try:
            with _fs_errors():
                data = safe_fs.read_small(self._root_fd, STORE_NAME, 4096)
        except FileNotFoundError:
            return None
        try:
            document = parse_canonical_json(data[:-1]) if data.endswith(b"\n") else None
        except FormatError:
            document = None
        if (
            document is None
            or set(document) != {"schema", "schema_version", "store_id"}
            or document["schema"] != STORE_SCHEMA
            or type(document["schema_version"]) is not int
            or document["schema_version"] != 1
            or not ledger.is_store_id(document["store_id"])
        ):
            raise ExperimentIntegrityError("the experiment store identity record is malformed")
        return str(document["store_id"])

    @contextlib.contextmanager
    def _locked_ledger(self, *, exclusive: bool) -> Iterator[tuple[int, bytes]]:
        self._check_namespace()
        fd = self._open_ledger(self._fds[LEDGER_DIR])
        try:
            self._lock(fd, exclusive)
            self._check_ledger_file(fd)
            with _fs_errors():
                data = safe_fs.pread_all(fd, os.fstat(fd).st_size)
            if not data:
                raise ExperimentIntegrityError(
                    "the experiment ledger is empty; it has no ledger_created entry"
                )
            yield fd, data
        finally:
            os.close(fd)

    def _open_ledger(self, ledger_dir: int) -> int:
        try:
            fd = os.open(LEDGER_NAME, safe_fs.APPEND_FLAGS, dir_fd=ledger_dir)
        except FileNotFoundError:
            raise ExperimentIntegrityError(
                "the experiment ledger is missing; it is never recreated for a used store"
            ) from None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ExperimentIntegrityError("the experiment ledger is a symlink") from None
            raise
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise ExperimentIntegrityError("the experiment ledger is not a regular file")
        return fd

    def _lock(self, fd: int, exclusive: bool) -> None:
        mode = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
        deadline = time.monotonic() + self._lock_timeout
        while True:
            try:
                fcntl.flock(fd, mode)
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LedgerBusyError(
                        "the experiment ledger lock was not acquired in time"
                    ) from None
                time.sleep(0.005)

    def _verify(
        self, data: bytes, *, allow_pending: bool = False
    ) -> tuple[LedgerState, list[EvidenceFile]]:
        with _ledger_errors():
            state, _torn = ledger.verify_ledger(data)
            ledger.verify_checkpoints(state, self._checkpoints())
            pending = ledger.pending_evidence(state, self._evidence_files())
            if pending and not allow_pending:
                raise ledger.PendingRepairError(
                    "repair evidence is not referenced by the ledger; run repair_torn_tail()"
                )
        self._check_store_binding(state)
        if self._pending_markers() and not allow_pending:
            raise PendingRepairEvidenceError(
                "a ledger repair is pending; run repair_torn_tail() to finish it"
            )
        if not set(state.runs) <= set(os.listdir(self._fds[RUN_IDS])):
            raise ExperimentIntegrityError(
                "the ledger names runs this store never reserved; it was replaced"
            )
        return state, pending

    def _append(
        self,
        build: Callable[[LedgerState], tuple[LedgerEvent, str | None, dict[str, object]]],
        *,
        allow_pending: bool = False,
        run_check: Callable[[], None] | None = None,
    ) -> Entry:
        """Append one event. ``run_check`` confirms a locked run's directory identity."""
        self._require_not_latched()
        if run_check is not None:
            run_check()
        with self._locked_ledger(exclusive=True) as (fd, data):
            line = self._append_locked(
                fd, data, build, allow_pending=allow_pending, run_check=run_check
            )
        with _ledger_errors():
            state, _torn = ledger.verify_ledger(data + line)
        return state.entries[-1]

    def _append_locked(
        self,
        fd: int,
        data: bytes,
        build: Callable[[LedgerState], tuple[LedgerEvent, str | None, dict[str, object]]],
        *,
        allow_pending: bool,
        run_check: Callable[[], None] | None = None,
    ) -> bytes:
        self._require_not_latched()
        state, _pending = self._verify(data, allow_pending=allow_pending)
        event_type, run_id, event_fields = build(state)
        line = ledger.encode_entry(
            state, event_type, run_id, format_timestamp(self._now()), event_fields
        )
        with _ledger_errors():
            ledger.verify_ledger(data + line)
        self._fault("ledger.before_write")
        self._check_namespace()
        self._check_ledger_file(fd)
        if run_check is not None:
            run_check()
        if os.fstat(fd).st_size != len(data):
            raise ExperimentIntegrityError("the ledger changed outside the lock")
        try:
            safe_fs.append_exact(
                fd, line, len(data), write=_ledger_write, truncate=_ledger_truncate
            )
        except safe_fs.RollbackError as exc:
            self._sync_failed = True
            raise ExperimentIntegrityError(str(exc)) from None
        except OSError:
            self._sync_failed = True
            raise
        self._fault("ledger.after_write")
        try:
            with _fs_errors():
                readback = safe_fs.pread_all(fd, len(line), len(data))
            if os.fstat(fd).st_size != len(data) + len(line) or readback != line:
                raise ExperimentIntegrityError("the appended entry could not be read back exactly")
            self._check_namespace()
            self._check_ledger_file(fd)
            if run_check is not None:
                run_check()
        except (ExperimentError, OSError) as exc:
            # The line was written and synced, so it may be durable in some file; whether
            # the authoritative ledger holds it is unknown.
            self._sync_failed = True
            raise ExperimentIntegrityError(
                f"{exc}; write outcome unknown; re-verify authoritative state"
            ) from None
        _log.info(
            "experiments.ledger_appended",
            extra=fields(event_type=event_type.value, run_id=run_id, ledger_seq=state.head_seq + 1),
        )
        return line

    def _check_store_binding(self, state: LedgerState) -> None:
        with _ledger_errors():
            bound = ledger.store_id_of(state)
        if bound != self._store_id:
            raise ExperimentIntegrityError("the ledger belongs to a different experiment store")

    def _pending_markers(self) -> list[PendingMarker]:
        """Every pending-repair marker in ledger/, validated against its name and store."""
        ledger_dir = self._fds[LEDGER_DIR]
        markers: list[PendingMarker] = []
        for name in sorted(os.listdir(ledger_dir)):
            if not name.startswith(ledger.PENDING_MARKER_PREFIX):
                continue
            parsed = ledger.parse_pending_marker_name(name)
            if parsed is None or parsed[0] != self._store_id:
                raise ExperimentIntegrityError("a pending-repair marker is malformed or foreign")
            facts = ledger.parse_evidence_name(parsed[1])
            with _fs_errors():
                content = safe_fs.read_small(ledger_dir, name, MAX_EVIDENCE_BYTES)
            if (
                facts is None
                or facts["torn_byte_length"] != len(content)
                or facts["torn_sha256"] != sha256_hex(content)
            ):
                raise ExperimentIntegrityError("a pending-repair marker does not match its name")
            markers.append(PendingMarker(name, parsed[1], content))
        return markers

    def _write_marker(self, evidence: str, content: bytes) -> safe_fs.Identity:
        """Durably create the pending-repair marker (no-replace) before any truncation."""
        ledger_dir = self._fds[LEDGER_DIR]
        name = ledger.pending_marker_name(self._store_id, evidence)
        if not safe_fs.exists(ledger_dir, name):
            stage = f".stage-{self._random_token()}"
            with _fs_errors():
                safe_fs.write_new_file(ledger_dir, stage, content)
                fd = safe_fs.open_file(ledger_dir, stage)
            try:
                os.fchmod(fd, 0o400)
                os.fsync(fd)
            finally:
                os.close(fd)
            _rename(ledger_dir, stage, ledger_dir, name)
            os.fsync(ledger_dir)
            os.fsync(self._root_fd)
        with _fs_errors():
            fd = safe_fs.open_file(ledger_dir, name)
        try:
            with _fs_errors():
                existing = safe_fs.read_all(fd, MAX_EVIDENCE_BYTES)
            marker_identity = safe_fs.identity(os.fstat(fd))
        finally:
            os.close(fd)
        if existing != content:
            raise ExperimentIntegrityError("an existing pending-repair marker does not match")
        return marker_identity

    def _evidence_files(self) -> list[EvidenceFile]:
        repair = self._fds[REPAIR_DIR]
        evidence: list[EvidenceFile] = []
        for name in sorted(os.listdir(repair)):
            if name.startswith(".stage-"):
                continue
            with _fs_errors():
                content = safe_fs.read_small(repair, name, MAX_EVIDENCE_BYTES)
            evidence.append(EvidenceFile(name, len(content), sha256_hex(content)))
        return evidence

    def _write_evidence(self, name: str, content: bytes) -> safe_fs.Identity:
        repair = self._fds[REPAIR_DIR]
        stage = f".stage-{self._random_token()}"
        with _fs_errors():
            safe_fs.write_new_file(repair, stage, content)
            if safe_fs.read_small(repair, stage, MAX_EVIDENCE_BYTES) != content:
                raise ExperimentIntegrityError("staged repair evidence did not read back exactly")
        _rename(repair, stage, repair, name)
        with _fs_errors():
            fd = safe_fs.open_file(repair, name)
        try:
            os.fchmod(fd, 0o400)
            evidence_identity = safe_fs.identity(os.fstat(fd))
        finally:
            os.close(fd)
        os.fsync(repair)
        os.fsync(self._fds[LEDGER_DIR])
        return evidence_identity

    def _confirm_before_truncation(
        self,
        fd: int,
        data: bytes,
        name: str,
        torn_bytes: bytes,
        evidence_identity: safe_fs.Identity | None,
        marker_identity: safe_fs.Identity,
    ) -> None:
        """Prove, immediately before truncation, that the evidence is durable where the
        authoritative root says it is and that the ledger is exactly what was verified.

        Re-walks root, ledger/, ledger/repair/, and the evidence file from the configured
        path without following symlinks; requires the evidence to be the same object that
        was written (or verified, on resume) with exactly the torn bytes. Any failure
        latches the store and leaves the ledger untruncated.
        """
        try:
            self._check_namespace()
            try:
                found = safe_fs.path_identities(self._root_path, [LEDGER_DIR, REPAIR_DIR, name])
            except safe_fs.FsIntegrityError:
                raise ExperimentIntegrityError("repair evidence is not in place") from None
            expected = [
                self._identities[""],
                self._identities[LEDGER_DIR],
                self._identities[REPAIR_DIR],
            ]
            if found[:3] != expected:
                raise ExperimentIntegrityError("the repair-evidence directory was replaced")
            if evidence_identity is not None and found[3] != evidence_identity:
                raise ExperimentIntegrityError("the repair evidence was replaced")
            with _fs_errors():
                evidence_fd = safe_fs.open_file(self._fds[REPAIR_DIR], name)
            try:
                if safe_fs.identity(os.fstat(evidence_fd)) != found[3]:
                    raise ExperimentIntegrityError("the repair evidence was replaced")
                with _fs_errors():
                    content = safe_fs.read_all(evidence_fd, MAX_EVIDENCE_BYTES)
            finally:
                os.close(evidence_fd)
            if len(content) != len(torn_bytes) or sha256_hex(content) != sha256_hex(torn_bytes):
                raise ExperimentIntegrityError("the repair evidence does not hold the torn bytes")
            marker = ledger.pending_marker_name(self._store_id, name)
            try:
                found = safe_fs.path_identities(self._root_path, [LEDGER_DIR, marker])
            except safe_fs.FsIntegrityError:
                raise ExperimentIntegrityError(
                    "the pending-repair marker is not in place"
                ) from None
            if found != [self._identities[""], self._identities[LEDGER_DIR], marker_identity]:
                raise ExperimentIntegrityError("the pending-repair marker was replaced")
            self._check_ledger_file(fd)
            with _fs_errors():
                current = safe_fs.pread_all(fd, os.fstat(fd).st_size)
            if current != data:
                raise ExperimentIntegrityError("the ledger changed during repair")
        except (ExperimentError, OSError) as exc:
            self._sync_failed = True
            raise ExperimentIntegrityError(f"{exc}; the ledger was not truncated") from None

    def _checkpoints(self) -> list[Checkpoint]:
        try:
            fd = os.open(self._checkpoint_file, safe_fs.READ_FLAGS)
        except FileNotFoundError:
            return []
        try:
            with _fs_errors():
                data = safe_fs.read_all(fd, MAX_EVIDENCE_BYTES)
        finally:
            os.close(fd)
        with _ledger_errors():
            return ledger.parse_checkpoints(data)

    def _append_checkpoint_line(self, line: bytes) -> None:
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(self._checkpoint_file, flags, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            size = os.fstat(fd).st_size
            with _fs_errors():
                safe_fs.append_exact(fd, line, size)
        finally:
            os.close(fd)
        directory = os.open(self._checkpoint_file.parent, safe_fs.DIR_FLAGS)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _resolve_inputs(self, inputs: Sequence[InputRef]) -> list[dict[str, object]]:
        resolved: list[dict[str, object]] = []
        for reference in inputs:
            if isinstance(reference, RawCaptureInput):
                if self._raw_store is None:
                    raise InputVerificationError("raw_capture inputs need a raw capture store")
                try:
                    verified = self._raw_store.verify_capture(reference.capture_id)
                except (RawStorageError, ValueError, OSError):
                    raise InputVerificationError(
                        "a raw capture input failed verification"
                    ) from None
                if verified.manifest_sha256 != reference.manifest_sha256:
                    raise InputVerificationError("a raw capture manifest hash does not match")
                provenance = verified.manifest.provenance
                clean = provenance.code_commit is not None and provenance.code_tree_dirty is False
                resolved.append({**reference.to_json(), "capture_code_clean": clean})
            else:
                self._verify_artifact_bytes(reference)
                resolved.append(reference.to_json())
        return resolved

    def _verify_artifact_bytes(self, reference: RunArtifactInput) -> None:
        try:
            with _fs_errors():
                run_fd = safe_fs.open_dir(self._fds[RUNS], reference.run_id)
            try:
                with _fs_errors():
                    artifacts_fd = safe_fs.open_dir(run_fd, ARTIFACTS)
                try:
                    digest, _size = _hash_file(artifacts_fd, reference.artifact_name)
                finally:
                    os.close(artifacts_fd)
            finally:
                os.close(run_fd)
        except (OSError, ExperimentIntegrityError):
            raise InputVerificationError("a run artifact input could not be read safely") from None
        if digest != reference.sha256:
            raise InputVerificationError("a run artifact input's bytes do not match its hash")

    def _verify_spec(self, run_fd: int, run: ledger.RunRecord) -> None:
        size = run.start_fields["spec_size_bytes"]
        if not is_non_negative_int(size):
            raise ExperimentIntegrityError("the recorded spec size is malformed")
        with _fs_errors():
            data = safe_fs.read_small(run_fd, SPEC_NAME, size)
        if sha256_hex(data) != run.start_fields["spec_sha256"]:
            raise ExperimentIntegrityError("run_spec.json does not match its recorded hash")
        try:
            spec = parse_run_spec(data)
        except SpecError:
            raise ExperimentIntegrityError("run_spec.json is invalid") from None
        recorded = [
            {key: value for key, value in item.items() if key != "capture_code_clean"}
            for item in run.inputs
        ]
        if recorded != [reference.to_json() for reference in spec.inputs]:
            raise ExperimentIntegrityError("run_spec.json inputs do not match run_started")

    def _verify_environment(self, run_fd: int, run: ledger.RunRecord) -> None:
        """environment.json exists exactly when a fingerprint was recorded, and matches it."""
        digest = None if run.identity is None else run.identity.installed_environment_sha256
        present = safe_fs.exists(run_fd, ENVIRONMENT_NAME)
        if digest is None:
            if present:
                raise ExperimentIntegrityError(
                    "environment.json exists but the run recorded no fingerprint"
                )
            return
        if not present:
            raise ExperimentIntegrityError("environment.json is missing")
        with _fs_errors():
            data = safe_fs.read_small(run_fd, ENVIRONMENT_NAME, reproducibility.MAX_DOCUMENT_BYTES)
        if sha256_hex(data) != digest:
            raise ExperimentIntegrityError("environment.json does not match its recorded hash")
        try:
            reproducibility.parse_document(data)
        except reproducibility.ReproducibilityError:
            raise ExperimentIntegrityError("environment.json is invalid") from None

    def _recover_one(self, runs: int, run_id: str, last_state: RunState) -> RecoveryResult:
        try:
            with _fs_errors():
                fd = safe_fs.open_dir(runs, run_id)
        except FileNotFoundError:
            return RecoveryResult(run_id, RecoveryOutcome.MISSING_DIRECTORY)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return RecoveryResult(run_id, RecoveryOutcome.ACTIVE)
            identity = os.fstat(fd)
            self._fault("recovery.locked")
            self._check_namespace()
            if not safe_fs.same_entry(runs, run_id, identity):
                return RecoveryResult(run_id, RecoveryOutcome.MOVED_CONCURRENTLY)

            def run_check() -> None:
                self._check_namespace()
                if not safe_fs.same_entry(runs, run_id, identity):
                    raise ExperimentIntegrityError("the run directory was moved or replaced")

            self._append(
                lambda _state: (
                    LedgerEvent.RUN_INTERRUPTED,
                    run_id,
                    {"last_state": last_state.value},
                ),
                run_check=run_check,
            )
            _seal_run_directory(fd)
            return RecoveryResult(run_id, RecoveryOutcome.INTERRUPTED)
        finally:
            os.close(fd)


def _repair_builder(
    event_fields: dict[str, object],
) -> Callable[[LedgerState], tuple[LedgerEvent, str | None, dict[str, object]]]:
    def build(_state: LedgerState) -> tuple[LedgerEvent, str | None, dict[str, object]]:
        return LedgerEvent.LEDGER_TAIL_REPAIRED, None, event_fields

    return build


def _hash_file(parent_fd: int, name: str) -> tuple[str, int]:
    with _fs_errors():
        fd = safe_fs.open_file(parent_fd, name)
    try:
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(fd, 1_048_576):
            digest.update(chunk)
            size += len(chunk)
        return digest.hexdigest(), size
    finally:
        os.close(fd)


def _verify_artifact_file(artifacts_fd: int, name: str, item: object) -> None:
    digest, size = _hash_file(artifacts_fd, name)
    if not isinstance(item, dict) or digest != item["sha256"] or size != item["size_bytes"]:
        raise ExperimentIntegrityError("a registered artifact does not match its recorded hash")
    mode = stat.S_IMODE(os.stat(name, dir_fd=artifacts_fd, follow_symlinks=False).st_mode)
    if mode != 0o400:
        raise ExperimentIntegrityError("a registered artifact is not read-only")


def _seal_run_directory(run_fd: int) -> None:
    """Make a terminal run's directories read-only (0500). Defense in depth only."""
    for name in (ARTIFACTS, STAGING):
        try:
            child = safe_fs.open_dir(run_fd, name)
        except (OSError, safe_fs.FsIntegrityError):
            continue
        try:
            os.fchmod(child, 0o500)
            os.fsync(child)
        finally:
            os.close(child)
    os.fchmod(run_fd, 0o500)
    os.fsync(run_fd)


def _check_run_artifact_inputs(state: LedgerState, resolved: list[dict[str, object]]) -> None:
    for item in resolved:
        if item["kind"] == "run_artifact":
            producer = state.runs.get(str(item["run_id"]))
            artifact = (
                None if producer is None else producer.artifacts.get(str(item["artifact_name"]))
            )
            if (
                producer is None
                or producer.state is not RunState.COMPLETED
                or artifact is None
                or artifact[0]["sha256"] != item["sha256"]
            ):
                raise InputVerificationError(
                    "a run_artifact input is not a registered artifact of a completed run"
                )


class RunHandle:
    """One reserved run. The run directory stays locked until the run is terminal."""

    def __init__(
        self,
        store: ExperimentStore,
        run_id: str,
        study_id: str,
        requested: RunClass,
        run_fd: int,
        identity: os.stat_result,
    ) -> None:
        self._store = store
        self.run_id = run_id
        self.study_id = study_id
        self._requested = requested
        self._run_fd = run_fd
        self._identity = identity
        self._state = RunState.RESERVED
        self._spec: RunSpec | None = None
        self._start_identity: tuple[GitIdentity, str | None] | None = None
        self._start_environment: str | None = None

    # ----- lifecycle -----

    def start(self, spec: RunSpec) -> Entry:
        """Verify inputs, write run_spec.json, and record run_started with full provenance."""
        self._require(RunState.RESERVED)
        if spec.study_id != self.study_id:
            raise RunStateError("the spec's study_id does not match the reservation")
        self._check_run_dir()
        store = self._store
        resolved = store._resolve_inputs(spec.inputs)
        git = collect_git_identity(store._repo_root)
        uv_lock = _uv_lock_sha256(store._repo_root)
        spec_bytes = spec.to_bytes()
        # Advisory pre-check so a refused start leaves no spec behind; the authoritative
        # check repeats under the ledger lock in build().
        _check_run_artifact_inputs(store.snapshot(), resolved)
        environment = self._capture_environment()
        if environment is None and safe_fs.exists(self._run_fd, ENVIRONMENT_NAME):
            # An earlier start attempt captured an environment that this one cannot: refuse
            # rather than record no fingerprint beside an existing environment.json.
            raise RunStateError(
                "an earlier start recorded environment.json but the environment can no longer "
                "be captured; start refused"
            )
        self._write_spec(spec_bytes)
        if environment is not None:
            self._write_environment(environment.document)
        identity = ExecutionIdentity(
            spec_sha256=sha256_hex(spec_bytes),
            code_commit=git.commit,
            code_tree_dirty=git.dirty,
            dirty_tree_sha256=git.dirty_sha256,
            package_version=_package_version(),
            uv_lock_sha256=uv_lock,
            installed_environment_sha256=None if environment is None else environment.sha256,
            app_config_sha256=store._app_config_sha256,
            config_section_sha256={name: spec.section_sha256(name) for name in SECTION_NAMES},
            python_version=platform.python_version(),
            platform=f"{sys.platform}-{platform.machine().lower()}",
            entrypoint=spec.entrypoint,
        )

        def build(state: LedgerState) -> tuple[LedgerEvent, str | None, dict[str, object]]:
            _check_run_artifact_inputs(state, resolved)
            effective = ledger.effective_run_class(self._requested, identity)
            eligible = ledger.start_eligibility(
                state, state.head_seq, effective, identity, resolved
            )
            return (
                LedgerEvent.RUN_STARTED,
                self.run_id,
                {
                    "effective_run_class_at_start": effective.value,
                    "evidence_eligible_at_start": eligible,
                    "execution_identity": identity.to_json(),
                    "execution_identity_sha256": identity.sha256(),
                    "inputs": resolved,
                    "spec_sha256": identity.spec_sha256,
                    "spec_size_bytes": len(spec_bytes),
                },
            )

        entry = store._append(build, run_check=self._check_run_dir)
        self._state = RunState.STARTED
        self._spec = spec
        self._start_identity = (git, uv_lock)
        self._start_environment = None if environment is None else environment.sha256
        return entry

    def staging_path(self) -> Path:
        """A fresh private path for a library to write an artifact into before commit."""
        self._require(RunState.STARTED)
        return (
            self._store._root_path
            / RUNS
            / self.run_id
            / STAGING
            / f"part-{self._store._random_token()}"
        )

    def write_artifact(
        self,
        name: str,
        data: bytes,
        *,
        artifact_type: ArtifactType,
        media_type: MediaType,
        schema_id: str | None = None,
        schema_version: int | None = None,
    ) -> Entry:
        """Write ``data`` as a new artifact (never overwriting) and register it."""
        self._require(RunState.STARTED)
        staged = self.staging_path()
        with _fs_errors():
            staging_fd = safe_fs.open_dir(self._run_fd, STAGING)
        try:
            with _fs_errors():
                safe_fs.write_new_file(staging_fd, staged.name, data)
        finally:
            os.close(staging_fd)
        return self.commit_artifact(
            staged,
            name,
            artifact_type=artifact_type,
            media_type=media_type,
            schema_id=schema_id,
            schema_version=schema_version,
        )

    def commit_artifact(
        self,
        staged: Path,
        name: str,
        *,
        artifact_type: ArtifactType,
        media_type: MediaType,
        schema_id: str | None = None,
        schema_version: int | None = None,
    ) -> Entry:
        """Hash a staged file, move it into artifacts/ without overwriting, and register it."""
        self._require(RunState.STARTED)
        require_artifact_name(name)
        kind, media = ArtifactType(artifact_type), MediaType(media_type)
        if schema_id is not None:
            require_identifier(schema_id, "artifact_schema_id")
        if (schema_id is None) != (schema_version is None):
            raise SpecError("artifact schema id and version go together")
        if schema_version is not None and not is_non_negative_int(schema_version):
            raise SpecError("artifact schema version must be a non-negative integer")
        expected_dir = self._store._root_path / RUNS / self.run_id / STAGING
        if staged.parent != expected_dir or _STAGED_NAME.fullmatch(staged.name) is None:
            raise RunStateError("the staged path is not this run's private staging path")
        self._check_run_dir()
        with _fs_errors():
            staging_fd = safe_fs.open_dir(self._run_fd, STAGING)
            artifacts_fd = safe_fs.open_dir(self._run_fd, ARTIFACTS)
        try:
            with _fs_errors():
                fd = safe_fs.open_file(staging_fd, staged.name)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            digest, size = _hash_file(staging_fd, staged.name)
            self._store._fault("artifact.staged")
            self._check_run_dir()
            try:
                _rename(staging_fd, staged.name, artifacts_fd, name)
            except FileExistsError:
                raise RunStateError("an artifact with that name already exists") from None
            with _fs_errors():
                fd = safe_fs.open_file(artifacts_fd, name)
            try:
                os.fchmod(fd, 0o400)
            finally:
                os.close(fd)
            os.fsync(artifacts_fd)
            os.fsync(staging_fd)
        finally:
            os.close(staging_fd)
            os.close(artifacts_fd)
        self._check_run_dir()
        self._store._fault("artifact.moved")
        event_fields: dict[str, object] = {
            "artifact_schema_id": schema_id,
            "artifact_schema_version": schema_version,
            "artifact_type": kind.value,
            "media_type": media.value,
            "name": name,
            "sha256": digest,
            "size_bytes": size,
        }
        entry = self._store._append(
            lambda _state: (LedgerEvent.ARTIFACT_REGISTERED, self.run_id, event_fields),
            run_check=self._check_run_dir,
        )
        _log.info(
            "experiments.artifact_registered",
            extra=fields(run_id=self.run_id, size_bytes=size, sha256=digest),
        )
        return entry

    def record_metric(
        self,
        name: str,
        split: str,
        value: int | Decimal | float,
        *,
        unit: str | None = None,
        fold: str | None = None,
        step: int | None = None,
    ) -> Entry:
        self._require(RunState.STARTED)
        require_identifier(name, "metric name")
        chosen = require_split(split)
        for item, what in ((unit, "unit"), (fold, "fold")):
            if item is not None:
                require_identifier(item, f"metric {what}")
        if step is not None and not is_non_negative_int(step):
            raise SpecError("metric step must be a non-negative integer")
        event_fields: dict[str, object] = {
            "fold": fold,
            "name": name,
            "split": chosen.value,
            "step": step,
            "unit": unit,
            "value": metric_value(value),
        }
        return self._store._append(
            lambda _state: (LedgerEvent.METRIC_RECORDED, self.run_id, event_fields),
            run_check=self._check_run_dir,
        )

    def record_warning(self, code: WarningCode, context: str | None = None) -> Entry:
        self._require(RunState.STARTED)
        chosen = WarningCode(code)
        if context is not None:
            require_identifier(context, "warning context")
        return self._store._append(
            lambda _state: (
                LedgerEvent.WARNING_RECORDED,
                self.run_id,
                {"code": chosen.value, "context": context},
            ),
            run_check=self._check_run_dir,
        )

    def complete(self) -> Entry:
        """Verify inputs and artifacts, write the pre-terminal manifest, record run_completed."""
        self._require(RunState.STARTED)
        store = self._store
        self._check_run_dir()
        git = collect_git_identity(store._repo_root)
        uv_lock = _uv_lock_sha256(store._repo_root)
        if self._start_identity != (git, uv_lock):
            self.fail(FailureCode.CODE_IDENTITY_CHANGED)
            raise RunStateError("the code identity changed during the run; the run was failed")
        if self._start_environment is not None:
            try:
                current: str | None = capture_environment(
                    store._repo_root, verify_conformance=False
                ).sha256
            except reproducibility.ReproducibilityError:
                current = None
            if current != self._start_environment:
                self.fail(FailureCode.ENVIRONMENT_CHANGED)
                raise RunStateError(
                    "the installed environment changed during the run; the run was failed"
                )
        snapshot = store.snapshot()
        run = snapshot.runs[self.run_id]
        if run.state is not RunState.STARTED:
            raise RunStateError("the run is not started")
        self._verify_files(run)
        if self._spec is None:
            raise RunStateError("the run has no spec")
        if store._resolve_inputs(self._spec.inputs) != [dict(item) for item in run.inputs]:
            raise InputVerificationError("an input no longer matches what the run started with")
        expected_last = run.last_event_seq

        def build(state: LedgerState) -> tuple[LedgerEvent, str | None, dict[str, object]]:
            current = state.runs[self.run_id]
            if current.state is not RunState.STARTED or current.last_event_seq != expected_last:
                raise RunStateError("the run changed while it was being completed")
            with _ledger_errors():
                manifest = ledger.completion_manifest_bytes(state, self.run_id)
            self._write_manifest(manifest)
            store._fault("complete.manifest_written")
            return (
                LedgerEvent.RUN_COMPLETED,
                self.run_id,
                {
                    "artifact_count": len(current.artifacts),
                    "manifest_sha256": sha256_hex(manifest),
                    "metric_count": len(current.metrics),
                },
            )

        entry = store._append(build, run_check=self._check_run_dir)
        self._finish(RunState.COMPLETED)
        _log.info("experiments.run_completed", extra=fields(run_id=self.run_id))
        return entry

    def fail(self, failure_code: FailureCode, exception_type: str | None = None) -> Entry:
        """Record run_failed. Only the exception's type name is stored, never its message."""
        self._require(RunState.STARTED)
        code = FailureCode(failure_code)
        entry = self._store._append(
            lambda _state: (
                LedgerEvent.RUN_FAILED,
                self.run_id,
                {"exception_type": exception_type, "failure_code": code.value},
            ),
            run_check=self._check_run_dir,
        )
        self._finish(RunState.FAILED)
        return entry

    def abort(self, reason: AbortReason) -> Entry:
        if self._state not in (RunState.RESERVED, RunState.STARTED):
            raise RunStateError("the run is no longer active")
        why = AbortReason(reason)
        entry = self._store._append(
            lambda _state: (LedgerEvent.RUN_ABORTED, self.run_id, {"reason": why.value}),
            run_check=self._check_run_dir,
        )
        self._finish(RunState.ABORTED)
        return entry

    def release(self) -> None:
        """Release the run lock without a terminal event (recovery will interrupt the run)."""
        if self._run_fd >= 0:
            os.close(self._run_fd)
            self._run_fd = -1

    # ----- internals -----

    def _require(self, state: RunState) -> None:
        if self._state is not state or self._run_fd < 0:
            raise RunStateError(f"the run is {self._state.value}, not {state.value}")

    def _check_run_dir(self) -> None:
        self._store._check_namespace()
        if not safe_fs.same_entry(self._store._fds[RUNS], self.run_id, self._identity):
            raise ExperimentIntegrityError("the run directory was moved or replaced")

    def _write_once(self, parent_fd: int, name: str, data: bytes) -> None:
        with _fs_errors():
            staging_fd = safe_fs.open_dir(self._run_fd, STAGING)
        stage = f"part-{self._store._random_token()}"
        try:
            with _fs_errors():
                safe_fs.write_new_file(staging_fd, stage, data)
            self._check_run_dir()
            _rename(staging_fd, stage, parent_fd, name)
            with _fs_errors():
                fd = safe_fs.open_file(parent_fd, name)
            try:
                os.fchmod(fd, 0o400)
            finally:
                os.close(fd)
            os.fsync(parent_fd)
            os.fsync(staging_fd)
        finally:
            os.close(staging_fd)
        self._check_run_dir()

    def _capture_environment(self) -> reproducibility.EnvironmentCapture | None:
        """An evidence_candidate start requires a verified, fingerprinted environment and is
        refused otherwise (never silently demoted). Other runs record a fingerprint when one
        can be computed, and none when it cannot."""
        evidence = self._requested is RunClass.EVIDENCE_CANDIDATE
        try:
            return capture_environment(self._store._repo_root, verify_conformance=evidence)
        except reproducibility.ReproducibilityError:
            if evidence:
                raise RunStateError(
                    "reproducibility verification failed; the evidence_candidate run was "
                    "not started"
                ) from None
            return None

    def _write_environment(self, document: bytes) -> None:
        # A start retried after a refusal must see the same environment.
        if safe_fs.exists(self._run_fd, ENVIRONMENT_NAME):
            with _fs_errors():
                existing = safe_fs.read_small(self._run_fd, ENVIRONMENT_NAME, len(document) + 1)
            if existing != document:
                raise RunStateError("an existing environment.json does not match; start refused")
            return
        self._write_once(self._run_fd, ENVIRONMENT_NAME, document)

    def _write_spec(self, spec_bytes: bytes) -> None:
        # A start refused after the spec was written may be retried with the identical spec.
        if safe_fs.exists(self._run_fd, SPEC_NAME):
            with _fs_errors():
                existing = safe_fs.read_small(self._run_fd, SPEC_NAME, len(spec_bytes) + 1)
            if existing != spec_bytes:
                raise RunStateError("an existing run_spec.json does not match; start refused")
            return
        self._write_once(self._run_fd, SPEC_NAME, spec_bytes)

    def _write_manifest(self, manifest: bytes) -> None:
        if safe_fs.exists(self._run_fd, MANIFEST_NAME):
            with _fs_errors():
                existing = safe_fs.read_small(self._run_fd, MANIFEST_NAME, len(manifest) + 1)
            if existing != manifest:
                raise RunStateError("an existing manifest.json does not match; completion refused")
            return
        self._write_once(self._run_fd, MANIFEST_NAME, manifest)

    def _verify_files(self, run: ledger.RunRecord) -> None:
        with _fs_errors():
            artifacts_fd = safe_fs.open_dir(self._run_fd, ARTIFACTS)
            staging_fd = safe_fs.open_dir(self._run_fd, STAGING)
        try:
            present = set(os.listdir(artifacts_fd))
            if present != set(run.artifacts):
                raise RunStateError("artifacts/ does not contain exactly the registered artifacts")
            for name, (item, _seq) in run.artifacts.items():
                _verify_artifact_file(artifacts_fd, name, item)
            if os.listdir(staging_fd):
                raise RunStateError("the staging directory is not empty")
        finally:
            os.close(artifacts_fd)
            os.close(staging_fd)

    def _finish(self, final: RunState) -> None:
        self._state = final
        try:
            _seal_run_directory(self._run_fd)
        finally:
            self.release()
