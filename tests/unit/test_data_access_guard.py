"""Tests for the deterministic data-access guard (synthetic scopes and data only)."""

import io
import json
import logging
import os
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from pmv.config import LoggingConfig, LogLevel
from pmv.data_access_guard import (
    DataRequest,
    Guard,
    GuardError,
    Identifier,
    RefusalReason,
    Window,
    check_config,
    check_path,
    request_from_json,
)
from pmv.integrity import canonical_json, canonical_line, sha256_hex
from pmv.log import configure_logging
from pmv.protected_scope import REGISTRY_PATH, Registry, Semantics, parse_registry

REPO = Path(__file__).resolve().parents[2]
START = datetime(2026, 2, 1, tzinfo=UTC)
END = datetime(2026, 3, 1, tzinfo=UTC)
MARGIN = timedelta(hours=1)
LAG = timedelta(seconds=60)
CONTRACT = "SYNBTC-26FEB01-T1"
CONDITION = "0x" + "c1" * 32
KALSHI_BTC: dict[str, Any] = {
    "event_ticker": "SYNBTC-26FEB01",
    "market_ticker": CONTRACT,
    "series_ticker": "SYNBTC",
    "venue": "kalshi",
}
POLYMARKET_BTC: dict[str, Any] = {
    "condition_id": CONDITION,
    "event_ids": ["700"],
    "market_id": "701",
    "slugs": ["syn-btc-up-feb"],
    "token_ids": ["702", "703"],
    "venue": "polymarket",
}


def scope(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "attestation": {"attested": True, "role": "project_owner"},
        "contracts": [POLYMARKET_BTC, KALSHI_BTC],
        "cycle_id": "cycle_a",
        "declared_at": "2026-01-01T00:00:00.000000Z",
        "holdout_id": "holdout_a",
        "margin_seconds": 3600,
        "observables": [{"observable": "btc_usd_price", "resolution_lag_seconds": 60}],
        "protected_interval": {
            "end": "2026-03-01T00:00:00.000000Z",
            "start": "2026-02-01T00:00:00.000000Z",
        },
        "scope_id": "scope_btc",
        "split_definition": {"path": "research/splits/split_a.yaml", "sha256": "1" * 64},
        "supersedes": None,
        "venues": ["kalshi"],
    }
    base.update(changes)
    return base


GOLD = scope(
    scope_id="scope_gold",
    cycle_id="cycle_gold",
    holdout_id="holdout_gold",
    contracts=[
        {
            "event_ticker": "SYNGOLD-26FEB01",
            "market_ticker": "SYNGOLD-26FEB01-T1",
            "series_ticker": "SYNGOLD",
            "venue": "kalshi",
        }
    ],
    observables=[{"observable": "xau_usd_price", "resolution_lag_seconds": 300}],
)


def registry(*scopes: dict[str, Any]) -> Registry:
    return parse_registry(
        canonical_line(
            {"schema": "pmv.protected_scope_registry", "schema_version": 1, "scopes": list(scopes)}
        )
    )


def window(
    provider: str = "coinbase",
    family: str = "btc_spot",
    start: datetime = datetime(2025, 6, 1, tzinfo=UTC),
    end: datetime = datetime(2025, 7, 1, tzinfo=UTC),
    semantics: str = "historical_observation",
    identifiers: tuple[tuple[str, str], ...] = (),
) -> Window:
    pairs = tuple(Identifier(kind, value) for kind, value in identifiers)
    return Window(provider, family, semantics, start, end, pairs)


def decide(guard: Guard, data_window: Window, *derived: Window) -> Any:
    return guard.decide(DataRequest("req_1", "data_scientist", data_window, tuple(derived)))


SYNTHETIC = window("pmv_synthetic", "synthetic_fixture", START, END)
GUARD = Guard(registry(scope(), GOLD))


# ----- A, B: before and after a real scope is declared -----


def test_a_an_empty_registry_refuses_real_data_but_allows_synthetic_fixtures() -> None:
    empty = Guard(registry())
    for real in (window(), window("coinbase", "eth_spot"), window("fx_data_vendor", "gold_spot")):
        decision = decide(empty, real)
        assert not decision.allowed
        assert decision.reason is RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    assert decide(empty, SYNTHETIC).allowed
    missing = Guard(None)
    assert decide(missing, window()).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    assert decide(missing, SYNTHETIC).allowed


def test_a_the_real_repository_registry_authorizes_no_real_data() -> None:
    guard = Guard.from_repo(REPO)
    assert decide(guard, window()).reason is RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    assert decide(guard, SYNTHETIC).allowed


def test_b_a_development_window_is_allowed_only_outside_an_active_scope() -> None:
    assert decide(GUARD, window(end=START - MARGIN)).allowed
    assert not decide(GUARD, window(end=START - MARGIN + timedelta(microseconds=1))).allowed


# ----- C, D, E: overlap, boundaries, margin -----


def test_c_a_protected_timestamp_is_refused() -> None:
    inside = window(start=START + timedelta(days=3), end=START + timedelta(days=4))
    assert decide(GUARD, inside).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    kalshi = window(
        "kalshi", "kalshi_btc_contracts", START + timedelta(days=3), START + timedelta(days=4)
    )
    decision = decide(GUARD, kalshi)
    assert decision.reason is RefusalReason.PROTECTED_SCOPE_OVERLAP
    assert decision.scope_id == "scope_btc"


