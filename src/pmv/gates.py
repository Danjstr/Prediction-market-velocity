"""Gate-record tooling: create, verify, list, and verify the Git-anchored history.

Records live at ``docs/decisions/gates/<gate_id>_<record_id>.md`` (see pmv.gate_record).
Creating a record does not publish a project decision: the tool leaves the new file
untracked and never stages, commits, or pushes. A decision becomes part of durable project
history only when the project owner reviews and commits it. Git is the external historical
anchor (it is not cryptographic notarization): ``verify_gate_history`` fails if any record
that was ever committed has been modified, deleted, or replaced.

Creation binds the record to one repository state. The project identity (commit, dirty
state and fingerprint, governance and config hashes) is captured before ``check.sh`` runs,
captured again afterwards, and once more immediately before the file is written; any
difference refuses the record. Experiment evidence is evaluated only at the pinned
experiment-ledger head. Protected-holdout evidence is always rejected in v1.

Usage: ``python -m pmv.gates {verify-history,verify,list,create} ...``
"""

import argparse
import contextlib
import errno
import fcntl
import json
import os
import secrets
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pmv import experiment_ledger as ledger
from pmv import safe_fs
from pmv.config import ConfigError, Environment, load_config
from pmv.experiments import (
    ExperimentError,
    ExperimentStore,
    collect_git_identity,
)
from pmv.gate_record import (
    GATES_DIR,
    GOVERNANCE_PATHS,
    ApprovalRequirement,
    CheckId,
    CheckOutcome,
    Decision,
    DocumentKind,
    FindingSeverity,
    FindingStatus,
    GateId,
    GateRecord,
    GateRecordError,
    Independence,
    LineageKey,
    LineageMember,
    ReviewConclusion,
    ReviewerRole,
    RunRole,
    RunStateAtPin,
    canonicalize,
    is_document_path,
    parse_file_name,
    parse_record_file,
    record_file_name,
    render_record,
    validate_record,
    verify_lineages,
)
from pmv.integrity import format_timestamp, sha256_hex, to_utc
from pmv.log import fields, get_logger
from pmv.raw_storage import RawCaptureStore, RawStorageError, collect_runtime_provenance

_log = get_logger("pmv.gates")

MAX_FILE_BYTES: Final = 16_777_216
CHECK_TIMEOUT_SECONDS: Final = 7200
_GIT_ENV: Final = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LC_ALL": "C",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    # Local replace refs must never alter the history being verified.
    "GIT_NO_REPLACE_OBJECTS": "1",
}


class GateError(Exception):
    """A gate record cannot be created or verified. Messages never echo content."""


class GateIntegrityError(GateError):
    """Gate records, their Git history, or the repository layout fail verification."""


class GateStateError(GateError):
    """The repository state does not permit this record (for example it changed)."""


class GateEvidenceError(GateError):
    """Referenced evidence does not exist or does not match at the pinned state."""


# ----- request -----


