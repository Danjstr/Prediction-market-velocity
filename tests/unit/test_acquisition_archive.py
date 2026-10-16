import io
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest

from pmv.acquisition.archive import (
    ArchiveRefusedError,
    ExtractionLimits,
    extract_archive,
    safe_member_name,
)
from pmv.integrity import sha256_hex

LIMITS = ExtractionLimits(free_space_margin_bytes=0)


def _tar(path: Path, files: dict[str, bytes], mode: Any = "w") -> Path:
    with tarfile.open(path, mode) as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


@pytest.mark.parametrize("mode", ["w", "w:gz", "w:bz2", "w:xz"])
def test_tar_family_extracts_and_hashes(tmp_path: Path, mode: str) -> None:
    files = {"./a.csv": b"a\n1\n", "sub/b.jsonl": b'{"x": 1}\n'}
    archive = _tar(tmp_path / "t.tar", files, mode)
    destination = tmp_path / "out"
    destination.mkdir()
    extracted = extract_archive(archive, destination, limits=LIMITS)
    assert [(e.name, e.size, e.sha256) for e in extracted] == [
        ("a.csv", 4, sha256_hex(b"a\n1\n")),
        ("sub/b.jsonl", 9, sha256_hex(b'{"x": 1}\n')),
    ]
    assert (destination / "sub" / "b.jsonl").read_bytes() == b'{"x": 1}\n'


def test_zip_extracts(tmp_path: Path) -> None:
    path = tmp_path / "t.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dir/", b"")
        archive.writestr("dir/a.csv", b"a\n" * 10)
    destination = tmp_path / "out"
    destination.mkdir()
    extracted = extract_archive(path, destination, limits=LIMITS)
    assert [e.name for e in extracted] == ["dir/a.csv"]


def test_unsupported_zip_compression_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_LZMA) as archive:
        archive.writestr("a.csv", b"a\n")
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ArchiveRefusedError, match="compression method"):
        extract_archive(path, destination, limits=LIMITS)


def test_case_insensitive_duplicates_are_refused(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "t.tar", {"A.csv": b"1", "a.csv": b"2"})
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ArchiveRefusedError, match="case is ignored"):
        extract_archive(archive, destination, limits=LIMITS)


def test_member_nested_under_a_file_is_refused(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "t.tar", {"a.csv": b"1", "a.csv/b.csv": b"2"})
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ArchiveRefusedError, match="nested under a file"):
        extract_archive(archive, destination, limits=LIMITS)


def test_destination_must_be_an_empty_real_directory(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "t.tar", {"a.csv": b"1"})
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "x").write_bytes(b"")
    with pytest.raises(ArchiveRefusedError, match="not empty"):
        extract_archive(archive, occupied, limits=LIMITS)
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ArchiveRefusedError, match="symlink"):
        extract_archive(archive, link, limits=LIMITS)
    with pytest.raises(ArchiveRefusedError, match="does not exist"):
        extract_archive(archive, tmp_path / "missing", limits=LIMITS)


def test_non_archive_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "plain.csv"
    path.write_bytes(b"a,b\n1,2\n")
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ArchiveRefusedError, match="not a supported"):
        extract_archive(path, destination, limits=LIMITS)


def test_depth_limit(tmp_path: Path) -> None:
    deep = "/".join(["d"] * 9) + "/a.csv"
    archive = _tar(tmp_path / "t.tar", {deep: b"1"})
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises(ArchiveRefusedError, match="depth"):
        extract_archive(archive, destination, limits=LIMITS)


@pytest.mark.parametrize(
    "name", ["", "a\x00b", "a\\b.csv", "a b.csv", "a//b.csv", "./", "x/../y", "é.csv"]
)
def test_unsafe_member_names(name: str) -> None:
    with pytest.raises(ArchiveRefusedError):
        safe_member_name(name, is_dir=False, max_depth=8)


def test_safe_member_name_normalizes_leading_dot_slash() -> None:
    assert safe_member_name("./a/b.csv", is_dir=False, max_depth=8) == "a/b.csv"
    assert safe_member_name("dir/", is_dir=True, max_depth=8) == "dir"