def test_d_a_boundary_straddling_window_is_refused() -> None:
    straddle = window(start=START - timedelta(days=10), end=START + timedelta(minutes=1))
    assert not decide(GUARD, straddle).allowed
    tail = window(start=END - timedelta(minutes=1), end=END + timedelta(days=10))
    assert not decide(GUARD, tail).allowed


def test_e_margin_and_resolution_lag_widen_the_protected_window() -> None:
    before = window(start=START - MARGIN - timedelta(days=1), end=START - MARGIN)
    assert decide(GUARD, before).allowed
    just_inside_margin = window(start=START - MARGIN, end=START - MARGIN + timedelta(seconds=1))
    assert not decide(GUARD, just_inside_margin).allowed
    after = window(start=END + MARGIN + LAG, end=END + MARGIN + LAG + timedelta(days=1))
    assert decide(GUARD, after).allowed
    inside_lag = window(start=END + MARGIN + LAG - timedelta(seconds=1), end=END + MARGIN + LAG)
    assert not decide(GUARD, inside_lag).allowed


# ----- F, G, H: equivalence -----


@pytest.mark.parametrize(
    ("provider", "family"),
    [
        ("binance", "btc_spot"),
        ("kraken", "btc_spot"),
        ("cf_benchmarks", "btc_reference_index"),
        ("cme", "btc_futures"),
        ("binance", "btc_perpetual"),
        ("public_dataset", "btc_price_dataset"),
    ],
)
def test_f_alternate_btc_sources_are_refused_during_a_protected_btc_window(
    provider: str, family: str
) -> None:
    decision = decide(
        GUARD, window(provider, family, START + timedelta(days=1), START + timedelta(days=2))
    )
    assert decision.reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


def test_f_other_venue_btc_markets_are_refused_during_a_protected_btc_window() -> None:
    feb = (START + timedelta(days=1), START + timedelta(days=2))
    unlisted = Guard(registry(scope(contracts=[])))
    target = window("polymarket", "polymarket_btc_markets", *feb)
    assert decide(unlisted, target).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    # The bulk request may also include the listed protected Polymarket contract itself.
    assert decide(GUARD, target).reason is RefusalReason.PROTECTED_SCOPE_OVERLAP


@pytest.mark.parametrize(
    ("provider", "family"),
    [
        ("fx_data_vendor", "gold_spot"),
        ("lbma", "gold_reference_price"),
        ("cme", "gold_futures"),
        ("equity_data_vendor", "gold_etf"),
        ("public_dataset", "gold_price_dataset"),
    ],
)
def test_g_gold_equivalents_are_refused_during_a_protected_gold_window(
    provider: str, family: str
) -> None:
    near_resolution = window(
        provider,
        family,
        END + MARGIN + timedelta(seconds=200),
        END + MARGIN + timedelta(seconds=250),
    )
    assert decide(GUARD, near_resolution).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


def test_g_other_venue_gold_markets_are_refused_near_a_protected_gold_resolution() -> None:
    near = (END + MARGIN + timedelta(seconds=200), END + MARGIN + timedelta(seconds=250))
    target = window("polymarket", "polymarket_gold_markets", *near)
    gold_only = Guard(registry(dict(GOLD, venues=[])))
    assert decide(gold_only, target).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    # Under GUARD the bulk request may also include the protected Polymarket BTC contract.
    assert decide(GUARD, target).reason is RefusalReason.PROTECTED_SCOPE_OVERLAP


@pytest.mark.parametrize(
    ("provider", "family"),
    [("coinbase", "eth_spot"), ("fx_data_vendor", "silver_spot"), ("fx_data_vendor", "dxy_index")],
)
def test_h_correlated_but_non_equivalent_assets_are_allowed(provider: str, family: str) -> None:
    assert decide(GUARD, window(provider, family, START, END)).allowed


# ----- I, J: contracts and metadata -----


def test_i_a_protected_contract_is_refused_under_every_semantics_at_every_time() -> None:
    named = (("kalshi_market_ticker", CONTRACT),)
    for start, end in (
        (datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 1, 2, tzinfo=UTC)),
        (START, END),
        (datetime(2030, 1, 1, tzinfo=UTC), datetime(2030, 1, 2, tzinfo=UTC)),
    ):
        for semantics in Semantics:
            target = window("kalshi", "kalshi_btc_contracts", start, end, semantics.value, named)
            assert decide(GUARD, target).reason is RefusalReason.PROTECTED_SCOPE_OVERLAP


def test_j_protected_venue_metadata_is_refused_whatever_the_window() -> None:
    for family in ("kalshi_btc_contracts", "kalshi_gold_contracts"):
        listing = window(
            "kalshi",
            family,
            datetime(2020, 1, 1, tzinfo=UTC),
            datetime(2020, 1, 2, tzinfo=UTC),
            semantics="contract_metadata",
        )
        assert decide(GUARD, listing).reason is RefusalReason.PROTECTED_SCOPE_OVERLAP


# ----- K, L, M: unknowns, derived requests, timestamps -----


