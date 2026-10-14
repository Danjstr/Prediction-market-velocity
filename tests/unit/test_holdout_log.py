"""Integration tests for the protected-holdout access log (synthetic data only)."""

import io
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import pmv.holdout_log as holdout_log
from pmv import holdout_record as hr
from pmv.config import LoggingConfig, LogLevel
from pmv.experiment_spec import (
    ArtifactType,
    MediaType,
    RunClass,
    RunSpec,
    Seed,
    Split,
    spec_sections,
)
from pmv.experiments import ExperimentStore
from pmv.gate_record import Decision, DocumentKind, GateId
from pmv.gates import DocumentEvidence, GateRequest, Supersedes, create_gate_record
from pmv.holdout_log import (
    AccessRefusedError,
    CandidateSpec,
    FileRef,
    HoldoutLog,
    HoldoutLogError,
    HoldoutLogIntegrityError,
    MirrorBehindError,
    NotReadyError,
    RecordRef,
    main,
)
from pmv.holdout_record import (
    ActorRole,
    Component,
    EventType,
    RefusalReason,
    SplitFormation,
)
from pmv.integrity import sha256_hex
from pmv.log import configure_logging

REPO = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 10, 14, 5, 0, tzinfo=UTC)
LEGACY = (
    "# Holdout Access Log\n\nIntro.\n\n---\n\n"
    "## Current Status\n\n| Item | Value |\n|---|---|\n| Last event | HAL-0004 |\n\n"
    "The status section summarizes the history below. It is a summary.\n\n---\n\n"
    "## Immutability\n\nAppend-only.\n\n---\n\n## Event Schema\n\nFields.\n\n---\n\n"
    "## Access History (append-only)\n\n"
    "### HAL-0001 — Log initialization\n\n- Event ID: HAL-0001\n\n"
    "### HAL-0004 — Correction of HAL-0001\n\n- Event ID: HAL-0004\n"
).encode()
LEGACY_SHA = sha256_hex(LEGACY)
CONFIG = 'schema_version = 1\nenvironment = "test"\n\n[logging]\nlevel = "INFO"\n'
LEDGER = hr.LEDGER_PATH
LOG = hr.LOG_PATH


def git(repo: Path, *arguments: str) -> bytes:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Owner",
        "GIT_AUTHOR_EMAIL": "owner@example.invalid",
        "GIT_COMMITTER_NAME": "Owner",
        "GIT_COMMITTER_EMAIL": "owner@example.invalid",
    }
    return subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(repo), "-c", "commit.gpgsign=false", *arguments],
        env=environment,
        capture_output=True,
        check=True,
    ).stdout


def commit(repo: Path, message: str = "change") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


CLOCK = Clock()


def write(repo: Path, path: str, data: str) -> FileRef:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data, encoding="utf-8")
    return FileRef(path, sha256_hex(target.read_bytes()))


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / LOG).write_bytes(LEGACY)
    for name in ("CLAUDE.md", "PROJECT_BRIEF.md", "START_HERE.md"):
        write(root, name, f"# {name}\n")
    write(root, "configs/test.toml", CONFIG)
    write(root, "scripts/check.sh", "#!/bin/sh\nexit 0\n")
    (root / "scripts" / "check.sh").chmod(0o755)
    write(root, "docs/plan.md", "Preregistered evaluation plan.\n")
    write(root, "docs/other_plan.md", "Another plan.\n")
    write(root, "docs/dev.md", "Development subset.\n")
    write(root, "docs/correction.md", "Correction note.\n")
    write(root, "research/splits/split_a.yaml", "split: a\n")
    for component in Component:
        write(root, f"src/candidate/{component.value}.txt", f"{component.value}\n")
    git(root, "init", "-q", "-b", "main")
    commit(root, "baseline")
    yield root
    gates = root / "docs" / "decisions" / "gates"
    if gates.is_dir():
        for item in gates.iterdir():
            item.chmod(0o644)


@pytest.fixture
def store(tmp_path: Path, repo: Path) -> Iterator[ExperimentStore]:
    root = tmp_path / "exp-root"
    root.mkdir(mode=0o700)
    with ExperimentStore(
        root, repo_root=repo, app_config_sha256="0" * 64, checkpoint_file=tmp_path / "cp.jsonl"
    ) as opened:
        handle = opened.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        handle.start(
            RunSpec(
                study_id="velocity_baseline",
                entrypoint="pmv.research.baselines:run",
                sections=spec_sections(model={"family": "logistic"}),
                seeds=(Seed("numpy", 7),),
                splits_accessed=(Split.TRAIN,),
            )
        )
        handle.write_artifact(
            "model.bin", b"model", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
        )
        handle.complete()
        yield opened
    for directory, _subdirs, _files in os.walk(root):
        os.chmod(directory, 0o700)


