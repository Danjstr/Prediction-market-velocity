"""Tests for the protected-scope registry, widen-only supersession, and registry history."""

import copy
import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from pmv.integrity import canonical_json, canonical_line, sha256_hex
from pmv.protected_scope import (
    IDENTIFIER_RULES,
    REGISTRY_PATH,
    IdentifierKind,
    Observable,
    ProtectedScopeError,
    Venue,
    empty_registry_bytes,
    normalize_identifier,
    parse_identifier_kind,
    parse_registry,
    validate_scope,
    verify_committed_registry,
    verify_registry_history,
)

REPO = Path(__file__).resolve().parents[2]
KALSHI_CONTRACT: dict[str, Any] = {
    "event_ticker": "SYNBTC-26FEB01",
    "market_ticker": "SYNBTC-26FEB01-T1",
    "series_ticker": "SYNBTC",
    "venue": "kalshi",
}


def scope(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "attestation": {"attested": True, "role": "project_owner"},
        "contracts": [copy.deepcopy(KALSHI_CONTRACT)],
        "cycle_id": "cycle_a",
        "declared_at": "2026-01-01T00:00:00.000000Z",
        "holdout_id": "holdout_a",
        "margin_seconds": 3600,
        "observables": [{"observable": "btc_usd_price", "resolution_lag_seconds": 60}],
        "protected_interval": {
            "end": "2026-03-01T00:00:00.000000Z",
            "start": "2026-02-01T00:00:00.000000Z",
        },
        "scope_id": "scope_a",
        "split_definition": {"path": "research/splits/split_a.yaml", "sha256": "1" * 64},
        "supersedes": None,
        "venues": ["kalshi"],
    }
    base.update(changes)
    return base


def registry(*scopes: dict[str, Any]) -> bytes:
    return canonical_line(
        {"schema": "pmv.protected_scope_registry", "schema_version": 1, "scopes": list(scopes)}
    )


def successor(prior: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return scope(
        scope_id="scope_b",
        supersedes={
            "scope_id": prior["scope_id"],
            "scope_sha256": sha256_hex(canonical_json(prior)),
        },
        **changes,
    )


def test_the_real_registry_and_the_synthetic_example_are_valid() -> None:
    real = parse_registry((REPO / REGISTRY_PATH).read_bytes())
    assert real.scopes == ()
    assert (REPO / REGISTRY_PATH).read_bytes() == empty_registry_bytes()
    example = parse_registry((REPO / "research" / "protected_scope.example.json").read_bytes())
    assert [item.scope_id for item in example.active] == ["example_scope"]


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.pop("margin_seconds"),
        lambda d: d.update(margin_seconds=True),
        lambda d: d.update(margin_seconds=-1),
        lambda d: d.update(margin_seconds=None),
        lambda d: d.update(extra=1),
        lambda d: d.update(observables=[]),
        lambda d: d["observables"][0].update(resolution_lag_seconds=None),
        lambda d: d["observables"][0].update(observable="eth_usd_price"),
        lambda d: d.update(split_definition=None),
        lambda d: d["split_definition"].update(path="../split.yaml"),
        lambda d: d["protected_interval"].update(end="2026-01-01T00:00:00.000000Z"),
        lambda d: d["protected_interval"].update(start="2026-02-01T00:00:00"),
        lambda d: d.update(attestation={"attested": False, "role": "project_owner"}),
        lambda d: d.update(venues=["polymarket", "kalshi"]),
        lambda d: d["contracts"][0].update(market_ticker="HAS SPACE"),
        lambda d: d["contracts"][0].update(market_ticker="synbtc-26feb01-t1"),
        lambda d: d["contracts"][0].update(event_ticker=["SYNBTC-26FEB01"]),
        lambda d: d["contracts"][0].update(event_ticker="SYNBTC-26FEB01 "),
        lambda d: d["contracts"][0].update(event_ticker="SYNBTC-26FEB0\u0130"),
        lambda d: d["contracts"][0].pop("series_ticker"),
        lambda d: d["contracts"][0].update(condition_id="0x" + "a" * 64),
        lambda d: d.update(
            contracts=[KALSHI_CONTRACT, dict(KALSHI_CONTRACT, event_ticker="SYNBTC-26FEB02")]
        ),
        lambda d: d.update(outcome="YES"),
    ],
)
def test_scopes_are_closed_metadata_with_required_margins(
    change: Callable[[dict[str, Any]], None],
) -> None:
    candidate = scope()
    change(candidate)
    with pytest.raises(ProtectedScopeError):
        validate_scope(candidate)


