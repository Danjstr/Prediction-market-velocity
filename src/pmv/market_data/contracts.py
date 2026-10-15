"""Canonical prediction-market contract identity (START_HERE "Data and Contract Identity").

A ``ContractSpec`` preserves the venue and market identity, the resolution-rule and
resolution-source identity, the YES region (threshold or range, with explicit boundary
inclusion, which is the tie semantics), the trading window and outcome-reference time, the
timezone the rule text is stated in, the rounding and void rules, the date-effective fee
schedule, and the price and quantity units.

``spec_key`` is the SHA-256 of the canonical encoding of every field, so any change to a
rule, threshold, time, or fee schedule is a different identity. Corrections create a new
spec; they never mutate one.

Nothing here infers venue semantics. A spec built from venue documentation that has not
been verified from current official sources is ``UNVERIFIED``; ``labels`` refuses to build
supervised labels from it. Polymarket is deferred (owner direction, Phase 1) and refused.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pmv.integrity import (
    canonical_json,
    decimal_text,
    format_timestamp,
    is_identifier,
    is_sha256,
    sha256_hex,
)
from pmv.market_data.timing import ensure_utc
from pmv.protected_scope import IdentifierKind, Provider, normalize_identifier

__all__ = [
    "SPEC_VERSION",
    "ContractSpec",
    "ContractSpecError",
    "OutsideTradingWindowError",
    "Underlying",
    "Verification",
    "YesRegion",
]

SPEC_VERSION: Final = 1
SUPPORTED_VENUES: Final = frozenset({Provider.KALSHI, Provider.PMV_SYNTHETIC})
_SYNTHETIC_ID_CHARS: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_.-")


class ContractSpecError(ValueError):
    """A contract spec is invalid. Messages never echo identifiers or values."""


class OutsideTradingWindowError(ValueError):
    """A decision time lies outside the contract's ``[open_time, close_time)`` window."""


class Underlying(StrEnum):
    BTC = "btc"
    GOLD = "gold"
    SYNTHETIC = "synthetic"


class Verification(StrEnum):
    """How the semantic fields of a spec are known.

    ``VERIFIED_OFFICIAL`` requires ``rules_source_sha256``, the SHA-256 of the official
    rule text or document the fields were taken from (recorded in research/sources.md).
    ``SYNTHETIC`` is allowed only for the ``pmv_synthetic`` venue.
    """

    VERIFIED_OFFICIAL = "verified_official"
    SYNTHETIC = "synthetic"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class YesRegion:
    """The contract resolves YES when the reference value lies in this region.

    Each bound is optional (one-sided thresholds) and states whether equality counts, so tie
    handling is always explicit. At least one bound is required.
    """

    lower: Decimal | None
    lower_inclusive: bool
    upper: Decimal | None
    upper_inclusive: bool

    def __post_init__(self) -> None:
        for bound in (self.lower, self.upper):
            if bound is not None and (not isinstance(bound, Decimal) or not bound.is_finite()):
                raise ContractSpecError("region bounds must be finite Decimal values")
        for flag in (self.lower_inclusive, self.upper_inclusive):
            if not isinstance(flag, bool):
                raise ContractSpecError("bound inclusion flags must be bool")
        if self.lower is None and self.upper is None:
            raise ContractSpecError("a YES region needs at least one bound")
        if self.lower is None and self.lower_inclusive:
            raise ContractSpecError("an absent lower bound cannot be inclusive")
        if self.upper is None and self.upper_inclusive:
            raise ContractSpecError("an absent upper bound cannot be inclusive")
        if self.lower is not None and self.upper is not None:
            if self.lower > self.upper:
                raise ContractSpecError("the lower bound exceeds the upper bound")
            if self.lower == self.upper and not (self.lower_inclusive and self.upper_inclusive):
                raise ContractSpecError("the YES region is empty")

    def encode(self) -> dict[str, object]:
        # normalize() gives one spelling per value, so 100 and 1E+2 are one identity.
        return {
            "lower": None if self.lower is None else decimal_text(self.lower.normalize()),
            "lower_inclusive": self.lower_inclusive,
            "upper": None if self.upper is None else decimal_text(self.upper.normalize()),
            "upper_inclusive": self.upper_inclusive,
        }


