"""G-6 end-to-end acquisition pipeline on synthetic data: prerequisites, modes, outcomes.

Every source, record, host, and byte here is synthetic. The transport is scripted; no
network request is made. Crash, restart, and conflict injection are in
``tests/failure_injection/test_acquisition_pipeline_faults.py``.
"""

import ast
import gzip
import io
import json
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from pmv.acquisition import pipeline as pipeline_module
from pmv.acquisition import synthetic as syn
from pmv.acquisition.confinement import WorkerLimits
from pmv.acquisition.fetch import FetchPolicy, TransportFailureError
from pmv.acquisition.pipeline import (
    AcquisitionPipeline,
    DirectoryBackupTarget,
    Outcome,
    PipelineInputs,
    PipelineSettings,
    RunMode,
)
from pmv.acquisition.receipts import ReceiptEvent, ReceiptJournal

REPO = Path(__file__).resolve().parents[2]
SCHEMA = syn.csv_schema(("row", "integer"), ("value", "decimal"))
CSV = b"row,value\n0,1.5\n1,-2.25\n"
SETTINGS_EXTRA: dict[str, Any] = {
    "worker_limits": WorkerLimits(wall_clock_seconds=60.0),
    "fetch_policy": FetchPolicy(free_space_margin_bytes=0),
}


@dataclass
class Env:
    root: Path
    store: Path
    backup: DirectoryBackupTarget

    def pipeline(self, transport: syn.SyntheticTransport, **kwargs: Any) -> AcquisitionPipeline:
        mode = kwargs.pop("mode", RunMode.SYNTHETIC)
        return AcquisitionPipeline(
            PipelineSettings(self.store, mode, **SETTINGS_EXTRA),
            transport=transport,
            backup=kwargs.pop("backup", self.backup),
            repository=kwargs.pop("repository", syn.StaticRepository()),
            **kwargs,
        )

    @property
    def base(self) -> Path:
        return self.store / "acquisitions" / "v1"

    def journal(self) -> ReceiptJournal:
        return ReceiptJournal(self.base / "journal.jsonl")


@pytest.fixture
def env(tmp_path: Path) -> Env:
    for name in ("store", "backup", "restore"):
        (tmp_path / name).mkdir(mode=0o700)
    backup = DirectoryBackupTarget(
        "synthetic_backup_policy", tmp_path / "backup", tmp_path / "restore"
    )
    return Env(tmp_path, tmp_path / "store", backup)


def _csv_inputs(data: bytes = CSV, **kwargs: Any) -> tuple[PipelineInputs, syn.SyntheticTransport]:
    item = syn.planned_file("a.csv", schema=SCHEMA, provider_sha256=syn.sha256(data))
    return syn.inputs([item], **kwargs), syn.SyntheticTransport(
        {syn.PREFIX + "a.csv": syn.ok(data)}
    )


def _stored(env: Env, name: str, acquisition: str = "synthetic_acq_1") -> Path:
    return env.base / "store" / "synthetic_source" / acquisition / name


# --- completed acquisitions ---------------------------------------------------------------


def test_csv_acquisition_completes_into_the_protected_store(env: Env) -> None:
    inputs, transport = _csv_inputs()
    report = env.pipeline(transport).run(inputs)
    assert report.outcome is Outcome.COMPLETED
    stored = _stored(env, "a.csv")
    assert stored.read_bytes() == CSV
    assert stored.stat().st_mode & 0o777 == 0o400
    assert stored.parent.stat().st_mode & 0o777 == 0o500
    assert not (env.base / "work" / "synthetic_acq_1").exists()
    events = [entry.event for entry in env.journal().entries]
    assert events == [
        ReceiptEvent.APPROVED_FOR_FETCH,
        ReceiptEvent.RECEIVED,
        ReceiptEvent.INTEGRITY_VERIFIED,
        ReceiptEvent.PARSER_VERIFIED,
        ReceiptEvent.BACKUP_VERIFIED,
        ReceiptEvent.STORED,
        ReceiptEvent.COMPLETED,
    ]
    record = json.loads((stored.parent / "acquisition.json").read_bytes())
    assert record["files"][0]["sha256"] == syn.sha256(CSV)
    assert record["files"][0]["hash_source"] == "provider"
    assert record["files"][0]["verification"]["verification"]["summary"]["records"] == 2
    assert record["mode"] == "synthetic"
    assert record["binding_sha256"] == env.journal().entries[0].plan_sha256


