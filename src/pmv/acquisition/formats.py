"""Parse-format allowlist and content sniffing (A-4).

Only CSV, JSON, JSONL, Parquet, DBN, and plain text may be parsed. Every file has a
declared format. That format must be allowed, must agree with the file extension, and
must agree with the file's leading and trailing bytes. Anything that looks like a pickle,
NumPy array, PyTorch or joblib archive, notebook, script, executable, or compressed
stream is refused, whatever its name. Archives are handled only by ``archive``.

Sniffing is defense in depth, not the safety property. The safety property is that no
code path ever deserializes an executable format: text formats are only decoded as text,
and Parquet and DBN are read only by pinned, reviewed readers (not yet adopted; see
``docs/acquisition_readiness.md``). Content that merely resembles another format, for
example protocol-0 pickle text inside a ``.csv``, is therefore inert. ``check_text_stream``
validates the whole of a text file, not just its head.
"""

import codecs
import os
from enum import StrEnum
from typing import Final


class FileFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    DBN = "dbn"
    TEXT = "text"


class FormatRefusedError(Exception):
    """A file's declared format, extension, or content is not on the allowlist."""


EXTENSIONS: Final[dict[FileFormat, tuple[str, ...]]] = {
    FileFormat.CSV: (".csv",),
    FileFormat.JSON: (".json",),
    FileFormat.JSONL: (".jsonl", ".ndjson"),
    FileFormat.PARQUET: (".parquet",),
    FileFormat.DBN: (".dbn",),
    FileFormat.TEXT: (".txt",),
}

REFUSED_EXTENSIONS: Final = frozenset(
    {
        ".pkl",
        ".pickle",
        ".joblib",
        ".pt",
        ".pth",
        ".ckpt",
        ".npy",
        ".npz",
        ".ipynb",
        ".py",
        ".pyc",
        ".sh",
        ".bash",
        ".exe",
        ".dll",
        ".so",
        ".bin",
        ".h5",
        ".hdf5",
        ".zst",
        ".gz",
        ".bz2",
        ".xz",
        ".zip",
        ".tar",
    }
)

# Leading signatures that are always refused for a parsed file.
_REFUSED_SIGNATURES: Final = (
    (b"\x93NUMPY", "NumPy array"),
    (b"PK\x03\x04", "zip container (PyTorch, joblib, or archive)"),
    (b"PK\x05\x06", "zip container"),
    (b"\x7fELF", "ELF executable"),
    (b"MZ", "Windows executable"),
    (b"#!", "script"),
    (b"\x1f\x8b", "gzip stream"),
    (b"BZh", "bzip2 stream"),
    (b"\xfd7zXZ\x00", "xz stream"),
    (b"\x28\xb5\x2f\xfd", "zstd stream"),
    (b"\x89HDF", "HDF5 file"),
    (b"%PDF", "PDF document"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable"),
    (b"\xfe\xed\xfa\xcf", "Mach-O executable"),
    (b"\xce\xfa\xed\xfe", "Mach-O executable"),
    (b"\xcf\xfa\xed\xfe", "Mach-O executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O or Java class file"),
    (b"7z\xbc\xaf\x27\x1c", "7z archive"),
    (b"Rar!", "RAR archive"),
    (b"\x00asm", "WebAssembly module"),
    (b"SQLite f", "SQLite database"),
)

_PARQUET_MAGIC: Final = b"PAR1"
_DBN_MAGIC: Final = b"DBN"
_TEXT_FORMATS: Final = frozenset(
    {FileFormat.CSV, FileFormat.JSON, FileFormat.JSONL, FileFormat.TEXT}
)


def _looks_like_pickle(head: bytes) -> bool:
    # Pickle protocol 2+ starts with PROTO (0x80) and a protocol number 2..5.
    return len(head) >= 2 and head[0] == 0x80 and 2 <= head[1] <= 5


def extension_of(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


def check_format(name: str, declared: FileFormat, head: bytes, tail: bytes) -> FileFormat:
    """Return ``declared`` if ``name`` and the file's bytes agree with it.

    ``head`` is at least the first 8 bytes of the file (all of it if shorter), and ``tail``
    the last 4 bytes. Raises FormatRefusedError otherwise.
    """
    if not isinstance(declared, FileFormat):
        raise FormatRefusedError("declared format is not on the allowlist")
    extension = extension_of(name)
    if extension in REFUSED_EXTENSIONS:
        raise FormatRefusedError(f"extension {extension!r} is refused")
    if extension not in EXTENSIONS[declared]:
        raise FormatRefusedError("file extension does not match the declared format")
    if _looks_like_pickle(head):
        raise FormatRefusedError("content is a pickle stream")
    for signature, what in _REFUSED_SIGNATURES:
        if head.startswith(signature):
            raise FormatRefusedError(f"content is a {what}")
    if declared is FileFormat.PARQUET:
        if not (head.startswith(_PARQUET_MAGIC) and tail.endswith(_PARQUET_MAGIC)):
            raise FormatRefusedError("content is not a Parquet file")
    elif declared is FileFormat.DBN:
        if not head.startswith(_DBN_MAGIC):
            raise FormatRefusedError("content is not a DBN file")
    elif declared in _TEXT_FORMATS:
        if head.startswith(b"\xef\xbb\xbf") or head.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise FormatRefusedError("byte-order marks and UTF-16 text are refused")
        if b"\x00" in head:
            raise FormatRefusedError("text content contains NUL bytes")
    return declared


TEXT_FORMATS: Final = _TEXT_FORMATS


def check_text_stream(fd: int, *, chunk_size: int = 1024 * 1024) -> None:
    """Validate a whole text file: strict UTF-8, no NUL bytes. Raises FormatRefusedError."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
    offset = 0
    while chunk := os.pread(fd, chunk_size, offset):
        offset += len(chunk)
        if b"\x00" in chunk:
            raise FormatRefusedError("text content contains NUL bytes")
        try:
            decoder.decode(chunk)
        except UnicodeDecodeError:
            raise FormatRefusedError("text content is not valid UTF-8") from None
    try:
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        raise FormatRefusedError("text content is not valid UTF-8") from None
