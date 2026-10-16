"""Tests for the segmented v2 capture store (F-11 segmentation and salvage, F-12, F-33).

Every store, root, clock, and environment fact is constructed by each test in a temporary
directory. Crash tests that kill real processes are in
``tests/failure_injection/test_capture_crash_points.py``.
"""

import hashlib
import io
import os
import stat
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import pmv.capture_store as capture_store
from pmv import safe_fs
from pmv.capture_environment import CaptureAuthorization, CaptureEnvironmentError, authorize_capture
from pmv.capture_format import (
    MAGIC,
    Direction,
    EventFrame,
    EventType,
    PayloadFrame,
    SegmentHeader,
    SegmentReader,
    TailDisposition,
    VenueEnvironment,
)
from pmv.capture_store import (
    CaptureClosedError,
    CaptureIntegrityError,
    CaptureSession,
    CaptureStore,
    CaptureStoreError,
    DiskHardStopError,
    OversizePayloadError,
    QuarantineReason,
    RecoveryOutcome,
    SalvageRefusedError,
    SegmentEnd,
    SegmentKind,
    SegmentPolicy,
    SessionStatus,
    segment_id,
)
from pmv.config import Environment, RawStorageConfig
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport
from pmv.raw_storage import RawCaptureStore

REPO = Path(__file__).resolve().parents[2]
DOMAIN = "d" * 32
HOST = "feed.pmv.example"
SOURCE = SourceIdentity(
    source_id="unit_source",
    feed_id="unit_feed",
    transport=Transport.WEBSOCKET,
    endpoint_id="unit_ws",
)
T0 = datetime(2026, 10, 16, 12, 0, 0, 123456, tzinfo=UTC)
WIDE = SegmentPolicy(
    max_segment_bytes=10**8, max_segment_frames=10**6, max_segment_duration_ns=10**15
)
PLENTY = 10**12


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=1)
        return self.now


class Monotonic:
    def __init__(self) -> None:
        self.now = 1_000_000

    def __call__(self) -> int:
        self.now += 1_000
        return self.now


def make_config(root: Path) -> RawStorageConfig:
    return RawStorageConfig(root=root, warning_free_bytes=1_000, hard_stop_free_bytes=100)


def make_provenance(
    config: RawStorageConfig, environment: Environment = Environment.TEST
) -> RuntimeProvenance:
    return RuntimeProvenance(
        code_commit=None,
        code_tree_dirty=None,
        config_source_sha256="0" * 64,
        raw_config_sha256=config.canonical_sha256(),
        environment=environment,
        python_version="3.13.5",
        platform="linux-x86_64",
        machine_label=None,
        parents=(),
    )


def open_store(
    root: Path,
    *,
    free: Callable[[], int] = lambda: PLENTY,
    monotonic: Callable[[], int] | None = None,
    environment: Environment = Environment.TEST,
) -> CaptureStore:
    config = make_config(root)
    return CaptureStore(
        config,
        make_provenance(config, environment),
        repo_root=REPO,
        clock_domain=DOMAIN,
        clock=Clock(),
        monotonic_ns=monotonic or Monotonic(),
        free_bytes=free,
    )


def grant(root: Path) -> CaptureAuthorization:
    return authorize_capture(
        deployment_environment=Environment.TEST,
        venue_environment=VenueEnvironment.SYNTHETIC,
        host=HOST,
        endpoint_id=SOURCE.endpoint_id,
        store_root=root,
        protected_base=root.parent / "protected-base",
    )


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "raw-root"
    path.mkdir(mode=0o700)
    yield path
    for directory, _subdirs, _files in os.walk(path):
        os.chmod(directory, 0o700)


@pytest.fixture
def store(root: Path) -> Iterator[CaptureStore]:
    with open_store(root) as opened:
        yield opened


def start(store: CaptureStore, root: Path, policy: SegmentPolicy = WIDE) -> CaptureSession:
    return store.start_session(grant(root), SOURCE, policy, T0)


def receive(session: CaptureSession, payload: bytes, connection: int, n: int) -> None:
    session.append_inbound(
        payload,
        connection=connection,
        observed_at=T0 + timedelta(seconds=n),
        monotonic_ns=10_000_000 + n,
    )


def capture(
    store: CaptureStore, root: Path, payloads: list[bytes], policy: SegmentPolicy = WIDE
) -> str:
    session = start(store, root, policy)
    connection = session.open_connection()
    for n, payload in enumerate(payloads):
        receive(session, payload, connection, n)
    session.close_connection(connection)
    session.close()
    return session.session_id


