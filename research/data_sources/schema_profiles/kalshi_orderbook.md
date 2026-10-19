# Kalshi — order book (REST snapshot and WebSocket `orderbook_delta`), `ticker`, `trade`, lifecycle, reference channels

**Status:** **SCHEMA INSPECTED** (AsyncAPI 2.0.0 and OpenAPI 3.34.0 re-fetched 2026-10-19; verbatim evidence in `research/kalshi/api_documentation_findings.md` §3.4, §4, §5, §11). Samples **ACCESS BLOCKED** (`api.elections.kalshi.com`, sandbox deny list; the WS endpoint is on the same host and needs an API key for every connection). **LICENSE/CREDENTIAL GATED** (KYC account and API key; M1). A `read`-scoped key suffices for WS market data, but no market-data-only scope exists: `read` also exposes portfolio, fills, and positions. Treat it as a class-5 credential and never request `write` (review API-B10-08).

## Evidence

| URL | Retrieved (UTC) | HTTP | Bytes | SHA-256 | Grade |
|---|---|---|---|---|---|
| https://docs.kalshi.com/asyncapi.yaml | 2026-10-19T04:18:27Z | 200 | 175,841 | `9edefced7ca008b3e5225a11b8db2b56974efc8efc2c6918b66de118f048259f` | VERIFIED-BY-DOC |
| https://docs.kalshi.com/websockets/orderbook-updates.md | 2026-10-19T04:19:01Z | 200 | 19,300 | `202c05a742b81ca244f32b689e24c73c8776128abc2efdf18167d17f5cdbecca` | VERIFIED-BY-DOC |
| https://docs.kalshi.com/getting_started/orderbook_responses.md | 2026-10-19T04:19:01Z | 200 | 8,513 | `a87d1a2b795b7fc06c9f57222ba95542a450fc987f90f2c10396af2fa2628c85` | VERIFIED-BY-DOC (byte-identical to the 2026-10-15 snapshot prefix) |
| https://docs.kalshi.com/websockets/cfbenchmarks-value.md | 2026-10-19T04:19:02Z | 200 | 25,755 | `1a5ec2239e3229a5cae58bb8c7a6ffd4a7d8c57837188b5ebd5bb114fbaa7194` | VERIFIED-BY-DOC |
| https://docs.kalshi.com/websockets/pyth-value.md | 2026-10-19T04:19:02Z | 200 | 26,244 | `70c0e8062402b316e6398bf86e079eafb74ca905606c1f8a60858664f11a0a5b` | VERIFIED-BY-DOC |

## REST order book

`GET /markets/{ticker}/orderbook` (depth 0–100) → `orderbook_fp {yes_dollars: [[price, count]…], no_dollars: […]}`: **bids only** on each leg. "A **NO BID** at price Y is equivalent to a **YES ASK** at price ($1.00 - Y)". **No timestamp and no sequence number** in the response, so a REST snapshot cannot seed or be aligned to the WS stream. Current state only.

## WebSocket channels (market data)

| Message | Key fields | Sequenced | Time fields | PMV class |
|---|---|---|---|---|
| `orderbook_snapshot` | `market_ticker`, `market_id`, `yes_dollars_fp`, `no_dollars_fp` (each `[price, size]`; key absent when that side is empty) | `sid`, `seq` | `sending_ts_ms` only (no event time) | DIRECT: full L2 by price level, both legs |
| `orderbook_delta` | `price_dollars`, `delta_fp` ("Fixed-point contract delta"), `side` | `sid`, `seq` | `ts_ms` (optional; "when the orderbook change was recorded"), `sending_ts_ms` | DIRECT; `delta_fp` relative (strong inference; negative example values) |
| `ticker` | `yes_bid_dollars`, `yes_ask_dollars`, sizes, `price_dollars`, volume, OI | **not sequenced** (gaps undetectable) | `ts_ms` | DERIVABLE from book + trades (except OI, dollar volume) |
| `trade` | `trade_id` (uuid), prices, `count_fp`, `taker_outcome_side`, `taker_book_side`, `is_block_trade` | `sid`, `seq` | `ts_ms` | DIRECT |
| `market_lifecycle_v2` | `event_type` (created, activated, close_date_updated, determined, settled, …), `close_ts`, `determination_ts`, `settled_ts` (seconds), `result`, `settlement_value`, strikes (`metadata_updated`) | `sid`, `seq` | seconds-resolution `*_ts`, `sending_ts_ms` | DIRECT (point-in-time metadata) |
| `cfbenchmarks_value` (≈1 Hz) / `cfbenchmarks_value_5hz` | BRTI value, `avg_60s_data`, `last_60s_windowed_average_15min` (final minute before :00/:15/:30/:45 only) | `seq` | `source_ts_ms` (5 Hz), `received_at` (Kalshi receipt) | SOURCE_SPECIFIC: BRTI as Kalshi receives it; paid entitlement |
| `pyth_value` | Pyth metals including `Metal.XAU/USD`, `Metal.Index.GOLD/USD`, `Metal.Index.1OZGOLD/USD` | `seq` | `source_ts_ms`, `received_at` | SOURCE_SPECIFIC: Pyth gold as Kalshi receives it; paid ($1,000/month, repo) |

Book derived quantities: best bid (max YES bid), best ask (1 − max NO bid), spread, quoted size at best, L2 depth, imbalance: all DERIVABLE from snapshot + deltas.

## Sequencing and recovery

`seq`: "Sequential number that should be checked if you want to guarantee you received all the messages. Used for snapshot/delta consistency." Scope (per `sid` is the inference), behaviour of `get_snapshot` replies within the sequence, and the documented resync procedure are **UNRESOLVED**. Terminal errors 10 and 25 ("Subscription buffer overflow") require resubscription. Kalshi has **no book checksum** (contrast Kraken CRC32). Duplicate delivery, conflation, and cross-channel ordering are undocumented.

## Timestamps

| Time | Present | Meaning |
|---|---|---|
| Exchange event time | `orderbook_delta.ts_ms` (optional), `trade.ts_ms`, `ticker.ts_ms` | matching-engine time (inference from changelog pattern) |
| Kalshi send time | `sending_ts_ms` (optional in every schema) | "when Kalshi queued this message at the network layer" |
| Receipt time | only PMV's own clock | — |
| Reference source time | `source_ts_ms` (CFB 5 Hz, Pyth); `received_at` = Kalshi's receipt of the upstream tick | separates reference publication from Kalshi's view |

Snapshots carry no event time. Lifecycle times are whole seconds.

## History

No historical order-book, delta, or snapshot endpoint exists. Every Kalshi L2, quoted-size, and spread observation at sub-minute resolution, and every receipt timestamp, must come from **PMV's own prospective capture** (the B08 capture store; owner-authorized collection only). This is the only source of protected prospective evaluation data for the venue.

## PMV relevance

- Executable entry price for late-window high-probability contracts depends on the ask side and quoted size, which only this stream (or the 1-minute candle ask OHLC, coarsely) provides.
- CFB and Pyth channels give the reference as Kalshi receives it, with both upstream and Kalshi-receipt times: potentially the most faithful settlement-reference capture, subject to entitlement and licence.

## Open questions

`seq` scope and resync; delta semantics confirmation; whether `last_60s_windowed_average_15min` equals the contract settlement value (inference only); entitlement prices and rights for CFB/Pyth channels; licence (M1).
