"""Capture environment boundaries (Step 11 F-37 and RT-4; Kalshi Red-Team RT-B2-09).

Three kinds of bytes must never be mistaken for one another:

- **synthetic** fixtures, written only by the ``test`` deployment environment, only for
  reserved test hosts (RFC 2606 ``.example``, ``.test``, ``.invalid``), and never into the
  protected raw location;
- **demo** captures from a venue's demo environment. Demo prices and behavior "may not be
  reflective" of production, so demo data is never evidence about production. It is still
  treated as real for protection (F-37): it is written only into the protected raw
  location, and research loaders refuse it (RT-B2-09);
- **production** captures, the only kind research may ever use, and only through the H-2
  release path.

A real collector refuses the ``test`` deployment environment (RT-4). Every demo or
production session needs an endpoint in ``APPROVED_CAPTURE_ENDPOINTS``: an exact host,
bound to one venue environment, named by an owner decision. **That registry is empty.**
Live capture is not authorized, so every non-synthetic session refuses today. Adding an
entry is an owner-approved, reviewed code change; a caller cannot supply one.

``authorize_capture`` is the only producer of a ``CaptureAuthorization``; the capture store
accepts nothing else. This is a code-level check: in-process monkeypatching of module
constants is out of scope, as for every code-level control.
"""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from pmv.capture_format import VenueEnvironment
from pmv.config import PROTECTED_RAW_BASE, Environment, protected_raw_root_problem
from pmv.integrity import is_identifier

__all__ = [
    "APPROVED_CAPTURE_ENDPOINTS",
    "CaptureAuthorization",
    "CaptureEndpoint",
    "CaptureEnvironmentError",
    "DataUse",
    "RefusedTestEnvironmentError",
    "VenueEnvironment",
    "authorize_capture",
    "is_reserved_test_host",
    "refuse_test_environment",
    "require_data_use",
]

RESERVED_TEST_SUFFIXES: Final = (".example", ".test", ".invalid")
_HOST_LABEL_CHARS: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


class CaptureEnvironmentError(Exception):
    """A capture or data use crosses an environment boundary. Fail closed."""


class RefusedTestEnvironmentError(CaptureEnvironmentError):
    """A command that may only run on real configurations was given the test environment."""


@dataclass(frozen=True, slots=True)
class CaptureEndpoint:
    """One owner-approved capture endpoint: an exact host in one venue environment."""

    venue_environment: VenueEnvironment
    host: str
    endpoint_id: str
    decision_record: str


# Owner-approved capture endpoints. EMPTY: live capture is not authorized (B08). An entry
# needs an owner decision record naming the exact host, its environment, and its purpose,
# and a reviewed code change.
APPROVED_CAPTURE_ENDPOINTS: Final[frozenset[CaptureEndpoint]] = frozenset()

_ISSUED: Final = object()


class CaptureAuthorization:
    """Proof that ``authorize_capture`` accepted one session's environment and endpoint.

    It is deliberately not a dataclass, so ``dataclasses.replace`` cannot re-issue it with
    other fields (RT-B8-02). The capture store does not trust it either: it re-runs
    ``authorize_capture`` from these fields and its own deployment environment before any
    session starts.
    """

    __slots__ = (
        "_deployment",
        "_endpoint_id",
        "_host",
        "_protected_base",
        "_store_root",
        "_venue",
    )

    def __init__(
        self,
        deployment_environment: Environment,
        venue_environment: VenueEnvironment,
        host: str,
        endpoint_id: str,
        store_root: Path,
        protected_base: Path,
        token: object,
    ) -> None:
        if token is not _ISSUED:
            raise CaptureEnvironmentError("capture authorizations come from authorize_capture")
        self._deployment = deployment_environment
        self._venue = venue_environment
        self._host = host
        self._endpoint_id = endpoint_id
        self._store_root = store_root
        self._protected_base = protected_base

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, "_protected_base"):
            raise AttributeError("capture authorizations are immutable")
        object.__setattr__(self, name, value)

    @property
    def deployment_environment(self) -> Environment:
        return self._deployment

    @property
    def venue_environment(self) -> VenueEnvironment:
        return self._venue

    @property
    def host(self) -> str:
        return self._host

    @property
    def endpoint_id(self) -> str:
        return self._endpoint_id

    @property
    def store_root(self) -> Path:
        return self._store_root

    @property
    def protected_base(self) -> Path:
        return self._protected_base


def is_reserved_test_host(host: str) -> bool:
    """Whether ``host`` is a lowercase DNS name under an RFC 2606 reserved test domain."""
    if not isinstance(host, str) or not 1 <= len(host) <= 253 or not host.isascii():
        return False
    labels = host.split(".")
    if any(not label or len(label) > 63 or not set(label) <= _HOST_LABEL_CHARS for label in labels):
        return False
    return host.endswith(RESERVED_TEST_SUFFIXES) and len(labels) >= 2


