"""Tests for the pure holdout-access ledger: schema, chain, state machine, and mirror."""

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from pmv import holdout_record as hr
from pmv.holdout_record import EventType, HoldoutRecordError, LogState
from pmv.integrity import canonical_line, chain_entry_sha256, sha256_hex

TS = "2026-10-14T05:00:00.000000Z"
COMMIT = "c" * 40
REPOSITORY = {"commit": COMMIT, "dirty_tree_sha256": None, "tree_dirty": False}
OWNER = {"attested": True, "role": "project_owner"}
LEGACY = (
    "# Holdout Access Log\n\nIntro.\n\n---\n\n"
    "## Current Status\n\n| Item | Value |\n|---|---|\n| Last event | HAL-0004 |\n\n"
    "The status section summarizes the history below. It is a summary.\n\n---\n\n"
    "## Immutability\n\nAppend-only.\n\n---\n\n## Event Schema\n\nFields.\n\n---\n\n"
    "## Access History (append-only)\n\n"
    "### HAL-0001 — Log initialization\n\n- Event ID: HAL-0001\n\n"
    "### HAL-0004 — Correction of HAL-0001\n\n- Event ID: HAL-0004\n"
).encode()


def init_fields() -> dict[str, object]:
    preamble, status, before, after, history = hr.split_legacy_file(LEGACY)
    body = before + hr.MACHINE_LEDGER_SECTION.encode() + after
    return {
        "body_sha256": sha256_hex(body),
        "body_size": len(body),
        "legacy_file_sha256": sha256_hex(LEGACY),
        "legacy_history_sha256": sha256_hex(history),
        "legacy_history_size": len(history),
        "legacy_status_sha256": sha256_hex(status),
        "preamble_sha256": sha256_hex(preamble),
        "prior_consumption": "not_known_consumed",
        "prior_contamination": "none_known",
        "prior_last_event": "HAL-0004",
    }


def identity(**changes: Any) -> dict[str, Any]:
    components = {
        name.value: [{"kind": "repo_file", "path": f"src/pmv/{name.value}.py", "sha256": "1" * 64}]
        for name in hr.Component
    }
    components["evaluation_plan"] = [
        {"kind": "repo_file", "path": "docs/plan.md", "sha256": "2" * 64}
    ]
    document: dict[str, Any] = {
        "candidate_id": "cand_a",
        "components": components,
        "cycle_id": "cycle_a",
        "experiment_ledger": {"entry_sha256": "3" * 64, "ledger_seq": 4, "store_id": "4" * 32},
        "holdout_id": "holdout_a",
        "project_commit": COMMIT,
        "schema": hr.IDENTITY_SCHEMA,
        "schema_version": 1,
    }
    document.update(changes)
    return document


