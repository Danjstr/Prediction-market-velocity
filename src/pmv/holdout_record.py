"""Protected-holdout access ledger: closed v1 events, chain, state machine, and mirror.

Pure functions; no filesystem or Git access. The authoritative record is the hash-chained
machine ledger ``research/holdout_access/ledger.v1.jsonl`` (one canonical JSON event per
line: ``ledger_seq`` from 0, ``prev_entry_sha256``, ``entry_sha256``). HOLDOUT_ACCESS_LOG.md
is its required human-visible mirror: every event from HAL-0005 has exactly one generated
Access History entry, and the Current Status table is derived from the ledger. Both are
rendered here deterministically so a verifier can require exact agreement.

Consumption (strict v1): ``access_started`` is the first consuming event. Once it is in
the ledger, the holdout is consumed permanently, whatever happens next. A suspected or
confirmed contamination also consumes. Nothing ever makes a holdout untouched again;
``correction_recorded`` is annotative only.

The ledger holds only controlled identities, hashes, counts, timestamps, roles, and
enumerated values. It never holds protected observations, outcomes, metrics, model
outputs, or narrative text.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from pmv.experiment_spec import ARTIFACT_NAME
from pmv.integrity import (
    FormatError,
    canonical_json,
    canonical_line,
    chain_entry_sha256,
    is_identifier,
    is_int,
    is_non_negative_int,
    is_sha256,
    is_timestamp,
    is_timestamp_id,
    parse_canonical_json,
    sha256_hex,
)

EVENT_SCHEMA: Final = "pmv.holdout_access.event"
IDENTITY_SCHEMA: Final = "pmv.holdout_access.candidate_identity"
SCHEMA_VERSION: Final = 1
LEDGER_PATH: Final = "research/holdout_access/ledger.v1.jsonl"
LOG_PATH: Final = "HOLDOUT_ACCESS_LOG.md"
FIRST_EVENT_NUMBER: Final = 5
REVIEWED_LEGACY_SHA256: Final = "faf41f5f1e00bfc555aee1f34ac4dec38b024469aec8a56aae440e10620f5db7"
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_STORE_ID: Final = re.compile(r"[0-9a-f]{32}")
EVENT_ID_PATTERN: Final = r"HAL-(000[5-9]|00[1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,8})"
_EVENT_ID: Final = re.compile(EVENT_ID_PATTERN)
_PATH_COMPONENT: Final = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_REPO_ROOTS: Final = ("configs", "docs", "research", "scripts", "src")

# ----- HOLDOUT_ACCESS_LOG.md layout anchors (from the reviewed legacy file) -----

STATUS_ANCHOR: Final = "## Current Status\n\n"
STATUS_END_ANCHOR: Final = "\nThe status section summarizes the history below."
INSERT_ANCHOR: Final = "---\n\n## Event Schema\n"
LEGACY_ANCHOR: Final = "### HAL-0001 — Log initialization\n"
MACHINE_LEDGER_SECTION: Final = (
    "---\n"
    "\n"
    "## Machine-Readable Ledger\n"
    "\n"
    "From HAL-0005 onward, every event in this log is first recorded in the hash-chained "
    "machine ledger `research/holdout_access/ledger.v1.jsonl` by `python -m pmv.holdout_log`. "
    "The machine ledger is authoritative for event identity, order, hashes, authorization "
    "state, and holdout state. The tool then appends the event's generated Access History "
    "entry and regenerates Current Status. `python -m pmv.holdout_log verify-history`, which "
    "is part of `scripts/check.sh`, requires the generated history and Current Status to "
    "agree exactly with the machine ledger.\n"
    "\n"
    "HAL-0001 through HAL-0004 predate the machine ledger and are pinned by exact-byte hash "
    "in the `log_initialized` event.\n"
    "\n"
    "Generated entries contain only controlled identities, hashes, counts, timestamps, "
    "roles, and enumerated values. Exact protected observations, protected outcomes, "
    "metrics, model outputs, and narrative details must not be stored in this log. "
    "Restricted evidence may be referenced only by approved identity/hash.\n"
    "\n"
    "`access_started` and its generated Markdown mirror must be committed in Git before any "
    "protected observation can be exposed.\n"
    "\n"
    "Never edit a generated Access History entry or Current Status by hand.\n"
    "\n"
)


class HoldoutRecordError(ValueError):
    """The ledger, an event, or the Markdown mirror violates v1. Never echoes content."""


class EventType(StrEnum):
    LOG_INITIALIZED = "log_initialized"
    CYCLE_REGISTERED = "cycle_registered"
    HOLDOUT_REGISTERED = "holdout_registered"
    ACCESS_REQUESTED = "access_requested"
    ACCESS_AUTHORIZED = "access_authorized"
    ACCESS_DENIED = "access_denied"
    ACCESS_STARTED = "access_started"
    ACCESS_COMPLETED = "access_completed"
    ACCESS_FAILED = "access_failed"
    ACCESS_INTERRUPTED = "access_interrupted"
    ACCESS_ATTEMPT_REFUSED = "access_attempt_refused"
    CONTAMINATION_RECORDED = "contamination_recorded"
    HISTORICAL_RECLASSIFICATION = "historical_reclassification"
    CORRECTION_RECORDED = "correction_recorded"


class ActorRole(StrEnum):
    PROJECT_OWNER = "project_owner"
    AUTHORIZED_OPERATOR = "authorized_operator"
    ML_ENGINEER = "ml_engineer"
    DATA_SCIENTIST = "data_scientist"
    STATISTICIAN = "statistician"
    INDEPENDENT_STATISTICAL_AUDITOR = "independent_statistical_auditor"
    QUANT_BUSINESS_LEAD = "quant_business_lead"
    RELIABILITY_RED_TEAM = "reliability_red_team"
    RISK_PERFORMANCE_ENGINEER = "risk_performance_engineer"
    API_EXECUTION_ENGINEER = "api_execution_engineer"
    UNKNOWN = "unknown"


class SplitFormation(StrEnum):
    MECHANICAL_PARTITION = "mechanical_partition"
    PROSPECTIVE_PERIOD = "prospective_period"


class DenialReason(StrEnum):
    OWNER_DECLINED = "owner_declined"
    GATE_6_INVALID = "gate_6_invalid"
    EVALUATION_PLAN_MISMATCH = "evaluation_plan_mismatch"
    CANDIDATE_IDENTITY_INVALID = "candidate_identity_invalid"
    HOLDOUT_CONSUMED = "holdout_consumed"


class RefusalReason(StrEnum):
    NO_AUTHORIZATION = "no_authorization"
    AUTHORIZATION_ALREADY_USED = "authorization_already_used"
    WRONG_CYCLE = "wrong_cycle"
    WRONG_HOLDOUT = "wrong_holdout"
    WRONG_CANDIDATE = "wrong_candidate"
    CANDIDATE_CHANGED = "candidate_changed"
    RUNNER_MISMATCH = "runner_mismatch"
    EVALUATION_PLAN_MISMATCH = "evaluation_plan_mismatch"
    GATE_6_INVALID = "gate_6_invalid"
    GATE_7_MISSING = "gate_7_missing"
    GATE_7_INVALID = "gate_7_invalid"
    HOLDOUT_CONSUMED = "holdout_consumed"
    OWNER_NOT_ATTESTED = "owner_not_attested"
    REPOSITORY_NOT_CLEAN = "repository_not_clean"


class FailureReason(StrEnum):
    RUNNER_ERROR = "runner_error"
    DATA_INTEGRITY_ERROR = "data_integrity_error"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    OPERATOR_ABORT = "operator_abort"


class InterruptReason(StrEnum):
    PROCESS_CRASH = "process_crash"
    UNKNOWN_STATE = "unknown_state"


class ContaminationLevel(StrEnum):
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class ExposureCategory(StrEnum):
    LABELS_OR_RESOLUTIONS = "labels_or_resolutions"
    PREDICTIONS_AGAINST_OUTCOMES = "predictions_against_outcomes"
    PERFORMANCE_METRICS = "performance_metrics"
    CALIBRATION_RESULTS = "calibration_results"
    PNL_OR_EV = "pnl_or_ev"
    ERROR_ANALYSIS = "error_analysis"
    TRADE_OUTCOMES = "trade_outcomes"
    RAW_PROTECTED_OBSERVATIONS = "raw_protected_observations"
    OTHER_OUTCOME_DERIVED = "other_outcome_derived"


class Component(StrEnum):
    CANDIDATE_MANIFEST = "candidate_manifest"
    READINESS_REVIEW = "readiness_review"
    MODEL = "model"
    FEATURE_DEFINITION = "feature_definition"
    PREPROCESSING = "preprocessing"
    CALIBRATION = "calibration"
    CONFIGS = "configs"
    COST_ASSUMPTIONS = "cost_assumptions"
    EXECUTION_ASSUMPTIONS = "execution_assumptions"
    INPUT_DEFINITION = "input_definition"
    EVALUATION_PLAN = "evaluation_plan"
    RUNNER = "runner"


ATTESTING_ROLES: Final = frozenset({ActorRole.PROJECT_OWNER})
OPERATOR_ROLES: Final = frozenset({ActorRole.PROJECT_OWNER, ActorRole.AUTHORIZED_OPERATOR})
CLOSING_EVENTS: Final = frozenset(
    {EventType.ACCESS_COMPLETED, EventType.ACCESS_FAILED, EventType.ACCESS_INTERRUPTED}
)
_ENVELOPE: Final = frozenset(
    {
        "schema",
        "schema_version",
        "ledger_seq",
        "event_id",
        "prev_entry_sha256",
        "entry_sha256",
        "recorded_at",
        "event_type",
        "repository",
    }
)
FIELDS: Final[Mapping[EventType, frozenset[str]]] = {
    EventType.LOG_INITIALIZED: frozenset(
        {
            "legacy_file_sha256",
            "preamble_sha256",
            "body_sha256",
            "body_size",
            "legacy_history_sha256",
            "legacy_history_size",
            "legacy_status_sha256",
            "prior_last_event",
            "prior_contamination",
            "prior_consumption",
        }
    ),
    EventType.CYCLE_REGISTERED: frozenset(
        {
            "cycle_id",
            "split_formation",
            "development_subset",
            "protected_start",
            "protected_end",
            "attestation",
        }
    ),
    EventType.HOLDOUT_REGISTERED: frozenset(
        {
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
            "attestation",
        }
    ),
    EventType.ACCESS_REQUESTED: frozenset(
        {
            "cycle_id",
            "holdout_id",
            "candidate_id",
            "candidate_identity",
            "candidate_identity_sha256",
            "requested_by",
        }
    ),
    EventType.ACCESS_AUTHORIZED: frozenset(
        {"request", "candidate_identity_sha256", "gate_6", "evaluation_plan", "attestation"}
    ),
    EventType.ACCESS_DENIED: frozenset({"request", "reason", "attestation"}),
    EventType.ACCESS_STARTED: frozenset(
        {
            "authorization",
            "candidate_identity_sha256",
            "gate_6",
            "gate_7",
            "evaluation_plan",
            "attestation",
        }
    ),
    EventType.ACCESS_COMPLETED: frozenset({"started", "recorded_by", "restricted_evidence_sha256"}),
    EventType.ACCESS_FAILED: frozenset(
        {"started", "recorded_by", "reason", "restricted_evidence_sha256"}
    ),
    EventType.ACCESS_INTERRUPTED: frozenset(
        {"started", "recorded_by", "reason", "restricted_evidence_sha256"}
    ),
    EventType.ACCESS_ATTEMPT_REFUSED: frozenset(
        {"cycle_id", "holdout_id", "candidate_id", "authorization", "reason"}
    ),
    EventType.CONTAMINATION_RECORDED: frozenset(
        {
            "holdout_id",
            "level",
            "exposure_categories",
            "exposed_roles",
            "restricted_evidence_sha256",
            "attestation",
        }
    ),
    EventType.HISTORICAL_RECLASSIFICATION: frozenset(
        {"holdout_id", "untouched_holdout_id", "attestation"}
    ),
    EventType.CORRECTION_RECORDED: frozenset({"corrects", "document", "attestation"}),
}


# ----- state -----


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    event_id: str
    sha256: str
    event_type: EventType
    recorded_at: str
    repository: Mapping[str, object]
    fields: Mapping[str, object]
    line: bytes


@dataclass(slots=True)
class HoldoutState:
    holdout_id: str
    cycle_id: str
    registered: str
    fields: Mapping[str, object]
    consumed_by: str | None = None
    historical_by: str | None = None
    contamination: list[tuple[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class RequestState:
    event_id: str
    holdout_id: str
    cycle_id: str
    candidate_id: str
    identity: Mapping[str, object]
    identity_sha256: str
    decision: str | None = None
    decided_by: str | None = None


@dataclass(slots=True)
class AuthorizationState:
    event_id: str
    request: str
    holdout_id: str
    identity_sha256: str
    gate_6: Mapping[str, object]
    evaluation_plan: Mapping[str, object]
    started_by: str | None = None


@dataclass(slots=True)
class StartState:
    event_id: str
    authorization: str
    holdout_id: str
    gate_7: Mapping[str, object]
    closed_by: str | None = None


@dataclass(slots=True)
class LogState:
    events: list[Event] = field(default_factory=list)
    cycles: dict[str, str] = field(default_factory=dict)
    holdouts: dict[str, HoldoutState] = field(default_factory=dict)
    requests: dict[str, RequestState] = field(default_factory=dict)
    authorizations: dict[str, AuthorizationState] = field(default_factory=dict)
    starts: dict[str, StartState] = field(default_factory=dict)

    @property
    def head_seq(self) -> int:
        return len(self.events) - 1

    @property
    def head_sha256(self) -> str | None:
        return self.events[-1].sha256 if self.events else None

    def by_id(self, event_id: str) -> Event | None:
        number = _event_number(event_id)
        if number is None:
            return None
        seq = number - FIRST_EVENT_NUMBER
        return self.events[seq] if 0 <= seq < len(self.events) else None

    @property
    def initialization(self) -> Mapping[str, object]:
        if not self.events:
            raise HoldoutRecordError("the holdout ledger has no log_initialized event")
        return self.events[0].fields


def event_id_for(seq: int) -> str:
    return f"HAL-{seq + FIRST_EVENT_NUMBER:04d}"


def _event_number(event_id: object) -> int | None:
    if not isinstance(event_id, str) or _EVENT_ID.fullmatch(event_id) is None:
        return None
    return int(event_id[4:])


# ----- ledger -----


def verify_ledger(data: bytes) -> LogState:
    """Fully verify ledger bytes from byte 0: encoding, schema, chain, and state machine."""
    if data and not data.endswith(b"\n"):
        raise HoldoutRecordError(
            "the holdout ledger ends with an incomplete entry; it fails closed and is never "
            "repaired automatically"
        )
    state = LogState()
    for line in data.split(b"\n")[:-1] if data else []:
        event = _parse_event(line, state)
        _apply(state, event)
        state.events.append(event)
    return state


def encode_event(
    state: LogState,
    event_type: EventType,
    recorded_at: str,
    repository: Mapping[str, object],
    fields: Mapping[str, object],
) -> bytes:
    seq = state.head_seq + 1
    body: dict[str, object] = {
        "event_id": event_id_for(seq),
        "event_type": EventType(event_type).value,
        "ledger_seq": seq,
        "prev_entry_sha256": state.head_sha256,
        "recorded_at": recorded_at,
        "repository": dict(repository),
        "schema": EVENT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        **fields,
    }
    return canonical_line({**body, "entry_sha256": chain_entry_sha256(body)})


def append_checked(state: LogState, line: bytes) -> LogState:
    """Verify that ``line`` is a valid next event on top of ``state``; return the new state."""
    event = _parse_event(line.removesuffix(b"\n"), state)
    _apply(state, event)
    state.events.append(event)
    return state


def _parse_event(line: bytes, state: LogState) -> Event:
    number = len(state.events)
    try:
        document = parse_canonical_json(line)
    except FormatError:
        raise HoldoutRecordError(f"holdout ledger line {number} is not canonical JSON") from None
    raw_type = document.get("event_type")
    try:
        event_type = EventType(raw_type) if isinstance(raw_type, str) else None
    except ValueError:
        event_type = None
    if event_type is None or set(document) != _ENVELOPE | FIELDS[event_type]:
        raise HoldoutRecordError(f"holdout ledger line {number} does not match the v1 schema")
    version = document["schema_version"]
    if document["schema"] != EVENT_SCHEMA or not is_int(version) or version != SCHEMA_VERSION:
        raise HoldoutRecordError(f"holdout ledger line {number} has an unsupported schema")
    seq = document["ledger_seq"]
    if not is_int(seq) or seq != number:
        raise HoldoutRecordError(f"holdout ledger line {number} breaks ledger_seq continuity")
    if document["event_id"] != event_id_for(number):
        raise HoldoutRecordError(f"holdout ledger line {number} has the wrong event_id")
    if document["prev_entry_sha256"] != state.head_sha256:
        raise HoldoutRecordError(f"holdout ledger line {number} breaks the hash chain")
    digest = document["entry_sha256"]
    body = {key: value for key, value in document.items() if key != "entry_sha256"}
    if not is_sha256(digest) or chain_entry_sha256(body) != digest:
        raise HoldoutRecordError(f"holdout ledger line {number} has an invalid entry_sha256")
    if not is_timestamp(document["recorded_at"]):
        raise HoldoutRecordError(f"holdout ledger line {number} has an invalid recorded_at")
    if state.events and str(document["recorded_at"]) < state.events[-1].recorded_at:
        raise HoldoutRecordError(f"holdout ledger line {number} is recorded before its predecessor")
    if (event_type is EventType.LOG_INITIALIZED) != (number == 0):
        raise HoldoutRecordError("only the first holdout ledger event is log_initialized")
    repository = _mapping(document["repository"], "repository")
    _validate_repository(repository)
    return Event(
        seq=number,
        event_id=str(document["event_id"]),
        sha256=str(digest),
        event_type=event_type,
        recorded_at=str(document["recorded_at"]),
        repository=repository,
        fields={key: document[key] for key in FIELDS[event_type]},
        line=line + b"\n",
    )


def _validate_repository(value: Mapping[str, object]) -> None:
    _keys(value, {"commit", "tree_dirty", "dirty_tree_sha256"}, "repository")
    commit = value["commit"]
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        raise HoldoutRecordError("repository.commit is malformed")
    dirty, fingerprint = value["tree_dirty"], value["dirty_tree_sha256"]
    if not isinstance(dirty, bool) or dirty != (fingerprint is not None):
        raise HoldoutRecordError("dirty_tree_sha256 is set exactly when the tree is dirty")
    if fingerprint is not None and not is_sha256(fingerprint):
        raise HoldoutRecordError("dirty_tree_sha256 is malformed")


# ----- state machine -----


def _apply(state: LogState, event: Event) -> None:
    where = f"holdout ledger event {event.event_id}"
    try:
        _APPLY[event.event_type](state, event)
    except HoldoutRecordError as exc:
        raise HoldoutRecordError(f"{where}: {exc}") from None
    except (KeyError, TypeError, ValueError):
        raise HoldoutRecordError(f"{where} has malformed fields") from None


def _apply_initialized(_state: LogState, event: Event) -> None:
    f = event.fields
    for key in (
        "legacy_file_sha256",
        "preamble_sha256",
        "body_sha256",
        "legacy_history_sha256",
        "legacy_status_sha256",
    ):
        _sha(f[key], key)
    for key in ("body_size", "legacy_history_size"):
        value = f[key]
        if not is_int(value) or value <= 0:
            raise HoldoutRecordError(f"{key} must be a positive integer")
    if f["prior_last_event"] != "HAL-0004":
        raise HoldoutRecordError("prior_last_event must be HAL-0004")
    if f["prior_contamination"] != "none_known" or f["prior_consumption"] != "not_known_consumed":
        raise HoldoutRecordError("the prior legacy status is not the reviewed v1 status")


def _apply_cycle(state: LogState, event: Event) -> None:
    f = event.fields
    cycle_id = _identifier(f["cycle_id"], "cycle_id")
    if cycle_id in state.cycles:
        raise HoldoutRecordError("the cycle is already registered")
    SplitFormation(_text(f["split_formation"]))
    _document(f["development_subset"])
    _interval(f["protected_start"], f["protected_end"])
    _attestation(f["attestation"], ATTESTING_ROLES)
    state.cycles[cycle_id] = event.event_id


def _apply_holdout(state: LogState, event: Event) -> None:
    f = event.fields
    holdout_id = _identifier(f["holdout_id"], "holdout_id")
    cycle_id = _identifier(f["cycle_id"], "cycle_id")
    if holdout_id in state.holdouts:
        raise HoldoutRecordError("the holdout is already registered")
    if cycle_id not in state.cycles:
        raise HoldoutRecordError("the holdout's cycle is not registered")
    if any(item.cycle_id == cycle_id for item in state.holdouts.values()):
        raise HoldoutRecordError("the cycle already has a registered holdout")
    split = _document(f["split_definition"])
    if not re.fullmatch(r"research/splits/[a-z][a-z0-9_]{0,63}\.yaml", str(split["path"])):
        raise HoldoutRecordError("the split definition must be research/splits/<split_id>.yaml")
    for key in (
        "snapshot_manifest_sha256",
        "metadata_sha256",
        "purge_embargo_sha256",
        "source_manifest_sha256",
    ):
        _sha(f[key], key)
    count = f["observation_count"]
    if not is_int(count) or count <= 0:
        raise HoldoutRecordError("observation_count must be a positive integer")
    _interval(f["start"], f["end"])
    _attestation(f["attestation"], ATTESTING_ROLES)
    state.holdouts[holdout_id] = HoldoutState(holdout_id, cycle_id, event.event_id, f)


def _apply_requested(state: LogState, event: Event) -> None:
    f = event.fields
    holdout = _holdout(state, f["holdout_id"])
    _unconsumed(holdout)
    if f["cycle_id"] != holdout.cycle_id:
        raise HoldoutRecordError("the request's cycle does not match the holdout")
    candidate_id = _identifier(f["candidate_id"], "candidate_id")
    identity = validate_candidate_identity(f["candidate_identity"])
    if (
        identity["cycle_id"] != holdout.cycle_id
        or identity["holdout_id"] != holdout.holdout_id
        or identity["candidate_id"] != candidate_id
    ):
        raise HoldoutRecordError("the candidate identity does not match the request")
    digest = candidate_identity_sha256(identity)
    if f["candidate_identity_sha256"] != digest:
        raise HoldoutRecordError("candidate_identity_sha256 does not match the identity")
    ActorRole(_text(f["requested_by"]))
    state.requests[event.event_id] = RequestState(
        event.event_id, holdout.holdout_id, holdout.cycle_id, candidate_id, identity, digest
    )


def _apply_authorized(state: LogState, event: Event) -> None:
    f = event.fields
    request = _request(state, f["request"])
    if request.decision is not None:
        raise HoldoutRecordError("the request was already decided")
    holdout = state.holdouts[request.holdout_id]
    _unconsumed(holdout)
    if f["candidate_identity_sha256"] != request.identity_sha256:
        raise HoldoutRecordError("the authorization does not match the requested candidate")
    _record_ref(f["gate_6"])
    plan = _document(f["evaluation_plan"])
    if plan != evaluation_plan_of(request.identity):
        raise HoldoutRecordError("the evaluation plan does not match the candidate identity")
    _attestation(f["attestation"], ATTESTING_ROLES)
    request.decision, request.decided_by = "authorized", event.event_id
    state.authorizations[event.event_id] = AuthorizationState(
        event.event_id,
        request.event_id,
        holdout.holdout_id,
        request.identity_sha256,
        _mapping(f["gate_6"], "gate_6"),
        plan,
    )


def _apply_denied(state: LogState, event: Event) -> None:
    f = event.fields
    request = _request(state, f["request"])
    if request.decision is not None:
        raise HoldoutRecordError("the request was already decided")
    DenialReason(_text(f["reason"]))
    _attestation(f["attestation"], ATTESTING_ROLES)
    request.decision, request.decided_by = "denied", event.event_id


def _apply_started(state: LogState, event: Event) -> None:
    f = event.fields
    authorization = _authorization(state, f["authorization"])
    if authorization.started_by is not None:
        raise HoldoutRecordError("the authorization was already used")
    holdout = state.holdouts[authorization.holdout_id]
    _unconsumed(holdout)
    if f["candidate_identity_sha256"] != authorization.identity_sha256:
        raise HoldoutRecordError("the started candidate differs from the authorized candidate")
    if f["gate_6"] != authorization.gate_6:
        raise HoldoutRecordError("the started Gate 6 record differs from the authorization")
    if _document(f["evaluation_plan"]) != authorization.evaluation_plan:
        raise HoldoutRecordError("the started evaluation plan differs from the authorization")
    _record_ref(f["gate_7"])
    _attestation(f["attestation"], OPERATOR_ROLES)
    authorization.started_by = event.event_id
    holdout.consumed_by = event.event_id
    state.starts[event.event_id] = StartState(
        event.event_id, authorization.event_id, holdout.holdout_id, _mapping(f["gate_7"], "gate_7")
    )


def _apply_closed(state: LogState, event: Event) -> None:
    f = event.fields
    start = _start(state, f["started"])
    if start.closed_by is not None:
        raise HoldoutRecordError("the access was already closed")
    if ActorRole(_text(f["recorded_by"])) not in OPERATOR_ROLES:
        raise HoldoutRecordError("only the owner or an authorized operator closes an access")
    if event.event_type is EventType.ACCESS_FAILED:
        FailureReason(_text(f["reason"]))
    if event.event_type is EventType.ACCESS_INTERRUPTED:
        InterruptReason(_text(f["reason"]))
    if "restricted_evidence_sha256" in f and f["restricted_evidence_sha256"] is not None:
        _sha(f["restricted_evidence_sha256"], "restricted_evidence_sha256")
    start.closed_by = event.event_id


def _apply_refused(state: LogState, event: Event) -> None:
    f = event.fields
    for key in ("cycle_id", "holdout_id", "candidate_id"):
        if f[key] is not None:
            _identifier(f[key], key)
    if f["authorization"] is not None:
        _ref(state, f["authorization"], {EventType.ACCESS_AUTHORIZED})
    RefusalReason(_text(f["reason"]))


def _apply_contamination(state: LogState, event: Event) -> None:
    f = event.fields
    holdout = _holdout(state, f["holdout_id"])
    level = ContaminationLevel(_text(f["level"]))
    categories = _sorted_unique_enum(f["exposure_categories"], ExposureCategory, "categories")
    _sorted_unique_enum(f["exposed_roles"], ActorRole, "exposed_roles")
    if not categories:
        raise HoldoutRecordError("a contamination names at least one exposure category")
    if f["restricted_evidence_sha256"] is not None:
        _sha(f["restricted_evidence_sha256"], "restricted_evidence_sha256")
    _attestation(f["attestation"], ATTESTING_ROLES)
    holdout.contamination.append((event.event_id, level.value))
    if holdout.consumed_by is None:
        holdout.consumed_by = event.event_id


def _apply_reclassified(state: LogState, event: Event) -> None:
    f = event.fields
    holdout = _holdout(state, f["holdout_id"])
    if holdout.consumed_by is None:
        raise HoldoutRecordError("only a consumed holdout can be reclassified as historical")
    if holdout.historical_by is not None:
        raise HoldoutRecordError("the holdout is already historical")
    untouched = _holdout(state, f["untouched_holdout_id"])
    if untouched.consumed_by is not None or untouched.cycle_id == holdout.cycle_id:
        raise HoldoutRecordError(
            "reclassification needs a different, untouched holdout for a new cycle"
        )
    _attestation(f["attestation"], ATTESTING_ROLES)
    holdout.historical_by = event.event_id


def _apply_correction(state: LogState, event: Event) -> None:
    f = event.fields
    _ref(state, f["corrects"], set(EventType))
    _document(f["document"])
    _attestation(f["attestation"], ATTESTING_ROLES)


_APPLY: Final[Mapping[EventType, Callable[[LogState, Event], None]]] = {
    EventType.LOG_INITIALIZED: _apply_initialized,
    EventType.CYCLE_REGISTERED: _apply_cycle,
    EventType.HOLDOUT_REGISTERED: _apply_holdout,
    EventType.ACCESS_REQUESTED: _apply_requested,
    EventType.ACCESS_AUTHORIZED: _apply_authorized,
    EventType.ACCESS_DENIED: _apply_denied,
    EventType.ACCESS_STARTED: _apply_started,
    EventType.ACCESS_COMPLETED: _apply_closed,
    EventType.ACCESS_FAILED: _apply_closed,
    EventType.ACCESS_INTERRUPTED: _apply_closed,
    EventType.ACCESS_ATTEMPT_REFUSED: _apply_refused,
    EventType.CONTAMINATION_RECORDED: _apply_contamination,
    EventType.HISTORICAL_RECLASSIFICATION: _apply_reclassified,
    EventType.CORRECTION_RECORDED: _apply_correction,
}


# ----- candidate identity -----


def validate_candidate_identity(value: object) -> Mapping[str, object]:
    """Validate the closed candidate identity object; return it unchanged."""
    identity = _mapping(value, "candidate_identity")
    _keys(
        identity,
        {
            "schema",
            "schema_version",
            "cycle_id",
            "holdout_id",
            "candidate_id",
            "project_commit",
            "experiment_ledger",
            "components",
        },
        "candidate_identity",
    )
    if identity["schema"] != IDENTITY_SCHEMA or identity["schema_version"] != SCHEMA_VERSION:
        raise HoldoutRecordError("the candidate identity schema is not supported")
    if not is_int(identity["schema_version"]):
        raise HoldoutRecordError("the candidate identity schema is not supported")
    for key in ("cycle_id", "holdout_id", "candidate_id"):
        _identifier(identity[key], key)
    commit = identity["project_commit"]
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        raise HoldoutRecordError("project_commit is malformed")
    pin = _mapping(identity["experiment_ledger"], "experiment_ledger")
    _keys(pin, {"store_id", "ledger_seq", "entry_sha256"}, "experiment_ledger")
    if not isinstance(pin["store_id"], str) or _STORE_ID.fullmatch(pin["store_id"]) is None:
        raise HoldoutRecordError("experiment_ledger.store_id is malformed")
    if not is_non_negative_int(pin["ledger_seq"]):
        raise HoldoutRecordError("experiment_ledger.ledger_seq is malformed")
    _sha(pin["entry_sha256"], "experiment_ledger.entry_sha256")
    components = _mapping(identity["components"], "components")
    _keys(components, {item.value for item in Component}, "components")
    for name, refs in components.items():
        items = _list(refs, f"components.{name}")
        if not items:
            raise HoldoutRecordError("every candidate component needs at least one reference")
        for ref in items:
            _component_ref(ref)
        keys = [canonical_json(_mapping(ref, "ref")) for ref in items]
        if keys != sorted(set(keys)):
            raise HoldoutRecordError("component references must be sorted and unique")
    plan = _list(components[Component.EVALUATION_PLAN.value], "evaluation_plan")
    if len(plan) != 1 or _mapping(plan[0], "ref")["kind"] != "repo_file":
        raise HoldoutRecordError("the evaluation plan is exactly one repository file")
    return identity


def candidate_identity_sha256(identity: Mapping[str, object]) -> str:
    return sha256_hex(canonical_line(identity))


def evaluation_plan_of(identity: Mapping[str, object]) -> dict[str, object]:
    components = _mapping(identity["components"], "components")
    ref = _mapping(_list(components[Component.EVALUATION_PLAN.value], "plan")[0], "ref")
    return {"path": ref["path"], "sha256": ref["sha256"]}


def _component_ref(value: object) -> None:
    ref = _mapping(value, "component reference")
    kind = ref.get("kind")
    if kind == "repo_file":
        _keys(ref, {"kind", "path", "sha256"}, "repo_file reference")
        if not is_repo_path(ref["path"]):
            raise HoldoutRecordError("a repository file path is not allowed")
        _sha(ref["sha256"], "repo_file sha256")
    elif kind == "run_artifact":
        _keys(ref, {"kind", "run_id", "artifact_name", "sha256"}, "run_artifact reference")
        if not is_timestamp_id(ref["run_id"]):
            raise HoldoutRecordError("a run_id is malformed")
        name = ref["artifact_name"]
        if not isinstance(name, str) or ARTIFACT_NAME.fullmatch(name) is None:
            raise HoldoutRecordError("an artifact name is malformed")
        _sha(ref["sha256"], "run_artifact sha256")
    else:
        raise HoldoutRecordError("a component reference kind is not supported")


def is_repo_path(path: object) -> bool:
    """A tracked repository file under configs/, docs/, research/, scripts/, or src/."""
    if not isinstance(path, str) or len(path) > 512:
        return False
    parts = path.split("/")
    if len(parts) < 2 or parts[0] not in _REPO_ROOTS:
        return False
    return all(_PATH_COMPONENT.fullmatch(part) is not None for part in parts)


# ----- Markdown mirror -----


@dataclass(frozen=True, slots=True)
class LogLayout:
    """HOLDOUT_ACCESS_LOG.md split into its fixed and generated parts."""

    preamble: bytes
    status: bytes
    body: bytes
    legacy: bytes
    generated: bytes


def split_legacy_file(data: bytes) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    """Split the reviewed legacy file: (preamble, status, body_before, body_after, legacy)."""
    text = _ascii_text(data)
    start = text.find(STATUS_ANCHOR)
    end = text.find(STATUS_END_ANCHOR)
    insert = text.find(INSERT_ANCHOR)
    legacy = text.find(LEGACY_ANCHOR)
    if (
        min(start, end, insert, legacy) < 0
        or text.count(STATUS_ANCHOR) != 1
        or text.count(INSERT_ANCHOR) != 1
        or text.count(LEGACY_ANCHOR) != 1
        or MACHINE_LEDGER_SECTION in text
        or not start < end < insert < legacy
    ):
        raise HoldoutRecordError("HOLDOUT_ACCESS_LOG.md does not have the reviewed legacy layout")
    status_from = start + len(STATUS_ANCHOR)
    return (
        data[: _byte(text, status_from)],
        data[_byte(text, status_from) : _byte(text, end)],
        data[_byte(text, end) : _byte(text, insert)],
        data[_byte(text, insert) : _byte(text, legacy)],
        data[_byte(text, legacy) :],
    )


def initialization_fields(legacy: bytes) -> dict[str, object]:
    """The log_initialized fields, derived only from the reviewed legacy file's bytes.

    The body hash covers the fixed text with the approved Machine-Readable Ledger section
    inserted, so the section's exact text is pinned too.
    """
    preamble, status, before, after, history = split_legacy_file(legacy)
    body = before + MACHINE_LEDGER_SECTION.encode("utf-8") + after
    return {
        "body_sha256": sha256_hex(body),
        "body_size": len(body),
        "legacy_file_sha256": sha256_hex(legacy),
        "legacy_history_sha256": sha256_hex(history),
        "legacy_history_size": len(history),
        "legacy_status_sha256": sha256_hex(status),
        "preamble_sha256": sha256_hex(preamble),
        "prior_consumption": "not_known_consumed",
        "prior_contamination": "none_known",
        "prior_last_event": "HAL-0004",
    }


def require_initialization(state: "LogState", legacy: bytes) -> None:
    """HAL-0005 must equal the fields re-derived from the reviewed legacy bytes exactly."""
    if dict(state.initialization) != initialization_fields(legacy):
        raise HoldoutRecordError(
            "log_initialized does not match the fields derived from the reviewed legacy file"
        )


def split_mirror(data: bytes, initialization: Mapping[str, object]) -> LogLayout:
    """Split a mirrored file using the sizes and hashes pinned by log_initialized."""
    text = _ascii_text(data)
    start = text.find(STATUS_ANCHOR)
    end = text.find(STATUS_END_ANCHOR)
    if start < 0 or end < 0 or end < start:
        raise HoldoutRecordError("HOLDOUT_ACCESS_LOG.md is missing its Current Status section")
    status_from = _byte(text, start + len(STATUS_ANCHOR))
    status_to = _byte(text, end)
    body_size = initialization["body_size"]
    legacy_size = initialization["legacy_history_size"]
    if not is_int(body_size) or not is_int(legacy_size):
        raise HoldoutRecordError("the initialization sizes are malformed")
    body = data[status_to : status_to + body_size]
    legacy = data[status_to + body_size : status_to + body_size + legacy_size]
    layout = LogLayout(
        preamble=data[:status_from],
        status=data[status_from:status_to],
        body=body,
        legacy=legacy,
        generated=data[status_to + body_size + legacy_size :],
    )
    for value, key in (
        (layout.preamble, "preamble_sha256"),
        (layout.body, "body_sha256"),
        (layout.legacy, "legacy_history_sha256"),
    ):
        if sha256_hex(value) != initialization[key]:
            raise HoldoutRecordError(
                "a fixed or legacy part of HOLDOUT_ACCESS_LOG.md differs from its pinned hash"
            )
    return layout


def render_log(layout: LogLayout, state: LogState) -> bytes:
    """The exact mirrored HOLDOUT_ACCESS_LOG.md for ``state``."""
    return (
        layout.preamble
        + render_status(state)
        + layout.body
        + layout.legacy
        + b"".join(render_entry(state, event) for event in state.events)
    )


def render_status(state: LogState) -> bytes:
    """The generated Current Status table: every value cites the event that justifies it."""
    last = state.events[-1].event_id
    current = _current_cycle(state)
    holdout = _holdout_for(state, current)
    opened = [event for event in state.events if event.event_type is EventType.ACCESS_STARTED]
    contamination = [
        (event.event_id, str(event.fields["level"]))
        for event in state.events
        if event.event_type is EventType.CONTAMINATION_RECORDED
    ]
    consumed = sorted(
        f"`{item.holdout_id}` ({item.consumed_by})"
        for item in state.holdouts.values()
        if item.consumed_by is not None
    )
    authorized = _open_authorizations(state, holdout)
    rows = [
        (
            "Current cycle",
            "N/A — no evaluation cycle is registered in the machine ledger "
            f"({state.events[0].event_id})."
            if current is None
            else f"`{current}` (registered {state.cycles[current]})",
        ),
        ("Holdout status", _holdout_status(state, current, holdout)),
        (
            "Protected holdout ever opened",
            "No repository evidence of protected-holdout access (no access_started event; "
            "HAL-0001 to HAL-0004 record none); activity outside the governed repository "
            f"and protocol is not knowable from this log ({state.events[0].event_id})."
            if not opened
            else "Yes — access_started " + ", ".join(event.event_id for event in opened),
        ),
        (
            "Known contamination",
            "None recorded in the machine ledger; prior status none known "
            f"({state.events[0].event_id})."
            if not contamination
            else ", ".join(f"{level} ({event_id})" for event_id, level in contamination),
        ),
        ("Gate currently authorized to open it", _authorization_text(authorized)),
        (
            "Consumed",
            "No consuming event in the machine ledger; prior status not known to be consumed "
            f"({state.events[0].event_id})."
            if not consumed
            else "Yes — " + ", ".join(consumed),
        ),
        (
            "Authoritative split definition",
            "N/A — no holdout is registered for the current cycle."
            if holdout is None
            else _doc_text(holdout.fields["split_definition"]) + f" ({holdout.registered})",
        ),
        (
            "Dataset identity / version / hash",
            "N/A — no holdout is registered for the current cycle."
            if holdout is None
            else f"snapshot manifest `{holdout.fields['snapshot_manifest_sha256']}`, "
            f"{holdout.fields['observation_count']} observations ({holdout.registered})",
        ),
        ("Last event", last),
    ]
    lines = ["| Item | Value |", "|---|---|", *(f"| {key} | {value} |" for key, value in rows)]
    return ("\n".join(lines) + "\n").encode("utf-8")


_TITLES: Final[Mapping[EventType, str]] = {
    EventType.LOG_INITIALIZED: "Machine ledger initialized",
    EventType.CYCLE_REGISTERED: "Evaluation cycle registered",
    EventType.HOLDOUT_REGISTERED: "Protected holdout registered",
    EventType.ACCESS_REQUESTED: "Access requested",
    EventType.ACCESS_AUTHORIZED: "Access authorized",
    EventType.ACCESS_DENIED: "Access denied",
    EventType.ACCESS_STARTED: "Access started (holdout consumed)",
    EventType.ACCESS_COMPLETED: "Access completed",
    EventType.ACCESS_FAILED: "Access failed",
    EventType.ACCESS_INTERRUPTED: "Access interrupted",
    EventType.ACCESS_ATTEMPT_REFUSED: "Access attempt refused",
    EventType.CONTAMINATION_RECORDED: "Contamination recorded",
    EventType.HISTORICAL_RECLASSIFICATION: "Historical reclassification",
    EventType.CORRECTION_RECORDED: "Correction recorded",
}

TEMPLATE_FIELDS: Final = (
    "Event ID",
    "UTC timestamp",
    "Actor / process",
    "Access type",
    "Reason",
    "Project phase and gate",
    "Cycle ID",
    "Candidate ID",
    "Candidate-manifest SHA-256",
    "Implementation snapshot identity",
    "Implementation readiness review SHA-256",
    "Git commit",
    "Working-tree cleanliness",
    "Dataset identity / version / hash",
    "Exact chronological split definition",
    "Split freeze timestamp",
    "Development boundary",
    "Purge / embargo definition",
    "Protected holdout boundary",
    "Exact rows / timestamps / partition requested",
    "Protected data actually exposed",
    "Exposure scope",
    "Authorization basis",
    "Pre-access verification results",
    "Operation performed",
    "Metrics / results revealed",
    "Downstream decision changed",
    "Contamination status",
    "Holdout consumed by this event",
    "Required remediation / escalation",
    "Evidence / artifact references",
)


def render_entry(state: LogState, event: Event) -> bytes:
    """The generated Access History entry for one event, in the existing template's fields."""
    kind = event.event_type.value
    na = f"N/A — not recorded by {kind} events"
    values: dict[str, str] = dict.fromkeys(TEMPLATE_FIELDS, na)
    repository = event.repository
    values.update(
        {
            "Event ID": event.event_id,
            "UTC timestamp": event.recorded_at,
            "Actor / process": f"`python -m pmv.holdout_log` ({kind})",
            "Access type": "N/A — not an access event",
            "Reason": f"`{kind}`",
            "Git commit": f"`{repository['commit']}`",
            "Working-tree cleanliness": "Clean"
            if repository["tree_dirty"] is False
            else f"Not clean — dirty-tree fingerprint `{repository['dirty_tree_sha256']}`",
            "Protected data actually exposed": "No",
            "Metrics / results revealed": "None — this log never records protected results",
            "Downstream decision changed": "No",
            "Contamination status": "none recorded by this event",
            "Holdout consumed by this event": "No",
            "Required remediation / escalation": "None",
            "Evidence / artifact references": f"Machine ledger `{LEDGER_PATH}` seq "
            f"{event.seq}, entry `{event.sha256}`",
        }
    )
    values.update(_entry_details(state, event))
    lines = [f"### {event.event_id} — {_TITLES[event.event_type]}", ""]
    lines.extend(f"- {name}: {values[name]}" for name in TEMPLATE_FIELDS)
    return ("\n" + "\n".join(lines) + "\n").encode("utf-8")


