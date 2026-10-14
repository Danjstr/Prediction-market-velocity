"""Personal/global Git ignore rules can never hide a file from the secret scanner.

Runs the real scripts/scan_secrets.sh, with the pinned Betterleaks binary, against a
temporary repository and a temporary HOME. Everything is synthetic: the canary is generated
at runtime and the real HOME is used only to locate the pinned binary, which is copied.
"""

import hashlib
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _pin(name: str) -> str:
    lines = (REPO / "scripts" / "betterleaks.pin").read_text(encoding="utf-8").splitlines()
    (value,) = [line.split("=", 1)[1] for line in lines if line.startswith(f"{name}=")]
    return value


VERSION = _pin("version")
INSTALLED = Path.home() / ".local" / "share" / "pmv-tools" / "betterleaks" / VERSION / "betterleaks"

pytestmark = pytest.mark.skipif(
    not INSTALLED.is_file(),
    reason="the pinned Betterleaks binary is not installed (scripts/install_betterleaks.sh)",
)


def _canary() -> str:
    digest = hashlib.sha256(secrets.token_bytes(16)).hexdigest()[:32].upper()
    return f"PMVCANARY_{digest}"


def _git(repo: Path, home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Ordinary Git as a user with this HOME would run it (global excludes apply)."""
    environment = {"PATH": "/usr/bin:/bin", "HOME": str(home), "LC_ALL": "C"}
    return subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(repo), *arguments],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    binary = home / ".local" / "share" / "pmv-tools" / "betterleaks" / VERSION / "betterleaks"
    binary.parent.mkdir(parents=True)
    shutil.copyfile(INSTALLED, binary)
    binary.chmod(0o500)
    (home / ".config" / "git").mkdir(parents=True)
    (home / ".config" / "git" / "ignore").write_text("leaky.txt\nbenign.txt\n", encoding="utf-8")
    (home / ".gitconfig").write_text(
        "[user]\n\tname = pmv-test\n\temail = test@example.invalid\n"
        "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n",
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for name in ("scan_secrets.sh", "betterleaks.pin"):
        shutil.copy2(REPO / "scripts" / name, repo / "scripts" / name)
    shutil.copy2(REPO / ".betterleaks.toml", repo / ".betterleaks.toml")
    (repo / ".gitignore").write_text("repo-ignored.txt\n", encoding="utf-8")
    assert _git(repo, home, "init", "-q").returncode == 0
    assert _git(repo, home, "add", "-A").returncode == 0
    assert _git(repo, home, "commit", "-q", "-m", "scanner fixture").returncode == 0
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    return repo, home, scratch


def _scan(repo: Path, home: Path, scratch: Path) -> subprocess.CompletedProcess[str]:
    environment = {"PATH": "/usr/bin:/bin", "HOME": str(home), "TMPDIR": str(scratch)}
    return subprocess.run(  # noqa: S603 - the project's own scanner
        [str(repo / "scripts" / "scan_secrets.sh")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _reported(output: str) -> set[str]:
    return {
        line.split("file=", 1)[1].split("'")[1]
        for line in output.splitlines()
        if line.strip().startswith("finding:")
    }


def test_global_ignores_cannot_hide_files_from_the_secret_scanner(
    setup: tuple[Path, Path, Path],
) -> None:
    repo, home, scratch = setup
    leaky, benign, repo_ignored = repo / "leaky.txt", repo / "benign.txt", repo / "repo-ignored.txt"
    canary = _canary()
    leaky.write_text(f"synthetic {canary}\n", encoding="utf-8")
    benign.write_text("nothing secret here\n", encoding="utf-8")
    repo_ignored.write_text(f"synthetic {_canary()}\n", encoding="utf-8")

    # A: ordinary Git considers both files globally ignored (and the third repo-ignored).
    for path in (leaky, benign, repo_ignored):
        assert _git(repo, home, "check-ignore", "-q", path.name).returncode == 0
    listed = _git(repo, home, "ls-files", "--others", "--exclude-standard").stdout.split()
    assert not {"leaky.txt", "benign.txt", "repo-ignored.txt"} & set(listed)

    # C, D: the real scanner still scans leaky.txt, fails, and names it (values redacted).
    result = _scan(repo, home, scratch)
    assert result.returncode == 1, result.stderr
    assert "RESULT: SECRET DETECTED" in result.stderr
    assert _reported(result.stdout) == {str(leaky)}
    assert canary not in result.stdout + result.stderr

    # B: benign.txt is enumerated too: the same globally ignored name, given a canary, is found.
    leaky.unlink()
    benign.write_text(f"synthetic {_canary()}\n", encoding="utf-8")
    result = _scan(repo, home, scratch)
    assert result.returncode == 1, result.stderr
    assert _reported(result.stdout) == {str(benign)}

    # E, F: with benign content there is no false finding, and the repository's own
    # .gitignore still excludes repo-ignored.txt (its canary is never read).
    benign.write_text("nothing secret here\n", encoding="utf-8")
    result = _scan(repo, home, scratch)
    assert result.returncode == 0, result.stderr
    assert "RESULT: CLEAN" in result.stdout
    assert "untracked: 0 finding(s)" in result.stdout

    # G: the scanner left nothing behind in its scratch area.
    assert not os.listdir(scratch)
