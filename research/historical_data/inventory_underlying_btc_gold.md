# Underlying-asset historical data inventory: Bitcoin and gold (Phase 1 batch 3, sections B and C)

**Status: research record, NOT an approved requirement. Documentation-only inventory and design input. No market data was downloaded, no market-data API host was contacted, no account was created, and no market values were used or recorded.** Prepared 2026-10-16 (UTC) by the Data Scientist agent on branch `phase1/historical-data-strategy`. Sources and hashes are in `research/sources.md` (section "Phase 1 batch 3").

Owner direction this responds to (2026-10-16): use verified historical data aggressively for development where provenance, timestamps, semantics, licensing and quality are adequate; build prospective capture in parallel; historical data exposed to development can never become protected holdout data; gold stays in scope.

## 0. How to read this record

- Tags: **VERIFIED-BY-DOC** (statement read on the provider's own page, URL given and hashed where practical); **SECONDARY** (third-party page or search-engine summary, not verified on the primary source); **INFERENCE** (agent reasoning); **UNRESOLVED** (not determinable from accessible documentation).
- "Search summary" means the WebSearch tool's synthesized answer. Those summaries are SECONDARY. One WebFetch summary (CFTC filing, §B.13) was demonstrably hallucinated and was discarded. Treat every SECONDARY claim as a lead to verify, not as a fact.
- Prices and plan costs quoted below are vendor list prices from documentation (not market observations). They change; reverify before any purchase.
- **Protection class** for every source below: per `docs/protected_information.md`, all BTC spot, CF Benchmarks indices, CME BTC futures, gold spot, LBMA, COMEX futures, gold ETFs and public datasets are equivalent observables of protected BTC/gold contracts. Therefore: historical data from any of these sources is **development-only** for whatever interval is exposed, and the same source covering the eventual protected interval must be **embargoed by the data-access guard** (`PROTECTED_EQUIVALENT_OBSERVABLE`). No source below is a protected-evaluation source by itself; protected evaluation data can only be prospectively captured data that has never been exposed.
- **PMV exposure to date:** no real observations from any source in this file have been exposed to PMV (consistent with START_HERE.md's "no real market observations before a protected scope is declared"). Incidental exposures during this research are listed in §6.

---

## 1. Reference / settlement providers actually used by the target contracts

This section is the reference-provider side only; contract rules and venue verification belong to the venue agent.

| Contract family | Reference source | Evidence | Status |
|---|---|---|---|
| Kalshi BTC (incl. `KXBTC15M`) | CME CF Bitcoin Real Time Index (**BRTI**), CF Benchmarks | CF Benchmarks BRTI page: "The BRTI is the price input for settlement of event contracts and prediction markets offered by Kalshi, CME Group and ForecastEX" (https://www.cfbenchmarks.com/data/indices/BRTI). Kalshi `cfbenchmarks_value` channel defines a 60 s windowed average before each quarter-hour (batch 2, venue_verification §1.7). Third-party pages quote the series rule "60 RTI prices are collected [in the last minute]... average... rounded to 2 decimals". | Provider: **VERIFIED-BY-DOC** (provider's own statement). Exact per-series averaging rule: **SECONDARY / UNRESOLVED** until read on Kalshi's official rules/contract terms (venue agent). |
| Polymarket BTC 5 m / 15 m / 4 h Up-or-Down | **Chainlink Data Streams BTC/USD TWAP, 60 s lookback** | Polymarket docs `concepts/resolution.md`: "Chainlink TWAP for up-down markets"; changelog 2026-08-07 (TWAP resolution; 5 m 30 s, 15 m and 4 h 60 s) and 2026-08-14 (5 m moved to 60 s at 00:00 UTC). | **VERIFIED-BY-DOC** (Polymarket docs). Before 2026-08-07 these markets settled on a non-TWAP Chainlink stream (SECONDARY): **historical labels have a regime break**. |
| Polymarket BTC hourly / daily Up-or-Down | Possibly **Binance BTCUSDT 1 h candle** | Search summaries only. Polymarket's resolution doc uses a one-hour BTC/USD example under the Chainlink TWAP section, which conflicts. | **UNRESOLVED** (conflict). Per-market rules must be read. |
| Kalshi gold (`KXGOLD15M`, `KXGOLDH`, `KXGOLDD`, `KXGOLDW` per third parties) | **Pyth** (third parties cite "Pyth - Gold" and `Metal.Index.GOLD/USD`; one 1-minute candle close rule) | Kalshi docs list Pyth gold feeds `Metal.XAU/USD` (ID 346), `Metal.Index.GOLD/USD` (3153, "Blended Gold Index in USD (24/7)"), `Metal.Index.1OZGOLD/USD` (3712) in the paid `pyth_value` channel (https://docs.kalshi.com/websockets/pyth-value.md). Series existence and rules: SECONDARY only (predictionmarketspicks.com etc.); batch 2 found no gold event series in Kalshi docs. | Provider family Pyth: **SECONDARY + doc-consistent**. Which Pyth feed (XAU spot vs blended index), candle definition, timezone: **UNRESOLVED**. |
| Polymarket gold "XAUUSD Daily Up or Down" | **Pyth `Metal.XAU/USD`** 1-minute candle "Close", 4:59 PM ET | Search summary quoting market rules (pythdata.app link). Polymarket docs list `xauusd` as a PolyBolt reference symbol with vendor `pyth`/`chainlink`/`massive`. | **SECONDARY**. |
| Polymarket gold "GC Up or Down" | **CME official daily settlement**, active month GC, as first published | Search summary quoting market rules; uses first-published value regardless of later correction. | **SECONDARY**. |
| Kalshi `GOLDPERP` (perpetual; out of approved scope) | UNRESOLVED (CFTC filing 2026-09-08 not text-extractable here) | §B.13 | **UNRESOLVED**. |

Consequences (INFERENCE):
1. **The label source is never a raw exchange.** Kalshi BTC labels depend on BRTI, Polymarket short BTC labels on a Chainlink TWAP, gold labels probably on Pyth. Exchange tick data is a *feature* source; it cannot reproduce labels exactly. The supervised label must come from official venue resolution (START_HERE.md Data and Contract Identity); the reference series is needed for (a) features expressed in the settlement index's units (distance to strike/open in index terms), (b) auditing label reconstruction, and (c) measuring basis between feature venues and the index.
2. **Basis risk is a first-class research variable.** BRTI is an order-book-based, cross-exchange, exponentially depth-weighted mid (methodology per search summary of CF Benchmarks' RTI guide v17; SECONDARY). Coinbase last trade ≠ BRTI ≠ Chainlink TWAP. For 15-minute windows with a 60 s averaging rule, the settlement-window averaging itself creates predictable structure in the final minute (mechanical, not "velocity"). That should be studied explicitly with time remaining as a variable.
3. **The equivalence catalog is incomplete for these sources** (see §5, escalation E-U1).

---

## 2. Bitcoin sources (section B)

Field order for each record: provider/URL · data type · asset/venue · coverage · granularity · trades / quotes / book · contract metadata · outcomes/settlements · timestamps · revisions · access/auth · cost · licensing · provenance quality · gaps · likely PMV use · class · PMV exposure.

### B.1 CF Benchmarks: BRTI (and BRR / BRRNY)
- **URL:** https://www.cfbenchmarks.com/data/indices/BRTI; methodology and constituent PDFs at `docs.cfbenchmarks.com` (not fetched, see licensing note). Kalshi passthrough doc: https://docs.kalshi.com/cfbenchmarks/rest-passthrough.md.
- **Type:** benchmark index (calculated, not traded). BTC-USD.
- **Coverage:** BRTI live since 2016-11-14 per older constituent list (SECONDARY). History depth via API: UNRESOLVED.
- **Granularity:** "once per 200 millisecond" index; "calculated every second" (both phrases on the page; VERIFIED-BY-DOC). Standard feed per second; 200 ms on request; WebSocket `maxResolution=PER_200MS` (SECONDARY).
- **Trades/quotes/book:** none (index values only). Inputs are constituent order books (SECONDARY: RTI methodology).
- **Constituents (SECONDARY, official PDF named but not fetched):** Coinbase, Kraken, Bitstamp, Gemini, itBit, LMAX Digital, Bullish (BRTI from 2025-07-14), Crypto.com (from 2025-03-31). Membership changes over time: point-in-time constituent history is required for any BRTI reconstruction.
- **Outcomes/settlements:** BRTI is the Kalshi BTC settlement input (VERIFIED-BY-DOC, provider statement). BRR (daily 4 pm London, trade-based VWM) settles CME BTC futures (INFERENCE from general knowledge; not verified here).
- **Timestamps:** index publication time, UTC (INFERENCE). Kalshi `cfbenchmarks_value` uses `quarter_close_ts_ms` windows (batch 2).
- **Revisions:** UNRESOLVED (no republication policy read). Hard Fork Policy and Benchmark Statement PDFs exist (VERIFIED-BY-DOC: listed on page).
- **Access:** (a) CF Benchmarks licence direct (contact sales); (b) **Kalshi CF Benchmarks REST passthrough**: authenticated Kalshi Trade API, entitlement-gated, forwards to `https://www.cfbenchmarks.com/api/v1/`, includes `history/values` returning **tick-level** history, some indices intra-second (VERIFIED-BY-DOC, docs.kalshi.com); 50 read tokens per call; (c) CME DataMine `CRYPTOCURRENCY` dataset, "second interval index values for Bitcoin" with symbol `BRTI` (VERIFIED-BY-DOC, CME's own `datamine_python` README on GitHub).
- **Cost:** direct licence UNRESOLVED; Kalshi passthrough: price UNRESOLVED (entitlement); DataMine: priced behind login (SECONDARY).
- **Licensing:** website: "Use and distribution of the CF Benchmarks data requires a license" and no use "to create, calculate, issue, settle... any financial instruments... without the express written consent" (VERIFIED-BY-DOC). Whether Kalshi-passthrough data may be stored and used for model development: **UNRESOLVED (blocking for that route)**. **The CF Benchmarks website terms prohibit scripts/robots accessing the site without permission**; therefore no further automated fetches of cfbenchmarks.com or docs.cfbenchmarks.com were made (see §7 AR-U2).
- **Provenance quality:** authoritative (UK BMR-registered administrator).
- **Gaps:** methodology parameters, constituent history, restatement policy not read.
- **PMV use:** reference series for Kalshi BTC features, label audit, basis studies; essential.
- **Class:** development (historical) / embargo protected interval / prospective capture of the Kalshi `cfbenchmarks_value` channel is the cheapest forward source.
- **PMV exposure:** none.

### B.2 Chainlink Data Streams: BTC/USD TWAP 60 s (Polymarket resolution source)
- **URL:** https://docs.chain.link/data-streams (**blocked by sandbox proxy**); Polymarket docs https://docs.polymarket.com/market-data/chainlink-twap and `concepts/resolution.md` (fetched).
- **Type:** oracle report stream (DON consensus). BTC/USD.
- **Coverage:** TWAP feeds live ~19:55 UTC 2026-07-31 (SECONDARY). Non-TWAP BTC/USD stream earlier. Retention of historical reports: **UNRESOLVED**.
- **Granularity:** reports per second-scale; TWAP lookback 60 s ("windowSeconds: 60 describes the lookback period, not the update interval": VERIFIED-BY-DOC, Polymarket). Polymarket reference stream: "up to five times per second" (VERIFIED-BY-DOC, applies to PolyBolt price feeds).
- **Trades/quotes/book:** none; v3 crypto schema has bid/ask/mid (SECONDARY); TWAP uses v2 schema (`validFromTimestamp`, `observationsTimestamp` in seconds, `price`) (SECONDARY).
- **Outcomes:** Polymarket up/down "price to beat" and "final price" both from the same TWAP stream; Up if final ≥ start (VERIFIED-BY-DOC).
- **Timestamps:** report span `[validFromTimestamp, observationsTimestamp]`, seconds resolution; TWAP span anchored to `observationsTimestamp`, sliding (SECONDARY from a documentation PR summary). Polymarket PolyBolt payloads carry `timestamp`, `receivedAt`, `isCarriedForward`, `seq`, `dropped`, `source` (VERIFIED-BY-DOC). Note: `source` can change per reconnect; Chainlink became default on `price.crypto` 2026-10-02 (VERIFIED-BY-DOC, changelog).
- **Revisions:** reports are signed; restatement: UNRESOLVED.
- **Access/auth:** Chainlink REST/WebSocket with HMAC credentials via self-serve portal (SECONDARY); Polymarket PolyBolt with CLOB API credentials; subscription gives only a 2-minute snapshot of history (VERIFIED-BY-DOC).
- **Cost:** ~USD 150/month per stream (SECONDARY, news report).
- **Licensing:** UNRESOLVED.
- **Third-party archive:** PMData sells recorded 30 s/60 s TWAP since 2026-08-01 (SECONDARY; provenance = third-party WebSocket capture; quality unknown).
- **PMV use:** label audit and feature alignment for Polymarket BTC short markets. History is ~2.5 months: thin for development; regime break at 2026-08-07/14.
- **Class:** development for exposed history; embargo protected interval; prospective capture recommended now.
- **PMV exposure:** none.

### B.3 Coinbase Exchange (and Advanced Trade)
- **URL:** https://docs.cdp.coinbase.com/exchange/ (fetched: candles, trades, WebSocket channels, pagination).
- **Type:** primary venue market data; BTC-USD; BRTI constituent.
- **Coverage:** trades REST paginated by `trade_id` cursors (`before`/`after`) (VERIFIED-BY-DOC); depth of retrievable history not stated (UNRESOLVED). Candles: granularity ∈ {60, 300, 900, 3600, 21600, 86400} s, ≤300 per request, "Historical rate data may be incomplete. No data is published for intervals where there are no ticks", "should not be polled frequently" (VERIFIED-BY-DOC).
- **Book:** no historical order book from Coinbase. Live: `level2` (now **authentication required**), `level2_batch` unauthenticated, 50 ms batches, `full` channel authenticated, sequence numbers and heartbeat (VERIFIED-BY-DOC).
- **Timestamps:** ISO-8601 UTC microseconds in WebSocket `time` (VERIFIED-BY-DOC from example payloads); semantics (matching-engine vs gateway) UNRESOLVED. Candle `time` = bucket start (VERIFIED-BY-DOC).
- **Revisions:** busted/cancelled trades policy UNRESOLVED.
- **Access/auth:** public REST for trades/candles; API host not contacted.
- **Cost:** free (rate-limited).
- **Licensing:** Coinbase market-data licence terms UNRESOLVED; Tardis states Coinbase data "is subject to Coinbase market data license restrictions" (SECONDARY). Amberdata claims to be an authorized Coinbase redistribution partner (SECONDARY).
- **Provenance quality:** primary-venue; good for trades; no historical book.
- **PMV use:** core feature venue (largest USD constituent); trade-tape velocity features; prospective L2 capture.
- **Class:** development (historical) / embargo / prospective capture candidate. **Exposure:** none.

### B.4 Kraken
- **URL:** https://docs.kraken.com/ (index fetched). Downloadable archives: support.kraken.com articles 360047543791 (time and sales) and 360047124832 (OHLCVT) (**not fetched; SECONDARY via search**).
- **Type:** primary venue; XBT/USD; BRTI constituent. Owner Payward also owns CF Benchmarks (VERIFIED-BY-DOC, CF Benchmarks footer): note conflict of interest, not a data-quality defect.
- **Coverage:** official full trade archive "every public trade for every pair from first trade through 30 September 2026", ~2 GB parts at assets.kraken.com with SHA-256 sums; OHLCVT 1–1440 min through 30 June 2026 (SECONDARY). REST Trades/OHLC endpoints with limits (SECONDARY).
- **Book:** WebSocket v2 `book` (depth up to 1000 per Tardis), `level3` (individual orders), CRC32 checksums (VERIFIED-BY-DOC, docs index). No historical book from Kraken.
- **Timestamps:** archive timestamp precision/semantics UNRESOLVED.
- **Revisions:** archive is quarterly-appended (SECONDARY); correction policy UNRESOLVED.
- **Access:** free downloads; no auth (SECONDARY).
- **Licensing:** UNRESOLVED (must be read before download).
- **Provenance quality:** primary venue's own archive: high for trades if timestamps are adequate.
- **PMV use:** cheapest long, complete trade tape of a BRTI constituent; good first development dataset for trade-based velocity features. Not sufficient for book features.
- **Class:** development (pre-cutoff only); embargo. **Exposure:** none.

### B.5 Binance spot and data.binance.vision
- **URL:** https://github.com/binance/binance-public-data README and `TERMS_AND_CONDITIONS.md` (fetched; data.binance.vision itself not contacted).
- **Type:** daily/monthly archives of aggTrades, klines (1s..1mo), trades; futures UM/CM (VERIFIED-BY-DOC).
- **Asset:** BTCUSDT (USDT-quoted, **not USD**; not a BRTI constituent; INFERENCE).
- **Timestamps:** spot timestamps in **microseconds from 2025-01-01**, milliseconds before (VERIFIED-BY-DOC) – a schema break to handle.
- **Revisions:** "Archived files may be updated at a later date"; changelog of replaced files with checksums (2022-08-08 kline fix, 2022-04-21 aggTrade alignment) (VERIFIED-BY-DOC). Daily files next day; monthly on first Monday.
- **Licensing (VERIFIED-BY-DOC, Vision Dataset Terms v1.0, updated 2026-08-26):** **CC BY-NC-SA 4.0, non-commercial only**; permitted uses include "algorithmic historical backtesting for purely personal non-production research"; **prohibits use "for live proprietary trading execution, automated commercial order generation"**; commercial use needs an enterprise licence. Repository code is MIT; the data is not.
- **INFERENCE:** PMV is designed to trade live; developing its production model on Binance Vision data is at best ambiguous and likely outside the licence. **Do not acquire without owner/legal review (E-U3).** Binance.com is also generally unavailable to US persons (INFERENCE; jurisdiction check needed).
- **PMV use if licensed:** label audit if a Polymarket hourly market truly settles on Binance BTCUSDT candles; cross-venue lead-lag. Otherwise not needed.
- **Class:** development only if licensed; embargo. **Exposure:** none (README example rows are non-BTC illustrations; not recorded).

### B.6 Gemini
- **URL:** developer.gemini.com (**blocked**); Market Data Agreement at gemini.com/legal (not fetched).
- **Coverage:** public trades REST limited to ~7 days, 500 records/request (SECONDARY); ms timestamps (SECONDARY). WebSocket v3 from 2026-07-24 (Tardis, SECONDARY): format break.
- **Licensing:** personal/internal use, analysis permitted; redistribution needs separate agreement (SECONDARY).
- **PMV use:** BRTI constituent; history only via vendors (Tardis since 2019-08-30, Amberdata since 2017). Low marginal value vs Coinbase/Kraken except for BRTI reconstruction.
- **Class:** development; embargo. **Exposure:** none.

### B.7 Bitstamp
- **URL:** API docs live under www.bitstamp.net/api (not fetched per hard rule).
- **Coverage:** REST transactions back ≤1 day (SECONDARY); WebSocket v2 public; `microtimestamp` field (SECONDARY). History via Tardis (since 2019-03-30) or Amberdata (since 2011) (SECONDARY).
- **Licensing:** UNRESOLVED. **PMV use:** BRTI constituent; vendor history only. **Class:** development; embargo. **Exposure:** none.

### B.8 Bullish, Crypto.com, LMAX Digital, itBit (other BRTI constituents); OKX, Bybit
- Bullish docs at docs.exchange.bullish.com (not fetched; one mistaken attempt at `api.exchange.bullish.com/docs/...`, an API host, was refused by the proxy, no content received). Public REST: last 100 trades (SECONDARY). Coin Metrics and Amberdata carry Bullish (SECONDARY).
- Crypto.com, LMAX Digital, itBit: not researched beyond constituent status (UNRESOLVED). Needed only for faithful BRTI reconstruction, which is not recommended (use BRTI history directly, B.1).
- **OKX / Bybit: not justified.** Not BRTI constituents, USDT-quoted, offshore; marginal for USD-index-settled contracts. Exclude unless a cross-market lead-lag study is approved.

### B.9 Tardis.dev (vendor; tick trades and full L2/L3 book history)
- **URL:** tardis.dev, docs.tardis.dev (**both blocked**). All facts SECONDARY (search summaries of Tardis docs).
- **Coverage:** Coinbase since 2019-03-30 (match, l2update, snapshot, ticker, full-channel events), Kraken since 2019-06-04 (book depth 1000), Bitstamp since 2019-03-30, Gemini since 2019-08-30; also Binance and many others.
- **Granularity:** raw exchange WebSocket messages as captured, plus normalized CSVs (incremental_book_L2, trades, quotes).
- **Timestamps:** exchange timestamp plus Tardis **`local_timestamp` (arrival at Tardis collector)**; when equal, exchange provided none. This is exactly the source-vs-receipt distinction PMV needs (SECONDARY).
- **Revisions/gaps:** collector outages and exchange format changes (Kraken v1→v2 on 2026-07-10; Gemini v2→v3 2026-07-24) (SECONDARY).
- **Access/cost:** subscriptions; spot-only from ~USD 350/month (academic) to 700/1,000/3,000; minimum order USD 300; history depth 4–5 years depending on billing; no fixed-range purchases (SECONDARY). First day of each month downloadable free (do not use: data sample).
- **Licensing:** Tardis ToS defines distribution; Coinbase restrictions flagged (SECONDARY; UNRESOLVED in detail). Client libraries MPL-2.0.
- **Provenance quality:** high (raw messages, receipt timestamps, replayable). Collector location/latency relative to PMV's future collector is different: receipt timestamps are not PMV's.
- **PMV use:** the best single historical source for **sub-minute book and trade-flow features** across BRTI constituents and for designing PMV's own replay format.
- **Class:** development (pre-cutoff); embargo. **Exposure:** none.

### B.10 Kaiko (and Amberdata, reported acquired by Kaiko in 2026: SECONDARY, unconfirmed)
- **URL:** https://docs.kaiko.com (fetched: timestamp, tick-level trades, raw order book snapshot).
- **Trades:** tick-level normalized; `timestamp` is "provided by the exchange **or the collection timestamp**" (VERIFIED-BY-DOC): **ambiguous per record**, a timestamp-discipline defect for PMV.
- **Book:** raw snapshots to 10% depth, "**at least one snapshot per minute**", timestamp = when Kaiko sent the REST request (VERIFIED-BY-DOC). Too coarse for sub-minute book features.
- **Timestamps:** UTC, ms in REST (VERIFIED-BY-DOC); trades nanoseconds field (VERIFIED-BY-DOC).
- **Reference rates/indices:** Kaiko benchmarks with replication data (VERIFIED-BY-DOC, index); not used by target contracts.
- **Cost/licensing:** enterprise, quote-only (UNRESOLVED).
- **Amberdata (SECONDARY):** Coinbase since 2014-12-01, full-depth book events for some exchanges, 1-minute REST snapshots; claims Coinbase redistribution partnership; standard licence allows commercial use, prohibits redistribution; quote-only pricing; docs.amberdata.io **blocked**.
- **PMV use:** alternatives to Tardis; not recommended first because of cost opacity and timestamp ambiguity (Kaiko).
- **Class:** development; embargo. **Exposure:** none (example payload price lines filtered).

### B.11 Coin Metrics (community vs pro), CoinDesk Data (formerly CCData/CryptoCompare)
- Coin Metrics docs index fetched (https://docs.coinmetrics.io); detail pages at gitbook-docs.coinmetrics.io and coinmetrics.io terms (redirect to www.talos.com) **blocked**. Community API: daily metrics, CC BY-NC 4.0, no market trades/books, live-only 1 s reference rate (SECONDARY). Pro: trades, books, candles, reference rates (SECONDARY). **Community tier: not useful** (daily, non-commercial). Pro: enterprise alternative to Tardis/Kaiko.
- CoinDesk Data: free tier ended 2026-05-21; L1/L2 history since 2020-09 (exchange-dependent), 1-minute full snapshots, quote-only pricing (SECONDARY); ccdata.io and developers.ccdata.io **blocked**. **Not recommended** (1-minute books, opaque pricing).

### B.12 Databento (CME BTC futures; crypto indices)
- **Crypto spot: not offered** (SECONDARY; Binance on roadmap). CME BTC/MBT futures are in GLBX.MDP3 (see C.1). CME event contracts (incl. Bitcoin, Gold) in GLBX.MDP3 since 2025-09-25 (VERIFIED-BY-DOC, Databento blog).
- **DBIX.CORE (2026-10-14):** Cboe CGIF indices incl. crypto benchmarks from Coin Metrics, CoinRoutes, Lukka, Cboe RealPrice; crypto indices update every second (VERIFIED-BY-DOC); history from 2025-11-23 (SECONDARY). **Does not include BRTI** per the listed providers (INFERENCE).
- **PMV use:** CME BTC futures basis/lead-lag as auxiliary features; CME event-contract books as a cross-venue comparison (scope expansion, optional).

### B.13 CFTC filing for Kalshi GOLDPERP (context only)
- https://www.cftc.gov/filings/ptc/ptc09082624176.pdf (downloaded as documentation, SHA-256 in sources file). Text not extractable with available tools; a WebFetch summary asserting LBMA settlement was contradicted by a second query and is **discarded as hallucinated**. Perpetuals are outside approved scope. Reference source **UNRESOLVED**.

---

## 3. Gold sources (section C)

### C.1 Databento GLBX.MDP3 (CME Globex: COMEX GC, MGC, 1OZ; also CME BTC futures)
- **URL:** https://databento.com/docs/venues-and-datasets/glbx-mdp3 and /pricing (JavaScript shells; no content retrievable); facts from Databento blog pages (fetched) and search summaries.
- **Type:** exchange feed normalized (CME MDP 3.0); CME, CBOT, NYMEX, **COMEX** futures, options, spreads (SECONDARY for venue list).
- **Coverage:** from **2010-06-06**; **MBO only from 2017-05-21**; before that MBP-10 max, backfilled from CME DataMine legacy FIX/FAST (VERIFIED-BY-DOC, blog 2024-12-03).
- **Schemas:** MBO, MBP-1, MBP-10, TBBO, trades, BBO intervals, OHLCV, definition, statistics, status (SECONDARY); statistics gains UPPER/LOWER_PRICE_LIMIT (VERIFIED-BY-DOC). Settlement prices in statistics schema: INFERENCE (to verify).
- **Contract metadata:** definition schema per instrument (expiry, tick, etc.); per-leg spread definitions from new normalization (VERIFIED-BY-DOC).
- **Timestamps (SECONDARY except where noted):** `ts_event` = matching-engine-received time (ns); `ts_recv` = Databento capture-server receipt (ns); `ts_in_delta` = matching-engine send time relative to `ts_recv`. **Pre-2017-05-21: all timestamps from tag 52 SendingTime, `ts_in_delta`=0, `F_BAD_TS_RECV` set on all messages** (VERIFIED-BY-DOC). Pre-2017 data is therefore unsuitable for latency-sensitive features. CME session times are US Central Time with DST (INFERENCE / standard CME practice; authoritative hours UNRESOLVED because cmegroup.com is unreachable).
- **Revisions:** **normalization changed retroactively for the full history on 2026-08-08** (per-leg definitions, standalone `F_LAST` record with action `N`, price limits, implied-matching status, FX spot class) (VERIFIED-BY-DOC). PMV must version any Databento pull by retrieval date and normalization version.
- **Access/auth:** API key; historical API host not contacted.
- **Cost:** historical pay-as-you-go (blog: usage-based historical remains, VERIFIED-BY-DOC); "from USD 0.50/GB" and plans USD 199 / 1,750 / 4,500 per month after 2026-06-22 (SECONDARY); Standard plan reportedly includes 16+ years L0, 1 year L1, 1 month L2/L3 (SECONDARY).
- **Licensing:** Databento states historical (T+1) data for internal use does not need an exchange licence; redistribution or professional/redistributor status triggers CME licensing (SECONDARY; the fetched FAQ page confirms Databento routes users to exchange licensing but the T+1 statement was not verified on a fetched page). CME Historical Distribution Licence, DDLA for derived works (SECONDARY). **Whether PMV's production model trained on this data is a "derived work" requiring a DDLA: UNRESOLVED (E-U4).**
- **Provenance quality:** high from 2017-05-21 (exchange MBO, dual timestamps).
- **Gaps:** issue-tracker reports missing status-schema data pre-2017 (SECONDARY).
- **PMV use:** **primary development source for gold intraday dynamics** (GC front month, MGC, 1OZ; 1OZ trades ~24/7 since 2026-07-24, SECONDARY), and CME BTC futures auxiliary.
- **Class:** development (pre-cutoff); embargo. **Exposure:** none.

### C.2 CME Group: COMEX GC / MGC / 1OZ specs, DataMine, licensing
- **URL:** www.cmegroup.com: two attempts (DataMine page, GC contract specs) failed with HTTP/2 stream reset: **source-access limitation (site anti-bot), not bypassed**. CME client wiki (cmegroupclientsite.atlassian.net) **blocked by proxy**. CME's GitHub `CMEGroupPublic/datamine_python` README fetched.
- **Contract metadata (SECONDARY, must be verified from CME Rulebook ch. 113 / contract specs by owner-supplied copy):** GC 100 oz, tick 0.10, physically delivered, months Feb/Apr/Jun/Aug/Oct/Dec listed 24 months; trading Sun 17:00–Fri 16:00 CT with daily 16:00–17:00 CT break. 1OZ: 1 oz, tick 0.25, cash-settled to GC settlements, ~24/7 since 2026-07-24 with weekend trades assigned next business-day trade date. MGC 10 oz, physical.
- **Daily settlement (SECONDARY):** active month = VWAP of Globex trades 13:29:00–13:30:00 ET; tiered fallbacks; other months via spread VWAPs 13:15–13:30; amended effective trade date 2026-01-12 (October added as lead month). Polymarket GC markets use the first-published settlement regardless of later correction (SECONDARY): **settlement corrections are a real label risk**.
- **DataMine (SECONDARY except tags):** Time & Sales (TICK), Market Depth MBO (MBO), CME CF Crypto Currency index (CRYPTOCURRENCY, includes BRTI second values), settlements (STL), EOD, BBO (VERIFIED-BY-DOC for tags in CME's README). Depth from 2005, BBO from 1999, T&S from 1982 (SECONDARY). Pricing behind login; education 50% discount; MDLA required; DDLA for derived works; Historical Distribution Licence for redistribution; "historical" = ≥8 h old (SECONDARY).
- **PMV use:** authoritative source for settlement history (if GC-settled contracts are in scope) and the BRTI history route; expensive/opaque; Databento covers the order-book need more cheaply.
- **Class:** development; embargo. **Exposure:** none.

### C.3 LBMA Gold Price (administered by ICE Benchmark Administration)
- **URL:** https://www.lbma.org.uk/prices-and-data/lbma-gold-price; https://www.ice.com/iba/lbma-gold-price (both fetched).
- **Type:** benchmark auction price, spot unallocated loco London; USD formation, GBP/EUR converted (VERIFIED-BY-DOC).
- **Timing:** auctions at **10:30 and 15:00 London time** (DST follows UK) (VERIFIED-BY-DOC); rounds of fixed duration, 30 s order windows, imbalance threshold; IBA holiday calendars published (VERIFIED-BY-DOC).
- **Participants:** 15 direct participants listed by LBMA (VERIFIED-BY-DOC).
- **Licensing:** "Any party using the LBMA Gold Price for valuation and pricing activities and in transactions and financial products requires a usage licence with IBA" (VERIFIED-BY-DOC). FRED deleted IBA datasets incl. LBMA gold on 2022-01-31 (SECONDARY: FRED notice summarized by search; FRED page not fetched because series pages display values). World Gold Council removed historical LBMA data 2025-03-18 at IBA request (SECONDARY). Third-party copies (DBnomics, MacroMicro) have **no evident licence: do not use**.
- **Revisions:** UNRESOLVED.
- **PMV use:** **not useful for 15-minute to 1-hour dynamics** (two prints per London business day). Relevant only if a target contract settles on LBMA (none found). **Not worth acquiring.**
- **Class:** auxiliary at most; embargo applies anyway. **Exposure:** none (page price widgets filtered; no values read).

### C.4 Pyth gold feeds (`Metal.XAU/USD`, `Metal.Index.GOLD/USD`, `Metal.Index.1OZGOLD/USD`)
- **URL:** docs.pyth.network (**blocked**); Kalshi `pyth_value` doc (fetched).
- **Type:** oracle aggregate of publisher prices; XAU spot follows market sessions; Index GOLD "Blended Gold Index in USD (24/7)" (VERIFIED-BY-DOC, Kalshi). Pyth indices launched 2026-06; gold index live 2026-06-24; built in-house with proprietary methodology, not MarketVector-administered (SECONDARY). XAU feed aggregates publishers with LBMA/COMEX/OTC access, ~50 ms updates (SECONDARY, Pyth blog).
- **Coverage/history:** UNRESOLVED (Pyth Benchmarks/historical API docs not readable). Index history at most since 2026-06.
- **Timestamps:** Kalshi feed ignores duplicate/out-of-order source timestamps per ticker; `value_usd` 8-dp string (VERIFIED-BY-DOC). Candle definitions used in settlement (1-minute close; ET timestamping): SECONDARY.
- **Access/cost:** Kalshi `pyth_value` WebSocket USD 1,000/month, first 7 days free, live only (VERIFIED-BY-DOC). Pyth Pro pricing UNRESOLVED.
- **Licensing:** UNRESOLVED.
- **Provenance quality:** methodology of the blended index unpublished to us: **a material label-semantics risk** for Kalshi gold if it settles on the index.
- **PMV use:** likely settlement reference for Kalshi gold and Polymarket XAUUSD daily; needed for label audit and index-unit features; prospective capture strongly recommended once a gold series is verified.
- **Class:** development for exposed history; embargo; not currently in the equivalence catalog (E-U1). **Exposure:** none.

### C.5 Other futures vendors (honest ranking; all SECONDARY; all vendor domains **blocked**)
| Vendor | GC/MGC coverage | Timestamps / content | Cost | Verdict for PMV |
|---|---|---|---|---|
| Tick Data LLC | GC trades from 1984, quotes (L1) from 2010; MGC from 2010-10 | ms from 2011-07; **"not collected in real time; downloaded after the close"** | min order USD 1,000 | Not needed: Databento better semantics |
| AlgoSeek | CME TAQ + 10-level MBP; start 2010/2015/2016 (conflicting) | UTC + Chicago; ms vs ns claims conflict | from USD 1,500/month rental | Not needed |
| PortaraCQG (CQG Data Factory) | GC ticks from 1987 (L1 claims doubtful pre-electronic) | ms default | quote | Not needed |
| Kibot | GC from 2009-09; trade + bid/ask at trade | seconds; ET | ~USD 3,750 bundle | Too coarse |
| FirstRate Data | GC bars 2008–2026-09 | bars | low | Bars only; baseline at most |
| Barchart OnDemand | tick/minute/EOD via API, one day per tick query | unknown | subscription | Not needed |
| Norgate | EOD only, continuous contracts | daily | ~USD 270/yr | Not useful intraday |
| Nasdaq Data Link CHRIS | **deprecated** | — | — | Not usable |

### C.6 Spot gold / XAU OTC feeds
- **Dukascopy (SWFX):** free XAUUSD tick quotes (best bid/ask from Dukascopy liquidity providers; **indicative quotes of one venue, not trades**), from ~2003-05; UTC; known crossed/zero spreads, duplicates, out-of-order records (SECONDARY). Data usage agreement UNRESOLVED; domain **blocked**. Use: auxiliary spot proxy for sessions when COMEX is closed. Not authoritative.
- **OANDA v20:** candles from S5 with bid/mid/ask, back to ~2005; no tick archive; licence = internal use only, no redistribution; website bans scrapers (SECONDARY). Auxiliary only; account required.
- **Other FX venues/ECNs:** not researched; same OTC/indicative caveat.

### C.7 Gold ETFs (GLD, IAU) and tokenized gold (PAXG, XAUT)
- ETFs: US equity hours only; NAV and creation mechanics introduce lags (INFERENCE). Available via equity data vendors (e.g. Databento equities; not researched). **Auxiliary, low priority.** Catalogued as equivalent observables already.
- Tokenized gold: 24/7 on crypto venues (Tardis/Kaiko coverage likely; UNRESOLVED); a weekend gold-dynamics proxy and possibly a Pyth index input (INFERENCE). **Auxiliary only**; issuer redemption/peg risk. Must be added to the equivalence catalog (already listed as a gap in protected_information.md prerequisite 3).

---

## 4. Ranked acquisition recommendations

**Blocking precondition for every acquisition below (E-U2):** under the owner's rule that exposed historical data can never become holdout, any purchase or download must be bounded to dates that will be development data. Because the chronological split is frozen once in Phase 2 on a dataset snapshot, the owner should first decide whether the protected holdout will be (a) prospectively captured data after a future date, or (b) the newest ~30% of a historical snapshot. Under (b), downloading "full history to present" now would consume the candidate holdout interval. Recommendation: (a), with all historical pulls capped at a cutoff that precedes the protected interval plus margin, enforced by the guard's trusted catalog. Nothing should be downloaded until the guard prerequisites marked "MUST RESOLVE BEFORE PHASE 1 AGENT-FACING REAL MARKET DATA" are closed.

### Bitcoin (most to least valuable)
1. **BRTI history** (B.1): via Kalshi CF Benchmarks passthrough (cheapest if entitlement and storage/use rights are confirmed) or CME DataMine `CRYPTOCURRENCY` (second-level BRTI). Needed for Kalshi label audit and index-unit features. Blocked on licence clarification.
2. **Tardis.dev** spot (B.9), Coinbase + Kraken + Bitstamp + Gemini L2/trades with receipt timestamps, bounded to development dates: the only economical route to sub-minute book features. One academic/solo month may suffice for a bounded pull (verify terms permit retention after the subscription ends).
3. **Kraken official trade archive** (B.4): free, complete, primary; first dataset for trade-flow velocity baselines once licence terms are read.
4. **Coinbase REST trades** (B.3): free primary tape; slower to backfill; use to cross-check vendors.
5. **Chainlink BTC/USD TWAP 60 s history** (B.2): only if Polymarket short BTC markets stay in scope; history is short (since 2026-07-31); prospective capture matters more.
6. **Databento CME BTC/MBT futures** (B.12/C.1): auxiliary basis/lead-lag; cheap PAYG; optional.
7. Kaiko / Amberdata / Coin Metrics Pro / CoinDesk Data: not recommended now (opaque cost; 1-minute books; ambiguous timestamps). Coin Metrics community: **not useful**.
8. Binance Vision: **do not use** without licence review (non-commercial; prohibits live trading use).

### Gold (most to least valuable)
1. **Databento GLBX.MDP3** GC front month, MGC, 1OZ from 2017-05-21 (MBO, dual ns timestamps), bounded to development dates.
2. **Pyth gold history** (`Metal.XAU/USD`, `Metal.Index.GOLD/USD`): only after the venue agent verifies a Kalshi/Polymarket gold series and its exact feed; methodology must be obtained first.
3. **CME settlement history** (DataMine STL, or Databento statistics if verified to carry settlements): only if GC-settlement-based markets are in scope.
4. Dukascopy XAUUSD ticks: auxiliary 24/5 spot proxy if its terms allow; indicative.
5. OANDA, tokenized gold, ETFs: auxiliary, optional.
6. Tick Data, AlgoSeek, Portara, Kibot, FirstRate, Barchart, Norgate: not worth the cost given Databento.
7. LBMA/IBA: **not useful** for this horizon; licensed; skip unless a contract settles on it.

---

## 5. Gold-source recommendation (development dynamics vs authoritative reference)

- **Best development source for gold intraday dynamics:** COMEX futures order books and trades via Databento GLBX.MDP3 (post-2017-05-21). COMEX is the most liquid transparent venue for gold price discovery, offers exchange MBO with matching-engine and capture timestamps, and has definition records for roll handling. Use the active GC month for the main series, with 1OZ for weekend dynamics after 2026-07-24. Features must handle the 16:00–17:00 CT daily break, DST shifts (CT vs UTC vs ET vs London), and roll dates (INFERENCE).
- **Authoritative reference source:** whatever the target contract names. On present evidence: Pyth (`Metal.Index.GOLD/USD` or `Metal.XAU/USD`) for Kalshi gold and Polymarket XAUUSD daily; CME official settlement for Polymarket GC daily; LBMA for none of the target contracts. These references are **not the same series** as COMEX futures. Futures carry a basis to spot (carry, delivery month), and a 24/7 blended index can move while COMEX is closed. A model trained on COMEX dynamics must therefore be evaluated against labels from the reference source, with the futures-to-reference basis measured explicitly as a feature or diagnostic.
- **Blocking unknowns for gold:** existence of a Kalshi gold series and its exact rules (venue agent; batch 2 found none in docs); the Pyth blended-index methodology; and Pyth historical availability and licence. Until these are resolved, gold work should be limited to dynamics research on COMEX data, with no label construction.

---

## 6. Incidental exposure log (no values recorded)

- `https://www.cfbenchmarks.com/data/indices/BRTI`: one line matching a price pattern was filtered unread. No values recorded.
- WebSearch summaries (third-party sites on Kalshi gold settlement, Pyth XAU structure, CME 1OZ margin examples) contained approximate gold price levels and spread/notional figures. Not recorded or used.
- Example payloads in Coinbase, Kraken, Kaiko, Polymarket and Binance documentation contain illustrative numeric prices, some with recent-looking timestamps (Polymarket 2026-09-08 BTC example). Price lines were filtered at read time and nothing was recorded. These are not treated as data.
- No protected scope is declared yet. None of this is believed to influence development, so no contamination event is proposed. The owner may decide otherwise.

## 7. Inaccessible sources

Denied by the sandbox proxy: `docs.chain.link`, `chain.link`, `docs.tardis.dev`, `tardis.dev`, `docs.pyth.network`, `ccdata.io`, `developers.ccdata.io`, `docs.amberdata.io`, `gitbook-docs.coinmetrics.io`, `www.talos.com` (Coin Metrics terms redirect), `developer.gemini.com`, `api.exchange.bullish.com` (mistaken docs path on an API host; see B.8), `cmegroupclientsite.atlassian.net`, `www.tickdata.com`, `algoseek.com`, `portaracqg.com`, `firstratedata.com`, `www.kibot.com`, `www.dukascopy.com`, `norgatedata.com`, `www.barchart.com`.

Site-side limitations, not bypassed: `www.cmegroup.com` (HTTP/2 stream reset on two attempts, then stopped); `databento.com/docs/*` and `/pricing` (JavaScript-rendered, no static content). CF Benchmarks' terms prohibit automated access, so no further fetches were made.

Not attempted: `support.kraken.com`, `assets.kraken.com` (data host, must not be contacted), `docs.exchange.bullish.com`, `fred.stlouisfed.org` (series pages display values), `data.chain.link` and `pythdata.app` (display live values).

## 8. ACCESS REQUESTS (owner decision; none are urgent for this batch)

| ID | Resource | Purpose | Intended data | Duration |
|---|---|---|---|---|
| AR-U1 | `docs.chain.link` (Data Streams pages only) | TWAP methodology, report timestamps, historical retention, licence | documentation only | temporary |
| AR-U2 | CF Benchmarks methodology, constituent-list and licensing PDFs (`docs.cfbenchmarks.com`). Because the site terms bar automated access, the owner downloads them manually and commits them, or obtains written permission | BRTI methodology, constituent history, restatement policy | documentation only | one-time |
| AR-U3 | `docs.tardis.dev` (pages only, no datasets or CSV samples) | coverage, timestamp semantics, ToS, licence retention | documentation only | temporary |
| AR-U4 | `docs.pyth.network` (+ `www.pyth.network` blog/methodology) | gold index methodology, Benchmarks history, licence | documentation only | temporary |
| AR-U5 | `support.kraken.com` (two archive articles plus Kraken data terms) | archive format, timestamps, licence | documentation only (not `assets.kraken.com`) | temporary |
| AR-U6 | CME Rulebook ch. 113 (GC), 1OZ/MGC specs, DataMine terms, ILA/DDLA, January 2026 fee list, as owner-supplied copies (the CME site blocks automated clients) | authoritative contract specs, settlement procedure, licensing | documentation only | one-time |
| AR-U7 | `gitbook-docs.coinmetrics.io`, `docs.amberdata.io`, `developer.gemini.com`, `docs.exchange.bullish.com` | vendor/venue docs | documentation only | optional, low priority |
| AR-U8 | Gold vendor sites (`www.tickdata.com`, `algoseek.com`, `www.dukascopy.com`) | verify the ranking in C.5/C.6 | documentation only | optional, low priority |

## 9. Escalations (proposed; not approved)

- **E-U1 (urgent before any real-data guard use):** The current requirement in `protected_information.md` is that the BTC catalog lists Coinbase, Binance, Kraken and Bitstamp, and the gold catalog lists spot, LBMA, COMEX, ETFs and public datasets. The concern is that this misses the actual settlement references and the other index constituents: **Pyth gold (`Metal.XAU/USD`, `Metal.Index.GOLD/USD`, `Metal.Index.1OZGOLD/USD`)**, Pyth BTC, Chainlink BTC/USD streams (spot and TWAP), BRTI via the Kalshi passthrough and the DataMine CRYPTOCURRENCY dataset, the Polymarket PolyBolt reference feeds, the remaining BRTI constituents (Gemini, itBit, LMAX, Bullish, Crypto.com), CME 1OZ/MGC and CME event contracts, and vendor archives (Tardis, Kaiko, Databento). Proposal: add these as equivalent observables in the trusted catalog. Benefit: closes embargo leaks. Tradeoff: more refusals. Classification: **blocking for real-data use**, consistent with prerequisite 3.
- **E-U2 (blocking for acquisition):** the holdout definition (prospective versus historical tail) must be fixed before any historical pull. See §4.
- **E-U3 (licence):** the Binance Vision terms are non-commercial and prohibit live-trading use. The owner or counsel should decide whether any Binance data may be used. Recommended default: exclude.
- **E-U4 (licence):** whether training a production model on CME data (Databento/DataMine) or CF Benchmarks data creates a CME DDLA or CF Benchmarks derived-use obligation. Owner/legal review is needed before a production model depends on these sources.
- **E-U5 (methodology, optional):** treat the settlement-window averaging mechanics (Kalshi's 60-second BRTI average, Chainlink's 60-second TWAP) as an explicit research axis in the final 1–2 minutes, separate from velocity. The mechanics create predictable structure that is not a velocity signal and could be mistaken for one.
- **E-U6 (data regime breaks, informational):** Polymarket switched to TWAP settlement on 2026-08-07 (5-minute markets moved to a 60-second window on 2026-08-14); Binance timestamps changed from milliseconds to microseconds on 2025-01-01; Kraken WebSocket v1 changed to v2 on 2026-07-10; Gemini v2 changed to v3 on 2026-07-24; Databento normalization changed retroactively on 2026-08-08; Databento timestamps before 2017-05-21 are flagged bad. Every dataset version and feature pipeline must carry these boundaries.
