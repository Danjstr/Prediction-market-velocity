# PMV data sources: owner action sheet and procurement packet (B09, 2026-10-18)

**Status.** This is the canonical owner-facing procurement document.
- The detailed research source is `research/data_sources/master_source_inventory.md` (100 rows).
- **Nothing has been bought, signed, or downloaded.** Acquisition still needs your per-source approval (A-1 to A-6, `docs/external_access.md` §2) and the cloud pipeline (`research/cloud/pmv_cloud_architecture_review.md` §12).
- You have approved documentation synchronization only. Purchases, vendor terms, data acquisition, live capture, cloud provisioning, and the open B09 decisions are **not** approved.

**Evidence conventions.**

| Tag | Meaning |
|---|---|
| **OWNER-VERIFIED** | You checked the official page and reported the fact on 2026-10-18. Recorded as your statement. A licence determination (A-2) still needs a verbatim quote and a hash |
| **FETCHED** | An agent fetched the official page on 2026-10-18; a tool summarized it (not verbatim) |
| **OWNER_VERIFY** | From search summaries only. The official URL is given; please check it |
| **Git** | From documentation snapshots in the repository |

**Status values.**

| Status | Meaning |
|---|---|
| FREE_TECHNICALLY_AVAILABLE | Free to obtain; PMV's use is not yet cleared |
| FREE_AND_USE_CLEARED | Free, and PMV's use is permitted |
| NEEDS_WRITTEN_PERMISSION | Obtainable; PMV needs consent or clarification for its use |
| NEEDS_LICENCE_QUOTE | Licence needed; no public price |
| PAID_SELF_SERVICE | Public price; sign up without negotiating |
| FREE_SAMPLE_ONLY | Only a sample is free |
| TECHNICALLY_UNAVAILABLE | Data does not exist or cannot be obtained |
| REJECTED | Terms clearly prohibit PMV's use, and there is no licensed path |

## 1. Executive summary

- **Free once permissions clear:**
  - Kalshi historical markets, trades, settlements, metadata, and the live WebSocket;
  - Kraken's full BTC trade archive, OHLCVT archive, and live public REST/WebSocket;
  - Kalshi contract terms and CFTC filings.

  Only the CFTC filings are already use-cleared.
- **Needs written permission or clarification:**
  - **Kalshi.** The Developer Agreement and the website Data Terms are separate documents. API use and storage appear tied to facilitating the member's own trading (OWNER-VERIFIED). ML and backtesting are **not** assumed prohibited; Kalshi must confirm them in writing.
  - **Kraken:** whether PMV's use needs market-data permission.
  - **Databento:** licence classification for ML, non-display, and proprietary use.
  - **Polymarket:** only if needed for scope.
- **Needs a licence quote:** CF Benchmarks BRTI (request a quote now; do not buy yet).
- **Paid, later and only if justified:**
  - Databento: $125 credit; historical from about $0.50/GB; Standard about $199/month.
  - Pyth Pro: budget about $2,500/month.
  - Tardis: cost depends on configuration.
- **Drop for now:**
  - Coinbase: its ordinary terms require prior written consent for ML use.
  - Direct CME DataMine: Databento is the cheaper route to the same exchange data.
- **A $20,000–$35,000 CME purchase is not needed.** CME's historical redistribution and derived-data licence fees are not research-data prices, and PMV does not redistribute.

## 2. Minimum viable dataset

| Side | Sources | Condition |
|---|---|---|
| Prediction / BTC | Kalshi historical markets, trades, and metadata; Kraken historical BTC trade archive; Kalshi contract, rule, and settlement metadata | Once Kalshi (M1) and Kraken (M2) clear |
| Gold | Databento GC/MGC trades and/or L1 | Once the licence classification clears (M3) |
| Prospective (later) | Kalshi WebSocket; Kraken WebSocket; BRTI or another reference series once its entitlement is resolved | Separately authorized capture |

