"""Tests for the low-level filesystem primitives."""

import errno
import os
from pathlib import Path

import pytest

from pmv import safe_fs


def test_path_identities_detect_replacement_and_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "a").mkdir(parents=True)
    (root / "a" / "file").write_bytes(b"x")
    first = safe_fs.path_identities(root, ["a", "file"])
    assert first == safe_fs.path_identities(root, ["a", "file"])
    os.rename(root / "a", root / "a-old")
    (root / "a").mkdir()
    (root / "a" / "file").write_bytes(b"x")
    assert safe_fs.path_identities(root, ["a", "file"]) != first
    (root / "link").symlink_to(root / "a")
    with pytest.raises(safe_fs.FsIntegrityError, match="not a plain directory"):
        safe_fs.path_identities(root, ["link", "file"])
    with pytest.raises(safe_fs.FsIntegrityError, match="symlink"):
        safe_fs.path_identities(root, ["link"])
    with pytest.raises(safe_fs.FsIntegrityError, match="missing"):
        safe_fs.path_identities(root, ["absent"])
    link_root = tmp_path / "link-root"
    link_root.symlink_to(root)
    with pytest.raises(safe_fs.FsIntegrityError, match="root"):
        safe_fs.path_identities(link_root, [])


def test_append_exact_rolls_back_short_writes(tmp_path: Path) -> None:
    path = tmp_path / "ledger"
    path.write_bytes(b"existing\n")
    fd = os.open(path, safe_fs.APPEND_FLAGS)
    try:
        with pytest.raises(OSError, match="short write"):
            safe_fs.append_exact(fd, b"new line\n", 9, write=lambda f, d: os.write(f, d[:3]))
        assert path.read_bytes() == b"existing\n"

        def failing_truncate(_fd: int, _size: int) -> None:
            raise OSError(errno.EIO, "I/O error")

        with pytest.raises(safe_fs.RollbackError, match="could not be rolled back"):
            safe_fs.append_exact(
                fd,
                b"new line\n",
                9,
                write=lambda f, d: os.write(f, d[:3]),
                truncate=failing_truncate,
            )
        assert path.read_bytes() == b"existing\nnew"
    finally:
        os.close(fd)


def test_rename_noreplace_refuses_existing_targets_without_fallback(tmp_path: Path) -> None:
    fd = os.open(tmp_path, safe_fs.DIR_FLAGS)
    try:
        (tmp_path / "a").write_bytes(b"a")
        (tmp_path / "empty").mkdir()
        (tmp_path / "dir").mkdir()
        with pytest.raises(FileExistsError):
            safe_fs.rename_noreplace(fd, "dir", fd, "empty", renameat2=safe_fs.RENAMEAT2)
        with pytest.raises(safe_fs.FsUnsupportedError):
            safe_fs.rename_noreplace(fd, "a", fd, "b", renameat2=None)
        assert (tmp_path / "a").exists()
    finally:
        os.close(fd)


def test_probe_capabilities_leaves_nothing_behind(tmp_path: Path) -> None:
    fd = os.open(tmp_path, safe_fs.DIR_FLAGS)
    try:
        status = os.fstat(fd)
        os.chmod(tmp_path, 0o700)
        safe_fs.probe_capabilities(fd, status.st_dev, os.geteuid(), renameat2=safe_fs.RENAMEAT2)
        assert os.listdir(tmp_path) == []
    finally:
        os.close(fd)