@pytest.mark.parametrize(
    ("provider", "family", "semantics"),
    [
        ("unknown_vendor", "btc_spot", "historical_observation"),
        ("coinbase", "doge_spot", "historical_observation"),
        ("coinbase", "btc_spot", "sentiment"),
        ("coinbase", "btc_spot", "prices"),
        ("kalshi", "kalshi_btc_contracts", "Current_State"),
        ("kalshi", "btc_spot", "historical_observation"),
        ("pmv_synthetic", "btc_spot", "historical_observation"),
        ("coinbase", "synthetic_fixture", "historical_observation"),
        ("coinbase", "btc_spot", "current_state"),
        ("fx_data_vendor", "gold_spot", "resolution"),
    ],
)
def test_k_unknown_or_uncatalogued_combinations_fail_closed(
    provider: str, family: str, semantics: str
) -> None:
    decision = decide(GUARD, window(provider, family, semantics=semantics))
    assert decision.reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION


def test_k_a_request_cannot_make_real_data_synthetic() -> None:
    with pytest.raises(GuardError):
        request_from_json(
            {
                "derived_inputs": [],
                "is_synthetic": True,
                "request_id": "r",
                "role": "data_scientist",
                "window": {
                    "end": "2025-01-02T00:00:00.000000Z",
                    "family": "btc_spot",
                    "identifiers": [],
                    "provider": "coinbase",
                    "semantics": "historical_observation",
                    "start": "2025-01-01T00:00:00.000000Z",
                },
            }
        )


def test_l_a_derived_feature_whose_lookback_crosses_the_protected_window_is_refused() -> None:
    target = window(start=START - timedelta(days=30), end=START - timedelta(days=2))
    lookback = window(start=START - timedelta(days=2), end=START + timedelta(hours=6))
    decision = decide(GUARD, target, lookback)
    assert decision.reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    assert decide(
        GUARD, target, window(start=START - timedelta(days=40), end=START - timedelta(days=30))
    ).allowed


def test_m_timestamps_are_utc_half_open_and_naive_values_fail() -> None:
    with pytest.raises(GuardError, match="timezone-aware"):
        window(start=datetime(2025, 1, 1), end=datetime(2025, 1, 2))  # noqa: DTZ001 - verifies rejection
    with pytest.raises(GuardError, match="start before end"):
        window(start=START, end=START)
    eastern = timezone(timedelta(hours=-5))
    shifted = window(
        start=START.astimezone(eastern) - MARGIN - timedelta(days=1),
        end=(START - MARGIN).astimezone(eastern),
    )
    assert decide(GUARD, shifted).allowed
    with pytest.raises(GuardError, match="UTC"):
        request_from_json(
            {
                "derived_inputs": [],
                "request_id": "r",
                "role": "data_scientist",
                "window": {
                    "end": "2025-01-02T00:00:00",
                    "family": "btc_spot",
                    "identifiers": [],
                    "provider": "coinbase",
                    "semantics": "historical_observation",
                    "start": "2025-01-01T00:00:00",
                },
            }
        )


# ----- N: no protected data in logs, refusals, or exceptions -----


def test_n_refusals_and_logs_carry_no_contract_ids_or_values() -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        decision = decide(
            GUARD,
            window(
                "kalshi",
                "kalshi_btc_contracts",
                START,
                END,
                identifiers=(("kalshi_market_ticker", CONTRACT),),
            ),
        )
    finally:
        logger = logging.getLogger("pmv")
        for item in list(logger.handlers):
            logger.removeHandler(item)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    assert decision.message() == "data request req_1 refused: PROTECTED_SCOPE_OVERLAP"
    output = buffer.getvalue()
    assert CONTRACT not in output
    assert CONTRACT not in decision.message()
    record = json.loads(output.splitlines()[-1])
    assert record["fields"]["reason"] == "PROTECTED_SCOPE_OVERLAP"
    assert set(record["fields"]) == {
        "request_id",
        "role",
        "provider",
        "family",
        "semantics",
        "identifiers",
        "start",
        "end",
        "derived_inputs",
        "allowed",
        "reason",
        "scope_id",
    }
    with pytest.raises(GuardError) as raised:
        window(start=datetime(2025, 1, 1), end=datetime(2025, 1, 2))  # noqa: DTZ001 - verifies rejection
    assert "2025" not in str(raised.value)


# ----- local path guard and settings shape -----


def test_local_protected_paths_are_refused_lexically_and_through_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "pmv-protected"
    (root / "holdout").mkdir(parents=True)
    assert (
        check_path(root / "holdout" / "x.parquet", root)
        is RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    )
    assert check_path(tmp_path / "data" / ".." / "pmv-protected" / "holdout", root) is not None
    link = tmp_path / "repo-link"
    link.symlink_to(root / "holdout")
    assert check_path(link / "x.parquet", root) is RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    assert check_path(tmp_path / "development" / "x.parquet", root) is None


def test_the_committed_settings_keep_the_required_defense_in_depth(tmp_path: Path) -> None:
    assert check_config(REPO) == []
    settings = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
    (tmp_path / ".claude").mkdir()
    mutations: list[Callable[[dict[str, Any]], None]] = [
        lambda s: s["sandbox"].update(enabled=False),
        lambda s: s["sandbox"].update(failIfUnavailable=False),
        lambda s: s["sandbox"].update(allowUnsandboxedCommands=True),
        lambda s: s["sandbox"]["filesystem"].update(denyRead=[]),
        lambda s: s["permissions"]["deny"].remove("Read(~/pmv-protected/**)"),
        lambda s: s["sandbox"]["filesystem"].update(denyWrite=[]),
        lambda s: s["permissions"]["deny"].remove("Edit(~/pmv-protected/**)"),
        lambda s: s["sandbox"].update(excludedCommands=["cat"]),
        lambda s: s["sandbox"]["filesystem"].update(allowRead=["~/pmv-protected"]),
        lambda s: s["permissions"].update(allow=["Read(~/pmv-protected/**)"]),
        lambda s: s.update(permissions=[]),
        lambda s: s["sandbox"].update(filesystem="off"),
    ]
    for mutate in mutations:
        broken = json.loads(json.dumps(settings))
        mutate(broken)
        (tmp_path / ".claude" / "settings.json").write_text(json.dumps(broken), encoding="utf-8")
        assert check_config(tmp_path)
    original = settings["permissions"]["deny"][:16]
    assert original[0] == "Read(**/.env*)"
    assert "Read(~/.aws/**)" in original