**Projected initial market-data cost: about $0–$160. This is not guaranteed.**
- The Databento estimator must confirm the exact cost for our symbols, schemas, and dates.
- Vendor permissions must clear first.
- Cloud cost is separate (§8).

This dataset is enough for the proposed M-0 go/no-go test (decision record D-B09-18). It lacks order books, exact BRTI, the gold reference series, and receipt-time data.

## 3. Procurement tiers

| Tier | Items |
|---|---|
| **TIER 0: contact / clear now** | Kalshi (M1); Kraken (M2); Databento (M3); CF Benchmarks BRTI quote (M4); Polymarket (M5) only if scope clarification is needed; you download the Kalshi BTC and gold contract terms |
| **TIER 1: acquire once cleared** | Kalshi historical/API data; Kraken historical archive; Databento GC/MGC L1/trades; prospective Kalshi and Kraken capture only when separately authorized |
| **TIER 2: only if research justifies** | Tardis historical order books; Pyth Metals; deeper Databento books; licensed BRTI history; selected Polymarket commercial or licensed sources |
| **TIER 3: do not buy now** | Direct CME DataMine; Coinbase licensed data; Kaiko; Coin Metrics; CoinDesk; LMAX; OANDA; Dukascopy; Goldsky; Bitquery; Oddpool; enterprise gold vendors; other redundant sources marked DROP |

## 4. Owner core source matrix

Columns:
- **Data / history / granularity:** what we get.
- **Book:** order-book level.
- **Live / cloud:** live availability and cloud-direct ingestion. Cloud-direct paths are documented but untested from GCP.
- **Acct / key:** account and API key needed.
- **Price → PMV cost:** public price, then projected PMV cost.
- **Ask:** what to ask, by outreach message.

### 4.1 Prediction-market sources

| ID | Provider / product | Asset | Role | Data / history / granularity | Book | Live / cloud | Acct / key | Price → PMV cost | Licence / terms issue | Status | Follow-up URL | Contact | Ask | Substitute | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K1 | Kalshi REST API, historical tier | BTC, gold PMs | Official labels, prices, trade flow | Trades, 1/60/1440-minute candles with bid/ask OHLC, settlements, market objects; back to about 2021-06; cutoff lags about 2–3 months (OWNER_VERIFY) | None | No / yes | Membership expected / no | Free → $0 | Developer Agreement (OWNER-VERIFIED): API use and storage tied to facilitating the member's own trading. Website Data Terms are separate and not applied to API data | NEEDS_WRITTEN_PERMISSION | <https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf> | `institutional@kalshi.com`, cc `support@kalshi.com` | M1 | None independent | 0 → 1 |
| K2 | Kalshi metadata, contract terms, CFTC filings | BTC, gold PMs | Rules, fees, settlement source, universe; resolves DET-1 (gold feed) and DET-2 (BTC rulebook) | Series, events, markets, fee history; contract PDFs; filings from 2024 | — | Current / yes | No / no | Free → $0 | Contract PDFs: owner download. Filings: public record | FREE_TECHNICALLY_AVAILABLE (filings: FREE_AND_USE_CLEARED) | <https://docs.kalshi.com/> | — | Download the KXBTC15M and KXGOLD15M terms | — | 0 |
| K3 | Kalshi WebSocket | BTC, gold PMs | Prospective books with receipt time; the only future holdout source | Full book (snapshot + delta), trades, lifecycle; live only | Full L2 | Yes / yes (cloud VM) | Yes (KYC) / yes, always | Free → $0 + cloud VM | As K1. The key can also trade, so it is a trading-grade secret | NEEDS_WRITTEN_PERMISSION | as K1 | as K1 | M1 | None | 1 (when authorized) |
| K4 | Kalshi CF Benchmarks channel and REST passthrough | BTC reference | BRTI (the settlement index) | BRTI values, 60 s window averages; passthrough depth UNKNOWN | — | Yes / yes | Yes / yes + entitlement | UNKNOWN | Kalshi + CF Benchmarks licence | NEEDS_LICENCE_QUOTE | <https://docs.kalshi.com/> | `institutional@kalshi.com` | M1 (price, depth, rights) | B4 (CF Benchmarks direct) | 0 (ask) / 2 (buy) |
| K5 | Kalshi `pyth_value` channel | Gold reference | Pyth gold values as Kalshi sees them | Live values with source and receipt times | — | Yes / yes | Yes / yes + entitlement | $1,000/month, 7 days free (Git) → $0 until DET-1 | Kalshi + Pyth terms | NEEDS_WRITTEN_PERMISSION | as K1 | as K1 | M1 | G3 | 2 |
| P1 | Polymarket Gamma, Data API, CLOB | BTC PMs | Metadata, fills, prospective books | Markets and tokens; indexed fills (three-year window); live L2 | L2 (live) | Yes / yes | No / no | Free → $0 | "Capital Markets Entities" must use data in consultation with Polymarket/ICE; whether an individual's own-account project counts is unclear. US persons are excluded from the international site | NEEDS_WRITTEN_PERMISSION | <https://institutional.polymarket.com/> | `data-licensing@polymarket.com` | M5 (only if needed) | P3 for US persons | 2 |
| P2 | Polymarket on-chain (Polygon RPC; BigQuery Polygon datasets) | BTC PMs | Canonical fills and payouts | Fill and resolution events from 2022-11 (BigQuery coverage UNKNOWN) | None | Near-live / yes | GCP project or RPC key | Query or provider fees → under $10 initially (estimate) | Same Polymarket/ICE statement covers on-chain derived data | NEEDS_WRITTEN_PERMISSION | as P1 | as P1 | M5 | P1 | 2 |
| P3 | Polymarket US (gateway REST; key-gated WebSocket) | BTC PMs | Tradable venue for US persons | Book, BBO, settlement, price history; no public trade tape | L2 (current) | Yes / yes | KYC for WebSocket | Free → $0 | Rulebook bars redistribution; Terms reportedly bar bulk downloads (OWNER_VERIFY) | NEEDS_WRITTEN_PERMISSION | <https://www.polymarketexchange.com/contact.html> | `data@polymarket.us` | M5 (US variant) | — | 2 |

