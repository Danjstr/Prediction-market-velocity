"""F-33: a real child process is killed at every durable boundary of the v2 capture store.

After each kill, a fresh store runs recovery (and salvage where applicable) and the test
checks that every frame either is accepted exactly once, or is refused or salvaged under
the explicit F-11 rule, and that no ambiguous state reads as a valid capture.

Each test builds its own temporary root; nothing depends on ambient state. These are
process-crash tests: the kernel keeps written bytes, so they do not model power loss.
"""

import hashlib
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from pmv.capture_format import PayloadFrame, TailDisposition
from pmv.capture_store import (
    FAULT_POINTS,
    CaptureStore,
    RecoveryOutcome,
    SalvageRefusedError,
    SegmentKind,
    SessionStatus,
    segment_id,
)
from pmv.config import Environment, RawStorageConfig
from pmv.raw_manifest import RuntimeProvenance

REPO = Path(__file__).resolve().parents[2]
DOMAIN = "d" * 32

CHILD = """
import os, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from pmv.capture_environment import authorize_capture
from pmv.capture_format import VenueEnvironment
from pmv.capture_store import CaptureStore, QuarantineReason, SegmentPolicy, segment_id
from pmv.config import Environment, RawStorageConfig
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport

root, repo, point, action = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
name, _, count = point.partition("@")
remaining = [int(count or "1")]

def hook(reached):
    if reached == name:
        remaining[0] -= 1
        if remaining[0] == 0:
            os._exit(70)

config = RawStorageConfig(root=root, warning_free_bytes=1000, hard_stop_free_bytes=100)
provenance = RuntimeProvenance(
    code_commit=None, code_tree_dirty=None, config_source_sha256="0" * 64,
    raw_config_sha256=config.canonical_sha256(), environment=Environment.TEST,
    python_version="3.13.5", platform="linux-x86_64", machine_label=None, parents=(),
)
source = SourceIdentity(
    source_id="unit_source", feed_id="unit_feed", transport=Transport.WEBSOCKET,
    endpoint_id="unit_ws",
)
grant = authorize_capture(
    deployment_environment=Environment.TEST, venue_environment=VenueEnvironment.SYNTHETIC,
    host="feed.pmv.example", endpoint_id="unit_ws", store_root=root,
    protected_base=root.parent / "protected-base",
)
frames = 4 if action == "rollover" else 10**6
policy = SegmentPolicy(
    max_segment_bytes=10**8, max_segment_frames=frames, max_segment_duration_ns=10**15
)
live_hook = None if action in ("salvage", "artifact") else hook
store = CaptureStore(
    config, provenance, repo_root=repo, clock_domain="d" * 32,
    free_bytes=lambda: 10**12, fault_hook=live_hook,
)
t0 = datetime(2026, 10, 16, 12, tzinfo=UTC)
session = store.start_session(grant, source, policy, t0)
connection = session.open_connection()
for n in range(3):
    session.append_inbound(
        b"payload-%d" % n, connection=connection, observed_at=t0 + timedelta(seconds=n),
        monotonic_ns=1000 + n,
    )
if action in ("single", "rollover"):
    session.close_connection(connection)
    session.close()
elif action == "quarantine":
    session.quarantine(QuarantineReason.REQUESTED)
elif action == "salvage":
    session._abandon()
    store.recover()
    store._fault_hook = hook
    store.salvage(segment_id(session.session_id, 0))
elif action == "artifact":
    session.close_connection(connection)
    session.close()
    store._fault_hook = hook
    store.write_artifact(session.session_id, "e" * 64, {"a.json": b"{}\\n"})
os._exit(0)
"""

BEFORE_HEADER = ["segment.dir_created", "segment.locked"]
UNFINALIZED = [
    "segment.header_written",
    "frame.written@1",
    "frame.written@3",
    "finalize.synced",
    "finalize.verified",
    "finalize.object_renamed",
    "finalize.manifest_written",
    "finalize.manifest_renamed",
    "finalize.files_read_only",
    "finalize.destination_ready",
]
FINALIZED = ["finalize.moved", "finalize.read_only"]