def test_report_journal_and_record_carry_no_file_content(env: Env) -> None:
    # Sentinel values with a decimal point cannot occur in a hex hash or a timestamp.
    sentinel = b"row,value\n0,424242.4242\n1,-313131.3131\n"
    inputs, transport = _csv_inputs(sentinel)
    report = env.pipeline(transport).run(inputs)
    stored = _stored(env, "a.csv")
    assert stored.read_bytes() == sentinel
    for blob in (
        json.dumps(report.document()).encode(),
        (env.base / "journal.jsonl").read_bytes(),
        (stored.parent / "acquisition.json").read_bytes(),
    ):
        assert b"424242.4242" not in blob
        assert b"313131.3131" not in blob


def test_rerun_is_idempotent_and_contacts_nothing(env: Env) -> None:
    inputs, transport = _csv_inputs()
    pipeline = env.pipeline(transport)
    first = pipeline.run(inputs)
    count = len(env.journal().entries)
    again = pipeline.run(inputs)
    assert again.outcome is Outcome.ALREADY_COMPLETED
    assert again.record_sha256 == first.record_sha256
    assert len(transport.requests) == 1
    assert len(env.journal().entries) == count


def test_compressed_jsonl_completes(env: Env) -> None:
    raw = b'{"row":0,"value":1.5}\n{"row":1,"value":null}\n'
    data = gzip.compress(raw)
    schema = {"keys": {"row": ["integer"], "value": ["number", "null"]}, "additional_keys": False}
    item = syn.planned_file("a.jsonl.gz", file_format="jsonl", compression="gzip", schema=schema)
    transport = syn.SyntheticTransport({syn.PREFIX + "a.jsonl.gz": syn.ok(data)})
    report = env.pipeline(transport).run(syn.inputs([item]))
    assert report.outcome is Outcome.COMPLETED
    assert _stored(env, "a.jsonl.gz").read_bytes() == data  # raw bytes, never decoded copies


def _tar_gz(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _archive_item(name: str, members: list[str]) -> dict[str, object]:
    return syn.planned_file(
        name,
        kind="archive",
        file_format=None,
        schema=None,
        members=[{"name": member, "format": "csv", "schema": SCHEMA} for member in members],
    )


def test_tar_archive_completes_and_stores_only_the_raw_archive(env: Env) -> None:
    data = _tar_gz({"d/a.csv": CSV, "b.csv": CSV})
    transport = syn.SyntheticTransport({syn.PREFIX + "a.tar.gz": syn.ok(data)})
    report = env.pipeline(transport).run(
        syn.inputs([_archive_item("a.tar.gz", ["d/a.csv", "b.csv"])])
    )
    assert report.outcome is Outcome.COMPLETED
    directory = _stored(env, "a.tar.gz").parent
    assert sorted(path.name for path in directory.iterdir()) == ["a.tar.gz", "acquisition.json"]
    record = json.loads((directory / "acquisition.json").read_bytes())
    members = record["files"][0]["verification"]["members"]
    assert [member["name"] for member in members] == ["b.csv", "d/a.csv"]


def test_zip_archive_completes(env: Env) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.csv", CSV)
    transport = syn.SyntheticTransport({syn.PREFIX + "a.zip": syn.ok(buffer.getvalue())})
    report = env.pipeline(transport).run(syn.inputs([_archive_item("a.zip", ["a.csv"])]))
    assert report.outcome is Outcome.COMPLETED


def test_archive_members_must_match_the_plan_exactly(env: Env) -> None:
    data = _tar_gz({"a.csv": CSV, "extra.csv": CSV})
    transport = syn.SyntheticTransport({syn.PREFIX + "a.tar.gz": syn.ok(data)})
    report = env.pipeline(transport).run(syn.inputs([_archive_item("a.tar.gz", ["a.csv"])]))
    assert report.outcome is Outcome.REJECTED
    assert report.files[0].code == "archive_members_differ_from_plan"
    assert not (env.base / "store").exists()
    assert not (env.base / "work" / "synthetic_acq_1" / "scratch").exists()


# --- rejections and retries ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"row,value\n0,not-a-number\n", "type_mismatch"),
        (b"other,header\n0,1\n", "schema_mismatch"),
        (b"\x80\x04\x95\x05\x00\x00\x00\x00\x00\x00\x00}\x94.", "signature"),
    ],
)
def test_bad_content_is_rejected_and_set_aside_never_stored(
    env: Env, data: bytes, code: str
) -> None:
    item = syn.planned_file("a.csv", schema=SCHEMA)
    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": syn.ok(data)})
    report = env.pipeline(transport).run(syn.inputs([item]))
    assert report.outcome is Outcome.REJECTED
    assert report.files[0].code == code
    assert not (env.base / "store").exists()
    rejected = list((env.base / "rejected" / "synthetic_acq_1").iterdir())
    assert [path.read_bytes() for path in rejected] == [data]
    last = env.journal().entries[-1]
    assert last.event is ReceiptEvent.REJECTED
    # A rejected acquisition stays rejected.
    assert env.pipeline(transport).run(syn.inputs([item])).outcome is Outcome.REJECTED


