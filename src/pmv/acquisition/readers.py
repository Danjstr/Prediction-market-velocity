"""Reader registry, expected schemas, and streaming verifiers for acquired files (G-2, G-3, G-5).

**Registry.** Every allowlisted parse format has one registered reader, with a fixed
identity (name and version) and a recorded adoption status:
- CSV, JSON, JSONL, and plain text are read by project code on the Python standard
  library only (``strict_parse`` rules; no third-party package);
- Parquet and DBN are **not adopted**. Reading them needs a third-party package, and
  adding a parser dependency needs owner approval first (``docs/acquisition_readiness.md``,
  "Reader dependencies awaiting owner approval"). Until then every Parquet or DBN file is
  refused (``RefusalCode.READER_NOT_ADOPTED``); its bytes are never interpreted.

**Compression.** A single compressed file (``.csv.gz``, ``.jsonl.bz2``, ``.json.xz``,
``.txt.gz``) is an encoding of one allowlisted format, not a container. gzip, bzip2, and xz
are decoded with the standard library, strictly (every byte after a stream must start
another complete stream; xz container only, with a decoder memory limit), and bounded by a
decoded-size cap and an expansion-ratio cap. zstd needs a third-party package and is not
adopted. Compressed Parquet and DBN are refused with their formats.

**Schemas.** A CSV, JSON, or JSONL file must declare its expected schema
(``RecordSchema``): exact ordered CSV columns with per-column value types, or required
JSON object keys with allowed value types. A mismatch fails the whole file. Values are
checked, never coerced.

**Verifiers** (``verify_stream``) run only inside the isolated worker (``parse_worker``).
They stream the decoded bytes with bounded lines and return a summary of counts and
hashes. A summary never contains a value from the file.
"""

import bz2
import csv
import gzip
import hashlib
import lzma
import re
import zlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import IO, Final, Protocol

from pmv.acquisition.archive import (
    ArchiveRefusedError,
    _HashingReader,
    _StrictStreams,
    _xz_decompressor,
)
from pmv.acquisition.formats import (
    EXTENSIONS,
    FileFormat,
    FormatRefusedError,
    check_format,
    extension_of,
)
from pmv.acquisition.strict_parse import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_LINE_BYTES,
    StrictParseError,
    iter_jsonl,
    parse_decimal_field,
    parse_json,
)
from pmv.acquisition.worker_protocol import RefusalCode
from pmv.integrity import canonical_json, sha256_hex

READER_REGISTRY_VERSION: Final = 1
_CHUNK: Final = 1024 * 1024
_INTEGER: Final = re.compile(r"-?(0|[1-9][0-9]{0,99})")
_COLUMN: Final = re.compile(r"[A-Za-z0-9_.:/ -]{1,128}")
_MAX_COLUMNS: Final = 1024


class Compression(StrEnum):
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    XZ = "xz"


COMPRESSION_SUFFIXES: Final[dict[Compression, str]] = {
    Compression.GZIP: ".gz",
    Compression.BZIP2: ".bz2",
    Compression.XZ: ".xz",
}
COMPRESSION_MAGIC: Final[dict[Compression, bytes]] = {
    Compression.GZIP: b"\x1f\x8b",
    Compression.BZIP2: b"BZh",
    Compression.XZ: b"\xfd7zXZ\x00",
}
# Compression a third-party package would be needed for. Refused, never guessed.
UNADOPTED_COMPRESSION: Final = frozenset({"zstd", "zst", "snappy", "lz4", "brotli"})


@dataclass(frozen=True, slots=True)
class ReaderSpec:
    """The registered reader for one format: identity and adoption status."""

    reader: str
    version: int
    adopted: bool
    implementation: str
    deferral: str | None = None

    def identity(self) -> dict[str, object]:
        return {
            "reader": self.reader,
            "version": self.version,
            "adopted": self.adopted,
            "implementation": self.implementation,
            "registry_version": READER_REGISTRY_VERSION,
        }


