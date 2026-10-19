# Polymarket (international, polymarket.com) — markets metadata, CLOB book, market WebSocket, Data API, reference-price feeds

**Status:** SCHEMA INSPECTED (official docs on `docs.polymarket.com`: Mintlify `.md` pages and embedded OpenAPI/AsyncAPI, read verbatim; no sample). Samples ACCESS BLOCKED (`clob.polymarket.com`, `gamma-api.polymarket.com`, `data-api.polymarket.com`, `ws-subscriptions-clob.polymarket.com`, `ws-live-v2.polymarket.com`, `polymarket.com`, `www.polymarket.com`; none requested). LICENSE GATED for the reference-price feeds (CLOB API credentials) and licence UNKNOWN for all data (terms not read). US persons: polymarket.com is **close-only** for the US (VERIFIED-BY-DOC); Polymarket US is a separate venue whose docs are not on this host.

Recon by agent `refs` (claude-opus-5-5), B10, 2026-10-19. Documentation only, under the owner B10 charter (official public API documentation). No market values are recorded here. Doc example payloads are cited only for field names and units.

**Evidence** (retrieved 2026-10-19 UTC, all HTTP 200; raw bytes under `$TMPDIR/b10_refs/pm/`, outside the repository)

| URL (docs.polymarket.com) | retrieved UTC | HTTP | bytes | sha256 | grade |
| - | - | - | - | - | - |
| /llms.txt | 04:21:52 | 200 | 15077 | 207f86f4cae9b684fdaa04f9e4ad3287c4d0f46e4b2af63792ae9bbcd2612d14 | index |
| /_llms/en/api-reference/predictions.txt | 04:21:58 | 200 | 28032 | ee72a2ab5d10d9c4a1b8a6c7532db037dfe090f91b09f2f03e0b2cef9200bd10 | index |
| /concepts/resolution.md | 04:22:06 | 200 | 7545 | 2264660d3f55b7d3df875d73b68098d7d62c1489cdd252bd846932e3088cd047 | VERIFIED-BY-DOC |
| /concepts/prices-orderbook.md | 04:22:08 | 200 | 4864 | f3f23f21862272a505f098b3703c8954a52719f0dc45eb9c71bc7231b5ce0380 | VERIFIED-BY-DOC |
| /market-data/market-details.md | 04:22:12 | 200 | 30471 | 00be2ab64b017c31524715c4ae43c08571e5bfa444e77ee885d0adc388aafd99 | VERIFIED-BY-DOC |
| /market-data/prices-order-books.md | 04:22:10 | 200 | 38860 | 438b620f7ac6c856c03444ac4f0d5893938c30510f533a25e0068907cec704cd | VERIFIED-BY-DOC |
| /market-data/realtime-data.md | 04:22:09 | 200 | 61150 | adcc641bde699fc6e2196e80a84e21b680aa0d36b30183b29b753c910dd5671e | VERIFIED-BY-DOC |
| /api-reference/markets/get-market-by-id.md (Gamma OpenAPI) | 04:22:18 | 200 | 27994 | 1a52ff01572c8a39e176432c0720ed0bc27aca31a9ec1122885a7c4c8b778b52 | VERIFIED-BY-DOC |
| /api-reference/events/get-event-by-id.md (Gamma OpenAPI) | 04:22:19 | 200 | 28084 | 896e3f4b6533aebfa0fcdc779a3ad9532f08f32ccda838e015c8cd54ddfc468d | VERIFIED-BY-DOC |
| /api-reference/market-data/get-order-book.md (CLOB OpenAPI) | 04:22:16 | 200 | 5803 | 85a606166da518d9c85523406bfeeeae76f4f069171320ea3b8c6c906974fcc4 | VERIFIED-BY-DOC |
| /api-reference/wss/market.md (AsyncAPI) | 04:22:14 | 200 | 44907 | 0828ba0ecbff80d9e611f6ceb3922ef48a9cd794feab97ede1ab879d7cbd5a79 | VERIFIED-BY-DOC |
| /api-reference/live-data/overview.md (PolyBolt) | 04:22:15 | 200 | 10311 | 0d1ead0547430d2b9411f7bc1cb5eb3a32482d205044f6f827f3ed915f35f2b5 | VERIFIED-BY-DOC |
| /api-reference/wss/polybolt.md (AsyncAPI) | 04:22:14 | 200 | 83227 | c3870cb5efb7aca23893f353646ce9d36128bdd3b34dfc4aa311972cf38c264e | VERIFIED-BY-DOC |
| /api-reference/markets/get-prices-history.md (CLOB, legacy) | 04:22:17 | 200 | 3898 | e8e811fc15da9cedc750732e85db65ac4049a7d373ed264a2a7bace9d559d98d | VERIFIED-BY-DOC |
| /api-reference/markets/get-a-tokens-price-history.md (Data API v2) | 04:22:17 | 200 | 22870 | dbd5e33956200540998dd8f99a361ff12cafc28de019ccc562170ac7b2582faa | VERIFIED-BY-DOC |
| /api-reference/feeds/list-trades.md (Data API v2) | 04:22:20 | 200 | 17024 | 507b47690c31d7d47657b667d304868e2d86aa959d368a42644691fa78ec2b5d | VERIFIED-BY-DOC |
| /trading/fees.md | 04:22:13 | 200 | 6189 | 7409b13c646126ff1c3bacc478c0594a7b3db2a2e735fcdf6ddb59b3fdc44035 | VERIFIED-BY-DOC |
| /api-reference/geoblock.md | 04:22:23 | 200 | 6154 | 0497c110220bd31c69acedcffbe478ff3c28c9b4a2c59bca45ab9028567cf0c3 | VERIFIED-BY-DOC |
| /changelog/predictions.md | 04:22:25 | 200 | 33010 | ff37e36331c9b7766e55f9aeda0077e6b3b354a95b635561f124c412ff7b11cd | VERIFIED-BY-DOC (dated vendor claims) |
| `research/historical_data/inventory_prediction_markets.md`, `research/data_sources/inventory_pm_gold_detail.md`, `master_source_inventory.md` | Git | — | 42170 / 43519 / 49175 | ecf63ac8… / 4767a498… / 6e57277c… | repo-Git (mixed G/S) |

