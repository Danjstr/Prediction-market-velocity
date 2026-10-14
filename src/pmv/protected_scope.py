"""Protected-scope registry and the equivalent-information catalog (Phase 0 Step 9).

The final holdout is protected INFORMATION, not just a file: protected observations,
outcomes, and equivalent information capable of reconstructing them (for example the
underlying asset price that resolves a protected contract) stay unavailable to development
agents until authorized final evaluation, whatever the source. This module defines:

- the closed v1 protected-scope record (metadata only: no values, labels, or outcomes);
- the registry ``research/protected_scopes/registry.v1.json``: an append-only list of
  scopes in which a successor may only WIDEN its predecessor, verified against Git history;
- the code-versioned catalog that maps every known (provider, instrument family) pair to
  the protected observables it can reveal. Unknown pairs fail closed in the guard.

The deterministic guard that applies all this to data requests is pmv.data_access_guard.
"""

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Final

from pmv.integrity import (
    FormatError,
    canonical_json,
    canonical_line,
    is_identifier,
    is_int,
    is_sha256,
    is_timestamp,
    parse_canonical_json,
    sha256_hex,
)

REGISTRY_PATH: Final = "research/protected_scopes/registry.v1.json"
REGISTRY_SCHEMA: Final = "pmv.protected_scope_registry"
SCHEMA_VERSION: Final = 1
_TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.%fZ"
_SPLIT_PATH: Final = re.compile(r"research/splits/[a-z][a-z0-9_]{0,63}\.yaml")
_GIT_ENV: Final = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "LC_ALL": "C",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
}


class ProtectedScopeError(ValueError):
    """The registry or a scope violates the v1 rules. Messages never echo values."""


class Observable(StrEnum):
    """Protected observables: anything revealing them can reconstruct protected targets."""

    BTC_USD_PRICE = "btc_usd_price"
    XAU_USD_PRICE = "xau_usd_price"


class Venue(StrEnum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"


class Provider(StrEnum):
    KALSHI = "kalshi"
    POLYMARKET = "polymarket"
    COINBASE = "coinbase"
    BINANCE = "binance"
    KRAKEN = "kraken"
    BITSTAMP = "bitstamp"
    CF_BENCHMARKS = "cf_benchmarks"
    CME = "cme"
    LBMA = "lbma"
    EQUITY_DATA_VENDOR = "equity_data_vendor"
    FX_DATA_VENDOR = "fx_data_vendor"
    PUBLIC_DATASET = "public_dataset"
    PMV_SYNTHETIC = "pmv_synthetic"


class Family(StrEnum):
    BTC_SPOT = "btc_spot"
    BTC_REFERENCE_INDEX = "btc_reference_index"
    BTC_FUTURES = "btc_futures"
    BTC_PERPETUAL = "btc_perpetual"
    BTC_PRICE_DATASET = "btc_price_dataset"
    KALSHI_BTC_CONTRACTS = "kalshi_btc_contracts"
    POLYMARKET_BTC_MARKETS = "polymarket_btc_markets"
    GOLD_SPOT = "gold_spot"
    GOLD_REFERENCE_PRICE = "gold_reference_price"
    GOLD_FUTURES = "gold_futures"
    GOLD_ETF = "gold_etf"
    GOLD_PRICE_DATASET = "gold_price_dataset"
    KALSHI_GOLD_CONTRACTS = "kalshi_gold_contracts"
    POLYMARKET_GOLD_MARKETS = "polymarket_gold_markets"
    ETH_SPOT = "eth_spot"
    SILVER_SPOT = "silver_spot"
    DXY_INDEX = "dxy_index"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class Semantics(StrEnum):
    """What a request reveals, which decides the temporal rule the guard applies.

    A historical observation has an observation time, so the protected interval decides.
    Every other kind returns an object's state as known NOW (status, result, settlement,
    live metadata, listings), which can carry information learned later; a timestamp the
    caller attaches cannot make it historical.
    """

    HISTORICAL_OBSERVATION = "historical_observation"
    CONTRACT_METADATA = "contract_metadata"
    CURRENT_STATE = "current_state"
    RESOLUTION = "resolution"
    SETTLEMENT = "settlement"
    DISCOVERY = "discovery"


class IdentifierKind(StrEnum):
    """Every identifier form the guard understands. Any other form fails closed."""

    KALSHI_MARKET_TICKER = "kalshi_market_ticker"
    KALSHI_EVENT_TICKER = "kalshi_event_ticker"
    KALSHI_SERIES_TICKER = "kalshi_series_ticker"
    POLYMARKET_CONDITION_ID = "polymarket_condition_id"
    POLYMARKET_MARKET_ID = "polymarket_market_id"
    POLYMARKET_EVENT_ID = "polymarket_event_id"
    POLYMARKET_TOKEN_ID = "polymarket_token_id"  # noqa: S105 - an identifier kind, not a secret
    POLYMARKET_SLUG = "polymarket_slug"


class Cardinality(StrEnum):
    """How many values a contract record holds for one identifier kind."""

    ONE = "one"  # exactly one value (a JSON string)
    SOME = "some"  # a non-empty, complete list
    ANY = "any"  # a list that may be empty; an empty list means unrecorded


@dataclass(frozen=True, slots=True)
class IdentifierRule:
    """How one identifier kind is normalized and which contract-record field holds it.

    Relationships are explicit: an event or series identifier reaches a contract only when
    the contract record lists it. Ticker strings are never parsed to infer parentage.
    """

    venue: Venue
    field: str
    pattern: re.Pattern[str]
    upper: bool
    cardinality: Cardinality
    numeric: bool = False


_KALSHI_TICKER: Final = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,127}")
_CONDITION_ID: Final = re.compile(r"0x[0-9a-f]{64}")
_DECIMAL_ID: Final = re.compile(r"[0-9]{1,78}")
_SLUG: Final = re.compile(r"[a-z0-9]{1,100}(?:-[a-z0-9]{1,100}){0,30}")
_ONE, _SOME, _ANY = Cardinality.ONE, Cardinality.SOME, Cardinality.ANY

