"""Raw-to-normalized replay through a venue adapter boundary.

``normalize_frames`` turns the frames of one raw capture (``pmv.raw_format``) into
normalized observations with a venue ``Normalizer``. Every frame has exactly one recorded
outcome, so nothing is dropped silently:

- a payload the parser understood: ``Parsed`` (zero or more items);
- a payload deliberately not normalized, such as a heartbeat: ``Skipped`` with a reason;
- a payload the parser cannot accept, or one the collector flagged malformed: ``Rejected``
  with a reason. The raw bytes stay preserved in the raw store, and the driver adds a
  ``frame_rejected`` stream event at the frame's position, so the book engine and
  validation see the break (whatever the frame carried is unknown);
- an event frame: a ``StreamEvent``.

The driver, not the parser, owns time and provenance. A parser receives the frame's
``received_at`` and returns items stamped with it; any item with another receipt time,
another capture or frame, a wrong item index, or another parser identity fails the replay
(``NormalizationContractError``). A parser therefore cannot make information available
earlier than PMV received it.

Official resolutions (``labels.ResolutionRecord``) are separated from observations at this
boundary, so they never enter an ``ObservationLog``.

A normalized capture records the parser identity and version that produced it. A parser
fix is a new version and a new normalized result; it never mutates an earlier one.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pmv.integrity import is_identifier, is_timestamp_id
from pmv.market_data.events import (
    BookDelta,
    BookSnapshot,
    Observation,
    ReferenceTick,
    StreamEvent,
    StreamEventKind,
    Trade,
    TradingStatusUpdate,
)
from pmv.market_data.labels import ResolutionRecord
from pmv.market_data.point_in_time import ObservationLog
from pmv.market_data.timing import Provenance, parse_timestamp
from pmv.raw_format import EventFrame, Frame, PayloadFrame

__all__ = [
    "FrameDisposition",
    "FrameRecord",
    "NormalizationContractError",
    "NormalizeContext",
    "NormalizedCapture",
    "Normalizer",
    "Parsed",
    "PayloadRejectedError",
    "Rejected",
    "Skipped",
    "check_parsed_item",
    "merge_captures",
    "normalize_frames",
    "rejection_event",
]

STREAM_PARSER_ID = "pmv_stream_event"
STREAM_PARSER_VERSION = 1
RAW_MALFORMED_REASON = "raw_flagged_malformed"


class NormalizationContractError(Exception):
    """A parser broke the normalization contract. The replay fails closed."""


class PayloadRejectedError(Exception):
    """Raised by a parser for a payload it cannot accept; ``reason`` is an identifier."""

    def __init__(self, reason: str) -> None:
        if not is_identifier(reason):
            raise ValueError("rejection reasons must be lowercase identifiers")
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class NormalizeContext:
    """What the driver tells a parser about one payload frame."""

    capture_id: str
    frame_sequence: int
    received_at: datetime
    source_timestamp: datetime | None
    parser_id: str
    parser_version: int

    def provenance(self, item_index: int) -> Provenance:
        return Provenance(
            self.capture_id, self.frame_sequence, item_index, self.parser_id, self.parser_version
        )


@dataclass(frozen=True, slots=True)
class Parsed:
    items: tuple[Observation | ResolutionRecord, ...]


@dataclass(frozen=True, slots=True)
class Skipped:
    reason: str

    def __post_init__(self) -> None:
        if not is_identifier(self.reason):
            raise ValueError("skip reasons must be lowercase identifiers")


@dataclass(frozen=True, slots=True)
class Rejected:
    reason: str

    def __post_init__(self) -> None:
        if not is_identifier(self.reason):
            raise ValueError("rejection reasons must be lowercase identifiers")


class Normalizer(Protocol):
    """A venue adapter. ``normalize`` returns ``Parsed`` or ``Skipped``, or raises
    ``PayloadRejectedError``. Any other exception propagates and fails the replay."""

    @property
    def parser_id(self) -> str: ...

    @property
    def parser_version(self) -> int: ...

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped: ...


class FrameDisposition(StrEnum):
    PARSED = "parsed"
    SKIPPED = "skipped"
    REJECTED = "rejected"
    STREAM_EVENT = "stream_event"


@dataclass(frozen=True, slots=True)
class FrameRecord:
    frame_sequence: int
    disposition: FrameDisposition
    item_count: int
    reason: str | None


@dataclass(frozen=True, slots=True)
class NormalizedCapture:
    capture_id: str
    parser_id: str
    parser_version: int
    frames: tuple[FrameRecord, ...]
    observations: tuple[Observation, ...]
    resolutions: tuple[ResolutionRecord, ...]

    def count(self, disposition: FrameDisposition) -> int:
        return sum(1 for frame in self.frames if frame.disposition is disposition)


def normalize_frames(
    capture_id: str, frames: Iterable[Frame], normalizer: Normalizer
) -> NormalizedCapture:
    """Normalize one capture's frames, in raw sequence order, with ``normalizer``."""
    if not is_timestamp_id(capture_id):
        raise ValueError("capture_id is not a PMV capture identifier")
    parser_id, parser_version = normalizer.parser_id, normalizer.parser_version
    if parser_id == STREAM_PARSER_ID:
        raise NormalizationContractError("the stream-event parser identity is reserved")
    records: list[FrameRecord] = []
    observations: list[Observation] = []
    resolutions: list[ResolutionRecord] = []
    expected_sequence = 0
    for frame in frames:
        if frame.sequence != expected_sequence:
            raise NormalizationContractError("raw frames are not in contiguous sequence order")
        expected_sequence += 1
        if isinstance(frame, EventFrame):
            observations.append(_stream_event(capture_id, frame))
            records.append(FrameRecord(frame.sequence, FrameDisposition.STREAM_EVENT, 1, None))
            continue
        context = _context(capture_id, frame, parser_id, parser_version)
        if frame.malformed:
            records.append(
                FrameRecord(frame.sequence, FrameDisposition.REJECTED, 0, RAW_MALFORMED_REASON)
            )
            observations.append(rejection_event(capture_id, frame.sequence, context.received_at))
            continue
        try:
            outcome = normalizer.normalize(frame.payload, context)
        except PayloadRejectedError as rejection:
            records.append(
                FrameRecord(frame.sequence, FrameDisposition.REJECTED, 0, rejection.reason)
            )
            observations.append(rejection_event(capture_id, frame.sequence, context.received_at))
            continue
        if isinstance(outcome, Skipped):
            records.append(FrameRecord(frame.sequence, FrameDisposition.SKIPPED, 0, outcome.reason))
            continue
        if not isinstance(outcome, Parsed):
            raise NormalizationContractError("a parser returned neither Parsed nor Skipped")
        for index, item in enumerate(outcome.items):
            _check_item(item, index, context)
            if isinstance(item, ResolutionRecord):
                resolutions.append(item)
            else:
                observations.append(item)
        records.append(
            FrameRecord(frame.sequence, FrameDisposition.PARSED, len(outcome.items), None)
        )
    return NormalizedCapture(
        capture_id,
        parser_id,
        parser_version,
        tuple(records),
        tuple(observations),
        tuple(resolutions),
    )