Fetched and skimmed but not relied on: `concepts/markets-events.md`, `concepts/positions-tokens.md`, `market-data/overview.md`, `api-reference/core/get-trades-for-a-user-or-markets.md` (v1), `api-reference/data-api/overview.md`, `get-resolution-state.md`, `get-fee-rate.md`, `get-clob-market-info.md`, `migrate/rtds-to-polybolt.md`, `api-reference/predictions/overview.md`, `trading/matching-engine.md`.

## Access and connectivity

| Service | Host (from docs) | Auth (docs) | PMV status |
| - | - | - | - |
| Gamma (markets/events/series metadata) | `gamma-api.polymarket.com` | public | BLOCKED (deny list), not requested |
| CLOB REST (book, prices, spreads, tick, fee rate) | `clob.polymarket.com` (staging `clob-staging.polymarket.com`) | public for market data (`security: []`) | BLOCKED, not requested |
| Market WebSocket | `wss://ws-subscriptions-clob.polymarket.com/ws/market` | public | BLOCKED (ws-* class), not requested |
| Data API v2 (trades, prices-history, positions, resolutions) | `data-api.polymarket.com/v2` | "Auth: none. All data routes are public" | BLOCKED, not requested |
| PolyBolt reference prices | `wss://ws-live-v2.polymarket.com/ws` | "Subscriptions require CLOB API credentials" | BLOCKED. Credentials mean a wallet-linked account: credentialed class |
| RTDS (legacy reference prices) | per migration guide | — | "RTDS is legacy" for reference prices |

**US persons (VERIFIED-BY-DOC, geoblock page):** the US (`US`) and US Minor Outlying Islands (`UM`) are listed under "Regulatory-Restricted Jurisdictions (Close-Only on Frontend and API)": "Users can close existing positions but cannot open new ones, on both the frontend and the API." Polymarket US (a CFTC-regulated venue; `docs.polymarket.us`, previously refused by the proxy) is **not documented on docs.polymarket.com**. Repo SECONDARY: PM-US BTC 15-minute markets since about 2026-09-22, settlement source CONFLICTING (BRTI vs Chainlink), no public trade tape, and the rulebook bars redistribution. If the owner is a US person (F-16), polymarket.com is research-only. It can never be an execution venue for PMV without a jurisdiction change, and PM-US is a different market with a different book.

## Transport, format, compression, delivery (historical vs live)