def crash(root: Path, point: str, action: str) -> int:
    completed = subprocess.run(  # noqa: S603 - runs this interpreter with a fixed test script
        [sys.executable, "-I", "-c", CHILD, str(root), str(REPO), point, action],
        capture_output=True,
        timeout=120,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    assert b"Traceback" not in completed.stderr, completed.stderr.decode(errors="replace")[-2000:]
    return completed.returncode


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "raw-root"
    path.mkdir(mode=0o700)
    yield path
    for directory, _subdirs, _files in os.walk(path):
        os.chmod(directory, 0o700)


def open_store(root: Path) -> CaptureStore:
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
    return CaptureStore(
        config, provenance, repo_root=REPO, clock_domain=DOMAIN, free_bytes=lambda: 10**12
    )


def only_session(root: Path) -> str:
    (session_id,) = os.listdir(root / "capture" / "v2" / "sessions")
    return session_id


def payloads(store: CaptureStore, session_id: str) -> list[bytes]:
    read = store.read_session(session_id)
    return [f.payload for _i, f in store.iter_frames(read) if isinstance(f, PayloadFrame)]


def test_every_named_fault_point_is_exercised() -> None:
    covered = {point.partition("@")[0] for point in BEFORE_HEADER + UNFINALIZED + FINALIZED}
    covered |= {
        "session.reserved",
        "rollover.previous_finalized",
        "quarantine.record_written",
        "quarantine.moved",
        "salvage.staged",
        "salvage.record_written",
        "salvage.moved",
        "artifact.staged",
        "artifact.moved",
    }
    assert covered == set(FAULT_POINTS)


def test_a_normal_child_run_completes(root: Path) -> None:
    assert crash(root, "never", "single") == 0
    with open_store(root) as store:
        session_id = only_session(root)
        assert store.read_session(session_id).status is SessionStatus.COMPLETE
        assert payloads(store, session_id) == [b"payload-0", b"payload-1", b"payload-2"]


def test_a_crash_after_reservation_leaves_an_empty_truncated_session(root: Path) -> None:
    assert crash(root, "session.reserved", "single") == 70
    with open_store(root) as store:
        assert store.recover() == []
        read = store.read_session(only_session(root))
        assert read.status is SessionStatus.TRUNCATED
        assert read.segments == ()


@pytest.mark.parametrize("point", BEFORE_HEADER)
def test_a_crash_before_the_header_is_quarantined_and_unsalvageable(root: Path, point: str) -> None:
    assert crash(root, point, "single") == 70
    session_id = only_session(root)
    name = segment_id(session_id, 0)
    with open_store(root) as store:
        assert [(r.name, r.outcome) for r in store.recover()] == [
            (name, RecoveryOutcome.QUARANTINED)
        ]
        with pytest.raises(SalvageRefusedError):
            store.salvage(name)
        read = store.read_session(session_id)
        assert read.status is SessionStatus.TRUNCATED
        assert read.segments == ()


@pytest.mark.parametrize("point", UNFINALIZED)
def test_a_crash_before_the_final_move_is_never_accepted(root: Path, point: str) -> None:
    assert crash(root, point, "single") == 70
    session_id = only_session(root)
    name = segment_id(session_id, 0)
    with open_store(root) as store:
        assert store.read_session(session_id).segments == ()
        assert [(r.name, r.outcome) for r in store.recover()] == [
            (name, RecoveryOutcome.QUARANTINED)
        ]
        assert store.recover() == []
        record = store.salvage(name)
        read = store.read_session(session_id)
        assert read.status is SessionStatus.ENDS_WITH_SALVAGE
        assert [ref.kind for ref in read.segments] == [SegmentKind.SALVAGED]
        # every complete frame the child wrote is kept, and nothing else
        expected = {
            "segment.header_written": 0,
            "frame.written@1": 0,
            "frame.written@3": 2,
        }.get(point, 3)
        assert payloads(store, session_id) == [b"payload-%d" % n for n in range(expected)]
        assert record.tail is TailDisposition.NONE


@pytest.mark.parametrize("point", FINALIZED)
def test_a_crash_after_the_final_move_is_accepted_exactly_once(root: Path, point: str) -> None:
    assert crash(root, point, "single") == 70
    session_id = only_session(root)
    with open_store(root) as store:
        assert store.recover() == []
        read = store.read_session(session_id)
        assert read.status is SessionStatus.COMPLETE
        assert [ref.kind for ref in read.segments] == [SegmentKind.FINALIZED]
        assert payloads(store, session_id) == [b"payload-0", b"payload-1", b"payload-2"]
        tightened = store.reconcile()
        assert len(tightened) == (1 if point == "finalize.moved" else 0)
        assert store.reconcile() == []
        assert not (root / "capture" / "v2" / "quarantine" / segment_id(session_id, 0)).exists()


@pytest.mark.parametrize(
    "point", ["finalize.verified", "finalize.moved", "rollover.previous_finalized"]
)
def test_a_crash_during_rollover_never_bridges_into_the_next_segment(
    root: Path, point: str
) -> None:
    assert crash(root, point, "rollover") == 70
    session_id = only_session(root)
    with open_store(root) as store:
        recovered = store.recover()
        for result in recovered:
            store.salvage(result.name or "")
        read = store.read_session(session_id)
        assert read.status in (SessionStatus.TRUNCATED, SessionStatus.ENDS_WITH_SALVAGE)
        assert read.segments[0].index == 0
        got = payloads(store, session_id)
        assert got == [b"payload-%d" % n for n in range(len(got))]
        if point != "finalize.verified":
            # segment 0 was finalized; nothing after it exists
            assert read.status is SessionStatus.TRUNCATED
            assert [ref.kind for ref in read.segments] == [SegmentKind.FINALIZED]


def test_a_crash_after_the_quarantine_record_completes_the_quarantine(root: Path) -> None:
    assert crash(root, "quarantine.record_written", "quarantine") == 70
    session_id = only_session(root)
    name = segment_id(session_id, 0)
    with open_store(root) as store:
        assert [r.outcome for r in store.recover()] == [RecoveryOutcome.QUARANTINED]
    record = (root / "capture" / "v2" / "quarantine" / name / "quarantine.json").read_text()
    assert '"reason":"requested"' in record


def test_a_crash_after_the_quarantine_move_needs_no_recovery(root: Path) -> None:
    assert crash(root, "quarantine.moved", "quarantine") == 70
    with open_store(root) as store:
        assert store.recover() == []
        name = segment_id(only_session(root), 0)
        assert store.salvage(name).tail is TailDisposition.NONE


@pytest.mark.parametrize("point", ["salvage.staged", "salvage.record_written"])
def test_an_interrupted_salvage_is_reported_and_can_be_repeated(root: Path, point: str) -> None:
    assert crash(root, point, "salvage") == 70
    session_id = only_session(root)
    name = segment_id(session_id, 0)
    with open_store(root) as store:
        assert [r.outcome for r in store.recover()] == [RecoveryOutcome.STALE_STAGING]
        assert store.read_session(session_id).status is SessionStatus.TRUNCATED
        store.salvage(name)
        read = store.read_session(session_id)
        assert read.status is SessionStatus.ENDS_WITH_SALVAGE
        assert payloads(store, session_id) == [b"payload-0", b"payload-1", b"payload-2"]


def test_a_salvage_interrupted_after_its_move_is_complete(root: Path) -> None:
    assert crash(root, "salvage.moved", "salvage") == 70
    session_id = only_session(root)
    with open_store(root) as store:
        assert store.recover() == []
        assert store.read_session(session_id).status is SessionStatus.ENDS_WITH_SALVAGE
        store.salvage(segment_id(session_id, 0))


@pytest.mark.parametrize(
    ("point", "written_again"), [("artifact.staged", True), ("artifact.moved", False)]
)
def test_an_interrupted_artifact_write_is_never_half_visible(
    root: Path, point: str, written_again: bool
) -> None:
    assert crash(root, point, "artifact") == 70
    session_id = only_session(root)
    with open_store(root) as store:
        outcomes = [r.outcome for r in store.recover()]
        assert outcomes == ([RecoveryOutcome.STALE_STAGING] if written_again else [])
        assert store.write_artifact(session_id, "e" * 64, {"a.json": b"{}\n"}) is written_again
        assert store.read_artifact(session_id, "e" * 64) == {"a.json": b"{}\n"}


def test_a_torn_frame_write_keeps_only_whole_frames(root: Path) -> None:
    """An interrupted write leaves part of a frame; salvage stops before it."""
    assert crash(root, "frame.written@3", "single") == 70
    session_id = only_session(root)
    name = segment_id(session_id, 0)
    partial = root / "capture" / "v2" / "open" / name / "segment.pmvraw.partial"
    data = partial.read_bytes()
    partial.write_bytes(data[:-4])
    with open_store(root) as store:
        store.recover()
        record = store.salvage(name)
        assert record.tail is TailDisposition.INCOMPLETE_FRAME
        assert payloads(store, session_id) == [b"payload-0"]
        assert record.document["source_object"] == {
            "name": "segment.pmvraw.partial",
            "sha256": hashlib.sha256(data[:-4]).hexdigest(),
            "size_bytes": len(data) - 4,
        }
