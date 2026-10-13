"""PMV raw frame format v1 (``pmv.raw.frames``).

A raw object is the magic line ``PMVRAW1\\n`` followed by frames. Each frame is a 4-byte
unsigned big-endian header length, an 8-byte unsigned big-endian payload length, the
header as canonical JSON, and the payload bytes. Payload frames carry the exact
application-level bytes delivered to PMV; event frames carry an empty payload. One
sequence counter covers both kinds: it starts at 0 and increases by exactly 1.

Readers check every declared length against the format maximum and against the bytes
remaining before reading it, so a corrupt or hostile length field never causes a large
allocation.
"""

import hashlib
import struct
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final, Protocol

from pmv.integrity import (
    FormatError,
    canonical_json,
    format_timestamp,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
    to_utc,
)

__all__ = [
    "MAGIC",
    "MAX_HEADER_BYTES",
    "MAX_PAYLOAD_BYTES",
    "PREFIX",
    "ByteStream",
    "EventFrame",
    "EventType",
    "Frame",
    "FrameReader",
    "ObjectSummary",
    "OversizePayloadError",
    "PayloadFrame",
    "RawFormatError",
    "canonical_json",
    "encode_event_frame",
    "encode_payload_frame",
    "format_timestamp",
    "is_sha256",
    "is_timestamp",
    "parse_canonical_json",
    "summarize_object",
    "to_utc",
]

MAGIC: Final = b"PMVRAW1\n"
FORMAT_NAME: Final = "pmv.raw.frames"
FORMAT_VERSION: Final = 1
FRAME_VERSION: Final = 1
MAX_HEADER_BYTES: Final = 65_536
MAX_PAYLOAD_BYTES: Final = 67_108_864
PREFIX: Final = struct.Struct(">IQ")

_PAYLOAD_KEYS: Final = frozenset(
    {
        "frame_version",
        "kind",
        "malformed",
        "payload_sha256",
        "received_at",
        "sequence",
        "source_timestamp",
        "written_at",
    }
)
_EVENT_KEYS: Final = frozenset({"event_type", "frame_version", "kind", "sequence", "written_at"})


class ByteStream(Protocol):
    """A readable binary stream (a buffered file or an in-memory buffer)."""

    def read(self, size: int = -1, /) -> bytes: ...


# Raw-format errors are canonical-metadata format errors; the name is kept for callers.
RawFormatError = FormatError


class OversizePayloadError(RawFormatError):
    """A payload is larger than MAX_PAYLOAD_BYTES."""


class EventType(StrEnum):
    """Operational events recorded as event frames."""

    RECONNECT = "reconnect"
    RATE_LIMIT = "rate_limit"
    GAP = "gap"
    DISK_WARNING = "disk_warning"
    DISK_HARD_STOP = "disk_hard_stop"
    SOURCE_CLOCK_REGRESSION = "source_clock_regression"
    LOCAL_CLOCK_REGRESSION = "local_clock_regression"


_EVENT_TYPE_VALUES: Final = frozenset(member.value for member in EventType)


@dataclass(frozen=True, slots=True)
class PayloadFrame:
    sequence: int
    received_at: str
    written_at: str
    source_timestamp: str | None
    payload_sha256: str
    malformed: bool
    payload: bytes


@dataclass(frozen=True, slots=True)
class EventFrame:
    sequence: int
    written_at: str
    event_type: EventType


Frame = PayloadFrame | EventFrame


def encode_payload_frame(
    *,
    sequence: int,
    payload: bytes,
    received_at: datetime,
    written_at: datetime,
    source_timestamp: datetime | None,
    malformed: bool,
) -> bytes:
    """Encode one payload frame around the exact ``payload`` bytes."""
    if type(payload) is not bytes:
        raise TypeError("payload must be bytes")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise OversizePayloadError(
            f"payload of {len(payload)} bytes exceeds the v1 limit of {MAX_PAYLOAD_BYTES} bytes"
        )
    if not isinstance(malformed, bool):
        raise TypeError("malformed must be a bool")
    header: dict[str, object] = {
        "frame_version": FRAME_VERSION,
        "kind": "payload",
        "malformed": malformed,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "received_at": format_timestamp(received_at),
        "sequence": _check_sequence(sequence),
        "source_timestamp": None
        if source_timestamp is None
        else format_timestamp(source_timestamp),
        "written_at": format_timestamp(written_at),
    }
    return _encode(header, payload)


def encode_event_frame(*, sequence: int, event_type: EventType, written_at: datetime) -> bytes:
    """Encode one event frame. Event frames have an empty payload."""
    header: dict[str, object] = {
        "event_type": EventType(event_type).value,
        "frame_version": FRAME_VERSION,
        "kind": "event",
        "sequence": _check_sequence(sequence),
        "written_at": format_timestamp(written_at),
    }
    return _encode(header, b"")


@dataclass(frozen=True, slots=True)
class ObjectSummary:
    """Facts derived by fully validating a raw object."""

    size_bytes: int
    sha256: str
    record_count: int
    payload_count: int
    event_count: int
    malformed_count: int
    event_counts: Mapping[EventType, int] = field(default_factory=dict)
    first_received_at: str | None = None
    last_received_at: str | None = None
    first_source_timestamp: str | None = None
    last_source_timestamp: str | None = None