def test_a_local_settings_file_may_not_reopen_the_protected_location(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_bytes(
        (REPO / ".claude" / "settings.json").read_bytes()
    )
    assert check_config(tmp_path) == []
    local = tmp_path / ".claude" / "settings.local.json"
    for override in (
        {"sandbox": {"enabled": False}},
        {"permissions": {"allow": ["Read(~/pmv-protected/**)"]}},
    ):
        local.write_text(json.dumps(override), encoding="utf-8")
        assert check_config(tmp_path)
    local.write_text("not json", encoding="utf-8")
    assert check_config(tmp_path)
    local.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
    assert check_config(tmp_path) == []


def test_logs_never_echo_an_uncatalogued_provider_or_family() -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    try:
        decision = decide(GUARD, window(CONTRACT, "SYN-GOLD-PROTECTED-1"))
    finally:
        logger = logging.getLogger("pmv")
        for item in list(logger.handlers):
            logger.removeHandler(item)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    assert decision.reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    output = buffer.getvalue()
    assert CONTRACT not in output
    assert "SYN-GOLD-PROTECTED-1" not in output
    record = json.loads(output.splitlines()[-1])
    assert record["fields"]["provider"] == "<uncatalogued>"


# ----- B-1: only a valid COMMITTED registry declares a scope -----

SPLIT = b"synthetic split definition\n"
SPLIT_DEFINITION = {"path": "research/splits/split_a.yaml", "sha256": sha256_hex(SPLIT)}


def _git(repo: Path, *arguments: str) -> None:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Owner",
        "GIT_AUTHOR_EMAIL": "owner@example.invalid",
        "GIT_COMMITTER_NAME": "Owner",
        "GIT_COMMITTER_EMAIL": "owner@example.invalid",
    }
    subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(repo), "-c", "commit.gpgsign=false", *arguments],
        env=environment,
        capture_output=True,
        check=True,
    )


def _registry_bytes(*scopes: dict[str, Any]) -> bytes:
    return canonical_line(
        {"schema": "pmv.protected_scope_registry", "schema_version": 1, "scopes": list(scopes)}
    )


def _repo(tmp_path: Path, *committed: dict[str, Any], split: bool = True) -> Path:
    """A repository whose committed registry holds ``committed`` (and the split file)."""
    repo = tmp_path / "repo"
    (repo / "research" / "protected_scopes").mkdir(parents=True)
    if split:
        (repo / "research" / "splits").mkdir()
        (repo / "research" / "splits" / "split_a.yaml").write_bytes(SPLIT)
    (repo / REGISTRY_PATH).write_bytes(_registry_bytes(*committed))
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "registry")
    return repo


VALID = scope(split_definition=SPLIT_DEFINITION)
JUNK = scope(
    contracts=[],
    venues=[],
    holdout_id=None,
    protected_interval={
        "end": "2099-01-01T00:00:01.000000Z",
        "start": "2099-01-01T00:00:00.000000Z",
    },
    split_definition={"path": "research/splits/split_a.yaml", "sha256": "0" * 64},
)
HISTORY_2025 = window()


def test_b1_an_empty_committed_registry_refuses_real_data(tmp_path: Path) -> None:
    guard = Guard.from_repo(_repo(tmp_path))
    assert decide(guard, HISTORY_2025).reason is RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    assert decide(guard, SYNTHETIC).allowed


@pytest.mark.parametrize("first", [JUNK, VALID])
def test_b1_an_uncommitted_first_scope_never_authorizes_real_data(
    tmp_path: Path, first: dict[str, Any]
) -> None:
    repo = _repo(tmp_path)
    (repo / REGISTRY_PATH).write_bytes(_registry_bytes(first))
    guard = Guard.from_repo(repo)
    for target in (
        HISTORY_2025,
        window("kalshi", "kalshi_btc_contracts", semantics="settlement"),
        window("polymarket", "polymarket_btc_markets", semantics="discovery"),
    ):
        assert decide(guard, target).reason is RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    assert decide(guard, SYNTHETIC).allowed


