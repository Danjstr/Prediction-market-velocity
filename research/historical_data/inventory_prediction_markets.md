# Historical prediction-market data inventory (Phase 1 batch 3, section A)

**Status:** research record, not an approved requirement. Documentation and metadata only. No market API host, RPC, subgraph, or query endpoint was contacted. No dataset, data file, viewer, or row preview was opened. No market values (prices, quantities, outcomes) were used or recorded here. Where a page showed real observations, see "Incidental exposure" at the end. Retrieval date: 2026-10-16 (UTC). Hashes are in `research/sources.md` (section "Phase 1 batch 3"). Kalshi API facts come from batch 2 (`research/kalshi/api_documentation_findings.md`, `research/kalshi/venue_verification.md`). docs.kalshi.com was not refetched.

**Tags:** VERIFIED-BY-DOC (url) = stated by an official or primary document fetched on 2026-10-16 (or in batch 2). SECONDARY = third-party page or search-result summary that was not verified against an official source. INFERENCE = my reasoning. UNRESOLVED = not determinable from what was accessible.

**Standing rule for every record:** all of this data is already public, so it can support **development only**. It can never become protected holdout data. Protected evaluation will almost certainly need **prospective PMV capture**, taken after the split is frozen and kept under the embargo. PMV has not exposed any real observation from these sources to development; the repo holds none (batch 1 and 2 were documentation-only). Acquisition must go through the deterministic data-access guard. Today the guard refuses all real requests (`PROTECTED_SCOPE_NOT_DECLARED`, `docs/protected_information.md`).

---

## 0. Cross-cutting findings (read first)

1. **No official historical order book exists on either venue.**
   - Kalshi: VERIFIED-BY-DOC in batch 2 (§7 of `api_documentation_findings.md`).
   - Polymarket: VERIFIED-BY-DOC, by absence. No book-history endpoint exists in the predictions API index (`https://docs.polymarket.com/_llms/en/api-reference/predictions.txt`). `GET /book` is the current book only.
   - Historical depth for 15–60-minute contracts therefore exists only in **third-party captures** (paid, unverified, licensing unclear) or in **PMV's own prospective capture**.
2. **Settlement rules changed over time on both venues. Historical labels must use per-market official settlement values, not values PMV recomputes.**
   - **Kalshi BTC, per CFTC filings (VERIFIED-BY-DOC):**
     - The BTC rulebook was originally a 300-second trimmed average.
     - Amended 2024-11-12 (effective 2024-11-27): "simple average of the CF Bitcoin Real-Time Index ('BRTI') for the minute (60 seconds) prior to <time>, excluding the highest and lowest 20% of values" (`https://www.cftc.gov/sites/default/files/filings/orgrules/24/11/rules1112248590.pdf`).
     - The CRYPTO rulebook (2025-07-18) uses a plain 60-second simple average. Missing data means "affected strikes resolve to No" (`…/ptc/25/07/ptc07182526860.pdf`).
     - The CRYPTOSHORT rulebook (2026-03-11) has a configurable `<lookbackduration>` and rounding before comparison. Missing data means "resolve based on the last piece of data available" (`…/ptc/26/03/ptc03112640675.pdf`).
   - **Which rulebook governs KXBTC15M is UNRESOLVED.**
     - SECONDARY: a search result points to the contract terms at `https://kalshi-public-docs.s3.amazonaws.com/contract_terms/CRYPTO15M.pdf`, which was not fetched (AR-A1).
     - SECONDARY: the rule is "60-second simple average of BRTI before close ≥ the same average before open; ties resolve YES".
   - **Polymarket crypto up/down (VERIFIED-BY-DOC, `https://docs.polymarket.com/changelog/predictions.md`):**
     - Before 2026-08-07: "a single price snapshot". SECONDARY: from a Chainlink Data Streams BTC/USD stream.
     - From 2026-08-07: a Chainlink TWAP at both open and close. 15-minute and 4-hour markets use a 60-second window. 5-minute markets used 30 seconds until 2026-08-14 00:00 UTC, then 60 seconds.
     - Up if final ≥ price to beat (`https://docs.polymarket.com/concepts/resolution.md`).
   - **INFERENCE:** history before and after these dates is from different label-generating regimes. It must be partitioned or modeled explicitly, not pooled silently.
3. **Execution-regime changes inside the history (VERIFIED-BY-DOC, Polymarket changelog):**
   - Crypto taker delay was 250 ms, then 50 ms from 2026-08-17 11:00 UTC, then 150 ms from 2026-09-04 14:00 UTC.
   - Taker fees on 15-minute crypto markets started 2026-01-05. They extended to all crypto markets created after 2026-03-06.
   - Protocol V2 migration on 2026-04-28 brought new exchange contracts and pUSD collateral (`https://docs.polymarket.com/resources/onchain-position-data.md`; SECONDARY for the date: `https://github.com/PaulieB14/polymarket-v2-subgraphs`).
   - Matching-engine restarts are followed by 2 minutes of post-only mode (`https://docs.polymarket.com/trading/matching-engine.md`).
   - Kalshi: batch 2 lists the timestamp and ack-race changes (WS ms timestamps from 2026-04-15, `sending_ts_ms` from 2026-10-01).
   - Backtests that span these dates need per-period fee, latency, and settlement models.
4. **No historical source records strategy-availability time.**
   - Official historical trade timestamps are venue event times: Kalshi `created_time`; Polymarket **block timestamp in seconds**, which is after off-chain matching. INFERENCE: Polygon block time lags the CLOB match.
   - Any availability time PMV derives must be marked **estimated**, per START_HERE.md.
