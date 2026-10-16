# Historical data feasibility: summary and ranked recommendations (Phase 1 batch 3)

**Status:** research synthesis, not an approved requirement and not a gate record. Documentation and metadata only. No dataset, sample, or market API was used, and no market value was recorded. It synthesizes:
- `inventory_prediction_markets.md` (section A, API / Execution);
- `inventory_underlying_btc_gold.md` (sections B and C, Data Scientist);
- `inventory_open_academic_regulatory.md` (sections D, E, and F).

Reviews: `statistician_review.md` and `red_team_review.md`. Sources and hashes are in `research/sources.md`, under "Phase 1 batch 3". Everything is retrieved as of 2026-10-16 UTC.

**Standing rule.** Every historical source below is public, already past, or both. It can support **development only**. Protected evaluation needs prospective PMV capture (H-1). Nothing has been exposed to development yet, apart from the incidental aggregate exposures in §7.

## 1. Headline conclusions

1. **Neither venue publishes historical order books.** Kalshi and Polymarket both lack them (VERIFIED-BY-DOC). Historical depth for 15–60-minute contracts exists only in third-party captures (paid or license-unclear) or in PMV's future capture. The velocity-versus-book features the strategy depends on therefore cannot be developed from official history.
2. **Official history is trades, candles, and settlements, and it is enough for discovery work**, provided:
   - official per-market settlement values are the labels;
   - trades and candles get synthetic availability (H-5);
   - all metadata is treated as `POST_HOC` (H-4).
3. **Settlement and execution regimes changed inside the history.** These are hard partition boundaries for labels, costs, and dataset versions:
   - Kalshi BTC rulebooks, per CFTC filings: a 300 s trimmed average, then a 60 s trimmed mean from 2024-11-27, then plain 60 s means under the CRYPTO (2025-07) and CRYPTOSHORT (2026-03) rulebooks, with different no-data rules. Which one governs KXBTC15M is UNRESOLVED.
   - Polymarket crypto up/down: a single snapshot until 2026-08-07, then a Chainlink 60 s TWAP at open and close.
   - Polymarket V2 contracts and pUSD from 2026-04-28.
   - Polymarket taker fees: 15-minute crypto markets from 2026-01-05, all crypto markets created from 2026-03-06.
   - Polymarket taker-delay changes: 2026-08-17 and 2026-09-04.
   - Kalshi WebSocket millisecond timestamps from 2026-04-15, and `sending_ts_ms` from 2026-10-01.
   - Databento retroactive renormalization on 2026-08-08.
   - Binance switched to microsecond timestamps on 2025-01-01.
4. **Gold.**
   - Several third-party sources agree that Kalshi lists **KXGOLD15M**: launched about August 2026, weekdays, settling on a Pyth GOLD 1-minute candle (SECONDARY; official terms UNRESOLVED).
   - Polymarket gold appears to be daily only.
   - Gold contract history is therefore at most about 2 months, too short for robust development. Gold underlying dynamics are best developed from COMEX futures (§3). Gold stays in scope (P4), but **gold evidence will be thin and capture-dependent**.
5. **The reference sources are not the exchange prices.**
   - Kalshi BTC settles on CF Benchmarks BRTI; CF Benchmarks as Kalshi's source agency is VERIFIED-BY-DOC through the CFTC filings.
   - Polymarket short BTC settles on Chainlink BTC/USD.
   - Kalshi gold settles on Pyth (SECONDARY).

   Features near the strike and labels need these sources or a modeled basis to them (Statistician S-14). BRTI history needs an entitled Kalshi account or CME DataMine. Whether either licence allows storage and research use is UNRESOLVED.
