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
import re
import secrets
import stat
from collections.abc import Callable, Mapping
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
    is_identifier,
    is_non_negative_int,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
    sha256_hex,
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
_V2_KEYS: Final = _KEYS | {"acquisition_id", "plan_sha256", "detail"}

Clock = Callable[[], datetime]


class ReceiptJournalError(Exception):
    """The journal is missing, malformed, changed underneath us, or could not be appended."""


class ReceiptEvent(StrEnum):
    # v1 (B06 ``Quarantine``)
    RECEIVED = "received"
    RELEASED = "released"
    # v2 only (bound to an acquisition; ``pipeline``)
    APPROVED_FOR_FETCH = "approved_for_fetch"
    FETCH_FAILED = "fetch_failed"
    INTEGRITY_VERIFIED = "integrity_verified"
    PARSER_VERIFIED = "parser_verified"
    BACKUP_VERIFIED = "backup_verified"
    STORED = "stored"
    REJECTED = "rejected"
    DISCARDED = "discarded"
    COMPLETED = "completed"
    TAIL_RECOVERED = "tail_recovered"


V1_EVENTS: Final = frozenset({ReceiptEvent.RECEIVED, ReceiptEvent.RELEASED})
# Events recorded before any bytes exist: their size and hash are null.
BYTELESS_EVENTS: Final = frozenset(
    {ReceiptEvent.APPROVED_FOR_FETCH, ReceiptEvent.FETCH_FAILED, ReceiptEvent.REJECTED}
)

_TEXT: Final = "text"
_INT: Final = "int"
_SHA: Final = "sha256"
_BOOL: Final = "bool"
# The closed ``detail`` schema of every v2 event: key -> value kind.
DETAIL_KEYS: Final[dict[ReceiptEvent, dict[str, str]]] = {
    ReceiptEvent.APPROVED_FOR_FETCH: {"attempt": _INT, "url": _TEXT},
    ReceiptEvent.FETCH_FAILED: {"attempt": _INT, "code": _TEXT},
    ReceiptEvent.RECEIVED: {
        "attempt": _INT,
        "final_url": _TEXT,
        "redirects": _INT,
        "hash_source": _TEXT,
    },
    ReceiptEvent.INTEGRITY_VERIFIED: {"kind": _TEXT},
    ReceiptEvent.PARSER_VERIFIED: {"verification_sha256": _SHA, "worker_identity_sha256": _SHA},
    ReceiptEvent.BACKUP_VERIFIED: {"policy_id": _TEXT, "evidence_sha256": _SHA},
    ReceiptEvent.STORED: {"path": _TEXT, "recovered": _BOOL},
    ReceiptEvent.REJECTED: {"stage": _TEXT, "code": _TEXT, "moved_to": _TEXT},
    ReceiptEvent.DISCARDED: {"reason": _TEXT, "moved_to": _TEXT},
    ReceiptEvent.COMPLETED: {"record_path": _TEXT, "files": _INT},
    ReceiptEvent.TAIL_RECOVERED: {"attestation": _TEXT, "evidence_file": _TEXT},
}
_MAX_TEXT: Final = 2048


@dataclass(frozen=True, slots=True)
class Binding:
    """What a v2 entry is bound to: the acquisition and the hash of its authorizing bundle.

    ``plan_sha256`` is the SHA-256 of the canonical bundle of every document that
    authorized the acquisition (plan, approval, licence, source quality, backup policy,
    restore tests, A-4 review), so an entry shows exactly which records authorized it.
    """

    acquisition_id: str
    plan_sha256: str

    def __post_init__(self) -> None:
        if not is_identifier(self.acquisition_id) or not is_sha256(self.plan_sha256):
            raise ReceiptJournalError("binding needs an identifier and a SHA-256")


@dataclass(frozen=True, slots=True)
class JournalEntry:
    seq: int
    event: ReceiptEvent
    session_id: str
    name: str
    size_bytes: int | None
    sha256: str | None
    recorded_at: str
    entry_sha256: str
    acquisition_id: str | None = None
    plan_sha256: str | None = None
    detail: Mapping[str, object] | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def new_session_id() -> str:
    return secrets.token_hex(16)


def _parse(line: bytes, seq: int, prev: str) -> JournalEntry:
    try:
        value = parse_canonical_json(line)
    except FormatError as error:
        raise ReceiptJournalError(f"journal entry {seq} is malformed: {error}") from None
    if set(value) not in (_KEYS, _V2_KEYS):
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
        or len(name) > 255
        or not is_timestamp(recorded)
    ):
        raise ReceiptJournalError(f"journal entry {seq} has an invalid field")
    kind = ReceiptEvent(event)
    bound = set(value) == _V2_KEYS
    byteless = bound and kind in BYTELESS_EVENTS and size is None and digest is None
    if not byteless and (
        isinstance(size, bool) or not is_non_negative_int(size) or not is_sha256(digest)
    ):
        raise ReceiptJournalError(f"journal entry {seq} has an invalid field")
    if not bound:
        if kind not in V1_EVENTS:
            raise ReceiptJournalError(f"journal entry {seq} has an unbound v2 event")
        return JournalEntry(
            seq=seq,
            event=kind,
            session_id=session,
            name=name,
            size_bytes=size,  # type: ignore[arg-type]
            sha256=digest,  # type: ignore[arg-type]
            recorded_at=recorded,
            entry_sha256=str(value["entry_sha256"]),
        )
    acquisition, plan = value["acquisition_id"], value["plan_sha256"]
    if kind is ReceiptEvent.RELEASED or not is_identifier(acquisition) or not is_sha256(plan):
        raise ReceiptJournalError(f"journal entry {seq} has an invalid binding")
    detail = _detail(value["detail"], kind, seq)
    return JournalEntry(
        seq=seq,
        event=kind,
        session_id=session,
        name=name,
        size_bytes=size,  # type: ignore[arg-type]
        sha256=digest,  # type: ignore[arg-type]
        recorded_at=recorded,
        entry_sha256=str(value["entry_sha256"]),
        acquisition_id=acquisition,
        plan_sha256=plan,
        detail=detail,
    )