@dataclass(frozen=True, slots=True)
class DocumentEvidence:
    path: str
    sha256: str
    kind: DocumentKind

    def to_json(self) -> dict[str, object]:
        return {"kind": DocumentKind(self.kind).value, "path": self.path, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class Finding:
    finding_id: str
    severity: FindingSeverity
    status: FindingStatus
    document: DocumentEvidence | None = None


@dataclass(frozen=True, slots=True)
class Review:
    role: ReviewerRole
    conclusion: ReviewConclusion
    independence: Independence
    document: DocumentEvidence | None = None


@dataclass(frozen=True, slots=True)
class RunEvidence:
    run_id: str
    role: RunRole


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    run_id: str
    artifact_name: str
    sha256: str


@dataclass(frozen=True, slots=True)
class CaptureEvidence:
    capture_id: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class LedgerPin:
    ledger_seq: int
    entry_sha256: str


@dataclass(frozen=True, slots=True)
class Supersedes:
    record_id: str
    record_sha256: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GateRequest:
    """What the operator asks to record. Everything else is computed and verified."""

    gate_id: GateId
    decision: Decision
    approval_attested: bool
    reasons: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    reviews: tuple[Review, ...] = ()
    cycle_id: str | None = None
    candidate_id: str | None = None
    ledger_pin: LedgerPin | None = None
    runs: tuple[RunEvidence, ...] = ()
    artifacts: tuple[ArtifactEvidence, ...] = ()
    raw_captures: tuple[CaptureEvidence, ...] = ()
    documents: tuple[DocumentEvidence, ...] = ()
    holdout: tuple[object, ...] = field(default=())
    run_check_sh: bool = True
    supersedes: Supersedes | None = None


@dataclass(frozen=True, slots=True)
class CreatedRecord:
    path: Path
    record_id: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ScannedRecord:
    name: str
    record: GateRecord
    sha256: str
    committed: bool


# ----- project identity -----


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    commit: str
    tree_dirty: bool
    dirty_tree_sha256: str | None
    governance: tuple[tuple[str, str], ...]
    configs: tuple[tuple[str, str], ...]

    def to_json(self) -> dict[str, object]:
        return {
            "commit": self.commit,
            "configs": [{"path": path, "sha256": digest} for path, digest in self.configs],
            "dirty_tree_sha256": self.dirty_tree_sha256,
            "governance": [
                {"kind": DocumentKind.GOVERNANCE.value, "path": path, "sha256": digest}
                for path, digest in self.governance
            ],
            "tree_dirty": self.tree_dirty,
        }


def capture_project_identity(repo: Path) -> ProjectIdentity:
    """The repository state a record binds to.

    Clean means clean apart from untracked, valid gate-record files in the gate directory.
    Otherwise the tree is dirty and the Step 6 dirty-tree fingerprint identifies it (that
    fingerprint covers the whole working tree, including other untracked gate records).
    """
    identity = collect_git_identity(repo)
    if identity.commit is None or identity.dirty is None:
        raise GateStateError("the repository's code identity cannot be determined")
    dirty = identity.dirty and not _only_new_gate_records(repo)
    governance = tuple((path, sha256_hex(_read_repo_file(repo, path))) for path in GOVERNANCE_PATHS)
    configs = tuple(
        (f"configs/{name}", sha256_hex(_read_repo_file(repo, f"configs/{name}")))
        for name in _config_names(repo)
    )
    return ProjectIdentity(
        commit=identity.commit,
        tree_dirty=dirty,
        dirty_tree_sha256=identity.dirty_sha256 if dirty else None,
        governance=governance,
        configs=configs,
    )


def _only_new_gate_records(repo: Path) -> bool:
    status = _git(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=none",
        "--no-renames",
    )
    flags = _git(repo, "ls-files", "-v", "-z")
    if any(entry[:1].islower() or entry[:1] == b"S" for entry in flags.split(b"\0") if entry):
        return False
    for entry in (item for item in status.split(b"\0") if item):
        code, path = entry[:2], entry[3:].decode("utf-8", errors="replace")
        directory, _, name = path.rpartition("/")
        if code != b"??" or directory != GATES_DIR or parse_file_name(name) is None:
            return False
        try:
            parse_record_file(_read_repo_file(repo, path), name)
        except GateRecordError:
            return False
    return True


def _config_names(repo: Path) -> list[str]:
    with _repo_dir(repo, ("configs",)) as fd:
        if fd is None:
            return []
        return sorted(name for name in os.listdir(fd) if name.endswith(".toml"))


# ----- creation -----


def run_check_sh(repo: Path) -> bool:
    """Run ./scripts/check.sh; return whether it passed. Its output is discarded."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed project script, no shell
            [str(repo / "scripts" / "check.sh")],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise GateStateError("check.sh did not finish within its time limit") from None
    return completed.returncode == 0


def create_gate_record(
    repo: Path,
    request: GateRequest,
    *,
    experiment_store: ExperimentStore | None = None,
    raw_store: RawCaptureStore | None = None,
    check_runner: Callable[[Path], bool] = run_check_sh,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    random_token: Callable[[], str] = lambda: secrets.token_hex(16),
    fault_hook: Callable[[str], None] | None = None,
) -> CreatedRecord:
    """Verify everything, then write one new record without replacing anything.

    Never stages or commits. The returned path is untracked until the owner commits it.
    """
    repo = Path(os.path.realpath(repo))
    if request.holdout:
        raise GateEvidenceError(
            "protected-holdout evidence requires holdout-access linkage, which does not exist "
            "yet; Step 7 v1 rejects every protected-holdout evidence reference"
        )
    before = capture_project_identity(repo)
    if request.decision is Decision.PASS and before.tree_dirty:
        raise GateStateError("a pass record requires a clean project tree")
    checks: list[dict[str, object]] = []
    if request.run_check_sh:
        passed = check_runner(repo)
        if fault_hook is not None:
            fault_hook("check.finished")
        if capture_project_identity(repo) != before:
            raise GateStateError("the repository changed while check.sh ran; rerun the gate tool")
        outcome = CheckOutcome.PASSED if passed else CheckOutcome.FAILED
        checks.append({"check_id": CheckId.CHECK_SH.value, "outcome": outcome.value})
    pin, runs, artifacts = _experiment_evidence(request, experiment_store)
    captures = _capture_evidence(request.raw_captures, raw_store)
    documents = [
        *request.documents,
        *(item.document for item in request.findings if item.document is not None),
        *(item.document for item in request.reviews if item.document is not None),
    ]
    for document in documents:
        _verify_document(repo, document)
    with _locked_gates_dir(repo) as gates_fd:
        _check_lineage(repo, request)
        moment = to_utc(clock())
        token = random_token()
        record_id = f"{moment:%Y%m%dT%H%M%S.%f}Z_{token}"
        if request.supersedes is not None and record_id <= request.supersedes.record_id:
            raise GateStateError("a successor must be recorded after the record it supersedes")
        document_json = canonicalize(
            {
                "decided_at": format_timestamp(moment),
                "decision": Decision(request.decision).value,
                "evidence": {
                    "artifacts": artifacts,
                    "checks": checks,
                    "documents": [item.to_json() for item in request.documents],
                    "holdout": [],
                    "raw_captures": captures,
                    "runs": runs,
                },
                "experiment_ledger": pin,
                "final_decision": {
                    "approval_attested": request.approval_attested,
                    "approval_requirement": ApprovalRequirement.REQUIRED.value,
                    "role": "project_owner",
                },
                "findings": [
                    {
                        "document": None if item.document is None else item.document.to_json(),
                        "finding_id": item.finding_id,
                        "severity": FindingSeverity(item.severity).value,
                        "status": FindingStatus(item.status).value,
                    }
                    for item in request.findings
                ],
                "gate_id": GateId(request.gate_id).value,
                "project": before.to_json(),
                "reasons": list(request.reasons),
                "record_id": record_id,
                "reviews": [
                    {
                        "conclusion": ReviewConclusion(item.conclusion).value,
                        "document": None if item.document is None else item.document.to_json(),
                        "independence": Independence(item.independence).value,
                        "role": ReviewerRole(item.role).value,
                    }
                    for item in request.reviews
                ],
                "schema": "pmv.gate_record",
                "schema_version": 1,
                "scope": {"candidate_id": request.candidate_id, "cycle_id": request.cycle_id},
                "supersedes": None
                if request.supersedes is None
                else {
                    "record_id": request.supersedes.record_id,
                    "record_sha256": request.supersedes.record_sha256,
                },
            }
        )
        record = validate_record(document_json)
        data = render_record(record)
        if fault_hook is not None:
            fault_hook("before_publish")
        if capture_project_identity(repo) != before:
            raise GateStateError("the repository changed before the record was written; rerun")
        name = record_file_name(record.gate_id, record.record_id)
        _write_no_replace(gates_fd, name, data, token)
    digest = sha256_hex(data)
    _log.info(
        "gates.record_created",
        extra=fields(gate_id=record.gate_id, record_id=record.record_id, sha256=digest),
    )
    return CreatedRecord(repo / GATES_DIR / name, record.record_id, digest)


def _experiment_evidence(
    request: GateRequest, store: ExperimentStore | None
) -> tuple[dict[str, object] | None, list[dict[str, object]], list[dict[str, object]]]:
    if request.ledger_pin is None:
        if request.runs or request.artifacts:
            raise GateEvidenceError("run and artifact evidence requires a pinned experiment ledger")
        return None, [], []
    if store is None:
        raise GateEvidenceError("a pinned experiment ledger needs the experiment store")
    try:
        state = store.snapshot()
    except ExperimentError as exc:
        raise GateEvidenceError(f"the experiment ledger did not verify: {exc}") from None
    seq = request.ledger_pin.ledger_seq
    if type(seq) is not int or not 0 <= seq <= state.head_seq:
        raise GateEvidenceError("the pinned ledger_seq is not in the verified ledger")
    if state.entries[seq].sha256 != request.ledger_pin.entry_sha256:
        raise GateEvidenceError("the pinned entry_sha256 does not match the ledger at that seq")
    checkpoint: dict[str, object] | None = None
    for status in store.checkpoint_status():
        if status.checkpoint.ledger_seq <= seq:
            checkpoint = {
                "committed_in_git": status.committed_in_git,
                "entry_sha256": status.checkpoint.entry_sha256,
                "ledger_seq": status.checkpoint.ledger_seq,
            }
    pin: dict[str, object] = {
        "checkpoint": checkpoint,
        "entry_sha256": request.ledger_pin.entry_sha256,
        "ledger_seq": seq,
        "store_id": ledger.store_id_of(state),
    }
    runs: list[dict[str, object]] = []
    for reference in request.runs:
        run = state.runs.get(reference.run_id)
        if run is None or run.reserved_seq > seq:
            raise GateEvidenceError("a referenced run is not in the ledger at the pinned head")
        if run.terminal_seq is None or run.terminal_seq > seq:
            raise GateEvidenceError("a referenced run is not terminal at the pinned head")
        runs.append(
            {
                "eligible_at_pin": ledger.eligibility_as_of(state, reference.run_id, seq),
                "role": RunRole(reference.role).value,
                "run_id": reference.run_id,
                "state_at_pin": RunStateAtPin(run.state.value).value,
            }
        )
    artifacts: list[dict[str, object]] = []
    for item in request.artifacts:
        run = state.runs.get(item.run_id)
        if run is None or run.completed_seq is None or run.completed_seq > seq:
            raise GateEvidenceError("an artifact's run is not completed at the pinned head")
        registered = run.artifacts.get(item.artifact_name)
        if registered is None or registered[1] > seq or registered[0]["sha256"] != item.sha256:
            raise GateEvidenceError("an artifact reference does not match the pinned ledger")
        artifacts.append(
            {"artifact_name": item.artifact_name, "run_id": item.run_id, "sha256": item.sha256}
        )
    _verify_run_files(
        store, state, [item.run_id for item in request.runs] + [a.run_id for a in request.artifacts]
    )
    return pin, runs, artifacts


def _verify_run_files(
    store: ExperimentStore, state: ledger.LedgerState, run_ids: Sequence[str]
) -> None:
    """The ledger alone is not evidence: every referenced run, and every run that produced
    one of its run-artifact inputs (transitively), must pass the store's own ``verify_run``
    (spec, environment.json, artifacts, manifest) or the record is refused (Step 11 F-13)."""
    pending, seen = list(run_ids), set[str]()
    while pending:
        run_id = pending.pop()
        if run_id in seen:
            continue
        seen.add(run_id)
        try:
            store.verify_run(run_id)
        except (ExperimentError, OSError):
            raise GateEvidenceError(
                "a referenced run, or a run that produced its inputs, failed verification"
            ) from None
        run = state.runs.get(run_id)
        for item in run.inputs if run is not None else ():
            if item.get("kind") == "run_artifact":
                pending.append(str(item["run_id"]))


def _capture_evidence(
    references: Sequence[CaptureEvidence], raw_store: RawCaptureStore | None
) -> list[dict[str, object]]:
    if not references:
        return []
    if raw_store is None:
        raise GateEvidenceError("raw capture evidence needs the raw capture store")
    captures: list[dict[str, object]] = []
    for reference in references:
        try:
            verified = raw_store.verify_capture(reference.capture_id)
        except (RawStorageError, ValueError, OSError):
            raise GateEvidenceError("a raw capture failed verification") from None
        if verified.manifest_sha256 != reference.manifest_sha256:
            raise GateEvidenceError("a raw capture manifest hash does not match")
        captures.append(
            {"capture_id": reference.capture_id, "manifest_sha256": reference.manifest_sha256}
        )
    return captures


def _verify_document(repo: Path, document: DocumentEvidence) -> None:
    """The document must be tracked at HEAD with exactly the referenced bytes."""
    if DocumentKind(document.kind) is DocumentKind.HOLDOUT_EVALUATION:
        raise GateEvidenceError(
            "protected-holdout evidence requires holdout-access linkage, which does not exist "
            "yet; Step 7 v1 rejects every protected-holdout evidence reference"
        )
    if not is_document_path(document.path):
        raise GateEvidenceError("a document path is not an allowed repository document")
    committed = _head_blob(repo, document.path)
    if committed is None or not _git(repo, "ls-files", "-z", "--", document.path):
        raise GateEvidenceError("a referenced document is not tracked at HEAD")
    working = _read_repo_file(repo, document.path)
    if working != committed or sha256_hex(working) != document.sha256:
        raise GateEvidenceError("a referenced document does not match its committed bytes")


def _check_lineage(repo: Path, request: GateRequest) -> None:
    """A new root needs an empty lineage; a successor needs the committed lineage head."""
    records = verify_gate_history(repo)
    key = LineageKey(GateId(request.gate_id).value, request.cycle_id, request.candidate_id)
    members = [item for item in records if item.record.lineage == key]
    if request.supersedes is None:
        if members:
            raise GateStateError("this gate lineage already has a record; supersede its head")
        return
    heads = verify_lineages(
        [LineageMember(item.record, item.sha256, item.committed) for item in records]
    )
    head = heads.get(key)
    prior = request.supersedes
    if head is None or head.record.record_id != prior.record_id:
        raise GateStateError("a successor must supersede the current head of its lineage")
    if head.sha256 != prior.record_sha256:
        raise GateStateError("the superseded record does not match the named SHA-256")
    if not head.committed:
        raise GateStateError("the superseded record must be committed at HEAD first")


def _write_no_replace(gates_fd: int, name: str, data: bytes, token: str) -> None:
    stage = f".tmp-{token}"
    try:
        with _fs_errors():
            safe_fs.write_new_file(gates_fd, stage, data)
            fd = safe_fs.open_file(gates_fd, stage)
        try:
            os.fchmod(fd, 0o444)
            os.fsync(fd)
        finally:
            os.close(fd)
        with _fs_errors():
            safe_fs.rename_noreplace(gates_fd, stage, gates_fd, name, renameat2=safe_fs.RENAMEAT2)
    except FileExistsError:
        raise GateIntegrityError("a gate record with that name already exists") from None
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(stage, dir_fd=gates_fd)
    os.fsync(gates_fd)
    with _fs_errors():
        written = safe_fs.read_small(gates_fd, name, MAX_FILE_BYTES)
    if written != data:
        raise GateIntegrityError("the written gate record did not read back exactly")
    parse_record_file(written, name)


# ----- verification -----


def verify_gate_record(path: Path) -> GateRecord:
    """Verify one record file offline: name, schema, semantics, and exact rendering."""
    parent = Path(os.path.realpath(path.parent))
    fd = os.open(parent, safe_fs.DIR_FLAGS)
    try:
        with _fs_errors():
            data = safe_fs.read_small(fd, path.name, MAX_FILE_BYTES)
    finally:
        os.close(fd)
    return parse_record_file(data, path.name)


def list_gate_records(repo: Path) -> list[ScannedRecord]:
    """Every record in the gate directory, verified, with whether HEAD holds it unchanged."""
    repo = Path(os.path.realpath(repo))
    scanned: list[ScannedRecord] = []
    with _repo_dir(repo, tuple(GATES_DIR.split("/"))) as fd:
        if fd is None:
            return []
        for name in sorted(os.listdir(fd)):
            if parse_file_name(name) is None:
                raise GateIntegrityError("the gate directory holds a file that is not a record")
            with _fs_errors():
                data = safe_fs.read_small(fd, name, MAX_FILE_BYTES)
            record = parse_record_file(data, name)
            committed = _head_blob(repo, f"{GATES_DIR}/{name}") == data
            scanned.append(ScannedRecord(name, record, sha256_hex(data), committed))
    return scanned


def verify_gate_history(repo: Path) -> list[ScannedRecord]:
    """Verify every record, every lineage, and the Git history of the gate directory.

    Fails if Git history shows any committed record modified, deleted, renamed, or
    replaced; if the working tree or index differs from HEAD for a committed record; if any
    file in the directory is not a valid record; or if any lineage rule is broken.
    """
    repo = Path(os.path.realpath(repo))
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise GateIntegrityError("gate history cannot be verified in a shallow clone")
    common = os.fsdecode(
        _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    )
    if os.path.lexists(Path(common) / "info" / "grafts"):
        raise GateIntegrityError("gate history cannot be verified while info/grafts rewrites it")
    if _git(repo, "for-each-ref", "--format=%(refname)", "refs/replace/").strip():
        # Replace objects are already ignored here (GIT_NO_REPLACE_OBJECTS); refusing them
        # outright keeps every tool's view of history identical (Step 11 F-20).
        raise GateIntegrityError("gate history cannot be verified while Git replace refs exist")
    _git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    # -m with --full-history shows each merge's changes against every parent, so a merge
    # cannot modify, delete, or replace a committed record without appearing here.
    history = _git(
        repo,
        "log",
        "--full-history",
        "-m",
        "--no-renames",
        "--format=",
        "--name-status",
        "-z",
        "--",
        GATES_DIR,
    )
    parts = [part for part in history.split(b"\0") if part]
    for status, path in zip(parts[0::2], parts[1::2], strict=True):
        name = path.decode("utf-8", errors="replace").rpartition("/")[2]
        if status.strip() != b"A" or parse_file_name(name) is None:
            raise GateIntegrityError(
                "Git history shows a gate record that was modified, deleted, or replaced"
            )
    status = _git(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--no-renames",
        "--",
        GATES_DIR,
    )
    for entry in (item for item in status.split(b"\0") if item):
        if entry[:2] not in (b"??", b"A "):
            raise GateIntegrityError("a committed gate record differs from HEAD")
    tracked = _git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", GATES_DIR)
    records = list_gate_records(repo)
    present = {f"{GATES_DIR}/{item.name}" for item in records if item.committed}
    for tracked_path in (
        item.decode("utf-8", errors="replace") for item in tracked.split(b"\0") if item
    ):
        if tracked_path not in present:
            raise GateIntegrityError("a committed gate record is missing or changed")
    try:
        verify_lineages(
            [LineageMember(item.record, item.sha256, item.committed) for item in records]
        )
    except GateRecordError as exc:
        raise GateIntegrityError(str(exc)) from None
    for item in records:
        _check_project_commit(repo, item)
        _check_project_pins(repo, item)
    return records


def _check_project_commit(repo: Path, item: ScannedRecord) -> None:
    """The recorded project commit must stay in HEAD's durable ancestry.

    For a committed record it must also be a strict ancestor of the commit that first
    introduced the record, so a record amended into the commit it describes (orphaning
    the recorded state) fails.
    """
    project = item.record.document["project"]
    commit = str(project["commit"]) if isinstance(project, dict) else ""
    if not _git_ok(repo, "cat-file", "-e", f"{commit}^{{commit}}"):
        raise GateIntegrityError("a gate record's project commit does not exist")
    if not _git_ok(repo, "merge-base", "--is-ancestor", commit, "HEAD"):
        raise GateIntegrityError("a gate record's project commit is not in HEAD's history")
    if not item.committed:
        return
    introduced = _git(
        repo,
        "log",
        "--full-history",
        "-m",
        "--diff-filter=A",
        "--reverse",
        "--format=%H",
        "--",
        f"{GATES_DIR}/{item.name}",
    ).split()
    if not introduced:
        raise GateIntegrityError("the commit that introduced a gate record cannot be found")
    first = introduced[0].decode("ascii")
    if first == commit or not _git_ok(repo, "merge-base", "--is-ancestor", commit, first):
        raise GateIntegrityError(
            "a gate record must be committed in a new commit after the project commit it records"
        )


def _check_project_pins(repo: Path, item: ScannedRecord) -> None:
    """Re-derive a clean-tree record's governance and config hashes from its project commit.

    A clean-tree record (every PASS is one) was captured from exactly the files at
    ``project.commit``, so each recorded hash must equal the hash of that file at that
    commit, and the recorded config set must equal the commit's ``configs/*.toml``. This
    turns the pins from self-reported fields into checked facts; a missing commit or file
    fails (Step 11 F-21). A dirty-tree record cannot be re-derived and is only canonical.
    Replace objects are never honored (``GIT_NO_REPLACE_OBJECTS``).
    """
    project = item.record.document["project"]
    if not isinstance(project, dict) or project["tree_dirty"] is not False:
        return
    commit = str(project["commit"])
    governance = project["governance"]
    configs = project["configs"]
    if not isinstance(governance, list) or not isinstance(configs, list):
        raise GateIntegrityError("a gate record's project pins are malformed")
    listed = (
        _git(repo, "ls-tree", "-z", "--name-only", f"{commit}:configs")
        if _git_ok(repo, "cat-file", "-e", f"{commit}:configs")
        else b""
    )
    committed_configs = sorted(
        f"configs/{name}"
        for name in (raw.decode("utf-8", "replace") for raw in listed.split(b"\0") if raw)
        if name.endswith(".toml")
    )
    recorded_configs = sorted(str(entry["path"]) for entry in configs)
    if recorded_configs != committed_configs:
        raise GateIntegrityError("a gate record's config set does not match its project commit")
    for entry in [*governance, *configs]:
        path, digest = str(entry["path"]), entry["sha256"]
        if sha256_hex(_git(repo, "cat-file", "blob", f"{commit}:{path}")) != digest:
            raise GateIntegrityError(
                "a gate record's governance or config hash does not match its project commit"
            )


# ----- filesystem and Git helpers -----


@contextlib.contextmanager
def _fs_errors() -> Iterator[None]:
    try:
        yield
    except safe_fs.FsUnsupportedError as exc:
        raise GateIntegrityError(str(exc)) from None
    except safe_fs.FsIntegrityError as exc:
        raise GateIntegrityError(str(exc)) from None


def _git(repo: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
            [
                "/usr/bin/git",
                "-C",
                str(repo),
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                "core.quotePath=false",
                *arguments,
            ],
            capture_output=True,
            env=_GIT_ENV,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GateIntegrityError("git could not be run") from None
    if completed.returncode != 0:
        raise GateIntegrityError("a git command failed")
    return completed.stdout


def _git_ok(repo: Path, *arguments: str) -> bool:
    """A yes/no git query: exit 0 is yes. ``cat-file -e`` reports a missing object as
    no; for anything else, an exit other than 0 or 1 fails closed."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
            ["/usr/bin/git", "-C", str(repo), "--no-optional-locks", *arguments],
            capture_output=True,
            env=_GIT_ENV,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GateIntegrityError("git could not be run") from None
    if completed.returncode not in (0, 1) and arguments[:1] != ("cat-file",):
        raise GateIntegrityError("a git command failed")
    return completed.returncode == 0


def _head_blob(repo: Path, path: str) -> bytes | None:
    listing = _git(repo, "ls-tree", "-z", "HEAD", "--", path)
    if not listing:
        return None
    meta = listing.split(b"\t", 1)[0].split(b" ")
    if len(meta) != 3 or meta[0] not in (b"100644", b"100755") or meta[1] != b"blob":
        raise GateIntegrityError("a committed path is not a regular file")
    return _git(repo, "cat-file", "blob", meta[2].decode("ascii"))


@contextlib.contextmanager
def _repo_dir(
    repo: Path, components: Sequence[str], *, create: bool = False
) -> Iterator[int | None]:
    """Open a repository directory without following symlinks (optionally creating it)."""
    fd = os.open(repo, safe_fs.DIR_FLAGS)
    try:
        for name in components:
            try:
                with _fs_errors():
                    child = safe_fs.open_dir(fd, name)
            except FileNotFoundError:
                if not create:
                    os.close(fd)
                    fd = -1
                    yield None
                    return
                os.mkdir(name, 0o755, dir_fd=fd)
                os.fsync(fd)
                with _fs_errors():
                    child = safe_fs.open_dir(fd, name)
            os.close(fd)
            fd = child
        yield fd
    finally:
        if fd >= 0:
            os.close(fd)


def _read_repo_file(repo: Path, path: str) -> bytes:
    *directories, name = path.split("/")
    with _repo_dir(repo, directories) as fd:
        if fd is None:
            raise GateEvidenceError("a repository file is missing")
        try:
            with _fs_errors():
                return safe_fs.read_small(fd, name, MAX_FILE_BYTES)
        except FileNotFoundError:
            raise GateEvidenceError("a repository file is missing") from None


@contextlib.contextmanager
def _locked_gates_dir(repo: Path, timeout_seconds: float = 30.0) -> Iterator[int]:
    with _repo_dir(repo, tuple(GATES_DIR.split("/")), create=True) as fd:
        assert fd is not None  # noqa: S101 - create=True always yields a descriptor
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise GateStateError("another gate record is being created") from None
                time.sleep(0.01)
        yield fd


# ----- request parsing and command line -----


def request_from_json(document: object) -> GateRequest:
    """Build a request from a closed JSON object (the ``create`` command's input file)."""
    item = _object(
        document,
        {
            "gate_id",
            "decision",
            "approval_attested",
            "reasons",
            "findings",
            "reviews",
            "cycle_id",
            "candidate_id",
            "experiment_ledger",
            "runs",
            "artifacts",
            "raw_captures",
            "documents",
            "holdout",
            "run_check_sh",
            "supersedes",
        },
    )
    try:
        pin = item["experiment_ledger"]
        supersedes = item["supersedes"]
        return GateRequest(
            gate_id=GateId(_text(item["gate_id"])),
            decision=Decision(_text(item["decision"])),
            approval_attested=_flag(item["approval_attested"]),
            reasons=tuple(_text(reason) for reason in _array(item["reasons"])),
            findings=tuple(
                Finding(
                    _text(f["finding_id"]),
                    FindingSeverity(_text(f["severity"])),
                    FindingStatus(_text(f["status"])),
                    _document(f["document"]),
                )
                for f in (
                    _object(x, {"finding_id", "severity", "status", "document"})
                    for x in _array(item["findings"])
                )
            ),
            reviews=tuple(
                Review(
                    ReviewerRole(_text(r["role"])),
                    ReviewConclusion(_text(r["conclusion"])),
                    Independence(_text(r["independence"])),
                    _document(r["document"]),
                )
                for r in (
                    _object(x, {"role", "conclusion", "independence", "document"})
                    for x in _array(item["reviews"])
                )
            ),
            cycle_id=None if item["cycle_id"] is None else _text(item["cycle_id"]),
            candidate_id=None if item["candidate_id"] is None else _text(item["candidate_id"]),
            ledger_pin=None
            if pin is None
            else LedgerPin(
                _integer(_object(pin, {"ledger_seq", "entry_sha256"})["ledger_seq"]),
                _text(_object(pin, {"ledger_seq", "entry_sha256"})["entry_sha256"]),
            ),
            runs=tuple(
                RunEvidence(_text(r["run_id"]), RunRole(_text(r["role"])))
                for r in (_object(x, {"run_id", "role"}) for x in _array(item["runs"]))
            ),
            artifacts=tuple(
                ArtifactEvidence(_text(a["run_id"]), _text(a["artifact_name"]), _text(a["sha256"]))
                for a in (
                    _object(x, {"run_id", "artifact_name", "sha256"})
                    for x in _array(item["artifacts"])
                )
            ),
            raw_captures=tuple(
                CaptureEvidence(_text(c["capture_id"]), _text(c["manifest_sha256"]))
                for c in (
                    _object(x, {"capture_id", "manifest_sha256"})
                    for x in _array(item["raw_captures"])
                )
            ),
            documents=tuple(
                doc for doc in (_document(x) for x in _array(item["documents"])) if doc is not None
            ),
            holdout=tuple(_array(item["holdout"])),
            run_check_sh=_flag(item["run_check_sh"]),
            supersedes=None
            if supersedes is None
            else Supersedes(
                _text(_object(supersedes, {"record_id", "record_sha256"})["record_id"]),
                _text(_object(supersedes, {"record_id", "record_sha256"})["record_sha256"]),
            ),
        )
    except ValueError:
        raise GateRecordError("the gate request uses an unknown value") from None


def _object(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GateRecordError("a gate request object does not have exactly the v1 fields")
    return value


def _array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise GateRecordError("a gate request field must be a list")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise GateRecordError("a gate request field must be a string")
    return value


def _flag(value: object) -> bool:
    if not isinstance(value, bool):
        raise GateRecordError("a gate request field must be a boolean")
    return value


def _integer(value: object) -> int:
    if type(value) is not int:
        raise GateRecordError("a gate request field must be an integer")
    return value


def _document(value: object) -> DocumentEvidence | None:
    if value is None:
        return None
    item = _object(value, {"path", "sha256", "kind"})
    return DocumentEvidence(
        _text(item["path"]), _text(item["sha256"]), DocumentKind(_text(item["kind"]))
    )


def _load_request(path: Path) -> GateRequest:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise GateRecordError("the gate request has duplicate keys")
            result[key] = value
        return result

    def no_floats(_text: str) -> object:
        raise GateRecordError("the gate request must not contain floats")

    try:
        document = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=no_floats,
            parse_constant=no_floats,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GateRecordError("the gate request is not valid JSON") from None
    return request_from_json(document)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pmv.gates", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-history", help="verify every record and the gate Git history")
    verify = commands.add_parser("verify", help="verify one record file")
    verify.add_argument("path", type=Path)
    commands.add_parser("list", help="list records with their lineage and commit status")
    create = commands.add_parser("create", help="create one new, untracked gate record")
    create.add_argument("--request", type=Path, required=True)
    create.add_argument("--config", type=Path, required=True)
    create.add_argument(
        "--environment", choices=[item.value for item in Environment], required=True
    )
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "verify-history":
            records = verify_gate_history(arguments.repo)
            sys.stdout.write(f"gate history verified: {len(records)} record(s)\n")
        elif arguments.command == "verify":
            record = verify_gate_record(arguments.path)
            sys.stdout.write(f"gate record verified: {record.gate_id} {record.record_id}\n")
        elif arguments.command == "list":
            for item in list_gate_records(arguments.repo):
                state = "committed" if item.committed else "not committed"
                sys.stdout.write(
                    f"{item.name} {item.record.decision.value} {item.sha256} {state}\n"
                )
        else:
            created = _create_from_cli(arguments)
            sys.stdout.write(
                f"created {created.path}\nsha256 {created.sha256}\n"
                "This file is untracked and not a project decision until you review and commit "
                "it yourself. The tool never stages, commits, or pushes.\n"
            )
    except (GateError, GateRecordError, ExperimentError, RawStorageError) as exc:
        # These messages are fixed text written by PMV and never echo content.
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 1
    except ConfigError:
        sys.stderr.write("ConfigError: the configuration could not be loaded or is invalid\n")
        return 1
    except subprocess.TimeoutExpired:
        sys.stderr.write("GateStateError: a subprocess did not finish within its time limit\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"OSError: {errno.errorcode.get(exc.errno or 0, 'unknown')}\n")
        return 1
    return 0


def _create_from_cli(arguments: argparse.Namespace) -> CreatedRecord:
    repo = Path(os.path.realpath(arguments.repo))
    request = _load_request(arguments.request)
    config = load_config(arguments.config, Environment(arguments.environment))
    with contextlib.ExitStack() as stack:
        experiment_store = None
        if request.ledger_pin is not None:
            if config.experiments.root is None:
                raise GateEvidenceError("the configuration has no [experiments] root")
            experiment_store = stack.enter_context(
                ExperimentStore(
                    config.experiments.root,
                    repo_root=repo,
                    app_config_sha256=config.source_sha256,
                    raw_root=config.raw_storage.root,
                )
            )
        raw_store = None
        if request.raw_captures:
            raw_store = stack.enter_context(
                RawCaptureStore(
                    config.raw_storage,
                    collect_runtime_provenance(config, repo_root=repo),
                    repo_root=repo,
                )
            )
        return create_gate_record(
            repo, request, experiment_store=experiment_store, raw_store=raw_store
        )


if __name__ == "__main__":
    raise SystemExit(main())