READERS: Final[dict[FileFormat, ReaderSpec]] = {
    FileFormat.CSV: ReaderSpec("pmv.strict_csv", 1, True, "python-stdlib csv, strict"),
    FileFormat.JSON: ReaderSpec("pmv.strict_json", 1, True, "python-stdlib json, strict"),
    FileFormat.JSONL: ReaderSpec("pmv.strict_jsonl", 1, True, "python-stdlib json, strict"),
    FileFormat.TEXT: ReaderSpec("pmv.strict_text", 1, True, "strict UTF-8 decoder"),
    FileFormat.PARQUET: ReaderSpec(
        "parquet",
        0,
        False,
        "none",
        "needs a third-party reader (candidate: pyarrow); owner approval required",
    ),
    FileFormat.DBN: ReaderSpec(
        "dbn",
        0,
        False,
        "none",
        "needs a third-party reader (candidate: databento-dbn); owner approval required",
    ),
}

SCHEMA_FORMATS: Final = frozenset({FileFormat.CSV, FileFormat.JSON, FileFormat.JSONL})


class ReaderError(Exception):
    """A file failed verification. Carries a closed refusal code and a record number."""

    def __init__(self, code: RefusalCode, record: int | None = None) -> None:
        super().__init__(code.value if record is None else f"{code.value} at record {record}")
        self.code = code
        self.record = record


class SpecError(Exception):
    """A reader specification (format, compression, or schema) is malformed or refused."""


# --- names and compression ----------------------------------------------------------------


def split_compressed_name(name: str) -> tuple[str, Compression]:
    """Return ``(inner_name, compression)`` for a file name. Unadopted codecs are refused."""
    lowered = name.lower()
    for codec in UNADOPTED_COMPRESSION:
        if lowered.endswith("." + codec):
            raise SpecError(f"compression {codec!r} has no adopted reader")
    for compression, suffix in COMPRESSION_SUFFIXES.items():
        if lowered.endswith(suffix):
            inner = name[: -len(suffix)]
            if not inner or extension_of(inner) == "":
                raise SpecError("a compressed file name must keep its inner extension")
            return inner, compression
    return name, Compression.NONE


def check_name(name: str, declared: FileFormat, compression: Compression) -> str:
    """Check that ``name`` carries the declared format and compression; return the inner name."""
    inner, found = split_compressed_name(name)
    if found is not compression:
        raise SpecError("file name does not match the declared compression")
    if extension_of(inner) not in EXTENSIONS[declared]:
        raise SpecError("file name does not match the declared format")
    if compression is not Compression.NONE and not READERS[declared].adopted:
        raise SpecError("compressed files of this format have no adopted reader")
    return inner


def check_signature(
    name: str, declared: FileFormat, compression: Compression, head: bytes, tail: bytes
) -> None:
    """Validate the file's leading bytes against its declared format before any dispatch."""
    inner = check_name(name, declared, compression)
    if compression is Compression.NONE:
        try:
            check_format(inner, declared, head, tail)
        except FormatRefusedError as error:
            raise SpecError(f"signature check failed: {error}") from None
    elif not head.startswith(COMPRESSION_MAGIC[compression]):
        raise SpecError("content does not start with the declared compression signature")


# --- schemas ------------------------------------------------------------------------------


class CsvType(StrEnum):
    TEXT = "text"
    NONEMPTY_TEXT = "nonempty_text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    OPTIONAL_INTEGER = "optional_integer"
    OPTIONAL_DECIMAL = "optional_decimal"


class JsonType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"
    OBJECT = "object"
    ARRAY = "array"


class JsonTopLevel(StrEnum):
    OBJECT = "object"
    ARRAY_OF_OBJECTS = "array_of_objects"


