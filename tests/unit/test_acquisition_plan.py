"""G-6 plan and A-3/A-4 evidence records: strict parsing, no coercion, fail closed."""

import copy
from typing import Any

import pytest

from pmv.acquisition import synthetic as syn
from pmv.acquisition.plan import (
    A4ReviewRecord,
    AcquisitionPlan,
    BackupPolicyRecord,
    FileKind,
    RestoreTestRecord,
    bundle_sha256,
    restore_tests_cover,
    size_class,
)
from pmv.acquisition.records import RecordError

SCHEMA = syn.csv_schema(("a", "integer"))


def _plan(**changes: Any) -> dict[str, Any]:
    document = copy.deepcopy(syn.inputs([syn.planned_file("a.csv", schema=SCHEMA)]).plan)
    assert isinstance(document, dict)
    document.update(changes)
    return document


def _file(**changes: Any) -> dict[str, Any]:
    item = syn.planned_file("a.csv", schema=SCHEMA)
    item.update(changes)
    return item


def test_synthetic_plan_parses() -> None:
    plan = AcquisitionPlan.from_document(_plan())
    assert plan.names == ("a.csv",)
    assert plan.files[0].artifact_type == "csv"


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"plan_version": 2}, "plan_version"),
        ({"plan_version": True}, "plan_version"),
        ({"max_attempts": 0}, "max_attempts"),
        ({"max_attempts": 11}, "at most 10"),
        ({"is_primary_source": False}, "mirror lineage"),
        ({"reproducible_from_provider": "maybe"}, "yes, no, or unknown"),
        ({"files": []}, "between 1 and 1000"),
        ({"acquisition_id": "Bad-ID"}, "identifier"),
        ({"decision_record": "docs/x.md"}, "docs/decisions"),
        ({"extra": 1}, "unexpected keys"),
    ],
)
def test_plan_refusals(changes: dict[str, Any], match: str) -> None:
    with pytest.raises(RecordError, match=match):
        AcquisitionPlan.from_document(_plan(**changes))


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"name": "../a.csv"}, "plain local file name"),
        ({"name": "a.csv.zst"}, "no adopted reader"),
        ({"url": "http://x.example/a.csv"}, "https"),
        ({"kind": "folder"}, "'file' or 'archive'"),
        ({"format": "pickle"}, "files\\[\\]"),
        ({"compression": "gzip"}, "compression"),
        ({"schema": None}, "expected schema"),
        ({"members": [{"name": "x.csv", "format": "csv", "schema": SCHEMA}]}, "no members"),
        ({"max_bytes": 0}, "max_bytes"),
        ({"expected_size_bytes": 10**9}, "within max_bytes"),
        ({"provider_sha256": "ABC"}, "SHA-256"),
    ],
)
def test_planned_file_refusals(changes: dict[str, Any], match: str) -> None:
    with pytest.raises(RecordError, match=match):
        AcquisitionPlan.from_document(_plan(files=[_file(**changes)]))


def test_duplicate_names_ignoring_case_are_refused() -> None:
    files = [_file(name="a.csv"), _file(name="A.csv")]
    with pytest.raises(RecordError, match="unique"):
        AcquisitionPlan.from_document(_plan(files=files))


def _archive(**changes: Any) -> dict[str, Any]:
    member = {"name": "d/a.csv", "format": "csv", "schema": SCHEMA}
    item = syn.planned_file(
        "a.tar.gz", kind="archive", file_format=None, schema=None, members=[member]
    )
    item.update(changes)
    return item


def test_archive_plan_parses() -> None:
    plan = AcquisitionPlan.from_document(_plan(files=[_archive()]))
    item = plan.files[0]
    assert item.kind is FileKind.ARCHIVE
    assert item.archive_kind == "tar.gz"
    assert item.artifact_type == "tar.gz"
    assert [member.name for member in item.members] == ["d/a.csv"]


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"name": "a.rar"}, "must end in"),
        ({"format": "csv"}, "no format or schema"),
        ({"compression": "gzip"}, "given by its name"),
        ({"members": []}, "between 1 and 1000"),
        ({"members": [{"name": "../a.csv", "format": "csv", "schema": SCHEMA}]}, "member"),
        ({"members": [{"name": "a.json", "format": "csv", "schema": SCHEMA}]}, "member"),
        ({"members": [{"name": "a.pkl", "format": "csv", "schema": SCHEMA}]}, "member"),
        (
            {
                "members": [
                    {"name": "a.csv", "format": "csv", "schema": SCHEMA},
                    {"name": "A.csv", "format": "csv", "schema": SCHEMA},
                ]
            },
            "unique",
        ),
    ],
)
def test_archive_refusals(changes: dict[str, Any], match: str) -> None:
    with pytest.raises(RecordError, match=match):
        AcquisitionPlan.from_document(_plan(files=[_archive(**changes)]))


def test_size_class_and_restore_coverage() -> None:
    assert size_class(9) == 1
    assert size_class(10) == 2
    assert size_class(1024 * 1024) == 7
    inputs = syn.inputs([syn.planned_file("a.csv", schema=SCHEMA)])
    plan = AcquisitionPlan.from_document(inputs.plan)
    tests = [RestoreTestRecord.from_document(doc) for doc in inputs.restore_tests]  # type: ignore[attr-defined]
    assert restore_tests_cover(plan.files, tests, "synthetic_backup_policy") == []
    assert restore_tests_cover(plan.files, tests, "synthetic_other") == ["a.csv"]
    small = [
        RestoreTestRecord.from_document({**inputs.restore_tests[0], "size_class": 1})  # type: ignore[index]
    ]
    assert restore_tests_cover(plan.files, small, "synthetic_backup_policy") == ["a.csv"]


def test_a_failed_or_mismatched_restore_test_covers_nothing() -> None:
    inputs = syn.inputs([syn.planned_file("a.csv", schema=SCHEMA)])
    plan = AcquisitionPlan.from_document(inputs.plan)
    base = inputs.restore_tests[0]  # type: ignore[index]
    failed = RestoreTestRecord.from_document({**base, "passed": False})
    mismatched = RestoreTestRecord.from_document({**base, "restored_sha256": "f" * 64})
    assert restore_tests_cover(plan.files, [failed, mismatched], "synthetic_backup_policy") == [
        "a.csv"
    ]


def test_backup_policy_synthetic_flag_must_match_its_identifier() -> None:
    document = syn.inputs([_file()]).backup_policy
    assert isinstance(document, dict)
    BackupPolicyRecord.from_document(document)
    with pytest.raises(RecordError, match="synthetic"):
        BackupPolicyRecord.from_document({**document, "synthetic": False})
    with pytest.raises(RecordError, match="synthetic"):
        BackupPolicyRecord.from_document({**document, "policy_id": "real_policy"})


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"review_path": "docs/x.md"}, "research/governance"),
        ({"reviewed_commit": "abc"}, "40-hex"),
        ({"a4_satisfied": "yes"}, "boolean"),
    ],
)
def test_a4_review_refusals(changes: dict[str, Any], match: str) -> None:
    document = syn.inputs([_file()]).a4_review
    assert isinstance(document, dict)
    with pytest.raises(RecordError, match=match):
        A4ReviewRecord.from_document({**document, **changes})


def test_bundle_hash_changes_with_any_document() -> None:
    documents = syn.inputs([_file()]).documents()
    first = bundle_sha256(documents)
    changed = {**documents, "licence": {**documents["licence"], "storage": "unknown"}}  # type: ignore[dict-item]
    assert bundle_sha256(changed) != first
    with pytest.raises(RecordError, match="wrong keys"):
        bundle_sha256({"plan": documents["plan"]})
