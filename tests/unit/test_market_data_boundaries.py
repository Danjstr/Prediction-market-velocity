"""Structural boundaries of ``pmv.market_data``, checked from source.

- No module imports a network library: nothing here fetches data.
- No module reads the wall clock: decision times are always supplied explicitly, so replay
  is deterministic and no module can stamp "now" onto data.
- Modules on the observation and feature side never import the label module, so outcome
  types cannot be wired into feature code by accident.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "pmv" / "market_data"
MODULES = sorted(path.stem for path in PACKAGE.glob("*.py"))
NETWORK_MODULES = frozenset(
    {
        "aiohttp",
        "asyncio",
        "ftplib",
        "http",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "ssl",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
    }
)
WALL_CLOCK_CALLS = frozenset({"now", "utcnow", "today", "time", "time_ns"})
FEATURE_SIDE = ("timing", "contracts", "events", "point_in_time", "validation", "books")


def tree(module: str) -> ast.Module:
    return ast.parse((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))


def imports(module: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree(module)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def test_the_package_has_the_expected_modules() -> None:
    assert MODULES == [
        "__init__",
        "books",
        "capture_replay",
        "contracts",
        "events",
        "kalshi",
        "labels",
        "point_in_time",
        "replay",
        "synthetic",
        "timing",
        "validation",
    ]


@pytest.mark.parametrize("module", MODULES)
def test_no_network_library_is_imported(module: str) -> None:
    assert not {name.split(".")[0] for name in imports(module)} & NETWORK_MODULES


@pytest.mark.parametrize("module", MODULES)
def test_no_wall_clock_is_read(module: str) -> None:
    for node in ast.walk(tree(module)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in WALL_CLOCK_CALLS, module
    assert "time" not in {name.split(".")[0] for name in imports(module)}


@pytest.mark.parametrize("module", FEATURE_SIDE)
def test_feature_side_modules_never_import_labels(module: str) -> None:
    forbidden = {
        "pmv.market_data.labels",
        "pmv.market_data.replay",
        "pmv.market_data.synthetic",
        "pmv.market_data.kalshi",
    }
    assert not imports(module) & forbidden