# Kalshi documents exactly one event per market and one series per event; Polymarket markets
# carry one Gamma market ID, one or more events, and two or more outcome token IDs.
IDENTIFIER_RULES: Final[Mapping[IdentifierKind, IdentifierRule]] = {
    IdentifierKind.KALSHI_MARKET_TICKER: IdentifierRule(
        Venue.KALSHI, "market_ticker", _KALSHI_TICKER, True, _ONE
    ),
    IdentifierKind.KALSHI_EVENT_TICKER: IdentifierRule(
        Venue.KALSHI, "event_ticker", _KALSHI_TICKER, True, _ONE
    ),
    IdentifierKind.KALSHI_SERIES_TICKER: IdentifierRule(
        Venue.KALSHI, "series_ticker", _KALSHI_TICKER, True, _ONE
    ),
    IdentifierKind.POLYMARKET_CONDITION_ID: IdentifierRule(
        Venue.POLYMARKET, "condition_id", _CONDITION_ID, False, _ONE
    ),
    IdentifierKind.POLYMARKET_MARKET_ID: IdentifierRule(
        Venue.POLYMARKET, "market_id", _DECIMAL_ID, False, _ONE, numeric=True
    ),
    IdentifierKind.POLYMARKET_EVENT_ID: IdentifierRule(
        Venue.POLYMARKET, "event_ids", _DECIMAL_ID, False, _SOME, numeric=True
    ),
    IdentifierKind.POLYMARKET_TOKEN_ID: IdentifierRule(
        Venue.POLYMARKET, "token_ids", _DECIMAL_ID, False, _SOME, numeric=True
    ),
    IdentifierKind.POLYMARKET_SLUG: IdentifierRule(Venue.POLYMARKET, "slugs", _SLUG, False, _ANY),
}
# Canonical contract identity per venue: Kalshi market_ticker, Polymarket condition_id.
CANONICAL_KIND: Final[Mapping[Venue, IdentifierKind]] = {
    Venue.KALSHI: IdentifierKind.KALSHI_MARKET_TICKER,
    Venue.POLYMARKET: IdentifierKind.POLYMARKET_CONDITION_ID,
}
_KIND_NAMES: Final = {kind.value.replace("_", ""): kind for kind in IdentifierKind}


def parse_identifier_kind(name: str) -> IdentifierKind | None:
    """A known kind, ignoring ASCII case and underscores (``polymarket_conditionId``)."""
    if not name.isascii():
        return None
    return _KIND_NAMES.get(name.replace("_", "").lower())


