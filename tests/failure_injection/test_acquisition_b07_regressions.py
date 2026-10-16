"""B07 regressions: B06 intake cleanup (RT-B6-26 c), Git facts, and Red-Team round 1."""

import errno
import io
import json
import os
import resource
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from pmv.acquisition import pipeline as pipeline_module
from pmv.acquisition import synthetic as syn
from pmv.acquisition import worker_protocol as wp
from pmv.acquisition.confinement import WorkerLimits
from pmv.acquisition.fetch import Fetcher, FetchError, FetchFailure, FetchPolicy, FetchRequest
from pmv.acquisition.formats import FileFormat
from pmv.acquisition.hosts import UrlAllowlist
from pmv.acquisition.isolation import (
    IsolationError,
    IsolationFailure,
    WorkerRefusedError,
    expected_identity,
    run_worker,
    verify_isolation,
)
from pmv.acquisition.pipeline import GitRepository
from pmv.acquisition.quarantine import Quarantine
from pmv.acquisition.readers import RecordSchema, VerifyLimits, verify_stream
from pmv.acquisition.receipts import (
    ReceiptEvent,
    ReceiptJournal,
    ReceiptJournalError,
    new_session_id,
    recover_torn_tail,
)
from pmv.integrity import canonical_json


def test_failed_intake_leaves_no_partial_file_in_quarantine(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    quarantine_dir.mkdir()
    ReceiptJournal.create(tmp_path / "receipts.jsonl")
    quarantine = Quarantine(quarantine_dir, journal=ReceiptJournal(tmp_path / "receipts.jsonl"))

    def interrupted() -> Iterator[bytes]:
        yield b"a,b\n"
        raise ConnectionResetError("synthetic interruption")

    with pytest.raises(ConnectionResetError):
        quarantine.receive("a.csv", interrupted())
    assert list(quarantine_dir.iterdir()) == []
    # The next intake session is not blocked by a leftover file.
    Quarantine(quarantine_dir, journal=ReceiptJournal(tmp_path / "receipts.jsonl"))


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed git commands on a temporary repository
        [  # noqa: S607 - git from PATH, as GitRepository uses it
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *arguments,
        ],
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


def test_git_repository_facts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("a\n")
    (root / "src").mkdir()
    (root / "src" / "x.py").write_text("x = 1\n")
    _git(root, "add", "docs/a.md", "src/x.py")
    _git(root, "commit", "-q", "-m", "first")
    first = _git(root, "rev-parse", "HEAD")
    repository = GitRepository(root)
    assert repository.head() == first
    assert repository.tree_clean()
    assert repository.committed_unchanged("docs/a.md")
    assert not repository.committed_unchanged("docs/missing.md")
    assert repository.is_ancestor(first)
    assert not repository.is_ancestor("f" * 40)
    (root / "src" / "x.py").write_text("x = 2\n")
    assert not repository.tree_clean()
    _git(root, "commit", "-q", "-am", "second")
    assert not repository.unchanged_since(first, "src")
    assert repository.unchanged_since(first, "docs")
    (root / "docs" / "a.md").write_text("changed\n")
    assert not repository.committed_unchanged("docs/a.md")
    (root / "untracked.txt").write_text("u\n")
    assert not repository.tree_clean()


# --- B07 Red-Team round 1 regressions (RT-B7-01 .. RT-B7-09) -------------------------------

ATTACKER = """
import ctypes, errno, json, os, resource, signal, sys
from pmv.acquisition import confinement, parse_worker
parse_worker._warm_up()
confinement.install_filter()
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
parent = os.getppid()
results = {}
class Rlimit(ctypes.Structure):
    _fields_ = [("cur", ctypes.c_ulong), ("max", ctypes.c_ulong)]
unlimited = Rlimit(resource.RLIM_INFINITY, resource.RLIM_INFINITY)
for name, args in {
    "prlimit_parent": (302, parent, resource.RLIMIT_CORE, ctypes.addressof(unlimited), 0),
    "kill_parent": (62, parent, signal.SIGSTOP),
    "setpriority_parent": (141, 0, parent, 19),
    "fcntl_setown": (72, 1, 8, parent),
    "fcntl_setsig": (72, 1, 10, signal.SIGUSR1),
    "fcntl_async": (72, 1, 4, 0o20000),
    "ioctl_tiocsti": (16, 0, 0x5412, 0),
}.items():
    ctypes.set_errno(0)
    status = libc.syscall(*(ctypes.c_long(a) for a in args))
    results[name] = status == -1 and ctypes.get_errno() == errno.EPERM
os.write(1, json.dumps(results).encode())
"""


def test_a_confined_worker_cannot_touch_its_parent(tmp_path: Path) -> None:
    script = tmp_path / "attacker.py"
    script.write_text(ATTACKER, encoding="utf-8")
    before = resource.getrlimit(resource.RLIMIT_CORE)
    result = subprocess.run(  # noqa: S603 - fixed interpreter and synthetic script
        [sys.executable, "-I", str(script)],
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-500:]
    denied = json.loads(result.stdout)
    assert denied
    assert all(denied.values()), denied
    assert resource.getrlimit(resource.RLIMIT_CORE) == before


def test_run_worker_hardens_the_parent() -> None:
    verify_isolation(WorkerLimits(wall_clock_seconds=60.0))
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)


