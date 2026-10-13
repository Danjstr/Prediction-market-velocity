"""Tests for the pure experiment-ledger verifier, state machine, and eligibility rules."""

import dataclasses
import json
from collections.abc import Callable
from typing import Any

import pytest

from pmv.experiment_ledger import (
    Checkpoint,
    EvidenceFile,
    LedgerError,
    LedgerEvent,
    LedgerState,
    PendingRepairError,
    TornTailError,
    _eligible_at_start,
    checkpoint_line,
    completion_manifest_bytes,
    effective_run_class,
    eligibility_as_of,
    encode_entry,
    evidence_name,
    parse_checkpoints,
    parse_evidence_name,
    parse_pending_marker_name,
    pending_evidence,
    pending_marker_name,
    start_eligibility,
    store_id_of,
    verify_checkpoints,
    verify_ledger,
)
from pmv.experiment_spec import SECTION_NAMES, ExecutionIdentity, RunClass, SpecError
from pmv.integrity import canonical_line, chain_entry_sha256, sha256_hex

TS = "2026-10-13T03:40:21.123456Z"
STORE = "0" * 32


def rid(letter: str) -> str:
    return "20261013T034021.123456Z_" + letter * 32


def make_identity(*, clean: bool = True) -> ExecutionIdentity:
    return ExecutionIdentity(
        spec_sha256="1" * 64,
        code_commit="a" * 40 if clean else None,
        code_tree_dirty=False if clean else None,
        dirty_tree_sha256=None,
        package_version="0.0.0",
        uv_lock_sha256="2" * 64,
        installed_environment_sha256=None,
        app_config_sha256="3" * 64,
        config_section_sha256=dict.fromkeys(SECTION_NAMES),
        python_version="3.13.5",
        platform="linux-x86_64",
        entrypoint="pmv.research.baselines:run",
    )


class Builder:
    def __init__(self) -> None:
        self.data = b""
        self.state: LedgerState = verify_ledger(b"")[0]
        self.add(LedgerEvent.LEDGER_CREATED, None, {"store_id": STORE})

    def add(self, event: LedgerEvent, run_id: str | None, fields: dict[str, object]) -> bytes:
        line = encode_entry(self.state, event, run_id, TS, fields)
        self.state = verify_ledger(self.data + line)[0]
        self.data += line
        return line

    def reserve(self, run_id: str, run_class: RunClass = RunClass.EVIDENCE_CANDIDATE) -> None:
        self.add(LedgerEvent.RUN_RESERVED, run_id, {"run_class": run_class.value, "study_id": "s"})

    def start(
        self,
        run_id: str,
        identity: ExecutionIdentity,
        inputs: list[dict[str, object]] | None = None,
        *,
        claim_eligible: bool | None = None,
    ) -> None:
        resolved = inputs or []
        requested = self.state.runs[run_id].requested_class
        effective = effective_run_class(requested, identity)
        eligible = start_eligibility(self.state, self.state.head_seq, effective, identity, resolved)
        self.add(
            LedgerEvent.RUN_STARTED,
            run_id,
            {
                "effective_run_class_at_start": effective.value,
                "evidence_eligible_at_start": eligible
                if claim_eligible is None
                else claim_eligible,
                "execution_identity": identity.to_json(),
                "execution_identity_sha256": identity.sha256(),
                "inputs": resolved,
                "spec_sha256": identity.spec_sha256,
                "spec_size_bytes": 100,
            },
        )

    def artifact(self, run_id: str, name: str, digest: str = "5" * 64) -> None:
        self.add(
            LedgerEvent.ARTIFACT_REGISTERED,
            run_id,
            {
                "artifact_schema_id": None,
                "artifact_schema_version": None,
                "artifact_type": "model",
                "media_type": "binary",
                "name": name,
                "sha256": digest,
                "size_bytes": 10,
            },
        )

    def metric(self, run_id: str, split: str = "development") -> None:
        self.add(
            LedgerEvent.METRIC_RECORDED,
            run_id,
            {
                "fold": None,
                "name": "log_loss",
                "split": split,
                "step": None,
                "unit": None,
                "value": {"text": "0.69", "type": "decimal"},
            },
        )

    def complete(self, run_id: str) -> bytes:
        manifest = completion_manifest_bytes(self.state, run_id)
        run = self.state.runs[run_id]
        self.add(
            LedgerEvent.RUN_COMPLETED,
            run_id,
            {
                "artifact_count": len(run.artifacts),
                "manifest_sha256": sha256_hex(manifest),
                "metric_count": len(run.metrics),
            },
        )
        return manifest