def test_b1_a_malformed_first_scope_refuses_real_data(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    broken = dict(VALID, margin_seconds=None)
    (repo / REGISTRY_PATH).write_bytes(_registry_bytes(broken))
    guard = Guard.from_repo(repo)
    assert decide(guard, HISTORY_2025).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    assert decide(guard, SYNTHETIC).allowed


def test_b1_a_committed_scope_with_a_placeholder_split_hash_refuses_real_data(
    tmp_path: Path,
) -> None:
    guard = Guard.from_repo(_repo(tmp_path, JUNK))
    assert decide(guard, HISTORY_2025).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    missing = Guard.from_repo(_repo(tmp_path / "other", VALID, split=False))
    assert decide(missing, HISTORY_2025).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION


def test_b1_a_committed_valid_scope_applies_the_normal_rules(tmp_path: Path) -> None:
    guard = Guard.from_repo(_repo(tmp_path, VALID))
    assert decide(guard, HISTORY_2025).allowed
    february = window(start=START + timedelta(days=3), end=START + timedelta(days=4))
    assert decide(guard, february).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


def test_b1_uncommitted_edits_refuse_and_uncommitted_appends_only_add_refusals(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path, VALID)
    registry_file = repo / REGISTRY_PATH
    february = window(start=START + timedelta(days=3), end=START + timedelta(days=4))
    narrowed = dict(
        VALID,
        protected_interval={
            "end": "2026-02-01T00:00:01.000000Z",
            "start": "2026-02-01T00:00:00.000000Z",
        },
    )
    registry_file.write_bytes(_registry_bytes(narrowed))
    guard = Guard.from_repo(repo)
    assert decide(guard, february).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    assert decide(guard, HISTORY_2025).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    assert decide(guard, SYNTHETIC).allowed
    gold_2025 = window("lbma", "gold_reference_price")
    assert (
        decide(Guard.from_repo(repo), gold_2025).reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    )
    registry_file.write_bytes(_registry_bytes(VALID, GOLD))
    appended = Guard.from_repo(repo)
    assert decide(appended, february).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    gold_feb = window(
        "lbma", "gold_reference_price", START + timedelta(days=3), START + timedelta(days=4)
    )
    assert decide(appended, gold_feb).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    assert decide(appended, gold_2025).allowed


def test_a_directory_that_is_not_a_repository_refuses_real_data(tmp_path: Path) -> None:
    (tmp_path / "research" / "protected_scopes").mkdir(parents=True)
    (tmp_path / REGISTRY_PATH).write_bytes(_registry_bytes())
    assert decide(Guard.from_repo(tmp_path), window()).reason is (
        RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    )


# ----- B-2: temporary fail-closed rule for non-historical semantics -----

OLD = (datetime(2025, 6, 1, tzinfo=UTC), datetime(2025, 6, 2, tzinfo=UTC))
FEB = (START + timedelta(days=4), START + timedelta(days=5))
OVERLAP = RefusalReason.PROTECTED_SCOPE_OVERLAP
UNKNOWN = RefusalReason.UNKNOWN_SCOPE_INTERSECTION
# Protects listed contracts only (no venue-wide period protection).
CONTRACTS_ONLY = Guard(registry(scope(venues=[])))
NONE_LISTED = Guard(registry(scope(contracts=[], venues=[])))
NON_HISTORICAL = [item.value for item in Semantics if item is not Semantics.HISTORICAL_OBSERVATION]


def kalshi(
    semantics: str,
    *identifiers: tuple[str, str],
    guard: Guard = GUARD,
    when: tuple[datetime, datetime] = OLD,
    family: str = "kalshi_btc_contracts",
) -> Any:
    return decide(guard, window("kalshi", family, *when, semantics, identifiers))


def polymarket(
    semantics: str,
    *identifiers: tuple[str, str],
    guard: Guard = GUARD,
    when: tuple[datetime, datetime] = OLD,
) -> Any:
    target = window("polymarket", "polymarket_btc_markets", *when, semantics, identifiers)
    return decide(guard, target)


def test_b2_bulk_polymarket_btc_settlement_in_the_protected_interval_is_refused() -> None:
    for guard in (GUARD, CONTRACTS_ONLY, NONE_LISTED):
        assert not polymarket("settlement", guard=guard, when=FEB).allowed
    assert polymarket("settlement", guard=NONE_LISTED, when=FEB).reason is UNKNOWN


def test_b2_resolution_of_an_unlisted_same_family_market_is_refused() -> None:
    unlisted = ("polymarket_condition_id", "0x" + "e5" * 32)
    for guard in (GUARD, CONTRACTS_ONLY, NONE_LISTED):
        assert polymarket("resolution", unlisted, guard=guard, when=FEB).reason is UNKNOWN
    unlisted_kalshi = ("kalshi_market_ticker", "SYNBTC-26FEB05-T9")
    assert kalshi("settlement", unlisted_kalshi, guard=CONTRACTS_ONLY).reason is UNKNOWN


@pytest.mark.parametrize("semantics", NON_HISTORICAL)
@pytest.mark.parametrize(
    "when", [OLD, FEB, (datetime(2031, 1, 1, tzinfo=UTC), datetime(2031, 1, 2, tzinfo=UTC))]
)
def test_b2_non_historical_requests_to_a_protected_asset_venue_are_refused_whatever_the_time(
    semantics: str, when: tuple[datetime, datetime]
) -> None:
    unrelated = ("polymarket_token_id", "999")
    assert polymarket(semantics, unrelated, guard=NONE_LISTED, when=when).reason is UNKNOWN
    # A mislabelled family on the same venue does not escape: the rule is per provider.
    gold_label = kalshi(
        semantics,
        ("kalshi_market_ticker", "SYNBTC-X"),
        guard=NONE_LISTED,
        when=when,
        family="kalshi_gold_contracts",
    )
    assert gold_label.reason is UNKNOWN


def test_b2_applies_per_provider_not_per_asserted_family() -> None:
    gold_only = Guard(registry(GOLD))
    # Kalshi and Polymarket both list gold contracts, so a "BTC" label does not escape.
    for provider, family, identifier in (
        ("kalshi", "kalshi_btc_contracts", ("kalshi_market_ticker", "SYNBTC-X")),
        ("polymarket", "polymarket_btc_markets", ("polymarket_token_id", "999")),
    ):
        target = window(provider, family, *OLD, "current_state", (identifier,))
        assert decide(gold_only, target).reason is UNKNOWN
        history = window(provider, family, *OLD, "historical_observation", (identifier,))
        assert decide(gold_only, history).allowed


# ----- B-3: a protected contract is refused under every semantics at every time -----

PERIODS = {
    "before": OLD,
    "during": FEB,
    "after": (END + timedelta(days=5), END + timedelta(days=6)),
    "long_after": (datetime(2030, 1, 1, tzinfo=UTC), datetime(2030, 1, 2, tzinfo=UTC)),
}


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize("semantics", [item.value for item in Semantics])
@pytest.mark.parametrize("guard", [GUARD, CONTRACTS_ONLY], ids=["venue_wide", "contracts_only"])
def test_b3_the_protected_kalshi_market_is_refused_before_during_and_after(
    period: str, semantics: str, guard: Guard
) -> None:
    named = ("kalshi_market_ticker", CONTRACT)
    assert kalshi(semantics, named, guard=guard, when=PERIODS[period]).reason is OVERLAP


@pytest.mark.parametrize("period", PERIODS)
@pytest.mark.parametrize(
    "identifier",
    [
        ("polymarket_condition_id", CONDITION),
        ("polymarket_token_id", "702"),
        ("polymarket_token_id", "703"),
    ],
)
def test_b3_the_protected_polymarket_condition_and_tokens_are_refused_before_during_and_after(
    period: str, identifier: tuple[str, str]
) -> None:
    for semantics in Semantics:
        decision = polymarket(
            semantics.value, identifier, guard=CONTRACTS_ONLY, when=PERIODS[period]
        )
        assert decision.reason is OVERLAP


def test_b3_post_interval_history_of_the_protected_kalshi_market_is_refused() -> None:
    after = (datetime(2026, 3, 6, tzinfo=UTC), datetime(2026, 3, 7, tzinfo=UTC))
    named = ("kalshi_market_ticker", CONTRACT)
    for guard in (GUARD, CONTRACTS_ONLY):
        assert kalshi("historical_observation", named, guard=guard, when=after).reason is OVERLAP


def test_b3_bulk_history_on_a_venue_with_a_protected_contract_is_refused_at_any_time() -> None:
    assert polymarket("historical_observation", guard=CONTRACTS_ONLY).reason is OVERLAP
    assert kalshi("historical_observation", guard=CONTRACTS_ONLY).reason is OVERLAP
    assert polymarket("historical_observation", guard=NONE_LISTED).allowed


def test_b3_other_contracts_keep_the_normal_temporal_rules() -> None:
    other = ("polymarket_token_id", "999")
    assert polymarket("historical_observation", other, guard=CONTRACTS_ONLY).allowed
    feb = polymarket("historical_observation", other, guard=CONTRACTS_ONLY, when=FEB)
    assert feb.reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


# ----- identity: aliases, explicit relationships, unknown forms -----


@pytest.mark.parametrize("spelling", [CONTRACT, CONTRACT.lower(), "SynBtc-26Feb01-T1"])
def test_a_protected_kalshi_market_ticker_is_refused_in_any_ascii_spelling(spelling: str) -> None:
    assert kalshi("historical_observation", ("kalshi_market_ticker", spelling)).reason is OVERLAP


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("kalshi_event_ticker", "SYNBTC-26FEB01"),
        ("kalshi_series_ticker", "SYNBTC"),
        ("kalshi_series_ticker", "synbtc"),
    ],
)
def test_the_protected_kalshi_market_through_its_event_or_series_is_refused(
    kind: str, value: str
) -> None:
    assert kalshi("historical_observation", (kind, value), guard=CONTRACTS_ONLY).reason is OVERLAP
    assert kalshi("discovery", (kind, value), guard=CONTRACTS_ONLY).reason is OVERLAP


