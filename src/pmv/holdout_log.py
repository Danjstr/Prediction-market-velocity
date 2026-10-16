"""Protected-holdout access log tooling (Phase 0 Step 8). Never opens protected data.

The authoritative record is ``research/holdout_access/ledger.v1.jsonl``; HOLDOUT_ACCESS_LOG.md
is its generated human-visible mirror (see pmv.holdout_record). One writer lock covers
ledger verification, the ledger append, and the mirror rewrite:

1. fully verify the ledger, then require the mirror to agree exactly (a mirror that is
   behind blocks every normal append until ``mirror`` brings it forward);
2. append one canonical event (single write; rollback on a short write; fsync; read back;
   root, directory, and file identities re-checked before and after);
3. write the regenerated HOLDOUT_ACCESS_LOG.md through a synced temporary file and an
   atomic rename, then read it back.

Strict v1 consumption: ``access_started`` consumes the holdout permanently. Before any
protected byte may be exposed, ``assert_started_committed`` must confirm that the event
and its mirror are committed in HEAD and that Gate 6, the Gate 7 PASS record used as v1
plan approval (Step 11 F-18: Gate 7 itself is the holdout result), and the
exact candidate identity still hold. Step 8 cannot prove that nobody bypassed this
protocol; known or suspected bypasses are recorded as contamination and consume the
holdout. There is no repair tooling: a malformed ledger fails closed.

Usage: ``python -m pmv.holdout_log {verify,verify-history,status,mirror,initialize,
assert-started-committed,record} ...``
"""

import argparse
import contextlib
import errno
import fcntl
import json
import os
import secrets
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pmv import experiment_ledger, safe_fs
from pmv import holdout_record as hr
from pmv.capture_environment import RefusedTestEnvironmentError, refuse_test_environment
from pmv.config import ConfigError, Environment, load_config
from pmv.experiments import ExperimentError, ExperimentStore, collect_git_identity
from pmv.gate_record import GATES_DIR, GateRecordError, LineageKey
from pmv.gates import GateError, ScannedRecord, verify_gate_history
from pmv.holdout_record import (
    LEDGER_PATH,
    LOG_PATH,
    ActorRole,
    Component,
    ContaminationLevel,
    DenialReason,
    EventType,
    ExposureCategory,
    FailureReason,
    HoldoutRecordError,
    InterruptReason,
    LogState,
    RefusalReason,
    SplitFormation,
)
from pmv.integrity import format_timestamp, sha256_hex, to_utc
from pmv.log import fields, get_logger

_log = get_logger("pmv.holdout_log")

LEDGER_DIR: Final = ("research", "holdout_access")
LEDGER_NAME: Final = "ledger.v1.jsonl"
MAX_FILE_BYTES: Final = 67_108_864
_ALLOWED_POST_COMMIT_PATHS: Final = (LEDGER_PATH, LOG_PATH)
_GIT_ENV: Final = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LC_ALL": "C",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
}

# Test seams: simulated short writes and failed rollbacks.
_ledger_write: Callable[[int, bytes], int] = os.write
_ledger_truncate: Callable[[int, int], None] = os.ftruncate


class HoldoutLogError(Exception):
    """The holdout log cannot be read, verified, or extended. Never echoes content."""


class HoldoutLogIntegrityError(HoldoutLogError):
    """The ledger, its mirror, its Git history, or its location fails verification."""


class MirrorBehindError(HoldoutLogIntegrityError):
    """The ledger holds events the Markdown mirror does not; run ``mirror`` first."""


class AccessRefusedError(HoldoutLogError):
    """An access attempt was refused; an access_attempt_refused event was recorded."""

    def __init__(self, reason: RefusalReason) -> None:
        super().__init__(f"access refused: {reason.value}")
        self.reason = reason


class NotReadyError(HoldoutLogError):
    """The committed access_started protocol is not complete; data must not be revealed."""


# ----- inputs -----