def frames_of(store: CaptureStore, session_id: str) -> list[object]:
    return [frame for _index, frame in store.iter_frames(store.read_session(session_id))]


def layout(root: Path) -> Path:
    return root / "capture" / "v2"


def segment_dir(root: Path, session_id: str, index: int) -> Path:
    return (
        layout(root)
        / "segments"
        / "unit_source"
        / "unit_feed"
        / session_id[0:4]
        / session_id[4:6]
        / session_id[6:8]
        / session_id
        / f"{index:06d}"
    )


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# ----- the basic lifecycle -----


def test_payload_bytes_direction_and_times_are_preserved(root: Path, store: CaptureStore) -> None:
    session = start(store, root)
    connection = session.open_connection()
    session.append_outbound(
        b'{"cmd":"subscribe"}', connection=connection, observed_at=T0, monotonic_ns=5
    )
    session.append_inbound(
        b"\x00exact\xffbytes",
        connection=connection,
        observed_at=T0 + timedelta(seconds=1),
        monotonic_ns=7,
        source_timestamp=T0,
    )
    session.close()
    frames = frames_of(store, session.session_id)
    assert isinstance(frames[0], SegmentHeader)
    assert frames[0].venue_environment is VenueEnvironment.SYNTHETIC
    assert frames[0].clock_domain == DOMAIN
    outbound, inbound = frames[2], frames[3]
    assert isinstance(outbound, PayloadFrame)
    assert outbound.direction is Direction.OUTBOUND
    assert outbound.payload == b'{"cmd":"subscribe"}'
    assert isinstance(inbound, PayloadFrame)
    assert inbound.direction is Direction.INBOUND
    assert inbound.payload == b"\x00exact\xffbytes"
    assert inbound.monotonic_ns == 7
    assert inbound.source_timestamp == "2026-10-16T12:00:00.123456Z"
    assert inbound.observed_at == "2026-10-16T12:00:01.123456Z"
    assert [frame.sequence for frame in frames] == list(range(len(frames)))  # type: ignore[attr-defined]
    final = frames[-1]
    assert isinstance(final, EventFrame)
    assert final.event_type is EventType.SESSION_CLOSED


def test_a_closed_session_is_complete_and_read_only(root: Path, store: CaptureStore) -> None:
    session_id = capture(store, root, [b"a", b"b"])
    read = store.read_session(session_id)
    assert read.status is SessionStatus.COMPLETE
    assert [ref.kind for ref in read.segments] == [SegmentKind.FINALIZED]
    directory = segment_dir(root, session_id, 0)
    assert mode(directory) == 0o500
    assert mode(directory / "segment.pmvraw") == 0o400
    assert mode(directory / "manifest.json") == 0o400
    assert os.listdir(layout(root) / "open") == []


@pytest.mark.parametrize(
    "policy",
    [
        SegmentPolicy(
            max_segment_bytes=10**8, max_segment_frames=3, max_segment_duration_ns=10**15
        ),
        SegmentPolicy(
            max_segment_bytes=400, max_segment_frames=10**6, max_segment_duration_ns=10**15
        ),
        SegmentPolicy(
            max_segment_bytes=10**8, max_segment_frames=10**6, max_segment_duration_ns=2_500
        ),
    ],
    ids=["frames", "bytes", "duration"],
)
def test_segments_roll_over_and_chain_without_loss(
    root: Path, store: CaptureStore, policy: SegmentPolicy
) -> None:
    payloads = [f"payload-{n}".encode() for n in range(12)]
    session_id = capture(store, root, payloads, policy)
    read = store.read_session(session_id)
    assert read.status is SessionStatus.COMPLETE
    assert len(read.segments) > 2
    for previous, current in zip(read.segments, read.segments[1:], strict=False):
        assert current.header.previous_segment_sha256 == previous.sha256
        assert current.first_sequence == previous.last_sequence + 1
    frames = frames_of(store, session_id)
    assert [f.payload for f in frames if isinstance(f, PayloadFrame)] == payloads
    headers = [f for f in frames if isinstance(f, SegmentHeader)]
    assert [h.segment_index for h in headers] == list(range(len(read.segments)))