class Builder:
    def __init__(self) -> None:
        self.data = b""
        self.state = LogState()
        self.add(EventType.LOG_INITIALIZED, init_fields())

    def add(self, event_type: EventType, fields: Mapping[str, object]) -> hr.Event:
        line = hr.encode_event(self.state, event_type, TS, REPOSITORY, fields)
        self.state = hr.verify_ledger(self.data + line)
        self.data += line
        return self.state.events[-1]

    def ref(self, event: hr.Event) -> dict[str, object]:
        return {"entry_sha256": event.sha256, "event_id": event.event_id}

    def cycle(self, cycle_id: str = "cycle_a") -> hr.Event:
        return self.add(
            EventType.CYCLE_REGISTERED,
            {
                "attestation": OWNER,
                "cycle_id": cycle_id,
                "development_subset": {"path": "docs/dev.md", "sha256": "5" * 64},
                "protected_end": "2026-12-01T00:00:00.000000Z",
                "protected_start": "2026-11-01T00:00:00.000000Z",
                "split_formation": "mechanical_partition",
            },
        )

    def holdout(self, holdout_id: str = "holdout_a", cycle_id: str = "cycle_a") -> hr.Event:
        return self.add(
            EventType.HOLDOUT_REGISTERED,
            {
                "attestation": OWNER,
                "cycle_id": cycle_id,
                "end": "2026-12-01T00:00:00.000000Z",
                "holdout_id": holdout_id,
                "metadata_sha256": "6" * 64,
                "observation_count": 1200,
                "purge_embargo_sha256": "7" * 64,
                "snapshot_manifest_sha256": "8" * 64,
                "source_manifest_sha256": "9" * 64,
                "split_definition": {"path": "research/splits/split_a.yaml", "sha256": "a" * 64},
                "start": "2026-11-01T00:00:00.000000Z",
            },
        )

    def request(self, document: dict[str, Any] | None = None) -> hr.Event:
        value = document or identity()
        return self.add(
            EventType.ACCESS_REQUESTED,
            {
                "candidate_id": value["candidate_id"],
                "candidate_identity": value,
                "candidate_identity_sha256": hr.candidate_identity_sha256(value),
                "cycle_id": value["cycle_id"],
                "holdout_id": value["holdout_id"],
                "requested_by": "statistician",
            },
        )

    def authorize(self, request: hr.Event) -> hr.Event:
        value = self.state.requests[request.event_id]
        return self.add(
            EventType.ACCESS_AUTHORIZED,
            {
                "attestation": OWNER,
                "candidate_identity_sha256": value.identity_sha256,
                "evaluation_plan": hr.evaluation_plan_of(value.identity),
                "gate_6": GATE_6,
                "request": self.ref(request),
            },
        )

    def start(self, authorization: hr.Event) -> hr.Event:
        value = self.state.authorizations[authorization.event_id]
        return self.add(
            EventType.ACCESS_STARTED,
            {
                "attestation": {"attested": True, "role": "authorized_operator"},
                "authorization": self.ref(authorization),
                "candidate_identity_sha256": value.identity_sha256,
                "evaluation_plan": dict(value.evaluation_plan),
                "gate_6": GATE_6,
                "gate_7": GATE_7,
            },
        )

    def started(self) -> hr.Event:
        self.cycle()
        self.holdout()
        return self.start(self.authorize(self.request()))


GATE_6 = {"record_id": "20261014T050000.000000Z_" + "b" * 32, "record_sha256": "b" * 64}
GATE_7 = {"record_id": "20261014T050001.000000Z_" + "c" * 32, "record_sha256": "c" * 64}


def lines(data: bytes) -> list[bytes]:
    return data.split(b"\n")[:-1]


def join(items: list[bytes]) -> bytes:
    return b"".join(item + b"\n" for item in items)


def rehash(document: dict[str, Any]) -> bytes:
    body = {key: value for key, value in document.items() if key != "entry_sha256"}
    return canonical_line({**body, "entry_sha256": chain_entry_sha256(body)})


def mutate_last(data: bytes, change: Callable[[dict[str, Any]], None]) -> bytes:
    items = lines(data)
    document = json.loads(items[-1])
    change(document)
    return join(items[:-1]) + rehash(document)


# ----- chain -----


def test_a_full_protocol_chain_verifies_and_consumes_at_access_started() -> None:
    builder = Builder()
    started = builder.started()
    state = hr.verify_ledger(builder.data)
    assert [event.event_id for event in state.events][:2] == ["HAL-0005", "HAL-0006"]
    assert state.holdouts["holdout_a"].consumed_by == started.event_id
    assert state.starts[started.event_id].closed_by is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda items: [items[0], items[2], items[1], *items[3:]], "continuity"),
        (lambda items: [items[0], *items[2:]], "continuity"),
        (lambda items: [items[0], items[1], items[1], *items[2:]], "continuity"),
        (lambda items: [items[1], *items[1:]], "continuity"),
    ],
    ids=["reordered", "interior-deleted", "duplicated", "replaced-first"],
)
def test_reordering_deletion_and_duplication_are_detected(
    mutate: Callable[[list[bytes]], list[bytes]], message: str
) -> None:
    builder = Builder()
    builder.started()
    with pytest.raises(HoldoutRecordError, match=message):
        hr.verify_ledger(join(mutate(lines(builder.data))))


