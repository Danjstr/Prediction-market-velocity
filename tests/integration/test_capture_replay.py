"""v2 capture sessions through normalization, books, validation, and artifacts (B08).

Synthetic data only: every session is written by the test into a temporary store with the
PMV synthetic fixture format. Covers order-book continuity after rejected, malformed,
missing, duplicate, out-of-order, and solicited frames, and the normalized-artifact
lineage, determinism, idempotency, and data-use rules.
"""

import hashlib
import json
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from pmv.capture_environment import CaptureEnvironmentError, DataUse, authorize_capture
from pmv.capture_format import EventType, VenueEnvironment
from pmv.capture_store import (
    CaptureIntegrityError,
    CaptureSession,
    CaptureStore,
    SegmentPolicy,
    SessionStatus,
    segment_id,
)
from pmv.config import Environment, RawStorageConfig
from pmv.market_data.books import BookFault, OrderBook, reconstruct, reconstruct_as_of
from pmv.market_data.capture_replay import (
    ArtifactError,
    Disposition,
    NormalizedSession,
    artifact_digest,
    artifact_key,
    decode_artifact,
    encode_artifact,
    load_artifact,
    normalize_session,
    persist_artifact,
    verify_artifact,
)
from pmv.market_data.contracts import ContractSpec, Underlying, Verification, YesRegion
from pmv.market_data.events import BookLevel, Outcome, StreamEvent, StreamEventKind
from pmv.market_data.labels import ResolutionRecord
from pmv.market_data.point_in_time import ObservationLog
from pmv.market_data.replay import NormalizationContractError
from pmv.market_data.synthetic import SyntheticNormalizer
from pmv.market_data.validation import AnomalyKind, ValidationPolicy, capture_order, validate
from pmv.protected_scope import Provider
from pmv.raw_manifest import RuntimeProvenance, SourceIdentity, Transport

REPO = Path(__file__).resolve().parents[2]
OPEN = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
SPEC = ContractSpec(
    venue=Provider.PMV_SYNTHETIC,
    market_id="syn-1",
    event_id=None,
    series_id=None,
    underlying=Underlying.SYNTHETIC,
    resolution_source_id="synthetic_reference",
    resolution_rule_id="synthetic_rule_v1",
    yes_region=YesRegion(Decimal(100), False, None, False),
    open_time=OPEN,
    close_time=OPEN + timedelta(minutes=15),
    outcome_reference_time=OPEN + timedelta(minutes=15),
    rule_timezone="UTC",
    rounding_rule_id="synthetic_no_rounding",
    void_rule_id="synthetic_void_v1",
    fee_schedule_id="synthetic_fees_v1",
    fee_schedule_effective_from=OPEN,
    price_units_per_payout=100,
    quantity_units_per_contract=1,
    verification=Verification.SYNTHETIC,
    rules_source_sha256=None,
)
KEY = SPEC.spec_key
SOURCE = SourceIdentity(
    source_id="unit_source",
    feed_id="unit_feed",
    transport=Transport.WEBSOCKET,
    endpoint_id="unit_ws",
)
WIDE = SegmentPolicy(
    max_segment_bytes=10**8, max_segment_frames=10**6, max_segment_duration_ns=10**15
)
VALIDATION = ValidationPolicy(
    timedelta(seconds=1), timedelta(seconds=5), timedelta(minutes=10), "capture_replay_v1"
)


def message(**fields: object) -> bytes:
    return json.dumps(fields, separators=(",", ":")).encode()


def snapshot(seq: int, bids: Sequence[tuple[float, int]] = ((40, 5),), **extra: object) -> bytes:
    return message(
        type="book_snapshot",
        spec_key=KEY,
        outcome="yes",
        bids=[list(level) for level in bids],
        asks=[[60, 5]],
        seq=seq,
        scope="book",
        **extra,
    )


def delta(seq: int, price: int = 41, quantity: int = 3, side: str = "bid") -> bytes:
    return message(
        type="book_delta",
        spec_key=KEY,
        outcome="yes",
        side=side,
        price=price,
        quantity=quantity,
        seq=seq,
        scope="book",
    )


class Clock:
    def __init__(self) -> None:
        self.now = OPEN

    def __call__(self) -> datetime:
        self.now += timedelta(microseconds=1)
        return self.now


