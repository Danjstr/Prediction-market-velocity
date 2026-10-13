"""Tests for configuration loading and validation."""

import hashlib
from pathlib import Path

import pytest

from pmv.config import (
    ConfigError,
    Environment,
    LogLevel,
    environment_from,
    load_config,
    load_config_for_environment,
)

REPO_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

VALID = 'schema_version = 1\nenvironment = "test"\n\n[logging]\nlevel = "INFO"\n'


def write_config(directory: Path, text: str, name: str = "test.toml") -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_file_loads(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, VALID), Environment.TEST)
    assert config.environment is Environment.TEST
    assert config.logging.level is LogLevel.INFO
    assert config.source_sha256 == hashlib.sha256(VALID.encode("utf-8")).hexdigest()


def test_every_shipped_config_file_is_valid() -> None:
    paths = sorted(REPO_CONFIG_DIR.glob("*.toml"))
    assert [path.stem for path in paths] == ["development", "test"]
    for path in paths:
        environment = Environment(path.stem)
        assert load_config(path, environment).environment is environment


def test_file_cannot_be_loaded_as_another_environment(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="declares environment 'test'"):
        load_config(write_config(tmp_path, VALID), Environment.PRODUCTION)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            'environment = "test"\n\n[logging]\nlevel = "INFO"\n',
            "missing required key 'schema_version'",
        ),
        (
            VALID.replace("schema_version = 1", "schema_version = 2"),
            "schema_version 2 is not supported",
        ),
        (VALID.replace("schema_version = 1", "schema_version = true"), "must be an integer"),
        (VALID.replace('"test"', '"Test"'), "is not one of"),
        (VALID.replace('"INFO"', '"info"'), "is not one of"),
        (VALID + "extra = 1\n", "unknown key"),
        ('schema_version = 1\nenvironment = "test"\n', "missing required key 'logging'"),
        ('schema_version = 1\nenvironment = "test"\nlogging = 5\n', "must be a table"),
        ("not toml = = =", "not valid UTF-8 TOML"),
    ],
)
def test_invalid_files_fail_with_clear_errors(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write_config(tmp_path, text), Environment.TEST)


def test_secret_like_keys_are_rejected_without_echoing_values(tmp_path: Path) -> None:
    path = write_config(tmp_path, VALID + 'api_key = "hunter2"\n')
    with pytest.raises(ConfigError, match="looks like a secret") as excinfo:
        load_config(path, Environment.TEST)
    assert "hunter2" not in str(excinfo.value)


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read configuration file"):
        load_config(tmp_path / "absent.toml", Environment.TEST)


def test_environment_must_be_set_explicitly() -> None:
    with pytest.raises(ConfigError, match="PMV_ENV is not set"):
        environment_from({})


@pytest.mark.parametrize("raw", ["prod", "Production", " test"])
def test_unknown_environment_names_are_rejected(raw: str) -> None:
    with pytest.raises(ConfigError, match="is not one of"):
        environment_from({"PMV_ENV": raw})


def test_environment_is_read_from_variable() -> None:
    assert environment_from({"PMV_ENV": "shadow"}) is Environment.SHADOW


def test_load_for_environment_uses_matching_file(tmp_path: Path) -> None:
    write_config(tmp_path, VALID)
    config = load_config_for_environment(tmp_path, {"PMV_ENV": "test"})
    assert config.environment is Environment.TEST


def test_log_summary_contains_only_allowlisted_fields(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, VALID), Environment.TEST)
    assert set(config.log_summary()) == {"environment", "config_path", "config_sha256", "log_level"}