def new_log(repo: Path, store: ExperimentStore | None = None, **options: Any) -> HoldoutLog:
    options.setdefault("clock", CLOCK)
    return HoldoutLog(repo, experiment_store=store, reviewed_legacy_sha256=LEGACY_SHA, **options)


def spec(repo: Path, store: ExperimentStore, **changes: Any) -> CandidateSpec:
    run_id = next(iter(store.snapshot().runs))
    digest = store.snapshot().runs[run_id].artifacts["model.bin"][0]["sha256"]
    components: dict[Component, list[dict[str, object]]] = {
        component: [
            {
                "kind": "repo_file",
                "path": f"src/candidate/{component.value}.txt",
                "sha256": sha256_hex((repo / f"src/candidate/{component.value}.txt").read_bytes()),
            }
        ]
        for component in Component
    }
    components[Component.MODEL] = [
        {"artifact_name": "model.bin", "kind": "run_artifact", "run_id": run_id, "sha256": digest}
    ]
    components[Component.EVALUATION_PLAN] = [
        {
            "kind": "repo_file",
            "path": "docs/plan.md",
            "sha256": sha256_hex((repo / "docs/plan.md").read_bytes()),
        }
    ]
    values: dict[str, Any] = {
        "cycle_id": "cycle_a",
        "holdout_id": "holdout_a",
        "candidate_id": "cand_a",
        "components": components,
    }
    values.update(changes)
    return CandidateSpec(**values)


def gate(
    repo: Path,
    gate_id: GateId,
    *,
    decision: Decision = Decision.PASS,
    plan: str = "docs/plan.md",
    candidate_id: str = "cand_a",
    supersedes: Supersedes | None = None,
) -> RecordRef:
    plan_ref = DocumentEvidence(plan, sha256_hex((repo / plan).read_bytes()), DocumentKind.PLAN)
    created = create_gate_record(
        repo,
        GateRequest(
            gate_id=gate_id,
            decision=decision,
            approval_attested=True,
            reasons=() if decision is Decision.PASS else ("criteria_not_met",),
            cycle_id="cycle_a",
            candidate_id=candidate_id,
            documents=(plan_ref,),
            supersedes=supersedes,
        ),
        check_runner=lambda _repo: True,
        clock=CLOCK,
    )
    commit(repo, f"record {gate_id.value}")
    return RecordRef(created.record_id, created.sha256)


@dataclass
class Prepared:
    log: HoldoutLog
    request: hr.Event
    authorization: hr.Event
    gate_6: RecordRef


def initialized(repo: Path, store: ExperimentStore | None = None) -> HoldoutLog:
    log = new_log(repo, store)
    log.initialize()
    commit(repo, "initialize holdout log")
    return log


def registered(repo: Path, store: ExperimentStore) -> HoldoutLog:
    log = initialized(repo, store)
    log.register_cycle(
        "cycle_a",
        SplitFormation.MECHANICAL_PARTITION,
        FileRef("docs/dev.md", sha256_hex((repo / "docs/dev.md").read_bytes())),
        T0 + timedelta(days=30),
        T0 + timedelta(days=60),
        attested=True,
    )
    commit(repo, "register cycle")
    log.register_holdout(
        "holdout_a",
        "cycle_a",
        FileRef(
            "research/splits/split_a.yaml",
            sha256_hex((repo / "research/splits/split_a.yaml").read_bytes()),
        ),
        snapshot_manifest_sha256="8" * 64,
        metadata_sha256="6" * 64,
        observation_count=1200,
        start=T0 + timedelta(days=30),
        end=T0 + timedelta(days=60),
        purge_embargo_sha256="7" * 64,
        source_manifest_sha256="9" * 64,
        attested=True,
    )
    commit(repo, "register holdout")
    return log


def prepared(repo: Path, store: ExperimentStore) -> Prepared:
    log = registered(repo, store)
    request = log.request_access(spec(repo, store), ActorRole.STATISTICIAN)
    commit(repo, "request")
    gate_6 = gate(repo, GateId.GATE_6)
    authorization = log.authorize(request.event_id, gate_6, attested=True)
    commit(repo, "authorize")
    return Prepared(log, request, authorization, gate_6)


def start(ready: Prepared, gate_7: RecordRef) -> hr.Event:
    return ready.log.start(
        ready.authorization.event_id, gate_7, operator=ActorRole.AUTHORIZED_OPERATOR, attested=True
    )


def last_event(repo: Path) -> hr.Event:
    state = new_log(repo).state()
    assert state is not None
    return state.events[-1]


# ----- initialization -----