def test_an_open_ended_prospective_scope_is_valid() -> None:
    open_ended = scope()
    open_ended["protected_interval"]["end"] = None
    assert validate_scope(open_ended).end is None


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["protected_interval"].update(start="2026-02-02T00:00:00.000000Z"),
        lambda d: d["protected_interval"].update(end="2026-02-28T00:00:00.000000Z"),
        lambda d: d.update(margin_seconds=60),
        lambda d: d["observables"][0].update(resolution_lag_seconds=0),
        lambda d: d.update(contracts=[]),
        lambda d: d.update(venues=[]),
        lambda d: d.update(cycle_id="cycle_b"),
    ],
)
def test_a_successor_may_never_shrink_its_predecessor(
    change: Callable[[dict[str, Any]], None],
) -> None:
    prior = scope()
    shrunk = successor(prior)
    change(shrunk)
    with pytest.raises(ProtectedScopeError, match="only widen"):
        parse_registry(registry(prior, shrunk))


def test_widening_supersession_forks_and_bad_references() -> None:
    prior = scope()
    wider = successor(
        prior,
        margin_seconds=7200,
        protected_interval={"end": None, "start": "2026-01-15T00:00:00.000000Z"},
        venues=["kalshi", "polymarket"],
    )
    parsed = parse_registry(registry(prior, wider))
    assert [item.scope_id for item in parsed.active] == ["scope_b"]
    fork = copy.deepcopy(wider)
    fork["scope_id"] = "scope_c"
    with pytest.raises(ProtectedScopeError, match="fork"):
        parse_registry(registry(prior, wider, fork))
    bad = successor(prior)
    bad["supersedes"]["scope_sha256"] = "0" * 64
    with pytest.raises(ProtectedScopeError, match="unknown or changed"):
        parse_registry(registry(prior, bad))
    with pytest.raises(ProtectedScopeError, match="share a scope_id"):
        parse_registry(registry(prior, prior))


def test_registries_must_be_canonical_and_versioned() -> None:
    with pytest.raises(ProtectedScopeError, match="canonical"):
        parse_registry(
            b'{"scopes": [], "schema": "pmv.protected_scope_registry", "schema_version": 1}\n'
        )
    with pytest.raises(ProtectedScopeError, match="not supported"):
        parse_registry(
            canonical_line(
                {"schema": "pmv.protected_scope_registry", "schema_version": True, "scopes": []}
            )
        )


# ----- Git history -----


def git(repo: Path, *arguments: str) -> bytes:
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
    return subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(repo), "-c", "commit.gpgsign=false", *arguments],
        env=environment,
        capture_output=True,
        check=True,
    ).stdout


def commit(repo: Path, message: str = "change") -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "research" / "protected_scopes").mkdir(parents=True)
    (root / REGISTRY_PATH).write_bytes(empty_registry_bytes())
    git(root, "init", "-q", "-b", "main")
    commit(root, "empty registry")
    return root


def write_registry(repo: Path, *scopes: dict[str, Any]) -> None:
    (repo / REGISTRY_PATH).write_bytes(registry(*scopes))


def test_history_accepts_appends_and_widening(repo: Path) -> None:
    prior = scope()
    write_registry(repo, prior)
    commit(repo, "declare scope")
    write_registry(repo, prior, successor(prior, margin_seconds=7200))
    assert len(verify_registry_history(repo).scopes) == 2
    commit(repo, "widen")
    assert len(verify_registry_history(repo).active) == 1


def test_history_rejects_edits_removals_and_deletion(repo: Path) -> None:
    prior = scope()
    write_registry(repo, prior)
    commit(repo, "declare scope")
    write_registry(repo)
    with pytest.raises(ProtectedScopeError, match="edited, removed, or replaced"):
        verify_registry_history(repo)
    commit(repo, "remove scope")
    write_registry(repo, prior)
    with pytest.raises(ProtectedScopeError, match="edited, removed, or replaced"):
        verify_registry_history(repo)


