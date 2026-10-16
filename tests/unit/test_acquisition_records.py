"""A-1, A-2, A-5, A-6 records. All identifiers, hosts, and decisions are hypothetical."""

import copy
from typing import Any

import pytest

from pmv.acquisition.records import (
    AcquisitionApproval,
    AcquisitionManifest,
    LicenceRecord,
    QualityTier,
    RecordError,
    SourceQuality,
    acquisition_gate_failures,
    independent_cross_checks,
    manifest_gate_failures,
)

DECISION = "docs/decisions/2099-01-01_hypothetical.md"
TS = "2099-01-01T00:00:00.000000Z"
TS_LATER = "2099-02-01T00:00:00.000000Z"


def licence_doc(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "licence_id": "lic_example",
        "source_id": "src_example",
        "terms_url": "https://docs.example.com/terms",
        "retrieved_at": TS,
        "terms_sha256": "a" * 64,
        "operative_terms_quoted": ["Licensee may download the files for research."],
        "research_use": "yes",
        "internal_model_development": "yes",
        "commercial_trading_use": "unknown",
        "automated_access": "yes",
        "storage": "yes",
        "retention_after_subscription": "unknown",
        "redistribution": "no",
        "derived_data": "unknown",
        "upstream_rights_established": "yes",
        "decision_record": DECISION,
    }
    document.update(overrides)
    return document


def approval_doc(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "approval_id": "appr_example",
        "source_id": "src_example",
        "dataset": "Synthetic example dataset",
        "instruments": ["EXAMPLE-1"],
        "date_range_start": TS,
        "date_range_end": TS_LATER,
        "formats": ["csv"],
        "expected_size_bytes": 1000,
        "cost": "0",
        "currency": "USD",
        "credential_required": False,
        "purchase_or_credential_decision": None,
        "url_prefixes": ["https://files.example.com/history/"],
        "host_class_decisions": {"https://files.example.com/history/": DECISION},
        "licence_id": "lic_example",
        "f09_settings_commit": "b" * 40,
        "decision_record": DECISION,
    }
    document.update(overrides)
    return document


def manifest_doc(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "manifest_version": 1,
        "acquisition_id": "acq_example",
        "approval_id": "appr_example",
        "licence_id": "lic_example",
        "input_licence_ids": ["lic_example"],
        "source_url": "https://files.example.com/history/a.csv",
        "retrieved_at": TS,
        "upstream_identity": "Example exchange of record",
        "is_primary_source": True,
        "mirror_lineage": [],
        "vendor_version": "v1",
        "tool_git_commit": "c" * 40,
        "tool_tree_dirty": False,
        "reproducible_from_provider": "unknown",
        "files": [{"name": "a.csv", "format": "csv", "size_bytes": 4, "sha256": "d" * 64}],
    }
    document.update(overrides)
    return document


def quality_doc(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "source_id": "src_example",
        "quality_tier": "Q2_primary_vendor",
        "upstream_group_id": "grp_example",
        "reconciliation_primary_source_id": "src_primary",
        "reconciliation_plan": "Preregistered sample reconciliation against the primary.",
        "assigned_at": TS,
        "decision_record": DECISION,
    }
    document.update(overrides)
    return document


def test_valid_records_parse() -> None:
    licence = LicenceRecord.from_document(licence_doc())
    approval = AcquisitionApproval.from_document(approval_doc())
    manifest = AcquisitionManifest.from_document(manifest_doc())
    quality = SourceQuality.from_document(quality_doc())
    assert licence.acquisition_failures() == []
    assert approval.allowlist.check("https://files.example.com/history/a.csv")
    assert manifest.file("a.csv").size_bytes == 4
    assert quality.usable_for_development
    failures = acquisition_gate_failures(
        approval, licence, quality, backup_restore_test_passed=True, safe_parsing_review_passed=True
    )
    assert failures == []


@pytest.mark.parametrize("build", [LicenceRecord.from_document, AcquisitionApproval.from_document])
def test_unknown_and_missing_keys_fail(build: Any) -> None:
    document = licence_doc() if build is LicenceRecord.from_document else approval_doc()
    extra = copy.deepcopy(document)
    extra["surprise"] = 1
    with pytest.raises(RecordError, match="unexpected keys"):
        build(extra)
    missing = copy.deepcopy(document)
    missing.pop("decision_record")
    with pytest.raises(RecordError, match="missing keys"):
        build(missing)


@pytest.mark.parametrize(
    "field", ["research_use", "automated_access", "storage", "upstream_rights_established"]
)
def test_unknown_licence_terms_count_as_no(field: str) -> None:
    licence = LicenceRecord.from_document(licence_doc(**{field: "unknown"}))
    assert f"licence: {field} is not granted" in licence.acquisition_failures()