def test_initialization_inserts_the_section_once_and_preserves_every_other_byte(repo: Path) -> None:
    log = new_log(repo)
    assert log.state() is None
    event = log.initialize()
    assert event.event_id == "HAL-0005"
    data = (repo / LOG).read_bytes()
    assert data.count(b"## Machine-Readable Ledger") == 1
    preamble, _status, before, after, history = hr.split_legacy_file(LEGACY)
    assert data.startswith(preamble)
    assert before + hr.MACHINE_LEDGER_SECTION.encode() + after + history in data
    assert data.index(history) < data.index("### HAL-0005 — Machine ledger initialized".encode())
    assert b"| Last event | HAL-0005 |" in data
    assert (repo / LEDGER).read_bytes().count(b"\n") == 1
    state = log.state()
    assert state is not None
    assert state.initialization["legacy_history_sha256"] == sha256_hex(history)
    with pytest.raises(HoldoutLogIntegrityError, match="already initialized"):
        log.initialize()
    commit(repo, "initialize")
    assert log.verify_history() is not None


def test_initialization_refuses_an_unexpected_legacy_file(repo: Path) -> None:
    (repo / LOG).write_bytes(LEGACY.replace(b"Intro.", b"Intro!"))
    with pytest.raises(HoldoutLogIntegrityError, match="not the reviewed legacy file"):
        new_log(repo).initialize()
    assert not (repo / LEDGER).exists()
    with pytest.raises(HoldoutLogIntegrityError, match="differs from the reviewed legacy"):
        new_log(repo).state()


def test_a_symlinked_ledger_directory_is_rejected(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "research" / "holdout_access").symlink_to(outside)
    with pytest.raises(HoldoutLogIntegrityError):
        new_log(repo).initialize()
    assert os.listdir(outside) == []


# ----- the protocol -----


