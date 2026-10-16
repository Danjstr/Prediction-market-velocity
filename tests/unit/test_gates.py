"""Integration tests for gate-record creation and Git-anchored history verification."""

import io
import json
import logging
import os
import stat
import subprocess
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import pmv.experiments as experiments
import pmv.gates as gates
from pmv.config import Environment, LoggingConfig, LogLevel, RawStorageConfig
from pmv.experiment_spec import (
    ArtifactType,
    MediaType,
    RunArtifactInput,
    RunClass,
    RunSpec,
    Seed,
    Split,
    SupersedeReason,
    spec_sections,
)
from pmv.experiments import ExperimentStore, RunHandle
from pmv.gate_record import (
    Decision,
    DocumentKind,
    FindingSeverity,
    FindingStatus,
    GateId,
    GateRecordError,
    Independence,
    ReviewConclusion,
    ReviewerRole,
    RunRole,
    parse_record_file,
    render_record,
    validate_record,
)
from pmv.gates import (
    ArtifactEvidence,
    CaptureEvidence,
    DocumentEvidence,
    Finding,
    GateEvidenceError,
    GateIntegrityError,
    GateRequest,
    GateStateError,
    LedgerPin,
    Review,
    RunEvidence,
    Supersedes,
    capture_project_identity,
    create_gate_record,
    list_gate_records,
    main,
    request_from_json,
    verify_gate_history,
    verify_gate_record,
)
from pmv.integrity import canonical_line, sha256_hex
from pmv.log import configure_logging
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport
from pmv.raw_storage import RawCaptureStore
from pmv.reproducibility import EnvironmentCapture

T0 = datetime(2026, 10, 14, 3, 15, tzinfo=UTC)
GOVERNANCE = ("CLAUDE.md", "HOLDOUT_ACCESS_LOG.md", "PROJECT_BRIEF.md", "START_HERE.md")
REVIEW = "docs/reviews/review.md"
CONFIG = 'schema_version = 1\nenvironment = "test"\n\n[logging]\nlevel = "INFO"\n'
DEVELOPMENT_CONFIG = CONFIG.replace('"test"', '"development"')


def development_config(tmp_path: Path) -> list[str]:
    """CLI arguments for a development configuration outside the repository (RT-4)."""
    path = tmp_path / "development.toml"
    path.write_text(DEVELOPMENT_CONFIG, encoding="ascii")
    return ["--config", str(path), "--environment", "development"]


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
    completed = subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(repo), "-c", "commit.gpgsign=false", *arguments],
        env=environment,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def commit_all(repo: Path, message: str = "change") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    root = tmp_path / "repo"
    (root / "configs").mkdir(parents=True)
    (root / "docs" / "reviews").mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in GOVERNANCE:
        (root / name).write_text(f"# {name}\n", encoding="ascii")
    (root / "configs" / "test.toml").write_text(CONFIG, encoding="ascii")
    (root / REVIEW).write_text("Reviewer rationale lives here.\n", encoding="ascii")
    check = root / "scripts" / "check.sh"
    check.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    check.chmod(0o755)
    git(root, "init", "-q", "-b", "main")
    commit_all(root, "baseline")
    yield root
    gates = root / "docs" / "decisions" / "gates"
    if gates.is_dir():
        for item in gates.iterdir():
            if not item.is_symlink():
                item.chmod(0o644)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


def review_document(repo: Path) -> DocumentEvidence:
    return DocumentEvidence(REVIEW, sha256_hex((repo / REVIEW).read_bytes()), DocumentKind.REVIEW)


def request(repo: Path, **overrides: Any) -> GateRequest:
    values: dict[str, Any] = {
        "gate_id": GateId.GATE_0,
        "decision": Decision.PASS,
        "approval_attested": True,
        "reviews": (
            Review(
                ReviewerRole.RELIABILITY_RED_TEAM,
                ReviewConclusion.RECOMMEND_PASS,
                Independence.INDEPENDENT,
                review_document(repo),
            ),
        ),
    }
    values.update(overrides)
    return GateRequest(**values)


SHARED_CLOCK = Clock()


def create(repo: Path, gate_request: GateRequest, **options: Any) -> Any:
    options.setdefault("check_runner", lambda _repo: True)
    options.setdefault("clock", SHARED_CLOCK)
    return create_gate_record(repo, gate_request, **options)


def head_count(repo: Path) -> int:
    return int(git(repo, "rev-list", "--count", "HEAD"))


# ----- creation -----


def test_a_pass_record_is_created_untracked_and_never_staged_or_committed(repo: Path) -> None:
    commits = head_count(repo)
    created = create(repo, request(repo))
    assert created.path.parent == repo / "docs" / "decisions" / "gates"
    assert created.path.name == f"gate_0_{created.record_id}.md"
    data = created.path.read_bytes()
    assert sha256_hex(data) == created.sha256
    assert stat.S_IMODE(created.path.stat().st_mode) == 0o444
    record = verify_gate_record(created.path)
    assert record.decision is Decision.PASS
    project = record.document["project"]
    assert isinstance(project, dict)
    assert project["commit"] == git(repo, "rev-parse", "HEAD").decode().strip()
    assert project["tree_dirty"] is False
    assert head_count(repo) == commits
    assert git(repo, "diff", "--cached", "--name-only") == b""
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=all").decode()
    assert status == f"?? docs/decisions/gates/{created.path.name}\n"
    (only,) = verify_gate_history(repo)
    assert only.committed is False
    assert [name for name in os.listdir(created.path.parent) if name.startswith(".")] == []