def test_relationships_are_explicit_never_inferred_from_ticker_prefixes() -> None:
    # A prefix of the protected ticker that is not its recorded event or series is a
    # different selector; with explicit records it is provably not the protected market.
    for kind, value in (
        ("kalshi_event_ticker", "SYNBTC-26FEB01-T"),
        ("kalshi_series_ticker", "SYNBTC-26FEB01"),
        ("kalshi_event_ticker", "SYNETH-26FEB01"),
    ):
        assert kalshi("historical_observation", (kind, value), guard=CONTRACTS_ONLY).allowed
        assert kalshi("discovery", (kind, value), guard=CONTRACTS_ONLY).reason is UNKNOWN


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("polymarket_condition_id", CONDITION),
        ("polymarket_conditionId", CONDITION.upper().replace("0X", "0x")),
        ("polymarket_token_id", "702"),
        ("polymarket_token_id", "0703"),
        ("polymarket_market_id", "701"),
        ("polymarket_slug", "Syn-BTC-Up-Feb"),
        ("polymarket_event_id", "700"),
    ],
)
def test_every_known_polymarket_alias_of_a_protected_market_is_refused(
    kind: str, value: str
) -> None:
    assert polymarket("historical_observation", (kind, value)).reason is OVERLAP
    assert polymarket("current_state", (kind, value)).reason is OVERLAP


