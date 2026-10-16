"""Explicit acquisition states, replayed deterministically from the receipt journal (G-6).

Every file of an acquisition moves through these states, and only along these arrows:

    (none) --approved_for_fetch--> APPROVED
    APPROVED --fetch_failed--> FETCH_FAILED --approved_for_fetch--> APPROVED (a retry)
    APPROVED --received--> RECEIVED          (bytes in quarantine, hashed on receipt)
    RECEIVED --integrity_verified--> INTEGRITY_VERIFIED   (hash and signature)
    INTEGRITY_VERIFIED --parser_verified--> PARSER_VERIFIED   (isolated worker)
    PARSER_VERIFIED --backup_verified--> BACKUP_VERIFIED   (A-3 backup and restore)
    BACKUP_VERIFIED --stored--> STORED       (accepted into the protected raw store)
    any state before STORED --rejected--> REJECTED   (terminal)
    RECEIVED .. BACKUP_VERIFIED --stage_failed--> the same state (environmental stop)
    APPROVED or FETCH_FAILED --discarded--> FETCH_FAILED (unjournaled bytes set aside)

When every file is STORED, one ``completed`` entry closes the acquisition. There is no
state, event, or arrow that makes a row visible to an agent: storage is not release
(``docs/external_access.md`` A-8). The state of an acquisition is a pure function of the
journal, so a restart resumes exactly where the last durable entry left off.

Replay fails closed on: an entry for the acquisition bound to a different
authorizing bundle (``plan_sha256``); an event the current state does not allow (for
example a second ``received``, or ``stored`` before ``backup_verified``); a file not in
the plan; and anything after ``completed``.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from pmv.acquisition.receipts import JournalEntry, ReceiptEvent


class FileState(StrEnum):
    NONE = "none"
    APPROVED = "approved_for_fetch"
    FETCH_FAILED = "fetch_failed"
    RECEIVED = "received"
    INTEGRITY_VERIFIED = "integrity_verified"
    PARSER_VERIFIED = "parser_verified"
    BACKUP_VERIFIED = "backup_verified"
    STORED = "stored"
    REJECTED = "rejected"


class StateError(Exception):
    """The journal or a requested transition is inconsistent with the state machine."""


_PRE_STORE: Final = frozenset(
    {
        FileState.NONE,
        FileState.APPROVED,
        FileState.FETCH_FAILED,
        FileState.RECEIVED,
        FileState.INTEGRITY_VERIFIED,
        FileState.PARSER_VERIFIED,
        FileState.BACKUP_VERIFIED,
    }
)
TRANSITIONS: Final[dict[tuple[FileState, ReceiptEvent], FileState]] = {
    (FileState.NONE, ReceiptEvent.APPROVED_FOR_FETCH): FileState.APPROVED,
    (FileState.FETCH_FAILED, ReceiptEvent.APPROVED_FOR_FETCH): FileState.APPROVED,
    (FileState.APPROVED, ReceiptEvent.FETCH_FAILED): FileState.FETCH_FAILED,
    (FileState.APPROVED, ReceiptEvent.RECEIVED): FileState.RECEIVED,
    (FileState.APPROVED, ReceiptEvent.DISCARDED): FileState.FETCH_FAILED,
    (FileState.FETCH_FAILED, ReceiptEvent.DISCARDED): FileState.FETCH_FAILED,
    (FileState.RECEIVED, ReceiptEvent.INTEGRITY_VERIFIED): FileState.INTEGRITY_VERIFIED,
    (FileState.INTEGRITY_VERIFIED, ReceiptEvent.PARSER_VERIFIED): FileState.PARSER_VERIFIED,
    (FileState.PARSER_VERIFIED, ReceiptEvent.BACKUP_VERIFIED): FileState.BACKUP_VERIFIED,
    (FileState.BACKUP_VERIFIED, ReceiptEvent.STORED): FileState.STORED,
    **{(state, ReceiptEvent.REJECTED): FileState.REJECTED for state in _PRE_STORE},
    # An environmental stop of a stage is recorded without changing the state (RT-B7-04).
    **{
        (state, ReceiptEvent.STAGE_FAILED): state
        for state in (
            FileState.RECEIVED,
            FileState.INTEGRITY_VERIFIED,
            FileState.PARSER_VERIFIED,
            FileState.BACKUP_VERIFIED,
        )
    },
}
ACQUISITION_NAME: Final = "*"


def next_state(current: FileState, event: ReceiptEvent) -> FileState:
    """The state after ``event``, or StateError if the state machine does not allow it."""
    try:
        return TRANSITIONS[(current, event)]
    except KeyError:
        raise StateError(f"{event.value} is not allowed in state {current.value}") from None


@dataclass(slots=True)
class FileProgress:
    """What the journal says about one planned file."""

    state: FileState = FileState.NONE
    attempts: int = 0
    received: JournalEntry | None = None
    last: JournalEntry | None = None
    entries: list[JournalEntry] = field(default_factory=list)


@dataclass(slots=True)
class AcquisitionState:
    acquisition_id: str
    plan_sha256: str
    files: dict[str, FileProgress]
    completed: JournalEntry | None = None

    @property
    def started(self) -> bool:
        return any(progress.entries for progress in self.files.values())

    def require(self, name: str, event: ReceiptEvent) -> FileState:
        """Check that ``event`` may be appended for ``name`` now; return the new state."""
        if self.completed is not None:
            raise StateError("the acquisition is already completed")
        if name not in self.files:
            raise StateError("file is not in the plan")
        return next_state(self.files[name].state, event)

    def apply(self, entry: JournalEntry) -> None:
        """Advance the state by one journal entry of this acquisition."""
        if entry.plan_sha256 != self.plan_sha256:
            raise StateError("journal entry is bound to a different authorizing bundle")
        if entry.event is ReceiptEvent.COMPLETED:
            if self.completed is not None or entry.name != ACQUISITION_NAME:
                raise StateError("acquisition completed twice or under a file name")
            if any(progress.state is not FileState.STORED for progress in self.files.values()):
                raise StateError("acquisition completed before every file was stored")
            self.completed = entry
            return
        progress = self.files.get(entry.name)
        if progress is None:
            raise StateError("journal names a file that is not in the plan")
        new = self.require(entry.name, entry.event)
        if entry.event is ReceiptEvent.APPROVED_FOR_FETCH:
            progress.attempts += 1
            attempt = entry.detail.get("attempt") if entry.detail else None
            if attempt != progress.attempts:
                raise StateError("fetch attempts are out of sequence")
        if entry.event is ReceiptEvent.RECEIVED:
            progress.received = entry
        progress.state = new
        progress.last = entry
        progress.entries.append(entry)

    @property
    def all_stored(self) -> bool:
        return all(progress.state is FileState.STORED for progress in self.files.values())

    @property
    def rejected(self) -> list[str]:
        return [name for name, p in self.files.items() if p.state is FileState.REJECTED]


def replay(
    entries: Iterable[JournalEntry],
    acquisition_id: str,
    plan_sha256: str,
    names: Sequence[str],
) -> AcquisitionState:
    """Rebuild the acquisition's state from every journal entry bound to it."""
    if len(set(names)) != len(names) or ACQUISITION_NAME in names:
        raise StateError("planned file names must be unique")
    state = AcquisitionState(
        acquisition_id=acquisition_id,
        plan_sha256=plan_sha256,
        files={name: FileProgress() for name in names},
    )
    for entry in entries:
        if entry.acquisition_id == acquisition_id:
            state.apply(entry)
    return state
