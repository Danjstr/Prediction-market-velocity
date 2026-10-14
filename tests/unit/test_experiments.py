"""Integration tests for the experiment tracking store, including crashes and concurrency."""

import io
import json
import logging
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import pmv.experiments as experiments
from pmv.config import (
    ConfigError,
    Environment,
    LoggingConfig,
    LogLevel,
    RawStorageConfig,
    load_config,
)
from pmv.experiment_ledger import LedgerEvent, RunState, completion_manifest_bytes
from pmv.experiment_spec import (
    AbortReason,
    ArtifactType,
    FailureCode,
    MediaType,
    RawCaptureInput,
    RunArtifactInput,
    RunClass,
    RunSpec,
    Seed,
    SpecError,
    Split,
    SupersedeReason,
    WarningCode,
    spec_sections,
)
from pmv.experiments import (
    DuplicateRunIdError,
    ExperimentError,
    ExperimentIntegrityError,
    ExperimentStore,
    GitIdentity,
    InputVerificationError,
    PendingRepairEvidenceError,
    RecoveryOutcome,
    RunHandle,
    RunStateError,
    TornLedgerError,
)
from pmv.integrity import canonical_line, sha256_hex
from pmv.log import configure_logging
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport
from pmv.raw_storage import RawCaptureStore
from pmv.reproducibility import EnvironmentCapture, ReproducibilityError

REPO = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 10, 13, 3, 40, 21, tzinfo=UTC)
CLEAN = GitIdentity("a" * 40, False, None)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=1)
        return self.now


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "exp-root"
    path.mkdir(mode=0o700)
    yield path
    for base in (path, tmp_path / "old-root", tmp_path / "raw-root"):
        if base.exists():
            for directory, _subdirs, _files in os.walk(base):
                os.chmod(directory, 0o700)


@pytest.fixture(autouse=True)
def clean_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(experiments, "collect_git_identity", lambda _repo: CLEAN)


def synthetic_capture(version: str = "1.0") -> EnvironmentCapture:
    document = canonical_line(
        {
            "distributions": [{"files_sha256": "7" * 64, "name": "numpy", "version": version}],
            "interpreter": {
                "byteorder": "little",
                "cache_tag": "cpython-313",
                "flags": {
                    "dev_mode": False,
                    "hash_randomization": 1,
                    "optimize": 0,
                    "utf8_mode": 0,
                },
                "gil_disabled": False,
                "implementation": "cpython",
                "platform": "linux-x86_64",
                "soabi": "cpython-313-x86_64-linux-gnu",
                "version": "3.13.5",
            },
            "project": {"editable": True, "name": "prediction-market-velocity", "version": "0.0.0"},
            "schema": "pmv.environment",
            "schema_version": 1,
        }
    )
    return EnvironmentCapture(document, sha256_hex(document))


class FakeEnvironment:
    """A synthetic installed environment; tests change or break it explicitly."""

    def __init__(self) -> None:
        self.capture: EnvironmentCapture | None = synthetic_capture()
        self.calls: list[bool] = []

    def __call__(self, _repo: Path, *, verify_conformance: bool) -> EnvironmentCapture:
        self.calls.append(verify_conformance)
        if self.capture is None:
            raise ReproducibilityError("synthetic verification failure")
        return self.capture


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> FakeEnvironment:
    fake = FakeEnvironment()
    monkeypatch.setattr(experiments, "capture_environment", fake)
    return fake


def open_store(root: Path, **kwargs: object) -> ExperimentStore:
    options: dict[str, object] = {
        "repo_root": REPO,
        "app_config_sha256": "0" * 64,
        "checkpoint_file": root.parent / "checkpoints.v1.jsonl",
        "clock": Clock(),
        "lock_timeout_seconds": 10.0,
    }
    options.update(kwargs)
    return ExperimentStore(root, **options)  # type: ignore[arg-type]  # test helper forwards typed keywords


def make_spec(**overrides: object) -> RunSpec:
    values: dict[str, object] = {
        "study_id": "velocity_baseline",
        "entrypoint": "pmv.research.baselines:run",
        "sections": spec_sections(model={"family": "logistic", "l2": "0.01"}),
        "seeds": (Seed("numpy", 7),),
        "splits_accessed": (Split.TRAIN,),
    }
    values.update(overrides)
    return RunSpec(**values)  # type: ignore[arg-type]  # test helper forwards typed keywords


def started(store: ExperimentStore, spec: RunSpec | None = None) -> RunHandle:
    handle = store.reserve_run("velocity_baseline", RunClass.EVIDENCE_CANDIDATE)
    handle.start(spec or make_spec())
    return handle


def completed(store: ExperimentStore, data: bytes = b"model-bytes") -> RunHandle:
    handle = started(store)
    handle.write_artifact(
        "model.bin", data, artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
    )
    handle.record_metric("log_loss", "development", Decimal("0.6931"))
    handle.complete()
    return handle


def mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def ledger_path(root: Path) -> Path:
    return root / "ledger" / "experiments.v1.jsonl"


class SimulatedCrashError(Exception):
    pass


def crash_at(point: str) -> Callable[[str], None]:
    def hook(name: str) -> None:
        if name == point:
            raise SimulatedCrashError

    return hook


# ----- lifecycle -----


def test_full_lifecycle_produces_verified_immutable_evidence(root: Path) -> None:
    with open_store(root) as store:
        handle = started(store)
        handle.write_artifact(
            "model.bin", b"\x00model", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
        )
        staged = handle.staging_path()
        staged.write_bytes(b"predictions")
        handle.commit_artifact(
            staged,
            "predictions.csv",
            artifact_type=ArtifactType.PREDICTIONS,
            media_type=MediaType.CSV,
            schema_id="predictions",
            schema_version=1,
        )
        handle.record_metric("log_loss", "development", 0.6931, unit="nats", fold="f1", step=3)
        handle.record_warning(WarningCode.CONVERGENCE_WARNING, "solver")
        handle.complete()
        state = store.snapshot()
        run = state.runs[handle.run_id]
        assert run.state is RunState.COMPLETED
        verification = store.verify_run(handle.run_id)
        assert verification.unregistered_files == ()
        assert verification.staging_files == ()
        directory = root / "runs" / handle.run_id
        assert (directory / "manifest.json").read_bytes() == completion_manifest_bytes(
            state, handle.run_id
        )
        assert mode(directory) == 0o500
        for name in ("run_spec.json", "environment.json", "manifest.json", "artifacts/model.bin"):
            assert mode(directory / name) == 0o400
        assert mode(ledger_path(root)) == 0o600
        assert (directory / "environment.json").read_bytes() == synthetic_capture().document
        assert run.identity is not None
        assert run.identity.version == 2
        assert run.identity.installed_environment_sha256 == synthetic_capture().sha256
        assert store.eligibility_as_of(handle.run_id)
        with pytest.raises(RunStateError):
            handle.record_metric("late", "development", 1)