### 4.2 BTC sources

| ID | Provider / product | Asset | Role | Data / history / granularity | Book | Live / cloud | Acct / key | Price → PMV cost | Licence / terms issue | Status | Follow-up URL | Contact | Ask | Substitute | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | Kraken historical archives (trades and OHLCVT) | BTC | Best free BTC trade tape; BRTI-proxy test | Complete public trade history with quarterly updates; OHLCVT 1–1440 minutes (OWNER-VERIFIED) | None | No / yes | No / no | Free → $0 | Whether PMV's private quantitative and ML trading use is permitted personal use or needs market-data permission | NEEDS_WRITTEN_PERMISSION | <https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-> | `marketdata@kraken.com` | M2 | O1 CoinAPI | 0 → 1 |
| B2 | Kraken public REST and WebSocket | BTC | Prospective BTC books, recent trades | Live L2 (checksummed), trades; L3 with key (OWNER-VERIFIED) | L2 (L3 with key) | Yes / yes | No (L3: yes) | Free → $0 + cloud VM | As B1 | NEEDS_WRITTEN_PERMISSION | <https://docs.kraken.com/exchange/guides/general/historical-data> | as B1 | M2 | O2 Tardis | 1 (when authorized) |
| B3 | Databento CME Bitcoin futures (BTC, MBT) | BTC futures | Optional futures lead-lag and basis | Trades, BBO/L1, book schemas, OHLCV, settlements; CME data from 2010 | Up to MBO | Yes (Standard) / yes | Yes / yes | Historical from about $0.50/GB; $125 credit (OWNER-VERIFIED) → rough estimate $2–50 for 2 years of trades and L1; use the estimator | ML, non-display, and proprietary-use classification open | PAID_SELF_SERVICE | <https://databento.com/pricing> | `support@databento.com` | M3 | Direct CME (Tier 3) | 2 (optional) |
| B4 | CF Benchmarks BRTI (direct) | BTC reference | High-value real-time BTC reference relevant to event contracts (OWNER-VERIFIED) | BRTI values; history UNKNOWN | — | Yes / UNKNOWN | Yes / yes | No public price; quote required (OWNER-VERIFIED) → UNKNOWN | Licence required for historical and real-time use | NEEDS_LICENCE_QUOTE | <https://www.cfbenchmarks.com/data/indices/BRTI> | <https://www.cfbenchmarks.com/about/contact> | M4 (quote; do not buy yet) | K4 | 0 (quote) / 2 (buy) |
| B5 | Coinbase public API (ordinary Market Data Terms) | BTC | Largest USD BRTI constituent | Trades, candles, live L2/L3 | L2/L3 live | Yes / yes | No / no | Free → $0 | Ordinary terms require prior written consent to use market data to train, validate, benchmark, or improve ML systems (OWNER-VERIFIED) | NEEDS_WRITTEN_PERMISSION | <https://www.coinbase.com/legal/market_data> | `marketdata@coinbase.com` | Optional message (not queued) | B1 + other constituents | **DROP for now** |

