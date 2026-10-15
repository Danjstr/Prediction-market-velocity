"""Kalshi adapter boundary: FAIL-CLOSED until verified from current official sources.

Kalshi is the first Phase 1 venue (owner direction). This module fixes where the Kalshi
adapter plugs in (``replay.Normalizer``) and what it must produce (``events``,
``labels.ResolutionRecord``, ``contracts.ContractSpec``), without assuming anything about
Kalshi's API.

Not one Kalshi message field, endpoint, channel, sequence rule, price unit, fee, contract
rule, or eligibility fact is encoded here. ``REQUIRED_VERIFICATIONS`` lists what must be
verified from current official documentation, with sources and retrieval dates recorded in
research/sources.md, before a parser is written. Until then ``KalshiNormalizer`` refuses
every payload by raising ``KalshiSpecUnverifiedError``, which fails the whole replay rather
than recording a per-frame rejection: an unverified parser must not produce a partially
normalized capture that looks usable.

The only Kalshi facts used are those already recorded in the repository: the ticker forms
and the one-event-per-market, one-series-per-event relationships in
``pmv.protected_scope``.
"""

from typing import Final

from pmv.market_data.replay import NormalizeContext, Parsed, Skipped
from pmv.protected_scope import IdentifierKind, normalize_identifier

__all__ = [
    "PARSER_ID",
    "REQUIRED_VERIFICATIONS",
    "KalshiNormalizer",
    "KalshiSpecUnverifiedError",
    "normalize_tickers",
]

PARSER_ID: Final = "kalshi_unverified"
PARSER_VERSION: Final = 1

# Each item must be verified from current official Kalshi sources and recorded (title,
# URL, retrieval date, status) in research/sources.md before code relies on it.
REQUIRED_VERIFICATIONS: Final = (
    "api_terms_and_permitted_use",
    "account_and_jurisdiction_eligibility",
    "authentication_for_market_data",
    "rest_market_and_event_metadata_schema",
    "websocket_channels_and_message_schema",
    "websocket_sequence_and_snapshot_semantics",
    "orderbook_representation_and_price_units",
    "orderbook_delta_semantics_absolute_or_relative",
    "trade_print_schema_and_identifiers",
    "timestamp_fields_and_resolution",
    "rate_limits",
    "historical_data_depth_and_resolution",
    "btc_and_gold_series_availability",
    "contract_rules_settlement_source_and_timing",
    "settlement_reference_window_or_averaging",
    "early_close_and_extension_semantics",
    "lifecycle_status_messages_and_result_fields",
    "sequence_number_scope_per_subscription_or_market",
    "tie_rounding_and_void_rules",
    "fee_schedule_and_effective_dates",
    "demo_environment_scope_and_fidelity",
)


class KalshiSpecUnverifiedError(RuntimeError):
    """The Kalshi wire format has not been verified from current official sources."""


class KalshiNormalizer:
    """Placeholder for the Kalshi parser. It refuses every payload."""

    @property
    def parser_id(self) -> str:
        return PARSER_ID

    @property
    def parser_version(self) -> int:
        return PARSER_VERSION

    def normalize(self, payload: bytes, context: NormalizeContext) -> Parsed | Skipped:
        raise KalshiSpecUnverifiedError(
            "Kalshi payloads cannot be normalized until the wire format is verified"
        )


def normalize_tickers(market: str, event: str, series: str) -> tuple[str, str, str] | None:
    """The normalized (market, event, series) tickers, or None if any form is invalid.

    Relationships are supplied explicitly by the caller and are never parsed from ticker
    strings.
    """
    normalized = (
        normalize_identifier(IdentifierKind.KALSHI_MARKET_TICKER, market),
        normalize_identifier(IdentifierKind.KALSHI_EVENT_TICKER, event),
        normalize_identifier(IdentifierKind.KALSHI_SERIES_TICKER, series),
    )
    if normalized[0] is None or normalized[1] is None or normalized[2] is None:
        return None
    return (normalized[0], normalized[1], normalized[2])
