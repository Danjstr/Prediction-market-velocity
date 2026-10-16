"""Tests for capture environment boundaries (F-37, RT-4, RT-B2-09).

Every environment fact under test is constructed by the test itself: temporary roots, an
explicit protected base, and explicitly patched endpoint registries. Nothing depends on
the ambient checkout, home directory, or branch.
"""

from pathlib import Path

import pytest

import pmv.capture_environment as capture_environment
from pmv.capture_environment import (
    APPROVED_CAPTURE_ENDPOINTS,
    CaptureAuthorization,
    CaptureEndpoint,
    CaptureEnvironmentError,
    DataUse,
    RefusedTestEnvironmentError,
    VenueEnvironment,
    authorize_capture,
    is_reserved_test_host,
    refuse_test_environment,
    require_data_use,
)
from pmv.config import Environment

HOST = "feed.pmv.example"


@pytest.fixture
def protected(tmp_path: Path) -> Path:
    base = tmp_path / "home" / "pmv-protected" / "raw"
    base.mkdir(parents=True)
    return base


def authorize(
    deployment: Environment,
    venue: VenueEnvironment,
    root: Path,
    protected: Path,
    host: str = HOST,
) -> CaptureAuthorization:
    return authorize_capture(
        deployment_environment=deployment,
        venue_environment=venue,
        host=host,
        endpoint_id="unit_ws",
        store_root=root,
        protected_base=protected,
    )


def test_the_endpoint_registry_is_empty() -> None:
    # Live capture is not authorized: no demo or production endpoint is approved.
    assert frozenset() == APPROVED_CAPTURE_ENDPOINTS


def test_the_test_environment_captures_synthetic_data_on_reserved_hosts(
    tmp_path: Path, protected: Path
) -> None:
    root = tmp_path / "store"
    root.mkdir()
    granted = authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, root, protected)
    assert granted.venue_environment is VenueEnvironment.SYNTHETIC
    assert granted.deployment_environment is Environment.TEST


@pytest.mark.parametrize("venue", [VenueEnvironment.DEMO, VenueEnvironment.PRODUCTION])
def test_a_collector_refuses_the_test_environment_for_real_venues(
    tmp_path: Path, protected: Path, venue: VenueEnvironment
) -> None:
    with pytest.raises(RefusedTestEnvironmentError, match="RT-4"):
        authorize(Environment.TEST, venue, tmp_path, protected)


@pytest.mark.parametrize(
    "host",
    [
        "api.elections.kalshi.com",
        "demo-api.kalshi.co",
        "example",
        "feed.example.com",
        "UPPER.example",
        "a..example",
        "x.local",
    ],
)
def test_synthetic_captures_use_reserved_test_hosts_only(
    tmp_path: Path, protected: Path, host: str
) -> None:
    with pytest.raises(CaptureEnvironmentError, match="reserved test hosts"):
        authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, tmp_path, protected, host)


def test_synthetic_captures_never_write_the_protected_store(
    tmp_path: Path, protected: Path
) -> None:
    inside = protected / "synthetic"
    inside.mkdir()
    with pytest.raises(CaptureEnvironmentError, match="never write the protected"):
        authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, inside, protected)
    # a symlink that resolves into the protected store is refused too
    link = tmp_path / "innocent"
    link.symlink_to(inside)
    with pytest.raises(CaptureEnvironmentError, match="never write the protected"):
        authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, link, protected)


@pytest.mark.parametrize(
    "deployment", [Environment.DEVELOPMENT, Environment.SHADOW, Environment.PRODUCTION]
)
def test_real_deployments_never_write_synthetic_captures(
    tmp_path: Path, protected: Path, deployment: Environment
) -> None:
    with pytest.raises(CaptureEnvironmentError, match="only by the test environment"):
        authorize(deployment, VenueEnvironment.SYNTHETIC, protected, protected)