### 4.3 Gold sources

| ID | Provider / product | Asset | Role | Data / history / granularity | Book | Live / cloud | Acct / key | Price → PMV cost | Licence / terms issue | Status | Follow-up URL | Contact | Ask | Substitute | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G1 | Databento COMEX GC, MGC (GLBX.MDP3) | Gold futures | Main gold dynamics source | Trades, BBO/L1, book schemas, OHLCV, definitions, settlements; data from 2010 (reliable L1 from 2017-05-21); CME, CBOT, NYMEX, COMEX supported (OWNER-VERIFIED) | L1 (deeper available) | Yes (Standard) / yes | Yes / yes | $125 credit; from about $0.50/GB; Standard about $199/month (OWNER-VERIFIED) → rough estimate $5–160 for 2 years of trades and L1. **Run the estimator**; credit coverage not assumed | ML, non-display, proprietary-use, pay-as-you-go personal/commercial classification, and derived-model retention open | PAID_SELF_SERVICE (licence open) | <https://databento.com/pricing> | `support@databento.com` | M3 | Direct CME (Tier 3) | 0 → 1 |
| G2 | Databento live CME (Standard plan) | Gold futures | Prospective gold capture with receipt time | Live trades and L1/L2 | L1–L3 | Yes / yes | Yes / yes | About $199/month → only while capturing gold | Live CME licence; classification open | PAID_SELF_SERVICE | as G1 | as G1 | M3 | — | 2 |
| G3 | Pyth Pro (metals: `Metal.XAU/USD`, `Metal.Index.GOLD/USD`) | Gold reference | The reference Kalshi gold contracts reportedly settle on | Full-resolution history and candles; GOLD index from about 2026-06 (OWNER_VERIFY) | — | Yes / yes | Yes / yes | Budget about $2,500/month (OWNER-VERIFIED route). The $99 route is unverified and not budgeted | No data licence seen; methodology not obtained | PAID_SELF_SERVICE | <https://app.pyth.com/plans> | via the plans page | After DET-1: feed, history start, storage/ML terms | K5 | 2 (do not buy now) |
| G4 | Kalshi gold contract terms | Gold PMs | Settles which Pyth feed and candle Kalshi uses (DET-1) | Rule text | — | — | No / no | Free → $0 | — | FREE_TECHNICALLY_AVAILABLE | <https://docs.kalshi.com/> | — | Download the KXGOLD15M terms | — | 0 |

### 4.4 Optional / fallback sources