6. **Public counter-evidence exists.** OpenMarket (Young 2026, arXiv 2607.26245) reports **no tradable after-cost edge** for a closely related design: Polymarket BTC 15-minute contracts against Binance order flow. This does not refute PMV's hypothesis, which covers different venues, features, and execution. It is the most direct public evidence against it, and it sets the bar: the baseline must include the market's own book-implied probability, and beating it after fees is the test (Statistician S-5, primary estimand).
7. **Licensing is the dominant unresolved risk.** It is unresolved or restrictive for:
   - Kalshi API data (the Developer Agreement is unretrieved, AR-3);
   - Polymarket (the terms of use are not retrievable as text);
   - Binance Vision (non-commercial; prohibits live-trading use);
   - CF Benchmarks (its site terms bar automated access; index data is licensed);
   - CME data (redistribution and derived-data terms);
   - most third-party archives.

   **No acquisition should precede a licence determination** for that source.
8. **Retention pressure.** Kalshi's historical-tier retention is undocumented. One secondary source reports a cutoff of about 100 days, and Polymarket's 1-minute price history keeps about 7 days. Some official history may age out while the governance prerequisites are pending. That pressure **never** justifies acquiring, parsing, or releasing data ahead of the licence determination, raw backup policy, safe-parsing controls, or release controls (Red-Team RT-B3-13). An early, owner-run, deterministic acquisition into the protected raw store would extend the S-6 collection rule to acquisition. That needs explicit owner approval, with the RT-B3-01, RT-B3-03, and RT-B3-06 conditions. If history ages out first, the owner may obtain terms manually or accept the loss as a recorded gap.

## 2. Ranked acquisition recommendations (all subject to H-1, H-2, H-7, and a licence determination)

| Rank | Source | Use | Why | Main blocker |
|---|---|---|---|---|
| 1 | **PMV prospective capture**: Kalshi WS book, trades, and lifecycle for KXBTC15M, KXBTCD, and KXGOLD15M; Polymarket market WS for BTC up/down; settlement-reference feeds; underlying exchange feeds | Development (receipt-time, PIT) and the **only** protected-evaluation source | The only source of replayable L2 with receipt times and PIT metadata | F-16, F-03 (a credential for Kalshi WS), raw backup policy, F-11/F-12/F-37, F-09 |
| 2 | **Kalshi official historical** (markets, trades, 1-minute candles, settlement values) | Official labels; trade-flow discovery | Primary, official settlement values | AR-3 (Developer Agreement data-use terms), retention unknown, H-2 |
| 3 | **Polymarket on-chain fills and resolutions (Polygon)**, re-derived from chain or taken from a packager (HF `SII-WANGZJ/Polymarket_data`, MIT, to 2026-10-04) verified against chain samples | Trade-flow and outcome history for BTC up/down | Primary-verifiable, finality-backed | Polymarket ToS; an RPC endpoint (a new access request); US eligibility (F-16); partition at 2026-04-28 and 2026-08-07 |
| 4 | **BRTI history**, through the Kalshi CF Benchmarks passthrough (entitled account) or CME DataMine CRYPTOCURRENCY (per-second) | Label audit; settlement-source features | It is the Kalshi BTC settlement source | Licence and entitlement; a credential (F-03) |
| 5 | **Databento GLBX.MDP3**: COMEX GC, MGC, 1OZ; CME BTC and MBT futures. MBO with exchange and capture nanosecond timestamps, from 2017-05-21 | Gold intraday dynamics (primary development source); BTC futures lead-lag (auxiliary) | Exchange-of-record data with documented timestamps and gap flags | Purchase (H-7), CME licence and derived-data terms (E-U4), account |
| 6 | **Tardis.dev**: Coinbase, Kraken, Bitstamp, and Gemini L2 and trades, with exchange and receipt timestamps (SECONDARY) | Sub-minute BTC book features in development | The only economical historical BTC book route | Purchase; docs proxy-refused (AR-U3); retention rights after subscription |
| 7 | **Kraken official trade archive; Coinbase REST trades** | Free primary BTC trade tapes; vendor cross-check | Primary sources | Licence terms (AR-U5); a deterministic fetch tool |
| 8 | **Polymarket paid L2 archives** (Marketlens, claimed since 2026-03-01; other vendors) | Historical Polymarket book features | The only route to historical Polymarket depth | Licence, methodology, purchase (AR-A7) |
| 9 | **Kalshi third-party L2** (HF `lerchen3/kalshi-orderbook-alpha`, top 3 levels, receipt nanoseconds). `Q4_unverified` until lineage is proven | Possibly the only historical Kalshi depth | Coverage of KXBTC15M is unknown | Licence "other"; provenance audit |
| 10 | Cross-checks (copies of one upstream are one source, not independent checks): HF `TrevorJS/kalshi-trades`, `Jon-Becker/prediction-market-analysis`, `TimeSeventeen/Polymarket-v1`, Polymarket Data API trades and resolutions | Reconciliation only | Independent copies | Licence for some; fetch-time quote fields are unusable |

