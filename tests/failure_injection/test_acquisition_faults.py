"""A-4 fault-injection fixtures for the acquisition safe-parsing controls.

Required by ``docs/external_access.md`` §2 A-4: a path-traversal tar, symlink and hardlink
tars, a decompression bomb of at least 1000:1, pickle disguised as Parquet, a remote-path
manifest, NaN and duplicate-key JSON, and a full disk. Every fixture is synthetic and
built inside ``tmp_path`` at test time. No hostile file is committed to the repository.
"""

import bz2
import errno
import io
import stat
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from pmv.acquisition.archive import ArchiveRefusedError, ExtractionLimits, extract_archive
from pmv.acquisition.formats import FileFormat, FormatRefusedError, check_format
from pmv.acquisition.records import ManifestFile, RecordError
from pmv.acquisition.strict_parse import StrictParseError, parse_json, parse_jsonl

# Protocol-4 pickle header bytes, written literally so no pickle module is imported.
PICKLE_BYTES = b"\x80\x04\x95\x05\x00\x00\x00\x00\x00\x00\x00}\x94."
SMALL_LIMITS = ExtractionLimits(free_space_margin_bytes=0)


def _tar(path: Path, members: Sequence[tuple[tarfile.TarInfo, bytes | None]]) -> Path:
    with tarfile.open(path, "w") as archive:
        for info, data in members:
            if data is not None:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            else:
                archive.addfile(info)
    return path


def _info(name: str, kind: bytes = tarfile.REGTYPE, link: str = "") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = link
    return info


def _dest(tmp_path: Path) -> Path:
    destination = tmp_path / "out"
    destination.mkdir()
    return destination


def _assert_refused_and_empty(archive: Path, destination: Path, match: str) -> None:
    with pytest.raises(ArchiveRefusedError, match=match):
        extract_archive(archive, destination, limits=SMALL_LIMITS)
    assert list(destination.iterdir()) == []


# --- path traversal ----------------------------------------------------------------------


@pytest.mark.parametrize("name", ["../evil.csv", "/etc/evil.csv", "a/../../evil.csv", "a/./b.csv"])
def test_path_traversal_tar_is_refused(tmp_path: Path, name: str) -> None:
    archive = _tar(tmp_path / "t.tar", [(_info("ok.csv"), b"a\n1\n"), (_info(name), b"x\n")])
    _assert_refused_and_empty(archive, _dest(tmp_path), "absolute or malformed|disallowed")
    assert not (tmp_path / "evil.csv").exists()


def test_path_traversal_zip_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../evil.csv", b"x\n")
    _assert_refused_and_empty(path, _dest(tmp_path), "disallowed component")


# --- links, devices ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "link"),
    [
        (tarfile.SYMTYPE, "/etc/passwd"),
        (tarfile.SYMTYPE, "ok.csv"),
        (tarfile.LNKTYPE, "ok.csv"),
        (tarfile.CHRTYPE, ""),
        (tarfile.BLKTYPE, ""),
        (tarfile.FIFOTYPE, ""),
    ],
)
def test_link_device_and_fifo_tar_members_are_refused(
    tmp_path: Path, kind: bytes, link: str
) -> None:
    archive = _tar(
        tmp_path / "t.tar", [(_info("ok.csv"), b"a\n"), (_info("l.csv", kind, link), None)]
    )
    _assert_refused_and_empty(archive, _dest(tmp_path), "link, device, FIFO")


def test_symlink_zip_member_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.zip"
    info = zipfile.ZipInfo("link.csv")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, b"/etc/passwd")
    _assert_refused_and_empty(path, _dest(tmp_path), "link, device, or FIFO")


def test_encrypted_zip_member_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("secret.csv", b"x")
    # zipfile clears the encryption flag on write, so set bit 0 in both headers directly.
    data = bytearray(path.read_bytes())
    local = data.index(b"PK\x03\x04")
    central = data.index(b"PK\x01\x02")
    data[local + 6] |= 0x1
    data[central + 8] |= 0x1
    path.write_bytes(bytes(data))
    _assert_refused_and_empty(path, _dest(tmp_path), "encrypted")


# --- decompression bomb ------------------------------------------------------------------


def test_decompression_bomb_of_at_least_1000_to_1_is_refused(tmp_path: Path) -> None:
    payload_size = 24 * 1024 * 1024
    path = tmp_path / "bomb.tar.bz2"
    info = _info("zeros.csv")
    info.size = payload_size
    with tarfile.open(path, "w:bz2") as archive:
        archive.addfile(info, io.BytesIO(bytes(payload_size)))
    ratio = payload_size / path.stat().st_size
    assert ratio >= 1000
    _assert_refused_and_empty(path, _dest(tmp_path), "expansion-ratio")