| ID | Provider / product | Asset | Role | Data / history / granularity | Book | Live / cloud | Acct / key | Price → PMV cost | Licence / terms issue | Status | Follow-up URL | Contact | Ask | Substitute | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O1 | CoinAPI flat files | BTC | Fallback if Kraken refuses B1 | Kraken trades and others | L2 | No / yes | Yes / yes | Pay-as-you-go → about $64–74 for full Kraken trades (OWNER_VERIFY) | Internal ML reportedly allowed | PAID_SELF_SERVICE | <https://www.coinapi.io/products/flat-files/pricing> | via site | Only if needed | B1 | Fallback |
| O2 | Tardis.dev | BTC | Historical order books, only if research shows need | Trades, L2/L3, raw exchange messages (OWNER-VERIFIED) | L2/L3 | No / yes | Yes / yes | Varies by exchange, dataset, history, and billing; recheck in the order tool (OWNER-VERIFIED) → UNKNOWN | Licence reportedly allows internal trading models (OWNER_VERIFY) | PAID_SELF_SERVICE | <https://docs.tardis.dev/historical-data-details> | `contact@tardis.dev` | Price for our configuration | O1 | 2 (do not buy now) |
| O3 | Databento deeper books (MBP-10, MBO) | Gold, BTC futures | Queue and depth features | Order-level and 10-level depth; MBO from 2017-05-21 | L2/L3 | No / yes | Yes / yes | From about $0.50/GB; large volumes → estimator | As G1 | PAID_SELF_SERVICE | <https://databento.com/pricing> | `support@databento.com` | M3 | — | 2 |
| O4 | Bitstamp, Gemini, Bullish, Crypto.com public APIs | BTC | Other BRTI constituents | Trades, live L2 | L2 live | Yes / yes | No / no | Free → $0 + cloud | Bitstamp: signed agreement for commercial use (OWNER_VERIFY) | NEEDS_WRITTEN_PERMISSION | (per exchange) | — | Later, if the BRTI-proxy test needs them | B1 | 2 |
| O5 | Marketlens; Chainlink Data Streams | Polymarket | Polymarket books and settlement reference | L2 snapshots from 2026-03; signed TWAP reports | L2 | — / yes | Yes / yes | $39+/month; about $150/month per stream (OWNER_VERIFY) | Licences UNKNOWN | PAID_SELF_SERVICE | <https://marketlens.trade/> ; <https://docs.chain.link/data-streams/billing> | via sites | Only if Polymarket is in scope | P1 capture | 2 |

## 5. Sources to drop or defer

| Source | Decision | Reason |
|---|---|---|
| Direct CME DataMine (BTC, GC, MGC, BRTI) | **Do not buy now (Tier 3)** | Databento is the preferred lower-cost path to CME/COMEX data. Fallback only if Databento lacks the required history or schema, its licence cannot cover PMV, or direct exchange data is required for a statistically justified feature. Do not confuse research-data prices with CME's redistribution or derived-data licence fees |
| Coinbase public API and licensed data | DROP for now | Ordinary terms require written consent for ML use. Kraken plus other BTC and reference sources give enough coverage. Reconsider only if the BRTI-proxy test shows material mismatches |
| Pyth $99 route | Defer | Unverified contents, history, XAU coverage, and rights |
| Kalshi website pages | Not used | Website data is legally distinct; API data is the right surface |
| Kraken Futures, offshore perpetuals, DVOL | Drop | Marginal value; US eligibility issues |
| Binance Vision | **REJECTED** | CC BY-NC-SA; prohibits live trading use (Git) |
| Kaiko, Coin Metrics, CoinDesk | Tier 3 | Enterprise pricing; redundant |
| LMAX, OANDA, Dukascopy | Tier 3 | Redundant; restricted or unsuitable terms |
| Goldsky, Bitquery, Dune, Allium | Tier 3 | BigQuery Polygon or RPC covers on-chain data |
| Oddpool | Tier 3 | PMV's own Kalshi capture is better |
| Enterprise gold vendors (LSEG, Bloomberg, Barchart, Tick Data, others) | Tier 3 | Databento is better value |
| Pyth Terminal free tier | TECHNICALLY_UNAVAILABLE | No API |

## 6. Owner outreach queue