def test_fetch_failure_is_recorded_then_retried(env: Env) -> None:
    failing = syn.ScriptedResponse(error=TransportFailureError())
    route = [failing, syn.ok(CSV)]
    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": route})
    inputs = syn.inputs([syn.planned_file("a.csv", schema=SCHEMA)])
    first = env.pipeline(transport).run(inputs)
    assert first.outcome is Outcome.IN_PROGRESS
    assert first.files[0].code == "transport_error"
    second = env.pipeline(transport).run(inputs)
    assert second.outcome is Outcome.COMPLETED
    attempts = [
        entry.detail["attempt"]  # type: ignore[index]
        for entry in env.journal().entries
        if entry.event is ReceiptEvent.APPROVED_FOR_FETCH
    ]
    assert attempts == [1, 2]


def test_attempts_are_capped(env: Env) -> None:
    failing = syn.ScriptedResponse(error=TransportFailureError())
    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": failing})
    inputs = syn.inputs([syn.planned_file("a.csv", schema=SCHEMA)], max_attempts=2)
    outcomes = [env.pipeline(transport).run(inputs).outcome for _ in range(3)]
    assert outcomes == [Outcome.IN_PROGRESS, Outcome.IN_PROGRESS, Outcome.REJECTED]
    assert len(transport.requests) == 2


def test_provider_hash_mismatch_is_a_fetch_failure(env: Env) -> None:
    item = syn.planned_file("a.csv", schema=SCHEMA, provider_sha256="0" * 64)
    transport = syn.SyntheticTransport({syn.PREFIX + "a.csv": syn.ok(CSV)})
    report = env.pipeline(transport).run(syn.inputs([item]))
    assert report.outcome is Outcome.IN_PROGRESS
    assert report.files[0].code == "hash_mismatch"
    assert list((env.base / "work" / "synthetic_acq_1" / "quarantine").iterdir()) == []


def test_redirect_out_of_scope_is_a_fetch_failure(env: Env) -> None:
    item = syn.planned_file("a.csv", schema=SCHEMA)
    transport = syn.SyntheticTransport(
        {syn.PREFIX + "a.csv": syn.redirect("https://api.vendor.example/v1/a.csv")}
    )
    report = env.pipeline(transport).run(syn.inputs([item]))
    assert report.files[0].code == "redirect_out_of_scope"
    assert len(transport.requests) == 1


# --- prerequisites: nothing starts unless every one holds ---------------------------------


def _refused(
    env: Env, inputs: PipelineInputs, transport: syn.SyntheticTransport, **kwargs: Any
) -> list[str]:
    report = env.pipeline(transport, **kwargs).run(inputs)
    assert report.outcome is Outcome.REFUSED
    assert transport.requests == []
    assert not (env.base / "journal.jsonl").exists()
    return list(report.failures)


@pytest.mark.parametrize(
    "missing",
    ["plan", "approval", "licence", "quality", "backup_policy", "restore_tests", "a4_review"],
)
def test_absent_records_refuse(env: Env, missing: str) -> None:
    inputs, transport = _csv_inputs()
    failures = _refused(env, replace(inputs, **{missing: None}), transport)
    assert failures


def _with(inputs: PipelineInputs, key: str, **changes: Any) -> PipelineInputs:
    document = getattr(inputs, key)
    assert isinstance(document, dict)
    return replace(inputs, **{key: {**document, **changes}})


