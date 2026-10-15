"""Official outcomes and supervised labels, kept apart from observations.

Labels are determined by official resolution status (START_HERE "Data and Contract
Identity"). A ``ResolutionRecord`` is an official result as PMV received it; it is not an
observation and ``point_in_time.ObservationLog`` refuses it, so outcome information cannot
reach feature code through a decision-time view.

``label_for`` turns a resolution into a label for one decision time, or into an explicit
``LabelExclusion``. Nothing is coerced: a void contract is excluded, never labelled NO, and
a resolution PMV received before the decision time is excluded as a leak hazard rather
than used. A missing resolution is an explicit exclusion too, so every candidate decision
row is accounted for and exclusions can be tallied as a selection mechanism.

Two exclusions guard against labelling decisions that could not have been traded, or whose
inputs may already contain the outcome:

- ``not_open_at_decision``: the last trading status PMV received for the contract by the
  decision time (``point_in_time.status_as_of``) is not ``open``, or none was received.
  A halted or closed market is not a tradable decision, and its prices may sit near the
  outcome;
- ``within_clock_error_of_close``: the decision is within ``LabelPolicy.max_clock_error``
  of ``close_time``. Decision times are on PMV's wall clock and contract times on the
  venue's; without a measured offset (Step 11 F-12) a decision just before close may in
  fact be after it.

``LabelPolicy`` is explicit, has no defaults, and carries a ``policy_id`` to record with
any experiment that relies on it.

``TrainingExample`` holds the contract spec, the label policy, a ``FeatureRow``, the
trading status at decision, the official resolution, and the label. It re-derives the label
with ``label_for``, so a hand-built ``Label`` cannot bypass the verification, window,
status, clock-margin, void, or availability rules. It also re-derives the row's time fields
from the spec. Build one with ``training_example``, which takes the ``AsOfView`` the
features were computed from and derives the status and the information cutoff from it.

Known limit: a ``ContractSpec`` does not record when PMV learned it. A spec built from
metadata fetched after the market (for example a realized early close) would leak into the
time fields; point-in-time spec versioning must exist before any venue spec builder
(``docs/market_data.md``).

Purge and embargo across split boundaries are Phase 2 (dataset and target construction)
and are not implemented here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

from pmv.integrity import is_identifier, is_sha256
from pmv.market_data.contracts import ContractSpec, Verification
from pmv.market_data.events import Outcome, TradingStatus
from pmv.market_data.point_in_time import (
    AsOfView,
    FeatureRow,
    FutureInformationError,
    status_as_of,
)
from pmv.market_data.timing import Provenance, ensure_utc

__all__ = [
    "Label",
    "LabelExclusion",
    "LabelPolicy",
    "OfficialResolution",
    "ResolutionRecord",
    "TrainingExample",
    "UnverifiedContractSpecError",
    "label_for",
    "training_example",
]


class UnverifiedContractSpecError(Exception):
    """A label was requested for a contract whose semantics are not verified."""


class OfficialResolution(StrEnum):
    YES = "yes"
    NO = "no"
    VOID = "void"


_ZERO: Final = timedelta(0)


class LabelExclusion(StrEnum):
    VOID = "void"
    DECISION_OUTSIDE_TRADING_WINDOW = "decision_outside_trading_window"
    WITHIN_CLOCK_ERROR_OF_CLOSE = "within_clock_error_of_close"
    NOT_OPEN_AT_DECISION = "not_open_at_decision"
    RESOLUTION_MISSING = "resolution_missing"
    RESOLUTION_AVAILABLE_AT_DECISION = "resolution_available_at_decision"
    RESOLUTION_BEFORE_REFERENCE_TIME = "resolution_before_reference_time"


@dataclass(frozen=True, slots=True)
class LabelPolicy:
    """Explicit labelling assumptions; record ``policy_id`` with every experiment.

    ``max_clock_error`` bounds the assumed offset between PMV's clock and the venue's.
    Decisions within it of ``close_time`` are excluded.
    """

    policy_id: str
    max_clock_error: timedelta

    def __post_init__(self) -> None:
        if not is_identifier(self.policy_id):
            raise ValueError("policy_id must be a lowercase identifier")
        if not isinstance(self.max_clock_error, timedelta) or self.max_clock_error < _ZERO:
            raise ValueError("max_clock_error must be a non-negative timedelta")


@dataclass(frozen=True, slots=True)
class ResolutionRecord:
    """An official resolution, as received by PMV. Not an observation."""

    spec_key: str
    resolution: OfficialResolution
    received_at: datetime
    provenance: Provenance

    def __post_init__(self) -> None:
        if not is_sha256(self.spec_key):
            raise ValueError("spec_key must be a ContractSpec key")
        if not isinstance(self.resolution, OfficialResolution):
            raise TypeError("resolution must be an OfficialResolution")
        object.__setattr__(self, "received_at", ensure_utc(self.received_at, "received_at"))
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")


@dataclass(frozen=True, slots=True)
class Label:
    """The official outcome of one contract, attached to one decision time."""

    spec_key: str
    decision_time: datetime
    outcome: Outcome
    resolution_received_at: datetime

    def __post_init__(self) -> None:
        if not is_sha256(self.spec_key):
            raise ValueError("spec_key must be a ContractSpec key")
        if not isinstance(self.outcome, Outcome):
            raise TypeError("outcome must be an Outcome")
        for name in ("decision_time", "resolution_received_at"):
            object.__setattr__(self, name, ensure_utc(getattr(self, name), name))


def label_for(
    spec: ContractSpec,
    resolution: ResolutionRecord | None,
    decision_time: datetime,
    *,
    status: TradingStatus | None,
    policy: LabelPolicy,
) -> Label | LabelExclusion:
    """The label for one decision, or why it has none.

    ``status`` is the last trading status PMV received for the contract by the decision
    time (``point_in_time.status_as_of``), or None if none was received.
    """
    if resolution is not None and not isinstance(resolution, ResolutionRecord):
        raise TypeError("resolution must be a ResolutionRecord or None")
    if resolution is not None and resolution.spec_key != spec.spec_key:
        raise ValueError("the resolution belongs to a different contract spec")
    if status is not None and not isinstance(status, TradingStatus):
        raise TypeError("status must be a TradingStatus or None")
    if not isinstance(policy, LabelPolicy):
        raise TypeError("policy must be a LabelPolicy")
    if spec.verification is Verification.UNVERIFIED:
        raise UnverifiedContractSpecError("contract semantics are not verified")
    moment = ensure_utc(decision_time, "decision_time")
    if not spec.tradable_at(moment):
        return LabelExclusion.DECISION_OUTSIDE_TRADING_WINDOW
    if moment + policy.max_clock_error >= spec.close_time:
        return LabelExclusion.WITHIN_CLOCK_ERROR_OF_CLOSE
    if status is not TradingStatus.OPEN:
        return LabelExclusion.NOT_OPEN_AT_DECISION
    if resolution is None:
        return LabelExclusion.RESOLUTION_MISSING
    if resolution.received_at <= moment:
        return LabelExclusion.RESOLUTION_AVAILABLE_AT_DECISION
    # A result received before its reference value was fixed is a provenance anomaly.
    if resolution.received_at < spec.outcome_reference_time:
        return LabelExclusion.RESOLUTION_BEFORE_REFERENCE_TIME
    if resolution.resolution is OfficialResolution.VOID:
        return LabelExclusion.VOID
    outcome = Outcome.YES if resolution.resolution is OfficialResolution.YES else Outcome.NO
    return Label(spec.spec_key, moment, outcome, resolution.received_at)


@dataclass(frozen=True, slots=True)
class TrainingExample:
    spec: ContractSpec
    policy: LabelPolicy
    features: FeatureRow
    status_at_decision: TradingStatus | None
    resolution: ResolutionRecord
    label: Label

    def __post_init__(self) -> None:
        if not isinstance(self.spec, ContractSpec) or not isinstance(self.features, FeatureRow):
            raise TypeError("a training example needs a ContractSpec and a FeatureRow")
        if not isinstance(self.resolution, ResolutionRecord):
            raise TypeError("resolution must be a ResolutionRecord")
        if not isinstance(self.label, Label):
            raise TypeError("label must be a Label")
        if self.features.spec_key != self.spec.spec_key:
            raise ValueError("features and label refer to different contracts")
        decision = self.features.decision_time
        cutoff = self.features.information_cutoff
        if cutoff is not None and cutoff > decision:
            raise FutureInformationError("feature information is later than decision time")
        if self.label.resolution_received_at <= decision:
            raise FutureInformationError("the outcome was available at decision time")
        if self.features.time_remaining != self.spec.time_remaining(decision) or (
            self.features.time_to_reference != self.spec.time_to_reference(decision)
        ):
            raise ValueError("feature time fields do not match the contract spec")
        expected = label_for(
            self.spec,
            self.resolution,
            decision,
            status=self.status_at_decision,
            policy=self.policy,
        )
        if expected != self.label:
            raise ValueError("the label is not the one the official resolution determines")


def training_example(
    spec: ContractSpec,
    view: AsOfView,
    features: FeatureRow,
    resolution: ResolutionRecord | None,
    policy: LabelPolicy,
) -> TrainingExample | LabelExclusion:
    """A training example for ``features`` computed from ``view``, or why it has no label.

    The row must come from this view: same contract, decision time, and information
    cutoff. The trading status at decision is derived from the view, never supplied.
    """
    if not isinstance(view, AsOfView):
        raise TypeError("a training example is built from the AsOfView of its features")
    if features.spec_key != spec.spec_key:
        raise ValueError("features and label refer to different contracts")
    if (
        features.decision_time != view.decision_time
        or features.information_cutoff != view.information_cutoff
    ):
        raise ValueError("the feature row was not built from this view")
    status = status_as_of(view, spec.spec_key)
    label = label_for(spec, resolution, features.decision_time, status=status, policy=policy)
    if isinstance(label, LabelExclusion):
        return label
    if resolution is None:  # unreachable: label_for excludes a missing resolution
        raise AssertionError("a label requires a resolution")
    return TrainingExample(spec, policy, features, status, resolution, label)