def completed_run(builder: Builder, run_id: str, **identity_options: bool) -> None:
    builder.reserve(run_id)
    builder.start(run_id, make_identity(**identity_options))
    builder.artifact(run_id, "model.bin")
    builder.metric(run_id)
    builder.complete(run_id)


def lines(data: bytes) -> list[bytes]:
    return data.split(b"\n")[:-1]


def join(items: list[bytes]) -> bytes:
    return b"".join(item + b"\n" for item in items)


# ----- chain integrity -----


def test_completion_manifest_is_pre_terminal_and_reproducible() -> None:
    builder = Builder()
    builder.reserve(rid("a"))
    builder.start(rid("a"), make_identity())
    builder.artifact(rid("a"), "model.bin")
    builder.metric(rid("a"))
    manifest = builder.complete(rid("a"))
    assert completion_manifest_bytes(builder.state, rid("a")) == manifest
    document = json.loads(manifest)
    completed_entry = builder.state.entries[-1]
    assert document["ledger_seq_last_preterminal"] == completed_entry.seq - 1
    assert completed_entry.sha256 not in manifest.decode()
    assert "manifest_sha256" not in document
    assert document["last_preterminal_entry_sha256"] == builder.state.entries[-2].sha256


def test_altered_entries_are_detected() -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    items = lines(builder.data)
    altered = json.loads(items[4])
    altered["value"]["text"] = "0.01"
    items[4] = json.dumps(altered, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(LedgerError, match="line 5 has an invalid entry_sha256"):
        verify_ledger(join(items))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda items: [items[0], items[2], items[1], *items[3:]], "continuity"),
        (lambda items: [items[0], items[1], *items[3:]], "continuity"),
        (lambda items: [items[0], items[1], items[1], *items[2:]], "continuity"),
    ],
    ids=["reordered", "interior-deleted", "duplicated"],
)
def test_reordered_deleted_duplicated_entries_are_detected(mutate: object, message: str) -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    with pytest.raises(LedgerError, match=message):
        verify_ledger(join(mutate(lines(builder.data))))  # type: ignore[operator]  # parametrized


def test_end_truncation_is_detected_only_with_a_checkpoint() -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    checkpoint = Checkpoint(builder.state.head_seq, builder.state.head_sha256 or "", TS)
    truncated = join(lines(builder.data)[:-1])
    state, _ = verify_ledger(truncated)
    with pytest.raises(LedgerError, match="beyond the verified ledger head"):
        verify_checkpoints(state, [checkpoint])
    verify_checkpoints(builder.state, [checkpoint])


def test_checkpoint_file_parsing() -> None:
    first = checkpoint_line(1, "a" * 64, TS)
    second = checkpoint_line(4, "b" * 64, TS)
    assert [item.ledger_seq for item in parse_checkpoints(first + second)] == [1, 4]
    with pytest.raises(LedgerError, match="does not increase"):
        parse_checkpoints(second + first)
    with pytest.raises(LedgerError, match="incomplete"):
        parse_checkpoints(first[:-3])


def test_torn_tail_versus_malformed_complete_line() -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    with pytest.raises(TornTailError) as excinfo:
        verify_ledger(builder.data + b'{"partial')
    assert excinfo.value.offset == len(builder.data)
    with pytest.raises(LedgerError, match="not canonical JSON"):
        verify_ledger(builder.data + b'{"partial\n')


# ----- state machine -----


@pytest.mark.parametrize(
    "illegal",
    [
        lambda b: b.metric(rid("a")),
        lambda b: b.artifact(rid("a"), "late.bin"),
        lambda b: b.start(rid("a"), make_identity()),
        lambda b: b.add(LedgerEvent.RUN_ABORTED, rid("a"), {"reason": "operator_request"}),
        lambda b: b.reserve(rid("a")),
        lambda b: b.add(
            LedgerEvent.RUN_SUPERSEDED,
            rid("a"),
            {"reason": "corrected_code", "superseded_by": rid("a")},
        ),
    ],
    ids=[
        "metric-after-complete",
        "artifact-after-complete",
        "restart",
        "abort-after-complete",
        "re-reserve",
        "self-supersede",
    ],
)
def test_completed_runs_are_immutable(illegal: object) -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    with pytest.raises(LedgerError):
        illegal(builder)  # type: ignore[operator]  # parametrized