def test_identity_is_checked_before_any_frame_is_acted_on(tmp_path: Path) -> None:
    script = tmp_path / "fake.py"
    script.write_text(
        "import os\n"
        "from pmv.acquisition import worker_protocol as wp\n"
        "from pmv.integrity import canonical_json\n"
        "hello = {'protocol': wp.PROTOCOL, 'version': 1, 'confined': True, 'identity': {}}\n"
        "frame = wp.frame(wp.FILE, canonical_json({'name': 'a.csv', 'size': 1}))\n"
        "os.write(1, wp.MAGIC + wp.frame(wp.HELLO, canonical_json(hello)) + frame)\n",
        encoding="utf-8",
    )
    seen: list[bytes] = []
    with pytest.raises(IsolationError) as caught:
        run_worker(
            wp.Operation.PROBE,
            {},
            input_fd=None,
            limits=WorkerLimits(wall_clock_seconds=30.0),
            on_frame=lambda kind, _payload: seen.append(kind),
            command=[sys.executable, "-I", str(script)],
        )
    assert caught.value.failure is IsolationFailure.IDENTITY_MISMATCH
    assert seen == []


def test_worker_identity_pins_interpreter_and_launch() -> None:
    identity = expected_identity()
    assert len(str(identity["executable_sha256"])) == 64
    assert "-S" in str(identity["launch"])
    assert "pmv.integrity" in identity["modules"]  # type: ignore[operator]


def test_short_line_input_is_linear(tmp_path: Path) -> None:
    schema = RecordSchema.from_document(FileFormat.TEXT, None)
    data = b"a\n" * (1024 * 1024)  # 2 MiB of 2-byte lines; quadratic code took ~99 s
    start = time.process_time()
    verify_stream(io.BytesIO(data), schema, VerifyLimits())
    assert time.process_time() - start < 30


def test_fetch_unlinks_its_name_when_a_post_link_step_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "q"
    directory.mkdir()
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = os.fsync
    calls = {"n": 0}

    def failing_dir_fsync(target: int) -> None:
        calls["n"] += 1
        if calls["n"] == 2:  # the file fsync first, then the directory fsync after the link
            raise OSError(errno.EIO, "synthetic I/O error")
        real_fsync(target)

    monkeypatch.setattr("pmv.acquisition.fetch.os.fsync", failing_dir_fsync)
    allow = UrlAllowlist.build([syn.PREFIX], {syn.PREFIX: syn.DECISION})
    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": syn.ok(b"a\n1\n")})
    try:
        with pytest.raises(FetchError) as caught:
            Fetcher(allow, transport, policy=FetchPolicy(free_space_margin_bytes=0)).fetch(
                FetchRequest(syn.PREFIX + "a.csv", "a.csv", 1024), fd
            )
    finally:
        monkeypatch.undo()
        os.close(fd)
    assert caught.value.failure is FetchFailure.WRITE_FAILED
    assert list(directory.iterdir()) == []


