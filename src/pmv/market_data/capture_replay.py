"""Replay of segmented (frame format v3) capture sessions into normalized artifacts (B08).

``normalize_session`` drives a venue ``Normalizer`` over the readable chain of one capture
session (``pmv.capture_store``). Every frame gets exactly one recorded disposition, in raw
sequence order, and nothing is reordered by any clock:

- ``segment_header``: a segment header (a storage boundary, no observation);
- ``parsed``: an inbound payload the parser understood (zero or more items);
- ``skipped``: an inbound payload deliberately not normalized, with a reason;
- ``rejected``: an inbound payload flagged malformed or refused by the parser, with a
  reason. The driver adds a ``frame_rejected`` stream event, which breaks every book of
  the session;
- ``outbound``: a message PMV sent (no observation);
- ``stream_event``: an operational event, as a ``StreamEvent``;
- ``session_end``: ``session_closed`` (no observation).

The session is the capture for normalization: provenance is ``(session_id, sequence,
item_index)``. Rolling over to a new segment does not break books; a connection opening
or closing, a gap, a rate limit, a hard stop, or a rejected frame does. Receipt time is the
frame's ``observed_at``, as in v1 (``available_at = received_at``); the frame's monotonic
time is kept beside it in the artifact.

Loading data refuses demo captures, and synthetic captures outside tests
(``capture_environment.require_data_use``; RT-B2-09). Normalizing a capture releases
nothing: artifacts are written only into the capture store, under the same protected root
as the raw bytes (A-7, A-8).

A **normalized artifact** is two canonical JSON files under
``normalized/<session_id>/<key>/``:

- ``observations.json``: the frame dispositions and the observations;
- ``labels.json``: the official resolutions, a separate channel that never enters an
  observation log.

A third file, ``artifact.json``, records the SHA-256 and size of both, and is checked on
every read; ``artifact_digest`` (its SHA-256) is the reference to record wherever an
artifact is used. ``load_artifact`` also checks the artifact against the session as the
store reads it now, and ``verify_artifact`` re-derives every byte from the raw segments.
A local writer who rewrites all three files consistently is detected only by a recorded
digest or by re-derivation (RT-B8-01).

``key`` is the SHA-256 of the derivation: this driver's identity and version, the session,
the exact SHA-256 and size of every input segment's bytes, why the readable chain ends
(its ``SessionStatus``), the venue and deployment environments, and the parser identity
and version. The files contain no
wall-clock creation time and no code commit, so generation is deterministic and
idempotent: the same derivation always yields identical bytes, and a different result
under the same key is an integrity failure, never a replacement. A parser fix is a new
parser version and therefore a new key.

Decoding checks that every frame accounts for exactly its own items (a parsed frame for
its observations and resolutions, a stream-event frame for one event, a rejected frame for
one ``frame_rejected`` event, and every other frame for none), so no observation can be
dropped, added, or moved without detection.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final

from pmv.capture_environment import CaptureEnvironmentError, DataUse, require_data_use
from pmv.capture_format import (
    Direction,
    EventFrame,
    EventType,
    PayloadFrame,
    SegmentHeader,
    VenueEnvironment,
)
from pmv.capture_store import CaptureStore, SessionRead, SessionStatus
from pmv.integrity import (
    FormatError,
    canonical_json,
    decimal_text,
    is_decimal_text,
    is_sha256,
    is_timestamp,
    is_timestamp_id,
    parse_canonical_json,
    sha256_hex,
)
from pmv.market_data.events import (
    BookDelta,
    BookLevel,
    BookSnapshot,
    Observation,
    Outcome,
    ReferenceTick,
    Side,
    StreamEvent,
    StreamEventKind,
    Trade,
    TradingStatus,
    TradingStatusUpdate,
)
from pmv.market_data.labels import OfficialResolution, ResolutionRecord
from pmv.market_data.replay import (
    STREAM_PARSER_ID,
    STREAM_PARSER_VERSION,
    NormalizationContractError,
    NormalizeContext,
    Normalizer,
    Parsed,
    PayloadRejectedError,
    Skipped,
    check_parsed_item,
    rejection_event,
)
from pmv.market_data.timing import Provenance, Timing, parse_timestamp
from pmv.protected_scope import Family, Provider

__all__ = [
    "DRIVER_ID",
    "DRIVER_VERSION",
    "ArtifactError",
    "Disposition",
    "FrameEntry",
    "NormalizedSession",
    "artifact_digest",
    "artifact_key",
    "decode_artifact",
    "encode_artifact",
    "load_artifact",
    "normalize_session",
    "persist_artifact",
    "verify_artifact",
]

DRIVER_ID: Final = "pmv_capture_replay"
DRIVER_VERSION: Final = 1
OBSERVATIONS_FILE: Final = "observations.json"
LABELS_FILE: Final = "labels.json"
RECORD_FILE: Final = "artifact.json"
RECORD_SCHEMA: Final = "pmv.normalized.artifact_record"
OBSERVATIONS_SCHEMA: Final = "pmv.normalized.capture"
LABELS_SCHEMA: Final = "pmv.normalized.labels"
SCHEMA_VERSION: Final = 1
RAW_MALFORMED_REASON: Final = "raw_flagged_malformed"


class ArtifactError(Exception):
    """A normalized artifact is malformed or inconsistent. Messages carry no values."""


class Disposition(StrEnum):
    SEGMENT_HEADER = "segment_header"
    PARSED = "parsed"
    SKIPPED = "skipped"
    REJECTED = "rejected"
    OUTBOUND = "outbound"
    STREAM_EVENT = "stream_event"
    SESSION_END = "session_end"


@dataclass(frozen=True, slots=True)
class FrameEntry:
    sequence: int
    segment_index: int
    disposition: Disposition
    item_count: int
    reason: str | None
    connection: int | None
    monotonic_ns: int


@dataclass(frozen=True, slots=True)
class NormalizedSession:
    session_id: str
    venue_environment: VenueEnvironment
    deployment_environment: str
    session_status: SessionStatus
    segments: tuple[tuple[int, str, str, int], ...]
    """``(index, kind, sha256, size_bytes)`` of every input segment, in chain order."""
    parser_id: str
    parser_version: int
    frames: tuple[FrameEntry, ...]
    observations: tuple[Observation, ...]
    resolutions: tuple[ResolutionRecord, ...]

    def count(self, disposition: Disposition) -> int:
        return sum(1 for frame in self.frames if frame.disposition is disposition)


def _segments(read: SessionRead) -> tuple[tuple[int, str, str, int], ...]:
    return tuple((ref.index, ref.kind.value, ref.sha256, ref.size_bytes) for ref in read.segments)


def normalize_session(
    store: CaptureStore, read: SessionRead, normalizer: Normalizer, *, use: DataUse
) -> NormalizedSession:
    """Normalize the readable chain of one session. Fails closed on any contract breach."""
    _require_use(read.venue_environment, read.deployment_environment, use)
    parser_id, parser_version = normalizer.parser_id, normalizer.parser_version
    if parser_id == STREAM_PARSER_ID:
        raise NormalizationContractError("the stream-event parser identity is reserved")
    session_id = read.session_id
    frames: list[FrameEntry] = []
    observations: list[Observation] = []
    resolutions: list[ResolutionRecord] = []
    for segment_index, frame in store.iter_frames(read):
        if isinstance(frame, SegmentHeader):
            frames.append(
                FrameEntry(
                    frame.sequence,
                    segment_index,
                    Disposition.SEGMENT_HEADER,
                    0,
                    None,
                    None,
                    frame.monotonic_ns,
                )
            )
            continue
        if isinstance(frame, EventFrame):
            if frame.event_type is EventType.SESSION_CLOSED:
                disposition = Disposition.SESSION_END
            else:
                disposition = Disposition.STREAM_EVENT
                observations.append(
                    StreamEvent(
                        StreamEventKind(frame.event_type.value),
                        parse_timestamp(frame.written_at),
                        Provenance(
                            session_id,
                            frame.sequence,
                            0,
                            STREAM_PARSER_ID,
                            STREAM_PARSER_VERSION,
                        ),
                    )
                )
            frames.append(
                FrameEntry(
                    frame.sequence,
                    segment_index,
                    disposition,
                    int(disposition is Disposition.STREAM_EVENT),
                    None,
                    frame.connection,
                    frame.monotonic_ns,
                )
            )
            continue
        frames.append(
            _payload(
                frame,
                segment_index,
                session_id,
                normalizer,
                parser_id,
                parser_version,
                observations,
                resolutions,
            )
        )
    return NormalizedSession(
        session_id=session_id,
        venue_environment=read.venue_environment,
        deployment_environment=read.deployment_environment,
        session_status=read.status,
        segments=_segments(read),
        parser_id=parser_id,
        parser_version=parser_version,
        frames=tuple(frames),
        observations=tuple(observations),
        resolutions=tuple(resolutions),
    )


def _payload(
    frame: PayloadFrame,
    segment_index: int,
    session_id: str,
    normalizer: Normalizer,
    parser_id: str,
    parser_version: int,
    observations: list[Observation],
    resolutions: list[ResolutionRecord],
) -> FrameEntry:
    def entry(disposition: Disposition, count: int, reason: str | None) -> FrameEntry:
        return FrameEntry(
            frame.sequence,
            segment_index,
            disposition,
            count,
            reason,
            frame.connection,
            frame.monotonic_ns,
        )

    if frame.direction is Direction.OUTBOUND:
        return entry(Disposition.OUTBOUND, 0, None)
    received = parse_timestamp(frame.observed_at)
    context = NormalizeContext(
        session_id,
        frame.sequence,
        received,
        None if frame.source_timestamp is None else parse_timestamp(frame.source_timestamp),
        parser_id,
        parser_version,
    )
    if frame.malformed:
        observations.append(rejection_event(session_id, frame.sequence, received))
        return entry(Disposition.REJECTED, 0, RAW_MALFORMED_REASON)
    try:
        outcome = normalizer.normalize(frame.payload, context)
    except PayloadRejectedError as rejection:
        observations.append(rejection_event(session_id, frame.sequence, received))
        return entry(Disposition.REJECTED, 0, rejection.reason)
    if isinstance(outcome, Skipped):
        return entry(Disposition.SKIPPED, 0, outcome.reason)
    if not isinstance(outcome, Parsed):
        raise NormalizationContractError("a parser returned neither Parsed nor Skipped")
    for index, item in enumerate(outcome.items):
        check_parsed_item(item, index, context)
        if isinstance(item, ResolutionRecord):
            resolutions.append(item)
        else:
            observations.append(item)
    return entry(Disposition.PARSED, len(outcome.items), None)


# ----- artifacts -----


def artifact_key(read: SessionRead, normalizer: Normalizer) -> str:
    """The content address of one derivation (see the module docstring)."""
    return _key(
        read.session_id,
        read.venue_environment,
        read.deployment_environment,
        _segments(read),
        read.status,
        normalizer.parser_id,
        normalizer.parser_version,
    )


def _key(
    session_id: str,
    venue: VenueEnvironment,
    deployment: str,
    segments: Sequence[tuple[int, str, str, int]],
    status: SessionStatus,
    parser_id: str,
    parser_version: int,
) -> str:
    return sha256_hex(
        canonical_json(
            {
                "driver": {"id": DRIVER_ID, "version": DRIVER_VERSION},
                "parser": {"id": parser_id, "version": parser_version},
                "schema": OBSERVATIONS_SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "segments": [list(segment) for segment in segments],
                "session_id": session_id,
                "session_status": status.value,
                "venue_environment": venue.value,
                "deployment_environment": deployment,
            }
        )
    )


def encode_artifact(session: NormalizedSession) -> tuple[str, dict[str, bytes]]:
    """Return ``(key, files)`` with deterministic canonical bytes."""
    key = _key(
        session.session_id,
        session.venue_environment,
        session.deployment_environment,
        session.segments,
        session.session_status,
        session.parser_id,
        session.parser_version,
    )
    observations = {
        "counts": {item.value: session.count(item) for item in Disposition},
        "deployment_environment": session.deployment_environment,
        "driver": {"id": DRIVER_ID, "version": DRIVER_VERSION},
        "frames": [
            [
                frame.sequence,
                frame.segment_index,
                frame.disposition.value,
                frame.item_count,
                frame.reason,
                frame.connection,
                frame.monotonic_ns,
            ]
            for frame in session.frames
        ],
        "key": key,
        "observations": [_encode_observation(item) for item in session.observations],
        "parser": {"id": session.parser_id, "version": session.parser_version},
        "schema": OBSERVATIONS_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "segments": [list(segment) for segment in session.segments],
        "session_id": session.session_id,
        "session_status": session.session_status.value,
        "venue_environment": session.venue_environment.value,
    }
    labels = {
        "key": key,
        "resolutions": [_encode_resolution(item) for item in session.resolutions],
        "schema": LABELS_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "session_id": session.session_id,
    }
    files = {
        LABELS_FILE: canonical_json(labels) + b"\n",
        OBSERVATIONS_FILE: canonical_json(observations) + b"\n",
    }
    files[RECORD_FILE] = _record(key, files)
    return key, files


def _record(key: str, files: Mapping[str, bytes]) -> bytes:
    """The artifact record: the SHA-256 and size of each content file (RT-B8-01)."""
    return (
        canonical_json(
            {
                "files": {
                    name: {"sha256": sha256_hex(files[name]), "size_bytes": len(files[name])}
                    for name in (LABELS_FILE, OBSERVATIONS_FILE)
                },
                "key": key,
                "schema": RECORD_SCHEMA,
                "schema_version": SCHEMA_VERSION,
            }
        )
        + b"\n"
    )


def artifact_digest(files: Mapping[str, bytes]) -> str:
    """SHA-256 of an artifact's record, which binds both content files.

    Record it wherever the artifact is used (for example an experiment manifest): it is
    the reference a later reader checks the artifact against.
    """
    return sha256_hex(files[RECORD_FILE])


def persist_artifact(store: CaptureStore, session: NormalizedSession) -> tuple[str, bool]:
    """Write the artifact into the capture store. Returns ``(key, written_now)``."""
    key, files = encode_artifact(session)
    return key, store.write_artifact(session.session_id, key, files)


def load_artifact(
    store: CaptureStore,
    session_id: str,
    key: str,
    *,
    use: DataUse,
    expected_digest: str | None = None,
) -> NormalizedSession:
    """Read, validate, and decode one artifact, and check it against its session.

    Checks, in order: each content file against the artifact record; the derivation key;
    the canonical form, frame contiguity, and item accounting; then the session as the
    store reads it now (same segments, status, and environments); then the data use.
    ``expected_digest``, when given, must equal ``artifact_digest``: a record kept
    elsewhere (for example in an experiment manifest) detects a rewritten artifact.
    ``verify_artifact`` additionally re-derives every byte.
    """
    files = store.read_artifact(session_id, key)
    if expected_digest is not None and (
        RECORD_FILE not in files or artifact_digest(files) != expected_digest
    ):
        raise ArtifactError("the artifact does not match its recorded digest")
    session = decode_artifact(files)
    if session.session_id != session_id or encode_artifact(session)[0] != key:
        raise ArtifactError("the artifact is not stored under its own key")
    # Refusing a demo or misused label needs no trust in the label; accepting one does,
    # so the session cross-check follows.
    _require_use(session.venue_environment, session.deployment_environment, use)
    read = store.read_session(session_id)
    if (
        session.segments != _segments(read)
        or session.session_status is not read.status
        or session.venue_environment is not read.venue_environment
        or session.deployment_environment != read.deployment_environment
    ):
        raise ArtifactError("the artifact does not match its session's current chain")
    return session


def verify_artifact(
    store: CaptureStore, session_id: str, key: str, normalizer: Normalizer, *, use: DataUse
) -> NormalizedSession:
    """Load an artifact and re-derive it from the raw segments; every byte must match."""
    session = load_artifact(store, session_id, key, use=use)
    fresh = normalize_session(store, store.read_session(session_id), normalizer, use=use)
    if encode_artifact(fresh) != (key, store.read_artifact(session_id, key)):
        raise ArtifactError("the artifact differs from a re-derivation of its raw segments")
    return session


def _require_use(venue: VenueEnvironment, deployment: str, use: DataUse) -> None:
    """Environment rules for loading data: demo never, synthetic for tests only, and
    nothing written by the test deployment is ever research data (RT-B8-02)."""
    require_data_use(venue, use)
    if use is DataUse.RESEARCH and deployment == "test":
        raise CaptureEnvironmentError("data written by the test environment is never research data")


def decode_artifact(files: Mapping[str, bytes]) -> NormalizedSession:
    if set(files) != {LABELS_FILE, OBSERVATIONS_FILE, RECORD_FILE}:
        raise ArtifactError("an artifact has exactly its record, observations, and labels files")
    record = _document(files[RECORD_FILE])
    _closed(record, {"files", "key", "schema", "schema_version"})
    if (record["schema"], record["schema_version"]) != (RECORD_SCHEMA, SCHEMA_VERSION):
        raise ArtifactError("unsupported artifact record schema")
    listed = _obj(record["files"])
    if set(listed) != {LABELS_FILE, OBSERVATIONS_FILE}:
        raise ArtifactError("the artifact record lists other files")
    for name in (LABELS_FILE, OBSERVATIONS_FILE):
        entry = _closed(_obj(listed[name]), {"sha256", "size_bytes"})
        if entry != {"sha256": sha256_hex(files[name]), "size_bytes": len(files[name])}:
            raise ArtifactError("an artifact file does not match its record")
    top = _document(files[OBSERVATIONS_FILE])
    labels = _document(files[LABELS_FILE])
    _closed(
        top,
        {
            "counts",
            "deployment_environment",
            "driver",
            "frames",
            "key",
            "observations",
            "parser",
            "schema",
            "schema_version",
            "segments",
            "session_id",
            "session_status",
            "venue_environment",
        },
    )
    _closed(labels, {"key", "resolutions", "schema", "schema_version", "session_id"})
    if (top["schema"], top["schema_version"]) != (OBSERVATIONS_SCHEMA, SCHEMA_VERSION) or (
        labels["schema"],
        labels["schema_version"],
    ) != (LABELS_SCHEMA, SCHEMA_VERSION):
        raise ArtifactError("unsupported artifact schema")
    if top["driver"] != {"id": DRIVER_ID, "version": DRIVER_VERSION}:
        raise ArtifactError("the artifact was produced by another driver version")
    session_id = _text(top["session_id"])
    if not is_timestamp_id(session_id) or labels["session_id"] != session_id:
        raise ArtifactError("an artifact session identifier is invalid")
    parser = _closed(_obj(top["parser"]), {"id", "version"})
    parser_id, parser_version = _text(parser["id"]), _int(parser["version"])
    segments = tuple(_segment(item) for item in _list(top["segments"]))
    try:
        status = SessionStatus(_text(top["session_status"]))
    except ValueError:
        raise ArtifactError("an artifact session status is invalid") from None
    try:
        environment = VenueEnvironment(_text(top["venue_environment"]))
    except ValueError:
        raise ArtifactError("an artifact venue environment is invalid") from None
    deployment = _text(top["deployment_environment"])
    if deployment not in ("development", "test", "shadow", "production"):
        raise ArtifactError("an artifact deployment environment is invalid")
    key = _key(session_id, environment, deployment, segments, status, parser_id, parser_version)
    if top["key"] != key or labels["key"] != key or record["key"] != key:
        raise ArtifactError("an artifact's key does not match its derivation")
    try:
        frames = tuple(_frame(item) for item in _list(top["frames"]))
        observations = tuple(_decode_observation(item) for item in _list(top["observations"]))
        resolutions = tuple(_decode_resolution(item) for item in _list(labels["resolutions"]))
    except (ValueError, TypeError, KeyError, InvalidOperation):
        raise ArtifactError("an artifact field is invalid") from None
    session = NormalizedSession(
        session_id,
        environment,
        deployment,
        status,
        segments,
        parser_id,
        parser_version,
        frames,
        observations,
        resolutions,
    )
    _check_frames(session)
    _check_items(session)
    if top["counts"] != {item.value: session.count(item) for item in Disposition}:
        raise ArtifactError("an artifact's counts do not match its frames")
    if encode_artifact(session)[1] != dict(files):
        raise ArtifactError("an artifact is not in canonical form")
    return session


def _check_frames(session: NormalizedSession) -> None:
    """Frames cover the whole readable chain: sequences 0, 1, 2, ... with no gap, one
    segment header per input segment, each at its segment's first sequence (RT-B8-01)."""
    if [frame.sequence for frame in session.frames] != list(range(len(session.frames))):
        raise ArtifactError("an artifact's frames are not one contiguous sequence")
    headers = [f for f in session.frames if f.disposition is Disposition.SEGMENT_HEADER]
    if [h.segment_index for h in headers] != [segment[0] for segment in session.segments]:
        raise ArtifactError("an artifact's segment headers do not match its segments")
    current = None
    for frame in session.frames:
        if frame.disposition is Disposition.SEGMENT_HEADER:
            current = frame.segment_index
        elif frame.segment_index != current:
            raise ArtifactError("a frame is attributed to the wrong segment")
    ends = [f for f in session.frames if f.disposition is Disposition.SESSION_END]
    if len(ends) > 1 or (ends and session.frames[-1] is not ends[0]):
        raise ArtifactError("a session end must be the artifact's last frame")
    # A complete session ends with session_closed; a salvaged one may (crash after the
    # close, before finalization); an open or truncated chain cannot.
    allowed = (
        {1}
        if session.session_status is SessionStatus.COMPLETE
        else {0, 1}
        if session.session_status is SessionStatus.ENDS_WITH_SALVAGE
        else {0}
    )
    if len(ends) not in allowed:
        raise ArtifactError("an artifact's session end does not match its status")


