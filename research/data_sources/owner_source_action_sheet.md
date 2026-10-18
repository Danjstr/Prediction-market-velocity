# PMV data sources: owner action sheet and procurement packet (B09, 2026-10-18)

**What this is.** A one-stop list of the data PMV can get, the data it might get, what needs written permission or a licence, what costs money and how much, and where you go to get it.
- The full 100-row research inventory is `research/data_sources/master_source_inventory.md`. This sheet is the owner-facing summary of it.
- **Nothing here has been bought, signed, or downloaded.** Acquisition still needs:
  - your per-source approval (A-1 to A-6, `docs/external_access.md` §2);
  - the cloud pipeline (`research/cloud/pmv_cloud_architecture_review.md` §12).

**How to read the evidence column.**

| Tag | Meaning |
|---|---|
| **VERIFIED (fetched)** | The official page was fetched on 2026-10-18 and summarized by a tool. It is still not verbatim, so check the wording before relying on it for a licence decision |
| **OWNER_VERIFY** | The official page is blocked to agents, so the fact comes from a search summary. The exact official URL is given; please open it in your browser |
| **Git** | From documentation snapshots already in the repository (Kalshi 2026-10-15, Polymarket 2026-10-16) |

Every price and licence statement not marked VERIFIED is OWNER_VERIFY.

**Status categories (one per source).**

| Status | Meaning |
|---|---|
| FREE_TECHNICALLY_AVAILABLE | Free to obtain; PMV's ML/trading use is **not** yet cleared |
| FREE_AND_USE_CLEARED | Free, and the intended use is affirmatively permitted |
| NEEDS_WRITTEN_PERMISSION | Obtainable, but PMV needs the provider's consent for its use |
| NEEDS_LICENCE_QUOTE | A licence or negotiated terms are needed; no public price |
| PAID_SELF_SERVICE | Public price; you can sign up without negotiating |
| FREE_SAMPLE_ONLY | Only a free sample exists; full history is paid or licence-bound |
| TECHNICALLY_UNAVAILABLE | The needed data does not exist or cannot be obtained |
| REJECTED | Terms clearly prohibit the use, with no practical licensed path |

---

## 1. Headline answers

1. **What can we get for $0, once permissions clear?** Kalshi historical trades, candles, settlements, and metadata; Kraken's full BTC trade and OHLCV history; Kraken live order books; CFTC rule filings.
   - All are technically free.
   - **None is use-cleared for PMV's ML and trading work yet.**
   - Only the CFTC filings are FREE_AND_USE_CLEARED, and they are rule text, not market data.
2. **What needs written permission?**
   - **Kalshi** (all API surfaces). Its Developer Agreement reportedly limits API use and storage to "facilitating your own trading on Kalshi". Whether research, backtesting, and model training count is for Kalshi to say.
   - **Kraken** (non-personal commercial use of public data).
   - **Polymarket** (if in scope).
   - **Coinbase** (its terms reportedly bar ML training without written consent).
3. **What needs a licence quote?** CF Benchmarks BRTI; CME DataMine; Kalshi's BRTI channel entitlement; the Coinbase Data Marketplace.
4. **What can you simply buy?**
   - **Databento:** $125 free credit, about $0.50+/GB historical, Standard plan $199/month.
   - **Tardis:** Solo Spot $700/month.
   - **Pyth Pro Metals:** $2,500/month (OWNER_VERIFY); a possible $99/month package also exists.
   - **Kalshi Pyth gold channel:** $1,000/month.
   - **CoinAPI:** about $70 for Kraken's full trade history.
   - **Marketlens:** $39/month.
   - **Chainlink Data Streams:** about $150/month per stream.
5. **Is a $20,000–$35,000 CME purchase necessary? No.**
   - CME publishes no DataMine price list.
   - The $35,220 figure on CME's fee list is the annual **historical distribution licence**, for redistributing CME data to others. PMV does not redistribute.
   - Databento sells the same CME/COMEX exchange data (GC, MGC, BTC, MBT) for tens to low hundreds of dollars at PMV's initial scale.

## 2. Owner core matrix

The matrix is split into two tables keyed by row ID, so that every required column fits. Priority: **0** = act now, free; **1** = cheap, high value; **2** = only if research justifies it; **3** = do not buy now; **DROP**.

### 2A. What each source is

