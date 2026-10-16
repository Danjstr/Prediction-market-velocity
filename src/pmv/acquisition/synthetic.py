"""Synthetic transport and synthetic owner records for acquisition dry runs and tests.

Nothing here touches a network or a real source. ``SyntheticTransport`` answers from a
fixed script keyed by URL. The record builders produce documents whose identifiers all
start with ``synthetic_``, whose hosts are under the reserved ``.example`` domain, and
whose decision-record paths are placeholders that do not exist: the pipeline accepts them
only in synthetic mode and refuses them in real mode. They are not approvals, licences,
or policies, and must never be presented as such.
"""

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from pmv.acquisition.fetch import TransportFailureError, TransportRequest
from pmv.acquisition.pipeline import PipelineInputs
from pmv.acquisition.plan import size_class

HOST = "files.vendor.example"
PREFIX = f"https://{HOST}/synthetic/"
DECISION = "docs/decisions/synthetic_placeholder.md"
REVIEW = "research/governance/synthetic_placeholder.md"
F09_COMMIT = "0" * 40


@dataclass(slots=True)
class ScriptedResponse:
    """One scripted answer. ``error`` is raised by ``send``; ``body_error`` mid-body."""

    status: int = 200
    headers: Sequence[tuple[str, str]] = ()
    chunks: Sequence[bytes] = ()
    error: BaseException | None = None
    body_error: BaseException | None = None
    body_error_after: int = 0
    closed: bool = False

    def iter_body(self) -> Iterator[bytes]:
        for index, chunk in enumerate(self.chunks):
            if self.body_error is not None and index == self.body_error_after:
                raise self.body_error
            yield chunk
        if self.body_error is not None and self.body_error_after >= len(self.chunks):
            raise self.body_error

    def close(self) -> None:
        self.closed = True


def ok(data: bytes, *, chunk: int = 7, headers: Sequence[tuple[str, str]] = ()) -> ScriptedResponse:
    """A 200 response carrying ``data`` with a correct Content-Length."""
    parts = [data[i : i + chunk] for i in range(0, len(data), chunk)] or [b""]
    return ScriptedResponse(
        status=200,
        headers=(("Content-Length", str(len(data))), *headers),
        chunks=parts,
    )


def redirect(location: str, status: int = 302) -> ScriptedResponse:
    return ScriptedResponse(status=status, headers=(("Location", location),))


@dataclass(slots=True)
class SyntheticTransport:
    """A Transport that answers from a script. Each URL's answers are used in order."""

    routes: Mapping[str, ScriptedResponse | list[ScriptedResponse]]
    synthetic: bool = True
    requests: list[TransportRequest] = field(default_factory=list)
    _served: dict[str, int] = field(default_factory=dict)

    def send(self, request: TransportRequest) -> ScriptedResponse:
        self.requests.append(request)
        route = self.routes.get(request.url)
        if route is None:
            raise TransportFailureError("no scripted route")
        if isinstance(route, ScriptedResponse):
            response = route
        else:
            index = self._served.get(request.url, 0)
            if index >= len(route):
                raise TransportFailureError("scripted route exhausted")
            self._served[request.url] = index + 1
            response = route[index]
        if response.error is not None:
            raise response.error
        return response


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def csv_schema(*columns: tuple[str, str]) -> dict[str, object]:
    return {"columns": [{"name": name, "type": kind} for name, kind in columns]}


def planned_file(
    name: str,
    *,
    file_format: str | None = "csv",
    compression: str = "none",
    schema: object = None,
    kind: str = "file",
    members: Sequence[Mapping[str, object]] = (),
    max_bytes: int = 1024 * 1024,
    expected_size_bytes: int | None = None,
    provider_sha256: str | None = None,
    url: str | None = None,
) -> dict[str, object]:
    """One synthetic plan file entry."""
    return {
        "name": name,
        "url": url or PREFIX + name,
        "kind": kind,
        "format": file_format,
        "compression": compression,
        "schema": schema,
        "members": list(members),
        "max_bytes": max_bytes,
        "expected_size_bytes": expected_size_bytes,
        "provider_sha256": provider_sha256,
    }


def _artifact_type(item: Mapping[str, object]) -> str:
    if item["kind"] == "archive":
        name = str(item["name"]).lower()
        for suffix in (".tar.gz", ".tar.bz2", ".tar.xz", ".tar", ".zip"):
            if name.endswith(suffix):
                return suffix[1:]
    if item["compression"] == "none":
        return str(item["format"])
    return f"{item['format']}+{item['compression']}"


