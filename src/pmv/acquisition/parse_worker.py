"""The isolated parse worker (G-1). Run only by ``isolation.run_worker``, never by hand.

Started as ``python -I -m pmv.acquisition.parse_worker <parameters>`` with no environment,
``/`` as its working directory, a new session, resource limits set by the parent, and three
descriptors: the input file on fd 0 (opened read-only by the parent), the output pipe on
fd 1, and ``/dev/null`` on fd 2. It never receives a path to read.

Bootstrap order (all trusted code, before any untrusted byte is read):
1. import every module the worker can use (no file can be opened later);
2. compute its code identity (``worker_identity``);
3. parse and validate the parameters;
4. confirm the parent's resource limits are in force (``confinement.verify_limits``);
5. set ``no_new_privs`` and install the seccomp filter (``confinement.install_filter``);
6. write the protocol magic and the ``HELLO`` frame, then run the operation and write
   ``RESULT``.

If a step before 6 fails, ``HELLO`` says ``confined: false`` and the parent treats the run
as an isolation failure. Every exception becomes a closed refusal code
(``worker_protocol.RefusalCode``); no exception text, value, or row content is written.
"""

# Every module the worker can use is imported here, before confinement: after the seccomp
# filter no file can be opened, so nothing may be imported lazily (``_warm_up`` also runs
# each path once). ``encodings.cp437`` is how zipfile decodes non-UTF-8 member names.
import bz2
import csv  # noqa: F401
import decimal  # noqa: F401
import encodings.cp437
import encodings.utf_8  # noqa: F401
import gzip
import hashlib
import io
import json  # noqa: F401
import lzma
import os
import platform
import stat
import sys
import zipfile
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from pmv.acquisition import archive, confinement, formats, readers, strict_parse
from pmv.acquisition import worker_protocol as wp
from pmv.acquisition.formats import FileFormat
from pmv.integrity import FormatError, canonical_json, parse_canonical_json

_CHUNK: Final = wp.MAX_DATA_PAYLOAD
_MAX_PARAMETERS: Final = 64 * 1024
IDENTITY_MODULES: Final = (
    archive,
    confinement,
    formats,
    readers,
    strict_parse,
    wp,
    sys.modules[__name__],
)


class _RefusedError(Exception):
    def __init__(self, code: wp.RefusalCode, record: int | None = None) -> None:
        super().__init__(code.value)
        self.code = code
        self.record = record


def worker_identity() -> dict[str, object]:
    """Deterministic identity of the code and runtime that parse: versions and source hashes."""
    modules: dict[str, str] = {}
    for module in IDENTITY_MODULES:
        name = (
            "pmv.acquisition.parse_worker" if module is sys.modules[__name__] else module.__name__
        )
        source = getattr(module, "__file__", None)
        if not source:
            raise RuntimeError("worker module has no source file")
        modules[name] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    return {
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
        "modules": modules,
        "readers": {fmt.value: spec.identity() for fmt, spec in readers.READERS.items()},
    }


def _write_all(data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(1, view) :]


def _send(kind: bytes, payload: bytes) -> None:
    _write_all(wp.frame(kind, payload))


def _send_json(kind: bytes, value: Mapping[str, object]) -> None:
    _send(kind, canonical_json(value))


def _refusal(code: wp.RefusalCode, record: int | None = None) -> dict[str, object]:
    return {"status": "refused", "code": code.value, "record": record}


# --- parameters ---------------------------------------------------------------------------

_COMMON: Final = frozenset({"operation", "limits"})
_KEYS: Final[dict[wp.Operation, frozenset[str]]] = {
    wp.Operation.PROBE: _COMMON,
    wp.Operation.VERIFY: _COMMON
    | {"name", "format", "compression", "schema", "decode", "reader_limits"},
    wp.Operation.EXTRACT: _COMMON | {"kind", "extraction"},
}
_ARCHIVE_KINDS: Final = frozenset({"tar", "tar.gz", "tar.bz2", "tar.xz", "zip"})
_EXTRACTION_KEYS: Final = frozenset(
    {"max_members", "max_member_bytes", "max_total_bytes", "max_ratio", "max_depth"}
)


def _int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS)
    return value


