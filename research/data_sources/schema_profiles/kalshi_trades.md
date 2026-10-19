# Kalshi — trades and candlesticks (live and historical tiers)

**Status:** **SCHEMA INSPECTED** (OpenAPI 3.34.0 re-fetched 2026-10-19; verbatim field evidence in `research/kalshi/api_documentation_findings.md` §3.5–3.7, §5, §7). Samples **ACCESS BLOCKED** (`api.elections.kalshi.com`, sandbox deny list). **LICENSE GATED** (Developer Agreement; M1).

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://docs.kalshi.com/openapi.yaml | 2026-10-19T04:18:27Z | 200 | 375,483 | `bd0c218a65b79f5ee2a27689a5b1d902b6df67663864373bf9e9980f0f9ad9ee` | VERIFIED-BY-DOC |
| https://docs.kalshi.com/getting_started/historical_data.md | 2026-10-19T04:19:01Z | 200 | 6,284 | `547782c580ec46acf8d4b84fe2fa3636d5f74104e57f394772496edba1fc37de` | VERIFIED-BY-DOC (byte-identical to the 2026-10-15 snapshot prefix `547782c580ec46ac`) |
| https://docs.kalshi.com/asyncapi.yaml | 2026-10-19T04:18:27Z | 200 | 175,841 | `9edefced7ca008b3e5225a11b8db2b56974efc8efc2c6918b66de118f048259f` | VERIFIED-BY-DOC (`info.version: 2.0.0`) |

## Trades

Endpoints: `GET /markets/trades` (live tier), `GET /historical/trades` (before `trades_created_ts`); `limit` 1–1000, cursor, `ticker`, `min_ts`, `max_ts`, `is_block_trade`. Live/historical boundary: query both and de-duplicate by `trade_id`.

| Field (schema `Trade`, re-extracted 2026-10-19) | Type | Semantics | PMV class |
|---|---|---|---|
| `trade_id` | string (REST; WS: uuid) | "Unique identifier for this trade" | DIRECT |
| `ticker` | string | market ticker | DIRECT |
| `count_fp` | fixed-point string | contracts | DIRECT |
| `yes_price_dollars`, `no_price_dollars` | strings | trade price per leg | DIRECT (prediction-market last trade) |
| `taker_outcome_side` {yes,no}; `taker_book_side` {bid,ask} | enum | aggressor side | DIRECT |
| `taker_side` | enum | deprecated | — |
| `created_time` | date-time | "Timestamp when this trade was executed"; precision not stated | DIRECT (exchange event time) |
| `is_block_trade` | bool | off-book block trade, included by default | DIRECT (filter for on-book flow) |

No `market_id`, no sequence number in REST trades. No receipt time. Whether one aggressor order across levels produces one or several prints is UNRESOLVED.

## Candlesticks

`GET /series/{s}/markets/{t}/candlesticks` and `GET /historical/markets/{t}/candlesticks`; `period_interval` ∈ {1, 60, 1440} minutes: **1-minute minimum granularity**.

| Field | Live schema | Historical schema | PMV class |
|---|---|---|---|
| `end_period_ts` | int (inclusive end) | same | — |
| `yes_bid` OHLC | `open_dollars`… | `open, low, high, close` (`BidAskDistributionHistorical`) | DIRECT: **the only historical bid/ask information Kalshi provides** (1-min OHLC of the best bid) |
| `yes_ask` OHLC | as above | as above | DIRECT (historical best-ask OHLC) |
| `price` OHLC, `mean`, `previous` | `_dollars` suffixes; `mean_dollars` "Mean traded YES contract price" | `open, low, high, close, mean, previous`; `mean` "Volume-weighted average price" | DERIVABLE from trades (except `previous`) |
| `volume`, `open_interest` | `_fp` | integers | volume DERIVABLE from trades; `open_interest` SOURCE_SPECIFIC (not derivable from public trades) |

How `yes_bid`/`yes_ask` OHLC are sampled (every BBO change or periodic snapshots) is UNRESOLVED. Live and historical candle schemas differ (separate parsers).

Further parser and leakage requirements (review API-B10-06/07):
- **Availability:** `end_period_ts` is the inclusive end, so a candle is usable only after `end_period_ts` plus publication lag. The live candle is mutable.
- **Synthetic candle:** `include_latest_before_start` prepends a synthetic candle (null OHLC, `previous_price` carried forward). Flag it; never ingest it as an observation.
- **Spread** from bid/ask OHLC is exact only at minute boundaries (open and close are simultaneous across sides; high and low are not).
- `previous` is derivable from trades (last trade before the period). Whether block trades are included in candle price OHLC is UNKNOWN, which matters for reconciliation with trades.
- Batch `/markets/candlesticks` allows `period_interval` ≥ 1 with no enum (still at least 1 minute).
- **Other documented endpoint:** `GET /series/{s}/events/{t}/forecast_percentile_history` accepts `period_interval` 0 ("5-second intervals"). It is authenticated and event-level, and its relationship to quotes is undocumented: UNKNOWN. The claim below ("the only historical quote evidence") holds among documented **public** endpoints.

## Timestamps and history

- `created_time` is the only trade time; receipt time is ABSENT historically.
- Historical tier exists for markets settled before `market_settled_ts` and trades before `trades_created_ts`; the cutoff lag and earliest date are not documented (B09 owner sheet: back to about 2021-06, OWNER_VERIFY).
- **No historical order book exists** (no L2 history endpoint). The historical book is limited to 1-minute bid/ask OHLC plus trade prints.

## Redundancy

- Candle `price` OHLC/VWAP/volume: DERIVABLE from trades → QA/reference only.
- Candle `yes_bid`/`yes_ask` OHLC and `open_interest`: SOURCE_SPECIFIC → **must be acquired** (the only historical quote evidence; required to estimate executable entry prices at the ask in development, with the 1-minute-resolution caveat: the intra-minute ask path is unknown, so entry-price evidence is bounded, not exact).
- Trades and candles together are the minimum Kalshi historical set; prospective WS capture (`kalshi_orderbook.md`) is the only source of tick-level book and receipt time.

## Open questions

Trade-time precision; `min_ts` units and ordering; candle bid/ask sampling rule; historical depth; licence (M1). All need either Kalshi clarification or a first licensed sample.