def test_history_rejects_a_deleted_registry_file(repo: Path) -> None:
    data = (repo / REGISTRY_PATH).read_bytes()
    (repo / REGISTRY_PATH).unlink()
    commit(repo, "delete")
    (repo / REGISTRY_PATH).write_bytes(data)
    commit(repo, "restore")
    with pytest.raises(ProtectedScopeError, match="removed the protected-scope registry"):
        verify_registry_history(repo)


def test_history_rejects_an_edit_hidden_in_a_merge(repo: Path) -> None:
    prior = scope()
    write_registry(repo, prior)
    commit(repo, "declare scope")
    git(repo, "checkout", "-q", "-b", "side")
    git(repo, "commit", "-q", "--allow-empty", "-m", "side")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
    shrunk = copy.deepcopy(prior)
    shrunk["margin_seconds"] = 0
    write_registry(repo, shrunk)
    commit(repo, "evil merge")
    write_registry(repo, prior)
    commit(repo, "restore")
    with pytest.raises(ProtectedScopeError, match="edited, removed, or replaced"):
        verify_registry_history(repo)


def test_history_ignores_replace_refs_and_refuses_grafts_and_shallow_clones(
    repo: Path, tmp_path: Path
) -> None:
    prior = scope()
    write_registry(repo, prior)
    commit(repo, "declare scope")
    write_registry(repo)
    commit(repo, "remove scope")
    git(repo, "replace", "--graft", "HEAD")
    with pytest.raises(ProtectedScopeError):
        verify_registry_history(repo)
    git(repo, "replace", "-d", git(repo, "rev-parse", "HEAD").decode().strip())
    grafts = repo / ".git" / "info" / "grafts"
    grafts.parent.mkdir(exist_ok=True)
    grafts.write_text(git(repo, "rev-parse", "HEAD").decode(), encoding="ascii")
    with pytest.raises(ProtectedScopeError, match="grafts"):
        verify_registry_history(repo)
    grafts.unlink()
    shallow = tmp_path / "shallow"
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow))
    with pytest.raises(ProtectedScopeError, match="shallow"):
        verify_registry_history(shallow)