5. **Current-state metadata leaks outcomes.**
   - Polymarket Gamma `markets` fields are current state, including `outcomePrices`, `lastTradePrice`, `bestBid`/`bestAsk`, `volume`, `closed`, `closedTime`, `umaResolutionStatus`, `updatedAt`, `pastSlugs`, and an editable `description` (VERIFIED-BY-DOC: `https://docs.polymarket.com/api-reference/markets/list-markets.md` schema).
   - Data API v2 `/v2/prices-history` appends a **settlement point (0/1 payout)** to resolved markets (VERIFIED-BY-DOC: `https://docs.polymarket.com/api-reference/markets/get-a-tokens-price-history.md`).
   - Third-party Kalshi market tables carry `yes_bid`/`yes_ask`/`last_price`/`result` as of **fetch time**, for example Jon-Becker `_fetched_at` (VERIFIED-BY-DOC: `https://github.com/Jon-Becker/prediction-market-analysis/blob/main/docs/SCHEMAS.md`).
   - None of these fields can be used as decision-time features.
6. **Gold.**
   - SECONDARY, with several independent third-party pages agreeing: Kalshi lists **KXGOLD15M**, which launched around August 2026. It runs weekdays, every 15 minutes, and settles on the Pyth GOLD 1-minute candle close (end ≥ start → YES).
   - This new evidence bears on batch 2 Escalation E-1, which found no gold series in docs.kalshi.com. Official terms remain UNRESOLVED (AR-A1, AR-3).
   - Polymarket: SECONDARY, daily "XAUUSD Up or Down" markets resolve on Pyth `Metal.XAU/USD` 1-minute candle closes. Whether an hourly or shorter gold market exists is UNRESOLVED. PolyBolt carries `xauusd` only on `price.equity`, with no gold TWAP (VERIFIED-BY-DOC: `https://docs.polymarket.com/api-reference/live-data/overview.md`).
   - Historical gold depth at 15–60 minutes is at most about 2 months (Kalshi), which is too short for robust development (INFERENCE).
7. **Polymarket eligibility (material, for owner F-16).**
   - polymarket.com puts **US = "Close-Only on Frontend and API"** (VERIFIED-BY-DOC: `https://docs.polymarket.com/api-reference/geoblock.md`). polymarket.com itself served "Trading is blocked in the United States on polymarket.com. Switch to polymarket.us".
   - Polymarket US is a **separate CFTC-regulated venue** with a separate API (`docs.polymarket.us`, blocked by the proxy) and separate credentials (SECONDARY).
   - Polymarket US BTC 15-minute markets launched around 2026-09-22 (SECONDARY). Their settlement source is CONFLICTING: CF Benchmarks BRTI per one source, the Chainlink BTC/USD oracle per another. UNRESOLVED.
   - Polymarket US has "no public trade tape" and redistribution restrictions in its rulebook (SECONDARY).
   - INFERENCE: if the owner is a US person, polymarket.com history is research-only for development. The relevant tradable venue would be Polymarket US, whose history is undocumented here.

---

## 1. Kalshi official sources

### K1. Kalshi Trade API v2: live and historical tiers (markets, trades, candlesticks, settlements)
- **Provider/URL:** Kalshi. Docs at `https://docs.kalshi.com/getting_started/historical_data.md` and `openapi.yaml` 3.34.0 (batch 2). API hosts are `external-api.kalshi.com` and `api.elections.kalshi.com`; neither was contacted.
- **Data type:** `/historical/markets`, `/historical/markets/{t}`, `/historical/markets/{t}/candlesticks`, `/historical/trades`, `/historical/cutoff`, and the live-tier equivalents. VERIFIED-BY-DOC (batch 2 §7).
- **Asset/venue:** all Kalshi series, including KXBTC15M (VERIFIED-BY-DOC only as an example ticker). KXBTCD hourly and KXGOLD15M are SECONDARY.
- **Coverage dates:** earliest date and retention are UNRESOLVED in the docs.
  - The cutoff advances over time (VERIFIED-BY-DOC).
  - SECONDARY: the historical cutoff was "100 days" when `https://github.com/jdkatz21/Prediction_Markets_Public` was written, and the endpoint split dates from March 2026.
  - SECONDARY (HF TrevorJS): trades are reachable back to June 2021.
- **Granularity:** trade prints, plus candles at 1 / 60 / 1440 minutes only, so 1 minute is the minimum (VERIFIED-BY-DOC).
- **Trades:** yes. `trade_id`, price, count, `created_time`, and `taker_side`, which is deprecated with a CONFLICTING removal date (batch 2).
- **Quotes:** candle `yes_bid`/`yes_ask` OHLC per minute only. How bid and ask are sampled within the minute is UNRESOLVED (batch 2 U15).
- **Order books/depth:** none historical (VERIFIED-BY-DOC).
- **Contract metadata:** markets carry `open_time`, `close_time`, `expected_expiration_time`, `settlement_ts`, strike fields, `strike_type`, and more. Series carry `settlement_sources`, `contract_url`, and `contract_terms_url`. The latter is the **current** terms, so terms can be post-hoc relative to old markets (VERIFIED-BY-DOC, batch 2).
- **Outcomes/settlements:** `result` and the settlement/expiration value per market (VERIFIED-BY-DOC, batch 2).
  - SECONDARY (HF DegenHedge card): some KXBTC15M markets show missing or mis-scaled strike or settlement fields in the API.
  - INFERENCE: the label builder needs an integrity validator that flags rather than repairs.
