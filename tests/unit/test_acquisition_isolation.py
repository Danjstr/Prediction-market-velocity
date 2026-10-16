"""G-1 isolated parsing with the real worker: confinement, verification, extraction.

Every input is synthetic and built in ``tmp_path``. Failure injection with misbehaving
workers is in ``tests/failure_injection/test_acquisition_isolation_faults.py``.
"""

import gzip
import io
import os
import tarfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from pmv.acquisition import isolation
from pmv.acquisition.archive import ArchiveRefusedError, ExtractionLimits
from pmv.acquisition.confinement import WorkerLimits, probe_names
from pmv.acquisition.formats import FileFormat
from pmv.acquisition.isolation import (
    FileSpec,
    IsolationError,
    IsolationFailure,
    WorkerRefusedError,
    isolated_extract,
    verify_file,
    verify_isolation,
)
from pmv.acquisition.readers import Compression, RecordSchema
from pmv.acquisition.worker_protocol import RefusalCode
from pmv.integrity import sha256_hex

CSV = b"row,value\n0,1.5\n1,-2\n"
CSV_SCHEMA = RecordSchema.from_document(
    FileFormat.CSV,
    {"columns": [{"name": "row", "type": "integer"}, {"name": "value", "type": "decimal"}]},
)
LIMITS = WorkerLimits(wall_clock_seconds=60.0)
SMALL = ExtractionLimits(free_space_margin_bytes=0)


@contextmanager
def _open(path: Path) -> Iterator[int]:
    fd = os.open(path, os.O_RDONLY)
    try:
        yield fd
    finally:
        os.close(fd)


def _verify(tmp_path: Path, name: str, data: bytes, spec: FileSpec) -> isolation.Verification:
    path = tmp_path / name
    path.write_bytes(data)
    with _open(path) as fd:
        return verify_file(
            fd, spec, expected_size=len(data), expected_sha256=sha256_hex(data), limits=LIMITS
        )


def _csv_spec(name: str = "a.csv", compression: Compression = Compression.NONE) -> FileSpec:
    return FileSpec(name, FileFormat.CSV, compression, CSV_SCHEMA)


def test_every_probed_syscall_is_denied_in_the_worker() -> None:
    run = verify_isolation(LIMITS)
    probe = run.result["probe"]
    assert isinstance(probe, dict)
    assert set(probe) == set(probe_names())
    assert all(value is True for value in probe.values())


def test_worker_identity_pins_code_and_runtime() -> None:
    identity = isolation.expected_identity()
    modules = identity["modules"]
    assert isinstance(modules, dict)
    assert {
        "pmv.acquisition.parse_worker",
        "pmv.acquisition.readers",
        "pmv.acquisition.strict_parse",
        "pmv.acquisition.archive",
        "pmv.acquisition.confinement",
    } <= set(modules)
    assert identity["implementation"] == "cpython"
    assert identity["readers"]["parquet"]["adopted"] is False  # type: ignore[index]


def test_csv_verifies_in_isolation_and_binds_to_exact_bytes(tmp_path: Path) -> None:
    result = _verify(tmp_path, "a.csv", CSV, _csv_spec())
    assert result.input_sha256 == sha256_hex(CSV)
    assert result.summary["records"] == 2
    assert result.summary["reader"] == {
        "reader": "pmv.strict_csv",
        "version": 1,
        "adopted": True,
        "implementation": "python-stdlib csv, strict",
        "registry_version": 1,
    }


def test_compressed_csv_verifies_in_isolation(tmp_path: Path) -> None:
    data = gzip.compress(CSV)
    result = _verify(tmp_path, "a.csv.gz", data, _csv_spec("a.csv.gz", Compression.GZIP))
    assert result.input_sha256 == sha256_hex(data)
    assert result.summary["decoded_sha256"] == sha256_hex(CSV)


def test_refusal_reports_code_and_record_only(tmp_path: Path) -> None:
    with pytest.raises(WorkerRefusedError) as caught:
        _verify(tmp_path, "a.csv", b"row,value\n0,SECRET\n", _csv_spec())
    assert caught.value.code is RefusalCode.TYPE_MISMATCH
    assert caught.value.record == 1
    assert "SECRET" not in str(caught.value)


def test_parquet_is_refused_without_being_read(tmp_path: Path) -> None:
    spec = FileSpec(
        "a.parquet",
        FileFormat.PARQUET,
        Compression.NONE,
        RecordSchema.from_document(FileFormat.PARQUET, None),
    )
    with pytest.raises(WorkerRefusedError) as caught:
        _verify(tmp_path, "a.parquet", b"PAR1" + b"\x80\x04\x95" + b"PAR1", spec)
    assert caught.value.code is RefusalCode.READER_NOT_ADOPTED


def test_pickle_disguised_as_csv_is_refused_in_isolation(tmp_path: Path) -> None:
    with pytest.raises(WorkerRefusedError) as caught:
        _verify(
            tmp_path, "a.csv", b"\x80\x04\x95\x05\x00\x00\x00\x00\x00\x00\x00}\x94.", _csv_spec()
        )
    assert caught.value.code is RefusalCode.FORMAT_REFUSED