def parse_parameters(text: str) -> dict[str, object]:
    """Validate the parameter document for its operation. Raises _RefusedError."""
    try:
        if len(text) > _MAX_PARAMETERS:
            raise FormatError("parameters are too large")
        document = parse_canonical_json(text.encode("ascii"))
        operation = wp.Operation(str(document.get("operation")))
    except (FormatError, ValueError, UnicodeEncodeError):
        raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS) from None
    if set(document) != _KEYS[operation]:
        raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS)
    limits = document["limits"]
    if not isinstance(limits, dict) or set(limits) != {
        "address_space_bytes",
        "cpu_seconds",
        "open_files",
    }:
        raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS)
    for value in limits.values():
        _int(value)
    if operation is wp.Operation.EXTRACT:
        extraction = document["extraction"]
        if document["kind"] not in _ARCHIVE_KINDS or not isinstance(extraction, dict):
            raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS)
        if set(extraction) != _EXTRACTION_KEYS:
            raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS)
        for value in extraction.values():
            _int(value)
    if operation is wp.Operation.VERIFY:
        try:
            file_format = FileFormat(str(document["format"]))
            compression = readers.Compression(str(document["compression"]))
            readers.RecordSchema.from_document(file_format, document["schema"])
            _decode_limits(document)
            _reader_limits(document)
            if not isinstance(document["name"], str):
                raise readers.SpecError("name must be text")
            readers.check_name(document["name"], file_format, compression)
        except (ValueError, TypeError, readers.SpecError):
            raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS) from None
    return document


def _object(document: Mapping[str, object], key: str, keys: set[str]) -> dict[str, object]:
    value = document[key]
    if not isinstance(value, dict) or set(value) != keys:
        raise readers.SpecError(f"{key} has the wrong keys")
    return value


def _decode_limits(document: Mapping[str, object]) -> readers.DecodeLimits:
    value = _object(document, "decode", {"max_decoded_bytes", "max_ratio"})
    return readers.DecodeLimits(
        max_decoded_bytes=value["max_decoded_bytes"],  # type: ignore[arg-type]
        max_ratio=value["max_ratio"],  # type: ignore[arg-type]
    )


def _reader_limits(document: Mapping[str, object]) -> readers.VerifyLimits:
    value = _object(document, "reader_limits", {"max_line_bytes", "max_json_bytes"})
    return readers.VerifyLimits(
        max_line_bytes=value["max_line_bytes"],  # type: ignore[arg-type]
        max_json_bytes=value["max_json_bytes"],  # type: ignore[arg-type]
    )


# --- operations ---------------------------------------------------------------------------


def _input_size() -> int:
    status = os.fstat(0)
    if not stat.S_ISREG(status.st_mode):
        raise _RefusedError(wp.RefusalCode.INPUT_NOT_REGULAR_FILE)
    return status.st_size


def _verify(document: Mapping[str, object]) -> dict[str, object]:
    file_format = FileFormat(str(document["format"]))
    compression = readers.Compression(str(document["compression"]))
    schema = readers.RecordSchema.from_document(file_format, document["schema"])
    decode = _decode_limits(document)
    limits = _reader_limits(document)
    if not readers.READERS[file_format].adopted:
        raise _RefusedError(wp.RefusalCode.READER_NOT_ADOPTED)
    size = _input_size()
    head = os.pread(0, 8, 0)
    tail = os.pread(0, 4, max(size - 4, 0))
    try:
        readers.check_signature(str(document["name"]), file_format, compression, head, tail)
    except readers.SpecError:
        raise _RefusedError(wp.RefusalCode.FORMAT_REFUSED) from None
    os.lseek(0, 0, os.SEEK_SET)
    source, raw = readers.decoded_source(0, compression, size, decode)
    summary = readers.verify_stream(source, schema, limits)
    raw.drain()
    if raw.size != size:
        raise _RefusedError(wp.RefusalCode.INPUT_NOT_REGULAR_FILE)
    return {
        "status": "ok",
        "summary": summary,
        "compression": compression.value,
        "decode": decode.document(),
        "input_bytes": raw.size,
        "input_sha256": raw.digest.hexdigest(),
    }


def _extraction_limits(document: Mapping[str, object]) -> archive.ExtractionLimits:
    values = document["extraction"]
    assert isinstance(values, dict)  # noqa: S101 - validated by parse_parameters
    return archive.ExtractionLimits(free_space_margin_bytes=0, **values)


def _stream_file(entry: archive._Entry, data: archive._Readable) -> None:
    _send_json(wp.FILE, {"name": entry.name, "size": entry.size})
    digest = hashlib.sha256()
    while chunk := data.read(_CHUNK):
        digest.update(chunk)
        _send(wp.DATA, chunk)
    _send_json(wp.END_FILE, {"sha256": digest.hexdigest()})