def test_other_illegal_events() -> None:
    builder = Builder()
    builder.reserve(rid("a"))
    with pytest.raises(LedgerError, match="not allowed for a reserved run"):
        builder.metric(rid("a"))
    builder.start(rid("a"), make_identity())
    builder.artifact(rid("a"), "model.bin")
    with pytest.raises(LedgerError, match="already registered"):
        builder.artifact(rid("a"), "model.bin")
    with pytest.raises(LedgerError, match="protected_holdout"):
        builder.metric(rid("a"), split="protected_holdout")
    with pytest.raises(LedgerError, match="unknown run"):
        builder.metric(rid("f"))
    with pytest.raises(LedgerError, match="counts do not match"):
        builder.add(
            LedgerEvent.RUN_COMPLETED,
            rid("a"),
            {"artifact_count": 5, "manifest_sha256": "1" * 64, "metric_count": 0},
        )


# ----- evidence eligibility -----


def test_forged_eligibility_is_rejected() -> None:
    builder = Builder()
    builder.reserve(rid("a"))
    with pytest.raises(LedgerError, match="evidence_eligible_at_start is wrong"):
        builder.start(rid("a"), make_identity(), claim_eligible=True)


def test_v1_runs_without_an_installed_environment_fingerprint_are_never_eligible() -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    assert not builder.state.runs[rid("a")].eligible_at_start
    assert not eligibility_as_of(builder.state, rid("a"), builder.state.head_seq)


def test_dirty_code_forces_exploratory_and_ineligible() -> None:
    builder = Builder()
    builder.reserve(rid("a"))
    builder.start(rid("a"), make_identity(clean=False))
    run = builder.state.runs[rid("a")]
    assert run.start_fields["effective_run_class_at_start"] == "exploratory"
    assert not run.eligible_at_start


def artifact_input(run_id: str, name: str = "model.bin") -> dict[str, object]:
    return {"artifact_name": name, "kind": "run_artifact", "run_id": run_id, "sha256": "5" * 64}


def mark_eligible(builder: Builder, *run_ids: str) -> None:
    """Pure-function seam: no v1 ledger can hold an eligible run (Option B), so the
    as-of rules a future approved fingerprint would enable are tested on in-memory state."""
    for run_id in run_ids:
        builder.state.runs[run_id].eligible_at_start = True


def test_eligibility_is_transitive_and_temporal() -> None:
    builder = Builder()
    completed_run(builder, rid("b"))
    builder.reserve(rid("c"))
    builder.start(rid("c"), make_identity(), [artifact_input(rid("b"))])
    builder.artifact(rid("c"), "model.bin")
    builder.complete(rid("c"))
    before_supersede = builder.state.head_seq
    completed_run(builder, rid("d"))
    builder.add(
        LedgerEvent.RUN_SUPERSEDED,
        rid("b"),
        {"reason": "corrected_code", "superseded_by": rid("d")},
    )
    verify_ledger(builder.data)
    assert not eligibility_as_of(builder.state, rid("c"), before_supersede)
    mark_eligible(builder, rid("b"), rid("c"), rid("d"))
    assert eligibility_as_of(builder.state, rid("c"), before_supersede)
    assert not eligibility_as_of(builder.state, rid("c"), builder.state.head_seq)
    assert not eligibility_as_of(builder.state, rid("b"), builder.state.head_seq)
    assert eligibility_as_of(builder.state, rid("d"), builder.state.head_seq)
    assert not eligibility_as_of(builder.state, rid("d"), before_supersede)


