"""PMV raw frame format v2 (``pmv.raw.frames`` v2), for segmented prospective capture.

Step 11 F-12 (with F-27) requires monotonic receipt time and message direction before real
collection; F-11 requires bounded segments. Version 1 (``pmv.raw_format``) has neither, so
v2 is a new format with its own magic. A v1 object is never read as v2, or the reverse:
each reader checks its own magic and frame version and refuses anything else
(``detect_format`` dispatches explicitly).

A v2 object is one **segment** of a capture **session**: the magic line ``PMVRAW2\\n``,
then frames. The framing is v1's: a 4-byte big-endian header length, an 8-byte big-endian
payload length, the header as canonical JSON, then the payload bytes. Frame kinds:

- ``segment`` (exactly once, first): the segment header. It names the session and the
  segment index, the source and its venue environment (RT-B2-09: every frame belongs to an
  object that carries its environment identity), the monotonic clock domain, and, after
  the first segment, the SHA-256 and last sequence of the previous segment. Segments are
  therefore hash-chained, and a missing, replaced, or reordered segment is detectable.
- ``payload``: the exact application-level bytes, with ``direction`` (``inbound`` from the
  source, ``outbound`` from PMV), the ``connection`` index within the session, the wall
  time ``observed_at`` (inbound: delivered to PMV; outbound: handed by PMV to its client
  layer), the monotonic time ``monotonic_ns`` at that moment, an optional caller-supplied
  ``source_timestamp`` (inbound only), and ``malformed`` (inbound only).
- ``event``: an operational event with an empty payload.

One ``sequence`` counter covers every frame of a session, across its segments: it starts
at 0 and increases by exactly 1. Sequence, not any clock, is the ordering authority.

``monotonic_ns`` values are ``CLOCK_MONOTONIC`` nanoseconds. They are comparable only
within one ``clock_domain`` (one boot of one host), never across hosts or boots, and they
are not timestamps. They measure intervals and order within a session; they never replace
``observed_at``.

The raw layer never parses payloads. A venue's own sequence numbers live inside payloads
and are extracted by the normalizer, not here.
"""

import hashlib
import re
import struct
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from pmv.integrity import (
    FormatError,
    canonical_json,
    is_identifier,
    is_sha256,
    is_timestamp,
    is_timestamp_id,
    parse_canonical_json,
)

__all__ = [
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "MAGIC",
    "MAX_HEADER_BYTES",
    "MAX_PAYLOAD_BYTES",
    "CaptureFormatError",
    "Direction",
    "EventFrame",
    "EventType",
    "Frame",
    "PayloadFrame",
    "PrefixScan",
    "SegmentHeader",
    "SegmentReader",
    "SegmentSummary",
    "TailDisposition",
    "VenueEnvironment",
    "detect_format",
    "encode_event",
    "encode_payload",
    "encode_segment_header",
    "scan_prefix",
    "summarize_segment",
]

MAGIC: Final = b"PMVRAW2\n"
V1_MAGIC: Final = b"PMVRAW1\n"
FORMAT_NAME: Final = "pmv.raw.frames"
FORMAT_VERSION: Final = 2
FRAME_VERSION: Final = 2
MAX_HEADER_BYTES: Final = 65_536
MAX_PAYLOAD_BYTES: Final = 67_108_864
PREFIX: Final = struct.Struct(">IQ")
CLOCK_DOMAIN: Final = re.compile(r"[0-9a-f]{32}")


class CaptureFormatError(FormatError):
    """A v2 object or frame is malformed. Messages never contain payload bytes."""


