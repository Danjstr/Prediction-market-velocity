# PMV master data-source inventory (B09, 2026-10-18)

**Status:** research and recommendation. **Not an approved requirement, not an acquisition approval, and not a licence determination.** No data was downloaded, no market API was called, no account or credential was created.

Every status below is a research classification. No source may be acquired, captured, or ingested until the A-1 to A-8 acquisition gate passes for that source (`docs/external_access.md` §2). Nothing acquired becomes agent-visible before H-2 release (`docs/release_tool_design.md`).

**Detailed records** (every field the owner required):
- `research/data_sources/inventory_pm_gold_detail.md`: PM-00 to PM-31, G-1 to G-26;
- `research/data_sources/inventory_btc_detail.md`: B-1 to B-35.

**Related records:**
- decisions: `docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md`;
- reviews and dispositions: `research/governance/b09_cloud_architecture_reviews.md`;
- batch 3 predecessors: `research/historical_data/`. This inventory updates them, and supersedes them where they conflict.

**Evidence tags.**

| Tag | Meaning |
|---|---|
| G | Git snapshot, VERIFIED-BY-DOC when captured (Kalshi 2026-10-15; Polymarket 2026-10-16). Needs re-verification before A-1 |
| FS | FETCHED-SUMMARY: an official page fetched on 2026-10-18 and summarized by the fetch tool. Still SECONDARY under O-8, because no verbatim quote and hash were recorded |
| S | SECONDARY: web-search summary or third-party source |
| I | Inference |
| UNKNOWN | Not established |

Every licence statement in this inventory is S or G. A-2 needs verbatim terms with a raw-byte hash.

**CLOUD DIRECT values** (CLOUD_DIRECT_INGESTION) are documented capabilities. They were **not tested from GCP**. Datacenter-IP blocking or geo policy may apply, and a chartered connectivity check precedes A-1 (architecture §7). No region is ever chosen to get around a venue restriction.

## 1. Headline findings

1. **Licensing, not technology, is the dominant blocker.** The evidence has moved from "terms unknown" to "terms possibly restrictive" for several sources. All of it is SECONDARY and needs owner-supplied texts:
   - **Kalshi:** see §2. Which agreement governs which surface is not established.
   - **Coinbase Market Data Terms:** personal or research use. ML training reportedly needs written consent.
   - **Kraken:** prior permission is required for non-personal commercial use of public-endpoint data.
   - **CME DS-45 (June 2026):** an ML/AI prohibition on "Information" of unclear scope, which conflicts with CME marketing its BigQuery data for ML.
   - **Polymarket:** "Capital Markets Entities" must license data, including on-chain data, through Polymarket/ICE. Whether a private own-account trader is one is UNKNOWN.
   - **Pyth:** history is now paid. No data licence was seen.
   - **Tardis.dev** reportedly permits internal trading models and grants a perpetual licence for downloaded data, except Coinbase data (S).
2. **Kalshi licence status is NEEDS_LICENCE_CLARIFICATION on every surface PMV would use** (§2).
   - It is not PROHIBITED_FOR_INTENDED_USE. No authoritative governing text has been read for any surface.
   - The website-oriented Data Terms of Use are **not** assumed to govern API data unless the agreement chain establishes it.
   - Because Kalshi is the only source of Kalshi market prices, a lawful right to use Kalshi API data for development, backtesting, and live decisions is critical for a Kalshi-venue strategy.
3. **No market-data source is AVAILABLE_NOW.** Only public-record documents, macro release calendars, and calendar code are. No source has SAMPLE_AVAILABLE_NOW as its main status.
4. **Historical order books exist only from third parties.**
   - Kalshi L2 history is effectively absent.
   - Polymarket L2 history starts about 2025-08 at best.
   - BTC spot L2 history is paid (Tardis, CoinAPI, Kaiko).
   - Prospective capture is the only source of replayable L2 with PMV receipt times, and the only source of protected evaluation data.
5. **Settlement references have no free historical route.**
   - BRTI (Kalshi BTC): CME DataMine, CF Benchmarks, or the Kalshi passthrough.
   - Pyth gold (Kalshi gold): Metals plan about $2,500/month (S), and the exact feed is unresolved (DET-1).
   - Chainlink Data Streams (Polymarket BTC): about $150/month (S).
6. **Gold history is thin by construction.**
   - About 2.5 months of KXGOLD15M.
   - A Pyth gold index live only since about 2026-06.
   - A weekend and daily-break hole between the 24/7 reference and COMEX hours.
7. **Cloud-to-cloud ingestion is documented for nearly every source.** It is untested from GCP. No source needs the Chromebook as a relay.

## 2. Kalshi: surfaces, governing agreements, and what is unverified

