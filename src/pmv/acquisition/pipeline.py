"""Source-neutral acquisition orchestrator into the protected raw store (G-6; A-1 to A-8).

``AcquisitionPipeline.run`` takes one acquisition from proposal to storage:

    proposed -> approved_for_fetch -> received (quarantine, hashed on receipt)
      -> integrity_verified -> parser_verified (isolated worker)
      -> backup_verified (A-3) -> stored (protected raw store, A-7) -> completed

Each transition is appended to the hash-chained receipt journal, bound to the acquisition
and to the hash of every document that authorized it (``receipts.Binding``), and only along
the arrows of ``state``. The journal is the only state: a run that crashes at any point is
resumed by the next run from the last durable entry (``state.replay``).

**Before any transport,** every machine-checkable prerequisite is validated, and anything
absent, malformed, inconsistent, or unverifiable refuses the run:
- A-1: the approval, and every planned URL under its allowlist; formats, total size cap,
  no credential (credential isolation, F-03, is not built);
- A-2: the licence determination, with no ``unknown`` permission;
- A-3: a backup policy, a passing restore test covering every planned artifact type and
  size class, and a backup target bound to that policy;
- A-4: an A-4 review record with no BLOCKING or MAJOR finding, an adopted reader for every
  planned format, and a passing isolation self-test;
- A-5 and A-6: the plan's provenance fields and the source-quality entry;
- the mode rules below.

**Modes.** ``SYNTHETIC`` runs accept only records whose identifiers start with
``synthetic_``, only hosts under reserved test domains, only a synthetic transport and
backup target, and refuse a store root inside ``~/pmv-protected``. ``REAL`` runs refuse
synthetic records, require the store root inside the protected raw location, a clean
committed tool tree, every cited decision and review file committed unchanged, the F-09
commit and the reviewed commit as ancestors of ``HEAD`` with no acquisition-code change
since the review, an A-4 record that says A-4 is satisfied, and a reviewed production
transport. **No production transport exists, so a real run always refuses today.**

**Storage is not release (A-8).** The pipeline writes only under its store root. The
stored artifact is exactly the received bytes. Decompressed and extracted plaintext exists
only in the acquisition's scratch directory under the same root, for verification, and is
deleted afterwards. The report returned to the caller (``PipelineReport``) carries states,
closed codes, sizes, and hashes only, never a value from a file. No step makes a row
visible to an agent: that requires the governed H-2 per-row release, which does not exist.

**Recovery.** A file found in quarantine without a journaled receipt is moved aside, never
deleted, and recorded as ``discarded``. A rejected file is moved to ``rejected/``. A copy
found in the store at its target name is accepted only if its bytes match the receipt;
otherwise the run stops and nothing is replaced. An interrupted fetch is recorded as
failed and retried, at most once per run and ``max_attempts`` in total.
"""

import contextlib
import errno
import fcntl
import hashlib
import os
import shutil
import stat
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol
from urllib.parse import urlsplit

from pmv.acquisition import isolation, readers
from pmv.acquisition.archive import ArchiveRefusedError, ExtractionLimits, archive_kind_of
from pmv.acquisition.backup import backup_and_verify_restore
from pmv.acquisition.confinement import WorkerLimits
from pmv.acquisition.fetch import (
    Fetcher,
    FetchError,
    FetchPolicy,
    FetchRequest,
    Transport,
    statvfs_free,
)
from pmv.acquisition.formats import FileFormat
from pmv.acquisition.plan import (
    BUNDLE_KEYS,
    A4ReviewRecord,
    AcquisitionPlan,
    BackupPolicyRecord,
    FileKind,
    PlannedFile,
    RestoreTestRecord,
    bundle_sha256,
    document_sha256,
    is_synthetic,
    restore_tests_cover,
)
from pmv.acquisition.quarantine import _TMPFILE_FLAGS, _link_fd
from pmv.acquisition.receipts import (
    Binding,
    JournalEntry,
    ReceiptEvent,
    ReceiptJournal,
    ReceiptJournalError,
    new_session_id,
)
from pmv.acquisition.records import (
    AcquisitionApproval,
    LicenceRecord,
    RecordError,
    SourceQuality,
    acquisition_gate_failures,
)
from pmv.acquisition.state import ACQUISITION_NAME, AcquisitionState, FileState, StateError, replay
from pmv.config import protected_raw_root_problem
from pmv.data_access_guard import PROTECTED_ROOT
from pmv.integrity import FormatError, canonical_json, canonical_line, parse_canonical_json
from pmv.safe_fs import DIR_FLAGS, READ_FLAGS

LAYOUT_VERSION: Final = "v1"
RECORD_VERSION: Final = 1
RECORD_NAME: Final = "acquisition.json"
_CHUNK: Final = 1024 * 1024
_MAX_RECORD_BYTES: Final = 64 * 1024 * 1024
_RESERVED_SUFFIXES: Final = (".example", ".test", ".invalid")
_RESERVED_DOMAINS: Final = ("example.com", "example.net", "example.org")
_ACQUISITION_CODE: Final = "src/pmv/acquisition"
# Isolation failures caused by the environment, not by the input: never a rejection.
_ENVIRONMENTAL: Final = frozenset(
    {
        isolation.IsolationFailure.UNSUPPORTED_PLATFORM,
        isolation.IsolationFailure.SPAWN_FAILED,
        isolation.IsolationFailure.IDENTITY_MISMATCH,
        isolation.IsolationFailure.NOT_CONFINED,
        isolation.IsolationFailure.PROTOCOL_MISMATCH,
        isolation.IsolationFailure.PROBE_FAILED,
    }
)

FaultHook = Callable[[str], None]
WallClock = Callable[[], datetime]


class RunMode(StrEnum):
    SYNTHETIC = "synthetic"
    REAL = "real"


class Outcome(StrEnum):
    REFUSED = "refused"
    IN_PROGRESS = "in_progress"
    REJECTED = "rejected"
    COMPLETED = "completed"
    ALREADY_COMPLETED = "already_completed"