def normalize_identifier(kind: IdentifierKind, value: str) -> str | None:
    """The one canonical spelling of an identifier, or None when the form is not recognized.

    Only ASCII is accepted, so Unicode case mapping can never turn one string into another
    identity; whitespace and every other character outside the documented form are refused.
    """
    if not value.isascii():
        return None
    rule = IDENTIFIER_RULES[kind]
    text = value.upper() if rule.upper else value.lower()
    if rule.pattern.fullmatch(text) is None:
        return None
    return str(int(text)) if rule.numeric else text


@dataclass(frozen=True, slots=True)
class Contract:
    """One protected contract: its canonical identity and every recorded identifier, by kind."""

    venue: Venue
    canonical: str
    aliases: Mapping[IdentifierKind, frozenset[str]]

    def reached_by(self, kind: IdentifierKind, value: str) -> bool | None:
        """True if this normalized identifier names or contains the contract, False if it
        provably does not, None if the record lacks that kind (identity unknown)."""
        if IDENTIFIER_RULES[kind].venue is not self.venue:
            return False
        known = self.aliases[kind]
        if not known:
            return None
        return value in known


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """What one (provider, family) pair can reveal.

    ``observables`` are the protected observables it can reconstruct (empty for
    catalogued non-equivalent assets such as ETH, silver, or DXY). ``venue`` is set for
    prediction-market contract families, whose data are the protected test cases
    themselves. ``synthetic`` marks project-built fixtures, which contain no market data.
    """

    observables: frozenset[Observable]
    venue: Venue | None = None
    synthetic: bool = False


_BTC = frozenset({Observable.BTC_USD_PRICE})
_GOLD = frozenset({Observable.XAU_USD_PRICE})
_NONE: frozenset[Observable] = frozenset()

# Code-versioned and deliberately conservative. A pair that is not listed fails closed.
# Adding a pair, or mapping a correlated asset to an observable, is a reviewed code change.
CATALOG: Final[Mapping[tuple[Provider, Family], CatalogEntry]] = {
    **{
        (provider, Family.BTC_SPOT): CatalogEntry(_BTC)
        for provider in (Provider.COINBASE, Provider.BINANCE, Provider.KRAKEN, Provider.BITSTAMP)
    },
    (Provider.CF_BENCHMARKS, Family.BTC_REFERENCE_INDEX): CatalogEntry(_BTC),
    (Provider.CME, Family.BTC_FUTURES): CatalogEntry(_BTC),
    (Provider.BINANCE, Family.BTC_PERPETUAL): CatalogEntry(_BTC),
    (Provider.PUBLIC_DATASET, Family.BTC_PRICE_DATASET): CatalogEntry(_BTC),
    (Provider.KALSHI, Family.KALSHI_BTC_CONTRACTS): CatalogEntry(_BTC, Venue.KALSHI),
    (Provider.POLYMARKET, Family.POLYMARKET_BTC_MARKETS): CatalogEntry(_BTC, Venue.POLYMARKET),
    (Provider.FX_DATA_VENDOR, Family.GOLD_SPOT): CatalogEntry(_GOLD),
    (Provider.LBMA, Family.GOLD_REFERENCE_PRICE): CatalogEntry(_GOLD),
    (Provider.CME, Family.GOLD_FUTURES): CatalogEntry(_GOLD),
    (Provider.EQUITY_DATA_VENDOR, Family.GOLD_ETF): CatalogEntry(_GOLD),
    (Provider.PUBLIC_DATASET, Family.GOLD_PRICE_DATASET): CatalogEntry(_GOLD),
    (Provider.KALSHI, Family.KALSHI_GOLD_CONTRACTS): CatalogEntry(_GOLD, Venue.KALSHI),
    (Provider.POLYMARKET, Family.POLYMARKET_GOLD_MARKETS): CatalogEntry(_GOLD, Venue.POLYMARKET),
    **{
        (provider, Family.ETH_SPOT): CatalogEntry(_NONE)
        for provider in (Provider.COINBASE, Provider.BINANCE, Provider.KRAKEN)
    },
    (Provider.FX_DATA_VENDOR, Family.SILVER_SPOT): CatalogEntry(_NONE),
    (Provider.FX_DATA_VENDOR, Family.DXY_INDEX): CatalogEntry(_NONE),
    (Provider.PMV_SYNTHETIC, Family.SYNTHETIC_FIXTURE): CatalogEntry(_NONE, synthetic=True),
}


