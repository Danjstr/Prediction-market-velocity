# PMV data sources: owner action sheet and procurement packet (B09, 2026-10-18)

**What this is.** One page answering, for each data source: what data we can get, what we might get, what needs written permission or a licence, what costs money and how much, and where you go to get it.
- The full research inventory is `research/data_sources/master_source_inventory.md` (100 rows). This sheet is the owner-facing summary.
- **Nothing here has been bought, signed, or downloaded.** Acquisition still needs:
  - your per-source approval (A-1 to A-6, `docs/external_access.md` §2);
  - the cloud pipeline (`research/cloud/pmv_cloud_architecture_review.md` §12).

**Evidence tags.**

| Tag | Meaning |
|---|---|
| **OWNER-VERIFIED** | The owner checked the official page and reported the fact on 2026-10-18 (documentation sync). Recorded as the owner's statement. A-2 licence determinations still need a verbatim quote and a hash of the document |
| **FETCHED** | An agent fetched the official page on 2026-10-18 and a tool summarized it. Not verbatim |
| **OWNER_VERIFY** | From search summaries only. The official URL is given; please check it in your browser |
| **Git** | From documentation snapshots in the repository (Kalshi 2026-10-15, Polymarket 2026-10-16) |

**Status categories (one per source).**

| Status | Meaning |
|---|---|
| FREE_TECHNICALLY_AVAILABLE | Free to obtain; PMV's ML/trading use is **not** yet cleared |
| FREE_AND_USE_CLEARED | Free, and the intended use is affirmatively permitted |
| NEEDS_WRITTEN_PERMISSION | Obtainable, but PMV needs the provider's consent or clarification for its use |
| NEEDS_LICENCE_QUOTE | A licence or negotiated terms are needed, and no public price exists |
| PAID_SELF_SERVICE | Public price; you can sign up without negotiating |
| FREE_SAMPLE_ONLY | Only a free sample exists; full history is paid or licence-bound |
| TECHNICALLY_UNAVAILABLE | The needed data does not exist or cannot be obtained |
| REJECTED | Terms clearly prohibit the use, and there is no practical licensed path |

---

## 1. Headline answers

1. **What can we get for $0, once permissions clear?**
   - Kalshi: historical trades, candles, settlements, metadata, and the live WebSocket.
   - Kraken: the full BTC trade archive, the OHLCVT archive, and live REST/WebSocket.
   - Rules: Kalshi contract terms and CFTC filings.
   - All are technically free. Only the CFTC filings are fully use-cleared.
2. **What needs written permission or clarification?**
   - **Kalshi.** The Developer Agreement limits API use, and storage of API data, to facilitating the member's own trading (OWNER-VERIFIED). Kalshi must confirm that storage, backtesting, modelling, ML training, model retention, and cloud backup count as such.
   - **Kraken:** whether this use needs market-data permission.
   - **Databento:** licence classification for ML and non-display use, proprietary trading, and pay-as-you-go use.
   - **Polymarket:** only if it is in scope.
   - Coinbase also needs consent, but is dropped for now.
3. **What needs a licence quote?**
   - **CF Benchmarks BRTI** (request a quote now; do not buy yet).
   - Kalshi's BRTI data entitlement.
   - Direct CME DataMine (not recommended).
4. **What can you simply buy, later and only if justified?**
   - **Databento:** $125 credit; historical from about $0.50/GB; Standard about $199/month.
   - **Pyth Pro:** budget about $2,500/month for metals.
   - **Tardis:** price varies by exchange, dataset, history, and billing.
   - **CoinAPI**, as a fallback.
5. **Do we need a $20,000–$35,000 CME purchase? No.**
   - The $35,220 figure on CME's fee list is the historical **redistribution** licence. PMV does not redistribute.
   - Databento is the preferred lower-cost route to the same CME/COMEX exchange data.

## 2. Minimum viable dataset (the initial target)

| Side | Sources | Condition |
|---|---|---|
| **BTC and prediction markets** | Kalshi historical markets, trades, and metadata; Kraken historical BTC trades; Kalshi contract, rule, and settlement metadata | Once Kalshi (M1) and Kraken (M2) permissions clear |
| **Gold** | Databento GC/MGC trades and/or L1 | Once the licence classification clears (M3) |
| **Prospective (later)** | Kalshi WebSocket; Kraken WebSocket; BRTI or another reference source once its entitlement is settled | Separately authorized capture |

- **Target market-data cost before optional upgrades: about $0–$160 initial.**
  - This depends on Databento's estimator result for our actual symbols, schemas, and dates, and on vendor permission. It is not guaranteed.
  - Cloud cost is separate: about $10–20/month at bootstrap.
