"""Tests for explicit secret-input loading and leak prevention."""

import io
import json
import logging
import os
import pickle
import traceback
from collections.abc import Iterator, Mapping
from typing import cast

import pytest

from pmv.config import LoggingConfig, LogLevel
from pmv.log import configure_logging, fields, get_logger
from pmv.redaction import REDACTED, Secret
from pmv.secret_inputs import SecretInputError, SecretSpec, load_secrets

ALPHA = SecretSpec("PMV_SECRET_UNIT_ALPHA")
BETA = SecretSpec("PMV_SECRET_UNIT_BETA")
GAMMA = SecretSpec("PMV_SECRET_UNIT_GAMMA")
FAKE_ALPHA = "FAKE-NOT-A-REAL-SECRET-ALPHA-0001"
FAKE_BETA = "FAKE-NOT-A-REAL-SECRET-BETA-0002"
FAKE_GAMMA = "FAKE-NOT-A-REAL-SECRET-GAMMA-0003"
ALL_FAKES = (FAKE_ALPHA, FAKE_BETA, FAKE_GAMMA)


class GuardedSource(Mapping[str, str]):
    """A source that records each lookup and fails on any enumeration."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values
        self.looked_up: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.looked_up.append(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("the loader must not iterate over the source")

    def __len__(self) -> int:
        raise AssertionError("the loader must not measure the source")


class SensitiveValue:
    """A non-string value whose text forms must never be produced."""

    rendered = False

    def __str__(self) -> str:
        SensitiveValue.rendered = True
        return "SENSITIVE-RENDERING"

    def __repr__(self) -> str:
        SensitiveValue.rendered = True
        return "SENSITIVE-RENDERING"


class SensitiveText(str):
    """A str subclass; rejected because it could override str methods."""


@pytest.fixture(autouse=True)
def reset_pmv_logger() -> Iterator[None]:
    yield
    logger = logging.getLogger("pmv")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


@pytest.mark.parametrize(
    "value", [FAKE_ALPHA, f"  {FAKE_ALPHA}\n", "FAKE-LINE-ONE\nFAKE-LINE-TWO\n"]
)
def test_values_are_wrapped_and_preserved_exactly(value: str) -> None:
    secret = load_secrets([ALPHA], {ALPHA.name: value}).get(ALPHA)
    assert isinstance(secret, Secret)
    assert secret.reveal() == value


def test_missing_secret_fails_naming_only_the_input() -> None:
    with pytest.raises(SecretInputError, match="missing: PMV_SECRET_UNIT_ALPHA"):
        load_secrets([ALPHA], {})


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_empty_secret_fails(value: str) -> None:
    with pytest.raises(SecretInputError, match="empty or whitespace-only: PMV_SECRET_UNIT_ALPHA"):
        load_secrets([ALPHA], {ALPHA.name: value})


def test_all_problems_are_reported_together_without_values() -> None:
    source = {BETA.name: "", GAMMA.name: FAKE_GAMMA}
    with pytest.raises(SecretInputError) as excinfo:
        load_secrets([ALPHA, BETA, GAMMA], source)
    message = str(excinfo.value)
    assert "missing: PMV_SECRET_UNIT_ALPHA" in message
    assert "empty or whitespace-only: PMV_SECRET_UNIT_BETA" in message
    rendered = "".join(traceback.format_exception(excinfo.value)) + repr(excinfo.value)
    assert FAKE_GAMMA not in rendered


@pytest.mark.parametrize(
    "value",
    [SensitiveValue(), 12345, b"FAKE-BYTES-VALUE", SensitiveText("FAKE-SUBCLASS-VALUE")],
    ids=["object", "int", "bytes", "str-subclass"],
)
def test_non_string_values_fail_without_rendering(
    value: object, capsys: pytest.CaptureFixture[str]
) -> None:
    SensitiveValue.rendered = False
    source = cast(Mapping[str, str], {ALPHA.name: value})
    with pytest.raises(SecretInputError, match="not a string: PMV_SECRET_UNIT_ALPHA") as excinfo:
        load_secrets([ALPHA], source)
    error = excinfo.value
    rendered = str(error) + repr(error) + "".join(traceback.format_exception(error))
    captured = capsys.readouterr()
    for output in (rendered, captured.out, captured.err):
        for marker in ("SENSITIVE-RENDERING", "12345", "FAKE-BYTES-VALUE", "FAKE-SUBCLASS-VALUE"):
            assert marker not in output
    assert not SensitiveValue.rendered


def test_only_declared_names_are_looked_up() -> None:
    source = GuardedSource(
        {ALPHA.name: FAKE_ALPHA, "PMV_SECRET_UNIT_UNRELATED": FAKE_BETA, "HOME": "/fake/home"}
    )
    loaded = load_secrets([ALPHA], source)
    assert source.looked_up == [ALPHA.name]
    assert loaded.names == (ALPHA.name,)


def test_process_environment_can_be_passed_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ALPHA.name, FAKE_ALPHA)
    assert load_secrets([ALPHA], os.environ).get(ALPHA).reveal() == FAKE_ALPHA


def test_container_renders_names_only() -> None:
    loaded = load_secrets([ALPHA, BETA], {ALPHA.name: FAKE_ALPHA, BETA.name: FAKE_BETA})
    renderings = (
        str(loaded),
        repr(loaded),
        f"{loaded}",
        f"{loaded!r}",
        str([loaded]),
        str({"k": loaded}),
    )
    for rendered in renderings:
        for fake in ALL_FAKES:
            assert fake not in rendered
    assert repr(loaded) == "LoadedSecrets(names=['PMV_SECRET_UNIT_ALPHA', 'PMV_SECRET_UNIT_BETA'])"


def test_container_cannot_be_pickled() -> None:
    loaded = load_secrets([ALPHA], {ALPHA.name: FAKE_ALPHA})
    with pytest.raises(TypeError, match="cannot be pickled"):
        pickle.dumps(loaded)


def test_requesting_an_unloaded_spec_fails() -> None:
    loaded = load_secrets([ALPHA], {ALPHA.name: FAKE_ALPHA})
    with pytest.raises(SecretInputError, match="PMV_SECRET_UNIT_BETA was not loaded"):
        loaded.get(BETA)


@pytest.mark.parametrize("name", ["PMV_SECRET_A", "PMV_SECRET_UNIT_ALPHA", "PMV_SECRET_X1_Y2"])
def test_well_formed_names_are_accepted(name: str) -> None:
    assert SecretSpec(name).name == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "API_KEY",
        "PMV_ENV",
        "PMV_SECRET_",
        "PMV_SECRET_alpha",
        "pmv_secret_alpha",
        "PMV_SECRET__ALPHA",
        "PMV_SECRET_ALPHA_",
    ],
)
def test_malformed_names_are_rejected_without_echo(name: str) -> None:
    with pytest.raises(ValueError, match="PMV_SECRET_<UPPER_SNAKE_CASE>") as excinfo:
        SecretSpec(name)
    assert str(excinfo.value) == "secret input names must match PMV_SECRET_<UPPER_SNAKE_CASE>"


def test_duplicate_specs_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        load_secrets([ALPHA, SecretSpec(ALPHA.name)], {ALPHA.name: FAKE_ALPHA})


def test_fake_values_never_reach_logs_stdout_or_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    logger = get_logger("pmv.tests")
    loaded = load_secrets([ALPHA], {ALPHA.name: FAKE_ALPHA})
    logger.info(
        "unit.secret",
        extra=fields(value=loaded.get(ALPHA), container=loaded, env={ALPHA.name: FAKE_ALPHA}),
    )
    try:
        load_secrets([ALPHA, BETA], {ALPHA.name: FAKE_ALPHA, BETA.name: " "})
    except SecretInputError:
        logger.exception("unit.secret_failure")
    captured = capsys.readouterr()
    for output in (buffer.getvalue(), captured.out, captured.err):
        assert FAKE_ALPHA not in output
    first, second = (json.loads(line) for line in buffer.getvalue().splitlines())
    assert first["fields"] == {
        "value": REDACTED,
        "container": "<unserializable LoadedSecrets>",
        "env": {ALPHA.name: REDACTED},
    }
    assert second["exception"]["type"] == "SecretInputError"