def test_altered_torn_and_malformed_entries_fail_closed() -> None:
    builder = Builder()
    builder.started()
    items = lines(builder.data)
    altered = json.loads(items[2])
    altered["observation_count"] = 1201
    items[2] = json.dumps(altered, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(HoldoutRecordError, match="invalid entry_sha256"):
        hr.verify_ledger(join(items))
    with pytest.raises(HoldoutRecordError, match="incomplete entry"):
        hr.verify_ledger(builder.data + b'{"event_type":"access_comp')
    with pytest.raises(HoldoutRecordError, match="not canonical"):
        hr.verify_ledger(builder.data + b"{bad}\n")


def test_complete_tail_deletion_is_not_detectable_by_the_chain_alone() -> None:
    builder = Builder()
    builder.started()
    truncated = join(lines(builder.data)[:-1])
    state = hr.verify_ledger(truncated)
    assert state.holdouts["holdout_a"].consumed_by is None


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(brier="0.21"),
        lambda d: d.update(pnl=10),
        lambda d: d.update(schema_version=2),
        lambda d: d.update(schema_version=True),
        lambda d: d.update(ledger_seq=True),
        lambda d: d.update(observation_count=True),
        lambda d: d.update(observation_count=0),
        lambda d: d.update(recorded_at="2026-10-14T05:00:00.00000\u0661Z"),
        lambda d: d.update(event_id="HAL-0099"),
        lambda d: d["repository"].update(tree_dirty=True),
        lambda d: d.update(start="2026-12-02T00:00:00.000000Z"),
    ],
)
def test_schema_violations_fail_closed(change: Callable[[dict[str, Any]], None]) -> None:
    builder = Builder()
    builder.cycle()
    builder.holdout()
    with pytest.raises(HoldoutRecordError):
        hr.verify_ledger(mutate_last(builder.data, change))


def test_log_initialized_is_first_and_unique() -> None:
    builder = Builder()
    with pytest.raises(HoldoutRecordError, match="only the first"):
        builder.add(EventType.LOG_INITIALIZED, init_fields())
    other = Builder()
    other.cycle()
    cycle_line = lines(other.data)[1]
    cycle = json.loads(cycle_line)
    cycle.update(event_id="HAL-0005", ledger_seq=0, prev_entry_sha256=None)
    with pytest.raises(HoldoutRecordError, match="only the first"):
        hr.verify_ledger(rehash(cycle))


# ----- state machine -----


def test_consumption_is_permanent_whatever_closes_the_access() -> None:
    for outcome, extra in (
        (EventType.ACCESS_COMPLETED, {"restricted_evidence_sha256": None}),
        (EventType.ACCESS_FAILED, {"reason": "runner_error", "restricted_evidence_sha256": None}),
        (
            EventType.ACCESS_INTERRUPTED,
            {"reason": "process_crash", "restricted_evidence_sha256": None},
        ),
    ):
        builder = Builder()
        started = builder.started()
        builder.add(
            outcome, {"recorded_by": "project_owner", "started": builder.ref(started), **extra}
        )
        holdout = builder.state.holdouts["holdout_a"]
        assert holdout.consumed_by == started.event_id
        with pytest.raises(HoldoutRecordError, match="already closed"):
            builder.add(
                outcome, {"recorded_by": "project_owner", "started": builder.ref(started), **extra}
            )


def test_nothing_can_be_requested_authorized_or_started_on_a_consumed_holdout() -> None:
    builder = Builder()
    started = builder.started()
    with pytest.raises(HoldoutRecordError, match="consumed"):
        builder.request()
    authorization = builder.state.starts[started.event_id].authorization
    with pytest.raises(HoldoutRecordError, match="already used"):
        builder.start(builder.state.by_id(authorization))  # type: ignore[arg-type]  # present


def test_an_authorization_is_single_use_and_requests_are_decided_once() -> None:
    builder = Builder()
    builder.cycle()
    builder.holdout()
    request = builder.request()
    builder.add(
        EventType.ACCESS_DENIED,
        {"attestation": OWNER, "reason": "owner_declined", "request": builder.ref(request)},
    )
    with pytest.raises(HoldoutRecordError, match="already decided"):
        builder.authorize(request)