- **Signals it gives:**
  - late-window Kalshi prices (1-minute candle bid and ask), trade flow, official settlements, and fees;
  - BTC spot trade velocity, as a BRTI proxy;
  - gold futures dynamics and settlements.
- **What it lacks:**
  - order books anywhere;
  - exact BRTI;
  - the gold reference series;
  - receipt-time data;
  - long Kalshi gold history (about 2.5 months).
- **Enough for:** the proposed M-0 go/no-go test (decision record D-B09-18). Spending beyond this waits for that result.

## 3. Procurement tiers

| Tier | Items |
|---|---|
| **TIER 0: contact and clear now** | Kalshi (M1); Kraken (M2); Databento (M3); CF Benchmarks BRTI quote (M4); Polymarket clarification only if needed for scope (M5). Also download the Kalshi contract terms (resolves DET-1 gold feed and DET-2 BTC rulebook) |
| **TIER 1: acquire once cleared** | Kalshi historical/API data; Kraken historical archive; Databento GC/MGC L1/trades; prospective Kalshi and Kraken capture when separately authorized |
| **TIER 2: buy only if research justifies it** | Tardis historical order books; Pyth Metals; deeper Databento book schemas (MBP-10, MBO); licensed BRTI history if the quote is economically reasonable; selected Polymarket commercial or licensed feeds |
| **TIER 3: do not buy now** | Direct CME DataMine bulk depth/MBO; Coinbase licensed data; Kaiko; Coin Metrics; CoinDesk; LMAX; OANDA; Dukascopy; Goldsky; Bitquery; Oddpool; enterprise gold vendors; other sources marked DROP |

## 4. Owner core matrix

Split into two tables keyed by row ID.

### 4A. What each source is

