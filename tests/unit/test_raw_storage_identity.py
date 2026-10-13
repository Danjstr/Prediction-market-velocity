"""Step 5 regressions: a moved or replaced raw root or managed directory fails closed."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pmv.config import Environment, RawStorageConfig
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport
from pmv.raw_storage import (
    QuarantineReason,
    RawCaptureStore,
    RawIntegrityError,
    StorageEvent,
    StorageEventType,
)

REPO = Path(__file__).resolve().parents[2]
SOURCE = SourceIdentity(
    source_id="unit_source", feed_id="unit_feed", transport=Transport.HTTP, endpoint_id="unit_ep"
)
T0 = datetime(2026, 10, 13, 3, 40, 21, tzinfo=UTC)


def open_store(root: Path) -> RawCaptureStore:
    config = RawStorageConfig(root=root, warning_free_bytes=1000, hard_stop_free_bytes=100)
    provenance = RuntimeProvenance(
        code_commit=None,
        code_tree_dirty=None,
        config_source_sha256="0" * 64,
        raw_config_sha256=config.canonical_sha256(),
        environment=Environment.TEST,
        python_version="3.13.5",
        platform="linux-x86_64",
        machine_label=None,
        parents=(),
    )
    return RawCaptureStore(config, provenance, repo_root=REPO, free_bytes=lambda: 10**12)


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "raw-root"
    path.mkdir(mode=0o700)
    yield path
    for base in (path, tmp_path / "old-root"):
        if base.exists():
            for directory, _subdirs, _files in os.walk(base):
                os.chmod(directory, 0o700)


def replace_root(root: Path) -> Path:
    """Move the whole root aside and create a fresh, empty root at the same path."""
    old = root.parent / "old-root"
    os.rename(root, old)
    root.mkdir(mode=0o700)
    return old


def test_finalize_fails_closed_when_the_root_was_replaced(root: Path) -> None:
    with open_store(root) as store:
        capture = store.start_capture(SOURCE, T0)
        capture.append_payload(b"payload", received_at=T0)
        old = replace_root(root)
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            capture.finalize()
    assert list(root.iterdir()) == []
    assert not (old / "raw" / "v1").exists()


def test_finalize_fails_closed_when_inprogress_was_replaced(root: Path) -> None:
    with open_store(root) as store:
        capture = store.start_capture(SOURCE, T0)
        capture.append_payload(b"payload", received_at=T0)
        os.rename(root / ".inprogress", root / "inprogress-moved")
        (root / ".inprogress").mkdir(mode=0o700)
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            capture.finalize()
    assert not (root / "raw" / "v1").exists()


def test_start_quarantine_recovery_and_ledgers_check_the_root(root: Path) -> None:
    with open_store(root) as store:
        capture = store.start_capture(SOURCE, T0)
        replace_root(root)
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            store.start_capture(SOURCE, T0)
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            capture.quarantine(QuarantineReason.REQUESTED)
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            store.recover_incomplete()
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            store.reconcile()
        event = StorageEvent(
            event_type=StorageEventType.RESTORE_VERIFIED,
            capture_id=capture.capture_id,
            occurred_at=T0,
            restored_sha256="2" * 64,
        )
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            store.append_storage_event(event)
    assert list(root.iterdir()) == []


def test_catalog_directory_replacement_is_detected(root: Path) -> None:
    with open_store(root) as store:
        capture = store.start_capture(SOURCE, T0)
        capture.append_payload(b"payload", received_at=T0)
        manifest = capture.finalize()
        os.rename(root / "catalog", root / "catalog-moved")
        (root / "catalog").mkdir(mode=0o700)
        event = StorageEvent(
            event_type=StorageEventType.RESTORE_VERIFIED,
            capture_id=manifest.capture_id,
            occurred_at=T0,
            restored_sha256="2" * 64,
        )
        with pytest.raises(RawIntegrityError, match="moved or replaced"):
            store.append_storage_event(event)
    assert list((root / "catalog").iterdir()) == []