class PipelineError(Exception):
    """The run stopped. Every durable state is kept; a later run resumes or the owner acts."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _RejectedError(Exception):
    def __init__(self, stage: str, code: str) -> None:
        super().__init__(f"{stage}: {code}")
        self.stage = stage
        self.code = code


# --- collaborators ------------------------------------------------------------------------


class Repository(Protocol):
    """Read-only facts about the tool's Git checkout (used in real mode)."""

    def head(self) -> str | None: ...
    def tree_clean(self) -> bool: ...
    def committed_unchanged(self, path: str) -> bool: ...
    def is_ancestor(self, commit: str) -> bool: ...
    def unchanged_since(self, commit: str, path: str) -> bool: ...


class GitRepository:
    """``Repository`` backed by fixed, read-only ``git`` commands on one checkout."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _git(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(  # noqa: S603 - fixed read-only git commands, no shell
            ["git", "-C", str(self._root), *arguments],  # noqa: S607 - git from PATH
            capture_output=True,
            check=False,
            timeout=60,
        )

    def head(self) -> str | None:
        result = self._git("rev-parse", "--verify", "HEAD^{commit}")
        text = result.stdout.decode("ascii", errors="replace").strip()
        return text if result.returncode == 0 and len(text) == 40 else None

    def tree_clean(self) -> bool:
        result = self._git("status", "--porcelain", "--untracked-files=normal")
        return result.returncode == 0 and not result.stdout.strip()

    def committed_unchanged(self, path: str) -> bool:
        tracked = self._git("ls-files", "--error-unmatch", "--", path)
        unchanged = self._git("diff", "--quiet", "HEAD", "--", path)
        return tracked.returncode == 0 and unchanged.returncode == 0

    def is_ancestor(self, commit: str) -> bool:
        return self._git("merge-base", "--is-ancestor", commit, "HEAD").returncode == 0

    def unchanged_since(self, commit: str, path: str) -> bool:
        return self._git("diff", "--quiet", commit, "HEAD", "--", path).returncode == 0


@dataclass(frozen=True, slots=True)
class BackupItem:
    name: str
    path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BackupEvidence:
    """What a backup target reports. ``verified`` must be true for the A-3 step to pass."""

    policy_id: str
    verified: bool
    details: Mapping[str, object]

    def document(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "verified": self.verified,
            "details": dict(self.details),
        }


class BackupTarget(Protocol):
    """Backs up verified files and proves a restore by hash (A-3)."""

    policy_id: str
    synthetic: bool

    def backup_and_verify(
        self, acquisition_id: str, items: Sequence[BackupItem]
    ) -> BackupEvidence: ...


class DirectoryBackupTarget:
    """A synthetic backup target: copies into one directory, restores into another.

    Used only for synthetic runs. It proves the mechanism, never A-3 for real data: real
    A-3 evidence needs the owner's backup policy and a restore from the real medium.
    """

    synthetic = True

    def __init__(self, policy_id: str, backup_root: Path, restore_root: Path) -> None:
        if not is_synthetic(policy_id):
            raise ValueError("a directory backup target is synthetic only")
        self.policy_id = policy_id
        self._backup_root = backup_root
        self._restore_root = restore_root

    def _fresh(self, root: Path, acquisition_id: str) -> Path:
        base = root / acquisition_id
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        attempt = 0
        while (base / str(attempt)).exists():
            attempt += 1
        target = base / str(attempt)
        target.mkdir(mode=0o700)
        return target

    def backup_and_verify(self, acquisition_id: str, items: Sequence[BackupItem]) -> BackupEvidence:
        if len({item.path.parent for item in items}) != 1:
            raise PipelineError("backup items must share one source directory")
        source = items[0].path.parent
        backup_dir = self._fresh(self._backup_root, acquisition_id)
        restore_dir = self._fresh(self._restore_root, acquisition_id)
        report = backup_and_verify_restore(items, source, backup_dir, restore_dir)
        return BackupEvidence(
            policy_id=self.policy_id,
            verified=report.passed,
            details={
                "verified": sorted(report.verified),
                "mismatched": sorted(report.mismatched),
                "missing": sorted(report.missing),
                "unexpected": sorted(report.unexpected),
            },
        )


# --- inputs, settings, report -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PipelineInputs:
    """The authorizing documents, exactly as the owner recorded them. Absent means None."""

    plan: object = None
    approval: object = None
    licence: object = None
    quality: object = None
    backup_policy: object = None
    restore_tests: object = None
    a4_review: object = None

    def documents(self) -> dict[str, object]:
        return {key: getattr(self, key) for key in BUNDLE_KEYS}


@dataclass(frozen=True, slots=True)
class PipelineSettings:
    store_root: Path
    mode: RunMode
    worker_limits: WorkerLimits = field(default_factory=WorkerLimits)
    fetch_policy: FetchPolicy = field(default_factory=FetchPolicy)
    extraction_limits: ExtractionLimits = field(default_factory=ExtractionLimits)


@dataclass(frozen=True, slots=True)
class FileReport:
    name: str
    state: str
    code: str | None
    size_bytes: int | None
    sha256: str | None


@dataclass(frozen=True, slots=True)
class PipelineReport:
    """Agent-safe summary: identifiers, states, closed codes, sizes, and hashes only."""

    outcome: Outcome
    acquisition_id: str | None
    failures: tuple[str, ...] = ()
    files: tuple[FileReport, ...] = ()
    record_sha256: str | None = None

    def document(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "acquisition_id": self.acquisition_id,
            "failures": list(self.failures),
            "files": [
                {
                    "name": item.name,
                    "state": item.state,
                    "code": item.code,
                    "size_bytes": item.size_bytes,
                    "sha256": item.sha256,
                }
                for item in self.files
            ],
            "record_sha256": self.record_sha256,
        }


@dataclass(frozen=True, slots=True)
class _Prepared:
    plan: AcquisitionPlan
    approval: AcquisitionApproval
    licence: LicenceRecord
    quality: SourceQuality
    policy: BackupPolicyRecord
    tests: tuple[RestoreTestRecord, ...]
    review: A4ReviewRecord
    documents: Mapping[str, object]
    binding: Binding


# --- filesystem helpers -------------------------------------------------------------------


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, DIR_FLAGS)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _check_private_dir(path: Path) -> None:
    status = path.lstat()
    if not stat.S_ISDIR(status.st_mode):
        raise PipelineError("store_path_not_a_directory")
    if status.st_uid != os.geteuid() or status.st_mode & 0o022:
        raise PipelineError("store_path_not_private")


def _ensure_dir(base: Path, *parts: str) -> Path:
    """Create ``base/parts...`` one component at a time (0700), syncing each parent."""
    current = base
    _check_private_dir(current)
    for part in parts:
        target = current / part
        try:
            os.mkdir(target, 0o700)
        except FileExistsError:
            pass
        else:
            _fsync_dir(current)
        _check_private_dir(target)
        current = target
    return current


def _hash_fd(fd: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    offset = 0
    while chunk := os.pread(fd, _CHUNK, offset):
        digest.update(chunk)
        size += len(chunk)
        offset += len(chunk)
    return size, digest.hexdigest()


def _hash_path(path: Path) -> tuple[int, str] | None:
    try:
        fd = os.open(path, READ_FLAGS)
    except FileNotFoundError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise PipelineError("store_entry_not_a_regular_file")
        return _hash_fd(fd)
    finally:
        os.close(fd)


def _write_new(directory: Path, name: str, data: bytes) -> None:
    """Write ``data`` as a new read-only file through an unnamed inode; never overwrites."""
    dir_fd = os.open(directory, DIR_FLAGS)
    try:
        fd = os.open(".", _TMPFILE_FLAGS, 0o400, dir_fd=dir_fd)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view) :]
            os.fsync(fd)
            _link_fd(fd, dir_fd, name)
        finally:
            os.close(fd)
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _store_copy(source: Path, directory: Path, name: str, size: int, sha256: str) -> None:
    """Copy ``source`` into ``directory/name`` only if its bytes match; never overwrites."""
    in_fd = os.open(source, READ_FLAGS)
    try:
        if not stat.S_ISREG(os.fstat(in_fd).st_mode):
            raise PipelineError("quarantine_entry_not_a_regular_file")
        dir_fd = os.open(directory, DIR_FLAGS)
        try:
            out_fd = os.open(".", _TMPFILE_FLAGS, 0o400, dir_fd=dir_fd)
            try:
                digest = hashlib.sha256()
                copied = 0
                while chunk := os.read(in_fd, _CHUNK):
                    copied += len(chunk)
                    digest.update(chunk)
                    view = memoryview(chunk)
                    while view:
                        view = view[os.write(out_fd, view) :]
                if (copied, digest.hexdigest()) != (size, sha256):
                    raise PipelineError("quarantine_copy_changed")
                os.fsync(out_fd)
                _link_fd(out_fd, dir_fd, name)
                mine = os.fstat(out_fd)
            finally:
                os.close(out_fd)
            linked = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            if (linked.st_dev, linked.st_ino) != (mine.st_dev, mine.st_ino):
                raise PipelineError("store_name_replaced")
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        os.close(in_fd)


def _move_aside(source: Path, target_dir: Path, name: str) -> None:
    """Move a file to ``target_dir/name`` without replacing anything there."""
    target = target_dir / name
    if target.exists() or target.is_symlink():
        raise PipelineError("move_target_exists")
    os.link(source, target, follow_symlinks=False)
    os.unlink(source)
    _fsync_dir(target_dir)
    _fsync_dir(source.parent)


def _reserved_host(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host.endswith(_RESERVED_SUFFIXES) or any(
        host == domain or host.endswith("." + domain) for domain in _RESERVED_DOMAINS
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _detail(entry: JournalEntry) -> Mapping[str, object]:
    if entry.detail is None:
        raise PipelineError("journal_entry_has_no_detail")
    return entry.detail


def _evidence_name(item: PlannedFile, kind: str) -> str:
    """A bounded working-evidence file name derived from the planned file name."""
    return f"{hashlib.sha256(item.name.encode('utf-8')).hexdigest()[:32]}.{kind}.json"


# --- the pipeline -------------------------------------------------------------------------


class AcquisitionPipeline:
    """Runs one acquisition at a time under an exclusive lock on its store root."""

    def __init__(
        self,
        settings: PipelineSettings,
        *,
        transport: Transport,
        backup: BackupTarget,
        repository: Repository,
        production_transports: frozenset[type] = frozenset(),
        clock: WallClock = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        fetch_disk_free: Callable[[int], int] | None = None,
        faults: FaultHook | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._backup = backup
        self._repository = repository
        self._production_transports = production_transports
        self._clock = clock
        self._monotonic = monotonic
        self._fetch_disk_free = fetch_disk_free
        self._faults = faults or (lambda _point: None)
        self._base = settings.store_root / "acquisitions" / LAYOUT_VERSION

    # --- layout --------------------------------------------------------------------------

    def _root_failures(self) -> list[str]:
        root = self._settings.store_root
        try:
            status = root.lstat()
        except FileNotFoundError:
            return ["A-7: the store root does not exist"]
        if not stat.S_ISDIR(status.st_mode):
            return ["A-7: the store root is not a directory (or is a symlink)"]
        if status.st_uid != os.geteuid() or status.st_mode & 0o022:
            return ["A-7: the store root is not private to the acquisition user"]
        if self._settings.mode is RunMode.REAL:
            if protected_raw_root_problem(root) is not None:
                return ["A-7: a real store root must resolve inside the protected raw location"]
        elif protected_raw_root_problem(root, PROTECTED_ROOT) is None:
            return ["A-7: a synthetic run must not write inside ~/pmv-protected"]
        return []

    def _path(self, *parts: str) -> Path:
        return self._base.joinpath(*parts)

    def _ensure(self, *parts: str) -> Path:
        return _ensure_dir(self._settings.store_root, "acquisitions", LAYOUT_VERSION, *parts)

    # --- prerequisites -------------------------------------------------------------------

    def _parse(self, inputs: PipelineInputs, failures: list[str]) -> _Prepared | None:
        parsed: dict[str, object] = {}
        parsers: dict[str, tuple[str, Callable[[object], object]]] = {
            "plan": ("A-1/A-5", AcquisitionPlan.from_document),
            "approval": ("A-1", AcquisitionApproval.from_document),  # type: ignore[dict-item]
            "licence": ("A-2", LicenceRecord.from_document),  # type: ignore[dict-item]
            "quality": ("A-6", SourceQuality.from_document),  # type: ignore[dict-item]
            "backup_policy": ("A-3", BackupPolicyRecord.from_document),
            "a4_review": ("A-4", A4ReviewRecord.from_document),
        }
        for key, (gate, parser) in parsers.items():
            document = getattr(inputs, key)
            if document is None:
                failures.append(f"{gate}: no {key.replace('_', ' ')} record")
                continue
            try:
                parsed[key] = parser(document)
            except RecordError as error:
                failures.append(f"{gate}: {key.replace('_', ' ')} record is malformed ({error})")
        tests: list[RestoreTestRecord] = []
        if not isinstance(inputs.restore_tests, list) or not inputs.restore_tests:
            failures.append("A-3: no restore-test records")
        else:
            for document in inputs.restore_tests:
                try:
                    tests.append(RestoreTestRecord.from_document(document))
                except RecordError as error:
                    failures.append(f"A-3: restore-test record is malformed ({error})")
        if failures:
            return None
        plan = parsed["plan"]
        assert isinstance(plan, AcquisitionPlan)  # noqa: S101 - parsed above
        documents = inputs.documents()
        return _Prepared(
            plan=plan,
            approval=parsed["approval"],  # type: ignore[arg-type]
            licence=parsed["licence"],  # type: ignore[arg-type]
            quality=parsed["quality"],  # type: ignore[arg-type]
            policy=parsed["backup_policy"],  # type: ignore[arg-type]
            tests=tuple(tests),
            review=parsed["a4_review"],  # type: ignore[arg-type]
            documents=documents,
            binding=Binding(plan.acquisition_id, bundle_sha256(documents)),
        )

    def _cross_checks(self, prepared: _Prepared) -> list[str]:
        plan, approval, policy = prepared.plan, prepared.approval, prepared.policy
        failures: list[str] = []
        if plan.approval_id != approval.approval_id or plan.source_id != approval.source_id:
            failures.append("A-1: the plan does not match its approval")
        if approval.credential_required:
            failures.append("F-03: credentialed acquisition is not supported")
        uncovered = restore_tests_cover(plan.files, prepared.tests, policy.policy_id)
        review_ok = prepared.review.no_blocking_findings and prepared.review.no_major_findings
        failures.extend(
            acquisition_gate_failures(
                approval,
                prepared.licence,
                prepared.quality,
                backup_restore_test_passed=not uncovered,
                safe_parsing_review_passed=review_ok,
            )
        )
        if uncovered:
            failures.append("A-3: a planned artifact type or size class has no restore test")
        if self._backup.policy_id != policy.policy_id or self._backup.synthetic != policy.synthetic:
            failures.append("A-3: the backup target is not bound to the backup policy")
        formats: set[FileFormat] = set()
        for item in plan.files:
            formats |= item.formats()
            try:
                approval.allowlist.check(item.url)
            except Exception:  # noqa: BLE001 - any refusal is a failure
                failures.append("A-1: a planned URL is outside the approved hosts and prefixes")
        if not formats <= set(approval.formats):
            failures.append("A-1: the plan contains a format the approval does not list")
        for file_format in sorted(formats):
            if not readers.READERS[file_format].adopted:
                failures.append(f"A-4: no adopted reader for {file_format.value}")
        if sum(item.max_bytes for item in plan.files) > approval.expected_size_bytes:
            failures.append("A-1: the plan's size caps exceed the approved expected size")
        return failures

    def _synthetic_failures(self, prepared: _Prepared) -> list[str]:
        identifiers = [
            prepared.plan.acquisition_id,
            prepared.plan.approval_id,
            prepared.plan.source_id,
            prepared.licence.licence_id,
            prepared.quality.source_id,
            prepared.policy.policy_id,
            *(test.test_id for test in prepared.tests),
        ]
        failures: list[str] = []
        if not all(is_synthetic(identifier) for identifier in identifiers):
            failures.append("mode: a synthetic run accepts only synthetic_ records")
        if not all(_reserved_host(item.url) for item in prepared.plan.files):
            failures.append("mode: a synthetic run fetches only from reserved test domains")
        if getattr(self._transport, "synthetic", None) is not True:
            failures.append("mode: a synthetic run needs a synthetic transport")
        if not self._backup.synthetic:
            failures.append("mode: a synthetic run needs a synthetic backup target")
        return failures

    def _real_failures(self, prepared: _Prepared) -> list[str]:
        failures: list[str] = []
        identifiers = [
            prepared.plan.acquisition_id,
            prepared.plan.source_id,
            prepared.licence.licence_id,
            prepared.policy.policy_id,
        ]
        if any(is_synthetic(identifier) for identifier in identifiers) or prepared.policy.synthetic:
            failures.append("mode: a real run refuses synthetic records")
        if (
            getattr(self._transport, "synthetic", None) is not False
            or type(self._transport) not in self._production_transports
        ):
            failures.append("G-4: no reviewed production transport")
        if self._backup.synthetic:
            failures.append("A-3: a real run needs the owner's real backup target")
        if not prepared.review.a4_satisfied:
            failures.append("A-4: the A-4 record does not say A-4 is satisfied")
        repository = self._repository
        if repository.head() is None or not repository.tree_clean():
            failures.append("A-5: the acquisition tool must run from a clean, committed tree")
        cited = [
            prepared.plan.decision_record,
            prepared.approval.decision_record,
            prepared.licence.decision_record,
            prepared.quality.decision_record,
            prepared.policy.decision_record,
            prepared.review.decision_record,
            prepared.review.review_path,
            *(test.decision_record for test in prepared.tests),
        ]
        if not all(repository.committed_unchanged(path) for path in cited):
            failures.append("records: a cited decision or review file is not committed unchanged")
        if not repository.is_ancestor(prepared.approval.f09_settings_commit):
            failures.append("F-09: the approval's F-09 commit is not an ancestor of HEAD")
        commit = prepared.review.reviewed_commit
        if not repository.is_ancestor(commit) or not repository.unchanged_since(
            commit, _ACQUISITION_CODE
        ):
            failures.append("A-4: the acquisition code changed since its review")
        return failures

    def _prerequisites(self, inputs: PipelineInputs) -> tuple[_Prepared | None, list[str]]:
        failures: list[str] = []
        prepared = self._parse(inputs, failures)
        failures[:0] = self._root_failures()
        if prepared is None:
            return None, failures
        failures.extend(self._cross_checks(prepared))
        if self._settings.mode is RunMode.SYNTHETIC:
            failures.extend(self._synthetic_failures(prepared))
        else:
            failures.extend(self._real_failures(prepared))
        if not failures:
            try:
                isolation.verify_isolation(self._settings.worker_limits)
            except isolation.IsolationError as error:
                failures.append(f"G-1: the isolation self-test failed ({error.failure.value})")
        return (None if failures else prepared), failures

    # --- run -----------------------------------------------------------------------------

    def run(self, inputs: PipelineInputs) -> PipelineReport:
        """Run, or resume, one acquisition. Returns an agent-safe report."""
        prepared, failures = self._prerequisites(inputs)
        if prepared is None:
            plan = inputs.plan
            acquisition = plan.get("acquisition_id") if isinstance(plan, Mapping) else None
            return PipelineReport(
                outcome=Outcome.REFUSED,
                acquisition_id=acquisition if isinstance(acquisition, str) else None,
                failures=tuple(failures),
            )
        self._ensure()
        lock = os.open(
            self._path(".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600
        )
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PipelineError("another_run_holds_the_lock") from None
            return self._locked_run(prepared)
        finally:
            os.close(lock)

    def _journal(self) -> ReceiptJournal:
        path = self._path("journal.jsonl")
        if not path.exists():
            ReceiptJournal.create(path)
        return ReceiptJournal(path, clock=self._clock)

    def _locked_run(self, prepared: _Prepared) -> PipelineReport:
        journal = self._journal()
        try:
            plan = prepared.plan
            try:
                state = replay(
                    journal.entries, plan.acquisition_id, prepared.binding.plan_sha256, plan.names
                )
            except StateError:
                return PipelineReport(
                    outcome=Outcome.REFUSED,
                    acquisition_id=plan.acquisition_id,
                    failures=(
                        "G-6: the acquisition's journal conflicts with this plan or binding",
                    ),
                )
            run = _Run(self, prepared, journal, state)
            return run.execute()
        finally:
            journal.close()


class _Run:
    """One locked run of one acquisition."""

    def __init__(
        self,
        pipeline: AcquisitionPipeline,
        prepared: _Prepared,
        journal: ReceiptJournal,
        state: AcquisitionState,
    ) -> None:
        self.p = pipeline
        self.prepared = prepared
        self.plan = prepared.plan
        self.journal = journal
        self.state = state
        self.session = new_session_id()
        acquisition = self.plan.acquisition_id
        self.quarantine = pipeline._ensure("work", acquisition, "quarantine")
        self.scratch_parent = pipeline._ensure("work", acquisition)
        self.evidence = pipeline._ensure("work", acquisition, "evidence")
        self.codes: dict[str, str] = {}
        self.fetched: set[str] = set()

    # --- journal -------------------------------------------------------------------------

    def append(
        self,
        event: ReceiptEvent,
        name: str,
        size: int | None,
        sha256: str | None,
        detail: Mapping[str, object],
    ) -> JournalEntry:
        if event is not ReceiptEvent.COMPLETED:
            self.state.require(name, event)
        try:
            entry = self.journal.append_bound(
                event, self.prepared.binding, self.session, name, size, sha256, detail
            )
        except ReceiptJournalError:
            raise PipelineError("journal_append_failed") from None
        self.state.apply(entry)
        return entry

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.p._base))

    # --- execute -------------------------------------------------------------------------

    def execute(self) -> PipelineReport:
        if self.state.completed is not None:
            self.verify_completed()
            self.seal_store()
            self.cleanup_work()
            return self.report(Outcome.ALREADY_COMPLETED)
        self.clear_scratch()
        self.recover_quarantine()
        for item in self.plan.files:
            if self.state.rejected:
                break
            self.advance(item)
        if self.state.rejected:
            return self.report(Outcome.REJECTED)
        if not self.state.all_stored:
            return self.report(Outcome.IN_PROGRESS)
        self.p._faults("before_complete")
        self.complete()
        self.cleanup_work()
        return self.report(Outcome.COMPLETED)

    def report(self, outcome: Outcome) -> PipelineReport:
        files = []
        for item in self.plan.files:
            progress = self.state.files[item.name]
            received = progress.received
            files.append(
                FileReport(
                    name=item.name,
                    state=progress.state.value,
                    code=self.codes.get(item.name),
                    size_bytes=received.size_bytes if received else None,
                    sha256=received.sha256 if received else None,
                )
            )
        completed = self.state.completed
        return PipelineReport(
            outcome=outcome,
            acquisition_id=self.plan.acquisition_id,
            files=tuple(files),
            record_sha256=completed.sha256 if completed else None,
        )

    # --- recovery ------------------------------------------------------------------------

    def clear_scratch(self) -> None:
        """Remove derived plaintext a crashed run left behind (raw bytes are never here)."""
        scratch = self.scratch_parent / "scratch"
        if scratch.exists() or scratch.is_symlink():
            _check_private_dir(scratch)
            shutil.rmtree(scratch)
            _fsync_dir(self.scratch_parent)

    def recover_quarantine(self) -> None:
        for path in sorted(self.quarantine.iterdir()):
            progress = self.state.files.get(path.name)
            if progress is None or progress.state is FileState.NONE or path.is_symlink():
                raise PipelineError("unexpected_quarantine_entry")
            current = progress.state
            if current in (FileState.APPROVED, FileState.FETCH_FAILED):
                orphans = self.p._ensure("orphans", self.plan.acquisition_id)
                moved = f"{len(self.journal.entries)}.orphan"
                size_and_hash = _hash_path(path)
                assert size_and_hash is not None  # noqa: S101 - listed just above
                _move_aside(path, orphans, moved)
                self.append(
                    ReceiptEvent.DISCARDED,
                    path.name,
                    size_and_hash[0],
                    size_and_hash[1],
                    {"reason": "unjournaled_receipt", "moved_to": self.rel(orphans / moved)},
                )
            elif current is FileState.REJECTED:
                assert progress.last is not None  # noqa: S101 - a rejection has an entry
                moved_to = (progress.last.detail or {}).get("moved_to")
                if not isinstance(moved_to, str) or moved_to == "none":
                    raise PipelineError("unexpected_quarantine_entry")
                target = self.p._base / moved_to
                self.p._ensure(*target.parent.relative_to(self.p._base).parts)
                _move_aside(path, target.parent, target.name)
            elif current is FileState.STORED:
                self.finish_store_cleanup(self.plan.file(path.name))

    # --- per-file progress ---------------------------------------------------------------

    def advance(self, item: PlannedFile) -> None:
        progress = self.state.files[item.name]
        while True:
            current = progress.state
            try:
                if current in (FileState.NONE, FileState.FETCH_FAILED):
                    if not self.fetch(item):
                        return
                elif current is FileState.APPROVED:
                    attempt = progress.attempts
                    self.append(
                        ReceiptEvent.FETCH_FAILED,
                        item.name,
                        None,
                        None,
                        {"attempt": attempt, "code": "interrupted"},
                    )
                elif current is FileState.RECEIVED:
                    self.check_integrity(item)
                elif current is FileState.INTEGRITY_VERIFIED:
                    self.verify_parser(item)
                elif current is FileState.PARSER_VERIFIED:
                    self.back_up(item)
                elif current is FileState.BACKUP_VERIFIED:
                    self.store(item)
                else:
                    return
            except _RejectedError as rejected:
                self.reject(item, rejected.stage, rejected.code)
                return

    def fetch(self, item: PlannedFile) -> bool:
        """Make at most one fetch attempt per file per run. Return whether to continue."""
        progress = self.state.files[item.name]
        if progress.attempts >= self.plan.max_attempts:
            raise _RejectedError("fetch", "attempts_exhausted")
        if item.name in self.fetched:
            return False
        self.fetched.add(item.name)
        attempt = progress.attempts + 1
        self.append(
            ReceiptEvent.APPROVED_FOR_FETCH,
            item.name,
            None,
            None,
            {"attempt": attempt, "url": item.url},
        )
        self.p._faults("after_approved")
        fetcher = Fetcher(
            self.prepared.approval.allowlist,
            self.p._transport,
            policy=self.p._settings.fetch_policy,
            clock=self.p._monotonic,
            disk_free=self.p._fetch_disk_free or statvfs_free,
        )
        request = FetchRequest(
            url=item.url,
            name=item.name,
            max_bytes=item.max_bytes,
            expected_size=item.expected_size_bytes,
            expected_sha256=item.provider_sha256,
        )
        dir_fd = os.open(self.quarantine, DIR_FLAGS)
        try:
            fetched = fetcher.fetch(request, dir_fd)
        except FetchError as error:
            self.codes[item.name] = error.failure.value
            self.append(
                ReceiptEvent.FETCH_FAILED,
                item.name,
                None,
                None,
                {"attempt": attempt, "code": error.failure.value},
            )
            return False
        finally:
            os.close(dir_fd)
        self.p._faults("after_fetch_linked")
        self.append(
            ReceiptEvent.RECEIVED,
            item.name,
            fetched.size,
            fetched.sha256,
            {
                "attempt": attempt,
                "final_url": fetched.final_url,
                "redirects": len(fetched.redirects),
                "hash_source": fetched.hash_source,
            },
        )
        self.p._faults("after_received")
        return True

    def received(self, item: PlannedFile) -> JournalEntry:
        entry = self.state.files[item.name].received
        assert entry is not None  # noqa: S101 - the state machine guarantees a receipt
        return entry

    def check_integrity(self, item: PlannedFile) -> None:
        receipt = self.received(item)
        try:
            fd = os.open(self.quarantine / item.name, READ_FLAGS)
        except FileNotFoundError:
            raise _RejectedError("integrity", "missing_from_quarantine") from None
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise _RejectedError("integrity", "not_a_regular_file")
            size, digest = _hash_fd(fd)
            if (size, digest) != (receipt.size_bytes, receipt.sha256):
                raise _RejectedError("integrity", "changed_after_receipt")
            if item.provider_sha256 is not None and digest != item.provider_sha256:
                raise _RejectedError("integrity", "provider_hash_mismatch")
            head = os.pread(fd, 512, 0)
            tail = os.pread(fd, 4, max(size - 4, 0))
        finally:
            os.close(fd)
        if item.kind is FileKind.ARCHIVE:
            try:
                kind = archive_kind_of(head)
            except ArchiveRefusedError:
                raise _RejectedError("integrity", "signature") from None
            if kind != item.archive_kind:
                raise _RejectedError("integrity", "signature")
        else:
            assert item.file_format is not None  # noqa: S101 - set for single files
            try:
                readers.check_signature(item.name, item.file_format, item.compression, head, tail)
            except readers.SpecError:
                raise _RejectedError("integrity", "signature") from None
        self.append(
            ReceiptEvent.INTEGRITY_VERIFIED,
            item.name,
            receipt.size_bytes,
            receipt.sha256,
            {"kind": item.kind.value},
        )
        self.p._faults("after_integrity")

    def _isolated(self, call: Callable[[], dict[str, object]]) -> dict[str, object]:
        try:
            return call()
        except isolation.WorkerRefusedError as refused:
            raise _RejectedError("parser", refused.code.value) from None
        except ArchiveRefusedError:
            raise _RejectedError("parser", "archive_refused") from None
        except isolation.IsolationError as error:
            if error.failure in _ENVIRONMENTAL:
                raise PipelineError(f"isolation_{error.failure.value}") from None
            raise _RejectedError("parser", error.failure.value) from None

    def verify_parser(self, item: PlannedFile) -> None:
        receipt = self.received(item)
        assert receipt.size_bytes is not None  # noqa: S101 - a receipt has bytes
        assert receipt.sha256 is not None  # noqa: S101 - a receipt has bytes
        limits = self.p._settings.worker_limits
        path = self.quarantine / item.name
        if item.kind is FileKind.FILE:

            def single() -> dict[str, object]:
                fd = os.open(path, READ_FLAGS)
                try:
                    verification = isolation.verify_file(
                        fd,
                        item.spec(),
                        expected_size=receipt.size_bytes or 0,
                        expected_sha256=str(receipt.sha256),
                        limits=limits,
                    )
                finally:
                    os.close(fd)
                return {"kind": "file", "verification": verification.document()}

            document = self._isolated(single)
        else:
            document = self._isolated(lambda: self._verify_archive(item, path, receipt))
        data = canonical_line(document)
        self._replace_unjournaled(self.evidence, _evidence_name(item, "verification"), data)
        identity = isolation.expected_identity()
        self.append(
            ReceiptEvent.PARSER_VERIFIED,
            item.name,
            receipt.size_bytes,
            receipt.sha256,
            {
                "verification_sha256": hashlib.sha256(data).hexdigest(),
                "worker_identity_sha256": hashlib.sha256(canonical_json(identity)).hexdigest(),
            },
        )
        self.p._faults("after_parser")

    def _verify_archive(
        self, item: PlannedFile, path: Path, receipt: JournalEntry
    ) -> dict[str, object]:
        scratch = self.p._ensure("work", self.plan.acquisition_id, "scratch")
        target = _ensure_dir(scratch, "extract")
        try:
            extracted = isolation.isolated_extract(
                path,
                target,
                limits=self.p._settings.extraction_limits,
                worker_limits=self.p._settings.worker_limits,
                expected_sha256=receipt.sha256,
            )
            planned = {member.name: member for member in item.members}
            if {entry.name for entry in extracted} != set(planned):
                raise _RejectedError("parser", "archive_members_differ_from_plan")
            members = []
            for entry in sorted(extracted, key=lambda e: e.name):
                fd = os.open(target.joinpath(*entry.name.split("/")), READ_FLAGS)
                try:
                    verification = isolation.verify_file(
                        fd,
                        planned[entry.name].spec(),
                        expected_size=entry.size,
                        expected_sha256=entry.sha256,
                        limits=self.p._settings.worker_limits,
                    )
                finally:
                    os.close(fd)
                members.append(
                    {
                        "name": entry.name,
                        "size_bytes": entry.size,
                        "sha256": entry.sha256,
                        "verification": verification.document(),
                    }
                )
            return {"kind": "archive", "archive_kind": item.archive_kind, "members": members}
        finally:
            self.clear_scratch()

    def _replace_unjournaled(self, directory: Path, name: str, data: bytes) -> None:
        """Write a working evidence file; one left by a crash before its journal entry goes."""
        with contextlib.suppress(FileNotFoundError):
            os.unlink(directory / name)
        _write_new(directory, name, data)

    def _evidence(self, name: str, expected_sha256: str) -> dict[str, object]:
        path = self.evidence / name
        found = _hash_path(path)
        if found is None or found[1] != expected_sha256:
            raise PipelineError("evidence_missing_or_changed")
        data = path.read_bytes()
        try:
            return parse_canonical_json(data[:-1]) if data.endswith(b"\n") else {}
        except FormatError:
            raise PipelineError("evidence_malformed") from None

    def back_up(self, item: PlannedFile) -> None:
        receipt = self.received(item)
        assert receipt.size_bytes is not None  # noqa: S101 - a receipt has bytes
        assert receipt.sha256 is not None  # noqa: S101 - a receipt has bytes
        evidence = self.p._backup.backup_and_verify(
            self.plan.acquisition_id,
            [
                BackupItem(
                    item.name, self.quarantine / item.name, receipt.size_bytes, receipt.sha256
                )
            ],
        )
        if evidence.policy_id != self.prepared.policy.policy_id or not evidence.verified:
            raise PipelineError("backup_not_verified")
        data = canonical_line(evidence.document())
        self._replace_unjournaled(self.evidence, _evidence_name(item, "backup"), data)
        self.append(
            ReceiptEvent.BACKUP_VERIFIED,
            item.name,
            receipt.size_bytes,
            receipt.sha256,
            {"policy_id": evidence.policy_id, "evidence_sha256": hashlib.sha256(data).hexdigest()},
        )
        self.p._faults("after_backup")

    def store_dir(self) -> Path:
        return self.p._ensure("store", self.plan.source_id, self.plan.acquisition_id)

    def store(self, item: PlannedFile) -> None:
        receipt = self.received(item)
        assert receipt.size_bytes is not None  # noqa: S101 - a receipt has bytes
        assert receipt.sha256 is not None  # noqa: S101 - a receipt has bytes
        directory = self.store_dir()
        existing = _hash_path(directory / item.name)
        recovered = False
        if existing is not None:
            if existing != (receipt.size_bytes, receipt.sha256):
                raise PipelineError("store_conflict_never_replaced")
            recovered = True
        else:
            try:
                _store_copy(
                    self.quarantine / item.name,
                    directory,
                    item.name,
                    receipt.size_bytes,
                    receipt.sha256,
                )
            except FileExistsError:
                raise PipelineError("store_conflict_never_replaced") from None
            except OSError as error:
                code = "store_disk_full" if error.errno == errno.ENOSPC else "store_write_failed"
                raise PipelineError(code) from None
        self.p._faults("after_store_link")
        self.append(
            ReceiptEvent.STORED,
            item.name,
            receipt.size_bytes,
            receipt.sha256,
            {"path": self.rel(directory / item.name), "recovered": recovered},
        )
        self.p._faults("after_stored")
        self.finish_store_cleanup(item)

    def finish_store_cleanup(self, item: PlannedFile) -> None:
        """Remove the quarantine copy once the stored copy is verified."""
        receipt = self.received(item)
        stored = _hash_path(self.store_dir() / item.name)
        if stored != (receipt.size_bytes, receipt.sha256):
            raise PipelineError("stored_copy_missing_or_changed")
        with contextlib.suppress(FileNotFoundError):
            os.unlink(self.quarantine / item.name)
            _fsync_dir(self.quarantine)

    def reject(self, item: PlannedFile, stage: str, code: str) -> None:
        self.codes[item.name] = code
        rejected_dir = self.p._path("rejected", self.plan.acquisition_id)
        moved_name = f"{len(self.journal.entries)}.rejected"
        present = (self.quarantine / item.name).exists()
        moved_to = self.rel(rejected_dir / moved_name) if present else "none"
        self.append(
            ReceiptEvent.REJECTED,
            item.name,
            None,
            None,
            {"stage": stage, "code": code, "moved_to": moved_to},
        )
        if present:
            self.p._ensure("rejected", self.plan.acquisition_id)
            _move_aside(self.quarantine / item.name, rejected_dir, moved_name)

    # --- completion ----------------------------------------------------------------------

    def record(self) -> bytes:
        prepared = self.prepared
        files = []
        for item in self.plan.files:
            progress = self.state.files[item.name]
            received = self.received(item)
            by_event = {entry.event: entry for entry in progress.entries}
            parser = by_event[ReceiptEvent.PARSER_VERIFIED]
            backup = by_event[ReceiptEvent.BACKUP_VERIFIED]
            stored = by_event[ReceiptEvent.STORED]
            verification = self._evidence(
                _evidence_name(item, "verification"), str(_detail(parser)["verification_sha256"])
            )
            backup_evidence = self._evidence(
                _evidence_name(item, "backup"), str(_detail(backup)["evidence_sha256"])
            )
            files.append(
                {
                    "name": item.name,
                    "url": item.url,
                    "final_url": _detail(received)["final_url"],
                    "redirects": _detail(received)["redirects"],
                    "kind": item.kind.value,
                    "artifact_type": item.artifact_type,
                    "size_bytes": received.size_bytes,
                    "sha256": received.sha256,
                    "hash_source": _detail(received)["hash_source"],
                    "provider_sha256": item.provider_sha256,
                    "retrieved_at": received.recorded_at,
                    "verification": verification,
                    "verification_sha256": _detail(parser)["verification_sha256"],
                    "backup_evidence": backup_evidence,
                    "stored_path": _detail(stored)["path"],
                }
            )
        repository = self.p._repository
        head = repository.head()
        record = {
            "record_version": RECORD_VERSION,
            "acquisition_id": self.plan.acquisition_id,
            "approval_id": self.plan.approval_id,
            "source_id": self.plan.source_id,
            "licence_id": prepared.licence.licence_id,
            "input_licence_ids": [prepared.licence.licence_id],
            "binding_sha256": prepared.binding.plan_sha256,
            "documents": {key: document_sha256(prepared.documents[key]) for key in BUNDLE_KEYS},
            "mode": self.p._settings.mode.value,
            "upstream_identity": self.plan.upstream_identity,
            "is_primary_source": self.plan.is_primary_source,
            "mirror_lineage": list(self.plan.mirror_lineage),
            "vendor_version": self.plan.vendor_version,
            "reproducible_from_provider": self.plan.reproducible_from_provider.value,
            "tool": {
                "git_commit": head,
                "tree_clean": repository.tree_clean() if head is not None else None,
                "worker_identity_sha256": hashlib.sha256(
                    canonical_json(isolation.expected_identity())
                ).hexdigest(),
            },
            "files": files,
        }
        return canonical_line(record)

    def complete(self) -> None:
        directory = self.store_dir()
        data = self.record()
        if len(data) > _MAX_RECORD_BYTES:
            raise PipelineError("record_too_large")
        existing = directory / RECORD_NAME
        if existing.exists() or existing.is_symlink():
            if _hash_path(existing) != (len(data), hashlib.sha256(data).hexdigest()):
                raise PipelineError("record_conflict_never_replaced")
        else:
            _write_new(directory, RECORD_NAME, data)
        self.p._faults("after_record")
        self.append(
            ReceiptEvent.COMPLETED,
            ACQUISITION_NAME,
            len(data),
            hashlib.sha256(data).hexdigest(),
            {"record_path": self.rel(existing), "files": len(self.plan.files)},
        )
        self.seal_store()

    def seal_store(self) -> None:
        """Make the completed acquisition's store directory read-only (idempotent)."""
        directory = self.p._path("store", self.plan.source_id, self.plan.acquisition_id)
        if stat.S_IMODE(directory.lstat().st_mode) != 0o500:
            os.chmod(directory, 0o500)
            _fsync_dir(directory.parent)

    def verify_completed(self) -> None:
        completed = self.state.completed
        assert completed is not None  # noqa: S101 - checked by execute()
        assert completed.detail is not None  # noqa: S101 - every v2 entry has detail
        record = self.p._base / str(completed.detail["record_path"])
        if _hash_path(record) != (completed.size_bytes, completed.sha256):
            raise PipelineError("record_missing_or_changed")
        for item in self.plan.files:
            receipt = self.received(item)
            directory = self.p._path("store", self.plan.source_id, self.plan.acquisition_id)
            if _hash_path(directory / item.name) != (receipt.size_bytes, receipt.sha256):
                raise PipelineError("stored_copy_missing_or_changed")

    def cleanup_work(self) -> None:
        """Delete the acquisition's working area once it is completed. Raw bytes are stored."""
        work = self.p._path("work", self.plan.acquisition_id)
        if not work.exists():
            return
        quarantine = work / "quarantine"
        if quarantine.exists() and any(quarantine.iterdir()):
            for path in quarantine.iterdir():
                self.finish_store_cleanup(self.plan.file(path.name))
        shutil.rmtree(work)
        _fsync_dir(work.parent)