def _entry_details(state: LogState, event: Event) -> dict[str, str]:
    f = event.fields
    kind = event.event_type
    if kind is EventType.LOG_INITIALIZED:
        return {
            "Reason": "Initialize the machine-readable holdout access ledger; not an access event",
            "Project phase and gate": "Phase 0 Step 8; no gate reached",
            "Operation performed": "Created the machine ledger, inserted the approved "
            "Machine-Readable Ledger section, and generated Current Status",
            "Evidence / artifact references": f"Legacy file `{f['legacy_file_sha256']}`; "
            f"HAL-0001 to HAL-0004 bytes `{f['legacy_history_sha256']}`; "
            f"prior status table `{f['legacy_status_sha256']}`; machine ledger seq 0, "
            f"entry `{event.sha256}`",
        }
    if kind is EventType.CYCLE_REGISTERED:
        return {
            "Cycle ID": f"`{f['cycle_id']}`",
            "Exact chronological split definition": f"split formation `{f['split_formation']}`",
            "Development boundary": _doc_text(f["development_subset"]),
            "Protected holdout boundary": f"`{f['protected_start']}` to `{f['protected_end']}`",
            "Authorization basis": _attest_text(f["attestation"]),
            "Operation performed": "Registered an evaluation cycle",
        }
    if kind is EventType.HOLDOUT_REGISTERED:
        return {
            "Cycle ID": f"`{f['cycle_id']}`",
            "Dataset identity / version / hash": f"holdout `{f['holdout_id']}`, snapshot "
            f"manifest `{f['snapshot_manifest_sha256']}`, metadata `{f['metadata_sha256']}`, "
            f"source manifest `{f['source_manifest_sha256']}`, "
            f"{f['observation_count']} observations",
            "Exact chronological split definition": _doc_text(f["split_definition"]),
            "Purge / embargo definition": f"`{f['purge_embargo_sha256']}`",
            "Protected holdout boundary": f"`{f['start']}` to `{f['end']}`",
            "Authorization basis": _attest_text(f["attestation"]),
            "Operation performed": "Registered the protected holdout identity (hashes only)",
        }
    if kind is EventType.ACCESS_REQUESTED:
        identity = _mapping(f["candidate_identity"], "identity")
        components = _mapping(identity["components"], "components")
        return {
            "Actor / process": f"`{f['requested_by']}` via `python -m pmv.holdout_log`",
            "Access type": "attempted (request only; no access)",
            "Cycle ID": f"`{f['cycle_id']}`",
            "Candidate ID": f"`{f['candidate_id']}`",
            "Candidate-manifest SHA-256": _refs_text(components["candidate_manifest"]),
            "Implementation snapshot identity": f"`{identity['project_commit']}`",
            "Implementation readiness review SHA-256": _refs_text(components["readiness_review"]),
            "Dataset identity / version / hash": f"holdout `{f['holdout_id']}`",
            "Operation performed": "Recorded an access request for candidate identity "
            f"`{f['candidate_identity_sha256']}`",
        }
    if kind is EventType.ACCESS_AUTHORIZED:
        request = state.requests[str(_mapping(f["request"], "request")["event_id"])]
        return _access_values(request) | {
            "Access type": "authorized (no access yet)",
            "Authorization basis": f"Gate 6 record {_record_text(f['gate_6'])}; evaluation "
            f"plan {_doc_text(f['evaluation_plan'])}; {_attest_text(f['attestation'])}",
            "Operation performed": f"Authorized request {request.event_id}",
        }
    if kind is EventType.ACCESS_DENIED:
        request = state.requests[str(_mapping(f["request"], "request")["event_id"])]
        return _access_values(request) | {
            "Access type": "attempted (denied; no access)",
            "Reason": f"`{f['reason']}`",
            "Authorization basis": _attest_text(f["attestation"]),
            "Operation performed": f"Denied request {request.event_id}",
        }
    if kind is EventType.ACCESS_STARTED:
        authorization = state.authorizations[
            str(_mapping(f["authorization"], "authorization")["event_id"])
        ]
        request = state.requests[authorization.request]
        return _access_values(request) | {
            "Access type": "authorized access started",
            "Authorization basis": f"Authorization {authorization.event_id}; Gate 6 record "
            f"{_record_text(f['gate_6'])}; Gate 7 preregistration record "
            f"{_record_text(f['gate_7'])}; {_attest_text(f['attestation'])}",
            "Pre-access verification results": "Candidate identity, Gate 6, Gate 7, and "
            "evaluation plan re-verified by the tool before this event",
            "Protected data actually exposed": "Must be assumed (strict v1: this event consumes)",
            "Exposure scope": "The deterministic evaluation runner started under this event",
            "Operation performed": "Recorded the durable pre-reveal access intent",
            "Holdout consumed by this event": "Yes — access_started consumes the holdout",
        }
    if kind in CLOSING_EVENTS:
        start = state.starts[str(_mapping(f["started"], "started")["event_id"])]
        request = state.requests[state.authorizations[start.authorization].request]
        evidence = f.get("restricted_evidence_sha256")
        return _access_values(request) | {
            "Actor / process": f"`{f['recorded_by']}` via `python -m pmv.holdout_log`",
            "Access type": "completed" if kind is EventType.ACCESS_COMPLETED else kind.value,
            "Reason": f"`{f['reason']}`" if "reason" in f else f"`{kind.value}`",
            "Protected data actually exposed": f"Assumed since {start.event_id}",
            "Operation performed": f"Closed access {start.event_id}",
            "Holdout consumed by this event": f"No — already consumed by {start.event_id}",
            "Evidence / artifact references": (
                f"Restricted evidence `{evidence}`; " if isinstance(evidence, str) else ""
            )
            + f"machine ledger seq {event.seq}, entry `{event.sha256}`",
        }
    if kind is EventType.ACCESS_ATTEMPT_REFUSED:
        return {
            "Access type": "attempted (refused; no access)",
            "Reason": f"`{f['reason']}`",
            "Cycle ID": _optional_code(f["cycle_id"]),
            "Candidate ID": _optional_code(f["candidate_id"]),
            "Dataset identity / version / hash": _optional_code(f["holdout_id"]),
            "Operation performed": "Refused an access attempt",
        }
    if kind is EventType.CONTAMINATION_RECORDED:
        holdout = state.holdouts[str(f["holdout_id"])]
        evidence = f["restricted_evidence_sha256"]
        return {
            "Access type": "accidental",
            "Cycle ID": f"`{holdout.cycle_id}`",
            "Dataset identity / version / hash": f"holdout `{holdout.holdout_id}`",
            "Protected data actually exposed": "Yes — categories "
            + ", ".join(f"`{item}`" for item in _list(f["exposure_categories"], "categories")),
            "Exposure scope": "roles "
            + (", ".join(f"`{item}`" for item in _list(f["exposed_roles"], "roles")) or "none"),
            "Authorization basis": _attest_text(f["attestation"]),
            "Contamination status": str(f["level"]),
            "Holdout consumed by this event": "Yes"
            if holdout.consumed_by == event.event_id
            else f"No — already consumed by {holdout.consumed_by}",
            "Required remediation / escalation": "Owner decision on a replacement untouched "
            "holdout; never erase this event",
            "Operation performed": "Recorded a contamination event",
            "Evidence / artifact references": (
                f"Restricted evidence `{evidence}`; " if isinstance(evidence, str) else ""
            )
            + f"machine ledger seq {event.seq}, entry `{event.sha256}`",
        }
    if kind is EventType.HISTORICAL_RECLASSIFICATION:
        return {
            "Dataset identity / version / hash": f"holdout `{f['holdout_id']}` (consumed; "
            f"remains consumed); new untouched holdout `{f['untouched_holdout_id']}`",
            "Authorization basis": _attest_text(f["attestation"]),
            "Operation performed": "Tagged a consumed holdout as historical development data",
        }
    corrects = _mapping(f["corrects"], "corrects")
    return {
        "Reason": f"Annotative correction of {corrects['event_id']}; it changes no state",
        "Authorization basis": _attest_text(f["attestation"]),
        "Operation performed": "Recorded a correction",
        "Evidence / artifact references": f"{_doc_text(f['document'])}; machine ledger seq "
        f"{event.seq}, entry `{event.sha256}`",
    }