@pytest.mark.parametrize(
    ("key", "changes", "expected"),
    [
        ("licence", {"storage": "unknown"}, "A-2: licence: storage is not granted"),
        ("licence", {"automated_access": "no"}, "A-2: licence: automated_access is not granted"),
        (
            "licence",
            {"licence_id": "synthetic_other"},
            "A-1/A-2: approval cites a different licence",
        ),
        (
            "quality",
            {"quality_tier": "Q4_unverified", "reconciliation_primary_source_id": "synthetic_p"},
            "A-6",
        ),
        (
            "a4_review",
            {"no_blocking_findings": False},
            "A-4: safe-parsing tool review has not passed",
        ),
        ("a4_review", {"no_major_findings": False}, "A-4: safe-parsing tool review has not passed"),
        ("plan", {"approval_id": "synthetic_other"}, "A-1: the plan does not match its approval"),
        ("approval", {"expected_size_bytes": 10}, "A-1: the plan's size caps exceed"),
        ("approval", {"formats": ["json"]}, "A-1: the plan contains a format"),
        ("backup_policy", {"policy_id": "synthetic_other"}, "A-3"),
    ],
)
def test_inconsistent_records_refuse(
    env: Env, key: str, changes: dict[str, Any], expected: str
) -> None:
    inputs, transport = _csv_inputs()
    failures = _refused(env, _with(inputs, key, **changes), transport)
    assert any(failure.startswith(expected) for failure in failures), failures


def test_malformed_record_refuses(env: Env) -> None:
    inputs, transport = _csv_inputs()
    failures = _refused(env, _with(inputs, "licence", unexpected=1), transport)
    assert any("malformed" in failure for failure in failures)


def test_failed_restore_test_refuses(env: Env) -> None:
    inputs, transport = _csv_inputs()
    tests = [{**test, "passed": False} for test in inputs.restore_tests]  # type: ignore[attr-defined]
    failures = _refused(env, replace(inputs, restore_tests=tests), transport)
    assert any("restore test" in failure for failure in failures)


def test_credentialed_acquisition_refuses(env: Env) -> None:
    inputs, transport = _csv_inputs(credential_required=True)
    assert any(f.startswith("F-03") for f in _refused(env, inputs, transport))


def test_unadopted_reader_refuses_before_transport(env: Env) -> None:
    item = syn.planned_file("a.parquet", file_format="parquet", schema=None)
    inputs = syn.inputs([item], approval_formats=("parquet",))
    transport = syn.SyntheticTransport({})
    assert "A-4: no adopted reader for parquet" in _refused(env, inputs, transport)


def test_url_outside_the_allowlist_refuses(env: Env) -> None:
    item = syn.planned_file("a.csv", schema=SCHEMA, url="https://elsewhere.example/a.csv")
    transport = syn.SyntheticTransport({})
    failures = _refused(env, syn.inputs([item]), transport)
    assert any("outside the approved hosts" in failure for failure in failures)


# --- modes --------------------------------------------------------------------------------


def test_synthetic_mode_refuses_real_looking_records(env: Env) -> None:
    item = syn.planned_file("a.csv", schema=SCHEMA)
    inputs = syn.inputs([item], acquisition_id="real_acq", source_id="real_source")
    failures = _refused(env, inputs, syn.SyntheticTransport({}))
    assert "mode: a synthetic run accepts only synthetic_ records" in failures


def test_synthetic_mode_refuses_a_non_synthetic_transport(env: Env) -> None:
    inputs, transport = _csv_inputs()
    transport.synthetic = False
    assert "mode: a synthetic run needs a synthetic transport" in _refused(env, inputs, transport)


def test_synthetic_mode_refuses_the_protected_area(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline_module, "PROTECTED_ROOT", env.root)
    inputs, transport = _csv_inputs()
    failures = _refused(env, inputs, transport)
    assert "A-7: a synthetic run must not write inside ~/pmv-protected" in failures