@dataclass(frozen=True, slots=True)
class FileRef:
    path: str
    sha256: str

    def to_json(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class RecordRef:
    record_id: str
    record_sha256: str

    def to_json(self) -> dict[str, object]:
        return {"record_id": self.record_id, "record_sha256": self.record_sha256}


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    """The candidate to request access for: every component as typed references."""

    cycle_id: str
    holdout_id: str
    candidate_id: str
    components: Mapping[Component, Sequence[Mapping[str, object]]]


@dataclass(frozen=True, slots=True)
class ReadyReport:
    started_event_id: str
    holdout_id: str
    candidate_identity_sha256: str
    head_commit: str


# ----- the log -----


@dataclass(slots=True)
class _Locked:
    repo_fd: int
    dir_fd: int
    identities: list[safe_fs.Identity]


class HoldoutLog:
    """Writer and verifier for one repository's protected-holdout access log."""

    def __init__(
        self,
        repo: Path,
        *,
        experiment_store: ExperimentStore | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        random_token: Callable[[], str] = lambda: secrets.token_hex(16),
        fault_hook: Callable[[str], None] | None = None,
        lock_timeout_seconds: float = 30.0,
        reviewed_legacy_sha256: str = hr.REVIEWED_LEGACY_SHA256,
    ) -> None:
        self.repo = Path(os.path.realpath(repo))
        self._store = experiment_store
        self._clock = clock
        self._token = random_token
        self._fault_hook = fault_hook
        self._lock_timeout = lock_timeout_seconds
        self._reviewed_legacy = reviewed_legacy_sha256
        self._latched = False
        self._legacy_cache: bytes | None = None

    # ----- reading and verification -----

    def state(self) -> LogState | None:
        """The verified ledger state (mirror must agree exactly), or None before init."""
        with self._locked(exclusive=False, create=False) as locked:
            if locked is None:
                self._require_uninitialized_log()
                return None
            data = self._read_ledger(locked)
            if data is None:
                self._require_uninitialized_log()
                return None
            state = self._verify_ledger(data)
            self._require_mirror(state, self._read_log())
            self._check_gate_references(state)
            return state

    def initialize(self) -> hr.Event:
        """Create the ledger with HAL-0005 (log_initialized) and the first mirror."""
        self._require_unlatched()
        with self._locked(exclusive=True, create=True) as locked:
            assert locked is not None  # noqa: S101 - create=True always yields a lock
            if safe_fs.exists(locked.dir_fd, LEDGER_NAME):
                raise HoldoutLogIntegrityError("the holdout ledger is already initialized")
            legacy = self._read_log()
            if sha256_hex(legacy) != self._reviewed_legacy:
                raise HoldoutLogIntegrityError(
                    "HOLDOUT_ACCESS_LOG.md is not the reviewed legacy file; not initialized"
                )
            self._verify_history_locked()
            preamble, _status, before, after, history = _split_legacy(legacy)
            body = before + hr.MACHINE_LEDGER_SECTION.encode("utf-8") + after
            try:
                event_fields = hr.initialization_fields(legacy)
            except HoldoutRecordError as exc:
                raise HoldoutLogIntegrityError(str(exc)) from None
            line = hr.encode_event(
                LogState(), EventType.LOG_INITIALIZED, self._now(), self._repository(), event_fields
            )
            state = self._verify_ledger(line)
            self._create_ledger(locked, line)
            self._fault("initialize.ledger_written")
            layout = hr.LogLayout(preamble, b"", body, history, b"")
            self._write_log(locked, legacy, hr.render_log(layout, state))
        _log.info("holdout_log.initialized")
        return state.events[0]

    def mirror(self) -> int:
        """Bring HOLDOUT_ACCESS_LOG.md forward to the verified ledger; never touches it.

        The current file must be exactly the rendering of a prefix of the ledger (or the
        reviewed legacy file); anything else fails closed. Returns the events added.
        """
        self._require_unlatched()
        with self._locked(exclusive=True, create=False) as locked:
            if locked is None or (data := self._read_ledger(locked)) is None:
                raise HoldoutLogIntegrityError("the holdout ledger is not initialized")
            state = self._verify_ledger(data)
            current = self._read_log()
            shown, layout = self._mirror_position(state, data, current)
            if shown == len(state.events):
                return 0
            self._write_log(locked, current, hr.render_log(layout, state))
        return len(state.events) - shown

    def verify_history(self) -> LogState | None:
        """Verify the working tree and every committed version in HEAD's history."""
        state = self.state()
        self._verify_history_locked()
        return state

    def _verify_history_locked(self) -> None:
        _verify_git_history(self.repo, self._reviewed_legacy, self._legacy_bytes())

    def _legacy_bytes(self) -> bytes:
        """The reviewed legacy HOLDOUT_ACCESS_LOG.md bytes, found by hash in Git history.

        HAL-0005's fields are re-derived from these bytes, never trusted as self-asserted.
        """
        if self._legacy_cache is None:
            self._legacy_cache = _find_reviewed_legacy(self.repo, self._reviewed_legacy)
        return self._legacy_cache

    # ----- events -----

    def register_cycle(
        self,
        cycle_id: str,
        split_formation: SplitFormation,
        development_subset: FileRef,
        protected_start: datetime,
        protected_end: datetime,
        *,
        attested: bool,
    ) -> hr.Event:
        self._verify_document(development_subset)
        return self._append(
            EventType.CYCLE_REGISTERED,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "cycle_id": cycle_id,
                "development_subset": development_subset.to_json(),
                "protected_end": format_timestamp(protected_end),
                "protected_start": format_timestamp(protected_start),
                "split_formation": SplitFormation(split_formation).value,
            },
        )

    def register_holdout(
        self,
        holdout_id: str,
        cycle_id: str,
        split_definition: FileRef,
        *,
        snapshot_manifest_sha256: str,
        metadata_sha256: str,
        observation_count: int,
        start: datetime,
        end: datetime,
        purge_embargo_sha256: str,
        source_manifest_sha256: str,
        attested: bool,
    ) -> hr.Event:
        """Record the protected set's identity (hashes and counts only; no data read)."""
        self._verify_document(split_definition)
        return self._append(
            EventType.HOLDOUT_REGISTERED,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "cycle_id": cycle_id,
                "end": format_timestamp(end),
                "holdout_id": holdout_id,
                "metadata_sha256": metadata_sha256,
                "observation_count": observation_count,
                "purge_embargo_sha256": purge_embargo_sha256,
                "snapshot_manifest_sha256": snapshot_manifest_sha256,
                "source_manifest_sha256": source_manifest_sha256,
                "split_definition": split_definition.to_json(),
                "start": format_timestamp(start),
            },
        )

    def request_access(self, spec: CandidateSpec, requested_by: ActorRole) -> hr.Event:
        state = self._require_state()
        holdout = state.holdouts.get(spec.holdout_id)
        if holdout is not None and holdout.consumed_by is not None:
            self._refuse(
                spec.cycle_id,
                spec.holdout_id,
                spec.candidate_id,
                None,
                RefusalReason.HOLDOUT_CONSUMED,
            )
        if holdout is not None and holdout.cycle_id != spec.cycle_id:
            self._refuse(
                spec.cycle_id, spec.holdout_id, spec.candidate_id, None, RefusalReason.WRONG_CYCLE
            )
        identity = self._build_identity(spec)
        digest = hr.candidate_identity_sha256(identity)
        return self._append(
            EventType.ACCESS_REQUESTED,
            lambda _state: {
                "candidate_id": spec.candidate_id,
                "candidate_identity": identity,
                "candidate_identity_sha256": digest,
                "cycle_id": spec.cycle_id,
                "holdout_id": spec.holdout_id,
                "requested_by": ActorRole(requested_by).value,
            },
        )

    def authorize(self, request_event_id: str, gate_6: RecordRef, *, attested: bool) -> hr.Event:
        """Owner authorization, backed by a committed, current Gate 6 PASS record."""
        state = self._require_state()
        request = state.requests.get(request_event_id)
        if request is None or request.decision is not None:
            raise HoldoutLogError("the request does not exist or was already decided")
        if not attested:
            raise HoldoutLogError("authorization requires the owner's explicit attestation")
        plan = hr.evaluation_plan_of(request.identity)
        if not self._gate_valid(gate_6, "gate_6", request, plan):
            raise HoldoutLogError("the Gate 6 record is not a committed, current, matching PASS")
        if self._identity_problem(request.identity) is not None:
            raise HoldoutLogError("the candidate changed since it was requested")
        reference = _event_ref(state, request_event_id)
        return self._append(
            EventType.ACCESS_AUTHORIZED,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "candidate_identity_sha256": request.identity_sha256,
                "evaluation_plan": plan,
                "gate_6": gate_6.to_json(),
                "request": reference,
            },
        )

    def deny(self, request_event_id: str, reason: DenialReason, *, attested: bool) -> hr.Event:
        state = self._require_state()
        reference = _event_ref(state, request_event_id)
        return self._append(
            EventType.ACCESS_DENIED,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "reason": DenialReason(reason).value,
                "request": reference,
            },
        )

    def start(
        self,
        authorization_event_id: str,
        gate_7: RecordRef,
        *,
        operator: ActorRole,
        attested: bool,
    ) -> hr.Event:
        """Record access_started (consuming) after re-verifying everything.

        Any failed check appends access_attempt_refused and raises AccessRefusedError.
        """
        state = self._require_state()
        authorization = state.authorizations.get(authorization_event_id)
        if authorization is None:
            self._refuse(None, None, None, None, RefusalReason.NO_AUTHORIZATION)
        assert authorization is not None  # noqa: S101 - _refuse always raises
        request = state.requests[authorization.request]
        reference = _event_ref(state, authorization_event_id)

        def refuse(reason: RefusalReason) -> None:
            self._refuse(
                request.cycle_id, request.holdout_id, request.candidate_id, reference, reason
            )

        if authorization.started_by is not None:
            refuse(RefusalReason.AUTHORIZATION_ALREADY_USED)
        if state.holdouts[authorization.holdout_id].consumed_by is not None:
            refuse(RefusalReason.HOLDOUT_CONSUMED)
        if not attested or operator not in hr.OPERATOR_ROLES:
            refuse(RefusalReason.OWNER_NOT_ATTESTED)
        problem = self._start_problem(request, authorization, gate_7)
        if problem is not None:
            refuse(problem)
        return self._append(
            EventType.ACCESS_STARTED,
            lambda _state: {
                "attestation": _attestation(ActorRole(operator), attested),
                "authorization": reference,
                "candidate_identity_sha256": authorization.identity_sha256,
                "evaluation_plan": dict(authorization.evaluation_plan),
                "gate_6": dict(authorization.gate_6),
                "gate_7": gate_7.to_json(),
            },
        )

    def finish(
        self,
        started_event_id: str,
        outcome: EventType,
        *,
        recorded_by: ActorRole,
        reason: FailureReason | InterruptReason | None = None,
        restricted_evidence_sha256: str | None = None,
    ) -> hr.Event:
        """Close a started access: completed, failed, or interrupted. Stays consumed."""
        if outcome not in hr.CLOSING_EVENTS:
            raise HoldoutLogError("an access closes as completed, failed, or interrupted")
        state = self._require_state()
        reference = _event_ref(state, started_event_id)
        event_fields: dict[str, object] = {
            "recorded_by": ActorRole(recorded_by).value,
            "started": reference,
        }
        event_fields["restricted_evidence_sha256"] = restricted_evidence_sha256
        if outcome is not EventType.ACCESS_COMPLETED:
            if reason is None:
                raise HoldoutLogError("a failed or interrupted access needs a reason")
            event_fields["reason"] = reason.value
        return self._append(outcome, lambda _state: event_fields)

    def record_contamination(
        self,
        holdout_id: str,
        level: ContaminationLevel,
        categories: Sequence[ExposureCategory],
        roles: Sequence[ActorRole],
        *,
        restricted_evidence_sha256: str | None,
        attested: bool,
    ) -> hr.Event:
        return self._append(
            EventType.CONTAMINATION_RECORDED,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "exposed_roles": sorted({ActorRole(item).value for item in roles}),
                "exposure_categories": sorted(
                    {ExposureCategory(item).value for item in categories}
                ),
                "holdout_id": holdout_id,
                "level": ContaminationLevel(level).value,
                "restricted_evidence_sha256": restricted_evidence_sha256,
            },
        )

    def reclassify(self, holdout_id: str, untouched_holdout_id: str, *, attested: bool) -> hr.Event:
        return self._append(
            EventType.HISTORICAL_RECLASSIFICATION,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "holdout_id": holdout_id,
                "untouched_holdout_id": untouched_holdout_id,
            },
        )

    def correct(self, event_id: str, document: FileRef, *, attested: bool) -> hr.Event:
        """Annotative only: it never changes or reverses state."""
        self._verify_document(document)
        state = self._require_state()
        reference = _event_ref(state, event_id)
        return self._append(
            EventType.CORRECTION_RECORDED,
            lambda _state: {
                "attestation": _attestation(ActorRole.PROJECT_OWNER, attested),
                "corrects": reference,
                "document": document.to_json(),
            },
        )

    # ----- the reveal precondition -----

    def assert_started_committed(self, started_event_id: str) -> ReadyReport:
        """Confirm the protocol is complete before Step 9 may expose any protected byte.

        The ledger and mirror verify and agree; access_started exists, is open, and its
        ledger and Markdown bytes are exactly HEAD's (working tree and index match HEAD);
        the tree is clean; Gate 6 and the Gate 7 PASS record used as v1 plan approval
        (Step 11 F-18) are committed, current, and matching; and the candidate identity
        still holds exactly.
        """
        # The full Git history is verified here, so a consuming event that was ever
        # committed and later reverted or rewritten forward can never look unconsumed.
        state = self.verify_history()
        if state is None:
            raise NotReadyError("the holdout ledger is not initialized")
        start = state.starts.get(started_event_id)
        if start is None:
            raise NotReadyError("access_started does not exist")
        if start.closed_by is not None:
            raise NotReadyError("the access is already closed")
        changed = _git(self.repo, "status", "--porcelain=v1", "-z", "--", LEDGER_PATH, LOG_PATH)
        if changed:
            raise NotReadyError("the ledger or its mirror differs from HEAD")
        for path in (LEDGER_PATH, LOG_PATH):
            if _head_blob(self.repo, path) != self._read_relative(path):
                raise NotReadyError("the ledger or its mirror is not committed in HEAD")
        identity = collect_git_identity(self.repo)
        if identity.commit is None or identity.dirty is not False:
            raise NotReadyError("the repository is not clean")
        authorization = state.authorizations[start.authorization]
        request = state.requests[authorization.request]
        gate_7 = RecordRef(str(start.gate_7["record_id"]), str(start.gate_7["record_sha256"]))
        if self._start_problem(request, authorization, gate_7) is not None:
            raise NotReadyError("Gate 6, Gate 7, or the candidate identity no longer holds")
        return ReadyReport(
            started_event_id, start.holdout_id, request.identity_sha256, identity.commit
        )

    # ----- checks -----

    def _start_problem(
        self, request: hr.RequestState, authorization: hr.AuthorizationState, gate_7: RecordRef
    ) -> RefusalReason | None:
        identity = collect_git_identity(self.repo)
        if identity.commit is None or identity.dirty is not False:
            return RefusalReason.REPOSITORY_NOT_CLEAN
        plan = dict(authorization.evaluation_plan)
        gate_6 = RecordRef(
            str(authorization.gate_6["record_id"]), str(authorization.gate_6["record_sha256"])
        )
        if not self._gate_valid(gate_6, "gate_6", request, plan):
            return RefusalReason.GATE_6_INVALID
        if self._find_record(gate_7) is None:
            return RefusalReason.GATE_7_MISSING
        if not self._gate_valid(gate_7, "gate_7", request, plan):
            return RefusalReason.GATE_7_INVALID
        return self._identity_problem(request.identity)

    def _gate_valid(
        self, ref: RecordRef, gate_id: str, request: hr.RequestState, plan: Mapping[str, object]
    ) -> bool:
        """A committed, current-head PASS for exactly this gate, cycle, candidate, and plan."""
        try:
            records = verify_gate_history(self.repo)
        except (GateError, GateRecordError):
            return False
        found = next((item for item in records if item.record.record_id == ref.record_id), None)
        if found is None or found.sha256 != ref.record_sha256 or not found.committed:
            return False
        record = found.record
        key = LineageKey(gate_id, request.cycle_id, request.candidate_id)
        if record.gate_id != gate_id or record.lineage != key or record.decision.value != "pass":
            return False
        successors = {
            item.record.supersedes[0]
            for item in records
            if item.record.supersedes is not None and item.record.lineage == key
        }
        if record.record_id in successors:
            return False
        evidence = record.document["evidence"]
        documents = evidence.get("documents", []) if isinstance(evidence, dict) else []
        return any(
            isinstance(item, dict)
            and item.get("kind") == "plan"
            and item.get("path") == plan["path"]
            and item.get("sha256") == plan["sha256"]
            for item in documents
        )

    def _find_record(self, ref: RecordRef) -> ScannedRecord | None:
        try:
            records = verify_gate_history(self.repo)
        except (GateError, GateRecordError):
            return None
        return next((item for item in records if item.record.record_id == ref.record_id), None)

    def _identity_problem(self, identity: Mapping[str, object]) -> RefusalReason | None:
        """Recompute the candidate identity; return why it no longer holds, else None.

        Every component reference must still hold exactly; the recorded project commit
        must be in HEAD's history; and since that commit only the holdout ledger, its
        mirror, and gate records may have changed. The experiment-ledger pin must hold.
        """
        components = identity["components"]
        assert isinstance(components, dict)  # noqa: S101 - validated identity
        for name, refs in components.items():
            for ref in refs:
                if not self._ref_holds(ref, identity):
                    if name == Component.RUNNER.value:
                        return RefusalReason.RUNNER_MISMATCH
                    if name == Component.EVALUATION_PLAN.value:
                        return RefusalReason.EVALUATION_PLAN_MISMATCH
                    return RefusalReason.CANDIDATE_CHANGED
        commit = str(identity["project_commit"])
        if not _git_ok(self.repo, "merge-base", "--is-ancestor", commit, "HEAD"):
            return RefusalReason.CANDIDATE_CHANGED
        changed = _git(self.repo, "diff", "--no-renames", "--name-only", "-z", commit, "HEAD")
        for path in (
            item.decode("utf-8", errors="replace") for item in changed.split(b"\0") if item
        ):
            if path not in _ALLOWED_POST_COMMIT_PATHS and not path.startswith(GATES_DIR + "/"):
                return RefusalReason.CANDIDATE_CHANGED
        if not self._pin_holds(identity["experiment_ledger"]):
            return RefusalReason.CANDIDATE_CHANGED
        return None

    def _ref_holds(self, ref: Mapping[str, object], identity: Mapping[str, object]) -> bool:
        if ref["kind"] == "repo_file":
            path, digest = str(ref["path"]), ref["sha256"]
            try:
                working = self._read_relative(path)
            except HoldoutLogError:
                return False
            at_commit = _blob_at(self.repo, str(identity["project_commit"]), path)
            return (
                sha256_hex(working) == digest
                and _head_blob(self.repo, path) == working
                and at_commit == working
            )
        return self._artifact_holds(ref, identity["experiment_ledger"])

    def _artifact_holds(self, ref: Mapping[str, object], pin: object) -> bool:
        if self._store is None or not isinstance(pin, dict):
            return False
        try:
            state = self._store.snapshot()
            run = state.runs.get(str(ref["run_id"]))
            seq = int(pin["ledger_seq"])
            if run is None or run.completed_seq is None or run.completed_seq > seq:
                return False
            registered = run.artifacts.get(str(ref["artifact_name"]))
            if (
                registered is None
                or registered[1] > seq
                or registered[0]["sha256"] != ref["sha256"]
            ):
                return False
            self._store.verify_run(str(ref["run_id"]))
        except (ExperimentError, OSError, ValueError):
            return False
        return True

    def _pin_holds(self, pin: object) -> bool:
        if self._store is None or not isinstance(pin, dict):
            return False
        try:
            state = self._store.snapshot()
        except ExperimentError:
            return False
        seq = pin["ledger_seq"]
        return (
            isinstance(seq, int)
            and 0 <= seq <= state.head_seq
            and state.entries[seq].sha256 == pin["entry_sha256"]
            and experiment_ledger.store_id_of(state) == pin["store_id"]
        )

    def _build_identity(self, spec: CandidateSpec) -> dict[str, object]:
        identity = collect_git_identity(self.repo)
        if identity.commit is None or identity.dirty is not False:
            raise HoldoutLogError("a candidate identity requires a clean repository")
        if self._store is None:
            raise HoldoutLogError("a candidate identity needs the experiment store")
        try:
            store_state = self._store.snapshot()
        except ExperimentError:
            raise HoldoutLogError("the experiment ledger did not verify") from None
        if store_state.head_sha256 is None:
            raise HoldoutLogError("the experiment ledger is empty")
        document: dict[str, object] = {
            "candidate_id": spec.candidate_id,
            "components": {
                Component(name).value: hr.refs_sorted([dict(ref) for ref in refs])
                for name, refs in spec.components.items()
            },
            "cycle_id": spec.cycle_id,
            "experiment_ledger": {
                "entry_sha256": store_state.head_sha256,
                "ledger_seq": store_state.head_seq,
                "store_id": experiment_ledger.store_id_of(store_state),
            },
            "holdout_id": spec.holdout_id,
            "project_commit": identity.commit,
            "schema": hr.IDENTITY_SCHEMA,
            "schema_version": hr.SCHEMA_VERSION,
        }
        try:
            hr.validate_candidate_identity(document)
        except HoldoutRecordError as exc:
            raise HoldoutLogError(str(exc)) from None
        if self._identity_problem(document) is not None:
            raise HoldoutLogError("a candidate component does not match its committed bytes")
        return document

    def _verify_document(self, document: FileRef) -> None:
        if not hr.is_repo_path(document.path):
            raise HoldoutLogError("the document path is not an allowed repository path")
        working = self._read_relative(document.path)
        if (
            _head_blob(self.repo, document.path) != working
            or sha256_hex(working) != document.sha256
        ):
            raise HoldoutLogError("the document is not committed with exactly the given bytes")

    def _check_gate_references(self, state: LogState) -> None:
        """Every gate record the ledger cites still exists with exactly its bytes."""
        cited = [
            event.fields[key]
            for event in state.events
            for key in ("gate_6", "gate_7")
            if key in event.fields
        ]
        if not cited:
            return
        try:
            present = {
                item.record.record_id: item.sha256 for item in verify_gate_history(self.repo)
            }
        except (GateError, GateRecordError) as exc:
            raise HoldoutLogIntegrityError(f"gate records do not verify: {exc}") from None
        for ref in cited:
            if (
                not isinstance(ref, dict)
                or present.get(str(ref["record_id"])) != ref["record_sha256"]
            ):
                raise HoldoutLogIntegrityError(
                    "a gate record cited by the ledger is missing or changed"
                )

    # ----- append machinery -----

    def _append(
        self, event_type: EventType, build: Callable[[LogState], Mapping[str, object]]
    ) -> hr.Event:
        self._require_unlatched()
        with self._locked(exclusive=True, create=False) as locked:
            if locked is None:
                raise HoldoutLogIntegrityError("the holdout ledger is not initialized")
            # Every authoritative append first verifies the full Git history, so state that
            # durable history once held (for example a committed access_started) cannot be
            # bypassed by reverting it forward in the working tree or a later commit.
            self._verify_history_locked()
            fd = self._open_ledger(locked)
            try:
                data = safe_fs.pread_all(fd, os.fstat(fd).st_size)
                state = self._verify_ledger(data)
                current = self._read_log()
                self._require_mirror(state, current)
                line = hr.encode_event(
                    state, event_type, self._now(), self._repository(), build(state)
                )
                try:
                    hr.append_checked(self._verify_ledger(data), line)
                except HoldoutRecordError as exc:
                    raise HoldoutLogError(str(exc)) from None
                new_state = self._verify_ledger(data + line)
                self._fault("ledger.before_write")
                self._check_location(locked, fd)
                if os.fstat(fd).st_size != len(data):
                    raise HoldoutLogIntegrityError("the ledger changed outside the lock")
                try:
                    safe_fs.append_exact(
                        fd, line, len(data), write=_ledger_write, truncate=_ledger_truncate
                    )
                except safe_fs.RollbackError as exc:
                    self._latched = True
                    raise HoldoutLogIntegrityError(str(exc)) from None
                except OSError:
                    self._latched = True
                    raise
                self._fault("ledger.after_write")
                try:
                    if safe_fs.pread_all(fd, len(line), len(data)) != line:
                        raise HoldoutLogIntegrityError("the appended event did not read back")
                    if os.fstat(fd).st_size != len(data) + len(line):
                        raise HoldoutLogIntegrityError("the ledger size is wrong after the append")
                    self._check_location(locked, fd)
                except (HoldoutLogError, OSError, safe_fs.FsIntegrityError) as exc:
                    self._latched = True
                    raise HoldoutLogIntegrityError(
                        f"{exc}; write outcome unknown; re-verify authoritative state"
                    ) from None
            finally:
                os.close(fd)
            self._fault("ledger.appended")
            layout = hr.split_mirror(current, new_state.initialization)
            self._write_log(locked, current, hr.render_log(layout, new_state))
        event = new_state.events[-1]
        _log.info(
            "holdout_log.event_appended",
            extra=fields(event_id=event.event_id, event_type=event_type.value),
        )
        return event

    def _refuse(
        self,
        cycle_id: str | None,
        holdout_id: str | None,
        candidate_id: str | None,
        authorization: Mapping[str, object] | None,
        reason: RefusalReason,
    ) -> None:
        self._append(
            EventType.ACCESS_ATTEMPT_REFUSED,
            lambda _state: {
                "authorization": None if authorization is None else dict(authorization),
                "candidate_id": candidate_id,
                "cycle_id": cycle_id,
                "holdout_id": holdout_id,
                "reason": reason.value,
            },
        )
        raise AccessRefusedError(reason)

    def _require_state(self) -> LogState:
        state = self.state()
        if state is None:
            raise HoldoutLogIntegrityError("the holdout ledger is not initialized")
        return state

    def _require_mirror(self, state: LogState, current: bytes) -> None:
        try:
            layout = hr.split_mirror(current, state.initialization)
        except HoldoutRecordError:
            layout = None
        if layout is not None and hr.render_log(layout, state) == current:
            return
        try:
            shown, _layout = self._mirror_position(
                state, b"".join(e.line for e in state.events), current
            )
        except HoldoutLogIntegrityError:
            raise HoldoutLogIntegrityError(
                "HOLDOUT_ACCESS_LOG.md does not agree with the machine ledger"
            ) from None
        if shown < len(state.events):
            raise MirrorBehindError(
                "HOLDOUT_ACCESS_LOG.md is behind the machine ledger; run the mirror command"
            )

    def _mirror_position(
        self, state: LogState, data: bytes, current: bytes
    ) -> tuple[int, hr.LogLayout]:
        """How many ledger events ``current`` shows exactly, and the layout to render."""
        init = state.initialization
        if sha256_hex(current) == init["legacy_file_sha256"]:
            preamble, _status, before, after, history = _split_legacy(current)
            body = before + hr.MACHINE_LEDGER_SECTION.encode("utf-8") + after
            return 0, hr.LogLayout(preamble, b"", body, history, b"")
        try:
            layout = hr.split_mirror(current, init)
        except HoldoutRecordError:
            raise HoldoutLogIntegrityError(
                "HOLDOUT_ACCESS_LOG.md does not agree with the machine ledger"
            ) from None
        lines = data.split(b"\n")[:-1]
        for count in range(len(lines), 0, -1):
            prefix = hr.verify_ledger(b"".join(item + b"\n" for item in lines[:count]))
            if hr.render_log(layout, prefix) == current:
                return count, layout
        raise HoldoutLogIntegrityError(
            "HOLDOUT_ACCESS_LOG.md does not agree with the machine ledger"
        )

    def _verify_ledger(self, data: bytes) -> LogState:
        try:
            state = hr.verify_ledger(data)
        except HoldoutRecordError as exc:
            raise HoldoutLogIntegrityError(str(exc)) from None
        if not state.events:
            raise HoldoutLogIntegrityError("the holdout ledger is empty")
        if state.initialization["legacy_file_sha256"] != self._reviewed_legacy:
            raise HoldoutLogIntegrityError("the ledger does not pin the reviewed legacy log")
        try:
            hr.require_initialization(state, self._legacy_bytes())
        except HoldoutRecordError as exc:
            raise HoldoutLogIntegrityError(str(exc)) from None
        return state

    def _require_uninitialized_log(self) -> None:
        if sha256_hex(self._read_log()) != self._reviewed_legacy:
            raise HoldoutLogIntegrityError(
                "HOLDOUT_ACCESS_LOG.md differs from the reviewed legacy file but no machine "
                "ledger exists"
            )

    def _require_unlatched(self) -> None:
        if self._latched:
            raise HoldoutLogIntegrityError(
                "a ledger write failed earlier; open a new HoldoutLog to re-verify before appending"
            )

    def _fault(self, point: str) -> None:
        if self._fault_hook is not None:
            self._fault_hook(point)

    def _now(self) -> str:
        return format_timestamp(to_utc(self._clock()))

    def _repository(self) -> dict[str, object]:
        identity = collect_git_identity(self.repo)
        if identity.commit is None or identity.dirty is None:
            raise HoldoutLogError("the repository's code identity cannot be determined")
        return {
            "commit": identity.commit,
            "dirty_tree_sha256": identity.dirty_sha256 if identity.dirty else None,
            "tree_dirty": identity.dirty,
        }

    # ----- filesystem -----

    @contextlib.contextmanager
    def _locked(self, *, exclusive: bool, create: bool) -> Iterator[_Locked | None]:
        repo_fd = os.open(self.repo, safe_fs.DIR_FLAGS)
        opened = [repo_fd]
        try:
            fd = repo_fd
            for name in LEDGER_DIR:
                try:
                    with _fs_errors():
                        child = safe_fs.open_dir(fd, name)
                except FileNotFoundError:
                    if not create:
                        yield None
                        return
                    os.mkdir(name, 0o755, dir_fd=fd)
                    os.fsync(fd)
                    with _fs_errors():
                        child = safe_fs.open_dir(fd, name)
                opened.append(child)
                fd = child
            identities = [safe_fs.identity(os.fstat(item)) for item in opened]
            mode = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
            deadline = time.monotonic() + self._lock_timeout
            while True:
                try:
                    fcntl.flock(fd, mode)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise HoldoutLogError(
                            "the holdout log lock was not acquired in time"
                        ) from None
                    time.sleep(0.01)
            yield _Locked(repo_fd, fd, identities)
        finally:
            for item in opened:
                os.close(item)

    def _check_location(self, locked: _Locked, ledger_fd: int) -> None:
        expected = [*locked.identities, safe_fs.identity(os.fstat(ledger_fd))]
        try:
            found = safe_fs.path_identities(self.repo, [*LEDGER_DIR, LEDGER_NAME])
        except safe_fs.FsIntegrityError:
            raise HoldoutLogIntegrityError(
                "the repository or ledger was moved or replaced"
            ) from None
        if found != expected:
            raise HoldoutLogIntegrityError("the repository or ledger was moved or replaced")

    def _open_ledger(self, locked: _Locked) -> int:
        try:
            fd = os.open(LEDGER_NAME, safe_fs.APPEND_FLAGS, dir_fd=locked.dir_fd)
        except FileNotFoundError:
            raise HoldoutLogIntegrityError("the holdout ledger is missing") from None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise HoldoutLogIntegrityError("the holdout ledger is a symlink") from None
            raise
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise HoldoutLogIntegrityError("the holdout ledger is not a regular file")
        return fd

    def _read_ledger(self, locked: _Locked) -> bytes | None:
        try:
            with _fs_errors():
                return safe_fs.read_small(locked.dir_fd, LEDGER_NAME, MAX_FILE_BYTES)
        except FileNotFoundError:
            return None

    def _create_ledger(self, locked: _Locked, line: bytes) -> None:
        stage = f".stage-{self._token()}"
        try:
            with _fs_errors():
                safe_fs.write_new_file(locked.dir_fd, stage, line)
                fd = safe_fs.open_file(locked.dir_fd, stage)
            try:
                os.fchmod(fd, 0o644)
                os.fsync(fd)
                created = safe_fs.identity(os.fstat(fd))
            finally:
                os.close(fd)
            with _fs_errors():
                safe_fs.rename_noreplace(
                    locked.dir_fd, stage, locked.dir_fd, LEDGER_NAME, renameat2=safe_fs.RENAMEAT2
                )
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(stage, dir_fd=locked.dir_fd)
        os.fsync(locked.dir_fd)
        self._fault("ledger.created")
        self._require_live(
            [*LEDGER_DIR, LEDGER_NAME], [*locked.identities, created], "the new holdout ledger"
        )
        if self._read_relative(LEDGER_PATH) != line:
            self._latched = True
            raise HoldoutLogIntegrityError("the new ledger did not read back exactly")

    def _read_log(self) -> bytes:
        return self._read_relative(LOG_PATH)

    def _read_relative(self, path: str) -> bytes:
        *directories, name = path.split("/")
        fd = os.open(self.repo, safe_fs.DIR_FLAGS)
        try:
            for directory in directories:
                with _fs_errors():
                    child = safe_fs.open_dir(fd, directory)
                os.close(fd)
                fd = child
            with _fs_errors():
                return safe_fs.read_small(fd, name, MAX_FILE_BYTES)
        except FileNotFoundError:
            raise HoldoutLogError("a repository file is missing") from None
        finally:
            os.close(fd)

    def _write_log(self, locked: _Locked, expected: bytes, data: bytes) -> None:
        """Replace HOLDOUT_ACCESS_LOG.md atomically, only if it still holds ``expected``."""
        stage = f".holdout-log-{self._token()}.tmp"
        repo_fd = locked.repo_fd
        try:
            with _fs_errors():
                safe_fs.write_new_file(repo_fd, stage, data)
                fd = safe_fs.open_file(repo_fd, stage)
            try:
                os.fchmod(fd, 0o644)
                os.fsync(fd)
                written = safe_fs.identity(os.fstat(fd))
            finally:
                os.close(fd)
            if self._read_log() != expected:
                raise HoldoutLogIntegrityError("HOLDOUT_ACCESS_LOG.md changed during the update")
            try:
                found = safe_fs.path_identities(self.repo, [])
            except safe_fs.FsIntegrityError:
                raise HoldoutLogIntegrityError("the repository was moved or replaced") from None
            if found != locked.identities[:1]:
                raise HoldoutLogIntegrityError("the repository was moved or replaced")
            os.rename(stage, LOG_PATH, src_dir_fd=repo_fd, dst_dir_fd=repo_fd)
            os.fsync(repo_fd)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(stage, dir_fd=repo_fd)
        self._fault("mirror.written")
        self._require_live([LOG_PATH], [locked.identities[0], written], "HOLDOUT_ACCESS_LOG.md")
        if self._read_log() != data:
            self._latched = True
            raise HoldoutLogIntegrityError("HOLDOUT_ACCESS_LOG.md did not read back exactly")

    def _require_live(
        self, components: list[str], expected: list[safe_fs.Identity], what: str
    ) -> None:
        """After a rename: the configured path must still lead to exactly what was written."""
        try:
            found = safe_fs.path_identities(self.repo, components)
        except safe_fs.FsIntegrityError:
            found = []
        if found != expected:
            self._latched = True
            raise HoldoutLogIntegrityError(
                f"{what} was moved or replaced after it was written; write outcome unknown; "
                "re-verify authoritative state"
            )