# The protected observables any catalogued family of each provider can reveal. Used where the
# caller-asserted family cannot be trusted to bound what an endpoint returns.
PROVIDER_OBSERVABLES: Final[Mapping[Provider, frozenset[Observable]]] = {
    provider: frozenset().union(
        *(entry.observables for (owner, _), entry in CATALOG.items() if owner is provider)
    )
    for provider in Provider
}


# ----- scopes -----


@dataclass(frozen=True, slots=True)
class Scope:
    """One validated protected scope. Metadata only."""

    document: Mapping[str, object]

    @property
    def scope_id(self) -> str:
        return str(self.document["scope_id"])

    @property
    def cycle_id(self) -> str:
        return str(self.document["cycle_id"])

    @property
    def sha256(self) -> str:
        return sha256_hex(canonical_json(self.document))

    @property
    def start(self) -> datetime:
        return _parse_time(_interval(self.document)["start"])

    @property
    def end(self) -> datetime | None:
        end = _interval(self.document)["end"]
        return None if end is None else _parse_time(end)

    @property
    def margin_seconds(self) -> int:
        return int(str(self.document["margin_seconds"]))

    @property
    def lags(self) -> Mapping[Observable, int]:
        return {
            Observable(str(item["observable"])): int(str(item["resolution_lag_seconds"]))
            for item in _items(self.document["observables"])
        }

    @property
    def venues(self) -> frozenset[Venue]:
        return frozenset(Venue(str(item)) for item in _list(self.document["venues"]))

    @property
    def contracts(self) -> tuple[Contract, ...]:
        return tuple(_contract(item) for item in _items(self.document["contracts"]))

    @property
    def supersedes(self) -> tuple[str, str] | None:
        value = self.document["supersedes"]
        if value is None:
            return None
        item = _mapping(value)
        return str(item["scope_id"]), str(item["scope_sha256"])


def validate_scope(value: object) -> Scope:
    document = _mapping(value)
    _keys(
        document,
        {
            "scope_id",
            "cycle_id",
            "holdout_id",
            "declared_at",
            "supersedes",
            "split_definition",
            "protected_interval",
            "margin_seconds",
            "observables",
            "venues",
            "contracts",
            "attestation",
        },
        "scope",
    )
    for key in ("scope_id", "cycle_id"):
        if not is_identifier(document[key]):
            raise ProtectedScopeError(f"{key} is malformed")
    if document["holdout_id"] is not None and not is_identifier(document["holdout_id"]):
        raise ProtectedScopeError("holdout_id is malformed")
    if not is_timestamp(document["declared_at"]):
        raise ProtectedScopeError("declared_at is malformed")
    if document["supersedes"] is not None:
        prior = _mapping(document["supersedes"])
        _keys(prior, {"scope_id", "scope_sha256"}, "supersedes")
        if not is_identifier(prior["scope_id"]) or not is_sha256(prior["scope_sha256"]):
            raise ProtectedScopeError("supersedes is malformed")
        if prior["scope_id"] == document["scope_id"]:
            raise ProtectedScopeError("a scope cannot supersede itself")
    split = _mapping(document["split_definition"])
    _keys(split, {"path", "sha256"}, "split_definition")
    if not isinstance(split["path"], str) or _SPLIT_PATH.fullmatch(split["path"]) is None:
        raise ProtectedScopeError("the split definition must be research/splits/<split_id>.yaml")
    if not is_sha256(split["sha256"]):
        raise ProtectedScopeError("the split definition hash is malformed")
    interval = _mapping(document["protected_interval"])
    _keys(interval, {"start", "end"}, "protected_interval")
    if not is_timestamp(interval["start"]):
        raise ProtectedScopeError("protected_interval.start is malformed")
    if interval["end"] is not None and (
        not is_timestamp(interval["end"]) or not str(interval["start"]) < str(interval["end"])
    ):
        raise ProtectedScopeError("protected_interval.end must be null or after start")
    margin = document["margin_seconds"]
    if not is_int(margin) or margin < 0:
        raise ProtectedScopeError("margin_seconds must be stated as a non-negative integer")
    observables = _items(document["observables"])
    if not observables:
        raise ProtectedScopeError("a scope protects at least one observable")
    for item in observables:
        _keys(item, {"observable", "resolution_lag_seconds"}, "observable")
        _enum(Observable, item["observable"], "observable")
        lag = item["resolution_lag_seconds"]
        if not is_int(lag) or lag < 0:
            raise ProtectedScopeError("resolution_lag_seconds must be a non-negative integer")
    _sorted_unique([str(item["observable"]) for item in observables], "observables")
    venues = [str(_enum(Venue, item, "venue")) for item in _list(document["venues"])]
    _sorted_unique(venues, "venues")
    contracts = _items(document["contracts"])
    for item in contracts:
        _validate_contract(item)
    _sorted_unique([canonical_json(item) for item in contracts], "contracts")
    identities = [(str(item["venue"]), str(_contract(item).canonical)) for item in contracts]
    if len(set(identities)) != len(identities):
        raise ProtectedScopeError("two contract records share a canonical identity")
    attestation = _mapping(document["attestation"])
    _keys(attestation, {"role", "attested"}, "attestation")
    if attestation["role"] != "project_owner" or attestation["attested"] is not True:
        raise ProtectedScopeError("a protected scope requires explicit project-owner attestation")
    return Scope(dict(document))


