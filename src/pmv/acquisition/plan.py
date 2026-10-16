"""Acquisition plan and pre-acquisition evidence records (G-6; A-1, A-3, A-4, A-5).

These are owner-controlled inputs. The pipeline parses them strictly (exact key sets, no
coercion) and validates them before any transport starts:

- ``AcquisitionPlan``: one acquisition. It names the approval, source, and every file:
  URL, kind (single file or archive), format, compression, expected schema, size cap,
  and, where the provider publishes them, expected size and SHA-256. An archive lists its
  expected members, each with a format and schema. A-5 provenance fields (upstream
  identity, mirror lineage, vendor version, reproducibility) come from the plan.
- ``BackupPolicyRecord`` (A-3): the owner's backup policy identifier and whether it is
  synthetic. The real policy is an open owner input; no real record exists.
- ``RestoreTestRecord`` (A-3): a passing restore test for one artifact type and size class
  under that policy.
- ``A4ReviewRecord`` (A-4): the safe-parsing review that covers the acquisition code, the
  commit it reviewed, and its verdict.

Identifiers that begin with ``synthetic_`` mark synthetic records. The pipeline accepts
synthetic records only in synthetic mode, and refuses them in real mode.

**Size class (development interpretation).** A-3 asks for a restore test "on a synthetic
file of the same format and size class". This module reads "size class" as the number of
decimal digits of the byte count, and a test covers a planned file when its artifact type
matches and its size class is at least that of the file's size cap. This is a proposed
reading for owner confirmation, not an approved definition.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pmv.acquisition.archive import ArchiveRefusedError, safe_member_name
from pmv.acquisition.formats import EXTENSIONS, FileFormat, extension_of
from pmv.acquisition.isolation import FileSpec
from pmv.acquisition.readers import Compression, RecordSchema, SpecError, check_name
from pmv.acquisition.records import RecordError, Tri
from pmv.integrity import canonical_json, is_identifier, is_sha256, is_timestamp, sha256_hex

PLAN_VERSION: Final = 1
SYNTHETIC_PREFIX: Final = "synthetic_"
_FILE_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}")
_DECISION_PATH: Final = re.compile(r"docs/decisions/[A-Za-z0-9._/-]{1,200}\.md")
_REVIEW_PATH: Final = re.compile(r"research/governance/[A-Za-z0-9._/-]{1,200}\.md")
_GIT_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
ARCHIVE_SUFFIXES: Final = {
    ".tar.gz": "tar.gz",
    ".tar.bz2": "tar.bz2",
    ".tar.xz": "tar.xz",
    ".tar": "tar",
    ".zip": "zip",
}
MAX_FILES: Final = 1000
MAX_MEMBERS: Final = 1000


class FileKind(StrEnum):
    FILE = "file"
    ARCHIVE = "archive"


def is_synthetic(identifier: str) -> bool:
    return identifier.startswith(SYNTHETIC_PREFIX)


def size_class(size_bytes: int) -> int:
    """The number of decimal digits of a byte count (see the module docstring)."""
    return len(str(max(size_bytes, 0)))


def _exact(document: object, keys: frozenset[str], what: str) -> Mapping[str, object]:
    if not isinstance(document, Mapping):
        raise RecordError(f"{what} must be a JSON object")
    if set(document) != keys:
        extra = sorted(set(document) - keys)
        missing = sorted(keys - set(document))
        raise RecordError(f"{what}: unexpected keys {extra}, missing keys {missing}")
    return document


def _ident(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not is_identifier(value):
        raise RecordError(f"{key} must be a lowercase identifier")
    return value


def _text(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise RecordError(f"{key} must be non-empty text")
    return value


def _bool(document: Mapping[str, object], key: str) -> bool:
    value = document[key]
    if not isinstance(value, bool):
        raise RecordError(f"{key} must be a boolean")
    return value


def _decision(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str) or _DECISION_PATH.fullmatch(value) is None or ".." in value:
        raise RecordError(f"{key} must cite a docs/decisions/*.md record")
    return value


def _positive(document: Mapping[str, object], key: str) -> int:
    value = document[key]
    if type(value) is not int or value <= 0:
        raise RecordError(f"{key} must be a positive integer")
    return value


def _sha_or_null(document: Mapping[str, object], key: str) -> str | None:
    value = document[key]
    if value is not None and not is_sha256(value):
        raise RecordError(f"{key} must be a lowercase SHA-256 or null")
    return value


# --- plan ---------------------------------------------------------------------------------

_PLAN_KEYS: Final = frozenset(
    {
        "plan_version",
        "acquisition_id",
        "approval_id",
        "source_id",
        "upstream_identity",
        "is_primary_source",
        "mirror_lineage",
        "vendor_version",
        "reproducible_from_provider",
        "max_attempts",
        "files",
        "decision_record",
    }
)
_FILE_KEYS: Final = frozenset(
    {
        "name",
        "url",
        "kind",
        "format",
        "compression",
        "schema",
        "members",
        "max_bytes",
        "expected_size_bytes",
        "provider_sha256",
    }
)
_MEMBER_KEYS: Final = frozenset({"name", "format", "schema"})


@dataclass(frozen=True, slots=True)
class PlannedMember:
    name: str
    file_format: FileFormat
    schema: RecordSchema

    def spec(self) -> FileSpec:
        return FileSpec(
            name=self.name.rsplit("/", 1)[-1],
            file_format=self.file_format,
            compression=Compression.NONE,
            schema=self.schema,
        )


@dataclass(frozen=True, slots=True)
class PlannedFile:
    name: str
    url: str
    kind: FileKind
    file_format: FileFormat | None
    compression: Compression
    schema: RecordSchema | None
    members: tuple[PlannedMember, ...]
    max_bytes: int
    expected_size_bytes: int | None
    provider_sha256: str | None

    @property
    def archive_kind(self) -> str | None:
        if self.kind is not FileKind.ARCHIVE:
            return None
        lowered = self.name.lower()
        for suffix, kind in ARCHIVE_SUFFIXES.items():
            if lowered.endswith(suffix):
                return kind
        return None

    @property
    def artifact_type(self) -> str:
        """What a restore test must match: ``csv``, ``csv+gzip``, ``tar.gz``, and so on."""
        if self.kind is FileKind.ARCHIVE:
            return str(self.archive_kind)
        assert self.file_format is not None  # noqa: S101 - set for every single file
        if self.compression is Compression.NONE:
            return self.file_format.value
        return f"{self.file_format.value}+{self.compression.value}"

    def formats(self) -> frozenset[FileFormat]:
        if self.kind is FileKind.ARCHIVE:
            return frozenset(member.file_format for member in self.members)
        assert self.file_format is not None  # noqa: S101 - set for every single file
        return frozenset({self.file_format})

    def spec(self) -> FileSpec:
        assert self.file_format is not None  # noqa: S101 - set for every single file
        assert self.schema is not None  # noqa: S101 - set for every single file
        return FileSpec(
            name=self.name,
            file_format=self.file_format,
            compression=self.compression,
            schema=self.schema,
        )

    @classmethod
    def from_document(cls, document: object) -> "PlannedFile":
        item = _exact(document, _FILE_KEYS, "plan file")
        name = item["name"]
        if not isinstance(name, str) or _FILE_NAME.fullmatch(name) is None or ".." in name:
            raise RecordError("files[].name must be a plain local file name")
        url = _text(item, "url")
        if not url.startswith("https://"):
            raise RecordError("files[].url must be an https URL")
        try:
            kind = FileKind(item["kind"] if isinstance(item["kind"], str) else "")
        except ValueError:
            raise RecordError("files[].kind must be 'file' or 'archive'") from None
        max_bytes = _positive(item, "max_bytes")
        expected = item["expected_size_bytes"]
        if expected is not None and (type(expected) is not int or not 0 <= expected <= max_bytes):
            raise RecordError("files[].expected_size_bytes must be null or within max_bytes")
        provider = _sha_or_null(item, "provider_sha256")
        if kind is FileKind.FILE:
            return cls._single(item, name, url, max_bytes, expected, provider)
        return cls._archive(item, name, url, max_bytes, expected, provider)

    @classmethod
    def _single(
        cls,
        item: Mapping[str, object],
        name: str,
        url: str,
        max_bytes: int,
        expected: int | None,
        provider: str | None,
    ) -> "PlannedFile":
        if item["members"] != []:
            raise RecordError("a single file has no members")
        try:
            file_format = FileFormat(item["format"] if isinstance(item["format"], str) else "")
            raw = item["compression"]
            compression = Compression(raw if isinstance(raw, str) else "")
            check_name(name, file_format, compression)
            schema = RecordSchema.from_document(file_format, item["schema"])
        except (ValueError, SpecError) as error:
            raise RecordError(f"files[]: {error}") from None
        return cls(
            name,
            url,
            FileKind.FILE,
            file_format,
            compression,
            schema,
            (),
            max_bytes,
            expected,
            provider,
        )

    @classmethod
    def _archive(
        cls,
        item: Mapping[str, object],
        name: str,
        url: str,
        max_bytes: int,
        expected: int | None,
        provider: str | None,
    ) -> "PlannedFile":
        if item["format"] is not None or item["schema"] is not None:
            raise RecordError("an archive has no format or schema of its own")
        if item["compression"] != Compression.NONE.value:
            raise RecordError("an archive's compression is given by its name")
        if not any(name.lower().endswith(suffix) for suffix in ARCHIVE_SUFFIXES):
            raise RecordError(
                "an archive name must end in .tar, .tar.gz, .tar.bz2, .tar.xz, or .zip"
            )
        raw_members = item["members"]
        if not isinstance(raw_members, list) or not raw_members or len(raw_members) > MAX_MEMBERS:
            raise RecordError("an archive lists between 1 and 1000 expected members")
        members: list[PlannedMember] = []
        for raw in raw_members:
            member = _exact(raw, _MEMBER_KEYS, "archive member")
            member_name = member["name"]
            try:
                normalized = safe_member_name(
                    member_name if isinstance(member_name, str) else "", is_dir=False, max_depth=8
                )
                fmt = FileFormat(member["format"] if isinstance(member["format"], str) else "")
                if normalized != member_name or extension_of(normalized) not in EXTENSIONS[fmt]:
                    raise SpecError("member name does not match its format")
                schema = RecordSchema.from_document(fmt, member["schema"])
            except (ArchiveRefusedError, ValueError, SpecError) as error:
                raise RecordError(f"archive member: {error}") from None
            members.append(PlannedMember(normalized, fmt, schema))
        folded = [member.name.casefold() for member in members]
        if len(set(folded)) != len(folded):
            raise RecordError("archive members must be unique ignoring case")
        return cls(
            name,
            url,
            FileKind.ARCHIVE,
            None,
            Compression.NONE,
            None,
            tuple(members),
            max_bytes,
            expected,
            provider,
        )


@dataclass(frozen=True, slots=True)
class AcquisitionPlan:
    acquisition_id: str
    approval_id: str
    source_id: str
    upstream_identity: str
    is_primary_source: bool
    mirror_lineage: tuple[str, ...]
    vendor_version: str
    reproducible_from_provider: Tri
    max_attempts: int
    files: tuple[PlannedFile, ...]
    decision_record: str

    @classmethod
    def from_document(cls, document: object) -> "AcquisitionPlan":
        plan = _exact(document, _PLAN_KEYS, "acquisition plan")
        if type(plan["plan_version"]) is not int or plan["plan_version"] != PLAN_VERSION:
            raise RecordError("plan_version must be 1")
        attempts = _positive(plan, "max_attempts")
        if attempts > 10:
            raise RecordError("max_attempts must be at most 10")
        lineage = plan["mirror_lineage"]
        if not isinstance(lineage, list) or not all(
            isinstance(item, str) and item.strip() for item in lineage
        ):
            raise RecordError("mirror_lineage must be a list of text")
        primary = _bool(plan, "is_primary_source")
        if not primary and not lineage:
            raise RecordError("a non-primary source needs its mirror lineage to the primary")
        raw = plan["reproducible_from_provider"]
        try:
            reproducible = Tri(raw if isinstance(raw, str) else "")
        except ValueError:
            raise RecordError("reproducible_from_provider must be yes, no, or unknown") from None
        raw_files = plan["files"]
        if not isinstance(raw_files, list) or not raw_files or len(raw_files) > MAX_FILES:
            raise RecordError("files must list between 1 and 1000 files")
        files = tuple(PlannedFile.from_document(item) for item in raw_files)
        folded = [item.name.casefold() for item in files]
        if len(set(folded)) != len(folded):
            raise RecordError("planned file names must be unique ignoring case")
        return cls(
            acquisition_id=_ident(plan, "acquisition_id"),
            approval_id=_ident(plan, "approval_id"),
            source_id=_ident(plan, "source_id"),
            upstream_identity=_text(plan, "upstream_identity"),
            is_primary_source=primary,
            mirror_lineage=tuple(lineage),
            vendor_version=_text(plan, "vendor_version"),
            reproducible_from_provider=reproducible,
            max_attempts=attempts,
            files=files,
            decision_record=_decision(plan, "decision_record"),
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.files)

    def file(self, name: str) -> PlannedFile:
        for item in self.files:
            if item.name == name:
                return item
        raise RecordError("file is not in the plan")


# --- A-3 ----------------------------------------------------------------------------------

_POLICY_KEYS: Final = frozenset({"policy_id", "synthetic", "backup_target_id", "decision_record"})
_RESTORE_KEYS: Final = frozenset(
    {
        "test_id",
        "policy_id",
        "artifact_type",
        "size_class",
        "fixture_sha256",
        "restored_sha256",
        "passed",
        "tested_at",
        "decision_record",
    }
)


@dataclass(frozen=True, slots=True)
class BackupPolicyRecord:
    policy_id: str
    synthetic: bool
    backup_target_id: str
    decision_record: str

    @classmethod
    def from_document(cls, document: object) -> "BackupPolicyRecord":
        record = _exact(document, _POLICY_KEYS, "backup policy")
        policy_id = _ident(record, "policy_id")
        synthetic = _bool(record, "synthetic")
        if synthetic != is_synthetic(policy_id):
            raise RecordError("a synthetic policy, and only one, has a synthetic_ identifier")
        return cls(
            policy_id=policy_id,
            synthetic=synthetic,
            backup_target_id=_ident(record, "backup_target_id"),
            decision_record=_decision(record, "decision_record"),
        )


@dataclass(frozen=True, slots=True)
class RestoreTestRecord:
    test_id: str
    policy_id: str
    artifact_type: str
    size_class: int
    passed: bool
    decision_record: str

    @classmethod
    def from_document(cls, document: object) -> "RestoreTestRecord":
        record = _exact(document, _RESTORE_KEYS, "restore test")
        artifact = _text(record, "artifact_type")
        size = _positive(record, "size_class")
        fixture, restored = record["fixture_sha256"], record["restored_sha256"]
        if not is_sha256(fixture) or not is_sha256(restored):
            raise RecordError("restore-test hashes must be lowercase SHA-256")
        if not is_timestamp(record["tested_at"]):
            raise RecordError("tested_at must be a canonical UTC timestamp")
        passed = _bool(record, "passed") and fixture == restored
        return cls(
            test_id=_ident(record, "test_id"),
            policy_id=_ident(record, "policy_id"),
            artifact_type=artifact,
            size_class=size,
            passed=passed,
            decision_record=_decision(record, "decision_record"),
        )

    def covers(self, planned: PlannedFile, policy_id: str) -> bool:
        return (
            self.passed
            and self.policy_id == policy_id
            and self.artifact_type == planned.artifact_type
            and self.size_class >= size_class(planned.max_bytes)
        )


# --- A-4 ----------------------------------------------------------------------------------

_REVIEW_KEYS: Final = frozenset(
    {
        "review_path",
        "reviewed_commit",
        "no_blocking_findings",
        "no_major_findings",
        "a4_satisfied",
        "decision_record",
    }
)


@dataclass(frozen=True, slots=True)
class A4ReviewRecord:
    review_path: str
    reviewed_commit: str
    no_blocking_findings: bool
    no_major_findings: bool
    a4_satisfied: bool
    decision_record: str

    @classmethod
    def from_document(cls, document: object) -> "A4ReviewRecord":
        record = _exact(document, _REVIEW_KEYS, "A-4 review record")
        path = record["review_path"]
        if not isinstance(path, str) or _REVIEW_PATH.fullmatch(path) is None or ".." in path:
            raise RecordError("review_path must cite a research/governance/*.md review")
        commit = record["reviewed_commit"]
        if not isinstance(commit, str) or _GIT_COMMIT.fullmatch(commit) is None:
            raise RecordError("reviewed_commit must be a 40-hex commit")
        return cls(
            review_path=path,
            reviewed_commit=commit,
            no_blocking_findings=_bool(record, "no_blocking_findings"),
            no_major_findings=_bool(record, "no_major_findings"),
            a4_satisfied=_bool(record, "a4_satisfied"),
            decision_record=_decision(record, "decision_record"),
        )


# --- the authorizing bundle ---------------------------------------------------------------

BUNDLE_KEYS: Final = (
    "plan",
    "approval",
    "licence",
    "quality",
    "backup_policy",
    "restore_tests",
    "a4_review",
)


def bundle_sha256(documents: Mapping[str, object]) -> str:
    """SHA-256 of the canonical bundle of every authorizing document (journal binding)."""
    if set(documents) != set(BUNDLE_KEYS):
        raise RecordError("the authorizing bundle has the wrong keys")
    return sha256_hex(canonical_json({key: documents[key] for key in BUNDLE_KEYS}))


def document_sha256(document: object) -> str:
    return sha256_hex(canonical_json({"document": document}))


def restore_tests_cover(
    files: Sequence[PlannedFile], tests: Sequence[RestoreTestRecord], policy_id: str
) -> list[str]:
    """Planned files with no covering passing restore test under ``policy_id``."""
    return [item.name for item in files if not any(test.covers(item, policy_id) for test in tests)]
