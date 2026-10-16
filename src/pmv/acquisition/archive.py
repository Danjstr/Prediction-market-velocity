"""Bounded, link-free, traversal-free archive extraction (A-4).

Supports tar (plain, gzip, bzip2, or xz) and zip. Never calls ``extractall``.

**Tar: one parser, two hash-bound passes.** Tar archives are read only by this module's
own header walker (``_walk_tar``). ``tarfile`` is not used, so no second parser can
interpret the bytes differently. The walker:
- verifies every header checksum and requires a ``ustar`` magic;
- allows only regular files (with zero-filled data padding), directories (size 0), pax
  extended headers, and GNU long names;
- caps each metadata header at 64 KiB and requires zero padding after it;
- accepts only allowlisted pax keys (``path`` and timestamps or ownership), and refuses
  global pax headers;
- refuses base-256 numbers;
- requires two zero blocks followed only by zero padding;
- bounds the total decompressed bytes and the expansion ratio;
- reads the compressed stream to its end, so a gzip, bzip2, or xz integrity error is
  detected, and refuses bytes after the last bzip2 or xz stream that do not form another
  complete stream;
- refuses duplicate pax keys and a pax ``path`` combined with a GNU long name, and ignores
  the ustar prefix field under GNU magic (where those bytes hold other fields).

The first pass validates every member and the limits, and hashes the raw archive bytes.
The second pass walks the same bytes again and writes the files, hashing the raw bytes
again. Each entry of the second pass must equal the planned entry at the same position
before anything is written for it, so a swapped file cannot write more than the plan. If
the two hashes or the two member lists differ (the file was swapped or changed),
everything written is rolled back.

**Zip.** Zip archives are read with ``zipfile``. Encrypted members, unsupported
compression methods, link, device, and FIFO members, and prepended data (a first local
header not at offset 0) are refused.

**Both formats.** The following hold for tar and zip alike:
- names must be relative, use only ``[A-Za-z0-9._-]`` components, contain no ``..``
  component, and be unique even ignoring case, including implicit parent directories;
- limits apply to member count, per-member size, total size, depth, and ratio;
- a free-disk precheck runs before any write;
- any failure, of any kind, removes everything this call created;
- the destination must be an existing, empty directory that is not a symlink;
- nested archives are not extracted;
- by default every extracted file must pass ``formats.check_format`` for the format
  implied by its extension, with whole-file UTF-8 validation for text formats.
"""

import bz2
import errno
import gzip
import hashlib
import lzma
import os
import re
import shutil
import stat
import zipfile
import zlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Protocol

from pmv.acquisition.formats import (
    EXTENSIONS,
    TEXT_FORMATS,
    FormatRefusedError,
    check_format,
    check_text_stream,
    extension_of,
)
from pmv.safe_fs import NEW_FILE_FLAGS, READ_FLAGS

_COMPONENT: Final = re.compile(r"[A-Za-z0-9._-]{1,255}")
_CHUNK: Final = 1024 * 1024
_BLOCK: Final = 512
_ZERO_BLOCK: Final = bytes(_BLOCK)
_MAX_META_BYTES: Final = 64 * 1024
_MIN_STREAM_ALLOWANCE: Final = 1024 * 1024
_XZ_MEMLIMIT: Final = 128 * 1024 * 1024
_ALLOWED_ZIP_METHODS: Final = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
_REGULAR_TYPES: Final = frozenset({b"0", b"\x00"})
_PAX_ALLOWED_KEYS: Final = frozenset(
    {b"path", b"mtime", b"atime", b"ctime", b"uid", b"gid", b"uname", b"gname"}
)
_GNU_MAGIC: Final = b"ustar  \x00"
_USTAR_MAGICS: Final = frozenset({b"ustar\x0000", _GNU_MAGIC})
_FORMAT_BY_EXTENSION: Final = {
    extension: file_format for file_format, names in EXTENSIONS.items() for extension in names
}
_DECOMPRESSION_ERRORS: Final = (
    OSError,
    EOFError,
    zlib.error,
    lzma.LZMAError,
    ValueError,
    zipfile.BadZipFile,
)

