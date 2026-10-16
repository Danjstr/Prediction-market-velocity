"""Backup copy and restore verification against an acquisition manifest (A-3).

``backup_and_verify_restore`` runs two copies: files from the source directory into the
backup location, and from there into an empty restore directory. Every file is checked
against its manifest SHA-256 and size at each step. The report lists verified,
mismatched, missing, and unexpected files. It passes only when every manifest file
verified and nothing else was present. Nothing is repaired silently.

Before any real acquisition, the A-3 restore test runs on a synthetic file of the same
format and size class (``synthetic_fixture``). The synthetic generator emits only
clearly labelled, deterministic synthetic values. It never emits real observations.

This is the verification mechanism only. The owner-approved backup policy (location,
off-device copy, retention) is a governance input and is not decided here. A restore
test counts as A-3 evidence only when ``backup_dir`` is on the policy's real backup
medium and the restore reads from that medium, not from a local scratch copy.
"""

import hashlib
import json
import os
import random
import stat
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from pmv.acquisition.formats import FileFormat
from pmv.acquisition.records import ManifestFile
from pmv.safe_fs import NEW_FILE_FLAGS, READ_FLAGS

_CHUNK: Final = 1024 * 1024
_SYNTHETIC_FORMATS: Final = frozenset({FileFormat.CSV, FileFormat.JSONL})


class BackupError(Exception):
    """A backup or restore step could not run (as opposed to a verification finding)."""


@dataclass(slots=True)
class RestoreReport:
    verified: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.verified) and not (self.mismatched or self.missing or self.unexpected)


def _copy_verified(source: Path, target: Path, expected: ManifestFile) -> bool:
    """Copy exclusively, hashing as it goes. Return whether the copy matches ``expected``."""
    digest = hashlib.sha256()
    size = 0
    in_fd = os.open(source, READ_FLAGS)
    try:
        if not stat.S_ISREG(os.fstat(in_fd).st_mode):
            return False
        out_fd = os.open(target, NEW_FILE_FLAGS, 0o400)
        try:
            while chunk := os.read(in_fd, _CHUNK):
                size += len(chunk)
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    view = view[os.write(out_fd, view) :]
            os.fsync(out_fd)
        finally:
            os.close(out_fd)
    finally:
        os.close(in_fd)
    return (size, digest.hexdigest()) == (expected.size_bytes, expected.sha256)


def _require_empty_dir(path: Path, what: str) -> None:
    try:
        status = path.lstat()
    except FileNotFoundError:
        raise BackupError(f"{what} does not exist") from None
    if not stat.S_ISDIR(status.st_mode):
        raise BackupError(f"{what} is not a directory (or is a symlink)")
    if any(path.iterdir()):
        raise BackupError(f"{what} must be empty")


def _stage(
    files: Sequence[ManifestFile], source: Path, target: Path, report: RestoreReport
) -> None:
    for entry in files:
        origin = source / entry.name
        if not origin.is_file() or origin.is_symlink():
            report.missing.append(entry.name)
            continue
        if not _copy_verified(origin, target / entry.name, entry):
            report.mismatched.append(entry.name)


def backup_and_verify_restore(
    files: Sequence[ManifestFile], source_dir: Path, backup_dir: Path, restore_dir: Path
) -> RestoreReport:
    """Back up ``files`` from ``source_dir``, restore them, and verify against the manifest."""
    if not files:
        raise BackupError("no manifest files to back up")
    resolved = [path.resolve() for path in (source_dir, backup_dir, restore_dir)]
    for index, first in enumerate(resolved):
        for second in resolved[index + 1 :]:
            if first == second or first.is_relative_to(second) or second.is_relative_to(first):
                raise BackupError("source, backup, and restore directories must be disjoint")
    _require_empty_dir(backup_dir, "backup directory")
    _require_empty_dir(restore_dir, "restore directory")
    staged = RestoreReport()
    _stage(files, source_dir, backup_dir, staged)
    report = RestoreReport(missing=list(staged.missing), mismatched=list(staged.mismatched))
    failed = set(report.missing) | set(report.mismatched)
    _stage([f for f in files if f.name not in failed], backup_dir, restore_dir, report)
    expected = {entry.name for entry in files}
    report.unexpected = sorted(p.name for p in restore_dir.iterdir() if p.name not in expected)
    failed = set(report.missing) | set(report.mismatched)
    report.verified = sorted(name for name in expected if name not in failed)
    return report


def synthetic_fixture(file_format: FileFormat, target_bytes: int, seed: int) -> bytes:
    """Deterministic synthetic content of ``file_format`` of at least ``target_bytes``.

    Every row carries ``synthetic=true``. Values are pseudo-random numbers from ``seed``
    and have no relation to any market.
    """
    if file_format not in _SYNTHETIC_FORMATS:
        raise BackupError("synthetic fixtures are generated for CSV and JSONL only")
    if target_bytes <= 0:
        raise BackupError("target_bytes must be positive")
    rng = random.Random(seed)  # noqa: S311 - synthetic test data, not security
    chunks: list[bytes] = []
    size = 0
    if file_format is FileFormat.CSV:
        header = b"synthetic,row,value_a,value_b\n"
        chunks.append(header)
        size += len(header)
    row = 0
    while size < target_bytes:
        a = rng.randrange(0, 10**6)
        b = rng.randrange(0, 10**6)
        if file_format is FileFormat.CSV:
            line = f"true,{row},{a / 10**6:.6f},{b}\n".encode("ascii")
        else:
            document = {"synthetic": True, "row": row, "value_a": f"{a / 10**6:.6f}", "value_b": b}
            line = json.dumps(document, sort_keys=True).encode("ascii") + b"\n"
        chunks.append(line)
        size += len(line)
        row += 1
    return b"".join(chunks)