def test_a_missing_or_symlinked_registry_is_rejected(repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.json"
    target.write_bytes(empty_registry_bytes())
    (repo / REGISTRY_PATH).unlink()
    with pytest.raises(ProtectedScopeError, match="missing or not a plain file"):
        verify_registry_history(repo)
    (repo / REGISTRY_PATH).symlink_to(target)
    with pytest.raises(ProtectedScopeError, match="missing or not a plain file"):
        verify_registry_history(repo)


def test_the_schema_document_matches_the_python_validator() -> None:
    schema = json.loads((REPO / "schemas" / "protected_scope_v1.json").read_text(encoding="utf-8"))
    definitions = schema["$defs"]
    valid = scope()
    properties = definitions["scope"]["properties"]
    assert set(definitions["scope"]["required"]) == set(valid) == set(properties)
    assert set(definitions["venue"]["enum"]) == {item.value for item in Venue}
    assert set(definitions["observable"]["enum"]) == {item.value for item in Observable}
    for key in ("attestation", "protected_interval", "split_definition"):
        assert set(properties[key]["required"]) == set(valid[key])
    assert set(properties["observables"]["items"]["required"]) == set(valid["observables"][0])
    records = {
        option["properties"]["venue"]["const"]: set(option["required"])
        for option in properties["contracts"]["items"]["oneOf"]
    }
    assert records == {
        venue.value: {
            "venue",
            *(rule.field for rule in IDENTIFIER_RULES.values() if rule.venue is venue),
        }
        for venue in Venue
    }
    assert set(schema["required"]) == {"schema", "schema_version", "scopes"}
    assert schema["properties"]["schema"]["const"] == "pmv.protected_scope_registry"


# ----- contract identity -----


POLYMARKET_CONTRACT: dict[str, Any] = {
    "condition_id": "0x" + "c1" * 32,
    "event_ids": ["700"],
    "market_id": "701",
    "slugs": ["syn-btc-up"],
    "token_ids": ["702", "703"],
    "venue": "polymarket",
}


@pytest.mark.parametrize(
    ("kind", "raw", "normalized"),
    [
        ("kalshi_market_ticker", "synbtc-26feb01-t1", "SYNBTC-26FEB01-T1"),
        ("KALSHI_EVENT_TICKER", "SynBtc-26Feb01", "SYNBTC-26FEB01"),
        ("polymarket_conditionId", "0x" + "C1" * 32, "0x" + "c1" * 32),
        ("polymarket_token_id", "000702", "702"),
        ("polymarket_slug", "Syn-BTC-Up", "syn-btc-up"),
    ],
)
def test_identifiers_normalize_to_one_spelling(kind: str, raw: str, normalized: str) -> None:
    parsed = parse_identifier_kind(kind)
    assert parsed is not None
    assert normalize_identifier(parsed, raw) == normalized


@pytest.mark.parametrize(
    ("kind", "raw"),
    [
        (IdentifierKind.KALSHI_MARKET_TICKER, "SYNBTC-26FEB01-T1 "),
        (IdentifierKind.POLYMARKET_CONDITION_ID, "0x" + "c1" * 31),
        (IdentifierKind.POLYMARKET_TOKEN_ID, "0x2be"),
        (IdentifierKind.POLYMARKET_SLUG, "syn btc"),
    ],
)
def test_unrecognized_identifier_forms_do_not_normalize(kind: IdentifierKind, raw: str) -> None:
    assert normalize_identifier(kind, raw) is None


def test_unknown_identifier_kinds_are_not_parsed() -> None:
    assert parse_identifier_kind("kalshi_ticker") is None
    assert parse_identifier_kind("polymarket_question_id") is None


def test_both_venues_validate_and_canonical_identities_are_unique() -> None:
    both = scope(contracts=sorted([KALSHI_CONTRACT, POLYMARKET_CONTRACT], key=canonical_json))
    identities = {(item.venue.value, item.canonical) for item in validate_scope(both).contracts}
    assert identities == {("kalshi", "SYNBTC-26FEB01-T1"), ("polymarket", "0x" + "c1" * 32)}


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(token_ids=[]),
        lambda d: d.update(event_ids=[]),
        lambda d: d.update(token_ids=["703", "702"]),
        lambda d: d.update(market_id=["701"]),
        lambda d: d.update(slugs="syn-btc-up"),
        lambda d: d.update(token_ids=["\u0667\u0660\u0662"]),
    ],
)
def test_polymarket_records_need_complete_event_and_token_lists(
    change: Callable[[dict[str, Any]], None],
) -> None:
    record = copy.deepcopy(POLYMARKET_CONTRACT)
    change(record)
    with pytest.raises(ProtectedScopeError):
        validate_scope(scope(contracts=[record]))
    validate_scope(scope(contracts=[dict(POLYMARKET_CONTRACT, slugs=[])]))


def test_successors_may_add_identifiers_but_never_drop_or_change_one() -> None:
    prior = scope(contracts=[POLYMARKET_CONTRACT])
    corrected = successor(
        prior,
        contracts=[
            dict(
                POLYMARKET_CONTRACT,
                slugs=["syn-btc-up", "syn-btc-up-2"],
                token_ids=["702", "703", "704"],
            )
        ],
    )
    assert len(parse_registry(registry(prior, corrected)).active) == 1
    changes: list[dict[str, Any]] = [{"token_ids": ["702"]}, {"slugs": []}, {"market_id": "799"}]
    for change in changes:
        shrunk = successor(prior, contracts=[dict(POLYMARKET_CONTRACT, **change)])
        with pytest.raises(ProtectedScopeError, match="only widen"):
            parse_registry(registry(prior, shrunk))
    moved = successor(scope(), contracts=[dict(KALSHI_CONTRACT, event_ticker="SYNBTC-26FEB02")])
    with pytest.raises(ProtectedScopeError, match="only widen"):
        parse_registry(registry(scope(), moved))