- **Timestamps:** REST `date-time`; timezone and precision UNRESOLVED (batch 2 §6). Candle `end_period_ts` is int64, inclusive end. `created_time` is the venue event time, not PMV receipt time.
- **Historical revisions:** market objects are current state (`updated_time`, status, result). Old live/historical overlap needs dedup by `trade_id` (batch 2). Contract terms URLs point to current terms.
- **Access:** public REST, no authentication for market data (VERIFIED-BY-DOC, batch 2). Rate limits are token buckets.
- **Cost:** free API.
- **Licensing:** using the API binds the user to the Developer Agreement (`https://kalshi.com/developer-agreement`), which could not be retrieved (AR-3). UNRESOLVED.
  - SECONDARY: jdkatz21 says Kalshi granted research permission and that its "data licensing agreement" is in that repo. That suggests data-use terms exist and matter.
- **Provenance quality:** highest available for Kalshi, as the venue's own record.
- **Known gaps:** no L2; 1-minute floor; retention unknown; deprecated fields; post-hoc metadata.
- **Likely PMV use:**
  - official labels (strike, settlement value, result) for KXBTC15M and KXGOLD15M;
  - trade-print features;
  - minute bid/ask candles as coarse quote proxies;
  - cross-checking PMV capture.
- **Supports:** development. Protected evaluation needs prospective capture.
- **Exposed to PMV development:** no.

### K2. Kalshi event live data `GET /live_data/events/{event_ticker}`
- **Docs:** batch 2 §9 (changelog 2026-07-30), not refetched. Public. Serves "crypto price charts (e.g. KXBTC15M events)". `is_historical` marks a frozen snapshot after maturity. The `details` schema is "flexible", so semantics are UNRESOLVED.
- **Use:** auxiliary only. It is an equivalent observable of the underlying and must be catalogued in the guard.
- **Licensing:** as K1.
- **Supports:** auxiliary or development.

### K3. Kalshi CF Benchmarks REST passthrough (history)
- **Docs:** batch 2 (`cfbenchmarks/rest-passthrough.md`). Authentication and entitlement required. Tick-level BRTI history.
- **Note:** reference-market data, so it belongs to the underlying inventory, not section A. Listed only because it is the settlement source of K1 BTC contracts.
- **Access:** blocked for PMV (no credentials, D3).
- **Supports:** development (auxiliary label recomputation) if access is approved.

### K4. Kalshi daily market-data reports (public S3 "reporting" files)
- **Provider/URL:** Kalshi. `kalshi-public-docs.s3.amazonaws.com/reporting/…` (SECONDARY: HF `carpetxie/winniethepooh` card). The Kalshi page `https://kalshi.com/market-data` is blocked (AR-3). Not contacted.
- **Data type:** daily bulk market files with tickers, open interest, and daily volume (SECONDARY: search summary of the kalshi.com/market-data page).
- **Granularity:** daily. **Not useful for 15–60-minute modeling** except as a market-universe and lifecycle cross-check.
- **Timestamps, licensing, coverage:** unknown. SECONDARY: 2023-01 onward per carpetxie.
- **Supports:** auxiliary only.

### K5. Kalshi contract terms documents (CRYPTO15M.pdf and gold 15-minute terms)
- **URL:** `https://kalshi-public-docs.s3.amazonaws.com/contract_terms/CRYPTO15M.pdf` (SECONDARY locator, from a search result). The gold terms filename is unknown. Not fetched: the domain is outside AR-1 (D1) and the same host serves the `/reporting` market data (AR-A1).
- **Type:** contract rules, not market data. Needed to settle U19 and U20 (settlement source, averaging, tie rule, no-data rule).
- **Supports:** label definition.

### K6. CFTC product filings by KalshiEX (primary regulatory source)
- **URL:** `https://www.cftc.gov/sites/default/files/filings/…`. Three PDFs were fetched and read (hashes in the sources file).
- **What they establish:** BTC, CRYPTO, and CRYPTOSHORT rule texts, and that the Source Agency is CF Benchmarks. All VERIFIED-BY-DOC (§0.2).
- **What they do not establish:** no fetched filing names KXBTC15M, CRYPTO15M, or any gold 15-minute product (UNRESOLVED). Appendix C (Source Agency) is confidential.
- **Licensing:** US government public record.
- **Supports:** label semantics for development.

---

## 2. Polymarket official sources (docs.polymarket.com, fetched 2026-10-16)

### P1. Gamma API: events, markets, series, tags (`gamma-api.polymarket.com`, not contacted)
- **Docs:** `https://docs.polymarket.com/api-reference/markets/list-markets.md`, `…/events/list-events.md`, `…/series/list-series.md`. VERIFIED-BY-DOC.
- **Data type:** contract metadata. Fields include `conditionId`, `questionID`, `clobTokenIds`, `positionIds`, `startDate`, `endDate`, `eventStartTime`, `closedTime`, `resolutionSource`, `description` (the rules), `feesEnabled`/`feeSchedule`/`makerBaseFee`/`takerBaseFee`, `orderPriceMinTickSize`, `version` (v1 CTF / v2 PositionManager), and `umaResolutionStatus`.
- **Recurring series:** series carry `recurrence` and `pythTokenID`. The series ticker or slug for BTC 15-minute markets is UNRESOLVED from docs. SECONDARY: event slugs look like `btc-updown-15m-<epoch>`.
- **Granularity:** per-market snapshot.
- **Trades/quotes/books:** none. `bestBid`/`bestAsk`/`lastTradePrice` are current state only.
- **Outcomes:** `outcomePrices` and `umaResolutionStatus` are current state and post-hoc.
- **Timestamps:** `date-time` strings. The timezone convention is not stated (UNRESOLVED; INFERENCE: ISO-8601 UTC).
- **Historical revisions:** current-state document. `description` can gain "Additional context" clarifications after trading starts (VERIFIED-BY-DOC: `concepts/resolution.md`). **This source can leak future information.** Snapshot the rules text at decision time prospectively.
- **Access:** public, no authentication. Rate limit 300 req/10 s on `/markets` (VERIFIED-BY-DOC: `api-reference/rate-limits.md`).
- **Cost:** free.
- **Licensing:** API spec metadata says "MIT" (that covers the spec, not the data). polymarket.com/tos is JS-rendered and its text was not retrievable. UNRESOLVED.
- **Provenance:** venue's own record, but current state.
- **Use:** market universe, contract identity (`conditionId`/token mapping), rules text, fee flags. Not features.
- **Supports:** development.

