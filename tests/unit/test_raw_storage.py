"""Tests for the filesystem raw capture store, including crash fault injection."""

import ctypes
import errno
import hashlib
import io
import json
import logging
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import pmv.raw_storage as raw_storage
from pmv.config import Environment, LoggingConfig, LogLevel, RawStorageConfig, load_config
from pmv.log import configure_logging
from pmv.raw_format import MAX_PAYLOAD_BYTES, EventType, FrameReader, PayloadFrame
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport
from pmv.raw_storage import (
    CaptureClosedError,
    CaptureEvent,
    CaptureOversizeError,
    CatalogIndexError,
    DiskHardStopError,
    DuplicateCaptureIdError,
    QuarantineReason,
    RawCapture,
    RawCaptureStore,
    RawIntegrityError,
    RawStorageError,
    RawStorageNotConfiguredError,
    RecoveryOutcome,
    StorageEvent,
    StorageEventType,
    UnsupportedFilesystemError,
    collect_runtime_provenance,
    parse_storage_events,
    rename_noreplace,
)

REPO = Path(__file__).resolve().parents[2]
SOURCE = SourceIdentity(
    source_id="unit_source",
    feed_id="unit_feed",
    transport=Transport.WEBSOCKET,
    endpoint_id="unit_ws",
)
T0 = datetime(2026, 10, 13, 3, 40, 21, 123456, tzinfo=UTC)
PLENTY = 10**12


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=1)
        return self.now


def make_config(root: Path, **overrides: object) -> RawStorageConfig:
    values: dict[str, object] = {
        "root": root,
        "warning_free_bytes": 1_000,
        "hard_stop_free_bytes": 100,
    }
    values.update(overrides)
    return RawStorageConfig(**values)  # type: ignore[arg-type]  # test helper forwards typed keywords