@pytest.fixture
def root(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "raw-root"
    path.mkdir(mode=0o700)
    yield path
    for directory, _subdirs, _files in os.walk(path):
        os.chmod(directory, 0o700)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(root: Path, clock: Clock) -> Iterator[CaptureStore]:
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
    counter = iter(range(10**6, 10**12, 1000))
    with CaptureStore(
        config,
        provenance,
        repo_root=REPO,
        clock_domain="d" * 32,
        clock=clock,
        monotonic_ns=lambda: next(counter),
        free_bytes=lambda: 10**12,
    ) as opened:
        yield opened


Step = tuple[str, object]


def run(
    store: CaptureStore,
    root: Path,
    steps: Sequence[Step],
    *,
    policy: SegmentPolicy = WIDE,
    close: bool = True,
) -> CaptureSession:
    """Write a session from steps: ("in", bytes), ("bad", bytes) flagged malformed,
    ("out", bytes), ("reconnect", None), ("gap", None)."""
    grant = authorize_capture(
        deployment_environment=Environment.TEST,
        venue_environment=VenueEnvironment.SYNTHETIC,
        host="feed.pmv.example",
        endpoint_id="unit_ws",
        store_root=root,
        protected_base=root.parent / "protected-base",
    )
    clock = store._clock
    assert isinstance(clock, Clock)
    clock.now = OPEN
    session = store.start_session(grant, SOURCE, policy, OPEN)
    connection = session.open_connection()
    for n, (kind, body) in enumerate(steps, start=1):
        moment = OPEN + timedelta(seconds=n)
        clock.now = moment
        if kind in ("in", "bad"):
            assert isinstance(body, bytes)
            session.append_inbound(
                body,
                connection=connection,
                observed_at=moment,
                monotonic_ns=n,
                malformed=kind == "bad",
            )
        elif kind == "out":
            assert isinstance(body, bytes)
            session.append_outbound(body, connection=connection, observed_at=moment, monotonic_ns=n)
        elif kind == "reconnect":
            session.close_connection(connection)
            connection = session.open_connection()
        elif kind == "gap":
            session.record_event(EventType.GAP, connection)
        else:
            raise AssertionError(kind)
    if close:
        # the session ends an hour later, after every decision time the tests examine
        clock.now = OPEN + timedelta(hours=1)
        session.close_connection(connection)
        session.close()
    return session


def normalized(store: CaptureStore, session_id: str) -> NormalizedSession:
    return normalize_session(
        store, store.read_session(session_id), SyntheticNormalizer(), use=DataUse.TEST
    )


def book(
    store: CaptureStore, root: Path, steps: Sequence[Step], **options: object
) -> OrderBook | None:
    """The book as PMV held it just after the last step, before the session closed."""
    session = run(store, root, steps, **options)  # type: ignore[arg-type]
    result = normalized(store, session.session_id)
    decision = OPEN + timedelta(seconds=len(steps), milliseconds=500)
    view = ObservationLog(result.observations).as_of(decision, min_latency=timedelta(0))
    return reconstruct_as_of(view, {KEY: SPEC}).get(session.session_id, KEY, Outcome.YES)


# ----- order-book continuity -----


def test_a_clean_stream_keeps_a_usable_book(root: Path, store: CaptureStore) -> None:
    found = book(store, root, [("in", snapshot(1)), ("in", delta(2))])
    assert found is not None
    assert found.usable
    assert found.bids == (BookLevel(41, 3), BookLevel(40, 5))


@pytest.mark.parametrize(
    "rejected",
    [
        ("bad", delta(2)),  # flagged malformed by the collector
        ("in", message(type="mystery")),  # schema rejection
        ("in", b"{not json"),  # undecodable
        ("in", delta(2, side="middle")),  # a rejected delta
        ("in", snapshot(2, bids=((40.5, 1),))),  # a rejected snapshot (floats are refused)
    ],
    ids=["malformed", "schema", "undecodable", "rejected_delta", "rejected_snapshot"],
)
def test_a_rejected_frame_breaks_the_book_until_a_new_snapshot(
    root: Path, store: CaptureStore, rejected: Step
) -> None:
    found = book(store, root, [("in", snapshot(1)), rejected, ("in", delta(3))])
    assert found is not None
    assert BookFault.FRAME_REJECTED in found.faults
    assert not found.usable
    assert found.bids == (BookLevel(40, 5),)  # the later delta was not applied
    recovered = book(
        store, root, [("in", snapshot(1)), rejected, ("in", delta(3)), ("in", snapshot(4))]
    )
    assert recovered is not None
    assert recovered.usable


def test_a_rejected_first_snapshot_leaves_no_book(root: Path, store: CaptureStore) -> None:
    session = run(store, root, [("in", snapshot(1, bids=((40.5, 1),))), ("in", delta(2))])
    result = normalized(store, session.session_id)
    books = reconstruct(ObservationLog(result.observations), {KEY: SPEC})
    assert books.get(session.session_id, KEY, Outcome.YES) is None
    report = validate(capture_order(ObservationLog(result.observations)), {KEY: SPEC}, VALIDATION)
    kinds = [anomaly.kind for anomaly in report.anomalies]
    assert AnomalyKind.STREAM_FRAME_REJECTED in kinds
    assert AnomalyKind.DELTA_WITHOUT_SNAPSHOT in kinds


@pytest.mark.parametrize(
    ("steps", "fault"),
    [
        ([("in", snapshot(1)), ("in", delta(3))], BookFault.SEQUENCE_GAP),
        ([("in", snapshot(1)), ("in", delta(2)), ("in", delta(2))], BookFault.DUPLICATE_SEQUENCE),
        ([("in", snapshot(1)), ("in", delta(3)), ("in", delta(2))], BookFault.SEQUENCE_GAP),
        (
            [("in", snapshot(1)), ("in", delta(2)), ("in", delta(1, price=39))],
            BookFault.SEQUENCE_REGRESSION,
        ),
        ([("in", snapshot(1)), ("gap", None), ("in", delta(2))], BookFault.STREAM_RESET),
        ([("in", snapshot(1)), ("reconnect", None), ("in", delta(2))], BookFault.STREAM_RESET),
    ],
    ids=["gap", "duplicate", "out_of_order", "stale", "gap_event", "reconnect"],
)
def test_known_and_uncertain_gaps_are_never_bridged(
    root: Path, store: CaptureStore, steps: list[Step], fault: BookFault
) -> None:
    found = book(store, root, steps)
    assert found is not None
    assert fault in found.faults
    assert not found.usable


def test_a_solicited_snapshot_is_not_a_recovery(root: Path, store: CaptureStore) -> None:
    broken = [("in", snapshot(1)), ("in", delta(3))]
    found = book(store, root, [*broken, ("in", snapshot(4, solicited=True))])
    assert found is not None
    assert BookFault.UNVERIFIED_SNAPSHOT in found.faults
    assert BookFault.SEQUENCE_GAP in found.faults
    clean = book(store, root, [("in", snapshot(1, solicited=True)), ("in", delta(2))])
    assert clean is not None
    assert clean.faults == frozenset({BookFault.UNVERIFIED_SNAPSHOT})
    recovered = book(
        store, root, [*broken, ("in", snapshot(4, solicited=True)), ("in", snapshot(5))]
    )
    assert recovered is not None
    assert recovered.usable


def test_segment_rollover_does_not_break_a_book(root: Path, store: CaptureStore) -> None:
    small = SegmentPolicy(
        max_segment_bytes=10**8, max_segment_frames=3, max_segment_duration_ns=10**15
    )
    steps: list[Step] = [("in", snapshot(1))]
    steps.extend(("in", delta(n, price=40 + n)) for n in range(2, 9))
    session = run(store, root, steps, policy=small)
    read = store.read_session(session.session_id)
    assert len(read.segments) > 3
    result = normalized(store, session.session_id)
    decision = OPEN + timedelta(seconds=len(steps), milliseconds=500)
    view = ObservationLog(result.observations).as_of(decision, min_latency=timedelta(0))
    found = reconstruct_as_of(view, {KEY: SPEC}).get(session.session_id, KEY, Outcome.YES)
    assert found is not None
    assert found.usable
    assert [level.price for level in found.bids] == [48, 47, 46, 45, 44, 43, 42, 40]
    assert result.count(Disposition.SEGMENT_HEADER) == len(read.segments)


def test_a_restart_after_an_uncertain_last_frame_inherits_nothing(
    root: Path, store: CaptureStore
) -> None:
    first = run(store, root, [("in", snapshot(1)), ("in", delta(2))], close=False)
    first._abandon()
    store.recover()
    name = segment_id(first.session_id, 0)
    partial = root / "capture" / "v2" / "quarantine" / name / "segment.pmvraw.partial"
    partial.parent.chmod(0o700)
    partial.chmod(0o600)
    partial.write_bytes(partial.read_bytes()[:-2])  # the last delta is torn
    store.salvage(name)
    old = normalized(store, first.session_id)
    assert old.session_status is SessionStatus.ENDS_WITH_SALVAGE
    old_books = reconstruct(ObservationLog(old.observations), {KEY: SPEC})
    old_book = old_books.get(first.session_id, KEY, Outcome.YES)
    assert old_book is not None
    assert old_book.bids == (BookLevel(40, 5),)  # the torn delta never appears
    # a new session starts from nothing: a delta without its own snapshot builds no book
    second = run(store, root, [("in", delta(3))])
    new = normalized(store, second.session_id)
    books = reconstruct(ObservationLog(old.observations + new.observations), {KEY: SPEC})
    assert books.get(second.session_id, KEY, Outcome.YES) is None


def test_outbound_messages_are_never_parsed_as_observations(
    root: Path, store: CaptureStore
) -> None:
    session = run(store, root, [("out", snapshot(1)), ("in", message(type="heartbeat"))])
    result = normalized(store, session.session_id)
    assert result.count(Disposition.OUTBOUND) == 1
    assert result.count(Disposition.SKIPPED) == 1
    assert [o for o in result.observations if not isinstance(o, StreamEvent)] == []


def test_every_frame_has_exactly_one_disposition_in_sequence_order(
    root: Path, store: CaptureStore
) -> None:
    session = run(
        store,
        root,
        [
            ("in", snapshot(1)),
            ("bad", b"\xff"),
            ("out", b"{}"),
            ("in", message(type="resolution", spec_key=KEY, result="yes")),
        ],
    )
    result = normalized(store, session.session_id)
    assert [f.sequence for f in result.frames] == list(range(len(result.frames)))
    assert [f.disposition for f in result.frames] == [
        Disposition.SEGMENT_HEADER,
        Disposition.STREAM_EVENT,
        Disposition.PARSED,
        Disposition.REJECTED,
        Disposition.OUTBOUND,
        Disposition.PARSED,
        Disposition.STREAM_EVENT,
        Disposition.SESSION_END,
    ]
    # the official resolution leaves through the label channel only
    assert len(result.resolutions) == 1
    assert not any(isinstance(o, ResolutionRecord) for o in result.observations)
    events = [o.kind for o in result.observations if isinstance(o, StreamEvent)]
    assert events == [
        StreamEventKind.CONNECTION_OPENED,
        StreamEventKind.FRAME_REJECTED,
        StreamEventKind.CONNECTION_CLOSED,
    ]


def test_the_stream_parser_identity_is_reserved(root: Path, store: CaptureStore) -> None:
    session = run(store, root, [("in", snapshot(1))])

    class Impostor(SyntheticNormalizer):
        @property
        def parser_id(self) -> str:
            return "pmv_stream_event"

    with pytest.raises(NormalizationContractError, match="reserved"):
        normalize_session(
            store, store.read_session(session.session_id), Impostor(), use=DataUse.TEST
        )


# ----- normalized artifacts -----


def test_artifacts_round_trip_deterministically(root: Path, store: CaptureStore) -> None:
    session = run(
        store,
        root,
        [
            ("in", snapshot(1)),
            ("in", delta(2)),
            ("in", message(type="trade", spec_key=KEY, outcome="yes", price=55, quantity=2)),
            ("in", message(type="reference", price="101.25")),
            ("in", message(type="status", spec_key=KEY, status="open")),
            ("in", message(type="resolution", spec_key=KEY, result="no")),
        ],
    )
    first = normalized(store, session.session_id)
    second = normalized(store, session.session_id)
    assert first == second
    key, files = encode_artifact(first)
    assert encode_artifact(second) == (key, files)
    assert decode_artifact(files) == first
    assert key == artifact_key(store.read_session(session.session_id), SyntheticNormalizer())
    assert persist_artifact(store, first) == (key, True)
    assert persist_artifact(store, second) == (key, False)
    loaded = load_artifact(store, session.session_id, key, use=DataUse.TEST)
    assert loaded == first
    # lineage: the artifact names every input segment's exact bytes
    refs = store.read_session(session.session_id).segments
    assert loaded.segments == tuple((r.index, r.kind.value, r.sha256, r.size_bytes) for r in refs)


def test_a_parser_version_is_a_new_artifact(root: Path, store: CaptureStore) -> None:
    session = run(store, root, [("in", snapshot(1))])
    read = store.read_session(session.session_id)

    class Fixed(SyntheticNormalizer):
        @property
        def parser_version(self) -> int:
            return 99

    assert artifact_key(read, SyntheticNormalizer()) != artifact_key(read, Fixed())


def test_synthetic_artifacts_are_refused_for_research(root: Path, store: CaptureStore) -> None:
    session = run(store, root, [("in", snapshot(1))])
    key, _written = persist_artifact(store, normalized(store, session.session_id))
    with pytest.raises(CaptureEnvironmentError, match="only for tests"):
        load_artifact(store, session.session_id, key, use=DataUse.RESEARCH)
    with pytest.raises(CaptureEnvironmentError, match="only for tests"):
        normalize_session(
            store,
            store.read_session(session.session_id),
            SyntheticNormalizer(),
            use=DataUse.RESEARCH,
        )


@pytest.mark.parametrize("use", list(DataUse))
def test_demo_tagged_artifacts_are_refused_by_loaders(
    root: Path, store: CaptureStore, use: DataUse
) -> None:
    session = run(store, root, [("in", snapshot(1))])
    demo = replace(normalized(store, session.session_id), venue_environment=VenueEnvironment.DEMO)
    key, files = encode_artifact(demo)
    store.write_artifact(session.session_id, key, files)
    with pytest.raises(CaptureEnvironmentError, match="demo captures are never loaded"):
        load_artifact(store, session.session_id, key, use=use)


Mutation = Callable[[dict[str, Any]], object]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda doc: doc.update(key="0" * 64),
        lambda doc: doc.update(
            session_status="complete" if doc["session_status"] != "complete" else "open"
        ),
        lambda doc: doc.update(counts={**doc["counts"], "parsed": 99}),
        lambda doc: doc.update(extra=1),
        lambda doc: doc["observations"].pop(),
    ],
    ids=["key", "status", "counts", "extra", "dropped_observation"],
)
def test_tampered_artifacts_are_refused(root: Path, store: CaptureStore, mutate: Mutation) -> None:
    session = run(store, root, [("in", snapshot(1)), ("in", delta(2))])
    _key, files = encode_artifact(normalized(store, session.session_id))
    document = json.loads(files["observations.json"])
    mutate(document)
    changed = dict(files)
    changed["observations.json"] = (
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    if changed == files:
        pytest.skip("mutation left the artifact unchanged")
    with pytest.raises(ArtifactError):
        decode_artifact(changed)


def test_noncanonical_or_partial_artifacts_are_refused(root: Path, store: CaptureStore) -> None:
    session = run(store, root, [("in", snapshot(1))])
    _key, files = encode_artifact(normalized(store, session.session_id))
    with pytest.raises(ArtifactError):
        decode_artifact({"observations.json": files["observations.json"]})
    spaced = dict(files)
    spaced["labels.json"] = json.dumps(json.loads(files["labels.json"]), indent=1).encode() + b"\n"
    with pytest.raises(ArtifactError):
        decode_artifact(spaced)


def test_normalizing_needs_an_intact_chain(root: Path, store: CaptureStore) -> None:
    session = run(store, root, [("in", snapshot(1))])
    read = store.read_session(session.session_id)
    target = (
        root
        / "capture/v2/segments/unit_source/unit_feed"
        / session.session_id[0:4]
        / session.session_id[4:6]
        / session.session_id[6:8]
        / session.session_id
        / "000000"
        / "segment.pmvraw"
    )
    target.chmod(0o600)
    data = bytearray(target.read_bytes())
    data[-10] ^= 0x01
    target.write_bytes(bytes(data))
    with pytest.raises(CaptureIntegrityError):
        normalize_session(store, read, SyntheticNormalizer(), use=DataUse.TEST)
    assert not (root / "capture" / "v2" / "normalized" / session.session_id).exists()


# ----- RT-B8-01 / RT-B8-02 regressions (artifact integrity, environment labels) -----


def rewrite(root: Path, session_id: str, key: str, files: dict[str, bytes]) -> None:
    """Overwrite a stored artifact's files in place, as a local writer could."""
    directory = root / "capture" / "v2" / "normalized" / session_id / key
    directory.chmod(0o700)
    for name, data in files.items():
        path = directory / name
        if path.exists():
            path.chmod(0o600)
        path.write_bytes(data)


def reencode(document: dict[str, Any]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def with_record(files: dict[str, bytes], key: str) -> dict[str, bytes]:
    """Recompute the artifact record so it matches tampered content (a consistent forgery)."""
    record = json.loads(files["artifact.json"])
    for name in ("labels.json", "observations.json"):
        record["files"][name] = {
            "sha256": hashlib.sha256(files[name]).hexdigest(),
            "size_bytes": len(files[name]),
        }
    record["key"] = key
    return {**files, "artifact.json": reencode(record)}


def stored(
    store: CaptureStore, root: Path, steps: Sequence[Step]
) -> tuple[str, str, dict[str, bytes]]:
    session = run(store, root, steps)
    key, written = persist_artifact(store, normalized(store, session.session_id))
    assert written
    return session.session_id, key, store.read_artifact(session.session_id, key)


def test_a_changed_value_is_caught_by_the_record_digest_or_re_derivation(
    root: Path, store: CaptureStore
) -> None:
    session_id, key, files = stored(store, root, [("in", snapshot(1)), ("in", delta(2))])
    digest = artifact_digest(files)
    document = json.loads(files["observations.json"])
    snapshot_entry = next(o for o in document["observations"] if o["type"] == "book_snapshot")
    snapshot_entry["bids"][0][0] = 49
    changed = {**files, "observations.json": reencode(document)}
    rewrite(root, session_id, key, changed)
    with pytest.raises(ArtifactError, match="does not match its record"):
        load_artifact(store, session_id, key, use=DataUse.TEST)
    # a consistent forgery (record rewritten too) passes the record check, but not a
    # digest recorded elsewhere, and not re-derivation from the raw segments
    rewrite(root, session_id, key, with_record(changed, key))
    with pytest.raises(ArtifactError, match="recorded digest"):
        load_artifact(store, session_id, key, use=DataUse.TEST, expected_digest=digest)
    with pytest.raises(ArtifactError, match="re-derivation"):
        verify_artifact(store, session_id, key, SyntheticNormalizer(), use=DataUse.TEST)


def test_a_deleted_rejection_is_detected(root: Path, store: CaptureStore) -> None:
    _session_id, key, files = stored(
        store, root, [("in", snapshot(1)), ("bad", delta(2)), ("in", delta(3))]
    )
    document = json.loads(files["observations.json"])
    rejected = next(f for f in document["frames"] if f[2] == "rejected")
    document["frames"].remove(rejected)
    document["observations"] = [
        o
        for o in document["observations"]
        if not (o["type"] == "stream_event" and o["kind"] == "frame_rejected")
    ]
    document["counts"]["rejected"] -= 1
    forged = with_record({**files, "observations.json": reencode(document)}, key)
    with pytest.raises(ArtifactError, match="contiguous"):
        decode_artifact(forged)


def test_a_relabelled_environment_is_refused(root: Path, store: CaptureStore) -> None:
    session_id, key, files = stored(store, root, [("in", snapshot(1))])
    document = json.loads(files["observations.json"])
    document["venue_environment"] = "production"
    forged = with_record({**files, "observations.json": reencode(document)}, key)
    with pytest.raises(ArtifactError, match="key does not match"):
        decode_artifact(forged)
    # re-keyed consistently and stored under its new key: the session and the test
    # deployment still refuse it
    relabelled = replace(
        normalized(store, session_id), venue_environment=VenueEnvironment.PRODUCTION
    )
    new_key, new_files = encode_artifact(relabelled)
    store.write_artifact(session_id, new_key, new_files)
    with pytest.raises(CaptureEnvironmentError, match="never research data"):
        load_artifact(store, session_id, new_key, use=DataUse.RESEARCH)
    with pytest.raises(CaptureEnvironmentError, match="only for research"):
        load_artifact(store, session_id, new_key, use=DataUse.TEST)


def test_an_artifact_must_match_its_sessions_current_chain(root: Path, store: CaptureStore) -> None:
    session_id, key, _files = stored(store, root, [("in", snapshot(1))])
    stale = replace(normalized(store, session_id), deployment_environment="development")
    stale_key, stale_files = encode_artifact(stale)
    store.write_artifact(session_id, stale_key, stale_files)
    with pytest.raises(ArtifactError, match="current chain"):
        load_artifact(store, session_id, stale_key, use=DataUse.TEST)
    assert load_artifact(store, session_id, key, use=DataUse.TEST).session_id == session_id
    assert verify_artifact(store, session_id, key, SyntheticNormalizer(), use=DataUse.TEST)
