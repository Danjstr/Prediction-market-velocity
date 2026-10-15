"""Decision-time views: only information observable at decision time.

``ObservationLog`` holds normalized observations. ``as_of`` returns an ``AsOfView`` holding
exactly the observations whose *effective* availability plus an explicit processing latency
is at or before the decision time. Feature code receives a view, never the log, so it cannot
reach later observations.

Effective availability is the running maximum of ``available_at`` over each capture's own
order ``(frame_sequence, item_index)``. Raw sequence, not wall-clock time, is the ordering
authority (``docs/raw_data.md``), so a view always holds a capture-order *prefix* of every
capture: an item can never appear before an earlier-recorded item of the same capture (for
example a stream gap event, or the snapshot a delta depends on), even across a local clock
regression. Raising an item's availability to that of an earlier item is conservative: it
only ever delays use.

The log admits canonical observations only. ``labels.ResolutionRecord`` and ``labels.Label``
are rejected, so official outcomes can never reach feature code through a view.

``FeatureRow`` records the view's information cutoff and refuses any cutoff later than the
decision time. Time remaining to close and to the outcome reference are part of every row,
because remaining horizon is a first-class variable (CLAUDE.md "Strategy Scope").

Log order is ``(effective availability, capture_id, frame_sequence, item_index)``. The
cross-capture tie-break is deterministic but not a claim about which of two simultaneous
receipts happened first. Validation anomalies are not attached to views; callers must
consult ``validation`` for the captures a view draws on.
"""

import bisect
import math
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Final

from pmv.integrity import is_identifier, is_sha256
from pmv.market_data.contracts import ContractSpec
from pmv.market_data.events import (
    Observation,
    TradingStatus,
    TradingStatusUpdate,
    is_observation,
)
from pmv.market_data.timing import ensure_utc

__all__ = [
    "AsOfView",
    "FeatureRow",
    "FutureInformationError",
    "ObservationLog",
    "build_feature_row",
    "effective_availability",
    "status_as_of",
]

_ZERO: Final = timedelta(0)


class FutureInformationError(Exception):
    """Information not observable at the decision time reached a decision-time artifact."""


def effective_availability(
    observations: Iterable[Observation],
) -> list[tuple[datetime, Observation]]:
    """Pair each observation with its effective availability, in log order."""
    items = list(observations)
    for item in items:
        if not is_observation(item):
            raise TypeError("only canonical observations may enter an observation log")
    positions = [item.provenance.position for item in items]
    if len(set(positions)) != len(positions):
        raise ValueError("two observations share one provenance position")
    paired: list[tuple[datetime, Observation]] = []
    running: dict[str, datetime] = {}
    for item in sorted(items, key=lambda value: value.provenance.position):
        capture_id = item.provenance.capture_id
        previous = running.get(capture_id)
        effective = item.available_at if previous is None else max(previous, item.available_at)
        running[capture_id] = effective
        paired.append((effective, item))
    paired.sort(key=lambda pair: (pair[0], *pair[1].provenance.position))
    return paired


class ObservationLog:
    """An immutable collection of canonical observations in effective-availability order."""

    __slots__ = ("_items", "_keys")

    def __init__(self, observations: Iterable[Observation]) -> None:
        paired = effective_availability(observations)
        self._items: tuple[Observation, ...] = tuple(item for _, item in paired)
        self._keys: tuple[datetime, ...] = tuple(key for key, _ in paired)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Observation]:
        return iter(self._items)

    def as_of(self, decision_time: datetime, *, min_latency: timedelta) -> "AsOfView":
        """Observations whose effective availability plus ``min_latency`` is at or before
        ``decision_time``.

        ``min_latency`` is required: it is the assumed time from receipt to a usable
        decision, an explicit (and conservative, if positive) modeling assumption.
        """
        moment = ensure_utc(decision_time, "decision_time")
        _check_latency(min_latency)
        end = bisect.bisect_right(self._keys, moment - min_latency)
        return AsOfView(moment, min_latency, self._items[:end])


def _check_latency(min_latency: object) -> None:
    if not isinstance(min_latency, timedelta) or min_latency < _ZERO:
        raise ValueError("min_latency must be a non-negative timedelta")