| ID | Provider / data product | Asset | Role in PMV | What data we get | History start / depth | Granularity | Order book | Live? | Cloud-direct? |
|---|---|---|---|---|---|---|---|---|---|
| K1 | Kalshi REST API: historical tier | BTC, gold PMs | Official labels, market prices, trade flow | Trades, 1/60/1440-minute candles with bid/ask OHLC, settlement values, market objects | Archive back to about 2021-06; live/historical cutoff lags about 2–3 months (OWNER_VERIFY) | Trade print; 1 minute | None | No | Yes (untested from GCP) |
| K2 | Kalshi REST metadata, contract terms, CFTC filings | BTC, gold PMs | Contract rules, fees, settlement source, universe | Series, events, markets, fee history, rulebook text, contract-terms PDFs | All series and events (Git); filings from 2024 | Per record | — | Current state | Yes |
| K3 | Kalshi WebSocket | BTC, gold PMs | **Prospective capture**: order books with receipt time; the only future holdout source | Full book (snapshot + delta), trades, lifecycle, settlement | Live only | Per message | Full L2 | Yes | Yes (cloud VM) |
| K4 | Kalshi CF Benchmarks channel and REST passthrough | BTC reference | BRTI, the index Kalshi BTC contracts settle on | BRTI values; 60 s window averages | Passthrough depth UNKNOWN; WebSocket live only | Tick / per update | — | Yes | Yes |
| K5 | Kalshi `pyth_value` channel | Gold reference | The Pyth gold values Kalshi observes | Values with source and receipt timestamps | Live only | Per update | — | Yes | Yes |
| P1 | Polymarket Gamma API | BTC PMs (gold daily only) | Contract metadata | Markets, token IDs, fees, ticks, resolution source | All markets (current state) | Per record | — | Current | Yes |
| P2 | Polymarket Data API v2 | BTC PMs | Trade and resolution cross-check | Indexed on-chain fills, resolutions | Three-year window per market | Per fill (block seconds) | None | — | Yes |
| P3 | Polymarket CLOB (book REST and market WebSocket) | BTC PMs | Prospective Polymarket books | L2, BBO, last trade, tick changes | Live only | Per message | Full L2 | Yes | Yes |
| P4 | Polymarket on-chain (Polygon RPC; BigQuery Polygon datasets) | BTC PMs | Canonical fills and payouts | `OrderFilled` and resolution events | From 2022-11 (BigQuery coverage UNKNOWN) | Per event | None | Near-live | Yes (BigQuery is native to GCP) |
| P5 | Polymarket US (public gateway REST; key-gated WebSocket) | BTC PMs | The tradable Polymarket venue for US persons | Book, BBO, settlement, price history; no public trade tape | Short / UNKNOWN | Per call | L2 (current) | Yes | Yes |
| B1 | Kraken full trade archive ("time and sales") | BTC | **Best free BTC trade tape**; BRTI-proxy test | Every public trade, every pair | From first trade to 2026-09-30, quarterly updates (OWNER_VERIFY) | Trade | None | No | Yes |
| B2 | Kraken OHLCVT archive | BTC | Bars with trade counts | OHLCV + trade count at 1–1440 minutes | To 2026-06-30 (OWNER_VERIFY) | 1 minute+ | None | No | Yes |
| B3 | Kraken REST and WebSocket v2 | BTC | Prospective BTC books; recent trades | Live L2 (checksummed), trades; L3 with key | Live / recent | Per message | L2 (L3 with key) | Yes | Yes |
| B4 | Tardis.dev Spot plan (Kraken, Bitstamp, Gemini, Crypto.com, Bullish) | BTC | Historical sub-minute spot order books | Trades, quotes, incremental L2, snapshots; exchange and receipt timestamps | 2019 onward; depth sold depends on billing | Per message, µs | L2 (L3 for some venues) | No (historical) | Yes (HTTPS pulls) |
| B5 | Coinbase public API (REST, WebSocket) | BTC | Largest USD BRTI constituent | Trades, candles, live L2/L3 | Trades by cursor; live | Trade / message | L2/L3 live | Yes | Yes |
| B6 | Coinbase Data Marketplace | BTC | Licensed Coinbase history | Tick trades, OHLCV, EOD (per help page) | UNKNOWN | Tick | UNKNOWN | — | UNKNOWN |
| B7 | Databento CME Bitcoin futures (GLBX.MDP3: BTC, MBT) | BTC futures | Regulated futures lead-lag and basis | Trades, TBBO, MBP-1, MBP-10, MBO, OHLCV, settlements | CME data from 2010; MBO from 2017-05-21 | Event, ns | Up to MBO | Yes (Standard plan) | Yes (API key) |
| B8 | CME DataMine Bitcoin futures | BTC futures | Same exchange data as B7 | T&S, depth, MBO, settlements | T&S from contract start | Tick, ns | Up to MBO | No | Yes (S3/SFTP) |
| B9 | CF Benchmarks BRTI (direct) | BTC reference | Kalshi's BTC settlement index | BRTI values | UNKNOWN | 200 ms / 1 s | — | Yes | UNKNOWN |
| B10 | CME DataMine CRYPTOCURRENCY (CME CF BRR/BRTI) | BTC reference | BRTI history route | BRTI per second | From 2016-11/12 (OWNER_VERIFY) | ~1 s | — | No | Yes |
| B11 | Bitstamp, Gemini, Bullish, Crypto.com public APIs | BTC | Other BRTI constituents (proxy fidelity) | Trades, live L2 | Short native history | Trade / message | L2 live | Yes | Yes |
| G1 | Databento COMEX GC, MGC, 1OZ (GLBX.MDP3) | Gold futures | **Main gold dynamics source** | Trades, TBBO, MBP-1, BBO-1s, OHLCV-1s/1m, definitions, settlements (statistics), status | 2010; reliable L1 from 2017-05-21 | Event, ns; 1 s bars | L1 (L2/L3 available) | Yes (Standard plan) | Yes (API key) |
| G2 | Databento live CME (Standard plan) | Gold futures | Prospective gold capture with receipt time | Live trades, L1/L2 | Live | Per message | L1–L3 | Yes | Yes |
| G3 | CME DataMine GC/MGC | Gold futures | Same exchange data as G1 | T&S, BBO, depth, MBO, settlements | T&S 1982; BBO 1999; depth 2005 (OWNER_VERIFY) | Tick | Up to MBO | No | Yes |
| G4 | Pyth Pro Metals (`Metal.XAU/USD`, `Metal.Index.GOLD/USD`) | Gold reference | The reference Kalshi gold contracts reportedly settle on | Candles from 1 minute; 200 ms price ranges | GOLD index from about 2026-06; XAU start UNKNOWN | 200 ms / 1 min | — | Yes | Yes (API key) |
| G5 | Pyth $99 package (offered to Polymarket users) | Gold reference | Possibly a cheap route to the gold reference | Reportedly XAU, XAG, WTI, equities | UNKNOWN | UNKNOWN | — | Yes | UNKNOWN |
| G6 | Kalshi gold contract terms (settlement reference determination) | Gold PMs | Which Pyth feed and candle Kalshi uses (DET-1) | Rule text | — | — | — | — | n/a |
| O1 | CoinAPI flat files | BTC | Backup source for Kraken trades or LMAX | Trades, quotes, book updates | Per exchange | Tick | L2 | No | Yes (S3-compatible) |
| O2 | Marketlens | Polymarket | Polymarket book history | L2 snapshots + price changes | From 2026-03 | 60 s / ms | L2 | — | Yes |
| O3 | Chainlink Data Streams | BTC reference (Polymarket) | Polymarket BTC settlement source | Signed reports, 60 s TWAP | Retention UNKNOWN | Per report | — | Yes | Yes |