def test_move_aside_makes_the_new_name_durable_before_unlinking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir, target_dir = tmp_path / "a", tmp_path / "b"
    source_dir.mkdir()
    target_dir.mkdir()
    (source_dir / "f").write_bytes(b"x")
    events: list[str] = []
    real_fsync_dir, real_unlink = pipeline_module._fsync_dir, os.unlink

    def fsync_dir(path: Path) -> None:
        events.append(f"fsync {path.name}")
        real_fsync_dir(path)

    def unlink(path: Path) -> None:
        events.append("unlink")
        real_unlink(path)

    monkeypatch.setattr(pipeline_module, "_fsync_dir", fsync_dir)
    monkeypatch.setattr("pmv.acquisition.pipeline.os.unlink", unlink)
    pipeline_module._move_aside(source_dir / "f", target_dir, "g")
    monkeypatch.undo()
    assert events == ["fsync b", "unlink", "fsync a"]
    assert (target_dir / "g").read_bytes() == b"x"


def test_synthetic_root_through_a_symlink_into_the_protected_area_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected = tmp_path / "protected"
    (protected / "inner").mkdir(parents=True, mode=0o700)
    link = tmp_path / "innocent"
    link.symlink_to(protected / "inner")
    monkeypatch.setattr(pipeline_module, "PROTECTED_ROOT", protected)
    assert pipeline_module._inside(link, protected)
    assert not pipeline_module._inside(tmp_path / "elsewhere", protected)


def test_real_mode_ignores_caller_supplied_transport_and_repository(tmp_path: Path) -> None:
    class DeclaredProduction(syn.SyntheticTransport):
        pass

    transport = DeclaredProduction({})
    transport.synthetic = False
    store = tmp_path / "store"
    store.mkdir(mode=0o700)
    pipeline = pipeline_module.AcquisitionPipeline(
        pipeline_module.PipelineSettings(store, pipeline_module.RunMode.REAL),
        transport=transport,
        backup=pipeline_module.DirectoryBackupTarget("synthetic_p", tmp_path / "b", tmp_path / "r"),
        repository=syn.StaticRepository("e" * 40, True, True, True, True),
    )
    item = syn.planned_file("a.csv", schema=syn.csv_schema(("a", "integer")))
    report = pipeline.run(syn.inputs([item]))
    assert report.outcome is pipeline_module.Outcome.REFUSED
    assert "G-4: no reviewed production transport" in report.failures
    # The all-true injected repository was ignored: the placeholder records are not committed.
    assert "records: a cited decision or review file is not committed unchanged" in report.failures
    assert transport.requests == []