def _check_items(session: NormalizedSession) -> None:
    """Every frame accounts for exactly its own items, in sequence order."""
    expected: list[tuple[int, int]] = []
    for frame in session.frames:
        if frame.disposition is Disposition.PARSED:
            count = frame.item_count
        elif frame.disposition in (Disposition.STREAM_EVENT, Disposition.REJECTED):
            count = 1
        else:
            count = 0
        if frame.disposition is not Disposition.PARSED and frame.item_count != (
            1 if frame.disposition is Disposition.STREAM_EVENT else 0
        ):
            raise ArtifactError("a frame's item count does not match its disposition")
        expected.extend((frame.sequence, index) for index in range(count))
    items: list[tuple[int, int]] = []
    rejected = {f.sequence for f in session.frames if f.disposition is Disposition.REJECTED}
    for item in (*session.observations, *session.resolutions):
        position = (item.provenance.frame_sequence, item.provenance.item_index)
        if item.provenance.capture_id != session.session_id:
            raise ArtifactError("an item belongs to another session")
        if position[0] in rejected and not (
            isinstance(item, StreamEvent) and item.kind is StreamEventKind.FRAME_REJECTED
        ):
            raise ArtifactError("a rejected frame carries an item other than its rejection")
        items.append(position)
    if sorted(items) != expected:
        raise ArtifactError("an artifact's items do not match its frames")


