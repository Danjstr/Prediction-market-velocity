# Pyth — gold/XAU price feeds (Pyth Core / Hermes and Pyth Pro, formerly Lazer)

**Status:** SCHEMA INSPECTED (official docs on docs.pyth.network, read verbatim; no sample). Samples and history ACCESS BLOCKED (`hermes.pyth.network`, `benchmarks.pyth.network`, `pythdata.app`; the Pro hosts `pyth.dourolabs.app`, `pyth-lazer*.dourolabs.app` were not requested because they serve market data). LICENSE GATED (API key and paid plan; no data licence text obtained). Gold index methodology NOT DOCUMENTED on docs.pyth.network.

Recon by agent `refs` (claude-opus-5-5), B10, 2026-10-19. Documentation only. This file holds no market values. Feed IDs and schedules are metadata.

**Evidence** (retrieved 2026-10-19 UTC, all HTTP 200 unless noted; raw bytes kept under `$TMPDIR/b10_refs/pyth/`, outside the repository)

| URL (docs.pyth.network) | retrieved UTC | HTTP | bytes | sha256 | grade |
| - | - | - | - | - | - |
| /llms.txt | 04:18:35 | 200 | 2365 | a5cd953bebb77825cf365b0299f50d2e77d4acfad09020d8b90966aafcdffb72 | VERIFIED-BY-DOC |
| /llms-price-feeds-core.txt | 04:18:40 | 200 | 8737 | 3bfe056b44f3162a2bd8468c8071ebec0f0a8d0cc293ba1e9e58ecefba079bf0 | VERIFIED-BY-DOC |
| /llms-price-feeds-pro.txt | 04:18:41 | 200 | 10923 | f29bb9956f63028dfbe402146e70dcab061c2e3edd15a6a5ab7b1057c376cf6c | VERIFIED-BY-DOC |
| /llms-price-feeds.txt | 04:18:41 | 200 | 3216 | 024f52fb8b58a0739c5b5077a5f588bf67fddc519ab8a42620a9189f34c60078 | VERIFIED-BY-DOC |
| /sitemap.xml | 04:19:47 | 200 | 20159 | 7ce399d109dde7b4ce0590ddd6471f9ef0afb640e14f67b82383c6cb981d8780 | page index |
| /price-feeds/pro/payload-reference.mdx | 04:18:58 | 200 | 16353 | 148972a9a654180cfc1d3a8e2fc0c0affee85e6eaf9daa514c375045b9a9faca | VERIFIED-BY-DOC |
| /price-feeds/pro/understanding-price-data.mdx | 04:19:00 | 200 | 10215 | 60c77037d3297d92b70c800794b750dfc6a925a5f66d86df251db9be0b097c90 | VERIFIED-BY-DOC |
| /price-feeds/pro/how-lazer-works.mdx | 04:19:01 | 200 | 4626 | 0ca8d7bc35780faf5fa7b34bd9bac411b5f2941763bfdca42b0171682a73841b | VERIFIED-BY-DOC |
| /price-feeds/pro/api/history.mdx | 04:19:02 | 200 | 10196 | cf531bc11a9f260ff7775d3a38422c48db26d3ba14fb8560306c3fddc2193caf | VERIFIED-BY-DOC |
| /price-feeds/pro/api/rest.mdx | 04:19:04 | 200 | 3630 | 374f3dc2dc4253e55dc35640f6a590c56b49e35e0f51df771e08e33a2b1f8dd5 | VERIFIED-BY-DOC |
| /price-feeds/pro/api/websocket.mdx | 04:19:05 | 200 | 1436 | d27446fb39fcd92d2b3e3d6f78d6748222a233948c74b1f1a8848a4a5302ee78 | VERIFIED-BY-DOC |
| /price-feeds/pro/price-feed-ids.mdx | 04:19:06 | 200 | 970 | bc3ae9ff26f84dad08b74d4be37dc1301607d5979a7897ee459fc43a2da82bee | VERIFIED-BY-DOC |
| /price-feeds/pro/faq.mdx | 04:19:07 | 200 | 12598 | b0d9f40c4059ae009e70ae12787bc47b115c741ac72bb9310f3bfd4090048108 | VERIFIED-BY-DOC |
| /price-feeds/pro/market-hours.mdx | 04:20:00 | 200 | 11989 | 6cab04b309c2f38b0cab4eebfb59babedc6df026494b11d49d8dc3fba26efaea | VERIFIED-BY-DOC |
| /price-feeds/pro/symbology-reference.mdx | 04:20:01 | 200 | 22511 | 01d2fdc27cfc4baddb96fe2d26931820e366625f3dfa306602aac1ddbd67152d | VERIFIED-BY-DOC |
| /price-feeds/pro/pyth-terminal.mdx | 04:20:11 | 200 | 3263 | f28807d9da2e26a29c05ca929d3dcaa97453d22e7124e1ddf94cfef928d77041 | VERIFIED-BY-DOC |
| /price-feeds/pro/acquire-api-key.mdx | 04:20:13 | 200 | 2578 | 9a69724be82d14cb6b4acc7ab9aeb98dfb58bad17e26ed22e9a285cc7b22d602 | VERIFIED-BY-DOC |
| /price-feeds/core/best-practices.mdx | 04:19:09 | 200 | 18545 | e29946572dfbe145d3a4edc139caefe73a1c107b6b596a2f1235d28df4885c56 | VERIFIED-BY-DOC |
| /price-feeds/core/fetch-price-updates.mdx | 04:19:10 | 200 | 15017 | 743f670d69815a897e40af88478128a64bf2fa79b6fc860dd76e28fc9691c6fe | VERIFIED-BY-DOC (example JSON) |
| /price-feeds/core/how-pyth-works.mdx | 04:20:03 | 200 | 983 | 7de8f48e41dcc0188ede20ab882ca05e7a022ec055c2f4c02801634af0c61bbc | VERIFIED-BY-DOC |
| /price-feeds/core/price-feeds/asset-classes.mdx | 04:20:04 | 200 | 3991 | b856e10ac2c8f73643caba2000f76feeee8304f88d7da884407c26cd49912951 | VERIFIED-BY-DOC |
| /price-feeds/core/upgrade.mdx | 04:20:52 | 200 | 1621 | e97fdf6403acecb2d99d8df01f371a0a19a1370568afe12064855c4c92c45683 | VERIFIED-BY-DOC |
| /price-feeds/core/upgrade/how-it-works.mdx | 04:20:53 | 200 | 4044 | 7ce7659e2db1cf2432d6083ff335e668917ffd07da92322ee0657347a1e9cdb2 | VERIFIED-BY-DOC |
| /api-reference/pyth-core/hermes/timestamp_price_updates.mdx | 04:20:08 | 200 | 863 | 2d16df599b9b99d64f0cb4a36641ed89f1cfc5f872339101acfbb302bab122a5 | stub (schema lives on the blocked Hermes host) |
| /price-feeds/core/price-feed-ids.mdx | 04:19:11 | 404 | 14 | — | not found |
| `research/kalshi/api_documentation_findings.md` §11 (Kalshi `pyth_value` page) | Git | — | — | — | repo-Git (VERIFIED-BY-DOC at batch 2) |
| `research/data_sources/inventory_pm_gold_detail.md`, `research/historical_data/inventory_underlying_btc_gold.md` | Git | — | — | — | repo-Git (mixed G/S) |