def test_duplicate_run_ids_are_refused(root: Path) -> None:
    with open_store(root, clock=lambda: T0, random_token=lambda: "a" * 32) as store:
        store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        with pytest.raises(DuplicateRunIdError):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


def test_artifacts_are_never_overwritten_and_corruption_is_detected(root: Path) -> None:
    with open_store(root) as store:
        handle = started(store)
        handle.write_artifact(
            "model.bin", b"first", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
        )
        with pytest.raises(RunStateError, match="already exists"):
            handle.write_artifact(
                "model.bin",
                b"second",
                artifact_type=ArtifactType.MODEL,
                media_type=MediaType.BINARY,
            )
        artifact = root / "runs" / handle.run_id / "artifacts" / "model.bin"
        assert artifact.read_bytes() == b"first"
        (root / "runs" / handle.run_id / ".staging").chmod(0o700)
        for leftover in (root / "runs" / handle.run_id / ".staging").iterdir():
            leftover.unlink()
        handle.complete()
        (root / "runs" / handle.run_id).chmod(0o700)
        (root / "runs" / handle.run_id / "artifacts").chmod(0o700)
        artifact.chmod(0o600)
        artifact.write_bytes(b"firsT")
        artifact.chmod(0o400)
        with pytest.raises(ExperimentIntegrityError, match="does not match"):
            store.verify_run(handle.run_id)


def test_unregistered_files_block_completion_and_are_reported(root: Path) -> None:
    with open_store(root) as store:
        handle = started(store)
        stray = root / "runs" / handle.run_id / "artifacts" / "stray.bin"
        stray.write_bytes(b"x")
        with pytest.raises(RunStateError, match="exactly the registered"):
            handle.complete()
        assert store.verify_run(handle.run_id).unregistered_files == ("stray.bin",)


def test_staged_paths_must_be_this_runs_private_staging(root: Path, tmp_path: Path) -> None:
    with open_store(root) as store:
        handle = started(store)
        outside = tmp_path / ("part-" + "0" * 32)
        outside.write_bytes(b"x")
        with pytest.raises(RunStateError, match="private staging"):
            handle.commit_artifact(
                outside, "x.bin", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
            )


def test_metric_rules(root: Path) -> None:
    with open_store(root) as store:
        handle = started(store)
        with pytest.raises(SpecError, match="protected_holdout"):
            handle.record_metric("log_loss", "protected_holdout", 1)
        for bad in (float("nan"), float("inf")):
            with pytest.raises(SpecError):
                handle.record_metric("log_loss", "development", bad)
        handle.record_metric("brier", "validation", Decimal("0.21"))
        metric = store.snapshot().runs[handle.run_id].metrics[0][1]
        assert metric["value"] == {"text": "0.21", "type": "decimal"}