def test_total_size_limit_applies_before_any_write(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "t.tar", [(_info("a.csv"), b"x" * 600), (_info("b.csv"), b"y" * 600)])
    limits = ExtractionLimits(max_total_bytes=1000, free_space_margin_bytes=0)
    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError, match="total-size"):
        extract_archive(archive, destination, limits=limits)
    assert list(destination.iterdir()) == []


def test_member_count_limit(tmp_path: Path) -> None:
    members = [(_info(f"f{i}.csv"), b"x\n") for i in range(5)]
    archive = _tar(tmp_path / "t.tar", members)
    limits = ExtractionLimits(max_members=4, free_space_margin_bytes=0)
    with pytest.raises(ArchiveRefusedError, match="member-count"):
        extract_archive(archive, _dest(tmp_path), limits=limits)


def test_bz2_stream_that_is_not_a_tar_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "x.bz2"
    path.write_bytes(bz2.compress(b"not a tar" * 100))
    _assert_refused_and_empty(path, _dest(tmp_path), r"corrupt|truncated|unreadable|malformed")


# --- pickle disguised as Parquet ---------------------------------------------------------


def test_pickle_disguised_as_parquet_is_refused() -> None:
    with pytest.raises(FormatRefusedError, match="pickle"):
        check_format("prices.parquet", FileFormat.PARQUET, PICKLE_BYTES[:8], PICKLE_BYTES[-4:])


def test_pickle_disguised_as_csv_is_refused() -> None:
    with pytest.raises(FormatRefusedError, match="pickle"):
        check_format("prices.csv", FileFormat.CSV, PICKLE_BYTES[:8], PICKLE_BYTES[-4:])


# --- remote-path manifest ----------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "https://evil.example/x.csv",
        "s3://bucket/x.csv",
        "hf://datasets/x/y.parquet",
        "/etc/passwd",
        "../x.csv",
        "dir/x.csv",
        "file:x.csv",
        "\\\\server\\share\\x.csv",
    ],
)
def test_remote_or_path_manifest_entries_are_refused(name: str) -> None:
    document = {"name": name, "format": "csv", "size_bytes": 1, "sha256": "0" * 64}
    with pytest.raises(RecordError, match="plain local file name"):
        ManifestFile.from_document(document)


# --- NaN and duplicate-key JSON ----------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        b'{"price": NaN}',
        b'{"price": Infinity}',
        b'{"price": -Infinity}',
        b'{"a": 1, "a": 2}',
        b'{"outer": {"b": 1, "b": 1}}',
        b'[{"x": 1}, {"y": NaN}]',
    ],
)
def test_nan_infinity_and_duplicate_keys_are_rejected(text: bytes) -> None:
    with pytest.raises(StrictParseError, match=r"NaN|duplicate"):
        parse_json(text)


def test_jsonl_with_nan_reports_the_line() -> None:
    with pytest.raises(StrictParseError, match="line 2"):
        parse_jsonl(b'{"a": 1}\n{"a": NaN}\n')


def test_json_floats_parse_to_decimal_never_float() -> None:
    value = parse_json(b'{"p": 0.1, "n": 3}')
    assert isinstance(value, dict)
    assert repr(value["p"]) == "Decimal('0.1')"
    assert type(value["n"]) is int


# --- full disk ---------------------------------------------------------------------------


def test_free_disk_precheck_refuses_before_writing(tmp_path: Path) -> None:
    archive = _tar(tmp_path / "t.tar", [(_info("a.csv"), b"x" * 1000)])
    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError, match="insufficient free disk"):
        extract_archive(archive, destination, limits=SMALL_LIMITS, disk_free=lambda _p: 999)
    assert list(destination.iterdir()) == []


def test_disk_full_during_write_rolls_back_everything(tmp_path: Path) -> None:
    archive = _tar(
        tmp_path / "t.tar",
        [(_info("d", tarfile.DIRTYPE), None), (_info("d/a.csv"), b"a\n"), (_info("b.csv"), b"b\n")],
    )
    destination = _dest(tmp_path)
    calls = {"n": 0}

    def failing_writer(fd: int, data: bytes) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(errno.ENOSPC, "No space left on device")
        import os

        os.write(fd, data)

    with pytest.raises(ArchiveRefusedError, match="disk full"):
        extract_archive(archive, destination, limits=SMALL_LIMITS, write_chunk=failing_writer)
    assert list(destination.iterdir()) == []