def _access_values(request: RequestState) -> dict[str, str]:
    components = _mapping(request.identity["components"], "components")
    return {
        "Cycle ID": f"`{request.cycle_id}`",
        "Candidate ID": f"`{request.candidate_id}`",
        "Candidate-manifest SHA-256": _refs_text(components["candidate_manifest"]),
        "Implementation snapshot identity": f"`{request.identity['project_commit']}`",
        "Implementation readiness review SHA-256": _refs_text(components["readiness_review"]),
        "Dataset identity / version / hash": f"holdout `{request.holdout_id}`",
        "Project phase and gate": "Phase 7 protocol; request " + request.event_id,
    }


def _current_cycle(state: LogState) -> str | None:
    cycles = [
        str(event.fields["cycle_id"])
        for event in state.events
        if event.event_type is EventType.CYCLE_REGISTERED
    ]
    return cycles[-1] if cycles else None


def _holdout_for(state: LogState, cycle_id: str | None) -> HoldoutState | None:
    for holdout in state.holdouts.values():
        if holdout.cycle_id == cycle_id:
            return holdout
    return None


def _holdout_status(state: LogState, cycle: str | None, holdout: HoldoutState | None) -> str:
    if cycle is None:
        first = state.events[0].event_id
        return f"No protected holdout is registered in the machine ledger ({first})."
    if holdout is None:
        return f"No protected holdout is registered for cycle `{cycle}`."
    if holdout.consumed_by is None:
        return f"Registered `{holdout.holdout_id}` ({holdout.registered}); untouched"
    suffix = f"; historical ({holdout.historical_by})" if holdout.historical_by else ""
    registered = f"Registered `{holdout.holdout_id}` ({holdout.registered})"
    return f"{registered}; consumed ({holdout.consumed_by}){suffix}"


