"""Replay synthetic raw captures through the normalization boundary.

Frames are encoded and read back with the real raw format (``pmv.raw_format``), then
normalized with the synthetic adapter. All data is synthetic.
"""

import io
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pmv.market_data.books import BookFault, reconstruct_as_of
from pmv.market_data.contracts import ContractSpec, Underlying, Verification, YesRegion
from pmv.market_data.events import (
    BookSnapshot,
    Outcome,
    ReferenceTick,
    StreamEvent,
    StreamEventKind,
    Trade,
    TradingStatus,
)
from pmv.market_data.kalshi import KalshiNormalizer, KalshiSpecUnverifiedError
from pmv.market_data.labels import (
    Label,
    LabelExclusion,
    LabelPolicy,
    OfficialResolution,
    label_for,
)
from pmv.market_data.replay import (
    FrameDisposition,
    NormalizationContractError,
    NormalizeContext,
    Parsed,
    PayloadRejectedError,
    Skipped,
    merge_captures,
    normalize_frames,
)
from pmv.market_data.synthetic import SyntheticNormalizer
from pmv.market_data.timing import Provenance, Timing
from pmv.market_data.validation import ValidationPolicy, capture_order, validate
from pmv.protected_scope import Provider
from pmv.raw_format import (
    MAGIC,
    EventType,
    Frame,
    FrameReader,
    encode_event_frame,
    encode_payload_frame,
)

OPEN = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CLOSE = OPEN + timedelta(minutes=15)
CAPTURE_A = "20260101T120000.000000Z_" + "a" * 32
CAPTURE_B = "20260101T120000.000000Z_" + "b" * 32
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
    close_time=CLOSE,
    outcome_reference_time=CLOSE,
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
ZERO = timedelta(0)


def at(seconds: float) -> datetime:
    return OPEN + timedelta(seconds=seconds)


def message(**fields: object) -> bytes:
    return json.dumps(fields, separators=(",", ":")).encode()


def capture(entries: Sequence[tuple[float, bytes | EventType, bool]]) -> list[Frame]:
    """Encode (received seconds, payload or event, malformed) entries and read them back."""
    data = bytearray(MAGIC)
    for sequence, (received, body, malformed) in enumerate(entries):
        if isinstance(body, EventType):
            data += encode_event_frame(sequence=sequence, event_type=body, written_at=at(received))
        else:
            data += encode_payload_frame(
                sequence=sequence,
                payload=body,
                received_at=at(received),
                written_at=at(received),
                source_timestamp=None,
                malformed=malformed,
            )
    return list(FrameReader(io.BytesIO(bytes(data)), len(data)).frames())


def frames_a() -> list[Frame]:
    return capture(
        [
            (
                1,
                message(
                    type="book_snapshot",
                    spec_key=KEY,
                    outcome="yes",
                    bids=[[40, 5]],
                    asks=[[60, 5]],
                    seq=1,
                    scope="book",
                    ts="2026-01-01T12:00:00.900000Z",
                ),
                False,
            ),
            (2, message(type="heartbeat"), False),
            (3, b"{not json", False),
            (4, message(type="trade", spec_key=KEY, outcome="yes", price=55, quantity=2), True),
            (5, EventType.RECONNECT, False),
            (6, message(type="mystery"), False),
            (7, message(type="trade", spec_key=KEY, outcome="yes", price=1.5, quantity=1), False),
            (
                8,
                message(
                    type="trade", spec_key=KEY, outcome="yes", price=52, quantity=1, trade_id="t1"
                ),
                False,
            ),
            (1000, message(type="resolution", spec_key=KEY, result="yes"), False),
        ]
    )


def frames_b() -> list[Frame]:
    return capture([(2.5, message(type="reference", price="101.25"), False)])


def test_every_frame_has_exactly_one_recorded_disposition() -> None:
    result = normalize_frames(CAPTURE_A, frames_a(), SyntheticNormalizer())
    dispositions = [(f.disposition, f.reason) for f in result.frames]
    assert dispositions == [
        (FrameDisposition.PARSED, None),
        (FrameDisposition.SKIPPED, "heartbeat"),
        (FrameDisposition.REJECTED, "undecodable_payload"),
        (FrameDisposition.REJECTED, "raw_flagged_malformed"),
        (FrameDisposition.STREAM_EVENT, None),
        (FrameDisposition.REJECTED, "unknown_message_type"),
        (FrameDisposition.REJECTED, "float_not_allowed"),
        (FrameDisposition.PARSED, None),
        (FrameDisposition.PARSED, None),
    ]
    assert sum(result.count(d) for d in FrameDisposition) == len(result.frames) == 9
    assert [type(o) for o in result.observations] == [BookSnapshot, StreamEvent, Trade]
    assert len(result.resolutions) == 1
    assert result.parser_id == "pmv_synthetic_v1"