### M1 — Kalshi
- **To:** `institutional@kalshi.com`, cc `support@kalshi.com`, from your member-account email.
- **When:** now.
- **Purpose:** confirm that historical storage, backtesting, feature engineering, statistical modelling, ML training and validation, derived-model retention, and cloud backup count as facilitating your own Kalshi trading. Also ask the price and rights of the BRTI and Pyth entitlements.

### M2 — Kraken
- **To:** `marketdata@kraken.com`.
- **When:** now.
- **Purpose:** whether PMV's private quantitative and ML use is permitted personal use, or needs market-data permission.

### M3 — Databento
- **To:** `support@databento.com`.
- **When:** now.
- **Purpose:** licence classification for ML, non-display, and proprietary use; pay-as-you-go personal vs commercial; derived-model retention. Then run the estimator.

### M4 — CF Benchmarks
- **To:** the official contact form <https://www.cfbenchmarks.com/about/contact>.
- **When:** now.
- **Purpose:** BRTI quote only; do not purchase.

### M5 — Polymarket
- **To:** `data-licensing@polymarket.com` (US: `data@polymarket.us`).
- **When:** only if scope clarification is needed.
- **Purpose:** whether an individual's own-account project is a "Capital Markets Entity", and whether PMV's uses are permitted.

### Optional — Coinbase
- **To:** `marketdata@coinbase.com`.
- **When:** not queued; Coinbase is DROP for now.
- **Purpose:** written consent for ML use, if it ever becomes necessary.

## 7. Ready-to-send outreach messages

Send these from your own email. They contain no account numbers. Agents never send them.

**M1 — Kalshi**

> Subject: Permission request: private research use of Kalshi API data for my own trading
>
> Hello,
>
> I am an individual Kalshi member developing a private, self-operated quantitative model to support my own trading on Kalshi. The Developer Agreement ties API use, and storage of API data, to facilitating a member's own trading. Could you confirm in writing that the following activities count as facilitating my own Kalshi trading, or tell me what authorization they need? They use data from Kalshi's REST API (including the historical endpoints and market, event, series, and settlement metadata) and WebSocket API.
>
> 1. Automated retrieval through the API, within published rate limits.
> 2. Historical storage of API data privately in my own cloud storage (Google Cloud), with encrypted backups.
> 3. Private quantitative research and backtesting.
> 4. Feature engineering and statistical modelling.
> 5. Training and validating machine-learning models.
> 6. Creating and retaining derived features and model parameters (weights), including after my API access ends.
> 7. Using the resulting model's output solely for my own trading on Kalshi.
> 8. Capturing WebSocket market data prospectively and storing it for the same purposes.
>
> I will not redistribute, publish, sell, or share raw Kalshi data or derived datasets with any third party.
>
> Could you also confirm:
> - that the Kalshi Data Terms of Use apply to website content and not to API data, or which document governs if they overlap;
> - the price, history depth, and permitted uses (including storage and model training) of the CF Benchmarks data entitlement (REST passthrough and WebSocket channel) and of the Pyth gold channel.
>
> Thank you.

**M2 — Kraken**

> Subject: Permission request: private quantitative research on Kraken public market data
>
> Hello,
>
> I am an individual developing a private, self-operated quantitative model whose signals I would use solely for my own trading. Please confirm whether this falls within permitted personal use, or requires market-data permission. If it requires permission, would you grant it for the following?
>
> 1. Downloading your historical public trade ("time and sales") and OHLCVT archives.
> 2. Storing them privately in my own Google Cloud storage, with backups.
> 3. Constructing features from them.
> 4. Training and validating machine-learning models on them.
> 5. Retaining the derived model artifacts.
> 6. Consuming your public WebSocket market data prospectively and storing it for the same purposes.
> 7. Using the resulting signals solely for my own trading.
>
> I will not redistribute any raw data. Thank you.

**M3 — Databento**