### P2. Data API v2 `/v2/prices-history` (replaces CLOB `/prices-history` as of 2026-09-04)
- **Docs:** `https://docs.polymarket.com/api-reference/markets/get-a-tokens-price-history.md`. Legacy CLOB route: `…/get-prices-history.md`, `…/get-batch-prices-history.md`. VERIFIED-BY-DOC.
- **Data type:** per-token price series. "Price" semantics are **undocumented**: "`resolution_seconds` … is the ONLY thing the payload says about provenance, deliberately". INFERENCE: probably the displayed price (midpoint, or last trade if spread > $0.10, per `concepts/prices-orderbook.md`). That is **not an executable price**. SECONDARY: the DegenHedge card reports that a Polymarket "displayed outcome price" was not a tradeable price.
- **Coverage and retention (VERIFIED-BY-DOC):**
  - 3-hour and 12-hour series are permanent, back to 2022-11-18.
  - 1-minute data lasts "at least 7 days", 5-minute "at least 60", 30-minute "at least 90" (floors).
  - The SDK page contradicts this: "Finer widths return only the last 30 days" (`market-data/prices-order-books.md`). CONFLICT.
  - Explicit windows are capped at 15 days.
- **Granularity:** 60 s at best, and only recently.
- **Usefulness:** for 15-minute markets older than about a week this is effectively useless (12-hour buckets). **Not useful for historical development beyond a rolling week.** Prospective capture can archive it daily, but that is weaker than book capture.
- **Outcomes:** a resolved market gets a final settlement point (0/1/fractional) at `resolution_seconds` 0. This **leaks outcome**; strip it from features.
- **Timestamps:** observation time in epoch seconds (OpenAPI); the TS SDK exposes it as ms. Source time, no receipt time.
- **Access:** public, no authentication. 200 req/10 s.
- **Licensing:** UNRESOLVED (as P1).
- **Supports:** development (marginal).

### P3. Data API v2 `/v2/trades` (and v1 `/trades`)
- **Docs:** `https://docs.polymarket.com/api-reference/feeds/list-trades.md`, `…/core/get-trades-for-a-user-or-markets.md`, `migrate/data-api-v1-to-v2.md`. VERIFIED-BY-DOC.
- **Data type:** fill-level trades.
  - Fields: `token_id`, `condition_id`, `side`, `price` ("execution price per share"), `size` (shares), `timestamp` ("Block timestamp of the fill, epoch seconds"), `transaction_hash`, and outcome label/index.
  - `taker_only` defaults to true; set false to include maker rows.
  - Keyset pagination on `(block_timestamp, sequence_id)`.
- **Coverage:** `condition`/`event_id` queries serve "a fixed three-year window". The bare feed is current plus previous month. Minimum size filter defaults to 0.01.
- **Timestamps:** block time in **seconds**, after matching and on-chain settlement, with no sub-second order except `sequence_id` (opaque). INFERENCE: the gap from match to block adds a non-trivial, variable delay for 15-minute markets.
- **Quality notes:** `outcome_index: 999` means unlabeled. Missing numerics mean unavailable, never zero. Profile enrichment (name, bio) is irrelevant and should be dropped.
- **Access:** public. 300 req/10 s.
- **Licensing:** UNRESOLVED.
- **Provenance:** venue-indexed copy of on-chain fills. Freshness is exposed via `/v2/status` data-freshness (`api-reference/service/get-data-freshness.md`).
- **Use:** trade prints per BTC up/down market. Easier than raw chain data, but a derived index.
- **Supports:** development.

### P4. Data API v2 `/v2/resolutions` (resolution lifecycle)
- **Docs:** `https://docs.polymarket.com/api-reference/markets/get-resolution-state.md`. VERIFIED-BY-DOC: selectors are `question_id`/`condition`/`event_id`; order of precedence is V2 lifecycle, then UMA, then terminal CTF.
- **Use:** outcome and settlement timing for labels (development). Field-level timestamps not reviewed in detail (UNRESOLVED).
- **Supports:** development.

### P5. CLOB current book, midpoint, spread, and last trade (`clob.polymarket.com`) and market WebSocket
- **Docs:** `api-reference/market-data/get-order-book.md`, `api-reference/wss/market.md`. VERIFIED-BY-DOC: current state only, no history.
- **Use:** prospective capture only.
- **Supports:** protected evaluation candidate, via prospective capture.

### P6. PolyBolt reference-price WebSocket (Chainlink TWAP `price.crypto.twap`, `price.crypto`, `price.equity`)
- **Docs:** `api-reference/live-data/overview.md`, `api-reference/wss/polybolt.md`, `market-data/realtime-data.md`, `migrate/rtds-to-polybolt.md`. VERIFIED-BY-DOC:
  - The TWAP channel is "used by crypto up/down market resolution (gated)" and requires CLOB API credentials.
  - The only window is `window_seconds: 60`.
  - A subscribe returns a snapshot of the preceding **two minutes only**, so there is no history.
  - `source` names the vendor (pyth / massive / chainlink) and can change between connections.
  - RTDS is legacy.
