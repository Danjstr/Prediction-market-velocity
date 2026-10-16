"""Regression tests for the B06 Reliability / Red-Team review of the acquisition tooling.

Each test reproduces a finding in
``research/governance/b06_acquisition_tooling_red_team_review.md`` with a small synthetic
input built in ``tmp_path``, and pins the fix.
"""

import bz2
import gzip
import io
import lzma
import os
import tarfile
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path

import pytest

from pmv.acquisition.archive import ArchiveRefusedError, ExtractionLimits, extract_archive
from pmv.acquisition.backup import BackupError, backup_and_verify_restore
from pmv.acquisition.formats import FileFormat, FormatRefusedError, check_format
from pmv.acquisition.quarantine import Quarantine, QuarantineError
from pmv.acquisition.receipts import ReceiptJournal
from pmv.acquisition.records import AcquisitionManifest, ManifestFile
from pmv.acquisition.strict_parse import (
    StrictParseError,
    iter_jsonl,
    parse_csv,
    parse_json,
)
from pmv.integrity import sha256_hex

LIMITS = ExtractionLimits(free_space_margin_bytes=0)


def _journal(directory: Path) -> ReceiptJournal:
    path = directory / "receipts.jsonl"
    if not path.exists():
        ReceiptJournal.create(path)
    return ReceiptJournal(path)


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
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
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
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
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


# --- round 4 (B06 continuation) -----------------------------------------------------------

# RT-B6-19: a file swapped between passes cannot write beyond the plan.


def test_swap_between_passes_writes_nothing_beyond_the_plan(tmp_path: Path) -> None:
    path = _write(tmp_path, _header(b"a.txt", b"0", 2) + _pad(b"a\n") + END)
    big = b"b\n" * 50_000
    swapped = _header(b"a.txt", b"0", len(big)) + _pad(big) + END
    written = {"bytes": 0}

    def swap_then_report(_destination: Path) -> int:
        path.write_bytes(swapped)  # the second pass reads the substituted archive
        return 1 << 40

    def counting_writer(fd: int, chunk: bytes) -> None:
        written["bytes"] += len(chunk)
        os.write(fd, chunk)

    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError, match="changed between validation and extraction"):
        extract_archive(
            path,
            destination,
            limits=LIMITS,
            disk_free=swap_then_report,
            write_chunk=counting_writer,
        )
    assert written["bytes"] == 0
    assert list(destination.iterdir()) == []


def test_extra_member_after_the_plan_is_refused_before_writing(tmp_path: Path) -> None:
    path = _write(tmp_path, _header(b"a.txt", b"0", 2) + _pad(b"a\n") + END)
    extra = _header(b"a.txt", b"0", 2) + _pad(b"a\n") + _header(b"b.txt", b"0", 2)
    extra += _pad(b"b\n") + END
    written: list[int] = []

    def swap_then_report(_destination: Path) -> int:
        path.write_bytes(extra)
        return 1 << 40

    def recording_writer(fd: int, chunk: bytes) -> None:
        written.append(fd)
        os.write(fd, chunk)

    destination = _dest(tmp_path)
    with pytest.raises(ArchiveRefusedError, match="changed between"):
        extract_archive(
            path,
            destination,
            limits=LIMITS,
            disk_free=swap_then_report,
            write_chunk=recording_writer,
        )
    assert len(written) == 1  # only the planned a.txt was written, then rolled back
    assert list(destination.iterdir()) == []


# RT-B6-20: bytes after the last bzip2 or xz stream must form another stream.


@pytest.mark.parametrize(
    ("suffix", "compress"),
    [("tar.bz2", bz2.compress), ("tar.xz", lzma.compress)],
)
@pytest.mark.parametrize("trailer", [b"junk", b"\x00" * 16, b"BZh9"])
def test_trailing_bytes_after_last_stream_are_refused(
    tmp_path: Path, suffix: str, compress: Callable[[bytes], bytes], trailer: bytes
) -> None:
    data = compress(_header(b"a.txt", b"0", 2) + _pad(b"a\n") + END) + trailer
    _refused(_write(tmp_path, data, f"t.{suffix}"), _dest(tmp_path), "compressed stream")