> Subject: Licensing question before purchase: historical CME/COMEX data for private research and own-account trading
>
> Hello,
>
> Before purchasing, I would like to confirm licensing for GLBX.MDP3 data: GC and MGC (and possibly BTC and MBT) trades, BBO/L1, OHLCV, definitions, and statistics. I may also want live data on the Standard plan.
>
> My intended use: I am an individual building a private quantitative model for my own trading. I would:
> - store the data privately in my own Google Cloud storage;
> - use it for research and backtesting;
> - train and validate machine-learning models;
> - retain derived features and model weights;
> - use the model's output in automated trading of my own account.
>
> I will not distribute any data externally.
>
> 1. Does pay-as-you-go historical data permit this use, and is it classified as personal or commercial use?
> 2. Does CME's June 2026 licence update, which restricts machine-learning use of "Information", apply to historical data bought from Databento for internal non-display use like mine?
> 3. On the Standard plan, does "license fees included" cover automated (non-display) proprietary use by an individual trading their own account, and which subscriber category applies?
> 4. Can I keep historical data and derived models after my subscription ends?
>
> Thank you.

*Signup questionnaire:*
- Answer truthfully: internal use, no redistribution, likely non-display use (automated processing).
- If you are unsure of professional vs non-professional status, ask rather than choosing the cheaper category.
- Run the estimator before buying.