def test_records_never_overwrite_an_existing_file(repo: Path) -> None:
    fixed = (lambda: T0, lambda: "a" * 32)
    create(repo, request(repo, cycle_id="cycle_a"), clock=fixed[0], random_token=fixed[1])
    with pytest.raises(GateIntegrityError, match="already exists"):
        create(repo, request(repo, cycle_id="cycle_b"), clock=fixed[0], random_token=fixed[1])


def test_a_lineage_cannot_get_a_second_root(repo: Path) -> None:
    create(repo, request(repo))
    with pytest.raises(GateStateError, match="supersede its head"):
        create(repo, request(repo))
    create(repo, request(repo, gate_id=GateId.GATE_1))
    create(repo, request(repo, cycle_id="cycle_a"))


def test_a_symlinked_gate_directory_is_rejected(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "docs" / "decisions").mkdir()
    (repo / "docs" / "decisions" / "gates").symlink_to(outside)
    with pytest.raises(GateIntegrityError):
        create(repo, request(repo, decision=Decision.FAIL, reasons=("control_missing",)))
    assert os.listdir(outside) == []


def test_dirty_trees_refuse_pass_but_record_fail_with_the_fingerprint(repo: Path) -> None:
    (repo / "START_HERE.md").write_text("# changed\n", encoding="ascii")
    with pytest.raises(GateStateError, match="clean project tree"):
        create(repo, request(repo))
    created = create(repo, request(repo, decision=Decision.FAIL, reasons=("control_missing",)))
    project = verify_gate_record(created.path).document["project"]
    assert isinstance(project, dict)
    assert project["tree_dirty"] is True
    assert isinstance(project["dirty_tree_sha256"], str)


def test_untracked_valid_gate_records_do_not_make_the_tree_dirty(repo: Path) -> None:
    create(repo, request(repo))
    second = create(repo, request(repo, gate_id=GateId.GATE_1))
    project = verify_gate_record(second.path).document["project"]
    assert isinstance(project, dict)
    assert project["tree_dirty"] is False
    (repo / "docs" / "decisions" / "gates" / "notes.txt").write_text("x", encoding="ascii")
    with pytest.raises(GateStateError, match="clean project tree"):
        create(repo, request(repo, gate_id=GateId.GATE_2))


# ----- check.sh identity binding -----


def test_repository_mutation_during_check_sh_refuses_the_record(repo: Path) -> None:
    def mutating_check(target: Path) -> bool:
        (target / "configs" / "test.toml").write_text(CONFIG + "\n", encoding="ascii")
        return True

    with pytest.raises(GateStateError, match=r"changed while check\.sh ran"):
        create(repo, request(repo), check_runner=mutating_check)
    assert not (repo / "docs" / "decisions" / "gates").exists() or not os.listdir(
        repo / "docs" / "decisions" / "gates"
    )


def test_repository_mutation_after_check_sh_before_publication_refuses(repo: Path) -> None:
    def hook(point: str) -> None:
        if point == "before_publish":
            (repo / "CLAUDE.md").write_text("# edited\n", encoding="ascii")

    with pytest.raises(GateStateError, match="changed before the record was written"):
        create(repo, request(repo), fault_hook=hook)
    assert os.listdir(repo / "docs" / "decisions" / "gates") == []


def test_a_dirty_fingerprint_must_stay_identical_through_the_check(repo: Path) -> None:
    (repo / REVIEW).write_text("draft one\n", encoding="ascii")

    def mutating_check(target: Path) -> bool:
        (target / REVIEW).write_text("draft two\n", encoding="ascii")
        return True

    failing = request(
        repo,
        decision=Decision.INCONCLUSIVE,
        reasons=("required_review_missing",),
        reviews=(),
    )
    with pytest.raises(GateStateError, match=r"changed while check\.sh ran"):
        create(repo, failing, check_runner=mutating_check)
    created = create(repo, failing)
    record = verify_gate_record(created.path)
    assert record.document["decision"] == "inconclusive"