@pytest.mark.parametrize(
    ("suffix", "compress"),
    [("tar.bz2", bz2.compress), ("tar.xz", lzma.compress)],
)
def test_concatenated_streams_and_clean_end_are_accepted(
    tmp_path: Path, suffix: str, compress: Callable[[bytes], bytes]
) -> None:
    tar = _header(b"a.txt", b"0", 2) + _pad(b"a\n") + END
    data = compress(tar[:512]) + compress(tar[512:])
    extracted = extract_archive(
        _write(tmp_path, data, f"t.{suffix}"), _dest(tmp_path), limits=LIMITS
    )
    assert [item.name for item in extracted] == ["a.txt"]


@pytest.mark.parametrize(
    ("suffix", "compress"),
    [("tar.bz2", bz2.compress), ("tar.xz", lzma.compress)],
)
def test_truncated_or_corrupt_strict_stream_is_refused(
    tmp_path: Path, suffix: str, compress: Callable[[bytes], bytes]
) -> None:
    payload = b"a\n" * 3000
    data = compress(_header(b"a.txt", b"0", len(payload)) + _pad(payload) + END)
    _refused(
        _write(tmp_path, data[: len(data) - 7], f"cut.{suffix}"), _dest(tmp_path), "compressed"
    )
    corrupt = bytearray(data)
    corrupt[len(corrupt) // 2] ^= 0xFF
    other = tmp_path / "other"
    other.mkdir()
    _refused(_write(other, bytes(corrupt), f"bad.{suffix}"), _dest(other), ".")


# RT-B6-21: one unambiguous name per member.


def test_duplicate_pax_keys_are_refused(tmp_path: Path) -> None:
    record = b"14 path=a.txt\n14 path=b.txt\n"
    data = _header(b"pax", b"x", len(record)) + _pad(record)
    data += _header(b"c.txt", b"0", 2) + _pad(b"c\n") + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "repeats a key")


@pytest.mark.parametrize("pax_first", [True, False])
def test_pax_path_with_gnu_long_name_is_refused(tmp_path: Path, pax_first: bool) -> None:
    record = b"16 path=pax.txt\n"
    pax = _header(b"pax", b"x", len(record)) + _pad(record)
    long_name = b"long.txt"
    gnu = _header(b"././@LongLink", b"L", len(long_name)) + _pad(long_name)
    data = (pax + gnu) if pax_first else (gnu + pax)
    data += _header(b"short.txt", b"0", 2) + _pad(b"s\n") + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "both a pax path and a GNU long name")


def test_gnu_magic_ignores_the_ustar_prefix_field(tmp_path: Path) -> None:
    header = bytearray(_header(b"a.txt", b"0", 2))
    header[257:265] = b"ustar  \x00"
    header[345:356] = b"14737327162"  # a GNU atime, not a path prefix
    header[148:156] = b"        "
    header[148:156] = f"{sum(header):06o}\x00 ".encode()
    data = bytes(header) + _pad(b"a\n") + END
    extracted = extract_archive(_write(tmp_path, data), _dest(tmp_path), limits=LIMITS)
    assert [item.name for item in extracted] == ["a.txt"]


# RT-B6-22: the released name must be the inode that was verified.


def test_release_refuses_a_replaced_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pmv.acquisition import quarantine as module

    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    data = b"a,b\n1,2\n"
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [data])
    original = module._link_fd

    def link_then_swap(fd: int, dir_fd: int, name: str) -> None:
        original(fd, dir_fd, name)
        target = released / "a.csv"
        target.unlink()
        target.write_bytes(b"a,b\n6,6\n")

    monkeypatch.setattr(module, "_link_fd", link_then_swap)
    with pytest.raises(QuarantineError, match="not the verified copy"):
        quarantine.release("a.csv", _manifest("a.csv", data, "csv"), released)
    assert (quarantine_dir / "a.csv").exists()
    assert [entry.event.value for entry in quarantine.journal.entries] == ["received"]


# --- round 4b (after the round 4 re-verification) ------------------------------------------

# RT-B6-23: xz means the XZ container only, with a decoder memory limit.


def test_legacy_lzma_stream_after_xz_is_refused(tmp_path: Path) -> None:
    tar = _header(b"a.csv", b"0", 4) + _pad(b"a,b\n") + _header(b"b.csv", b"0", 4)
    tar += _pad(b"c,d\n") + END
    data = lzma.compress(tar[:1024]) + lzma.compress(tar[1024:], format=lzma.FORMAT_ALONE)
    _refused(_write(tmp_path, data, "mixed.tar.xz"), _dest(tmp_path), "compressed stream")