**Do not use:**
- Binance Vision (E-U3);
- the Cryptolake and OANDA mirrors, which look like redistribution in breach of vendor terms;
- broker XAU/USD CFD tick sets, except as a labeled auxiliary proxy;
- third-party mirrors and repackagings (BrockMisner and its forks, pmxt through Joseph3222, papylove) until lineage to a primary source is proven (`Q4_unverified`, Red-Team RT-B3-04);
- the `signals` table of HF `DegenHedge/kalshi-btc-15m`, which contains a vendor's model probabilities and graded outcomes;
- Gamma 15-minute snapshot archives;
- Polymarket `prices-history` beyond its about 7 days of 1-minute retention;
- Kaggle single-uploader sets with unknown licences;
- Kaiko, Coin Metrics, and CoinDesk Data for now (1-minute books, opaque cost);
- LBMA/IBA at this horizon, since no target contract settles on it;
- `mlfinlab` (proprietary) and `pypbo` (AGPL) code.

## 3. Gold-source recommendation

- **Development dynamics.** Use COMEX futures through Databento GLBX.MDP3:
  - the active GC month as the main series;
  - MGC;
  - 1OZ for weekend dynamics after its launch.

  Handle the 16:00–17:00 CT daily break, CT/ET/London/UTC DST, and roll dates as versioned calendars (`docs/phase2.md` §4).
- **Authoritative reference.** Use whatever the target contract names. On present evidence that is Pyth (`Metal.Index.GOLD/USD` or `Metal.XAU/USD`) for Kalshi KXGOLD15M and Polymarket daily XAUUSD, which is UNRESOLVED officially. It is not COMEX and not LBMA. The futures-to-reference basis (carry, and the 24/7 blended index moving while COMEX is closed) must be modeled and measured.
- **Until the contract and its reference are verified** (AR-3, AR-A1, AR-U4/AR-A6), gold work is limited to underlying-dynamics research on COMEX data, with no gold labels.
- **CME access.** `www.cmegroup.com` gives no usable content to automated clients. The authoritative CME documents (Rulebook chapter 113, GC/MGC/1OZ specifications, DataMine and licence terms) need owner-supplied copies (AR-U6). Databento documentation describes the data but does not replace CME's own rules.
- **Open data cannot support gold development.** Every open intraday gold set is an unnamed-broker CFD feed or a mirror in breach of terms.

## 4. Prediction-market archive recommendations

- **Kalshi.** The official historical endpoints are primary (rank 2). Third-party copies are for reconciliation only. Every market-object field in archives is end-of-life or fetch-time state (`POST_HOC`). The only historical depth candidate is `lerchen3/kalshi-orderbook-alpha`, subject to licence and coverage checks.
- **Polymarket.** The chain is the primary record of fills and resolution (rank 3). The API is a convenience cross-check. Book history exists only from paid or third-party captures (rank 8).
  - Gamma `outcomePrices` and `lastTradePrice`, and the settlement point that `prices-history` appends, are outcome leaks and must be quarantined at normalization.
  - Block time is an event time after off-chain matching, never availability.