# ----- codecs -----


def _ts(moment: datetime | None) -> str | None:
    return None if moment is None else moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _prov(provenance: Provenance) -> list[object]:
    return [
        provenance.capture_id,
        provenance.frame_sequence,
        provenance.item_index,
        provenance.parser_id,
        provenance.parser_version,
    ]


def _timing(timing: Timing) -> dict[str, object]:
    return {"received_at": _ts(timing.received_at), "source_time": _ts(timing.source_time)}


def _levels(levels: Sequence[BookLevel]) -> list[list[int]]:
    return [[level.price, level.quantity] for level in levels]


def _encode_observation(item: Observation) -> dict[str, object]:
    if isinstance(item, StreamEvent):
        return {
            "kind": item.kind.value,
            "provenance": _prov(item.provenance),
            "recorded_at": _ts(item.recorded_at),
            "type": "stream_event",
        }
    if isinstance(item, ReferenceTick):
        return {
            "family": item.family.value,
            "price": decimal_text(item.price),
            "provenance": _prov(item.provenance),
            "provider": item.provider.value,
            "type": "reference_tick",
            **_timing(item.timing),
        }
    common: dict[str, object] = {
        "provenance": _prov(item.provenance),
        "spec_key": item.spec_key,
        **_timing(item.timing),
    }
    if isinstance(item, BookSnapshot):
        return {
            **common,
            "asks": _levels(item.asks),
            "bids": _levels(item.bids),
            "outcome": item.outcome.value,
            "sequence_scope": item.sequence_scope,
            "solicited": item.solicited,
            "type": "book_snapshot",
            "venue_sequence": item.venue_sequence,
        }
    if isinstance(item, BookDelta):
        return {
            **common,
            "new_quantity": item.new_quantity,
            "outcome": item.outcome.value,
            "price": item.price,
            "sequence_scope": item.sequence_scope,
            "side": item.side.value,
            "type": "book_delta",
            "venue_sequence": item.venue_sequence,
        }
    if isinstance(item, Trade):
        return {
            **common,
            "outcome": item.outcome.value,
            "price": item.price,
            "quantity": item.quantity,
            "taker_side": None if item.taker_side is None else item.taker_side.value,
            "type": "trade",
            "venue_trade_id": item.venue_trade_id,
        }
    return {**common, "status": item.status.value, "type": "trading_status"}