Other pages fetched but not relied on: `price-feeds/changelog.mdx` (JS component only), `price-feeds/pro/futures-terminology.mdx`, `getting-started.mdx` (Core and Pro), `rate-limits.mdx`, `hip-3-service.mdx`, `subscribe-to-prices.mdx`, `hermes/price_feeds_metadata.mdx`, `core/price-feeds/price-feed-ids.mdx`.

## Access and connectivity

- **docs.pyth.network is reachable** through the PMV proxy. Earlier repo records said it was refused; that no longer holds.
- **Pyth Core (Hermes).** "Since **August 26, 2026**, every `hermes.pyth.network` request requires a Pyth API Key." The on-chain contracts "stay permissionless and need no key". `hermes.pyth.network` is on the PMV deny list and was not requested. The docs also name an "upgraded drop-in endpoint", `https://pyth.dourolabs.app/hermes`. It is a market-data host and was not requested.
- **Pyth Pro (formerly Lazer).** "Pyth Pro (formerly Lazer) is a subscription-based price streaming service". "API keys are required for Pyth Pro websocket connections and for authenticated HTTP endpoints." Keys "are permissioned for specific asset types and minimum channel rates". A free trial key is issued from Pyth Terminal (`pythdata.app`, on the deny list).
- **Pyth Core was rebuilt on Pyth Pro.** "Pyth Network upgraded Pyth Core on **August 26, 2026 at 16:00 UTC**." The new Core "leverages the high-performance Pyth Pro architecture while preserving the existing interfaces". "Pythnet is being shut down", and the pages on "the oracle program, price aggregation, cross-chain relaying, and the Pythnet account reference — have been retired". **Consequence:** pre-2026-08-26 Core (Pythnet) data and post-cutover data come from different aggregation infrastructure. Treat the cutover as a candidate regime break in any Pyth series.
- **Not requested:** `pyth.dourolabs.app` (History API and Symbology API, including the unauthenticated `/v1/symbols`), `pyth-lazer*.dourolabs.app`, `mcp.pyth.network`, and the OpenAPI JSON files on those hosts. All are market-data hosts. Fetching `/v1/symbols` would settle the gold feed metadata question, but it needs a separate classification decision (ACCESS REQUEST below).

