"""Regression tests for the B06 Reliability / Red-Team review of the acquisition tooling.

Each test reproduces a finding in
``research/governance/b06_acquisition_tooling_red_team_review.md`` with a small synthetic
input built in ``tmp_path``, and pins the fix.
"""

import gzip
import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

from pmv.acquisition.archive import ArchiveRefusedError, ExtractionLimits, extract_archive
from pmv.acquisition.backup import BackupError, backup_and_verify_restore
from pmv.acquisition.formats import FileFormat, FormatRefusedError, check_format
from pmv.acquisition.quarantine import Quarantine, QuarantineError
from pmv.acquisition.records import AcquisitionManifest, ManifestFile
from pmv.acquisition.strict_parse import (
    StrictParseError,
    iter_jsonl,
    parse_csv,
    parse_json,
)
from pmv.integrity import sha256_hex

LIMITS = ExtractionLimits(free_space_margin_bytes=0)


def _dest(tmp_path: Path) -> Path:
    destination = tmp_path / "out"
    destination.mkdir()
    return destination


def _tar_bytes(files: dict[str, bytes], **kwargs: object) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", **kwargs) as archive:  # type: ignore[call-overload]
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _refused(path: Path, destination: Path, match: str) -> None:
    with pytest.raises(ArchiveRefusedError, match=match):
        extract_archive(path, destination, limits=LIMITS)
    assert list(destination.iterdir()) == []


# RT-B6-01: metadata headers are capped before tarfile reads them into memory.