@dataclass(frozen=True, slots=True)
class ContractSpec:
    """One binary contract's identity and semantics. All times are UTC.

    ``close_time`` is the last instant trading can occur (exclusive); decisions are made in
    ``[open_time, close_time)``. ``outcome_reference_time`` is when the reference value that
    decides the outcome is fixed; it may be after ``close_time``. Identifier-valued rule
    fields (``resolution_source_id``, ``resolution_rule_id``, ``rounding_rule_id``,
    ``void_rule_id``, ``fee_schedule_id``) are project identifiers whose meaning is recorded
    with the official source; they are never free text.
    """

    venue: Provider
    market_id: str
    event_id: str | None
    series_id: str | None
    underlying: Underlying
    resolution_source_id: str
    resolution_rule_id: str
    yes_region: YesRegion
    open_time: datetime
    close_time: datetime
    outcome_reference_time: datetime
    rule_timezone: str
    rounding_rule_id: str
    void_rule_id: str
    fee_schedule_id: str
    fee_schedule_effective_from: datetime
    price_units_per_payout: int
    quantity_units_per_contract: int
    verification: Verification
    rules_source_sha256: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.venue, Provider) or self.venue not in SUPPORTED_VENUES:
            raise ContractSpecError("venue is not supported in Phase 1 (Kalshi, synthetic)")
        if not isinstance(self.underlying, Underlying):
            raise ContractSpecError("underlying must be an Underlying")
        if not isinstance(self.verification, Verification):
            raise ContractSpecError("verification must be a Verification")
        if not isinstance(self.yes_region, YesRegion):
            raise ContractSpecError("yes_region must be a YesRegion")
        self._check_identity()
        for name in (
            "resolution_source_id",
            "resolution_rule_id",
            "rounding_rule_id",
            "void_rule_id",
            "fee_schedule_id",
        ):
            if not is_identifier(getattr(self, name)):
                raise ContractSpecError(f"{name} must be a lowercase identifier")
        for name in (
            "open_time",
            "close_time",
            "outcome_reference_time",
            "fee_schedule_effective_from",
        ):
            object.__setattr__(self, name, ensure_utc(getattr(self, name), name))
        if not self.open_time < self.close_time:
            raise ContractSpecError("open_time must be before close_time")
        # A reference value fixed before trading closes would leave trading open after the
        # outcome is determined; such a contract is out of scope and refused, not modeled.
        if self.outcome_reference_time < self.close_time:
            raise ContractSpecError("outcome_reference_time must not precede close_time")
        try:
            ZoneInfo(self.rule_timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError) as error:
            raise ContractSpecError("rule_timezone must be an IANA timezone name") from error
        for name in ("price_units_per_payout", "quantity_units_per_contract"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ContractSpecError(f"{name} must be a positive int")
        if self.price_units_per_payout < 2:
            raise ContractSpecError("price_units_per_payout must be at least 2")
        self._check_verification()

    def _check_identity(self) -> None:
        if self.venue is Provider.KALSHI:
            kinds = (
                ("market_id", IdentifierKind.KALSHI_MARKET_TICKER),
                ("event_id", IdentifierKind.KALSHI_EVENT_TICKER),
                ("series_id", IdentifierKind.KALSHI_SERIES_TICKER),
            )
            for name, kind in kinds:
                value = getattr(self, name)
                # Kalshi documents one event per market and one series per event, so both
                # relationships are required, explicit, and never parsed from the ticker.
                if not isinstance(value, str) or normalize_identifier(kind, value) != value:
                    raise ContractSpecError(f"{name} must be a normalized Kalshi ticker")
            if self.underlying not in (Underlying.BTC, Underlying.GOLD):
                raise ContractSpecError("a Kalshi contract in scope must be BTC or gold")
            return
        for name in ("market_id", "event_id", "series_id"):
            value = getattr(self, name)
            if value is None and name != "market_id":
                continue
            if (
                not isinstance(value, str)
                or not 1 <= len(value) <= 128
                or not set(value) <= _SYNTHETIC_ID_CHARS
            ):
                raise ContractSpecError(f"{name} is not a synthetic identifier")
        if self.underlying is not Underlying.SYNTHETIC:
            raise ContractSpecError("a synthetic contract must have a synthetic underlying")

    def _check_verification(self) -> None:
        if self.verification is Verification.VERIFIED_OFFICIAL:
            if self.venue is Provider.PMV_SYNTHETIC:
                raise ContractSpecError("a synthetic contract cannot be officially verified")
            if not is_sha256(self.rules_source_sha256):
                raise ContractSpecError("a verified spec must record its rules source SHA-256")
        elif self.rules_source_sha256 is not None and not is_sha256(self.rules_source_sha256):
            raise ContractSpecError("rules_source_sha256 must be a SHA-256 or None")
        if self.verification is Verification.SYNTHETIC and self.venue is not Provider.PMV_SYNTHETIC:
            raise ContractSpecError("only the synthetic venue may use SYNTHETIC verification")

    def encode(self) -> Mapping[str, object]:
        """The canonical field mapping that ``spec_key`` hashes."""
        return {
            "close_time": format_timestamp(self.close_time),
            "event_id": self.event_id,
            "fee_schedule_effective_from": format_timestamp(self.fee_schedule_effective_from),
            "fee_schedule_id": self.fee_schedule_id,
            "market_id": self.market_id,
            "open_time": format_timestamp(self.open_time),
            "outcome_reference_time": format_timestamp(self.outcome_reference_time),
            "price_units_per_payout": self.price_units_per_payout,
            "quantity_units_per_contract": self.quantity_units_per_contract,
            "resolution_rule_id": self.resolution_rule_id,
            "resolution_source_id": self.resolution_source_id,
            "rounding_rule_id": self.rounding_rule_id,
            "rule_timezone": self.rule_timezone,
            "rules_source_sha256": self.rules_source_sha256,
            "series_id": self.series_id,
            "spec_version": SPEC_VERSION,
            "underlying": self.underlying.value,
            "venue": self.venue.value,
            "verification": self.verification.value,
            "void_rule_id": self.void_rule_id,
            "yes_region": self.yes_region.encode(),
        }

    @property
    def spec_key(self) -> str:
        return sha256_hex(canonical_json(self.encode()))

    @property
    def window_length(self) -> timedelta:
        return self.close_time - self.open_time

    def time_remaining(self, decision_time: datetime) -> timedelta:
        """Time from ``decision_time`` to ``close_time``; always positive.

        Raises ``OutsideTradingWindowError`` outside ``[open_time, close_time)``. Time
        remaining is a first-class model input (CLAUDE.md "Strategy Scope"); the remaining
        forecast horizon runs to ``outcome_reference_time`` (``time_to_reference``).
        """
        moment = self._check_decision_time(decision_time)
        return self.close_time - moment

    def time_to_reference(self, decision_time: datetime) -> timedelta:
        """Time from ``decision_time`` to the instant the outcome's reference value is fixed."""
        moment = self._check_decision_time(decision_time)
        return self.outcome_reference_time - moment

    def elapsed(self, decision_time: datetime) -> timedelta:
        moment = self._check_decision_time(decision_time)
        return moment - self.open_time

    def tradable_at(self, decision_time: datetime) -> bool:
        moment = ensure_utc(decision_time, "decision_time")
        return self.open_time <= moment < self.close_time

    def _check_decision_time(self, decision_time: datetime) -> datetime:
        moment = ensure_utc(decision_time, "decision_time")
        if not self.open_time <= moment < self.close_time:
            raise OutsideTradingWindowError("decision time is outside the trading window")
        return moment
