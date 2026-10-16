"""G-6 state machine, v2 journal binding (RT-B6-27), and torn-tail recovery (RT-B6-26)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pmv.acquisition.receipts import (
    GENESIS,
    Binding,
    ReceiptEvent,
    ReceiptJournal,
    ReceiptJournalError,
    new_session_id,
    recover_torn_tail,
)
from pmv.acquisition.state import (
    FileState,
    StateError,
    next_state,
    replay,
)

BINDING = Binding("synthetic_acq_1", "a" * 64)
OTHER = Binding("synthetic_acq_1", "b" * 64)
SHA = "c" * 64
SESSION = new_session_id()
DECISION = "docs/decisions/synthetic_placeholder.md"


def _clock() -> datetime:
    return datetime(2099, 1, 1, tzinfo=UTC)


@pytest.fixture
def journal(tmp_path: Path) -> ReceiptJournal:
    path = tmp_path / "journal.jsonl"
    ReceiptJournal.create(path)
    return ReceiptJournal(path, clock=_clock)


def _happy(journal: ReceiptJournal, binding: Binding = BINDING, name: str = "a.csv") -> None:
    steps: list[tuple[ReceiptEvent, int | None, str | None, dict[str, object]]] = [
        (ReceiptEvent.APPROVED_FOR_FETCH, None, None, {"attempt": 1, "url": "https://x.example/a"}),
        (
            ReceiptEvent.RECEIVED,
            3,
            SHA,
            {
                "attempt": 1,
                "final_url": "https://x.example/a",
                "redirects": 0,
                "hash_source": "receipt",
            },
        ),
        (ReceiptEvent.INTEGRITY_VERIFIED, 3, SHA, {"kind": "file"}),
        (
            ReceiptEvent.PARSER_VERIFIED,
            3,
            SHA,
            {"verification_sha256": SHA, "worker_identity_sha256": SHA},
        ),
        (
            ReceiptEvent.BACKUP_VERIFIED,
            3,
            SHA,
            {"policy_id": "synthetic_p", "evidence_sha256": SHA},
        ),
        (ReceiptEvent.STORED, 3, SHA, {"path": "store/x/a.csv", "recovered": False}),
    ]
    for event, size, digest, detail in steps:
        journal.append_bound(event, binding, SESSION, name, size, digest, detail)


def test_full_sequence_replays_to_stored(journal: ReceiptJournal) -> None:
    _happy(journal)
    reopened = ReceiptJournal(journal.path)
    state = replay(reopened.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv"])
    assert state.files["a.csv"].state is FileState.STORED
    assert state.all_stored
    entry = reopened.entries[-1]
    assert (entry.acquisition_id, entry.plan_sha256) == (
        BINDING.acquisition_id,
        BINDING.plan_sha256,
    )


@pytest.mark.parametrize(
    ("state", "event"),
    [
        (FileState.NONE, ReceiptEvent.RECEIVED),
        (FileState.APPROVED, ReceiptEvent.STORED),
        (FileState.RECEIVED, ReceiptEvent.RECEIVED),
        (FileState.RECEIVED, ReceiptEvent.PARSER_VERIFIED),
        (FileState.INTEGRITY_VERIFIED, ReceiptEvent.BACKUP_VERIFIED),
        (FileState.PARSER_VERIFIED, ReceiptEvent.STORED),
        (FileState.STORED, ReceiptEvent.REJECTED),
        (FileState.STORED, ReceiptEvent.STORED),
        (FileState.REJECTED, ReceiptEvent.APPROVED_FOR_FETCH),
        (FileState.RECEIVED, ReceiptEvent.DISCARDED),
    ],
)
def test_illegal_transitions_are_refused(state: FileState, event: ReceiptEvent) -> None:
    with pytest.raises(StateError):
        next_state(state, event)


def test_no_event_exposes_rows_to_agents() -> None:
    names = {event.value for event in ReceiptEvent}
    assert not any("release_to_agent" in name or "agent" in name for name in names)


def test_duplicate_receipt_is_refused_on_replay(journal: ReceiptJournal) -> None:
    _happy(journal)
    journal.append_bound(
        ReceiptEvent.RECEIVED,
        BINDING,
        SESSION,
        "a.csv",
        3,
        SHA,
        {
            "attempt": 1,
            "final_url": "https://x.example/a",
            "redirects": 0,
            "hash_source": "receipt",
        },
    )
    with pytest.raises(StateError):
        replay(journal.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv"])


def test_conflicting_binding_is_refused(journal: ReceiptJournal) -> None:
    _happy(journal)
    with pytest.raises(StateError, match="different authorizing bundle"):
        replay(journal.entries, OTHER.acquisition_id, OTHER.plan_sha256, ["a.csv"])


def test_unplanned_file_is_refused(journal: ReceiptJournal) -> None:
    _happy(journal, name="b.csv")
    with pytest.raises(StateError, match="not in the plan"):
        replay(journal.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv"])


def test_attempts_must_be_in_sequence(journal: ReceiptJournal) -> None:
    journal.append_bound(
        ReceiptEvent.APPROVED_FOR_FETCH,
        BINDING,
        SESSION,
        "a.csv",
        None,
        None,
        {"attempt": 2, "url": "u"},
    )
    with pytest.raises(StateError, match="out of sequence"):
        replay(journal.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv"])


def test_completed_requires_every_file_stored(journal: ReceiptJournal) -> None:
    _happy(journal)
    journal.append_bound(
        ReceiptEvent.COMPLETED, BINDING, SESSION, "*", 10, SHA, {"record_path": "r", "files": 2}
    )
    with pytest.raises(StateError, match="before every file"):
        replay(journal.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv", "b.csv"])


def test_other_acquisitions_are_ignored(journal: ReceiptJournal) -> None:
    _happy(journal, binding=Binding("synthetic_other", "d" * 64))
    state = replay(journal.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv"])
    assert state.files["a.csv"].state is FileState.NONE
    assert not state.started


# --- v2 entry schema ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "size", "digest", "detail", "match"),
    [
        (ReceiptEvent.RECEIVED, None, None, {"attempt": 1}, "invalid field"),
        (ReceiptEvent.STORED, 3, SHA, {"path": "p"}, "wrong detail keys"),
        (ReceiptEvent.STORED, 3, SHA, {"path": "p", "recovered": "no"}, "invalid detail"),
        (ReceiptEvent.FETCH_FAILED, None, None, {"attempt": True, "code": "x"}, "invalid detail"),
        (ReceiptEvent.FETCH_FAILED, None, None, {"attempt": 1, "code": "a\nb"}, "invalid detail"),
        (ReceiptEvent.RELEASED, 3, SHA, {}, "wrong detail keys|invalid binding"),
        (ReceiptEvent.STORED, 3, SHA, {"path": "p", "recovered": 1.5}, "cannot be encoded"),
    ],
)
def test_v2_entries_have_closed_schemas(
    journal: ReceiptJournal,
    event: ReceiptEvent,
    size: int | None,
    digest: str | None,
    detail: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ReceiptJournalError, match=match):
        journal.append_bound(event, BINDING, SESSION, "a.csv", size, digest, detail)
    assert journal.entries == []


def test_unbound_append_refuses_v2_events(journal: ReceiptJournal) -> None:
    with pytest.raises(ReceiptJournalError, match="unbound"):
        journal.append(ReceiptEvent.STORED, SESSION, "a.csv", 3, SHA)


def test_binding_is_validated() -> None:
    with pytest.raises(ReceiptJournalError):
        Binding("Not An Identifier", SHA)
    with pytest.raises(ReceiptJournalError):
        Binding("synthetic_acq", "xyz")


def test_v1_and_v2_entries_share_one_chain(journal: ReceiptJournal) -> None:
    journal.append(ReceiptEvent.RECEIVED, SESSION, "old.csv", 3, SHA)
    _happy(journal)
    reopened = ReceiptJournal(journal.path)
    assert reopened.entries[0].acquisition_id is None
    assert reopened.entries[1].acquisition_id == BINDING.acquisition_id


# --- torn-tail recovery (RT-B6-26 d) ------------------------------------------------------


def test_torn_tail_is_preserved_and_recovered_with_attestation(journal: ReceiptJournal) -> None:
    _happy(journal)
    journal.close()
    data = journal.path.read_bytes()
    torn = b'{"seq":6,"prev'
    journal.path.write_bytes(data + torn)
    with pytest.raises(ReceiptJournalError, match="torn tail"):
        ReceiptJournal(journal.path)
    entry = recover_torn_tail(journal.path, DECISION, committed=lambda _p: True, clock=_clock)
    assert entry.event is ReceiptEvent.TAIL_RECOVERED
    assert entry.size_bytes == len(torn)
    assert entry.plan_sha256 == GENESIS
    evidence = journal.path.parent / str(entry.name)
    assert evidence.read_bytes() == torn
    assert evidence.stat().st_mode & 0o777 == 0o400
    reopened = ReceiptJournal(journal.path)
    assert len(reopened.entries) == 7
    state = replay(reopened.entries, BINDING.acquisition_id, BINDING.plan_sha256, ["a.csv"])
    assert state.files["a.csv"].state is FileState.STORED


@pytest.mark.parametrize("attestation", ["", "docs/other.md", "docs/decisions/../x.md", "x"])
def test_torn_tail_recovery_needs_an_owner_attestation(
    journal: ReceiptJournal, attestation: str
) -> None:
    journal.path.write_bytes(b'{"partial')
    with pytest.raises(ReceiptJournalError, match="attestation"):
        recover_torn_tail(journal.path, attestation, committed=lambda _p: True)
    assert journal.path.read_bytes() == b'{"partial'


def test_torn_tail_recovery_refuses_a_whole_journal_or_tampered_body(
    journal: ReceiptJournal,
) -> None:
    _happy(journal)
    with pytest.raises(ReceiptJournalError, match="no torn tail"):
        recover_torn_tail(journal.path, DECISION, committed=lambda _p: True)
    data = journal.path.read_bytes().replace(b'"attempt":1', b'"attempt":2', 1)
    journal.path.write_bytes(data + b"{")
    with pytest.raises(ReceiptJournalError, match="wrong entry hash"):
        recover_torn_tail(journal.path, DECISION, committed=lambda _p: True)