- **Live book:** market WS. JSON. Subscribe `{"assets_ids": [...], "type": "market"}`, optional `initial_dump` ("Whether to send an initial orderbook snapshot on subscribe. Defaults to true."), `level` (enum 1/2/3, "Subscription level. Defaults to 2."; **the meaning of each level is not documented**), and `custom_feature_enabled` ("Enable best_bid_ask, new_market, and market_resolved events."). Heartbeat: "Send the text frame `PING` every 10 seconds; the server replies with `PONG`."
- **Snapshot REST:** `GET /book?token_id=`, `POST /books` (batch), `/price`, `/midpoint`, `/spread`, `/last-trade-price`, `/tick-size`, `/fee-rate`.
- **Historical:** **no historical order book from the venue.** Price history only:
  - Legacy CLOB `GET /prices-history`: `market` (asset id), `startTs`/`endTs` ("unix timestamp"), `interval` enum `max, all, 1m, 1w, 1d, 6h, 1h`, `fidelity` ("Accuracy of the data expressed in minutes. Default is 1 minute."). Response `history[] {t: uint32, p: number}`.
  - Data API v2 `GET /v2/prices-history` (changelog 2026-09-04: "replaces the CLOB-hosted route"): window forms `start`/`end` (cap 15 days), `interval`, or `as_of`; `bucket_seconds` 60…86400; cursor pagination. **Retention by grain:** "The 3-hour and 12-hour series are permanent (back to 2022-11-18); … 1-minute data at least 7 days, 5-minute at least 60, 30-minute at least 90." A resolved market's series ends with a settlement point (0/1/fractional) at `resolution_seconds` 0.
  - Data API v2 `GET /v2/trades`: on-chain fills, keyset-paginated by `(block_timestamp, sequence_id)`.
- **Consequence:** sub-minute Polymarket history exists only as one's own (or third-party) WS capture. 1-minute price history ages out after about 7 days. For short-horizon BTC up/down research, Polymarket history is essentially **prospective-capture-only** at useful resolution (consistent with repo `inventory_open_academic_regulatory.md` key finding 2).

## Fields

### Gamma market (OpenAPI `Market`; most properties have no description in the spec)

| field | native type | official semantics | PMV class | notes |
| - | - | - | - | - |
| `id` | string | Gamma market id | SOURCE_SPECIFIC | |
| `question` | string? | market question | SOURCE_SPECIFIC | "The market title describes the question, but the **rules** define how it resolves." |
| `conditionId` | string | on-chain condition id (WS `market` = "Condition ID of the market") | DIRECT (identity) | |
| `slug` | string? | URL segment | SOURCE_SPECIFIC | |
| `outcomes` | string? | "Outcome labels and prices are JSON-encoded strings. Parse them into arrays; entries at the same index describe the same outcome." | DIRECT | "For these binary markets, index `0` is YES and index `1` is NO." For up/down markets the labels are presumably Up/Down (UNVERIFIED) |
| `outcomePrices` | string? | JSON-encoded string, index-aligned | PROXY (display price) | Display price is the midpoint, or the last trade if the spread > $0.10 (concepts page) |
| `clobTokenIds` | string? | JSON-encoded token id array for CTF (`v1`) | DIRECT (identity) | "Use `market.version` to select the identifiers: `positionIds` is already an array for Polymarket Protocol V2 (`v2`); parse `clobTokenIds` for CTF (`v1`). Both fields can be populated, so their presence does not select the protocol." |
| `positionIds` | string[]? | V2 outcome identifiers | DIRECT (identity) | Protocol V2 (CLOB V2 live 2026-04-28; pUSD collateral) |
| `version` | string? | `v1` (CTF) / `v2` | SOURCE_SPECIFIC | "Treat versions other than `v1` and `v2` as unsupported." |
| `startDate`, `endDate`, `startDateIso`, `endDateIso` | date-time? | not described. Resolution page: "End date — When the market is eligible for resolution" | PROXY (timing) | **Whether `endDate` equals the up/down window end is UNVERIFIED** |
| `eventStartTime` | date-time? | not described | UNKNOWN | Candidate for the up/down window start (INFERENCE) |
| `closedTime`, `acceptingOrdersTimestamp` | string? | not described | SOURCE_SPECIFIC | |
| `resolutionSource` | string? | "Where the outcome will be determined from" | DIRECT (rule metadata) | Free text |
| `description` | string? | rules text (INFERENCE) | DIRECT (rule metadata) | Per-market rules must be read |
| `active`, `closed`, `archived`, `acceptingOrders`, `enableOrderBook`, `negRisk` | boolean? | state. "`isTradeReady = state.active && !state.closed && state.acceptingOrders`" | DIRECT (state) | Current state only: POST_HOC for history (repo H-4) |
| `orderPriceMinTickSize` | number | "Minimum price increment for limit orders. Prices must be multiples of this value." | DIRECT | Can change (`tick_size_change`) |
| `orderMinSize` | number | "Minimum order size in USDC." | DIRECT | |
| `feesEnabled`, `feeSchedule{rate, exponent, takerOnly, rebateRate}` | bool / object | "Base rate used in the fee calculation"; "Exponent applied to the price component of the fee curve"; "fees are charged to the taker side only"; "Fraction of taker fees rebated back to the resting maker" | DIRECT (cost) | |
| `bestBid`, `bestAsk`, `lastTradePrice`, `spread`, `umaResolutionStatus`, `automaticallyResolved`, `resolvedBy`, `questionID` | various | not described | SOURCE_SPECIFIC | Snapshot fields; not point-in-time |

