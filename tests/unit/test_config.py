"""Tests for configuration loading and validation."""

import hashlib
import os
from pathlib import Path

import pytest

from pmv.config import (
    ConfigError,
    Environment,
    LogLevel,
    RawStorageConfig,
    environment_from,
    load_config,
    load_config_for_environment,
    protected_raw_root_problem,
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


def test_raw_storage_is_unset_when_the_section_is_absent(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, VALID), Environment.TEST)
    raw = config.raw_storage
    assert (raw.root, raw.warning_free_bytes, raw.hard_stop_free_bytes) == (None, None, None)
    assert (raw.retention_class, raw.backup_policy_id) == (None, None)


def test_shipped_configs_leave_raw_storage_policy_unset() -> None:
    for path in sorted(REPO_CONFIG_DIR.glob("*.toml")):
        raw = load_config(path, Environment(path.stem)).raw_storage
        assert raw == type(raw)()


def test_raw_storage_section_is_parsed_and_validated(tmp_path: Path) -> None:
    section = (
        '\n[raw_storage]\nroot = "/srv/pmv-raw"\nwarning_free_bytes = 2000\n'
        'hard_stop_free_bytes = 1000\nretention_class = "keep_all"\n'
    )
    raw = load_config(write_config(tmp_path, VALID + section), Environment.TEST).raw_storage
    assert raw.root == Path("/srv/pmv-raw")
    assert (raw.warning_free_bytes, raw.hard_stop_free_bytes) == (2000, 1000)
    assert raw.retention_class == "keep_all"
    assert raw.backup_policy_id is None


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ('root = "relative/raw"', "absolute"),
        ("warning_free_bytes = 100\nhard_stop_free_bytes = 100", "must exceed"),
        ("hard_stop_free_bytes = 0", "positive"),
        ("hard_stop_free_bytes = true", "must be an integer"),
        ('retention_class = "Keep All"', "lowercase identifier"),
        ("extra = 1", "unknown key"),
    ],
)
def test_invalid_raw_storage_values_fail_clearly(
    tmp_path: Path, section: str, message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(
            write_config(tmp_path, VALID + "\n[raw_storage]\n" + section + "\n"), Environment.TEST
        )


# ----- Step 11 F-01: real raw data lives in the protected raw location -----


def raw_config(environment: str, root: Path) -> str:
    return (
        f'schema_version = 1\nenvironment = "{environment}"\n\n[logging]\nlevel = "INFO"\n'
        f'\n[raw_storage]\nroot = "{root}"\n'
    )


@pytest.fixture
def protected_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import pmv.config as config_module

    base = tmp_path / "home" / "pmv-protected" / "raw"
    base.mkdir(parents=True)
    monkeypatch.setattr(config_module, "PROTECTED_RAW_BASE", base)
    return base


@pytest.mark.parametrize("environment", ["development", "shadow", "production"])
def test_a_real_raw_root_inside_the_protected_location_loads(
    tmp_path: Path, protected_base: Path, environment: str
) -> None:
    for root in (protected_base, protected_base / "kalshi" / "2026"):
        path = write_config(tmp_path, raw_config(environment, root), f"{environment}.toml")
        config = load_config(path, Environment(environment))
        assert config.raw_storage.root == root


@pytest.mark.parametrize(
    "relative",
    [
        "../raw-sibling",
        "../../pmv-raw",
        "kalshi/../../escape",
    ],
)
def test_a_real_raw_root_outside_the_protected_location_is_refused(
    tmp_path: Path, protected_base: Path, relative: str
) -> None:
    root = Path(f"{protected_base}/{relative}")
    path = write_config(tmp_path, raw_config("development", root), "development.toml")
    with pytest.raises(ConfigError, match="protected raw location"):
        load_config(path, Environment.DEVELOPMENT)


def test_a_symlink_escaping_the_protected_location_is_refused(
    tmp_path: Path, protected_base: Path
) -> None:
    outside = tmp_path / "agent-readable"
    outside.mkdir()
    link = protected_base / "linked"
    link.symlink_to(outside, target_is_directory=True)
    path = write_config(tmp_path, raw_config("production", link / "x"), "production.toml")
    with pytest.raises(ConfigError, match="protected raw location"):
        load_config(path, Environment.PRODUCTION)


def test_test_configurations_and_direct_store_configs_may_use_temporary_roots(
    tmp_path: Path, protected_base: Path
) -> None:
    scratch = tmp_path / "scratch-raw"
    path = write_config(tmp_path, raw_config("test", scratch))
    assert load_config(path, Environment.TEST).raw_storage.root == scratch
    assert RawStorageConfig(root=scratch).root == scratch
    assert protected_raw_root_problem(Path("relative/raw"), protected_base) is not None


# ----- Step 11 red-team finding 3: HOME cannot move the protected location -----


def test_the_protected_raw_location_ignores_a_changed_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pwd

    import pmv.config as config_module

    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    assert config_module.account_home() == real_home
    assert real_home / "pmv-protected" / "raw" == config_module.PROTECTED_RAW_BASE
    fake_home = tmp_path / "fake-home"
    monkeypatch.setenv("HOME", str(fake_home))
    assert config_module.account_home() == real_home
    root = fake_home / "pmv-protected" / "raw" / "kalshi"
    root.mkdir(parents=True)
    path = write_config(tmp_path, raw_config("development", root), "development.toml")
    with pytest.raises(ConfigError, match="protected raw location"):
        load_config(path, Environment.DEVELOPMENT)


def test_an_unknown_account_home_refuses_every_real_raw_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pwd

    import pmv.config as config_module

    def missing(_uid: int) -> pwd.struct_passwd:
        raise KeyError(_uid)

    monkeypatch.setattr(pwd, "getpwuid", missing)
    assert config_module.account_home() == config_module.UNKNOWN_ACCOUNT_HOME
    base = config_module.UNKNOWN_ACCOUNT_HOME / "pmv-protected" / "raw"
    monkeypatch.setattr(config_module, "PROTECTED_RAW_BASE", base)
    for root in (base, base / "kalshi"):
        path = write_config(tmp_path, raw_config("production", root), "production.toml")
        with pytest.raises(ConfigError, match="account home directory"):
            load_config(path, Environment.PRODUCTION)
