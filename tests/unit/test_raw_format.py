"""Tests for the PMV raw frame format v1."""

import hashlib
import io
from datetime import UTC, datetime, timedelta, timezone

import pytest

from pmv.raw_format import (
    MAGIC,
    MAX_HEADER_BYTES,
    MAX_PAYLOAD_BYTES,
    PREFIX,
    EventFrame,
    EventType,
    FrameReader,
    OversizePayloadError,
    PayloadFrame,
    RawFormatError,
    canonical_json,
    encode_event_frame,
    encode_payload_frame,
    format_timestamp,
    parse_canonical_json,
    summarize_object,
)

T0 = datetime(2026, 10, 13, 3, 40, 21, 123456, tzinfo=UTC)


def payload_frame(sequence: int, payload: bytes, **overrides: object) -> bytes:
    arguments: dict[str, object] = {
        "sequence": sequence,
        "payload": payload,
        "received_at": T0,
        "written_at": T0 + timedelta(microseconds=5),
        "source_timestamp": None,
        "malformed": False,
    }
    arguments.update(overrides)
    return encode_payload_frame(**arguments)  # type: ignore[arg-type]  # test helper forwards typed keywords


def frames_of(data: bytes) -> list[PayloadFrame | EventFrame]:
    return list(FrameReader(io.BytesIO(data), len(data)).frames())


def raw_header(header: dict[str, object], payload: bytes = b"") -> bytes:
    encoded = canonical_json(header)
    return PREFIX.pack(len(encoded), len(payload)) + encoded + payload


def valid_payload_header(sequence: int, payload: bytes) -> dict[str, object]:
    return {
        "frame_version": 1,
        "kind": "payload",
        "malformed": False,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "received_at": format_timestamp(T0),
        "sequence": sequence,
        "source_timestamp": None,
        "written_at": format_timestamp(T0),
    }


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\x00",
        b"line one\nline two\r\n",
        b"\x00\xff\x00\xfe" * 100,
        bytes(range(256)) * 4,
        '{"price": 0.53, "text": "café"}'.encode(),
        b"\x80\x81 not utf-8 \xc3\x28",
    ],
    ids=["empty", "null", "newlines", "nulls", "all-bytes", "utf8-json", "invalid-utf8"],
)
def test_payload_bytes_round_trip_exactly(payload: bytes) -> None:
    data = MAGIC + payload_frame(0, payload)
    (frame,) = frames_of(data)
    assert isinstance(frame, PayloadFrame)
    assert frame.payload == payload
    assert frame.payload_sha256 == hashlib.sha256(payload).hexdigest()


def test_timestamps_are_utc_six_digit_z_and_stay_distinct() -> None:
    eastern = timezone(timedelta(hours=-5))
    data = MAGIC + payload_frame(
        0,
        b"x",
        received_at=datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=eastern),
        written_at=datetime(2026, 1, 2, 8, 4, 5, 7, tzinfo=UTC),
        source_timestamp=datetime(2026, 1, 2, 8, 4, 5, tzinfo=UTC),
    )
    (frame,) = frames_of(data)
    assert isinstance(frame, PayloadFrame)
    assert frame.received_at == "2026-01-02T08:04:05.000006Z"
    assert frame.written_at == "2026-01-02T08:04:05.000007Z"
    assert frame.source_timestamp == "2026-01-02T08:04:05.000000Z"


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        payload_frame(0, b"x", received_at=datetime(2026, 1, 2))  # noqa: DTZ001 - verifies naive datetimes are rejected


def test_sequence_must_be_continuous_from_zero() -> None:
    assert [
        f.sequence for f in frames_of(MAGIC + payload_frame(0, b"a") + payload_frame(1, b"b"))
    ] == [0, 1]
    for data in (
        MAGIC + payload_frame(1, b"a"),
        MAGIC + payload_frame(0, b"a") + payload_frame(2, b"b"),
    ):
        with pytest.raises(RawFormatError, match="sequence is not continuous"):
            frames_of(data)
    with pytest.raises(RawFormatError, match="sequence is not continuous"):
        frames_of(MAGIC + payload_frame(0, b"a") + payload_frame(0, b"a"))


def test_events_share_the_sequence_and_have_no_payload() -> None:
    data = (
        MAGIC
        + payload_frame(0, b"a")
        + encode_event_frame(sequence=1, event_type=EventType.RECONNECT, written_at=T0)
        + payload_frame(2, b"b")
    )
    frames = frames_of(data)
    assert isinstance(frames[1], EventFrame)
    assert frames[1].event_type is EventType.RECONNECT
    event = {"event_type": "gap", "frame_version": 1, "kind": "event", "sequence": 0}
    with_payload = MAGIC + raw_header({**event, "written_at": format_timestamp(T0)}, b"x")
    with pytest.raises(RawFormatError, match="empty payload"):
        frames_of(with_payload)


def test_maximum_payload_is_accepted_and_one_more_byte_is_rejected() -> None:
    at_limit = bytes(MAX_PAYLOAD_BYTES)
    frame = payload_frame(0, at_limit)
    (decoded,) = frames_of(MAGIC + frame)
    assert isinstance(decoded, PayloadFrame)
    assert len(decoded.payload) == MAX_PAYLOAD_BYTES
    with pytest.raises(OversizePayloadError):
        payload_frame(0, at_limit + b"\x00")