def test_identity_matching_uses_explicit_relationships_only() -> None:
    kalshi, polymarket = (
        validate_scope(scope(contracts=[record])).contracts[0]
        for record in (KALSHI_CONTRACT, dict(POLYMARKET_CONTRACT, slugs=[]))
    )
    assert kalshi.reached_by(IdentifierKind.KALSHI_EVENT_TICKER, "SYNBTC-26FEB01") is True
    assert kalshi.reached_by(IdentifierKind.KALSHI_SERIES_TICKER, "SYNBTC") is True
    # No ticker-prefix parentage: a prefix of the market ticker is not its event or series.
    assert kalshi.reached_by(IdentifierKind.KALSHI_EVENT_TICKER, "SYNBTC-26FEB01-T") is False
    assert kalshi.reached_by(IdentifierKind.KALSHI_SERIES_TICKER, "SYNBTC-26FEB01") is False
    assert kalshi.reached_by(IdentifierKind.POLYMARKET_TOKEN_ID, "702") is False
    assert polymarket.reached_by(IdentifierKind.POLYMARKET_TOKEN_ID, "703") is True
    assert polymarket.reached_by(IdentifierKind.POLYMARKET_TOKEN_ID, "704") is False
    assert polymarket.reached_by(IdentifierKind.POLYMARKET_SLUG, "anything") is None


@pytest.mark.parametrize(
    ("kind", "raw"),
    [
        (IdentifierKind.KALSHI_MARKET_TICKER, "synbtc-26feb01-t\u0131"),
        (IdentifierKind.KALSHI_SERIES_TICKER, "STRA\u00dfE"),
        (IdentifierKind.POLYMARKET_TOKEN_ID, "\u0667\u0660\u0662"),
        (IdentifierKind.POLYMARKET_SLUG, "syn-btc-\u212a"),
        (IdentifierKind.KALSHI_MARKET_TICKER, "\tSYNBTC"),
        (IdentifierKind.KALSHI_MARKET_TICKER, "SYN BTC"),
    ],
)
def test_non_ascii_and_whitespace_identifiers_are_rejected(kind: IdentifierKind, raw: str) -> None:
    assert normalize_identifier(kind, raw) is None


def test_non_ascii_kind_names_are_rejected() -> None:
    assert parse_identifier_kind("kalsh\u0131_market_ticker") is None
    assert parse_identifier_kind("KALSHI_MARKET_TICKER") is IdentifierKind.KALSHI_MARKET_TICKER


# ----- the committed registry and its split definitions -----


SPLIT = b"synthetic split definition\n"


def committed_scope(**changes: Any) -> dict[str, Any]:
    return scope(
        split_definition={"path": "research/splits/split_a.yaml", "sha256": sha256_hex(SPLIT)},
        **changes,
    )


def test_only_the_committed_registry_declares_a_scope(repo: Path) -> None:
    write_registry(repo, committed_scope())
    committed, working = verify_committed_registry(repo)
    assert committed.scopes == ()
    assert len(working.scopes) == 1
    (repo / "research" / "splits").mkdir()
    (repo / "research" / "splits" / "split_a.yaml").write_bytes(SPLIT)
    commit(repo, "declare scope with its split")
    committed, working = verify_committed_registry(repo)
    assert [item.scope_id for item in committed.active] == ["scope_a"]


def test_a_committed_scope_needs_its_split_definition_at_head(repo: Path) -> None:
    write_registry(repo, scope())
    commit(repo, "scope with a placeholder split hash")
    with pytest.raises(ProtectedScopeError, match="split definition"):
        verify_committed_registry(repo)
    (repo / "research" / "splits").mkdir()
    (repo / "research" / "splits" / "split_a.yaml").write_bytes(b"other bytes\n")
    commit(repo, "a split with different bytes")
    with pytest.raises(ProtectedScopeError, match="split definition"):
        verify_committed_registry(repo)


def test_l1_a_kind_name_with_a_unicode_lookalike_is_rejected() -> None:
    # KELVIN SIGN lower-cases to ASCII "k"; without the ASCII check it would parse.
    assert "\u212a".lower() == "k"
    assert parse_identifier_kind("\u212aALSHI_MARKET_TICKER") is None


def test_l1_a_committed_split_definition_that_is_a_symlink_is_refused(repo: Path) -> None:
    (repo / "research" / "splits").mkdir()
    (repo / "research" / "splits" / "real.yaml").write_bytes(SPLIT)
    (repo / "research" / "splits" / "split_a.yaml").symlink_to("real.yaml")
    # Git stores a symlink's target as its blob, so match that hash: only the mode refuses it.
    link_hash = {"path": "research/splits/split_a.yaml", "sha256": sha256_hex(b"real.yaml")}
    write_registry(repo, scope(split_definition=link_hash))
    commit(repo, "scope whose split path is a symlink")
    with pytest.raises(ProtectedScopeError, match="split definition"):
        verify_committed_registry(repo)