def _open_authorizations(state: LogState, holdout: HoldoutState | None) -> list[AuthorizationState]:
    if holdout is None or holdout.consumed_by is not None:
        return []
    return [
        authorization
        for authorization in state.authorizations.values()
        if authorization.holdout_id == holdout.holdout_id and authorization.started_by is None
    ]


def _authorization_text(authorized: list[AuthorizationState]) -> str:
    if not authorized:
        return (
            "None — opening requires an access_authorized event backed by a committed Gate 6 "
            "PASS record and, before access_started, a committed Gate 7 preregistration PASS "
            "record."
        )
    if len(authorized) > 1:
        return f"Multiple open authorizations ({len(authorized)}): " + ", ".join(
            item.event_id for item in authorized
        )
    only = authorized[0]
    return (
        f"Authorization {only.event_id} for candidate identity `{only.identity_sha256}` "
        f"(Gate 6 record `{_mapping(only.gate_6, 'gate_6')['record_id']}`)"
    )


def _doc_text(value: object) -> str:
    document = _mapping(value, "document")
    return f"`{document['path']}` `{document['sha256']}`"


def _record_text(value: object) -> str:
    record = _mapping(value, "record")
    return f"`{record['record_id']}` (`{record['record_sha256']}`)"


def _attest_text(value: object) -> str:
    attestation = _mapping(value, "attestation")
    return f"`{attestation['role']}` approval attested"


