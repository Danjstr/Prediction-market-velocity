"""G-6 failure injection: crash and restart, retries, duplicates, conflicts, interruptions.

Crashes are injected at every durable boundary of the pipeline, both in-process (an
exception that unwinds everything, as a crash would leave the files) and as a real
``SIGKILL`` of a subprocess. A later run must resume from the journal and either complete
with exactly the received bytes stored, or stop without replacing anything.
"""

import errno
import fcntl
import json
import os
import signal
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from pmv.acquisition import isolation
from pmv.acquisition import synthetic as syn
from pmv.acquisition.confinement import WorkerLimits
from pmv.acquisition.fetch import FetchPolicy
from pmv.acquisition.pipeline import (
    AcquisitionPipeline,
    BackupEvidence,
    DirectoryBackupTarget,
    Outcome,
    PipelineError,
    PipelineInputs,
    PipelineSettings,
    RunMode,
)
from pmv.acquisition.receipts import ReceiptEvent, ReceiptJournal, ReceiptJournalError
from pmv.acquisition.state import FileState

SCHEMA = syn.csv_schema(("row", "integer"), ("value", "decimal"))
CSV = b"row,value\n0,1.5\n1,-2.25\n"
URL = syn.PREFIX + "a.csv"
POINTS = (
    "after_approved",
    "after_fetch_linked",
    "after_received",
    "after_integrity",
    "after_parser",
    "after_backup",
    "after_store_link",
    "after_stored",
    "before_complete",
    "after_record",
)


class SimulatedCrashError(BaseException):
    """Unwinds like a crash: no cleanup code in the pipeline catches a BaseException."""


@dataclass
class Env:
    root: Path
    store: Path

    def backup(self) -> DirectoryBackupTarget:
        return DirectoryBackupTarget(
            "synthetic_backup_policy", self.root / "backup", self.root / "restore"
        )

    def pipeline(self, transport: syn.SyntheticTransport, **kwargs: Any) -> AcquisitionPipeline:
        return AcquisitionPipeline(
            PipelineSettings(
                self.store,
                RunMode.SYNTHETIC,
                worker_limits=WorkerLimits(wall_clock_seconds=60.0),
                fetch_policy=FetchPolicy(free_space_margin_bytes=0),
            ),
            transport=transport,
            backup=kwargs.pop("backup", self.backup()),
            repository=syn.StaticRepository(),
            **kwargs,
        )

    @property
    def base(self) -> Path:
        return self.store / "acquisitions" / "v1"

    def stored(self, name: str = "a.csv") -> Path:
        return self.base / "store" / "synthetic_source" / "synthetic_acq_1" / name

    def entries(self) -> list[Any]:
        journal = ReceiptJournal(self.base / "journal.jsonl")
        try:
            return journal.entries
        finally:
            journal.close()


@pytest.fixture
def env(tmp_path: Path) -> Env:
    for name in ("store", "backup", "restore"):
        (tmp_path / name).mkdir(mode=0o700)
    return Env(tmp_path, tmp_path / "store")


def _inputs(**kwargs: Any) -> PipelineInputs:
    return syn.inputs([syn.planned_file("a.csv", schema=SCHEMA)], **kwargs)


def _transport() -> syn.SyntheticTransport:
    return syn.SyntheticTransport({URL: syn.ok(CSV)})


def _crash_at(point: str) -> Any:
    def hook(reached: str) -> None:
        if reached == point:
            raise SimulatedCrashError(point)

    return hook


@pytest.mark.parametrize("point", POINTS)
def test_crash_at_every_boundary_then_resume_completes(env: Env, point: str) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at(point)).run(_inputs())
    report = env.pipeline(transport).run(_inputs())
    assert report.outcome is Outcome.COMPLETED
    assert env.stored().read_bytes() == CSV
    events = [entry.event for entry in env.entries()]
    assert events.count(ReceiptEvent.STORED) == 1
    assert events.count(ReceiptEvent.COMPLETED) == 1
    assert env.pipeline(transport).run(_inputs()).outcome is Outcome.ALREADY_COMPLETED