- **Use:** settlement-source capture for Polymarket BTC labels, prospectively only. Needs credentials, which D3 does not allow.
- **Supports:** prospective, auxiliary.

### P7. Polygon on-chain records (CTF Exchange / V2 Exchange `OrderFilled`, `OrdersMatched`, `FeeCharged`; Conditional Tokens / PositionManager resolution events)
- **Docs:** `https://docs.polymarket.com/resources/onchain-position-data.md`, `…/resources/contracts.md` (addresses), `…/resources/blockchain-data.md`. VERIFIED-BY-DOC:
  - Event names and the v1/v2 identifier derivations.
  - Resolution: `ConditionResolution` / `payoutNumerators` (CTF). `ConditionResolved` and `OracleAggregator` (V2, results in ppm).
  - Record the exchange address or EIP-712 domain version ("2" = CTF, "3" = V2) per fill.
- **Coverage:** CLOB from 2022-11 (SECONDARY: HF SII-WANGZJ). V2 since 2026-04-28. INFERENCE: complete and immutable once final.
- **Granularity:** per fill, block timestamp in **seconds**, ordered by block number and log index.
- **Quotes/books:** none. Resting orders are off-chain.
- **Outcomes:** on-chain payout vectors, which are authoritative for settlement.
- **Revisions:** immutable after finality. Chain reorganizations are possible near the tip (INFERENCE).
- **Known pitfalls:**
  - One `OrderFilled` per maker plus a taker summary event, and operator/relayer legs, cause double counting unless cleaned (SECONDARY: `https://github.com/JasonJSant/polymarket-skilled-traders`, HF SII-WANGZJ and TimeSeventeen cards).
  - Third-party indexers can lag contract upgrades (VERIFIED-BY-DOC: `blockchain-data.md` note).
- **Access:** Polygon RPC or an indexer (not contacted). Cost: RPC provider fees or free tiers.
- **Licensing:** public blockchain data; no venue licence is attached (INFERENCE). Indexer and vendor terms apply separately.
- **Provenance:** highest for Polymarket trades and outcomes.
- **Use:** canonical Polymarket trade tape and settlement labels for development.
- **Supports:** development.

### P8. Subgraphs (Polymarket official manifests on Goldsky; community V2 subgraphs; The Graph)
- **URLs:** `https://github.com/Polymarket/polymarket-subgraph` (LGPL-3.0; activity, fpmm, oi, orderbook, pnl, polymarket, sports-oracle). Public Goldsky orderbook-subgraph endpoint quoted in `https://github.com/Polymarket/agent-skills/blob/main/market-data.md` (not contacted). `https://github.com/PaulieB14/polymarket-v2-subgraphs` (V2, start block 84902353).
- **Status:** SECONDARY: the official/old subgraph stopped indexing completely around the 2026-04-28 V2 migration (warproxxx/poly_data README; JasonJSant README). V2 coverage is community-maintained.
- **"orderbook" naming:** despite the name, these hold fills and matches, not resting depth. INFERENCE from the README descriptions.
- **Docs:** docs.goldsky.com and thegraph.com were refused by the proxy (AR-A4).
- **Licensing:** code LGPL. Hosted query terms UNRESOLVED.
- **Supports:** development (convenience only; P7 is the canonical source).

### P9. Dune, Allium, Goldsky datasets/pipelines, ClickHouse CryptoHouse
- **URLs:** listed at `https://docs.polymarket.com/resources/blockchain-data.md` (VERIFIED-BY-DOC as listed). dune.com, docs.dune.com, docs.allium.so, docs.goldsky.com, and crypto.clickhouse.com were all refused by the proxy.
- **Data:** SQL-queryable on-chain trades, balances, positions.
- **Timestamps:** block times.
- **Cost, licensing, coverage:** UNRESOLVED.
- **Use:** auxiliary cross-check. Queries are market-data access and must go through the guard.
- **Supports:** auxiliary.

---

## 3. Third-party archives and datasets

Records are compact. All are development only and not exposed to PMV. Licences are as stated on the card or repo; none was reviewed by counsel.