def _refs_text(value: object) -> str:
    return ", ".join(
        f"`{_mapping(ref, 'ref').get('path') or _mapping(ref, 'ref').get('run_id')}` "
        f"`{_mapping(ref, 'ref')['sha256']}`"
        for ref in _list(value, "refs")
    )


def _optional_code(value: object) -> str:
    return "N/A — not identified by the refused attempt" if value is None else f"`{value}`"


# ----- helpers -----


def _holdout(state: LogState, value: object) -> HoldoutState:
    holdout = state.holdouts.get(_identifier(value, "holdout_id"))
    if holdout is None:
        raise HoldoutRecordError("the holdout is not registered")
    return holdout


def _unconsumed(holdout: HoldoutState) -> None:
    if holdout.consumed_by is not None:
        raise HoldoutRecordError("the holdout is consumed; nothing can be authorized or started")


def _ref(state: LogState, value: object, types: set[EventType]) -> Event:
    ref = _mapping(value, "event reference")
    _keys(ref, {"event_id", "entry_sha256"}, "event reference")
    event = state.by_id(str(ref["event_id"]))
    if event is None or event.sha256 != ref["entry_sha256"] or event.event_type not in types:
        raise HoldoutRecordError("an event reference does not match an earlier event")
    return event


def _request(state: LogState, value: object) -> RequestState:
    return state.requests[_ref(state, value, {EventType.ACCESS_REQUESTED}).event_id]


