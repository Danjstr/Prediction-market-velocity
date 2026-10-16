"""Durable, hash-chained receipt journal for quarantine intake and release (A-4, A-5).

Every intake writes a ``received`` entry (name, size, SHA-256) before the receipt is
used, and every successful release writes a ``released`` entry. A crash therefore never
loses the hash-on-receipt record (RT-B6-12): after an interruption the quarantine copy is
discarded and the source re-acquired, and the journal shows what was received before, so
a re-acquisition whose bytes differ is visible as a possible upstream revision rather
than silently replacing the earlier record.

Format: one canonical-JSON line per entry, append-only. Each entry carries ``seq``
(from 0), ``prev_sha256`` (64 zeros for the first entry), ``event``, ``session_id``,
``name``, ``size_bytes``, ``sha256``, ``recorded_at``, and ``entry_sha256``, the SHA-256
of the canonical entry without that field. The journal is verified in full when opened:
any malformed line, broken chain, sequence gap, torn tail, or unknown event fails closed.
Appends take an exclusive ``flock``, check that the file has not changed since it was
verified (same inode, same size; a same-size in-place edit is caught only at the next
open) and that its path still names the same inode, refuse to grow past the size limit,
and either land as one fsynced write or are rolled back.

**Limitations (G-6).** Entries carry no acquisition, manifest, or approval identifier,
so a ``released`` entry does not by itself show which manifest authorized it. Nothing
yet compares the hashes of a re-acquisition against earlier receipts, and there is no
reconciliation tool or runbook for interruptions (a file released but not journaled, a
received file not journaled, a torn tail). Each of these fails closed today.

The journal is evidence for the owner-run acquisition tool, not an authorization: it
never makes a file agent-visible (``docs/external_access.md`` A-8).
"""

import fcntl
import os
import secrets
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from pmv.integrity import (
    FormatError,
    canonical_line,
    chain_entry_sha256,
    format_timestamp,
    is_non_negative_int,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
)
from pmv.safe_fs import APPEND_FLAGS, NEW_FILE_FLAGS, append_exact, pread_all

GENESIS: Final = "0" * 64
MAX_JOURNAL_BYTES: Final = 64 * 1024 * 1024
_KEYS: Final = frozenset(
    {
        "seq",
        "prev_sha256",
        "event",
        "session_id",
        "name",
        "size_bytes",
        "sha256",
        "recorded_at",
        "entry_sha256",
    }
)

Clock = Callable[[], datetime]


class ReceiptJournalError(Exception):
    """The journal is missing, malformed, changed underneath us, or could not be appended."""


class ReceiptEvent(StrEnum):
    RECEIVED = "received"
    RELEASED = "released"


@dataclass(frozen=True, slots=True)
class JournalEntry:
    seq: int
    event: ReceiptEvent
    session_id: str
    name: str
    size_bytes: int
    sha256: str
    recorded_at: str
    entry_sha256: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def new_session_id() -> str:
    return secrets.token_hex(16)


def _parse(line: bytes, seq: int, prev: str) -> JournalEntry:
    try:
        value = parse_canonical_json(line)
    except FormatError as error:
        raise ReceiptJournalError(f"journal entry {seq} is malformed: {error}") from None
    if set(value) != _KEYS:
        raise ReceiptJournalError(f"journal entry {seq} has the wrong keys")
    body = {key: item for key, item in value.items() if key != "entry_sha256"}
    if value["seq"] != seq or isinstance(value["seq"], bool):
        raise ReceiptJournalError(f"journal entry {seq} is out of sequence")
    if value["prev_sha256"] != prev:
        raise ReceiptJournalError(f"journal entry {seq} breaks the hash chain")
    if value["entry_sha256"] != chain_entry_sha256(body):
        raise ReceiptJournalError(f"journal entry {seq} has a wrong entry hash")
    event, session, name = value["event"], value["session_id"], value["name"]
    size, digest, recorded = value["size_bytes"], value["sha256"], value["recorded_at"]
    if (
        not isinstance(event, str)
        or event not in set(ReceiptEvent)
        or not isinstance(session, str)
        or len(session) != 32
        or any(char not in "0123456789abcdef" for char in session)
        or not isinstance(name, str)
        or not name
        or isinstance(size, bool)
        or not is_non_negative_int(size)
        or not is_sha256(digest)
        or not is_timestamp(recorded)
    ):
        raise ReceiptJournalError(f"journal entry {seq} has an invalid field")
    return JournalEntry(
        seq=seq,
        event=ReceiptEvent(event),
        session_id=session,
        name=name,
        size_bytes=size,
        sha256=digest,
        recorded_at=recorded,
        entry_sha256=str(value["entry_sha256"]),
    )


