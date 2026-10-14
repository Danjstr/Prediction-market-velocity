"""Experiment run specifications, input references, metric values, and execution identity.

Everything here is a closed schema. Values inside spec sections are "safe values" only:
null, booleans, integers, identifiers, exact decimal strings, canonical timestamps,
SHA-256 digests, lists, and objects with identifier keys. There are no floats, free text,
or paths, so a specification cannot carry a credential or a mutable location.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pmv.integrity import (
    FormatError,
    canonical_line,
    decimal_text,
    is_decimal_text,
    is_identifier,
    is_int,
    is_non_negative_int,
    is_sha256,
    is_timestamp,
    is_timestamp_id,
    parse_canonical_json,
    sha256_hex,
)
from pmv.redaction import redact_text

SPEC_SCHEMA: Final = "pmv.experiment.run_spec"
IDENTITY_SCHEMA: Final = "pmv.experiment.execution_identity"
SCHEMA_VERSION: Final = 1
# Execution identity versions. v1 (Step 6, "Option B") requires a null installed-environment
# fingerprint, so no v1 run can be evidence-eligible. v2 (Step 10) records the SHA-256 of the
# canonical environment document (pmv.reproducibility), or null when none was captured.
IDENTITY_V1: Final = 1
IDENTITY_V2: Final = 2
IDENTITY_VERSIONS: Final = (IDENTITY_V1, IDENTITY_V2)
MAX_SPEC_BYTES: Final = 1_048_576
MAX_SAFE_DEPTH: Final = 8
SEED_MAX: Final = 2**64 - 1
SECTION_NAMES: Final = ("experiment", "features", "model", "calibration", "validation")
ARTIFACT_NAME: Final = re.compile(r"[a-z][a-z0-9_]{0,63}(\.[a-z0-9]{1,8})?")
ENTRYPOINT: Final = re.compile(r"[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*:[a-z_][a-z0-9_]*")
EXCEPTION_TYPE: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,127}")
_PACKAGE_VERSION: Final = re.compile(r"[0-9][0-9A-Za-z.+-]{0,63}")
_PYTHON_VERSION: Final = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}")
_PLATFORM: Final = re.compile(r"[a-z0-9]{1,32}-[a-z0-9_]{1,32}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")


class SpecError(ValueError):
    """A specification, reference, or identity is invalid. Messages never echo values."""


class RunClass(StrEnum):
    EXPLORATORY = "exploratory"
    DEVELOPMENT = "development"
    EVIDENCE_CANDIDATE = "evidence_candidate"


class Split(StrEnum):
    TRAIN = "train"
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    INNER_VALIDATION = "inner_validation"
    PROTECTED_HOLDOUT = "protected_holdout"


class ArtifactType(StrEnum):
    MODEL = "model"
    PREDICTIONS = "predictions"
    CALIBRATION = "calibration"
    TABLE = "table"
    FIGURE = "figure"
    REPORT = "report"
    LOG_SUMMARY = "log_summary"


class MediaType(StrEnum):
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    BINARY = "binary"
    PNG = "png"
    SVG = "svg"
    HTML = "html"


class WarningCode(StrEnum):
    NONDETERMINISTIC_OPERATION = "nondeterministic_operation"
    CONVERGENCE_WARNING = "convergence_warning"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    RESOURCE_LIMIT = "resource_limit"
    LIBRARY_WARNING = "library_warning"


class FailureCode(StrEnum):
    EXCEPTION = "exception"
    INPUT_VERIFICATION_FAILED = "input_verification_failed"
    ARTIFACT_VERIFICATION_FAILED = "artifact_verification_failed"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    INVALID_STATE = "invalid_state"
    CODE_IDENTITY_CHANGED = "code_identity_changed"
    # Ledger entry v2 only: the installed environment changed during the run.
    ENVIRONMENT_CHANGED = "environment_changed"


# The failure codes a v1 ledger entry may carry, exactly as Step 6 defined them.
V1_FAILURE_CODES: Final = frozenset(FailureCode) - {FailureCode.ENVIRONMENT_CHANGED}


class AbortReason(StrEnum):
    OPERATOR_REQUEST = "operator_request"
    INVALID_INPUT = "invalid_input"
    RESOURCE_LIMIT = "resource_limit"


class SupersedeReason(StrEnum):
    CORRECTED_INPUT = "corrected_input"
    CORRECTED_CODE = "corrected_code"
    CORRECTED_CONFIG = "corrected_config"
    METHODOLOGY_CHANGE = "methodology_change"


def require_identifier(value: object, what: str) -> str:
    if not is_identifier(value) or redact_text(value) != value:
        raise SpecError(f"{what} must match [a-z][a-z0-9_]{{0,63}}")
    return value


def require_run_id(value: object, what: str = "run_id") -> str:
    if not is_timestamp_id(value):
        raise SpecError(f"{what} is malformed")
    return value


def require_artifact_name(value: object) -> str:
    if not isinstance(value, str) or ARTIFACT_NAME.fullmatch(value) is None:
        raise SpecError("artifact name is malformed")
    return value


def require_split(value: object) -> Split:
    """Return the split; ``protected_holdout`` is always refused in Step 6."""
    try:
        split = Split(str(value)) if isinstance(value, str) else None
    except ValueError:
        split = None
    if split is None:
        raise SpecError("split is not a known split")
    if split is Split.PROTECTED_HOLDOUT:
        raise SpecError("protected_holdout is not accessible in Step 6")
    return split


def validate_safe_value(value: object, depth: int = 0) -> None:
    """Accept only the safe-value grammar; raise SpecError otherwise."""
    if depth > MAX_SAFE_DEPTH:
        raise SpecError("spec value is nested too deeply")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise SpecError("floats are not allowed; use exact decimal strings")
    if isinstance(value, str):
        if not (
            is_identifier(value)
            or is_decimal_text(value)
            or is_timestamp(value)
            or is_sha256(value)
        ):
            raise SpecError("spec strings must be identifiers, decimals, timestamps, or hashes")
        if redact_text(value) != value:
            raise SpecError("spec value looks like secret material")
        return
    if isinstance(value, list | tuple):
        for item in value:
            validate_safe_value(item, depth + 1)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            require_identifier(key, "spec object key")
            validate_safe_value(item, depth + 1)
        return
    raise SpecError("spec contains an unsupported value type")


@dataclass(frozen=True, slots=True)
class Seed:
    domain: str
    value: int

    def __post_init__(self) -> None:
        require_identifier(self.domain, "seed domain")
        if not is_int(self.value):
            raise SpecError("seed value must be an integer")
        if not 0 <= self.value <= SEED_MAX:
            raise SpecError("seed value must be in 0..2**64-1")


@dataclass(frozen=True, slots=True)
class RawCaptureInput:
    capture_id: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        require_run_id(self.capture_id, "capture_id")
        if not is_sha256(self.manifest_sha256):
            raise SpecError("manifest_sha256 must be a SHA-256 hex digest")

    def to_json(self) -> dict[str, object]:
        return {
            "capture_id": self.capture_id,
            "kind": "raw_capture",
            "manifest_sha256": self.manifest_sha256,
        }


@dataclass(frozen=True, slots=True)
class RunArtifactInput:
    run_id: str
    artifact_name: str
    sha256: str

    def __post_init__(self) -> None:
        require_run_id(self.run_id)
        require_artifact_name(self.artifact_name)
        if not is_sha256(self.sha256):
            raise SpecError("artifact sha256 must be a SHA-256 hex digest")

    def to_json(self) -> dict[str, object]:
        return {
            "artifact_name": self.artifact_name,
            "kind": "run_artifact",
            "run_id": self.run_id,
            "sha256": self.sha256,
        }


InputRef = RawCaptureInput | RunArtifactInput


def parse_input(value: object) -> InputRef:
    if not isinstance(value, Mapping):
        raise SpecError("input reference must be an object")
    kind = value.get("kind")
    if kind == "raw_capture" and set(value) == {"kind", "capture_id", "manifest_sha256"}:
        return RawCaptureInput(_text(value["capture_id"]), _text(value["manifest_sha256"]))
    if kind == "run_artifact" and set(value) == {"kind", "run_id", "artifact_name", "sha256"}:
        return RunArtifactInput(
            _text(value["run_id"]), _text(value["artifact_name"]), _text(value["sha256"])
        )
    raise SpecError(
        "input reference kind is not supported; derived data must use an immutable reference"
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RunSpec:
    """The declared experiment specification (``run_spec.json``)."""

    study_id: str
    entrypoint: str
    sections: Mapping[str, Mapping[str, object] | None]
    seeds: tuple[Seed, ...] = ()
    inputs: tuple[InputRef, ...] = ()
    informed_by: tuple[str, ...] = ()
    splits_accessed: tuple[Split, ...] = ()
    candidate_id: str | None = None
    selection_round: int | None = None
    extra: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_identifier(self.study_id, "study_id")
        if not isinstance(self.entrypoint, str) or ENTRYPOINT.fullmatch(self.entrypoint) is None:
            raise SpecError("entrypoint must be a module:function identity")
        if set(self.sections) != set(SECTION_NAMES):
            raise SpecError("sections must name exactly the five v1 sections")
        for section in self.sections.values():
            if section is not None:
                if not isinstance(section, Mapping):
                    raise SpecError("a section must be an object or null")
                validate_safe_value(section)
        domains = [seed.domain for seed in self.seeds]
        if len(set(domains)) != len(domains):
            raise SpecError("seed domains must be unique")
        if len(set(self.inputs)) != len(self.inputs):
            raise SpecError("inputs must not repeat")
        for run_id in self.informed_by:
            require_run_id(run_id, "informed_by")
        if len(set(self.informed_by)) != len(self.informed_by):
            raise SpecError("informed_by must not repeat")
        for split in self.splits_accessed:
            require_split(split)
        if len(set(self.splits_accessed)) != len(self.splits_accessed):
            raise SpecError("splits_accessed must not repeat")
        if self.candidate_id is not None:
            require_identifier(self.candidate_id, "candidate_id")
        if self.selection_round is not None and not is_non_negative_int(self.selection_round):
            raise SpecError("selection_round must be a non-negative integer")
        if self.extra:
            raise SpecError("run spec v1 has no extra fields")

    def to_json(self) -> dict[str, object]:
        return {
            "entrypoint": self.entrypoint,
            "informed_by": sorted(self.informed_by),
            "inputs": [ref.to_json() for ref in self.inputs],
            "schema": SPEC_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "sections": {name: self.sections[name] for name in SECTION_NAMES},
            "seeds": [
                {"domain": seed.domain, "value": seed.value}
                for seed in sorted(self.seeds, key=lambda seed: seed.domain)
            ],
            "selection": {
                "candidate_id": self.candidate_id,
                "selection_round": self.selection_round,
            },
            "splits_accessed": sorted(split.value for split in self.splits_accessed),
            "study_id": self.study_id,
        }

    def to_bytes(self) -> bytes:
        data = canonical_line(self.to_json())
        if len(data) > MAX_SPEC_BYTES:
            raise SpecError("run spec exceeds the maximum size")
        return data

    def sha256(self) -> str:
        return sha256_hex(self.to_bytes())

    def section_sha256(self, name: str) -> str | None:
        section = self.sections[name]
        if section is None:
            return None
        return sha256_hex(canonical_line(dict(section)))


def parse_run_spec(data: bytes) -> RunSpec:
    """Parse canonical ``run_spec.json`` bytes, rejecting anything outside the v1 schema."""
    if len(data) > MAX_SPEC_BYTES or not data.endswith(b"\n"):
        raise SpecError("run spec is too large or does not end with one newline")
    try:
        document = parse_canonical_json(data[:-1])
    except FormatError:
        raise SpecError("run spec is not canonical JSON") from None
    keys = {
        "entrypoint",
        "informed_by",
        "inputs",
        "schema",
        "schema_version",
        "sections",
        "seeds",
        "selection",
        "splits_accessed",
        "study_id",
    }
    if set(document) != keys or document["schema"] != SPEC_SCHEMA:
        raise SpecError("run spec fields do not match the v1 schema")
    if not is_int(document["schema_version"]) or document["schema_version"] != SCHEMA_VERSION:
        raise SpecError("run spec schema_version is not supported")
    sections = document["sections"]
    selection = document["selection"]
    if not isinstance(sections, Mapping) or not isinstance(selection, Mapping):
        raise SpecError("run spec sections or selection are malformed")
    if set(selection) != {"candidate_id", "selection_round"}:
        raise SpecError("run spec selection fields do not match the v1 schema")
    seeds = _list(document["seeds"])
    inputs = _list(document["inputs"])
    informed_by = _list(document["informed_by"])
    splits = _list(document["splits_accessed"])
    parsed_seeds: list[Seed] = []
    for seed in seeds:
        if not isinstance(seed, Mapping) or set(seed) != {"domain", "value"}:
            raise SpecError("seed entries must have domain and value")
        value = seed["value"]
        if not is_int(value):
            raise SpecError("seed value must be an integer")
        parsed_seeds.append(Seed(_text(seed["domain"]), value))
    candidate = selection["candidate_id"]
    selection_round = selection["selection_round"]
    if selection_round is not None and not is_int(selection_round):
        raise SpecError("selection_round must be an integer or null")
    spec = RunSpec(
        study_id=_text(document["study_id"]),
        entrypoint=_text(document["entrypoint"]),
        sections={name: _section(sections.get(name)) for name in SECTION_NAMES if name in sections},
        seeds=tuple(parsed_seeds),
        inputs=tuple(parse_input(item) for item in inputs),
        informed_by=tuple(_text(item) for item in informed_by),
        splits_accessed=tuple(require_split(item) for item in splits),
        candidate_id=None if candidate is None else _text(candidate),
        selection_round=selection_round,
    )
    if spec.to_bytes() != data:
        raise SpecError("run spec is not in canonical v1 form")
    return spec


def metric_value(value: int | Decimal | float) -> dict[str, object]:
    """Encode a metric value exactly: integers as integers, everything else as decimal text."""
    if isinstance(value, bool):
        raise SpecError("booleans are not metric values")
    if isinstance(value, int):
        return {"text": str(value), "type": "integer"}
    try:
        return {"text": decimal_text(value), "type": "decimal"}
    except (TypeError, ValueError) as exc:
        raise SpecError(f"metric value is not a finite number: {exc}") from None


def validate_metric_value(value: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"text", "type"}:
        raise SpecError("metric value must have type and text")
    text, kind = value["text"], value["type"]
    if kind == "integer":
        if not isinstance(text, str) or re.fullmatch(r"-?(0|[1-9][0-9]*)", text) is None:
            raise SpecError("integer metric text is malformed")
    elif kind == "decimal":
        if not is_decimal_text(text):
            raise SpecError("decimal metric text is malformed")
    else:
        raise SpecError("metric value type is not integer or decimal")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionIdentity:
    """The full identity of one execution: spec, code, configuration, and runtime."""

    spec_sha256: str
    code_commit: str | None
    code_tree_dirty: bool | None
    dirty_tree_sha256: str | None
    package_version: str
    uv_lock_sha256: str | None
    installed_environment_sha256: str | None
    app_config_sha256: str
    config_section_sha256: Mapping[str, str | None]
    python_version: str
    platform: str
    entrypoint: str
    version: int = IDENTITY_V2

    def __post_init__(self) -> None:
        if isinstance(self.version, bool) or self.version not in IDENTITY_VERSIONS:
            raise SpecError("execution identity version is not supported")
        for name in ("spec_sha256", "app_config_sha256"):
            if not is_sha256(getattr(self, name)):
                raise SpecError(f"{name} must be a SHA-256 hex digest")
        for name in ("dirty_tree_sha256", "uv_lock_sha256"):
            value = getattr(self, name)
            if value is not None and not is_sha256(value):
                raise SpecError(f"{name} must be a SHA-256 hex digest or null")
        environment = self.installed_environment_sha256
        if self.version == IDENTITY_V1 and environment is not None:
            # Option B: no installed-environment fingerprint is approved in v1, so the
            # value must be null and no v1 run can be evidence-eligible.
            raise SpecError("installed_environment_sha256 must be null in v1")
        if environment is not None and not is_sha256(environment):
            raise SpecError("installed_environment_sha256 must be a SHA-256 hex digest or null")
        if self.code_commit is not None and (
            not isinstance(self.code_commit, str) or _COMMIT.fullmatch(self.code_commit) is None
        ):
            raise SpecError("code_commit must be a 40-character lowercase hex commit or null")
        if self.code_tree_dirty is not None and not isinstance(self.code_tree_dirty, bool):
            raise SpecError("code_tree_dirty must be a bool or null")
        if self.code_commit is None and (
            self.code_tree_dirty is not None or self.dirty_tree_sha256 is not None
        ):
            raise SpecError("an unknown commit requires unknown dirty state")
        if self.code_tree_dirty is True and self.dirty_tree_sha256 is None:
            raise SpecError("a dirty tree requires dirty_tree_sha256")
        if self.code_tree_dirty is not True and self.dirty_tree_sha256 is not None:
            raise SpecError("dirty_tree_sha256 is only recorded for a dirty tree")
        if self.code_commit is not None and self.code_tree_dirty is None:
            raise SpecError("a known commit requires a known dirty state")
        for value, pattern, what in (
            (self.package_version, _PACKAGE_VERSION, "package_version"),
            (self.python_version, _PYTHON_VERSION, "python_version"),
            (self.platform, _PLATFORM, "platform"),
            (self.entrypoint, ENTRYPOINT, "entrypoint"),
        ):
            if not isinstance(value, str) or pattern.fullmatch(value) is None:
                raise SpecError(f"{what} has an invalid format")
        if set(self.config_section_sha256) != set(SECTION_NAMES):
            raise SpecError("config_section_sha256 must name exactly the five v1 sections")
        for digest in self.config_section_sha256.values():
            if digest is not None and not is_sha256(digest):
                raise SpecError("a config section hash is malformed")

    def to_json(self) -> dict[str, object]:
        return {
            "app_config_sha256": self.app_config_sha256,
            "code_commit": self.code_commit,
            "code_tree_dirty": self.code_tree_dirty,
            "config_section_sha256": {
                name: self.config_section_sha256[name] for name in SECTION_NAMES
            },
            "dirty_tree_sha256": self.dirty_tree_sha256,
            "entrypoint": self.entrypoint,
            "installed_environment_sha256": self.installed_environment_sha256,
            "package_version": self.package_version,
            "platform": self.platform,
            "python_version": self.python_version,
            "schema": IDENTITY_SCHEMA,
            "schema_version": self.version,
            "spec_sha256": self.spec_sha256,
            "uv_lock_sha256": self.uv_lock_sha256,
        }

    def sha256(self) -> str:
        return sha256_hex(canonical_line(self.to_json()))

    def code_is_clean(self) -> bool:
        return (
            self.code_commit is not None
            and self.code_tree_dirty is False
            and self.uv_lock_sha256 is not None
        )


def parse_execution_identity(value: object) -> ExecutionIdentity:
    """Parse a v1 or v2 execution identity (both have the same fields)."""
    keys = (set(ExecutionIdentity.__dataclass_fields__) - {"version"}) | {
        "schema",
        "schema_version",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise SpecError("execution identity fields do not match the schema")
    version = value["schema_version"]
    if (
        value["schema"] != IDENTITY_SCHEMA
        or not is_int(version)
        or version not in IDENTITY_VERSIONS
    ):
        raise SpecError("execution identity schema is not supported")
    sections = value["config_section_sha256"]
    if not isinstance(sections, Mapping):
        raise SpecError("config_section_sha256 must be an object")
    dirty = value["code_tree_dirty"]
    if dirty is not None and not isinstance(dirty, bool):
        raise SpecError("code_tree_dirty must be a bool or null")
    return ExecutionIdentity(
        spec_sha256=_text(value["spec_sha256"]),
        code_commit=_optional_text(value["code_commit"]),
        code_tree_dirty=dirty,
        dirty_tree_sha256=_optional_text(value["dirty_tree_sha256"]),
        package_version=_text(value["package_version"]),
        uv_lock_sha256=_optional_text(value["uv_lock_sha256"]),
        installed_environment_sha256=_optional_text(value["installed_environment_sha256"]),
        app_config_sha256=_text(value["app_config_sha256"]),
        config_section_sha256={name: _optional_text(item) for name, item in sections.items()},
        python_version=_text(value["python_version"]),
        platform=_text(value["platform"]),
        entrypoint=_text(value["entrypoint"]),
        version=int(str(version)),
    )


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise SpecError("expected a string value")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise SpecError("run spec lists are malformed")
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else _text(value)


def _section(value: object) -> Mapping[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise SpecError("a section must be an object or null")
    return value


def spec_sections(
    **sections: Mapping[str, object] | None,
) -> dict[str, Mapping[str, object] | None]:
    """Build the five-section mapping, defaulting unspecified sections to null."""
    unknown = set(sections) - set(SECTION_NAMES)
    if unknown:
        raise SpecError("unknown spec section")
    return {name: sections.get(name) for name in SECTION_NAMES}