### CLOB REST `GET /book` (OpenAPI `OrderBookSummary`)

| field | type | semantics (quoted) | PMV class |
| - | - | - | - |
| `market` | string | "Market condition ID" | DIRECT |
| `asset_id` | string | "Token ID (asset ID)" | DIRECT |
| `timestamp` | string | "Timestamp of the order book snapshot" (example `'1234567890'`; **unit not stated** in the REST spec) | DIRECT (time; unit UNKNOWN) |
| `hash` | string | "Hash of the order book summary". Guide: "Compare it with the previous response's hash to determine whether the book changed between reads." | SOURCE_SPECIFIC (change detection, not a checksum algorithm) |
| `bids` / `asks` | `OrderSummary[] {price: string, size: string}` | OpenAPI: bids "sorted by price descending", asks "sorted by price ascending" | DIRECT (L2, aggregated) |
| `min_order_size`, `tick_size` | string | "Minimum order size"; "Minimum price increment (tick size)" | DIRECT |
| `neg_risk` | boolean | "Whether negative risk is enabled for this market" | SOURCE_SPECIFIC |
| `last_trade_price` | string | "Last trade price" | DIRECT |

**CONFLICT (sort order):** the guide (`market-data/prices-order-books.md`) says "Bids are ordered by ascending price and asks by descending price, so the best bid and ask are the last entries in their respective arrays". The OpenAPI says the opposite. The WS `book` example lists bids ascending. A parser must sort explicitly and never rely on array position.

### Market WebSocket messages (AsyncAPI `market` channel)

| `event_type` | fields | timestamp | notes |
| - | - | - | - |
| `book` | `asset_id`, `market` (condition id), `bids[]`, `asks[]` (`{price, size}` strings: "Price level (e.g., '0.50')", "Total size at this price level"), `timestamp`, `hash` ("Hash of the orderbook content") | `timestamp` string, "Unix timestamp in milliseconds" | "Full aggregated orderbook for an asset". Snapshot on subscribe (`initial_dump`) |
| `price_change` | `market`, `price_changes[] {asset_id, price ("Price level affected"), size ("New aggregate size (0 means level removed)"), side, hash ("Hash of the order that caused this change"), best_bid, best_ask}`, `timestamp` | ms string | "Delta update to orderbook price levels when an order is placed or cancelled". **Absolute** new level size (VERIFIED-BY-DOC), unlike Kalshi's relative deltas. One message can carry several assets |
| `last_trade_price` | `asset_id`, `market`, `price` ("Trade execution price"), `size` ("Trade size"), `fee_rate_bps` ("Fee rate in basis points"), `side` ("From taker's perspective"), `timestamp`, `transaction_hash` | ms string | Taker side given. Trade id not in schema |
| `tick_size_change` | `asset_id`, `market`, `old_tick_size`, `new_tick_size`, `timestamp` | ms string | "Market tick size update when price approaches limits". Matters for the 0.93–0.97 band, where tick changes can occur |
| `best_bid_ask` | `asset_id`, `market`, `best_bid`, `best_ask`, `spread`, `timestamp` | ms string | Requires `custom_feature_enabled: true` |
| `new_market` | `id`, `question` (described as "Condition ID", an apparent doc error), `slug`, `description`, `assets_ids`, `outcomes`, `event_message{id,ticker,slug,title,description}`, `tags`, `condition_id`, `active`, `clob_token_ids`, `order_price_min_tick_size`, `group_item_title`, sports fields, `timestamp` | ms | Requires `custom_feature_enabled` |
| `market_resolved` | `winning_asset_id`, `winning_outcome`, (`market`, `timestamp`) | ms | Requires `custom_feature_enabled`. The venue outcome event (label source candidate) |