def _encode_resolution(item: ResolutionRecord) -> dict[str, object]:
    return {
        "provenance": _prov(item.provenance),
        "received_at": _ts(item.received_at),
        "resolution": item.resolution.value,
        "spec_key": item.spec_key,
    }


_OBSERVATION_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "stream_event": frozenset({"kind", "provenance", "recorded_at", "type"}),
    "reference_tick": frozenset(
        {"family", "price", "provenance", "provider", "received_at", "source_time", "type"}
    ),
    "book_snapshot": frozenset(
        {
            "asks",
            "bids",
            "outcome",
            "provenance",
            "received_at",
            "sequence_scope",
            "solicited",
            "source_time",
            "spec_key",
            "type",
            "venue_sequence",
        }
    ),
    "book_delta": frozenset(
        {
            "new_quantity",
            "outcome",
            "price",
            "provenance",
            "received_at",
            "sequence_scope",
            "side",
            "source_time",
            "spec_key",
            "type",
            "venue_sequence",
        }
    ),
    "trade": frozenset(
        {
            "outcome",
            "price",
            "provenance",
            "quantity",
            "received_at",
            "source_time",
            "spec_key",
            "taker_side",
            "type",
            "venue_trade_id",
        }
    ),
    "trading_status": frozenset(
        {"provenance", "received_at", "source_time", "spec_key", "status", "type"}
    ),
}