def test_authorization_and_start_must_match_the_request_exactly() -> None:
    builder = Builder()
    builder.cycle()
    builder.holdout()
    request = builder.request()
    good = builder.state.requests[request.event_id]
    with pytest.raises(HoldoutRecordError, match="requested candidate"):
        builder.add(
            EventType.ACCESS_AUTHORIZED,
            {
                "attestation": OWNER,
                "candidate_identity_sha256": "0" * 64,
                "evaluation_plan": hr.evaluation_plan_of(good.identity),
                "gate_6": GATE_6,
                "request": builder.ref(request),
            },
        )
    with pytest.raises(HoldoutRecordError, match="evaluation plan"):
        builder.add(
            EventType.ACCESS_AUTHORIZED,
            {
                "attestation": OWNER,
                "candidate_identity_sha256": good.identity_sha256,
                "evaluation_plan": {"path": "docs/other.md", "sha256": "2" * 64},
                "gate_6": GATE_6,
                "request": builder.ref(request),
            },
        )
    authorization = builder.authorize(request)
    with pytest.raises(HoldoutRecordError, match="must explicitly attest"):
        builder.add(
            EventType.ACCESS_STARTED,
            {
                "attestation": {"attested": True, "role": "statistician"},
                "authorization": builder.ref(authorization),
                "candidate_identity_sha256": good.identity_sha256,
                "evaluation_plan": hr.evaluation_plan_of(good.identity),
                "gate_6": GATE_6,
                "gate_7": GATE_7,
            },
        )


def test_contamination_consumes_and_corrections_never_undo_anything() -> None:
    builder = Builder()
    builder.cycle()
    holdout = builder.holdout()
    contamination = builder.add(
        EventType.CONTAMINATION_RECORDED,
        {
            "attestation": OWNER,
            "exposed_roles": ["ml_engineer"],
            "exposure_categories": ["performance_metrics"],
            "holdout_id": "holdout_a",
            "level": "suspected",
            "restricted_evidence_sha256": None,
        },
    )
    assert builder.state.holdouts["holdout_a"].consumed_by == contamination.event_id
    builder.add(
        EventType.CORRECTION_RECORDED,
        {
            "attestation": OWNER,
            "corrects": builder.ref(contamination),
            "document": {"path": "docs/correction.md", "sha256": "d" * 64},
        },
    )
    assert builder.state.holdouts["holdout_a"].consumed_by == contamination.event_id
    assert holdout.event_type is EventType.HOLDOUT_REGISTERED
    with pytest.raises(HoldoutRecordError, match="consumed"):
        builder.request()


def test_reclassification_needs_a_consumed_holdout_and_a_new_untouched_one() -> None:
    builder = Builder()
    builder.started()
    reclassify = {
        "attestation": OWNER,
        "holdout_id": "holdout_a",
        "untouched_holdout_id": "holdout_b",
    }
    with pytest.raises(HoldoutRecordError, match="not registered"):
        builder.add(EventType.HISTORICAL_RECLASSIFICATION, reclassify)
    builder.cycle("cycle_b")
    builder.holdout("holdout_b", "cycle_b")
    builder.add(EventType.HISTORICAL_RECLASSIFICATION, reclassify)
    holdout = builder.state.holdouts["holdout_a"]
    assert holdout.consumed_by is not None
    assert holdout.historical_by is not None


# ----- candidate identity -----


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["components"].pop("runner"),
        lambda d: d["components"].update(model=[]),
        lambda d: d["components"].update(
            model=[
                {"kind": "repo_file", "path": "src/b.py", "sha256": "1" * 64},
                {"kind": "repo_file", "path": "src/a.py", "sha256": "1" * 64},
            ]
        ),
        lambda d: d["components"]["evaluation_plan"].append(
            {"kind": "repo_file", "path": "docs/plan2.md", "sha256": "2" * 64}
        ),
        lambda d: d["components"].update(
            model=[{"kind": "repo_file", "path": "../secret", "sha256": "1" * 64}]
        ),
        lambda d: d["components"].update(model=[{"kind": "url", "path": "x", "sha256": "1" * 64}]),
        lambda d: d.update(holdout_id="Holdout A"),
        lambda d: d["experiment_ledger"].update(ledger_seq=True),
    ],
)
def test_candidate_identity_is_closed_and_exact(change: Callable[[dict[str, Any]], None]) -> None:
    document = identity()
    change(document)
    with pytest.raises(HoldoutRecordError):
        hr.validate_candidate_identity(document)