def test_the_full_protocol_reaches_ready_only_once_everything_is_committed(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    gate_7 = gate(repo, GateId.GATE_7)
    started = start(ready, gate_7)
    state = ready.log.state()
    assert state is not None
    assert state.holdouts["holdout_a"].consumed_by == started.event_id
    with pytest.raises(NotReadyError, match="differs from HEAD"):
        ready.log.assert_started_committed(started.event_id)
    git(repo, "add", LEDGER)
    git(repo, "commit", "-q", "-m", "ledger only")
    with pytest.raises(HoldoutLogIntegrityError, match="does not mirror HEAD's whole ledger"):
        ready.log.assert_started_committed(started.event_id)
    with pytest.raises(HoldoutLogIntegrityError, match="does not mirror HEAD's whole ledger"):
        ready.log.verify_history()
    commit(repo, "mirror")
    report = ready.log.assert_started_committed(started.event_id)
    assert report.started_event_id == started.event_id
    assert report.holdout_id == "holdout_a"
    assert ready.log.verify_history() is not None


def test_markdown_committed_without_the_ledger_is_not_ready(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    started = start(ready, gate(repo, GateId.GATE_7))
    git(repo, "add", LOG)
    git(repo, "commit", "-q", "-m", "markdown only")
    with pytest.raises(HoldoutLogIntegrityError, match="committed version fails verification"):
        ready.log.assert_started_committed(started.event_id)


def refused(ready: Prepared, gate_7: RecordRef, reason: RefusalReason) -> None:
    with pytest.raises(AccessRefusedError) as raised:
        start(ready, gate_7)
    assert raised.value.reason is reason
    event = last_event(ready.log.repo)
    assert event.event_type is EventType.ACCESS_ATTEMPT_REFUSED
    assert event.fields["reason"] == reason.value
    state = ready.log.state()
    assert state is not None
    assert state.holdouts["holdout_a"].consumed_by is None


def test_gate_6_valid_but_gate_7_missing_is_refused(repo: Path, store: ExperimentStore) -> None:
    ready = prepared(repo, store)
    refused(
        ready,
        RecordRef("20261014T050000.000000Z_" + "f" * 32, "0" * 64),
        RefusalReason.GATE_7_MISSING,
    )


def test_a_failed_gate_7_is_refused(repo: Path, store: ExperimentStore) -> None:
    ready = prepared(repo, store)
    refused(ready, gate(repo, GateId.GATE_7, decision=Decision.FAIL), RefusalReason.GATE_7_INVALID)


def test_a_superseded_gate_7_is_refused(repo: Path, store: ExperimentStore) -> None:
    ready = prepared(repo, store)
    first = gate(repo, GateId.GATE_7)
    gate(repo, GateId.GATE_7, supersedes=Supersedes(first.record_id, first.record_sha256))
    refused(ready, first, RefusalReason.GATE_7_INVALID)


def test_a_gate_7_for_another_candidate_is_refused(repo: Path, store: ExperimentStore) -> None:
    ready = prepared(repo, store)
    refused(ready, gate(repo, GateId.GATE_7, candidate_id="cand_b"), RefusalReason.GATE_7_INVALID)


def test_a_gate_7_with_a_different_evaluation_plan_is_refused(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    refused(
        ready, gate(repo, GateId.GATE_7, plan="docs/other_plan.md"), RefusalReason.GATE_7_INVALID
    )


def test_a_superseded_gate_6_is_refused_at_start(repo: Path, store: ExperimentStore) -> None:
    ready = prepared(repo, store)
    gate(
        repo,
        GateId.GATE_6,
        supersedes=Supersedes(ready.gate_6.record_id, ready.gate_6.record_sha256),
    )
    refused(ready, gate(repo, GateId.GATE_7), RefusalReason.GATE_6_INVALID)


def test_a_candidate_changed_after_authorization_is_refused(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    write(repo, "src/candidate/runner.txt", "changed runner\n")
    commit(repo, "change runner")
    refused(ready, gate(repo, GateId.GATE_7), RefusalReason.RUNNER_MISMATCH)


def test_any_other_production_change_after_authorization_is_refused(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    write(repo, "src/unrelated.py", "x = 1\n")
    commit(repo, "unrelated source change")
    refused(ready, gate(repo, GateId.GATE_7), RefusalReason.CANDIDATE_CHANGED)


def test_a_dirty_repository_is_refused_at_start(repo: Path, store: ExperimentStore) -> None:
    ready = prepared(repo, store)
    gate_7 = gate(repo, GateId.GATE_7)
    write(repo, "docs/scratch.md", "uncommitted\n")
    refused(ready, gate_7, RefusalReason.REPOSITORY_NOT_CLEAN)


def test_start_without_authorization_is_refused_and_recorded(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    with pytest.raises(AccessRefusedError) as raised:
        ready.log.start(
            "HAL-0099", gate(repo, GateId.GATE_7), operator=ActorRole.PROJECT_OWNER, attested=True
        )
    assert raised.value.reason is RefusalReason.NO_AUTHORIZATION
    assert last_event(repo).event_type is EventType.ACCESS_ATTEMPT_REFUSED


def test_duplicate_starts_and_retries_against_a_consumed_holdout_are_refused(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    gate_7 = gate(repo, GateId.GATE_7)
    start(ready, gate_7)
    commit(repo, "started")
    with pytest.raises(AccessRefusedError) as raised:
        start(ready, gate_7)
    assert raised.value.reason is RefusalReason.AUTHORIZATION_ALREADY_USED
    commit(repo, "refusal")
    with pytest.raises(AccessRefusedError) as raised:
        ready.log.request_access(spec(repo, store), ActorRole.STATISTICIAN)
    assert raised.value.reason is RefusalReason.HOLDOUT_CONSUMED


def test_a_committed_start_stays_consumed_when_an_uncommitted_closing_event_is_lost(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    started = start(ready, gate(repo, GateId.GATE_7))
    commit(repo, "started")
    ready.log.finish(
        started.event_id, EventType.ACCESS_COMPLETED, recorded_by=ActorRole.AUTHORIZED_OPERATOR
    )
    git(repo, "checkout", "--", LEDGER, LOG)
    state = new_log(repo, store).state()
    assert state is not None
    assert state.holdouts["holdout_a"].consumed_by == started.event_id
    assert state.starts[started.event_id].closed_by is None
    assert any("OPEN" in line for line in holdout_log.status_lines(state))
    ready.log.finish(
        started.event_id,
        EventType.ACCESS_INTERRUPTED,
        recorded_by=ActorRole.PROJECT_OWNER,
        reason=hr.InterruptReason.UNKNOWN_STATE,
    )
    ready.log.correct(
        started.event_id,
        FileRef("docs/correction.md", sha256_hex((repo / "docs/correction.md").read_bytes())),
        attested=True,
    )
    state = new_log(repo, store).state()
    assert state is not None
    assert state.holdouts["holdout_a"].consumed_by == started.event_id


# ----- mirror -----


def test_access_started_cannot_proceed_with_an_unreconciled_mirror(
    repo: Path, store: ExperimentStore
) -> None:
    ready = prepared(repo, store)
    gate_7 = gate(repo, GateId.GATE_7)
    crashing = new_log(repo, store, fault_hook=crash_at("ledger.appended"))
    with pytest.raises(KeyboardInterrupt):
        crashing.correct(ready.request.event_id, correction(repo), attested=True)
    before = (repo / LEDGER).read_bytes()
    with pytest.raises(MirrorBehindError):
        start(
            Prepared(new_log(repo, store), ready.request, ready.authorization, ready.gate_6), gate_7
        )
    assert (repo / LEDGER).read_bytes() == before
    state_log = new_log(repo, store)
    assert state_log.mirror() == 1
    state = state_log.state()
    assert state is not None
    assert state.holdouts["holdout_a"].consumed_by is None


def crash_at(point: str) -> Callable[[str], None]:
    def hook(name: str) -> None:
        if name == point:
            raise KeyboardInterrupt

    return hook


def test_a_crash_between_ledger_and_markdown_blocks_appends_until_mirror(repo: Path) -> None:
    initialized(repo)
    crashing = new_log(repo, fault_hook=crash_at("ledger.appended"))
    document = FileRef("docs/correction.md", sha256_hex((repo / "docs/correction.md").read_bytes()))
    with pytest.raises(KeyboardInterrupt):
        crashing.correct("HAL-0005", document, attested=True)
    ledger_bytes = (repo / LEDGER).read_bytes()
    assert ledger_bytes.count(b"\n") == 2
    log = new_log(repo)
    with pytest.raises(MirrorBehindError):
        log.correct("HAL-0005", document, attested=True)
    with pytest.raises(MirrorBehindError):
        log.state()
    assert log.mirror() == 1
    assert (repo / LEDGER).read_bytes() == ledger_bytes
    assert log.mirror() == 0
    log.correct("HAL-0005", document, attested=True)


def test_a_crash_during_initialization_is_completed_by_mirror(repo: Path) -> None:
    with pytest.raises(KeyboardInterrupt):
        new_log(repo, fault_hook=crash_at("initialize.ledger_written")).initialize()
    assert (repo / LOG).read_bytes() == LEGACY
    log = new_log(repo)
    with pytest.raises(MirrorBehindError):
        log.state()
    assert log.mirror() == 1
    assert log.state() is not None


def test_mirror_refuses_a_markdown_file_that_is_not_a_ledger_prefix(repo: Path) -> None:
    initialized(repo)
    data = (repo / LOG).read_bytes()
    (repo / LOG).write_bytes(
        data.replace(b"| Last event | HAL-0005 |", b"| Last event | HAL-0006 |")
    )
    with pytest.raises(HoldoutLogIntegrityError, match="does not agree"):
        new_log(repo).mirror()


# ----- Git history -----


def restored_after_bad_commit(repo: Path, path: str, change: Callable[[bytes], bytes]) -> None:
    original = (repo / path).read_bytes()
    (repo / path).write_bytes(change(original))
    commit(repo, "bad change")
    (repo / path).write_bytes(original)
    commit(repo, "restore")


@pytest.mark.parametrize(
    ("path", "change"),
    [
        (LOG, lambda data: data.replace(b"Intro.", b"Intro!")),
        (
            LOG,
            lambda data: data.replace(
                b"- Event ID: HAL-0001\n", b"- Event ID: HAL-0001 (edited)\n"
            ),
        ),
        (
            LOG,
            lambda data: data.replace(b"| Last event | HAL-0006 |", b"| Last event | HAL-0007 |"),
        ),
        (LOG, lambda data: data[: data.rindex(b"\n### HAL-0006")] + b"\n"),
        (LEDGER, lambda data: data[: data.rindex(b"\n", 0, len(data) - 1) + 1]),
    ],
    ids=[
        "static-prose",
        "legacy-entry",
        "status",
        "generated-entry-deleted",
        "ledger-tail-deleted",
    ],
)
def test_history_rejects_any_committed_change_to_fixed_or_generated_content(
    repo: Path, path: str, change: Callable[[bytes], bytes]
) -> None:
    log = initialized(repo)
    log.correct(
        "HAL-0005",
        FileRef("docs/correction.md", sha256_hex((repo / "docs/correction.md").read_bytes())),
        attested=True,
    )
    commit(repo, "correction")
    log.verify_history()
    restored_after_bad_commit(repo, path, change)
    log.state()
    with pytest.raises(HoldoutLogIntegrityError):
        log.verify_history()


def test_history_rejects_a_generated_entry_deleted_through_a_merge(repo: Path) -> None:
    log = initialized(repo)
    log.correct(
        "HAL-0005",
        FileRef("docs/correction.md", sha256_hex((repo / "docs/correction.md").read_bytes())),
        attested=True,
    )
    commit(repo, "correction")
    original = (repo / LOG).read_bytes()
    git(repo, "checkout", "-q", "-b", "side")
    git(repo, "commit", "-q", "--allow-empty", "-m", "side")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
    (repo / LOG).write_bytes(original[: original.rindex(b"\n### HAL-0006")] + b"\n")
    commit(repo, "evil merge")
    (repo / LOG).write_bytes(original)
    commit(repo, "restore")
    with pytest.raises(HoldoutLogIntegrityError, match="committed version"):
        log.verify_history()


def test_history_rejects_a_commit_that_removed_the_ledger(repo: Path) -> None:
    log = initialized(repo)
    ledger = (repo / LEDGER).read_bytes()
    (repo / LEDGER).unlink()
    commit(repo, "remove ledger")
    (repo / LEDGER).write_bytes(ledger)
    commit(repo, "restore ledger")
    with pytest.raises(HoldoutLogIntegrityError, match="removed the holdout ledger"):
        log.verify_history()


# ----- append safety -----


def correction(repo: Path) -> FileRef:
    return FileRef("docs/correction.md", sha256_hex((repo / "docs/correction.md").read_bytes()))


def test_a_short_write_rolls_back_and_latches(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = initialized(repo)
    before = (repo / LEDGER).read_bytes()
    monkeypatch.setattr(holdout_log, "_ledger_write", lambda fd, data: os.write(fd, data[:7]))
    with pytest.raises(OSError, match="short write"):
        log.correct("HAL-0005", correction(repo), attested=True)
    monkeypatch.undo()
    assert (repo / LEDGER).read_bytes() == before
    with pytest.raises(HoldoutLogIntegrityError, match="open a new HoldoutLog"):
        log.correct("HAL-0005", correction(repo), attested=True)
    new_log(repo).correct("HAL-0005", correction(repo), attested=True)


def test_a_failed_rollback_leaves_a_torn_ledger_that_fails_closed(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = initialized(repo)

    def failing_truncate(_fd: int, _size: int) -> None:
        raise OSError(5, "I/O error")

    monkeypatch.setattr(holdout_log, "_ledger_write", lambda fd, data: os.write(fd, data[:7]))
    monkeypatch.setattr(holdout_log, "_ledger_truncate", failing_truncate)
    with pytest.raises(HoldoutLogIntegrityError, match="could not be rolled back"):
        log.correct("HAL-0005", correction(repo), attested=True)
    monkeypatch.undo()
    with pytest.raises(HoldoutLogIntegrityError, match="incomplete entry"):
        new_log(repo).state()


def test_replacing_the_ledger_directory_before_the_write_fails_closed(repo: Path) -> None:
    initialized(repo)
    directory = repo / "research" / "holdout_access"

    def replace(point: str) -> None:
        if point == "ledger.before_write":
            os.rename(directory, directory.with_name("holdout_access_old"))
            directory.mkdir()

    with pytest.raises(HoldoutLogIntegrityError, match="moved or replaced"):
        new_log(repo, fault_hook=replace).correct("HAL-0005", correction(repo), attested=True)
    old = directory.with_name("holdout_access_old") / "ledger.v1.jsonl"
    assert old.read_bytes().count(b"\n") == 1


CHILD = """
import sys, time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from pmv.holdout_log import FileRef, HoldoutLog
repo, legacy, digest = Path(sys.argv[1]), sys.argv[2], sys.argv[3]

def clock():
    return datetime(2030, 1, 1, tzinfo=UTC) + timedelta(microseconds=time.monotonic_ns() // 1000)

for _ in range(3):
    HoldoutLog(repo, reviewed_legacy_sha256=legacy, lock_timeout_seconds=120, clock=clock).correct(
        "HAL-0005", FileRef("docs/correction.md", digest), attested=True
    )
"""


def test_concurrent_writers_produce_one_valid_chain_and_an_exact_mirror(repo: Path) -> None:
    initialized(repo)
    digest = correction(repo).sha256
    children = [
        subprocess.Popen(  # noqa: S603 - runs this interpreter with a fixed test script
            [sys.executable, "-I", "-c", CHILD, str(repo), LEGACY_SHA, digest],
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(4)
    ]
    assert [child.wait(timeout=300) for child in children] == [0, 0, 0, 0]
    state = new_log(repo).state()
    assert state is not None
    assert len(state.events) == 1 + 12


# ----- logging and command line -----


def test_logs_carry_no_content(repo: Path, store: ExperimentStore) -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        ready = prepared(repo, store)
    finally:
        logger = logging.getLogger("pmv")
        for item in list(logger.handlers):
            logger.removeHandler(item)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    output = buffer.getvalue()
    assert ready.authorization.event_id in output
    for forbidden in ("cand_a", "holdout_a", "docs/plan.md", str(repo), "candidate_identity"):
        assert forbidden not in output


def test_the_command_line_verifies_and_reports_status_without_tracebacks(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(hr, "REVIEWED_LEGACY_SHA256", LEGACY_SHA)
    monkeypatch.setattr(holdout_log.HoldoutLog.__init__, "__defaults__", None, raising=False)
    initialized(repo)
    log_args = ["--repo", str(repo)]
    request = tmp_path / "request.json"
    request.write_text('{"action": "correct", "arguments": {"extra": 1}}', encoding="ascii")
    config = ["--config", str(repo / "configs/test.toml"), "--environment", "test"]
    assert main([*log_args, "record", "--request", str(request), *config]) == 1
    error = capsys.readouterr().err
    assert error.startswith("HoldoutLogError: ")
    assert "Traceback" not in error


def test_status_lines_describe_an_uninitialized_log() -> None:
    assert holdout_log.status_lines(None)[0].startswith("holdout log: not initialized")


def test_holdout_log_errors_never_echo_values(repo: Path) -> None:
    log = initialized(repo)
    with pytest.raises(HoldoutLogError) as raised:
        log.correct("HAL-0005", FileRef("docs/correction.md", "0" * 64), attested=True)
    assert "0" * 64 not in str(raised.value)


# ----- red-team repair regressions -----


def started_and_ready(repo: Path, store: ExperimentStore) -> tuple[Prepared, hr.Event, RecordRef]:
    ready = prepared(repo, store)
    gate_7 = gate(repo, GateId.GATE_7)
    started = start(ready, gate_7)
    commit(repo, "started")
    assert ready.log.assert_started_committed(started.event_id).started_event_id == started.event_id
    return ready, started, gate_7


@pytest.mark.parametrize(
    "follow_up",
    ["restart", "new_request_other_candidate", "new_authorization", "new_cycle", "reveal_check"],
)
def test_reverting_a_committed_start_never_makes_the_holdout_reusable(
    repo: Path, store: ExperimentStore, follow_up: str
) -> None:
    ready, started, gate_7 = started_and_ready(repo, store)
    git(repo, "revert", "--no-edit", "HEAD")
    state = new_log(repo, store).state()
    assert state is not None
    assert state.holdouts["holdout_a"].consumed_by is None
    log = new_log(repo, store)
    actions: dict[str, Callable[[], object]] = {
        "restart": lambda: start(
            Prepared(log, ready.request, ready.authorization, ready.gate_6), gate_7
        ),
        "new_request_other_candidate": lambda: log.request_access(
            spec(repo, store, candidate_id="cand_b"), ActorRole.STATISTICIAN
        ),
        "new_authorization": lambda: log.deny(
            ready.request.event_id, hr.DenialReason.OWNER_DECLINED, attested=True
        ),
        "new_cycle": lambda: log.register_cycle(
            "cycle_b",
            SplitFormation.PROSPECTIVE_PERIOD,
            FileRef("docs/dev.md", sha256_hex((repo / "docs/dev.md").read_bytes())),
            T0 + timedelta(days=90),
            T0 + timedelta(days=120),
            attested=True,
        ),
        "reveal_check": lambda: log.assert_started_committed(started.event_id),
    }
    with pytest.raises(HoldoutLogIntegrityError, match="not append-only"):
        actions[follow_up]()
    assert new_log(repo, store).state() is not None


def test_a_ledger_only_head_fails_until_the_mirror_is_committed(repo: Path) -> None:
    log = initialized(repo)
    log.correct("HAL-0005", correction(repo), attested=True)
    git(repo, "add", LEDGER)
    git(repo, "commit", "-q", "-m", "ledger only")
    with pytest.raises(HoldoutLogIntegrityError, match="does not mirror HEAD's whole ledger"):
        log.verify_history()
    lagging = git(repo, "rev-parse", "HEAD").decode().strip()
    commit(repo, "mirror")
    assert log.verify_history() is not None
    fixed = git(repo, "rev-parse", "HEAD").decode().strip()
    git(repo, "checkout", "-q", "--detach", lagging)
    with pytest.raises(HoldoutLogIntegrityError):
        log.verify_history()
    git(repo, "checkout", "-q", "--detach", fixed)
    assert log.verify_history() is not None
    git(repo, "checkout", "-q", "main")


def test_merges_follow_the_head_exactness_rule(repo: Path) -> None:
    log = initialized(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    log.correct("HAL-0005", correction(repo), attested=True)
    git(repo, "add", LEDGER)
    git(repo, "commit", "-q", "-m", "ledger only on feature")
    git(repo, "checkout", "-q", "main")
    (repo / LOG).write_bytes(git(repo, "show", "HEAD:" + LOG))
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "feature")
    with pytest.raises(HoldoutLogIntegrityError, match="behind the machine ledger"):
        log.verify_history()
    with pytest.raises(HoldoutLogIntegrityError, match="does not mirror HEAD's whole ledger"):
        log._verify_history_locked()
    log.mirror()
    commit(repo, "mirror after merge")
    assert log.verify_history() is not None
    git(repo, "checkout", "-q", "-b", "pr")
    log.correct("HAL-0005", correction(repo), attested=True)
    commit(repo, "pr event with its mirror")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "pr")
    git(repo, "checkout", "-q", "--detach", "HEAD")
    state = log.verify_history()
    assert state is not None
    assert len(state.events) == 3


def test_a_forged_initialization_with_consistent_but_wrong_hashes_fails(repo: Path) -> None:
    forged_legacy = LEGACY.replace(b"Append-only.", b"Editable.")
    fields = {**hr.initialization_fields(forged_legacy), "legacy_file_sha256": LEGACY_SHA}
    line = hr.encode_event(
        hr.LogState(),
        EventType.LOG_INITIALIZED,
        "2026-10-14T05:00:00.000000Z",
        {
            "commit": git(repo, "rev-parse", "HEAD").decode().strip(),
            "dirty_tree_sha256": None,
            "tree_dirty": False,
        },
        fields,
    )
    state = hr.verify_ledger(line)
    preamble, _status, before, after, history = hr.split_legacy_file(forged_legacy)
    layout = hr.LogLayout(
        preamble, b"", before + hr.MACHINE_LEDGER_SECTION.encode() + after, history, b""
    )
    (repo / "research" / "holdout_access").mkdir()
    (repo / LEDGER).write_bytes(line)
    (repo / LOG).write_bytes(hr.render_log(layout, state))
    with pytest.raises(HoldoutLogIntegrityError, match="derived from the reviewed legacy"):
        new_log(repo).state()


def test_the_cli_never_echoes_a_secret_shaped_enum_value(
    repo: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    initialized(repo)
    request = tmp_path / "request.json"
    shaped = "SECRET_sk_live_ABC123"
    request.write_text(
        '{"action": "register_cycle", "arguments": {"cycle_id": "cycle_a", '
        f'"split_formation": "{shaped}", '
        '"development_subset": {"path": "docs/dev.md", "sha256": "' + "0" * 64 + '"}, '
        '"protected_start": "2026-11-01T00:00:00.000000Z", '
        '"protected_end": "2026-12-01T00:00:00.000000Z", "attested": true}}',
        encoding="ascii",
    )
    config = ["--config", str(repo / "configs/test.toml"), "--environment", "test"]
    assert main(["--repo", str(repo), "record", "--request", str(request), *config]) == 1
    captured = capsys.readouterr()
    assert shaped not in captured.err + captured.out
    assert "Traceback" not in captured.err
    assert captured.err.startswith("HoldoutLogError: ")


def test_a_markdown_file_replaced_after_its_rename_is_not_reported_as_written(repo: Path) -> None:
    initialized(repo)

    def replace(point: str) -> None:
        if point == "mirror.written":
            data = (repo / LOG).read_bytes()
            (repo / LOG).rename(repo / "detached.md")
            (repo / LOG).write_bytes(data)

    log = new_log(repo, fault_hook=replace)
    with pytest.raises(HoldoutLogIntegrityError, match="moved or replaced after it was written"):
        log.correct("HAL-0005", correction(repo), attested=True)
    with pytest.raises(HoldoutLogIntegrityError, match="open a new HoldoutLog"):
        log.correct("HAL-0005", correction(repo), attested=True)


def test_a_ledger_directory_replaced_after_initialization_rename_fails_closed(repo: Path) -> None:
    directory = repo / "research" / "holdout_access"

    def replace(point: str) -> None:
        if point == "ledger.created":
            os.rename(directory, directory.with_name("holdout_access_detached"))
            directory.mkdir()

    with pytest.raises(HoldoutLogIntegrityError, match="moved or replaced after it was written"):
        new_log(repo, fault_hook=replace).initialize()
    assert (repo / LOG).read_bytes() == LEGACY


def test_interrupted_access_preserves_the_evidence_hash(repo: Path, store: ExperimentStore) -> None:
    ready, started, _gate_7 = started_and_ready(repo, store)
    event = ready.log.finish(
        started.event_id,
        EventType.ACCESS_INTERRUPTED,
        recorded_by=ActorRole.PROJECT_OWNER,
        reason=hr.InterruptReason.PROCESS_CRASH,
        restricted_evidence_sha256="e" * 64,
    )
    assert event.fields["restricted_evidence_sha256"] == "e" * 64


def test_the_docs_state_the_local_git_anchoring_limit() -> None:
    text = (REPO / "docs" / "holdout_access.md").read_text(encoding="utf-8")
    assert "not a complete external notarization" in text
    assert "BEFORE ANY REAL PROTECTED-HOLDOUT REVEAL IN PHASE 7" in text