def test_unrelated_polymarket_identifiers_are_historical_only() -> None:
    for kind, value in (
        ("polymarket_condition_id", "0x" + "d2" * 32),
        ("polymarket_token_id", "999"),
        ("polymarket_market_id", "998"),
        ("polymarket_event_id", "997"),
        ("polymarket_slug", "syn-eth-up-feb"),
    ):
        assert polymarket("historical_observation", (kind, value), guard=CONTRACTS_ONLY).allowed
        assert polymarket("current_state", (kind, value), guard=CONTRACTS_ONLY).reason is UNKNOWN


def test_a_missing_identity_relation_fails_closed() -> None:
    no_slugs = Guard(registry(scope(venues=[], contracts=[dict(POLYMARKET_BTC, slugs=[])])))
    decision = polymarket(
        "historical_observation", ("polymarket_slug", "syn-eth-up"), guard=no_slugs
    )
    assert decision.reason is UNKNOWN
    named = polymarket(
        "historical_observation",
        ("polymarket_slug", "x"),
        ("polymarket_token_id", "702"),
        guard=no_slugs,
    )
    assert named.reason is OVERLAP


@pytest.mark.parametrize(
    ("family", "kind", "value"),
    [
        ("kalshi_btc_contracts", "kalshi_ticker", CONTRACT),
        ("kalshi_btc_contracts", "kalshi_market_ticker", CONTRACT + " "),
        ("kalshi_btc_contracts", "kalshi_market_ticker", " " + CONTRACT),
        ("kalshi_btc_contracts", "kalshi_market_ticker", "SYNBTC-26FEB01-T\u0131"),
        ("kalshi_btc_contracts", "kalsh\u0131_market_ticker", CONTRACT),
        ("kalshi_btc_contracts", "polymarket_condition_id", CONDITION),
        ("polymarket_btc_markets", "polymarket_condition_id", "0xZZ"),
        ("polymarket_btc_markets", "polymarket_question_id", "1"),
        ("polymarket_btc_markets", "polymarket_token_id", "0x2be"),
        ("polymarket_btc_markets", "polymarket_token_id", "\u0667\u0660\u0662"),
        ("polymarket_btc_markets", "polymarket_slug", "syn-btc-\u212a"),
    ],
)
def test_unknown_non_ascii_or_malformed_identifiers_fail_closed(
    family: str, kind: str, value: str
) -> None:
    provider = family.split("_")[0]
    for guard in (GUARD, NONE_LISTED):
        target = window(provider, family, *OLD, "historical_observation", ((kind, value),))
        assert decide(guard, target).reason is UNKNOWN


def test_identifiers_on_a_non_venue_family_fail_closed() -> None:
    target = window("coinbase", "btc_spot", *OLD, identifiers=(("kalshi_market_ticker", CONTRACT),))
    assert decide(GUARD, target).reason is UNKNOWN


# ----- information semantics -----


@pytest.mark.parametrize("provider", ["coinbase", "lbma"])
def test_underlying_history_follows_the_protected_interval(provider: str) -> None:
    family = {"coinbase": "btc_spot", "lbma": "gold_reference_price"}[provider]
    assert decide(GUARD, window(provider, family, *OLD)).allowed
    overlapping = window(provider, family, START + timedelta(days=1), END + timedelta(days=1))
    assert decide(GUARD, overlapping).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


@pytest.mark.parametrize(
    "semantics", ["prices", "trades", "historical", "HISTORICAL OBSERVATION", ""]
)
def test_unknown_information_semantics_fail_closed(semantics: str) -> None:
    assert polymarket(semantics).reason is UNKNOWN
    assert decide(GUARD, window(semantics=semantics)).reason is UNKNOWN


def test_requests_round_trip_from_json_with_semantics_and_identifiers() -> None:
    body: dict[str, Any] = {
        "derived_inputs": [],
        "request_id": "r",
        "role": "data_scientist",
        "window": {
            "end": "2025-06-02T00:00:00.000000Z",
            "family": "polymarket_btc_markets",
            "identifiers": [{"kind": "polymarket_token_id", "value": "702"}],
            "provider": "polymarket",
            "semantics": "historical_observation",
            "start": "2025-06-01T00:00:00.000000Z",
        },
    }
    assert GUARD.decide(request_from_json(body)).reason is OVERLAP
    body["window"]["identifiers"] = [{"kind": "polymarket_token_id", "value": 702}]
    with pytest.raises(GuardError):
        request_from_json(body)


# ----- open-ended (prospective) scopes -----

OPEN_START = datetime(2026, 6, 1, tzinfo=UTC)
OPEN = Guard(
    registry(
        scope(
            contracts=[],
            protected_interval={"end": None, "start": "2026-06-01T00:00:00.000000Z"},
        )
    )
)


def _btc(
    start: datetime, end: datetime, provider: str = "coinbase", family: str = "btc_spot"
) -> Window:
    return window(provider, family, start, end)


def test_open_ended_scope_allows_only_history_ending_before_start_minus_margin() -> None:
    boundary = OPEN_START - MARGIN
    assert decide(OPEN, _btc(boundary - timedelta(days=30), boundary)).allowed
    one_microsecond = _btc(boundary - timedelta(days=1), boundary + timedelta(microseconds=1))
    assert decide(OPEN, one_microsecond).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


@pytest.mark.parametrize(
    "offset",
    [timedelta(0), timedelta(seconds=1), timedelta(days=400), timedelta(days=365 * 50)],
)
def test_open_ended_scope_protects_the_start_and_everything_after(offset: timedelta) -> None:
    at = OPEN_START + offset
    decision = decide(OPEN, _btc(at, at + timedelta(minutes=1)))
    assert decision.reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    assert decision.scope_id == "scope_btc"