DiskFree = Callable[[Path], int]
ChunkWriter = Callable[[int, bytes], None]


class _Readable(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class ArchiveRefusedError(Exception):
    """An archive failed a safety check, or extraction failed and was rolled back."""


@dataclass(frozen=True, slots=True)
class ExtractionLimits:
    max_members: int = 10_000
    max_member_bytes: int = 2 * 1024**3
    max_total_bytes: int = 8 * 1024**3
    max_ratio: int = 200
    max_depth: int = 8
    free_space_margin_bytes: int = 512 * 1024**2


@dataclass(frozen=True, slots=True)
class ExtractedFile:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _Entry:
    name: str
    is_dir: bool
    size: int


def _disk_free(path: Path) -> int:
    return shutil.disk_usage(path).free


def _write_chunk(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "short write")
        view = view[written:]


def safe_member_name(raw: str, *, is_dir: bool, max_depth: int) -> str:
    """Return the normalized member name, or raise ArchiveRefusedError."""
    if not isinstance(raw, str) or not raw or "\x00" in raw or "\\" in raw:
        raise ArchiveRefusedError("member name is empty or contains NUL or backslash")
    name = raw[2:] if raw.startswith("./") else raw
    if is_dir and name.endswith("/"):
        name = name[:-1]
    if not name or name.startswith("/") or name.endswith("/"):
        raise ArchiveRefusedError("member name is absolute or malformed")
    parts = name.split("/")
    if len(parts) > max_depth:
        raise ArchiveRefusedError("member path exceeds the depth limit")
    for part in parts:
        if part in {".", ".."} or _COMPONENT.fullmatch(part) is None:
            raise ArchiveRefusedError("member name has a disallowed component")
    return str(PurePosixPath(*parts))


def _archive_kind(path: Path) -> str:
    with path.open("rb") as handle:
        head = handle.read(_BLOCK)
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        return "zip"
    if head.startswith(b"\x1f\x8b"):
        return "tar.gz"
    if head.startswith(b"BZh"):
        return "tar.bz2"
    if head.startswith(b"\xfd7zXZ\x00"):
        return "tar.xz"
    if len(head) >= 265 and head[257:265] in _USTAR_MAGICS:
        return "tar"
    raise ArchiveRefusedError("file is not a supported tar or zip archive")


class _HashingReader:
    """Raw file reader that hashes every byte it returns."""

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self.digest = hashlib.sha256()

    def read(self, size: int = -1, /) -> bytes:
        data = os.read(self._fd, _CHUNK if size is None or size < 0 else size)
        self.digest.update(data)
        return data

    def readable(self) -> bool:
        return True

    def drain(self) -> None:
        while self.read(_CHUNK):
            pass


class _Decompressor(Protocol):
    @property
    def eof(self) -> bool: ...
    @property
    def needs_input(self) -> bool: ...
    @property
    def unused_data(self) -> bytes: ...
    def decompress(self, data: bytes, max_length: int = -1) -> bytes: ...


class _StrictStreams:
    """bzip2 or xz reader that refuses anything after the last stream except another stream.

    ``BZ2File`` and ``LZMAFile`` silently ignore trailing bytes that are not a valid
    stream (RT-B6-20). Here every byte after a stream's end must start another complete
    stream, or decompression fails and the archive is refused.
    """

    def __init__(self, raw: _HashingReader, factory: Callable[[], _Decompressor]) -> None:
        self._raw = raw
        self._factory = factory
        self._decompressor = factory()
        self._done = False

    def read(self, size: int = -1, /) -> bytes:
        limit = _CHUNK if size is None or size < 0 else size
        while not self._done:
            if self._decompressor.eof:
                data = self._decompressor.unused_data or self._raw.read(_CHUNK)
                if not data:
                    self._done = True
                    break
                self._decompressor = self._factory()
            elif self._decompressor.needs_input:
                data = self._raw.read(_CHUNK)
                if not data:
                    raise ArchiveRefusedError("compressed stream is truncated")
            else:
                data = b""
            try:
                out = self._decompressor.decompress(data, limit)
            except (OSError, EOFError, lzma.LZMAError, ValueError, MemoryError):
                raise ArchiveRefusedError("compressed stream is corrupt") from None
            if out:
                return out
        return b""


def _xz_decompressor() -> lzma.LZMADecompressor:
    """XZ container only (never legacy ``.lzma`` or raw), with a decoder memory limit."""
    return lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=_XZ_MEMLIMIT)


