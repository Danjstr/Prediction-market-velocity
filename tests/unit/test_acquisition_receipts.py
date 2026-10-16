"""Tests for the durable receipt journal (RT-B6-12): synthetic data only."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pmv.acquisition.quarantine import Quarantine, QuarantineError
from pmv.acquisition.receipts import (
    GENESIS,
    ReceiptEvent,
    ReceiptJournal,
    ReceiptJournalError,
    verify_journal,
)
from pmv.acquisition.records import AcquisitionManifest
from pmv.integrity import sha256_hex

DATA = b"a,b\n1,2\n"
SESSION = "0" * 31 + "1"


def _clock() -> datetime:
    return datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def _new(tmp_path: Path) -> ReceiptJournal:
    path = tmp_path / "receipts.jsonl"
    ReceiptJournal.create(path)
    return ReceiptJournal(path, clock=_clock)


def _manifest(name: str, data: bytes, file_format: str = "csv") -> AcquisitionManifest:
    document: dict[str, Any] = {
        "manifest_version": 1,
        "acquisition_id": "acq_example",
        "approval_id": "appr_example",
        "licence_id": "lic_example",
        "input_licence_ids": ["lic_example"],
        "source_url": "https://files.example.com/history/a.csv",
        "retrieved_at": "2099-01-01T00:00:00.000000Z",
        "upstream_identity": "Synthetic",
        "is_primary_source": True,
        "mirror_lineage": [],
        "vendor_version": "v1",
        "tool_git_commit": "c" * 40,
        "tool_tree_dirty": False,
        "reproducible_from_provider": "no",
        "files": [
            {
                "name": name,
                "format": file_format,
                "size_bytes": len(data),
                "sha256": sha256_hex(data),
            }
        ],
    }
    return AcquisitionManifest.from_document(document)


def test_entries_chain_and_survive_reopen(tmp_path: Path) -> None:
    journal = _new(tmp_path)
    first = journal.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))
    second = journal.append(ReceiptEvent.RELEASED, SESSION, "a.csv", 8, sha256_hex(DATA))
    journal.close()
    reopened = ReceiptJournal(journal.path)
    assert [entry.seq for entry in reopened.entries] == [0, 1]
    assert reopened.entries[0] == first
    assert reopened.head == second.entry_sha256 != GENESIS


def test_create_never_replaces_an_existing_journal(tmp_path: Path) -> None:
    journal = _new(tmp_path)
    journal.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))
    with pytest.raises(ReceiptJournalError, match="already exists"):
        ReceiptJournal.create(journal.path)
    assert len(ReceiptJournal(journal.path).entries) == 1


def test_missing_journal_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ReceiptJournalError, match="does not exist"):
        ReceiptJournal(tmp_path / "absent.jsonl")


def test_symlinked_journal_is_refused(tmp_path: Path) -> None:
    journal = _new(tmp_path)
    link = tmp_path / "link.jsonl"
    link.symlink_to(journal.path)
    with pytest.raises(ReceiptJournalError, match="cannot be opened"):
        ReceiptJournal(link)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda data: data[:-1], "torn tail"),
        (lambda data: data.replace(b'"size_bytes":8', b'"size_bytes":9', 1), "entry hash"),
        (lambda data: data.split(b"\n", 1)[1], "out of sequence"),
        (lambda data: data + data.split(b"\n", 1)[0] + b"\n", "out of sequence"),
        (lambda data: data.replace(b"received", b"accepted", 1), "invalid field|entry hash"),
        (lambda data: b"{}\n" + data, "wrong keys"),
        (lambda data: b"not json\n", "malformed"),
    ],
)
def test_tampered_journal_fails_closed(tmp_path: Path, mutate: object, match: str) -> None:
    journal = _new(tmp_path)
    journal.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))
    journal.append(ReceiptEvent.RELEASED, SESSION, "a.csv", 8, sha256_hex(DATA))
    journal.close()
    data = journal.path.read_bytes()
    with pytest.raises(ReceiptJournalError, match=match):
        verify_journal(mutate(data))  # type: ignore[operator]


def test_broken_chain_is_refused(tmp_path: Path) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    one = _new(tmp_path / "one")
    one.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))
    one.append(ReceiptEvent.RECEIVED, SESSION, "b.csv", 8, sha256_hex(DATA))
    second_line = one.path.read_bytes().splitlines(keepends=True)[1]
    two = _new(tmp_path / "two")
    two.append(ReceiptEvent.RECEIVED, SESSION, "x.csv", 8, sha256_hex(DATA))
    with pytest.raises(ReceiptJournalError, match="hash chain"):
        verify_journal(two.path.read_bytes() + second_line)


def test_concurrent_append_is_detected(tmp_path: Path) -> None:
    journal = _new(tmp_path)
    other = ReceiptJournal(journal.path)
    other.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))
    with pytest.raises(ReceiptJournalError, match="changed since it was verified"):
        journal.append(ReceiptEvent.RECEIVED, SESSION, "b.csv", 8, sha256_hex(DATA))
    assert len(ReceiptJournal(journal.path).entries) == 1


def test_replaced_journal_file_is_detected(tmp_path: Path) -> None:
    journal = _new(tmp_path)
    os.unlink(journal.path)
    ReceiptJournal.create(journal.path)
    with pytest.raises(ReceiptJournalError, match="changed since it was verified"):
        journal.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))


def test_quarantine_journals_receipt_and_release(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    journal = _new(tmp_path)
    quarantine = Quarantine(quarantine_dir, journal=journal)
    quarantine.receive("a.csv", [DATA])
    quarantine.release("a.csv", _manifest("a.csv", DATA), released)
    entries = ReceiptJournal(journal.path).entries
    assert [(entry.event, entry.name, entry.sha256) for entry in entries] == [
        (ReceiptEvent.RECEIVED, "a.csv", sha256_hex(DATA)),
        (ReceiptEvent.RELEASED, "a.csv", sha256_hex(DATA)),
    ]
    assert {entry.session_id for entry in entries} == {quarantine.session_id}


def test_receipt_survives_an_interrupted_session(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    quarantine_dir.mkdir()
    journal = _new(tmp_path)
    Quarantine(quarantine_dir, journal=journal).receive("a.csv", [DATA])
    del journal  # the process "crashes": the in-memory receipt is gone
    entries = ReceiptJournal(tmp_path / "receipts.jsonl").entries
    assert [(entry.event, entry.size_bytes) for entry in entries] == [
        (ReceiptEvent.RECEIVED, len(DATA))
    ]


def test_journal_inside_quarantine_is_refused(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    quarantine_dir.mkdir()
    journal = _new(quarantine_dir)
    with pytest.raises(QuarantineError, match=r"empty|outside the quarantine"):
        Quarantine(quarantine_dir, journal=journal)


def test_failed_receipt_journal_append_removes_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pmv.acquisition import receipts as module

    quarantine_dir = tmp_path / "q"
    quarantine_dir.mkdir()
    journal = _new(tmp_path)

    def full_disk(_fd: int, _data: bytes, _size: int) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(module, "append_exact", full_disk)
    quarantine = Quarantine(quarantine_dir, journal=journal)
    with pytest.raises(ReceiptJournalError, match="append failed"):
        quarantine.receive("a.csv", [DATA])
    assert list(quarantine_dir.iterdir()) == []
    assert quarantine.receipts == {}


def test_failed_release_journal_append_keeps_the_quarantine_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quarantine_dir = tmp_path / "q"
    released = tmp_path / "released"
    quarantine_dir.mkdir()
    released.mkdir()
    journal = _new(tmp_path)
    quarantine = Quarantine(quarantine_dir, journal=journal)
    quarantine.receive("a.csv", [DATA])

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ReceiptJournalError("receipt journal append failed: synthetic")

    monkeypatch.setattr(journal, "append", refuse)
    with pytest.raises(QuarantineError, match="not journaled"):
        quarantine.release("a.csv", _manifest("a.csv", DATA), released)
    assert (quarantine_dir / "a.csv").exists()


def test_append_never_grows_past_the_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pmv.acquisition import receipts as module

    journal = _new(tmp_path)
    journal.append(ReceiptEvent.RECEIVED, SESSION, "a.csv", 8, sha256_hex(DATA))
    monkeypatch.setattr(module, "MAX_JOURNAL_BYTES", journal.path.stat().st_size + 10)
    with pytest.raises(ReceiptJournalError, match="exceed its size limit"):
        journal.append(ReceiptEvent.RELEASED, SESSION, "a.csv", 8, sha256_hex(DATA))
    assert len(ReceiptJournal(journal.path).entries) == 1