| ID | Source (URL) | Venue / content | Coverage (as claimed) | Granularity / timestamps | Books? | Licence | Provenance / quality | 15–60m BTC/gold relevance |
|---|---|---|---|---|---|---|---|---|
| T1 | HF `TrevorJS/kalshi-trades` (`https://huggingface.co/datasets/TrevorJS/kalshi-trades`) | Kalshi trades and markets via public API; markets "backfilled" | 2021-06 → 2026-01 (card) | trade prints; `created_time` timestamp[us, UTC]; market `yes_bid`/`yes_ask` are **fetch-time** state | no | CC-BY-4.0 (card) | derived from K1; some orphan trades dropped (card), i.e. not raw | Medium: KXBTC15M trades before 2026-01 if K1 retention is short; cross-check only |
| T2 | GitHub `Jon-Becker/prediction-market-analysis` (`https://github.com/jon-becker/prediction-market-analysis`) | Kalshi markets/trades plus Polymarket markets/OrderFilled; ~36 GiB archive on `s3.jbecker.dev` | unknown (README) | trades `created_time`; Polymarket block-level; `_fetched_at` on every row | no | code MIT; **data licence UNRESOLVED** | widely cited (SSRN/arXiv list in README); market tables are post-hoc snapshots | Medium (trades); market fields unusable as features |
| T3 | HF `DegenHedge/kalshi-btc-15m` (`https://huggingface.co/datasets/DegenHedge/kalshi-btc-15m`) | KXBTC15M per-window official strike, settlement value, result, volume (from K1), plus the vendor's own signals and logged asks | 2026-01-10 → 2026-10-04 (card) | one row per window; one logged snapshot ~3 min before close | no | CC-BY-4.0 (card) | **contains the vendor's model probabilities and graded outcomes; do not ingest `signals`** | Medium as a K1 cross-check of settlement values; otherwise redundant with K1. **Incidental exposure: see end** |
| T4 | HF `lerchen3/kalshi-orderbook-alpha` (`https://huggingface.co/datasets/lerchen3/kalshi-orderbook-alpha`) | Kalshi WS snapshots and deltas, top-3 levels plus a >1,000-lot level, for a rolling top-200-by-volume universe | unknown; files `data/YYYY/MM/DD` | local receipt **ns** plus Kalshi exchange ts and their difference (card) | partial (top 3) | "other" (UNRESOLVED) | independent capture, not colocated; universe changes over time (`universe` records) | Possibly the **only historical Kalshi L2 for KXBTC15M**, if the series was in the universe. Coverage of BTC15M UNRESOLVED; licence must be resolved first |
| T5 | GitHub `jdkatz21/Prediction_Markets_Public` (`https://github.com/jdkatz21/Prediction_Markets_Public`) | Kalshi macro (Fed) markets: trades and orderbook snapshots; replication package | paper period | daily-derived products | yes (macro only) | no LICENSE file (404); README cites a Kalshi data licensing agreement and research permission | academic | Not useful for BTC/gold. Useful as **evidence that Kalshi data-use permission/licensing matters** |
| T6 | HF `carpetxie/winniethepooh` | Kalshi daily reporting files (K4) normalized | 2023-01-01 → 2025-02-10 | daily | no | MIT (card) | derived from K4 | Not useful |
| T7 | HF `thomaswmitch/kalshi-prediction-markets-betting` / `-markets` | Kalshi trades (~5M) and market snapshots | 2023-08 → 2025-08 | trade ISO strings; market quotes are snapshot state | no | MIT (card) | small subset; selection unknown | Low (KXBTC15M launch date UNRESOLVED; likely little or no coverage) |
| T8 | HF `SII-WANGZJ/Polymarket_data` (`https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data`) | All Polymarket CLOB `OrderFilled` (V1 plus V2 since 2026-04), processed trades, markets, users | 2022-11-21 → 2026-10-04 (release 2026-10-05) | block ts **seconds**, block number, log index | no | MIT (card badge; repo LICENSE) | "re-verified against chain"; earlier releases missed V2 sell-side fills (card), so versioning matters; `markets.outcome_prices` is post-hoc | **High** for Polymarket BTC up/down trade history (bulk alternative to running P7). Verify a sample against chain |
| T9 | HF `TimeSeventeen/Polymarket-v1` and arXiv 2606.04217 (`https://arxiv.org/abs/2606.04217`) | V1 OrderFilled, cleaned daily layers (relayers removed), CTF lifecycle | 2022-11-21 → 2026-04-28 (V1 only) | block seconds | no ("None of the layers include order-book snapshots…") | CC-BY-4.0 | academic, documented cleaning, ground-truth aggressor | Medium-high for pre-V2 BTC up/down trades; ends at the V2 migration |
| T10 | HF `benjessel/polymarket_trades` | V2 fills via RPC merged with T8; weekly refresh | → ongoing | block ts | no | **none stated** (UNRESOLVED) | single maintainer | Low (licence) |
| T11 | HF `BrockMisner/polymarket-btc-updown` (card says produced by `aliplayer1/polymarket-data-pipeline` / `aliplayer1/polymarket-crypto-updown`) | Polymarket crypto up/down 5m/15m/1h/4h: markets, CLOB price history, on-chain plus WS ticks, Binance/Chainlink spot, **WS best bid/ask** | unknown | WS BBO `ts_ms` = receipt; ticks ms (on-chain rows inherit block time); spot source ts | BBO only | MIT (card) | **apparent mirror of another account's dataset (provenance UNRESOLVED)**; updated every 3 h | Medium: only free source found with historical Polymarket BBO for BTC 15m/1h. Verify upstream and licence |
| T12 | GitHub `marketlenstrade/polymarket-historical-data` (`https://github.com/marketlenstrade/polymarket-historical-data`) plus Marketlens paid archive (`marketlens.trade`, blocked) | Full book snapshots and deltas plus trades; sample includes BTC 5m/15m/hourly for one day | sample 2026-06-15 only; archive claims every book update "since March 1, 2026" | `t` ms UTC; `is_reseed` after reconnect; "trade aligned compact" variant folds deltas between trades | **yes (L2)** | sample CC-BY-4.0; archive terms UNRESOLVED | vendor; compaction loses inter-trade book dynamics in the free variant | **High if licensable**: closest to replayable Polymarket L2 history for BTC 15m/1h since 2026-03. Paid; needs AR-A7 and owner purchase decision |
| T13 | Polymarket order-book vendors: PolymarketData.co, PolyHistorical, PMData.dev, PolyOrderbooks, Telonex (all refused by the proxy) | Claimed: L2 snapshots (300 ms to 1 s), trades, Chainlink data for crypto up/down; PolymarketData.co claims from 2025-08 | per vendor claims (SECONDARY) | unknown | claimed yes | UNRESOLVED; paid tiers | unverified vendors; not affiliated with Polymarket (per PolyHistorical, SECONDARY) | Potentially high; **unverifiable now** (AR-A7) |
| T14 | GitHub `warproxxx/poly_data` (`https://github.com/warproxxx/poly_data`) | Pipeline: V2 OrderFilled via Envio HyperSync (needs token) | V2 genesis onward | block seconds | no | GPL-3.0 (code) | tool, not data; states the old Goldsky pipeline "no longer returns complete data" | Tool reference only; no code reuse without licence review |
| T15 | GitHub `manja316/polymarket-historical-data` | Gamma 15-minute snapshots, paid full set | 30+ days (README, 2026-04) | 15 min | top-10 for top markets | CC-BY-4.0 sample; paid full | Gamma-derived current-state snapshots | **Not useful** (15-minute sampling for 15-minute contracts) |
| T16 | Kaggle `hugobde/polymarket-bitcoin-15min-up-or-down` (`https://www.kaggle.com/datasets/hugobde/polymarket-bitcoin-15min-up-or-down`) | "Up" price at 1-minute fidelity for BTC 15m (SECONDARY: search summary) | ~2025-10 → 2025-12 (SECONDARY) | 1 min, CLOB price history | no | **"Unknown"** (page JSON) | single uploader | Low |
| T17 | HF `lowskillcoding/pdata-prediction-markets`, `SimpleFunctions/world-state-daily`, `sadaftkhan/sayf-episodes` (gated, 401) | multi-venue daily / episodic | various | daily / episodic | episodic only | not reviewed | not reviewed | Not useful or not accessible |

