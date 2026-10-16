"""B07 regressions: B06 quarantine intake cleanup (RT-B6-26 c) and real-mode Git facts."""

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from pmv.acquisition.pipeline import GitRepository
from pmv.acquisition.quarantine import Quarantine
from pmv.acquisition.receipts import ReceiptJournal


def test_failed_intake_leaves_no_partial_file_in_quarantine(tmp_path: Path) -> None:
    quarantine_dir = tmp_path / "q"
    quarantine_dir.mkdir()
    ReceiptJournal.create(tmp_path / "receipts.jsonl")
    quarantine = Quarantine(quarantine_dir, journal=ReceiptJournal(tmp_path / "receipts.jsonl"))

    def interrupted() -> Iterator[bytes]:
        yield b"a,b\n"
        raise ConnectionResetError("synthetic interruption")

    with pytest.raises(ConnectionResetError):
        quarantine.receive("a.csv", interrupted())
    assert list(quarantine_dir.iterdir()) == []
    # The next intake session is not blocked by a leftover file.
    Quarantine(quarantine_dir, journal=ReceiptJournal(tmp_path / "receipts.jsonl"))


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed git commands on a temporary repository
        [  # noqa: S607 - git from PATH, as GitRepository uses it
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=synthetic",
            "-c",
            "user.email=synthetic@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *arguments,
        ],
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


def test_git_repository_facts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("a\n")
    (root / "src").mkdir()
    (root / "src" / "x.py").write_text("x = 1\n")
    _git(root, "add", "docs/a.md", "src/x.py")
    _git(root, "commit", "-q", "-m", "first")
    first = _git(root, "rev-parse", "HEAD")
    repository = GitRepository(root)
    assert repository.head() == first
    assert repository.tree_clean()
    assert repository.committed_unchanged("docs/a.md")
    assert not repository.committed_unchanged("docs/missing.md")
    assert repository.is_ancestor(first)
    assert not repository.is_ancestor("f" * 40)
    (root / "src" / "x.py").write_text("x = 2\n")
    assert not repository.tree_clean()
    _git(root, "commit", "-q", "-am", "second")
    assert not repository.unchanged_since(first, "src")
    assert repository.unchanged_since(first, "docs")
    (root / "docs" / "a.md").write_text("changed\n")
    assert not repository.committed_unchanged("docs/a.md")
    (root / "untracked.txt").write_text("u\n")
    assert not repository.tree_clean()