class AsOfView:
    """What was observable at one decision time. It holds no later observation.

    A view built directly re-derives effective availability from its own items, so it
    refuses any item that would not be available, and any item recorded after it in the
    same capture.
    """

    __slots__ = ("_cutoff", "_items", "decision_time", "min_latency")

    def __init__(
        self, decision_time: datetime, min_latency: timedelta, items: tuple[Observation, ...]
    ) -> None:
        self.decision_time = ensure_utc(decision_time, "decision_time")
        _check_latency(min_latency)
        self.min_latency = min_latency
        paired = effective_availability(items)
        horizon = self.decision_time - min_latency
        if any(key > horizon for key, _ in paired):
            raise FutureInformationError("an observation is later than the decision time")
        self._items: tuple[Observation, ...] = tuple(item for _, item in paired)
        self._cutoff = max((item.available_at for item in self._items), default=None)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Observation]:
        return iter(self._items)

    @property
    def information_cutoff(self) -> datetime | None:
        """The latest ``available_at`` in the view, or None when it is empty."""
        return self._cutoff

    def of_type[T](self, kind: type[T]) -> tuple[T, ...]:
        return tuple(item for item in self._items if isinstance(item, kind))

    def for_contract(self, spec_key: str) -> tuple[Observation, ...]:
        return tuple(item for item in self._items if getattr(item, "spec_key", None) == spec_key)


@dataclass(frozen=True, slots=True)
class FeatureRow:
    """Features for one contract at one decision time.

    ``information_cutoff`` is the latest receipt time of any observation the view exposed;
    it must not be after ``decision_time``. Values must be finite: missing-data handling
    is an explicit Phase 2 decision, never a silent NaN.
    """

    spec_key: str
    decision_time: datetime
    information_cutoff: datetime | None
    time_remaining: timedelta
    time_to_reference: timedelta
    feature_set_id: str
    values: Mapping[str, float]

    def __post_init__(self) -> None:
        if not is_sha256(self.spec_key):
            raise ValueError("spec_key must be a ContractSpec key")
        object.__setattr__(self, "decision_time", ensure_utc(self.decision_time, "decision_time"))
        if self.information_cutoff is not None:
            cutoff = ensure_utc(self.information_cutoff, "information_cutoff")
            object.__setattr__(self, "information_cutoff", cutoff)
            if cutoff > self.decision_time:
                raise FutureInformationError("feature information is later than decision time")
        if self.time_remaining <= _ZERO or self.time_to_reference < self.time_remaining:
            raise ValueError("time remaining must be positive and end before the reference")
        if not is_identifier(self.feature_set_id):
            raise ValueError("feature_set_id must be a lowercase identifier")
        frozen: dict[str, float] = {}
        for name, value in self.values.items():
            if not is_identifier(name):
                raise ValueError("feature names must be lowercase identifiers")
            if type(value) is not float or not math.isfinite(value):
                raise ValueError("feature values must be finite floats")
            frozen[name] = value
        object.__setattr__(self, "values", MappingProxyType(frozen))


def build_feature_row(
    view: AsOfView,
    spec: ContractSpec,
    feature_set_id: str,
    values: Mapping[str, float],
) -> FeatureRow:
    """Build a row from a view, deriving the time fields from the contract spec."""
    if not isinstance(view, AsOfView):
        raise TypeError("features are built from an AsOfView")
    return FeatureRow(
        spec_key=spec.spec_key,
        decision_time=view.decision_time,
        information_cutoff=view.information_cutoff,
        time_remaining=spec.time_remaining(view.decision_time),
        time_to_reference=spec.time_to_reference(view.decision_time),
        feature_set_id=feature_set_id,
        values=values,
    )


def status_as_of(view: AsOfView, spec_key: str) -> TradingStatus | None:
    """The last trading status received for a contract in the view, or None.

    "Last" is log order (effective availability, then the deterministic capture tie-break).
    A status is not invalidated by a later stream reset; callers that need fresh status
    must check liveness separately.
    """
    if not isinstance(view, AsOfView):
        raise TypeError("trading status at a decision time comes from an AsOfView")
    updates = [item for item in view.of_type(TradingStatusUpdate) if item.spec_key == spec_key]
    return updates[-1].status if updates else None