### Data API v2 trade row (`GET /v2/trades`)

`condition_id` ("On-chain condition id of the market"), `token_id` ("CLOB asset id of the traded outcome token"), `outcome`, `outcome_index` (`999` = could not be determined), `price` ("Execution price per share, in USDC"), `size` ("Filled quantity in shares; bare sizes are shares, never USD"), `side` ("`BUY` or `SELL`, from this wallet's perspective"; **not** the aggressor side), `timestamp` ("Block timestamp of the fill, epoch seconds"), `transaction_hash`, `proxy_wallet`, profile fields (`name`, `pseudonym`, `bio`, images), `slug`, `event_slug`, `title`. Classes: price/size/timestamp DIRECT (seconds precision; block time, not match time); side PROXY; profile fields SOURCE_SPECIFIC (personal-data adjacent; do not store without need).

### Data API v2 price-history point

`timestamp` ("The OBSERVATION's own time, epoch seconds … an aggregate reports its bucket start"), `price` ("Price in the range 0…1"), `resolution_seconds` ("`0` for an exact tick, the bucket width for an aggregate … This is the ONLY thing the payload says about provenance, deliberately."). **What "price" is (mid, last trade, or display price) is not documented: UNKNOWN.** Class: PROXY.

### PolyBolt reference prices (credentialed)

Channels: `price.crypto`, `price.equity` (includes `xauusd`, `xagusd`), `price.crypto.twap` ("60-second time-weighted average prices (TWAP) from Chainlink"; symbols `btcusd`, `ethusd`, `solusd`, `xrpusd`, `dogeusd`, `hypeusd`, `bnbusd`, `zecusd`; "Only 60 exists today"), `price.equity.twap`. Envelope: `v`, `channel`, `seq` ("Dense per-connection, per-channel sequence … Resets on every reconnect"), `ts` ("Producer event time, Unix milliseconds"), `snapshot`, `dropped` (slow-consumer frame count). Payload: `symbol`, `value` (float, "Prefer full_accuracy_value"), `full_accuracy_value` ("Exact decimal price as published by the source"), `timestamp` ("Source event time, Unix milliseconds"), `window_seconds`, `source` (`pyth` / `massive` / `chainlink`), and for `price.crypto` updates `receivedAt`, `isCarriedForward`. Snapshot: "the previous two minutes of points". **There is no history beyond 2 minutes.**

## Timestamps

- Market WS: every message has `timestamp`, "Unix timestamp in milliseconds" (string). Whether it is matching-engine time or publish time is **not stated**. No receipt time is provided, so PMV must stamp receipt.
- REST book `timestamp`: unit not stated (UNKNOWN; probably ms, by analogy).
- Data API trades: block timestamp in **seconds**, so it differs from the WS `last_trade_price` ms time (match vs chain inclusion). Repo research (Dubach 2026, arXiv:2604.24366) documents feed-vs-chain disagreement and ingestion delays.
- PolyBolt: `ts` producer event time and payload `timestamp` source event time (ms); `receivedAt` on `price.crypto`.
- **Execution timing (VERIFIED-BY-DOC, changelog):** "The taker delay on crypto markets is now `150ms`, up from `50ms`", effective 2026-09-04 14:00 UTC (earlier 250 ms → 50 ms on 2026-08-17). A taker order on crypto markets is held about 150 ms before matching, so PMV's latency model must include it. It also changes over time: a regime variable.

## Sequencing and book semantics

- **No sequence number on the market WS** (none in the AsyncAPI). Gap detection relies on the `book` `hash` and on re-snapshot (re-subscribe or REST `/book`). The hash algorithm is not documented. It is "Hash of the orderbook content" for snapshots, while `price_change.hash` is "Hash of the order that caused this change": **two different meanings under one field name.** No documented way exists to verify a locally maintained book against the `book` hash after applying deltas. That is UNKNOWN and needs a test in capture.
- Book depth: aggregated price levels (MBP, full depth as served; no depth cap documented). No order-level (MBO) data. `level` 1/2/3 semantics undocumented.
- `price_change` gives the absolute new size per level, plus `best_bid`/`best_ask` after the change. Replay is idempotent per level.
- YES/NO books: each outcome token has its own book (`asset_id`). Whether the venue mirrors complementary liquidity (YES bid at p = NO ask at 1−p) into each book is not stated in the fetched pages (UNKNOWN). Do not double-count.
- PolyBolt has a dense `seq` per connection and channel, resetting on reconnect, plus a `dropped` counter.

