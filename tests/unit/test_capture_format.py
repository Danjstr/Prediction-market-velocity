"""Tests for raw frame format v2 (F-12, F-27): schema, version refusal, prefix scanning."""

import hashlib
import io
import json
import struct
from datetime import UTC, datetime

import pytest

from pmv.capture_format import (
    MAGIC,
    CaptureFormatError,
    Direction,
    EventFrame,
    EventType,
    PayloadFrame,
    SegmentHeader,
    SegmentReader,
    TailDisposition,
    VenueEnvironment,
    detect_format,
    encode_event,
    encode_payload,
    encode_segment_header,
    scan_prefix,
    summarize_segment,
)
from pmv.integrity import canonical_json
from pmv.raw_format import MAGIC as V1_MAGIC
from pmv.raw_format import FrameReader, RawFormatError, encode_payload_frame

SESSION = "20261016T120000.000000Z_" + "a" * 32
DOMAIN = "b" * 32
WALL = "2026-10-16T12:00:00.000000Z"
LATER = "2026-10-16T12:00:01.000000Z"


def header(**overrides: object) -> SegmentHeader:
    values: dict[str, object] = {
        "sequence": 0,
        "session_id": SESSION,
        "segment_index": 0,
        "previous_segment_sha256": None,
        "previous_last_sequence": None,
        "source_id": "unit_source",
        "feed_id": "unit_feed",
        "endpoint_id": "unit_ws",
        "transport": "websocket",
        "deployment_environment": "test",
        "venue_environment": VenueEnvironment.SYNTHETIC,
        "clock_domain": DOMAIN,
        "session_started_at": WALL,
        "written_at": WALL,
        "monotonic_ns": 5,
    }
    values.update(overrides)
    return SegmentHeader(**values)  # type: ignore[arg-type]  # test helper forwards typed fields


def opened(sequence: int, connection: int = 0) -> bytes:
    return encode_event(
        sequence=sequence,
        event_type=EventType.CONNECTION_OPENED,
        connection=connection,
        written_at=WALL,
        monotonic_ns=6,
    )


def inbound(sequence: int, payload: bytes = b'{"x":1}', **overrides: object) -> bytes:
    values: dict[str, object] = {
        "sequence": sequence,
        "payload": payload,
        "direction": Direction.INBOUND,
        "connection": 0,
        "observed_at": WALL,
        "monotonic_ns": 10 + sequence,
        "source_timestamp": None,
        "malformed": False,
        "written_at": WALL,
    }
    values.update(overrides)
    return encode_payload(**values)  # type: ignore[arg-type]  # test helper forwards typed fields


def closed(sequence: int) -> bytes:
    return encode_event(
        sequence=sequence,
        event_type=EventType.SESSION_CLOSED,
        connection=None,
        written_at=LATER,
        monotonic_ns=99,
    )


def segment(*frames: bytes, first: SegmentHeader | None = None) -> bytes:
    return MAGIC + encode_segment_header(first or header()) + b"".join(frames)


def read(data: bytes) -> list[object]:
    return list(SegmentReader(io.BytesIO(data), len(data)).frames())


def raw_frame(document: dict[str, object], payload: bytes = b"") -> bytes:
    body = canonical_json(document)
    return struct.pack(">IQ", len(body), len(payload)) + body + payload


def test_a_complete_segment_round_trips_exactly() -> None:
    data = segment(
        opened(1),
        inbound(2, b"\x00exact bytes\xff"),
        inbound(3, b"out", direction=Direction.OUTBOUND),
        closed(4),
    )
    frames = read(data)
    assert isinstance(frames[0], SegmentHeader)
    assert isinstance(frames[2], PayloadFrame)
    assert frames[2].payload == b"\x00exact bytes\xff"
    assert frames[2].direction is Direction.INBOUND
    assert frames[2].monotonic_ns == 12
    assert isinstance(frames[3], PayloadFrame)
    assert frames[3].direction is Direction.OUTBOUND
    assert isinstance(frames[4], EventFrame)
    summary = summarize_segment(io.BytesIO(data), len(data))
    assert summary.sha256 == hashlib.sha256(data).hexdigest()
    assert (summary.inbound_count, summary.outbound_count, summary.frame_count) == (1, 1, 5)
    assert summary.session_closed
    assert (summary.first_sequence, summary.last_sequence) == (0, 4)


def test_v1_and_v2_are_never_read_as_each_other() -> None:
    v2 = segment(opened(1))
    v1 = V1_MAGIC + encode_payload_frame(
        sequence=0,
        payload=b"x",
        received_at=datetime(2026, 1, 1, tzinfo=UTC),
        written_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_timestamp=None,
        malformed=False,
    )
    assert detect_format(v2) == 2
    assert detect_format(v1) == 1
    assert detect_format(b"PMVRAW3\n") is None
    with pytest.raises(CaptureFormatError, match="PMVRAW2 magic"):
        read(v1)
    with pytest.raises(RawFormatError, match="PMVRAW1 magic"):
        list(FrameReader(io.BytesIO(v2), len(v2)).frames())
    # a v1 frame inside a v2 object is refused by its frame_version
    v1_frame_in_v2 = MAGIC + encode_segment_header(header()) + v1[len(V1_MAGIC) :]
    with pytest.raises(CaptureFormatError, match="frame_version"):
        read(v1_frame_in_v2)