# ----- Git history -----


def _verify_git_history(repo: Path, reviewed_legacy: str, legacy: bytes) -> None:
    """Every committed version in HEAD's history, including merges against every parent.

    Once the ledger exists it is never removed and every committed version is a byte-prefix
    of every later one. At each commit the mirror must be exactly the rendering of a prefix
    of that commit's ledger (it may lag after a partial commit, never lead or diverge), and
    the number of events it shows never decreases, so generated history is append-only and
    the fixed and legacy parts stay pinned. Every committed log_initialized must equal the
    fields re-derived from the reviewed legacy bytes. At HEAD itself the mirror must show the
    whole ledger exactly; only past commits may lag. (The working tree is checked separately
    by ``HoldoutLog.state``.)
    """
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise HoldoutLogIntegrityError("holdout history cannot be verified in a shallow clone")
    common = os.fsdecode(
        _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    )
    if os.path.lexists(Path(common) / "info" / "grafts"):
        raise HoldoutLogIntegrityError(
            "holdout history cannot be verified while info/grafts rewrites it"
        )
    graph = [
        line.split()
        for line in _git(repo, "rev-list", "--topo-order", "--parents", "HEAD")
        .decode()
        .splitlines()
    ]
    blobs = {commit: _blob_ids(repo, commit) for commit, *_parents in graph}
    shown: dict[tuple[str, str], int] = {}
    for commit, *parents in reversed(graph):
        ledger_blob, log_blob = blobs[commit]
        parent_blobs = [blobs[parent] for parent in parents if parent in blobs]
        if ledger_blob is None:
            if any(item[0] is not None for item in parent_blobs):
                raise HoldoutLogIntegrityError("a commit removed the holdout ledger")
            continue
        if log_blob is None:
            raise HoldoutLogIntegrityError("a commit has the ledger but no HOLDOUT_ACCESS_LOG.md")
        ledger_bytes = _cat(repo, ledger_blob)
        for parent_ledger, _parent_log in parent_blobs:
            if (
                parent_ledger is not None
                and parent_ledger != ledger_blob
                and not ledger_bytes.startswith(_cat(repo, parent_ledger))
            ):
                raise HoldoutLogIntegrityError(
                    "Git history shows a holdout ledger change that is not append-only"
                )
        key = (ledger_blob, log_blob)
        if key not in shown:
            shown[key] = _shown_events(ledger_bytes, _cat(repo, log_blob), reviewed_legacy, legacy)
        for parent_ledger, parent_log in parent_blobs:
            if (
                parent_ledger is not None
                and parent_log is not None
                and shown[key] < shown[(parent_ledger, parent_log)]
            ):
                raise HoldoutLogIntegrityError(
                    "Git history shows generated HOLDOUT_ACCESS_LOG.md history removed"
                )
    head_ledger, head_log = blobs[graph[0][0]] if graph else (None, None)
    if head_ledger is not None and head_log is not None:
        events = _cat(repo, head_ledger).count(b"\n")
        if shown[(head_ledger, head_log)] != events:
            raise HoldoutLogIntegrityError(
                "HEAD's HOLDOUT_ACCESS_LOG.md does not mirror HEAD's whole ledger; commit the "
                "ledger and its mirror together"
            )