### 2B. Access, cost, and action

| ID | Account? | API key? | Public price | Projected PMV cost | Licence / terms issue | Current status | Follow-up URL | Contact | What you must ask | Best substitute | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|
| K1 | Technically no; Kalshi membership expected (Developer Agreement §4, OWNER_VERIFY) | No | Free | $0 | Developer Agreement §3/§3.1 reportedly limits API use and storage to "facilitating your own trading on Kalshi" (OWNER_VERIFY). The website Data Terms appear to define Kalshi Data as website content and are **not** assumed to govern the API | NEEDS_WRITTEN_PERMISSION | <https://kalshi.com/developer-agreement> | `institutional@kalshi.com`, cc `support@kalshi.com`, from your member-account email | Message M1 (§6) | Third-party copies carry the same upstream problem; none independent | **0** |
| K2 | No | No | Free | $0 | Contract PDFs: owner download (agents cannot fetch the bucket). CFTC filings: public record | FREE_TECHNICALLY_AVAILABLE (filings: FREE_AND_USE_CLEARED) | <https://docs.kalshi.com/> ; <https://www.cftc.gov/> | — | Download the KXBTC15M and KXGOLD15M contract terms; resolves DET-1 (gold feed) and DET-2 (BTC rulebook) | — | **0** |
| K3 | Yes (KYC member) | **Yes, always** (Git) | Free | $0 + cloud VM (~$50–70/month per collector pair) | As K1; the key can also trade, so it is handled as a trading-grade secret | NEEDS_WRITTEN_PERMISSION | <https://kalshi.com/developer-agreement> | as K1 | Included in M1 (live capture and storage) | None | **0** (after permission) |
| K4 | Yes | Yes + entitlement | UNKNOWN | UNKNOWN | Kalshi terms + CF Benchmarks licence; storage and ML rights unknown | NEEDS_LICENCE_QUOTE | <https://docs.kalshi.com/> (CF Benchmarks passthrough page) | `institutional@kalshi.com` | Entitlement price, history depth, and storage/ML rights (in M1) | B10, B9 | 1 (ask now) |
| K5 | Yes | Yes + entitlement | **$1,000/month; first 7 days free** (Git) | $0 until DET-1 resolved; then $1,000/month if bought | Kalshi + Pyth terms | NEEDS_WRITTEN_PERMISSION | as K1 | as K1 | Covered by M1 | G5, G4 | 2 |
| P1–P3 | No | No | Free | $0 | Polymarket says "Capital Markets Entities" must use data in consultation with Polymarket/ICE. Whether an individual's own-account algorithmic project is one is unclear. US persons are excluded from the international site | NEEDS_WRITTEN_PERMISSION | <https://institutional.polymarket.com/> ; <https://polymarket.com/tos> | `data-licensing@polymarket.com` | Message M4 (§6), only if Polymarket is in scope | P5 for US persons | 2 (scope decision first) |
| P4 | GCP project (vault identity) or RPC provider | RPC key | BigQuery query bytes; RPC provider tiers | <$10 initially (I) | Same Polymarket/ICE statement covers on-chain derived data | NEEDS_WRITTEN_PERMISSION | as P1 | as P1 | M4 | P2 | 2 |
| P5 | For WebSocket (KYC) | For WebSocket | Free | $0 | Rulebook bars redistribution; reported Terms of Use limit use to "personal, non-commercial use in connection with your trading" and bar bulk downloads (OWNER_VERIFY) | NEEDS_WRITTEN_PERMISSION | <https://polymarketexchange.com/files/legal/latest/rulebook> ; <https://www.polymarketexchange.com/contact.html> | `data@polymarket.us` | M4 (US version) | — | 2 |
| B1 | No | No | Free | $0 | Kraken API notice: prior permission for "any non-personal commercial use of data from publicly accessible endpoints" (OWNER_VERIFY; on the legacy docs page only). Current docs also say Kraken provides no bulk dump, which conflicts with the support articles | NEEDS_WRITTEN_PERMISSION | <https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-> | `marketdata@kraken.com` (OWNER_VERIFY) | Message M2 (§6) | O1 CoinAPI (~$64–74 for full Kraken trades, OWNER_VERIFY) | **0** |
| B2 | No | No | Free | $0 | As B1 | NEEDS_WRITTEN_PERMISSION | <https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data> | as B1 | In M2 | Derive from B1 | 0 |
| B3 | No (L3: yes) | No (L3: yes) | Free | $0 + cloud VM | As B1 | NEEDS_WRITTEN_PERMISSION | <https://docs.kraken.com/exchange/guides/general/historical-data> (VERIFIED) | as B1 | In M2 (prospective WebSocket use) | B4 | 0 |
| B4 | Yes | Yes (valid while subscribed) | Solo Spot **$700/month**; Academic $350 (eligibility); Pro $1,000; Business $3,000 (OWNER_VERIFY). Quarterly or yearly billing gives more history | LOW $700 (one month, depth UNKNOWN) / EXPECTED $2,100 (one quarter) / HIGH $8,400 (one year, about 4 years of history) | Licence reportedly allows internal trading models and keeps downloaded data perpetually (OWNER_VERIFY). Coinbase data excluded from Spot | PAID_SELF_SERVICE | <https://tardis.dev/#pricing> ; <https://docs.tardis.dev/faq/billing-and-subscriptions> | `contact@tardis.dev` | Exact history depth per billing period; confirm licence clauses 9.4/9.5 | O1 (per-exchange-day) | 2 |
| B5 | No | No | Free | $0 | Market Data Terms reportedly bar using data to "develop, train … validate … any … machine learning model" without prior express written consent (OWNER_VERIFY). Not usable for PMV ML training without consent | NEEDS_WRITTEN_PERMISSION | <https://www.coinbase.com/legal/market_data> | `marketdata@coinbase.com` | Message M5 (optional) | B1 + B11 (Kraken plus other constituents) | **DROP for now** |
| B6 | Yes | — | CONTACT SALES / UNKNOWN | UNKNOWN | Licence on purchase | NEEDS_LICENCE_QUOTE | <https://help.coinbase.com/en/data-marketplace/getting-started/coinbase-data-marketplace> | `marketdata@coinbase.com` | Only if B5 consent is refused and Coinbase proves necessary | B1 | **DROP for now** |
| B7 | Yes | Yes | Historical usage-based from $0.50/GB (varies by schema); $125 new-account credit (6 months). Standard $199/month (includes last 12 months of L1 and live CME) (VERIFIED) | 2 years trades + TBBO + OHLCV-1s + definitions/statistics: about 3/8/17 GB → about **$2 / $25 / $50** (estimate) | **OWNER_VERIFY:** the catalog table reportedly marks usage-based as "Personal use ✓ / Commercial use ✗" while Standard includes "Commercial use". CME DS-45 ML clause scope unclear | PAID_SELF_SERVICE | <https://databento.com/pricing> ; <https://databento.com/catalog/cme/GLBX.MDP3> | `support@databento.com` | Message M3 (§6) | B8 | 1 (optional for BTC) |
| B8 | CME login | — | **CONTACT SALES / UNKNOWN** (catalog prices only after login) | UNKNOWN | ILA/DDLA; DS-45 | NEEDS_LICENCE_QUOTE | <https://www.cmegroup.com/datamine.html> | `CMEDataSales@cmegroup.com` | Only if Databento cannot serve | B7 | **3** |
| B9 | Yes | Yes | **CONTACT SALES / UNKNOWN** | UNKNOWN | Licence required for any use; restatement policy unknown | NEEDS_LICENCE_QUOTE | <https://www.cfbenchmarks.com/data/indices/BRTI> | `licensing@cfbenchmarks.com` | Message M6 (§6) | K4, B10 | 2 |
| B10 | CME login | — | **CONTACT SALES / UNKNOWN** | UNKNOWN | MDLA + derived-data licence; DS-45 | NEEDS_LICENCE_QUOTE | <https://www.cmegroup.com/datamine.html> | `CMEDataSales@cmegroup.com` | Price for CRYPTOCURRENCY dataset history; ML and internal-use scope | K4, B9 | 2 |
| B11 | No | No | Free | $0 + cloud | Bitstamp: signed Data License Agreement for commercial use (OWNER_VERIFY); others unread | NEEDS_WRITTEN_PERMISSION | (per exchange) | Bitstamp: `partners@bitstamp.net` (OWNER_VERIFY) | Later, only if the BRTI-proxy test needs them | B4 | 3 |
| G1 | Yes | Yes | As B7 | 2 years GC+MGC trades + TBBO + OHLCV-1s + definitions/statistics: about 10/27/53 GB → about **$5 / $40 / $160** (estimate). Adding 2 years of MBP-1 would be about 100–800 GB, beyond the credit. Alternative: **one month of Standard ($199)** includes the last 12 months of L1, with older data bought usage-based | As B7 | PAID_SELF_SERVICE | <https://databento.com/pricing> ; <https://databento.com/signup> | `support@databento.com` | M3 | G3 | **1** |
| G2 | Yes | Yes | Standard **$199/month** (live CME, licence fees included) (VERIFIED); professional and non-display coverage OWNER_VERIFY | $199/month while capturing gold | Live CME licence; DS-45 | PAID_SELF_SERVICE | <https://databento.com/catalog/cme/GLBX.MDP3> | `support@databento.com` | Does Standard cover an individual's automated non-display trading research? (M3) | — | 2 |
| G3 | CME login | — | **CONTACT SALES / UNKNOWN** | UNKNOWN | ILA/DDLA; DS-45 | NEEDS_LICENCE_QUOTE | <https://www.cmegroup.com/datamine.html> | `CMEDataSales@cmegroup.com` | Not needed while Databento serves | G1 | **3** |
| G4 | Yes | Yes | Metals bundle **$2,500/month**; free trial key from Pyth Terminal (OWNER_VERIFY) | $2,500 for one month, after DET-1 | No data licence seen; index methodology not obtained | PAID_SELF_SERVICE | <https://www.pyth.network/pricing> | Pyth contact via the pricing page | Which feed Kalshi uses (DET-1 first); history start; storage/ML terms | G5, K5 | 2 |
| G5 | Yes | Yes | **$99/month, first month free** (OWNER_VERIFY) | $0–$99 | Feeds, history, and licence UNKNOWN; offered via Polymarket's docs | PAID_SELF_SERVICE (OWNER_VERIFY) | <https://www.pyth.network/pricing> | Form linked from Polymarket's docs | Does it include the feed Kalshi settles on, with history, for private research? | G4 | 2 (check first) |
| G6 | No | No | Free | $0 | — | FREE_TECHNICALLY_AVAILABLE | as K2 | — | Download the KXGOLD15M terms | — | **0** |
| O1 | Yes | Yes | Pay-as-you-go $1/credit; $25 free credit; trades about $6–24/GiB (OWNER_VERIFY) | About $64–74 for Kraken's full trade history (OWNER_VERIFY) | Internal ML reportedly allowed; no redistribution | PAID_SELF_SERVICE | <https://www.coinapi.io/products/flat-files/pricing> | via site | Only if B1 is refused | B1 | 1 (fallback) |
| O2 | Yes | Yes | Pro $39/month; Scale $199/month (OWNER_VERIFY) | $39–$117 | Licence UNKNOWN | PAID_SELF_SERVICE | <https://marketlens.trade/> | via site | Only if Polymarket in scope | P3 capture | 2 |
| O3 | Yes | Yes | About $150/month per stream (OWNER_VERIFY) | $150/month | ToS accepted at key creation; unread | PAID_SELF_SERVICE | <https://docs.chain.link/data-streams/billing> | via portal | Only if Polymarket BTC in scope; history retention | Polymarket reference feed (credentials) | 2 |