def test_rollover_bounds_are_explicit() -> None:
    with pytest.raises(ValueError, match="positive"):
        SegmentPolicy(max_segment_bytes=0, max_segment_frames=10, max_segment_duration_ns=10)
    with pytest.raises(ValueError, match="header and one frame"):
        SegmentPolicy(max_segment_bytes=10, max_segment_frames=1, max_segment_duration_ns=10)
    with pytest.raises(ValueError, match="segment bound"):
        SegmentPolicy(
            max_segment_bytes=capture_store.MAX_SEGMENT_BYTES + 1,
            max_segment_frames=10,
            max_segment_duration_ns=10,
        )


# ----- integrity -----


def test_a_changed_byte_in_any_segment_is_detected(root: Path, store: CaptureStore) -> None:
    policy = SegmentPolicy(
        max_segment_bytes=10**8, max_segment_frames=3, max_segment_duration_ns=10**15
    )
    session_id = capture(store, root, [b"one", b"two", b"three", b"four"], policy)
    target = segment_dir(root, session_id, 1) / "segment.pmvraw"
    target.chmod(0o600)
    data = bytearray(target.read_bytes())
    data[-3] ^= 0x01
    target.write_bytes(bytes(data))
    target.chmod(0o400)
    with pytest.raises(CaptureIntegrityError):
        store.read_session(session_id)


def test_a_missing_middle_segment_is_never_bridged(root: Path, store: CaptureStore) -> None:
    policy = SegmentPolicy(
        max_segment_bytes=10**8, max_segment_frames=3, max_segment_duration_ns=10**15
    )
    session_id = capture(store, root, [b"1", b"2", b"3", b"4", b"5"], policy)
    total = len(store.read_session(session_id).segments)
    victim = segment_dir(root, session_id, 1)
    victim.chmod(0o700)
    for item in victim.iterdir():
        item.unlink()
    victim.rmdir()
    read = store.read_session(session_id)
    assert read.status is SessionStatus.TRUNCATED
    assert [ref.index for ref in read.segments] == [0]
    assert read.unreachable_indices == tuple(range(2, total))


def test_a_segment_from_another_session_is_refused(root: Path, store: CaptureStore) -> None:
    policy = SegmentPolicy(
        max_segment_bytes=10**8, max_segment_frames=3, max_segment_duration_ns=10**15
    )
    first = capture(store, root, [b"1", b"2", b"3"], policy)
    second = capture(store, root, [b"x", b"y", b"z"], policy)
    # replace session one's segment 1 with session two's segment 1
    mine, theirs = segment_dir(root, first, 1), segment_dir(root, second, 1)
    mine.chmod(0o700)
    theirs.chmod(0o700)
    for name in ("segment.pmvraw", "manifest.json"):
        (mine / name).unlink()
        (mine / name).write_bytes((theirs / name).read_bytes())
    with pytest.raises(CaptureIntegrityError):
        store.read_session(first)


def test_iteration_rechecks_every_byte(root: Path, store: CaptureStore) -> None:
    session_id = capture(store, root, [b"payload"])
    read = store.read_session(session_id)
    target = segment_dir(root, session_id, 0) / "segment.pmvraw"
    target.chmod(0o600)
    data = bytearray(target.read_bytes())
    data[-5] ^= 0x01
    target.write_bytes(bytes(data))
    with pytest.raises(CaptureIntegrityError):
        list(store.iter_frames(read))


def test_an_unknown_session_has_no_reservation(store: CaptureStore) -> None:
    with pytest.raises(CaptureIntegrityError, match="no reservation"):
        store.read_session("20261016T000000.000000Z_" + "0" * 32)


def test_reconcile_tightens_a_segment_left_writable(root: Path, store: CaptureStore) -> None:
    session_id = capture(store, root, [b"a"])
    segment_dir(root, session_id, 0).chmod(0o700)
    results = store.reconcile()
    assert [r.outcome for r in results] == [RecoveryOutcome.TIGHTENED]
    assert mode(segment_dir(root, session_id, 0)) == 0o500
    assert store.reconcile() == []


# ----- writer discipline -----