def test_production_use_needs_commercial_and_derived_rights() -> None:
    licence = LicenceRecord.from_document(licence_doc())
    assert "licence: commercial_trading_use is not granted" in licence.production_failures()
    granted = LicenceRecord.from_document(
        licence_doc(commercial_trading_use="yes", derived_data="yes")
    )
    assert granted.production_failures() == []


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"terms_url": "http://docs.example.com/terms"}, "https"),
        ({"terms_sha256": "A" * 64}, "SHA-256"),
        ({"operative_terms_quoted": []}, "non-empty list"),
        ({"research_use": True}, "yes, no, or unknown"),
        ({"decision_record": "../outside.md"}, "docs/decisions"),
        ({"retrieved_at": "2099-01-01"}, "timestamp"),
    ],
)
def test_licence_field_validation(overrides: dict[str, Any], match: str) -> None:
    with pytest.raises(RecordError, match=match):
        LicenceRecord.from_document(licence_doc(**overrides))


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"cost": "10.00"}, "docs/decisions"),
        ({"credential_required": True}, "docs/decisions"),
        ({"cost": "-1"}, "negative"),
        ({"cost": "NaN"}, "plain decimal"),
        ({"cost": 1}, "decimal text"),
        ({"currency": "usd"}, "ISO 4217"),
        ({"f09_settings_commit": "pending"}, "F-09"),
        ({"date_range_end": TS}, "precede"),
        ({"expected_size_bytes": 0}, "positive"),
        ({"expected_size_bytes": True}, "positive"),
        ({"formats": ["pickle"]}, "allowlisted"),
        ({"url_prefixes": ["https://api.example.com/history/"]}, "host-class decision"),
        ({"url_prefixes": ["http://files.example.com/history/"]}, "url_prefixes"),
    ],
)
def test_approval_fail_closed_rules(overrides: dict[str, Any], match: str) -> None:
    with pytest.raises(RecordError, match=match):
        AcquisitionApproval.from_document(approval_doc(**overrides))


def test_paid_approval_with_separate_decision_parses() -> None:
    approval = AcquisitionApproval.from_document(
        approval_doc(cost="10.00", purchase_or_credential_decision=DECISION)
    )
    assert str(approval.cost) == "10.00"


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"tool_tree_dirty": True}, "clean, committed tree"),
        ({"is_primary_source": False}, "mirror lineage"),
        ({"input_licence_ids": ["lic_other"]}, "including licence_id"),
        ({"manifest_version": 2}, "manifest_version"),
        ({"manifest_version": True}, "manifest_version"),
        ({"files": []}, "non-empty"),
        ({"source_url": "s3://bucket/a.csv"}, "https"),
        (
            {
                "files": [
                    {"name": "a.csv", "format": "csv", "size_bytes": 1, "sha256": "d" * 64},
                    {"name": "A.CSV", "format": "csv", "size_bytes": 1, "sha256": "d" * 64},
                ]
            },
            "duplicate",
        ),
    ],
)
def test_manifest_fail_closed_rules(overrides: dict[str, Any], match: str) -> None:
    with pytest.raises(RecordError, match=match):
        AcquisitionManifest.from_document(manifest_doc(**overrides))


def test_reproducible_unknown_is_treated_as_no() -> None:
    assert not AcquisitionManifest.from_document(manifest_doc()).reproducible
    assert AcquisitionManifest.from_document(
        manifest_doc(reproducible_from_provider="yes")
    ).reproducible


def test_quality_rules() -> None:
    with pytest.raises(RecordError, match="different primary"):
        SourceQuality.from_document(quality_doc(reconciliation_primary_source_id=None))
    with pytest.raises(RecordError, match="different primary"):
        SourceQuality.from_document(quality_doc(reconciliation_primary_source_id="src_example"))
    anchor = SourceQuality.from_document(
        quality_doc(quality_tier="Q1_authoritative", reconciliation_primary_source_id=None)
    )
    assert anchor.quality_tier is QualityTier.Q1_AUTHORITATIVE
    unverified = SourceQuality.from_document(quality_doc(quality_tier="Q4_unverified"))
    assert not unverified.usable_for_development


def test_copies_of_one_upstream_are_one_cross_check() -> None:
    a = SourceQuality.from_document(quality_doc(source_id="src_a"))
    b = SourceQuality.from_document(quality_doc(source_id="src_b"))
    c = SourceQuality.from_document(quality_doc(source_id="src_c", upstream_group_id="grp_other"))
    assert independent_cross_checks([a, b]) == 1
    assert independent_cross_checks([a, b, c]) == 2


def test_gate_lists_every_unmet_condition() -> None:
    failures = acquisition_gate_failures(
        None, None, None, backup_restore_test_passed=False, safe_parsing_review_passed=False
    )
    assert [item.split(":")[0] for item in failures] == ["A-1", "A-2", "A-3", "A-4", "A-6"]


def test_gate_detects_cross_record_mismatches() -> None:
    approval = AcquisitionApproval.from_document(approval_doc(licence_id="lic_other"))
    licence = LicenceRecord.from_document(licence_doc(source_id="src_other"))
    quality = SourceQuality.from_document(quality_doc(quality_tier="Q4_unverified"))
    failures = acquisition_gate_failures(
        approval, licence, quality, backup_restore_test_passed=True, safe_parsing_review_passed=True
    )
    assert "A-1/A-2: approval cites a different licence" in failures
    assert "A-1/A-2: approval and licence name different sources" in failures
    assert "A-6: Q4_unverified sources are not acquired for development" in failures


def test_manifest_agrees_with_its_approval() -> None:
    approval = AcquisitionApproval.from_document(approval_doc())
    assert manifest_gate_failures(AcquisitionManifest.from_document(manifest_doc()), approval) == []


def test_manifest_disagreements_with_its_approval() -> None:
    approval = AcquisitionApproval.from_document(approval_doc(expected_size_bytes=3))
    manifest = AcquisitionManifest.from_document(
        manifest_doc(
            approval_id="appr_other",
            licence_id="lic_other",
            input_licence_ids=["lic_other"],
            source_url="https://files.example.com/elsewhere/a.csv",
            files=[{"name": "a.json", "format": "json", "size_bytes": 4, "sha256": "d" * 64}],
        )
    )
    failures = manifest_gate_failures(manifest, approval)
    assert failures == [
        "A-5: manifest cites a different approval",
        "A-5: manifest cites a different licence than the approval",
        "A-1: manifest source_url is outside the approved hosts and prefixes",
        "A-1: manifest contains a format the approval does not list",
        "A-1: manifest exceeds the approved expected size",
    ]
