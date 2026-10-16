"""Timestamp semantics and provenance for normalized observations.

Every normalized observation carries two distinct clocks, never substituted for each other:

- ``source_time``: the time the source asserts for the event (exchange or publisher
  clock). It is untrusted: it may be absent, skewed, or later than receipt. It is kept for
  latency and anomaly analysis only.
- ``received_at``: PMV's collector clock when the application-level payload was delivered
  to PMV. It is the raw frame's ``received_at`` and cannot be changed by a parser.

``available_at`` is the earliest decision time at which an observation may be used, and it
is always ``received_at``. It is never ``source_time``: an event the exchange stamped at
``t`` was not observable to PMV before PMV received it, so using the source clock would let
information leak backwards in time.

Known limit: ``received_at`` is a wall clock. Raw frame v3 (``pmv.capture_format``, B08)
also records a monotonic receipt time, kept beside the observations in the normalized
artifact, but decision-time views order by ``received_at`` with deterministic tie-breaks;
a recorded clock regression is flagged by validation, never repaired.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from pmv.integrity import is_identifier, is_non_negative_int, is_timestamp, is_timestamp_id, to_utc

__all__ = ["Provenance", "Timing", "ensure_utc", "parse_timestamp"]

_TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.%fZ"


def ensure_utc(moment: datetime, what: str) -> datetime:
    """Return ``moment`` in UTC; naive or non-datetime values are rejected."""
    if not isinstance(moment, datetime):
        raise TypeError(f"{what} must be a datetime")
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{what} must be timezone-aware")
    return to_utc(moment)


def parse_timestamp(text: str) -> datetime:
    """Parse a canonical PMV timestamp (``YYYY-MM-DDTHH:MM:SS.ffffffZ``)."""
    if not is_timestamp(text):
        raise ValueError("not a canonical PMV UTC timestamp")
    return datetime.strptime(text, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Timing:
    """When an observation happened (per the source) and when PMV received it."""

    received_at: datetime
    source_time: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "received_at", ensure_utc(self.received_at, "received_at"))
        if self.source_time is not None:
            object.__setattr__(self, "source_time", ensure_utc(self.source_time, "source_time"))

    @property
    def available_at(self) -> datetime:
        """The earliest decision time at which the observation may be used."""
        return self.received_at


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a normalized observation came from, down to its position in a raw frame.

    ``(capture_id, frame_sequence, item_index)`` is unique per normalized observation: one
    raw payload can yield several observations, numbered from 0 in parse order.
    """

    capture_id: str
    frame_sequence: int
    item_index: int
    parser_id: str
    parser_version: int

    def __post_init__(self) -> None:
        if not is_timestamp_id(self.capture_id):
            raise ValueError("capture_id is not a PMV capture identifier")
        if not is_non_negative_int(self.frame_sequence):
            raise ValueError("frame_sequence must be a non-negative int")
        if not is_non_negative_int(self.item_index):
            raise ValueError("item_index must be a non-negative int")
        if not is_identifier(self.parser_id):
            raise ValueError("parser_id must be a lowercase identifier")
        if not is_non_negative_int(self.parser_version) or self.parser_version < 1:
            raise ValueError("parser_version must be a positive int")

    @property
    def position(self) -> tuple[str, int, int]:
        return (self.capture_id, self.frame_sequence, self.item_index)
