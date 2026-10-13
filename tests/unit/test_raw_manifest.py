"""Tests for the closed raw capture manifest schema (pmv.raw.manifest v1)."""

import hashlib
import json
from pathlib import Path

import pytest

from pmv.config import Environment
from pmv.raw_format import canonical_json
from pmv.raw_manifest import (
    BackupStatus,
    CapturePolicy,
    CaptureTimes,
    ManifestError,
    Observations,
    RawManifest,
    RawObjectMetadata,
    RuntimeProvenance,
    SourceIdentity,
    Transport,
    expected_relative_path,
    manifest_keys,
    parse_manifest,
    validate_capture_id,
    validate_identifier,
)

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "schemas" / "raw_manifest_v1.json"
CAPTURE_ID = "20261013T034021.123456Z_" + "5f3e8b6b8ac14c5eab77375997d65712"
SOURCE = SourceIdentity(
    source_id="unit_source", feed_id="unit_feed", transport=Transport.WEBSOCKET, endpoint_id="ep_v1"
)
TS = "2026-10-13T03:40:21.123456Z"


def provenance(**overrides: object) -> RuntimeProvenance:
    values: dict[str, object] = {
        "code_commit": "a" * 40,
        "code_tree_dirty": False,
        "config_source_sha256": "b" * 64,
        "raw_config_sha256": "c" * 64,
        "environment": Environment.TEST,
        "python_version": "3.13.5",
        "platform": "linux-x86_64",
        "machine_label": None,
        "parents": (),
    }
    values.update(overrides)
    return RuntimeProvenance(**values)  # type: ignore[arg-type]  # test helper forwards typed keywords


def manifest() -> RawManifest:
    return RawManifest(
        capture_id=CAPTURE_ID,
        source=SOURCE,
        raw_object=RawObjectMetadata(
            relative_path=expected_relative_path(SOURCE, CAPTURE_ID),
            size_bytes=123,
            sha256="d" * 64,
            record_count=4,
        ),
        times=CaptureTimes(
            capture_started_at=TS,
            capture_ended_at=TS,
            first_received_at=TS,
            last_received_at=TS,
            first_source_timestamp=None,
            last_source_timestamp=None,
            finalized_at=TS,
            monotonic_duration_ns=5,
        ),
        observations=Observations(
            payload_count=3,
            event_count=1,
            malformed_message_count=0,
            reconnect_count=1,
            gap_event_count=0,
            rate_limit_event_count=0,
            source_clock_regression_count=0,
            local_clock_regression_count=0,
        ),
        provenance=provenance(),
        policy=CapturePolicy(
            retention_class=None,
            backup_policy_id=None,
            backup_status_at_finalization=BackupStatus.NOT_CONFIGURED,
        ),
    )


def document() -> dict[str, object]:
    return manifest().to_json()


def encode(doc: dict[str, object]) -> bytes:
    return canonical_json(doc) + b"\n"


def test_manifest_round_trips_through_canonical_bytes() -> None:
    data = manifest().to_bytes()
    assert data.endswith(b"}\n")
    assert data.count(b"\n") == 1
    assert data == canonical_json(json.loads(data)) + b"\n"
    assert parse_manifest(data) == manifest()


def test_manifest_hash_is_over_the_exact_bytes_and_is_not_inside_the_manifest() -> None:
    data = manifest().to_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest.encode() not in data
    assert "manifest_sha256" not in json.loads(data)


def test_noncanonical_bytes_are_rejected() -> None:
    data = manifest().to_bytes()
    pretty = json.dumps(json.loads(data), indent=2).encode() + b"\n"
    for variant in (data[:-1], data + b"\n", pretty, data.replace(b'":', b'": ', 1)):
        with pytest.raises(ManifestError):
            parse_manifest(variant)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("source",),
        ("object",),
        ("time",),
        ("observations",),
        ("provenance",),
        ("policy_at_capture",),
    ],
)
def test_unknown_fields_are_rejected_at_every_level(path: tuple[str, ...]) -> None:
    doc = document()
    target: dict[str, object] = doc
    for key in path:
        child = target[key]
        assert isinstance(child, dict)
        target = child
    target["unexpected"] = 1
    with pytest.raises(ManifestError, match=r"schema|fields"):
        parse_manifest(encode(doc))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", 2),
        ("schema_version", 0),
        ("schema_version", True),
        ("schema", "pmv.raw.manifest.v2"),
        ("status", "partial"),
        ("capture_id", "../../etc"),
    ],
)
def test_other_versions_and_statuses_are_rejected(key: str, value: object) -> None:
    doc = {**document(), key: value}
    with pytest.raises(ManifestError):
        parse_manifest(encode(doc))


def test_floats_are_rejected() -> None:
    data = manifest().to_bytes().replace(b'"size_bytes":123', b'"size_bytes":123.0')
    with pytest.raises(ManifestError):
        parse_manifest(data)


def test_relative_path_must_match_the_capture() -> None:
    doc = document()
    obj = doc["object"]
    assert isinstance(obj, dict)
    obj["relative_path"] = expected_relative_path(SOURCE, CAPTURE_ID).replace(
        "unit_feed", "other_feed"
    )
    with pytest.raises(ManifestError, match="relative_path"):
        parse_manifest(encode(doc))


@pytest.mark.parametrize(
    "value",
    ["", "A", "1abc", "../x", "x/y", "x\\y", ".hidden", "x y", "x\n", "café", "/abs", "a" * 65],
)
def test_identifiers_reject_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError, match="must match"):
        validate_identifier(value, "source_id")
    with pytest.raises(ValueError, match="must match"):
        SourceIdentity(source_id=value, feed_id="f", transport=Transport.HTTP, endpoint_id="e")


@pytest.mark.parametrize(
    "value", ["", "../x", "20261013T034021Z_" + "0" * 32, "20261013T034021.123456Z_" + "G" * 32]
)
def test_capture_ids_are_validated(value: str) -> None:
    with pytest.raises(ValueError, match="capture ID"):
        validate_capture_id(value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"machine_label": "Bearer abcdefghijkl"},
        {"machine_label": "token=abc"},
        {"machine_label": "my host"},
        {"code_commit": "not-a-commit"},
        {"code_commit": None, "code_tree_dirty": True},
        {"python_version": "3.13.5 (main, secret)"},
        {"platform": "Linux x86_64 user@host"},
        {"config_source_sha256": "password=hunter2"},
        {"parents": ("../etc",)},
    ],
)
def test_provenance_rejects_free_text_and_secret_like_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"must|invalid|both|SHA-256|capture ID"):
        provenance(**overrides)


def test_secret_like_values_in_manifest_bytes_are_rejected_without_echo() -> None:
    doc = document()
    prov = doc["provenance"]
    assert isinstance(prov, dict)
    prov["machine_label"] = "password=SENSITIVEVALUE"
    with pytest.raises(ManifestError) as excinfo:
        parse_manifest(encode(doc))
    assert "SENSITIVEVALUE" not in str(excinfo.value)


def test_json_schema_document_matches_the_closed_schema() -> None:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    doc = document()
    assert sorted(schema["required"]) == sorted(manifest_keys()) == sorted(doc)
    assert schema["additionalProperties"] is False
    for section in ("source", "object", "time", "observations", "provenance", "policy_at_capture"):
        section_doc = doc[section]
        assert isinstance(section_doc, dict)
        properties = schema["properties"][section]
        assert sorted(properties["required"]) == sorted(section_doc)
        assert sorted(properties["properties"]) == sorted(section_doc)
        assert properties["additionalProperties"] is False
