"""Immutable provenance manifest for a finalized raw capture (``pmv.raw.manifest`` v1).

The manifest is the authoritative description of a capture. It has a closed schema:
unknown fields, other schema versions, floats, and noncanonical bytes are rejected, and
every string value has an exact format or a fixed set of values, so no free text (and
therefore no credential) can be stored in it. Its canonical bytes are
``canonical_json(manifest) + b"\\n"``; the SHA-256 of those bytes is recorded outside the
manifest (in the catalog), never inside it.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pmv.config import Environment
from pmv.raw_format import (
    FORMAT_NAME,
    FORMAT_VERSION,
    RawFormatError,
    canonical_json,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
)
from pmv.redaction import redact_text

SCHEMA: Final = "pmv.raw.manifest"
SCHEMA_VERSION: Final = 1
MAX_MANIFEST_BYTES: Final = 1_048_576
OBJECT_NAME: Final = "records.pmvraw"
IDENTIFIER: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")
CAPTURE_ID: Final = re.compile(r"\d{8}T\d{6}\.\d{6}Z_[0-9a-f]{32}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_PYTHON_VERSION: Final = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}")
_PLATFORM: Final = re.compile(r"[a-z0-9]{1,32}-[a-z0-9_]{1,32}")
_RELATIVE_PATH: Final = re.compile(
    r"raw/v1/[a-z][a-z0-9_]{0,63}/[a-z][a-z0-9_]{0,63}/\d{4}/\d{2}/\d{2}/"
    r"\d{8}T\d{6}\.\d{6}Z_[0-9a-f]{32}/records\.pmvraw"
)


class ManifestError(ValueError):
    """A manifest or one of its fields is invalid. Messages never include field values."""


class Transport(StrEnum):
    WEBSOCKET = "websocket"
    HTTP = "http"


class BackupStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    PENDING = "pending"


def validate_identifier(value: object, what: str) -> str:
    """Return ``value`` if it is a lowercase symbolic identifier usable as a path component."""
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{what} must match [a-z][a-z0-9_]{{0,63}}")
    _reject_secret_text(value, what)
    return value


def validate_capture_id(value: object) -> str:
    """Return ``value`` if it is a well-formed capture ID."""
    if not isinstance(value, str) or CAPTURE_ID.fullmatch(value) is None:
        raise ValueError("capture ID is malformed")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceIdentity:
    """Symbolic identity of a data source. Never derived from URLs or server strings."""

    source_id: str
    feed_id: str
    transport: Transport
    endpoint_id: str

    def __post_init__(self) -> None:
        validate_identifier(self.source_id, "source_id")
        validate_identifier(self.feed_id, "feed_id")
        validate_identifier(self.endpoint_id, "endpoint_id")
        if not isinstance(self.transport, Transport):
            raise ValueError("transport must be a Transport value")


@dataclass(frozen=True, slots=True, kw_only=True)
class RawObjectMetadata:
    relative_path: str
    size_bytes: int
    sha256: str
    record_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CaptureTimes:
    capture_started_at: str
    capture_ended_at: str
    first_received_at: str | None
    last_received_at: str | None
    first_source_timestamp: str | None
    last_source_timestamp: str | None
    finalized_at: str
    monotonic_duration_ns: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Observations:
    payload_count: int
    event_count: int
    malformed_message_count: int
    reconnect_count: int
    gap_event_count: int
    rate_limit_event_count: int
    source_clock_regression_count: int
    local_clock_regression_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RuntimeProvenance:
    """Where and how a capture was produced. Contains no hostname and no free text."""

    code_commit: str | None
    code_tree_dirty: bool | None
    config_source_sha256: str
    raw_config_sha256: str
    environment: Environment
    python_version: str
    platform: str
    machine_label: str | None
    parents: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.code_commit is not None and (
            not isinstance(self.code_commit, str) or _COMMIT.fullmatch(self.code_commit) is None
        ):
            raise ValueError("code_commit must be a 40-character lowercase hex commit or None")
        if self.code_tree_dirty is not None and not isinstance(self.code_tree_dirty, bool):
            raise ValueError("code_tree_dirty must be a bool or None")
        if (self.code_commit is None) != (self.code_tree_dirty is None):
            raise ValueError("code_commit and code_tree_dirty must both be known or both be None")
        for name in ("config_source_sha256", "raw_config_sha256"):
            if not is_sha256(getattr(self, name)):
                raise ValueError(f"{name} must be a SHA-256 hex digest")
        if not isinstance(self.environment, Environment):
            raise ValueError("environment must be an Environment value")
        _check_pattern(self.python_version, _PYTHON_VERSION, "python_version")
        _check_pattern(self.platform, _PLATFORM, "platform")
        if self.machine_label is not None:
            validate_identifier(self.machine_label, "machine_label")
        if not isinstance(self.parents, tuple):
            raise ValueError("parents must be a tuple of capture IDs")
        for parent in self.parents:
            validate_capture_id(parent)


@dataclass(frozen=True, slots=True, kw_only=True)
class CapturePolicy:
    retention_class: str | None
    backup_policy_id: str | None
    backup_status_at_finalization: BackupStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class RawManifest:
    capture_id: str
    source: SourceIdentity
    raw_object: RawObjectMetadata
    times: CaptureTimes
    observations: Observations
    provenance: RuntimeProvenance
    policy: CapturePolicy

    def to_json(self) -> dict[str, object]:
        """Return the manifest as a JSON-compatible dictionary, validating every field."""
        document = _manifest_document(self)
        parse_manifest_document(document)
        return document

    def to_bytes(self) -> bytes:
        """Return the canonical manifest bytes: canonical JSON plus one newline."""
        return canonical_json(self.to_json()) + b"\n"


def parse_manifest(data: bytes) -> RawManifest:
    """Parse canonical manifest bytes, rejecting anything outside the v1 schema."""
    if len(data) > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest exceeds the maximum size")
    if not data.endswith(b"\n"):
        raise ManifestError("manifest must end with exactly one newline")
    try:
        document = parse_canonical_json(data[:-1])
    except RawFormatError as exc:
        raise ManifestError(f"manifest is not canonical JSON: {exc}") from None
    return parse_manifest_document(document)


def parse_manifest_document(document: Mapping[str, object]) -> RawManifest:
    """Validate a decoded manifest document against the closed v1 schema."""
    top = _closed(
        document,
        {
            "schema",
            "schema_version",
            "capture_id",
            "status",
            "source",
            "object",
            "time",
            "observations",
            "provenance",
            "policy_at_capture",
        },
        "manifest",
    )
    if top["schema"] != SCHEMA:
        raise ManifestError("manifest schema is not pmv.raw.manifest")
    version = top["schema_version"]
    if isinstance(version, bool) or version != SCHEMA_VERSION:
        raise ManifestError("manifest schema_version is not supported")
    if top["status"] != "finalized":
        raise ManifestError("manifest status must be finalized")
    try:
        capture_id = validate_capture_id(top["capture_id"])
    except ValueError:
        raise ManifestError("manifest capture_id is malformed") from None

    source_doc = _closed(
        top["source"], {"source_id", "feed_id", "transport", "endpoint_id"}, "source"
    )
    try:
        source = SourceIdentity(
            source_id=_text(source_doc["source_id"], "source.source_id"),
            feed_id=_text(source_doc["feed_id"], "source.feed_id"),
            transport=Transport(_text(source_doc["transport"], "source.transport")),
            endpoint_id=_text(source_doc["endpoint_id"], "source.endpoint_id"),
        )
    except ValueError:
        raise ManifestError("manifest source is invalid") from None

    object_doc = _closed(
        top["object"],
        {
            "relative_path",
            "format",
            "format_version",
            "encoding",
            "compression",
            "size_bytes",
            "sha256",
            "record_count",
        },
        "object",
    )
    if object_doc["format"] != FORMAT_NAME or object_doc["format_version"] != FORMAT_VERSION:
        raise ManifestError("manifest object format is not pmv.raw.frames v1")
    if isinstance(object_doc["format_version"], bool):
        raise ManifestError("manifest object format_version is invalid")
    if object_doc["encoding"] != "binary" or object_doc["compression"] != "none":
        raise ManifestError("manifest object encoding or compression is not supported")
    relative_path = _text(object_doc["relative_path"], "object.relative_path")
    if _RELATIVE_PATH.fullmatch(relative_path) is None:
        raise ManifestError("manifest object.relative_path is malformed")
    raw_object = RawObjectMetadata(
        relative_path=relative_path,
        size_bytes=_count(object_doc["size_bytes"], "object.size_bytes"),
        sha256=_digest(object_doc["sha256"], "object.sha256"),
        record_count=_count(object_doc["record_count"], "object.record_count"),
    )

    time_doc = _closed(
        top["time"],
        {
            "capture_started_at",
            "capture_ended_at",
            "first_received_at",
            "last_received_at",
            "first_source_timestamp",
            "last_source_timestamp",
            "finalized_at",
            "monotonic_duration_ns",
        },
        "time",
    )
    times = CaptureTimes(
        capture_started_at=_timestamp(time_doc["capture_started_at"], "time.capture_started_at"),
        capture_ended_at=_timestamp(time_doc["capture_ended_at"], "time.capture_ended_at"),
        first_received_at=_optional_timestamp(
            time_doc["first_received_at"], "time.first_received_at"
        ),
        last_received_at=_optional_timestamp(time_doc["last_received_at"], "time.last_received_at"),
        first_source_timestamp=_optional_timestamp(
            time_doc["first_source_timestamp"], "time.first_source_timestamp"
        ),
        last_source_timestamp=_optional_timestamp(
            time_doc["last_source_timestamp"], "time.last_source_timestamp"
        ),
        finalized_at=_timestamp(time_doc["finalized_at"], "time.finalized_at"),
        monotonic_duration_ns=_count(
            time_doc["monotonic_duration_ns"], "time.monotonic_duration_ns"
        ),
    )

    observation_keys = (
        "payload_count",
        "event_count",
        "malformed_message_count",
        "reconnect_count",
        "gap_event_count",
        "rate_limit_event_count",
        "source_clock_regression_count",
        "local_clock_regression_count",
    )
    observation_doc = _closed(top["observations"], set(observation_keys), "observations")
    observations = Observations(
        **{key: _count(observation_doc[key], f"observations.{key}") for key in observation_keys}
    )

    provenance_doc = _closed(
        top["provenance"],
        {
            "software",
            "code_commit",
            "code_tree_dirty",
            "config_source_sha256",
            "raw_config_sha256",
            "environment",
            "python_version",
            "platform",
            "machine_label",
            "parents",
        },
        "provenance",
    )
    if provenance_doc["software"] != "pmv":
        raise ManifestError("manifest provenance.software must be pmv")
    parents = provenance_doc["parents"]
    if not isinstance(parents, list):
        raise ManifestError("manifest provenance.parents must be a list")
    dirty = provenance_doc["code_tree_dirty"]
    if dirty is not None and not isinstance(dirty, bool):
        raise ManifestError("manifest provenance.code_tree_dirty is invalid")
    try:
        provenance = RuntimeProvenance(
            code_commit=_optional_text(provenance_doc["code_commit"], "provenance.code_commit"),
            code_tree_dirty=dirty,
            config_source_sha256=_text(
                provenance_doc["config_source_sha256"], "provenance.config_source_sha256"
            ),
            raw_config_sha256=_text(
                provenance_doc["raw_config_sha256"], "provenance.raw_config_sha256"
            ),
            environment=Environment(_text(provenance_doc["environment"], "provenance.environment")),
            python_version=_text(provenance_doc["python_version"], "provenance.python_version"),
            platform=_text(provenance_doc["platform"], "provenance.platform"),
            machine_label=_optional_text(
                provenance_doc["machine_label"], "provenance.machine_label"
            ),
            parents=tuple(_text(parent, "provenance.parents") for parent in parents),
        )
    except ValueError:
        raise ManifestError("manifest provenance is invalid") from None

    policy_doc = _closed(
        top["policy_at_capture"],
        {"retention_class", "backup_policy_id", "backup_status_at_finalization"},
        "policy_at_capture",
    )
    try:
        retention_class = _optional_text(policy_doc["retention_class"], "policy.retention_class")
        backup_policy_id = _optional_text(policy_doc["backup_policy_id"], "policy.backup_policy_id")
        if retention_class is not None:
            validate_identifier(retention_class, "retention_class")
        if backup_policy_id is not None:
            validate_identifier(backup_policy_id, "backup_policy_id")
        policy = CapturePolicy(
            retention_class=retention_class,
            backup_policy_id=backup_policy_id,
            backup_status_at_finalization=BackupStatus(
                _text(policy_doc["backup_status_at_finalization"], "policy.backup_status")
            ),
        )
    except ValueError:
        raise ManifestError("manifest policy_at_capture is invalid") from None

    expected_prefix = f"raw/v1/{source.source_id}/{source.feed_id}/"
    if not relative_path.startswith(expected_prefix) or f"/{capture_id}/" not in relative_path:
        raise ManifestError("manifest object.relative_path does not match its capture")
    return RawManifest(
        capture_id=capture_id,
        source=source,
        raw_object=raw_object,
        times=times,
        observations=observations,
        provenance=provenance,
        policy=policy,
    )


def expected_relative_path(source: SourceIdentity, capture_id: str) -> str:
    """Return the root-relative path of a capture's raw object (UTC start-date hierarchy)."""
    validate_capture_id(capture_id)
    year, month, day = capture_id[0:4], capture_id[4:6], capture_id[6:8]
    return (
        f"raw/v1/{source.source_id}/{source.feed_id}/{year}/{month}/{day}/{capture_id}/"
        f"{OBJECT_NAME}"
    )