def _decode_observation(value: object) -> Observation:
    item = _obj(value)
    kind = _text(item.get("type"))
    keys = _OBSERVATION_KEYS.get(kind)
    if keys is None:
        raise ArtifactError("an observation has an unknown type")
    _closed(item, set(keys))
    provenance = _decode_prov(item["provenance"])
    if kind == "stream_event":
        return StreamEvent(
            StreamEventKind(_text(item["kind"])), _time(item["recorded_at"]), provenance
        )
    timing = Timing(_time(item["received_at"]), _opt_time(item["source_time"]))
    if kind == "reference_tick":
        price = _text(item["price"])
        if not is_decimal_text(price):
            raise ArtifactError("a reference price is not decimal text")
        return ReferenceTick(
            Provider(_text(item["provider"])),
            Family(_text(item["family"])),
            Decimal(price),
            timing,
            provenance,
        )
    spec_key = _text(item["spec_key"])
    if kind == "trading_status":
        return TradingStatusUpdate(
            spec_key, TradingStatus(_text(item["status"])), timing, provenance
        )
    outcome = Outcome(_text(item["outcome"]))
    if kind == "trade":
        taker = item["taker_side"]
        trade_id = item["venue_trade_id"]
        return Trade(
            spec_key,
            outcome,
            _int(item["price"]),
            _int(item["quantity"]),
            None if taker is None else Side(_text(taker)),
            None if trade_id is None else _text(trade_id),
            timing,
            provenance,
        )
    sequence = None if item["venue_sequence"] is None else _int(item["venue_sequence"])
    scope = None if item["sequence_scope"] is None else _text(item["sequence_scope"])
    if kind == "book_delta":
        return BookDelta(
            spec_key,
            outcome,
            Side(_text(item["side"])),
            _int(item["price"]),
            _int(item["new_quantity"]),
            sequence,
            scope,
            timing,
            provenance,
        )
    solicited = item["solicited"]
    if not isinstance(solicited, bool):
        raise ArtifactError("solicited must be a boolean")
    return BookSnapshot(
        spec_key,
        outcome,
        _decode_levels(item["bids"]),
        _decode_levels(item["asks"]),
        sequence,
        scope,
        timing,
        provenance,
        solicited,
    )


