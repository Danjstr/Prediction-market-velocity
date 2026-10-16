from pathlib import Path
from typing import Any

import pytest

from pmv.acquisition.backup import (
    BackupError,
    backup_and_verify_restore,
    synthetic_fixture,
)
from pmv.acquisition.formats import FileFormat
from pmv.acquisition.quarantine import Quarantine, QuarantineError, hash_file
from pmv.acquisition.receipts import ReceiptJournal
from pmv.acquisition.records import AcquisitionManifest, ManifestFile
from pmv.acquisition.strict_parse import parse_csv, parse_jsonl
from pmv.integrity import sha256_hex

DATA = b"synthetic,row\ntrue,0\n"


def _journal(directory: Path) -> ReceiptJournal:
    path = directory / "receipts.jsonl"
    if not path.exists():
        ReceiptJournal.create(path)
    return ReceiptJournal(path)


def _manifest(name: str, data: bytes, file_format: str = "csv") -> AcquisitionManifest:
    document: dict[str, Any] = {
        "manifest_version": 1,
        "acquisition_id": "acq_example",
        "approval_id": "appr_example",
        "licence_id": "lic_example",
        "input_licence_ids": ["lic_example"],
        "source_url": "https://files.example.com/history/a.csv",
        "retrieved_at": "2099-01-01T00:00:00.000000Z",
        "upstream_identity": "Synthetic",
        "is_primary_source": True,
        "mirror_lineage": [],
        "vendor_version": "v1",
        "tool_git_commit": "c" * 40,
        "tool_tree_dirty": False,
        "reproducible_from_provider": "no",
        "files": [
            {
                "name": name,
                "format": file_format,
                "size_bytes": len(data),
                "sha256": sha256_hex(data),
            }
        ],
    }
    return AcquisitionManifest.from_document(document)


def _dirs(tmp_path: Path, *names: str) -> list[Path]:
    paths = [tmp_path / name for name in names]
    for path in paths:
        path.mkdir()
    return paths


def test_receive_hashes_and_release_moves(tmp_path: Path) -> None:
    quarantine_dir, released = _dirs(tmp_path, "q", "released")
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    receipt = quarantine.receive("a.csv", [DATA[:5], DATA[5:]])
    assert receipt.sha256 == sha256_hex(DATA)
    quarantine.release("a.csv", _manifest("a.csv", DATA), released)
    assert (released / "a.csv").read_bytes() == DATA
    assert not (quarantine_dir / "a.csv").exists()


def test_quarantine_must_start_empty(tmp_path: Path) -> None:
    (quarantine_dir,) = _dirs(tmp_path, "q")
    (quarantine_dir / "left.csv").write_bytes(b"")
    with pytest.raises(QuarantineError, match="empty"):
        Quarantine(quarantine_dir, journal=_journal(tmp_path))


@pytest.mark.parametrize("name", ["../a.csv", "a/b.csv", "", ".", ".."])
def test_receive_refuses_unsafe_names(tmp_path: Path, name: str) -> None:
    (quarantine_dir,) = _dirs(tmp_path, "q")
    with pytest.raises(QuarantineError, match="plain component"):
        Quarantine(quarantine_dir, journal=_journal(tmp_path)).receive(name, [DATA])


def test_tampered_file_stays_in_quarantine(tmp_path: Path) -> None:
    quarantine_dir, released = _dirs(tmp_path, "q", "released")
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [DATA])
    target = quarantine_dir / "a.csv"
    target.chmod(0o600)
    target.write_bytes(DATA + b"true,1\n")
    with pytest.raises(QuarantineError, match="changed after receipt"):
        quarantine.release("a.csv", _manifest("a.csv", DATA), released)
    assert target.exists()
    assert list(released.iterdir()) == []


def test_manifest_mismatch_and_absence_refuse_release(tmp_path: Path) -> None:
    quarantine_dir, released = _dirs(tmp_path, "q", "released")
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [DATA])
    with pytest.raises(QuarantineError, match="does not match"):
        quarantine.release("a.csv", _manifest("a.csv", b"other\n"), released)
    with pytest.raises(QuarantineError, match="not in the acquisition manifest"):
        quarantine.release("a.csv", _manifest("b.csv", DATA), released)
    with pytest.raises(QuarantineError, match="no receipt"):
        quarantine.release("b.csv", _manifest("b.csv", DATA), released)