def _detail(value: object, event: ReceiptEvent, seq: int) -> dict[str, object]:
    """Validate a v2 ``detail`` object against the event's closed schema."""
    schema = DETAIL_KEYS[event]
    if not isinstance(value, dict) or set(value) != set(schema):
        raise ReceiptJournalError(f"journal entry {seq} has the wrong detail keys")
    for key, kind in schema.items():
        item = value[key]
        if kind == _TEXT:
            ok = isinstance(item, str) and 0 < len(item) <= _MAX_TEXT and item.isprintable()
        elif kind == _INT:
            ok = not isinstance(item, bool) and is_non_negative_int(item)
        elif kind == _SHA:
            ok = is_sha256(item)
        else:
            ok = isinstance(item, bool)
        if not ok:
            raise ReceiptJournalError(f"journal entry {seq} has an invalid detail field")
    return dict(value)


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
        """Append an unbound v1 entry (``received`` or ``released``)."""
        if event not in V1_EVENTS:
            raise ReceiptJournalError("only received and released entries may be unbound")
        return self._append(
            {
                "event": event.value,
                "session_id": session_id,
                "name": name,
                "size_bytes": size,
                "sha256": sha256,
            }
        )

    def append_bound(
        self,
        event: ReceiptEvent,
        binding: Binding,
        session_id: str,
        name: str,
        size: int | None,
        sha256: str | None,
        detail: Mapping[str, object],
    ) -> JournalEntry:
        """Append a v2 entry bound to an acquisition and its authorizing bundle (RT-B6-27)."""
        return self._append(
            {
                "event": event.value,
                "session_id": session_id,
                "name": name,
                "size_bytes": size,
                "sha256": sha256,
                "acquisition_id": binding.acquisition_id,
                "plan_sha256": binding.plan_sha256,
                "detail": dict(detail),
            }
        )

    def _append(self, fields: Mapping[str, object]) -> JournalEntry:
        if self._fd < 0:
            raise ReceiptJournalError("receipt journal is closed")
        body: dict[str, object] = {
            "seq": len(self.entries),
            "prev_sha256": self.head,
            **fields,
            "recorded_at": format_timestamp(self._clock()),
        }
        try:
            body["entry_sha256"] = chain_entry_sha256(body)
            line = canonical_line(body)
        except FormatError as error:
            raise ReceiptJournalError(f"journal entry cannot be encoded: {error}") from None
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


_ATTESTATION: Final = re.compile(r"docs/decisions/[A-Za-z0-9._/-]{1,200}\.md")
MAX_TORN_TAIL_BYTES: Final = 1024 * 1024
RECOVERY_BINDING: Final = Binding(acquisition_id="journal_recovery", plan_sha256=GENESIS)


def recover_torn_tail(path: Path, attestation: str, *, clock: Clock = _utc_now) -> JournalEntry:
    """Owner-run recovery of a journal whose final entry was torn by a crash (RT-B6-26 d).

    A torn tail (bytes after the last newline) is indistinguishable, by the bytes alone,
    from deliberate truncation-and-append tampering. This tool therefore runs only with an
    owner attestation: ``attestation`` must cite the ``docs/decisions/`` record in which the
    owner states that the crash happened. Every complete entry must still verify. The torn
    bytes are preserved, never discarded: they are written to a new read-only evidence file
    beside the journal, then the journal is truncated to its last complete entry, and a
    ``tail_recovered`` entry recording the evidence file, its size and SHA-256, and the
    attestation is appended. Nothing is repaired silently.
    """
    if not isinstance(attestation, str) or _ATTESTATION.fullmatch(attestation) is None:
        raise ReceiptJournalError("attestation must cite a docs/decisions record")
    if ".." in attestation:
        raise ReceiptJournalError("attestation must cite a docs/decisions record")
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as error:
        raise ReceiptJournalError(f"receipt journal cannot be opened: {error}") from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ReceiptJournalError("receipt journal is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        size = os.fstat(fd).st_size
        if size > MAX_JOURNAL_BYTES:
            raise ReceiptJournalError("receipt journal exceeds its size limit")
        data = pread_all(fd, size)
        if not data or data.endswith(b"\n"):
            raise ReceiptJournalError("receipt journal has no torn tail")
        cut = data.rfind(b"\n") + 1
        entries = verify_journal(data[:cut])
        tail = data[cut:]
        if len(tail) > MAX_TORN_TAIL_BYTES:
            raise ReceiptJournalError("torn tail is larger than one entry could be")
        digest = sha256_hex(tail)
        evidence = path.parent / f"{path.name}.torn-{len(entries)}-{digest[:16]}"
        evidence_fd = os.open(evidence, NEW_FILE_FLAGS, 0o400)
        try:
            append_exact(evidence_fd, tail, 0)
            os.fsync(evidence_fd)
        finally:
            os.close(evidence_fd)
        _fsync_dir(path.parent)
        os.ftruncate(fd, cut)
        os.fsync(fd)
    finally:
        os.close(fd)
    journal = ReceiptJournal(path, clock=clock)
    try:
        return journal.append_bound(
            ReceiptEvent.TAIL_RECOVERED,
            RECOVERY_BINDING,
            new_session_id(),
            evidence.name,
            len(tail),
            digest,
            {"attestation": attestation, "evidence_file": evidence.name},
        )
    finally:
        journal.close()


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