def test_declared_lengths_are_checked_before_reading() -> None:
    class GuardedStream(io.BytesIO):
        def read(self, size: int | None = -1, /) -> bytes:
            assert size is not None
            assert 0 <= size <= 1024, "a declared length was read before it was checked"
            return super().read(size)

    oversize_header = PREFIX.pack(MAX_HEADER_BYTES + 1, 0)
    oversize_payload = PREFIX.pack(10, MAX_PAYLOAD_BYTES + 1)
    past_end = PREFIX.pack(10, MAX_PAYLOAD_BYTES)
    zero_header = PREFIX.pack(0, 0)
    for prefix, message in (
        (oversize_header, "header length is out of range"),
        (oversize_payload, "payload length is out of range"),
        (past_end, "extends past the end"),
        (zero_header, "header length is out of range"),
    ):
        data = MAGIC + prefix + b"{}"
        with pytest.raises(RawFormatError, match=message):
            list(FrameReader(GuardedStream(data), len(data)).frames())


def test_truncation_anywhere_is_detected() -> None:
    data = MAGIC + payload_frame(0, b"payload bytes") + payload_frame(1, b"more")
    for cut in (1, len(MAGIC) + 3, len(data) - 1):
        truncated = data[:cut]
        with pytest.raises(RawFormatError):
            frames_of(truncated)


def test_object_longer_than_its_size_is_rejected() -> None:
    data = MAGIC + payload_frame(0, b"a")
    with pytest.raises(RawFormatError, match="longer than its recorded size"):
        list(FrameReader(io.BytesIO(data + b"extra"), len(data)).frames())


def test_missing_magic_is_rejected() -> None:
    with pytest.raises(RawFormatError, match="magic"):
        frames_of(b"PMVRAW2\n" + payload_frame(0, b"a"))


def test_payload_hash_corruption_is_detected() -> None:
    data = bytearray(MAGIC + payload_frame(0, b"exact payload"))
    data[-1] ^= 0x01
    with pytest.raises(RawFormatError, match="payload SHA-256 does not match"):
        frames_of(bytes(data))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"kind": "mystery"}, "unknown frame kind"),
        ({"extra": 1}, "header keys do not match"),
        ({"frame_version": 2}, "unsupported frame_version"),
        ({"frame_version": True}, "unsupported frame_version"),
        ({"sequence": True}, "sequence is not continuous"),
        ({"received_at": "2026-10-13T03:40:21Z"}, "invalid received_at"),
        ({"payload_sha256": "ABC"}, "invalid payload_sha256"),
        ({"malformed": 0}, "invalid malformed flag"),
    ],
)
def test_closed_header_schema(change: dict[str, object], message: str) -> None:
    header = {**valid_payload_header(0, b"p"), **change}
    with pytest.raises(RawFormatError, match=message):
        frames_of(MAGIC + raw_header(header, b"p"))


def test_unknown_event_type_is_rejected() -> None:
    header = {
        "event_type": "teleport",
        "frame_version": 1,
        "kind": "event",
        "sequence": 0,
        "written_at": format_timestamp(T0),
    }
    with pytest.raises(RawFormatError, match="unknown event_type"):
        frames_of(MAGIC + raw_header(header))


def test_noncanonical_duplicate_and_float_headers_are_rejected() -> None:
    canonical = canonical_json(valid_payload_header(0, b"p"))
    spaced = canonical.replace(b",", b", ", 1)
    duplicate = canonical[:-1] + b',"kind":"payload"}'
    for header_bytes, message in ((spaced, "not canonical"), (duplicate, "duplicate keys")):
        data = MAGIC + PREFIX.pack(len(header_bytes), 1) + header_bytes + b"p"
        with pytest.raises(RawFormatError, match=message):
            frames_of(data)
    with pytest.raises(RawFormatError, match="floats are not allowed"):
        parse_canonical_json(b'{"a":1.5}')
    with pytest.raises(RawFormatError, match="floats are not allowed"):
        canonical_json({"a": 1.5})


def test_parse_errors_never_echo_content() -> None:
    secret_like = b'{"a":"SENSITIVE-CONTENT"'
    with pytest.raises(RawFormatError) as excinfo:
        parse_canonical_json(secret_like)
    assert "SENSITIVE" not in str(excinfo.value)


def test_summary_counts_and_hash_cover_the_whole_object() -> None:
    data = (
        MAGIC
        + payload_frame(0, b"a", source_timestamp=T0)
        + payload_frame(1, b"a", malformed=True)
        + encode_event_frame(sequence=2, event_type=EventType.GAP, written_at=T0)
    )
    summary = summarize_object(io.BytesIO(data), len(data))
    assert summary.size_bytes == len(data)
    assert summary.sha256 == hashlib.sha256(data).hexdigest()
    assert (summary.record_count, summary.payload_count, summary.event_count) == (3, 2, 1)
    assert summary.malformed_count == 1
    assert summary.event_counts == {EventType.GAP: 1}
    assert summary.first_source_timestamp == format_timestamp(T0)