def test_oversized_pax_header_is_refused_by_the_prescan(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo("a.parquet")
        info.pax_headers = {"comment": "x" * (128 * 1024)}
        info.size = 0
        archive.addfile(info, io.BytesIO(b""))
    path = tmp_path / "pax.tar.gz"
    path.write_bytes(gzip.compress(buffer.getvalue()))
    _refused(path, _dest(tmp_path), "metadata header exceeds")


def test_oversized_gnu_long_name_is_refused_by_the_prescan(tmp_path: Path) -> None:
    path = tmp_path / "gnu.tar"
    path.write_bytes(_tar_bytes({"a" * 70_000 + ".csv": b"x\n"}, format=tarfile.GNU_FORMAT))
    _refused(path, _dest(tmp_path), "metadata header exceeds")


def test_pax_size_override_is_refused(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo("a.txt")
        info.pax_headers = {"size": "4"}
        info.size = 4
        archive.addfile(info, io.BytesIO(b"abc\n"))
    path = tmp_path / "size.tar"
    path.write_bytes(buffer.getvalue())
    _refused(path, _dest(tmp_path), "disallowed key")


# RT-B6-02: corrupt, truncated, or trailing-data tars are refused, not shortened.


def test_corrupt_header_in_the_middle_is_refused(tmp_path: Path) -> None:
    data = bytearray(_tar_bytes({"a.txt": b"a\n", "b.txt": b"b\n"}))
    data[1024 + 10] ^= 0xFF  # second member's header (one header + one data block in)
    path = tmp_path / "mid.tar"
    path.write_bytes(bytes(data))
    _refused(path, _dest(tmp_path), "corrupt header")


def test_gzip_checksum_error_is_refused(tmp_path: Path) -> None:
    data = bytearray(gzip.compress(_tar_bytes({"a.txt": b"a\n"})))
    data[-8] ^= 0xFF  # CRC32 trailer
    path = tmp_path / "crc.tar.gz"
    path.write_bytes(bytes(data))
    _refused(path, _dest(tmp_path), "corrupt or unreadable")


def test_truncated_compressed_tar_is_refused(tmp_path: Path) -> None:
    data = gzip.compress(_tar_bytes({"a.txt": b"a\n" * 4000, "b.txt": b"b\n"}))
    path = tmp_path / "cut.tar.gz"
    path.write_bytes(data[: len(data) // 2])
    _refused(path, _dest(tmp_path), r"truncated|corrupt|unreadable")


def test_data_after_the_end_marker_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "trail.tar"
    path.write_bytes(_tar_bytes({"a.txt": b"a\n"}) + b"hidden payload")
    _refused(path, _dest(tmp_path), "after its end marker")


# RT-B6-03: a corrupt zip never leaves partial files behind.


def test_corrupt_zip_member_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "z.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.txt", b"first\n" * 100)
        archive.writestr("b.txt", os.urandom(4096).hex().encode())
    data = bytearray(path.read_bytes())
    second = data.index(b"PK\x03\x04", 4)
    for offset in range(second + 60, second + 120):
        data[offset] ^= 0x5A
    path.write_bytes(bytes(data))
    _refused(path, _dest(tmp_path), "corrupt or unreadable")


# RT-B6-04 and RT-B6-09: JSON memory and value bounds.


def test_json_default_size_cap_is_small() -> None:
    with pytest.raises(StrictParseError, match="size limit"):
        parse_json(b"[" + b"1," * (9 * 1024 * 1024) + b"1]")


def test_iter_jsonl_bounds_each_line() -> None:
    stream = io.BytesIO(b'{"a": 1}\n' + b'{"b": "' + b"x" * 2000 + b'"}\n')
    reader = iter_jsonl(stream, max_line_bytes=100)
    assert next(reader) == {"a": 1}
    with pytest.raises(StrictParseError, match="line 2: exceeds"):
        next(reader)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        (b"[1e999999999]", "exponent"),
        (b"[" + b"9" * 101 + b"]", "digits"),
        (b'["\\ud800"]', "surrogate"),
        (b'{"\\udfff": 1}', "surrogate"),
    ],
)
def test_json_value_bounds(text: bytes, match: str) -> None:
    with pytest.raises(StrictParseError, match=match):
        parse_json(text)


# RT-B6-05 is covered in tests/unit/test_acquisition_hosts.py (rule 8 patterns).

# RT-B6-07: release copies exactly the bytes it verifies.


def _manifest(name: str, data: bytes, file_format: str) -> AcquisitionManifest:
    return AcquisitionManifest.from_document(
        {
            "manifest_version": 1,
            "acquisition_id": "acq_example",
            "approval_id": "appr_example",
            "licence_id": "lic_example",
            "input_licence_ids": ["lic_example"],
            "source_url": "https://files.example.com/history/x",
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
    )


def test_swapped_quarantine_file_is_never_released(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    data = b"a,b\n1,2\n"
    quarantine = Quarantine(quarantine_dir)
    quarantine.receive("a.csv", [data])
    swapped = quarantine_dir / "a.csv"
    swapped.unlink()
    swapped.write_bytes(b"a,b\n6,6\n")
    with pytest.raises(QuarantineError, match="changed after receipt"):
        quarantine.release("a.csv", _manifest("a.csv", data, "csv"), released)
    assert list(released.iterdir()) == []


def test_invalid_utf8_after_the_head_is_refused_on_release(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    data = b"a,b\n" + b"1,2\n" * 1000 + b"\xff\xfe\n"
    quarantine = Quarantine(quarantine_dir)
    quarantine.receive("a.csv", [data])
    with pytest.raises(QuarantineError, match="UTF-8"):
        quarantine.release("a.csv", _manifest("a.csv", data, "csv"), released)
    assert list(released.iterdir()) == []
    assert (quarantine_dir / "a.csv").exists()


# RT-B6-08: more refused signatures.


@pytest.mark.parametrize(
    "head",
    [b"%PDF-1.7", b"\xcf\xfa\xed\xfe\x07\x00", b"7z\xbc\xaf\x27\x1c\x00", b"SQLite format 3"],
)
def test_more_refused_signatures(head: bytes) -> None:
    with pytest.raises(FormatRefusedError):
        check_format("a.txt", FileFormat.TEXT, head[:8], head[-4:])


# RT-B6-10: CSV bare carriage returns and padded header names.


@pytest.mark.parametrize(
    ("data", "match"),
    [(b"a,b\r1,2\r", "carriage return"), (b"a, a\n1,2\n", "padded")],
)
def test_csv_ambiguities(data: bytes, match: str) -> None:
    with pytest.raises(StrictParseError, match=match):
        parse_csv(data)


# RT-B6-11: implicit parent directories take part in the case-folding check.


def test_implicit_parent_case_collision_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "t.tar"
    path.write_bytes(_tar_bytes({"A": b"1", "a/x.csv": b"2"}))
    _refused(path, _dest(tmp_path), "case is ignored")


# RT-B6-12: extracted files must pass the format check.


@pytest.mark.parametrize(
    ("name", "data", "match"),
    [
        ("model.pkl", b"\x80\x04K\x01.", "no allowlisted parse format"),
        ("README", b"hello\n", "no allowlisted parse format"),
        ("a.parquet", b"\x80\x04\x95\x05\x00\x00\x00", "pickle"),
    ],
)
def test_extracted_files_are_format_checked(
    tmp_path: Path, name: str, data: bytes, match: str
) -> None:
    path = tmp_path / "t.tar"
    path.write_bytes(_tar_bytes({"ok.txt": b"fine\n", name: data}))
    _refused(path, _dest(tmp_path), match)


# RT-B6-13: backup and restore locations must be disjoint.


def test_backup_directories_must_be_disjoint(tmp_path: Path) -> None:
    source = tmp_path / "src"
    backup = tmp_path / "backup"
    nested = backup / "restore"
    for directory in (source, backup):
        directory.mkdir()
    data = b"a\n"
    (source / "a.csv").write_bytes(data)
    entry = ManifestFile(name="a.csv", format=FileFormat.CSV, size_bytes=2, sha256=sha256_hex(data))
    with pytest.raises(BackupError, match="disjoint"):
        backup_and_verify_restore([entry], source, backup, backup)
    nested.mkdir()
    with pytest.raises(BackupError, match="disjoint"):
        backup_and_verify_restore([entry], source, backup, nested)


# --- round 2 ------------------------------------------------------------------------------


def _header(name: bytes, kind: bytes, size: int) -> bytes:
    block = bytearray(512)
    block[0 : len(name)] = name
    block[100:108] = b"0000644\x00"
    block[108:116] = b"0000000\x00"
    block[116:124] = b"0000000\x00"
    block[124:136] = f"{size:011o}\x00".encode()
    block[136:148] = b"00000000000\x00"
    block[148:156] = b"        "
    block[156:157] = kind
    block[257:265] = b"ustar\x0000"
    block[148:156] = f"{sum(block):06o}\x00 ".encode()
    return bytes(block)


def _pad(data: bytes) -> bytes:
    return data + bytes(-len(data) % 512)


END = bytes(1024)


def _write(tmp_path: Path, data: bytes, name: str = "x.tar") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


# RT-B6-14: the walker is the only parser; desynchronizing layouts are refused.


def test_directory_entry_with_nonzero_size_is_refused(tmp_path: Path) -> None:
    hidden = _header(b"hidden.txt", b"0", 3) + _pad(b"hi\n")
    data = _header(b"d/", b"5", len(hidden)) + hidden + _header(b"a.txt", b"0", 2) + _pad(b"a\n")
    _refused(_write(tmp_path, data + END), _dest(tmp_path), "directory entry has a non-zero")


def test_pax_record_hidden_in_padding_is_refused(tmp_path: Path) -> None:
    record = b"14 path=a.txt\n"
    padding = bytearray(_pad(record))
    hidden = b"11 size=99\n"
    padding[len(record) : len(record) + len(hidden)] = hidden
    data = _header(b"pax", b"x", len(record)) + bytes(padding)
    data += _header(b"a.txt", b"0", 2) + _pad(b"a\n") + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "non-zero padding")


def test_global_pax_header_is_refused(tmp_path: Path) -> None:
    record = b"14 path=a.txt\n"
    data = _header(b"g", b"g", len(record)) + _pad(record) + _header(b"a.txt", b"0", 2)
    data += _pad(b"a\n") + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "link, device, FIFO")


def test_member_data_padding_must_be_zero(tmp_path: Path) -> None:
    padded = bytearray(_pad(b"a\n"))
    padded[100] = 0x41
    data = _header(b"a.txt", b"0", 2) + bytes(padded) + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "non-zero padding")


def test_non_ustar_header_is_refused(tmp_path: Path) -> None:
    header = bytearray(_header(b"a.txt", b"0", 2))
    header[257:265] = bytes(8)
    header[148:156] = b"        "
    header[148:156] = f"{sum(header):06o}\x00 ".encode()
    data = bytes(header) + _pad(b"a\n") + END
    path = tmp_path / "v7.tar"
    path.write_bytes(gzip.compress(data))
    _refused(path, _dest(tmp_path), "not ustar")


def test_pax_path_names_the_member(tmp_path: Path) -> None:
    record = b"18 path=sub/b.txt\n"
    data = _header(b"pax", b"x", len(record)) + _pad(record)
    data += _header(b"ignored.txt", b"0", 2) + _pad(b"b\n") + END
    destination = _dest(tmp_path)
    extracted = extract_archive(_write(tmp_path, data), destination, limits=LIMITS)
    assert [item.name for item in extracted] == ["sub/b.txt"]


# RT-B6-17: the archive is bound by hash across both passes.


def test_archive_changed_between_passes_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pmv.acquisition import archive as module

    path = _write(tmp_path, _header(b"a.txt", b"0", 2) + _pad(b"a\n") + END)
    original = module._tar_pass
    calls = {"n": 0}

    def changing_pass(*args: object, **kwargs: object) -> tuple[list[object], str]:
        entries, digest = original(*args, **kwargs)  # type: ignore[arg-type]
        calls["n"] += 1
        return entries, digest if calls["n"] == 1 else "0" * 64  # type: ignore[return-value]

    monkeypatch.setattr(module, "_tar_pass", changing_pass)
    _refused(path, _dest(tmp_path), "changed between validation and extraction")


# RT-B6-15: huge exponents raise the parser's own error.


def test_huge_exponent_raises_strict_parse_error() -> None:
    with pytest.raises(StrictParseError):
        parse_json(b"[1e99999999999999999999]")


# RT-B6-16: path patterns are case-insensitive; deeper labels and named domains count.


@pytest.mark.parametrize(
    "url",
    [
        "https://files.example.com/h/API/x.parquet",
        "https://files.example.com/h/V2/x.parquet",
        "https://files.example.com/h/GraphQL",
        "https://files.example.com/h/WS",
        "https://files.example.com/h/x.ndjson",
        "https://files.example.com/h/x.csv/",
        "https://files.example.com/h/X.CSV",
    ],
)
def test_case_insensitive_path_patterns(url: str) -> None:
    from pmv.acquisition.hosts import HostPolicyError, UrlAllowlist

    with pytest.raises(HostPolicyError, match="restricted"):
        UrlAllowlist.build(["https://files.example.com/h/"]).check(url)


@pytest.mark.parametrize(
    "host",
    [
        "eu.api.example.com",
        "x.marketdata.example.com",
        "eth-mainnet.g.alchemy.com",
        "mainnet.infura.io",
        "docs.kalshi.com",
        "kalshi.com",
        "gamma.polymarket.com",
    ],
)
def test_deeper_labels_and_named_domains_are_restricted(host: str) -> None:
    from pmv.acquisition.hosts import host_restriction

    assert host_restriction(host) is not None


# RT-B6-18: extracted text is validated in full.


def test_extracted_csv_with_late_invalid_utf8_is_refused(tmp_path: Path) -> None:
    body = b"a,b\n" + b"1,2\n" * 100 + b"\xff\n"
    data = _header(b"a.csv", b"0", len(body)) + _pad(body) + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "UTF-8")


# Carried: data prepended to a zip is refused.


def test_zip_with_prepended_data_is_refused(tmp_path: Path) -> None:
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("a.txt", b"a\n")
    path = tmp_path / "pre.zip"
    raw = inner.getvalue()
    path.write_bytes(raw[:4] + raw)  # starts with PK\x03\x04, real members are shifted
    _refused(path, _dest(tmp_path), r"before its first member|corrupt|unreadable")
