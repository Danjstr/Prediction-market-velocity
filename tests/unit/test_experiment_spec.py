"""Tests for run specs, safe values, input references, metrics, and execution identity."""

import json
from decimal import Decimal

import pytest

from pmv.experiment_spec import (
    IDENTITY_V1,
    IDENTITY_V2,
    SECTION_NAMES,
    V1_FAILURE_CODES,
    ExecutionIdentity,
    FailureCode,
    RawCaptureInput,
    RunArtifactInput,
    RunSpec,
    Seed,
    SpecError,
    Split,
    metric_value,
    parse_execution_identity,
    parse_input,
    parse_run_spec,
    require_split,
    spec_sections,
    validate_safe_value,
)

RUN_A = "20261013T034021.123456Z_" + "a" * 32
CAPTURE = "20261013T034021.123456Z_" + "c" * 32


def make_spec(**overrides: object) -> RunSpec:
    values: dict[str, object] = {
        "study_id": "velocity_baseline",
        "entrypoint": "pmv.research.baselines:run",
        "sections": spec_sections(
            model={"family": "logistic", "l2": "0.01", "max_iter": 200},
            validation={"train_start": "2026-01-01T00:00:00.000000Z", "embargo_minutes": 15},
        ),
        "seeds": (Seed("numpy", 7), Seed("cv_split", 11)),
        "inputs": (
            RawCaptureInput(CAPTURE, "1" * 64),
            RunArtifactInput(RUN_A, "features.parquet", "2" * 64),
        ),
        "splits_accessed": (Split.TRAIN, Split.DEVELOPMENT),
    }
    values.update(overrides)
    return RunSpec(**values)  # type: ignore[arg-type]  # test helper forwards typed keywords


def test_spec_round_trips_canonically_and_hash_covers_only_its_bytes() -> None:
    spec = make_spec()
    data = spec.to_bytes()
    assert parse_run_spec(data).to_bytes() == data
    assert parse_run_spec(data).sha256() == spec.sha256()
    document = json.loads(data)
    assert [seed["domain"] for seed in document["seeds"]] == ["cv_split", "numpy"]
    assert set(document["sections"]) == set(SECTION_NAMES)
    assert spec.sha256() != make_spec(seeds=(Seed("numpy", 8),)).sha256()


def test_same_spec_with_different_input_bytes_has_a_different_hash() -> None:
    first = make_spec(inputs=(RawCaptureInput(CAPTURE, "1" * 64),))
    second = make_spec(inputs=(RawCaptureInput(CAPTURE, "3" * 64),))
    assert first.sha256() != second.sha256()


@pytest.mark.parametrize(
    "value",
    [
        0.5,
        "free text here",
        "/abs/path",
        "../x",
        {"Bad Key": 1},
        {"key": object()},
        "token=abc",
    ],
)
def test_safe_values_reject_floats_text_paths_and_secrets(value: object) -> None:
    with pytest.raises(SpecError):
        validate_safe_value({"a": value})


def test_safe_values_reject_deep_nesting() -> None:
    value: object = 1
    for _ in range(10):
        value = {"a": value}
    with pytest.raises(SpecError, match="nested too deeply"):
        validate_safe_value(value)


@pytest.mark.parametrize(
    "document",
    [
        {"kind": "dataset_snapshot", "snapshot_id": "x"},
        {"kind": "path", "path": "/data/january"},
        {"kind": "raw_capture", "capture_id": CAPTURE},
    ],
)
def test_unrepresentable_inputs_cannot_be_referenced(document: dict[str, object]) -> None:
    with pytest.raises(SpecError):
        parse_input(document)


def test_protected_holdout_is_refused() -> None:
    with pytest.raises(SpecError, match="protected_holdout"):
        require_split("protected_holdout")
    with pytest.raises(SpecError, match="protected_holdout"):
        make_spec(splits_accessed=(Split.PROTECTED_HOLDOUT,))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(extra=1),
        lambda d: d.update(schema_version=2),
        lambda d: d["sections"].update(unknown=None),
        lambda d: d["seeds"].append({"domain": "numpy", "value": 1}),
        lambda d: d.update(schema_version=True),
        lambda d: d["seeds"].__setitem__(0, {"domain": "cv_split", "value": True}),
        lambda d: d["selection"].update(selection_round=True),
        lambda d: d["inputs"].append(d["inputs"][0]),
    ],
)
def test_parse_rejects_schema_violations(change: object) -> None:
    document = json.loads(make_spec().to_bytes())
    change(document)  # type: ignore[operator]  # parametrized mutation
    data = json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    with pytest.raises(SpecError):
        parse_run_spec(data)