- **Universe enumeration.** Enumerate from creation events (Kalshi lifecycle `created`, on-chain condition preparation), never from post-hoc listings, to bound survivorship (Statistician S-16).
- **Polymarket US.**
  - polymarket.com is "close-only" for US users (VERIFIED-BY-DOC), so if the owner is a US person, polymarket.com history is research-only for development.
  - The tradable venue would be Polymarket US: a separate CFTC-regulated venue, whose history, terms, and settlement source are undocumented here (docs proxy-refused, AR-A3).
  - This is an F-16 owner question.

## 5. Inaccessible sources

- **Site-side, not bypassed:**
  - `www.cmegroup.com`: HTTP/2 reset, then a timeout; anti-bot behavior;
  - `kalshi.com`: Vercel challenge, AR-3;
  - `www.bls.gov`: 403;
  - `databento.com/docs` and `/pricing`: JavaScript-rendered, so no static content;
  - `polymarket.com/tos`: JavaScript-rendered, so no text;
  - CF Benchmarks: its terms bar automated access, so fetching stopped.
- **Refused by the sandbox proxy** (about 50 distinct hosts across the three inventories; each inventory lists its own), including:
  - Chainlink, Pyth, UMA, Goldsky, The Graph, Dune, and Allium documentation;
  - `docs.cfbenchmarks.com`;
  - Tardis, Coin Metrics, CCData, and Amberdata;
  - Gemini developer docs;
  - the gold futures vendors and Dukascopy;
  - Polymarket order-book vendors (Marketlens and others);
  - `docs.polymarket.us` and `polymarketexchange.com`;
  - `archive.pmxt.dev`;
  - eCFR, the Federal Reserve, ALFRED, and CFTC public reporting.

  Full lists are in each inventory.
- **Gated:** some HF datasets (401); the Kalshi CF Benchmarks passthrough and PolyBolt TWAP (authenticated).
- **Not attempted, out of scope:** `help.kalshi.com` and `kalshi-public-docs.s3.amazonaws.com`, both outside AR-1 D1; `assets.kraken.com` and other data hosts; FRED series pages. Live-value hosts `data.chain.link` and `pythdata.app` were not attempted by the underlying-data agent, but were attempted, and refused by the proxy, by the prediction-market agent (§7).

## 6. ACCESS REQUESTS (new; none used; for owner decision)

They are consolidated, and duplicates across inventories are merged. All are **documentation only**, with no data, samples, or queries, unless stated otherwise.