def _shown_events(
    ledger_bytes: bytes, log_bytes: bytes, reviewed_legacy: str, legacy: bytes
) -> int:
    """How many ledger events a committed mirror shows exactly (it may lag, never diverge)."""
    try:
        state = hr.verify_ledger(ledger_bytes)
        if not state.events or state.initialization["legacy_file_sha256"] != reviewed_legacy:
            raise HoldoutRecordError("the ledger does not pin the reviewed legacy log")
        hr.require_initialization(state, legacy)
        if sha256_hex(log_bytes) == reviewed_legacy:
            return 0
        layout = hr.split_mirror(log_bytes, state.initialization)
        lines = ledger_bytes.split(b"\n")[:-1]
        for count in range(len(lines), 0, -1):
            prefix = hr.verify_ledger(b"".join(item + b"\n" for item in lines[:count]))
            if hr.render_log(layout, prefix) == log_bytes:
                return count
        raise HoldoutRecordError("the committed mirror disagrees with the committed ledger")
    except HoldoutRecordError as exc:
        raise HoldoutLogIntegrityError(f"a committed version fails verification: {exc}") from None


def _find_reviewed_legacy(repo: Path, reviewed_legacy: str) -> bytes:
    """The reviewed legacy HOLDOUT_ACCESS_LOG.md from Git history, matched by SHA-256."""
    commits = _git(repo, "log", "--full-history", "--format=%H", "--", LOG_PATH).split()
    seen: set[str] = set()
    for commit in commits:
        listing = _git(repo, "ls-tree", "-z", commit.decode("ascii"), "--", LOG_PATH)
        if not listing:
            continue
        blob = listing.split(b"\t", 1)[0].decode("ascii").split(" ")[2]
        if blob in seen:
            continue
        seen.add(blob)
        data = _cat(repo, blob)
        if sha256_hex(data) == reviewed_legacy:
            return data
    raise HoldoutLogIntegrityError(
        "the reviewed legacy HOLDOUT_ACCESS_LOG.md is not in Git history"
    )