def _decode_resolution(value: object) -> ResolutionRecord:
    item = _closed(_obj(value), {"provenance", "received_at", "resolution", "spec_key"})
    return ResolutionRecord(
        _text(item["spec_key"]),
        OfficialResolution(_text(item["resolution"])),
        _time(item["received_at"]),
        _decode_prov(item["provenance"]),
    )


def _decode_levels(value: object) -> tuple[BookLevel, ...]:
    levels = []
    for entry in _list(value):
        pair = _list(entry)
        if len(pair) != 2:
            raise ArtifactError("a book level is malformed")
        levels.append(BookLevel(_int(pair[0]), _int(pair[1])))
    return tuple(levels)


def _decode_prov(value: object) -> Provenance:
    parts = _list(value)
    if len(parts) != 5:
        raise ArtifactError("a provenance entry is malformed")
    return Provenance(
        _text(parts[0]), _int(parts[1]), _int(parts[2]), _text(parts[3]), _int(parts[4])
    )


def _frame(value: object) -> FrameEntry:
    parts = _list(value)
    if len(parts) != 7:
        raise ArtifactError("a frame entry is malformed")
    reason = parts[4]
    connection = parts[5]
    return FrameEntry(
        _int(parts[0]),
        _int(parts[1]),
        Disposition(_text(parts[2])),
        _int(parts[3]),
        None if reason is None else _text(reason),
        None if connection is None else _int(connection),
        _int(parts[6]),
    )