## Transport, format, compression, delivery (historical vs live)

| Product | Live | Historical | Notes |
| - | - | - | - |
| Pyth Core / Hermes | REST `GET /v2/updates/price/latest`, SSE `GET /v2/updates/price/stream` ("SSE streams auto-close after 24 hours"); the docs advertise "400ms updates" | `GET /v2/updates/price/{publish_time}` (named in the API stub; schema on the blocked host) | Response has `binary` (signed, hex) plus `parsed` JSON |
| Pyth Pro WebSocket | `wss://pyth-lazer-{0,1,2}.dourolabs.app/v1/stream`. "You MUST connect to all three endpoints simultaneously." Channels `real_time` ("no faster than 1ms, no slower than 50ms"), `fixed_rate@50ms`, `fixed_rate@200ms`, `fixed_rate@1000ms` | — | JSON, optional signed binary (`evm`, `solana`, `stellar`, `leUnsigned`) |
| Pyth Pro REST | `POST /v1/latest_price` | `POST /v1/price` with `timestamp` "Unix timestamp in microseconds" | Each feed has a `min_channel` |
| Pyth Pro History API (`https://pyth.dourolabs.app/v1`) | — | `GET /{channel}/price` (µs timestamp), `GET /{channel}/price/range` ("the window may not exceed 60 seconds", max 100 ids, limit 1–1000, cursor `next`), `GET /{channel}/history` (OHLC; TradingView UDF; resolutions `1`,`2`,`5`,`15`,`30`,`60`,…,`D`,`W`,`M`; `from`/`to` "Unix seconds"), `GET /publisher_updates` ("Raw publisher updates", default window "7 days ago") | The History Service "Stores all publisher updates, aggregated data, and transactions." History depth per feed is **not stated** |
| "Benchmarks" | — | **Not documented** on docs.pyth.network. The only mention is Pyth Terminal: "Access Benchmark Data — View benchmark pricing for US equities and FX". `benchmarks.pyth.network` is not described anywhere fetched | The repo's G-7a/G-7b rows (Benchmarks endpoints, TradingView shim retired 2026-08-26) stay SECONDARY |

## Fields

### Pyth Core (Hermes `parsed` element)

| field | native type | official semantics | PMV class | notes |
| - | - | - | - | - |
| `id` | hex string (32 bytes) | feed ID (example only) | SOURCE_SPECIFIC | Core uses hex IDs. Pro uses numeric IDs; `hermes_id` in Pro symbology links them |
| `price.price` | int64 as string | "Price as integer, multiply by 10^expo for actual value" | DIRECT (reference value) | |
| `price.conf` | uint64 as string | "Confidence interval (same scale as price)" | SOURCE_SPECIFIC | See confidence semantics below |
| `price.expo` | int32 | "Exponent, typically -8" | DIRECT | Same exponent for price and conf (best-practices) |
| `price.publish_time` | uint (example: 10-digit integer) | "`publishTime` (uint) — Unix timestamp of publication" | DIRECT (time) | **Integer seconds** in every doc example. No sub-second field in the Core schema. Whether this is aggregate time or slot time is not stated in the fetched docs |
| `ema_price.{price,conf,expo,publish_time}` | as above | EMA of price and conf (Pro doc: about 1-hour window, inverse-confidence weighted) | DERIVABLE (from the price series, but only approximately: the weighting needs conf) | |
| `metadata.slot` | integer | not defined in fetched docs (Pythnet/Router slot) | SOURCE_SPECIFIC | Meaning after the 2026-08-26 upgrade is UNKNOWN |
| `metadata.proof_available_time` | integer seconds | not defined in fetched docs | SOURCE_SPECIFIC | In examples it trails `publish_time` by a few seconds: a possible availability-time proxy (UNKNOWN) |
| `metadata.prev_publish_time` | integer seconds | not defined in fetched docs | SOURCE_SPECIFIC | Lets a consumer detect a carried-forward vs fresh update (INFERENCE) |

