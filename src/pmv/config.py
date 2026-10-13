"""Typed, validated application configuration loaded from TOML files.

Each environment has one file, ``configs/<environment>.toml``. The environment is
chosen explicitly through ``PMV_ENV``; there is no default. A file is validated
completely before any value is used.
"""

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from pmv.redaction import is_secret_key

CONFIG_SCHEMA_VERSION: Final = 1
ENVIRONMENT_VARIABLE: Final = "PMV_ENV"
_IDENTIFIER: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")


class ConfigError(Exception):
    """Configuration is missing, malformed, or inconsistent."""


class Environment(StrEnum):
    """Deployment environment. Selecting one never changes behavior implicitly."""

    DEVELOPMENT = "development"
    TEST = "test"
    SHADOW = "shadow"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Minimum severity of emitted log records."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True, kw_only=True)
class LoggingConfig:
    level: LogLevel


@dataclass(frozen=True, slots=True, kw_only=True)
class RawStorageConfig:
    """Raw capture storage policy. Every value is unset unless configured explicitly.

    There is no default root and there are no default disk thresholds; capture operations
    fail closed while the values they need are unset.
    """

    root: Path | None = None
    warning_free_bytes: int | None = None
    hard_stop_free_bytes: int | None = None
    retention_class: str | None = None
    backup_policy_id: str | None = None

    def __post_init__(self) -> None:
        if self.root is not None and not self.root.is_absolute():
            raise ValueError("raw_storage.root must be an absolute path")
        for name in ("warning_free_bytes", "hard_stop_free_bytes"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError(f"raw_storage.{name} must be an integer")
            if value is not None and value <= 0:
                raise ValueError(f"raw_storage.{name} must be positive")
        warning, hard_stop = self.warning_free_bytes, self.hard_stop_free_bytes
        if warning is not None and hard_stop is not None and warning <= hard_stop:
            raise ValueError("raw_storage.warning_free_bytes must exceed hard_stop_free_bytes")
        for name in ("retention_class", "backup_policy_id"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not _IDENTIFIER.fullmatch(value)
            ):
                raise ValueError(f"raw_storage.{name} must be a lowercase identifier")

    def canonical_sha256(self) -> str:
        """Return the SHA-256 of the canonical JSON of these values (raw_config_sha256)."""
        values = {
            "backup_policy_id": self.backup_policy_id,
            "hard_stop_free_bytes": self.hard_stop_free_bytes,
            "retention_class": self.retention_class,
            "root": None if self.root is None else str(self.root),
            "warning_free_bytes": self.warning_free_bytes,
        }
        encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class ExperimentStorageConfig:
    """Experiment tracking store. The root is unset unless configured explicitly."""

    root: Path | None = None

    def __post_init__(self) -> None:
        if self.root is not None and not self.root.is_absolute():
            raise ValueError("experiments.root must be an absolute path")


@dataclass(frozen=True, slots=True, kw_only=True)
class AppConfig:
    environment: Environment
    logging: LoggingConfig
    source_path: Path
    source_sha256: str
    raw_storage: RawStorageConfig = field(default_factory=RawStorageConfig)
    experiments: ExperimentStorageConfig = field(default_factory=ExperimentStorageConfig)

    def log_summary(self) -> dict[str, str]:
        """Return the fields that identify this configuration in logs.

        Log this summary, never the configuration object itself.
        """
        return {
            "environment": self.environment.value,
            "config_path": str(self.source_path),
            "config_sha256": self.source_sha256,
            "log_level": self.logging.level.value,
        }


def environment_from(environ: Mapping[str, str]) -> Environment:
    """Return the environment named by ``PMV_ENV`` in ``environ``."""
    raw = environ.get(ENVIRONMENT_VARIABLE, "")
    if not raw:
        raise ConfigError(
            f"{ENVIRONMENT_VARIABLE} is not set; choose one of: {_choices(Environment)}"
        )
    return _parse_enum(Environment, raw, ENVIRONMENT_VARIABLE)


def config_path(config_dir: Path, environment: Environment) -> Path:
    """Return the configuration file path for ``environment``."""
    return config_dir / f"{environment.value}.toml"


def load_config_for_environment(config_dir: Path, environ: Mapping[str, str]) -> AppConfig:
    """Select the environment from ``environ`` and load its configuration file."""
    environment = environment_from(environ)
    return load_config(config_path(config_dir, environment), environment)


def load_config(path: Path, expected_environment: Environment) -> AppConfig:
    """Load and validate one configuration file.

    The file must declare ``expected_environment``, so a file written for one
    environment can never be loaded as another.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc.strerror}") from exc
    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path} is not valid UTF-8 TOML: {exc}") from exc

    where = str(path)
    _reject_secret_keys(document, where)
    _reject_unknown_keys(
        document, {"schema_version", "environment", "logging", "raw_storage", "experiments"}, where
    )

    schema_version = _require_int(document, "schema_version", where)
    if schema_version != CONFIG_SCHEMA_VERSION:
        raise ConfigError(
            f"{where}: schema_version {schema_version} is not supported; "
            f"expected {CONFIG_SCHEMA_VERSION}"
        )
    environment_name = _require_str(document, "environment", where)
    environment = _parse_enum(Environment, environment_name, f"{where}: environment")
    if environment is not expected_environment:
        raise ConfigError(
            f"{where} declares environment {environment.value!r}, "
            f"but {expected_environment.value!r} was requested"
        )

    logging_table = _require_table(document, "logging", where)
    logging_where = f"{where} [logging]"
    _reject_unknown_keys(logging_table, {"level"}, logging_where)
    level_name = _require_str(logging_table, "level", logging_where)
    level = _parse_enum(LogLevel, level_name, f"{logging_where}: level")

    raw_storage = RawStorageConfig()
    if "raw_storage" in document:
        raw_storage = _parse_raw_storage(_require_table(document, "raw_storage", where), where)
    experiments = ExperimentStorageConfig()
    if "experiments" in document:
        experiments = _parse_experiments(_require_table(document, "experiments", where), where)

    return AppConfig(
        environment=environment,
        logging=LoggingConfig(level=level),
        source_path=path,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        raw_storage=raw_storage,
        experiments=experiments,
    )


def _parse_experiments(table: Mapping[str, object], where: str) -> ExperimentStorageConfig:
    table_where = f"{where} [experiments]"
    _reject_unknown_keys(table, {"root"}, table_where)
    root = _require_str(table, "root", table_where) if "root" in table else None
    try:
        return ExperimentStorageConfig(root=None if root is None else Path(root))
    except ValueError as exc:
        raise ConfigError(f"{table_where}: {exc}") from None


def _parse_raw_storage(table: Mapping[str, object], where: str) -> RawStorageConfig:
    table_where = f"{where} [raw_storage]"
    _reject_unknown_keys(
        table,
        {
            "root",
            "warning_free_bytes",
            "hard_stop_free_bytes",
            "retention_class",
            "backup_policy_id",
        },
        table_where,
    )
    root = _require_str(table, "root", table_where) if "root" in table else None
    try:
        return RawStorageConfig(
            root=None if root is None else Path(root),
            warning_free_bytes=_optional_int(table, "warning_free_bytes", table_where),
            hard_stop_free_bytes=_optional_int(table, "hard_stop_free_bytes", table_where),
            retention_class=_optional_str(table, "retention_class", table_where),
            backup_policy_id=_optional_str(table, "backup_policy_id", table_where),
        )
    except ValueError as exc:
        raise ConfigError(f"{table_where}: {exc}") from None


def _optional_int(table: Mapping[str, object], key: str, where: str) -> int | None:
    return _require_int(table, key, where) if key in table else None


def _optional_str(table: Mapping[str, object], key: str, where: str) -> str | None:
    return _require_str(table, key, where) if key in table else None


def _reject_secret_keys(value: object, where: str, trail: str = "") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{trail}.{key}" if trail else str(key)
            if is_secret_key(str(key)):
                raise ConfigError(
                    f"{where}: key {name!r} looks like a secret; "
                    "secrets never belong in configuration files"
                )
            _reject_secret_keys(item, where, name)
    elif isinstance(value, list):
        for item in value:
            _reject_secret_keys(item, where, trail)


def _reject_unknown_keys(table: Mapping[str, object], allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s): {', '.join(map(repr, unknown))}")


def _require(table: Mapping[str, object], key: str, where: str) -> object:
    if key not in table:
        raise ConfigError(f"{where}: missing required key {key!r}")
    return table[key]


def _require_int(table: Mapping[str, object], key: str, where: str) -> int:
    value = _require(table, key, where)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where}: {key!r} must be an integer")
    return value


def _require_str(table: Mapping[str, object], key: str, where: str) -> str:
    value = _require(table, key, where)
    if not isinstance(value, str):
        raise ConfigError(f"{where}: {key!r} must be a string")
    return value


def _require_table(table: Mapping[str, object], key: str, where: str) -> Mapping[str, object]:
    value = _require(table, key, where)
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: {key!r} must be a table")
    return value


def _parse_enum[E: StrEnum](enum_type: type[E], raw: str, where: str) -> E:
    try:
        return enum_type(raw)
    except ValueError:
        raise ConfigError(f"{where}: {raw!r} is not one of: {_choices(enum_type)}") from None


def _choices(enum_type: type[StrEnum]) -> str:
    return ", ".join(member.value for member in enum_type)