**M4 — CF Benchmarks** (via <https://www.cfbenchmarks.com/about/contact>)

> Subject: Licence quote request: BRTI historical and real-time data for private research and own-account trading
>
> Hello,
>
> I am an individual developing a private quantitative model for my own trading on event contracts that settle on the CME CF Bitcoin Real Time Index. Please send a quote and licence terms for:
> - historical BRTI values at the finest available granularity, with your restatement policy or first-published vintages;
> - a point-in-time constituent history;
> - optionally, real-time BRTI.
>
> Intended use: private storage in my own cloud, research, backtesting, machine-learning model training, and own-account trading. No redistribution. If an authorized channel (for example Kalshi's data entitlement or CME DataMine) is the better route for this use, please say so.
>
> Thank you.

**M5 — Polymarket** (only if needed)

> Subject: Does an individual's own-account research project count as a "Capital Markets Entity"?
>
> Hello,
>
> I am an individual, not a firm, developing a private quantitative model for my own trading. I would:
> - retrieve public Polymarket data (Gamma, Data API, CLOB order books, and on-chain fills and resolutions);
> - store it privately in my own cloud storage;
> - backtest and train machine-learning models;
> - use the output solely for my own trading.
>
> I will not redistribute data.
>
> Am I a "Capital Markets Entity" that must consume data in consultation with Polymarket and ICE? If not, are these uses permitted under your terms? If so, what is the licensing route?
>
> [For Polymarket US: which terms govern automated retrieval and storage of public gateway and WebSocket data for my own trading research?]
>
> Thank you.

**Optional — Coinbase** (not queued)

> Subject: Written consent request: Market Data Terms, machine-learning use for own-account trading
>
> Your Market Data Terms require prior written consent to use market data to train or validate machine-learning models. I am an individual building a private model for my own trading. The data would be stored in private cloud storage, never redistributed, and the model's output used solely for my own trading. Would Coinbase grant consent, or is a licence required? If a licence is required, what does it cost?

## 8. Costs and budget scenarios

All figures are rough. Prices marked OWNER_VERIFY or estimate are not quotes.

### 8.1 Minimum viable
- **Sources:** K1, K2, B1, G1 (§2).
- **One-time market data:** about **$0–$160**. Not guaranteed: it needs the Databento estimator result and cleared permissions.
- **Monthly:** cloud about $10–20 at bootstrap.
- **Licensing prerequisites:** M1, M2, M3.

### 8.2 Better dataset
- **Sources:** minimum viable, plus:
  - prospective capture (K3, B2, and K4 once its entitlement is resolved);
  - one month of Databento Standard (about $199) for 12 months of L1;
  - one licensed BRTI history (quote, M4);
  - a gold reference after DET-1 (K5 at $1,000/month, or Pyth).
- **One-time:** about $200–$400, plus the BRTI quote (UNKNOWN).
- **Monthly:** about $380–$1,400 (cloud about $180; Databento live about $199 if capturing gold; gold reference).
- **Licensing prerequisites:** M1–M4, capture and credential approvals.

### 8.3 Ideal / expensive dataset
- **Sources:** better dataset, plus:
  - Tardis historical order books (configuration-dependent cost);
  - Pyth Metals (budget about $2,500/month);
  - deeper Databento books;
  - Polymarket sources, if in scope.
- **One-time:** several thousand dollars, depending on the Tardis configuration, plus quotes.
- **Monthly:** about $3,000–$4,000 or more.
- **Licensing prerequisites:** all of the above, plus the Tardis and Pyth licences and M5.

## 9. Accounts / API keys eventually required

| Account | When | Notes |
|---|---|---|
| Kalshi member account + API key | Prospective capture and reference channels | The key can trade. Keep it only in GCP Secret Manager, never on the Chromebook or in an agent session |
| Databento account + API key | Tier 1 (gold) | Card at signup; answer the licence questionnaire truthfully |
| GCP billing account | CLOUD-0 | Upgrade beyond the free trial |
| CF Benchmarks licence (or Kalshi entitlement) | Only if the BRTI quote is economical | — |
| Tardis, Pyth | Tier 2 only | — |
| Polymarket credentials | Only if Polymarket is in scope | — |
| Kraken | Not needed for public data | L3 needs a key (optional) |

## 10. Remaining blockers

**Current state:**
- cloud architecture research is complete;
- source procurement research is complete, and this packet is complete;
- no bulk market data has been acquired, no vendor purchase made, and no cloud resource provisioned;
- no `T0` exists, and no protected holdout has been opened.

**Blockers:**
1. Kalshi's written clarification (M1). This is the critical path.
2. Kraken's answer (M2).
3. Databento's licence classification (M3) and the estimator result for our exact pull.
4. The CF Benchmarks quote (M4).
5. DET-1 and DET-2: you download the Kalshi contract terms.
6. Your cloud decisions and per-source approvals (decision record D-B09-10 to D-B09-16), plus the other open B09 decisions.

## 11. Owner links — action required

**Kalshi**
- Developer Agreement: <https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf>
- Website Data Terms: <https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf>
- Terms of Service: <https://kalshi.com/terms>
- API docs: <https://docs.kalshi.com/>
- Help / contact: <https://help.kalshi.com/en/articles/13823855-contact-kalshi-support>
- Contacts: `institutional@kalshi.com`, `support@kalshi.com`

**Kraken**
- Trade archive: <https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales->
- OHLCVT archive: <https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data>
- API docs: <https://docs.kraken.com/exchange/guides/general/historical-data>
- Legal: <https://www.kraken.com/legal>
- Contact: `marketdata@kraken.com`

**Databento**
- Pricing: <https://databento.com/pricing>
- CME catalog: <https://databento.com/catalog/cme/GLBX.MDP3>
- Signup: <https://databento.com/signup>
- Cost estimator: <https://databento.com/docs/api-reference-historical/metadata/metadata-get-cost>
- Legal: <https://databento.com/legal>
- Contact: `support@databento.com`

**CF Benchmarks**
- BRTI: <https://www.cfbenchmarks.com/data/indices/BRTI>
- Contact: <https://www.cfbenchmarks.com/about/contact>

**Polymarket** (only if in scope)
- Institutional: <https://institutional.polymarket.com/>
- Terms: <https://polymarket.com/tos>
- Docs: <https://docs.polymarket.com/>
- US contact: <https://www.polymarketexchange.com/contact.html>

**Pyth** (do not buy now)
- Products: <https://app.pyth.com/products>
- Plans: <https://app.pyth.com/plans>

**Tardis** (do not buy now)
- Home: <https://tardis.dev/>
- Data details: <https://docs.tardis.dev/historical-data-details>

**CME DataMine** (fallback only)
- DataMine: <https://www.cmegroup.com/datamine.html>

**Coinbase** (DROP for now)
- Market Data Terms: <https://www.coinbase.com/legal/market_data>