class FrameReader:
    """Validate a raw object of known ``size`` while reading it frame by frame.

    ``frames()`` checks the magic, every length (against the format maximum and the bytes
    remaining), the closed header schema, sequence continuity, and each payload SHA-256,
    and requires the object to end exactly after the last frame.
    """

    def __init__(self, stream: ByteStream, size: int) -> None:
        self._stream = stream
        self._remaining = size
        self._size = size
        self._hash = hashlib.sha256()
        self._complete = False

    @property
    def sha256(self) -> str:
        if not self._complete:
            raise RawFormatError("the object has not been read completely")
        return self._hash.hexdigest()

    def frames(self) -> Iterator[Frame]:
        if self._read(len(MAGIC)) != MAGIC:
            raise RawFormatError("the object does not start with the PMVRAW1 magic")
        sequence = 0
        while self._remaining:
            if self._remaining < PREFIX.size:
                raise RawFormatError(f"frame {sequence}: truncated length prefix")
            header_length, payload_length = PREFIX.unpack(self._read(PREFIX.size))
            if header_length == 0 or header_length > MAX_HEADER_BYTES:
                raise RawFormatError(f"frame {sequence}: header length is out of range")
            if payload_length > MAX_PAYLOAD_BYTES:
                raise RawFormatError(f"frame {sequence}: payload length is out of range")
            if header_length + payload_length > self._remaining:
                raise RawFormatError(f"frame {sequence}: frame extends past the end of the object")
            header = parse_canonical_json(self._read(header_length))
            yield _decode(header, self._read(payload_length), sequence)
            sequence += 1
        if self._stream.read(1):
            raise RawFormatError("the object is longer than its recorded size")
        self._complete = True

    def _read(self, count: int) -> bytes:
        data = self._stream.read(count)
        if len(data) != count:
            raise RawFormatError("unexpected end of the object")
        self._hash.update(data)
        self._remaining -= count
        return data


def summarize_object(stream: ByteStream, size: int) -> ObjectSummary:
    """Fully validate a raw object and return its size, SHA-256, and observations."""
    reader = FrameReader(stream, size)
    payload_count = event_count = malformed_count = 0
    event_counts: dict[EventType, int] = {}
    first_received: str | None = None
    last_received: str | None = None
    first_source: str | None = None
    last_source: str | None = None
    record_count = 0
    for frame in reader.frames():
        record_count += 1
        if isinstance(frame, PayloadFrame):
            payload_count += 1
            malformed_count += int(frame.malformed)
            first_received = first_received or frame.received_at
            last_received = frame.received_at
            if frame.source_timestamp is not None:
                first_source = first_source or frame.source_timestamp
                last_source = frame.source_timestamp
        else:
            event_count += 1
            event_counts[frame.event_type] = event_counts.get(frame.event_type, 0) + 1
    return ObjectSummary(
        size_bytes=size,
        sha256=reader.sha256,
        record_count=record_count,
        payload_count=payload_count,
        event_count=event_count,
        malformed_count=malformed_count,
        event_counts=event_counts,
        first_received_at=first_received,
        last_received_at=last_received,
        first_source_timestamp=first_source,
        last_source_timestamp=last_source,
    )


def _encode(header: Mapping[str, object], payload: bytes) -> bytes:
    header_bytes = canonical_json(header)
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise RawFormatError("frame header exceeds the v1 limit")
    return PREFIX.pack(len(header_bytes), len(payload)) + header_bytes + payload


def _check_sequence(sequence: int) -> int:
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise ValueError("sequence must be a non-negative integer")
    return sequence


def _decode(header: Mapping[str, object], payload: bytes, expected_sequence: int) -> Frame:
    where = f"frame {expected_sequence}"
    version = header.get("frame_version")
    if isinstance(version, bool) or version != FRAME_VERSION:
        raise RawFormatError(f"{where}: unsupported frame_version")
    sequence = header.get("sequence")
    if isinstance(sequence, bool) or sequence != expected_sequence:
        raise RawFormatError(f"{where}: sequence is not continuous")
    written_at = _timestamp_field(header, "written_at", where)
    kind = header.get("kind")
    if kind == "payload":
        if set(header) != _PAYLOAD_KEYS:
            raise RawFormatError(f"{where}: payload header keys do not match the v1 schema")
        received_at = _timestamp_field(header, "received_at", where)
        source_timestamp = (
            None
            if header["source_timestamp"] is None
            else _timestamp_field(header, "source_timestamp", where)
        )
        digest = header["payload_sha256"]
        if not isinstance(digest, str) or not is_sha256(digest):
            raise RawFormatError(f"{where}: invalid payload_sha256")
        malformed = header["malformed"]
        if not isinstance(malformed, bool):
            raise RawFormatError(f"{where}: invalid malformed flag")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise RawFormatError(f"{where}: payload SHA-256 does not match")
        return PayloadFrame(
            sequence=expected_sequence,
            received_at=received_at,
            written_at=written_at,
            source_timestamp=source_timestamp,
            payload_sha256=digest,
            malformed=malformed,
            payload=payload,
        )
    if kind == "event":
        if set(header) != _EVENT_KEYS:
            raise RawFormatError(f"{where}: event header keys do not match the v1 schema")
        if payload:
            raise RawFormatError(f"{where}: event frames must have an empty payload")
        raw_type = header["event_type"]
        if not isinstance(raw_type, str) or raw_type not in _EVENT_TYPE_VALUES:
            raise RawFormatError(f"{where}: unknown event_type")
        return EventFrame(
            sequence=expected_sequence, written_at=written_at, event_type=EventType(raw_type)
        )
    raise RawFormatError(f"{where}: unknown frame kind")


def _timestamp_field(header: Mapping[str, object], key: str, where: str) -> str:
    value = header.get(key)
    if not isinstance(value, str) or not is_timestamp(value):
        raise RawFormatError(f"{where}: invalid {key}")
    return value
