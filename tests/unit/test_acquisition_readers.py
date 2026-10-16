"""G-2/G-3/G-5 readers: registry, names, schemas, streaming verification, bounded decoding.

These run the verifiers in-process to test their logic. The same code runs isolated in the
worker; isolation itself is tested in ``test_acquisition_isolation.py``.
"""

import bz2
import gzip
import io
import lzma
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from pmv.acquisition import readers
from pmv.acquisition.formats import FileFormat
from pmv.acquisition.readers import (
    Compression,
    DecodeLimits,
    ReaderError,
    RecordSchema,
    SpecError,
    VerifyLimits,
    check_name,
    check_signature,
    decoded_source,
    split_compressed_name,
    verify_stream,
)
from pmv.acquisition.worker_protocol import RefusalCode
from pmv.integrity import sha256_hex

CSV_SCHEMA = RecordSchema.from_document(
    FileFormat.CSV,
    {
        "columns": [
            {"name": "row", "type": "integer"},
            {"name": "value", "type": "decimal"},
            {"name": "note", "type": "text"},
            {"name": "maybe", "type": "optional_decimal"},
        ]
    },
)
JSONL_SCHEMA = RecordSchema.from_document(
    FileFormat.JSONL,
    {"keys": {"row": ["integer"], "value": ["number", "null"]}, "additional_keys": False},
)
LIMITS = VerifyLimits(max_line_bytes=4096, max_json_bytes=4096)


def _verify(data: bytes, schema: RecordSchema) -> dict[str, object]:
    return verify_stream(io.BytesIO(data), schema, LIMITS)


def _refused(data: bytes, schema: RecordSchema) -> ReaderError:
    with pytest.raises(ReaderError) as caught:
        _verify(data, schema)
    return caught.value


# --- registry and names -------------------------------------------------------------------


def test_parquet_and_dbn_are_registered_but_not_adopted() -> None:
    for file_format in (FileFormat.PARQUET, FileFormat.DBN):
        spec = readers.READERS[file_format]
        assert not spec.adopted
        assert spec.deferral is not None
        assert "owner approval" in spec.deferral
    for file_format in (FileFormat.CSV, FileFormat.JSON, FileFormat.JSONL, FileFormat.TEXT):
        assert readers.READERS[file_format].adopted


def test_unadopted_formats_are_refused_before_reading() -> None:
    schema = RecordSchema.from_document(FileFormat.PARQUET, None)
    with pytest.raises(ReaderError) as caught:
        verify_stream(io.BytesIO(b"PAR1" + b"\x80\x04" + b"PAR1"), schema, LIMITS)
    assert caught.value.code is RefusalCode.READER_NOT_ADOPTED


@pytest.mark.parametrize(
    ("name", "inner", "compression"),
    [
        ("a.csv", "a.csv", Compression.NONE),
        ("a.csv.gz", "a.csv", Compression.GZIP),
        ("a.jsonl.bz2", "a.jsonl", Compression.BZIP2),
        ("a.json.xz", "a.json", Compression.XZ),
        ("a.TXT.GZ", "a.TXT", Compression.GZIP),
    ],
)
def test_compressed_names_split(name: str, inner: str, compression: Compression) -> None:
    assert split_compressed_name(name) == (inner, compression)


@pytest.mark.parametrize("name", ["a.dbn.zst", "a.csv.zstd", "a.csv.lz4", "a.csv.snappy"])
def test_unadopted_codecs_are_refused(name: str) -> None:
    with pytest.raises(SpecError, match="no adopted reader"):
        split_compressed_name(name)


@pytest.mark.parametrize(
    ("name", "file_format", "compression", "match"),
    [
        ("a.gz", FileFormat.CSV, Compression.GZIP, "inner extension"),
        ("a.csv.gz", FileFormat.CSV, Compression.NONE, "compression"),
        ("a.json.gz", FileFormat.CSV, Compression.GZIP, "format"),
        ("a.parquet.gz", FileFormat.PARQUET, Compression.GZIP, "no adopted reader"),
        ("a.csv", FileFormat.JSONL, Compression.NONE, "format"),
    ],
)
def test_names_must_carry_format_and_compression(
    name: str, file_format: FileFormat, compression: Compression, match: str
) -> None:
    with pytest.raises(SpecError, match=match):
        check_name(name, file_format, compression)