@contextmanager
def _decompressed(raw: _HashingReader, kind: str) -> Iterator[_Readable]:
    if kind == "tar.gz":
        with gzip.GzipFile(fileobj=raw, mode="rb") as stream:  # type: ignore[call-overload]
            yield stream
    elif kind == "tar.bz2":
        yield _StrictStreams(raw, bz2.BZ2Decompressor)
    elif kind == "tar.xz":
        yield _StrictStreams(raw, _xz_decompressor)
    else:
        yield raw


def _read_exact(stream: _Readable, size: int) -> bytes:
    parts: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(min(remaining, _CHUNK))
        if not chunk:
            raise ArchiveRefusedError("archive is truncated")
        parts.append(chunk)
        remaining -= len(chunk)
    return b"".join(parts)


def _octal(field: bytes) -> int:
    if field[:1] and field[0] & 0x80:
        raise ArchiveRefusedError("base-256 tar numbers are refused")
    text = field.replace(b"\x00", b" ").strip()
    if not text:
        return 0
    if not text.isdigit() or any(digit > ord("7") for digit in text):
        raise ArchiveRefusedError("tar header has a malformed number")
    return int(text, 8)


def _parse_pax(data: bytes) -> bytes | None:
    """Validate pax records; return the ``path`` value if present."""
    path: bytes | None = None
    seen: set[bytes] = set()
    offset = 0
    while offset < len(data):
        space = data.find(b" ", offset)
        if space <= offset or not data[offset:space].isdigit():
            raise ArchiveRefusedError("pax header is malformed")
        length = int(data[offset:space])
        record = data[offset : offset + length]
        if length <= space - offset or len(record) != length or not record.endswith(b"\n"):
            raise ArchiveRefusedError("pax header is malformed")
        key, separator, value = record[space - offset + 1 : -1].partition(b"=")
        if not separator:
            raise ArchiveRefusedError("pax header is malformed")
        if key not in _PAX_ALLOWED_KEYS:
            raise ArchiveRefusedError("pax header has a disallowed key")
        if key in seen:
            raise ArchiveRefusedError("pax header repeats a key")
        seen.add(key)
        if key == b"path":
            if not value:
                raise ArchiveRefusedError("pax header has an empty path")
            path = value
        offset += length
    return path