def test_expected_hash_mismatch_is_an_input_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    path.write_bytes(CSV)
    with _open(path) as fd, pytest.raises(IsolationError) as caught:
        verify_file(
            fd, _csv_spec(), expected_size=len(CSV), expected_sha256="0" * 64, limits=LIMITS
        )
    assert caught.value.failure is IsolationFailure.INPUT_MISMATCH


def test_directory_input_is_refused(tmp_path: Path) -> None:
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(IsolationError):
            verify_file(fd, _csv_spec(), expected_size=0, expected_sha256="0" * 64, limits=LIMITS)
    finally:
        os.close(fd)


def test_memory_exhaustion_is_contained(tmp_path: Path) -> None:
    # A whole-document JSON within the reader's cap but beyond a tiny address-space limit.
    spec = FileSpec(
        "a.json",
        FileFormat.JSON,
        Compression.NONE,
        RecordSchema.from_document(
            FileFormat.JSON,
            {"keys": {"a": ["string"]}, "additional_keys": True, "top_level": "array_of_objects"},
        ),
    )
    data = b"[" + b",".join([b'{"a":"x"}'] * 400_000) + b"]"
    path = tmp_path / "a.json"
    path.write_bytes(data)
    tight = WorkerLimits(address_space_bytes=96 * 1024 * 1024, wall_clock_seconds=60.0)
    with _open(path) as fd, pytest.raises((WorkerRefusedError, IsolationError)) as caught:
        verify_file(
            fd, spec, expected_size=len(data), expected_sha256=sha256_hex(data), limits=tight
        )
    error = caught.value
    if isinstance(error, WorkerRefusedError):
        assert error.code in (RefusalCode.RESOURCE_EXHAUSTED, RefusalCode.DECODED_TOO_LARGE)
    else:
        assert isinstance(error, IsolationError)
        assert error.failure in (IsolationFailure.SIGNALED, IsolationFailure.ABNORMAL_EXIT)


# --- isolated extraction ------------------------------------------------------------------


def _tar(path: Path, members: dict[str, bytes], mode: str = "w:gz") -> Path:
    with tarfile.open(path, mode) as archive:  # type: ignore[call-overload]
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def _dest(tmp_path: Path) -> Path:
    destination = tmp_path / "out"
    destination.mkdir()
    return destination


def test_tar_extracts_through_the_worker(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "a.tar.gz", {"d/a.csv": CSV, "b.jsonl": b'{"x":1}\n'})
    destination = _dest(tmp_path)
    extracted = isolated_extract(archive, destination, limits=SMALL, worker_limits=LIMITS)
    assert sorted(item.name for item in extracted) == ["b.jsonl", "d/a.csv"]
    assert (destination / "d" / "a.csv").read_bytes() == CSV
    assert {item.sha256 for item in extracted} == {sha256_hex(CSV), sha256_hex(b'{"x":1}\n')}


def test_zip_extracts_through_the_worker(tmp_path: Path) -> None:
    path = tmp_path / "a.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.csv", CSV)
    destination = _dest(tmp_path)
    extracted = isolated_extract(path, destination, limits=SMALL, worker_limits=LIMITS)
    assert [item.name for item in extracted] == ["a.csv"]
    assert (destination / "a.csv").read_bytes() == CSV


@pytest.mark.parametrize(
    "members",
    [
        {"../escape.csv": CSV},
        {"a.pkl": b"\x80\x04."},
        {"run.sh": b"#!/bin/sh\n"},
    ],
)
def test_hostile_tar_members_are_refused_and_rolled_back(
    tmp_path: Path, members: dict[str, bytes]
) -> None:
    archive = _tar(tmp_path / "a.tar.gz", {"ok.csv": CSV, **members})
    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError):
        isolated_extract(archive, destination, limits=SMALL, worker_limits=LIMITS)
    assert list(destination.iterdir()) == []


def test_tar_bomb_is_refused_in_the_worker(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "a.tar.gz", {"zeros.csv": bytes(30 * 1024 * 1024)})
    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError):
        isolated_extract(archive, destination, limits=SMALL, worker_limits=LIMITS)
    assert list(destination.iterdir()) == []


def test_archive_hash_mismatch_is_refused_before_extraction(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "a.tar.gz", {"a.csv": CSV})
    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError, match="expected hash"):
        isolated_extract(archive, destination, worker_limits=LIMITS, expected_sha256="0" * 64)


def test_parent_disk_check_rolls_back(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "a.tar.gz", {"a.csv": CSV, "b.csv": CSV})
    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError, match="free disk"):
        isolated_extract(
            archive,
            destination,
            limits=ExtractionLimits(free_space_margin_bytes=1),
            worker_limits=LIMITS,
            disk_free=lambda _path: 0,
        )
    assert list(destination.iterdir()) == []