### 2C. Dropped or rejected

| Source | Status | Why drop |
|---|---|---|
| Kalshi website pages | NOT USED | Live display; API data is the right surface |
| Kraken Futures | FREE_TECHNICALLY_AVAILABLE | Perpetuals are not BRTI inputs; low value |
| Offshore perpetuals (Binance, Bybit, OKX, Deribit) and DVOL | NEEDS_WRITTEN_PERMISSION | US eligibility and geo restrictions; marginal value |
| Binance Vision | **REJECTED** | CC BY-NC-SA; prohibits live trading use (verified in Git) |
| Kaiko, Coin Metrics, CoinDesk Data | NEEDS_LICENCE_QUOTE | Enterprise pricing (Kaiko L2 from about $2.5k/month, OWNER_VERIFY); nothing beyond Tardis/CoinAPI for PMV |
| LMAX Digital (via CoinAPI +$500/month) | PAID_SELF_SERVICE | BRTI fidelity only |
| OANDA | NEEDS_WRITTEN_PERMISSION | XAU restricted for US accounts (OWNER_VERIFY); COMEX via Databento is better |
| Dukascopy | NEEDS_WRITTEN_PERMISSION | Reportedly personal non-commercial, "not to construct a database" (OWNER_VERIFY); CFD quotes only |
| Goldsky, Bitquery, Dune, Allium | PAID / quote | BigQuery Polygon or RPC covers on-chain data more cheaply |
| Oddpool | PAID_SELF_SERVICE | PMV's own Kalshi capture is better |
| CME DataMine (all products) | NEEDS_LICENCE_QUOTE | Databento supplies the same CME/COMEX exchange data far more cheaply |
| Pyth Terminal free tier | TECHNICALLY_UNAVAILABLE | No API |
| LSEG, Bloomberg, Barchart, Tick Data, Massive, Twelve Data, FirstRate, Kibot | Paid | Lower quality or enterprise cost; Databento is better |