---

## 4. Settlement and reference source per BTC/gold short-horizon contract

| Contract | Documented settlement source | Status |
|---|---|---|
| Kalshi KXBTC15M (15-minute up/down) | CF Benchmarks BRTI, 60-second simple average before close vs. before open, tie → YES | SECONDARY only. The governing rulebook (CRYPTO15M?) is UNRESOLVED (K5, AR-A1). CF Benchmarks as Source Agency for Kalshi crypto is VERIFIED-BY-DOC (K6) |
| Kalshi KXBTCD (hourly/daily strike) | CF Benchmarks BRTI 60-second average; trimmed mean (excluding top/bottom 20%) under the BTC rulebook from 2024-11-27, plain mean under CRYPTO/CRYPTOSHORT | Rule texts VERIFIED-BY-DOC (K6). Which rulebook applies to which series and period is UNRESOLVED |
| Kalshi KXGOLD15M | Pyth GOLD 1-minute candle close, end ≥ start → YES; weekdays | SECONDARY only; UNRESOLVED officially |
| Polymarket BTC Up or Down 5m/15m/1h/4h (polymarket.com) | From 2026-08-07: Chainlink TWAP (60 s for 15m and 4h; the docs give a 1-hour window as an example). Before that: single price snapshot (SECONDARY: Chainlink Data Streams BTC/USD) | TWAP and dates VERIFIED-BY-DOC. Whether **1-hour** markets moved to TWAP: the changelog names only 5m, 15m, and 4h, so UNRESOLVED. Pre-2026-08-07 source is SECONDARY |
| Polymarket gold (XAUUSD) Up or Down, daily | Pyth `Metal.XAU/USD` 1-minute candle close, 4:59 PM ET | SECONDARY. Hourly or shorter gold markets: UNRESOLVED |
| Polymarket US BTC 15m | CF Benchmarks BRTI (one source) vs. Chainlink BTC/USD (another) | CONFLICTING, UNRESOLVED (docs.polymarket.us blocked) |

---

## 5. Ranked acquisition recommendation (15–60-minute BTC/gold)

1. **PMV prospective capture**: Kalshi WS book, trades, and lifecycle for KXBTC15M, KXBTCD, KXGOLD15M; Polymarket market WS for BTC up/down 15m/1h; the settlement-source feeds. This is the only source of replayable L2 with observed receipt and availability times, and the only candidate for protected evaluation. It is blocked today by F-16 eligibility, the guard prerequisites, and D3 (credentials for gated feeds). Start as soon as authorized; history accrues only from then.
2. **K1 Kalshi official historical** (markets, trades, 1-minute candles, settlement values). Use it for official labels and trade prints. First resolve retention, the cutoff lag, and Developer Agreement data-use terms (AR-3). Pull early: if the historical tier is truncated (SECONDARY: about 100 days), old KXBTC15M history may become unavailable over time. That is a reason for **prompt guarded acquisition**, not ad-hoc pulls.
3. **P7 Polygon on-chain fills and resolutions**, or **T8** as a bulk copy verified against chain samples. This is the canonical Polymarket BTC up/down trade tape and outcomes. Join with P1 for contract identity. Partition at 2026-04-28 (V2) and 2026-08-07 (TWAP).
4. **T12 Marketlens archive** (paid) or another **T13** vendor, only after licence and methodology review. This is the only path to historical Polymarket L2 for BTC 15m/1h (claimed since 2025-08 or 2026-03). Owner purchase decision required.
5. **T4 Kalshi orderbook alpha**, only if its licence permits and it contains KXBTC15M or KXGOLD15M. It is possibly the only historical Kalshi L2.
6. **P3 Data API trades** and **P4 resolutions**: convenient cross-checks of P7.
7. **T1, T9, T11**: cross-checks or gap fill. T11 needs provenance resolution.
8. **Not useful:** P2 beyond the last ~7 days at 1-minute grain; K4/T6 (daily); T15 (15-minute sampling); T7, T16, T17; T5 for BTC/gold; T3 `signals`.

**Gold:** only K1 KXGOLD15M is plausible (about 2 months of history if the SECONDARY launch date is right). Polymarket gold is daily, so off-horizon. **Gold development data is thin. E-1 should be revisited with the owner** (INFERENCE).

---

## 6. Inaccessible sources

