"""Low-level filesystem primitives for append-only, no-overwrite storage.

Directory-relative, symlink-refusing traversal; ``renameat2(RENAME_NOREPLACE)`` with no
fallback to a plain rename; exact writes and reads; single-write appends with rollback;
inode identity checks; and a re-walk of a configured absolute root so a long-lived process
notices that a directory it holds was moved or replaced.

These primitives raise their own small exception types. Each storage domain maps them to
its own errors and keeps its own schemas and policies.
"""

import ctypes
import errno
import fcntl
import os
import re
import secrets
import stat
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final, cast

DIR_FLAGS: Final = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
NEW_FILE_FLAGS: Final = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
READ_FLAGS: Final = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
APPEND_FLAGS: Final = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC
_COMPONENT: Final = re.compile(r"[A-Za-z0-9._-]{1,255}")
_RENAME_NOREPLACE: Final = 1
_UNSUPPORTED_ERRNOS: Final = frozenset({errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP})

RenameAt2 = Callable[[int, bytes, int, bytes, int], int]
Identity = tuple[int, int]


class FsIntegrityError(Exception):
    """A managed path is unsafe, unexpected, moved, or replaced."""


class FsUnsupportedError(Exception):
    """The filesystem lacks a required capability (fail closed)."""


class RollbackError(FsIntegrityError):
    """An append failed and the file could not be restored to its previous size."""


def load_renameat2() -> RenameAt2 | None:
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        function = libc.renameat2
    except (OSError, AttributeError):
        return None
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    return cast(RenameAt2, function)


RENAMEAT2: Final[RenameAt2 | None] = load_renameat2()


def rename_noreplace(
    src_dir_fd: int,
    src_name: str,
    dst_dir_fd: int,
    dst_name: str,
    *,
    renameat2: RenameAt2 | None,
) -> None:
    """Move ``src_name`` to ``dst_name`` only if the destination does not exist.

    Raises FileExistsError if it exists, FsUnsupportedError if RENAME_NOREPLACE is
    unavailable, and OSError (for example EXDEV) otherwise. Never falls back.
    """
    source = component(src_name)
    destination = component(dst_name)
    if renameat2 is None:
        raise FsUnsupportedError("renameat2 is not available")
    if renameat2(src_dir_fd, source, dst_dir_fd, destination, _RENAME_NOREPLACE) == 0:
        return
    error = ctypes.get_errno()
    if error in _UNSUPPORTED_ERRNOS:
        raise FsUnsupportedError("RENAME_NOREPLACE is not supported here")
    raise OSError(error, os.strerror(error))


def component(name: str) -> bytes:
    """Validate one path component: no separators, no NUL, not ``.`` or ``..``."""
    if not isinstance(name, str) or _COMPONENT.fullmatch(name) is None or name in {".", ".."}:
        raise FsIntegrityError("unsafe path component")
    return os.fsencode(name)