def _extract(document: Mapping[str, object]) -> dict[str, object]:
    limits = _extraction_limits(document)
    kind = str(document["kind"])
    size = _input_size()
    if archive.archive_kind_of(os.pread(0, 512, 0)) != kind:
        raise _RefusedError(wp.RefusalCode.ARCHIVE_REFUSED)
    budget = archive._Budget(limits, size)
    if kind == "zip":
        handle = os.fdopen(0, "rb", closefd=False)
        with zipfile.ZipFile(handle) as container:
            entries = archive._zip_entries(container, budget)
            for entry, info in entries:
                if entry.is_dir:
                    _send(wp.DIR, entry.name.encode("utf-8"))
                    continue
                with container.open(info) as stream:
                    _stream_file(entry, stream)
        files = [entry for entry, _ in entries if not entry.is_dir]
        dirs = len(entries) - len(files)
        return {
            "status": "ok",
            "files": len(files),
            "directories": dirs,
            "total_bytes": sum(entry.size for entry in files),
        }
    planned, first_hash = archive.tar_pass_fd(
        0,
        kind,
        limits,
        size,
        lambda entry, _data: budget.admit(entry.name, is_dir=entry.is_dir, size=entry.size),
    )
    position = 0

    def send_entry(entry: archive._Entry, data: archive._Readable | None) -> None:
        nonlocal position
        if position >= len(planned) or entry != planned[position]:
            raise archive.ArchiveRefusedError("archive changed between passes")
        position += 1
        if data is None:
            _send(wp.DIR, entry.name.encode("utf-8"))
        else:
            _stream_file(entry, data)

    streamed, second_hash = archive.tar_pass_fd(0, kind, limits, size, send_entry)
    if streamed != planned or second_hash != first_hash:
        raise archive.ArchiveRefusedError("archive changed between passes")
    files = [entry for entry in planned if not entry.is_dir]
    return {
        "status": "ok",
        "files": len(files),
        "directories": len(planned) - len(files),
        "total_bytes": sum(entry.size for entry in files),
        "archive_sha256": first_hash,
    }


def _run(operation: wp.Operation, document: Mapping[str, object]) -> dict[str, object]:
    try:
        if operation is wp.Operation.PROBE:
            return {"status": "ok", "probe": confinement.probe()}
        if operation is wp.Operation.VERIFY:
            return _verify(document)
        return _extract(document)
    except _RefusedError as refused:
        return _refusal(refused.code, refused.record)
    except readers.ReaderError as error:
        return _refusal(error.code, error.record)
    except (archive.ArchiveRefusedError, zipfile.BadZipFile, EOFError):
        return _refusal(wp.RefusalCode.ARCHIVE_REFUSED)
    except (MemoryError, RecursionError):
        return _refusal(wp.RefusalCode.RESOURCE_EXHAUSTED)
    except Exception:  # noqa: BLE001 - every other failure becomes a closed code
        return _refusal(wp.RefusalCode.INTERNAL_ERROR)


def _warm_up() -> None:
    """Exercise every reader and decoder on built-in synthetic bytes before confinement.

    After the seccomp filter no file can be opened, so a module that Python imports lazily
    on first use would fail. Running each path once here loads all of them.
    """
    csv_schema = readers.RecordSchema.from_document(
        FileFormat.CSV, {"columns": [{"name": "a", "type": "decimal"}]}
    )
    json_keys = {"keys": {"a": ["number"]}, "additional_keys": False}
    limits = readers.VerifyLimits()
    samples = (
        (b"a\n1.5\n", csv_schema),
        (b'{"a":1.5}\n', readers.RecordSchema.from_document(FileFormat.JSONL, json_keys)),
        (
            b'{"a":1}',
            readers.RecordSchema.from_document(
                FileFormat.JSON, {**json_keys, "top_level": "object"}
            ),
        ),
        (b"text\n", readers.RecordSchema.from_document(FileFormat.TEXT, None)),
    )
    for data, schema in samples:
        readers.verify_stream(io.BytesIO(data), schema, limits)
    for compress in (gzip.compress, bz2.compress, lzma.compress):
        compress(b"x")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as container:
        container.writestr("a.csv", b"a\n1\n")
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as container:
        for info in container.infolist():
            container.read(info)


def main(argv: list[str]) -> int:
    identity = worker_identity()
    hello: dict[str, object] = {
        "protocol": wp.PROTOCOL,
        "version": wp.PROTOCOL_VERSION,
        "confined": False,
        "identity": identity,
    }
    try:
        if len(argv) != 2:
            raise _RefusedError(wp.RefusalCode.BAD_PARAMETERS)
        document = parse_parameters(argv[1])
        operation = wp.Operation(str(document["operation"]))
        limits = document["limits"]
        assert isinstance(limits, dict)  # noqa: S101 - validated by parse_parameters
        try:
            confinement.verify_limits(limits)
        except confinement.ConfinementError:
            raise _RefusedError(wp.RefusalCode.LIMITS_NOT_APPLIED) from None
        _warm_up()
        try:
            confinement.install_filter()
        except confinement.ConfinementError:
            raise _RefusedError(wp.RefusalCode.CONFINEMENT_FAILED) from None
    except _RefusedError as refused:
        _write_all(wp.MAGIC)
        _send_json(wp.HELLO, hello)
        _send_json(wp.RESULT, _refusal(refused.code, refused.record))
        return 0
    hello["confined"] = True
    _write_all(wp.MAGIC)
    _send_json(wp.HELLO, hello)
    _send_json(wp.RESULT, _run(operation, document))
    return 0


if __name__ == "__main__":
    try:
        status = main(sys.argv)
    except BaseException:  # noqa: BLE001 - never print a traceback (it could carry content)
        status = 70
    os._exit(status)
