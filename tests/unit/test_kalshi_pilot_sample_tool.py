"""B12 pilot fetch tool: offline checks of its scope guards and ceilings (no network).

``fetch`` is replaced by a stub returning invented bytes; nothing here contacts a host.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

TOOL = (
    Path(__file__).resolve().parents[2] / "research/data_sources/recon_tools/kalshi_pilot_sample.py"
)


@pytest.fixture
def tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location("kalshi_pilot_sample", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "RECON_ROOT", tmp_path.resolve())
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    return module


def stub(
    monkeypatch: pytest.MonkeyPatch, tool: ModuleType, responses: dict[str, object]
) -> list[str]:
    seen: list[str] = []

    def fake_fetch(path: str, direct: bool) -> bytes:
        seen.append(path)
        for prefix, body in responses.items():
            if path.startswith(prefix):
                return json.dumps(body).encode()
        raise AssertionError(path)

    monkeypatch.setattr(tool, "fetch", fake_fetch)
    return seen


def test_build_path_uses_fixed_templates_only(tool: ModuleType) -> None:
    assert tool.build_path("cutoff", {}) == "/trade-api/v2/historical/cutoff"
    assert (
        tool.build_path("historical_trades", {"ticker": "KXBTC15M-X", "limit": "1000"})
        == "/trade-api/v2/historical/trades?limit=1000&ticker=KXBTC15M-X"
    )
    with pytest.raises(KeyError):
        tool.build_path("portfolio_orders", {})


def test_store_refuses_paths_outside_recon_root(tool: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="must resolve under"):
        tool.Store(tmp_path.parent / "elsewhere")


def test_market_requires_series_prefix_and_cutoff(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tool.Store(tmp_path / "pilot")
    with pytest.raises(SystemExit, match="ticker must match"):
        tool.cmd_market(store, "KXETH15M-30JAN010015", False)
    with pytest.raises(SystemExit, match="discover"):
        tool.cmd_market(store, "KXBTC15M-30JAN010015", False)


def test_market_after_cutoff_is_not_sampled(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tool.Store(tmp_path / "pilot")
    (store.out / "cutoff.json").write_text(
        json.dumps({"market_settled_ts": "2030-01-01T00:00:00Z"})
    )
    stub(
        monkeypatch,
        tool,
        {
            "/trade-api/v2/historical/markets/": {
                "market": {
                    "open_time": "2030-01-01T00:00:00Z",
                    "close_time": "2030-01-01T00:15:00Z",
                }
            },
        },
    )
    with pytest.raises(SystemExit, match="historical cutoff"):
        tool.cmd_market(store, "KXBTC15M-30JAN010015", False)


def test_market_pages_trades_until_empty_cursor(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tool.Store(tmp_path / "pilot")
    (store.out / "cutoff.json").write_text(
        json.dumps({"market_settled_ts": "2031-01-01T00:00:00Z"})
    )
    seen = stub(
        monkeypatch,
        tool,
        {
            "/trade-api/v2/historical/markets/KXBTC15M-30JAN010015/candlesticks": {
                "candlesticks": [{"end_period_ts": 60}]
            },
            "/trade-api/v2/historical/markets/": {
                "market": {
                    "open_time": "2030-01-01T00:00:00Z",
                    "close_time": "2030-01-01T00:15:00Z",
                }
            },
            "/trade-api/v2/historical/trades": {"trades": [{"trade_id": "a"}], "cursor": ""},
        },
    )
    tool.cmd_market(store, "KXBTC15M-30JAN010015", False)
    assert len(seen) == 3
    assert seen[2] == "/trade-api/v2/historical/trades?limit=1000&ticker=KXBTC15M-30JAN010015"
    manifest = (store.out / "manifest.jsonl").read_text().splitlines()
    assert [json.loads(line)["rows"] for line in manifest] == [1, 1, 1]
    assert tool.Store(tmp_path / "pilot").rows == 3  # cumulative across invocations


def test_ceiling_stops_before_writing(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tool, "MAX_ROWS", 2)
    store = tool.Store(tmp_path / "pilot")
    stub(monkeypatch, tool, {"/trade-api/v2/events": {"events": [{}, {}, {}]}})
    with pytest.raises(SystemExit, match="ceiling"):
        tool.cmd_depth(store, "2030-01-01", False)
    assert not list(store.out.glob("depth_events_*"))


def test_proxy_route_never_reads_runtime_proxy_variables(
    tool: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PMV_EGRESS_PROXY_HOST", "user:pw@proxy")
    monkeypatch.setenv("PMV_EGRESS_PROXY_PORT", "3128")
    with pytest.raises(SystemExit) as raised:
        tool.proxy_address()
    assert "pw" not in str(raised.value)