@pytest.mark.parametrize(
    ("head", "compression"),
    [
        (b"a,b\n", Compression.GZIP),
        (b"\x1f\x8b\x08\x00", Compression.XZ),
        (b"BZh9", Compression.GZIP),
    ],
)
def test_compressed_signature_must_match(head: bytes, compression: Compression) -> None:
    suffix = readers.COMPRESSION_SUFFIXES[compression]
    with pytest.raises(SpecError, match="signature"):
        check_signature("a.csv" + suffix, FileFormat.CSV, compression, head, b"")


def test_plain_signature_refuses_pickle_and_gzip() -> None:
    with pytest.raises(SpecError, match="pickle"):
        check_signature("a.csv", FileFormat.CSV, Compression.NONE, b"\x80\x04\x95", b"")
    with pytest.raises(SpecError, match="gzip"):
        check_signature("a.csv", FileFormat.CSV, Compression.NONE, b"\x1f\x8b\x08", b"")


# --- schemas ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("file_format", "document", "match"),
    [
        (FileFormat.CSV, None, "needs an expected schema"),
        (FileFormat.CSV, {"columns": []}, "non-empty"),
        (FileFormat.CSV, {"columns": [{"name": " a", "type": "text"}]}, "padded"),
        (FileFormat.CSV, {"columns": [{"name": "a", "type": "float"}]}, "unknown CSV"),
        (
            FileFormat.CSV,
            {"columns": [{"name": "a", "type": "text"}, {"name": "a", "type": "text"}]},
            "unique",
        ),
        (FileFormat.CSV, {"columns": [{"name": "a", "type": "text"}], "x": 1}, "exactly"),
        (FileFormat.JSONL, {"keys": {}, "additional_keys": False}, "non-empty"),
        (FileFormat.JSONL, {"keys": {"a": ["float"]}, "additional_keys": False}, "unknown JSON"),
        (FileFormat.JSONL, {"keys": {"a": ["string"]}, "additional_keys": "no"}, "boolean"),
        (FileFormat.JSON, {"keys": {"a": ["string"]}, "additional_keys": False}, "exactly"),
        (FileFormat.TEXT, {"columns": []}, "only CSV"),
    ],
)
def test_malformed_schemas_are_refused(
    file_format: FileFormat, document: object, match: str
) -> None:
    with pytest.raises(SpecError, match=match):
        RecordSchema.from_document(file_format, document)


def test_schema_document_round_trips_and_hash_is_stable() -> None:
    again = RecordSchema.from_document(FileFormat.CSV, CSV_SCHEMA.document())
    assert again == CSV_SCHEMA
    assert again.sha256() == CSV_SCHEMA.sha256()


# --- CSV ----------------------------------------------------------------------------------

GOOD_CSV = b'row,value,note,maybe\n0,1.5,"a, b",\n1,-2,"multi\nline",3.25\n'


