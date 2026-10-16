"""Hash-on-receipt intake and manifest-gated release from quarantine (A-4, A-5).

Files arrive in an empty quarantine directory. Each is written exclusively and hashed
while it is written, before anything parses it.

Release reads the quarantined file once, through a single descriptor. It copies those
bytes into a hidden partial file in the destination and hashes them as it copies, so
what is released is exactly what was hashed. A writer racing on the quarantine path
cannot substitute unverified bytes. The copy is released only if every one of these
checks passes:
- the copied bytes hash to the value recorded at receipt;
- that hash and size equal the file's acquisition-manifest entry;
- the file's name, extension, and content agree with its declared allowlisted format
  (whole-file UTF-8 validation for text formats).

The partial file is then renamed into place without overwriting anything
(``renameat2`` with ``RENAME_NOREPLACE``, with no fallback), and the quarantine copy is
removed. On any failure, the partial copy is removed and the quarantined file stays.

**Limitations.** Receipts are held in memory for one intake session; persisting them is
part of the end-to-end acquisition pipeline. The receipt proves that bytes did not change
after intake. It cannot prove the bytes are what the provider intended unless the
manifest hash comes from an independent provider checksum
(``docs/acquisition_readiness.md``).
"""

import hashlib
import os
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pmv.acquisition.formats import (
    TEXT_FORMATS,
    FileFormat,
    FormatRefusedError,
    check_format,
    check_text_stream,
)
from pmv.acquisition.records import AcquisitionManifest, RecordError
from pmv.safe_fs import (
    DIR_FLAGS,
    NEW_FILE_FLAGS,
    READ_FLAGS,
    RENAMEAT2,
    FsIntegrityError,
    component,
    rename_noreplace,
)

_CHUNK: Final = 1024 * 1024
_PARTIAL_FLAGS: Final = (NEW_FILE_FLAGS & ~os.O_WRONLY) | os.O_RDWR


class QuarantineError(Exception):
    """Intake or release refused. The file, if any, stays in quarantine."""


@dataclass(frozen=True, slots=True)
class Receipt:
    name: str
    size: int
    sha256: str


def _real_dir(path: Path, what: str) -> None:
    try:
        status = path.lstat()
    except FileNotFoundError:
        raise QuarantineError(f"{what} does not exist") from None
    if not stat.S_ISDIR(status.st_mode):
        raise QuarantineError(f"{what} is not a directory (or is a symlink)")


def hash_file(path: Path) -> tuple[int, str]:
    """Return ``(size, sha256)`` of a regular file, refusing symlinks."""
    digest = hashlib.sha256()
    size = 0
    fd = os.open(path, READ_FLAGS)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise QuarantineError("not a regular file")
        while chunk := os.read(fd, _CHUNK):
            size += len(chunk)
            digest.update(chunk)
    finally:
        os.close(fd)
    return size, digest.hexdigest()


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


class Quarantine:
    """A quarantine directory. It must be empty when the intake session opens."""

    def __init__(self, directory: Path) -> None:
        _real_dir(directory, "quarantine directory")
        if any(directory.iterdir()):
            raise QuarantineError("quarantine directory must be empty at intake")
        self.directory = directory
        self.receipts: dict[str, Receipt] = {}

    def receive(self, name: str, chunks: Iterable[bytes]) -> Receipt:
        """Write ``chunks`` to a new file ``name`` and hash it on receipt."""
        try:
            component(name)
        except FsIntegrityError:
            raise QuarantineError("file name is not a plain component") from None
        if name.startswith(".") or name in self.receipts:
            raise QuarantineError("file name is hidden or was already received")
        digest = hashlib.sha256()
        size = 0
        fd = os.open(self.directory / name, NEW_FILE_FLAGS, 0o400)
        try:
            for chunk in chunks:
                _write_all(fd, chunk)
                size += len(chunk)
                digest.update(chunk)
            os.fsync(fd)
        finally:
            os.close(fd)
        receipt = Receipt(name=name, size=size, sha256=digest.hexdigest())
        self.receipts[name] = receipt
        return receipt

    def release(self, name: str, manifest: AcquisitionManifest, destination: Path) -> Receipt:
        """Copy-verify ``name`` into ``destination`` only if every check passes."""
        receipt = self.receipts.get(name)
        if receipt is None:
            raise QuarantineError("file has no receipt in this quarantine session")
        try:
            entry = manifest.file(name)
        except RecordError:
            raise QuarantineError("file is not in the acquisition manifest") from None
        if (receipt.size, receipt.sha256) != (entry.size_bytes, entry.sha256):
            raise QuarantineError("file does not match its acquisition-manifest entry")
        _real_dir(destination, "release destination")
        partial = f".{name}.partial"
        source_dir = os.open(self.directory, DIR_FLAGS)
        target_dir = os.open(destination, DIR_FLAGS)
        try:
            self._copy_verified(source_dir, target_dir, name, partial, receipt, entry.format)
            try:
                rename_noreplace(target_dir, partial, target_dir, name, renameat2=RENAMEAT2)
            except BaseException:
                os.unlink(partial, dir_fd=target_dir)
                raise
            os.unlink(name, dir_fd=source_dir)
        finally:
            os.close(target_dir)
            os.close(source_dir)
        del self.receipts[name]
        return receipt

    @staticmethod
    def _copy_verified(
        source_dir: int,
        target_dir: int,
        name: str,
        partial: str,
        receipt: Receipt,
        declared: FileFormat,
    ) -> None:
        in_fd = os.open(name, READ_FLAGS, dir_fd=source_dir)
        try:
            if not stat.S_ISREG(os.fstat(in_fd).st_mode):
                raise QuarantineError("quarantined entry is not a regular file")
            out_fd = os.open(partial, _PARTIAL_FLAGS, 0o400, dir_fd=target_dir)
        except BaseException:
            os.close(in_fd)
            raise
        try:
            digest = hashlib.sha256()
            size = 0
            while chunk := os.read(in_fd, _CHUNK):
                size += len(chunk)
                digest.update(chunk)
                _write_all(out_fd, chunk)
            if (size, digest.hexdigest()) != (receipt.size, receipt.sha256):
                raise QuarantineError("file changed after receipt")
            os.fsync(out_fd)
            _check_copied_format(out_fd, name, size, declared)
        except BaseException:
            os.close(out_fd)
            os.close(in_fd)
            os.unlink(partial, dir_fd=target_dir)
            raise
        os.close(out_fd)
        os.close(in_fd)


def _check_copied_format(fd: int, name: str, size: int, declared: FileFormat) -> None:
    """Check the copy through the descriptor that wrote it, never by reopening its name."""
    head = os.pread(fd, 8, 0)
    tail = os.pread(fd, 4, max(size - 4, 0))
    try:
        file_format = check_format(name, declared, head, tail)
        if file_format in TEXT_FORMATS:
            check_text_stream(fd)
    except FormatRefusedError as error:
        raise QuarantineError(f"format check failed: {error}") from None