**Coinbase recommendation: DROP for now.** Getting Coinbase consent costs owner time and may be refused. Kraken plus the other constituents, plus a licensed BRTI series, cover the same need. Reconsider only if the free BRTI-proxy test (Kraken-based) shows material mismatches near the strike that Coinbase would fix.

## 3. Procurement tiers

| Tier | What | Cost |
|---|---|---|
| **0: get free / ask permission now** | Send M1 (Kalshi), M2 (Kraken), M3 (Databento/CME). Download the Kalshi contract terms (K2, G6). Ask Kalshi for the BRTI entitlement price (in M1). Optionally M6 (CF Benchmarks quote). M4 (Polymarket) only if Polymarket is in scope | $0 |
| **1: cheap and high value** | Databento GC/MGC (and optionally BTC/MBT) L1 history inside the $125 credit, or one month of Standard ($199) to cover the last 12 months of L1 (after the M3 answer). CoinAPI Kraken trades (~$70) only if Kraken refuses B1 | $0–$200 one-time |
| **2: only if initial research justifies it** | Tardis Solo Spot (from $700/month; one quarter about $2,100). Kalshi `pyth_value` ($1,000/month) or Pyth Metals ($2,500/month) or the $99 package, after DET-1. One BRTI history licence (quote). Databento MBO/MBP-10 or live Standard for gold capture ($199/month). Marketlens, Chainlink, BigQuery Polygon only if Polymarket is in scope | Hundreds to a few thousand dollars |
| **3: do not buy now** | CME DataMine (any product), Coinbase Data Marketplace, Kaiko, Coin Metrics, CoinDesk, LMAX, enterprise gold vendors, Goldsky, Bitquery, Oddpool, OANDA, Dukascopy | — |

