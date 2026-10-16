"""Hash-on-receipt intake and manifest-gated release from quarantine (A-4, A-5).

Files arrive in an empty quarantine directory. Each is written exclusively and hashed
while it is written, before anything parses it.

Release reads the quarantined file once, through a single descriptor. It copies those
bytes into an unnamed ``O_TMPFILE`` inode in the destination and hashes them as it copies,
so what is released is exactly what was hashed, and no partial file ever has a name that
another writer could replace. A writer racing on the quarantine path
cannot substitute unverified bytes. The copy is released only if every one of these
checks passes:
- the copied bytes hash to the value recorded at receipt;
- that hash and size equal the file's acquisition-manifest entry;
- the file's name, extension, and content agree with its declared allowlisted format
  (whole-file UTF-8 validation for text formats).

The verified inode is then given its final name with ``linkat`` from the descriptor
(through ``/proc/self/fd``), which never overwrites an existing name (RT-B6-22, RT-B6-25).
The released name must then resolve to that inode; otherwise release fails. A
filesystem without ``O_TMPFILE``, or a system without ``/proc``, fails closed. On any
failure before the link, the unnamed copy simply disappears and the quarantined file
stays.

Every receipt and every release is appended to a durable, hash-chained receipt journal
(``receipts.py``) kept outside the quarantine directory. A receipt is usable only after
its ``received`` entry is on disk; if that append fails, the new file is removed. After a
successful link the ``released`` entry is appended before the quarantine copy is
removed; if that append fails, release raises and the quarantine copy stays, so the
owner sees an unjournaled release instead of a silent one. The destination directory is
fsynced after the link and before the journal append, and the quarantine directory after
the unlink (RT-B6-28).

**Limitations.** Receipts are usable only within one intake session; after an
interruption the quarantine is discarded and the source re-acquired (the journal keeps
the earlier receipt for comparison). The receipt proves that bytes did not change
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
from pmv.acquisition.receipts import (
    ReceiptEvent,
    ReceiptJournal,
    ReceiptJournalError,
    new_session_id,
)
from pmv.acquisition.records import AcquisitionManifest, RecordError
from pmv.safe_fs import (
    DIR_FLAGS,
    NEW_FILE_FLAGS,
    READ_FLAGS,
    FsIntegrityError,
    component,
)

_CHUNK: Final = 1024 * 1024
_TMPFILE_FLAGS: Final = os.O_TMPFILE | os.O_RDWR | os.O_CLOEXEC


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


def _link_fd(fd: int, dir_fd: int, name: str) -> None:
    """Give the unnamed inode behind ``fd`` the name ``name``; never overwrites."""
    os.link(f"/proc/self/fd/{fd}", name, dst_dir_fd=dir_fd, follow_symlinks=True)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


class Quarantine:
    """A quarantine directory. It must be empty when the intake session opens."""

    def __init__(self, directory: Path, *, journal: ReceiptJournal) -> None:
        _real_dir(directory, "quarantine directory")
        if any(directory.iterdir()):
            raise QuarantineError("quarantine directory must be empty at intake")
        quarantine_root = directory.resolve()
        journal_dir = journal.directory.resolve()
        if journal_dir == quarantine_root or quarantine_root in journal_dir.parents:
            raise QuarantineError("receipt journal must be outside the quarantine directory")
        self.directory = directory
        self.journal = journal
        self.session_id = new_session_id()
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
        try:
            self.journal.append(
                ReceiptEvent.RECEIVED, self.session_id, name, receipt.size, receipt.sha256
            )
        except BaseException:
            os.unlink(self.directory / name)
            raise
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
        source_dir = os.open(self.directory, DIR_FLAGS)
        target_dir = os.open(destination, DIR_FLAGS)
        try:
            out_fd = self._copy_verified(source_dir, target_dir, name, receipt, entry.format)
            try:
                status = os.fstat(out_fd)
                try:
                    _link_fd(out_fd, target_dir, name)
                except FileExistsError:
                    raise
                except OSError as error:
                    raise QuarantineError(f"cannot link the verified copy: {error}") from None
            finally:
                os.close(out_fd)
            try:
                released = os.stat(name, dir_fd=target_dir, follow_symlinks=False)
            except FileNotFoundError:
                raise QuarantineError("released file is not the verified copy") from None
            identity = (status.st_dev, status.st_ino)
            if not stat.S_ISREG(released.st_mode) or (released.st_dev, released.st_ino) != identity:
                raise QuarantineError("released file is not the verified copy")
            os.fsync(target_dir)  # the link is durable before the journal says "released"
            try:
                self.journal.append(
                    ReceiptEvent.RELEASED, self.session_id, name, receipt.size, receipt.sha256
                )
            except ReceiptJournalError as error:
                raise QuarantineError(
                    f"file was released but its release was not journaled: {error}"
                ) from None
            os.unlink(name, dir_fd=source_dir)
            os.fsync(source_dir)
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
        receipt: Receipt,
        declared: FileFormat,
    ) -> int:
        """Copy into an unnamed inode, verify, and format-check; return its open fd."""
        in_fd = os.open(name, READ_FLAGS, dir_fd=source_dir)
        try:
            if not stat.S_ISREG(os.fstat(in_fd).st_mode):
                raise QuarantineError("quarantined entry is not a regular file")
            try:
                out_fd = os.open(".", _TMPFILE_FLAGS, 0o400, dir_fd=target_dir)
            except OSError as error:
                raise QuarantineError(
                    f"destination filesystem cannot create unnamed files: {error}"
                ) from None
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
            raise
        finally:
            os.close(in_fd)
        return out_fd


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