def test_a_request_must_carry_the_exact_identity_hash() -> None:
    builder = Builder()
    builder.cycle()
    builder.holdout()
    value = identity()
    with pytest.raises(HoldoutRecordError, match="does not match the identity"):
        builder.add(
            EventType.ACCESS_REQUESTED,
            {
                "candidate_id": "cand_a",
                "candidate_identity": value,
                "candidate_identity_sha256": "0" * 64,
                "cycle_id": "cycle_a",
                "holdout_id": "holdout_a",
                "requested_by": "statistician",
            },
        )
    with pytest.raises(HoldoutRecordError, match="does not match the request"):
        builder.add(
            EventType.ACCESS_REQUESTED,
            {
                "candidate_id": "cand_b",
                "candidate_identity": value,
                "candidate_identity_sha256": hr.candidate_identity_sha256(value),
                "cycle_id": "cycle_a",
                "holdout_id": "holdout_a",
                "requested_by": "statistician",
            },
        )


# ----- mirror -----


def mirror_layout(state: LogState) -> hr.LogLayout:
    preamble, _status, before, after, history = hr.split_legacy_file(LEGACY)
    return hr.LogLayout(
        preamble, b"", before + hr.MACHINE_LEDGER_SECTION.encode() + after, history, b""
    )


def test_the_mirror_is_exact_and_pins_the_fixed_and_legacy_parts() -> None:
    builder = Builder()
    builder.started()
    rendered = hr.render_log(mirror_layout(builder.state), builder.state)
    assert rendered.count(b"## Machine-Readable Ledger") == 1
    assert LEGACY.split(b"### HAL-0001")[1].split(b"\n### HAL-0004")[0] in rendered
    layout = hr.split_mirror(rendered, builder.state.initialization)
    assert hr.render_log(layout, builder.state) == rendered
    text = rendered.decode()
    assert "| Consumed | Yes — `holdout_a` (HAL-0010) |" in text
    assert "### HAL-0010 — Access started (holdout consumed)" in text
    for forbidden in ("brier", "pnl", "accuracy"):
        assert forbidden not in text.lower()
    tampered = (
        rendered.replace(b"Intro.", b"Intro!"),
        rendered.replace(b"- Event ID: HAL-0001\n", b"- Event ID: HAL-0001 \n"),
        rendered.replace(b"Never edit a generated", b"Always edit a generated"),
    )
    for value in tampered:
        assert value != rendered
        with pytest.raises(HoldoutRecordError, match="pinned hash"):
            hr.split_mirror(value, builder.state.initialization)


def test_the_legacy_layout_is_checked_before_initialization() -> None:
    with pytest.raises(HoldoutRecordError, match="reviewed legacy layout"):
        hr.split_legacy_file(LEGACY.replace(b"## Event Schema", b"## Schema"))
    with pytest.raises(HoldoutRecordError, match="reviewed legacy layout"):
        hr.split_legacy_file(LEGACY + hr.MACHINE_LEDGER_SECTION.encode())


def test_every_generated_entry_uses_the_existing_template_fields() -> None:
    builder = Builder()
    builder.started()
    entry = hr.render_entry(builder.state, builder.state.events[-1]).decode()
    for name in hr.TEMPLATE_FIELDS:
        assert f"\n- {name}: " in entry
    assert "Holdout consumed by this event: Yes" in entry


def test_the_schema_document_matches_the_python_validator() -> None:
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2] / "schemas" / "holdout_access_event_v1.json"
        ).read_text(encoding="ascii")
    )
    branches = {branch["properties"]["event_type"]["const"]: branch for branch in schema["oneOf"]}
    assert schema["properties"]["event_type"]["enum"] == [item.value for item in EventType]
    envelope = set(schema["required"])
    for event_type in EventType:
        branch = branches[event_type.value]
        assert set(branch["propertyNames"]["enum"]) == envelope | hr.FIELDS[event_type]
        assert set(branch["required"]) == hr.FIELDS[event_type]
    assert branches["access_denied"]["properties"]["reason"]["enum"] == [
        item.value for item in hr.DenialReason
    ]
    assert branches["access_attempt_refused"]["properties"]["reason"]["enum"] == [
        item.value for item in hr.RefusalReason
    ]
    components = schema["$defs"]["candidate_identity"]["properties"]["components"]
    assert set(components["required"]) == {item.value for item in hr.Component}
    builder = Builder()
    builder.started()
    document = json.loads(builder.state.events[-1].line)
    assert set(document) == envelope | hr.FIELDS[EventType.ACCESS_STARTED]


