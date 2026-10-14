"""Integration checks for the protected-information embargo (Phase 0 Step 9).

The sentinel probe runs only with ``PMV_SENTINEL_PROBE=1``, inside the Claude Code sandbox,
after the project owner has created a synthetic, non-secret sentinel OUTSIDE the sandbox:

    mkdir -p ~/pmv-protected/sentinel
    echo PMV-SYNTHETIC-SENTINEL-NOT-SECRET > ~/pmv-protected/sentinel/SENTINEL.txt

Invariant: the real protected contents are never read, modified, deleted, or copied into
the repository, and nothing persists into the real protected directory. Claude Code masks
the denied path inside Bash with an isolated tmpfs, so listing an empty masked directory or
creating entries inside that mask is acceptable and is not tested. Persistence into the
underlying real directory cannot be proven from inside the sandbox: the owner verifies it
outside Claude before and after the probe (docs/protected_information.md). The owner removes
the sentinel afterwards.

Every probe that attempts a change first asserts that the sentinel is NOT visible, so a run
outside the sandbox fails before it could touch the real sentinel.
"""

import ast
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pmv.data_access_guard import (
    PROTECTED_ROOT,
    DataRequest,
    Guard,
    RefusalReason,
    Window,
    check_config,
    check_path,
)

REPO = Path(__file__).resolve().parents[2]
SENTINEL = PROTECTED_ROOT / "sentinel" / "SENTINEL.txt"
MARKER = "PMV-SYNTHETIC-SENTINEL-NOT-SECRET"
NETWORK_MODULES = frozenset(
    {
        "aiohttp",
        "asyncio",
        "ftplib",
        "http",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "ssl",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
    }
)


def request(provider: str, family: str) -> DataRequest:
    return DataRequest(
        "integration_1",
        "data_scientist",
        Window(
            provider,
            family,
            "historical_observation",
            datetime(2025, 6, 1, tzinfo=UTC),
            datetime(2025, 6, 2, tzinfo=UTC),
        ),
    )


def test_the_real_repository_refuses_real_market_data_until_a_scope_is_declared() -> None:
    guard = Guard.from_repo(REPO)
    assert guard.decide(request("coinbase", "btc_spot")).reason is (
        RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    )
    assert guard.decide(request("kalshi", "kalshi_btc_contracts")).reason is (
        RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    )
    assert guard.decide(request("pmv_synthetic", "synthetic_fixture")).allowed


def test_the_committed_settings_pass_the_configuration_check() -> None:
    assert check_config(REPO) == []


@pytest.mark.parametrize("module", ["protected_scope", "data_access_guard"])
def test_the_embargo_modules_import_no_network_library(module: str) -> None:
    tree = ast.parse((REPO / "src" / "pmv" / f"{module}.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not imported & NETWORK_MODULES


def test_the_guard_refuses_the_protected_location_and_links_into_it(tmp_path: Path) -> None:
    assert check_path(SENTINEL) is RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    traversal = PROTECTED_ROOT.parent / "elsewhere" / ".." / PROTECTED_ROOT.name / "x"
    assert check_path(traversal) is RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    assert check_path(Path("~") / PROTECTED_ROOT.name / "x") is (
        RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    )
    link = tmp_path / "link"
    link.symlink_to(PROTECTED_ROOT)
    assert check_path(link / "sentinel" / "SENTINEL.txt") is (
        RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    )


# ----- sentinel probe (owner-run, inside the sandbox) -----

probe = pytest.mark.skipif(
    os.environ.get("PMV_SENTINEL_PROBE") != "1",
    reason="set PMV_SENTINEL_PROBE=1 after creating the synthetic sentinel outside the sandbox",
)


def _shell(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed probe commands
        list(arguments), capture_output=True, text=True, check=False, timeout=30
    )


def _require_masked() -> None:
    """Fail before any change attempt if the real sentinel or its directory is visible."""
    assert not os.path.lexists(SENTINEL), "the sentinel is visible: not masked, or not sandboxed"
    assert not os.path.lexists(SENTINEL.parent)


@probe
def test_probe_the_real_protected_entries_are_not_visible() -> None:
    _require_masked()
    try:
        entries = os.listdir(PROTECTED_ROOT)
    except OSError:
        return
    assert SENTINEL.parent.name not in entries


@probe
def test_probe_python_reads_of_the_sentinel_fail() -> None:
    with pytest.raises(OSError):  # noqa: PT011 - any OS refusal is acceptable
        SENTINEL.read_text(encoding="utf-8")
    with pytest.raises(OSError):  # noqa: PT011
        open(SENTINEL, encoding="utf-8").read()  # noqa: SIM115 - probes builtin open


@probe
def test_probe_traversal_and_repo_symlinks_cannot_reach_the_sentinel() -> None:
    traversal = REPO / ".." / "pmv-protected" / "sentinel" / "SENTINEL.txt"
    if REPO.parent == PROTECTED_ROOT.parent:
        with pytest.raises(OSError):  # noqa: PT011
            traversal.read_text(encoding="utf-8")
    link = REPO / ".sentinel-probe-link"
    link.symlink_to(PROTECTED_ROOT)
    try:
        with pytest.raises(OSError):  # noqa: PT011
            (link / "sentinel" / "SENTINEL.txt").read_text(encoding="utf-8")
    finally:
        link.unlink()


@probe
@pytest.mark.parametrize("command", ["cat", "head", "tail"])
def test_probe_shell_readers_cannot_read_the_sentinel(command: str) -> None:
    executable = shutil.which(command)
    assert executable is not None
    result = _shell(executable, str(SENTINEL))
    assert result.returncode != 0
    assert MARKER not in result.stdout + result.stderr


@probe
def test_probe_copies_and_redirection_create_no_repository_artifact() -> None:
    cp, bash = shutil.which("cp"), shutil.which("bash")
    assert cp is not None
    assert bash is not None
    targets = [REPO / f".sentinel-probe-{name}.txt" for name in ("cp", "redirect", "copyfile")]
    try:
        assert _shell(cp, str(SENTINEL), str(targets[0])).returncode != 0
        redirect = _shell(bash, "-c", 'cat < "$1" > "$2"', "probe", str(SENTINEL), str(targets[1]))
        assert redirect.returncode != 0
        with pytest.raises(OSError):  # noqa: PT011
            shutil.copyfile(SENTINEL, targets[2])
        for target in targets:
            assert not target.exists() or MARKER not in target.read_text(encoding="utf-8")
        assert not targets[0].exists()
        assert not targets[2].exists()
    finally:
        for target in targets:
            target.unlink(missing_ok=True)


@probe
def test_probe_the_sentinel_cannot_be_modified_touched_or_deleted() -> None:
    _require_masked()
    with pytest.raises(OSError):  # noqa: PT011
        open(SENTINEL, "a", encoding="utf-8").write("x")  # noqa: SIM115 - probes append
    _require_masked()
    with pytest.raises(OSError):  # noqa: PT011
        os.utime(SENTINEL)
    with pytest.raises(OSError):  # noqa: PT011
        SENTINEL.unlink()
    with pytest.raises(OSError):  # noqa: PT011
        SENTINEL.write_text("x", encoding="utf-8")
    bash = shutil.which("bash")
    assert bash is not None
    assert _shell(bash, "-c", 'echo x >> "$1"', "probe", str(SENTINEL)).returncode != 0