| ID | Resource | Purpose | Priority | Duration |
|---|---|---|---|---|
| AR-4 (A1) | `kalshi-public-docs.s3.amazonaws.com/contract_terms/*.pdf` only, excluding `/reporting/` (market data). The proxy is host-level, so owner-supplied copies are preferred | KXBTC15M, KXBTCD, and KXGOLD15M settlement source, averaging, tie, and no-data rules (UR-4, UR-5) | **High**; blocking for labels and E-1 | Temporary |
| AR-5 (A2) | `help.kalshi.com` | Settlement and eligibility articles | Medium | Temporary |
| AR-6 (A3) | `docs.polymarket.us`, `polymarketexchange.com/files/legal/*` | Polymarket US API, history, terms, settlement source | **High if the owner is a US person** | Temporary |
| AR-7 (A5, U1) | `docs.chain.link`, Data Streams pages only (not `data.chain.link`) | Polymarket settlement-source methodology, timestamps, retention, licence | Medium-high | Temporary |
| AR-8 (A6, U4) | `docs.pyth.network`, plus Pyth methodology pages | Gold reference methodology and history licence | **High for gold** | Temporary |
| AR-9 (U2) | CF Benchmarks methodology, constituent, and licensing PDFs, **supplied by the owner**, because the site terms bar automated access | BRTI methodology and restatement policy | **High for BTC labels** | One-time |
| AR-10 (U6) | CME Rulebook chapter 113, GC/MGC/1OZ specifications, DataMine and licence terms (ILA/DDLA), **supplied by the owner** | Authoritative gold futures specs and licensing | High for gold | One-time |
| AR-11 (U3) | `docs.tardis.dev`, pages only | Coverage, timestamp semantics, licence retention | Medium | Temporary |
| AR-12 (U5) | `support.kraken.com`, archive articles and data terms (not `assets.kraken.com`) | Kraken archive format and licence | Medium | Temporary |
| AR-13 (A7) | Polymarket L2 vendors' docs, pricing, and terms (`marketlens.trade`, `www.polymarketdata.co`, `pmdata.dev`, `polyorderbooks.com`, `polyhistorical.com`, `www.telonex.io`) | Historical Polymarket L2 licensing and capture method | Medium | Temporary |
| AR-14 (D1) | `archive.pmxt.dev`, landing and docs only | pmxt archive provenance and licence | Low-medium | Temporary |
| AR-15 (D2–D6) | `www.ecfr.gov` (17 CFR 40); `www.federalreserve.gov` (FOMC calendar); `fred.stlouisfed.org/docs`, `alfred.stlouisfed.org`; `publicreporting.cftc.gov` docs; the BLS schedule, owner-supplied | Regulation text; ex-ante macro release-time calendar (times only, no values) | Low-medium | eCFR and FOMC permanent; others temporary |
| AR-16 (A4, A8, U7, U8) | Indexer docs (Goldsky, Dune, Allium, The Graph), UMA, Envio, Coin Metrics, Amberdata, Gemini, Bullish docs, gold vendors | Lower-priority verification | Low | Temporary |

A future **data** acquisition (Kalshi historical endpoints, a Polygon RPC, vendor downloads) is a separate request under H-2 and H-7. It is never covered by these documentation requests.

## 7. Incidental exposure and process events (disclosed for owner decision)

- **Aggregate outcome statistics were read.**
  - The HF dataset card `DegenHedge/kalshi-btc-15m` contains aggregate outcome-dependent statistics for KXBTC15M over 2026-01-10 to 2026-10-04. Two research agents read it. No values were recorded in any PMV file.
  - Search-result summaries and paper abstracts contained aggregate figures (third-party Brier and edge claims on KXBTC15M, fee and volume totals, classifier accuracies).
- **Consequences.**
  - This information is outcome-dependent and predates 2026-10-16. No cycle or protected scope exists, so no HOLDOUT_ACCESS_LOG.md event can be recorded. The ledger needs a cycle.
  - It **rules out** using any BTC-family period (and, given search summaries with recent gold levels and F-06, any gold-family period) ending on or before 2026-10-16 as an "unexamined snapshot" holdout under H-1 option (a). Under the recommended prospective formation (b), it has no effect on the holdout.
  - Recommendation: record it in the first cycle's registration as a pre-cycle disclosure, and start the first protected interval after 2026-10-16 plus margin.
- **Process events.**
  - One agent requested a documentation path on an API host (`api.exchange.bullish.com`). The proxy refused it and nothing was returned.
  - One agent fetched `cfbenchmarks.com` pages before reading that its terms bar automated access, and stopped once it had read them.

  The cfbenchmarks.com page output contained a live BRTI value, and nothing was recorded. The API-host request is a serious near miss, stopped only by the network layer. It has an incident record (`incident_2026-10-16_api_host_request.md`).
  - The prediction-market agent also attempted live-value display hosts (`data.chain.link`, `pythdata.app`, `polygonscan.com`, and others). All were refused by the proxy.
  - About 50 proxy refusals in total depended on owner clicks.
  - Lessons: check the host class and the site terms before fetching, and implement F-09 deterministic denies for API, data, and live-display hosts (Red-Team RT-B3-11).