def make_provenance(config: RawStorageConfig) -> RuntimeProvenance:
    return RuntimeProvenance(
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


def open_store(
    root: Path,
    *,
    free: Callable[[], int] = lambda: PLENTY,
    config: RawStorageConfig | None = None,
    **kwargs: object,
) -> RawCaptureStore:
    config = config or make_config(root)
    return RawCaptureStore(
        config,
        make_provenance(config),
        repo_root=REPO,
        clock=Clock(),
        free_bytes=free,
        **kwargs,  # type: ignore[arg-type]  # test helper forwards typed keywords
    )


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "raw-root"
    path.mkdir(mode=0o700)
    yield path
    for directory, _subdirs, _files in os.walk(path):
        os.chmod(directory, 0o700)


@pytest.fixture
def store(root: Path) -> Iterator[RawCaptureStore]:
    with open_store(root) as opened:
        yield opened


def final_dir(root: Path, capture_id: str) -> Path:
    date = (capture_id[0:4], capture_id[4:6], capture_id[6:8])
    return root.joinpath("raw", "v1", "unit_source", "unit_feed", *date, capture_id)


def read_frames(path: Path) -> list[object]:
    data = path.read_bytes()
    return list(FrameReader(io.BytesIO(data), len(data)).frames())


def capture_with(store: RawCaptureStore, payloads: list[bytes]) -> RawCapture:
    capture = store.start_capture(SOURCE, T0)
    for index, payload in enumerate(payloads):
        capture.append_payload(payload, received_at=T0 + timedelta(seconds=index))
    return capture


def mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


# ----- exact preservation, hashing, manifest -----


def test_payloads_are_preserved_exactly_and_in_order(root: Path, store: RawCaptureStore) -> None:
    payloads = [
        b"",
        b"\x00",
        b"a\nb\r\nc",
        bytes(range(256)),
        b'{"dup":1}',
        b'{"dup":1}',
        b"\xff\xfe not utf-8",
    ]
    capture = store.start_capture(SOURCE, T0)
    for index, payload in enumerate(payloads):
        capture.append_payload(payload, received_at=T0 + timedelta(seconds=index))
    manifest = capture.finalize()
    frames = read_frames(final_dir(root, manifest.capture_id) / "records.pmvraw")
    assert [frame.payload for frame in frames if isinstance(frame, PayloadFrame)] == payloads
    assert manifest.observations.payload_count == len(payloads)
    result = store.verify_capture(manifest.capture_id)
    assert result.directory_read_only


def test_manifest_records_exact_size_and_sha256(root: Path, store: RawCaptureStore) -> None:
    manifest = capture_with(store, [b"one", b"two"]).finalize()
    directory = final_dir(root, manifest.capture_id)
    data = (directory / "records.pmvraw").read_bytes()
    assert manifest.raw_object.size_bytes == len(data)
    assert manifest.raw_object.sha256 == hashlib.sha256(data).hexdigest()
    assert manifest.raw_object.record_count == 2
    manifest_bytes = (directory / "manifest.json").read_bytes()
    assert store.read_manifest(manifest.capture_id) == manifest
    entry = store.read_catalog().entries[manifest.capture_id]
    assert entry.manifest_sha256 == hashlib.sha256(manifest_bytes).hexdigest()
    assert (
        entry.manifest_path
        == f"{manifest.raw_object.relative_path[: -len('records.pmvraw')]}manifest.json"
    )


def test_out_of_order_duplicate_and_malformed_payloads_are_preserved_and_counted(
    root: Path, store: RawCaptureStore
) -> None:
    capture = store.start_capture(SOURCE, T0)
    capture.append_payload(b"m1", received_at=T0, source_timestamp=T0 + timedelta(seconds=5))
    capture.append_payload(b"m1", received_at=T0, source_timestamp=T0 + timedelta(seconds=5))
    capture.append_payload(b"m0", received_at=T0, source_timestamp=T0 + timedelta(seconds=1))
    capture.append_payload(b"{not json", received_at=T0 - timedelta(seconds=1), malformed=True)
    capture.record_event(CaptureEvent(EventType.RECONNECT))
    manifest = capture.finalize()
    obs = manifest.observations
    assert (obs.payload_count, obs.malformed_message_count, obs.reconnect_count) == (4, 1, 1)
    assert obs.source_clock_regression_count == 1
    assert obs.local_clock_regression_count == 1
    frames = read_frames(final_dir(root, manifest.capture_id) / "records.pmvraw")
    payloads = [frame.payload for frame in frames if isinstance(frame, PayloadFrame)]
    assert payloads == [b"m1", b"m1", b"m0", b"{not json"]
    assert [frame.sequence for frame in frames] == list(range(len(frames)))  # type: ignore[attr-defined]  # both frame types have sequence


def test_source_received_and_written_timestamps_stay_distinct(
    root: Path, store: RawCaptureStore
) -> None:
    capture = store.start_capture(SOURCE, T0)
    capture.append_payload(b"x", received_at=T0, source_timestamp=T0 - timedelta(seconds=3))
    manifest = capture.finalize()
    (frame,) = read_frames(final_dir(root, manifest.capture_id) / "records.pmvraw")
    assert isinstance(frame, PayloadFrame)
    assert frame.received_at == "2026-10-13T03:40:21.123456Z"
    assert frame.source_timestamp == "2026-10-13T03:40:18.123456Z"
    assert frame.written_at not in (frame.received_at, frame.source_timestamp)


def test_naive_datetimes_are_rejected(store: RawCaptureStore) -> None:
    naive = datetime(2026, 10, 13)  # noqa: DTZ001 - verifies naive datetimes are rejected
    with pytest.raises(ValueError, match="timezone-aware"):
        store.start_capture(SOURCE, naive)
    capture = store.start_capture(SOURCE, T0)
    with pytest.raises(ValueError, match="timezone-aware"):
        capture.append_payload(b"x", received_at=naive)
    capture.quarantine(QuarantineReason.REQUESTED)


def test_capture_id_and_date_path_use_the_utc_start(root: Path, store: RawCaptureStore) -> None:
    from datetime import timezone

    late_eastern = datetime(2026, 10, 12, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    capture = store.start_capture(SOURCE, late_eastern)
    assert capture.capture_id.startswith("20261013T043000.000000Z_")
    manifest = capture.finalize()
    assert manifest.times.capture_started_at == "2026-10-13T04:30:00.000000Z"
    assert final_dir(root, manifest.capture_id).is_dir()
    assert "/2026/10/13/" in manifest.raw_object.relative_path


# ----- corruption and consistency -----


def test_single_byte_corruption_and_truncation_are_detected(
    root: Path, store: RawCaptureStore
) -> None:
    manifest = capture_with(store, [b"payload-one", b"payload-two"]).finalize()
    directory = final_dir(root, manifest.capture_id)
    raw = directory / "records.pmvraw"
    directory.chmod(0o700)
    raw.chmod(0o600)
    original = raw.read_bytes()
    for position in (len(original) - 1, 20, 3):
        corrupted = bytearray(original)
        corrupted[position] ^= 0x01
        raw.write_bytes(bytes(corrupted))
        with pytest.raises(RawIntegrityError):
            store.verify_capture(manifest.capture_id)
    raw.write_bytes(original[:-1])
    with pytest.raises(RawIntegrityError):
        store.verify_capture(manifest.capture_id)


def test_manifest_object_mismatch_is_detected(root: Path, store: RawCaptureStore) -> None:
    import dataclasses

    manifest = capture_with(store, [b"abc"]).finalize()
    directory = final_dir(root, manifest.capture_id)
    directory.chmod(0o700)
    target = directory / "manifest.json"
    target.chmod(0o600)
    for changed in (
        dataclasses.replace(
            manifest, raw_object=dataclasses.replace(manifest.raw_object, size_bytes=1)
        ),
        dataclasses.replace(
            manifest, raw_object=dataclasses.replace(manifest.raw_object, sha256="0" * 64)
        ),
    ):
        target.write_bytes(changed.to_bytes())
        target.chmod(0o400)
        with pytest.raises(RawIntegrityError, match="does not match its manifest"):
            store.verify_capture(manifest.capture_id)
        target.chmod(0o600)


def test_finalized_capture_rejects_unexpected_files(root: Path, store: RawCaptureStore) -> None:
    manifest = capture_with(store, [b"abc"]).finalize()
    directory = final_dir(root, manifest.capture_id)
    directory.chmod(0o700)
    (directory / "manifest.json.tmp").write_bytes(b"")
    with pytest.raises(RawIntegrityError, match="unexpected entries"):
        store.verify_capture(manifest.capture_id)


def test_incomplete_capture_is_never_finalized(root: Path, store: RawCaptureStore) -> None:
    capture = capture_with(store, [b"abc"])
    with pytest.raises(RawIntegrityError, match="not finalized"):
        store.verify_capture(capture.capture_id)
    assert not final_dir(root, capture.capture_id).exists()
    assert (root / ".inprogress" / capture.capture_id / "records.pmvraw.partial").is_file()
    capture.quarantine(QuarantineReason.REQUESTED)


# ----- identifiers, reservations, overwrite refusal -----


def test_duplicate_capture_ids_are_refused(root: Path) -> None:
    with open_store(root, random_token=lambda: "a" * 32) as store:
        first = store.start_capture(SOURCE, T0)
        with pytest.raises(DuplicateCaptureIdError):
            store.start_capture(SOURCE, T0)
        manifest = first.finalize()
        assert store.verify_capture(manifest.capture_id).manifest == manifest


@pytest.mark.parametrize(
    "capture_id", ["../../etc", "x", "/abs", "20261013T034021.123456Z_" + "0" * 31]
)
def test_malicious_capture_ids_are_rejected(store: RawCaptureStore, capture_id: str) -> None:
    with pytest.raises(ValueError, match="capture ID"):
        store.verify_capture(capture_id)


def test_finalized_capture_is_never_overwritten(root: Path, store: RawCaptureStore) -> None:
    capture = capture_with(store, [b"new data"])
    blocker = final_dir(root, capture.capture_id)
    blocker.mkdir(parents=True, mode=0o700)
    for parent in blocker.parents:
        if parent == root:
            break
        parent.chmod(0o700)
    with pytest.raises(FileExistsError):
        capture.finalize()
    assert list(blocker.iterdir()) == []
    assert (root / ".inprogress" / capture.capture_id).is_dir()


def test_rename_noreplace_semantics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "d"
    directory.mkdir()
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        (directory / "a").write_bytes(b"a")
        (directory / "b").write_bytes(b"b")
        (directory / "empty").mkdir()
        (directory / "src_dir").mkdir()
        with pytest.raises(FileExistsError):
            rename_noreplace(fd, "a", fd, "b")
        with pytest.raises(FileExistsError):
            rename_noreplace(fd, "src_dir", fd, "empty")
        assert (directory / "b").read_bytes() == b"b"
        with pytest.raises(FileNotFoundError):
            rename_noreplace(fd, "missing", fd, "c")
        for bad in ("..", ".", "a/b", "", "a\x00b"):
            with pytest.raises(RawIntegrityError):
                rename_noreplace(fd, bad, fd, "c")
        rename_noreplace(fd, "a", fd, "c")
        assert (directory / "c").read_bytes() == b"a"

        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("plain rename must never be used")

        monkeypatch.setattr(os, "rename", forbidden)
        monkeypatch.setattr(os, "replace", forbidden)
        for error in (errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP):

            def unsupported(*_args: object, _error: int = error) -> int:
                ctypes.set_errno(_error)
                return -1

            monkeypatch.setattr(raw_storage, "_renameat2", unsupported)
            with pytest.raises(UnsupportedFilesystemError):
                rename_noreplace(fd, "c", fd, "d")

        def cross_device(*_args: object) -> int:
            ctypes.set_errno(errno.EXDEV)
            return -1

        monkeypatch.setattr(raw_storage, "_renameat2", cross_device)
        with pytest.raises(OSError, match="cross-device") as excinfo:
            rename_noreplace(fd, "c", fd, "d")
        assert excinfo.value.errno == errno.EXDEV
        monkeypatch.setattr(raw_storage, "_renameat2", None)
        with pytest.raises(UnsupportedFilesystemError):
            rename_noreplace(fd, "c", fd, "d")
        assert (directory / "c").exists()
    finally:
        os.close(fd)


def test_store_fails_closed_without_noreplace(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(raw_storage, "_renameat2", None)
    with pytest.raises(UnsupportedFilesystemError):
        open_store(root)
    assert not [name for name in os.listdir(root) if name.startswith(".probe")]


# ----- root validation and path safety -----


def test_root_must_be_configured_absolute_outside_git_and_private(
    tmp_path: Path, root: Path
) -> None:
    with pytest.raises(RawStorageNotConfiguredError):
        RawCaptureStore(RawStorageConfig(), make_provenance(RawStorageConfig()), repo_root=REPO)
    with pytest.raises(ValueError, match="absolute"):
        RawStorageConfig(root=Path("relative/raw"))
    config = make_config(root)
    with pytest.raises(RawStorageError, match="outside the Git"):
        RawCaptureStore(config, make_provenance(config), repo_root=root.parent)
    nested_repo = root / "repo"
    nested_repo.mkdir()
    with pytest.raises(RawStorageError, match="outside the Git"):
        RawCaptureStore(config, make_provenance(config), repo_root=nested_repo)
    nested_repo.rmdir()
    root.chmod(0o770)
    with pytest.raises(RawIntegrityError, match="writable by group"):
        open_store(root)
    root.chmod(0o700)
    with pytest.raises(RawStorageError, match="provenance"):
        RawCaptureStore(
            config, make_provenance(make_config(root, retention_class="x")), repo_root=REPO
        )


def test_capture_requires_disk_thresholds(root: Path) -> None:
    config = RawStorageConfig(root=root)
    with (
        RawCaptureStore(config, make_provenance(config), repo_root=REPO) as store,
        pytest.raises(RawStorageNotConfiguredError, match="thresholds"),
    ):
        store.start_capture(SOURCE, T0)
    assert os.listdir(root / ".capture_ids") == []


def test_symlinked_root_is_rejected(tmp_path: Path, root: Path) -> None:
    link = tmp_path / "link-root"
    link.symlink_to(root)
    config = make_config(link)
    with pytest.raises(RawIntegrityError, match="not a plain directory"):
        RawCaptureStore(config, make_provenance(config), repo_root=REPO)


@pytest.mark.parametrize("managed", [".inprogress", ".capture_ids", "quarantine", "raw", "catalog"])
def test_symlinked_managed_directories_are_rejected(
    tmp_path: Path, root: Path, managed: str
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (root / managed).symlink_to(outside)
    with pytest.raises(RawIntegrityError, match="not a plain directory"):
        open_store(root)
    assert os.listdir(outside) == []


def test_symlinked_intermediate_final_path_is_rejected(tmp_path: Path, root: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    with open_store(root) as store:
        (root / "raw" / "v1").symlink_to(outside)
        capture = capture_with(store, [b"abc"])
        with pytest.raises(RawIntegrityError, match="not a plain directory"):
            capture.finalize()
    assert os.listdir(outside) == []
    assert (root / ".inprogress" / capture.capture_id).is_dir()


# ----- locking, identity races, recovery -----


def test_recovery_never_touches_a_live_capture(root: Path, store: RawCaptureStore) -> None:
    capture = capture_with(store, [b"live"])
    results = store.recover_incomplete()
    assert [(r.capture_id, r.outcome) for r in results] == [
        (capture.capture_id, RecoveryOutcome.ACTIVE)
    ]
    assert (root / ".inprogress" / capture.capture_id).is_dir()
    manifest = capture.finalize()
    assert store.verify_capture(manifest.capture_id).manifest == manifest


def test_start_aborts_when_its_directory_is_replaced_before_locking(root: Path) -> None:
    def move_away(point: str) -> None:
        if point == "start.opened":
            (name,) = os.listdir(root / ".inprogress")
            os.rename(root / ".inprogress" / name, root / "moved-away")

    with (
        open_store(root, fault_hook=move_away) as store,
        pytest.raises(RawIntegrityError, match="moved"),
    ):
        store.start_capture(SOURCE, T0)
    assert os.listdir(root / "moved-away") == []
    assert len(os.listdir(root / ".capture_ids")) == 1


def test_recovery_leaves_a_concurrently_moved_capture_alone(root: Path) -> None:
    with open_store(root) as store:
        capture = capture_with(store, [b"orphan"])
        capture._abandon()

    def move_away(point: str) -> None:
        if point == "recovery.locked":
            os.rename(root / ".inprogress" / capture.capture_id, root / "moved-away")

    with open_store(root, fault_hook=move_away) as store:
        results = store.recover_incomplete()
    assert (capture.capture_id, RecoveryOutcome.MOVED_CONCURRENTLY) in [
        (r.capture_id, r.outcome) for r in results
    ]
    assert not (root / "quarantine" / capture.capture_id).exists()
    assert not (root / "moved-away" / "quarantine.json").exists()


def test_reserved_capture_without_data_is_reported(root: Path) -> None:
    class SimulatedCrashError(Exception):
        pass

    def crash(point: str) -> None:
        if point == "start.reserved":
            raise SimulatedCrashError

    with open_store(root, fault_hook=crash) as store, pytest.raises(SimulatedCrashError):
        store.start_capture(SOURCE, T0)
    with open_store(root) as store:
        results = store.recover_incomplete()
    assert [r.outcome for r in results] == [RecoveryOutcome.RESERVED_NO_DATA]
    assert len(os.listdir(root / ".capture_ids")) == 1


def test_explicit_quarantine(root: Path, store: RawCaptureStore) -> None:
    capture = capture_with(store, [b"abc"])
    capture.quarantine(QuarantineReason.REQUESTED)
    directory = root / "quarantine" / capture.capture_id
    record = json.loads((directory / "quarantine.json").read_bytes())
    assert record["reason"] == "requested"
    assert set(os.listdir(directory)) == {"quarantine.json", "records.pmvraw.partial"}
    assert mode(directory) == 0o700
    assert mode(directory / "quarantine.json") == 0o600
    with pytest.raises(CaptureClosedError):
        capture.append_payload(b"more", received_at=T0)
    assert store.recover_incomplete() == []


# ----- write failures, disk policy, oversize -----


def test_partial_frame_write_poisons_the_capture(
    root: Path, store: RawCaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = capture_with(store, [b"good"])
    real_write_all = raw_storage._write_all

    def partial_then_fail(fd: int, data: bytes) -> None:
        os.write(fd, data[: len(data) // 2])
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(raw_storage, "_write_all", partial_then_fail)
    with pytest.raises(OSError, match="No space"):
        capture.append_payload(b"x" * 100, received_at=T0)
    monkeypatch.setattr(raw_storage, "_write_all", real_write_all)
    with pytest.raises(CaptureClosedError):
        capture.append_payload(b"more", received_at=T0)
    with pytest.raises(CaptureClosedError, match="write failure"):
        capture.finalize()
    capture.quarantine(QuarantineReason.WRITE_FAILURE)
    assert (root / "quarantine" / capture.capture_id / "quarantine.json").is_file()
    assert not final_dir(root, capture.capture_id).exists()


def test_disk_warning_is_logged_and_recorded_once(root: Path) -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        with open_store(root, free=lambda: 500) as store:
            manifest = capture_with(store, [b"a", b"b", b"c"]).finalize()
    finally:
        _reset_logging()
    assert manifest.observations.payload_count == 3
    assert manifest.observations.event_count == 1
    events = [json.loads(line)["event"] for line in buffer.getvalue().splitlines()]
    assert events.count("raw.disk_warning") == 1


def test_hard_stop_refuses_a_new_capture(root: Path) -> None:
    with (
        open_store(root, free=lambda: 100) as store,
        pytest.raises(DiskHardStopError) as excinfo,
    ):
        store.start_capture(SOURCE, T0)
    assert excinfo.value.manifest is None
    assert os.listdir(root / ".capture_ids") == []


def test_hard_stop_finalizes_the_captured_prefix(root: Path) -> None:
    free = {"bytes": PLENTY}
    with open_store(root, free=lambda: free["bytes"]) as store:
        capture = capture_with(store, [b"first", b"second"])
        free["bytes"] = 50
        with pytest.raises(DiskHardStopError) as excinfo:
            capture.append_payload(b"never stored", received_at=T0)
        manifest = excinfo.value.manifest
        assert manifest is not None
        assert manifest.observations.payload_count == 2
        assert manifest.observations.event_count == 1
        assert store.verify_capture(manifest.capture_id).manifest == manifest
        frames = read_frames(final_dir(root, manifest.capture_id) / "records.pmvraw")
        assert b"never stored" not in [f.payload for f in frames if isinstance(f, PayloadFrame)]
        with pytest.raises(CaptureClosedError):
            capture.append_payload(b"x", received_at=T0)


def test_oversize_payload_quarantines_the_capture(root: Path, store: RawCaptureStore) -> None:
    capture = capture_with(store, [b"kept"])
    oversize = bytes(MAX_PAYLOAD_BYTES + 1)
    with pytest.raises(CaptureOversizeError):
        capture.append_payload(oversize, received_at=T0)
    record = json.loads((root / "quarantine" / capture.capture_id / "quarantine.json").read_bytes())
    assert record["reason"] == "oversize_payload"
    assert record["oversize_payload_bytes"] == MAX_PAYLOAD_BYTES + 1
    assert record["oversize_payload_sha256"] == hashlib.sha256(oversize).hexdigest()
    assert not final_dir(root, capture.capture_id).exists()
    with pytest.raises(CaptureClosedError):
        capture.append_payload(b"x", received_at=T0)


def test_enospc_while_writing_the_manifest_leaves_the_capture_in_progress(
    root: Path, store: RawCaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = capture_with(store, [b"abc"])
    real = raw_storage._write_new_file

    def no_space(parent_fd: int, name: str, data: bytes) -> None:
        if name == "manifest.json.tmp":
            raise OSError(errno.ENOSPC, "No space left on device")
        real(parent_fd, name, data)

    monkeypatch.setattr(raw_storage, "_write_new_file", no_space)
    with pytest.raises(OSError, match="No space"):
        capture.finalize()
    monkeypatch.setattr(raw_storage, "_write_new_file", real)
    assert not final_dir(root, capture.capture_id).exists()
    assert [r.outcome for r in store.recover_incomplete()] == [RecoveryOutcome.QUARANTINED]


# ----- catalog -----


def test_catalog_failure_never_destroys_a_finalized_capture(
    store: RawCaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture = capture_with(store, [b"abc"])

    def failing(_entry: object) -> None:
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setattr(store, "_append_catalog", failing)
    with pytest.raises(CatalogIndexError) as excinfo:
        capture.finalize()
    manifest = excinfo.value.manifest
    monkeypatch.undo()
    assert store.verify_capture(manifest.capture_id).manifest == manifest
    assert manifest.capture_id not in store.read_catalog().entries
    result = store.reconcile()
    assert result.added == (manifest.capture_id,)
    assert manifest.capture_id in store.read_catalog().entries


def test_missing_catalog_is_rebuilt_from_manifests(root: Path, store: RawCaptureStore) -> None:
    first = capture_with(store, [b"a"]).finalize()
    second = capture_with(store, [b"b"]).finalize()
    (root / "catalog" / "captures.v1.jsonl").unlink()
    result = store.reconcile()
    assert sorted(result.added) == sorted([first.capture_id, second.capture_id])
    assert set(store.read_catalog().entries) == {first.capture_id, second.capture_id}
    assert store.reconcile().added == ()


def test_conflicting_catalog_entries_are_an_integrity_failure(
    root: Path, store: RawCaptureStore
) -> None:
    manifest = capture_with(store, [b"a"]).finalize()
    catalog = root / "catalog" / "captures.v1.jsonl"
    entry = json.loads(catalog.read_bytes().splitlines()[0])
    entry["manifest_sha256"] = "0" * 64
    with catalog.open("ab") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    assert store.read_catalog().conflicting_ids == (manifest.capture_id,)
    with pytest.raises(RawIntegrityError, match="conflicting"):
        store.reconcile()


def test_catalog_torn_tail_is_isolated_and_reported(root: Path, store: RawCaptureStore) -> None:
    catalog = root / "catalog" / "captures.v1.jsonl"
    catalog.write_bytes(b'{"capture_id":"20261013T')
    catalog.chmod(0o600)
    manifest = capture_with(store, [b"a"]).finalize()
    report = store.read_catalog()
    assert report.invalid_lines == (1,)
    assert manifest.capture_id in report.entries


def test_catalog_short_write_is_rolled_back(
    root: Path, store: RawCaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = capture_with(store, [b"a"]).finalize()
    catalog = root / "catalog" / "captures.v1.jsonl"
    before = catalog.read_bytes()

    def short_write(fd: int, data: bytes) -> int:
        return os.write(fd, data[: len(data) // 2])

    monkeypatch.setattr(raw_storage, "_ledger_write", short_write)
    with pytest.raises(CatalogIndexError):
        capture_with(store, [b"b"]).finalize()
    assert catalog.read_bytes() == before
    monkeypatch.undo()
    assert store.read_catalog().invalid_lines == ()
    assert first.capture_id in store.read_catalog().entries


# ----- authoritative storage-events ledger -----


def backup_event(capture_id: str) -> StorageEvent:
    return StorageEvent(
        event_type=StorageEventType.BACKUP_VERIFIED,
        capture_id=capture_id,
        occurred_at=T0,
        backup_policy_id="offsite_a",
        object_sha256="1" * 64,
    )


def restore_event(capture_id: str) -> StorageEvent:
    return StorageEvent(
        event_type=StorageEventType.RESTORE_VERIFIED,
        capture_id=capture_id,
        occurred_at=T0,
        restored_sha256="2" * 64,
    )


@pytest.fixture
def ledger(root: Path, store: RawCaptureStore) -> Path:
    capture_id = capture_with(store, [b"a"]).finalize().capture_id
    for event in (backup_event(capture_id), restore_event(capture_id), backup_event(capture_id)):
        store.append_storage_event(event)
    return root / "catalog" / "storage-events.v1.jsonl"


def test_storage_events_form_a_verified_chain(ledger: Path, store: RawCaptureStore) -> None:
    events = store.read_storage_events()
    assert [event.ledger_seq for event in events] == [0, 1, 2]
    assert events[0].prev_entry_sha256 is None
    assert events[1].prev_entry_sha256 == events[0].entry_sha256
    assert events[2].prev_entry_sha256 == events[1].entry_sha256
    first = json.loads(ledger.read_bytes().splitlines()[0])
    body = {key: value for key, value in first.items() if key != "entry_sha256"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    assert first["entry_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert mode(ledger) == 0o600


def _rewrite(ledger: Path, lines: list[bytes]) -> None:
    ledger.write_bytes(b"".join(line + b"\n" for line in lines))


def test_altered_entry_is_detected(ledger: Path, store: RawCaptureStore) -> None:
    lines = ledger.read_bytes().splitlines()
    entry = json.loads(lines[1])
    entry["restored_sha256"] = "3" * 64
    lines[1] = json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()
    _rewrite(ledger, lines)
    with pytest.raises(RawIntegrityError, match="line 2 has an invalid entry_sha256"):
        store.read_storage_events()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda lines: [lines[1], lines[0], lines[2]], "ledger_seq"),
        (lambda lines: [lines[0], lines[2]], "ledger_seq"),
        (lambda lines: [lines[0], lines[0], lines[1], lines[2]], "ledger_seq"),
    ],
    ids=["reordered", "interior-deleted", "duplicated"],
)
def test_reordered_deleted_or_duplicated_entries_are_detected(
    ledger: Path,
    store: RawCaptureStore,
    mutate: Callable[[list[bytes]], list[bytes]],
    message: str,
) -> None:
    _rewrite(ledger, mutate(ledger.read_bytes().splitlines()))
    with pytest.raises(RawIntegrityError, match=message):
        store.read_storage_events()


def test_removing_complete_entries_from_the_end_is_not_detectable(
    ledger: Path, store: RawCaptureStore
) -> None:
    # Documented limitation: Step 5 has no separately anchored ledger head.
    _rewrite(ledger, ledger.read_bytes().splitlines()[:2])
    assert len(store.read_storage_events()) == 2


def test_torn_authoritative_tail_blocks_reads_and_appends(
    ledger: Path, store: RawCaptureStore
) -> None:
    capture_id = store.read_storage_events()[0].body["capture_id"]
    assert isinstance(capture_id, str)
    with ledger.open("ab") as handle:
        handle.write(b'{"capture_id":"2026')
    damaged = ledger.read_bytes()
    with pytest.raises(RawIntegrityError, match="incomplete"):
        store.read_storage_events()
    with pytest.raises(RawIntegrityError, match="appends are refused"):
        store.append_storage_event(backup_event(capture_id))
    assert ledger.read_bytes() == damaged


def test_storage_event_short_write_is_rolled_back(
    ledger: Path, store: RawCaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture_id = str(store.read_storage_events()[0].body["capture_id"])
    before = ledger.read_bytes()
    monkeypatch.setattr(raw_storage, "_ledger_write", lambda fd, data: os.write(fd, data[:7]))
    with pytest.raises(OSError, match="short write"):
        store.append_storage_event(restore_event(capture_id))
    assert ledger.read_bytes() == before
    monkeypatch.undo()
    assert store.append_storage_event(restore_event(capture_id)).ledger_seq == 3


def test_failed_rollback_is_an_integrity_failure_and_leaves_bytes(
    ledger: Path, store: RawCaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    capture_id = str(store.read_storage_events()[0].body["capture_id"])
    before = ledger.read_bytes()

    def failing_truncate(_fd: int, _size: int) -> None:
        raise OSError(errno.EIO, "I/O error")

    monkeypatch.setattr(raw_storage, "_ledger_write", lambda fd, data: os.write(fd, data[:7]))
    monkeypatch.setattr(raw_storage, "_ledger_truncate", failing_truncate)
    with pytest.raises(RawIntegrityError, match="could not be rolled back"):
        store.append_storage_event(restore_event(capture_id))
    assert ledger.read_bytes().startswith(before)
    assert len(ledger.read_bytes()) == len(before) + 7


def test_storage_event_fields_are_closed_per_type() -> None:
    capture_id = "20261013T034021.123456Z_" + "0" * 32
    with pytest.raises(ValueError, match="needs object_sha256"):
        StorageEvent(
            event_type=StorageEventType.BACKUP_VERIFIED,
            capture_id=capture_id,
            occurred_at=T0,
            backup_policy_id="p",
        )
    with pytest.raises(ValueError, match="takes only restored_sha256"):
        StorageEvent(
            event_type=StorageEventType.RESTORE_VERIFIED,
            capture_id=capture_id,
            occurred_at=T0,
            restored_sha256="2" * 64,
            object_sha256="1" * 64,
        )
    assert parse_storage_events(b"") == []


# ----- permissions, logging, provenance -----


def test_permissions_through_the_lifecycle(root: Path, store: RawCaptureStore) -> None:
    capture = capture_with(store, [b"abc"])
    active = root / ".inprogress" / capture.capture_id
    assert mode(active) == 0o700
    assert mode(active / "records.pmvraw.partial") == 0o600
    assert mode(root / ".capture_ids" / capture.capture_id) == 0o600
    manifest = capture.finalize()
    directory = final_dir(root, manifest.capture_id)
    assert mode(directory) == 0o500
    assert mode(directory / "records.pmvraw") == 0o400
    assert mode(directory / "manifest.json") == 0o400
    for managed in (".capture_ids", ".inprogress", "quarantine", "raw", "catalog"):
        assert mode(root / managed) == 0o700
    assert mode(root / "catalog" / "captures.v1.jsonl") == 0o600


def _reset_logging() -> None:
    logger = logging.getLogger("pmv")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def test_logs_never_contain_payloads_or_exception_text(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = b"SENSITIVE-PAYLOAD-MARKER"
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        with open_store(root) as store:
            manifest = capture_with(store, [marker, b"\x00" + marker]).finalize()
            capture = capture_with(store, [marker])

            def failing(fd: int, data: bytes) -> None:
                raise OSError(errno.EIO, "I/O error SENSITIVE-PAYLOAD-MARKER")

            monkeypatch.setattr(raw_storage, "_write_all", failing)
            with pytest.raises(OSError, match="I/O error"):
                capture.append_payload(marker, received_at=T0)
            monkeypatch.undo()
            capture.quarantine(QuarantineReason.WRITE_FAILURE)
            store.recover_incomplete()
            store.reconcile()
            assert store.verify_capture(manifest.capture_id)
    finally:
        _reset_logging()
    output = buffer.getvalue()
    assert "SENSITIVE-PAYLOAD-MARKER" not in output
    records = [json.loads(line) for line in output.splitlines()]
    assert records
    assert all(record["event"] != "log.invalid_event" for record in records)
    assert {"raw.capture_started", "raw.capture_finalized", "raw.write_failed"} <= {
        record["event"] for record in records
    }


def test_runtime_provenance_identifies_code_without_hostname(tmp_path: Path) -> None:
    config = load_config(REPO / "configs" / "test.toml", Environment.TEST)
    provenance = collect_runtime_provenance(config, repo_root=REPO)
    assert provenance.code_commit is not None
    assert isinstance(provenance.code_tree_dirty, bool)
    assert provenance.platform.startswith("linux-")
    assert os.uname().nodename not in repr(provenance)
    outside = collect_runtime_provenance(config, repo_root=tmp_path)
    assert (outside.code_commit, outside.code_tree_dirty) == (None, None)


def _scratch_git(repo: Path, *arguments: str) -> str:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(repo.parent),
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    completed = subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(repo), *arguments],
        env=environment,
        capture_output=True,
        check=True,
    )
    return completed.stdout.decode().strip()


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _scratch_git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n", encoding="ascii")
    _scratch_git(repo, "add", "-A")
    _scratch_git(repo, "commit", "-q", "-m", "a")
    (repo / "b.txt").write_text("b\n", encoding="ascii")
    _scratch_git(repo, "add", "-A")
    _scratch_git(repo, "commit", "-q", "-m", "b")
    return repo


def test_f20_a_clean_scratch_repository_has_a_known_identity(scratch_repo: Path) -> None:
    head = _scratch_git(scratch_repo, "rev-parse", "HEAD")
    assert raw_storage._git_identity(scratch_repo) == (head, False)


def test_f20_a_replace_ref_cannot_spoof_the_raw_capture_code_identity(
    scratch_repo: Path,
) -> None:
    # Step 11 red-team finding 1: a replace ref made a dirty tree report as clean HEAD.
    head = _scratch_git(scratch_repo, "rev-parse", "HEAD")
    (scratch_repo / "evil.md").write_text("not in HEAD\n", encoding="ascii")
    _scratch_git(scratch_repo, "add", "-A")
    tree = _scratch_git(scratch_repo, "write-tree")
    fake = _scratch_git(scratch_repo, "commit-tree", tree, "-p", head, "-m", "fake")
    _scratch_git(scratch_repo, "replace", head, fake)
    assert raw_storage._git_identity(scratch_repo) == (None, None)
    _scratch_git(scratch_repo, "pack-refs", "--all")
    assert raw_storage._git_identity(scratch_repo) == (None, None)
    _scratch_git(scratch_repo, "replace", "-d", head)
    assert raw_storage._git_identity(scratch_repo) == (head, True)


def test_f20_grafts_and_shallow_history_make_the_raw_capture_identity_unknown(
    scratch_repo: Path, tmp_path: Path
) -> None:
    grafts = scratch_repo / ".git" / "info" / "grafts"
    grafts.parent.mkdir(exist_ok=True)
    grafts.write_text(_scratch_git(scratch_repo, "rev-parse", "HEAD") + "\n", encoding="ascii")
    assert raw_storage._git_identity(scratch_repo) == (None, None)
    grafts.unlink()
    shallow = tmp_path / "shallow"
    _scratch_git(tmp_path, "clone", "-q", "--depth=1", f"file://{scratch_repo}", str(shallow))
    assert raw_storage._git_identity(shallow) == (None, None)


# ----- crash fault injection (a real child process killed at each boundary) -----

CHILD = """
import os, sys
from datetime import UTC, datetime
from pathlib import Path
from pmv.config import Environment, RawStorageConfig
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport
from pmv.raw_storage import QuarantineReason, RawCaptureStore

root, repo, point, action = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]

def hook(name):
    if name == point:
        os._exit(70)

config = RawStorageConfig(root=root, warning_free_bytes=1000, hard_stop_free_bytes=100)
provenance = RuntimeProvenance(
    code_commit=None, code_tree_dirty=None, config_source_sha256="0" * 64,
    raw_config_sha256=config.canonical_sha256(), environment=Environment.TEST,
    python_version="3.13.5", platform="linux-x86_64", machine_label=None, parents=(),
)
store = RawCaptureStore(
    config, provenance, repo_root=repo, free_bytes=lambda: 10**12, fault_hook=hook
)
source = SourceIdentity(
    source_id="unit_source", feed_id="unit_feed", transport=Transport.WEBSOCKET,
    endpoint_id="unit_ws",
)
capture = store.start_capture(source, datetime.now(UTC))
capture.append_payload(b"\\x00crash test payload\\n", received_at=datetime.now(UTC))
if action == "finalize":
    capture.finalize()
else:
    capture.quarantine(QuarantineReason.REQUESTED)
os._exit(0)
"""

BEFORE_MOVE = [
    "start.in_progress_created",
    "start.opened",
    "start.locked",
    "finalize.raw_synced",
    "finalize.raw_verified",
    "finalize.raw_renamed",
    "finalize.manifest_written",
    "finalize.manifest_renamed",
    "finalize.files_read_only",
    "finalize.destination_ready",
]
AFTER_MOVE = ["finalize.moved", "finalize.read_only", "finalize.before_catalog"]


def crash_child(root: Path, point: str, action: str = "finalize") -> int:
    completed = subprocess.run(  # noqa: S603 - runs this interpreter with a fixed test script
        [sys.executable, "-I", "-c", CHILD, str(root), str(REPO), point, action],
        capture_output=True,
        timeout=120,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    return completed.returncode


def only_capture_id(root: Path) -> str:
    (capture_id,) = os.listdir(root / ".capture_ids")
    return capture_id


def test_crash_after_reservation_reports_reserved_no_data(root: Path) -> None:
    assert crash_child(root, "start.reserved") == 70
    with open_store(root) as store:
        assert [r.outcome for r in store.recover_incomplete()] == [RecoveryOutcome.RESERVED_NO_DATA]
        assert store.reconcile().added == ()


@pytest.mark.parametrize("point", BEFORE_MOVE)
def test_crash_before_the_final_move_is_quarantined_never_finalized(root: Path, point: str) -> None:
    assert crash_child(root, point) == 70
    capture_id = only_capture_id(root)
    assert not final_dir(root, capture_id).exists()
    with open_store(root) as store:
        with pytest.raises(RawIntegrityError, match="not finalized"):
            store.verify_capture(capture_id)
        results = store.recover_incomplete()
        assert [(r.capture_id, r.outcome) for r in results] == [
            (capture_id, RecoveryOutcome.QUARANTINED)
        ]
        assert store.reconcile().added == ()
    assert (root / "quarantine" / capture_id / "quarantine.json").is_file()
    assert os.listdir(root / ".inprogress") == []


@pytest.mark.parametrize("point", AFTER_MOVE)
def test_crash_after_the_final_move_is_a_valid_finalized_capture(root: Path, point: str) -> None:
    assert crash_child(root, point) == 70
    capture_id = only_capture_id(root)
    with open_store(root) as store:
        assert store.recover_incomplete() == []
        before = store.verify_capture(capture_id)
        assert before.directory_read_only is (point != "finalize.moved")
        result = store.reconcile()
        assert result.added == (capture_id,)
        assert result.mode_tightened == (() if point != "finalize.moved" else (capture_id,))
        assert store.verify_capture(capture_id).directory_read_only
        assert store.reconcile() == raw_storage.ReconcileResult((), (), ())


def test_crash_after_quarantine_record_completes_the_quarantine(root: Path) -> None:
    assert crash_child(root, "quarantine.record_written", action="quarantine") == 70
    capture_id = only_capture_id(root)
    with open_store(root) as store:
        assert [r.outcome for r in store.recover_incomplete()] == [RecoveryOutcome.QUARANTINED]
    record = json.loads((root / "quarantine" / capture_id / "quarantine.json").read_bytes())
    assert record["reason"] == "requested"


def test_crash_after_quarantine_move_needs_no_recovery(root: Path) -> None:
    assert crash_child(root, "quarantine.moved", action="quarantine") == 70
    capture_id = only_capture_id(root)
    with open_store(root) as store:
        assert store.recover_incomplete() == []
    assert (root / "quarantine" / capture_id).is_dir()


def test_normal_child_run_finalizes(root: Path) -> None:
    assert crash_child(root, "never", action="finalize") == 0
    capture_id = only_capture_id(root)
    with open_store(root) as store:
        assert store.verify_capture(capture_id).directory_read_only
        assert capture_id in store.read_catalog().entries