| Surface | Believed governing documents | Basis | Unverified | Status |
|---|---|---|---|---|
| **Website** (kalshi.com pages, market pages) | Kalshi Terms of Service; the Kalshi Data Terms of Use (S) | ToS URL from the AsyncAPI `license.url` (G); Data Terms text from search summaries of a PDF (S) | Whether the Data Terms address the website only, or also data products or APIs; their exact wording | Not a PMV source. The host is `live-display` and bot-challenged. **NOT_USEFUL** (PM-00) |
| **Official API data** (historical tier, metadata, REST, WebSocket) | **Kalshi Developer Agreement.** The documentation states that API use binds the user to it (G, DOC-1015 welcome page). Possibly also the ToS and any documents it incorporates; the precedence order is UNKNOWN | G for the Developer Agreement reference. S (third-party review) for its reported §3 (use limited to facilitating a member's own trading) and §3.1 (no sharing with third parties without authorization) | The full text; whether it, the ToS, or the Data Terms govern stored-data uses (storage in a third-party cloud, backtesting, ML training, derived features, retention, live automated decisions); whether "non-commercial" applies to own-account trading; whether the Data Terms are incorporated into the Developer Agreement | **NEEDS_LICENCE_CLARIFICATION** (PM-01 to PM-04, B-15) |
| **PMV's own capture** from the authorized API or WebSocket | The Developer Agreement, plus the member or customer agreement of the authenticated account (G: a key is required for every WebSocket) | As above | As above, plus whether a separate data-only account is permitted, and the key scope | **NEEDS_LICENCE_CLARIFICATION** (PM-31) |
| **Third-party archives of Kalshi data** (HF, GitHub, vendors) | The redistributor's licence (CC-BY, MIT, or none). Under A-2, the redistributor's right to grant it depends on the upstream Kalshi terms; unknown counts as no | G | The upstream permission for each redistributor | **NEEDS_LICENCE_CLARIFICATION** (PM-18, PM-28, PM-29, PM-30a) |
| **Upstream settlement and reference data** carried by Kalshi (CF Benchmarks BRTI channel and passthrough; Pyth channel) | Kalshi's terms **and** the upstream licensor's terms (CF Benchmarks; Pyth) | G (channels documented), S (licensor terms) | Both licences; storage and ML rights; restatement policy (BRTI) | **NEEDS_LICENCE_CLARIFICATION** (B-13, B-14, G-8) |

**Next action (owner):**
- Supply the Developer Agreement, the ToS, the Data Terms of Use, and any incorporated documents (AR-3, extended).
- Then send a clarification request, extended from the B09 draft. It should ask, for each surface, about:
  - storage in a third-party cloud;
  - backtesting and statistical or ML model development, including whether a logistic model counts as an "ML system";
  - derived features, and retention after the account or access ends;
  - processing by development tools;
  - **use of API data for live automated trading decisions in the production runtime**;
  - monitoring and reconciliation retention;
  - whether own-account trading is "commercial".

## 3. Status rules and precedence

| Status | Rule |
|---|---|
| AVAILABLE_NOW | No credential, no payment, and no material known restriction on private research and model use |
| SAMPLE_AVAILABLE_NOW | Only a lawful free sample can be obtained now |
| NEEDS_OWNER_CREDENTIAL | The main blocker is an owner account, key, or owner-supplied document, and the licence is not otherwise at issue |
| NEEDS_PAYMENT | A commercial product whose licence is read as part of the purchase decision, with no specific known restriction |
| NEEDS_LICENCE_CLARIFICATION | A specific licence concern is known (restrictive, conflicting, or upstream-dependent terms), **or** a free or credential-only source's terms are unread |
| PROHIBITED_FOR_INTENDED_USE | **Authoritative** governing evidence (verified text) clearly prohibits the intended use |
| TECHNICALLY_UNAVAILABLE | Discontinued, not offered, or not reconstructable |
| NOT_USEFUL | Accessible but does not materially help PMV |

**Precedence (main blocker):** PROHIBITED (authoritative only) > NEEDS_LICENCE_CLARIFICATION > NEEDS_PAYMENT > NEEDS_OWNER_CREDENTIAL. Secondary conditions are in the detail records.

**Determinations, not sources:**
- **DET-1:** the KXGOLD15M reference feed (346 or 3153) and candle rule;
- **DET-2:** the governing KXBTC15M rulebook (CRYPTO or CRYPTOSHORT).

Both need owner-supplied contract terms (AR-3/AR-4).

## 4. Master source matrix

**Column notes:**
- **CLOUD DIRECT:** documented, untested from GCP.
- **OPERATIONAL STATUS:** the main status.
- **PMV VALUE:** H, M, or L.

Rows are sorted by status group in the owner's order, then by PMV value.

### 4.1 AVAILABLE_NOW

| ID | SOURCE | ASSET | DATA TYPE | GRANULARITY | HISTORY | AUTH | COST | LICENCE STATUS | CLOUD DIRECT | OPERATIONAL STATUS | PMV VALUE | SUBSTITUTE | NEXT ACTION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PM-06a | CFTC filings of Kalshi rulebooks (BTC 2024-11-12, CRYPTO 2025-07-18, CRYPTOSHORT 2026-03-11; GOLDPERP unread) | BTC, gold | Settlement rule text | Per filing | 2024 onward | None | Free | US public record | YES | AVAILABLE_NOW | H | Kalshi contract-terms PDFs (PM-06b) | Already in Git; read GOLDPERP when relevant |
| X-1 | Scheduled macro release calendars (BLS, BEA, FOMC) | BTC, gold | Release **times only** (no values) | Per event | Long | None | Free | US public record | YES | AVAILABLE_NOW | M | — | Hosts refused to agents (AR-15); a deterministic tool or owner copy supplies times |
| G-24a | `pandas_market_calendars` / `exchange_calendars` | Gold, CME BTC | Session and holiday calendars (code) | Session | n/a | None | Free | MIT / Apache-2.0 | n/a | AVAILABLE_NOW | M | Databento `status` (G-3); CME documents (G-24b) | Dependency review; validate against open 2026 bugs |

### 4.2 SAMPLE_AVAILABLE_NOW

None as a main status. Lawful samples exist only as secondary conditions:
- Tardis first-of-month files, where using them accepts the licence (B-8);
- a Marketlens one-day file (PM-23).

Agents do not download them (acquisition gate, exposure).

### 4.3 NEEDS_OWNER_CREDENTIAL (owner-supplied documents)

| ID | SOURCE | ASSET | DATA TYPE | GRANULARITY | HISTORY | AUTH | COST | LICENCE STATUS | CLOUD DIRECT | OPERATIONAL STATUS | PMV VALUE | SUBSTITUTE | NEXT ACTION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PM-06b | Kalshi contract-terms PDFs and rulebook (current and original) | BTC, gold | Settlement rules; resolves DET-1 and DET-2 | Per series | — | Owner copy (agents may not fetch the bucket host) | Free | Copyright; commit metadata only | n/a | NEEDS_OWNER_CREDENTIAL | **H** | CFTC filings (PM-06a) | Owner supplies (AR-3/AR-4) |
| G-24b | CME Rulebook ch. 113, GC/MGC/1OZ specs, holiday calendar, 1OZ 24/7 notice | Gold | Authoritative rules and hours | — | — | Owner copy (cmegroup.com blocks automated clients) | Free | — | n/a | NEEDS_OWNER_CREDENTIAL | M | G-24a with validation | Owner supplies (AR-10) |

### 4.4 NEEDS_PAYMENT

| ID | SOURCE | ASSET | DATA TYPE | GRANULARITY | HISTORY | AUTH | COST | LICENCE STATUS | CLOUD DIRECT | OPERATIONAL STATUS | PMV VALUE | SUBSTITUTE | NEXT ACTION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B-8 | Tardis.dev (Kraken, Bitstamp, Gemini, Crypto.com, Bullish; Coinbase only in All Exchanges) | BTC | Trades, quotes, incremental L2, snapshots, some L3; exchange and receipt timestamps | Per message, µs | 2019 onward (Bullish 2026-04) | API key | Single class from about $350–700/month, quarterly minimum; All Exchanges from about $650–1,200/month (S) | Reportedly perpetual licence for downloads and internal trading models allowed (S); Coinbase portion carries Coinbase terms | YES_WITH_PAYMENT | NEEDS_PAYMENT | H | CoinAPI (B-30), Kaiko (B-29) | Defer until PMV's own Kalshi books exist for the same period, or a preregistered experiment shows book features help in the tail (BIZ-B9C-06). Then the owner reads the licence (AR-11) and buys the smallest slice |
| G-6 | Pyth Pro History API (`Metal.XAU/USD` 346; `Metal.Index.GOLD/USD` 3153; 1OZGOLD 3712) | Gold | Settlement-reference candles and 200 ms prices | 200 ms / 1 min | GOLD index from about 2026-06 (S) | API key | Metals about $2,500/month (S) | No data licence seen; methodology not obtained | YES_WITH_PAYMENT | NEEDS_PAYMENT | H (conditional) | G-8 (forward only) | Only after DET-1, AR-8 terms and methodology, and the proposed gold spend gate (K4) |
| G-7a | Pyth Benchmarks / Hermes timestamp endpoints | Gold | Signed price updates | ≤60 s | As G-6 | Paid key | Paid plan | As G-6 | YES_WITH_PAYMENT | NEEDS_PAYMENT | M | G-6 | With G-6 |
| B-16 | Chainlink Data Streams BTC/USD (60 s TWAP for Polymarket) | BTC | Polymarket settlement-reference reports | Per report | Retention undocumented; TWAP from about 2026-07-31 | HMAC key | About $150/month per stream (S) | ToS unread | YES_WITH_PAYMENT | NEEDS_PAYMENT | M (H if Polymarket in scope) | B-21 (forward only) | Only if Polymarket BTC is in scope; read ToS (AR-7) |
| PM-23 | Marketlens Polymarket L2 archive | PM | L2 snapshots and price changes | 60 s / ms | From 2026-03 | API key | $39–199/month (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | M | PM-22, PM-24 | Only if Polymarket in scope; AR-13 |
| B-30 | CoinAPI Flat Files | BTC | Trades, quotes, book updates, snapshots | Tick | Per exchange (LMAX 2020) | API key | $2–24/GiB; $25 credit (S) | Internal ML reportedly allowed (S) | YES_WITH_PAYMENT | NEEDS_PAYMENT | M | B-8 | À-la-carte fallback |
| G-12 | Chainlink Data Streams XAU (24/7 blended metals) | Gold | Reference reconciliation | Per report | UNKNOWN | Key | Commercial | UNKNOWN | UNKNOWN | NEEDS_PAYMENT | L–M | G-6 | Later, for the 24/7 hole |
| PM-24 | Other Polymarket L2 vendors | PM | L2 | 250 ms–1 min | Various | Accounts | $49–360/month (S) | UNKNOWN (PMData: commercial only at Enterprise) | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | PM-23 | Shortlist after AR-13 |
| PM-30b | Oddpool Kalshi order-book snapshots | PM | L2 snapshots | 1–5 min | UNKNOWN | Account | $30–100/month (S) | Upstream Kalshi terms | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | PM-31 capture | None now |
| PM-16 | Goldsky Turbo Pipelines (Polymarket v2 datasets) | PM | On-chain fills | Per event | From 2026-04-28 (v2) | Account | Paid (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | PM-14 | None |
| PM-19 | Bitquery Polymarket datastore and BigQuery datashares | PM | On-chain fills, payouts | Per event | From 2025-09-01 (S) | Account | From $400 (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | PM-14 | None |
| B-25 | LMAX Digital (via CoinAPI) | BTC | Trades, quotes, book | Tick | 2020 / 2021 | Key | +$500/month (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | — | BRTI fidelity only |
| B-17 | Chainlink Candlestick API | BTC | OHLC | 1 min (≤24 h windows) | Short | JWT | With B-16 | As B-16 | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | B-16 | None |
| B-29 | Kaiko (including Amberdata) | BTC | Tick trades; book snapshots; full tick book from 2022-12 | Tick | Trades to 2010 (S) | Enterprise | Quote | Licence on purchase | YES_WITH_PAYMENT (GCS/BigQuery delivery) | NEEDS_PAYMENT | L | B-8 | Defer |
| B-31 | CoinDesk Data (CCData) | BTC | L1/L2; 1-min snapshots; trades | Tick–1 min | From 2020-09 (S) | Enterprise | Quote | Licence on purchase | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | B-8 | Defer |
| B-32 | Coin Metrics Pro | BTC | Trades, candles, quotes, books (5 exchanges), reference rates | Tick | UNKNOWN | Enterprise | Quote | Licence on purchase | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | B-8 | Defer |
| G-16 | Massive (formerly Polygon.io) `C:XAUUSD` | Gold | Aggregated FX quotes, bars | Tick / 1 min | 10+ years with gaps 2010-07 to 2013-07 and 2021-01 to 2025-08 (S) | Account | From $49/month (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | G-15 | Skip |
| G-17 | Twelve Data XAU/USD | Gold | Bars | 1 min | From 2020-01-09 (S) | Account | From $79/month (S) | Business plan for company use | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | G-2 | Skip |
| G-21a | LSEG Tick History | Gold | GC, XAU=, XAUFIX= L1–L3 | µs | From 1996 (S) | Enterprise | Quote | Enterprise licence | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | G-1 | Skip |
| G-21b | Bloomberg Tick History | Gold | GC ticks | Tick | From 2008 (S) | Enterprise | Quote | Enterprise licence | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | G-1 | Skip |
| G-21c | Barchart OnDemand | Gold | Tick, minute, EOD | Tick | UNKNOWN | Account | From about $500/month (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | G-2 | Skip |
| G-21d | Tick Data LLC; AlgoSeek; PortaraCQG | Gold | GC trades, quotes, some depth | ms | Long (S) | Accounts | $1,000 minimum to $1,500+/month (S) | UNKNOWN | YES_WITH_PAYMENT | NEEDS_PAYMENT | L | G-2 | Skip |

### 4.5 NEEDS_LICENCE_CLARIFICATION

| ID | SOURCE | ASSET | DATA TYPE | GRANULARITY | HISTORY | AUTH | COST | LICENCE STATUS | CLOUD DIRECT | OPERATIONAL STATUS | PMV VALUE | SUBSTITUTE | NEXT ACTION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PM-31 | **PMV prospective capture** (Kalshi WS + reference channels; constituent WS; Polymarket/PM-US if in scope) | BTC, gold | L2 deltas, trades, lifecycle, reference values, receipt times | Per message | From capture start | Kalshi key; others as inputs | Cloud cost; optional paid channels | Kalshi: Developer Agreement + member agreement (§2); exchange WS: each venue's terms | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | **H (only protected-evaluation source)** | None | Kalshi clarification; cloud F-03 successor; venue connector; capture charter |
| PM-01 | Kalshi official historical tier | BTC, gold | Trades, 1-min candles, settlements, market objects | Trade / 1 min | About 2021-06 onward; cutoff lag 2–3 months (S) | None | Free | Developer Agreement (G reference; text unread); Data Terms applicability UNVERIFIED | YES | NEEDS_LICENCE_CLARIFICATION | **H (official labels and prices)** | PM-28/29 (same upstream) | §2 next action |
| PM-02 | Kalshi metadata (series, events, markets, fee history) | BTC, gold | Contract metadata, fees, settlement sources | Per record | All series and events (G) | None | Free | As PM-01 | YES | NEEDS_LICENCE_CLARIFICATION | H | PM-06 | With PM-01 |
| B-15 | Kalshi per-market settlement values | BTC, gold | Official label | Per market | As PM-01 | None | Free | As PM-01 | YES | NEEDS_LICENCE_CLARIFICATION | H | BRTI recomputation (audit only) | With PM-01 |
| PM-04 | Kalshi WebSocket | BTC, gold | L2, trades, lifecycle | Per message | Live only | Key always (G) | Free | As PM-31 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | H | PM-03 | Part of PM-31 |
| B-2 | Kraken downloadable trade archive | BTC | Full trade tape, OHLCVT | Trade | First trade to 2026-09-30 (S) | None | Free | Prior permission for non-personal commercial use (S) | YES (host to confirm, DA-B9C-22) | NEEDS_LICENCE_CLARIFICATION | **H (best free BTC tape)** | B-8, B-30 | Owner emails `marketdata@kraken.com`; supplies support articles (AR-12) |
| B-1 | Kraken spot REST (Trades, OHLC, Depth) | BTC | Trades; 720 recent candles; current book only | Trade (ns) | From first trade (S) | None | Free | As B-2 | YES | NEEDS_LICENCE_CLARIFICATION | H | B-2 | Same Kraken permission request |
| B-3 | Kraken spot WebSocket v2 (book, trade, level3) | BTC | Live L2 (checksummed), trades, L3 | Per message | Live only | None (L3: key) | Free | As B-2 | YES | NEEDS_LICENCE_CLARIFICATION | H (capture) | B-7, B-22 | Same Kraken permission request; capture charter |
| B-4 | Kraken Futures REST (trades, history events, candles, funding) | BTC perps (not BRTI inputs) | Trades, candles, funding | Trade | Last 100 trades / 7 days; event lookback UNKNOWN (S) | None | Free | As B-2 | YES | NEEDS_LICENCE_CLARIFICATION | L–M | Tardis Kraken Futures (from 2019-03-30) | Later; lead-lag feature only |
| G-2 | Databento GLBX.MDP3 GC/MGC/1OZ L1 and bars | Gold | Trades, TBBO, MBP-1, BBO-1s, OHLCV-1s/1m | Event / 1 s | 2010 onward (reliable from 2017-05-21) | API key | Likely inside the $125 credit; $0.50/GB (S) | Databento says historical data needs no licence (FS); CME non-display historical licensed at no fee (S); **DS-45 ML scope and DDLA open** | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | **H (best-value gold)** | G-5 | Owner reads Databento terms; written DS-45 scope answer; then the pipeline-proving first acquisition |
| G-3 | Databento GLBX.MDP3 definitions, statistics (settlements), status | Gold | Roll calendar, official settlements, open interest, session state | Event | 2010 onward; `status` from 2017-05-21 (S) | API key | Small (I) | As G-2 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | H | G-5 STL; G-24 calendars | With G-2 |
| G-1 | Databento GLBX.MDP3 GC/MGC MBO, MBP-10 | Gold | Order-level and 10-level depth | Event, ns | MBO from 2017-05-21 | API key | $0.50/GB | As G-2 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | H | G-5 | Only after L1 features show signal |
| G-26 | **Live CME GC/MGC/1OZ capture** (Databento Live or a CME feed) | Gold | Live trades, L1/L2 with receipt times | Per message | Live only | Key | Live CME licence fees (Databento Standard includes live CME, S); non-display/automated-use fees UNKNOWN | CME live licence; DS-45 | YES_WITH_PAYMENT | NEEDS_LICENCE_CLARIFICATION | H (gold receipt-time parity, S-B9C-04) | None | Price and licence enquiry with G-2 |
| B-10 | CME DataMine CRYPTOCURRENCY (BRTI/BRR) and BTC futures | BTC | BRTI index values; futures T/L2/L3/settlements | About 1 s | BRTI from 2016-11/12 (S) | CME login | Quote-only | MDLA; DS-45 ML scope; DDLA | YES_WITH_PAYMENT | NEEDS_LICENCE_CLARIFICATION | H | B-12, B-13 | Quote plus written ML/storage scope |
| G-5 | CME DataMine gold (T&S, BBO, depth, MBO, settlements) | Gold | Exchange history | Tick, ns | 1982 / 1999 / 2005 | CME login, ILA | Quote-only | ILA/DDLA; DS-45 | YES_WITH_PAYMENT | NEEDS_LICENCE_CLARIFICATION | M | G-1/2/3 | Only if Databento licensing fails |
| B-11 | CME Historical Market Depth on Google Cloud (BigQuery Analytics Hub) | BTC, gold futures | Depth, settlements | ns | 2014 onward | CME order | Quote-only | As B-10 | YES_WITH_PAYMENT (most cloud-native) | NEEDS_LICENCE_CLARIFICATION | M | B-9 | With the B-10 enquiry |
| B-12 | CF Benchmarks direct (BRTI history) | BTC | BRTI index values | 200 ms / 1 s | UNKNOWN | Entitlement | Quote-only | Licence; "later pulls may reflect revisions" (S); no use to settle instruments without consent (G) | YES_WITH_PAYMENT | NEEDS_LICENCE_CLARIFICATION | H | B-10, B-13 | Owner obtains methodology and licence (AR-9) and a quote |
| B-13 | Kalshi CF Benchmarks REST passthrough (BRTI history) | BTC | BRTI values | Tick | Depth UNKNOWN | Kalshi key + entitlement | UNKNOWN | Kalshi + CF Benchmarks terms (§2) | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | H | B-10, B-12 | Ask price and storage/ML rights in the Kalshi request |
| B-14 | Kalshi `cfbenchmarks_value` WebSocket (forward) | BTC | BRTI values; 60 s window averages | Per update | Live only | Kalshi key + entitlement | UNKNOWN | As B-13 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | H (capture) | B-13 | Part of PM-31 once licensed |
| G-8 | Kalshi `pyth_value` WS | Gold | Reference values as Kalshi sees them | Per update | Live only | Kalshi key + entitlement | $1,000/month; 7-day trial (G) | Kalshi + Pyth terms | YES_WITH_PAYMENT | NEEDS_LICENCE_CLARIFICATION | H (capture) | G-6 | After DET-1 and the proposed K4 gate |
| B-9 | Databento CME BTC/MBT futures | BTC | Futures depth, trades, settlements | Event, ns | About 2017 onward (I) | API key | Credit / $0.50/GB | As G-2 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | M | B-10, B-11 | Optional, after the DS-45 answer |
| B-5 | Coinbase Exchange public REST (trades, candles) | BTC | Trades; 1-min+ candles | Trade (µs) | Trades by cursor, depth "not specified" (FS) | None | Free | Market Data Terms: personal or research use; ML training reportedly needs written consent (S) | YES | NEEDS_LICENCE_CLARIFICATION | H technically; high legal risk | B-1/B-2, B-22, B-23 | Hold. Request consent only if the BRTI-proxy test shows Coinbase matters |
| B-7 | Coinbase Exchange WebSocket / FIX market data | BTC | Live L2 (`level2_batch`), full L2/L3 (key), sequence numbers | Per message | Live only | None / key | Free | As B-5 | YES | NEEDS_LICENCE_CLARIFICATION | H technically | B-3 | As B-5 |
| B-6 | Coinbase Advanced Trade public REST | BTC | Candles; ticker; current book | 1 min | ≤350 candles per request (S) | None | Free | As B-5 | YES | NEEDS_LICENCE_CLARIFICATION | L | B-5 | None |
| PM-14 | BigQuery Polygon datasets (Polymarket fills and resolutions decoded from logs) | PM (BTC) | On-chain fills, payouts | Per event | Start UNKNOWN; Polymarket decoding UNKNOWN | GCP project (vault identity only) | Query bytes | Pre-GA terms; Polymarket/ICE statement (S) | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | M (H if Polymarket in scope); "potentially best" route | PM-13, PM-21 | Docs access request; Polymarket licensing enquiry |
| PM-20 | Polymarket US gateway REST / WS | PM (BTC) | Book, BBO, settlement, price history | Per call / message | Short | None (REST); KYC key (WS) | Free | Rulebook bars redistribution (S) | YES | NEEDS_LICENCE_CLARIFICATION | M (H if owner is a US person) | — | F-16; AR-6 |
| PM-11 | Polymarket CLOB book REST and market WebSocket (prospective) | PM (BTC) | L2, BBO, last trade, tick-size changes | Per message (ms, S) | Live only; no book history (G) | None for the market channel (S) | Free | Polymarket/ICE statement (S); ToS text unretrieved | YES | NEEDS_LICENCE_CLARIFICATION | M | PM-22/23/24 (history) | With F-16 and Polymarket scope |
| PM-08 | Polymarket Gamma API (markets, events, series) | PM (BTC; gold daily only) | Contract metadata, token map, fees, tick, resolution source | Per record | All markets, current state (POST_HOC) | None | Free | As PM-11 | YES | NEEDS_LICENCE_CLARIFICATION | M | PM-21 markets table | With F-16 and Polymarket scope |
| PM-09 | Polymarket Data API v2 (`/v2/trades`, `/v2/resolutions`) | PM (BTC) | Indexed on-chain fills; resolutions | Per fill (block seconds) | Three-year window per condition; v1 reportedly retiring 2026-10-24 (S) | None | Free | As PM-11 | YES | NEEDS_LICENCE_CLARIFICATION | L | PM-13, PM-14 | Cross-check only |
| PM-12 / B-21 | Polymarket PolyBolt Chainlink reference feed | BTC | Polymarket settlement reference (forward) | Per update | 2-min snapshot | CLOB credentials | Free | UNKNOWN | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | M | B-16 | With F-16 |
| PM-13 | Polygon RPC (self-decoded fills) | PM | On-chain fills, payouts | Per event | 2022-11 onward | RPC key | Provider tier | As PM-14; RPC ToS | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | M | PM-14 | Reconciliation for PM-14 |
| PM-21 | HF `SII-WANGZJ/Polymarket_data` and similar | PM (BTC) | Packaged on-chain fills | Per fill | 2022-11 to 2026-10 | None | Free | Packager MIT/CC-BY vs upstream | YES | NEEDS_LICENCE_CLARIFICATION | M | PM-14 | Only if Polymarket in scope |
| PM-22 | pmxt archive (Polymarket WS stream) | PM | L2 events | 1–10 s | 2026-02 to about 2026-08 (S) | None | Free | CC BY 4.0 claimed (S) | YES | NEEDS_LICENCE_CLARIFICATION | M | PM-23 | Discovery-only (partial universe, S-B9C-13) |
| PM-26 | OpenMarket corpus (Young 2026) | PM, BTC | Polymarket BTC 15m + Binance | ms | 2026-02 to 2026-05 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | NEEDS_LICENCE_CLARIFICATION | M (replication target) | — | Locate; reading its results counts as outcome inspection (S-B9C-14) |
| B-22 | Bitstamp REST and WebSocket v2 | BTC (BRTI constituent) | Trades; OHLC; live diff book with `microtimestamp` | Trade / message | Transactions last day only; OHLC ≤1000 bars per request | None | Free | Signed Data License Agreement for commercial use (S) | YES | NEEDS_LICENCE_CLARIFICATION | M | B-8 (history from 2019) | Permission request before capture |
| B-23 | Gemini REST and WebSocket v3 | BTC (BRTI constituent) | Trades; candles; live book | Trade / message | Trades 7 or 90 days (CONFLICT, S) | None | Free | Market Data Agreement unread | YES | NEEDS_LICENCE_CLARIFICATION | M–L | B-8 | Later |
| B-24 | Bullish REST and WebSocket | BTC (BRTI constituent) | Trades; book; candles | Trade / message | Native history UNKNOWN; Tardis from 2026-04-29 | None | Free | Terms unread | YES | NEEDS_LICENCE_CLARIFICATION | L–M | B-8 | Later |
| B-27 | Crypto.com Exchange REST | BTC (BRTI constituent) | Trades; candles | Trade | Time-range queries; depth UNKNOWN | None | Free | No terms found | YES | NEEDS_LICENCE_CLARIFICATION | L–M | B-8 | Later |
| B-34 | Offshore BTC perpetuals and price-discovery venues (Binance, Bybit, OKX, Deribit live APIs); history via Tardis derivatives | BTC | Trades, L2, funding | Per message | Via vendors | Varies | Free / vendor | Venue terms; US-person eligibility; geo restrictions are **never** worked around | UNKNOWN | NEEDS_LICENCE_CLARIFICATION | M (lead-lag) | B-4, B-9 | Owner eligibility check before any consideration |
| B-35 | Deribit DVOL / options implied volatility | BTC | Volatility index | 1 s–1 min | UNKNOWN | Varies | Free / vendor | Terms unread | UNKNOWN | NEEDS_LICENCE_CLARIFICATION | L–M | Realized-volatility features | Later |
| G-15 | OANDA v20 XAU_USD candles | Gold | Spot bid/mid/ask | 5 s | About 2005 onward | Owner account + token | No published data fee | "Internal Use" incl. research (S); ML retention unread | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | M | G-16 | Owner reads the API licence |
| G-23 | Tokenized gold (PAXG, XAUT) on crypto venues | Gold | 24/7 proxy | Per venue | Per venue | Per venue | Free | Venue terms | UNKNOWN | NEEDS_LICENCE_CLARIFICATION | M (24/7 hole) | G-12 | Later |
| PM-18 | Allium predictions (Polymarket and Kalshi books) | PM | L2 snapshots, trades | Sub-minute to hourly | UNKNOWN | Enterprise | Enterprise | Kalshi book inherits Kalshi upstream terms | YES_WITH_PAYMENT | NEEDS_LICENCE_CLARIFICATION | M | PM-31 | After the Kalshi answer |
| PM-03 | Kalshi live-tier REST polling (orderbook, trades, candles) | BTC, gold | Book (no sequence or timestamp), trades | Poll | Current only | None | Free | As PM-01 | YES | NEEDS_LICENCE_CLARIFICATION | L–M | PM-04 | Fallback to PM-04 only |
| B-18 | Chainlink Data Feeds BTC/USD (push oracle) via RPC | BTC | Oracle rounds (not the Polymarket TWAP) | Per round | Long | RPC key | Free / provider tier | chain.link ToS unread | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | L | B-19 | None |
| B-19 | BigQuery `crypto_ethereum.logs` (Chainlink `AnswerUpdated`) | BTC | Oracle events | Per event | Long | GCP project (vault identity only) | Query bytes | Dataset terms unread | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | L | B-18 | None |
| B-20 | PMData Chainlink stream archive | BTC | Chainlink stream reports (third-party capture) | Per report | From 2026-06-07 (S) vs 2026-08-01 (G): CONFLICT | Account | Paid | UNKNOWN; lineage unverified | UNKNOWN | NEEDS_LICENCE_CLARIFICATION | L–M | B-16 | Only if Polymarket in scope |
| G-4 | Databento GLBX.MDP3 CME gold event contracts | Gold | Event-contract MBO | Event, ns | From 2025-09-25 (G) | API key | $0.50/GB | As G-2 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | L | — | Exploratory, later |
| G-14 | Dukascopy SWFX XAUUSD ticks | Gold | Single-venue CFD quotes | Tick | From about 2003-05 (S) | None | Free | Reportedly personal, non-commercial; "may not be used to construct a database" (S, unverified) | YES | NEEDS_LICENCE_CLARIFICATION | L | G-15 | None |
| G-20 | Gold ETFs GLD/IAU via Databento equities | Gold (proxy) | Trades, BBO, MBO | Event | XNAS.ITCH from 2018-05-01 (S) | API key | From $0.40/GB (S) | As G-2 | YES_WITH_CREDENTIAL | NEEDS_LICENCE_CLARIFICATION | L | G-2 | None |
| PM-17 | Dune `polymarket_polygon` curated tables | PM | Fills; hourly prices | Per fill / hour | About 1 h refresh (S) | Account | Tiered | Dune ToS unread | UNKNOWN | NEEDS_LICENCE_CLARIFICATION | L | PM-14 | None (not independent) |
| PM-25 | HF aliplayer1 / BrockMisner BTC up/down sets | PM (BTC) | BBO, ticks, spot | ms | UNKNOWN | None | Free | MIT asserted; lineage unverified | YES | NEEDS_LICENCE_CLARIFICATION | L | PM-22 | None |
| PM-28 | HF `TrevorJS/kalshi-trades` | PM (BTC) | Copy of Kalshi trades | Trade | 2021-06 to 2026-01 (G) | None | Free | CC-BY asserted vs Kalshi upstream terms | YES | NEEDS_LICENCE_CLARIFICATION | L | PM-01 | Cross-check only, after the Kalshi answer |
| PM-29 | `Jon-Becker/prediction-market-analysis` | PM | Kalshi and Polymarket trades, markets | Trade | UNKNOWN | None | Free | Data licence UNRESOLVED (G) | YES | NEEDS_LICENCE_CLARIFICATION | L | PM-01, PM-14 | None |
| PM-30a | Other Kalshi third-party sets (DegenHedge `windows`, papylove 15m incl. metals, RooseveltHonaker) | PM | Strike and settlement; trades | Per window / trade | DegenHedge 2026-01-10 to 2026-10-04; papylove metals from 2026-08-31 (G) | None | Free | Kalshi upstream terms; some unlicensed; never ingest DegenHedge `signals` | YES | NEEDS_LICENCE_CLARIFICATION | L | PM-01 | None |

### 4.6 PROHIBITED_FOR_INTENDED_USE, TECHNICALLY_UNAVAILABLE, NOT_USEFUL

| ID | SOURCE | ASSET | DATA TYPE | GRANULARITY | HISTORY | AUTH | COST | LICENCE STATUS | CLOUD DIRECT | OPERATIONAL STATUS | PMV VALUE | SUBSTITUTE | NEXT ACTION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B-28 | Binance Vision | BTCUSDT | Trades, klines | µs / 1 s | Long | None | Free | CC BY-NC-SA; prohibits live proprietary trading execution (G, VERIFIED-BY-DOC 2026-10-16) | YES | PROHIBITED_FOR_INTENDED_USE | L | B-8 derivatives | Exclude |
| G-10 | Pyth Terminal free tier | Gold | Live display, no API | 10 s | 30 days | None | Free | Personal, non-commercial (S) | NO | TECHNICALLY_UNAVAILABLE | — | G-6 | Exclude (live display) |
| G-7b | Pyth TradingView shim | Gold | Candles | — | Retired 2026-08-26 (S) | — | — | — | — | TECHNICALLY_UNAVAILABLE | — | G-6 | None |
| G-9 | Pyth on-chain reconstruction | Gold | Historical prices | — | Not reconstructable (S) | RPC | — | — | UNKNOWN | TECHNICALLY_UNAVAILABLE | — | G-6 | None |
| B-26 | itBit / Paxos | BTC | Former BRTI constituent | — | Removed 2026-08-27 (S) | — | — | — | — | TECHNICALLY_UNAVAILABLE | — | — | Point-in-time BRTI reconstruction only |
| PM-00 | Kalshi website pages | PM | Live display | — | — | — | — | ToS / Data Terms (§2) | NO | NOT_USEFUL | — | PM-01 | Never used |
| PM-10 | Polymarket prices-history | PM | Displayed price | ≥3 h beyond 90 days | Short at fine grain | None | Free | — | YES | NOT_USEFUL | — | PM-14 | None |
| PM-05 | Kalshi Research via DoubleZero | PM | Institutional L1/L2 (no binaries) | — | Live | Subscription | UNKNOWN | UNKNOWN | UNKNOWN | NOT_USEFUL | — | — | Watch (possible sanctioned data channel) |
| PM-07 | Kalshi daily reporting files | PM | Daily aggregates | Daily | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | NOT_USEFUL | — | PM-01 | None |
| PM-15 | Legacy BigQuery `public-data-finance.crypto_polygon`; Nansen sets | PM | Chain data | Per event | Frozen since 2024-09-01 (FS) | GCP project | Query bytes | Dataset terms UNKNOWN | YES_WITH_CREDENTIAL | NOT_USEFUL | — | PM-14 | None |
| PM-27 | HF `lerchen3/kalshi-orderbook-alpha` | PM | Kalshi L2 top 3 levels | ns | About 12 h on 2026-07-19 (G) | None | Free | "other" | YES | NOT_USEFUL | — | PM-31 | Schema reference only |
| G-11 | Chainlink XAU/USD push feed (on-chain) | Gold | Oracle rounds | 0.3% deviation, about 24 h heartbeat (S) | Long | RPC key | Free / provider | UNKNOWN | YES_WITH_CREDENTIAL | NOT_USEFUL | — | G-12 | None |
| G-13 | LBMA Gold Price (IBA/ICE) | Gold | Twice-daily auction price | 2 per day | Long | IBA licence | Licence fee | Licence required (G) | YES_WITH_PAYMENT | NOT_USEFUL | — | — | None (no target settles on it) |
| G-18 | TrueFX | Gold | FX top of book (no XAU) | Tick | — | — | — | — | — | NOT_USEFUL | — | — | None |
| G-19 | FXCM tick repository | Gold | FX ticks (no XAUUSD in the free set) | Tick | From 2015 (S) | — | — | — | — | NOT_USEFUL | — | — | None |
| G-21e | Kibot; FirstRate Data | Gold | Bars or second-level data in ET | 1 s–bars | From 2008–2009 (S) | Account | Low | UNKNOWN | — | NOT_USEFUL | — | G-2 | None |
| G-22 | Open HF/Kaggle XAU sets | Gold | Unnamed-broker CFD ticks; mirrors | Tick | Various | None | Free | Doubtful licence claims | — | NOT_USEFUL | — | G-2 | None |
| B-33 | Databento DBIX.CORE | BTC | Cboe indices (no BRTI) | — | — | — | — | — | — | NOT_USEFUL | — | — | None |

### 4.7 Required-source checklist

| Owner-required source | Rows |
|---|---|
| Kalshi | PM-00 to PM-07, PM-31, B-13 to B-15, G-8 |
| Polymarket | PM-08 to PM-26 |
| Kraken | B-1 to B-4 |
| Coinbase | B-5 to B-7 |
| Tardis | B-8 |
| Databento CME BTC | B-9 |
| Databento CME/COMEX gold | G-1 to G-4, G-26 |
| CME DataMine BTC | B-10, B-11 |
| CME DataMine gold | G-5, B-11 |
| CF Benchmarks / BRTI | B-12 (direct), B-10 (via CME), B-13/B-14 (via Kalshi) |
| Pyth metals | G-6 to G-10 |
| Blockchain / on-chain | PM-13 to PM-17, PM-19, B-16 to B-19, G-9, G-11, G-12 |
| Additional sources found | X-1, B-34, B-35, G-26, PM-18, B-30, G-15, G-23 |

## 5. Coverage map

| Need | Kalshi BTC 15m/1h | Kalshi gold 15m | Polymarket BTC | Main holes |
|---|---|---|---|---|
| Contract metadata and times | PM-02 (POST_HOC); PM-04 lifecycle (point-in-time, prospective) | Same | PM-08, PM-13/14 | Point-in-time metadata only prospectively |
| Trade history | PM-01 (2021 onward) | PM-01 (about 2.5 months; largely live tier) | PM-13/14/21 | Gold depth; Polymarket US has no public tape |
| Prices / candles | PM-01 1-min candles | Same | Derived from fills | No sub-minute official Kalshi quotes |
| Historical bid/ask | Candle OHLC only | Same | PM-22/23/24 | **No official historical BBO on any venue** |
| Historical order book | Effectively none | None | Third-party only | **Kalshi L2 history absent** |
| Settlement / outcome | PM-01/02, PM-06; DET-2 open | DET-1 open | PM-13/14, PM-09 | Rule documents needed |
| Fee and tick regimes | PM-02 fee history; ticks not recoverable | Same | PM-08 + changelog | Historical ticks |
| Reference series | B-10/12/13 (licence-gated); B-14 forward | G-6 (paid); G-8 forward | B-16 (paid); B-21 forward | **No free or licence-verified historical reference** |
| Underlying ticks | B-2 Kraken; B-8 Tardis | G-2 Databento COMEX | Same as Kalshi BTC | Coinbase consent; gold 24/7 hole |
| Underlying L1/L2 | B-8 (paid); B-3/B-7 capture | G-1/G-2; G-26 capture | Same | **No free historical spot L2** |
| Macro event times | X-1 | X-1 | X-1 | — |
| Receipt / availability time | PM-31 only | PM-31 (+ G-26) | PM-31 | **No historical source carries PMV availability time** (synthetic availability H-5) |
| Protected evaluation | PM-31 only | PM-31 | PM-31 | Capture blocked by licence, credential, connector, charter |

**Universe completeness (S-B9C-13).**
- The Kalshi universe is generated from the deterministic series schedule; missing contracts are ledgered.
- Minutes with no quote are reason-coded, never dropped.
- Third-party archives with partial coverage (pmxt v1 missed about half of markets) are discovery-only.

## 6. Critical missing data

1. A lawful right to use Kalshi API data for development, backtesting, model training, and live decisions (§2).
2. Licensed BRTI history at second-level resolution, with a known restatement policy and point-in-time constituents (S-B9C-07).
3. DET-1 (gold reference feed), DET-2 (BTC rulebook), and the Pyth index methodology.
4. Any historical Kalshi order book.
5. Historical spot L2 without payment.
6. Gold reference history longer than about 4 months, and exchange gold prices during COMEX breaks before late July 2026.
7. PMV availability timestamps for historical data. These come only from capture; history uses synthetic availability (H-5).

## 7. Acquisition order once cloud storage is operational

Each step needs its own A-1 to A-6 approval. **The order is conditional:** whichever source's written permission arrives first goes first (DA-B9C-21). The owner pursues the licence letters in parallel, starting now.

| Step | Source | Why | Specific preconditions |
|---|---|---|---|
| 0 (owner, now) | Licence letters and terms copies: Kalshi (§2), Kraken, Databento/CME DS-45 scope; optional Coinbase, Polymarket | Every market-data source is licence-gated | Owner sends; agents draft |
| Prospective, as early as licences allow | **PMV capture (PM-31):** Kalshi WS + `cfbenchmarks_value`; Kraken WS (B-3) under the Kraken permission; G-26 if gold receipt-time parity is wanted | Receipt-time truth, future protected evaluation, execution realism, power. Every uncaptured day is lost | Licence; cloud F-03 successor; venue connector; capture charter; Stage-appropriate controls (architecture §3.3 B6–B8) |
| 1 | **Kalshi historical + metadata** (PM-01, PM-02, B-15) | Official labels, prices, fee history; the near-free go/no-go test (proposed K2) | Kalshi clarification; D-B09-2/-7/-9; paginated REST tooling; cutoff handling |
| 2 | **Kraken full trade archive** (B-2) | Free, complete constituent tape for velocity baselines and the BRTI-proxy test | Kraken permission; archive host resolved |
| 3 (pipeline-proving fallback) | **Databento GC/MGC/1OZ L1 + metadata** (G-2, G-3), inside the $125 credit | Clearest historical licence statement among vendors (FS), subject to DS-45; proves the cloud pipeline if Kalshi's answer is slow | Databento terms; DS-45 answer; DBN reader (B7-6) |
| 4 | **One licensed BRTI route** (B-13, B-10, or B-12) | Only if the free BRTI-proxy disagreement test shows the gap matters near the strike (BIZ-B9C-07); first-published vintages or a no-restatement policy required (S-B9C-07). BRTI is a feature and recomputation-audit source, never a label source: labels are the official resolution (`docs/phase2.md`) | Quote; written scope |
| 5 | **Tardis smallest slice** (B-8) | Only after the trigger in §4.4 | Licence read |
| 6 | Polymarket sources (PM-14, PM-21, B-16) | Only if Polymarket is in scope after F-16 and licensing; first replicate or rebut OpenMarket (PM-26) | F-16; licensing |

**Historical data drives development** (architecture §11). Historical rows released as development-only are used for exploration, training, pilot models, and hypothesis generation. Whether they may also decide the final audit-candidate comparison is owner decision D-B09-20 (`docs/phase2.md` S-9, a working-design rule; under it, archive results screen and narrow candidates as logged hypotheses). Once released, they can never become holdout.

### 7a. Prospective equivalents for historical feature sources (S-B9C-04)

A feature developed on a historical source is evaluable on the protected set only if PMV captures an equivalent source before `T0 − max_lookback`. Under D-B09-20 option (a), it is **selectable** only if equivalent capture starts early enough before `T0 − m` to give a powered receipt-time development comparison, plus the lookback and purge. Equivalent capture start dates are therefore a power-driven input to choosing `T0` (S-B9C2-08).

| Historical source | Prospective equivalent | Overlap window to schedule |
|---|---|---|
| PM-01 Kalshi history | PM-04 Kalshi WS (PM-31) | Capture overlapping a later historical-tier pull |
| B-2 Kraken archive | B-3 Kraken WS | Capture overlapping the next quarterly archive drop |
| B-8 Tardis (if bought) | B-3, B-7, B-22, B-23 WS capture | Capture overlapping the purchased period |
| G-2 Databento COMEX | G-26 live CME capture | Live capture later re-acquired from the archive |
| B-10/B-12/B-13 BRTI | B-14 `cfbenchmarks_value` | Forward capture overlapping a licensed history pull |
| G-6 Pyth | G-8 `pyth_value` | As above |
| PM-14/PM-21 Polymarket fills | PM-11 / PM-20 capture | If Polymarket is in scope |

## 8. Escalations from this inventory

| # | Current requirement | Concern | Proposal | Urgency |
|---|---|---|---|---|
| INV-1 | A-2 resolved from owner-supplied terms (D-B09-3/-4) | The Kalshi agreement chain per surface is unknown. Secondary evidence suggests restrictive Data Terms of uncertain scope | Supply the Developer Agreement, ToS, Data Terms, and incorporated documents. Send the extended clarification (§2) | **Critical path** for Kalshi; does not block other sources |
| INV-2 | Batch 3 ranked Coinbase as the core BTC venue | Coinbase terms (S) may bar ML training | Prefer Kraken, Bitstamp, and Tardis non-Coinbase data. Request consent only if the BRTI-proxy test shows Coinbase matters | Optional now; blocking before any Coinbase-trained model |
| INV-3 | E-U4 (CME derived data) open | DS-45 (S) adds an ML prohibition of unclear scope | Obtain CME's written scope ruling (directly or via Databento) | High; blocks CME-derived training |
| INV-4 | Gold stays in scope (P4) | Gold history is short, paid, and exposed; gold reference subscriptions cost about $42k/year (S) | **Owner decision before cycle registration** (S-B9C-06, BIZ-B9C-04): gold exploratory in cycle 1, or a separate gold cycle, or a stated per-asset power floor. No paid gold reference until DET-1 and the proposed K4 gate pass | Required before cycle registration; not blocking now |
| INV-5 | Polymarket scope tied to F-16 | Polymarket licensing; PM-US bars redistribution; OpenMarket null result | Rule F-16 and Polymarket scope before any Polymarket spend | Medium |
| INV-6 | Terms-first rule | Most legal pages are on refused or live-display hosts | Owner supplies terms copies for shortlisted sources: Kalshi set, Kraken notice and support articles, Coinbase Market Data Terms, Databento terms, Tardis licence, CME DS-45 and DataMine terms | High |