# ----- red-team repair regressions -----


@pytest.mark.parametrize(
    "bad", ["HAL-0001", "HAL-0004", "HAL-00005", "HAL-005", "HAL-\u0665\u0665\u0665\u0665"]
)
def test_malformed_event_ids_are_rejected_by_python_and_the_schema(bad: str) -> None:
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2] / "schemas" / "holdout_access_event_v1.json"
        ).read_text(encoding="ascii")
    )
    pattern = schema["$defs"]["event_id"]["pattern"]
    assert pattern == "^" + hr.EVENT_ID_PATTERN + "$"
    assert re.search(pattern, bad) is None
    assert re.fullmatch(hr.EVENT_ID_PATTERN, bad) is None
    builder = Builder()
    assert builder.state.by_id(bad) is None
    with pytest.raises(HoldoutRecordError):
        hr.verify_ledger(mutate_last(builder.data, lambda d: d.update(event_id=bad)))
    for good in ("HAL-0005", "HAL-0010", "HAL-9999", "HAL-10000"):
        assert re.search(pattern, good) is not None


def test_the_schema_evaluation_plan_is_exactly_one_repository_file() -> None:
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2] / "schemas" / "holdout_access_event_v1.json"
        ).read_text(encoding="ascii")
    )
    plan = schema["$defs"]["candidate_identity"]["properties"]["components"]["properties"][
        "evaluation_plan"
    ]
    assert plan == {
        "type": "array",
        "minItems": 1,
        "maxItems": 1,
        "items": {"$ref": "#/$defs/repo_file_ref"},
    }
    assert schema["$defs"]["repo_file_ref"]["properties"]["kind"] == {"const": "repo_file"}
    document = identity()
    document["components"]["evaluation_plan"] = [
        {
            "artifact_name": "plan.md",
            "kind": "run_artifact",
            "run_id": "20261014T050000.000000Z_" + "a" * 32,
            "sha256": "2" * 64,
        }
    ]
    with pytest.raises(HoldoutRecordError, match="exactly one repository file"):
        hr.validate_candidate_identity(document)


def test_log_initialized_must_equal_the_fields_derived_from_the_reviewed_legacy() -> None:
    builder = Builder()
    hr.require_initialization(builder.state, LEGACY)
    forged_legacy = LEGACY.replace(b"Append-only.", b"Editable.")
    forged = {**hr.initialization_fields(forged_legacy), "legacy_file_sha256": sha256_hex(LEGACY)}
    other = LogState()
    line = hr.encode_event(other, EventType.LOG_INITIALIZED, TS, REPOSITORY, forged)
    forged_state = hr.verify_ledger(line)
    with pytest.raises(HoldoutRecordError, match="derived from the reviewed legacy"):
        hr.require_initialization(forged_state, LEGACY)


def test_interrupted_accesses_keep_their_evidence_hash() -> None:
    builder = Builder()
    started = builder.started()
    event = builder.add(
        EventType.ACCESS_INTERRUPTED,
        {
            "reason": "process_crash",
            "recorded_by": "project_owner",
            "restricted_evidence_sha256": "e" * 64,
            "started": builder.ref(started),
        },
    )
    assert event.fields["restricted_evidence_sha256"] == "e" * 64
    assert (
        "Restricted evidence `" + "e" * 64 + "`" in hr.render_entry(builder.state, event).decode()
    )


def test_multiple_open_authorizations_are_shown_as_multiple() -> None:
    builder = Builder()
    builder.cycle()
    builder.holdout()
    first = builder.authorize(builder.request())
    second = builder.authorize(builder.request())
    status = hr.render_status(builder.state).decode()
    assert (
        f"| Gate currently authorized to open it | Multiple open authorizations (2): "
        f"{first.event_id}, {second.event_id} |"
    ) in status
    builder.start(first)
    status = hr.render_status(builder.state).decode()
    assert "None — opening requires" in status


def test_the_opened_status_never_claims_more_than_repository_evidence() -> None:
    builder = Builder()
    status = hr.render_status(builder.state).decode()
    assert (
        "| Protected holdout ever opened | No repository evidence of protected-holdout access"
        in status
    )
    assert "not knowable from this log" in status
    assert "| Protected holdout ever opened | No —" not in status