def widens(new: Scope, old: Scope) -> bool:
    """Whether ``new`` covers at least everything ``old`` protects (never shrinks)."""
    old_end, new_end = old.end, new.end
    end_ok = new_end is None or (old_end is not None and new_end >= old_end)
    lags_ok = all(new.lags.get(observable, -1) >= lag for observable, lag in old.lags.items())
    holdout_ok = old.document["holdout_id"] in (None, new.document["holdout_id"])
    return (
        new.cycle_id == old.cycle_id
        and holdout_ok
        and new.start <= old.start
        and end_ok
        and new.margin_seconds >= old.margin_seconds
        and lags_ok
        and new.venues >= old.venues
        and _contracts_widen(new.contracts, old.contracts)
    )


def _contracts_widen(new: Sequence[Contract], old: Sequence[Contract]) -> bool:
    """Every old contract survives with every identifier (lists may only gain values)."""
    by_identity = {(item.venue, item.canonical): item for item in new}
    for item in old:
        successor = by_identity.get((item.venue, item.canonical))
        if successor is None:
            return False
        if any(not values <= successor.aliases[kind] for kind, values in item.aliases.items()):
            return False
    return True


def _contract_fields(venue: Venue) -> dict[str, IdentifierKind]:
    return {rule.field: kind for kind, rule in IDENTIFIER_RULES.items() if rule.venue is venue}


def _field_values(item: Mapping[str, object], field: str, kind: IdentifierKind) -> list[object]:
    if IDENTIFIER_RULES[kind].cardinality is Cardinality.ONE:
        return [item[field]]
    return _list(item[field])


def _validate_contract(item: Mapping[str, object]) -> None:
    venue = Venue(_enum(Venue, item.get("venue"), "contract venue"))
    fields = _contract_fields(venue)
    _keys(item, {"venue", *fields}, "contract")
    for field, kind in fields.items():
        cardinality = IDENTIFIER_RULES[kind].cardinality
        if cardinality is not Cardinality.ONE and not isinstance(item[field], list):
            raise ProtectedScopeError("a contract identifier list must be a list")
        values = _field_values(item, field, kind)
        if cardinality is Cardinality.SOME and not values:
            raise ProtectedScopeError("a required contract identifier list is empty")
        for value in values:
            if not isinstance(value, str) or normalize_identifier(kind, value) != value:
                raise ProtectedScopeError("a contract identifier is malformed or not canonical")
        _sorted_unique(values, "contract identifiers")


def _contract(item: Mapping[str, object]) -> Contract:
    venue = Venue(str(item["venue"]))
    aliases = {
        kind: frozenset(str(value) for value in _field_values(item, field, kind))
        for field, kind in _contract_fields(venue).items()
    }
    return Contract(venue, str(item[IDENTIFIER_RULES[CANONICAL_KIND[venue]].field]), aliases)


# ----- registry -----


@dataclass(frozen=True, slots=True)
class Registry:
    scopes: tuple[Scope, ...]

    @property
    def active(self) -> tuple[Scope, ...]:
        """Scopes not superseded. Every scope stays protected; supersession only widens."""
        superseded = {scope.supersedes[0] for scope in self.scopes if scope.supersedes}
        return tuple(scope for scope in self.scopes if scope.scope_id not in superseded)