def _blob_ids(repo: Path, commit: str) -> tuple[str | None, str | None]:
    listing = _git(repo, "ls-tree", "-z", commit, "--", LEDGER_PATH, LOG_PATH)
    found: dict[str, str] = {}
    for item in (part for part in listing.split(b"\0") if part):
        meta, _, path = item.partition(b"\t")
        mode, kind, blob = meta.decode("ascii").split(" ")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise HoldoutLogIntegrityError("a committed holdout log path is not a regular file")
        found[path.decode("utf-8", errors="replace")] = blob
    return found.get(LEDGER_PATH), found.get(LOG_PATH)


def _cat(repo: Path, blob: str) -> bytes:
    return _git(repo, "cat-file", "blob", blob)


def _blob_at(repo: Path, commit: str, path: str) -> bytes | None:
    listing = _git(repo, "ls-tree", "-z", commit, "--", path)
    if not listing:
        return None
    meta = listing.split(b"\t", 1)[0].decode("ascii").split(" ")
    if len(meta) != 3 or meta[1] != "blob" or meta[0] not in ("100644", "100755"):
        return None
    return _cat(repo, meta[2])


def _head_blob(repo: Path, path: str) -> bytes | None:
    return _blob_at(repo, "HEAD", path)


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
        raise HoldoutLogIntegrityError("git could not be run") from None
    if completed.returncode != 0:
        raise HoldoutLogIntegrityError("a git command failed")
    return completed.stdout