def _segment(value: object) -> tuple[int, str, str, int]:
    parts = _list(value)
    if len(parts) != 4 or parts[1] not in ("finalized", "salvaged") or not is_sha256(parts[2]):
        raise ArtifactError("a segment entry is malformed")
    return _int(parts[0]), _text(parts[1]), _text(parts[2]), _int(parts[3])


def _document(data: bytes) -> dict[str, object]:
    if not data.endswith(b"\n"):
        raise ArtifactError("an artifact file is incomplete")
    try:
        return parse_canonical_json(data[:-1])
    except FormatError:
        raise ArtifactError("an artifact file is not canonical JSON") from None


def _closed(value: Mapping[str, object], keys: set[str]) -> Mapping[str, object]:
    if set(value) != keys:
        raise ArtifactError("an artifact record does not match its schema")
    return value


def _obj(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ArtifactError("an artifact record is not an object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ArtifactError("an artifact field is not a list")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ArtifactError("an artifact field is not text")
    return value


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactError("an artifact field is not an integer")
    return value


def _time(value: object) -> datetime:
    text = _text(value)
    if not is_timestamp(text):
        raise ArtifactError("an artifact timestamp is malformed")
    return parse_timestamp(text)


def _opt_time(value: object) -> datetime | None:
    return None if value is None else _time(value)