def test_receipt_time_and_provenance_come_from_the_raw_frame() -> None:
    result = normalize_frames(CAPTURE_A, frames_a(), SyntheticNormalizer())
    snapshot = result.observations[0]
    assert isinstance(snapshot, BookSnapshot)
    assert snapshot.timing == Timing(at(1), at(0.9))
    assert snapshot.provenance == Provenance(CAPTURE_A, 0, 0, "pmv_synthetic_v1", 1)
    assert result.resolutions[0].received_at == at(1000)


def test_replay_is_deterministic() -> None:
    first = normalize_frames(CAPTURE_A, frames_a(), SyntheticNormalizer())
    second = normalize_frames(CAPTURE_A, frames_a(), SyntheticNormalizer())
    assert first == second


def test_end_to_end_views_features_and_labels_stay_separated() -> None:
    a = normalize_frames(CAPTURE_A, frames_a(), SyntheticNormalizer())
    b = normalize_frames(CAPTURE_B, frames_b(), SyntheticNormalizer())
    log = merge_captures([a, b])
    assert [type(o) for o in log] == [BookSnapshot, ReferenceTick, StreamEvent, Trade]
    view = log.as_of(at(3), min_latency=ZERO)
    assert [type(o) for o in view] == [BookSnapshot, ReferenceTick]
    policy_labels = LabelPolicy("replay_labels_v1", timedelta(seconds=1))
    # no trading status was received, so the decision is not known to be tradable
    unknown = label_for(
        SPEC, a.resolutions[0], view.decision_time, status=None, policy=policy_labels
    )
    assert unknown is LabelExclusion.NOT_OPEN_AT_DECISION
    label = label_for(
        SPEC,
        a.resolutions[0],
        view.decision_time,
        status=TradingStatus.OPEN,
        policy=policy_labels,
    )
    assert isinstance(label, Label)
    assert all(not isinstance(o, type(a.resolutions[0])) for o in log)
    policy = ValidationPolicy(
        timedelta(seconds=1), timedelta(seconds=5), timedelta(seconds=60), "replay_validation_v1"
    )
    report = validate(capture_order(log), {KEY: SPEC}, policy)
    assert [anomaly.kind.value for anomaly in report.anomalies] == ["stream_reconnect"]


def test_a_capture_cannot_be_merged_twice() -> None:
    a = normalize_frames(CAPTURE_A, frames_a(), SyntheticNormalizer())
    with pytest.raises(ValueError, match="more than once"):
        merge_captures([a, a])


def test_frames_must_be_contiguous() -> None:
    frames = frames_a()
    with pytest.raises(NormalizationContractError, match="contiguous"):
        normalize_frames(CAPTURE_A, frames[1:], SyntheticNormalizer())


class Backdating:
    """A misbehaving parser that makes data available before PMV received it."""

    parser_id = "backdating"
    parser_version = 1

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped:
        timing = Timing(context.received_at - timedelta(seconds=1), None)
        return Parsed((Trade(KEY, Outcome.YES, 50, 1, None, None, timing, context.provenance(0)),))


class WrongProvenance:
    parser_id = "wrong_provenance"
    parser_version = 1

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped:
        timing = Timing(context.received_at, None)
        return Parsed((Trade(KEY, Outcome.YES, 50, 1, None, None, timing, context.provenance(1)),))


class ReturnsGarbage:
    parser_id = "garbage"
    parser_version = 1

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped:
        return Parsed(("not an observation",))  # type: ignore[arg-type]


class EmitsStreamEvents:
    parser_id = "stream_forger"
    parser_version = 1

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped:
        return Parsed(
            (StreamEvent(StreamEventKind.GAP, context.received_at, context.provenance(0)),)
        )