def authorize_capture(
    *,
    deployment_environment: Environment,
    venue_environment: VenueEnvironment,
    host: str,
    endpoint_id: str,
    store_root: Path,
    protected_base: Path = PROTECTED_RAW_BASE,
) -> CaptureAuthorization:
    """Check one capture session against the environment rules, or refuse.

    - ``test`` deployment: synthetic only, reserved test hosts only, and a store root
      outside the protected raw location.
    - ``development``: demo or production, never synthetic. ``shadow`` and ``production``:
      production only.
    - Demo and production: the exact host and endpoint must be an approved endpoint for
      that venue environment, and the store root must be inside the protected raw
      location (demo is protected like real data, F-37).

    ``protected_base`` is an additional location a synthetic (``test``) store must stay
    out of; the account's real protected location is always refused too. Demo and
    production stores are checked against the real protected location only (RT-B8-13).
    """
    if not isinstance(deployment_environment, Environment):
        raise CaptureEnvironmentError("unknown deployment environment")
    if not isinstance(venue_environment, VenueEnvironment):
        raise CaptureEnvironmentError("unknown venue environment")
    if not is_identifier(endpoint_id):
        raise CaptureEnvironmentError("endpoint_id must be a lowercase identifier")
    if not isinstance(store_root, Path) or not store_root.is_absolute():
        raise CaptureEnvironmentError("the store root must be an absolute path")
    if deployment_environment is Environment.TEST:
        inside_protected = protected_raw_root_problem(store_root, protected_base) is None
        if venue_environment is not VenueEnvironment.SYNTHETIC:
            raise RefusedTestEnvironmentError(
                "the test environment captures synthetic data only (RT-4)"
            )
        if not is_reserved_test_host(host):
            raise CaptureEnvironmentError("synthetic captures use reserved test hosts only")
        if (
            inside_protected
            or _resolves_inside(store_root, protected_base)
            or _resolves_inside(store_root, PROTECTED_RAW_BASE)
        ):
            raise CaptureEnvironmentError("synthetic captures never write the protected raw store")
    else:
        if venue_environment is VenueEnvironment.SYNTHETIC:
            raise CaptureEnvironmentError(
                "synthetic captures are written only by the test environment"
            )
        if venue_environment is VenueEnvironment.DEMO and (
            deployment_environment is not Environment.DEVELOPMENT
        ):
            raise CaptureEnvironmentError("demo captures run only in the development environment")
        if not any(
            approved.venue_environment is venue_environment
            and approved.host == host
            and approved.endpoint_id == endpoint_id
            for approved in APPROVED_CAPTURE_ENDPOINTS
        ):
            raise CaptureEnvironmentError(
                "no owner-approved capture endpoint matches this host and environment; "
                "live capture is not authorized"
            )
        # Always the account's real protected location, never a caller-supplied base
        # (RT-B8-13). Read at call time, so tests can substitute a temporary base.
        if protected_raw_root_problem(store_root, PROTECTED_RAW_BASE) is not None:
            raise CaptureEnvironmentError(
                "real and demo captures are written only inside the protected raw location"
            )
    return CaptureAuthorization(
        deployment_environment,
        venue_environment,
        host,
        endpoint_id,
        store_root,
        protected_base,
        _ISSUED,
    )


def _resolves_inside(root: Path, base: Path) -> bool:
    lexical = Path(os.path.normpath(root))
    resolved = Path(os.path.realpath(root))
    for candidate_base in (Path(os.path.normpath(base)), Path(os.path.realpath(base))):
        if lexical.is_relative_to(candidate_base) or resolved.is_relative_to(candidate_base):
            return True
    return False


def refuse_test_environment(environment: Environment, command: str) -> None:
    """RT-4: commands that create project records or touch real data refuse ``test``."""
    if environment is Environment.TEST:
        raise RefusedTestEnvironmentError(
            f"{command} refuses the test environment; use a real configuration (RT-4)"
        )


class DataUse(StrEnum):
    """Why captured data is being loaded."""

    TEST = "test"
    RESEARCH = "research"


def require_data_use(venue_environment: VenueEnvironment, use: DataUse) -> None:
    """Research loaders accept production captures only (RT-B2-09, F-37).

    Demo captures are refused for every use: they are protected like real data but are
    never evidence about production. Synthetic captures are accepted only for tests.
    """
    if not isinstance(venue_environment, VenueEnvironment) or not isinstance(use, DataUse):
        raise CaptureEnvironmentError("unknown venue environment or data use")
    if venue_environment is VenueEnvironment.DEMO:
        raise CaptureEnvironmentError("demo captures are never loaded as data (RT-B2-09)")
    if venue_environment is VenueEnvironment.SYNTHETIC and use is not DataUse.TEST:
        raise CaptureEnvironmentError("synthetic captures are loaded only for tests")
    if venue_environment is VenueEnvironment.PRODUCTION and use is not DataUse.RESEARCH:
        raise CaptureEnvironmentError("production captures are loaded only for research")
