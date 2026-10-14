"""The authoritative experiment ledger: verification, run state, and evidence eligibility.

Pure functions over ledger bytes; no filesystem access. Every entry is one canonical JSON
line with ``ledger_seq`` (from 0, +1), ``prev_entry_sha256`` (null first), and
``entry_sha256`` (SHA-256 of the canonical entry without that field). Entry 0 is always
the ``ledger_created`` genesis entry, and only entry 0 may be. Verification checks
encoding, the closed schema of every event type, sequence continuity, every hash and
link, and every run's state transitions, recomputes the start-time policy fields, and
rebuilds every completed run's manifest to check its recorded hash.

Entry versions: v1 entries (Step 6) are verified exactly as originally defined: their
``run_started`` carries a v1 execution identity (null environment fingerprint, never
eligible) and ``run_failed`` uses only the v1 failure codes. v2 entries (Step 10) carry a v2
execution identity, may record ``environment_changed``, and a clean ``evidence_candidate``
start must carry an environment fingerprint. Writers emit v2. Versions never go backwards:
once a v2 entry appears, a later v1 entry is refused.

Tamper evidence: this detects altered, reordered, duplicated, malformed, and interior-
deleted entries and broken links. It cannot detect complete entries removed from the end
unless a checkpoint anchors a later head; checkpoints are verified when supplied.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from pmv.experiment_spec import (
    EXCEPTION_TYPE,
    IDENTITY_V2,
    MAX_SPEC_BYTES,
    V1_FAILURE_CODES,
    AbortReason,
    ArtifactType,
    ExecutionIdentity,
    FailureCode,
    MediaType,
    RunArtifactInput,
    RunClass,
    SpecError,
    SupersedeReason,
    WarningCode,
    parse_execution_identity,
    parse_input,
    require_artifact_name,
    require_identifier,
    require_run_id,
    require_split,
    validate_metric_value,
)
from pmv.integrity import (
    FormatError,
    canonical_line,
    chain_entry_sha256,
    is_int,
    is_non_negative_int,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
    sha256_hex,
)

ENTRY_SCHEMA: Final = "pmv.experiment.ledger_entry"
CHECKPOINT_SCHEMA: Final = "pmv.experiment.ledger_checkpoint"
MANIFEST_SCHEMA: Final = "pmv.experiment.run_manifest"
ENTRY_V1: Final = 1
ENTRY_V2: Final = 2
ENTRY_VERSIONS: Final = (ENTRY_V1, ENTRY_V2)
ENTRY_WRITE_VERSION: Final = ENTRY_V2  # the entry version writers emit
SCHEMA_VERSION: Final = 1  # the run manifest and checkpoint formats (unchanged in Step 10)
_STORE_ID: Final = re.compile(r"[0-9a-f]{32}")
PENDING_MARKER_PREFIX: Final = "repair-pending-"
_EVIDENCE_NAME: Final = re.compile(
    r"torn-(0|[1-9][0-9]*)-([1-9][0-9]*)-([1-9][0-9]*)-(none|0|[1-9][0-9]*)"
    r"-(none|[0-9a-f]{64})-([0-9a-f]{64})\.bin"
)


class LedgerError(Exception):
    """The ledger, a checkpoint, or repair evidence fails verification."""


class TornTailError(LedgerError):
    """The ledger ends with an incomplete entry starting at ``offset``."""

    def __init__(self, offset: int) -> None:
        super().__init__(
            "the experiment ledger ends with an incomplete entry; appends are refused until "
            "repair_torn_tail() preserves and removes it"
        )
        self.offset = offset


class PendingRepairError(LedgerError):
    """Repair evidence exists that no ledger_tail_repaired event references yet."""


class LedgerEvent(StrEnum):
    LEDGER_CREATED = "ledger_created"
    RUN_RESERVED = "run_reserved"
    RUN_STARTED = "run_started"
    ARTIFACT_REGISTERED = "artifact_registered"
    METRIC_RECORDED = "metric_recorded"
    WARNING_RECORDED = "warning_recorded"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_ABORTED = "run_aborted"
    RUN_INTERRUPTED = "run_interrupted"
    RUN_SUPERSEDED = "run_superseded"
    LEDGER_TAIL_REPAIRED = "ledger_tail_repaired"


class RunState(StrEnum):
    RESERVED = "reserved"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    INTERRUPTED = "interrupted"


TERMINAL_STATES: Final = frozenset(
    {RunState.COMPLETED, RunState.FAILED, RunState.ABORTED, RunState.INTERRUPTED}
)
_ENVELOPE: Final = frozenset(
    {
        "schema",
        "schema_version",
        "ledger_seq",
        "prev_entry_sha256",
        "entry_sha256",
        "event_type",
        "run_id",
        "recorded_at",
    }
)
_FIELDS: Final[Mapping[LedgerEvent, frozenset[str]]] = {
    LedgerEvent.LEDGER_CREATED: frozenset({"store_id"}),
    LedgerEvent.RUN_RESERVED: frozenset({"study_id", "run_class"}),
    LedgerEvent.RUN_STARTED: frozenset(
        {
            "spec_sha256",
            "spec_size_bytes",
            "execution_identity",
            "execution_identity_sha256",
            "effective_run_class_at_start",
            "evidence_eligible_at_start",
            "inputs",
        }
    ),
    LedgerEvent.ARTIFACT_REGISTERED: frozenset(
        {
            "name",
            "artifact_type",
            "media_type",
            "size_bytes",
            "sha256",
            "artifact_schema_id",
            "artifact_schema_version",
        }
    ),
    LedgerEvent.METRIC_RECORDED: frozenset({"name", "split", "value", "unit", "fold", "step"}),
    LedgerEvent.WARNING_RECORDED: frozenset({"code", "context"}),
    LedgerEvent.RUN_COMPLETED: frozenset({"manifest_sha256", "artifact_count", "metric_count"}),
    LedgerEvent.RUN_FAILED: frozenset({"failure_code", "exception_type"}),
    LedgerEvent.RUN_ABORTED: frozenset({"reason"}),
    LedgerEvent.RUN_INTERRUPTED: frozenset({"last_state"}),
    LedgerEvent.RUN_SUPERSEDED: frozenset({"superseded_by", "reason"}),
    LedgerEvent.LEDGER_TAIL_REPAIRED: frozenset(
        {
            "repair_evidence_name",
            "torn_byte_offset",
            "torn_byte_length",
            "torn_sha256",
            "original_ledger_size",
            "last_valid_ledger_seq",
            "last_valid_entry_sha256",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class Entry:
    seq: int
    prev_sha256: str | None
    sha256: str
    event_type: LedgerEvent
    run_id: str | None
    recorded_at: str
    fields: Mapping[str, object]
    start: int
    end: int
    version: int = ENTRY_V1


@dataclass(slots=True)
class RunRecord:
    run_id: str
    study_id: str
    requested_class: RunClass
    reserved_seq: int
    state: RunState = RunState.RESERVED
    started_seq: int | None = None
    start_fields: Mapping[str, object] = field(default_factory=dict)
    identity: ExecutionIdentity | None = None
    eligible_at_start: bool = False
    inputs: list[Mapping[str, object]] = field(default_factory=list)
    artifacts: dict[str, tuple[Mapping[str, object], int]] = field(default_factory=dict)
    metrics: list[tuple[int, Mapping[str, object]]] = field(default_factory=list)
    warnings: list[tuple[int, Mapping[str, object]]] = field(default_factory=list)
    last_event_seq: int = 0
    preterminal_seq: int | None = None
    terminal_seq: int | None = None
    completed_seq: int | None = None
    manifest_sha256: str | None = None
    superseded_seq: int | None = None
    superseded_by: str | None = None


@dataclass(slots=True)
class LedgerState:
    entries: list[Entry] = field(default_factory=list)
    runs: dict[str, RunRecord] = field(default_factory=dict)
    repairs: dict[str, Entry] = field(default_factory=dict)
    size: int = 0
    version: int = ENTRY_V1  # the highest entry version seen so far

    @property
    def head_seq(self) -> int:
        return len(self.entries) - 1

    @property
    def head_sha256(self) -> str | None:
        return self.entries[-1].sha256 if self.entries else None


@dataclass(frozen=True, slots=True)
class Checkpoint:
    ledger_seq: int
    entry_sha256: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class EvidenceFile:
    """A repair-evidence file, described by its name and its actual content."""

    name: str
    length: int
    sha256: str


def verify_ledger(data: bytes, *, allow_torn_tail: bool = False) -> tuple[LedgerState, int | None]:
    """Fully verify ledger bytes from byte 0.

    Returns the state of every complete entry and, if ``allow_torn_tail``, the offset of
    an incomplete final entry (else None). A malformed complete line is never treated as a
    torn tail.
    """
    state = LedgerState()
    offset = 0
    torn: int | None = None
    while offset < len(data):
        newline = data.find(b"\n", offset)
        if newline == -1:
            torn = offset
            break
        entry = _parse_entry(data[offset:newline], state, offset, newline + 1)
        _apply(state, entry)
        offset = newline + 1
    state.size = offset
    if torn is not None and not allow_torn_tail:
        raise TornTailError(torn)
    return state, torn


def encode_entry(
    state: LedgerState,
    event_type: LedgerEvent,
    run_id: str | None,
    recorded_at: str,
    fields: Mapping[str, object],
    *,
    version: int = ENTRY_WRITE_VERSION,
) -> bytes:
    """Build the next canonical ledger line on top of ``state`` (writers use v2)."""
    body: dict[str, object] = {
        "event_type": event_type.value,
        "ledger_seq": state.head_seq + 1,
        "prev_entry_sha256": state.head_sha256,
        "recorded_at": recorded_at,
        "run_id": run_id,
        "schema": ENTRY_SCHEMA,
        "schema_version": version,
        **fields,
    }
    return canonical_line({**body, "entry_sha256": chain_entry_sha256(body)})


def effective_run_class(requested: RunClass, identity: ExecutionIdentity) -> RunClass:
    """Dirty-tree policy C: unknown or dirty code, or no uv.lock identity, is exploratory."""
    return requested if identity.code_is_clean() else RunClass.EXPLORATORY


def start_eligibility(
    state: LedgerState,
    before_seq: int,
    effective: RunClass,
    identity: ExecutionIdentity,
    inputs: Sequence[Mapping[str, object]],
) -> bool:
    """Evidence eligibility at start, from the ledger prefix up to ``before_seq``.

    Requires an evidence_candidate class, an installed-environment fingerprint, raw
    captures produced by clean code, and run-artifact producers that are evidence-eligible
    as of the same prefix. A v1 ExecutionIdentity cannot carry a fingerprint (Option B), so
    this is always false for v1 entries; a v2 identity can.
    """
    return _eligible_at_start(
        state,
        before_seq,
        effective,
        environment_fingerprinted=identity.installed_environment_sha256 is not None,
        inputs=inputs,
    )


def _eligible_at_start(
    state: LedgerState,
    before_seq: int,
    effective: RunClass,
    *,
    environment_fingerprinted: bool,
    inputs: Sequence[Mapping[str, object]],
) -> bool:
    """The start-eligibility rules as a pure function."""
    if effective is not RunClass.EVIDENCE_CANDIDATE or not environment_fingerprinted:
        return False
    for item in inputs:
        if item["kind"] == "raw_capture":
            if item["capture_code_clean"] is not True:
                return False
        elif not eligibility_as_of(state, str(item["run_id"]), before_seq):
            return False
    return True


def eligibility_as_of(state: LedgerState, run_id: str, seq: int) -> bool:
    """Whether ``run_id`` and its transitive run-artifact inputs are evidence-eligible as of
    ledger sequence ``seq``. Later supersession changes this; it never changes history."""
    run = state.runs.get(run_id)
    if run is None or not run.eligible_at_start:
        return False
    if run.completed_seq is None or run.completed_seq > seq:
        return False
    if run.superseded_seq is not None and run.superseded_seq <= seq:
        return False
    return all(
        eligibility_as_of(state, str(item["run_id"]), seq)
        for item in run.inputs
        if item["kind"] == "run_artifact"
    )


def completion_manifest_bytes(state: LedgerState, run_id: str) -> bytes:
    """The pre-terminal completion manifest: built only from events before run_completed."""
    run = state.runs.get(run_id)
    if run is None or run.identity is None or run.started_seq is None:
        raise LedgerError("the run has not started")
    if run.state is RunState.STARTED:
        last_seq = run.last_event_seq
    elif run.state is RunState.COMPLETED and run.preterminal_seq is not None:
        last_seq = run.preterminal_seq
    else:
        raise LedgerError("only a started or completed run has a completion manifest")
    document: dict[str, object] = {
        "artifacts": [
            {**dict(item), "ledger_seq": seq}
            for item, seq in sorted(run.artifacts.values(), key=lambda pair: pair[1])
        ],
        "effective_run_class_at_start": run.start_fields["effective_run_class_at_start"],
        "evidence_eligible_at_start": run.eligible_at_start,
        "execution_identity": run.identity.to_json(),
        "execution_identity_sha256": run.start_fields["execution_identity_sha256"],
        "inputs": [dict(item) for item in run.inputs],
        "last_preterminal_entry_sha256": state.entries[last_seq].sha256,
        "ledger_seq_last_preterminal": last_seq,
        "ledger_seq_start": run.reserved_seq,
        "metrics": [{**dict(item), "ledger_seq": seq} for seq, item in run.metrics],
        "requested_run_class": run.requested_class.value,
        "run_id": run.run_id,
        "schema": MANIFEST_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "spec_sha256": run.start_fields["spec_sha256"],
        "study_id": run.study_id,
        "terminal_state": RunState.COMPLETED.value,
        "warnings": [{**dict(item), "ledger_seq": seq} for seq, item in run.warnings],
    }
    return canonical_line(document)


def checkpoint_line(ledger_seq: int, entry_sha256: str, recorded_at: str) -> bytes:
    return canonical_line(
        {
            "entry_sha256": entry_sha256,
            "ledger_seq": ledger_seq,
            "recorded_at": recorded_at,
            "schema": CHECKPOINT_SCHEMA,
            "schema_version": SCHEMA_VERSION,
        }
    )


def parse_checkpoints(data: bytes) -> list[Checkpoint]:
    """Parse the checkpoint file: canonical lines with strictly increasing ledger_seq."""
    if data and not data.endswith(b"\n"):
        raise LedgerError("the checkpoint file ends with an incomplete line")
    checkpoints: list[Checkpoint] = []
    for number, line in enumerate(data.split(b"\n")[:-1] if data else [], start=1):
        try:
            document = parse_canonical_json(line)
        except FormatError:
            raise LedgerError(f"checkpoint line {number} is not canonical JSON") from None
        keys = {"entry_sha256", "ledger_seq", "recorded_at", "schema", "schema_version"}
        seq = document.get("ledger_seq")
        if (
            set(document) != keys
            or document["schema"] != CHECKPOINT_SCHEMA
            or not is_int(document["schema_version"])
            or document["schema_version"] != SCHEMA_VERSION
            or not is_non_negative_int(seq)
            or not is_sha256(document["entry_sha256"])
            or not is_timestamp(document["recorded_at"])
        ):
            raise LedgerError(f"checkpoint line {number} does not match the v1 schema")
        if checkpoints and seq <= checkpoints[-1].ledger_seq:
            raise LedgerError(f"checkpoint line {number} does not increase ledger_seq")
        digest, recorded = document["entry_sha256"], document["recorded_at"]
        if not isinstance(digest, str) or not isinstance(recorded, str):
            raise LedgerError(f"checkpoint line {number} does not match the v1 schema")
        checkpoints.append(Checkpoint(seq, digest, recorded))
    return checkpoints


def verify_checkpoints(state: LedgerState, checkpoints: Sequence[Checkpoint]) -> None:
    """Every checkpoint must name an existing entry with exactly that hash."""
    for checkpoint in checkpoints:
        if checkpoint.ledger_seq > state.head_seq:
            raise LedgerError(
                f"checkpoint {checkpoint.ledger_seq} is beyond the verified ledger head; "
                "entries may have been removed"
            )
        if state.entries[checkpoint.ledger_seq].sha256 != checkpoint.entry_sha256:
            raise LedgerError(f"checkpoint {checkpoint.ledger_seq} does not match the ledger")


def evidence_name(
    *,
    offset: int,
    length: int,
    original_size: int,
    last_seq: int | None,
    last_sha256: str | None,
    torn_sha256: str,
) -> str:
    """The permanent repair-evidence name, binding every fact about the torn region."""
    seq = "none" if last_seq is None else str(last_seq)
    sha = "none" if last_sha256 is None else last_sha256
    return f"torn-{offset}-{length}-{original_size}-{seq}-{sha}-{torn_sha256}.bin"


def parse_evidence_name(name: str) -> dict[str, object] | None:
    match = _EVIDENCE_NAME.fullmatch(name)
    if match is None:
        return None
    offset, length, original = int(match[1]), int(match[2]), int(match[3])
    return {
        "torn_byte_offset": offset,
        "torn_byte_length": length,
        "original_ledger_size": original,
        "last_valid_ledger_seq": None if match[4] == "none" else int(match[4]),
        "last_valid_entry_sha256": None if match[5] == "none" else match[5],
        "torn_sha256": match[6],
    }


def is_store_id(value: object) -> bool:
    """A permanent experiment-store identity: 32 lowercase hex characters (128 bits)."""
    return isinstance(value, str) and _STORE_ID.fullmatch(value) is not None


def store_id_of(state: LedgerState) -> str:
    """The store identity bound by the ledger_created genesis entry."""
    if not state.entries:
        raise LedgerError("the ledger has no ledger_created entry")
    return str(state.entries[0].fields["store_id"])


def pending_marker_name(store_id: str, evidence: str) -> str:
    """The pending-repair marker for ``evidence``, bound to the store identity."""
    return f"{PENDING_MARKER_PREFIX}{store_id}-{evidence}"


def parse_pending_marker_name(name: str) -> tuple[str, str] | None:
    """Return (store_id, evidence name) for a pending-repair marker name, else None."""
    if not name.startswith(PENDING_MARKER_PREFIX):
        return None
    rest = name[len(PENDING_MARKER_PREFIX) :]
    store_id, separator, evidence = rest[:32], rest[32:33], rest[33:]
    if not is_store_id(store_id) or separator != "-" or parse_evidence_name(evidence) is None:
        return None
    return store_id, evidence


def pending_evidence(state: LedgerState, evidence: Sequence[EvidenceFile]) -> list[EvidenceFile]:
    """Check repair evidence against the ledger; return evidence not yet referenced.

    Every referenced evidence file must exist with exactly the recorded length and hash,
    and every evidence file's name must agree with its content.
    """
    by_name = {item.name: item for item in evidence}
    for name in state.repairs:
        if name not in by_name:
            raise LedgerError("referenced repair evidence is missing")
    pending: list[EvidenceFile] = []
    for item in evidence:
        facts = parse_evidence_name(item.name)
        if facts is None:
            raise LedgerError("an unexpected file is in the repair-evidence directory")
        if facts["torn_byte_length"] != item.length or facts["torn_sha256"] != item.sha256:
            raise LedgerError("repair evidence content does not match its name")
        entry = state.repairs.get(item.name)
        if entry is None:
            pending.append(item)
            continue
        recorded = {key: entry.fields[key] for key in facts}
        if recorded != facts:
            raise LedgerError("repair evidence does not match its ledger_tail_repaired event")
    return sorted(pending, key=lambda item: item.name)


def check_pending_matches_head(state: LedgerState, item: EvidenceFile) -> None:
    """Pending evidence is consistent if the ledger was truncated exactly at its offset.

    The entry it names as last valid must end at the torn offset, and only repair events
    may follow that entry.
    """
    facts = parse_evidence_name(item.name)
    if facts is None:
        raise LedgerError("an unexpected file is in the repair-evidence directory")
    _check_repair_position(state, facts, len(state.entries))


# ----- internals -----


def _parse_entry(line: bytes, state: LedgerState, start: int, end: int) -> Entry:
    number = len(state.entries) + 1
    try:
        document = parse_canonical_json(line)
    except FormatError:
        raise LedgerError(f"ledger line {number} is not canonical JSON") from None
    raw_type = document.get("event_type")
    try:
        event_type = LedgerEvent(raw_type) if isinstance(raw_type, str) else None
    except ValueError:
        event_type = None
    if event_type is None or set(document) != _ENVELOPE | _FIELDS[event_type]:
        raise LedgerError(f"ledger line {number} does not match the entry schema")
    version = document["schema_version"]
    if document["schema"] != ENTRY_SCHEMA or not is_int(version) or version not in ENTRY_VERSIONS:
        raise LedgerError(f"ledger line {number} has an unsupported schema")
    if version < state.version:
        raise LedgerError(f"ledger line {number}: entry versions must not go backwards")
    if (event_type is LedgerEvent.LEDGER_CREATED) != (not state.entries):
        raise LedgerError(f"ledger line {number}: only the first entry is ledger_created")
    seq = document["ledger_seq"]
    if not is_int(seq) or seq != len(state.entries):
        raise LedgerError(f"ledger line {number} breaks ledger_seq continuity")
    if document["prev_entry_sha256"] != state.head_sha256:
        raise LedgerError(f"ledger line {number} breaks the hash chain")
    digest = document["entry_sha256"]
    body = {key: value for key, value in document.items() if key != "entry_sha256"}
    if not is_sha256(digest) or chain_entry_sha256(body) != digest:
        raise LedgerError(f"ledger line {number} has an invalid entry_sha256")
    recorded_at = document["recorded_at"]
    if not is_timestamp(recorded_at):
        raise LedgerError(f"ledger line {number} has an invalid recorded_at")
    run_id = document["run_id"]
    if event_type in (LedgerEvent.LEDGER_CREATED, LedgerEvent.LEDGER_TAIL_REPAIRED):
        if run_id is not None:
            raise LedgerError(f"ledger line {number}: {event_type.value} has no run_id")
    else:
        try:
            require_run_id(run_id)
        except SpecError:
            raise LedgerError(f"ledger line {number} has a malformed run_id") from None
    fields = {key: document[key] for key in _FIELDS[event_type]}
    return Entry(
        seq=len(state.entries),
        prev_sha256=state.head_sha256,
        sha256=digest,
        event_type=event_type,
        run_id=run_id if isinstance(run_id, str) else None,
        recorded_at=recorded_at,
        fields=fields,
        start=start,
        end=end,
        version=version,
    )


def _apply(state: LedgerState, entry: Entry) -> None:
    where = f"ledger entry {entry.seq}"
    try:
        _APPLY[entry.event_type](state, entry)
    except SpecError as exc:
        raise LedgerError(f"{where}: {exc}") from None
    except (KeyError, TypeError, ValueError):
        raise LedgerError(f"{where} has malformed fields") from None
    state.entries.append(entry)
    state.version = max(state.version, entry.version)
    if entry.run_id is not None and entry.run_id in state.runs:
        run = state.runs[entry.run_id]
        if entry.event_type is not LedgerEvent.RUN_SUPERSEDED:
            run.last_event_seq = entry.seq


def _run(state: LedgerState, entry: Entry, *allowed: RunState) -> RunRecord:
    run = state.runs.get(entry.run_id or "")
    if run is None:
        raise LedgerError(f"ledger entry {entry.seq} refers to an unknown run")
    if run.state not in allowed:
        raise LedgerError(
            f"ledger entry {entry.seq}: {entry.event_type.value} is not allowed for a "
            f"{run.state.value} run"
        )
    return run


def _apply_reserved(state: LedgerState, entry: Entry) -> None:
    if entry.run_id is None or entry.run_id in state.runs:
        raise LedgerError(f"ledger entry {entry.seq} reserves a run ID that already exists")
    state.runs[entry.run_id] = RunRecord(
        run_id=entry.run_id,
        study_id=require_identifier(entry.fields["study_id"], "study_id"),
        requested_class=RunClass(str(entry.fields["run_class"])),
        reserved_seq=entry.seq,
        last_event_seq=entry.seq,
    )


def _apply_started(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.RESERVED)
    fields = entry.fields
    identity = parse_execution_identity(fields["execution_identity"])
    if identity.version != entry.version:
        raise LedgerError(
            f"ledger entry {entry.seq}: the execution identity version must match the entry"
        )
    if identity.sha256() != fields["execution_identity_sha256"]:
        raise LedgerError(f"ledger entry {entry.seq}: execution_identity_sha256 does not match")
    if identity.spec_sha256 != fields["spec_sha256"]:
        raise LedgerError(f"ledger entry {entry.seq}: spec_sha256 does not match the identity")
    size = fields["spec_size_bytes"]
    if not is_int(size) or not 0 < size <= MAX_SPEC_BYTES:
        raise LedgerError(f"ledger entry {entry.seq}: spec_size_bytes is invalid")
    inputs = fields["inputs"]
    if not isinstance(inputs, list):
        raise LedgerError(f"ledger entry {entry.seq}: inputs must be a list")
    resolved: list[Mapping[str, object]] = []
    for item in inputs:
        resolved.append(_resolved_input(state, entry, item))
    if len({canonical_line(dict(item)) for item in resolved}) != len(resolved):
        raise LedgerError(f"ledger entry {entry.seq}: inputs must not repeat")
    effective = effective_run_class(run.requested_class, identity)
    if (
        effective is RunClass.EVIDENCE_CANDIDATE
        and identity.version == IDENTITY_V2
        and identity.installed_environment_sha256 is None
    ):
        raise LedgerError(
            f"ledger entry {entry.seq}: an evidence_candidate start requires an "
            "environment fingerprint"
        )
    eligible = start_eligibility(state, entry.seq - 1, effective, identity, resolved)
    if fields["effective_run_class_at_start"] != effective.value:
        raise LedgerError(f"ledger entry {entry.seq}: effective_run_class_at_start is wrong")
    if fields["evidence_eligible_at_start"] is not eligible:
        raise LedgerError(f"ledger entry {entry.seq}: evidence_eligible_at_start is wrong")
    run.state = RunState.STARTED
    run.started_seq = entry.seq
    run.start_fields = fields
    run.identity = identity
    run.eligible_at_start = eligible
    run.inputs = resolved


def _resolved_input(state: LedgerState, entry: Entry, item: object) -> Mapping[str, object]:
    if not isinstance(item, Mapping):
        raise LedgerError(f"ledger entry {entry.seq}: an input is malformed")
    if item.get("kind") == "raw_capture":
        if set(item) != {"kind", "capture_id", "manifest_sha256", "capture_code_clean"}:
            raise LedgerError(f"ledger entry {entry.seq}: a raw_capture input is malformed")
        if not isinstance(item["capture_code_clean"], bool):
            raise LedgerError(f"ledger entry {entry.seq}: capture_code_clean must be a bool")
        parse_input({key: value for key, value in item.items() if key != "capture_code_clean"})
        return item
    if not isinstance(parse_input(item), RunArtifactInput):
        raise LedgerError(f"ledger entry {entry.seq}: an input is malformed")
    producer = state.runs.get(str(item["run_id"]))
    if producer is None or producer.state is not RunState.COMPLETED:
        raise LedgerError(
            f"ledger entry {entry.seq}: a run_artifact input's producer is not completed"
        )
    artifact = producer.artifacts.get(str(item["artifact_name"]))
    if artifact is None or artifact[0]["sha256"] != item["sha256"]:
        raise LedgerError(
            f"ledger entry {entry.seq}: a run_artifact input does not match a registered artifact"
        )
    return item


def _apply_artifact(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.STARTED)
    fields = entry.fields
    name = require_artifact_name(fields["name"])
    if name in run.artifacts:
        raise LedgerError(f"ledger entry {entry.seq}: artifact name is already registered")
    ArtifactType(str(fields["artifact_type"]))
    MediaType(str(fields["media_type"]))
    _non_negative(fields["size_bytes"], entry, "size_bytes")
    if not is_sha256(fields["sha256"]):
        raise LedgerError(f"ledger entry {entry.seq}: artifact sha256 is malformed")
    schema_id, schema_version = fields["artifact_schema_id"], fields["artifact_schema_version"]
    if (schema_id is None) != (schema_version is None):
        raise LedgerError(f"ledger entry {entry.seq}: artifact schema id and version go together")
    if schema_id is not None:
        require_identifier(schema_id, "artifact_schema_id")
        _non_negative(schema_version, entry, "artifact_schema_version")
    run.artifacts[name] = (fields, entry.seq)


def _apply_metric(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.STARTED)
    fields = entry.fields
    require_identifier(fields["name"], "metric name")
    require_split(fields["split"])
    validate_metric_value(fields["value"])
    for key in ("unit", "fold"):
        if fields[key] is not None:
            require_identifier(fields[key], f"metric {key}")
    if fields["step"] is not None:
        _non_negative(fields["step"], entry, "step")
    run.metrics.append((entry.seq, fields))


def _apply_warning(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.STARTED)
    WarningCode(str(entry.fields["code"]))
    if entry.fields["context"] is not None:
        require_identifier(entry.fields["context"], "warning context")
    run.warnings.append((entry.seq, entry.fields))


def _apply_completed(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.STARTED)
    fields = entry.fields
    if not is_sha256(fields["manifest_sha256"]):
        raise LedgerError(f"ledger entry {entry.seq}: manifest_sha256 is malformed")
    artifact_count, metric_count = fields["artifact_count"], fields["metric_count"]
    if (
        not is_int(artifact_count)
        or not is_int(metric_count)
        or artifact_count != len(run.artifacts)
        or metric_count != len(run.metrics)
    ):
        raise LedgerError(f"ledger entry {entry.seq}: completion counts do not match the run")
    if sha256_hex(completion_manifest_bytes(state, run.run_id)) != fields["manifest_sha256"]:
        raise LedgerError(
            f"ledger entry {entry.seq}: manifest_sha256 does not match the rebuilt manifest"
        )
    run.preterminal_seq = run.last_event_seq
    _terminate(run, entry, RunState.COMPLETED)
    run.completed_seq = entry.seq
    run.manifest_sha256 = str(fields["manifest_sha256"])


def _apply_failed(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.STARTED)
    code = FailureCode(str(entry.fields["failure_code"]))
    if entry.version == ENTRY_V1 and code not in V1_FAILURE_CODES:
        raise LedgerError(f"ledger entry {entry.seq}: the failure code is not valid in v1")
    exception_type = entry.fields["exception_type"]
    if exception_type is not None and (
        not isinstance(exception_type, str) or EXCEPTION_TYPE.fullmatch(exception_type) is None
    ):
        raise LedgerError(f"ledger entry {entry.seq}: exception_type is malformed")
    _terminate(run, entry, RunState.FAILED)


def _apply_aborted(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.RESERVED, RunState.STARTED)
    AbortReason(str(entry.fields["reason"]))
    _terminate(run, entry, RunState.ABORTED)


def _apply_interrupted(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, RunState.RESERVED, RunState.STARTED)
    if entry.fields["last_state"] != run.state.value:
        raise LedgerError(f"ledger entry {entry.seq}: last_state does not match the run")
    _terminate(run, entry, RunState.INTERRUPTED)


def _apply_superseded(state: LedgerState, entry: Entry) -> None:
    run = _run(state, entry, *TERMINAL_STATES)
    if run.superseded_seq is not None:
        raise LedgerError(f"ledger entry {entry.seq}: the run is already superseded")
    by = require_run_id(entry.fields["superseded_by"], "superseded_by")
    replacement = state.runs.get(by)
    if by == run.run_id or replacement is None or replacement.state is not RunState.COMPLETED:
        raise LedgerError(f"ledger entry {entry.seq}: superseded_by must be another completed run")
    SupersedeReason(str(entry.fields["reason"]))
    run.superseded_seq = entry.seq
    run.superseded_by = by


def _apply_repaired(state: LedgerState, entry: Entry) -> None:
    fields = entry.fields
    name = fields["repair_evidence_name"]
    if not isinstance(name, str) or name in state.repairs:
        raise LedgerError(f"ledger entry {entry.seq}: repair evidence is referenced twice")
    facts = parse_evidence_name(name)
    if facts is None or any(
        type(fields[key]) is not type(value) or fields[key] != value for key, value in facts.items()
    ):
        raise LedgerError(f"ledger entry {entry.seq}: repair fields do not match the evidence name")
    offset, length = facts["torn_byte_offset"], facts["torn_byte_length"]
    if not is_int(offset) or not is_int(length) or length <= 0:
        raise LedgerError(f"ledger entry {entry.seq}: repair byte range is invalid")
    if offset + length != facts["original_ledger_size"]:
        raise LedgerError(f"ledger entry {entry.seq}: repair byte range does not add up")
    _check_repair_position(state, facts, entry.seq)
    state.repairs[name] = entry


def _check_repair_position(state: LedgerState, facts: Mapping[str, object], at_seq: int) -> None:
    last_seq, last_sha = facts["last_valid_ledger_seq"], facts["last_valid_entry_sha256"]
    offset = facts["torn_byte_offset"]
    if last_seq is None:
        if offset != 0 or last_sha is not None:
            raise LedgerError("repair evidence does not match the start of the ledger")
        following = state.entries[:at_seq]
    else:
        if not is_int(last_seq) or last_seq >= at_seq or last_seq >= len(state.entries):
            raise LedgerError("repair evidence names an entry that does not precede it")
        previous = state.entries[last_seq]
        if previous.sha256 != last_sha or previous.end != offset:
            raise LedgerError("repair evidence does not match the entry before the torn region")
        following = state.entries[last_seq + 1 : at_seq]
    if any(item.event_type is not LedgerEvent.LEDGER_TAIL_REPAIRED for item in following):
        raise LedgerError("only repair events may follow the entry before a repaired tail")


def _terminate(run: RunRecord, entry: Entry, final: RunState) -> None:
    run.state = final
    run.terminal_seq = entry.seq


def _non_negative(value: object, entry: Entry, what: str) -> int:
    if not is_non_negative_int(value):
        raise LedgerError(f"ledger entry {entry.seq}: {what} must be a non-negative integer")
    return value


def _apply_created(_state: LedgerState, entry: Entry) -> None:
    """Genesis: its position is checked when the entry is parsed."""
    if not is_store_id(entry.fields["store_id"]):
        raise LedgerError(f"ledger entry {entry.seq}: store_id is malformed")


_APPLY: Final = {
    LedgerEvent.LEDGER_CREATED: _apply_created,
    LedgerEvent.RUN_RESERVED: _apply_reserved,
    LedgerEvent.RUN_STARTED: _apply_started,
    LedgerEvent.ARTIFACT_REGISTERED: _apply_artifact,
    LedgerEvent.METRIC_RECORDED: _apply_metric,
    LedgerEvent.WARNING_RECORDED: _apply_warning,
    LedgerEvent.RUN_COMPLETED: _apply_completed,
    LedgerEvent.RUN_FAILED: _apply_failed,
    LedgerEvent.RUN_ABORTED: _apply_aborted,
    LedgerEvent.RUN_INTERRUPTED: _apply_interrupted,
    LedgerEvent.RUN_SUPERSEDED: _apply_superseded,
    LedgerEvent.LEDGER_TAIL_REPAIRED: _apply_repaired,
}