@dataclass(frozen=True, slots=True)
class RecordSchema:
    """The expected structure of one CSV, JSON, or JSONL file."""

    file_format: FileFormat
    columns: tuple[tuple[str, CsvType], ...] = ()
    keys: tuple[tuple[str, frozenset[JsonType]], ...] = ()
    additional_keys: bool = False
    top_level: JsonTopLevel | None = None

    @classmethod
    def from_document(cls, file_format: FileFormat, document: object) -> "RecordSchema":
        if file_format not in SCHEMA_FORMATS:
            if document is not None:
                raise SpecError("only CSV, JSON, and JSONL files take a schema")
            return cls(file_format=file_format)
        if not isinstance(document, Mapping):
            raise SpecError("a CSV, JSON, or JSONL file needs an expected schema")
        if file_format is FileFormat.CSV:
            return cls._csv(document)
        return cls._json(file_format, document)

    @classmethod
    def _csv(cls, document: Mapping[str, object]) -> "RecordSchema":
        if set(document) != {"columns"}:
            raise SpecError("a CSV schema has exactly the key 'columns'")
        raw = document["columns"]
        if not isinstance(raw, list) or not raw or len(raw) > _MAX_COLUMNS:
            raise SpecError("CSV columns must be a non-empty list")
        columns: list[tuple[str, CsvType]] = []
        for item in raw:
            if not isinstance(item, Mapping) or set(item) != {"name", "type"}:
                raise SpecError("each CSV column has exactly 'name' and 'type'")
            name, kind = item["name"], item["type"]
            if not isinstance(name, str) or _COLUMN.fullmatch(name) is None:
                raise SpecError("CSV column names are short plain text")
            if name != name.strip():
                raise SpecError("CSV column names must not be padded")
            try:
                columns.append((name, CsvType(kind if isinstance(kind, str) else "")))
            except ValueError:
                raise SpecError("unknown CSV column type") from None
        if len({name for name, _ in columns}) != len(columns):
            raise SpecError("CSV column names must be unique")
        return cls(file_format=FileFormat.CSV, columns=tuple(columns))

    @classmethod
    def _json(cls, file_format: FileFormat, document: Mapping[str, object]) -> "RecordSchema":
        expected = {"keys", "additional_keys"}
        if file_format is FileFormat.JSON:
            expected.add("top_level")
        if set(document) != expected:
            raise SpecError(f"a {file_format.value} schema has exactly the keys {sorted(expected)}")
        raw = document["keys"]
        if not isinstance(raw, Mapping) or not raw or len(raw) > _MAX_COLUMNS:
            raise SpecError("schema keys must be a non-empty object")
        keys: list[tuple[str, frozenset[JsonType]]] = []
        for key, allowed in raw.items():
            if not isinstance(key, str) or _COLUMN.fullmatch(key) is None:
                raise SpecError("schema key names are short plain text")
            if not isinstance(allowed, list) or not allowed:
                raise SpecError("each schema key lists its allowed types")
            try:
                types = frozenset(
                    JsonType(item if isinstance(item, str) else "") for item in allowed
                )
            except ValueError:
                raise SpecError("unknown JSON value type") from None
            if len(types) != len(allowed):
                raise SpecError("a schema key repeats a type")
            keys.append((key, types))
        additional = document["additional_keys"]
        if not isinstance(additional, bool):
            raise SpecError("additional_keys must be a boolean")
        top: JsonTopLevel | None = None
        if file_format is FileFormat.JSON:
            try:
                top = JsonTopLevel(_text(document["top_level"]))
            except ValueError:
                raise SpecError("top_level must be 'object' or 'array_of_objects'") from None
        return cls(
            file_format=file_format,
            keys=tuple(sorted(keys)),
            additional_keys=additional,
            top_level=top,
        )

    def document(self) -> dict[str, object] | None:
        """The canonical document form (the inverse of ``from_document``)."""
        if self.file_format is FileFormat.CSV:
            return {"columns": [{"name": n, "type": t.value} for n, t in self.columns]}
        if self.file_format in SCHEMA_FORMATS:
            result: dict[str, object] = {
                "keys": {k: sorted(t.value for t in types) for k, types in self.keys},
                "additional_keys": self.additional_keys,
            }
            if self.top_level is not None:
                result["top_level"] = self.top_level.value
            return result
        return None

    def sha256(self) -> str:
        return sha256_hex(canonical_json({"schema": self.document()}))


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _csv_value_ok(value: str, kind: CsvType) -> bool:
    if kind is CsvType.TEXT:
        return True
    if kind is CsvType.NONEMPTY_TEXT:
        return value != ""
    if value == "" and kind in (CsvType.OPTIONAL_INTEGER, CsvType.OPTIONAL_DECIMAL):
        return True
    if kind in (CsvType.INTEGER, CsvType.OPTIONAL_INTEGER):
        return _INTEGER.fullmatch(value) is not None
    try:
        parse_decimal_field(value)
    except StrictParseError:
        return False
    return True