@pytest.mark.parametrize("deployment", [Environment.SHADOW, Environment.PRODUCTION])
def test_demo_capture_runs_only_in_development(protected: Path, deployment: Environment) -> None:
    with pytest.raises(CaptureEnvironmentError, match="only in the development"):
        authorize(deployment, VenueEnvironment.DEMO, protected, protected)


@pytest.mark.parametrize(
    ("deployment", "venue"),
    [
        (Environment.DEVELOPMENT, VenueEnvironment.DEMO),
        (Environment.DEVELOPMENT, VenueEnvironment.PRODUCTION),
        (Environment.SHADOW, VenueEnvironment.PRODUCTION),
        (Environment.PRODUCTION, VenueEnvironment.PRODUCTION),
    ],
)
def test_every_real_capture_refuses_today(
    protected: Path, deployment: Environment, venue: VenueEnvironment
) -> None:
    with pytest.raises(CaptureEnvironmentError, match="live capture is not authorized"):
        authorize(deployment, venue, protected, protected)


def test_an_approved_endpoint_binds_its_exact_host_and_environment(
    tmp_path: Path, protected: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a (test-only) registry entry, everything else must still match exactly."""
    entry = CaptureEndpoint(
        VenueEnvironment.PRODUCTION, "feed.approved.example", "unit_ws", "docs/decisions/x.md"
    )
    monkeypatch.setattr(capture_environment, "APPROVED_CAPTURE_ENDPOINTS", frozenset({entry}))
    monkeypatch.setattr(capture_environment, "PROTECTED_RAW_BASE", protected)
    granted = authorize(
        Environment.PRODUCTION,
        VenueEnvironment.PRODUCTION,
        protected,
        protected,
        "feed.approved.example",
    )
    assert granted.host == "feed.approved.example"
    for host in ("other.approved.example", "FEED.approved.example", "feed.approved.example."):
        with pytest.raises(CaptureEnvironmentError, match="not authorized"):
            authorize(
                Environment.PRODUCTION, VenueEnvironment.PRODUCTION, protected, protected, host
            )
    # the same host as a demo endpoint is a different, unapproved endpoint
    with pytest.raises(CaptureEnvironmentError, match="not authorized"):
        authorize(
            Environment.DEVELOPMENT,
            VenueEnvironment.DEMO,
            protected,
            protected,
            "feed.approved.example",
        )
    # real data is written only inside the protected location
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(CaptureEnvironmentError, match="only inside the protected"):
        authorize(
            Environment.PRODUCTION,
            VenueEnvironment.PRODUCTION,
            outside,
            protected,
            "feed.approved.example",
        )


def test_demo_is_protected_like_real_data(
    tmp_path: Path, protected: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = CaptureEndpoint(VenueEnvironment.DEMO, "demo.feed.example", "unit_ws", "d.md")
    monkeypatch.setattr(capture_environment, "APPROVED_CAPTURE_ENDPOINTS", frozenset({entry}))
    monkeypatch.setattr(capture_environment, "PROTECTED_RAW_BASE", protected)
    granted = authorize(
        Environment.DEVELOPMENT, VenueEnvironment.DEMO, protected, protected, "demo.feed.example"
    )
    assert granted.venue_environment is VenueEnvironment.DEMO
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(CaptureEnvironmentError, match="only inside the protected"):
        authorize(
            Environment.DEVELOPMENT, VenueEnvironment.DEMO, outside, protected, "demo.feed.example"
        )


def test_authorizations_cannot_be_constructed_directly(tmp_path: Path) -> None:
    with pytest.raises(CaptureEnvironmentError, match="come from authorize_capture"):
        CaptureAuthorization(
            Environment.PRODUCTION,
            VenueEnvironment.PRODUCTION,
            "x.example",
            "unit_ws",
            tmp_path,
            tmp_path,
            object(),
        )


def test_authorizations_cannot_be_reissued_or_mutated(tmp_path: Path, protected: Path) -> None:
    """RT-B8-02: a test authorization cannot be turned into a production one."""
    import dataclasses

    root = tmp_path / "store"
    root.mkdir()
    granted = authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, root, protected)
    with pytest.raises(TypeError):
        dataclasses.replace(granted, deployment_environment=Environment.PRODUCTION)  # type: ignore[type-var]
    with pytest.raises(AttributeError):
        granted._deployment = Environment.PRODUCTION
    assert granted.deployment_environment is Environment.TEST


def test_inputs_are_validated(tmp_path: Path, protected: Path) -> None:
    with pytest.raises(CaptureEnvironmentError, match="absolute"):
        authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, Path("relative"), protected)
    with pytest.raises(CaptureEnvironmentError, match="endpoint_id"):
        authorize_capture(
            deployment_environment=Environment.TEST,
            venue_environment=VenueEnvironment.SYNTHETIC,
            host=HOST,
            endpoint_id="Bad-Id",
            store_root=tmp_path,
            protected_base=protected,
        )


@pytest.mark.parametrize(
    ("host", "reserved"),
    [
        ("a.example", True),
        ("x.y.test", True),
        ("bad.invalid", True),
        ("example", False),
        ("a.example.com", False),
        ("a_b.example", False),
        ("", False),
        ("a." * 130 + "example", False),
    ],
)
def test_reserved_test_hosts(host: str, reserved: bool) -> None:
    assert is_reserved_test_host(host) is reserved


# ----- data use (research loaders) -----


@pytest.mark.parametrize("use", list(DataUse))
def test_demo_captures_are_never_loaded_as_data(use: DataUse) -> None:
    with pytest.raises(CaptureEnvironmentError, match="demo captures are never loaded"):
        require_data_use(VenueEnvironment.DEMO, use)


def test_synthetic_data_is_for_tests_and_production_for_research() -> None:
    require_data_use(VenueEnvironment.SYNTHETIC, DataUse.TEST)
    require_data_use(VenueEnvironment.PRODUCTION, DataUse.RESEARCH)
    with pytest.raises(CaptureEnvironmentError, match="only for tests"):
        require_data_use(VenueEnvironment.SYNTHETIC, DataUse.RESEARCH)
    with pytest.raises(CaptureEnvironmentError, match="only for research"):
        require_data_use(VenueEnvironment.PRODUCTION, DataUse.TEST)


def test_commands_refuse_the_test_environment() -> None:
    with pytest.raises(RefusedTestEnvironmentError, match="RT-4"):
        refuse_test_environment(Environment.TEST, "pmv.example command")
    for environment in (Environment.DEVELOPMENT, Environment.SHADOW, Environment.PRODUCTION):
        refuse_test_environment(environment, "pmv.example command")


def test_real_captures_ignore_a_caller_supplied_protected_base(
    tmp_path: Path, protected: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RT-B8-13: only the account's real protected location counts for real data."""
    entry = CaptureEndpoint(VenueEnvironment.PRODUCTION, "feed.approved.example", "unit_ws", "x")
    monkeypatch.setattr(capture_environment, "APPROVED_CAPTURE_ENDPOINTS", frozenset({entry}))
    monkeypatch.setattr(capture_environment, "PROTECTED_RAW_BASE", protected)
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(CaptureEnvironmentError, match="only inside the protected"):
        authorize(
            Environment.PRODUCTION,
            VenueEnvironment.PRODUCTION,
            outside,
            outside,  # a caller claiming its own root is the protected base
            "feed.approved.example",
        )


def test_synthetic_stores_also_avoid_the_real_protected_location(
    tmp_path: Path, protected: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capture_environment, "PROTECTED_RAW_BASE", protected)
    inside = protected / "synthetic"
    inside.mkdir()
    elsewhere = tmp_path / "unrelated-base"
    elsewhere.mkdir()
    with pytest.raises(CaptureEnvironmentError, match="never write the protected"):
        authorize(Environment.TEST, VenueEnvironment.SYNTHETIC, inside, elsewhere)