## 4. Datasets by ambition

| | Minimum viable | Better | Ideal / expensive |
|---|---|---|---|
| **Sources** | K1 + K2 Kalshi history and rules; B1/B2 Kraken archive; G1 Databento GC/MGC L1 history (and B7 BTC futures if wanted) | Minimum, plus prospective capture: K3 Kalshi WebSocket, K4 BRTI channel, B3 Kraken WebSocket. One month Databento Standard for 12 months of L1; one licensed BRTI history route; K5 or G5 gold reference after DET-1 | Better, plus Tardis Solo Spot (1 year), Pyth Metals history, Databento MBO/MBP-10, the Polymarket stack (P1–P4, O2, O3) if in scope |
| **Signals available** | Late-window Kalshi prices (1-minute candle bid/ask), trade flow, official settlements and fees; BTC spot trade velocity (BRTI proxy); gold futures 1 s dynamics and settlements | Plus real Kalshi order books with PMV receipt times; actual BRTI; Kalshi's gold reference; execution-realistic data; future protected holdout | Plus historical spot order books; full gold depth; cross-venue Polymarket comparison |
| **Important missing information** | No order books anywhere; BRTI only approximated; no gold reference; no receipt-time data; Kalshi gold has about 2.5 months of history | Historical spot books; long gold reference history | Little beyond what does not exist (historical Kalshi books) |
| **One-time cost** | **$0–$160** (Databento, likely inside the $125 credit) | **About $200–$400** plus a BRTI quote (UNKNOWN) | **About $8,000–$10,000** plus quotes (Tardis one year $8,400) |
| **Monthly cost** | Cloud about **$10–20** | Cloud about $180 + Databento live $199 if capturing gold + $99–$1,000 gold reference = **about $380–$1,400** | **About $3,000–$4,000+** (Pyth Metals $2,500, Databento, Polymarket feeds, cloud) |
| **Licensing prerequisites** | Kalshi written answer (M1); Kraken permission (M2); Databento terms and the usage-based "commercial use" and DS-45 questions (M3) | Plus Kalshi capture and credential approvals; BRTI licence; Pyth/Kalshi reference terms | Plus Tardis licence read; Pyth licence; Polymarket clarification (M4) |

The minimum viable dataset is enough for the proposed M-0 go/no-go test (decision record D-B09-18). Spending beyond it should wait for that result.

## 5. Accounts and API keys you would eventually need

| Account | When | Notes |
|---|---|---|
| Kalshi member account + API key | Capture (K3), BRTI channel (K4), gold channel (K5) | The key can also trade: store it only in GCP Secret Manager. Never put it on the Chromebook or in an agent session |
| Databento account + API key | Tier 1 | Card at signup; complete the licence questionnaire truthfully (§6, M3) |
| GCP billing account | CLOUD-0 | Upgrade beyond the free trial |
| Tardis account + API key | Tier 2 only | Key valid while subscribed; download within the paid period |
| Pyth Pro key | Tier 2 only | After DET-1 |
| CF Benchmarks or CME DataMine login | Only for a BRTI licence | Whichever route the quotes favour |
| Polymarket (CLOB credentials / Polymarket US KYC) | Only if Polymarket is in scope | After M4 and F-16 |
| Kraken | Not needed for public data | L3 needs a key (optional) |

## 6. Ready-to-send messages

Send from your own email (for Kalshi, the email on your member account). These contain no account numbers. Adjust the wording freely; agents never send them.

### M1: Kalshi (to `institutional@kalshi.com`, cc `support@kalshi.com`)