def test_code_identity_change_fails_the_run(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with open_store(root) as store:
        handle = started(store)
        changed = GitIdentity("b" * 40, False, None)
        monkeypatch.setattr(experiments, "collect_git_identity", lambda _repo: changed)
        with pytest.raises(RunStateError, match="code identity changed"):
            handle.complete()
        run = store.snapshot().runs[handle.run_id]
        assert run.state is RunState.FAILED


def test_dirty_code_is_recorded_as_exploratory(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dirty = GitIdentity("a" * 40, True, "4" * 64)
    monkeypatch.setattr(experiments, "collect_git_identity", lambda _repo: dirty)
    with open_store(root) as store:
        handle = started(store)
        run = store.snapshot().runs[handle.run_id]
        assert run.start_fields["effective_run_class_at_start"] == "exploratory"
        assert run.identity is not None
        assert run.identity.dirty_tree_sha256 == "4" * 64


def test_clean_and_dirty_git_identity_collection_on_this_repository() -> None:
    identity = experiments.collect_git_identity(REPO)
    assert identity.commit is not None
    assert identity.dirty in (True, False)
    assert (identity.dirty_sha256 is None) == (identity.dirty is False)
    assert experiments.collect_git_identity(REPO) == identity


# ----- inputs and temporal eligibility -----


def raw_store(base: Path, *, clean: bool) -> tuple[RawCaptureStore, str, str]:
    root = base / "raw-root"
    root.mkdir(mode=0o700, exist_ok=True)
    config = RawStorageConfig(root=root, warning_free_bytes=1000, hard_stop_free_bytes=100)
    provenance = RuntimeProvenance(
        code_commit="a" * 40 if clean else None,
        code_tree_dirty=False if clean else None,
        config_source_sha256="0" * 64,
        raw_config_sha256=config.canonical_sha256(),
        environment=Environment.TEST,
        python_version="3.13.5",
        platform="linux-x86_64",
        machine_label=None,
        parents=(),
    )
    store = RawCaptureStore(config, provenance, repo_root=REPO, free_bytes=lambda: 10**12)
    source = SourceIdentity(
        source_id="unit_source", feed_id="unit_feed", transport=Transport.HTTP, endpoint_id="ep"
    )
    capture = store.start_capture(source, T0)
    capture.append_payload(b"raw", received_at=T0)
    manifest = capture.finalize()
    digest = store.verify_capture(manifest.capture_id).manifest_sha256
    return store, manifest.capture_id, digest


def test_raw_capture_inputs_are_verified_exactly(root: Path, tmp_path: Path) -> None:
    raws, capture_id, digest = raw_store(tmp_path, clean=False)
    with raws, open_store(root, raw_store=raws, raw_root=raws.config.root) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        with pytest.raises(InputVerificationError, match="does not match"):
            handle.start(make_spec(inputs=(RawCaptureInput(capture_id, "f" * 64),)))
        handle.start(make_spec(inputs=(RawCaptureInput(capture_id, digest),)))
        (recorded,) = store.snapshot().runs[handle.run_id].inputs
        assert recorded["capture_code_clean"] is False
    with open_store(root) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        with pytest.raises(InputVerificationError, match="raw capture store"):
            handle.start(make_spec(inputs=(RawCaptureInput(capture_id, digest),)))


def test_run_artifact_inputs_need_a_completed_producer_and_exact_bytes(root: Path) -> None:
    with open_store(root) as store:
        producer = started(store)
        producer.write_artifact(
            "model.bin", b"bytes", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
        )
        digest = sha256_hex(b"bytes")
        consumer = store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        reference = RunArtifactInput(producer.run_id, "model.bin", digest)
        with pytest.raises(InputVerificationError, match="completed run"):
            consumer.start(make_spec(inputs=(reference,)))
        producer.complete()
        with pytest.raises(InputVerificationError, match="do not match"):
            consumer.start(
                make_spec(inputs=(RunArtifactInput(producer.run_id, "model.bin", "f" * 64),))
            )
        consumer.start(make_spec(inputs=(reference,)))


def test_supersession_never_rewrites_history_and_retracts_as_of_eligibility(root: Path) -> None:
    with open_store(root) as store:
        producer = completed(store)
        state = store.snapshot()
        digest = state.runs[producer.run_id].artifacts["model.bin"][0]["sha256"]
        assert isinstance(digest, str)
        consumer = started(
            store, make_spec(inputs=(RunArtifactInput(producer.run_id, "model.bin", digest),))
        )
        consumer.write_artifact(
            "model.bin", b"c", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
        )
        consumer.complete()
        before = store.snapshot()
        replacement = completed(store, b"corrected")
        store.supersede(producer.run_id, replacement.run_id, SupersedeReason.CORRECTED_CODE)
        after = store.snapshot()
        assert after.entries[: len(before.entries)] == before.entries
        for run in after.runs.values():
            assert run.identity is not None
            assert run.identity.installed_environment_sha256 == synthetic_capture().sha256
            assert run.start_fields["effective_run_class_at_start"] == "evidence_candidate"
            assert run.eligible_at_start is True
        # Supersession retracts later as-of answers (transitively), never history.
        assert not store.eligibility_as_of(producer.run_id)
        assert not store.eligibility_as_of(consumer.run_id)
        assert store.eligibility_as_of(producer.run_id, len(before.entries) - 1)
        assert store.eligibility_as_of(consumer.run_id, len(before.entries) - 1)
        assert store.eligibility_as_of(replacement.run_id)


# ----- recovery -----


def test_recovery_interrupts_orphans_and_never_touches_active_runs(root: Path) -> None:
    with open_store(root) as store:
        orphan = started(store)
        orphan.release()
        active = started(store)
        results = {item.run_id: item.outcome for item in store.recover()}
        assert results[orphan.run_id] is RecoveryOutcome.INTERRUPTED
        assert results[active.run_id] is RecoveryOutcome.ACTIVE
        state = store.snapshot()
        assert state.runs[orphan.run_id].state is RunState.INTERRUPTED
        assert state.runs[active.run_id].state is RunState.STARTED
        active.abort(AbortReason.OPERATOR_REQUEST)


def test_reservation_without_a_ledger_event_is_reported(root: Path) -> None:
    with (
        open_store(root, fault_hook=crash_at("reserve.reserved")) as store,
        pytest.raises(SimulatedCrashError),
    ):
        store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
    with open_store(root) as store:
        assert [item.outcome for item in store.recover()] == [RecoveryOutcome.RESERVED_UNRECORDED]


# ----- authoritative append protections -----


def test_root_replacement_before_write_fails_closed(root: Path) -> None:
    with open_store(root):
        genesis = ledger_path(root).read_bytes()

    def replace(point: str) -> None:
        if point == "ledger.before_write":
            os.rename(root, root.parent / "old-root")
            root.mkdir(mode=0o700)

    with (
        open_store(root, fault_hook=replace) as store,
        pytest.raises(ExperimentIntegrityError, match="moved or replaced"),
    ):
        store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
    assert ledger_path(root.parent / "old-root").read_bytes() == genesis


def test_root_replacement_after_write_is_not_reported_as_recorded(root: Path) -> None:
    def replace(point: str) -> None:
        if point == "ledger.after_write":
            os.rename(root, root.parent / "old-root")
            root.mkdir(mode=0o700)

    with open_store(root, fault_hook=replace) as store:
        with pytest.raises(ExperimentIntegrityError, match="write outcome unknown; re-verify"):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        with pytest.raises(ExperimentIntegrityError, match="open a new store"):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


def test_short_write_rolls_back_and_latches_the_store(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with open_store(root) as store:
        handle = started(store)
        before = ledger_path(root).read_bytes()
        monkeypatch.setattr(experiments, "_ledger_write", lambda fd, data: os.write(fd, data[:9]))
        with pytest.raises(OSError, match="short write"):
            handle.record_metric("log_loss", "development", 1)
        monkeypatch.undo()
        monkeypatch.setattr(experiments, "collect_git_identity", lambda _repo: CLEAN)
        assert ledger_path(root).read_bytes() == before
        with pytest.raises(ExperimentIntegrityError, match="open a new store"):
            handle.record_metric("log_loss", "development", 1)
    with open_store(root) as fresh:
        assert fresh.snapshot().head_seq == 2


def test_failed_rollback_leaves_a_torn_tail_that_blocks_appends(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_truncate(_fd: int, _size: int) -> None:
        raise OSError(5, "I/O error")

    with open_store(root) as store:
        handle = started(store)
        monkeypatch.setattr(experiments, "_ledger_write", lambda fd, data: os.write(fd, data[:9]))
        monkeypatch.setattr(experiments, "_ledger_truncate", failing_truncate)
        with pytest.raises(ExperimentIntegrityError, match="could not be rolled back"):
            handle.record_metric("log_loss", "development", 1)
    monkeypatch.undo()
    monkeypatch.setattr(experiments, "collect_git_identity", lambda _repo: CLEAN)
    with open_store(root) as store:
        with pytest.raises(TornLedgerError):
            store.snapshot()
        with pytest.raises(TornLedgerError):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


# ----- torn-tail repair -----


def torn_store(root: Path) -> bytes:
    with open_store(root) as store:
        completed(store)
    path = ledger_path(root)
    path.chmod(0o600)
    with path.open("ab") as handle:
        handle.write(b'{"event_type":"metric_rec')
    return path.read_bytes()


def evidence(root: Path) -> list[str]:
    return sorted(os.listdir(root / "ledger" / "repair"))


def test_repair_preserves_evidence_then_removes_the_tail(root: Path) -> None:
    damaged = torn_store(root)
    with open_store(root) as store:
        report = store.repair_torn_tail()
        assert report.truncated_bytes == len(b'{"event_type":"metric_rec')
        assert report.evidence_written is not None
        (name,) = evidence(root)
        assert (root / "ledger" / "repair" / name).read_bytes() == b'{"event_type":"metric_rec'
        assert mode(root / "ledger" / "repair" / name) == 0o400
        state = store.snapshot()
        assert state.entries[-1].event_type is LedgerEvent.LEDGER_TAIL_REPAIRED
        assert ledger_path(root).read_bytes().startswith(damaged[: damaged.rfind(b"\n") + 1])
        assert store.repair_torn_tail().events_appended == ()
        store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


def test_repair_resumes_after_crash_with_evidence_written(root: Path) -> None:
    torn_store(root)
    with (
        open_store(root, fault_hook=crash_at("repair.evidence_written")) as store,
        pytest.raises(SimulatedCrashError),
    ):
        store.repair_torn_tail()
    with open_store(root) as store:
        with pytest.raises(TornLedgerError):
            store.snapshot()
        report = store.repair_torn_tail()
        assert report.evidence_written is None
        assert len(report.events_appended) == 1
        assert len(evidence(root)) == 1
        store.snapshot()


def test_repair_resumes_after_crash_with_ledger_truncated(root: Path) -> None:
    torn_store(root)
    with (
        open_store(root, fault_hook=crash_at("repair.truncated")) as store,
        pytest.raises(SimulatedCrashError),
    ):
        store.repair_torn_tail()
    with open_store(root) as store:
        with pytest.raises(PendingRepairEvidenceError):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        report = store.repair_torn_tail()
        assert report.truncated_bytes == 0
        assert len(report.events_appended) == 1
        store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


def test_a_torn_repair_event_is_itself_preserved_and_repaired(root: Path) -> None:
    torn_store(root)
    with (
        open_store(root, fault_hook=crash_at("repair.truncated")) as store,
        pytest.raises(SimulatedCrashError),
    ):
        store.repair_torn_tail()
    with ledger_path(root).open("ab") as handle:
        handle.write(b'{"event_type":"ledger_tail_rep')
    with open_store(root) as store:
        report = store.repair_torn_tail()
        assert report.evidence_written is not None
        assert len(report.events_appended) == 2
        assert len(evidence(root)) == 2
        state = store.snapshot()
        assert [entry.event_type for entry in state.entries[-2:]] == [
            LedgerEvent.LEDGER_TAIL_REPAIRED,
            LedgerEvent.LEDGER_TAIL_REPAIRED,
        ]


def test_repair_refuses_to_contradict_a_checkpoint(root: Path) -> None:
    with open_store(root) as store:
        completed(store)
        store.append_checkpoint()
    path = ledger_path(root)
    data = path.read_bytes()
    path.write_bytes(data[:-5])
    with (
        open_store(root) as store,
        pytest.raises(ExperimentIntegrityError, match="beyond the verified ledger head"),
    ):
        store.repair_torn_tail()
    assert path.read_bytes() == data[:-5]
    assert evidence(root) == []


def test_repair_refuses_a_malformed_complete_line(root: Path) -> None:
    with open_store(root) as store:
        completed(store)
    with ledger_path(root).open("ab") as handle:
        handle.write(b"{not json}\n")
    with open_store(root) as store, pytest.raises(ExperimentIntegrityError, match="not canonical"):
        store.repair_torn_tail()


# ----- checkpoints -----


def test_checkpoints_detect_end_truncation_and_are_not_auto_committed(root: Path) -> None:
    with open_store(root) as store:
        completed(store)
        checkpoint = store.append_checkpoint()
        with pytest.raises(ExperimentError, match="already checkpointed"):
            store.append_checkpoint()
        (status,) = store.checkpoint_status()
        assert status.checkpoint == checkpoint
        assert status.committed_in_git is False
    path = ledger_path(root)
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(b"".join(line + b"\n" for line in lines[:-1]))
    with open_store(root) as store, pytest.raises(ExperimentIntegrityError, match="beyond"):
        store.snapshot()


# ----- filesystem attacks, logging, configuration -----


def test_symlinked_root_or_managed_directories_are_rejected(root: Path, tmp_path: Path) -> None:
    link = tmp_path / "link-root"
    link.symlink_to(root)
    with pytest.raises(ExperimentIntegrityError, match="not a plain directory"):
        open_store(link)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (root / "runs").symlink_to(outside)
    with pytest.raises(ExperimentIntegrityError, match="not a plain directory"):
        open_store(root)
    assert os.listdir(outside) == []


def test_root_must_not_nest_with_the_repository_or_raw_root(root: Path, tmp_path: Path) -> None:
    with pytest.raises(ExperimentError, match="nested"):
        open_store(root, repo_root=root.parent)
    with pytest.raises(ExperimentError, match="nested"):
        open_store(root, raw_root=root / "raw")
    with pytest.raises(ExperimentError, match="absolute"):
        ExperimentStore(Path("relative"), repo_root=REPO, app_config_sha256="0" * 64)


def test_logs_never_contain_artifact_or_spec_contents(root: Path) -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        with open_store(root) as store:
            handle = started(store)
            handle.write_artifact(
                "model.bin",
                b"SENSITIVE-ARTIFACT-MARKER",
                artifact_type=ArtifactType.MODEL,
                media_type=MediaType.BINARY,
            )
            handle.fail(FailureCode.EXCEPTION, "ValueError")
    finally:
        logger = logging.getLogger("pmv")
        for item in list(logger.handlers):
            logger.removeHandler(item)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    output = buffer.getvalue()
    assert "SENSITIVE-ARTIFACT-MARKER" not in output
    assert "logistic" not in output
    records = [json.loads(line) for line in output.splitlines()]
    assert all(record["event"] != "log.invalid_event" for record in records)


def test_experiments_config_section(tmp_path: Path) -> None:
    base = 'schema_version = 1\nenvironment = "test"\n\n[logging]\nlevel = "INFO"\n'
    path = tmp_path / "test.toml"
    path.write_text(base, encoding="utf-8")
    assert load_config(path, Environment.TEST).experiments.root is None
    path.write_text(base + '\n[experiments]\nroot = "/srv/pmv-experiments"\n', encoding="utf-8")
    assert load_config(path, Environment.TEST).experiments.root == Path("/srv/pmv-experiments")
    for section in ('root = "relative"', "extra = 1"):
        path.write_text(base + f"\n[experiments]\n{section}\n", encoding="utf-8")
        with pytest.raises(ConfigError):
            load_config(path, Environment.TEST)
    for shipped in sorted((REPO / "configs").glob("*.toml")):
        assert load_config(shipped, Environment(shipped.stem)).experiments.root is None


# ----- red-team regressions -----


def detach(path: Path) -> None:
    """Rename ``path`` aside and put an empty private directory in its place."""
    os.rename(path, path.with_name(path.name + "-detached"))
    path.mkdir(mode=0o700)


def test_c1_repair_directory_replaced_before_truncation_never_truncates(root: Path) -> None:
    damaged = torn_store(root)
    repair = root / "ledger" / "repair"

    def replace(point: str) -> None:
        if point == "repair.evidence_written":
            detach(repair)

    with open_store(root, fault_hook=replace) as store:
        with pytest.raises(ExperimentIntegrityError, match="the ledger was not truncated"):
            store.repair_torn_tail()
        with pytest.raises(ExperimentIntegrityError, match="open a new store"):
            store.repair_torn_tail()
    assert ledger_path(root).read_bytes() == damaged
    assert os.listdir(repair) == []
    with open_store(root) as fresh:
        with pytest.raises(TornLedgerError):
            fresh.snapshot()
        with pytest.raises(TornLedgerError):
            fresh.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
    assert ledger_path(root).read_bytes() == damaged


def test_c1_evidence_file_replaced_before_truncation_never_truncates(root: Path) -> None:
    damaged = torn_store(root)
    repair = root / "ledger" / "repair"

    def replace(point: str) -> None:
        if point == "repair.evidence_written":
            (name,) = os.listdir(repair)
            content = (repair / name).read_bytes()
            os.rename(repair / name, root / "moved-evidence.bin")
            (repair / name).write_bytes(content)

    with (
        open_store(root, fault_hook=replace) as store,
        pytest.raises(ExperimentIntegrityError, match="the repair evidence was replaced"),
    ):
        store.repair_torn_tail()
    assert ledger_path(root).read_bytes() == damaged


def run_dir_replacer(root: Path, point: str) -> tuple[Callable[[str], None], list[str]]:
    targets: list[str] = []

    def hook(name: str) -> None:
        if name == point and targets:
            detach(root / "runs" / targets.pop())

    return hook, targets


def test_c2_start_with_replaced_run_directory_is_not_reported(root: Path) -> None:
    hook, targets = run_dir_replacer(root, "ledger.before_write")
    with open_store(root, fault_hook=hook) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        targets.append(handle.run_id)
        with pytest.raises(ExperimentIntegrityError, match="run directory was moved or replaced"):
            handle.start(make_spec())
        assert store.snapshot().runs[handle.run_id].state is RunState.RESERVED


def test_c2_commit_artifact_with_replaced_run_directory_is_not_reported(root: Path) -> None:
    hook, targets = run_dir_replacer(root, "artifact.moved")
    with open_store(root, fault_hook=hook) as store:
        handle = started(store)
        targets.append(handle.run_id)
        staged = handle.staging_path()
        staged.write_bytes(b"model")
        with pytest.raises(ExperimentIntegrityError, match="run directory was moved or replaced"):
            handle.commit_artifact(
                staged, "model.bin", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
            )
        assert store.snapshot().runs[handle.run_id].artifacts == {}


def test_c2_complete_with_replaced_run_directory_is_not_reported(root: Path) -> None:
    hook, targets = run_dir_replacer(root, "complete.manifest_written")
    with open_store(root, fault_hook=hook) as store:
        handle = started(store)
        handle.write_artifact(
            "model.bin", b"x", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
        )
        targets.append(handle.run_id)
        with pytest.raises(ExperimentIntegrityError, match="run directory was moved or replaced"):
            handle.complete()
        assert store.snapshot().runs[handle.run_id].state is RunState.STARTED


def test_c2_run_directory_replaced_after_write_latches_with_unknown_outcome(root: Path) -> None:
    hook, targets = run_dir_replacer(root, "ledger.after_write")
    with open_store(root, fault_hook=hook) as store:
        handle = started(store)
        targets.append(handle.run_id)
        with pytest.raises(ExperimentIntegrityError, match="write outcome unknown; re-verify"):
            handle.record_metric("log_loss", "development", 1)
        with pytest.raises(ExperimentIntegrityError, match="open a new store"):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


def test_c2_a_pristine_store_creates_the_ledger_with_its_genesis_entry(root: Path) -> None:
    with open_store(root) as store:
        (genesis,) = store.snapshot().entries
        assert genesis.event_type is LedgerEvent.LEDGER_CREATED
        assert genesis.run_id is None
        assert mode(ledger_path(root)) == 0o600
    assert [name for name in os.listdir(root / "ledger") if name.startswith(".")] == []
    with open_store(root) as again:
        assert again.snapshot().head_seq == 0


def test_c2_a_used_store_never_recreates_a_deleted_ledger(root: Path) -> None:
    with open_store(root) as store:
        completed(store)
        ledger_path(root).unlink()
        with pytest.raises(ExperimentIntegrityError, match="missing"):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
    with pytest.raises(ExperimentIntegrityError, match="prior history"):
        open_store(root)
    assert not ledger_path(root).exists()


def test_c2_a_used_store_refuses_a_replaced_empty_ledger(root: Path) -> None:
    with open_store(root) as store:
        completed(store)
        ledger_path(root).rename(root / "old-ledger.jsonl")
        ledger_path(root).write_bytes(b"")
        with pytest.raises(ExperimentIntegrityError, match="moved or replaced"):
            store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
    with pytest.raises(ExperimentIntegrityError, match="empty"):
        open_store(root)


def test_c2_a_ledger_from_another_store_is_refused(root: Path, tmp_path: Path) -> None:
    other = tmp_path / "other-root"
    other.mkdir(mode=0o700)
    with open_store(other) as store:
        completed(store)
    with open_store(root) as store:
        completed(store)
    ledger_path(root).unlink()
    os.link(ledger_path(other), ledger_path(root))
    with (
        open_store(root) as store,
        pytest.raises(ExperimentIntegrityError, match="different experiment store"),
    ):
        store.snapshot()


# ----- real processes: concurrency and crashes -----

CHILD = """
import os, sys
from pathlib import Path
from decimal import Decimal
import pmv.experiments as experiments
from pmv.experiment_spec import (
    ArtifactType, MediaType, RunClass, RunSpec, Seed, Split, spec_sections,
)

root, repo, checkpoints = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
mode, point = sys.argv[4], sys.argv[5]
experiments.collect_git_identity = lambda _repo: experiments.GitIdentity("a" * 40, False, None)

def hook(name):
    if name == point:
        os._exit(70)

store = experiments.ExperimentStore(
    root, repo_root=repo, app_config_sha256="0" * 64, checkpoint_file=checkpoints,
    fault_hook=hook, lock_timeout_seconds=60.0,
)
spec = RunSpec(
    study_id="velocity_baseline", entrypoint="pmv.research.baselines:run",
    sections=spec_sections(model={"family": "logistic"}), seeds=(Seed("numpy", 7),),
    splits_accessed=(Split.TRAIN,),
)
handle = store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
handle.start(spec)
if mode == "metrics":
    for step in range(10):
        handle.record_metric("log_loss", "development", Decimal("0.5"), step=step)
    handle.abort("operator_request")
else:
    handle.write_artifact(
        "model.bin", b"bytes", artifact_type=ArtifactType.MODEL, media_type=MediaType.BINARY
    )
    handle.complete()
os._exit(0)
"""


def run_child(root: Path, mode_name: str, point: str) -> "subprocess.Popen[bytes]":
    return subprocess.Popen(  # noqa: S603 - runs this interpreter with a fixed test script
        [
            sys.executable,
            "-I",
            "-c",
            CHILD,
            str(root),
            str(REPO),
            str(root.parent / "checkpoints.v1.jsonl"),
            mode_name,
            point,
        ],
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_concurrent_processes_append_a_single_valid_chain(root: Path) -> None:
    with open_store(root):
        pass
    children = [run_child(root, "metrics", "never") for _ in range(4)]
    assert [child.wait(timeout=180) for child in children] == [0, 0, 0, 0]
    with open_store(root) as store:
        state = store.snapshot()
        assert len(state.runs) == 4
        assert len(state.entries) == 1 + 4 * (1 + 1 + 10 + 1)
        assert all(run.state is RunState.ABORTED for run in state.runs.values())


@pytest.mark.parametrize(
    ("point", "outcome", "check"),
    [
        ("reserve.reserved", RecoveryOutcome.RESERVED_UNRECORDED, None),
        ("reserve.locked", RecoveryOutcome.RESERVED_UNRECORDED, None),
        ("ledger.after_write", RecoveryOutcome.INTERRUPTED, None),
        ("artifact.staged", RecoveryOutcome.INTERRUPTED, "staging"),
        ("artifact.moved", RecoveryOutcome.INTERRUPTED, "unregistered"),
        ("complete.manifest_written", RecoveryOutcome.INTERRUPTED, "orphan_manifest"),
    ],
)
def test_crashes_at_each_boundary_are_recoverable_without_rewriting_history(
    root: Path, point: str, outcome: RecoveryOutcome, check: str | None
) -> None:
    with open_store(root):
        pass
    assert run_child(root, "artifact", point).wait(timeout=180) == 70
    with open_store(root) as store:
        before = ledger_path(root).read_bytes()
        (result,) = store.recover()
        assert result.outcome is outcome
        assert ledger_path(root).read_bytes().startswith(before)
        state = store.snapshot()
        if outcome is RecoveryOutcome.INTERRUPTED:
            run = state.runs[result.run_id]
            assert run.state is RunState.INTERRUPTED
            verification = store.verify_run(result.run_id)
            if check == "staging":
                assert verification.staging_files
            elif check == "unregistered":
                assert verification.unregistered_files == ("model.bin",)
            elif check == "orphan_manifest":
                assert verification.orphan_manifest
        assert store.recover() in ([], [result])


# ----- pending-repair state: post-truncation race and crash points (real processes) -----

REPAIR_CHILD = """
import os, sys
from pathlib import Path
import pmv.experiments as experiments

root, repo, checkpoints, point, detach = (
    Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5] == "1"
)

def hook(name):
    if name == point:
        if detach:
            repair = root / "ledger" / "repair"
            os.rename(repair, repair.with_name("repair-detached"))
            repair.mkdir(mode=0o700)
        os._exit(70)

store = experiments.ExperimentStore(
    root, repo_root=repo, app_config_sha256="0" * 64, checkpoint_file=checkpoints,
    fault_hook=hook, lock_timeout_seconds=60.0,
)
store.repair_torn_tail()
os._exit(0)
"""


def run_repair_child(root: Path, point: str, *, detach_repair: bool = False) -> int:
    child = subprocess.Popen(  # noqa: S603 - runs this interpreter with a fixed test script
        [
            sys.executable,
            "-I",
            "-c",
            REPAIR_CHILD,
            str(root),
            str(REPO),
            str(root.parent / "checkpoints.v1.jsonl"),
            point,
            "1" if detach_repair else "0",
        ],
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return child.wait(timeout=180)


def markers(root: Path) -> list[str]:
    return sorted(
        name for name in os.listdir(root / "ledger") if name.startswith("repair-pending-")
    )


def assert_repaired_exactly_once(root: Path, damaged: bytes) -> None:
    torn = damaged[damaged.rfind(b"\n") + 1 :]
    with open_store(root) as store:
        state = store.snapshot()
        repairs = [
            entry for entry in state.entries if entry.event_type is LedgerEvent.LEDGER_TAIL_REPAIRED
        ]
        assert len(repairs) == 1
        name = str(repairs[0].fields["repair_evidence_name"])
        assert (root / "ledger" / "repair" / name).read_bytes() == torn
        assert repairs[0].fields["torn_byte_offset"] == len(damaged) - len(torn)
        assert markers(root) == []
        assert ledger_path(root).read_bytes().startswith(damaged[: len(damaged) - len(torn)])
        store.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)


def test_repair_directory_replaced_after_truncation_cannot_hide_the_repair(root: Path) -> None:
    damaged = torn_store(root)
    torn = damaged[damaged.rfind(b"\n") + 1 :]
    assert run_repair_child(root, "repair.truncated", detach_repair=True) == 70
    assert ledger_path(root).read_bytes() == damaged[: len(damaged) - len(torn)]
    assert os.listdir(root / "ledger" / "repair") == []
    (marker,) = markers(root)
    assert (root / "ledger" / marker).read_bytes() == torn
    with open_store(root) as fresh:
        with pytest.raises(PendingRepairEvidenceError, match="repair is pending"):
            fresh.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        with pytest.raises(PendingRepairEvidenceError, match="repair is pending"):
            fresh.snapshot()
        with pytest.raises(PendingRepairEvidenceError, match="repair is pending"):
            fresh.recover()
        report = fresh.repair_torn_tail()
        assert report.truncated_bytes == 0
        assert len(report.evidence_restored) == 1
        assert report.events_appended == report.evidence_restored
        assert report.markers_retired == report.evidence_restored
    detached = root / "ledger" / "repair-detached" / report.evidence_restored[0]
    assert detached.read_bytes() == torn
    assert_repaired_exactly_once(root, damaged)


@pytest.mark.parametrize(
    ("point", "refusal"),
    [
        ("repair.before_truncate", TornLedgerError),
        ("repair.truncated", PendingRepairEvidenceError),
        ("repair.event_appended", PendingRepairEvidenceError),
        ("repair.marker_unlinked", None),
    ],
)
def test_repair_crashes_at_each_pending_state_boundary_resume_exactly(
    root: Path, point: str, refusal: type[Exception] | None
) -> None:
    damaged = torn_store(root)
    assert run_repair_child(root, point) == 70
    with open_store(root) as fresh:
        if refusal is not None:
            with pytest.raises(refusal):
                fresh.reserve_run("velocity_baseline", RunClass.DEVELOPMENT)
        fresh.repair_torn_tail()
        assert fresh.repair_torn_tail() == experiments.RepairReport(None, 0, ())
    assert_repaired_exactly_once(root, damaged)


def test_markers_are_created_before_truncation_and_bind_the_store(root: Path) -> None:
    torn_store(root)
    seen: list[list[str]] = []

    def hook(point: str) -> None:
        if point in ("repair.evidence_written", "repair.before_truncate"):
            seen.append(markers(root))

    with open_store(root, fault_hook=hook) as store:
        store.repair_torn_tail()
    store_id = json.loads((root / "store.v1.json").read_text(encoding="ascii"))["store_id"]
    assert seen[0] == []
    (marker,) = seen[1]
    assert marker.startswith(f"repair-pending-{store_id}-torn-")
    assert markers(root) == []


def test_the_store_identity_record_is_permanent_and_bound_by_genesis(root: Path) -> None:
    with open_store(root) as store:
        genesis = store.snapshot().entries[0]
    record = json.loads((root / "store.v1.json").read_text(encoding="ascii"))
    assert genesis.fields["store_id"] == record["store_id"]
    assert mode(root / "store.v1.json") == 0o400
    with open_store(root) as again:
        assert again.snapshot().entries[0] == genesis
    (root / "store.v1.json").rename(root.parent / "store.v1.json")
    with pytest.raises(ExperimentIntegrityError, match="identity record is missing"):
        open_store(root)


# ----- Step 10: installed-environment identity -----


def test_an_evidence_candidate_start_is_refused_when_verification_fails(
    root: Path, environment: FakeEnvironment
) -> None:
    environment.capture = None
    with open_store(root) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.EVIDENCE_CANDIDATE)
        with pytest.raises(RunStateError, match="reproducibility verification failed"):
            handle.start(make_spec())
        run = store.snapshot().runs[handle.run_id]
        assert run.state is RunState.RESERVED
        directory = root / "runs" / handle.run_id
        assert not (directory / "run_spec.json").exists()
        assert not (directory / "environment.json").exists()
        environment.capture = synthetic_capture()
        handle.start(make_spec())
        assert store.snapshot().runs[handle.run_id].eligible_at_start is True
    assert environment.calls == [True, True]


@pytest.mark.parametrize("run_class", [RunClass.EXPLORATORY, RunClass.DEVELOPMENT])
def test_other_runs_never_require_verification_and_record_no_unverifiable_fingerprint(
    root: Path, environment: FakeEnvironment, run_class: RunClass
) -> None:
    with open_store(root) as store:
        fingerprinted = store.reserve_run("velocity_baseline", run_class)
        fingerprinted.start(make_spec())
        environment.capture = None
        blind = store.reserve_run("velocity_baseline", run_class)
        blind.start(make_spec())
        blind.complete()
        state = store.snapshot()
        identity = state.runs[blind.run_id].identity
        assert identity is not None
        assert identity.installed_environment_sha256 is None
        assert not (root / "runs" / blind.run_id / "environment.json").exists()
        store.verify_run(blind.run_id)
        first = state.runs[fingerprinted.run_id].identity
        assert first is not None
        assert first.installed_environment_sha256 == synthetic_capture().sha256
        assert not state.runs[fingerprinted.run_id].eligible_at_start
    # A run started without a fingerprint has nothing to re-check at completion.
    assert environment.calls == [False, False]


def test_an_environment_change_during_the_run_fails_it(
    root: Path, environment: FakeEnvironment
) -> None:
    with open_store(root) as store:
        handle = started(store)
        environment.capture = synthetic_capture("2.0")
        with pytest.raises(RunStateError, match="installed environment changed"):
            handle.complete()
        failed = store.snapshot().runs[handle.run_id]
        assert failed.state is RunState.FAILED
        last = store.snapshot().entries[-1]
        assert last.fields["failure_code"] == "environment_changed"
        assert last.version == 2
        assert not store.eligibility_as_of(handle.run_id)
        unverifiable = started(store)
        environment.capture = None
        with pytest.raises(RunStateError, match="installed environment changed"):
            unverifiable.complete()


def test_a_code_change_is_still_reported_separately(
    root: Path, monkeypatch: pytest.MonkeyPatch, environment: FakeEnvironment
) -> None:
    with open_store(root) as store:
        handle = started(store)
        environment.capture = synthetic_capture("2.0")
        monkeypatch.setattr(
            experiments, "collect_git_identity", lambda _repo: GitIdentity("b" * 40, False, None)
        )
        with pytest.raises(RunStateError, match="code identity changed"):
            handle.complete()
        assert store.snapshot().entries[-1].fields["failure_code"] == "code_identity_changed"


def test_environment_json_must_match_the_recorded_fingerprint(root: Path) -> None:
    with open_store(root) as store:
        handle = completed(store)
        store.verify_run(handle.run_id)
        directory = root / "runs" / handle.run_id
        target = directory / "environment.json"
        os.chmod(directory, 0o700)
        os.chmod(target, 0o600)
        original = target.read_bytes()
        target.write_bytes(synthetic_capture("9.9").document)
        with pytest.raises(ExperimentIntegrityError, match="does not match its recorded hash"):
            store.verify_run(handle.run_id)
        target.unlink()
        with pytest.raises(ExperimentIntegrityError, match=r"environment\.json is missing"):
            store.verify_run(handle.run_id)
        target.write_bytes(original)
        store.verify_run(handle.run_id)


def test_a_stray_environment_json_without_a_fingerprint_is_an_integrity_error(
    root: Path, environment: FakeEnvironment
) -> None:
    environment.capture = None
    with open_store(root) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.EXPLORATORY)
        handle.start(make_spec())
        handle.complete()
        directory = root / "runs" / handle.run_id
        os.chmod(directory, 0o700)
        (directory / "environment.json").write_bytes(synthetic_capture().document)
        with pytest.raises(ExperimentIntegrityError, match="recorded no fingerprint"):
            store.verify_run(handle.run_id)


def test_a_retried_start_must_see_the_same_environment(
    root: Path, environment: FakeEnvironment
) -> None:
    with open_store(root) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.EVIDENCE_CANDIDATE)
        directory = root / "runs" / handle.run_id
        (directory / "environment.json").write_bytes(synthetic_capture("0.1").document)
        with pytest.raises(RunStateError, match=r"existing environment\.json does not match"):
            handle.start(make_spec())
        assert store.snapshot().runs[handle.run_id].state is RunState.RESERVED
        (directory / "environment.json").unlink()
        handle.start(make_spec())


def test_a_retry_that_cannot_capture_beside_an_earlier_capture_is_refused(
    root: Path, environment: FakeEnvironment
) -> None:
    with open_store(root) as store:
        handle = store.reserve_run("velocity_baseline", RunClass.EXPLORATORY)
        directory = root / "runs" / handle.run_id
        (directory / "environment.json").write_bytes(synthetic_capture().document)
        environment.capture = None
        with pytest.raises(RunStateError, match="can no longer be captured"):
            handle.start(make_spec())
        assert not (directory / "run_spec.json").exists()


# ----- Step 11 M-4: verification is a required precondition, not a stored claim -----

REAL_CAPTURE_ENVIRONMENT = experiments.capture_environment
REAL_COLLECT_GIT_IDENTITY = experiments.collect_git_identity


def test_m4_a_capture_that_skips_verification_cannot_produce_an_eligible_run(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the store's real capture path, a failing ``reproducibility.verify`` refuses an
    evidence start even though a plain capture would succeed: no fingerprint, and so no
    eligibility, can be obtained by bypassing verification. No ``verified`` field exists
    because the same process that would write it is the one being checked."""
    from pmv import reproducibility

    monkeypatch.setattr(experiments, "capture_environment", REAL_CAPTURE_ENVIRONMENT)

    def refuse(_root: Path) -> EnvironmentCapture:
        raise ReproducibilityError("synthetic conformance failure")

    monkeypatch.setattr(reproducibility, "verify", refuse)
    monkeypatch.setattr(reproducibility, "capture", synthetic_capture)
    with open_store(root) as store:
        candidate = store.reserve_run("velocity_baseline", RunClass.EVIDENCE_CANDIDATE)
        with pytest.raises(RunStateError, match="reproducibility verification failed"):
            candidate.start(make_spec())
        assert store.snapshot().runs[candidate.run_id].state is RunState.RESERVED
        exploratory = store.reserve_run("velocity_baseline", RunClass.EXPLORATORY)
        exploratory.start(make_spec())
        run = store.snapshot().runs[exploratory.run_id]
        assert run.identity is not None
        assert run.identity.installed_environment_sha256 == synthetic_capture().sha256
        assert not run.eligible_at_start
        assert not any(item.eligible_at_start for item in store.snapshot().runs.values())
    assert not hasattr(run.identity, "verified")


# ----- Step 11 F-20: replace refs, grafts, and shallow clones make identity unknown -----


def _git(repo: Path, *arguments: str) -> str:
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
        text=True,
    ).stdout.strip()


def test_f20_a_replace_ref_cannot_spoof_experiment_code_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(experiments, "collect_git_identity", REAL_COLLECT_GIT_IDENTITY)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "f.py").write_text("innocent = True\n", encoding="ascii")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "A")
    innocent = _git(repo, "rev-parse", "HEAD")
    (repo / "f.py").write_text("innocent = False\n", encoding="ascii")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "B")
    malicious = _git(repo, "rev-parse", "HEAD")
    assert experiments.collect_git_identity(repo) == GitIdentity(malicious, False, None)
    # The audit's spoof: record A while B's content runs.
    _git(repo, "reset", "-q", "--soft", innocent)
    _git(repo, "replace", innocent, malicious)
    assert experiments.collect_git_identity(repo) == experiments.UNKNOWN_GIT
    _git(repo, "replace", "-d", innocent)
    identity = experiments.collect_git_identity(repo)
    assert identity.commit == innocent
    assert identity.dirty is True
    grafts = repo / ".git" / "info" / "grafts"
    grafts.parent.mkdir(exist_ok=True)
    grafts.write_text(innocent + "\n", encoding="ascii")
    assert experiments.collect_git_identity(repo) == experiments.UNKNOWN_GIT