def test_start_rules_taint_consumers_of_ineligible_inputs() -> None:
    builder = Builder()
    completed_run(builder, rid("b"))
    completed_run(builder, rid("e"), clean=False)
    mark_eligible(builder, rid("b"))
    head = builder.state.head_seq
    candidate = RunClass.EVIDENCE_CANDIDATE

    def eligible(inputs: list[dict[str, object]], *, fingerprinted: bool = True) -> bool:
        return _eligible_at_start(
            builder.state, head, candidate, environment_fingerprinted=fingerprinted, inputs=inputs
        )

    assert eligible([artifact_input(rid("b"))])
    assert not eligible([artifact_input(rid("b"))], fingerprinted=False)
    assert not eligible([artifact_input(rid("e"))])
    assert not _eligible_at_start(
        builder.state, head, RunClass.DEVELOPMENT, environment_fingerprinted=True, inputs=[]
    )
    raw = {"capture_id": rid("f"), "kind": "raw_capture", "manifest_sha256": "6" * 64}
    assert eligible([{**raw, "capture_code_clean": True}])
    assert not eligible([{**raw, "capture_code_clean": False}])


def test_ineligible_producers_and_dirty_raw_captures_taint_consumers() -> None:
    builder = Builder()
    completed_run(builder, rid("b"), clean=False)
    builder.reserve(rid("c"))
    builder.start(rid("c"), make_identity(), [artifact_input(rid("b"))])
    assert not builder.state.runs[rid("c")].eligible_at_start
    builder.reserve(rid("d"))
    raw = {
        "capture_code_clean": False,
        "capture_id": rid("e"),
        "kind": "raw_capture",
        "manifest_sha256": "6" * 64,
    }
    builder.start(rid("d"), make_identity(), [raw])
    assert not builder.state.runs[rid("d")].eligible_at_start


def test_run_artifact_inputs_require_a_completed_producer_and_exact_hash() -> None:
    builder = Builder()
    builder.reserve(rid("b"))
    builder.start(rid("b"), make_identity())
    builder.artifact(rid("b"), "model.bin")
    builder.reserve(rid("c"))
    with pytest.raises(LedgerError, match="producer is not completed"):
        builder.start(rid("c"), make_identity(), [artifact_input(rid("b"))])
    builder.complete(rid("b"))
    wrong = {**artifact_input(rid("b")), "sha256": "7" * 64}
    with pytest.raises(LedgerError, match="does not match a registered artifact"):
        builder.start(rid("c"), make_identity(), [wrong])


# ----- repair evidence -----


def repair_fields(state: LedgerState, offset: int, torn: bytes) -> dict[str, object]:
    name = evidence_name(
        offset=offset,
        length=len(torn),
        original_size=offset + len(torn),
        last_seq=state.head_seq,
        last_sha256=state.head_sha256,
        torn_sha256=sha256_hex(torn),
    )
    return {
        "last_valid_entry_sha256": state.head_sha256,
        "last_valid_ledger_seq": state.head_seq,
        "original_ledger_size": offset + len(torn),
        "repair_evidence_name": name,
        "torn_byte_length": len(torn),
        "torn_byte_offset": offset,
        "torn_sha256": sha256_hex(torn),
    }


def test_repair_events_and_evidence_must_agree() -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    torn = b'{"partial'
    fields = repair_fields(builder.state, len(builder.data), torn)
    name = str(fields["repair_evidence_name"])
    evidence = [EvidenceFile(name, len(torn), sha256_hex(torn))]
    assert pending_evidence(builder.state, evidence) == evidence
    builder.add(LedgerEvent.LEDGER_TAIL_REPAIRED, None, fields)
    assert pending_evidence(builder.state, evidence) == []
    with pytest.raises(LedgerError, match="missing"):
        pending_evidence(builder.state, [])
    with pytest.raises(LedgerError, match="content does not match"):
        pending_evidence(builder.state, [EvidenceFile(name, len(torn), "0" * 64)])
    with pytest.raises(LedgerError, match="unexpected file"):
        pending_evidence(builder.state, [*evidence, EvidenceFile("notes.txt", 1, "0" * 64)])
    with pytest.raises(LedgerError, match="referenced twice"):
        builder.add(LedgerEvent.LEDGER_TAIL_REPAIRED, None, fields)


def test_repair_event_offsets_must_match_the_ledger() -> None:
    builder = Builder()
    completed_run(builder, rid("a"))
    fields = repair_fields(builder.state, len(builder.data) + 5, b"xyz")
    with pytest.raises(LedgerError):
        builder.add(LedgerEvent.LEDGER_TAIL_REPAIRED, None, fields)
    assert PendingRepairError.__mro__[1] is LedgerError


# ----- red-team regressions: genesis, Option B, strict integers, ASCII, manifests -----