def _json_type(value: object) -> JsonType:
    if value is None:
        return JsonType.NULL
    if isinstance(value, bool):
        return JsonType.BOOLEAN
    if isinstance(value, int):
        return JsonType.INTEGER
    if isinstance(value, Decimal):
        return JsonType.NUMBER
    if isinstance(value, str):
        return JsonType.STRING
    if isinstance(value, dict):
        return JsonType.OBJECT
    return JsonType.ARRAY


def _check_object(value: object, schema: RecordSchema, record: int) -> None:
    if not isinstance(value, dict):
        raise ReaderError(RefusalCode.SCHEMA_MISMATCH, record)
    expected = dict(schema.keys)
    if not schema.additional_keys and set(value) - set(expected):
        raise ReaderError(RefusalCode.SCHEMA_MISMATCH, record)
    for key, allowed in expected.items():
        if key not in value:
            raise ReaderError(RefusalCode.SCHEMA_MISMATCH, record)
        found = _json_type(value[key])
        if found not in allowed and not (found is JsonType.INTEGER and JsonType.NUMBER in allowed):
            raise ReaderError(RefusalCode.TYPE_MISMATCH, record)


# --- streaming ----------------------------------------------------------------------------


class ByteSource(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class LineReader:
    """``readline(limit)`` over a byte source, hashing and counting what it yields."""

    def __init__(self, source: ByteSource) -> None:
        self._source = source
        self._buffer = b""
        self._eof = False
        self.digest = hashlib.sha256()
        self.size = 0

    def _fill(self) -> bool:
        if self._eof:
            return False
        chunk = self._source.read(_CHUNK)
        if not chunk:
            self._eof = True
            return False
        self._buffer += chunk
        return True

    def peek(self, count: int) -> bytes:
        """Return up to ``count`` leading bytes without consuming them."""
        while len(self._buffer) < count and self._fill():
            pass
        return self._buffer[:count]

    def readline(self, limit: int = -1, /) -> bytes:
        bound = limit if limit > 0 else len(self._buffer) + _CHUNK
        while True:
            newline = self._buffer.find(b"\n", 0, bound)
            if newline >= 0:
                return self._take(newline + 1)
            if len(self._buffer) >= bound:
                return self._take(bound)
            if not self._fill():
                return self._take(len(self._buffer))

    def _take(self, count: int) -> bytes:
        line, self._buffer = self._buffer[:count], self._buffer[count:]
        self.digest.update(line)
        self.size += len(line)
        return line


def _decode_line(raw: bytes, record: int) -> str:
    if b"\x00" in raw:
        raise ReaderError(RefusalCode.PARSE_FAILED, record)
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ReaderError(RefusalCode.PARSE_FAILED, record) from None


def _physical_lines(lines: LineReader, max_line_bytes: int) -> Iterator[str]:
    """Strict UTF-8 physical lines with one consistent terminator and no bare CR."""
    terminator: bytes | None = None
    number = 0
    while raw := lines.readline(max_line_bytes + 1):
        number += 1
        if len(raw) > max_line_bytes:
            raise ReaderError(RefusalCode.PARSE_FAILED, number)
        if number == 1 and raw.startswith(b"\xef\xbb\xbf"):
            raise ReaderError(RefusalCode.FORMAT_REFUSED, number)
        if raw.endswith(b"\n"):
            ending = b"\r\n" if raw.endswith(b"\r\n") else b"\n"
            if terminator is None:
                terminator = ending
            elif ending != terminator:
                raise ReaderError(RefusalCode.PARSE_FAILED, number)
            body = raw[: -len(ending)]
        else:
            body = raw
        if b"\r" in body:
            raise ReaderError(RefusalCode.PARSE_FAILED, number)
        yield _decode_line(raw, number)


def _verify_csv(lines: LineReader, schema: RecordSchema, max_line_bytes: int) -> int:
    csv.field_size_limit(max_line_bytes)
    reader = csv.reader(_physical_lines(lines, max_line_bytes), strict=True)
    names = tuple(name for name, _ in schema.columns)
    kinds = tuple(kind for _, kind in schema.columns)
    try:
        header = next(reader, None)
        if header is None or tuple(header) != names:
            raise ReaderError(RefusalCode.SCHEMA_MISMATCH, 0)
        records = 0
        for row in reader:
            records += 1
            if len(row) != len(names):
                raise ReaderError(RefusalCode.PARSE_FAILED, records)
            for value, kind in zip(row, kinds, strict=True):
                if not _csv_value_ok(value, kind):
                    raise ReaderError(RefusalCode.TYPE_MISMATCH, records)
    except csv.Error:
        raise ReaderError(RefusalCode.PARSE_FAILED, reader.line_num) from None
    return records


def _verify_jsonl(lines: LineReader, schema: RecordSchema, max_line_bytes: int) -> int:
    records = 0
    try:
        for value in iter_jsonl(_as_io(lines), max_line_bytes=max_line_bytes):
            records += 1
            _check_object(value, schema, records)
    except StrictParseError:
        raise ReaderError(RefusalCode.PARSE_FAILED, records + 1) from None
    return records


def _verify_json(lines: LineReader, schema: RecordSchema, max_json_bytes: int) -> int:
    data = lines.readline(max_json_bytes + 1)
    while len(data) <= max_json_bytes and (more := lines.readline(max_json_bytes + 1)):
        data += more
    if len(data) > max_json_bytes:
        raise ReaderError(RefusalCode.DECODED_TOO_LARGE)
    try:
        value = parse_json(data, max_bytes=max_json_bytes)
    except StrictParseError:
        raise ReaderError(RefusalCode.PARSE_FAILED, 1) from None
    if schema.top_level is JsonTopLevel.OBJECT:
        _check_object(value, schema, 1)
        return 1
    if not isinstance(value, list):
        raise ReaderError(RefusalCode.SCHEMA_MISMATCH, 1)
    for index, item in enumerate(value, start=1):
        _check_object(item, schema, index)
    return len(value)


def _verify_text(lines: LineReader, max_line_bytes: int) -> int:
    count = 0
    while raw := lines.readline(max_line_bytes + 1):
        count += 1
        if len(raw) > max_line_bytes:
            raise ReaderError(RefusalCode.PARSE_FAILED, count)
        if count == 1 and raw.startswith(b"\xef\xbb\xbf"):
            raise ReaderError(RefusalCode.FORMAT_REFUSED, count)
        _decode_line(raw, count)
    return count


class _IoAdapter:
    def __init__(self, lines: LineReader) -> None:
        self._lines = lines

    def readline(self, size: int = -1, /) -> bytes:
        return self._lines.readline(size)


def _as_io(lines: LineReader) -> IO[bytes]:
    return _IoAdapter(lines)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class VerifyLimits:
    max_line_bytes: int = DEFAULT_MAX_LINE_BYTES
    max_json_bytes: int = DEFAULT_MAX_BYTES

    def __post_init__(self) -> None:
        for value in (self.max_line_bytes, self.max_json_bytes):
            if type(value) is not int or not (1024 <= value <= 64 * 1024 * 1024):
                raise SpecError("reader limits must be integers between 1 KiB and 64 MiB")

    def document(self) -> dict[str, int]:
        return {"max_line_bytes": self.max_line_bytes, "max_json_bytes": self.max_json_bytes}


def verify_stream(
    source: ByteSource, schema: RecordSchema, limits: VerifyLimits
) -> dict[str, object]:
    """Verify one decoded file completely. Return a value-free summary or raise ReaderError."""
    spec = READERS[schema.file_format]
    if not spec.adopted:
        raise ReaderError(RefusalCode.READER_NOT_ADOPTED)
    lines = LineReader(source)
    try:
        check_format(
            "verify" + EXTENSIONS[schema.file_format][0], schema.file_format, lines.peek(8), b""
        )
    except FormatRefusedError:
        raise ReaderError(RefusalCode.FORMAT_REFUSED, 1) from None
    if schema.file_format is FileFormat.CSV:
        records = _verify_csv(lines, schema, limits.max_line_bytes)
    elif schema.file_format is FileFormat.JSONL:
        records = _verify_jsonl(lines, schema, limits.max_line_bytes)
    elif schema.file_format is FileFormat.JSON:
        records = _verify_json(lines, schema, limits.max_json_bytes)
    else:
        records = _verify_text(lines, limits.max_line_bytes)
    if lines.readline(1):
        raise ReaderError(RefusalCode.PARSE_FAILED)
    return {
        "format": schema.file_format.value,
        "records": records,
        "decoded_bytes": lines.size,
        "decoded_sha256": lines.digest.hexdigest(),
        "schema_sha256": schema.sha256(),
        "reader": spec.identity(),
        "limits": limits.document(),
    }


# --- bounded decoding of single compressed files -------------------------------------------


@dataclass(frozen=True, slots=True)
class DecodeLimits:
    """Caps on what one file may decode to (G-5). Both apply; the smaller one binds."""

    max_decoded_bytes: int = 8 * 1024**3
    max_ratio: int = 200

    def __post_init__(self) -> None:
        if type(self.max_decoded_bytes) is not int or self.max_decoded_bytes <= 0:
            raise SpecError("max_decoded_bytes must be a positive integer")
        if type(self.max_ratio) is not int or not (1 <= self.max_ratio <= 10_000):
            raise SpecError("max_ratio must be an integer between 1 and 10000")

    def document(self) -> dict[str, int]:
        return {"max_decoded_bytes": self.max_decoded_bytes, "max_ratio": self.max_ratio}


class _Bounded:
    """Decoded byte source that refuses to exceed its size or expansion-ratio cap."""

    def __init__(self, inner: ByteSource, input_size: int, limits: DecodeLimits) -> None:
        self._inner = inner
        self._ratio_cap = limits.max_ratio * max(input_size, 1)
        self._size_cap = limits.max_decoded_bytes
        self.total = 0

    def read(self, size: int = -1, /) -> bytes:
        try:
            data = self._inner.read(_CHUNK if size is None or size < 0 else size)
        except ArchiveRefusedError:
            raise ReaderError(RefusalCode.COMPRESSION_REFUSED) from None
        except (OSError, EOFError, zlib.error, lzma.LZMAError, ValueError):
            raise ReaderError(RefusalCode.COMPRESSION_REFUSED) from None
        self.total += len(data)
        if self.total > self._size_cap:
            raise ReaderError(RefusalCode.DECODED_TOO_LARGE)
        if self.total > self._ratio_cap:
            raise ReaderError(RefusalCode.EXPANSION_RATIO_EXCEEDED)
        return data


class RawReader(_HashingReader):
    """The undecoded input, hashed and counted, so a verification binds to exact bytes."""

    def __init__(self, fd: int) -> None:
        super().__init__(fd)
        self.size = 0

    def read(self, size: int = -1, /) -> bytes:
        data = super().read(size)
        self.size += len(data)
        return data


def decoded_source(
    fd: int, compression: Compression, input_size: int, limits: DecodeLimits
) -> tuple[ByteSource, RawReader]:
    """A bounded, strict source of the decoded bytes of the file open on ``fd``.

    Reads from the descriptor's current offset. The second item is the raw reader; drain it
    after decoding to hash every input byte, including any the decoder did not need.
    """
    raw = RawReader(fd)
    inner: ByteSource
    if compression is Compression.NONE:
        inner = raw
    elif compression is Compression.GZIP:
        inner = gzip.GzipFile(fileobj=raw, mode="rb")  # type: ignore[call-overload]
    elif compression is Compression.BZIP2:
        inner = _StrictStreams(raw, bz2.BZ2Decompressor)
    else:
        inner = _StrictStreams(raw, _xz_decompressor)
    return _Bounded(inner, input_size, limits), raw