> Subject: Permission request: private research use of Kalshi API data for my own trading
>
> Hello,
>
> I am an individual Kalshi member developing a private, self-operated quantitative model to support my own trading on Kalshi. I would like written confirmation of whether the following uses of data obtained through Kalshi's REST API (including the historical endpoints and market, event, series, and settlement metadata) and WebSocket API are permitted under the Developer Agreement and any other applicable Kalshi terms:
>
> 1. Automated retrieval through the API, within published rate limits.
> 2. Storing historical API data privately in my own cloud storage (Google Cloud), including encrypted backups.
> 3. Private quantitative research and backtesting.
> 4. Statistical modelling, and training and validating machine-learning models.
> 5. Creating and retaining derived features and model parameters (weights), including after my API access ends.
> 6. Using the resulting model's output solely for my own trading on Kalshi.
> 7. Capturing WebSocket market data prospectively and storing it for the same purposes.
>
> I will not redistribute, publish, sell, or share raw Kalshi data or derived datasets with any third party.
>
> Could you also tell me:
> - whether these uses fall within "facilitating your own trading on Kalshi" under the Developer Agreement, or need separate written authorization;
> - whether the Kalshi Data Terms of Use apply to API data, or only to website content, and which document governs if they differ;
> - the price, history depth, and permitted uses (including storage and model training) of the CF Benchmarks data entitlement (REST passthrough and WebSocket channel), and of the Pyth gold channel.
>
> Thank you.

### M2: Kraken (to `marketdata@kraken.com`)

> Subject: Permission request: private quantitative research on Kraken public market data
>
> Hello,
>
> I am an individual developing a private, self-operated quantitative model whose signals I would use solely for my own trading. Your API notice says prior permission is needed for non-personal commercial use of public market data. Could you confirm in writing whether the following are permitted:
>
> 1. Downloading your historical public trade ("time and sales") and OHLCVT archives.
> 2. Storing them privately in my own Google Cloud storage, with backups.
> 3. Constructing features from them.
> 4. Training and validating machine-learning models on them.
> 5. Retaining the derived model artifacts.
> 6. Consuming your public WebSocket market data prospectively, and storing it for the same purposes.
> 7. Using the resulting signals solely for my own trading.
>
> I will not redistribute any raw data. Please also confirm the current download location of the full trade archive. Your developer documentation says Kraken does not provide a bulk historical data dump, while your support articles describe the archive.
>
> Thank you.

### M3: Databento (to `support@databento.com`; questions on CME licensing)

> Subject: Licensing question before purchase: historical CME/COMEX data for private research and own-account trading
>
> Hello,
>
> Before purchasing, I would like to confirm the licensing for historical GLBX.MDP3 data (GC, MGC, and possibly BTC and MBT futures: trades, TBBO, MBP-1, OHLCV, definitions, statistics), and possibly live data on the Standard plan.
>
> My intended use: I am an individual building a private quantitative model for my own trading. I would store the data privately in my own Google Cloud storage, use it for research and backtesting, train and validate machine-learning models, retain derived features and model weights, and use the model's output in automated trading of my own account. I will not distribute any data externally.
>
> 1. Does usage-based (pay-as-you-go) historical data permit this use? Your catalog appears to show usage-based as "personal use" and the Standard plan as "commercial use".
> 2. Does CME's June 2026 licence update (DS-45), which restricts machine-learning use of "Information", apply to historical data bought from Databento for internal non-display use like mine?
> 3. On the Standard plan, does "license fees included" cover automated (non-display) use by an individual trading their own account, and which subscriber category would I fall under?
> 4. Can I keep historical data and derived models after my subscription ends?
>
> Thank you.

**Signup questionnaire guidance.**
- Databento's licence questionnaire is not public. Its blog says it covers professional vs non-professional status, display vs non-display use, internal use vs redistribution, and devices.
- Answer it truthfully:
  - **internal use, no redistribution**;
  - **non-display use is likely**, because automated or algorithmic processing is non-display;
  - **professional vs non-professional** depends on CME's definition. Databento's blog treats "commercial purposes, such as trading" as professional. CME's non-professional status requires personal use limited to managing your own assets. If unsure, say so and ask, rather than choosing the cheaper category.
- Historical-only purchases reportedly need no exchange licence (VERIFIED, Databento blog), but question 1 above must be confirmed first.

### M4: Polymarket (to `data-licensing@polymarket.com`; US: `data@polymarket.us`). Send only if Polymarket is in scope

> Subject: Does an individual's own-account research project count as a "Capital Markets Entity"?
>
> Hello,
>
> I am an individual (not a firm) developing a private quantitative model for my own trading. I would retrieve public Polymarket data (Gamma, Data API, CLOB order books, and on-chain fills and resolutions), store it privately in my own cloud storage, backtest, train machine-learning models, and use the output solely for my own trading. I would not redistribute data. Am I a "Capital Markets Entity" that must consume data in consultation with Polymarket and ICE? If not, are these uses permitted under your terms? If so, what is the licensing route?
>
> [For Polymarket US: which terms govern automated retrieval and storage of public gateway data and WebSocket data for my own trading research, given the Terms of Use limits on bulk download?]
>
> Thank you.

### M5: Coinbase (to `marketdata@coinbase.com`). Optional; recommended DROP for now

> Subject: Written consent request: Market Data Terms, machine-learning use for own-account trading
>
> Hello,
>
> Your Market Data Terms require prior express written consent to use market data to train or validate machine-learning models. I am an individual building a private model for my own trading. I would store public Exchange market data privately in my own cloud storage, train and validate models, retain derived features and weights, and use the output solely for my own trading, with no redistribution. Would Coinbase grant written consent for this, or is a Data Marketplace licence required? If the latter, what does it cost?
>
> Thank you.