def verify_journal(data: bytes) -> list[JournalEntry]:
    """Verify a whole journal and return its entries. Any defect raises."""
    if data and not data.endswith(b"\n"):
        raise ReceiptJournalError("journal has a torn tail")
    entries: list[JournalEntry] = []
    prev = GENESIS
    for seq, line in enumerate(data.splitlines(keepends=False)):
        entry = _parse(line, seq, prev)
        entries.append(entry)
        prev = entry.entry_sha256
    return entries


class ReceiptJournal:
    """An append-only receipt journal file, verified when opened."""

    def __init__(self, path: Path, *, clock: Clock = _utc_now) -> None:
        self.path = path
        self._clock = clock
        try:
            fd = os.open(path, APPEND_FLAGS)
        except FileNotFoundError:
            raise ReceiptJournalError("receipt journal does not exist") from None
        except OSError as error:
            raise ReceiptJournalError(f"receipt journal cannot be opened: {error}") from None
        self._fd = fd
        try:
            status = os.fstat(fd)
            if not stat.S_ISREG(status.st_mode):
                raise ReceiptJournalError("receipt journal is not a regular file")
            self._identity = (status.st_dev, status.st_ino)
            fcntl.flock(fd, fcntl.LOCK_SH)
            try:
                size = os.fstat(fd).st_size
                if size > MAX_JOURNAL_BYTES:
                    raise ReceiptJournalError("receipt journal exceeds its size limit")
                self.entries = verify_journal(pread_all(fd, size))
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        except BaseException:
            os.close(fd)
            raise
        self._size = size

    @staticmethod
    def create(path: Path) -> None:
        """Create a new, empty journal. Refuses to replace an existing file."""
        try:
            fd = os.open(path, NEW_FILE_FLAGS, 0o600)
        except FileExistsError:
            raise ReceiptJournalError("receipt journal already exists") from None
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    @property
    def directory(self) -> Path:
        return self.path.parent

    @property
    def head(self) -> str:
        return self.entries[-1].entry_sha256 if self.entries else GENESIS

    def append(
        self, event: ReceiptEvent, session_id: str, name: str, size: int, sha256: str
    ) -> JournalEntry:
        if self._fd < 0:
            raise ReceiptJournalError("receipt journal is closed")
        body: dict[str, object] = {
            "seq": len(self.entries),
            "prev_sha256": self.head,
            "event": event.value,
            "session_id": session_id,
            "name": name,
            "size_bytes": size,
            "sha256": sha256,
            "recorded_at": format_timestamp(self._clock()),
        }
        body["entry_sha256"] = chain_entry_sha256(body)
        line = canonical_line(body)
        entry = _parse(line[:-1], len(self.entries), self.head)
        if self._size + len(line) > MAX_JOURNAL_BYTES:
            raise ReceiptJournalError("receipt journal would exceed its size limit")
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        except OSError as error:
            raise ReceiptJournalError(f"receipt journal cannot be locked: {error}") from None
        try:
            try:
                status = os.fstat(self._fd)
            except OSError as error:
                raise ReceiptJournalError(f"receipt journal cannot be checked: {error}") from None
            try:
                named = os.stat(self.path, follow_symlinks=False)
            except FileNotFoundError:
                raise ReceiptJournalError("receipt journal changed since it was verified") from None
            if (
                (status.st_dev, status.st_ino) != self._identity
                or (named.st_dev, named.st_ino) != self._identity
                or status.st_size != self._size
            ):
                raise ReceiptJournalError("receipt journal changed since it was verified")
            try:
                append_exact(self._fd, line, self._size)
            except OSError as error:
                raise ReceiptJournalError(f"receipt journal append failed: {error}") from None
        finally:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._size += len(line)
        self.entries.append(entry)
        return entry