def test_format_check_runs_before_release(tmp_path: Path) -> None:
    quarantine_dir, released = _dirs(tmp_path, "q", "released")
    pickle_bytes = b"\x80\x04\x95\x05\x00\x00\x00\x00\x00\x00\x00}\x94."
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("p.parquet", [pickle_bytes])
    with pytest.raises(QuarantineError, match="pickle"):
        quarantine.release("p.parquet", _manifest("p.parquet", pickle_bytes, "parquet"), released)
    assert list(released.iterdir()) == []


def test_release_never_overwrites(tmp_path: Path) -> None:
    quarantine_dir, released = _dirs(tmp_path, "q", "released")
    (released / "a.csv").write_bytes(b"existing")
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [DATA])
    with pytest.raises(FileExistsError):
        quarantine.release("a.csv", _manifest("a.csv", DATA), released)
    assert (released / "a.csv").read_bytes() == b"existing"


def test_hash_file_refuses_symlinks(tmp_path: Path) -> None:
    real = tmp_path / "real.csv"
    real.write_bytes(DATA)
    link = tmp_path / "link.csv"
    link.symlink_to(real)
    assert hash_file(real) == (len(DATA), sha256_hex(DATA))
    with pytest.raises(OSError, match=r"symbolic links|Too many levels"):
        hash_file(link)


@pytest.mark.parametrize("file_format", [FileFormat.CSV, FileFormat.JSONL])
def test_synthetic_fixture_is_deterministic_parseable_and_sized(file_format: FileFormat) -> None:
    data = synthetic_fixture(file_format, 50_000, seed=7)
    assert data == synthetic_fixture(file_format, 50_000, seed=7)
    assert data != synthetic_fixture(file_format, 50_000, seed=8)
    assert 50_000 <= len(data) < 50_200
    if file_format is FileFormat.CSV:
        header, rows = parse_csv(data)
        assert header[0] == "synthetic"
        assert all(row[0] == "true" for row in rows)
    else:
        assert all(isinstance(v, dict) and v["synthetic"] is True for v in parse_jsonl(data))


def test_synthetic_fixture_refuses_other_formats() -> None:
    with pytest.raises(BackupError):
        synthetic_fixture(FileFormat.PARQUET, 10, seed=1)
    with pytest.raises(BackupError):
        synthetic_fixture(FileFormat.CSV, 0, seed=1)


def _entry(name: str, data: bytes) -> ManifestFile:
    return ManifestFile(
        name=name, format=FileFormat.CSV, size_bytes=len(data), sha256=sha256_hex(data)
    )


def test_synthetic_same_format_backup_and_restore_passes(tmp_path: Path) -> None:
    source, backup, restore = _dirs(tmp_path, "src", "backup", "restore")
    files = []
    for index in range(3):
        data = synthetic_fixture(FileFormat.CSV, 20_000, seed=index)
        (source / f"f{index}.csv").write_bytes(data)
        files.append(_entry(f"f{index}.csv", data))
    report = backup_and_verify_restore(files, source, backup, restore)
    assert report.passed
    assert report.verified == ["f0.csv", "f1.csv", "f2.csv"]
    for entry in files:
        assert hash_file(restore / entry.name) == (entry.size_bytes, entry.sha256)


def test_backup_reports_corruption_and_missing_files(tmp_path: Path) -> None:
    source, backup, restore = _dirs(tmp_path, "src", "backup", "restore")
    good = synthetic_fixture(FileFormat.CSV, 1000, seed=1)
    (source / "good.csv").write_bytes(good)
    (source / "bad.csv").write_bytes(b"corrupted")
    files = [_entry("good.csv", good), _entry("bad.csv", good), _entry("gone.csv", good)]
    report = backup_and_verify_restore(files, source, backup, restore)
    assert not report.passed
    assert report.verified == ["good.csv"]
    assert report.mismatched == ["bad.csv"]
    assert report.missing == ["gone.csv"]
    assert not (restore / "bad.csv").exists()


def test_backup_requires_empty_targets_and_files(tmp_path: Path) -> None:
    source, backup, restore = _dirs(tmp_path, "src", "backup", "restore")
    (backup / "old").write_bytes(b"")
    data = b"a\n"
    (source / "a.csv").write_bytes(data)
    with pytest.raises(BackupError, match="must be empty"):
        backup_and_verify_restore([_entry("a.csv", data)], source, backup, restore)
    with pytest.raises(BackupError, match="no manifest files"):
        backup_and_verify_restore([], source, backup, restore)