def test_real_mode_refuses_synthetic_records(
    env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tool_checkout(tmp_path / "tool", commit_records=True)
    monkeypatch.setattr(pipeline_module, "TOOL_ROOT", tmp_path / "tool")
    inputs, transport = _csv_inputs()
    failures = _refused(env, inputs, transport, mode=RunMode.REAL)
    assert "mode: a real run refuses synthetic records" in failures
    assert "G-4: no reviewed production transport" in failures
    assert "A-7: a real store root must resolve inside the protected raw location" in failures


def test_real_mode_refuses_even_with_every_git_fact_true(
    env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tool_checkout(tmp_path / "tool", commit_records=True)
    monkeypatch.setattr(pipeline_module, "TOOL_ROOT", tmp_path / "tool")
    inputs, transport = _csv_inputs()
    repository = syn.StaticRepository("e" * 40, True, True, True, True)
    failures = _refused(env, inputs, transport, mode=RunMode.REAL, repository=repository)
    assert "G-4: no reviewed production transport" in failures
    assert "A-3: a real run needs the owner's real backup target" in failures
    assert "A-4: the A-4 record does not say A-4 is satisfied" in failures


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


def _tool_checkout(root: Path, *, commit_records: bool) -> str:
    """A temporary, real Git checkout standing in for the tool's own repository.

    Real mode reads every Git fact from ``pipeline.TOOL_ROOT``; tests point that at this
    repository so the facts are constructed explicitly, never taken from ``/workspace``.
    """
    root.mkdir()
    _git(root, "init", "-q")
    (root / "src" / "pmv" / "acquisition").mkdir(parents=True)
    (root / "src" / "pmv" / "acquisition" / "tool.py").write_text("TOOL = 1\n")
    paths = ["src/pmv/acquisition/tool.py"]
    if commit_records:
        for record in (syn.DECISION, syn.REVIEW):
            (root / record).parent.mkdir(parents=True, exist_ok=True)
            (root / record).write_text("synthetic placeholder record\n")
            paths.append(record)
    _git(root, "add", *paths)
    _git(root, "commit", "-q", "-m", "synthetic baseline")
    return _git(root, "rev-parse", "HEAD")


A5_DIRTY = "A-5: the acquisition tool must run from a clean, committed tree"
RECORDS = "records: a cited decision or review file is not committed unchanged"


def test_real_mode_checks_git_facts(
    env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "tool"
    _tool_checkout(checkout, commit_records=False)
    # A tracked, uncommitted change to the acquisition tool.
    (checkout / "src" / "pmv" / "acquisition" / "tool.py").write_text("TOOL = 2\n")
    monkeypatch.setattr(pipeline_module, "TOOL_ROOT", checkout)
    inputs, transport = _csv_inputs()
    failures = _refused(env, inputs, transport, mode=RunMode.REAL)
    assert A5_DIRTY in failures
    assert RECORDS in failures
    assert "F-09: the approval's F-09 commit is not an ancestor of HEAD" in failures
    assert "A-4: the acquisition code changed since its review" in failures


def test_real_mode_refuses_an_untracked_file_in_the_tool_tree(
    env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "tool"
    _tool_checkout(checkout, commit_records=False)
    (checkout / "src" / "pmv" / "acquisition" / "planted.py").write_text("X = 1\n")
    monkeypatch.setattr(pipeline_module, "TOOL_ROOT", checkout)
    inputs, transport = _csv_inputs()
    assert A5_DIRTY in _refused(env, inputs, transport, mode=RunMode.REAL)


def test_real_mode_reads_clean_committed_git_facts(
    env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "tool"
    head = _tool_checkout(checkout, commit_records=True)
    monkeypatch.setattr(pipeline_module, "TOOL_ROOT", checkout)
    inputs, transport = _csv_inputs()
    inputs = _with(inputs, "approval", f09_settings_commit=head)
    inputs = _with(inputs, "a4_review", reviewed_commit=head)
    failures = _refused(env, inputs, transport, mode=RunMode.REAL)
    # A clean, committed checkout produces none of the Git-fact failures...
    assert A5_DIRTY not in failures
    assert RECORDS not in failures
    assert "F-09: the approval's F-09 commit is not an ancestor of HEAD" not in failures
    assert "A-4: the acquisition code changed since its review" not in failures
    # ...and the run is still refused for the reasons that do not depend on Git.
    assert "G-4: no reviewed production transport" in failures
    assert "mode: a real run refuses synthetic records" in failures


# --- structural boundaries ----------------------------------------------------------------

NETWORK = {
    "socket",
    "ssl",
    "http",
    "requests",
    "httpx",
    "aiohttp",
    "asyncio",
    "ftplib",
    "smtplib",
    "websocket",
    "websockets",
    "urllib3",
}


@pytest.mark.parametrize(
    "module",
    sorted(path.name for path in (REPO / "src" / "pmv" / "acquisition").glob("*.py")),
)
def test_acquisition_code_contains_no_network_client(module: str) -> None:
    tree = ast.parse((REPO / "src" / "pmv" / "acquisition" / module).read_text("utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module)
    tops = {name.split(".")[0] for name in imported}
    assert not tops & NETWORK
    assert not {name for name in imported if name.startswith("urllib")} - {"urllib.parse"}