def _authorization(state: LogState, value: object) -> AuthorizationState:
    return state.authorizations[_ref(state, value, {EventType.ACCESS_AUTHORIZED}).event_id]


def _start(state: LogState, value: object) -> StartState:
    return state.starts[_ref(state, value, {EventType.ACCESS_STARTED}).event_id]


def _record_ref(value: object) -> None:
    ref = _mapping(value, "gate record reference")
    _keys(ref, {"record_id", "record_sha256"}, "gate record reference")
    if not is_timestamp_id(ref["record_id"]):
        raise HoldoutRecordError("a gate record_id is malformed")
    _sha(ref["record_sha256"], "record_sha256")


def _document(value: object) -> Mapping[str, object]:
    document = _mapping(value, "document")
    _keys(document, {"path", "sha256"}, "document")
    if not is_repo_path(document["path"]):
        raise HoldoutRecordError("a document path is not an allowed repository path")
    _sha(document["sha256"], "document sha256")
    return document


def _attestation(value: object, roles: frozenset[ActorRole]) -> None:
    attestation = _mapping(value, "attestation")
    _keys(attestation, {"role", "attested"}, "attestation")
    if ActorRole(_text(attestation["role"])) not in roles or attestation["attested"] is not True:
        raise HoldoutRecordError("the required role must explicitly attest this event")