def _manifest_document(manifest: RawManifest) -> dict[str, object]:
    source, obj, times = manifest.source, manifest.raw_object, manifest.times
    observations, provenance, policy = manifest.observations, manifest.provenance, manifest.policy
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "capture_id": manifest.capture_id,
        "status": "finalized",
        "source": {
            "source_id": source.source_id,
            "feed_id": source.feed_id,
            "transport": source.transport.value,
            "endpoint_id": source.endpoint_id,
        },
        "object": {
            "relative_path": obj.relative_path,
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "encoding": "binary",
            "compression": "none",
            "size_bytes": obj.size_bytes,
            "sha256": obj.sha256,
            "record_count": obj.record_count,
        },
        "time": {
            "capture_started_at": times.capture_started_at,
            "capture_ended_at": times.capture_ended_at,
            "first_received_at": times.first_received_at,
            "last_received_at": times.last_received_at,
            "first_source_timestamp": times.first_source_timestamp,
            "last_source_timestamp": times.last_source_timestamp,
            "finalized_at": times.finalized_at,
            "monotonic_duration_ns": times.monotonic_duration_ns,
        },
        "observations": {
            "payload_count": observations.payload_count,
            "event_count": observations.event_count,
            "malformed_message_count": observations.malformed_message_count,
            "reconnect_count": observations.reconnect_count,
            "gap_event_count": observations.gap_event_count,
            "rate_limit_event_count": observations.rate_limit_event_count,
            "source_clock_regression_count": observations.source_clock_regression_count,
            "local_clock_regression_count": observations.local_clock_regression_count,
        },
        "provenance": {
            "software": "pmv",
            "code_commit": provenance.code_commit,
            "code_tree_dirty": provenance.code_tree_dirty,
            "config_source_sha256": provenance.config_source_sha256,
            "raw_config_sha256": provenance.raw_config_sha256,
            "environment": provenance.environment.value,
            "python_version": provenance.python_version,
            "platform": provenance.platform,
            "machine_label": provenance.machine_label,
            "parents": list(provenance.parents),
        },
        "policy_at_capture": {
            "retention_class": policy.retention_class,
            "backup_policy_id": policy.backup_policy_id,
            "backup_status_at_finalization": policy.backup_status_at_finalization.value,
        },
    }


