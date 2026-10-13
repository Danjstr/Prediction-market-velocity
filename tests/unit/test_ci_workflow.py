"""Static policy checks for the CI workflow and the uv pin.

These are textual checks of the approved values, not full YAML validation.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
UV_PIN = REPO / "scripts" / "uv.pin"

APPROVED_ACTIONS = {
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1": "# v7.0.1",
    "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97": "# v7.0.0",
}
APPROVED_UV_PIN = {
    "version": "0.13.0",
    "archive": "uv-x86_64-unknown-linux-gnu.tar.gz",
    "archive_sha256": "1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154",
    "archive_size": "17380567",
}
APPROVED_TRIGGERS = ["  pull_request:", "  push:", "    branches: [main]"]
# One marker per step, in the required order: bootstrap and security steps must all
# precede the quality gate, and the cleanliness check must come last.
REQUIRED_STEP_ORDER = [
    "uses: actions/checkout@",
    "uses: actions/setup-python@",
    "scripts/install_uv.sh",
    "scripts/install_betterleaks.sh",
    "scripts/ci/prepare_runner_userns.sh",
    "./scripts/check.sh",
    "git status --porcelain",
]


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _values(key: str) -> list[str]:
    pattern = rf"^\s*(?:-\s+)?{re.escape(key)}:\s*(.*?)\s*$"
    return re.findall(pattern, _workflow(), re.MULTILINE)


def test_actions_are_exactly_the_approved_commit_pins() -> None:
    uses = _values("uses")
    found: dict[str, str] = {}
    for value in uses:
        target, _, comment = value.partition(" ")
        found[target] = comment.strip()
    assert len(uses) == len(APPROVED_ACTIONS)
    assert found == APPROVED_ACTIONS


def test_no_floating_action_references() -> None:
    for value in _values("uses"):
        target = value.split()[0]
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", target), target


def test_runner_is_exactly_ubuntu_24_04() -> None:
    assert _values("runs-on") == ["ubuntu-24.04"]


def test_checkout_fetches_full_history_without_persisted_credentials() -> None:
    assert _values("fetch-depth") == ["0"]
    assert _values("persist-credentials") == ["false"]


def test_permissions_are_only_read_access_to_contents() -> None:
    text = _workflow()
    assert len(re.findall(r"^\s*permissions:", text, re.MULTILINE)) == 1
    assert re.search(r"^permissions:\n  contents: read\n(?!  )", text, re.MULTILINE)


def test_workflow_does_not_reference_tokens_or_secrets() -> None:
    text = _workflow().lower()
    for forbidden in ("github.token", "github_token", "secrets."):
        assert forbidden not in text


def test_triggers_are_exactly_pull_requests_and_pushes_to_main() -> None:
    text = _workflow()
    assert len(re.findall(r"^on:", text, re.MULTILINE)) == 1
    block = re.search(r"^on:\n((?:[ \t]+\S.*\n|[ \t]*\n)*)", text, re.MULTILINE)
    assert block is not None
    assert [line for line in block[1].splitlines() if line.strip()] == APPROVED_TRIGGERS


def test_unintended_triggers_are_absent() -> None:
    text = _workflow()
    for forbidden in (
        "pull_request_target",
        "schedule:",
        "workflow_dispatch",
        "workflow_run",
        "workflow_call",
        "release:",
        "repository_dispatch",
        "issue_comment",
    ):
        assert forbidden not in text


def test_steps_run_in_the_required_order() -> None:
    text = _workflow()
    assert len(re.findall(r"^\s*- name:", text, re.MULTILINE)) == len(REQUIRED_STEP_ORDER)
    positions = []
    for marker in REQUIRED_STEP_ORDER:
        assert text.count(marker) == 1, marker
        positions.append(text.index(marker))
    assert positions == sorted(positions)


def test_no_caching_artifacts_or_tracing() -> None:
    text = _workflow()
    for forbidden in ("upload-artifact", "actions/cache", "enable-cache", "set -x", "toJSON("):
        assert forbidden not in text


def test_ci_uses_the_canonical_gate_and_pinned_installers() -> None:
    text = _workflow()
    for required in (
        "./scripts/check.sh",
        "scripts/install_uv.sh",
        "scripts/install_betterleaks.sh",
        "scripts/ci/prepare_runner_userns.sh",
    ):
        assert required in text


def test_uv_pin_is_exactly_the_approved_release() -> None:
    entries: dict[str, str] = {}
    for line in UV_PIN.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator == "=", line
        assert key not in entries, line
        entries[key] = value
    assert entries == APPROVED_UV_PIN