def test_lone_legacy_lzma_named_xz_is_refused(tmp_path: Path) -> None:
    tar = _header(b"a.csv", b"0", 4) + _pad(b"a,b\n") + END
    data = lzma.compress(tar, format=lzma.FORMAT_ALONE)
    _refused(_write(tmp_path, data, "alone.tar.xz"), _dest(tmp_path), "not a supported")


def _xz_with_dict_property(data: bytes, prop: int) -> bytes:
    """Rewrite the LZMA2 dictionary-size byte in the first block header (no big encoder)."""
    out = bytearray(data)
    start = 12  # after the stream header
    size = (out[start] + 1) * 4
    flags = out[start + 1]
    offset = start + 2
    for present in (flags & 0x40, flags & 0x80):  # optional compressed/uncompressed sizes
        if present:
            while out[offset] & 0x80:
                offset += 1
            offset += 1
    assert out[offset : offset + 2] == b"\x21\x01"  # LZMA2, one property byte
    out[offset + 2] = prop
    out[start + size - 4 : start + size] = zlib.crc32(out[start : start + size - 4]).to_bytes(
        4, "little"
    )
    return bytes(out)


def test_xz_decoder_memory_limit_is_enforced(tmp_path: Path) -> None:
    tar = _header(b"a.csv", b"0", 4) + _pad(b"a,b\n") + END
    data = _xz_with_dict_property(lzma.compress(tar, format=lzma.FORMAT_XZ), 39)  # 3 GiB
    _refused(_write(tmp_path, data, "bigdict.tar.xz"), _dest(tmp_path), "compressed stream")


# RT-B6-24: empty names never fall back to another name.


def test_empty_pax_path_is_refused(tmp_path: Path) -> None:
    record = b"8 path=\n"
    data = _header(b"pax", b"x", len(record)) + _pad(record)
    data += _header(b"h.csv", b"0", 4) + _pad(b"a,b\n") + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "empty path")


@pytest.mark.parametrize("long_name", [b"", b"\x00\x00"])
def test_empty_gnu_long_name_is_refused(tmp_path: Path, long_name: bytes) -> None:
    data = _header(b"././@LongLink", b"L", len(long_name)) + _pad(long_name)
    data += _header(b"h.csv", b"0", 4) + _pad(b"a,b\n") + END
    _refused(_write(tmp_path, data), _dest(tmp_path), "long name is empty")


# RT-B6-25: the copy has no name in the destination until it is verified and linked.


def test_unverified_copy_never_has_a_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pmv.acquisition import quarantine as module

    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    data = b"a,b\n1,2\n"
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [data])
    seen: list[list[str]] = []
    original = module._check_copied_format

    def observe(fd: int, name: str, size: int, declared: FileFormat) -> None:
        seen.append(sorted(os.listdir(released)))
        original(fd, name, size, declared)

    monkeypatch.setattr(module, "_check_copied_format", observe)
    quarantine.release("a.csv", _manifest("a.csv", data, "csv"), released)
    assert seen == [[]]
    assert (released / "a.csv").read_bytes() == data


def test_failed_check_leaves_no_file_in_the_destination(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    data = b"a,b\n\x00\n"
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [data])
    with pytest.raises(QuarantineError):
        quarantine.release("a.csv", _manifest("a.csv", data, "csv"), released)
    assert os.listdir(released) == []
    assert (quarantine_dir / "a.csv").exists()


# RT-B6-28: directory entries are made durable in a safe order.


def test_release_fsyncs_directories_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import stat as stat_module

    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    data = b"a,b\n1,2\n"
    quarantine = Quarantine(quarantine_dir, journal=_journal(tmp_path))
    quarantine.receive("a.csv", [data])
    labels = {
        (path.stat().st_dev, path.stat().st_ino): label
        for label, path in (("dest", released), ("quarantine", quarantine_dir))
    }
    events: list[str] = []
    real_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        status = os.fstat(fd)
        label = labels.get((status.st_dev, status.st_ino))
        if stat_module.S_ISDIR(status.st_mode) and label is not None:
            events.append(f"fsync:{label}")
        real_fsync(fd)

    original_append = quarantine.journal.append

    def recording_append(*args: object, **kwargs: object) -> object:
        events.append("journal")
        return original_append(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "fsync", recording_fsync)
    monkeypatch.setattr(quarantine.journal, "append", recording_append)
    quarantine.release("a.csv", _manifest("a.csv", data, "csv"), released)
    assert events == ["fsync:dest", "journal", "fsync:quarantine"]