def parse_registry(data: bytes) -> Registry:
    """Parse and fully validate the canonical registry file."""
    if not data.endswith(b"\n"):
        raise ProtectedScopeError("the registry must end with one newline")
    try:
        document = parse_canonical_json(data[:-1])
    except FormatError:
        raise ProtectedScopeError("the registry is not canonical JSON") from None
    _keys(document, {"schema", "schema_version", "scopes"}, "registry")
    version = document["schema_version"]
    if document["schema"] != REGISTRY_SCHEMA or not is_int(version) or version != SCHEMA_VERSION:
        raise ProtectedScopeError("the registry schema is not supported")
    scopes: list[Scope] = []
    by_id: dict[str, Scope] = {}
    successors: set[str] = set()
    for item in _list(document["scopes"]):
        scope = validate_scope(item)
        if scope.scope_id in by_id:
            raise ProtectedScopeError("two scopes share a scope_id")
        if scope.supersedes is not None:
            prior_id, prior_sha = scope.supersedes
            prior = by_id.get(prior_id)
            if prior is None or prior.sha256 != prior_sha:
                raise ProtectedScopeError("a scope supersedes an unknown or changed earlier scope")
            if prior_id in successors:
                raise ProtectedScopeError("a scope has competing successors (a fork)")
            if not widens(scope, prior):
                raise ProtectedScopeError("a successor scope may only widen, never shrink")
            successors.add(prior_id)
        by_id[scope.scope_id] = scope
        scopes.append(scope)
    return Registry(tuple(scopes))


def empty_registry_bytes() -> bytes:
    return canonical_line(
        {"schema": REGISTRY_SCHEMA, "schema_version": SCHEMA_VERSION, "scopes": []}
    )


def load_registry(repo: Path) -> Registry:
    """The working-tree registry, read without following symlinks."""
    return parse_registry(_read_repo_file(repo, REGISTRY_PATH))


def verify_registry_history(repo: Path) -> Registry:
    """The working-tree registry, after :func:`_verify_history` passes."""
    return _verify_history(repo)[1]


def verify_committed_registry(repo: Path) -> tuple[Registry, Registry]:
    """(committed HEAD registry, working-tree registry), both verified.

    Only the COMMITTED registry can declare a scope: an uncommitted file never authorizes
    real data. Every committed scope's split definition must exist at HEAD as a regular file
    whose SHA-256 matches, so a placeholder hash cannot make a scope operational.
    """
    committed, working = _verify_history(repo)
    for scope in committed.scopes:
        split = _mapping(scope.document["split_definition"])
        data = _head_file(Path(os.path.realpath(repo)), str(split["path"]))
        if data is None or sha256_hex(data) != split["sha256"]:
            raise ProtectedScopeError("a committed scope's split definition is missing or changed")
    return committed, working


def _verify_history(repo: Path) -> tuple[Registry, Registry]:
    """Verify the working tree and every committed version in HEAD's history.

    Once the registry exists it is never removed. Across every commit (merges compared with
    every parent) the scope list only grows: each earlier version's scopes are an exact
    prefix of each later version's, so a declared scope is never edited, removed, replaced,
    or shrunk. The working tree must extend HEAD the same way. Shallow clones, grafts, and
    replace refs cannot be used to hide history. Git is not external notarization.
    """
    repo = Path(os.path.realpath(repo))
    if _git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ProtectedScopeError("registry history cannot be verified in a shallow clone")
    common = os.fsdecode(
        _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    )
    if os.path.lexists(Path(common) / "info" / "grafts"):
        raise ProtectedScopeError(
            "registry history cannot be verified while info/grafts rewrites it"
        )
    working = load_registry(repo)
    graph = [
        line.split()
        for line in _git(repo, "rev-list", "--topo-order", "--parents", "HEAD")
        .decode()
        .splitlines()
    ]
    blobs = {commit: _blob(repo, commit) for commit, *_parents in graph}
    parsed: dict[str, Registry] = {}
    for commit, *parents in reversed(graph):
        blob = blobs[commit]
        parent_blobs = [blobs[parent] for parent in parents if parent in blobs]
        if blob is None:
            if any(item is not None for item in parent_blobs):
                raise ProtectedScopeError("a commit removed the protected-scope registry")
            continue
        registry = parsed.setdefault(blob, _committed(repo, blob))
        for parent_blob in parent_blobs:
            if parent_blob is not None and parent_blob != blob:
                _require_prefix(
                    parsed.setdefault(parent_blob, _committed(repo, parent_blob)), registry
                )
    head = blobs[graph[0][0]] if graph else None
    if head is None:
        return Registry(()), working
    _require_prefix(parsed[head], working)
    return parsed[head], working