def _git_ok(repo: Path, *arguments: str) -> bool:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
            ["/usr/bin/git", "-C", str(repo), "--no-optional-locks", *arguments],
            capture_output=True,
            env=_GIT_ENV,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise HoldoutLogIntegrityError("git could not be run") from None
    return completed.returncode == 0


@contextlib.contextmanager
def _fs_errors() -> Iterator[None]:
    try:
        yield
    except (safe_fs.FsIntegrityError, safe_fs.FsUnsupportedError) as exc:
        raise HoldoutLogIntegrityError(str(exc)) from None


def _split_legacy(data: bytes) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    try:
        return hr.split_legacy_file(data)
    except HoldoutRecordError as exc:
        raise HoldoutLogIntegrityError(str(exc)) from None


def _event_ref(state: LogState, event_id: str) -> dict[str, object]:
    event = state.by_id(event_id)
    if event is None:
        raise HoldoutLogError("the referenced event does not exist")
    return {"entry_sha256": event.sha256, "event_id": event.event_id}


def _attestation(role: ActorRole, attested: bool) -> dict[str, object]:
    return {"attested": attested, "role": ActorRole(role).value}


# ----- command line -----


def status_lines(state: LogState | None) -> list[str]:
    if state is None:
        return ["holdout log: not initialized (HOLDOUT_ACCESS_LOG.md is the reviewed legacy file)"]
    lines = [f"holdout log: {len(state.events)} event(s), last {state.events[-1].event_id}"]
    for holdout in state.holdouts.values():
        condition = (
            "untouched" if holdout.consumed_by is None else f"CONSUMED ({holdout.consumed_by})"
        )
        if holdout.historical_by:
            condition += f", historical ({holdout.historical_by})"
        lines.append(f"holdout {holdout.holdout_id} cycle {holdout.cycle_id}: {condition}")
    for start in state.starts.values():
        closed = start.closed_by or "OPEN — outcome unrecorded; holdout consumed"
        lines.append(f"access {start.event_id}: closed by {closed}")
    return lines