def open_dir(parent_fd: int, name: str) -> int:
    component(name)
    try:
        return os.open(name, DIR_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise FsIntegrityError(f"managed path {name!r} is not a plain directory") from None
        raise


def open_file(parent_fd: int, name: str, flags: int = READ_FLAGS) -> int:
    component(name)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise FsIntegrityError(f"managed file {name!r} is a symlink") from None
        raise
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise FsIntegrityError(f"managed file {name!r} is not a regular file")
    return fd


def check_dir(fd: int, device: int, uid: int, name: str) -> None:
    status = os.fstat(fd)
    if not stat.S_ISDIR(status.st_mode):
        raise FsIntegrityError(f"managed path {name!r} is not a directory")
    if status.st_dev != device:
        raise FsIntegrityError(f"managed path {name!r} is not on the root's filesystem")
    if status.st_uid != uid:
        raise FsIntegrityError(f"managed path {name!r} is not owned by the current user")
    if status.st_mode & 0o022:
        raise FsIntegrityError(f"managed path {name!r} is writable by group or others")


def ensure_dir(parent_fd: int, name: str, device: int, uid: int) -> int:
    """Open ``name`` under ``parent_fd``, creating it (0700, parent synced) if missing."""
    created = False
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        created = True
    except FileExistsError:
        pass
    fd = open_dir(parent_fd, name)
    try:
        if created:
            os.fchmod(fd, 0o700)
        check_dir(fd, device, uid, name)
        if created:
            os.fsync(parent_fd)
    except BaseException:
        os.close(fd)
        raise
    return fd


def write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError(errno.EIO, "write made no progress")
        offset += written


def read_all(fd: int, limit: int) -> bytes:
    size = os.fstat(fd).st_size
    if size > limit:
        raise FsIntegrityError("a managed metadata file is larger than its limit")
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            raise FsIntegrityError("a managed file changed while it was read")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def pread_all(fd: int, size: int, offset: int = 0) -> bytes:
    chunks: list[bytes] = []
    end = offset + size
    while offset < end:
        chunk = os.pread(fd, end - offset, offset)
        if not chunk:
            raise FsIntegrityError("a ledger changed while it was read")
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def read_small(parent_fd: int, name: str, limit: int) -> bytes:
    fd = open_file(parent_fd, name)
    try:
        return read_all(fd, limit)
    finally:
        os.close(fd)


def write_new_file(parent_fd: int, name: str, data: bytes) -> None:
    """Create ``name`` exclusively (0600), write all of ``data``, and sync it."""
    component(name)
    fd = os.open(name, NEW_FILE_FLAGS, 0o600, dir_fd=parent_fd)
    try:
        write_all(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def identity(status: os.stat_result) -> Identity:
    return status.st_dev, status.st_ino


def same_entry(parent_fd: int, name: str, expected: os.stat_result) -> bool:
    """Return whether ``name`` still names the directory whose identity was recorded."""
    try:
        status = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(status.st_mode) and identity(status) == identity(expected)


def path_identities(root: Path, components: Sequence[str]) -> list[Identity]:
    """Re-walk ``root`` from the filesystem namespace and return each component's identity.

    The root's final component and every listed component are opened without following
    symlinks. The last component may be a file. A missing or symlinked component raises
    FsIntegrityError.
    """
    try:
        fd = os.open(root, DIR_FLAGS)
    except OSError as exc:
        raise FsIntegrityError("the configured root is missing or not a plain directory") from exc
    opened = [fd]
    try:
        identities = [identity(os.fstat(fd))]
        for index, name in enumerate(components):
            component(name)
            if index == len(components) - 1:
                try:
                    status = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    raise FsIntegrityError(f"managed path {name!r} is missing") from None
                if stat.S_ISLNK(status.st_mode):
                    raise FsIntegrityError(f"managed path {name!r} is a symlink")
                identities.append(identity(status))
            else:
                try:
                    fd = open_dir(fd, name)
                except FileNotFoundError:
                    raise FsIntegrityError(f"managed path {name!r} is missing") from None
                opened.append(fd)
                identities.append(identity(os.fstat(fd)))
        return identities
    finally:
        for item in opened:
            os.close(item)


def append_exact(
    fd: int,
    data: bytes,
    size_before: int,
    *,
    write: Callable[[int, bytes], int] = os.write,
    truncate: Callable[[int, int], None] = os.ftruncate,
) -> None:
    """Append ``data`` with one write and sync it, or roll back to ``size_before``."""
    try:
        written = write(fd, data)
        if written != len(data):
            raise OSError(errno.EIO, "short write to a ledger")
        os.fsync(fd)
    except OSError:
        rollback(fd, size_before, truncate=truncate)
        raise


def rollback(
    fd: int, size_before: int, *, truncate: Callable[[int, int], None] = os.ftruncate
) -> None:
    try:
        truncate(fd, size_before)
        os.fsync(fd)
    except OSError:
        raise RollbackError(
            "a ledger append failed and could not be rolled back; the damaged bytes were left "
            "in place"
        ) from None


def probe_capabilities(
    parent_fd: int, device: int, uid: int, *, renameat2: RenameAt2 | None
) -> None:
    """Fail closed unless RENAME_NOREPLACE and flock behave correctly under ``parent_fd``."""
    name = f".probe-{secrets.token_hex(8)}"
    probe = ensure_dir(parent_fd, name, device, uid)
    lock_fds: list[int] = []
    try:
        for file_name in ("a", "b"):
            write_new_file(probe, file_name, b"")
        try:
            rename_noreplace(probe, "a", probe, "b", renameat2=renameat2)
        except FileExistsError:
            pass
        else:
            raise FsUnsupportedError("RENAME_NOREPLACE replaced an existing file")
        rename_noreplace(probe, "a", probe, "c", renameat2=renameat2)
        lock_fds = [open_file(probe, "c"), open_file(probe, "c")]
        fcntl.flock(lock_fds[0], fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            fcntl.flock(lock_fds[1], fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise FsUnsupportedError("flock does not provide exclusive locks here")
    finally:
        for fd in lock_fds:
            os.close(fd)
        for file_name in ("a", "b", "c"):
            try:
                os.unlink(file_name, dir_fd=probe)
            except FileNotFoundError:
                continue
        os.close(probe)
        os.rmdir(name, dir_fd=parent_fd)
        os.fsync(parent_fd)
