"""Deterministic data-access guard for the protected-information embargo (Phase 0 Step 9).

Every PROJECT market-data request (and every local path a data loader would read) is
decided here, never by agent discretion:

    agent/tool -> DataRequest -> guard -> ALLOW | REFUSE(reason)

Refusal reasons (bounded; they never carry values, labels, outcomes, contract IDs, or URLs):

- ``PROTECTED_SCOPE_NOT_DECLARED``: no real protected scope is declared yet, so no real
  market observation may reach agents (otherwise the holdout could be chosen after looking);
- ``PROTECTED_SCOPE_OVERLAP``: the request may reach a protected contract (any known alias,
  or an event, series, or bulk selector that cannot be proven to exclude it) in a way its
  information semantics forbid, or protected-period data of a protected venue's contracts;
- ``PROTECTED_EQUIVALENT_OBSERVABLE``: another source that can reconstruct a protected
  observable (for example BTC spot for a protected BTC contract) during the protected window;
- ``UNKNOWN_SCOPE_INTERSECTION``: the registry is missing or invalid, or the provider,
  family, semantics, combination, or identifier kind or form is not catalogued, so overlap
  cannot be ruled out;
- ``DIRECT_HOLDOUT_ACCESS_FORBIDDEN``: a local path inside the protected location.

Information semantics decide the temporal rule. ``historical_observation`` is judged by
the protected interval (plus margin and lag). ``current_state``, ``resolution``,
``settlement``, ``contract_metadata``, and ``discovery`` return what is known NOW, so for a
protected contract (or a selector that may include one, or a venue whose protected-period
contracts are protected) they are refused whatever window the caller supplies.

Identifiers are normalized here, never chosen by the caller: each (kind, value) maps to one
canonical spelling and is matched against every alias the scope records. Unknown kinds or
forms fail closed. Synthetic fixtures are allowed only for the catalogued synthetic provider
and family; a request cannot declare itself synthetic. Intervals are half-open UTC
``[start, end)``; naive timestamps are rejected. A derived request is checked window by
window: if ANY input window is refused, the request is refused.

Limit: this enforces PROJECT data paths only. It does not intercept general web research,
which the Protected Information Rule in CLAUDE.md governs.
"""

import argparse
import json
import os
import stat
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final

from pmv.integrity import format_timestamp, is_identifier, to_utc
from pmv.log import fields, get_logger
from pmv.protected_scope import (
    CATALOG,
    IDENTIFIER_RULES,
    PROVIDER_OBSERVABLES,
    CatalogEntry,
    Family,
    IdentifierKind,
    ProtectedScopeError,
    Provider,
    Registry,
    Scope,
    Semantics,
    Venue,
    normalize_identifier,
    parse_identifier_kind,
    verify_committed_registry,
)

_log = get_logger("pmv.data_access_guard")

PROTECTED_ROOT: Final = Path.home() / "pmv-protected"
PROTECTED_NAME: Final = "pmv-protected"
SETTINGS_PATH: Final = ".claude/settings.json"
LOCAL_SETTINGS_PATH: Final = ".claude/settings.local.json"
REQUIRED_DENIES: Final = ("Read(~/pmv-protected/**)", "Edit(~/pmv-protected/**)")


class RefusalReason(StrEnum):
    PROTECTED_SCOPE_NOT_DECLARED = "PROTECTED_SCOPE_NOT_DECLARED"
    PROTECTED_SCOPE_OVERLAP = "PROTECTED_SCOPE_OVERLAP"
    PROTECTED_EQUIVALENT_OBSERVABLE = "PROTECTED_EQUIVALENT_OBSERVABLE"
    UNKNOWN_SCOPE_INTERSECTION = "UNKNOWN_SCOPE_INTERSECTION"
    DIRECT_HOLDOUT_ACCESS_FORBIDDEN = "DIRECT_HOLDOUT_ACCESS_FORBIDDEN"


class GuardError(ValueError):
    """A malformed request (for example a naive timestamp). Never echoes values."""