### Pyth Pro (`streamUpdated` / REST / History rows)

| field | native type | official semantics (quoted) | PMV class | notes |
| - | - | - | - | - |
| `parsed.timestampUs` | string (µs) | update timestamp | DIRECT (time) | Microseconds |
| `priceFeedId` | u32 | "Unique identifier for the price feed" | SOURCE_SPECIFIC | Gold IDs below |
| `price` | i64 (string in JSON) | "Main aggregate price calculated from all contributing publishers, represented as mantissa." "Non-zero when present" | DIRECT | |
| `exponent` | i16 | "`actual_price = mantissa × 10^exponent`" | DIRECT | |
| `confidence` | i64 | "Price uncertainty across publishers; higher = more disagreement." Marked EXPERIMENTAL in the quick-start | SOURCE_SPECIFIC | |
| `bestBidPrice` / `bestAskPrice` | i64 | "Tightest non-overlapping bid/ask across publishers. (Experimental)" | SOURCE_SPECIFIC | "not yet covered by automated data quality assurance" |
| `publisherCount` | u16 | "Number of contributing publishers." | SOURCE_SPECIFIC | Quality filter |
| `marketSession` | string | "`regular`, `preMarket`, `postMarket`, `overNight`, `closed`" | DIRECT (session state) | Still updates when the price is carried forward |
| `feedUpdateTimestamp` | u64 (µs) | "Timestamp when price was last generated for this feed (μs)." | DIRECT (time) | Key freshness field (below) |
| `emaPrice` / `emaConfidence` | i64 | "Exponential moving average of the price/confidence" | DERIVABLE (approx.) | about 1 h; "does not reset on market session boundaries" |
| `fundingRate`, `fundingTimestamp`, `fundingRateInterval` | i64/u64 | derivatives only | n/a | Not relevant to gold spot |
| History row fields | — | `channel`, `channel_name`, `price_feed_id`, `price`, `publish_time`, `best_bid_price`, `best_ask_price`, `publisher_count`, `exponent`, `confidence`, `funding_*`, `market_session`, `ema_price`, `ema_confidence`, `feed_update_timestamp` | as above | The unit of `publish_time` in History rows is **not stated** (UNKNOWN; probably µs given the µs query parameters) |
| OHLC `t,o,h,l,c,v` | arrays | "`t` Unix timestamps (seconds)"; "`v` Volumes (if available)" | DERIVABLE | Candle construction (which ticks, open/close boundaries, carried-forward handling) is **not documented**. This is DET-1's "candle rule" |

### Symbology (reference data, `GET /v1/symbols`; not fetched)

Documented fields: `pyth_lazer_id`, `name`, `symbol`, `description`, `hermes_id`, `asset_type` (values include `metal` and **`kalshi`**), `instrument_type` (`spot`, `future`, `perp`, `rate`, `index`, `nav`), `quote_currency`, `groups` (e.g. `pyth-indices`), `exchange_id`, `exponent`, `min_publishers`, `min_channel`, `state` (`stable`, `coming_soon`, `inactive`), `schedule` (format `TZ;<weekly>;<holidays>`), `market_session_schedule`, `market_sessions` (per-session `schedule`, `min_pub`, `state`), and futures and corporate-action fields. This endpoint would give point-in-time-free (current-only) metadata for feeds 346/3153/3712: schedule, min_publishers, instrument_type `spot` vs `index`, and `groups`.