def test_check_outcomes_are_recorded_and_a_failed_check_cannot_pass(repo: Path) -> None:
    with pytest.raises(GateRecordError, match="passing check_sh"):
        create(repo, request(repo), check_runner=lambda _repo: False)
    created = create(
        repo,
        request(repo, decision=Decision.FAIL, reasons=("control_missing",)),
        check_runner=lambda _repo: False,
    )
    evidence = verify_gate_record(created.path).document["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["checks"] == [{"check_id": "check_sh", "outcome": "failed"}]


def test_the_default_runner_executes_the_project_check_script(repo: Path) -> None:
    created = create_gate_record(repo, request(repo), clock=Clock())
    evidence = verify_gate_record(created.path).document["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["checks"] == [{"check_id": "check_sh", "outcome": "passed"}]


# ----- documents, approval, holdout -----


def test_documents_must_be_tracked_unmodified_and_exact(repo: Path) -> None:
    good = review_document(repo)
    cases: list[tuple[DocumentEvidence, str]] = [
        (DocumentEvidence(REVIEW, "0" * 64, DocumentKind.REVIEW), "committed bytes"),
        (DocumentEvidence("docs/reviews/new.md", good.sha256, DocumentKind.REVIEW), "not tracked"),
        (DocumentEvidence("docs/../CLAUDE.md", good.sha256, DocumentKind.REVIEW), "allowed"),
    ]
    (repo / "docs" / "reviews" / "new.md").write_bytes((repo / REVIEW).read_bytes())
    for document, message in cases:
        with pytest.raises(GateEvidenceError, match=message):
            create(
                repo,
                request(
                    repo,
                    decision=Decision.FAIL,
                    reasons=("control_missing",),
                    documents=(document,),
                ),
            )
    (repo / "docs" / "reviews" / "new.md").unlink()
    (repo / REVIEW).write_text("edited after commit\n", encoding="ascii")
    with pytest.raises(GateEvidenceError, match="committed bytes"):
        create(repo, request(repo, decision=Decision.FAIL, reasons=("control_missing",)))


@pytest.mark.parametrize("gate_id", list(GateId))
def test_every_gate_including_gate_0_requires_attested_owner_approval(
    repo: Path, gate_id: GateId
) -> None:
    with pytest.raises(GateRecordError, match="requires owner approval"):
        create(repo, request(repo, gate_id=gate_id, approval_attested=False))
    created = create(repo, request(repo, gate_id=gate_id))
    final = verify_gate_record(created.path).document["final_decision"]
    assert final == {
        "approval_attested": True,
        "approval_requirement": "required",
        "role": "project_owner",
    }


def test_gate_6_without_holdout_evidence_is_allowed_but_holdout_evidence_is_not(
    repo: Path,
) -> None:
    create(repo, request(repo, gate_id=GateId.GATE_6))
    with pytest.raises(GateEvidenceError, match="protected-holdout evidence"):
        create(
            repo, request(repo, gate_id=GateId.GATE_7, holdout=({"split": "protected_holdout"},))
        )
    holdout_document = DocumentEvidence(
        REVIEW, review_document(repo).sha256, DocumentKind.HOLDOUT_EVALUATION
    )
    with pytest.raises(GateEvidenceError, match="protected-holdout evidence"):
        create(repo, request(repo, gate_id=GateId.GATE_7, documents=(holdout_document,)))


def test_blocking_findings_accepted_by_owner_cannot_pass(repo: Path) -> None:
    accepted = Finding("open_issue", FindingSeverity.BLOCKING, FindingStatus.ACCEPTED_BY_OWNER)
    with pytest.raises(GateRecordError, match="accepted_by_owner does not resolve"):
        create(repo, request(repo, findings=(accepted,)))
    resolved = Finding("open_issue", FindingSeverity.BLOCKING, FindingStatus.RESOLVED)
    create(repo, request(repo, findings=(resolved,)))


# ----- supersession -----


def test_supersession_requires_the_committed_lineage_head(repo: Path) -> None:
    root = create(repo, request(repo, decision=Decision.FAIL, reasons=("control_missing",)))
    successor = request(repo, supersedes=Supersedes(root.record_id, root.sha256))
    with pytest.raises(GateStateError, match="committed at HEAD first"):
        create(repo, successor)
    commit_all(repo, "record root decision")
    with pytest.raises(GateStateError, match="named SHA-256"):
        create(repo, request(repo, supersedes=Supersedes(root.record_id, "0" * 64)))
    second = create(repo, successor)
    assert verify_gate_record(second.path).supersedes == (root.record_id, root.sha256)
    assert sha256_hex(root.path.read_bytes()) == root.sha256
    commit_all(repo, "record second decision")
    with pytest.raises(GateStateError, match="current head"):
        create(repo, successor)
    with pytest.raises(GateStateError, match="recorded after"):
        create(
            repo,
            request(repo, supersedes=Supersedes(second.record_id, second.sha256)),
            clock=lambda: T0,
        )
    third = create(repo, request(repo, supersedes=Supersedes(second.record_id, second.sha256)))
    heads = [item.record.record_id for item in verify_gate_history(repo)]
    assert heads == sorted([root.record_id, second.record_id, third.record_id])


def test_superseding_a_modified_committed_predecessor_is_rejected(repo: Path) -> None:
    root = create(repo, request(repo, decision=Decision.FAIL, reasons=("control_missing",)))
    commit_all(repo, "record root decision")
    root.path.chmod(0o644)
    root.path.write_bytes(root.path.read_bytes().replace(b"control_missing", b"criteria_not_met"))
    successor = request(
        repo,
        decision=Decision.FAIL,
        reasons=("control_missing",),
        supersedes=Supersedes(root.record_id, root.sha256),
    )
    with pytest.raises(GateIntegrityError, match="differs from HEAD"):
        create(repo, successor)


# ----- Git-anchored history -----


def test_history_rejects_committed_records_that_were_modified_or_deleted(repo: Path) -> None:
    created = create(repo, request(repo))
    commit_all(repo, "record decision")
    verify_gate_history(repo)
    created.path.chmod(0o644)
    original = created.path.read_bytes()
    created.path.write_bytes(original + b"\n")
    with pytest.raises(GateIntegrityError, match="differs from HEAD"):
        verify_gate_history(repo)
    commit_all(repo, "tamper")
    created.path.write_bytes(original)
    with pytest.raises(GateIntegrityError, match="modified, deleted, or replaced"):
        verify_gate_history(repo)


def test_history_rejects_a_deleted_committed_record(repo: Path) -> None:
    created = create(repo, request(repo))
    commit_all(repo, "record decision")
    created.path.unlink()
    with pytest.raises(GateIntegrityError, match="differs from HEAD"):
        verify_gate_history(repo)
    commit_all(repo, "delete decision")
    with pytest.raises(GateIntegrityError, match="modified, deleted, or replaced"):
        verify_gate_history(repo)


def test_history_rejects_stray_files_and_shallow_clones(repo: Path, tmp_path: Path) -> None:
    create(repo, request(repo))
    commit_all(repo, "record decision")
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow))
    with pytest.raises(GateIntegrityError, match="shallow"):
        verify_gate_history(shallow)
    (repo / "docs" / "decisions" / "gates" / ".tmp-leftover").write_bytes(b"partial")
    with pytest.raises(GateIntegrityError, match="not a record"):
        verify_gate_history(repo)