def _decode_name(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ArchiveRefusedError("member name is not valid UTF-8") from None


class _BoundedReader:
    def __init__(self, stream: _Readable, size: int) -> None:
        self._stream = stream
        self._remaining = size

    def read(self, size: int = -1, /) -> bytes:
        if self._remaining == 0:
            return b""
        want = self._remaining if size is None or size < 0 else min(size, self._remaining)
        data = _read_exact(self._stream, min(want, _CHUNK))
        self._remaining -= len(data)
        return data

    def finish(self) -> None:
        while self.read(_CHUNK):
            pass


def _walk_tar(
    stream: _Readable, limits: ExtractionLimits, stream_limit: int
) -> Iterator[tuple[_Entry, _Readable | None]]:
    """Yield validated entries. For a regular file, the second item streams its data."""
    consumed = 0
    pending_path: bytes | None = None
    pending_long: bytes | None = None
    while True:
        block = _read_exact(stream, _BLOCK)
        consumed += _BLOCK
        if block == _ZERO_BLOCK:
            if pending_path is not None or pending_long is not None:
                raise ArchiveRefusedError("metadata header is not followed by a member")
            if _read_exact(stream, _BLOCK) != _ZERO_BLOCK:
                raise ArchiveRefusedError("archive has a malformed end-of-archive marker")
            consumed += _BLOCK
            while chunk := stream.read(_CHUNK):
                consumed += len(chunk)
                if chunk.count(0) != len(chunk):
                    raise ArchiveRefusedError("archive has data after its end marker")
                if consumed > stream_limit:
                    raise ArchiveRefusedError("archive exceeds the expansion-ratio limit")
            return
        if _octal(block[148:156]) != sum(block[:148]) + 8 * 32 + sum(block[156:]):
            raise ArchiveRefusedError("archive has a corrupt header block")
        if block[257:265] not in _USTAR_MAGICS:
            raise ArchiveRefusedError("archive header is not ustar")
        kind = block[156:157]
        size = _octal(block[124:136])
        padded = -(-size // _BLOCK) * _BLOCK
        consumed += padded
        if consumed > stream_limit:
            raise ArchiveRefusedError("archive exceeds the expansion-ratio limit")
        if kind in {b"x", b"L"}:
            if size > _MAX_META_BYTES:
                raise ArchiveRefusedError("tar metadata header exceeds the size limit")
            data = _read_exact(stream, padded)
            if data[size:].count(0) != padded - size:
                raise ArchiveRefusedError("tar metadata header has non-zero padding")
            if kind == b"x":
                if pending_path is not None:
                    raise ArchiveRefusedError("archive has consecutive pax headers")
                pending_path = _parse_pax(data[:size]) or b""
            else:
                if pending_long is not None:
                    raise ArchiveRefusedError("archive has consecutive long-name headers")
                pending_long = data[:size].rstrip(b"\x00")
                if not pending_long:
                    raise ArchiveRefusedError("GNU long name is empty")
            continue
        if kind == b"5":
            if size != 0:
                raise ArchiveRefusedError("directory entry has a non-zero size")
        elif kind not in _REGULAR_TYPES:
            raise ArchiveRefusedError("archive contains a link, device, FIFO, or sparse member")
        if size > limits.max_member_bytes:
            raise ArchiveRefusedError("member exceeds the per-member size limit")
        if pending_path and pending_long is not None:
            raise ArchiveRefusedError("member has both a pax path and a GNU long name")
        if pending_path:
            raw_name = pending_path
        elif pending_long:
            raw_name = pending_long
        else:
            gnu = block[257:265] == _GNU_MAGIC
            prefix = b"" if gnu else block[345:500].split(b"\x00", 1)[0]
            base = block[0:100].split(b"\x00", 1)[0]
            raw_name = prefix + b"/" + base if prefix else base
        pending_path = None
        pending_long = None
        is_dir = kind == b"5"
        name = safe_member_name(_decode_name(raw_name), is_dir=is_dir, max_depth=limits.max_depth)
        entry = _Entry(name=name, is_dir=is_dir, size=size)
        if is_dir:
            yield entry, None
            continue
        reader = _BoundedReader(stream, size)
        yield entry, reader
        reader.finish()
        padding = _read_exact(stream, padded - size)
        if padding.count(0) != len(padding):
            raise ArchiveRefusedError("member data has non-zero padding")


class _Budget:
    def __init__(self, limits: ExtractionLimits, archive_size: int) -> None:
        self.limits = limits
        self.archive_size = max(archive_size, 1)
        self.members = 0
        self.total = 0
        self.explicit: set[str] = set()
        self.files: set[str] = set()
        self.dirs: set[str] = set()
        self.spelling: dict[str, str] = {}

    def _claim(self, path: str) -> None:
        folded = path.casefold()
        existing = self.spelling.setdefault(folded, path)
        if existing != path:
            raise ArchiveRefusedError("member names collide when case is ignored")

    def admit(self, name: str, *, is_dir: bool, size: int) -> None:
        limits = self.limits
        self.members += 1
        if self.members > limits.max_members:
            raise ArchiveRefusedError("archive exceeds the member-count limit")
        if size < 0 or size > limits.max_member_bytes:
            raise ArchiveRefusedError("member exceeds the per-member size limit")
        self.total += size
        if self.total > limits.max_total_bytes:
            raise ArchiveRefusedError("archive exceeds the total-size limit")
        if self.total > limits.max_ratio * self.archive_size:
            raise ArchiveRefusedError("archive exceeds the expansion-ratio limit")
        if name in self.explicit:
            raise ArchiveRefusedError("duplicate member name")
        parents = [str(parent) for parent in PurePosixPath(name).parents if str(parent) != "."]
        if any(parent in self.files for parent in parents):
            raise ArchiveRefusedError("member is nested under a file")
        if not is_dir and name in self.dirs:
            raise ArchiveRefusedError("file and directory share a name")
        for path in [name, *parents]:
            self._claim(path)
        self.explicit.add(name)
        (self.dirs if is_dir else self.files).add(name)
        self.dirs.update(parents)


def _stream_limit(limits: ExtractionLimits, archive_size: int) -> int:
    return min(
        limits.max_total_bytes + 2 * _BLOCK * (limits.max_members + 2) + _MIN_STREAM_ALLOWANCE,
        max(limits.max_ratio * archive_size, _MIN_STREAM_ALLOWANCE),
    )


def _tar_pass(
    archive_path: Path,
    kind: str,
    limits: ExtractionLimits,
    archive_size: int,
    visit: Callable[[_Entry, _Readable | None], None],
) -> tuple[list[_Entry], str]:
    """Walk the tar once. Return its entries and the SHA-256 of the raw archive bytes."""
    entries: list[_Entry] = []
    fd = os.open(archive_path, READ_FLAGS)
    try:
        raw = _HashingReader(fd)
        with _decompressed(raw, kind) as stream:
            for entry, data in _walk_tar(stream, limits, _stream_limit(limits, archive_size)):
                entries.append(entry)
                visit(entry, data)
        raw.drain()
    finally:
        os.close(fd)
    return entries, raw.digest.hexdigest()


def _zip_entries(archive: zipfile.ZipFile, budget: _Budget) -> list[tuple[_Entry, zipfile.ZipInfo]]:
    infos = archive.infolist()
    if infos and min(info.header_offset for info in infos) != 0:
        raise ArchiveRefusedError("zip archive has data before its first member")
    entries: list[tuple[_Entry, zipfile.ZipInfo]] = []
    for info in infos:
        if info.flag_bits & 0x1:
            raise ArchiveRefusedError("archive contains an encrypted member")
        if info.compress_type not in _ALLOWED_ZIP_METHODS:
            raise ArchiveRefusedError("archive uses an unsupported compression method")
        mode = (info.external_attr >> 16) & 0o177777
        kind = stat.S_IFMT(mode)
        is_dir = info.is_dir()
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ArchiveRefusedError("archive contains a link, device, or FIFO member")
        if (kind == stat.S_IFDIR and not is_dir) or (kind == stat.S_IFREG and is_dir):
            raise ArchiveRefusedError("archive member type and name disagree")
        name = safe_member_name(info.filename, is_dir=is_dir, max_depth=budget.limits.max_depth)
        size = 0 if is_dir else info.file_size
        budget.admit(name, is_dir=is_dir, size=size)
        entries.append((_Entry(name=name, is_dir=is_dir, size=size), info))
    return entries


def _check_destination(destination: Path) -> None:
    try:
        status = destination.lstat()
    except FileNotFoundError:
        raise ArchiveRefusedError("destination does not exist") from None
    if not stat.S_ISDIR(status.st_mode):
        raise ArchiveRefusedError("destination is not a directory (or is a symlink)")
    if any(destination.iterdir()):
        raise ArchiveRefusedError("destination is not empty")


def _rollback(destination: Path) -> None:
    for child in destination.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_file(
    destination: Path, entry: _Entry, data: _Readable, write_chunk: ChunkWriter
) -> ExtractedFile:
    target = destination.joinpath(*entry.name.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0
    fd = os.open(target, NEW_FILE_FLAGS, 0o600)
    try:
        while chunk := data.read(_CHUNK):
            written += len(chunk)
            if written > entry.size:
                raise ArchiveRefusedError("member data exceeds its declared size")
            digest.update(chunk)
            write_chunk(fd, chunk)
    finally:
        os.close(fd)
    if written != entry.size:
        raise ArchiveRefusedError("member data is shorter than its declared size")
    return ExtractedFile(name=entry.name, size=written, sha256=digest.hexdigest())


def _check_extracted_format(destination: Path, extracted: ExtractedFile) -> None:
    declared = _FORMAT_BY_EXTENSION.get(extension_of(extracted.name))
    if declared is None:
        raise ArchiveRefusedError("archive member has no allowlisted parse format")
    fd = os.open(destination.joinpath(*extracted.name.split("/")), READ_FLAGS)
    try:
        head = os.pread(fd, 8, 0)
        tail = os.pread(fd, 4, max(extracted.size - 4, 0))
        try:
            check_format(extracted.name.rsplit("/", 1)[-1], declared, head, tail)
            if declared in TEXT_FORMATS:
                check_text_stream(fd)
        except FormatRefusedError as error:
            raise ArchiveRefusedError(f"archive member refused: {error}") from None
    finally:
        os.close(fd)


def _extract_tar(
    archive_path: Path,
    kind: str,
    destination: Path,
    limits: ExtractionLimits,
    disk_free: DiskFree,
    write_chunk: ChunkWriter,
) -> list[ExtractedFile]:
    archive_size = archive_path.stat().st_size
    budget = _Budget(limits, archive_size)
    planned, first_hash = _tar_pass(
        archive_path,
        kind,
        limits,
        archive_size,
        lambda entry, _data: budget.admit(entry.name, is_dir=entry.is_dir, size=entry.size),
    )
    if disk_free(destination) < budget.total + limits.free_space_margin_bytes:
        raise ArchiveRefusedError("insufficient free disk space for extraction")
    extracted: list[ExtractedFile] = []
    position = 0

    def write(entry: _Entry, data: _Readable | None) -> None:
        nonlocal position
        if position >= len(planned) or entry != planned[position]:
            raise ArchiveRefusedError("archive changed between validation and extraction")
        position += 1
        if data is None:
            destination.joinpath(*entry.name.split("/")).mkdir(parents=True, exist_ok=True)
        else:
            extracted.append(_write_file(destination, entry, data, write_chunk))

    written, second_hash = _tar_pass(archive_path, kind, limits, archive_size, write)
    if written != planned or second_hash != first_hash:
        raise ArchiveRefusedError("archive changed between validation and extraction")
    return extracted


def _extract_zip(
    archive_path: Path,
    destination: Path,
    limits: ExtractionLimits,
    disk_free: DiskFree,
    write_chunk: ChunkWriter,
) -> list[ExtractedFile]:
    budget = _Budget(limits, archive_path.stat().st_size)
    with zipfile.ZipFile(archive_path) as archive:
        entries = _zip_entries(archive, budget)
        if disk_free(destination) < budget.total + limits.free_space_margin_bytes:
            raise ArchiveRefusedError("insufficient free disk space for extraction")
        extracted: list[ExtractedFile] = []
        for entry, info in entries:
            if entry.is_dir:
                destination.joinpath(*entry.name.split("/")).mkdir(parents=True, exist_ok=True)
                continue
            with archive.open(info) as stream:
                extracted.append(_write_file(destination, entry, stream, write_chunk))
    return extracted


def extract_archive(
    archive_path: Path,
    destination: Path,
    *,
    limits: ExtractionLimits | None = None,
    disk_free: DiskFree = _disk_free,
    write_chunk: ChunkWriter = _write_chunk,
    check_formats: bool = True,
) -> list[ExtractedFile]:
    """Validate every member, then extract regular files into the empty ``destination``."""
    limits = limits or ExtractionLimits()
    _check_destination(destination)
    kind = _archive_kind(archive_path)
    try:
        if kind == "zip":
            extracted = _extract_zip(archive_path, destination, limits, disk_free, write_chunk)
        else:
            extracted = _extract_tar(
                archive_path, kind, destination, limits, disk_free, write_chunk
            )
        if check_formats:
            for item in extracted:
                _check_extracted_format(destination, item)
    except ArchiveRefusedError:
        _rollback(destination)
        raise
    except _DECOMPRESSION_ERRORS as error:
        _rollback(destination)
        if isinstance(error, OSError) and error.errno == errno.ENOSPC:
            raise ArchiveRefusedError("extraction rolled back: disk full") from None
        if isinstance(error, OSError) and error.errno is not None:
            raise ArchiveRefusedError("extraction rolled back: write failed") from None
        raise ArchiveRefusedError("archive is corrupt or unreadable") from None
    except BaseException:
        _rollback(destination)
        raise
    return extracted