def test_unjournaled_receipt_is_set_aside_not_deleted(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_fetch_linked")).run(_inputs())
    env.pipeline(transport).run(_inputs())
    orphans = list((env.base / "orphans" / "synthetic_acq_1").iterdir())
    assert [path.read_bytes() for path in orphans] == [CSV]
    discarded = [entry for entry in env.entries() if entry.event is ReceiptEvent.DISCARDED]
    assert len(discarded) == 1
    assert discarded[0].sha256 == syn.sha256(CSV)


def test_interrupted_fetch_is_recorded_and_counts_as_an_attempt(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_approved")).run(_inputs())
    env.pipeline(transport).run(_inputs())
    failed = [entry for entry in env.entries() if entry.event is ReceiptEvent.FETCH_FAILED]
    assert [entry.detail["code"] for entry in failed] == ["interrupted"]


def test_store_link_without_journal_is_recovered_only_when_bytes_match(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_store_link")).run(_inputs())
    env.pipeline(transport).run(_inputs())
    stored = [entry for entry in env.entries() if entry.event is ReceiptEvent.STORED]
    assert stored[0].detail["recovered"] is True


def test_conflicting_bytes_in_the_store_are_never_replaced(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_backup")).run(_inputs())
    target = env.stored()
    for directory in (env.base / "store", target.parent.parent, target.parent):
        directory.mkdir(mode=0o700, exist_ok=True)
    target.write_bytes(b"row,value\n9,9\n")
    with pytest.raises(PipelineError, match="store_conflict_never_replaced"):
        env.pipeline(transport).run(_inputs())
    assert target.read_bytes() == b"row,value\n9,9\n"
    quarantined = env.base / "work" / "synthetic_acq_1" / "quarantine" / "a.csv"
    assert quarantined.read_bytes() == CSV


def test_conflicting_record_is_never_replaced(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("before_complete")).run(_inputs())
    record = env.stored("acquisition.json")
    record.write_bytes(b"{}\n")
    with pytest.raises(PipelineError, match="record_conflict_never_replaced"):
        env.pipeline(transport).run(_inputs())
    assert record.read_bytes() == b"{}\n"


def test_bytes_changed_in_quarantine_after_receipt_are_rejected(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_received")).run(_inputs())
    quarantined = env.base / "work" / "synthetic_acq_1" / "quarantine" / "a.csv"
    quarantined.chmod(0o600)
    quarantined.write_bytes(b"row,value\n0,9.9\n1,-2.25\n")
    report = env.pipeline(transport).run(_inputs())
    assert report.outcome is Outcome.REJECTED
    assert report.files[0].code == "changed_after_receipt"
    assert not env.stored().exists()


def test_same_acquisition_id_with_a_different_bundle_is_refused(env: Env) -> None:
    transport = _transport()
    env.pipeline(transport).run(_inputs())
    changed = _inputs(licence_overrides={"redistribution": "yes"})
    report = env.pipeline(transport).run(changed)
    assert report.outcome is Outcome.REFUSED
    assert report.failures == (
        "G-6: the acquisition's journal conflicts with this plan or binding",
    )


def test_duplicate_artifacts_in_separate_acquisitions_do_not_conflict(env: Env) -> None:
    transport = _transport()
    first = env.pipeline(transport).run(_inputs())
    second = env.pipeline(transport).run(_inputs(acquisition_id="synthetic_acq_2"))
    assert first.outcome is second.outcome is Outcome.COMPLETED
    assert first.files[0].sha256 == second.files[0].sha256


def test_a_concurrent_run_is_refused(env: Env) -> None:
    transport = _transport()
    env.base.mkdir(parents=True, mode=0o700)
    (env.store / "acquisitions").chmod(0o700)
    lock = os.open(env.base / ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with pytest.raises(PipelineError, match="another_run_holds_the_lock"):
            env.pipeline(transport).run(_inputs())
    finally:
        os.close(lock)
    assert transport.requests == []


class FailingBackup:
    synthetic = True
    policy_id = "synthetic_backup_policy"

    def backup_and_verify(self, acquisition_id: str, items: Any) -> BackupEvidence:
        return BackupEvidence(self.policy_id, False, {"mismatched": ["a.csv"]})


def test_backup_failure_stops_without_rejecting_and_a_retry_completes(env: Env) -> None:
    transport = _transport()
    with pytest.raises(PipelineError, match="backup_not_verified"):
        env.pipeline(transport, backup=FailingBackup()).run(_inputs())
    last = env.entries()[-1]
    assert last.event is ReceiptEvent.STAGE_FAILED
    assert last.detail == {"stage": "backup", "code": "backup_not_verified"}
    assert env.pipeline(transport).run(_inputs()).outcome is Outcome.COMPLETED


def test_disk_full_while_storing_names_nothing_and_a_retry_completes(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_backup")).run(_inputs())

    def full(_fd: int, _data: bytes) -> int:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr("pmv.acquisition.pipeline.os.write", full)
    with pytest.raises(PipelineError, match="store_disk_full"):
        env.pipeline(transport).run(_inputs())
    assert not env.stored().exists()
    monkeypatch.undo()
    assert env.pipeline(transport).run(_inputs()).outcome is Outcome.COMPLETED


def test_environmental_isolation_failure_stops_without_rejecting(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _transport()

    def broken(*_args: object, **_kwargs: object) -> object:
        raise isolation.IsolationError(isolation.IsolationFailure.IDENTITY_MISMATCH)

    monkeypatch.setattr(isolation, "verify_file", broken)
    with pytest.raises(PipelineError, match="isolation_identity_mismatch"):
        env.pipeline(transport).run(_inputs())
    entries = env.entries()
    assert entries[-1].event is ReceiptEvent.STAGE_FAILED
    assert entries[-2].event is ReceiptEvent.INTEGRITY_VERIFIED  # state unchanged
    monkeypatch.undo()
    assert env.pipeline(transport).run(_inputs()).outcome is Outcome.COMPLETED


def test_unexpected_quarantine_entry_stops_the_run(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_received")).run(_inputs())
    (env.base / "work" / "synthetic_acq_1" / "quarantine" / "intruder.csv").write_bytes(b"x")
    with pytest.raises(PipelineError, match="unexpected_quarantine_entry"):
        env.pipeline(transport).run(_inputs())


def test_tampered_store_after_completion_is_detected(env: Env) -> None:
    transport = _transport()
    env.pipeline(transport).run(_inputs())
    stored = env.stored()
    stored.parent.chmod(0o700)
    stored.chmod(0o600)
    stored.write_bytes(b"row,value\n0,0\n1,0\n")
    with pytest.raises(PipelineError, match="stored_copy_missing_or_changed"):
        env.pipeline(transport).run(_inputs())


def test_tampered_journal_fails_closed(env: Env) -> None:
    transport = _transport()
    env.pipeline(transport).run(_inputs())
    path = env.base / "journal.jsonl"
    path.write_bytes(path.read_bytes().replace(b'"attempt":1', b'"attempt":2', 1))
    with pytest.raises(ReceiptJournalError):
        env.pipeline(transport).run(_inputs())


def test_scratch_plaintext_from_a_crash_is_removed(env: Env) -> None:
    transport = _transport()
    with pytest.raises(SimulatedCrashError):
        env.pipeline(transport, faults=_crash_at("after_integrity")).run(_inputs())
    scratch = env.base / "work" / "synthetic_acq_1" / "scratch"
    scratch.mkdir(mode=0o700)
    (scratch / "leftover.csv").write_bytes(b"derived")
    env.pipeline(transport).run(_inputs())
    assert not scratch.exists()


# --- real process kills -------------------------------------------------------------------

KILLER = textwrap.dedent(
    """
    import os, signal, sys
    from pathlib import Path
    from pmv.acquisition import synthetic as syn
    from pmv.acquisition.confinement import WorkerLimits
    from pmv.acquisition.fetch import FetchPolicy
    from pmv.acquisition.pipeline import (
        AcquisitionPipeline, DirectoryBackupTarget, PipelineSettings, RunMode)

    root, point = Path(sys.argv[1]), sys.argv[2]
    schema = syn.csv_schema(("row", "integer"), ("value", "decimal"))
    data = b"row,value\\n0,1.5\\n1,-2.25\\n"

    def hook(reached):
        if reached == point:
            os.kill(os.getpid(), signal.SIGKILL)

    pipeline = AcquisitionPipeline(
        PipelineSettings(root / "store", RunMode.SYNTHETIC,
                         worker_limits=WorkerLimits(wall_clock_seconds=60.0),
                         fetch_policy=FetchPolicy(free_space_margin_bytes=0)),
        transport=syn.SyntheticTransport({syn.PREFIX + "a.csv": syn.ok(data)}),
        backup=DirectoryBackupTarget("synthetic_backup_policy", root / "backup", root / "restore"),
        repository=syn.StaticRepository(),
        faults=hook,
    )
    pipeline.run(syn.inputs([syn.planned_file("a.csv", schema=schema)]))
    """
)


@pytest.mark.parametrize("point", ["after_fetch_linked", "after_store_link", "after_stored"])
def test_sigkill_then_resume_completes(env: Env, tmp_path: Path, point: str) -> None:
    script = tmp_path / "killer.py"
    script.write_text(KILLER, encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed interpreter and synthetic script
        [sys.executable, "-I", str(script), str(env.root), point],
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == -signal.SIGKILL
    report = env.pipeline(_transport()).run(_inputs())
    assert report.outcome is Outcome.COMPLETED
    assert env.stored().read_bytes() == CSV
    record = json.loads(env.stored("acquisition.json").read_bytes())
    assert record["files"][0]["sha256"] == syn.sha256(CSV)
    states = {entry.event for entry in env.entries()}
    assert ReceiptEvent.COMPLETED in states
    assert FileState.STORED.value in {event.value for event in states}