def test_the_command_line_verifies_lists_and_reports_failures(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--repo", str(repo), "verify-history"]) == 0
    created = create(repo, request(repo))
    assert main(["--repo", str(repo), "verify", str(created.path)]) == 0
    assert main(["--repo", str(repo), "list"]) == 0
    output = capsys.readouterr().out
    assert created.path.name in output
    assert "not committed" in output
    created.path.chmod(0o644)
    created.path.write_bytes(created.path.read_bytes().replace(b"PASS", b"FAIL"))
    assert main(["--repo", str(repo), "verify", str(created.path)]) == 1
    assert "GateRecordError" in capsys.readouterr().err


def test_the_command_line_creates_from_a_closed_request_file(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = {
        "approval_attested": True,
        "artifacts": [],
        "candidate_id": None,
        "cycle_id": None,
        "decision": "inconclusive",
        "documents": [{"kind": "review", "path": REVIEW, "sha256": review_document(repo).sha256}],
        "experiment_ledger": None,
        "findings": [],
        "gate_id": "gate_1",
        "holdout": [],
        "raw_captures": [],
        "reasons": ["policy_not_defined"],
        "reviews": [],
        "run_check_sh": True,
        "runs": [],
        "supersedes": None,
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(document), encoding="ascii")
    config = development_config(tmp_path)
    assert main(["--repo", str(repo), "create", "--request", str(path), *config]) == 0
    output = capsys.readouterr().out
    assert "untracked and not a project decision" in output
    (record,) = list_gate_records(repo)
    assert record.record.document["decision"] == "inconclusive"
    path.write_text(json.dumps({**document, "extra": 1}), encoding="ascii")
    assert main(["--repo", str(repo), "create", "--request", str(path), *config]) == 1
    assert git(repo, "diff", "--cached", "--name-only") == b""


# ----- experiment evidence -----


@pytest.fixture
def store(tmp_path: Path, repo: Path) -> Iterator[ExperimentStore]:
    root = tmp_path / "exp-root"
    root.mkdir(mode=0o700)
    with ExperimentStore(
        root, repo_root=repo, app_config_sha256="0" * 64, checkpoint_file=tmp_path / "cp.jsonl"
    ) as opened:
        yield opened
    for directory, _subdirs, _files in os.walk(root):
        os.chmod(directory, 0o700)


def completed_run(
    store: ExperimentStore,
    data: bytes = b"model",
    run_class: RunClass = RunClass.DEVELOPMENT,
) -> RunHandle:
    """A completed run. A development run is never evidence-eligible (Step 10 made a
    verified, fingerprinted evidence_candidate eligible; see the test below)."""
    handle = store.reserve_run("velocity_baseline", run_class)
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
        "model.bin", data, artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
    )
    handle.complete()
    return handle


def pin(store: ExperimentStore) -> LedgerPin:
    seq, digest = store.ledger_head()
    assert digest is not None
    return LedgerPin(seq, digest)


def failing(repo: Path, **overrides: Any) -> GateRequest:
    return request(repo, decision=Decision.FAIL, reasons=("criteria_not_met",), **overrides)


def test_run_evidence_is_evaluated_only_at_the_pinned_head(
    repo: Path, store: ExperimentStore
) -> None:
    early = completed_run(store)
    pinned = pin(store)
    late = completed_run(store, b"later")
    candidate = RunEvidence(early.run_id, RunRole.CANDIDATE)
    created = create(
        repo, failing(repo, ledger_pin=pinned, runs=(candidate,)), experiment_store=store
    )
    record = verify_gate_record(created.path)
    ledger_pin = record.document["experiment_ledger"]
    assert isinstance(ledger_pin, dict)
    assert ledger_pin["ledger_seq"] == pinned.ledger_seq
    evidence = record.document["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["runs"] == [
        {
            "eligible_at_pin": False,
            "role": "candidate",
            "run_id": early.run_id,
            "state_at_pin": "completed",
        }
    ]
    later = RunEvidence(late.run_id, RunRole.SUPPORTING)
    with pytest.raises(GateEvidenceError, match="pinned head"):
        create(
            repo,
            failing(repo, gate_id=GateId.GATE_1, ledger_pin=pinned, runs=(later,)),
            experiment_store=store,
        )
    before = created.path.read_bytes()
    store.supersede(early.run_id, late.run_id, SupersedeReason.CORRECTED_CODE)
    assert created.path.read_bytes() == before
    verify_gate_record(created.path)


SYNTHETIC_ENVIRONMENT = canonical_line(
    {
        "distributions": [],
        "interpreter": {
            "byteorder": "little",
            "cache_tag": "cpython-313",
            "flags": {"dev_mode": False, "hash_randomization": 1, "optimize": 0, "utf8_mode": 0},
            "gil_disabled": False,
            "implementation": "cpython",
            "platform": "linux-x86_64",
            "soabi": None,
            "version": "3.13.5",
        },
        "project": {"editable": True, "name": "prediction-market-velocity", "version": "0.0.0"},
        "schema": "pmv.environment",
        "schema_version": 1,
    }
)


def eligible_runs_enabled(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A verified synthetic environment and a committed uv.lock make clean candidates eligible."""
    monkeypatch.setattr(
        experiments,
        "capture_environment",
        lambda _repo, *, verify_conformance: EnvironmentCapture(
            SYNTHETIC_ENVIRONMENT, sha256_hex(SYNTHETIC_ENVIRONMENT)
        ),
    )
    (repo / "uv.lock").write_text("# synthetic lock\n", encoding="ascii")
    commit_all(repo, "lock")


def candidate_request(repo: Path, store: ExperimentStore, run_id: str) -> GateRequest:
    return request(repo, ledger_pin=pin(store), runs=(RunEvidence(run_id, RunRole.CANDIDATE),))


def run_dir(store: ExperimentStore, run_id: str) -> Path:
    directory = store._root_path / "runs" / run_id
    os.chmod(directory, 0o700)
    return directory


def test_an_eligible_v2_candidate_run_can_support_a_pass(
    repo: Path, store: ExperimentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    eligible_runs_enabled(repo, monkeypatch)
    run = completed_run(store, run_class=RunClass.EVIDENCE_CANDIDATE)
    assert store.eligibility_as_of(run.run_id)
    create(repo, candidate_request(repo, store, run.run_id), experiment_store=store)


@pytest.mark.parametrize(
    "damage",
    ["delete_environment", "tamper_environment", "delete_artifact", "tamper_manifest"],
)
def test_f13_a_pass_cannot_rest_on_missing_or_tampered_run_files(
    repo: Path, store: ExperimentStore, monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    eligible_runs_enabled(repo, monkeypatch)
    run = completed_run(store, run_class=RunClass.EVIDENCE_CANDIDATE)
    directory = run_dir(store, run.run_id)
    if damage == "delete_environment":
        (directory / "environment.json").unlink()
    elif damage == "tamper_environment":
        target = writable(directory / "environment.json")
        target.write_bytes(target.read_bytes().replace(b"3.13.5", b"3.13.6"))
    elif damage == "delete_artifact":
        os.chmod(directory / "artifacts", 0o700)
        (directory / "artifacts" / "model.bin").unlink()
    else:
        target = writable(directory / "manifest.json")
        target.write_bytes(target.read_bytes() + b" ")
    # The ledger still says the run is completed and eligible ...
    assert store.eligibility_as_of(run.run_id)
    # ... but the gate tool verifies the files and refuses.
    with pytest.raises(GateEvidenceError, match="failed verification"):
        create(repo, candidate_request(repo, store, run.run_id), experiment_store=store)


def test_f13_a_tampered_producer_of_an_input_is_refused_too(
    repo: Path, store: ExperimentStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    eligible_runs_enabled(repo, monkeypatch)
    producer = completed_run(store, run_class=RunClass.EVIDENCE_CANDIDATE)
    digest = store.snapshot().runs[producer.run_id].artifacts["model.bin"][0]["sha256"]
    assert isinstance(digest, str)
    consumer = store.reserve_run("velocity_baseline", RunClass.EVIDENCE_CANDIDATE)
    consumer.start(
        RunSpec(
            study_id="velocity_baseline",
            entrypoint="pmv.research.baselines:run",
            sections=spec_sections(model={"family": "logistic"}),
            seeds=(Seed("numpy", 7),),
            splits_accessed=(Split.TRAIN,),
            inputs=(RunArtifactInput(producer.run_id, "model.bin", digest),),
        )
    )
    consumer.write_artifact(
        "model.bin", b"consumer", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
    )
    consumer.complete()
    assert store.eligibility_as_of(consumer.run_id)
    (run_dir(store, producer.run_id) / "environment.json").unlink()
    with pytest.raises(GateEvidenceError, match="produced its inputs"):
        create(repo, candidate_request(repo, store, consumer.run_id), experiment_store=store)


def test_ineligible_candidate_runs_cannot_pass(repo: Path, store: ExperimentStore) -> None:
    run = completed_run(store)
    with pytest.raises(GateRecordError, match="evidence-eligible"):
        create(
            repo,
            request(
                repo, ledger_pin=pin(store), runs=(RunEvidence(run.run_id, RunRole.CANDIDATE),)
            ),
            experiment_store=store,
        )
    create(
        repo,
        request(repo, ledger_pin=pin(store), runs=(RunEvidence(run.run_id, RunRole.BASELINE),)),
        experiment_store=store,
    )


def test_pins_runs_and_artifacts_must_match_the_ledger(repo: Path, store: ExperimentStore) -> None:
    run = completed_run(store)
    head = pin(store)
    state = store.snapshot()
    digest = state.runs[run.run_id].artifacts["model.bin"][0]["sha256"]
    assert isinstance(digest, str)
    missing = "20261013T034021.123456Z_" + "f" * 32
    cases: list[tuple[dict[str, Any], str]] = [
        ({"ledger_pin": LedgerPin(head.ledger_seq, "0" * 64)}, "entry_sha256"),
        ({"ledger_pin": LedgerPin(head.ledger_seq + 5, head.entry_sha256)}, "verified ledger"),
        (
            {"ledger_pin": head, "runs": (RunEvidence(missing, RunRole.BASELINE),)},
            "not in the ledger",
        ),
        (
            {
                "ledger_pin": head,
                "artifacts": (ArtifactEvidence(run.run_id, "model.bin", "0" * 64),),
            },
            "does not match",
        ),
        ({"artifacts": (ArtifactEvidence(run.run_id, "model.bin", digest),)}, "pinned experiment"),
    ]
    for overrides, message in cases:
        with pytest.raises(GateEvidenceError, match=message):
            create(repo, failing(repo, **overrides), experiment_store=store)
    with pytest.raises(GateEvidenceError, match="experiment store"):
        create(repo, failing(repo, ledger_pin=head))
    created = create(
        repo,
        failing(
            repo,
            ledger_pin=head,
            runs=(RunEvidence(run.run_id, RunRole.BASELINE),),
            artifacts=(ArtifactEvidence(run.run_id, "model.bin", digest),),
        ),
        experiment_store=store,
    )
    ledger_pin = verify_gate_record(created.path).document["experiment_ledger"]
    assert isinstance(ledger_pin, dict)
    assert (
        ledger_pin["store_id"]
        == json.loads((store._root_path / "store.v1.json").read_text(encoding="ascii"))["store_id"]
    )


def test_raw_capture_evidence_is_verified_exactly(repo: Path, tmp_path: Path) -> None:
    root = tmp_path / "raw-root"
    root.mkdir(mode=0o700)
    config = RawStorageConfig(root=root, warning_free_bytes=1000, hard_stop_free_bytes=100)
    provenance = RuntimeProvenance(
        code_commit=None,
        code_tree_dirty=None,
        config_source_sha256="0" * 64,
        raw_config_sha256=config.canonical_sha256(),
        environment=Environment.TEST,
        python_version="3.13.5",
        platform="linux-x86_64",
        machine_label=None,
        parents=(),
    )
    with RawCaptureStore(config, provenance, repo_root=repo, free_bytes=lambda: 10**12) as raw:
        source = SourceIdentity(
            source_id="unit_source", feed_id="unit_feed", transport=Transport.HTTP, endpoint_id="ep"
        )
        capture = raw.start_capture(source, T0)
        capture.append_payload(b"raw", received_at=T0)
        manifest = capture.finalize()
        digest = raw.verify_capture(manifest.capture_id).manifest_sha256
        reference = CaptureEvidence(manifest.capture_id, digest)
        with pytest.raises(GateEvidenceError, match="raw capture store"):
            create(repo, failing(repo, raw_captures=(reference,)))
        with pytest.raises(GateEvidenceError, match="does not match"):
            create(
                repo,
                failing(repo, raw_captures=(CaptureEvidence(manifest.capture_id, "0" * 64),)),
                raw_store=raw,
            )
        created = create(repo, failing(repo, raw_captures=(reference,)), raw_store=raw)
    evidence = verify_gate_record(created.path).document["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["raw_captures"] == [
        {"capture_id": manifest.capture_id, "manifest_sha256": digest}
    ]


def test_logs_carry_no_content(repo: Path) -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        created = create(repo, request(repo))
    finally:
        logger = logging.getLogger("pmv")
        for item in list(logger.handlers):
            logger.removeHandler(item)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    output = buffer.getvalue()
    assert created.record_id in output
    assert REVIEW not in output
    assert str(repo) not in output
    assert "reliability_red_team" not in output


# ----- red-team repair regressions: request closure, history, ancestry, CLI errors -----


def test_the_request_cannot_choose_whether_owner_approval_is_required(
    repo: Path, tmp_path: Path
) -> None:
    assert "approval_requirement" not in GateRequest.__dataclass_fields__
    document = {
        "approval_attested": True,
        "approval_requirement": "not_required",
        "artifacts": [],
        "candidate_id": None,
        "cycle_id": None,
        "decision": "fail",
        "documents": [],
        "experiment_ledger": None,
        "findings": [],
        "gate_id": "gate_0",
        "holdout": [],
        "raw_captures": [],
        "reasons": ["control_missing"],
        "reviews": [],
        "run_check_sh": False,
        "runs": [],
        "supersedes": None,
    }
    with pytest.raises(GateRecordError, match="exactly the v1 fields"):
        request_from_json(document)


def committed_record(repo: Path, **overrides: Any) -> Any:
    created = create(repo, request(repo, **overrides))
    commit_all(repo, "record decision")
    return created


def merge_side(repo: Path, change: Callable[[], None], *, strategy: str | None = None) -> None:
    """Create a side branch, then merge it into main while ``change`` runs in the merge."""
    git(repo, "checkout", "-q", "-b", "side")
    git(repo, "commit", "-q", "--allow-empty", "-m", "side work")
    git(repo, "checkout", "-q", "main")
    if strategy is None:
        git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
        change()
        commit_all(repo, "merge side")
    else:
        git(repo, "merge", "-q", "-s", strategy, "--no-edit", "side")


def writable(path: Path) -> Path:
    path.chmod(0o644)
    return path


def test_c1_a_merge_commit_cannot_modify_a_committed_record(repo: Path) -> None:
    created = committed_record(repo, decision=Decision.FAIL, reasons=("control_missing",))
    data = created.path.read_bytes()

    def tamper() -> None:
        writable(created.path).write_bytes(data.replace(b"control_missing", b"criteria_not_met"))

    merge_side(repo, tamper)
    with pytest.raises(GateIntegrityError, match="modified, deleted, or replaced"):
        verify_gate_history(repo)


def test_c1_a_merge_commit_cannot_delete_a_committed_record(repo: Path) -> None:
    created = committed_record(repo)
    merge_side(repo, created.path.unlink)
    with pytest.raises(GateIntegrityError, match="modified, deleted, or replaced"):
        verify_gate_history(repo)


def test_c1_the_same_record_name_on_two_branches_merged_with_ours_is_rejected(
    repo: Path,
) -> None:
    fixed = {"clock": lambda: T0, "random_token": lambda: "c" * 32}
    git(repo, "checkout", "-q", "-b", "other")
    create(repo, request(repo, decision=Decision.FAIL, reasons=("control_missing",)), **fixed)
    commit_all(repo, "record on other")
    git(repo, "checkout", "-q", "main")
    create(repo, request(repo, decision=Decision.FAIL, reasons=("criteria_not_met",)), **fixed)
    commit_all(repo, "record on main")
    git(repo, "merge", "-q", "-s", "ours", "--no-edit", "other")
    with pytest.raises(GateIntegrityError, match="modified, deleted, or replaced"):
        verify_gate_history(repo)


def test_c1_a_side_branch_modification_merged_with_ours_is_rejected(repo: Path) -> None:
    created = committed_record(repo, decision=Decision.FAIL, reasons=("control_missing",))
    git(repo, "checkout", "-q", "-b", "side")
    writable(created.path).write_bytes(
        created.path.read_bytes().replace(b"control_missing", b"criteria_not_met")
    )
    commit_all(repo, "tamper on side")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "-s", "ours", "--no-edit", "side")
    assert b"control_missing" in created.path.read_bytes()
    with pytest.raises(GateIntegrityError, match="modified, deleted, or replaced"):
        verify_gate_history(repo)


def test_legitimate_merges_and_detached_pr_merge_states_verify(repo: Path) -> None:
    committed_record(repo)
    git(repo, "checkout", "-q", "-b", "feature")
    create(repo, request(repo, gate_id=GateId.GATE_1))
    commit_all(repo, "record on feature")
    git(repo, "checkout", "-q", "main")
    (repo / "docs" / "notes.md").write_text("unrelated\n", encoding="ascii")
    commit_all(repo, "unrelated main work")
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "feature")
    assert len(verify_gate_history(repo)) == 2
    git(repo, "checkout", "-q", "--detach", "HEAD")
    assert len(verify_gate_history(repo)) == 2
    git(repo, "checkout", "-q", "main")
    merge_side(repo, lambda: None)
    assert len(verify_gate_history(repo)) == 2


def test_local_replace_refs_and_grafts_cannot_hide_history(repo: Path) -> None:
    created = committed_record(repo, decision=Decision.FAIL, reasons=("control_missing",))
    writable(created.path).write_bytes(
        created.path.read_bytes().replace(b"control_missing", b"criteria_not_met")
    )
    commit_all(repo, "tamper")
    git(repo, "replace", "--graft", "HEAD")
    # Step 11 F-20: any replace ref now fails closed before history is even read.
    with pytest.raises(GateIntegrityError, match="replace refs exist"):
        verify_gate_history(repo)
    git(repo, "replace", "-d", git(repo, "rev-parse", "HEAD").decode().strip())
    grafts = repo / ".git" / "info" / "grafts"
    grafts.parent.mkdir(exist_ok=True)
    grafts.write_text(git(repo, "rev-parse", "HEAD").decode(), encoding="ascii")
    with pytest.raises(GateIntegrityError, match="info/grafts"):
        verify_gate_history(repo)


def test_c2_a_record_in_a_new_commit_verifies_and_later_commits_keep_it_valid(
    repo: Path,
) -> None:
    created = committed_record(repo)
    for index in range(3):
        (repo / "docs" / f"later_{index}.md").write_text("later\n", encoding="ascii")
        commit_all(repo, f"later work {index}")
    (only,) = verify_gate_history(repo)
    assert only.record.record_id == created.record_id


def test_c2_amending_a_record_into_its_project_commit_fails(repo: Path) -> None:
    create(repo, request(repo))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--amend", "--no-edit")
    with pytest.raises(GateIntegrityError, match="not in HEAD's history"):
        verify_gate_history(repo)


def test_c2_a_record_whose_project_commit_left_history_fails(repo: Path) -> None:
    (repo / "docs" / "extra.md").write_text("extra\n", encoding="ascii")
    commit_all(repo, "extra")
    create(repo, request(repo))
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    with pytest.raises(GateIntegrityError, match="not in HEAD's history"):
        verify_gate_history(repo)


def test_c2_a_project_commit_reached_only_through_a_later_merge_fails(repo: Path) -> None:
    git(repo, "checkout", "-q", "-b", "other")
    (repo / "docs" / "other.md").write_text("other\n", encoding="ascii")
    commit_all(repo, "other work")
    created = create(repo, request(repo))
    git(repo, "checkout", "-q", "main")
    assert created.path.exists()
    commit_all(repo, "record committed on main")
    with pytest.raises(GateIntegrityError, match="not in HEAD's history"):
        verify_gate_history(repo)
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "other")
    with pytest.raises(GateIntegrityError, match="new commit after the project commit"):
        verify_gate_history(repo)


def test_cli_reports_config_errors_without_a_traceback(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(
        'schema_version = 1\nenvironment = "development"\nsecret_value = "hunter2x"\n',
        encoding="ascii",
    )
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps(
            {
                "approval_attested": True,
                "artifacts": [],
                "candidate_id": None,
                "cycle_id": None,
                "decision": "fail",
                "documents": [],
                "experiment_ledger": None,
                "findings": [],
                "gate_id": "gate_0",
                "holdout": [],
                "raw_captures": [],
                "reasons": ["control_missing"],
                "reviews": [],
                "run_check_sh": False,
                "runs": [],
                "supersedes": None,
            }
        ),
        encoding="ascii",
    )
    arguments = ["--repo", str(repo), "create", "--request", str(path)]
    assert main([*arguments, "--config", str(bad), "--environment", "development"]) == 1
    error = capsys.readouterr().err
    assert error == "ConfigError: the configuration could not be loaded or is invalid\n"
    assert (
        main(
            [*arguments, "--config", str(tmp_path / "missing.toml"), "--environment", "development"]
        )
        == 1
    )
    error = capsys.readouterr().err
    assert "Traceback" not in error
    assert str(tmp_path) not in error


def test_a_check_sh_timeout_fails_closed_without_a_traceback(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    script = repo / "scripts" / "check.sh"
    script.write_text("#!/bin/sh\nsleep 5\n", encoding="ascii")
    commit_all(repo, "slow check")
    monkeypatch.setattr(gates, "CHECK_TIMEOUT_SECONDS", 0.2)
    with pytest.raises(GateStateError, match="time limit"):
        create_gate_record(repo, request(repo))
    path = tmp_path / "request.json"
    path.write_text(
        json.dumps(
            {
                "approval_attested": True,
                "artifacts": [],
                "candidate_id": None,
                "cycle_id": None,
                "decision": "fail",
                "documents": [],
                "experiment_ledger": None,
                "findings": [],
                "gate_id": "gate_0",
                "holdout": [],
                "raw_captures": [],
                "reasons": ["control_missing"],
                "reviews": [],
                "run_check_sh": True,
                "runs": [],
                "supersedes": None,
            }
        ),
        encoding="ascii",
    )
    config = development_config(tmp_path)
    assert main(["--repo", str(repo), "create", "--request", str(path), *config]) == 1
    assert (
        capsys.readouterr().err == "GateStateError: check.sh did not finish within its time limit\n"
    )


def test_pass_cannot_rest_on_an_ineligible_runs_artifacts(
    repo: Path, store: ExperimentStore
) -> None:
    run = completed_run(store)
    digest = store.snapshot().runs[run.run_id].artifacts["model.bin"][0]["sha256"]
    assert isinstance(digest, str)
    artifact = (ArtifactEvidence(run.run_id, "model.bin", digest),)
    with pytest.raises(GateRecordError, match=r"must be listed in evidence\.runs"):
        create(
            repo, request(repo, ledger_pin=pin(store), artifacts=artifact), experiment_store=store
        )
    baseline = (RunEvidence(run.run_id, RunRole.BASELINE),)
    with pytest.raises(GateRecordError, match="candidate or supporting runs"):
        create(
            repo,
            request(repo, ledger_pin=pin(store), runs=baseline, artifacts=artifact),
            experiment_store=store,
        )
    candidate = (RunEvidence(run.run_id, RunRole.CANDIDATE),)
    with pytest.raises(GateRecordError, match="evidence-eligible"):
        create(
            repo,
            request(repo, ledger_pin=pin(store), runs=candidate, artifacts=artifact),
            experiment_store=store,
        )


# ----- Step 11 F-21: governance and config pins are re-derived, not trusted -----


@pytest.mark.parametrize("field", ["governance", "configs"])
def test_f21_a_forged_pin_in_a_canonical_record_fails_history_verification(
    repo: Path, field: str
) -> None:
    created = committed_record(repo)
    verify_gate_history(repo)
    record = parse_record_file(created.path.read_bytes(), created.path.name)
    document = json.loads(json.dumps(dict(record.document)))
    document["project"][field][0]["sha256"] = "f" * 64
    forged = render_record(validate_record(document))
    writable(created.path).write_bytes(forged)
    # A forged file that is otherwise canonical must not pass as the committed record:
    # re-commit it as the "original" by rewriting the introducing commit's content.
    git(repo, "reset", "-q", "--soft", "HEAD~1")
    commit_all(repo, "record decision (forged)")
    with pytest.raises(GateIntegrityError, match="does not match its project commit"):
        verify_gate_history(repo)


def test_f21_a_record_whose_config_set_differs_from_its_commit_fails(repo: Path) -> None:
    created = committed_record(repo)
    record = parse_record_file(created.path.read_bytes(), created.path.name)
    document = json.loads(json.dumps(dict(record.document)))
    document["project"]["configs"] = []
    writable(created.path).write_bytes(render_record(validate_record(document)))
    git(repo, "reset", "-q", "--soft", "HEAD~1")
    commit_all(repo, "record decision (forged)")
    with pytest.raises(GateIntegrityError, match="config set does not match"):
        verify_gate_history(repo)


# ----- Step 11 F-20: replace refs cannot spoof evidence identity -----


def test_f20_a_replace_ref_makes_gate_evidence_identity_unknown(repo: Path) -> None:
    (repo / "docs" / "other.md").write_text("other\n", encoding="ascii")
    commit_all(repo, "other")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    previous = git(repo, "rev-parse", "HEAD~1").decode().strip()
    git(repo, "replace", head, previous)
    with pytest.raises(GateStateError, match="code identity cannot be determined"):
        capture_project_identity(repo)
    git(repo, "replace", "-d", head)
    assert capture_project_identity(repo).commit == head


def test_the_create_command_refuses_the_test_environment(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RT-4: gate commands refuse the test environment before reading anything."""
    request_path = tmp_path / "request.json"
    request_path.write_text("{}", encoding="ascii")
    arguments = ["--repo", str(repo), "create", "--request", str(request_path)]
    config = ["--config", str(repo / "configs" / "test.toml"), "--environment", "test"]
    assert main([*arguments, *config]) == 1
    error = capsys.readouterr().err
    assert error.startswith("RefusedTestEnvironmentError: pmv.gates create refuses")
    assert list_gate_records(repo) == []