def _closed(value: object, keys: set[str], where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ManifestError(f"manifest {where} must be an object")
    if set(value) != keys:
        raise ManifestError(f"manifest {where} fields do not match the v1 schema")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"manifest {where} must be a string")
    _reject_secret_text(value, where)
    return value


def _optional_text(value: object, where: str) -> str | None:
    return None if value is None else _text(value, where)


def _timestamp(value: object, where: str) -> str:
    if not is_timestamp(value) or not isinstance(value, str):
        raise ManifestError(f"manifest {where} is not a canonical UTC timestamp")
    return value


def _optional_timestamp(value: object, where: str) -> str | None:
    return None if value is None else _timestamp(value, where)


def _count(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManifestError(f"manifest {where} must be a non-negative integer")
    return value


def _digest(value: object, where: str) -> str:
    if not isinstance(value, str) or not is_sha256(value):
        raise ManifestError(f"manifest {where} must be a SHA-256 hex digest")
    return value


def _check_pattern(value: object, pattern: re.Pattern[str], what: str) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{what} has an invalid format")


def _reject_secret_text(value: str, where: str) -> None:
    # Defense in depth only: every field already has a strict format.
    if redact_text(value) != value:
        raise ValueError(f"{where} looks like it contains secret material")


def manifest_keys() -> Sequence[str]:
    """Top-level manifest keys, for documentation and schema consistency tests."""
    return (
        "capture_id",
        "object",
        "observations",
        "policy_at_capture",
        "provenance",
        "schema",
        "schema_version",
        "source",
        "status",
        "time",
    )