def test_recover_torn_tail_requires_a_committed_attestation(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    ReceiptJournal.create(path)
    path.write_bytes(b'{"torn')
    with pytest.raises(ReceiptJournalError, match="committed"):
        recover_torn_tail(path, syn.DECISION, committed=lambda _path: False)
    assert path.read_bytes() == b'{"torn'


def test_interrupted_torn_tail_recovery_completes_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "journal.jsonl"
    ReceiptJournal.create(path)
    journal = ReceiptJournal(path)
    journal.append(ReceiptEvent.RECEIVED, new_session_id(), "a.csv", 1, "c" * 64)
    journal.close()
    path.write_bytes(path.read_bytes() + b'{"torn')

    def crash(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic crash after truncation")

    monkeypatch.setattr(ReceiptJournal, "append_bound", crash)
    with pytest.raises(RuntimeError):
        recover_torn_tail(path, syn.DECISION, committed=lambda _path: True)
    monkeypatch.undo()
    assert path.read_bytes().endswith(b"\n")  # truncated, entry missing
    entry = recover_torn_tail(path, syn.DECISION, committed=lambda _path: True)
    assert entry.event is ReceiptEvent.TAIL_RECOVERED
    assert (tmp_path / str(entry.name)).read_bytes() == b'{"torn'
    with pytest.raises(ReceiptJournalError, match="no torn tail"):
        recover_torn_tail(path, syn.DECISION, committed=lambda _path: True)


def test_worker_timeout_in_the_pipeline_stops_without_rejecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("store", "backup", "restore"):
        (tmp_path / name).mkdir(mode=0o700)

    def timed_out(*_args: object, **_kwargs: object) -> object:
        raise IsolationError(IsolationFailure.TIMEOUT)

    data = b"a\n1\n"
    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": syn.ok(data)})
    pipeline = pipeline_module.AcquisitionPipeline(
        pipeline_module.PipelineSettings(
            tmp_path / "store",
            pipeline_module.RunMode.SYNTHETIC,
            worker_limits=WorkerLimits(wall_clock_seconds=60.0),
            fetch_policy=FetchPolicy(free_space_margin_bytes=0),
        ),
        transport=transport,
        backup=pipeline_module.DirectoryBackupTarget(
            "synthetic_backup_policy", tmp_path / "backup", tmp_path / "restore"
        ),
        repository=syn.StaticRepository(),
    )
    inputs = syn.inputs([syn.planned_file("a.csv", schema=syn.csv_schema(("a", "integer")))])
    monkeypatch.setattr("pmv.acquisition.isolation.verify_file", timed_out)
    with pytest.raises(pipeline_module.PipelineError, match="isolation_timeout"):
        pipeline.run(inputs)
    monkeypatch.undo()
    assert pipeline.run(inputs).outcome is pipeline_module.Outcome.COMPLETED


# --- B07 Red-Team round 2 regressions (RT-B7-12, RT-B7-13, RT-B7-04 residual) -------------


def test_a_worker_started_with_site_processing_refuses() -> None:
    with pytest.raises(IsolationError) as caught:
        run_worker(
            wp.Operation.PROBE,
            {},
            input_fd=None,
            limits=WorkerLimits(wall_clock_seconds=60.0),
            command=[
                sys.executable,
                "-I",
                "-m",
                "pmv.acquisition.parse_worker",
                canonical_json(
                    {"operation": "probe", "limits": WorkerLimits().as_parameters()}
                ).decode("ascii"),
            ],
        )
    assert caught.value.failure is IsolationFailure.NOT_CONFINED


def test_registered_transports_are_matched_by_identity_not_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registered(syn.SyntheticTransport):
        pass

    class Impostor(syn.SyntheticTransport):
        pass

    Impostor.__module__ = Registered.__module__
    Impostor.__qualname__ = Registered.__qualname__
    monkeypatch.setattr(pipeline_module, "PRODUCTION_TRANSPORTS", frozenset({Registered}))
    assert any(Registered is kind for kind in pipeline_module.PRODUCTION_TRANSPORTS)
    assert not any(Impostor is kind for kind in pipeline_module.PRODUCTION_TRANSPORTS)


def test_worker_internal_error_stops_without_rejecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("store", "backup", "restore"):
        (tmp_path / name).mkdir(mode=0o700)

    def internal(*_args: object, **_kwargs: object) -> object:
        raise WorkerRefusedError(wp.RefusalCode.INTERNAL_ERROR, None)

    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": syn.ok(b"a\n1\n")})
    pipeline = pipeline_module.AcquisitionPipeline(
        pipeline_module.PipelineSettings(
            tmp_path / "store",
            pipeline_module.RunMode.SYNTHETIC,
            worker_limits=WorkerLimits(wall_clock_seconds=60.0),
            fetch_policy=FetchPolicy(free_space_margin_bytes=0),
        ),
        transport=transport,
        backup=pipeline_module.DirectoryBackupTarget(
            "synthetic_backup_policy", tmp_path / "backup", tmp_path / "restore"
        ),
        repository=syn.StaticRepository(),
    )
    inputs = syn.inputs([syn.planned_file("a.csv", schema=syn.csv_schema(("a", "integer")))])
    monkeypatch.setattr("pmv.acquisition.isolation.verify_file", internal)
    with pytest.raises(pipeline_module.PipelineError, match="isolation_internal_error"):
        pipeline.run(inputs)
    monkeypatch.undo()
    assert pipeline.run(inputs).outcome is pipeline_module.Outcome.COMPLETED


# --- B07 Red-Team round 3 regression (RT-B7-14) --------------------------------------------


def test_a_planted_module_in_the_package_root_cannot_shadow_the_stdlib(tmp_path: Path) -> None:
    from pmv.acquisition import isolation

    root = tmp_path / "root"
    root.mkdir()
    (root / "pmv").symlink_to(Path(isolation._PACKAGE_ROOT) / "pmv")
    marker = tmp_path / "shadow-ran"
    (root / "csv.py").write_text(f"open({str(marker)!r}, 'w').close()\nraise SystemExit(99)\n")
    parameters = canonical_json({"operation": "probe", "limits": WorkerLimits().as_parameters()})
    result = run_worker(
        wp.Operation.PROBE,
        {},
        input_fd=None,
        limits=WorkerLimits(wall_clock_seconds=60.0),
        command=[
            sys.executable,
            "-I",
            "-S",
            "-c",
            isolation._BOOTSTRAP,
            str(root),
            parameters.decode("ascii"),
        ],
    )
    assert not marker.exists()
    assert result.result["status"] == "ok"