def _require_prefix(earlier: Registry, later: Registry) -> None:
    before = [canonical_json(scope.document) for scope in earlier.scopes]
    after = [canonical_json(scope.document) for scope in later.scopes]
    if after[: len(before)] != before:
        raise ProtectedScopeError(
            "registry history shows a protected scope edited, removed, or replaced"
        )


def _committed(repo: Path, blob: str) -> Registry:
    try:
        return parse_registry(_git(repo, "cat-file", "blob", blob))
    except ProtectedScopeError as exc:
        raise ProtectedScopeError(f"a committed registry version is invalid: {exc}") from None


def _head_file(repo: Path, path: str) -> bytes | None:
    """A regular file's bytes at HEAD, or None if it is absent or not a regular file."""
    listing = _git(repo, "ls-tree", "-z", "HEAD", "--", path)
    if not listing:
        return None
    meta = listing.split(b"\t", 1)[0].decode("ascii").split(" ")
    if len(meta) != 3 or meta[0] not in {"100644", "100755"} or meta[1] != "blob":
        return None
    return _git(repo, "cat-file", "blob", meta[2])


def _blob(repo: Path, commit: str) -> str | None:
    listing = _git(repo, "ls-tree", "-z", commit, "--", REGISTRY_PATH)
    if not listing:
        return None
    meta = listing.split(b"\t", 1)[0].decode("ascii").split(" ")
    if len(meta) != 3 or meta[1] != "blob" or meta[0] not in ("100644", "100755"):
        raise ProtectedScopeError("the committed registry path is not a regular file")
    return meta[2]


def _git(repo: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument list, absolute path, clean environment
            ["/usr/bin/git", "-C", str(repo), "--no-optional-locks", *arguments],
            capture_output=True,
            env=_GIT_ENV,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ProtectedScopeError("git could not be run") from None
    if completed.returncode != 0:
        raise ProtectedScopeError("a git command failed")
    return completed.stdout


def _read_repo_file(repo: Path, path: str) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory_flags = flags | os.O_DIRECTORY
    *directories, name = path.split("/")
    try:
        fd = os.open(repo, directory_flags)
        try:
            for directory in directories:
                child = os.open(directory, directory_flags, dir_fd=fd)
                os.close(fd)
                fd = child
            file_fd = os.open(name, flags, dir_fd=fd)
        finally:
            os.close(fd)
    except OSError:
        raise ProtectedScopeError(
            "the protected-scope registry is missing or not a plain file"
        ) from None
    try:
        chunks = []
        while chunk := os.read(file_fd, 1_048_576):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(file_fd)


# ----- helpers -----


def _parse_time(value: object) -> datetime:
    return datetime.strptime(str(value), _TIMESTAMP_FORMAT).replace(tzinfo=UTC)


def _interval(document: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(document["protected_interval"])


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProtectedScopeError("a registry field must be an object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ProtectedScopeError("a registry field must be a list")
    return value


def _items(value: object) -> list[Mapping[str, object]]:
    return [_mapping(item) for item in _list(value)]


def _keys(value: Mapping[str, object], expected: set[str], what: str) -> None:
    if set(value) != expected:
        raise ProtectedScopeError(f"{what} fields do not match the v1 schema")


def _enum(enum: type[StrEnum], value: object, what: str) -> str:
    if not isinstance(value, str) or value not in {item.value for item in enum}:
        raise ProtectedScopeError(f"{what} is not a known value")
    return value


def _sorted_unique(values: Sequence[object], what: str) -> None:
    keys = [value if isinstance(value, (str, bytes)) else str(value) for value in values]
    if any(not (str(left) < str(right)) for left, right in pairwise(keys)):
        raise ProtectedScopeError(f"{what} must be sorted and unique")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pmv.protected_scope", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-history", help="verify the registry and its Git history")
    arguments = parser.parse_args(argv)
    try:
        committed, registry = verify_committed_registry(arguments.repo)
    except ProtectedScopeError as exc:
        sys.stderr.write(f"ProtectedScopeError: {exc}\n")
        return 1
    sys.stdout.write(
        f"protected-scope registry verified: {len(registry.scopes)} scope(s), "
        f"{len(registry.active)} active, {len(committed.scopes)} committed\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