## Timestamps

- **Core:** `publish_time` is integer Unix seconds in all examples, and Core has no sub-second field. "Aggregate publish time" is **not defined** in the fetched docs; the Pythnet aggregation pages that defined it were retired. Classify the exact semantics as UNKNOWN beyond "Unix timestamp of publication".
- **Pro:** `timestampUs` (message) and `feedUpdateTimestamp` (when "the price for this specific feed was last generated") are **microseconds**. History and REST query parameters are microseconds. OHLC `t` is seconds.
- **Carry-forward semantics (VERIFIED-BY-DOC, critical for labels near closures):** "Starting March 23, 2026, once a feed produces its first valid price, a price will always be provided for that feed going forward, even during off-hours (the most recent price will be carried forward)." Also: "If fewer than `min_pub` publishers have contributed a price, no new aggregate is produced … `price`, `confidence`, … `feedUpdateTimestamp` are all carried forward". Detection: `feedUpdateTimestamp` < `timestampUs`. A recorded series at fixed rate therefore contains stale repeated values. Any feature or label built on it must use `feedUpdateTimestamp`, not the message time.
- **Receipt time:** none from Pyth. Kalshi's `pyth_value` adds `source_ts_ms` ("Pyth source timestamp") and `received_at` ("When Kalshi received the Pyth update"), in ms, and drops "duplicate and out-of-order source timestamps … independently per underlying ticker" (repo-Git, Kalshi docs).
- **Timezone:** epoch UTC. Schedules use IANA zones with local times ("the local time does not change—only the offset from UTC").

## Sequencing and book semantics

- No book. Pyth publishes an aggregate, not an order book. `bestBidPrice`/`bestAskPrice` are a cross-publisher inside quote (experimental), not a venue BBO.
- **No sequence number in the payload.** Ordering is by `timestampUs`. Internally "messages will be processed in the same order they arrived at the Relayer", and "Pro guarantees deterministic aggregation: all aggregators produce the exact same aggregated results". Clients connected to 3 endpoints see duplicates and gaps during failover: "Expected behavior during endpoint failovers. The SDK deduplicates across connections."
- **Gap recovery:** History API `price/range` (≤60 s windows) or `price` at a µs timestamp; needs a key and entitlement.
- **Aggregation (VERIFIED-BY-DOC, Pro, and therefore post-upgrade Core):** "The aggregate `price` is the median of all publisher prices when at least `min_pub` publishers have contributed a price in the current aggregation window." Stale publisher data is removed "based on configurable timeouts". Circuit breakers exclude out-of-line updates. Each publisher contributes up to three values (bid, price, ask), with imputation rules for missing ones.
- **Confidence (Pro, current):** "`confidence = max(price − p25, p75 − price)`" over the pooled publisher {price, bid, ask} set. "Confidence reflects the measurement uncertainty of the prices reported among publishers. This may or may not reflect the uncertainty (volatility) of the underlying market price." The Core best-practices page still describes the legacy design: publisher intervals "intended to achieve 95% coverage", and an aggregate "somewhat analogous to an interquartile range". These two descriptions differ. Post-2026-08-26 Core conf presumably follows the Pro formula (INFERENCE, UNVERIFIED). **conf is not a calibrated 95% interval and must not be used as a volatility estimate without testing.**

## Instrument / contract identity, expiry, reference-end, settlement/reference fields