| ID | Provider / data product | Asset | Role in PMV | What data we get | History start / depth | Granularity | Order book | Live? | Cloud-direct? |
|---|---|---|---|---|---|---|---|---|---|
| K1 | Kalshi REST API: historical tier | BTC, gold PMs | Official labels, market prices, trade flow | Trades; 1/60/1440-minute candles with bid/ask OHLC; settlement values; market objects | Archive back to about 2021-06; cutoff lags about 2–3 months (OWNER_VERIFY) | Trade print; 1 minute | None | No | Yes (untested from GCP) |
| K2 | Kalshi REST metadata; contract terms; CFTC filings | BTC, gold PMs | Contract rules, fees, settlement source, universe | Series, events, markets, fee history, rulebook text, contract PDFs | All series and events (Git); filings from 2024 | Per record | — | Current state | Yes |
| K3 | Kalshi WebSocket | BTC, gold PMs | Prospective capture of books with receipt time; the only future holdout source | Full book (snapshot + delta), trades, lifecycle, settlement | Live only | Per message | Full L2 | Yes | Yes (cloud VM) |
| K4 | Kalshi CF Benchmarks channel and REST passthrough | BTC reference | BRTI, the index Kalshi BTC contracts settle on | BRTI values; 60 s window averages | Passthrough depth UNKNOWN; WebSocket live only | Tick / update | — | Yes | Yes |
| K5 | Kalshi `pyth_value` channel | Gold reference | The Pyth gold values Kalshi observes | Values with source and receipt timestamps | Live only | Per update | — | Yes | Yes |
| P1 | Polymarket Gamma API | BTC PMs | Contract metadata | Markets, token IDs, fees, ticks, resolution source | All markets (current state) | Per record | — | Current | Yes |
| P2 | Polymarket Data API v2 | BTC PMs | Trade and resolution cross-check | Indexed fills, resolutions | Three-year window per market | Per fill | None | — | Yes |
| P3 | Polymarket CLOB (REST and WebSocket) | BTC PMs | Prospective Polymarket books | L2, BBO, last trade, tick changes | Live only | Per message | Full L2 | Yes | Yes |
| P4 | Polymarket on-chain (Polygon RPC; BigQuery Polygon datasets) | BTC PMs | Canonical fills and payouts | Fill and resolution events | From 2022-11 (BigQuery coverage UNKNOWN) | Per event | None | Near-live | Yes |
| P5 | Polymarket US (public gateway; key-gated WebSocket) | BTC PMs | The tradable Polymarket venue for US persons | Book, BBO, settlement, price history; no public trade tape | Short / UNKNOWN | Per call | L2 (current) | Yes | Yes |
| B1 | Kraken downloadable trade archive ("time and sales") | BTC | **Best free BTC trade tape**; BRTI-proxy test | Complete public trade history, every pair; quarterly updates (OWNER-VERIFIED) | From first trade (latest file to 2026-09-30, OWNER_VERIFY) | Trade | None | No | Yes |
| B2 | Kraken OHLCVT archive | BTC | Bars with trade counts | OHLCV + trade count, 1–1440 minutes (OWNER-VERIFIED availability) | To 2026-06-30 (OWNER_VERIFY) | 1 minute+ | None | No | Yes |
| B3 | Kraken public REST and WebSocket | BTC | Prospective BTC books; recent trades | Live L2 (checksummed), trades; L3 with a key (OWNER-VERIFIED availability) | Live / recent | Per message | L2 (L3 with key) | Yes | Yes |
| B4 | Tardis.dev historical data | BTC | Historical crypto microstructure, if order-book features prove valuable | Trades, L2/L3, raw exchange messages, with exchange and receipt timestamps (OWNER-VERIFIED) | 2019 onward; depth sold depends on billing | Per message, µs | L2/L3 | No (historical) | Yes (HTTPS pulls) |
| B5 | Coinbase public API (ordinary Market Data Terms) | BTC | Largest USD BRTI constituent | Trades, candles, live L2/L3 | Trades by cursor; live | Trade / message | L2/L3 live | Yes | Yes |
| B6 | Coinbase licensed data (Data Marketplace) | BTC | Licensed Coinbase history | Tick trades, OHLCV (per help page) | UNKNOWN | Tick | UNKNOWN | — | UNKNOWN |
| B7 | Databento CME Bitcoin futures (GLBX.MDP3: BTC, MBT) | BTC futures | Regulated futures lead-lag and basis (optional) | Trades, BBO/L1, order-book schemas, OHLCV, settlements | CME data from 2010; MBO from 2017-05-21 | Event, ns | Up to MBO | Yes (Standard) | Yes (API key) |
| B8 | CME DataMine Bitcoin futures | BTC futures | Same exchange data as B7 | T&S, depth, MBO, settlements | From contract start | Tick | Up to MBO | No | Yes (S3/SFTP) |
| B9 | CF Benchmarks BRTI (direct) | BTC reference | High-value BTC real-time reference; relevant to event and prediction contracts (OWNER-VERIFIED) | BRTI values | UNKNOWN | 200 ms / 1 s | — | Yes | UNKNOWN |
| B10 | CME DataMine CRYPTOCURRENCY (CME CF BRR/BRTI) | BTC reference | A BRTI history route | BRTI per second | From 2016-11/12 (OWNER_VERIFY) | ~1 s | — | No | Yes |
| B11 | Bitstamp, Gemini, Bullish, Crypto.com public APIs | BTC | Other BRTI constituents | Trades, live L2 | Short native history | Trade / message | L2 live | Yes | Yes |
| G1 | Databento COMEX GC, MGC, 1OZ (GLBX.MDP3) | Gold futures | **Main gold dynamics source** | Trades, BBO/L1, order-book schemas, OHLCV, definitions, settlements (OWNER-VERIFIED schema availability) | 2010; reliable L1 from 2017-05-21 | Event, ns; 1 s bars | L1 (deeper available) | Yes (Standard) | Yes (API key) |
| G2 | Databento live CME (Standard plan) | Gold futures | Prospective gold capture with receipt time | Live trades, L1/L2 | Live | Per message | L1–L3 | Yes | Yes |
| G3 | CME DataMine GC/MGC | Gold futures | Same exchange data as G1 | T&S, BBO, depth, MBO, settlements | T&S 1982; BBO 1999; depth 2005 (OWNER_VERIFY) | Tick | Up to MBO | No | Yes |
| G4 | Pyth Pro (metals: `Metal.XAU/USD`, `Metal.Index.GOLD/USD`) | Gold reference | The reference Kalshi gold contracts reportedly settle on | Full-resolution history; candles; prices | GOLD index from about 2026-06; XAU start UNKNOWN | 200 ms / 1 min | — | Yes | Yes (API key) |
| G5 | Pyth $99 package (offered via Polymarket's docs) | Gold reference | Possible cheap reference route | Reportedly XAU, XAG, WTI, equities | UNKNOWN | UNKNOWN | — | Yes | UNKNOWN |
| G6 | Kalshi gold contract terms (DET-1) | Gold PMs | Which Pyth feed and candle Kalshi uses | Rule text | — | — | — | — | n/a |
| O1 | CoinAPI flat files | BTC | Fallback for Kraken trades or LMAX | Trades, quotes, book updates | Per exchange | Tick | L2 | No | Yes (S3-compatible) |
| O2 | Marketlens | Polymarket | Polymarket book history | L2 snapshots + price changes | From 2026-03 | 60 s / ms | L2 | — | Yes |
| O3 | Chainlink Data Streams | BTC reference (Polymarket) | Polymarket BTC settlement source | Signed reports, 60 s TWAP | Retention UNKNOWN | Per report | — | Yes | Yes |

### 4B. Access, cost, and action

| ID | Account? | API key? | Public price | Projected PMV cost | Licence / terms issue | Current status | Follow-up URL | Contact | What you must ask | Best substitute | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|
| K1 | Kalshi membership expected (Developer Agreement) | No | Free | $0 | **Developer Agreement** (OWNER-VERIFIED): API use is limited to facilitating a member's own trading, and storage of API data is limited to purposes that facilitate the member's own trading. This does **not** by itself prohibit ML or backtesting. Kalshi must confirm that historical storage, backtesting, feature engineering, statistical modelling, ML training and validation, derived-model retention, and cloud backup count as facilitating the member's own Kalshi trading. The website Data Terms are a separate document and are **not** extended to API data | NEEDS_WRITTEN_PERMISSION (clarification) | <https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf> | `institutional@kalshi.com`, cc `support@kalshi.com`, from your member-account email | M1 | None independent (third-party copies share the upstream terms) | 0 → 1 |
| K2 | No | No | Free | $0 | Contract PDFs are an owner download; CFTC filings are public record | FREE_TECHNICALLY_AVAILABLE (filings: FREE_AND_USE_CLEARED) | <https://docs.kalshi.com/> ; <https://www.cftc.gov/> | — | Download the KXBTC15M and KXGOLD15M contract terms | — | 0 |
| K3 | Yes (KYC member) | **Yes, always** (Git) | Free | $0 + cloud VM (about $50–70/month per collector pair) | As K1. The key can also trade, so it is handled as a trading-grade secret | NEEDS_WRITTEN_PERMISSION | as K1 | as K1 | In M1 (prospective capture and storage) | None | 1 (when separately authorized) |
| K4 | Yes | Yes + entitlement | UNKNOWN | UNKNOWN | Kalshi terms + CF Benchmarks licence | NEEDS_LICENCE_QUOTE | <https://docs.kalshi.com/> | `institutional@kalshi.com` | Entitlement price, depth, storage/ML rights (in M1) | B9, B10 | 0 (ask) / 2 (buy) |
| K5 | Yes | Yes + entitlement | $1,000/month; first 7 days free (Git) | $0 until DET-1 is resolved | Kalshi + Pyth terms | NEEDS_WRITTEN_PERMISSION | as K1 | as K1 | In M1 | G4 | 2 |
| P1–P3 | No | No | Free | $0 | Polymarket says "Capital Markets Entities" must use data in consultation with Polymarket/ICE. Whether an individual's own-account project is one is unclear. US persons are excluded from the international site | NEEDS_WRITTEN_PERMISSION | <https://institutional.polymarket.com/> ; <https://polymarket.com/tos> | `data-licensing@polymarket.com` | M5, only if Polymarket is in scope | P5 for US persons | 0 (if needed) / 2 |
| P4 | GCP project or RPC provider | RPC key | Query bytes / provider tiers | Under $10 initially (estimate) | As P1 (covers on-chain derived data) | NEEDS_WRITTEN_PERMISSION | as P1 | as P1 | M5 | P2 | 2 |
| P5 | For WebSocket (KYC) | For WebSocket | Free | $0 | Rulebook bars redistribution; reported Terms of Use limit use to personal, non-commercial use in connection with your trading, and bar bulk downloads (OWNER_VERIFY) | NEEDS_WRITTEN_PERMISSION | <https://polymarketexchange.com/files/legal/latest/rulebook> ; <https://www.polymarketexchange.com/contact.html> | `data@polymarket.us` | M5 (US variant) | — | 2 |
| B1 | No | No | Free (technically $0) | $0 | Whether a private, owner-operated quantitative and ML trading use is permitted personal use or needs market-data permission. The legacy API notice asks for permission for non-personal commercial use of public market data (OWNER_VERIFY) | NEEDS_WRITTEN_PERMISSION | <https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-> | `marketdata@kraken.com` | M2 | O1 CoinAPI (about $64–74 for full Kraken trades, OWNER_VERIFY) | 0 → 1 |
| B2 | No | No | Free | $0 | As B1 | NEEDS_WRITTEN_PERMISSION | <https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data> | as B1 | In M2 | Derive from B1 | 0 → 1 |
| B3 | No (L3: yes) | No (L3: yes) | Free | $0 + cloud VM | As B1 | NEEDS_WRITTEN_PERMISSION | <https://docs.kraken.com/exchange/guides/general/historical-data> | as B1 | In M2 (prospective WebSocket use) | B4 | 1 (when separately authorized) |
| B4 | Yes | Yes (valid while subscribed) | **Varies** by exchange, dataset, history depth, and billing period. Recheck plans and minimum order in the order tool. A $700/month Solo single-data-plan figure was observed (OWNER_VERIFY) and is not a universal PMV cost | UNKNOWN until configured in the order tool | Licence reportedly allows internal trading models and keeps downloaded data perpetually (OWNER_VERIFY); Coinbase excluded from single-plan products | PAID_SELF_SERVICE | <https://tardis.dev/> ; <https://docs.tardis.dev/historical-data-details> | `contact@tardis.dev` | Price for Kraken (and other constituents) L2 for our dates; licence clauses | O1 | 2 (do not buy yet) |
| B5 | No | No | Free | $0 | **Ordinary Market Data Terms prohibit using market data to train, validate, benchmark, or otherwise improve ML systems without prior written consent** (OWNER-VERIFIED) | NEEDS_WRITTEN_PERMISSION | <https://www.coinbase.com/legal/market_data> | `marketdata@coinbase.com` | Not queued (optional message in §6) | B1 + B11 | **DROP for now** |
| B6 | Yes | — | CONTACT SALES / UNKNOWN | UNKNOWN | Licence on purchase | NEEDS_LICENCE_QUOTE | <https://help.coinbase.com/en/data-marketplace/getting-started/coinbase-data-marketplace> | `marketdata@coinbase.com` | — | B1 | 3 |
| B7 | Yes | Yes | $125 credit; historical from about $0.50/GB; Standard about $199/month (OWNER-VERIFIED) | Optional. Rough estimate for 2 years of BTC/MBT trades, BBO, OHLCV, and definitions: about $2–50. **Use the estimator** | Licence classification open (M3) | PAID_SELF_SERVICE | <https://databento.com/pricing> | `support@databento.com` | M3 | B8 | 2 (optional) |
| B8 | CME login | — | CONTACT SALES / UNKNOWN | UNKNOWN | ILA/DDLA; DS-45 | NEEDS_LICENCE_QUOTE | <https://www.cmegroup.com/datamine.html> | `CMEDataSales@cmegroup.com` | Only under the fallback conditions in §5 | B7 | **3** |
| B9 | Yes | Yes | **No public price; quote required** for the intended product or service use (OWNER-VERIFIED) | UNKNOWN | Licence required for historical and real-time use | NEEDS_LICENCE_QUOTE | <https://www.cfbenchmarks.com/data/indices/BRTI> | Official contact form: <https://www.cfbenchmarks.com/about/contact> | M4: request a quote now; do not purchase yet | K4, B10 | 0 (quote) / 2 (buy) |
| B10 | CME login | — | CONTACT SALES / UNKNOWN | UNKNOWN | MDLA + derived-data licence; DS-45 | NEEDS_LICENCE_QUOTE | <https://www.cmegroup.com/datamine.html> | `CMEDataSales@cmegroup.com` | Only if CF Benchmarks and Kalshi routes fail | B9, K4 | 3 |
| B11 | No | No | Free | $0 + cloud | Bitstamp: signed Data License Agreement for commercial use (OWNER_VERIFY); others unread | NEEDS_WRITTEN_PERMISSION | (per exchange) | Bitstamp `partners@bitstamp.net` (OWNER_VERIFY) | Later, only if the BRTI-proxy test needs them | B4 | 3 |
| G1 | Yes | Yes | $125 new-account credit; historical from about $0.50/GB; Standard about $199/month; CME, CBOT, NYMEX, COMEX supported (OWNER-VERIFIED) | Rough estimate for 2 years of GC+MGC trades, BBO, OHLCV, and definitions: about $5–160. **Do not assume the $125 credit covers it until the estimator is run** for our exact symbols, schemas, and dates. Alternative: one month of Standard covers the last 12 months of L1 | **Open:** ML use; non-display use; proprietary trading; pay-as-you-go personal vs commercial classification; derived-model retention | PAID_SELF_SERVICE (licence open) | <https://databento.com/pricing> ; <https://databento.com/catalog/cme/GLBX.MDP3> | `support@databento.com` | M3 | G3 | **0 → 1** |
| G2 | Yes | Yes | Standard about $199/month | $199/month while capturing gold | Live CME licence; DS-45 | PAID_SELF_SERVICE | as G1 | as G1 | In M3 | — | 2 |
| G3 | CME login | — | CONTACT SALES / UNKNOWN | UNKNOWN | ILA/DDLA; DS-45 | NEEDS_LICENCE_QUOTE | <https://www.cmegroup.com/datamine.html> | `CMEDataSales@cmegroup.com` | Only under the fallback conditions in §5 | G1 | **3** |
| G4 | Yes | Yes | **Budget assumption: Pyth Pro from about $2,500/month** for the level covering commodities/metals, full-resolution history, and non-display use (OWNER-VERIFIED route) | $2,500 for one month, only if justified | No data licence seen; index methodology not obtained | PAID_SELF_SERVICE | <https://app.pyth.com/products> ; <https://app.pyth.com/plans> | via the plans page | DET-1 first; then history start and storage/ML terms | K5 | 2 (do not buy yet) |
| G5 | Yes | Yes | $99/month (**UNVERIFIED / OWNER_VERIFY**) | **Do not budget** until contents, history, XAU coverage, and licence rights are confirmed | UNKNOWN | OWNER_VERIFY | <https://app.pyth.com/plans> | — | Exact feeds and rights | G4 | 2 |
| G6 | No | No | Free | $0 | — | FREE_TECHNICALLY_AVAILABLE | as K2 | — | Download the KXGOLD15M terms | — | 0 |
| O1 | Yes | Yes | Pay-as-you-go; $25 credit (OWNER_VERIFY) | About $64–74 for Kraken's full trades (OWNER_VERIFY) | Internal ML reportedly allowed | PAID_SELF_SERVICE | <https://www.coinapi.io/products/flat-files/pricing> | via site | Only if Kraken refuses B1 | B1 | fallback |
| O2 | Yes | Yes | $39–199/month (OWNER_VERIFY) | $39+/month | Licence UNKNOWN | PAID_SELF_SERVICE | <https://marketlens.trade/> | via site | Only if Polymarket is in scope | P3 capture | 2 |
| O3 | Yes | Yes | About $150/month per stream (OWNER_VERIFY) | $150/month | ToS unread | PAID_SELF_SERVICE | <https://docs.chain.link/data-streams/billing> | via portal | Only if Polymarket BTC is in scope | — | 2 |

## 5. Explicit recommendations

- **CME DataMine: do not buy direct CME DataMine yet.**
  - Databento is the preferred lower-cost path to CME/COMEX data.
  - Direct DataMine becomes a fallback only if one of these holds:
    - Databento lacks the required history or schema;
    - Databento's licence cannot cover PMV;
    - direct exchange data is required for a statistically justified feature.
  - Historical research-product prices are **not** the same thing as CME's redistribution or derived-data licence fees.
- **Coinbase: drop for now.**
  - The ordinary terms prohibit ML training and validation without written consent (OWNER-VERIFIED).
  - Kraken plus the other BTC and reference sources give enough coverage, so obtaining consent is not worth your time now.
  - Reconsider only if the Kraken-based BRTI-proxy test shows material mismatches near the strike.
- **Pyth: do not buy yet.**
  - Budget around $2,500/month if it is ever needed.
  - Do not budget around the $99 package until it is confirmed.
- **Tardis: do not buy yet.** It is useful only if order-book features prove valuable. Price it in the order tool at that point.
- **CF Benchmarks: request a quote now, do not purchase yet.**

**Dropped or rejected sources:**

| Source | Status | Reason |
|---|---|---|
| Kalshi website pages | Not used | Website data is legally separate; API data is the right surface |
| Kraken Futures | FREE_TECHNICALLY_AVAILABLE | Perpetuals are not BRTI inputs |
| Offshore perpetuals and DVOL | NEEDS_WRITTEN_PERMISSION | US eligibility; marginal value |
| Binance Vision | **REJECTED** | CC BY-NC-SA; prohibits live trading use (Git, verified) |
| Kaiko, Coin Metrics, CoinDesk | NEEDS_LICENCE_QUOTE | Enterprise pricing; redundant |
| LMAX, OANDA, Dukascopy | Various | Redundant; restricted or unsuitable terms |
| Goldsky, Bitquery, Dune, Allium | Paid / quote | BigQuery Polygon or RPC covers on-chain data |
| Oddpool | PAID_SELF_SERVICE | PMV's own Kalshi capture is better |
| Pyth Terminal free tier | TECHNICALLY_UNAVAILABLE | No API |
| LSEG, Bloomberg, Barchart, Tick Data, Massive, Twelve Data, FirstRate, Kibot | Paid | Databento is better |

## 6. Owner outreach queue (ready to send)

Send from your own email; for Kalshi, use the email on your member account. The messages contain no account numbers. Agents never send them.

| # | To | When |
|---|---|---|
| **M1** | Kalshi: `institutional@kalshi.com`, cc `support@kalshi.com` | Now |
| **M2** | Kraken: `marketdata@kraken.com` | Now |
| **M3** | Databento: `support@databento.com` | Now |
| **M4** | CF Benchmarks: official contact form <https://www.cfbenchmarks.com/about/contact> | Now (quote only) |
| **M5** | Polymarket: `data-licensing@polymarket.com` (US: `data@polymarket.us`) | Only if clarification is needed for scope |
| (optional) | Coinbase: `marketdata@coinbase.com` | Not queued; Coinbase is DROP for now |

### M1: Kalshi

> Subject: Permission request: private research use of Kalshi API data for my own trading
>
> Hello,
>
> I am an individual Kalshi member developing a private, self-operated quantitative model to support my own trading on Kalshi. The Developer Agreement limits API use, and storage of API data, to facilitating a member's own trading. Could you confirm in writing that the following activities, using data from Kalshi's REST API (including the historical endpoints and market, event, series, and settlement metadata) and WebSocket API, count as facilitating my own Kalshi trading, or tell me what authorization they need:
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

### M2: Kraken

> Subject: Permission request: private quantitative research on Kraken public market data
>
> Hello,
>
> I am an individual developing a private, self-operated quantitative model whose signals I would use solely for my own trading. Please confirm whether this falls within permitted personal use, or whether it requires market-data permission, and if so whether you would grant it for:
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

### M3: Databento

> Subject: Licensing question before purchase: historical CME/COMEX data for private research and own-account trading
>
> Hello,
>
> Before purchasing, I would like to confirm licensing for GLBX.MDP3 data: GC and MGC (and possibly BTC and MBT) trades, BBO/L1, OHLCV, definitions, and statistics. I may also want live data on the Standard plan.
>
> My intended use: I am an individual building a private quantitative model for my own trading. I would store the data privately in my own Google Cloud storage, use it for research and backtesting, train and validate machine-learning models, retain derived features and model weights, and use the model's output in automated trading of my own account. I will not distribute any data externally.
>
> 1. Does pay-as-you-go historical data permit this use, and is it classified as personal or commercial use?
> 2. Does CME's June 2026 licence update, which restricts machine-learning use of "Information", apply to historical data bought from Databento for internal non-display use like mine?
> 3. On the Standard plan, does "license fees included" cover automated (non-display) proprietary use by an individual trading their own account, and which subscriber category applies?
> 4. Can I keep historical data and derived models after my subscription ends?
>
> Thank you.

**Signup questionnaire.**
- Answer it truthfully: internal use, no redistribution, and likely non-display use (automated processing).
- Professional vs non-professional status follows CME's definition. If unsure, ask rather than choosing the cheaper category.
- Run the cost estimator for the exact symbols, schemas, and dates before buying anything.

### M4: CF Benchmarks (via <https://www.cfbenchmarks.com/about/contact>)

> Subject: Licence quote request: BRTI historical and real-time data for private research and own-account trading
>
> Hello,
>
> I am an individual developing a private quantitative model for my own trading on event contracts that settle on the CME CF Bitcoin Real Time Index. Please send a quote and licence terms for:
> - historical BRTI values at the finest available granularity, with your restatement policy or first-published vintages;
> - a point-in-time constituent history;
> - optionally, real-time BRTI.
>
> Intended use: private storage in my own cloud, research, backtesting, machine-learning model training, and own-account trading. No redistribution. If access through an authorized channel (for example Kalshi's data entitlement or CME DataMine) is the better route for this use, please say so.
>
> Thank you.

### M5: Polymarket (only if clarification is needed for scope)

> Subject: Does an individual's own-account research project count as a "Capital Markets Entity"?
>
> Hello,
>
> I am an individual, not a firm, developing a private quantitative model for my own trading. I would retrieve public Polymarket data (Gamma, Data API, CLOB order books, and on-chain fills and resolutions), store it privately in my own cloud storage, backtest, train machine-learning models, and use the output solely for my own trading. I will not redistribute data.
>
> Am I a "Capital Markets Entity" that must consume data in consultation with Polymarket and ICE? If not, are these uses permitted under your terms? If so, what is the licensing route?
>
> [For Polymarket US: which terms govern automated retrieval and storage of public gateway and WebSocket data for my own trading research?]
>
> Thank you.

### Optional, not queued: Coinbase (`marketdata@coinbase.com`)

> Subject: Written consent request: Market Data Terms, machine-learning use for own-account trading
>
> Your Market Data Terms require prior written consent to use market data to train or validate machine-learning models. I am an individual building a private model for my own trading, with private cloud storage, no redistribution, and output used solely for my own trading. Would Coinbase grant consent, or is a licence required, and at what cost?

## 7. Accounts and API keys you would eventually need

| Account | When | Notes |
|---|---|---|
| Kalshi member account + API key | Prospective capture and reference channels | The key can also trade. Keep it only in GCP Secret Manager, never on the Chromebook or in an agent session |
| Databento account + API key | Tier 1 (gold) | Card at signup; complete the licence questionnaire truthfully |
| GCP billing account | CLOUD-0 | Upgrade beyond the free trial |
| CF Benchmarks licence (or Kalshi entitlement) | Only if the BRTI quote is economical | — |
| Tardis, Pyth | Tier 2 only | — |
| Polymarket credentials | Only if Polymarket is in scope | — |
| Kraken | Not needed for public data | L3 needs a key (optional) |

## 8. Current state and remaining blockers

**State.**
- Cloud architecture research is complete.
- Source procurement research is complete, and this packet exists.
- No bulk market data has been acquired. No vendor purchase has been made. No cloud resource has been provisioned.
- No `T0` exists, and no protected holdout has been opened.

**Remaining blockers.**
1. Kalshi's written clarification (M1). Kalshi data is the critical path.
2. Kraken's answer (M2).
3. Databento's licence classification answers (M3), and the estimator result for our exact pull.
4. CF Benchmarks quote (M4), which decides whether licensed BRTI is affordable.
5. DET-1 and DET-2: you download the Kalshi contract terms.
6. Owner cloud decisions and per-source approvals (decision record D-B09-10 to D-B09-16). Data cannot land anywhere safe before CLOUD-1/2.

---

## OWNER LINKS — ACTION REQUIRED

**Kalshi**
- Developer Agreement (PDF): <https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf>
- Website Data Terms (PDF): <https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf>
- Terms of Service: <https://kalshi.com/terms>
- API documentation: <https://docs.kalshi.com/>
- Help / contact: <https://help.kalshi.com/en/articles/13823855-contact-kalshi-support>
- Contact: `institutional@kalshi.com`, cc `support@kalshi.com`

**Kraken**
- Historical trade archive: <https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales->
- OHLCVT archive: <https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data>
- API docs: <https://docs.kraken.com/exchange/guides/general/historical-data>
- Legal: <https://www.kraken.com/legal>
- Contact: `marketdata@kraken.com`

**Databento**
- Pricing: <https://databento.com/pricing>
- CME catalog and plans: <https://databento.com/catalog/cme/GLBX.MDP3>
- Signup: <https://databento.com/signup>
- Cost estimator API: <https://databento.com/docs/api-reference-historical/metadata/metadata-get-cost>
- Legal: <https://databento.com/legal>
- Contact: `support@databento.com`

**CF Benchmarks (BRTI)**
- BRTI: <https://www.cfbenchmarks.com/data/indices/BRTI>
- Contact form: <https://www.cfbenchmarks.com/about/contact>

**Pyth**
- Products: <https://app.pyth.com/products>
- Plans: <https://app.pyth.com/plans>

**Tardis.dev**
- Home and pricing: <https://tardis.dev/>
- Historical data details: <https://docs.tardis.dev/historical-data-details>

**Polymarket** (only if in scope)
- Institutional data statement: <https://institutional.polymarket.com/>
- Terms: <https://polymarket.com/tos>
- API docs: <https://docs.polymarket.com/>
- Polymarket US contact: <https://www.polymarketexchange.com/contact.html>
- Contacts: `data-licensing@polymarket.com`, `data@polymarket.us`

**CME DataMine** (fallback only)
- DataMine: <https://www.cmegroup.com/datamine.html>
- Contact: `CMEDataSales@cmegroup.com`

**Coinbase** (DROP for now)
- Market Data Terms: <https://www.coinbase.com/legal/market_data>
- Data Marketplace: <https://help.coinbase.com/en/data-marketplace/getting-started/coinbase-data-marketplace>