## Instrument / contract identity, expiry, reference-end, settlement/reference fields

- **Crypto up/down resolution (VERIFIED-BY-DOC):** "Polymarket uses two **Resolution Sources**, UMA for prediction markets and Chainlink TWAP for up-down markets." "Each market specifies an asset pair, a start time, and a duration … The TWAP at the start sets the **price to beat**. When the duration ends, the TWAP at that time sets the **final price**. Both values come from the same **Chainlink TWAP stream**." "The market resolves **Up** when the final price is **equal to or greater** than the price to beat, and **Down** when it is **lower**." No UMA process.
- **TWAP window history (VERIFIED-BY-DOC, changelog):** 2026-08-07: "Crypto up/down markets now resolve using Chainlink-computed time-weighted average prices instead of a single price snapshot … 5-minute markets use a `30-second` lookback; 15-minute and 4-hour markets use a `60-second` lookback." 2026-08-14 00:00 UTC: 5-minute markets moved to 60 s. **Regime breaks:** before 2026-08-07, single snapshot (repo SECONDARY: Chainlink Data Streams BTC/USD); 30 s for 5-minute markets 08-07 to 08-14. Whether **1-hour** markets use TWAP is not named in the changelog (the resolution page's example is "a specific one-hour window"): UNRESOLVED, read per-market rules. Repo SECONDARY says hourly/daily markets may use a Binance BTCUSDT 1 h candle. CONFLICT, UNRESOLVED.
- **TWAP timestamp alignment:** whether "the TWAP at the start" means the TWAP whose window ends at the start time (i.e. the 60 s before the start) is not stated (INFERENCE: trailing window).
- **Gold:** Polymarket gold is daily only (repo SECONDARY): "XAUUSD Daily Up or Down" on Pyth `Metal.XAU/USD` 1-min close at 4:59 PM ET; "GC Up or Down" on CME daily settlement. PolyBolt `xauusd` vendor is Pyth/Chainlink/Massive. Pyth docs confirm Polymarket uses a Pyth Pro package including XAU. **No Polymarket 15-min to 1-hour gold markets are documented**, so Polymarket is not a gold venue for PMV's horizon.
- **Payout:** "Winning tokens become redeemable for \$1.00 each"; UMA "Unknown/50-50 … each token redeems for \$0.50" (UMA markets only). Collateral is pUSD (V2) / USDC.

## Fees (VERIFIED-BY-DOC)

"`fee = C × feeRate × p × (1 - p)`"; "**Makers are never charged fees.** Only takers pay fees." Crypto: taker fee rate `0.07`, maker rebate 20%. "Fees are rounded to 5 decimal places. The smallest fee charged is **0.00001 USDC**." Per-market parameters are in `feeSchedule` (with an `exponent`, so the curve can differ from the p(1−p) table; read per market). In PMV's band the fee per share is 0.07 × p(1−p) (C shares cost C times that), which falls toward the extremes. Break-even must use the executable ask, this fee, and the 150 ms taker delay. Tax treatment for a non-US offshore venue is a separate open issue (Phase 4.5).

## Licence / access gating

- Market data endpoints are public (no key). The Polymarket terms and any data licence were **not read**. The repo records that the docs' terms live on a refused host, so licence status stays UNKNOWN / NEEDS_LICENCE_CLARIFICATION (`master_source_inventory.md` PM-08, PM-11; INV-5: "Polymarket scope tied to F-16").
- Reference prices need CLOB API credentials (wallet-linked account): credentialed class; vendor redistribution rights (Chainlink, Pyth, Massive) UNKNOWN.
- Protected-information class: Polymarket BTC books and Chainlink TWAP are equivalent observables of protected BTC windows (the TWAP is a direct settlement-reference input for Polymarket BTC). Both need catalog entries before real-data use (RT-B3-05).

## PMV relevance: unique vs derivable

- **Unique:** Polymarket's own order book and flow for its contracts (a separate crowd and liquidity pool, 150 ms taker delay, fee curve). The `market_resolved` outcome for its markets. The Chainlink TWAP reference stream (2-minute snapshot only).
- **Derivable:** underlying BTC velocity (from exchanges). The Polymarket "price" series and display prices (from the book). Fee costs (from `feeSchedule`).
- Schema richness is not predictive evidence. No predictive claim is made.

## Comparison I — Kalshi vs Polymarket: unique state, cross-venue information, or another estimate of the same probability?

| Dimension | Kalshi KXBTC15M | Polymarket BTC 15-min Up/Down |
| - | - | - |
| Reference | CF Benchmarks **BRTI** (depth-weighted mid of about 7 USD exchanges), 60 s average before close vs before open (rulebook UNRESOLVED; trimmed or plain mean by regime) | **Chainlink Data Streams BTC/USD TWAP**, 60 s lookback, since 2026-08-07 (VERIFIED-BY-DOC). Before: single snapshot |
| Tie rule | YES on tie (SECONDARY) | Up on "equal to or greater" (VERIFIED-BY-DOC) |
| Window grid | Quarter-hour closes :00/:15/:30/:45 (Kalshi channel design, G) | Start time plus duration per market. Grid alignment to quarter-hours is UNVERIFIED (Gamma `eventStartTime`/`endDate` semantics undocumented) |
| Book data | Sequenced snapshot + relative deltas (Kalshi WS) | Unsequenced snapshot + absolute deltas + hash |
| Costs | Kalshi fee schedule | Taker fee 0.07·p(1−p) per share; makers free; 150 ms taker delay |
| PMV access | Primary venue | US persons: close-only. PM-US is a separate venue |

Assessment (INFERENCE unless marked; untested):

1. **Mostly another estimate of nearly the same event.** Where windows coincide, both contracts ask whether BTC is higher at the end of the window than at the start, measured by two different 60 s averages of two different composite references. BRTI and the Chainlink BTC/USD stream are both multi-source aggregates of largely overlapping liquid venues. Over 15 minutes they should agree on direction except when the move is within a small basis. So Polymarket's mid is mostly a second crowd estimate of a highly correlated probability, not independent information about BTC.
2. **Where it could be unique:** (a) the reference basis, BRTI-average minus Chainlink-TWAP near the strike. It can make the two contracts resolve differently, which is a cross-venue *mispricing* opportunity (near-arbitrage), not a predictive signal. (b) Lead-lag between the two crowds' quotes, which is untested and confounded by fees, the 150 ms taker delay, and thin books. (c) Differences in participant mix. None is established, and PMV may not be able to trade the Polymarket side at all (US close-only).
3. **Window alignment is unverified.** Without confirmed identical start and end times, cross-venue comparisons may mix different windows. That needs Gamma metadata and per-market rules (blocked host).
4. **Reference mismatch has a regime history** (pre-2026-08-07 snapshot; 30 s vs 60 s for 5-minute markets) that any historical comparison must partition.
5. **Recommendation:** **defer Polymarket until Kalshi-only research shows an edge.** Reasons: polymarket.com is close-only for US persons; sub-minute Polymarket history needs prospective capture; licence and terms are unread; and its likely contribution is a correlated second estimate. If a Kalshi edge is found, a bounded prospective capture of the Polymarket market WS (BTC up/down books) plus `market_resolved` could test cross-venue features as a later experiment (owner decision, F-16). This matches existing repo guidance (INV-5; Polymarket deferred to Tier 2). Urgency: optional, not blocking.

## Open questions / unverified items

1. Meaning of WS `level` 1/2/3; hash algorithm; whether a local book can be verified against `book.hash`.
2. Book sort-order CONFLICT (guide vs OpenAPI).
3. REST `/book` `timestamp` unit; whether WS `timestamp` is match or publish time.
4. Gamma `eventStartTime`/`startDate`/`endDate` semantics for up/down windows; quarter-hour alignment with Kalshi.
5. Whether 1-hour BTC up/down markets use the Chainlink TWAP or a Binance candle (CONFLICT).
6. TWAP alignment: whether the "TWAP at the start" is the trailing 60 s ending at the start.
7. What the Data API price-history `price` is (mid, last, display).
8. Polymarket terms of use and data licence (not read); PM-US docs (`docs.polymarket.us`, previously refused) and settlement source.
9. Complementary YES/NO book mirroring.