- **Proxy-refused (user denied):** docs.goldsky.com, thegraph.com, docs.dune.com, dune.com, docs.uma.xyz, oracle.uma.xyz, docs.chain.link, data.chain.link, docs.cfbenchmarks.com, learn.polymarket.com, docs.polymarket.us, polymarketexchange.com, integrity.polymarket.com, www.polymarketdata.co, polyhistorical.com, pmdata.dev, polyorderbooks.com, marketlens.trade, www.telonex.io, predictionmarketspicks.com, calipermarkets.com, www.pyth.network, docs.pyth.network, pythdata.app, docs.allium.so, crypto.clickhouse.com, polygonscan.com, docs.envio.dev, degenhedge.com.
- **Anti-bot:** kalshi.com, HTTP 429 Vercel challenge (AR-3, existing; not retried).
- **JS-rendered, text not retrievable:** polymarket.com/tos (the Terms of Use body was not present in the HTML). Kaggle dataset page (metadata only).
- **Auth-gated:** HF `sadaftkhan/sayf-episodes` (401). Kalshi CF Benchmarks passthrough. PolyBolt TWAP channel.
- **Not attempted because outside approved scope (D1):** help.kalshi.com and `kalshi-public-docs.s3.amazonaws.com`. Both are reachable or redirecting via the proxy, but need their own access request.
- **Empty response:** `https://docs.polymarket.com/market-data/chainlink-twap.md` returned 0 bytes (redirect). TWAP content was read from `market-data/realtime-data.md` instead.

## 7. ACCESS REQUESTS (for owner decision; none used)

| ID | Domain / resource | Purpose | Intended data | Recommendation |
|---|---|---|---|---|
| AR-A1 | `kalshi-public-docs.s3.amazonaws.com/contract_terms/*.pdf` only (CRYPTO15M.pdf, the gold 15-minute terms file, BTC/CRYPTO terms) | settle U19/U20: KXBTC15M/KXGOLD15M settlement source, averaging, tie and no-data rules | contract-rule PDFs only; **exclude `/reporting/`** (market data) | temporary. The proxy is host-level, so prefer owner-supplied copies or a path-restricted fetch |
| AR-A2 | `help.kalshi.com` (crypto and commodity settlement articles) | corroborate settlement rules | help articles | temporary |
| AR-A3 | `docs.polymarket.us`, `polymarketexchange.com/files/legal/*` | Polymarket US API (history endpoints, `asset-prices/history`), rulebook, data and redistribution terms, settlement source | documentation and legal text | temporary; **high priority if the owner is a US person** |
| AR-A4 | `docs.goldsky.com/chains/polymarket`, `docs.dune.com`, `docs.allium.so`, `thegraph.com/docs` | indexer coverage, lag, terms | documentation only, no queries | temporary, low |
| AR-A5 | `docs.chain.link` (Data Streams and TWAP methodology pages; **not** `data.chain.link`, which displays live prices) | Polymarket settlement-source methodology and timestamps | documentation | temporary (coordinate with the reference-feed inventory) |
| AR-A6 | `docs.pyth.network` (Metal.XAU/USD, GOLD candle methodology) | gold settlement source for KXGOLD15M and Polymarket gold | documentation | temporary (reference-feed scope) |
| AR-A7 | vendor docs, pricing, and terms pages: `marketlens.trade`, `www.polymarketdata.co`, `pmdata.dev`, `polyorderbooks.com`, `polyhistorical.com`, `www.telonex.io` | assess historical-L2 licensing, capture method, timestamp semantics | documentation, terms, and pricing only; no samples | temporary |
| AR-A8 | `docs.uma.xyz`, `docs.envio.dev`, `degenhedge.com` (methodology page) | low-priority methodology checks | documentation | optional |
| AR-3 | `kalshi.com` (existing): Developer Agreement, `/regulatory/filings`, `/market-data`, fee schedule | data-use and licensing terms for K1; filings index | legal and docs | already requested; still blocking for K1 licensing |

## 8. Key unresolved items

1. Kalshi historical retention and cutoff lag (U15). KXBTC15M and KXGOLD15M listing start dates.
2. The KXBTC15M governing rulebook text. Whether the rules changed during the series' life (trimmed vs. plain mean, no-data rule).
3. Official KXGOLD15M existence and terms.
4. Polymarket `/v2/prices-history` price definition, and the 30-day vs. 60/90-day retention conflict.
5. Polymarket 1-hour BTC up/down settlement rule after 2026-08-07. The exact pre-2026-08-07 snapshot source.
6. Data-use licensing for Kalshi API data (Developer Agreement), Polymarket API data (ToS not retrievable), and T2/T4/T10/T12/T13.
7. Polymarket US: history availability, settlement source, and eligibility. Owner jurisdiction (F-16).
8. Match-to-block delay on Polygon for Polymarket fills, needed to estimate availability time.

## Incidental exposure

- **HF dataset card `DegenHedge/kalshi-btc-15m` README** (read in full before filtering). It contains aggregate outcome-dependent statistics for KXBTC15M over 2026-01-10 to 2026-10-04 (signal win rate vs. entry price, strike and BTC price ranges, specific window anomalies). **No values recorded.** All of it is public, already-past development-era data. Flagged so the lead can decide whether a contamination note is needed in HOLDOUT_ACCESS_LOG.md. INFERENCE: probably not needed, because no protected scope exists and this period can only be development data. The rule "before a real protected scope is declared, agents do not inspect real market observations" was nonetheless touched.
- **WebSearch result summaries** (third-party settlement and gold articles) included aggregate figures: settle-match statistics, fee and volume totals, manipulation-study totals. No values recorded.
- **arXiv 2606.04217 abstract:** aggregate classifier accuracies on Polymarket V1 data. No values recorded.
- **polymarket.com/tos HTML:** navigation and category labels only were viewed. Embedded page JSON was not inspected. No values recorded.