def test_the_first_frame_must_be_the_only_segment_header() -> None:
    with pytest.raises(CaptureFormatError, match="segment header"):
        read(MAGIC + opened(0))
    second = encode_segment_header(
        header(
            sequence=2, segment_index=1, previous_segment_sha256="c" * 64, previous_last_sequence=1
        )
    )
    with pytest.raises(CaptureFormatError, match="must be first"):
        read(segment(opened(1), second))
    with pytest.raises(CaptureFormatError, match="no header"):
        read(MAGIC)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"segment_index": 0, "previous_segment_sha256": "c" * 64}, "no predecessor"),
        ({"segment_index": 1, "sequence": 5}, "previous_segment_sha256"),
        (
            {
                "segment_index": 1,
                "sequence": 5,
                "previous_segment_sha256": "c" * 64,
                "previous_last_sequence": 3,
            },
            "does not follow",
        ),
        ({"clock_domain": "short"}, "clock_domain"),
        ({"transport": "carrier_pigeon"}, "transport"),
        ({"deployment_environment": "staging"}, "deployment_environment"),
        ({"session_id": "not-a-session"}, "session_id"),
    ],
)
def test_segment_headers_are_strict(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(CaptureFormatError, match=message):
        header(**overrides)


def test_unknown_or_extra_header_keys_are_refused() -> None:
    document = header().to_json() | {"extra": 1}
    with pytest.raises(CaptureFormatError, match="v2 schema"):
        read(MAGIC + raw_frame(document))
    unknown_environment = header().to_json() | {"venue_environment": "staging"}
    with pytest.raises(CaptureFormatError, match="venue_environment"):
        read(MAGIC + raw_frame(unknown_environment))


def test_sequence_must_be_continuous() -> None:
    with pytest.raises(CaptureFormatError, match="continuous"):
        read(segment(opened(1), inbound(3)))


def test_payload_hash_mismatch_is_refused() -> None:
    frame = bytearray(inbound(1))
    frame[-1] ^= 0x01
    with pytest.raises(CaptureFormatError, match="SHA-256"):
        read(segment(bytes(frame)))


def test_outbound_frames_carry_no_source_time_or_malformed_flag() -> None:
    with pytest.raises(CaptureFormatError, match="outbound"):
        inbound(1, direction=Direction.OUTBOUND, source_timestamp=WALL)
    with pytest.raises(CaptureFormatError, match="outbound"):
        inbound(1, direction=Direction.OUTBOUND, malformed=True)


def test_connection_events_must_name_a_connection() -> None:
    with pytest.raises(CaptureFormatError, match="name their connection"):
        encode_event(
            sequence=1,
            event_type=EventType.CONNECTION_CLOSED,
            connection=None,
            written_at=WALL,
            monotonic_ns=1,
        )


def test_nothing_may_follow_session_closed_or_the_object_end() -> None:
    with pytest.raises(CaptureFormatError, match="follows session_closed"):
        read(segment(closed(1), opened(2)))
    data = segment(opened(1))
    with pytest.raises(CaptureFormatError, match="longer than its recorded size"):
        list(SegmentReader(io.BytesIO(data + b"x"), len(data)).frames())
    with pytest.raises(CaptureFormatError):
        read(data[:-1])


def test_lengths_are_checked_before_reading() -> None:
    huge = struct.pack(">IQ", 1, 2**62)
    with pytest.raises(CaptureFormatError, match="out of range"):
        read(segment(huge + b"{"))


def test_frame_headers_must_be_canonical_json() -> None:
    document = json.loads(canonical_json(header().to_json()))
    noncanonical = json.dumps(document, indent=1).encode("ascii")
    frame = struct.pack(">IQ", len(noncanonical), 0) + noncanonical
    with pytest.raises(CaptureFormatError, match="canonical"):
        read(MAGIC + frame)


# ----- prefix scanning (F-11 salvage) -----


def test_a_complete_object_scans_as_fully_valid() -> None:
    data = segment(opened(1), inbound(2), closed(3))
    scan = scan_prefix(data)
    assert (scan.valid_bytes, scan.frame_count, scan.last_sequence) == (len(data), 4, 3)
    assert scan.tail is TailDisposition.NONE
    assert scan.session_closed


def test_a_torn_last_frame_is_excluded_and_reported() -> None:
    good = segment(opened(1), inbound(2))
    torn = good + inbound(3)[:7]
    scan = scan_prefix(torn)
    assert scan.valid_bytes == len(good)
    assert scan.frame_count == 3
    assert scan.tail is TailDisposition.INCOMPLETE_FRAME
    assert not scan.session_closed


def test_nothing_after_an_invalid_frame_is_used() -> None:
    good = segment(opened(1))
    bad = bytearray(inbound(2))
    bad[-1] ^= 0xFF
    data = good + bytes(bad) + inbound(3)
    scan = scan_prefix(data)
    assert scan.valid_bytes == len(good)
    assert scan.tail is TailDisposition.INVALID_FRAME


def test_frames_after_session_closed_are_invalid_tail() -> None:
    good = segment(closed(1))
    scan = scan_prefix(good + opened(2))
    assert scan.valid_bytes == len(good)
    assert scan.tail is TailDisposition.INVALID_FRAME


@pytest.mark.parametrize("data", [b"", MAGIC[:3], MAGIC, MAGIC + b"\x00\x00"])
def test_no_header_means_nothing_is_recoverable(data: bytes) -> None:
    scan = scan_prefix(data)
    assert scan.header is None
    assert scan.valid_bytes == 0
    assert scan.tail is TailDisposition.INCOMPLETE_FRAME


def test_a_wrong_magic_is_an_invalid_object() -> None:
    scan = scan_prefix(b"NOTPMV!!" + b"x" * 20)
    assert scan.header is None
    assert scan.tail is TailDisposition.INVALID_FRAME


def test_a_prefix_is_itself_a_valid_segment() -> None:
    good = segment(opened(1), inbound(2))
    scan = scan_prefix(good + b"\x00\x00\x00")
    prefix = (good + b"\x00\x00\x00")[: scan.valid_bytes]
    assert prefix == good
    assert len(read(prefix)) == 3
