"""The JSON Schema documents must agree with the authoritative Python validators."""

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from pmv.experiment_ledger import (
    _ENVELOPE,
    _FIELDS,
    LedgerEvent,
    LedgerState,
    checkpoint_line,
    completion_manifest_bytes,
    encode_entry,
    verify_ledger,
)
from pmv.experiment_spec import (
    SECTION_NAMES,
    V1_FAILURE_CODES,
    AbortReason,
    ArtifactType,
    ExecutionIdentity,
    FailureCode,
    MediaType,
    RunClass,
    RunSpec,
    Split,
    SupersedeReason,
    WarningCode,
    spec_sections,
)
from pmv.experiments import ExperimentStore

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
TS = "2026-10-13T03:40:21.123456Z"
RUN = "20261013T034021.123456Z_" + "a" * 32


def load(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return document


ENTRY = load("experiment_ledger_entry_v1.json")
ENTRY_V2 = load("experiment_ledger_entry_v2.json")
SPEC = load("experiment_run_spec_v1.json")
MANIFEST = load("experiment_run_manifest_v1.json")
CHECKPOINT = load("experiment_ledger_checkpoint_v1.json")
BRANCHES = {branch["properties"]["event_type"]["const"]: branch for branch in ENTRY["oneOf"]}
BRANCHES_V2 = {branch["properties"]["event_type"]["const"]: branch for branch in ENTRY_V2["oneOf"]}


def matches(schema: dict[str, Any], value: str) -> bool:
    return re.search(schema["pattern"], value) is not None


def identity() -> ExecutionIdentity:
    return ExecutionIdentity(
        spec_sha256="1" * 64,
        code_commit="a" * 40,
        code_tree_dirty=False,
        dirty_tree_sha256=None,
        package_version="0.0.0",
        uv_lock_sha256="2" * 64,
        installed_environment_sha256=None,
        app_config_sha256="3" * 64,
        config_section_sha256=dict.fromkeys(SECTION_NAMES),
        python_version="3.13.5",
        platform="linux-x86_64",
        entrypoint="pmv.research.baselines:run",
    )


def test_every_event_branch_has_exactly_the_python_field_set() -> None:
    assert ENTRY["properties"]["event_type"]["enum"] == [event.value for event in LedgerEvent]
    assert set(BRANCHES) == {event.value for event in LedgerEvent}
    assert set(ENTRY["required"]) == _ENVELOPE
    for event in LedgerEvent:
        branch = BRANCHES[event.value]
        assert set(branch["propertyNames"]["enum"]) == _ENVELOPE | _FIELDS[event]
        assert set(branch["required"]) == _FIELDS[event]


@pytest.mark.parametrize(
    ("event", "field", "values"),
    [
        ("run_aborted", "reason", AbortReason),
        ("run_superseded", "reason", SupersedeReason),
        ("run_failed", "failure_code", FailureCode),
        ("warning_recorded", "code", WarningCode),
        ("artifact_registered", "artifact_type", ArtifactType),
        ("artifact_registered", "media_type", MediaType),
    ],
)
def test_event_specific_enums_match_python(event: str, field: str, values: type[StrEnum]) -> None:
    expected = [item.value for item in values]
    if values is FailureCode:
        assert BRANCHES[event]["properties"][field]["enum"] == [
            item.value for item in FailureCode if item in V1_FAILURE_CODES
        ]
    else:
        assert BRANCHES[event]["properties"][field]["enum"] == expected
    assert BRANCHES_V2[event]["properties"][field]["enum"] == expected


def test_the_v2_entry_schema_differs_from_v1_only_where_step_10_changed_it() -> None:
    assert ENTRY["properties"]["schema_version"] == {"const": 1}
    assert ENTRY_V2["properties"]["schema_version"] == {"const": 2}
    assert ENTRY_V2["properties"]["event_type"] == ENTRY["properties"]["event_type"]
    for event in LedgerEvent:
        assert set(BRANCHES_V2[event.value]["required"]) == set(BRANCHES[event.value]["required"])
    identity_v1 = ENTRY["$defs"]["execution_identity"]["properties"]
    identity_v2 = ENTRY_V2["$defs"]["execution_identity"]["properties"]
    assert identity_v1["schema_version"] == {"const": 1}
    assert identity_v2["schema_version"] == {"const": 2}
    changed = {"schema_version", "installed_environment_sha256"}
    assert {key: value for key, value in identity_v1.items() if key not in changed} == {
        key: value for key, value in identity_v2.items() if key not in changed
    }
    assert identity_v2["installed_environment_sha256"]["oneOf"] == [
        {"$ref": "#/$defs/sha256"},
        {"type": "null"},
    ]
    started = BRANCHES_V2["run_started"]["properties"]["evidence_eligible_at_start"]
    assert started["type"] == "boolean"


def test_shared_definitions_match_python() -> None:
    definitions = ENTRY["$defs"]
    assert definitions["run_class"]["enum"] == [item.value for item in RunClass]
    assert definitions["split"]["enum"] == [
        item.value for item in Split if item is not Split.PROTECTED_HOLDOUT
    ]
    assert matches(definitions["artifact_name"], "model.bin")
    assert matches(definitions["artifact_name"], "predictions")
    assert not matches(definitions["artifact_name"], "../model.bin")
    assert BRANCHES["artifact_registered"]["properties"]["name"] == {
        "$ref": "#/$defs/artifact_name"
    }
    assert BRANCHES["metric_recorded"]["properties"]["name"] == {"$ref": "#/$defs/identifier"}
    assert not matches(definitions["run_id"], "2026101\u06633T034021.123456Z_" + "a" * 32)
    assert not matches(definitions["timestamp"], "2026-10-13T03:40:21.12345\u0666Z")
    started = BRANCHES["run_started"]["properties"]
    assert started["spec_size_bytes"]["minimum"] == 1
    assert started["evidence_eligible_at_start"] == {
        "const": False,
        "description": started["evidence_eligible_at_start"]["description"],
    }
    assert definitions["resolved_inputs"]["uniqueItems"] is True
    environment = definitions["execution_identity"]["properties"]["installed_environment_sha256"]
    assert environment["const"] is None


def test_no_schema_uses_unicode_digit_classes() -> None:
    for path in SCHEMAS.glob("experiment_*.json"):
        assert "\\\\d" not in path.read_text(encoding="utf-8")


def test_object_schemas_list_exactly_the_python_keys() -> None:
    assert set(ENTRY["$defs"]["execution_identity"]["required"]) == set(identity().to_json())
    spec = RunSpec(
        study_id="s",
        entrypoint="pmv.research.baselines:run",
        sections=spec_sections(),
    )
    assert set(SPEC["required"]) == set(spec.to_json()) == set(SPEC["properties"])
    assert SPEC["properties"]["inputs"]["uniqueItems"] is True
    assert set(CHECKPOINT["required"]) == set(json.loads(checkpoint_line(0, "a" * 64, TS)))
    state: LedgerState = verify_ledger(b"")[0]
    data = b""
    started = identity()
    for event, run_id, fields in (
        (LedgerEvent.LEDGER_CREATED, None, {"store_id": "0" * 32}),
        (LedgerEvent.RUN_RESERVED, RUN, {"run_class": "development", "study_id": "s"}),
        (
            LedgerEvent.RUN_STARTED,
            RUN,
            {
                "effective_run_class_at_start": "development",
                "evidence_eligible_at_start": False,
                "execution_identity": started.to_json(),
                "execution_identity_sha256": started.sha256(),
                "inputs": [],
                "spec_sha256": started.spec_sha256,
                "spec_size_bytes": 100,
            },
        ),
    ):
        data += encode_entry(state, event, run_id, TS, fields)
        state = verify_ledger(data)[0]
    manifest = json.loads(completion_manifest_bytes(state, RUN))
    assert set(MANIFEST["required"]) == set(manifest) == set(MANIFEST["properties"])


def test_store_identity_schema_matches_the_store_record(tmp_path: Path) -> None:
    root = tmp_path / "exp-root"
    root.mkdir(mode=0o700)
    repo = Path(__file__).resolve().parents[2]
    with ExperimentStore(
        root, repo_root=repo, app_config_sha256="0" * 64, checkpoint_file=tmp_path / "c.jsonl"
    ):
        pass
    schema = load("experiment_store_v1.json")
    record = json.loads((root / "store.v1.json").read_text(encoding="ascii"))
    assert set(schema["required"]) == set(record) == set(schema["properties"])
    assert matches(schema["$defs"]["store_id"], record["store_id"])
    assert BRANCHES["ledger_created"]["properties"]["store_id"] == {"$ref": "#/$defs/store_id"}
