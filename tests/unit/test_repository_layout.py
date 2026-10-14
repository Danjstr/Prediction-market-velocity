"""Source and control trees must never be silently ignored by Git (Step 11 F-02).

An ignored file under these trees is never committed, never run by CI, invisible to the
Git code identity, and outside the untracked secret scan.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROTECTED_TREES = ("src", "tests", "research", "docs", "scripts", "schemas", ".claude")
# Ignored on purpose: bytecode caches and the personal Claude settings override (which
# the protected-information settings check validates separately).
ALLOWED_IGNORED_PARTS = ("__pycache__",)
ALLOWED_IGNORED_PATHS = (".claude/settings.local.json",)


def git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    return subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(REPO), "-c", "core.excludesFile=/dev/null", *arguments],
        env=environment,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/pmv/data/loader.py",
        "src/pmv/logs/handler.py",
        "src/data/ingest.py",
        "tests/unit/data/test_x.py",
        "research/data/notes.yaml",
        "docs/data/notes.md",
        "scripts/data/run.sh",
        "schemas/data/x.json",
        ".claude/agents/data/x.md",
        "src/pmv/secrets/redact.py",
        "src/pmv/venv/x.py",
        "src/pmv/keystore/x.py",
        "tests/fixtures/sample.parquet",
        "tests/fixtures/sample.db",
        "tests/fixtures/sample.sqlite",
        "tests/fixtures/sample.log",
        "tests/fixtures/sample.feather",
        "research/notes/sample.arrow",
    ],
)
def test_paths_inside_source_and_control_trees_are_not_ignored(path: str) -> None:
    # check-ignore exits 1 when the path is NOT ignored (it need not exist).
    assert git("check-ignore", "-q", "--no-index", path).returncode == 1


@pytest.mark.parametrize(
    "path",
    [
        "data/raw.bin",
        "logs/run.log",
        "secrets/token.txt",
        "venv/bin/python",
        ".venv/bin/python",
        "keystore/key.json",
        "local.parquet",
        "local.db",
        "local.sqlite3",
        "run.log",
    ],
)
def test_root_level_data_and_logs_stay_ignored(path: str) -> None:
    assert git("check-ignore", "-q", "--no-index", path).returncode == 0


def test_no_existing_file_in_a_protected_tree_is_ignored() -> None:
    listed = git(
        "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", *PROTECTED_TREES
    )
    assert listed.returncode == 0
    offenders = [
        item
        for item in (raw.decode("utf-8", "replace") for raw in listed.stdout.split(b"\0") if raw)
        if item not in ALLOWED_IGNORED_PATHS
        and not any(part in ALLOWED_IGNORED_PARTS for part in Path(item).parts)
    ]
    assert offenders == []