def test_csv_verifies_and_reports_counts_and_hashes_only() -> None:
    summary = _verify(GOOD_CSV, CSV_SCHEMA)
    assert summary["records"] == 2
    assert summary["decoded_bytes"] == len(GOOD_CSV)
    assert summary["decoded_sha256"] == sha256_hex(GOOD_CSV)
    assert summary["schema_sha256"] == CSV_SCHEMA.sha256()
    assert b"1.5" not in repr(summary).encode()


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"row,value,note\n0,1,x\n", RefusalCode.SCHEMA_MISMATCH),
        (b"value,row,note,maybe\n1,0,x,\n", RefusalCode.SCHEMA_MISMATCH),
        (b"row,value,note,maybe\n0,1,x\n", RefusalCode.PARSE_FAILED),
        (b"row,value,note,maybe\nx,1,x,\n", RefusalCode.TYPE_MISMATCH),
        (b"row,value,note,maybe\n0,1e5,x,\n", RefusalCode.TYPE_MISMATCH),
        (b"row,value,note,maybe\n0,NaN,x,\n", RefusalCode.TYPE_MISMATCH),
        (b"row,value,note,maybe\n0,1,x,abc\n", RefusalCode.TYPE_MISMATCH),
        (b"row,value,note,maybe\r\n0,1,x,\n", RefusalCode.PARSE_FAILED),
        (b"row,value,note,maybe\n0,1,x\r,\n", RefusalCode.PARSE_FAILED),
        (b"\xef\xbb\xbfrow,value,note,maybe\n", RefusalCode.FORMAT_REFUSED),
        (b"row,value,note,maybe\n0,1,\x00,\n", RefusalCode.PARSE_FAILED),
        (b"row,value,note,maybe\n0,1,\xff,\n", RefusalCode.PARSE_FAILED),
        (b'row,value,note,maybe\n0,1,"x"y,\n', RefusalCode.PARSE_FAILED),
        (b"", RefusalCode.SCHEMA_MISMATCH),
    ],
)
def test_csv_refusals(data: bytes, code: RefusalCode) -> None:
    assert _refused(data, CSV_SCHEMA).code is code


def test_csv_line_cap_bounds_memory() -> None:
    long_line = b"row,value,note,maybe\n0,1," + b"x" * 5000 + b",\n"
    assert _refused(long_line, CSV_SCHEMA).code is RefusalCode.PARSE_FAILED


def test_refusals_carry_a_record_number_never_content() -> None:
    error = _refused(b"row,value,note,maybe\n0,1,ok,\n1,SECRETVALUE,x,\n", CSV_SCHEMA)
    assert error.record == 2
    assert "SECRET" not in str(error)


# --- JSON and JSONL -----------------------------------------------------------------------


def test_jsonl_verifies() -> None:
    summary = _verify(b'{"row":0,"value":1.5}\n{"row":1,"value":null}\n', JSONL_SCHEMA)
    assert summary["records"] == 2


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b'{"row":0}\n', RefusalCode.SCHEMA_MISMATCH),
        (b'{"row":0,"value":1,"extra":2}\n', RefusalCode.SCHEMA_MISMATCH),
        (b'{"row":"0","value":1}\n', RefusalCode.TYPE_MISMATCH),
        (b'{"row":true,"value":1}\n', RefusalCode.TYPE_MISMATCH),
        (b"[1,2]\n", RefusalCode.SCHEMA_MISMATCH),
        (b'{"row":0,"value":NaN}\n', RefusalCode.PARSE_FAILED),
        (b'{"row":0,"row":1,"value":1}\n', RefusalCode.PARSE_FAILED),
        (b'{"row":0,"value":1}', RefusalCode.PARSE_FAILED),
        (b'{"row":0,"value":1}\n\n', RefusalCode.PARSE_FAILED),
    ],
)
def test_jsonl_refusals(data: bytes, code: RefusalCode) -> None:
    assert _refused(data, JSONL_SCHEMA).code is code


def test_json_object_and_array_of_objects() -> None:
    keys = {"keys": {"a": ["string"]}, "additional_keys": True}
    obj = RecordSchema.from_document(FileFormat.JSON, {**keys, "top_level": "object"})
    arr = RecordSchema.from_document(FileFormat.JSON, {**keys, "top_level": "array_of_objects"})
    assert _verify(b'{"a":"x","b":1}', obj)["records"] == 1
    assert _verify(b'[{"a":"x"},{"a":"y"}]', arr)["records"] == 2
    assert _refused(b'[{"a":"x"}]', obj).code is RefusalCode.SCHEMA_MISMATCH
    assert _refused(b'{"a":"x"}', arr).code is RefusalCode.SCHEMA_MISMATCH
    assert _refused(b'[{"a":1}]', arr).code is RefusalCode.TYPE_MISMATCH