_ACTIONS: Final = {
    "register_cycle": {
        "cycle_id",
        "split_formation",
        "development_subset",
        "protected_start",
        "protected_end",
        "attested",
    },
    "register_holdout": {
        "holdout_id",
        "cycle_id",
        "split_definition",
        "snapshot_manifest_sha256",
        "metadata_sha256",
        "observation_count",
        "start",
        "end",
        "purge_embargo_sha256",
        "source_manifest_sha256",
        "attested",
    },
    "request_access": {"cycle_id", "holdout_id", "candidate_id", "components", "requested_by"},
    "authorize": {"request", "gate_6", "attested"},
    "deny": {"request", "reason", "attested"},
    "start": {"authorization", "gate_7", "operator", "attested"},
    "finish": {"started", "outcome", "recorded_by", "reason", "restricted_evidence_sha256"},
    "record_contamination": {
        "holdout_id",
        "level",
        "exposure_categories",
        "exposed_roles",
        "restricted_evidence_sha256",
        "attested",
    },
    "reclassify": {"holdout_id", "untouched_holdout_id", "attested"},
    "correct": {"corrects", "document", "attested"},
}


def run_action(log: HoldoutLog, document: object) -> hr.Event:
    """Run one closed JSON action (the ``record`` command's input)."""
    if not isinstance(document, dict) or set(document) != {"action", "arguments"}:
        raise HoldoutLogError("an action request has exactly the fields action and arguments")
    action, arguments = document["action"], document["arguments"]
    if (
        action not in _ACTIONS
        or not isinstance(arguments, dict)
        or set(arguments) != _ACTIONS[action]
    ):
        raise HoldoutLogError("the action or its arguments do not match the v1 request schema")
    a = arguments
    try:
        if action == "register_cycle":
            return log.register_cycle(
                _s(a["cycle_id"]),
                SplitFormation(_s(a["split_formation"])),
                _file(a["development_subset"]),
                _time(a["protected_start"]),
                _time(a["protected_end"]),
                attested=_b(a["attested"]),
            )
        if action == "register_holdout":
            return log.register_holdout(
                _s(a["holdout_id"]),
                _s(a["cycle_id"]),
                _file(a["split_definition"]),
                snapshot_manifest_sha256=_s(a["snapshot_manifest_sha256"]),
                metadata_sha256=_s(a["metadata_sha256"]),
                observation_count=_i(a["observation_count"]),
                start=_time(a["start"]),
                end=_time(a["end"]),
                purge_embargo_sha256=_s(a["purge_embargo_sha256"]),
                source_manifest_sha256=_s(a["source_manifest_sha256"]),
                attested=_b(a["attested"]),
            )
        if action == "request_access":
            components = a["components"]
            if not isinstance(components, dict):
                raise HoldoutLogError("components must be an object")
            spec = CandidateSpec(
                _s(a["cycle_id"]),
                _s(a["holdout_id"]),
                _s(a["candidate_id"]),
                {Component(key): [dict(ref) for ref in value] for key, value in components.items()},
            )
            return log.request_access(spec, ActorRole(_s(a["requested_by"])))
        if action == "authorize":
            return log.authorize(_s(a["request"]), _record(a["gate_6"]), attested=_b(a["attested"]))
        if action == "deny":
            return log.deny(
                _s(a["request"]), DenialReason(_s(a["reason"])), attested=_b(a["attested"])
            )
        if action == "start":
            return log.start(
                _s(a["authorization"]),
                _record(a["gate_7"]),
                operator=ActorRole(_s(a["operator"])),
                attested=_b(a["attested"]),
            )
        if action == "finish":
            outcome = EventType(_s(a["outcome"]))
            reason_text = a["reason"]
            reason: FailureReason | InterruptReason | None = None
            if reason_text is not None:
                reason = (
                    InterruptReason(_s(reason_text))
                    if outcome is EventType.ACCESS_INTERRUPTED
                    else FailureReason(_s(reason_text))
                )
            evidence = a["restricted_evidence_sha256"]
            return log.finish(
                _s(a["started"]),
                outcome,
                recorded_by=ActorRole(_s(a["recorded_by"])),
                reason=reason,
                restricted_evidence_sha256=None if evidence is None else _s(evidence),
            )
        if action == "record_contamination":
            evidence = a["restricted_evidence_sha256"]
            return log.record_contamination(
                _s(a["holdout_id"]),
                ContaminationLevel(_s(a["level"])),
                [ExposureCategory(_s(item)) for item in _l(a["exposure_categories"])],
                [ActorRole(_s(item)) for item in _l(a["exposed_roles"])],
                restricted_evidence_sha256=None if evidence is None else _s(evidence),
                attested=_b(a["attested"]),
            )
        if action == "reclassify":
            return log.reclassify(
                _s(a["holdout_id"]), _s(a["untouched_holdout_id"]), attested=_b(a["attested"])
            )
        return log.correct(_s(a["corrects"]), _file(a["document"]), attested=_b(a["attested"]))
    except HoldoutRecordError:
        raise
    except (KeyError, TypeError, ValueError):
        # Never echo caller-supplied values (an Enum ValueError repeats the bad input).
        raise HoldoutLogError(
            "the action arguments are malformed or use an unknown value"
        ) from None