@pytest.mark.parametrize(
    ("provider", "family"),
    [
        ("binance", "btc_perpetual"),
        ("cme", "btc_futures"),
        ("cf_benchmarks", "btc_reference_index"),
    ],
)
def test_open_ended_scope_protects_equivalent_observables(provider: str, family: str) -> None:
    later = OPEN_START + timedelta(days=90)
    target = _btc(later, later + timedelta(hours=1), provider, family)
    assert decide(OPEN, target).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    kalshi_later = window("kalshi", "kalshi_btc_contracts", later, later + timedelta(hours=1))
    assert decide(OPEN, kalshi_later).reason is OVERLAP


def test_open_ended_scope_refuses_a_lookback_that_crosses_the_start() -> None:
    target = _btc(OPEN_START - timedelta(days=30), OPEN_START - timedelta(days=2))
    lookback = _btc(OPEN_START - timedelta(days=2), OPEN_START + timedelta(hours=1))
    decision = decide(OPEN, target, lookback)
    assert decision.reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE
    assert decide(OPEN, target).allowed


@pytest.mark.parametrize("semantics", NON_HISTORICAL)
def test_open_ended_scope_refuses_sensitive_non_historical_requests(semantics: str) -> None:
    unrelated = ("polymarket_token_id", "999")
    old = polymarket(semantics, unrelated, guard=OPEN, when=OLD)
    assert old.reason is UNKNOWN
    assert decide(OPEN, window("coinbase", "btc_spot", *OLD, semantics)).reason is UNKNOWN


# ----- M-1: pending scopes combine conservatively with the committed floor -----

NO_SLUGS = scope(venues=[], contracts=[dict(POLYMARKET_BTC, slugs=[])])
SLUGS_FILLED = scope(
    scope_id="scope_btc_2",
    venues=[],
    contracts=[dict(POLYMARKET_BTC, slugs=["syn-btc-up-feb"])],
    supersedes={"scope_id": "scope_btc", "scope_sha256": sha256_hex(canonical_json(NO_SLUGS))},
)
OTHER_SLUG = ("polymarket_slug", "syn-eth-up-feb")


def test_m1_committed_refuse_and_pending_allow_is_refuse() -> None:
    committed = registry(NO_SLUGS)
    pending = registry(NO_SLUGS, SLUGS_FILLED)
    assert polymarket("historical_observation", OTHER_SLUG, guard=Guard(pending)).allowed
    combined = Guard(committed, pending)
    assert polymarket("historical_observation", OTHER_SLUG, guard=combined).reason is UNKNOWN


def test_m1_committed_allow_and_pending_refuse_is_refuse() -> None:
    gold_feb = window("lbma", "gold_reference_price", *FEB)
    assert decide(Guard(registry(scope())), gold_feb).allowed
    combined = Guard(registry(scope()), registry(scope(), GOLD))
    assert decide(combined, gold_feb).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


def test_m1_committed_refuse_and_pending_refuse_is_refuse() -> None:
    btc_feb = window(*("coinbase", "btc_spot"), *FEB)
    combined = Guard(registry(scope()), registry(scope(), GOLD))
    assert decide(combined, btc_feb).reason is RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE


def test_m1_an_uncommitted_first_scope_cannot_authorize_real_data() -> None:
    combined = Guard(registry(), registry(scope()))
    assert decide(combined, window()).reason is RefusalReason.PROTECTED_SCOPE_NOT_DECLARED
    assert decide(combined, SYNTHETIC).allowed


def test_m1_an_invalid_pending_registry_cannot_create_an_allow(tmp_path: Path) -> None:
    repo = _repo(tmp_path, VALID)
    assert decide(Guard.from_repo(repo), HISTORY_2025).allowed
    for broken in (b"not json\n", _registry_bytes(dict(VALID, margin_seconds=-1))):
        (repo / REGISTRY_PATH).write_bytes(broken)
        refused = decide(Guard.from_repo(repo), HISTORY_2025)
        assert refused.reason is RefusalReason.UNKNOWN_SCOPE_INTERSECTION


def test_m1_the_original_reproduction_through_the_repository(tmp_path: Path) -> None:
    committed = dict(NO_SLUGS, split_definition=SPLIT_DEFINITION)
    filled = dict(
        SLUGS_FILLED,
        split_definition=SPLIT_DEFINITION,
        supersedes={"scope_id": "scope_btc", "scope_sha256": sha256_hex(canonical_json(committed))},
    )
    repo = _repo(tmp_path, committed)
    request = polymarket("historical_observation", OTHER_SLUG, guard=Guard.from_repo(repo))
    assert request.reason is UNKNOWN
    (repo / REGISTRY_PATH).write_bytes(_registry_bytes(committed, filled))
    after = polymarket("historical_observation", OTHER_SLUG, guard=Guard.from_repo(repo))
    assert after.reason is UNKNOWN


# ----- L-1: mutation survivors -----


def test_l1_non_historical_requests_on_a_non_venue_family_fail_closed_even_off_asset() -> None:
    # The provider serves no protected BTC family, so only this rule refuses it.
    silver_now = window("fx_data_vendor", "silver_spot", *OLD, "current_state")
    assert decide(Guard(registry(scope())), silver_now).reason is UNKNOWN