def _interval(start: object, end: object) -> None:
    if not is_timestamp(start) or not is_timestamp(end) or not str(start) < str(end):
        raise HoldoutRecordError("an interval needs two UTC timestamps with start before end")


def _sorted_unique_enum(value: object, enum: type[StrEnum], what: str) -> list[str]:
    items = [_text(item) for item in _list(value, what)]
    for item in items:
        enum(item)
    if items != sorted(set(items)):
        raise HoldoutRecordError(f"{what} must be sorted and unique")
    return items


def _identifier(value: object, what: str) -> str:
    if not is_identifier(value):
        raise HoldoutRecordError(f"{what} is malformed")
    return value


def _sha(value: object, what: str) -> None:
    if not is_sha256(value):
        raise HoldoutRecordError(f"{what} is malformed")


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise HoldoutRecordError("expected a string value")
    return value


def _mapping(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise HoldoutRecordError(f"{what} must be an object")
    return value


def _list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise HoldoutRecordError(f"{what} must be a list")
    return value


def _keys(value: Mapping[str, object], expected: set[str], what: str) -> None:
    if set(value) != expected:
        raise HoldoutRecordError(f"{what} fields do not match the v1 schema")


def _ascii_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise HoldoutRecordError("HOLDOUT_ACCESS_LOG.md is not valid UTF-8") from None


def _byte(text: str, index: int) -> int:
    return len(text[:index].encode("utf-8"))


def refs_sorted(refs: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Component references in their canonical order."""
    return sorted(refs, key=lambda ref: canonical_json(ref))