def test_payloads_need_an_open_connection(root: Path, store: CaptureStore) -> None:
    session = start(store, root)
    with pytest.raises(ValueError, match="not open"):
        receive(session, b"x", 0, 0)
    connection = session.open_connection()
    session.close_connection(connection)
    with pytest.raises(ValueError, match="not open"):
        receive(session, b"x", connection, 1)
    with pytest.raises(ValueError, match="not open"):
        session.close_connection(connection)
    with pytest.raises(ValueError, match="gap or rate_limit"):
        session.record_event(EventType.SESSION_CLOSED)
    session.record_event(EventType.GAP)
    second = session.open_connection()
    assert second == 1
    session.close()
    payloads = [f for f in frames_of(store, session.session_id) if isinstance(f, PayloadFrame)]
    assert payloads == []


def test_clock_regressions_are_recorded_never_repaired(root: Path, store: CaptureStore) -> None:
    session = start(store, root)
    connection = session.open_connection()
    session.append_inbound(
        b"a",
        connection=connection,
        observed_at=T0 + timedelta(seconds=5),
        monotonic_ns=500,
        source_timestamp=T0 + timedelta(seconds=5),
    )
    session.append_inbound(
        b"b", connection=connection, observed_at=T0, monotonic_ns=400, source_timestamp=T0
    )
    session.close()
    frames = frames_of(store, session.session_id)
    events = [f.event_type for f in frames if isinstance(f, EventFrame)]
    assert EventType.MONOTONIC_REGRESSION in events
    assert EventType.SOURCE_CLOCK_REGRESSION in events
    assert EventType.LOCAL_CLOCK_REGRESSION in events
    payloads = [f for f in frames if isinstance(f, PayloadFrame)]
    assert [p.payload for p in payloads] == [b"a", b"b"]  # never reordered


def test_an_oversize_payload_quarantines_the_open_segment(
    root: Path, store: CaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capture_store, "MAX_PAYLOAD_BYTES", 8)
    session = start(store, root)
    connection = session.open_connection()
    with pytest.raises(OversizePayloadError):
        receive(session, b"123456789", connection, 0)
    with pytest.raises(CaptureClosedError):
        receive(session, b"1", connection, 1)
    name = segment_id(session.session_id, 0)
    record = (layout(root) / "quarantine" / name / "quarantine.json").read_text()
    assert '"reason":"oversize_payload"' in record
    assert '"oversize_payload_bytes":9' in record
    assert store.read_session(session.session_id).status is SessionStatus.TRUNCATED


