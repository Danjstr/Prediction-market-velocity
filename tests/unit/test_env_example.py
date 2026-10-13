"""Tests that env.example lists variable names only."""

import re
from pathlib import Path

from pmv.secret_inputs import SecretSpec

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / "env.example"
_ASSIGNMENT = re.compile(r"([A-Z][A-Z0-9_]*)=(.*)")


def _names() -> list[str]:
    names: list[str] = []
    for number, line in enumerate(ENV_EXAMPLE.read_text(encoding="utf-8").splitlines(), start=1):
        if not line or line.startswith("#"):
            continue
        match = _ASSIGNMENT.fullmatch(line)
        assert match is not None, f"env.example line {number} is not a NAME= line"
        assert match[2] == "", f"env.example line {number} contains a value"
        names.append(match[1])
    return names


def test_env_example_contains_names_without_values() -> None:
    assert "PMV_ENV" in _names()


def test_env_example_names_are_the_selector_or_well_formed_secret_inputs() -> None:
    for name in _names():
        if name != "PMV_ENV":
            SecretSpec(name)