def inputs(
    files: Sequence[Mapping[str, object]],
    *,
    acquisition_id: str = "synthetic_acq_1",
    source_id: str = "synthetic_source",
    approval_formats: Sequence[str] = ("csv", "json", "jsonl", "text"),
    expected_size_bytes: int = 64 * 1024 * 1024,
    max_attempts: int = 3,
    url_prefixes: Sequence[str] = (PREFIX,),
    licence_overrides: Mapping[str, object] | None = None,
    credential_required: bool = False,
) -> PipelineInputs:
    """A complete, internally consistent set of synthetic authorizing documents."""
    plan = {
        "plan_version": 1,
        "acquisition_id": acquisition_id,
        "approval_id": "synthetic_approval",
        "source_id": source_id,
        "upstream_identity": "Synthetic upstream (no real source)",
        "is_primary_source": True,
        "mirror_lineage": [],
        "vendor_version": "synthetic-v1",
        "reproducible_from_provider": "no",
        "max_attempts": max_attempts,
        "files": [dict(item) for item in files],
        "decision_record": DECISION,
    }
    approval = {
        "approval_id": "synthetic_approval",
        "source_id": source_id,
        "dataset": "Synthetic dataset",
        "instruments": ["SYNTHETIC"],
        "date_range_start": "2099-01-01T00:00:00.000000Z",
        "date_range_end": "2099-01-02T00:00:00.000000Z",
        "formats": list(approval_formats),
        "expected_size_bytes": expected_size_bytes,
        "cost": "0",
        "currency": "USD",
        "credential_required": credential_required,
        "purchase_or_credential_decision": DECISION if credential_required else None,
        "url_prefixes": list(url_prefixes),
        "host_class_decisions": {prefix: DECISION for prefix in url_prefixes},
        "licence_id": "synthetic_licence",
        "f09_settings_commit": F09_COMMIT,
        "decision_record": DECISION,
    }
    licence: dict[str, object] = {
        "licence_id": "synthetic_licence",
        "source_id": source_id,
        "terms_url": f"https://{HOST}/terms",
        "retrieved_at": "2099-01-01T00:00:00.000000Z",
        "terms_sha256": "a" * 64,
        "operative_terms_quoted": ["Synthetic terms; not a licence."],
        "research_use": "yes",
        "internal_model_development": "yes",
        "commercial_trading_use": "yes",
        "automated_access": "yes",
        "storage": "yes",
        "retention_after_subscription": "yes",
        "redistribution": "no",
        "derived_data": "yes",
        "upstream_rights_established": "yes",
        "decision_record": DECISION,
    }
    licence.update(licence_overrides or {})
    quality = {
        "source_id": source_id,
        "quality_tier": "Q1_authoritative",
        "upstream_group_id": "synthetic_group",
        "reconciliation_primary_source_id": None,
        "reconciliation_plan": "Synthetic: none.",
        "assigned_at": "2099-01-01T00:00:00.000000Z",
        "decision_record": DECISION,
    }
    policy = {
        "policy_id": "synthetic_backup_policy",
        "synthetic": True,
        "backup_target_id": "synthetic_directory",
        "decision_record": DECISION,
    }
    tests = [
        {
            "test_id": f"synthetic_restore_{index}",
            "policy_id": "synthetic_backup_policy",
            "artifact_type": artifact,
            "size_class": 12,
            "fixture_sha256": "b" * 64,
            "restored_sha256": "b" * 64,
            "passed": True,
            "tested_at": "2099-01-01T00:00:00.000000Z",
            "decision_record": DECISION,
        }
        for index, artifact in enumerate(sorted({_artifact_type(item) for item in files}))
    ]
    review = {
        "review_path": REVIEW,
        "reviewed_commit": "c" * 40,
        "no_blocking_findings": True,
        "no_major_findings": True,
        "a4_satisfied": False,
        "decision_record": DECISION,
    }
    if any(size_class(int(str(item["max_bytes"]))) > 12 for item in files):
        raise ValueError("synthetic restore tests cover size classes up to 12 digits only")
    return PipelineInputs(
        plan=plan,
        approval=approval,
        licence=licence,
        quality=quality,
        backup_policy=policy,
        restore_tests=tests,
        a4_review=review,
    )


@dataclass(slots=True)
class StaticRepository:
    """A fixed answer for every Git fact the pipeline asks in real mode (tests only)."""

    head_commit: str | None = None
    clean: bool = False
    committed: bool = False
    ancestor: bool = False
    unchanged: bool = False

    def head(self) -> str | None:
        return self.head_commit

    def tree_clean(self) -> bool:
        return self.clean

    def committed_unchanged(self, path: str) -> bool:
        return self.committed

    def is_ancestor(self, commit: str) -> bool:
        return self.ancestor

    def unchanged_since(self, commit: str, path: str) -> bool:
        return self.unchanged
