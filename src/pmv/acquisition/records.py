"""Acquisition approval, licence, manifest, and source-quality records (A-1, A-2, A-5, A-6).

Every record is parsed from a strict JSON document (``strict_parse.parse_json``), with
exact key sets: an unknown or missing key fails. Values are validated and never coerced.
``unknown`` is treated as ``no`` wherever a permission or a property is required. The
agents propose these records, and the owner decision records they cite are the
authority. ``acquisition_gate_failures`` lists every unmet condition. Acquisition may
proceed only when it returns an empty list and every other gate condition (A-3, A-4, A-7)
is recorded.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from pmv.acquisition.formats import FileFormat
from pmv.acquisition.hosts import HostPolicyError, UrlAllowlist
from pmv.acquisition.strict_parse import StrictParseError, parse_decimal_field
from pmv.integrity import is_identifier, is_sha256, is_timestamp

_DECISION_PATH: Final = re.compile(r"docs/decisions/[A-Za-z0-9._/-]{1,200}\.md")
_GIT_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_FILE_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}")
_CURRENCY: Final = re.compile(r"[A-Z]{3}")


class RecordError(Exception):
    """A record is malformed or fails a fail-closed rule. Messages name the field only."""


class Tri(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"

    @property
    def granted(self) -> bool:
        return self is Tri.YES


class QualityTier(StrEnum):
    Q1_AUTHORITATIVE = "Q1_authoritative"
    Q2_PRIMARY_VENDOR = "Q2_primary_vendor"
    Q3_SECONDARY = "Q3_secondary"
    Q4_UNVERIFIED = "Q4_unverified"


def _text(value: object) -> str:
    """Return ``value`` if it is text, else an empty string that no enum accepts."""
    return value if isinstance(value, str) else ""


def _exact_keys(document: Mapping[str, object], keys: frozenset[str], what: str) -> None:
    if not isinstance(document, Mapping):
        raise RecordError(f"{what} must be a JSON object")
    actual = set(document)
    if actual != keys:
        extra = sorted(actual - keys)
        missing = sorted(keys - actual)
        raise RecordError(f"{what}: unexpected keys {extra}, missing keys {missing}")


def _str(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise RecordError(f"{key} must be non-empty text")
    return value


def _ident(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not is_identifier(value):
        raise RecordError(f"{key} must be a lowercase identifier")
    return value


def _ts(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not is_timestamp(value):
        raise RecordError(f"{key} must be a canonical UTC timestamp")
    return value


def _sha(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not is_sha256(value):
        raise RecordError(f"{key} must be a lowercase SHA-256 hex digest")
    return value


def _decision(document: Mapping[str, object], key: str) -> str:
    value = document[key]
    if not isinstance(value, str) or _DECISION_PATH.fullmatch(value) is None or ".." in value:
        raise RecordError(f"{key} must cite a docs/decisions/*.md record")
    return value


def _tri(document: Mapping[str, object], key: str) -> Tri:
    value = document[key]
    try:
        return Tri(_text(value))
    except ValueError:
        raise RecordError(f"{key} must be yes, no, or unknown") from None


def _bool(document: Mapping[str, object], key: str) -> bool:
    value = document[key]
    if not isinstance(value, bool):
        raise RecordError(f"{key} must be a boolean")
    return value


def _str_list(
    document: Mapping[str, object], key: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    value = document[key]
    if not isinstance(value, list) or (not value and not allow_empty):
        raise RecordError(f"{key} must be a {'' if allow_empty else 'non-empty '}list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise RecordError(f"{key} items must be non-empty text")
    if len(set(value)) != len(value):
        raise RecordError(f"{key} has duplicate items")
    return tuple(value)


# --- A-2 licence -------------------------------------------------------------------------

_LICENCE_KEYS: Final = frozenset(
    {
        "licence_id",
        "source_id",
        "terms_url",
        "retrieved_at",
        "terms_sha256",
        "operative_terms_quoted",
        "research_use",
        "internal_model_development",
        "commercial_trading_use",
        "automated_access",
        "storage",
        "retention_after_subscription",
        "redistribution",
        "derived_data",
        "upstream_rights_established",
        "decision_record",
    }
)


@dataclass(frozen=True, slots=True)
class LicenceRecord:
    licence_id: str
    source_id: str
    terms_url: str
    retrieved_at: str
    terms_sha256: str
    operative_terms_quoted: tuple[str, ...]
    research_use: Tri
    internal_model_development: Tri
    commercial_trading_use: Tri
    automated_access: Tri
    storage: Tri
    retention_after_subscription: Tri
    redistribution: Tri
    derived_data: Tri
    upstream_rights_established: Tri
    decision_record: str

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> "LicenceRecord":
        _exact_keys(document, _LICENCE_KEYS, "licence record")
        terms_url = _str(document, "terms_url")
        if not terms_url.startswith("https://"):
            raise RecordError("terms_url must be an https URL")
        return cls(
            licence_id=_ident(document, "licence_id"),
            source_id=_ident(document, "source_id"),
            terms_url=terms_url,
            retrieved_at=_ts(document, "retrieved_at"),
            terms_sha256=_sha(document, "terms_sha256"),
            operative_terms_quoted=_str_list(document, "operative_terms_quoted"),
            research_use=_tri(document, "research_use"),
            internal_model_development=_tri(document, "internal_model_development"),
            commercial_trading_use=_tri(document, "commercial_trading_use"),
            automated_access=_tri(document, "automated_access"),
            storage=_tri(document, "storage"),
            retention_after_subscription=_tri(document, "retention_after_subscription"),
            redistribution=_tri(document, "redistribution"),
            derived_data=_tri(document, "derived_data"),
            upstream_rights_established=_tri(document, "upstream_rights_established"),
            decision_record=_decision(document, "decision_record"),
        )

    def acquisition_failures(self) -> list[str]:
        """Unmet L-ACQ conditions. ``unknown`` counts as ``no``."""
        required = {
            "research_use": self.research_use,
            "internal_model_development": self.internal_model_development,
            "automated_access": self.automated_access,
            "storage": self.storage,
            "upstream_rights_established": self.upstream_rights_established,
        }
        return [f"licence: {name} is not granted" for name, v in required.items() if not v.granted]

    def production_failures(self) -> list[str]:
        """Unmet preliminary production-use (E-B4-3) and L-PROD conditions."""
        failures = self.acquisition_failures()
        for name, value in (
            ("commercial_trading_use", self.commercial_trading_use),
            ("derived_data", self.derived_data),
        ):
            if not value.granted:
                failures.append(f"licence: {name} is not granted")
        return failures


# --- A-1 approval ------------------------------------------------------------------------

_APPROVAL_KEYS: Final = frozenset(
    {
        "approval_id",
        "source_id",
        "dataset",
        "instruments",
        "date_range_start",
        "date_range_end",
        "formats",
        "expected_size_bytes",
        "cost",
        "currency",
        "credential_required",
        "purchase_or_credential_decision",
        "url_prefixes",
        "host_class_decisions",
        "licence_id",
        "f09_settings_commit",
        "decision_record",
    }
)


@dataclass(frozen=True, slots=True)
class AcquisitionApproval:
    approval_id: str
    source_id: str
    dataset: str
    instruments: tuple[str, ...]
    date_range_start: str
    date_range_end: str
    formats: tuple[FileFormat, ...]
    expected_size_bytes: int
    cost: Decimal
    currency: str
    credential_required: bool
    purchase_or_credential_decision: str | None
    allowlist: UrlAllowlist
    licence_id: str
    f09_settings_commit: str
    decision_record: str

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> "AcquisitionApproval":
        _exact_keys(document, _APPROVAL_KEYS, "acquisition approval")
        start = _ts(document, "date_range_start")
        end = _ts(document, "date_range_end")
        if not start < end:
            raise RecordError("date_range_start must precede date_range_end")
        size = document["expected_size_bytes"]
        if type(size) is not int or size <= 0:
            raise RecordError("expected_size_bytes must be a positive integer")
        cost_text = document["cost"]
        if not isinstance(cost_text, str):
            raise RecordError("cost must be decimal text")
        try:
            cost = parse_decimal_field(cost_text)
        except StrictParseError:
            raise RecordError("cost must be a plain decimal") from None
        if cost < 0:
            raise RecordError("cost must not be negative")
        currency = _str(document, "currency")
        if _CURRENCY.fullmatch(currency) is None:
            raise RecordError("currency must be an ISO 4217 code")
        try:
            formats = tuple(FileFormat(item) for item in _str_list(document, "formats"))
        except ValueError:
            raise RecordError("formats must be allowlisted parse formats") from None
        credential = _bool(document, "credential_required")
        separate = document["purchase_or_credential_decision"]
        if cost > 0 or credential:
            separate_decision = _decision(document, "purchase_or_credential_decision")
        elif separate is None:
            separate_decision = None
        else:
            separate_decision = _decision(document, "purchase_or_credential_decision")
        decisions = document["host_class_decisions"]
        if not isinstance(decisions, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in decisions.items()
        ):
            raise RecordError("host_class_decisions must map hosts to decision records")
        for value in decisions.values():
            _decision({"host_class_decision": value}, "host_class_decision")
        # Keys are exact approved prefixes (host and path prefix), per §1.1 rules 1 and 8.
        try:
            allowlist = UrlAllowlist.build(_str_list(document, "url_prefixes"), decisions)
        except HostPolicyError as error:
            raise RecordError(f"url_prefixes: {error}") from None
        commit = document["f09_settings_commit"]
        if not isinstance(commit, str) or _GIT_COMMIT.fullmatch(commit) is None:
            raise RecordError("f09_settings_commit must be the 40-hex commit of the F-09 denies")
        return cls(
            approval_id=_ident(document, "approval_id"),
            source_id=_ident(document, "source_id"),
            dataset=_str(document, "dataset"),
            instruments=_str_list(document, "instruments"),
            date_range_start=start,
            date_range_end=end,
            formats=formats,
            expected_size_bytes=size,
            cost=cost,
            currency=currency,
            credential_required=credential,
            purchase_or_credential_decision=separate_decision,
            allowlist=allowlist,
            licence_id=_ident(document, "licence_id"),
            f09_settings_commit=commit,
            decision_record=_decision(document, "decision_record"),
        )


# --- A-5 manifest ------------------------------------------------------------------------

_FILE_KEYS: Final = frozenset({"name", "format", "size_bytes", "sha256"})
_MANIFEST_KEYS: Final = frozenset(
    {
        "manifest_version",
        "acquisition_id",
        "approval_id",
        "licence_id",
        "input_licence_ids",
        "source_url",
        "retrieved_at",
        "upstream_identity",
        "is_primary_source",
        "mirror_lineage",
        "vendor_version",
        "tool_git_commit",
        "tool_tree_dirty",
        "reproducible_from_provider",
        "files",
    }
)


@dataclass(frozen=True, slots=True)
class ManifestFile:
    name: str
    format: FileFormat
    size_bytes: int
    sha256: str

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> "ManifestFile":
        _exact_keys(document, _FILE_KEYS, "manifest file")
        name = document["name"]
        # A plain file name only: no directories, no schemes, no remote or absolute paths.
        if not isinstance(name, str) or _FILE_NAME.fullmatch(name) is None or ".." in name:
            raise RecordError("files[].name must be a plain local file name")
        try:
            file_format = FileFormat(_text(document["format"]))
        except ValueError:
            raise RecordError("files[].format must be an allowlisted parse format") from None
        size = document["size_bytes"]
        if type(size) is not int or size < 0:
            raise RecordError("files[].size_bytes must be a non-negative integer")
        return cls(name=name, format=file_format, size_bytes=size, sha256=_sha(document, "sha256"))


@dataclass(frozen=True, slots=True)
class AcquisitionManifest:
    acquisition_id: str
    approval_id: str
    licence_id: str
    input_licence_ids: tuple[str, ...]
    source_url: str
    retrieved_at: str
    upstream_identity: str
    is_primary_source: bool
    mirror_lineage: tuple[str, ...]
    vendor_version: str
    tool_git_commit: str
    reproducible_from_provider: Tri
    files: tuple[ManifestFile, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> "AcquisitionManifest":
        _exact_keys(document, _MANIFEST_KEYS, "acquisition manifest")
        if document["manifest_version"] != 1 or type(document["manifest_version"]) is not int:
            raise RecordError("manifest_version must be 1")
        licence_id = _ident(document, "licence_id")
        inputs = _str_list(document, "input_licence_ids")
        if not all(is_identifier(item) for item in inputs) or licence_id not in inputs:
            raise RecordError("input_licence_ids must list identifiers including licence_id")
        primary = _bool(document, "is_primary_source")
        lineage = _str_list(document, "mirror_lineage", allow_empty=True)
        if not primary and not lineage:
            raise RecordError("a non-primary source needs its mirror lineage to the primary")
        commit = document["tool_git_commit"]
        if not isinstance(commit, str) or _GIT_COMMIT.fullmatch(commit) is None:
            raise RecordError("tool_git_commit must be a 40-hex commit")
        if _bool(document, "tool_tree_dirty"):
            raise RecordError("the acquisition tool must run from a clean, committed tree")
        raw_files = document["files"]
        if not isinstance(raw_files, list) or not raw_files:
            raise RecordError("files must be a non-empty list")
        files = tuple(ManifestFile.from_document(item) for item in raw_files)
        names = [item.name.casefold() for item in files]
        if len(set(names)) != len(names):
            raise RecordError("files have duplicate names")
        source_url = _str(document, "source_url")
        if not source_url.startswith("https://"):
            raise RecordError("source_url must be an https URL")
        return cls(
            acquisition_id=_ident(document, "acquisition_id"),
            approval_id=_ident(document, "approval_id"),
            licence_id=licence_id,
            input_licence_ids=inputs,
            source_url=source_url,
            retrieved_at=_ts(document, "retrieved_at"),
            upstream_identity=_str(document, "upstream_identity"),
            is_primary_source=primary,
            mirror_lineage=lineage,
            vendor_version=_str(document, "vendor_version"),
            tool_git_commit=commit,
            reproducible_from_provider=_tri(document, "reproducible_from_provider"),
            files=files,
        )

    @property
    def reproducible(self) -> bool:
        """``unknown`` is treated as ``no`` (A-3)."""
        return self.reproducible_from_provider.granted

    def file(self, name: str) -> ManifestFile:
        for item in self.files:
            if item.name == name:
                return item
        raise RecordError("file is not in the acquisition manifest")


# --- A-6 source quality ------------------------------------------------------------------

_QUALITY_KEYS: Final = frozenset(
    {
        "source_id",
        "quality_tier",
        "upstream_group_id",
        "reconciliation_primary_source_id",
        "reconciliation_plan",
        "assigned_at",
        "decision_record",
    }
)


@dataclass(frozen=True, slots=True)
class SourceQuality:
    source_id: str
    quality_tier: QualityTier
    upstream_group_id: str
    reconciliation_primary_source_id: str | None
    reconciliation_plan: str
    assigned_at: str
    decision_record: str

    @classmethod
    def from_document(cls, document: Mapping[str, object]) -> "SourceQuality":
        _exact_keys(document, _QUALITY_KEYS, "source-quality entry")
        try:
            tier = QualityTier(_text(document["quality_tier"]))
        except ValueError:
            raise RecordError("quality_tier must be one of Q1..Q4") from None
        primary = document["reconciliation_primary_source_id"]
        if primary is not None and not is_identifier(primary):
            raise RecordError("reconciliation_primary_source_id must be an identifier or null")
        source_id = _ident(document, "source_id")
        if tier is not QualityTier.Q1_AUTHORITATIVE and (primary is None or primary == source_id):
            raise RecordError(
                "a non-Q1 source needs a different primary source to reconcile against"
            )
        return cls(
            source_id=source_id,
            quality_tier=tier,
            upstream_group_id=_ident(document, "upstream_group_id"),
            reconciliation_primary_source_id=primary,
            reconciliation_plan=_str(document, "reconciliation_plan"),
            assigned_at=_ts(document, "assigned_at"),
            decision_record=_decision(document, "decision_record"),
        )

    @property
    def usable_for_development(self) -> bool:
        return self.quality_tier is not QualityTier.Q4_UNVERIFIED


def independent_cross_checks(entries: Sequence[SourceQuality]) -> int:
    """Number of independent sources: copies of one upstream count once (RT-B3-14)."""
    return len({entry.upstream_group_id for entry in entries})


# --- gate --------------------------------------------------------------------------------


def manifest_gate_failures(
    manifest: AcquisitionManifest, approval: AcquisitionApproval
) -> list[str]:
    """Every disagreement between an acquisition manifest and its approval (A-1, A-5)."""
    failures: list[str] = []
    if manifest.approval_id != approval.approval_id:
        failures.append("A-5: manifest cites a different approval")
    if manifest.licence_id != approval.licence_id:
        failures.append("A-5: manifest cites a different licence than the approval")
    try:
        approval.allowlist.check(manifest.source_url)
    except HostPolicyError:
        failures.append("A-1: manifest source_url is outside the approved hosts and prefixes")
    if any(item.format not in approval.formats for item in manifest.files):
        failures.append("A-1: manifest contains a format the approval does not list")
    total = sum(item.size_bytes for item in manifest.files)
    if total > approval.expected_size_bytes:
        failures.append("A-1: manifest exceeds the approved expected size")
    return failures


def acquisition_gate_failures(
    approval: AcquisitionApproval | None,
    licence: LicenceRecord | None,
    quality: SourceQuality | None,
    *,
    backup_restore_test_passed: bool,
    safe_parsing_review_passed: bool,
) -> list[str]:
    """Every unmet pre-acquisition condition for one source. Empty means no failure found.

    The two boolean inputs must come from recorded evidence (the A-3 restore-test record
    and the A-4 review record); this function does not verify them, nor that cited
    decision records exist. An empty result is necessary, never sufficient.
    """
    failures: list[str] = []
    if approval is None:
        failures.append("A-1: no owner acquisition approval")
    if licence is None:
        failures.append("A-2: no licence determination")
    else:
        failures.extend(f"A-2: {item}" for item in licence.acquisition_failures())
    if not backup_restore_test_passed:
        failures.append("A-3: no passing synthetic backup and restore test")
    if not safe_parsing_review_passed:
        failures.append("A-4: safe-parsing tool review has not passed")
    if quality is None:
        failures.append("A-6: no source-quality entry")
    elif not quality.usable_for_development:
        failures.append("A-6: Q4_unverified sources are not acquired for development")
    if approval is not None and licence is not None:
        if approval.licence_id != licence.licence_id:
            failures.append("A-1/A-2: approval cites a different licence")
        if approval.source_id != licence.source_id:
            failures.append("A-1/A-2: approval and licence name different sources")
    if approval is not None and quality is not None and approval.source_id != quality.source_id:
        failures.append("A-1/A-6: approval and source-quality entry name different sources")
    return failures