def test_seeds_are_bounded_unique_integers() -> None:
    with pytest.raises(SpecError):
        Seed("numpy", 2**64)
    with pytest.raises(SpecError):
        Seed("numpy", True)
    with pytest.raises(SpecError, match="unique"):
        make_spec(seeds=(Seed("numpy", 1), Seed("numpy", 2)))


def test_metric_values_are_exact_and_finite() -> None:
    assert metric_value(3) == {"text": "3", "type": "integer"}
    assert metric_value(Decimal("0.6931")) == {"text": "0.6931", "type": "decimal"}
    assert metric_value(0.1) == {"text": "0.1", "type": "decimal"}
    for bad in (float("nan"), float("inf"), True):
        with pytest.raises(SpecError):
            metric_value(bad)


def identity(**overrides: object) -> ExecutionIdentity:
    values: dict[str, object] = {
        "spec_sha256": "1" * 64,
        "code_commit": "a" * 40,
        "code_tree_dirty": False,
        "dirty_tree_sha256": None,
        "package_version": "0.0.0",
        "uv_lock_sha256": "2" * 64,
        "installed_environment_sha256": None,
        "app_config_sha256": "3" * 64,
        "config_section_sha256": dict.fromkeys(SECTION_NAMES),
        "python_version": "3.13.5",
        "platform": "linux-x86_64",
        "entrypoint": "pmv.research.baselines:run",
    }
    values.update(overrides)
    return ExecutionIdentity(**values)  # type: ignore[arg-type]  # test helper forwards typed keywords


def test_execution_identity_round_trips_and_hashes_deterministically() -> None:
    first = identity()
    assert parse_execution_identity(first.to_json()) == first
    assert first.sha256() == identity().sha256()
    assert first.sha256() != identity(python_version="3.13.6").sha256()
    assert first.code_is_clean()
    assert not identity(uv_lock_sha256=None).code_is_clean()


@pytest.mark.parametrize(
    "overrides",
    [
        {"code_commit": None, "code_tree_dirty": False},
        {"code_commit": None, "code_tree_dirty": None, "dirty_tree_sha256": "4" * 64},
        {"code_tree_dirty": True, "dirty_tree_sha256": None},
        {"code_tree_dirty": False, "dirty_tree_sha256": "4" * 64},
        {"code_tree_dirty": None},
        {"platform": "Linux x86_64 user@host"},
        {"config_section_sha256": {"model": None}},
        {"installed_environment_sha256": "9" * 64, "version": IDENTITY_V1},
        {"installed_environment_sha256": "not-a-digest"},
        {"version": 3},
        {"version": True},
    ],
)
def test_execution_identity_rejects_inconsistent_null_combinations(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(SpecError):
        identity(**overrides)


def test_parsed_execution_identity_rejects_boolean_schema_version() -> None:
    document = identity().to_json()
    document["schema_version"] = True
    with pytest.raises(SpecError, match="schema is not supported"):
        parse_execution_identity(document)


def test_v1_and_v2_identities_parse_exactly_as_their_version() -> None:
    v1 = identity(version=IDENTITY_V1)
    v2 = identity(installed_environment_sha256="9" * 64)
    assert v2.version == IDENTITY_V2
    assert v1.to_json()["schema_version"] == 1
    assert v2.to_json()["schema_version"] == 2
    assert parse_execution_identity(v1.to_json()) == v1
    assert parse_execution_identity(v2.to_json()) == v2
    assert v1.sha256() != identity(version=IDENTITY_V2).sha256()
    forged = v1.to_json()
    forged["installed_environment_sha256"] = "9" * 64
    with pytest.raises(SpecError, match="must be null in v1"):
        parse_execution_identity(forged)
    assert frozenset(FailureCode) - {FailureCode.ENVIRONMENT_CHANGED} == V1_FAILURE_CODES