- **Gold feed IDs (repo-Git, from Kalshi's `pyth_value` page, not from docs.pyth.network):** `Metal.XAU/USD` (346), `Metal.Index.GOLD/USD` (3153, "Blended Gold Index in USD (24/7)"), `Metal.Index.1OZGOLD/USD` (3712, 24/7). **docs.pyth.network does not mention `Metal.Index.GOLD/USD`, `1OZGOLD`, or any gold index, and publishes no index methodology.** The symbology page shows an `index` instrument type and a `pyth-indices` group, so indices exist as a class. The constituents, weights, and blending rules of the GOLD index are UNDOCUMENTED.
- **XAU spot derivation (VERIFIED-BY-DOC, FAQ):** "Pyth follows CME futures market hours for precious metals, since the spot price is derived from futures." The best-practices page adds that for futures-based assets the front month "**doesn't** represent the current price of the asset", and that "each contract should have a weighted stratergy based on their expiration dates" (sic). The exact XAU spot construction is not stated.
- **Metals market hours (VERIFIED-BY-DOC):** Market Hours table: "Metals | From Sunday 6PM ET to Friday 5PM ET | Daily maintenance window applies from 5PM ET to 6PM ET, Monday to Thursday. Spot gold and silver trading also follow CME holiday closures." The FAQ gives the same: "Sunday 6:00 p.m. ET through Friday 5:00 p.m. ET … 60-minute break each day at 5:00 p.m. ET (17:00-18:00)". So **`Metal.XAU/USD` has weekend and daily-break gaps**, during which Pro carries the last price forward (`marketSession` = `closed` presumably; INFERENCE). Kalshi's doc labels 3153/3712 as 24/7; their actual schedules would be in `/v1/symbols` (not fetched).
- **Kalshi gold settlement (DET-1): still UNRESOLVED.** No page on docs.pyth.network mentions Kalshi gold contracts. The only Kalshi link is `asset_type` value `kalshi` in symbology, meaning Pyth publishes feeds of class "kalshi" (probably Kalshi market prices; UNKNOWN). Repo evidence: third parties cite "Pyth GOLD" and a 1-minute candle close (SECONDARY). Which feed (346 vs 3153), the candle definition (Pyth OHLC `close` vs last `price` at a time; seconds-aligned `t`), the time zone, and handling of a carried-forward close are all open. Only the Kalshi contract terms (owner download, PM-06b/G4) can resolve DET-1.
- **Polymarket uses Pyth Pro (VERIFIED-BY-DOC):** "See how Polymarket uses Pyth Pro data through Terminal … This package includes metals such as XAU and XAG". Polymarket PolyBolt `price.equity` lists `xauusd` with vendor `pyth`/`chainlink`/`massive` (see `polymarket_markets_book.md`).

## Licence / access gating

- Every data path needs a Pyth API key: Hermes since 2026-08-26, and all of Pro. Keys are entitlement-scoped by asset type and channel.
- Repo pricing (SECONDARY / OWNER_VERIFY): Metals plan about $2,500/month (`owner_source_action_sheet.md` G3; `master_source_inventory.md` G-6). The $99 package is unverified. Kalshi `pyth_value` costs $1,000/month with 7 days free (repo-Git, K5/G-8).
- **No data licence text was found** on docs.pyth.network. The best-practices footnote points to `https://www.pyth.network/terms-of-use` on `www.pyth.network`, which is BLOCKED for this task. The repo already records "No data licence seen" (`master_source_inventory.md`). Storage, ML training, and derived-model rights are UNKNOWN. Status stays **NEEDS_LICENCE_CLARIFICATION / NEEDS_PAYMENT**.
- Protected-information class: every Pyth gold feed is an equivalent observable (and the probable settlement input) for protected gold contracts. It is still missing from the guard's equivalence catalog (E-U1, RT-B3-05).

## PMV relevance: unique vs derivable

- **Unique:** the exact reference series that probably settles Kalshi KXGOLD15M and Polymarket XAUUSD daily markets (if DET-1 confirms it). No exchange feed can reproduce a median-of-publishers aggregate or an undisclosed blended index exactly. `feedUpdateTimestamp` and `marketSession` give the reference's own staleness state, which no other source gives.
- **Derivable or approximable:** the XAU level and short-horizon moves during CME hours. Pyth says XAU spot "is derived from futures", so COMEX GC/MGC (Databento) carries the same price discovery, offset by a roll- and carry-dependent basis. EMA fields are derivable approximately.
- **Not useful as a velocity signal by itself:** an aggregate of publishers who mostly source from the same futures and OTC markets adds latency and smoothing, not new information. That is an expectation, not a tested claim.
- This profile makes no claim of predictive value.

## Comparison H — Databento COMEX gold vs Pyth gold: different economic objects

| | COMEX GC/MGC futures (Databento GLBX.MDP3) | Pyth `Metal.XAU/USD` (346) | Pyth `Metal.Index.GOLD/USD` (3153) |
| - | - | - | - |
| Object | A tradable, dated futures contract (delivery month) with an exchange order book | Oracle aggregate: median of publisher "spot" prices. Pyth says the spot price "is derived from futures" | A proprietary "blended" 24/7 index. Methodology undocumented |
| Price formation | Matching engine: trades, MBO/MBP book, exchange timestamps (ns) | Publisher submissions → median → carry-forward when below `min_pub` | UNKNOWN (repo SECONDARY: built in-house, live since about 2026-06) |
| Hours | CME Globex: Sunday 18:00 to Friday 17:00 ET with a daily 17:00–18:00 ET break | Same as CME (VERIFIED-BY-DOC) | 24/7 per Kalshi docs. The weekend inputs are UNKNOWN (tokenised gold? OTC? repo INFERENCE) |
| Level | Spot + carry (contango), which changes with days to delivery and **jumps at roll** | Spot-equivalent (construction from futures not documented) | UNKNOWN relation to spot or futures |
| Role for PMV | **Market dynamics and velocity features** (order flow, book pressure, trade intensity) during CME hours | **Possible settlement reference** (Polymarket XAUUSD daily per SECONDARY rules; Kalshi DET-1 candidate) | **Possible settlement reference** for Kalshi KXGOLD15M (DET-1 candidate). Only source for weekend and daily-break label dynamics |

Conclusions (evidence-based; INFERENCE where noted):

1. They are different economic objects. COMEX is where gold price discovery happens during CME hours. Pyth XAU is a derived reference of that discovery (by Pyth's own statement), shifted by a futures-to-spot basis. The GOLD index is a third, opaque object.
2. A model can take velocity information from COMEX, but **labels and distance-to-strike must be computed in the settlement reference's units**. That requires an estimated GC↔Pyth basis. The basis can only be estimated over the short, development-exposed overlap (about 2026-06 onward for 3153; `inventory_pm_gold_detail.md`).
3. During the 17:00–18:00 ET break and at weekends, COMEX gives no information. Pyth XAU carries a stale value, and only the 24/7 GOLD index moves. If Kalshi gold settles on 3153, windows in those hours have **no exchange-based feature source** (except 1OZ since about 2026-07, which is thin, and tokenised gold). Those windows may need to be excluded or treated as a separate regime.
4. Roll dates and front-month weighting (Pyth's own guidance) mean the GC front-month vs Pyth relationship has structural breaks. Features must be roll-aware.
5. Recommendation (optional, not blocking): keep gold dynamics research on COMEX, and do not buy Pyth history until DET-1 names the feed and candle rule. If DET-1 says 3153, obtain the index methodology before any label work. Without it, label semantics (weekend inputs, blending) cannot be audited.

## Open questions / unverified items

1. **DET-1:** which Pyth feed (346 or 3153), which candle or price definition, which timestamp alignment, and how a carried-forward close is handled. Source: Kalshi contract terms (owner).
2. `Metal.Index.GOLD/USD` methodology, inputs, and schedule: not on docs.pyth.network. A blog or methodology page may be on `www.pyth.network` (BLOCKED).
3. History depth per gold feed on the Pro History API: not stated. Repo SECONDARY says the GOLD index starts about 2026-06.
4. Hermes OpenAPI field definitions (`publish_time`, `prev_publish_time`, `proof_available_time`, `slot`): the spec is on `hermes.pyth.network/docs/openapi.json` (BLOCKED).
5. Unit of `publish_time` in Pro History rows (µs or s): UNKNOWN.
6. Which confidence formula post-upgrade Core uses (legacy 95%-coverage or Pro IQR-max): UNKNOWN.
7. Meaning of Pyth symbology `asset_type: kalshi`: UNKNOWN.
8. Regime break at the 2026-08-26 Core upgrade (Pythnet → Pro routers) for any series spanning it: candidate, untested.
9. Licence text (terms of use on `www.pyth.network`, BLOCKED): storage and ML rights UNKNOWN.

**ACCESS REQUEST (proposed, not made):** host `pyth.dourolabs.app`, path `/v1/symbols?asset_type=metal` only. The docs say "no auth required" and describe it as reference data ("it describes *what* a feed is, not its current value"). Purpose: schedules, `min_publishers`, `instrument_type`, `groups`, `hermes_id` for feeds 346/3153/3712. Host class: it shares a host with authenticated price APIs, so the strictest class applies (market-data host). It must be owner-classified before any request.