def _s(value: object) -> str:
    if not isinstance(value, str):
        raise HoldoutLogError("an action argument must be a string")
    return value


def _b(value: object) -> bool:
    if not isinstance(value, bool):
        raise HoldoutLogError("an action argument must be a boolean")
    return value


def _i(value: object) -> int:
    if type(value) is not int:
        raise HoldoutLogError("an action argument must be an integer")
    return value


def _l(value: object) -> list[object]:
    if not isinstance(value, list):
        raise HoldoutLogError("an action argument must be a list")
    return value


def _file(value: object) -> FileRef:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise HoldoutLogError("a file reference has exactly path and sha256")
    return FileRef(_s(value["path"]), _s(value["sha256"]))


def _record(value: object) -> RecordRef:
    if not isinstance(value, dict) or set(value) != {"record_id", "record_sha256"}:
        raise HoldoutLogError("a gate record reference has exactly record_id and record_sha256")
    return RecordRef(_s(value["record_id"]), _s(value["record_sha256"]))


def _time(value: object) -> datetime:
    text = _s(value)
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        raise HoldoutLogError("a timestamp must be YYYY-MM-DDTHH:MM:SS.ffffffZ") from None


def _load_json(path: Path) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise HoldoutLogError("the request has duplicate keys")
            result[key] = value
        return result

    def no_floats(_text: str) -> object:
        raise HoldoutLogError("the request must not contain floats")

    try:
        return json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=no_floats,
            parse_constant=no_floats,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HoldoutLogError("the request is not valid JSON") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pmv.holdout_log", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify", help="verify the ledger and its exact Markdown mirror")
    commands.add_parser("verify-history", help="also verify every committed version")
    commands.add_parser("status", help="print the derived holdout and access status")
    commands.add_parser("mirror", help="bring HOLDOUT_ACCESS_LOG.md forward to the ledger")
    commands.add_parser("initialize", help="create HAL-0005 (log_initialized); once only")
    ready = commands.add_parser("assert-started-committed", help="the pre-reveal check")
    ready.add_argument("event_id")
    record = commands.add_parser("record", help="append one event from a closed JSON request")
    record.add_argument("--request", type=Path, required=True)
    record.add_argument("--config", type=Path, required=True)
    record.add_argument(
        "--environment", choices=[item.value for item in Environment], required=True
    )
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "record":
            _record_from_cli(arguments)
            return 0
        log = HoldoutLog(arguments.repo)
        if arguments.command == "verify":
            sys.stdout.write("\n".join(status_lines(log.state())) + "\nverified\n")
        elif arguments.command == "verify-history":
            sys.stdout.write("\n".join(status_lines(log.verify_history())) + "\nhistory verified\n")
        elif arguments.command == "status":
            sys.stdout.write("\n".join(status_lines(log.state())) + "\n")
        elif arguments.command == "mirror":
            sys.stdout.write(f"mirror: {log.mirror()} event(s) added\n")
        elif arguments.command == "initialize":
            event = log.initialize()
            sys.stdout.write(f"initialized: {event.event_id} {event.sha256}\n")
        else:
            report = log.assert_started_committed(arguments.event_id)
            sys.stdout.write(
                f"ready: {report.started_event_id} holdout {report.holdout_id} "
                f"at {report.head_commit}\n"
            )
    except (
        HoldoutLogError,
        HoldoutRecordError,
        GateError,
        GateRecordError,
        ExperimentError,
        RefusedTestEnvironmentError,
    ) as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 1
    except ConfigError:
        sys.stderr.write("ConfigError: the configuration could not be loaded or is invalid\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"OSError: {errno.errorcode.get(exc.errno or 0, 'unknown')}\n")
        return 1
    return 0


def _record_from_cli(arguments: argparse.Namespace) -> None:
    refuse_test_environment(Environment(arguments.environment), "pmv.holdout_log record")
    document = _load_json(arguments.request)
    config = load_config(arguments.config, Environment(arguments.environment))
    repo = Path(os.path.realpath(arguments.repo))
    with contextlib.ExitStack() as stack:
        store = None
        if config.experiments.root is not None:
            store = stack.enter_context(
                ExperimentStore(
                    config.experiments.root,
                    repo_root=repo,
                    app_config_sha256=config.source_sha256,
                    raw_root=config.raw_storage.root,
                )
            )
        event = run_action(HoldoutLog(repo, experiment_store=store), document)
    sys.stdout.write(
        f"recorded {event.event_id} ({event.event_type.value}) {event.sha256}\n"
        "Commit the ledger and HOLDOUT_ACCESS_LOG.md promptly; the tool never commits.\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