### M6: CF Benchmarks (to `licensing@cfbenchmarks.com`). Quote request

> Subject: Licence quote: BRTI historical and real-time data for private research and own-account trading
>
> Hello,
>
> I am an individual developing a private quantitative model for my own trading on contracts that settle on the CME CF Bitcoin Real Time Index. I would like a quote and licence terms for:
> - historical BRTI values at the finest available granularity, with first-published vintages or your restatement policy;
> - a point-in-time constituent history;
> - optionally, real-time BRTI.
>
> My use: private storage in my own cloud, research, backtesting, machine-learning model training, and own-account trading. No redistribution. I can also access BRTI through Kalshi's data entitlement or CME DataMine: which route do you recommend for this use?
>
> Thank you.

## 7. Remaining unknowns that block acquisition

1. **Kalshi's written answer to M1.** It gates K1, K3, K4, and K5. Without it, the Kalshi-venue strategy has no lawful training data.
2. **Kraken's permission (M2)** and the archive location.
3. **Databento usage-based "commercial use" and CME DS-45 scope (M3).**
4. **DET-1 and DET-2:** the Kalshi gold reference feed and the BTC rulebook. You download the contract terms.
5. The cloud pipeline and your per-source A-1 to A-6 approvals (decision record D-B09-10 to D-B09-16). Data cannot land anywhere safe before CLOUD-1/2.
6. Prices still marked UNKNOWN: Kalshi BRTI entitlement, CF Benchmarks, CME DataMine, Coinbase Data Marketplace, Pyth $99 package contents.

---

## OWNER LINKS — ACTION REQUIRED

**Kalshi**
- Developer Agreement: <https://kalshi.com/developer-agreement>
- Terms of Service: <https://kalshi.com/terms>
- Data Terms of Use (PDF): <https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf>
- Fee schedule: <https://kalshi.com/docs/kalshi-fee-schedule.pdf>
- API documentation: <https://docs.kalshi.com/>
- Help centre / contact: <https://help.kalshi.com/en/articles/13823855-contact-kalshi-support>
- Contact: `institutional@kalshi.com`, `support@kalshi.com`

**Kraken**
- Historical trades archive: <https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales->
- OHLCVT archive: <https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data>
- Developer docs (historical data): <https://docs.kraken.com/exchange/guides/general/historical-data>
- Legal terms: <https://www.kraken.com/legal>
- Permission contact: `marketdata@kraken.com`

**Polymarket**
- Institutional data statement: <https://institutional.polymarket.com/>
- Polymarket Institute: <https://institute.polymarket.com/>
- Terms of Service: <https://polymarket.com/tos>
- API docs: <https://docs.polymarket.com/>
- Polymarket US rulebook: <https://polymarketexchange.com/files/legal/latest/rulebook>
- Polymarket US contact: <https://www.polymarketexchange.com/contact.html>
- Contacts: `data-licensing@polymarket.com`, `data@polymarket.us`

**Databento**
- Pricing: <https://databento.com/pricing>
- CME catalog and plans: <https://databento.com/catalog/cme/GLBX.MDP3>
- Signup: <https://databento.com/signup>
- Cost estimate API (`get_cost`): <https://databento.com/docs/api-reference-historical/metadata/metadata-get-cost>
- Licensing explainer: <https://databento.com/blog/introduction-market-data-licensing>
- Legal terms: <https://databento.com/legal>
- Contact: `support@databento.com`

**CME DataMine** (Tier 3, for reference)
- DataMine: <https://www.cmegroup.com/datamine.html>
- Ordering guide: <https://www.cmegroup.com/tools-information/webhelp/data-services-portal/Content/Ordering-CME-Datamine-Products.html>
- 2026 fee list: <https://www.cmegroup.com/market-data/files/january-2026-market-data-fee-list.pdf>
- June 2026 licence updates (DS-45): <https://www.cmegroup.com/market-data/files/market-data-license-agreement-updates-june-2026.pdf>
- Contact: `CMEDataSales@cmegroup.com`, `marketdata@cmegroup.com`

**CF Benchmarks (BRTI)**
- BRTI page: <https://www.cfbenchmarks.com/data/indices/BRTI>
- CME CF crypto benchmarks FAQ: <https://www.cmegroup.com/articles/faqs/cme-cf-cryptocurrency-benchmarks-faq.html>
- Contact: `licensing@cfbenchmarks.com`

**Tardis.dev**
- Pricing: <https://tardis.dev/#pricing>
- Billing FAQ: <https://docs.tardis.dev/faq/billing-and-subscriptions>
- Contact: `contact@tardis.dev`

**Pyth**
- Pricing and trial: <https://www.pyth.network/pricing>
- History API docs: <https://docs.pyth.network/price-feeds/pro/api/history>

**Coinbase**
- Market Data Terms: <https://www.coinbase.com/legal/market_data>
- Data Marketplace: <https://help.coinbase.com/en/data-marketplace/getting-started/coinbase-data-marketplace>
- Contact: `marketdata@coinbase.com`

**Backups (only if needed)**
- CoinAPI flat-file pricing: <https://www.coinapi.io/products/flat-files/pricing>
- Marketlens: <https://marketlens.trade/>
- Chainlink Data Streams billing: <https://docs.chain.link/data-streams/billing>