def merge_captures(captures: Sequence[NormalizedCapture]) -> ObservationLog:
    """One availability-ordered log of every observation in ``captures``."""
    capture_ids = [capture.capture_id for capture in captures]
    if len(set(capture_ids)) != len(capture_ids):
        raise ValueError("a capture appears more than once")
    return ObservationLog(item for capture in captures for item in capture.observations)


def _context(
    capture_id: str, frame: PayloadFrame, parser_id: str, parser_version: int
) -> NormalizeContext:
    source = None if frame.source_timestamp is None else parse_timestamp(frame.source_timestamp)
    return NormalizeContext(
        capture_id,
        frame.sequence,
        parse_timestamp(frame.received_at),
        source,
        parser_id,
        parser_version,
    )


def rejection_event(capture_id: str, frame_sequence: int, received_at: datetime) -> StreamEvent:
    """The driver's record that a payload frame was rejected (B08 order-book continuity).

    It is available when the frame was received, carries no payload information, and
    breaks every book in the capture (``events.RESETS_BOOK_STATE``): the rejected frame may
    have been a snapshot or delta for any of them.
    """
    return StreamEvent(
        StreamEventKind.FRAME_REJECTED,
        received_at,
        Provenance(capture_id, frame_sequence, 0, STREAM_PARSER_ID, STREAM_PARSER_VERSION),
    )


def _stream_event(capture_id: str, frame: EventFrame) -> StreamEvent:
    return StreamEvent(
        StreamEventKind(frame.event_type.value),
        parse_timestamp(frame.written_at),
        Provenance(capture_id, frame.sequence, 0, STREAM_PARSER_ID, STREAM_PARSER_VERSION),
    )


def check_parsed_item(item: object, index: int, context: NormalizeContext) -> None:
    """Enforce the normalization contract on one parsed item (shared by every driver)."""
    _check_item(item, index, context)


def _check_item(item: object, index: int, context: NormalizeContext) -> None:
    provenance: Provenance
    received: datetime
    if isinstance(item, ResolutionRecord):
        provenance, received = item.provenance, item.received_at
    elif isinstance(item, (BookSnapshot, BookDelta, Trade, TradingStatusUpdate, ReferenceTick)):
        provenance, received = item.provenance, item.timing.received_at
    else:
        raise NormalizationContractError("a parser returned an unsupported item type")
    if provenance != context.provenance(index):
        raise NormalizationContractError("a parsed item does not carry the driver's provenance")
    if received != context.received_at:
        raise NormalizationContractError("a parsed item changed the frame's receipt time")