def rehash(document: dict[str, object]) -> bytes:
    body = {key: value for key, value in document.items() if key != "entry_sha256"}
    return canonical_line({**body, "entry_sha256": chain_entry_sha256(body)})


def mutate_last(data: bytes, change: Callable[[dict[str, Any]], None]) -> bytes:
    items = lines(data)
    document = json.loads(items[-1])
    change(document)
    return join(items[:-1]) + rehash(document)


def test_entry_zero_is_always_and_only_ledger_created() -> None:
    builder = Builder()
    builder.reserve(rid("a"))
    items = lines(builder.data)
    reserve = json.loads(items[1])
    reserve.update(ledger_seq=0, prev_entry_sha256=None)
    with pytest.raises(LedgerError, match="only the first entry is ledger_created"):
        verify_ledger(rehash(reserve))
    with pytest.raises(LedgerError, match="only the first entry is ledger_created"):
        builder.add(LedgerEvent.LEDGER_CREATED, None, {"store_id": STORE})
    genesis = json.loads(items[0])
    genesis["run_id"] = rid("a")
    with pytest.raises(LedgerError, match="has no run_id"):
        verify_ledger(rehash(genesis))
    for bad in ("A" * 32, "0" * 31, 7):
        genesis = {**json.loads(items[0]), "run_id": None, "store_id": bad}
        with pytest.raises(LedgerError, match="store_id is malformed"):
            verify_ledger(rehash(genesis))
    assert store_id_of(builder.state) == STORE


def test_a_non_null_installed_environment_fingerprint_is_rejected_in_v1() -> None:
    with pytest.raises(SpecError, match="must be null in v1"):
        dataclasses.replace(make_identity(), installed_environment_sha256="9" * 64)
    builder = Builder()
    builder.reserve(rid("a"))
    identity = make_identity().to_json()
    identity["installed_environment_sha256"] = "9" * 64
    with pytest.raises(LedgerError, match="must be null in v1"):
        builder.add(
            LedgerEvent.RUN_STARTED,
            rid("a"),
            {
                "effective_run_class_at_start": "evidence_candidate",
                "evidence_eligible_at_start": True,
                "execution_identity": identity,
                "execution_identity_sha256": sha256_hex(canonical_line(identity)),
                "inputs": [],
                "spec_sha256": identity["spec_sha256"],
                "spec_size_bytes": 100,
            },
        )


def completed_without_metrics(builder: Builder, run_id: str) -> None:
    builder.reserve(run_id)
    builder.start(run_id, make_identity())
    builder.artifact(run_id, "model.bin")
    builder.complete(run_id)


def started(builder: Builder) -> Builder:
    builder.reserve(rid("a"))
    builder.start(rid("a"), make_identity())
    return builder


def with_metric_step(builder: Builder) -> Builder:
    started(builder)
    builder.add(
        LedgerEvent.METRIC_RECORDED,
        rid("a"),
        {
            "fold": None,
            "name": "log_loss",
            "split": "development",
            "step": 1,
            "unit": None,
            "value": {"text": "1", "type": "integer"},
        },
    )
    return builder


def with_artifact(builder: Builder) -> Builder:
    started(builder)
    builder.artifact(rid("a"), "model.bin")
    return builder


def with_schema_artifact(builder: Builder) -> Builder:
    started(builder)
    builder.add(
        LedgerEvent.ARTIFACT_REGISTERED,
        rid("a"),
        {
            "artifact_schema_id": "predictions",
            "artifact_schema_version": 1,
            "artifact_type": "predictions",
            "media_type": "csv",
            "name": "predictions.csv",
            "sha256": "5" * 64,
            "size_bytes": 1,
        },
    )
    return builder


def with_one_byte_repair(builder: Builder) -> Builder:
    completed_run(builder, rid("a"))
    builder.add(
        LedgerEvent.LEDGER_TAIL_REPAIRED,
        None,
        repair_fields(builder.state, len(builder.data), b"x"),
    )
    return builder


def set_identity_schema_version(document: dict[str, Any]) -> None:
    document["execution_identity"]["schema_version"] = True
    document["execution_identity_sha256"] = sha256_hex(
        canonical_line(document["execution_identity"])
    )