@pytest.mark.parametrize(
    ("normalizer", "match"),
    [
        (Backdating(), "receipt time"),
        (WrongProvenance(), "provenance"),
        (ReturnsGarbage(), "unsupported"),
        (EmitsStreamEvents(), "unsupported"),
    ],
)
def test_parsers_cannot_break_the_contract(normalizer: object, match: str) -> None:
    frames = capture([(1, message(type="anything"), False)])
    with pytest.raises(NormalizationContractError, match=match):
        normalize_frames(CAPTURE_A, frames, normalizer)  # type: ignore[arg-type]


def test_the_stream_parser_identity_is_reserved() -> None:
    class Impostor(Backdating):
        parser_id = "pmv_stream_event"

    with pytest.raises(NormalizationContractError, match="reserved"):
        normalize_frames(CAPTURE_A, [], Impostor())


def test_rejection_reasons_are_identifiers() -> None:
    with pytest.raises(ValueError, match="identifiers"):
        PayloadRejectedError("Free text reason")


def test_kalshi_fails_closed_for_the_whole_replay() -> None:
    frames = capture([(1, message(type="anything"), False)])
    with pytest.raises(KalshiSpecUnverifiedError):
        normalize_frames(CAPTURE_A, frames, KalshiNormalizer())


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (message(type="trade", spec_key=KEY, outcome="yes", price=50), "unexpected_fields"),
        (
            message(type="trade", spec_key=KEY, outcome="maybe", price=50, quantity=1),
            "bad_enum_value",
        ),
        (
            message(type="trade", spec_key="x", outcome="yes", price=50, quantity=1),
            "invalid_observation",
        ),
        (message(type="reference", price=101), "bad_field_type"),
        (message(type="resolution", spec_key="x", result="yes"), "invalid_resolution"),
        (b'{"type":"heartbeat","type":"heartbeat"}', "duplicate_key"),
        (b"[]", "not_an_object"),
        (b"\xff", "undecodable_payload"),
        (b'{"type":"reference","price":NaN}', "float_not_allowed"),
    ],
)
def test_synthetic_rejections_are_enumerated(body: bytes, reason: str) -> None:
    result = normalize_frames(CAPTURE_A, capture([(1, body, False)]), SyntheticNormalizer())
    assert [(f.disposition, f.reason) for f in result.frames] == [
        (FrameDisposition.REJECTED, reason)
    ]


def test_resolutions_parse_all_official_results() -> None:
    for result in OfficialResolution:
        frames = capture(
            [(1, message(type="resolution", spec_key=KEY, result=result.value), False)]
        )
        normalized = normalize_frames(CAPTURE_A, frames, SyntheticNormalizer())
        assert normalized.resolutions[0].resolution is result
        assert normalized.observations == ()


def test_raw_frames_replay_into_point_in_time_books() -> None:
    def delta(seq: int, price: int, quantity: int) -> bytes:
        return message(
            type="book_delta",
            spec_key=KEY,
            outcome="yes",
            side="bid",
            price=price,
            quantity=quantity,
            seq=seq,
            scope="book",
        )

    snapshot = message(
        type="book_snapshot",
        spec_key=KEY,
        outcome="yes",
        bids=[[40, 5]],
        asks=[[60, 5]],
        seq=1,
        scope="book",
    )
    frames = capture(
        [
            (1, snapshot, False),
            (2, delta(2, 45, 3), False),
            (3, EventType.GAP, False),
            (4, delta(1, 46, 1), False),
        ]
    )
    result = normalize_frames(CAPTURE_A, frames, SyntheticNormalizer())
    log = merge_captures([result])
    before = reconstruct_as_of(log.as_of(at(2), min_latency=ZERO), {KEY: SPEC})
    book = before.get(CAPTURE_A, KEY, Outcome.YES)
    assert book is not None
    assert book.usable
    assert book.best_bid is not None
    assert (book.best_bid.price, book.best_bid.quantity) == (45, 3)
    after = reconstruct_as_of(log.as_of(at(4), min_latency=ZERO), {KEY: SPEC})
    broken = after.get(CAPTURE_A, KEY, Outcome.YES)
    assert broken is not None
    assert broken.faults == frozenset({BookFault.STREAM_RESET})
    assert broken.best_bid == book.best_bid
    assert after.latest(KEY, Outcome.YES, decision_time=at(4), max_silence=ZERO) is None
    assert after.last_seen(CAPTURE_A) == at(4)