class ByteStream(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class VenueEnvironment(StrEnum):
    """Which environment of a source the bytes came from (Step 11 F-37, RT-B2-09)."""

    SYNTHETIC = "synthetic"
    DEMO = "demo"
    PRODUCTION = "production"


class EventType(StrEnum):
    CONNECTION_OPENED = "connection_opened"
    CONNECTION_CLOSED = "connection_closed"
    GAP = "gap"
    RATE_LIMIT = "rate_limit"
    DISK_WARNING = "disk_warning"
    DISK_HARD_STOP = "disk_hard_stop"
    SOURCE_CLOCK_REGRESSION = "source_clock_regression"
    LOCAL_CLOCK_REGRESSION = "local_clock_regression"
    MONOTONIC_REGRESSION = "monotonic_regression"
    SESSION_CLOSED = "session_closed"


CONNECTION_EVENTS: Final = frozenset({EventType.CONNECTION_OPENED, EventType.CONNECTION_CLOSED})
_EVENT_VALUES: Final = frozenset(member.value for member in EventType)
_TRANSPORTS: Final = frozenset({"websocket", "http"})
_ENVIRONMENTS: Final = frozenset({"development", "test", "shadow", "production"})

_SEGMENT_KEYS: Final = frozenset(
    {
        "clock_domain",
        "deployment_environment",
        "endpoint_id",
        "feed_id",
        "frame_version",
        "kind",
        "monotonic_ns",
        "previous_last_sequence",
        "previous_segment_sha256",
        "segment_index",
        "sequence",
        "session_id",
        "session_started_at",
        "source_id",
        "transport",
        "venue_environment",
        "written_at",
    }
)
_PAYLOAD_KEYS: Final = frozenset(
    {
        "connection",
        "direction",
        "frame_version",
        "kind",
        "malformed",
        "monotonic_ns",
        "observed_at",
        "payload_sha256",
        "sequence",
        "source_timestamp",
        "written_at",
    }
)
_EVENT_KEYS: Final = frozenset(
    {"connection", "event_type", "frame_version", "kind", "monotonic_ns", "sequence", "written_at"}
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SegmentHeader:
    sequence: int
    session_id: str
    segment_index: int
    previous_segment_sha256: str | None
    previous_last_sequence: int | None
    source_id: str
    feed_id: str
    endpoint_id: str
    transport: str
    deployment_environment: str
    venue_environment: VenueEnvironment
    clock_domain: str
    session_started_at: str
    written_at: str
    monotonic_ns: int

    def __post_init__(self) -> None:
        if not is_timestamp_id(self.session_id):
            raise CaptureFormatError("segment header: malformed session_id")
        _count(self.segment_index, "segment_index")
        _count(self.sequence, "sequence")
        _count(self.monotonic_ns, "monotonic_ns")
        if self.segment_index == 0:
            if (
                self.previous_segment_sha256 is not None
                or self.previous_last_sequence is not None
                or self.sequence != 0
            ):
                raise CaptureFormatError("segment header: the first segment has no predecessor")
        else:
            if not is_sha256(self.previous_segment_sha256):
                raise CaptureFormatError("segment header: missing previous_segment_sha256")
            previous = _count(self.previous_last_sequence, "previous_last_sequence")
            if self.sequence != previous + 1:
                raise CaptureFormatError("segment header: sequence does not follow its predecessor")
        for name in ("source_id", "feed_id", "endpoint_id"):
            if not is_identifier(getattr(self, name)):
                raise CaptureFormatError(f"segment header: malformed {name}")
        if self.transport not in _TRANSPORTS:
            raise CaptureFormatError("segment header: unknown transport")
        if self.deployment_environment not in _ENVIRONMENTS:
            raise CaptureFormatError("segment header: unknown deployment_environment")
        if not isinstance(self.venue_environment, VenueEnvironment):
            raise CaptureFormatError("segment header: unknown venue_environment")
        if (
            not isinstance(self.clock_domain, str)
            or CLOCK_DOMAIN.fullmatch(self.clock_domain) is None
        ):
            raise CaptureFormatError("segment header: malformed clock_domain")
        for name in ("session_started_at", "written_at"):
            if not is_timestamp(getattr(self, name)):
                raise CaptureFormatError(f"segment header: malformed {name}")

    def to_json(self) -> dict[str, object]:
        return {
            "clock_domain": self.clock_domain,
            "deployment_environment": self.deployment_environment,
            "endpoint_id": self.endpoint_id,
            "feed_id": self.feed_id,
            "frame_version": FRAME_VERSION,
            "kind": "segment",
            "monotonic_ns": self.monotonic_ns,
            "previous_last_sequence": self.previous_last_sequence,
            "previous_segment_sha256": self.previous_segment_sha256,
            "segment_index": self.segment_index,
            "sequence": self.sequence,
            "session_id": self.session_id,
            "session_started_at": self.session_started_at,
            "source_id": self.source_id,
            "transport": self.transport,
            "venue_environment": self.venue_environment.value,
            "written_at": self.written_at,
        }


@dataclass(frozen=True, slots=True)
class PayloadFrame:
    sequence: int
    direction: Direction
    connection: int
    observed_at: str
    monotonic_ns: int
    source_timestamp: str | None
    payload_sha256: str
    malformed: bool
    written_at: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class EventFrame:
    sequence: int
    event_type: EventType
    connection: int | None
    written_at: str
    monotonic_ns: int


Frame = SegmentHeader | PayloadFrame | EventFrame


def detect_format(prefix: bytes) -> int | None:
    """1 or 2 for a PMV raw object's leading bytes, otherwise None. Never guesses."""
    if prefix[: len(MAGIC)] == MAGIC:
        return 2
    if prefix[: len(V1_MAGIC)] == V1_MAGIC:
        return 1
    return None


def encode_segment_header(header: SegmentHeader) -> bytes:
    return _encode(header.to_json(), b"")


def encode_payload(
    *,
    sequence: int,
    payload: bytes,
    direction: Direction,
    connection: int,
    observed_at: str,
    monotonic_ns: int,
    source_timestamp: str | None,
    malformed: bool,
    written_at: str,
) -> bytes:
    """Encode one payload frame around the exact ``payload`` bytes."""
    if type(payload) is not bytes:
        raise TypeError("payload must be bytes")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise CaptureFormatError("payload exceeds the v2 limit")
    header: dict[str, object] = {
        "connection": _count(connection, "connection"),
        "direction": Direction(direction).value,
        "frame_version": FRAME_VERSION,
        "kind": "payload",
        "malformed": malformed,
        "monotonic_ns": _count(monotonic_ns, "monotonic_ns"),
        "observed_at": observed_at,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "sequence": _count(sequence, "sequence"),
        "source_timestamp": source_timestamp,
        "written_at": written_at,
    }
    _check_payload_header(header, "payload frame")
    return _encode(header, payload)


def encode_event(
    *,
    sequence: int,
    event_type: EventType,
    connection: int | None,
    written_at: str,
    monotonic_ns: int,
) -> bytes:
    header: dict[str, object] = {
        "connection": connection,
        "event_type": EventType(event_type).value,
        "frame_version": FRAME_VERSION,
        "kind": "event",
        "monotonic_ns": _count(monotonic_ns, "monotonic_ns"),
        "sequence": _count(sequence, "sequence"),
        "written_at": written_at,
    }
    _check_event_header(header, "event frame")
    return _encode(header, b"")


class SegmentReader:
    """Validate one complete v2 segment object of known ``size`` while reading it.

    ``frames()`` checks the magic, every length, the closed header schemas, that the first
    frame (and only the first) is the segment header, sequence continuity from the header,
    each payload SHA-256, that ``session_closed`` (if present) is the last frame, and that
    the object ends exactly after its last frame.
    """

    def __init__(self, stream: ByteStream, size: int) -> None:
        self._stream = stream
        self._remaining = size
        self._hash = hashlib.sha256()
        self._complete = False
        self.header: SegmentHeader | None = None
        self.last_sequence: int | None = None

    @property
    def sha256(self) -> str:
        if not self._complete:
            raise CaptureFormatError("the segment has not been read completely")
        return self._hash.hexdigest()

    def frames(self) -> Iterator[Frame]:
        if self._take(len(MAGIC)) != MAGIC:
            raise CaptureFormatError("the object does not start with the PMVRAW2 magic")
        closed = False
        index = 0
        while self._remaining:
            if closed:
                raise CaptureFormatError("a frame follows session_closed")
            frame = self._next_frame(index)
            index += 1
            self.last_sequence = _sequence_of(frame)
            if isinstance(frame, EventFrame) and frame.event_type is EventType.SESSION_CLOSED:
                closed = True
            yield frame
        if self.header is None:
            raise CaptureFormatError("the segment has no header frame")
        if self._stream.read(1):
            raise CaptureFormatError("the object is longer than its recorded size")
        self._complete = True

    def _next_frame(self, index: int) -> Frame:
        if self._remaining < PREFIX.size:
            raise CaptureFormatError(f"frame {index}: truncated length prefix")
        header_length, payload_length = PREFIX.unpack(self._take(PREFIX.size))
        if header_length == 0 or header_length > MAX_HEADER_BYTES:
            raise CaptureFormatError(f"frame {index}: header length is out of range")
        if payload_length > MAX_PAYLOAD_BYTES:
            raise CaptureFormatError(f"frame {index}: payload length is out of range")
        if header_length + payload_length > self._remaining:
            raise CaptureFormatError(f"frame {index}: frame extends past the end of the object")
        try:
            document = parse_canonical_json(self._take(header_length))
        except FormatError:
            raise CaptureFormatError(f"frame {index}: header is not canonical JSON") from None
        payload = self._take(payload_length)
        expected = None if self.last_sequence is None else self.last_sequence + 1
        frame = _decode(document, payload, index, expected)
        if isinstance(frame, SegmentHeader):
            if index != 0:
                raise CaptureFormatError(f"frame {index}: a segment header must be first")
            self.header = frame
        elif index == 0:
            raise CaptureFormatError("frame 0: the first frame must be the segment header")
        return frame

    def _take(self, count: int) -> bytes:
        data = self._stream.read(count)
        if len(data) != count:
            raise CaptureFormatError("unexpected end of the object")
        self._hash.update(data)
        self._remaining -= count
        return data


@dataclass(frozen=True, slots=True)
class SegmentSummary:
    """Facts derived by fully validating one segment object."""

    header: SegmentHeader
    size_bytes: int
    sha256: str
    frame_count: int
    first_sequence: int
    last_sequence: int
    inbound_count: int
    outbound_count: int
    malformed_count: int
    event_counts: Mapping[EventType, int]
    session_closed: bool
    first_observed_at: str | None
    last_observed_at: str | None


def summarize_segment(stream: ByteStream, size: int) -> SegmentSummary:
    reader = SegmentReader(stream, size)
    frames = inbound = outbound = malformed = 0
    events: dict[EventType, int] = {}
    closed = False
    first_observed: str | None = None
    last_observed: str | None = None
    for frame in reader.frames():
        frames += 1
        if isinstance(frame, PayloadFrame):
            if frame.direction is Direction.INBOUND:
                inbound += 1
                malformed += int(frame.malformed)
            else:
                outbound += 1
            first_observed = first_observed or frame.observed_at
            last_observed = frame.observed_at
        elif isinstance(frame, EventFrame):
            events[frame.event_type] = events.get(frame.event_type, 0) + 1
            closed = closed or frame.event_type is EventType.SESSION_CLOSED
    header = reader.header
    if header is None or reader.last_sequence is None:  # frames() guarantees both
        raise CaptureFormatError("the segment has no header frame")
    return SegmentSummary(
        header=header,
        size_bytes=size,
        sha256=reader.sha256,
        frame_count=frames,
        first_sequence=header.sequence,
        last_sequence=reader.last_sequence,
        inbound_count=inbound,
        outbound_count=outbound,
        malformed_count=malformed,
        event_counts=events,
        session_closed=closed,
        first_observed_at=first_observed,
        last_observed_at=last_observed,
    )


class TailDisposition(StrEnum):
    """What follows the longest valid frame prefix of an object (F-11 salvage)."""

    NONE = "none"
    INCOMPLETE_FRAME = "incomplete_frame"
    INVALID_FRAME = "invalid_frame"


@dataclass(frozen=True, slots=True)
class PrefixScan:
    """The longest prefix of an object made only of complete, fully valid frames.

    ``header`` is None when even the magic and segment header are not valid; then nothing
    is recoverable and ``valid_bytes`` is 0.
    """

    header: SegmentHeader | None
    valid_bytes: int
    frame_count: int
    last_sequence: int | None
    total_bytes: int
    tail: TailDisposition
    session_closed: bool


def scan_prefix(data: bytes) -> PrefixScan:
    """Find the longest valid frame prefix of ``data`` (a possibly torn segment object).

    A frame counts only if it is complete and passes every check a full read applies
    (lengths, canonical closed header, sequence continuity, payload SHA-256). The first
    incomplete or invalid frame ends the prefix; nothing after it is ever used, even if it
    looks valid. Nothing is repaired.
    """
    total = len(data)
    if data[: len(MAGIC)] != MAGIC:
        tail = (
            TailDisposition.INCOMPLETE_FRAME
            if MAGIC.startswith(data)
            else TailDisposition.INVALID_FRAME
        )
        return PrefixScan(None, 0, 0, None, total, tail, False)
    offset = len(MAGIC)
    header: SegmentHeader | None = None
    last: int | None = None
    frames = 0
    closed = False
    valid = 0
    while True:
        if offset == total:
            return (
                PrefixScan(header, valid, frames, last, total, TailDisposition.NONE, closed)
                if header is not None
                else PrefixScan(None, 0, 0, None, total, TailDisposition.INCOMPLETE_FRAME, False)
            )
        if closed:
            return PrefixScan(
                header, valid, frames, last, total, TailDisposition.INVALID_FRAME, True
            )
        if total - offset < PREFIX.size:
            return _scan_end(header, valid, frames, last, total, TailDisposition.INCOMPLETE_FRAME)
        header_length, payload_length = PREFIX.unpack_from(data, offset)
        if (
            header_length == 0
            or header_length > MAX_HEADER_BYTES
            or payload_length > MAX_PAYLOAD_BYTES
        ):
            return _scan_end(header, valid, frames, last, total, TailDisposition.INVALID_FRAME)
        end = offset + PREFIX.size + header_length + payload_length
        if end > total:
            return _scan_end(header, valid, frames, last, total, TailDisposition.INCOMPLETE_FRAME)
        start = offset + PREFIX.size
        try:
            document = parse_canonical_json(data[start : start + header_length])
            frame = _decode(
                document,
                data[start + header_length : end],
                frames,
                None if last is None else last + 1,
            )
        except FormatError:
            return _scan_end(header, valid, frames, last, total, TailDisposition.INVALID_FRAME)
        if isinstance(frame, SegmentHeader) != (frames == 0):
            return _scan_end(header, valid, frames, last, total, TailDisposition.INVALID_FRAME)
        if isinstance(frame, SegmentHeader):
            header = frame
        frames += 1
        last = _sequence_of(frame)
        closed = isinstance(frame, EventFrame) and frame.event_type is EventType.SESSION_CLOSED
        offset = end
        valid = end


def _scan_end(
    header: SegmentHeader | None,
    valid: int,
    frames: int,
    last: int | None,
    total: int,
    tail: TailDisposition,
) -> PrefixScan:
    if header is None:
        return PrefixScan(None, 0, 0, None, total, tail, False)
    return PrefixScan(header, valid, frames, last, total, tail, False)


def _sequence_of(frame: Frame) -> int:
    return frame.sequence


def _encode(header: Mapping[str, object], payload: bytes) -> bytes:
    header_bytes = canonical_json(header)
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise CaptureFormatError("frame header exceeds the v2 limit")
    return PREFIX.pack(len(header_bytes), len(payload)) + header_bytes + payload


def _count(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CaptureFormatError(f"{what} must be a non-negative integer")
    return value


def _decode(
    document: Mapping[str, object], payload: bytes, index: int, expected: int | None
) -> Frame:
    where = f"frame {index}"
    version = document.get("frame_version")
    if isinstance(version, bool) or version != FRAME_VERSION:
        raise CaptureFormatError(f"{where}: unsupported frame_version")
    sequence = document.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise CaptureFormatError(f"{where}: invalid sequence")
    if expected is not None and sequence != expected:
        raise CaptureFormatError(f"{where}: sequence is not continuous")
    kind = document.get("kind")
    if kind == "segment":
        if set(document) != _SEGMENT_KEYS or payload:
            raise CaptureFormatError(f"{where}: segment header does not match the v2 schema")
        environment = document["venue_environment"]
        if not isinstance(environment, str) or environment not in {
            item.value for item in VenueEnvironment
        }:
            raise CaptureFormatError(f"{where}: unknown venue_environment")
        try:
            return SegmentHeader(
                sequence=sequence,
                session_id=_str(document, "session_id", where),
                segment_index=_int_field(document, "segment_index", where),
                previous_segment_sha256=_opt_str(document, "previous_segment_sha256", where),
                previous_last_sequence=_opt_int(document, "previous_last_sequence", where),
                source_id=_str(document, "source_id", where),
                feed_id=_str(document, "feed_id", where),
                endpoint_id=_str(document, "endpoint_id", where),
                transport=_str(document, "transport", where),
                deployment_environment=_str(document, "deployment_environment", where),
                venue_environment=VenueEnvironment(environment),
                clock_domain=_str(document, "clock_domain", where),
                session_started_at=_str(document, "session_started_at", where),
                written_at=_str(document, "written_at", where),
                monotonic_ns=_int_field(document, "monotonic_ns", where),
            )
        except CaptureFormatError as exc:
            raise CaptureFormatError(f"{where}: {exc}") from None
    if expected is None:
        raise CaptureFormatError(f"{where}: the first frame must be the segment header")
    if kind == "payload":
        _check_payload_header(document, where)
        if hashlib.sha256(payload).hexdigest() != document["payload_sha256"]:
            raise CaptureFormatError(f"{where}: payload SHA-256 does not match")
        return PayloadFrame(
            sequence=sequence,
            direction=Direction(_str(document, "direction", where)),
            connection=_int_field(document, "connection", where),
            observed_at=_str(document, "observed_at", where),
            monotonic_ns=_int_field(document, "monotonic_ns", where),
            source_timestamp=_opt_str(document, "source_timestamp", where),
            payload_sha256=_str(document, "payload_sha256", where),
            malformed=bool(document["malformed"]),
            written_at=_str(document, "written_at", where),
            payload=payload,
        )
    if kind == "event":
        _check_event_header(document, where)
        if payload:
            raise CaptureFormatError(f"{where}: event frames must have an empty payload")
        return EventFrame(
            sequence=sequence,
            event_type=EventType(_str(document, "event_type", where)),
            connection=_opt_int(document, "connection", where),
            written_at=_str(document, "written_at", where),
            monotonic_ns=_int_field(document, "monotonic_ns", where),
        )
    raise CaptureFormatError(f"{where}: unknown frame kind")


def _check_payload_header(document: Mapping[str, object], where: str) -> None:
    if set(document) != _PAYLOAD_KEYS:
        raise CaptureFormatError(f"{where}: payload header does not match the v2 schema")
    direction = document["direction"]
    if direction not in {item.value for item in Direction}:
        raise CaptureFormatError(f"{where}: invalid direction")
    _int_field(document, "connection", where)
    _int_field(document, "monotonic_ns", where)
    for name in ("observed_at", "written_at"):
        if not is_timestamp(document[name]):
            raise CaptureFormatError(f"{where}: invalid {name}")
    source = document["source_timestamp"]
    if source is not None and not is_timestamp(source):
        raise CaptureFormatError(f"{where}: invalid source_timestamp")
    if not is_sha256(document["payload_sha256"]):
        raise CaptureFormatError(f"{where}: invalid payload_sha256")
    malformed = document["malformed"]
    if not isinstance(malformed, bool):
        raise CaptureFormatError(f"{where}: invalid malformed flag")
    if direction == Direction.OUTBOUND.value and (source is not None or malformed):
        raise CaptureFormatError(f"{where}: outbound frames carry no source time or malformed flag")


def _check_event_header(document: Mapping[str, object], where: str) -> None:
    if set(document) != _EVENT_KEYS:
        raise CaptureFormatError(f"{where}: event header does not match the v2 schema")
    event_type = document["event_type"]
    if not isinstance(event_type, str) or event_type not in _EVENT_VALUES:
        raise CaptureFormatError(f"{where}: unknown event_type")
    connection = _opt_int(document, "connection", where)
    if EventType(event_type) in CONNECTION_EVENTS and connection is None:
        raise CaptureFormatError(f"{where}: connection events name their connection")
    _int_field(document, "monotonic_ns", where)
    if not is_timestamp(document["written_at"]):
        raise CaptureFormatError(f"{where}: invalid written_at")


def _str(document: Mapping[str, object], key: str, where: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise CaptureFormatError(f"{where}: invalid {key}")
    return value


def _opt_str(document: Mapping[str, object], key: str, where: str) -> str | None:
    return None if document.get(key) is None else _str(document, key, where)


def _int_field(document: Mapping[str, object], key: str, where: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CaptureFormatError(f"{where}: invalid {key}")
    return value


def _opt_int(document: Mapping[str, object], key: str, where: str) -> int | None:
    return None if document.get(key) is None else _int_field(document, key, where)