@pytest.mark.parametrize(
    ("build", "change"),
    [
        (lambda b: completed_run(b, rid("a")), lambda d: d.update(schema_version=True)),
        (lambda b: b.reserve(rid("a")), lambda d: d.update(ledger_seq=True)),
        (lambda b: completed_run(b, rid("a")), lambda d: d.update(artifact_count=True)),
        (lambda b: completed_without_metrics(b, rid("a")), lambda d: d.update(metric_count=False)),
        (started, lambda d: d.update(spec_size_bytes=True)),
        (started, set_identity_schema_version),
        (with_metric_step, lambda d: d.update(step=True)),
        (with_artifact, lambda d: d.update(size_bytes=True)),
        (with_schema_artifact, lambda d: d.update(artifact_schema_version=True)),
        (with_one_byte_repair, lambda d: d.update(torn_byte_length=True)),
    ],
    ids=[
        "schema_version",
        "ledger_seq",
        "artifact_count",
        "metric_count",
        "spec_size_bytes",
        "identity_schema_version",
        "step",
        "size_bytes",
        "artifact_schema_version",
        "torn_byte_length",
    ],
)
def test_booleans_are_never_accepted_as_integers(
    build: Callable[[Builder], object], change: Callable[[dict[str, Any]], None]
) -> None:
    builder = Builder()
    build(builder)
    with pytest.raises(LedgerError):
        verify_ledger(mutate_last(builder.data, change))


def test_checkpoints_reject_boolean_integers() -> None:
    for change in ({"schema_version": True}, {"ledger_seq": True}):
        document = {**json.loads(checkpoint_line(1, "a" * 64, TS)), **change}
        with pytest.raises(LedgerError, match="v1 schema"):
            parse_checkpoints(canonical_line(document))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(recorded_at="2026-10-13T03:40:21.12345\u0666Z"),
        lambda d: d.update(run_id="2026101\u06633T034021.123456Z_" + "a" * 32),
    ],
    ids=["recorded_at", "run_id"],
)
def test_non_ascii_digits_are_rejected(change: Callable[[dict[str, Any]], None]) -> None:
    builder = Builder()
    builder.reserve(rid("a"))
    with pytest.raises(LedgerError):
        verify_ledger(mutate_last(builder.data, change))


def test_spec_size_must_be_positive_and_inputs_must_not_repeat() -> None:
    builder = started(Builder())
    for size in (0, 1_048_577):

        def set_size(document: dict[str, Any], size: int = size) -> None:
            document["spec_size_bytes"] = size

        with pytest.raises(LedgerError, match="spec_size_bytes"):
            verify_ledger(mutate_last(builder.data, set_size))
    builder = Builder()
    completed_run(builder, rid("b"))
    builder.reserve(rid("c"))
    with pytest.raises(LedgerError, match="must not repeat"):
        builder.start(
            rid("c"), make_identity(), [artifact_input(rid("b")), artifact_input(rid("b"))]
        )


def test_run_completed_must_carry_the_rebuilt_manifest_hash() -> None:
    builder = started(Builder())
    builder.artifact(rid("a"), "model.bin")
    with pytest.raises(LedgerError, match="rebuilt manifest"):
        builder.add(
            LedgerEvent.RUN_COMPLETED,
            rid("a"),
            {"artifact_count": 1, "manifest_sha256": "1" * 64, "metric_count": 0},
        )
    manifest = builder.complete(rid("a"))
    assert builder.state.runs[rid("a")].manifest_sha256 == sha256_hex(manifest)


def test_evidence_names_use_canonical_ascii_numbers() -> None:
    torn = sha256_hex(b"x")
    assert parse_evidence_name(f"torn-7-1-8-none-none-{torn}.bin") is not None
    for bad in (
        f"torn-07-1-8-none-none-{torn}.bin",
        f"torn-7-0-7-none-none-{torn}.bin",
        "torn-\u0667" + f"-1-8-none-none-{torn}.bin",
    ):
        assert parse_evidence_name(bad) is None


def test_pending_marker_names_bind_the_store_and_the_evidence() -> None:
    evidence = f"torn-7-1-8-6-{'a' * 64}-{sha256_hex(b'x')}.bin"
    name = pending_marker_name(STORE, evidence)
    assert parse_pending_marker_name(name) == (STORE, evidence)
    for bad in (name.replace(STORE, "A" * 32), name + "x", "repair-pending-" + evidence):
        assert parse_pending_marker_name(bad) is None