@dataclass(frozen=True, slots=True)
class Identifier:
    """A caller-supplied identifier, kept raw; the guard decides whether it is understood."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not isinstance(self.value, str):
            raise GuardError("an identifier has a string kind and value")


@dataclass(frozen=True, slots=True)
class Window:
    """One input window: what is read, from where, with which semantics, and when.

    ``[start, end)`` is UTC. It bounds only historical observations; for every other
    semantics the guard ignores it, because a current-state object is not historical.
    """

    provider: str
    family: str
    semantics: str
    start: datetime
    end: datetime
    identifiers: tuple[Identifier, ...] = ()

    def __post_init__(self) -> None:
        if not all(isinstance(item, Identifier) for item in self.identifiers):
            raise GuardError("identifiers must be Identifier values")
        for value in (self.start, self.end):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise GuardError("request timestamps must be timezone-aware")
        if not to_utc(self.start) < to_utc(self.end):
            raise GuardError("a request window needs start before end")


@dataclass(frozen=True, slots=True)
class DataRequest:
    """A project data request. Derived requests list every input window they need."""

    request_id: str
    role: str
    window: Window
    derived_inputs: tuple[Window, ...] = field(default=())

    def __post_init__(self) -> None:
        if not is_identifier(self.request_id) or not is_identifier(self.role):
            raise GuardError("request_id and role must be identifiers")


@dataclass(frozen=True, slots=True)
class Decision:
    request_id: str
    allowed: bool
    reason: RefusalReason | None = None
    scope_id: str | None = None

    def message(self) -> str:
        if self.allowed:
            return f"data request {self.request_id} allowed"
        assert self.reason is not None  # noqa: S101 - a refusal always has a reason
        return f"data request {self.request_id} refused: {self.reason.value}"


class Guard:
    """Decides requests against a registry; a missing or invalid registry refuses real data.

    ``registry`` is the committed registry: only its active scopes can declare a scope and
    so lift ``PROTECTED_SCOPE_NOT_DECLARED``, and it is the authorization floor. ``pending`` is
    a verified working-tree registry extending it. Each window is decided against BOTH, and a
    refusal from either stands, so a pending scope can add refusals but never remove one.
    """

    def __init__(self, registry: Registry | None, pending: Registry | None = None) -> None:
        self._registry = registry
        self._pending = pending

    @classmethod
    def from_repo(cls, repo: Path) -> "Guard":
        """The committed registry and the working tree, only after Git history and every
        committed split definition verify; otherwise refuse real data."""
        try:
            committed, working = verify_committed_registry(repo)
        except ProtectedScopeError:
            return cls(None)
        return cls(committed, working)

    def decide(self, request: DataRequest) -> Decision:
        decision = self._decide(request)
        _log.info(
            "data_guard.decision",
            extra=fields(
                request_id=request.request_id,
                role=request.role,
                provider=_catalogued(Provider, request.window.provider),
                family=_catalogued(Family, request.window.family),
                semantics=_catalogued(Semantics, request.window.semantics),
                identifiers=len(request.window.identifiers),
                start=format_timestamp(request.window.start),
                end=format_timestamp(request.window.end),
                derived_inputs=len(request.derived_inputs),
                allowed=decision.allowed,
                reason=None if decision.reason is None else decision.reason.value,
                scope_id=decision.scope_id,
            ),
        )
        return decision

    def _decide(self, request: DataRequest) -> Decision:
        for window in (request.window, *request.derived_inputs):
            refusal = self._window(window)
            if refusal is not None:
                return Decision(request.request_id, False, refusal[0], refusal[1])
        return Decision(request.request_id, True)

    def _window(self, window: Window) -> tuple[RefusalReason, str | None] | None:
        unknown = RefusalReason.UNKNOWN_SCOPE_INTERSECTION, None
        try:
            entry = CATALOG.get((Provider(window.provider), Family(window.family)))
            semantics = Semantics(window.semantics)
        except ValueError:
            return unknown
        if entry is None:
            return unknown
        identifiers = _normalized(window.identifiers, entry.venue)
        if identifiers is None:
            return unknown
        if entry.synthetic:
            return None
        if entry.venue is None and semantics is not Semantics.HISTORICAL_OBSERVATION:
            return unknown  # current state of an underlying is not a catalogued combination
        if self._registry is None:
            return unknown
        if not self._registry.active:
            return RefusalReason.PROTECTED_SCOPE_NOT_DECLARED, None
        for registry in (self._registry, self._pending):
            if registry is not None:
                refusal = _against(registry.active, window, entry, semantics, identifiers)
                if refusal is not None:
                    return refusal
        return None


def _against(
    scopes: Sequence[Scope],
    window: Window,
    entry: CatalogEntry,
    semantics: Semantics,
    identifiers: Sequence[tuple[IdentifierKind, str]],
) -> tuple[RefusalReason, str | None] | None:
    """The first refusal one set of active scopes gives a window, or None."""
    for scope in scopes:
        refusal = _identity(scope, entry.venue, identifiers)
        if refusal is not None:
            return refusal, scope.scope_id
    provider_observables = PROVIDER_OBSERVABLES[Provider(window.provider)]
    start, end = to_utc(window.start), to_utc(window.end)
    for scope in scopes:
        if semantics is not Semantics.HISTORICAL_OBSERVATION:
            # TEMPORARY FAIL-CLOSED RULE until a trusted endpoint / contract-lifecycle
            # catalog exists: a venue that serves any protected asset can expose current
            # or final state of markets that reconstruct the protected path, and nothing
            # here can prove the requested object is unrelated.
            if provider_observables & set(scope.lags):
                return RefusalReason.UNKNOWN_SCOPE_INTERSECTION, scope.scope_id
            continue
        protected = entry.observables & set(scope.lags)
        venue_wide = entry.venue is not None and entry.venue in scope.venues
        for observable in protected:
            if _overlaps(start, end, scope, scope.lags[observable]):
                if venue_wide:
                    return RefusalReason.PROTECTED_SCOPE_OVERLAP, scope.scope_id
                return RefusalReason.PROTECTED_EQUIVALENT_OBSERVABLE, scope.scope_id
    return None


def _identity(
    scope: Scope, venue: Venue | None, identifiers: Sequence[tuple[IdentifierKind, str]]
) -> RefusalReason | None:
    """Refuse a protected contract under EVERY semantics and at EVERY time.

    A request on a venue that names no identifier is bulk and may include any protected
    contract there. An identifier reaches a contract only through the record's explicit
    identifiers; a kind the record does not hold leaves identity unknown (fail closed).
    """
    on_venue = [item for item in scope.contracts if item.venue is venue]
    if not on_venue:
        return None
    if not identifiers:
        return RefusalReason.PROTECTED_SCOPE_OVERLAP
    results = [item.reached_by(kind, value) for item in on_venue for kind, value in identifiers]
    if any(result is True for result in results):
        return RefusalReason.PROTECTED_SCOPE_OVERLAP
    if any(result is None for result in results):
        return RefusalReason.UNKNOWN_SCOPE_INTERSECTION
    return None


def _normalized(
    identifiers: Sequence[Identifier], venue: Venue | None
) -> list[tuple[IdentifierKind, str]] | None:
    """Known kinds for this venue in canonical spelling, or None if anything is not understood."""
    result: list[tuple[IdentifierKind, str]] = []
    for item in identifiers:
        kind = parse_identifier_kind(item.kind)
        if kind is None or venue is None or IDENTIFIER_RULES[kind].venue is not venue:
            return None
        value = normalize_identifier(kind, item.value)
        if value is None:
            return None
        result.append((kind, value))
    return result


def _catalogued(enum: type[StrEnum], value: str) -> str:
    """Log only catalogued names; an arbitrary string could be a contract ID or a value."""
    return value if value in {item.value for item in enum} else "<uncatalogued>"


def _overlaps(start: datetime, end: datetime, scope: Scope, lag_seconds: int) -> bool:
    """[start, end) against [scope.start - margin, scope.end + margin + lag)."""
    margin = timedelta(seconds=scope.margin_seconds)
    protected_start = scope.start - margin
    if end <= protected_start:
        return False
    if scope.end is None:
        return True
    protected_end = scope.end + margin + timedelta(seconds=lag_seconds)
    return start < protected_end


def check_path(path: Path, protected_root: Path = PROTECTED_ROOT) -> RefusalReason | None:
    """Refuse any local path inside the protected location (lexically or after symlinks)."""
    root = Path(os.path.realpath(protected_root))
    lexical = Path(os.path.abspath(os.path.expanduser(path)))
    resolved = Path(os.path.realpath(lexical))
    for candidate in (lexical, resolved):
        if (
            candidate == root
            or candidate.is_relative_to(root)
            or candidate.is_relative_to(protected_root)
        ):
            return RefusalReason.DIRECT_HOLDOUT_ACCESS_FORBIDDEN
    return None


def check_config(repo: Path) -> list[str]:
    """Problems with the committed defense-in-depth settings (empty when correct).

    Checks the shared settings file and, if present, the local override file: any
    allow-style entry that names the protected location is a problem, and a local file
    may not override the sandbox at all.
    """
    problems: list[str] = []
    try:
        settings = json.loads((repo / SETTINGS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["the project Claude settings are missing or not valid JSON"]
    if not isinstance(settings, dict):
        return ["the project Claude settings are not a JSON object"]
    permissions = _section(settings, "permissions", problems)
    deny = permissions.get("deny", [])
    for rule in REQUIRED_DENIES:
        if not isinstance(deny, list) or rule not in deny:
            problems.append("a required protected-path permission deny is missing")
    sandbox = _section(settings, "sandbox", problems)
    if sandbox.get("enabled") is not True or sandbox.get("failIfUnavailable") is not True:
        problems.append("the sandbox must be enabled and fail closed")
    if sandbox.get("allowUnsandboxedCommands") is not False:
        problems.append("unsandboxed command fallback must be disabled")
    filesystem = _section(sandbox, "filesystem", problems)
    for key in ("denyRead", "denyWrite"):
        listed = filesystem.get(key, [])
        if not isinstance(listed, list) or "~/pmv-protected" not in listed:
            problems.append(f"the sandbox {key} list must include the protected location")
    if "excludedCommands" in sandbox:
        problems.append("excludedCommands must not be used")
    if _allows_protected(settings):
        problems.append("an allow entry names the protected location")
    local = repo / LOCAL_SETTINGS_PATH
    if os.path.lexists(local) and not _is_null_device(local):
        try:
            overrides = json.loads(local.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            problems.append("the local Claude settings are unreadable or not valid JSON")
        else:
            if not isinstance(overrides, dict) or "sandbox" in overrides:
                problems.append("the local Claude settings must not override the sandbox")
            if _allows_protected(overrides):
                problems.append("a local allow entry names the protected location")
    return problems


def _is_null_device(path: Path) -> bool:
    """The Claude Code sandbox masks absent protected files with /dev/null; that is no override."""
    try:
        status = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISCHR(status.st_mode) and status.st_rdev == os.stat(os.devnull).st_rdev


def _section(parent: dict[str, object], key: str, problems: list[str]) -> dict[str, object]:
    value = parent.get(key, {})
    if not isinstance(value, dict):
        problems.append(f"the settings section {key} is not a JSON object")
        return {}
    return value


def _allows_protected(value: object, under_allow: bool = False) -> bool:
    """Whether any string under an allow-style key (allow, allowRead, ...) names the location."""
    if isinstance(value, dict):
        return any(
            _allows_protected(item, under_allow or "allow" in str(key).lower())
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_allows_protected(item, under_allow) for item in value)
    return under_allow and isinstance(value, str) and PROTECTED_NAME in value


def _window_from_json(value: object) -> Window:
    if not isinstance(value, dict) or set(value) != {
        "provider",
        "family",
        "semantics",
        "start",
        "end",
        "identifiers",
    }:
        raise GuardError("a request window has exactly the v1 fields")
    identifiers = value["identifiers"]
    if not isinstance(identifiers, list):
        raise GuardError("identifiers must be a list")
    parsed: list[Identifier] = []
    for item in identifiers:
        if not isinstance(item, dict) or set(item) != {"kind", "value"}:
            raise GuardError("an identifier has exactly a kind and a value")
        parsed.append(Identifier(item["kind"], item["value"]))
    return Window(
        str(value["provider"]),
        str(value["family"]),
        str(value["semantics"]),
        _time(value["start"]),
        _time(value["end"]),
        tuple(parsed),
    )


def _time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GuardError("timestamps must be UTC (YYYY-MM-DDTHH:MM:SS.ffffffZ)")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        raise GuardError("timestamps must be UTC (YYYY-MM-DDTHH:MM:SS.ffffffZ)") from None


def request_from_json(value: object) -> DataRequest:
    if not isinstance(value, dict) or set(value) != {
        "request_id",
        "role",
        "window",
        "derived_inputs",
    }:
        raise GuardError("a data request has exactly the v1 fields")
    derived = value["derived_inputs"]
    if not isinstance(derived, list):
        raise GuardError("derived_inputs must be a list")
    return DataRequest(
        str(value["request_id"]),
        str(value["role"]),
        _window_from_json(value["window"]),
        tuple(_window_from_json(item) for item in derived),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pmv.data_access_guard", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config", help="verify the committed defense-in-depth settings")
    decide = commands.add_parser("decide", help="decide one JSON data request (no data is fetched)")
    decide.add_argument("--request", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "check-config":
        problems = check_config(arguments.repo)
        for problem in problems:
            sys.stderr.write(f"settings: {problem}\n")
        if not problems:
            sys.stdout.write("protected-information settings verified\n")
        return 1 if problems else 0
    try:
        request = request_from_json(json.loads(arguments.request.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        sys.stderr.write("GuardError: the request could not be read or is malformed\n")
        return 1
    decision = Guard.from_repo(arguments.repo).decide(request)
    sys.stdout.write(decision.message() + "\n")
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