def test_json_document_cap() -> None:
    schema = RecordSchema.from_document(
        FileFormat.JSON,
        {"keys": {"a": ["string"]}, "additional_keys": False, "top_level": "object"},
    )
    big = b'{"a":"' + b"x" * 5000 + b'"}'
    assert _refused(big, schema).code is RefusalCode.DECODED_TOO_LARGE


def test_text_is_strict_utf8() -> None:
    schema = RecordSchema.from_document(FileFormat.TEXT, None)
    assert _verify(b"line one\nline two\n", schema)["records"] == 2
    assert _refused(b"ok\n\xc3\x28\n", schema).code is RefusalCode.PARSE_FAILED
    assert _refused(b"#!/bin/sh\n", schema).code is RefusalCode.FORMAT_REFUSED


# --- bounded decoding (G-5) ---------------------------------------------------------------


def _source(tmp_path: Path, data: bytes, compression: Compression, limits: DecodeLimits) -> bytes:
    path = tmp_path / "input"
    path.write_bytes(data)
    fd = os.open(path, os.O_RDONLY)
    try:
        source, raw = decoded_source(fd, compression, len(data), limits)
        out = b""
        while chunk := source.read(65536):
            out += chunk
        raw.drain()
        assert raw.size == len(data)
        assert raw.digest.hexdigest() == sha256_hex(data)
        return out
    finally:
        os.close(fd)


PAYLOAD = b"row,value\n" + b"1,2\n" * 1000
CODECS: dict[Compression, Callable[[bytes], bytes]] = {
    Compression.GZIP: gzip.compress,
    Compression.BZIP2: bz2.compress,
    Compression.XZ: lzma.compress,
}


@pytest.mark.parametrize("compression", list(CODECS))
def test_each_codec_round_trips(tmp_path: Path, compression: Compression) -> None:
    data = CODECS[compression](PAYLOAD)
    assert _source(tmp_path, data, compression, DecodeLimits()) == PAYLOAD


@pytest.mark.parametrize("compression", list(CODECS))
def test_decompression_bomb_is_refused_by_ratio(tmp_path: Path, compression: Compression) -> None:
    bomb = CODECS[compression](bytes(20 * 1024 * 1024))
    assert 20 * 1024 * 1024 / len(bomb) >= 1000  # the A-4 fixture: at least 1000:1
    with pytest.raises(ReaderError) as caught:
        _source(tmp_path, bomb, compression, DecodeLimits(max_ratio=100))
    assert caught.value.code is RefusalCode.EXPANSION_RATIO_EXCEEDED


def test_decoded_size_cap(tmp_path: Path) -> None:
    data = gzip.compress(PAYLOAD)
    with pytest.raises(ReaderError) as caught:
        _source(tmp_path, data, Compression.GZIP, DecodeLimits(max_decoded_bytes=100))
    assert caught.value.code is RefusalCode.DECODED_TOO_LARGE


@pytest.mark.parametrize(
    ("compression", "mangle"),
    [
        (Compression.GZIP, lambda d: d[:-6]),
        (Compression.GZIP, lambda d: d + b"garbage"),
        (Compression.GZIP, lambda d: d[:-8] + bytes([d[-8] ^ 1]) + d[-7:]),
        (Compression.BZIP2, lambda d: d + b"garbage"),
        (Compression.BZIP2, lambda d: d[:-4]),
        (Compression.XZ, lambda d: d + b"garbage"),
        (Compression.XZ, lambda d: d[: len(d) // 2]),
    ],
)
def test_corrupt_truncated_or_trailing_streams_are_refused(
    tmp_path: Path, compression: Compression, mangle: Callable[[bytes], bytes]
) -> None:
    data = mangle(CODECS[compression](PAYLOAD))
    with pytest.raises(ReaderError) as caught:
        _source(tmp_path, data, compression, DecodeLimits())
    assert caught.value.code is RefusalCode.COMPRESSION_REFUSED


def test_legacy_lzma_is_refused_as_xz(tmp_path: Path) -> None:
    data = lzma.compress(PAYLOAD, format=lzma.FORMAT_ALONE)
    with pytest.raises(ReaderError):
        _source(tmp_path, data, Compression.XZ, DecodeLimits())