def test_a_write_failure_poisons_the_session(
    root: Path, store: CaptureStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = start(store, root)
    connection = session.open_connection()

    def failing(_fd: int, _data: bytes) -> None:
        raise OSError(28, "no space")

    monkeypatch.setattr(safe_fs, "write_all", failing)
    with pytest.raises(OSError, match="no space"):
        receive(session, b"x", connection, 0)
    monkeypatch.undo()
    with pytest.raises(CaptureClosedError):
        receive(session, b"y", connection, 1)
    with pytest.raises(CaptureClosedError, match="write failure"):
        session.close()
    session.quarantine(QuarantineReason.WRITE_FAILURE)
    assert (layout(root) / "quarantine" / segment_id(session.session_id, 0)).is_dir()


def test_disk_pressure_warns_once_and_hard_stop_closes(root: Path) -> None:
    free = [5_000]
    with open_store(root, free=lambda: free[0]) as store:
        session = start(store, root)
        connection = session.open_connection()
        free[0] = 500
        receive(session, b"a", connection, 0)
        receive(session, b"b", connection, 1)
        free[0] = 50
        with pytest.raises(DiskHardStopError) as stopped:
            receive(session, b"c", connection, 2)
        assert stopped.value.manifest is not None
        assert stopped.value.manifest.end is SegmentEnd.DISK_HARD_STOP
        with pytest.raises(CaptureClosedError):
            receive(session, b"d", connection, 3)
        frames = frames_of(store, session.session_id)
        events = [f.event_type for f in frames if isinstance(f, EventFrame)]
        assert events.count(EventType.DISK_WARNING) == 1
        assert events[-2:] == [EventType.DISK_HARD_STOP, EventType.SESSION_CLOSED]
        assert [f.payload for f in frames if isinstance(f, PayloadFrame)] == [b"a", b"b"]
        assert store.read_session(session.session_id).status is SessionStatus.COMPLETE
        with pytest.raises(DiskHardStopError):
            start(store, root)


# ----- authorization binding -----


def test_sessions_need_a_matching_authorization(root: Path, tmp_path: Path) -> None:
    with open_store(root) as store:
        with pytest.raises(CaptureEnvironmentError):
            store.start_session(object(), SOURCE, WIDE, T0)  # type: ignore[arg-type]
        other_root = tmp_path / "other"
        other_root.mkdir()
        with pytest.raises(CaptureEnvironmentError, match="another store root"):
            store.start_session(grant(other_root), SOURCE, WIDE, T0)
        other_source = SourceIdentity(
            source_id="unit_source",
            feed_id="unit_feed",
            transport=Transport.WEBSOCKET,
            endpoint_id="other_ws",
        )
        with pytest.raises(CaptureEnvironmentError, match="another endpoint"):
            store.start_session(grant(root), other_source, WIDE, T0)
    with (
        open_store(root, environment=Environment.DEVELOPMENT) as development,
        pytest.raises(CaptureEnvironmentError, match="another deployment"),
    ):
        development.start_session(grant(root), SOURCE, WIDE, T0)


def test_the_store_root_must_be_outside_the_repository(tmp_path: Path) -> None:
    config = make_config(REPO / "not-a-store")
    with pytest.raises(CaptureStoreError, match="outside the Git working tree"):
        CaptureStore(config, make_provenance(config), repo_root=REPO, clock_domain=DOMAIN)


def test_the_clock_domain_is_required(root: Path) -> None:
    config = make_config(root)
    with pytest.raises(CaptureStoreError, match="clock_domain"):
        CaptureStore(config, make_provenance(config), repo_root=REPO, clock_domain="boot")


def test_the_v1_store_and_v2_store_share_a_root_without_interference(root: Path) -> None:
    session_id = ""
    with open_store(root) as store:
        session_id = capture(store, root, [b"v2"])
    config = make_config(root)
    with RawCaptureStore(config, make_provenance(config), repo_root=REPO) as v1:
        capture_v1 = v1.start_capture(SOURCE, T0)
        capture_v1.append_payload(b"v1", received_at=T0)
        capture_v1.finalize()
        assert v1.reconcile().integrity_failures == ()
        assert v1.recover_incomplete() == []
    with open_store(root) as store:
        assert store.read_session(session_id).status is SessionStatus.COMPLETE


# ----- recovery and salvage (F-11) -----


def abandoned(store: CaptureStore, root: Path, payloads: list[bytes]) -> CaptureSession:
    """A session whose writer stopped without finalizing (as after a crash)."""
    session = start(store, root)
    connection = session.open_connection()
    for n, payload in enumerate(payloads):
        receive(session, payload, connection, n)
    session._abandon()
    return session


def test_recovery_never_touches_a_live_segment(root: Path, store: CaptureStore) -> None:
    session = start(store, root)
    results = store.recover()
    assert [r.outcome for r in results] == [RecoveryOutcome.ACTIVE]
    session.close()


def test_recovery_quarantines_and_salvage_keeps_every_complete_frame(
    root: Path, store: CaptureStore
) -> None:
    session = abandoned(store, root, [b"first", b"second", b"third"])
    name = segment_id(session.session_id, 0)
    results = store.recover()
    assert [(r.name, r.outcome) for r in results] == [(name, RecoveryOutcome.QUARANTINED)]
    assert os.listdir(layout(root) / "open") == []
    quarantined = layout(root) / "quarantine" / name / "segment.pmvraw.partial"
    # tear the last frame, as an interrupted write would
    data = quarantined.read_bytes()
    quarantined.write_bytes(data[:-3])
    before = hashlib.sha256(quarantined.read_bytes()).hexdigest()
    record = store.salvage(name)
    assert hashlib.sha256(quarantined.read_bytes()).hexdigest() == before
    assert record.tail is TailDisposition.INCOMPLETE_FRAME
    assert record.document["quarantine_reason"] == "orphaned_open_segment"
    assert record.document["rule"] == "longest_valid_frame_prefix_v1"
    read = store.read_session(session.session_id)
    assert read.status is SessionStatus.ENDS_WITH_SALVAGE
    assert [ref.kind for ref in read.segments] == [SegmentKind.SALVAGED]
    frames = [frame for _i, frame in store.iter_frames(read)]
    assert [f.payload for f in frames if isinstance(f, PayloadFrame)] == [b"first", b"second"]
    salvaged = layout(root) / "salvage" / name / "salvaged.pmvraw"
    assert salvaged.read_bytes() == data[: record.prefix_size]
    assert mode(salvaged) == 0o400


def test_salvage_is_repeatable_and_detects_a_changed_input(root: Path, store: CaptureStore) -> None:
    session = abandoned(store, root, [b"a", b"b"])
    store.recover()
    name = segment_id(session.session_id, 0)
    first = store.salvage(name)
    again = store.salvage(name)
    assert again.document == first.document
    quarantined = layout(root) / "quarantine" / name / "segment.pmvraw.partial"
    quarantined.write_bytes(quarantined.read_bytes()[:-1])
    with pytest.raises(CaptureIntegrityError, match="differs"):
        store.salvage(name)


def test_salvage_refuses_when_nothing_is_valid(root: Path, store: CaptureStore) -> None:
    session = abandoned(store, root, [b"a"])
    store.recover()
    name = segment_id(session.session_id, 0)
    quarantined = layout(root) / "quarantine" / name / "segment.pmvraw.partial"
    quarantined.write_bytes(MAGIC + b"\x00\x00")
    with pytest.raises(SalvageRefusedError, match="nothing can be salvaged"):
        store.salvage(name)
    assert not (layout(root) / "salvage" / name).exists()
    assert store.read_session(session.session_id).status is SessionStatus.TRUNCATED
    with pytest.raises(SalvageRefusedError, match="not quarantined"):
        store.salvage(segment_id(session.session_id, 1))


def test_a_complete_but_unfinalized_object_is_salvaged_never_promoted(
    root: Path, store: CaptureStore
) -> None:
    session = abandoned(store, root, [b"a"])
    store.recover()
    name = segment_id(session.session_id, 0)
    record = store.salvage(name)
    assert record.tail is TailDisposition.NONE
    read = store.read_session(session.session_id)
    assert read.status is SessionStatus.ENDS_WITH_SALVAGE
    assert not segment_dir(root, session.session_id, 0).exists()


def test_a_salvaged_segment_ends_the_chain(root: Path, store: CaptureStore) -> None:
    policy = SegmentPolicy(
        max_segment_bytes=10**8, max_segment_frames=3, max_segment_duration_ns=10**15
    )
    session = start(store, root, policy)
    connection = session.open_connection()
    for n in range(5):
        receive(session, b"p%d" % n, connection, n)
    open_index = session.segment_index
    session._abandon()
    store.recover()
    store.salvage(segment_id(session.session_id, open_index))
    read = store.read_session(session.session_id)
    assert read.status is SessionStatus.ENDS_WITH_SALVAGE
    assert [ref.kind for ref in read.segments][-1] is SegmentKind.SALVAGED
    assert [ref.index for ref in read.segments] == list(range(open_index + 1))
    payloads = [f.payload for _i, f in store.iter_frames(read) if isinstance(f, PayloadFrame)]
    assert payloads == [b"p%d" % n for n in range(5)]


def test_a_session_with_an_open_segment_reads_as_open(root: Path, store: CaptureStore) -> None:
    session = start(store, root)
    assert store.read_session(session.session_id).status is SessionStatus.OPEN
    session.close()


def test_sync_is_a_checkpoint_not_a_finalization(root: Path, store: CaptureStore) -> None:
    session = start(store, root)
    connection = session.open_connection()
    receive(session, b"x", connection, 0)
    session.sync()
    assert store.read_session(session.session_id).status is SessionStatus.OPEN
    session.close()


# ----- normalized-artifact storage -----


def test_artifacts_are_content_addressed_and_never_replaced(
    root: Path, store: CaptureStore
) -> None:
    session_id = capture(store, root, [b"x"])
    key = "e" * 64
    files = {"a.json": b"{}\n", "b.json": b"[]\n"}
    assert store.write_artifact(session_id, key, files) is True
    assert store.write_artifact(session_id, key, files) is False
    assert store.read_artifact(session_id, key) == files
    with pytest.raises(CaptureIntegrityError, match="different artifact"):
        store.write_artifact(session_id, key, {"a.json": b"{}\n", "b.json": b"[1]\n"})
    directory = layout(root) / "normalized" / session_id / key
    assert mode(directory) == 0o500
    assert mode(directory / "a.json") == 0o400


def test_segment_reader_accepts_only_whole_finalized_objects(
    root: Path, store: CaptureStore
) -> None:
    session_id = capture(store, root, [b"x"])
    data = (segment_dir(root, session_id, 0) / "segment.pmvraw").read_bytes()
    assert len(list(SegmentReader(io.BytesIO(data), len(data)).frames())) == 5
