# Historical-Data Inventory: Open Datasets, Academic/Technical Sources, Regulatory/Reference (Phase 1 batch 3, sections D–F)

**Status:** research record, not an approved requirement. Documentation only: dataset cards and metadata, paper abstracts and pages, READMEs, and regulator pages. No dataset file, viewer, preview, or row sample was opened. No market-data API was called. No market values are recorded or used here. Retrieved 2026-10-16 (UTC). Branch `phase1/historical-data-strategy`.

**Conventions.**
- Tags: **VERIFIED-BY-DOC** means the publisher's own card, README, or page says so (it is a documented claim, not observed behavior). **INFERENCE** means my reasoning from the documentation. **UNRESOLVED** means it could not be found out without opening data or a blocked source.
- "Exposed to PMV development" is **none** for every record here. Reading a card is not data exposure. Incidental exposures from reading cards and pages are listed in section G.
- Revision SHAs are the Hugging Face dataset commit at retrieval time. They are recorded so any later acquisition can be pinned (see recommendation R-3).

**Owner direction this batch implements (2026-10-16):** use verified existing historical data aggressively for development, and build prospective capture in parallel. Historical data exposed to development can never become protected holdout.

---

## Cross-cutting findings (read first)

1. **Most open "venue" datasets are third-party API scrapes redistributed under a license the scraper chose.** A CC-BY or MIT tag on Hugging Face or Kaggle does not show that the redistributor had the right to grant it. Kalshi data is governed by the Kalshi Developer Agreement. One card (RooseveltHonaker) tells users to comply with it, which implies the redistributor does not claim to override it. Polymarket off-chain data (CLOB WebSocket and REST) is governed by Polymarket's terms. Polymarket **on-chain** fills (Polygon `OrderFilled` events) are public blockchain records. Their provenance can be checked against any Polygon RPC node, so they are the one open venue data family with primary-source provenance. **INFERENCE.** Venue terms of use are another agent's scope. They are **UNRESOLVED** here, partly because kalshi.com is bot-blocked (AR-3).
2. **Historical order books do not exist from the venues.** Kalshi and Polymarket expose live books only, so any historical depth comes from someone's own WebSocket recorder. Those recorders have gaps, clock skew, receipt-time-only stamps (several), and sub-sampled universes. They are still the only route to historical depth for development. **VERIFIED-BY-DOC** for the cards that say so (mileswangs, polyorderbooks, Joseph3222/pmxt, lerchen3).
3. **Many datasets are live-updating and reach to roughly 2026-10-15 or 2026-10-16** (aliplayer1 every 3 h, TimeSeventeen daily, RooseveltHonaker, rogerdehe, papylove). Any acquisition must be **pinned to a revision and cut at a fixed development boundary before anyone reads it**. Otherwise a later refresh could carry observations from a future prospective protected window into development. This is the main protected-information risk in this section.
4. **Underlying-asset equivalence.** BTC spot or perp tick data, and XAU/USD ticks, are equivalent observables for BTC and gold contracts (docs/protected_information.md). The same rule applies to them as to venue data. In particular, Chainlink BTC/USD streams (mileswangs, aliplayer1) are the documented Polymarket resolution source, so they are direct equivalents.
5. **Gold is weak in open data.** Every open XAU/USD tick set I found is an OTC broker CFD or retail-FX feed (unnamed broker, Dukascopy-like, OANDA, Tickmill, HistData). None is COMEX GC futures or LBMA. Whatever reference a Kalshi or Polymarket gold contract settles on (another agent's scope, **UNRESOLVED** here), these feeds are at best auxiliary proxies with unknown licensing.

---

## D. Open/public datasets

### D.1 Kalshi

#### D-K1. TrevorJS/kalshi-trades (merges Andrew Becker's `kalshi_trades`)
- URL: https://huggingface.co/datasets/TrevorJS/kalshi-trades (rev `5c622baf…`)
- Data type: trade prints plus market metadata. Venue: Kalshi, all series.
- Coverage: June 2021 to January 2026 (VERIFIED-BY-DOC).
- Granularity: every public trade, with `created_time` at µs UTC (VERIFIED-BY-DOC). Kalshi's own timestamp resolution is not stated (UNRESOLVED).
- Trades: yes (`yes_price`, `no_price` in cents, `count`, `taker_side`). Quotes: only a single `yes_bid` / `yes_ask` / `no_bid` / `no_ask` "at time of fetch", which is a snapshot taken at the fetch time, not a history. **It must never be used as a historical quote**, because doing so is a lookahead trap (INFERENCE).
- Order books/depth: none. Contract metadata: ticker, event_ticker, title, open/close times, status. Outcomes: `result` (VERIFIED-BY-DOC). Settlement value or strike as structured fields: not listed (UNRESOLVED).
- Timestamp semantics: trade creation time from Kalshi's API. Market metadata was backfilled later through the `/markets` batch endpoint, so its fields reflect fetch-time state (VERIFIED-BY-DOC, plus INFERENCE).
- Historical revisions: one upload, 2026-01-30. The card reports cleaning that removed 21,950 duplicate trades.
- Access: HF download, no authentication. Cost: free. License: CC-BY-4.0 asserted by the redistributor. Kalshi's terms are **UNRESOLVED**.
- Provenance: medium. The source is Kalshi's public trades endpoint, which another agent is verifying, so the data is reproducible from the venue in principle.
- Gaps: no quotes or depth, and no per-trade sequence number.
- Likely PMV use: long-horizon calibration and favourite-longshot (FLB) baselines, taker-flow features, and cross-checks of trades obtained directly from the venue.
- Classification: **development**, after cross-validation against Kalshi's official historical endpoints. Exposed to PMV: none.

#### D-K2. jon-becker/prediction-market-analysis (and mirror rhinot/prediction-market-analysis)
- URL: https://github.com/jon-becker/prediction-market-analysis (MIT, active as of 2026-10-09). Mirror: https://huggingface.co/datasets/rhinot/prediction-market-analysis (rev `969daa41…`, one 36 GiB `data.tar.zst`).
- Data type: Kalshi markets and trades, plus Polymarket markets, trades, and blocks (API-collected and blockchain-indexed). The card also mentions order books, but the repository tree shows only markets/trades/blocks (UNRESOLVED).
- Coverage: UNRESOLVED (the schemas doc was not read).
- Timestamp semantics: per `docs/SCHEMAS.md` (UNRESOLVED).
- Access: Cloudflare R2 tarball (s3.jbecker.dev, not contacted) or the HF mirror. Includes open-source indexers.
- License: MIT for code and data (asserted). Venue terms UNRESOLVED.
- Provenance: medium. It is widely used in academic work: the README lists roughly 18 SSRN and arXiv papers, including Bürgi/Whelan-adjacent work and Le (2026). The indexers are an inspectable reference implementation (license-compatible).
- Classification: **development** (cross-check source) and code reference. Exposed: none.

#### D-K3. RooseveltHonaker/kalshi-trades-data
- URL: https://huggingface.co/datasets/RooseveltHonaker/kalshi-trades-data (rev `9e631f1f…`, 1,130 numbered immutable JSONL shards, updated 2026-10-16).
- Data type: raw per-market trade lists as returned by Kalshi's API, including the market window and reported volume, plus trade IDs, prices, quantities, taker direction, and a block-trade flag (VERIFIED-BY-DOC).
- Coverage: UNRESOLVED (shards are numbered, not dated).
- License: none declared. The card says users must comply with the Kalshi Developer Agreement, so redistribution rights are **unclear**.
- Provenance: medium-low (anonymous). On the positive side, it is raw-ish and stored in immutable shards.
- Classification: **auxiliary only** until the license is resolved. Live-updating, so it carries the finding-3 risk. Exposed: none.

#### D-K4. papylove/kalshi-15m-data and papylove/kalshi-15m-metals-data
- URLs: https://huggingface.co/datasets/papylove/kalshi-15m-data (rev `7b6e986c…`) and https://huggingface.co/datasets/papylove/kalshi-15m-metals-data.
- Data type: daily parquet files of Kalshi 15-minute markets (crypto, and metals including gold), plus a `spot_history/` folder with `SOURCE.json`, and `price_history_alpaca/` (gold, silver, platinum, WTI) in the metals repository. Schema UNRESOLVED: there is **no README and no license**.
- Coverage from file paths: 2026-06-22 to 2026-10-11 (crypto) and from 2026-08-31 (metals) (VERIFIED-BY-DOC from file names only).
- Provenance: unknown. Alpaca-sourced reference prices are probably subject to Alpaca's data terms (INFERENCE).
- This is the only open source found that claims to cover **Kalshi 15-minute gold/metals** markets, which makes it interesting despite the quality problems.
- Classification: **auxiliary only / do not use** until the provenance and license are known. Live-updating (finding 3). Exposed: none.

#### D-K5. DegenHedge/kalshi-btc-15m (KXBTC15M settlements plus a vendor signal record)
- URL: https://huggingface.co/datasets/DegenHedge/kalshi-btc-15m (rev `dcf917e4…`, release v2026.10, CC-BY-4.0). Ships CHECKSUMS.sha256, CITATION.cff, METHODOLOGY.md, DATA_DICTIONARY.md, and a stdlib validator.
- Data type:
  - `windows`: one row per KXBTC15M window, 2026-01-10 to 2026-10-04, with Kalshi's official strike, settlement value, result, contracts traded, and open/close times, pulled from `/trade-api/v2/markets` and `/historical/markets` on 2026-10-05.
  - `signals`: a commercial tipster's logged signals, including a 10-second-poll ask snapshot taken about 170 s before close (VERIFIED-BY-DOC).
- The card documents the settlement rule for the era: the 60-second BRTI average before close compared with the 60-second average before open.
- Trades, depth: none. Quotes: sparse logged snapshots in `signals` only.
- Provenance: good for `windows`, because it can be re-derived from Kalshi's official API. `signals` comes from a marketing source and is biased by selection ("published record"). **Do not use `signals` for modeling.**
- PMV use: settlement-integrity checks, label construction cross-check (strike and settlement value), and the settlement-rule era boundary. It overlaps D-K1 and the venue's own historical endpoints.
- Classification: **development (cross-check only)**. The `windows` table is outcome data through 2026-10-04. Exposed: none, but see G-1.

#### D-K6. lerchen3/kalshi-orderbook-alpha
- URL: https://huggingface.co/datasets/lerchen3/kalshi-orderbook-alpha (rev `50d081ab…`, license "other").
- Data type: live order-book snapshots and every `orderbook_delta`, with derived state and local receipt time in ns plus Kalshi's exchange timestamp where present (VERIFIED-BY-DOC).
- Universe: the top 200 markets by volume, rebalanced every 10 minutes. Books are truncated to the top 3 levels plus a ">1,000-contract" best level.
- Coverage: **a single day (2026-07-19), about 12 hours** (file paths).
- Classification: **auxiliary**. It is too short for development. It is useful only as a schema and latency reference. Exposed: none.

#### D-K7. Others (low value)
- bennett-tan/kalshi-btc-15m: about 33.8M trades with a `resolved_yes` label, no license, no provenance.
- thomaswmitch/kalshi-prediction-markets-*: trades Aug 2023 to Aug 2025, MIT asserted.
- reapxdev/kalshi-scraper.
- tsedbroo/kalshi-forecast-alpha.
- Kaggle: gavinalfaro (Kalshi finance/economics, 18 months), simplefunctions/settled-markets (license unknown).

All are **auxiliary only or skip**: no provenance, unknown license, and they duplicate D-K1/D-K2. Exposed: none.

### D.2 Polymarket

#### D-P1. Polygon on-chain `OrderFilled` archives (primary-source-verifiable)
- Same data family, several packagers:
  - **SII-WANGZJ/Polymarket_data** (https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data, rev `73bc1adc…`; GitHub code MIT; HF card has no license field). Coverage 2022-11-21 to 2026-10-04, covering V1 and V2 CTF exchange contracts. Files: raw `orderfilled`, processed `trades`, `markets`, and derived `quant` and `users`.
  - **TimeSeventeen/Polymarket-v2** (CC-BY-4.0, V2 exchange from 2026-04-03, updated daily to 2026-10-15).
  - **vgregoire/polymarket-users** (CC-BY-4.0, 2022-11-11 to 2026-03-29). This is the replication data for Akey, Grégoire, Harvie & Martineau, SSRN 6443103, so it is academically maintained. Its card notes that Polymarket ToS may govern some off-chain fields.
  - **PolyData/polymarket_trade_capture_5Mar2026** (CC-BY-4.0, via the Goldsky indexer, to 2026-03-05).
  - The Qin & Yang **Polymarket-v1 Database** (arXiv 2606.04217, V1 to 2026-04-28; distribution location UNRESOLVED).
- Data type: every CLOB fill, with block number, tx hash, log index, maker and taker wallets, price, amounts, maker/taker direction, and token. The direction is chain-truth (VERIFIED-BY-DOC).
- Quotes/depth: none. Contract metadata: joined from the Gamma API (fetch-time state, a lookahead risk for mutable fields, INFERENCE). Outcomes: from market metadata. Resolution on-chain is through the UMA/CTF payout. Polymarket crypto up/down markets resolve on Chainlink.
- Timestamp semantics: **Polygon block timestamp (seconds)**. This is settlement time, not matching time. Several papers (2604.24366, 2606.04217) document a sub-second to multi-second gap between engine match and chain settlement. So these timestamps are **not decision-time observables at sub-block resolution** (VERIFIED-BY-DOC plus INFERENCE).
- Historical revisions: the SII 2026-10-05 release fixed missing V2 sell-side fills and changed hash formatting. Earlier snapshots were wrong (VERIFIED-BY-DOC). Re-derivation from chain is possible.
- License: chain data is public; the packagers assert MIT or CC-BY.
- Provenance: **high**, because it can be verified against Polygon RPC.
- PMV use: Polymarket trade-flow features, ground-truth aggressor side, and FLB/calibration studies of crypto up/down markets.
- Classification: **development** (the best Polymarket trade source). Exposed: none.

#### D-P2. Polymarket order-book recordings (third-party WebSocket captures)
- **pmxt archive** (archive.pmxt.dev; v1 and v2 on R2). Hourly order-book files, also mirrored to the Internet Archive as `pmxt-polymarket-v{1,2}-YYYY-MM-DD` items.
  - Packaged by **Joseph3222/polymarket-orderbook** (CC-BY-4.0, rev `efe472f1…`): 2026-02-22 to 2026-08-10, plus a 1-minute full-depth rollup.
  - Documented flaws (VERIFIED-BY-DOC): v1 (to 2026-04-12) subscribed to only about half of markets; source timestamps are **1-second**; v1 emitted a book snapshot about every 10 s; there is an outage gap; 2026-08-10 is partial.
  - **archive.pmxt.dev was refused by the sandbox proxy** (see ACCESS REQUESTS).
- **mileswangs/polymarket-btc-updown-5m-orderbook-tick-data** (CC-BY-4.0, rev `acb8cecf…`). A free two-week sample (2026-08-08 to about 08-21) from the commercial PMData. Contents: raw `book` and `price_change` messages with Polymarket event time and receipt time at µs; redundant dual WebSocket; Chainlink Data Streams BTC/USD (direct); on-chain fills. **5-minute markets only.** The best timestamp documentation found (VERIFIED-BY-DOC).
- **polyorderbooks/polymarket-crypto-updown-orderbooks-l2** (CC-BY-4.0; Zenodo DOI 10.5281/zenodo.22084114). 1-second L2 polling with a 60-second reconcile. Covers 805 resolved markets across 5m, 15m, and 4h; window dates UNRESOLVED. Documents crossed snapshots and empty ladders.
- **aliplayer1/polymarket-crypto-updown** (MIT, rev `ffb15ce5…`, updated every 3 h, has a `.gap_manifest.json`).
  - Contents: markets including `fee_rate_bps`; CLOB price history; on-chain and WebSocket ticks with a Binance spot price attached; Binance and Chainlink spot feed; best bid/ask snapshots (receipt time ms) for BTC, ETH, and others across 5m/15m/1h/4h.
  - Pipeline repo referenced but returned 404 on GitHub (UNRESOLVED).
  - Many near-identical forks exist (BrockMisner, obadiaha, heaouwtj, notkali, Radim462, bmoney1321) with unclear lineage.
- **predict-quant/poly-btc-orderbook** (high downloads, no license, no card).
- Kaggle Polymarket order-book sets (marvingozo CC-BY-NC; gyroflaw poly-btc-15m CC0; namz8888 100 ms CC-BY-SA; marketlens one day; and others): all without provenance.
- Classification: **development candidates for depth and spread studies only after a gap/clock audit**. pmxt/Joseph3222 and aliplayer1 are the only ones with multi-month 15m/1h coverage. Treat all of them as non-authoritative. Licenses are as asserted by recorders of venue data, so Polymarket ToS is UNRESOLVED. Exposed: none.

#### D-P3. OpenMarket (Young 2026, arXiv 2607.26245)
- A synchronized Polymarket BTC 15-minute plus Binance BTC/USDT millisecond corpus, 2026-02-12 to 2026-05-15 (54 Polymarket days). It comes with explicit lead-lag pairing metadata, a Rust pipeline, and frozen tag v0.5.2 (VERIFIED-BY-DOC, abstract).
- The authors report a **negative result**: no tradable edge after costs from a walk-forward logistic model on microstructure features.
- Release location and license: UNRESOLVED (I did not read past the abstract).
- PMV use: the closest public analogue of the PMV hypothesis, and a must-read. The corpus is a **development** candidate once the license and location are verified. Exposed: none.

#### D-P4. Others
- Harvard Dataverse doi:10.7910/DVN/KHX5QY (Chernoff 2026): a CC0 Kalshi/Polymarket matched-pair file of about 14 KB with event-level metadata. Auxiliary.
- Coyevans matched-book samples (CC-BY-NC, MLB).
- ailinsun/polymarket-kalshi-contract-equivalence-gold: contract-equivalence labels. Possibly useful for cross-venue mapping methodology. Auxiliary.

### D.3 BTC high-frequency (underlying)
Venue-native archives (Binance data.binance.vision, Coinbase, Kraken, CME, Tardis, and others) are another agent's scope. The open redistributions below are inferior copies of them.

- **D-B1. rogerdehe/mktdata-binance-2026** (MIT asserted, rev `617edad5…`). Full-depth L2 **deltas** plus trades for Binance USDT-M perpetuals, UTC ns, with a full snapshot spliced in about every 60 s, from 2026-07-15 and growing. "Goldmine" recorder, receipt-time semantics unclear (UNRESOLVED). The Binance market-data license makes the MIT relicense doubtful. **Auxiliary / cross-check only.**
- **D-B2. delmiron27/cryptolake-binance-futures-btc** (license "other", rev `7c027b47…`). Book20 snapshots, trades, funding, liquidations, and open interest for BTC-USDT-PERP, about 2024-11 to 2026-06, with gaps. The card says it is a mirror of a **paid Cryptolake subscription capture**. **High suspicion of redistribution in breach of the vendor's terms. Do not use.**
- **D-B3. predict-quant/binance-spot-orderbook / binance-future-orderbook** (spot: no license; futures: Apache-2.0 asserted). Depth-20 snapshots, 2026-04 to 2026-05. Auxiliary.
- **D-B4. AisotTechnologies/aisot_btc_lob_trades** (CC-BY-NC-SA, gated with manual approval). Bitstamp order books and trades, Jul–Aug 2018 (from file names). Old, non-commercial, gated. Methodology reference only.
- **D-B5. Zenodo 10.5281/zenodo.10600374** "Order Book Data from Six Crypto-Exchanges" (Henker et al., CC-BY-4.0, 2024). Academic, but old and short. Methodology or benchmark only.
- **D-B6. Kaggle** (martinsn high-frequency crypto LOB 2021 CC0; siavashraz BTC perp LOB; krrdev1 Binance L3 CC-BY-NC; and others). Provenance unknown. Skip.
- **D-B7. vaquum/binance_btcusdt_* klines** (no license). Klines are trivially re-derivable from the official Binance archive, so use the official source instead.

### D.4 Gold intraday
- **D-G1. CarlosSilva1/xauusd-ticks** (CC-BY-4.0 asserted, rev `d14fc64d…`). XAU/USD bid/ask ticks at ms UTC, 2021-05-24 to 2026-05-24. The card says it was "reconstructed from broker data". **Broker unnamed, so redistribution rights are doubtful.** Many clones (Arpanbh, Junsoo1, addyAIMLprojects, renkotrading26). **Auxiliary only.**
- **D-G2. bunqi/OANDA_XAUUSD_Gold** (no card or license; OANDA bars at many resolutions, 2006–2026). OANDA terms almost certainly forbid redistribution (INFERENCE). Do not use.
- **D-G3. Tickmill / HistData / Dukascopy-derived Kaggle and HF sets** (sheldonrobinson/histdata-forex-xauusd says "Data files © Original Authors"; alchimistvq 1m; novandraanugrah 2004–2026 CC0 asserted, with no provenance for the CC0). These are retail CFD quotes: dealer-specific spreads, weekend gaps, no volume. Auxiliary at best.
- **D-G4. COMEX GC futures on Kaggle** (youneseloiarm, gvyshnya, guillemservera). Daily only, probably Yahoo-sourced. Not intraday, so not useful.
- **Conclusion:** there is **no defensible open intraday gold source**. Gold must come from licensed vendor or exchange data (another agent's scope) or from prospective capture.

---

## E. Academic and technical sources

Tags:
- Status **V**: title, authors, and year verified via Crossref DOI or the arXiv abstract page on 2026-10-16.
- Status **S**: identified via search results or a publisher landing page only.

Phases: P1 data, P2 dataset/target, P3 baselines, P4 models, P4.5 risk policy, P5 audit, P6–7 holdout, P8 monitoring, P9 execution.

### E.1 Prediction-market pricing, efficiency, FLB, microstructure

| # | Citation | Locator | Relevance to PMV | Phase | St |
|---|---|---|---|---|---|
| 1 | Bürgi, Deng, Whelan (2025/26), *Makers and Takers: The Economics of the Kalshi Prediction Market*, CESifo WP 12122 / CEPR DP20631 | SSRN 5502658; https://www.karlwhelan.com/Papers/Kalshi.pdf | The core Kalshi FLB and maker/taker-return evidence. The fee asymmetry drives the cost model. | P2, P3, P4.5 | S |
| 2 | Lee et al. (2026), *Cryptocurrency prediction markets through the derivatives lens: Evidence from Kalshi and Polymarket*, Int. Rev. Financial Analysis | doi:10.1016/j.irfa.2026.105433; SSRN 6748186 | Treats BTC 15-minute contracts as cash-or-nothing digitals across both venues. **The most directly relevant paper.** | P2–P4 | V (Crossref) |
| 3 | Young (2026), *OpenMarket: A Synchronized Polymarket–Binance Dataset…* | arXiv:2607.26245 | A documented **null result** for this exact strategy class (BTC 15m vs Binance flow). Sets the prior PMV must beat. | P1, P3, P5 | V |
| 4 | Dai, Jia, Yu (2026), *Settlement Manipulation in Prediction Markets* | arXiv:2606.31675 | Settlement-window manipulation of underlying-settled crypto contracts. A design risk and possible feature. Says 15m is much less affected than 5m. | P2, P10 | V |
| 5 | Dubach (2026), *The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book* | arXiv:2604.24366 | Feed-vs-chain trade-direction disagreement, ingestion delays, and spread facts. These shape the timestamp and aggressor-side design. | P1, P2 | V |
| 6 | Qin, Yang (2026), *Polymarket-v1 Database* | arXiv:2606.04217 | Ground-truth aggressor side. Tick-rule, VPIN, and OFI biases in prediction markets. | P2, P4 | V |
| 7 | Gebele, Mutzel, Matthes (2026), *Executable Arbitrage and Market Efficiency in Prediction Markets* | arXiv:2608.00666 | Payoff-space vs executable no-arbitrage. Depth-aware executable values. | P3, P9 | V |
| 8 | Gebele, Matthes (2026), *When Certainty Is Not Worth It: Capital Lock-Up and Settlement Discounting* | arXiv:2605.31431 | The settlement-delay discount. Matters near certainty (high-price contracts). | P2, P4.5 | V |
| 9 | Cardozo, Rivero-Wildemauwe (2026), *The Favorite-Longshot Bias in Prediction Markets: Evidence from Polymarket* | arXiv:2609.12878 | Polymarket FLB. Compare with #1. | P3 | V |
| 10 | Le (2026), *Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets* | arXiv:2602.19520 | Calibration by domain and time-to-close across Kalshi and Polymarket. | P3 | V |
| 11 | Kagan, Baiocchi (2026), *Calibration in Prediction Markets: Theory and Evidence* (Kalshi Research WP) | https://kalshi.com/research/kalshi-research-calibration.pdf | Venue-authored, so not independent. Says it excludes intraday crypto. Has a resolution-timestamp caveat. | P3 | S (kalshi.com bot-blocked) |
| 12 | Akey, Grégoire, Harvie, Martineau (2026), *Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket* | SSRN 6443103 | Trader-level P&L distribution. Ships the D-P1 vgregoire data. | P3, P4.5 | S |
| 13 | Snowberg, Wolfers (2010), *Explaining the Favorite–Long Shot Bias*, JPE 118(4) | doi:10.1086/655844 | FLB theory: misperception vs risk-love. | P3 | V |
| 14 | Wolfers, Zitzewitz (2004), *Prediction Markets*, JEP 18(2) | doi:10.1257/0895330041371321 | Foundations. | P2 | V |
| 15 | Manski (2006), *Interpreting the predictions of prediction markets*, Econ. Letters | doi:10.1016/j.econlet.2006.01.004 | Price ≠ mean belief. A warning about reading price as probability. | P3 | V |
| 16 | Page, Clemen (2013), *Do Prediction Markets Produce Well-Calibrated Probability Forecasts?*, Econ. J. | doi:10.1111/j.1468-0297.2012.02561.x | Calibration vs time-to-expiry. Directly relevant to time remaining as a first-class variable. | P3 | V |

### E.2 Order flow, microstructure, realized volatility, digital pricing, crypto

| # | Citation | Locator | Relevance to PMV | Phase | St |
|---|---|---|---|---|---|
| 17 | Cont, Kukanov, Stoikov (2014), *The Price Impact of Order Book Events*, J. Fin. Econometrics 12(1) | doi:10.1093/jjfinec/nbt003; arXiv:1011.6402 | OFI: the canonical short-horizon velocity feature for the BTC underlying. | P4 | V |
| 18 | Kolm, Turiel, Westray (2023), *Deep order flow imbalance*, Math. Finance | doi:10.1111/mafi.12413 | Multi-level OFI and when DL helps over linear OFI. A benchmark for "simple first". | P4 | V |
| 19 | Easley, López de Prado, O'Hara (2012), *Flow Toxicity and Liquidity in a High-frequency World*, RFS | doi:10.1093/rfs/hhs053 | VPIN. Also see #6 on its misestimation. | P4, P8 | V |
| 20 | Makarov, Schoar (2020), *Trading and arbitrage in cryptocurrency markets*, JFE 135(2) | doi:10.1016/j.jfineco.2019.07.001 | Cross-exchange BTC price dispersion. Index (BRTI) vs single venue. | P2 | V |
| 21 | Aït-Sahalia, Mykland, Zhang (2005), *How Often to Sample a Continuous-Time Process in the Presence of Market Microstructure Noise*, RFS | doi:10.1093/rfs/hhi016 | Optimal sampling for remaining-window volatility. | P4 | V |
| 22 | Zhang, Mykland, Aït-Sahalia (2005), *A Tale of Two Time Scales*, JASA | doi:10.1198/016214505000000169 | TSRV: noise-robust RV. | P4 | V |
| 23 | Barndorff-Nielsen, Hansen, Lunde, Shephard (2008), *Designing Realized Kernels…*, Econometrica 76(6) | doi:10.3982/ECTA6495 | Realized kernels. | P4 | V |
| 24 | Hansen, Lunde (2006), *Realized Variance and Market Microstructure Noise*, JBES | doi:10.1198/073500106000000071 | Noise diagnostics. | P4 | V |
| 25 | Corsi (2009), *A Simple Approximate Long-Memory Model of Realized Volatility*, J. Fin. Econometrics | doi:10.1093/jjfinec/nbp001 | HAR-RV: a simple volatility-forecast baseline for the digital-option fair value. | P3 | V |
| 26 | Breeden, Litzenberger (1978), *Prices of State-Contingent Claims Implicit in Option Prices*, J. Business | doi:10.1086/296025 | Digital = −∂C/∂K. Lets option-implied (Deribit/CME) probabilities serve as a benchmark for the binary. | P3 | V |
| 27 | Andersen, Bollerslev, Diebold, Vega (2003), *Micro Effects of Macro Announcements*, AER 93(1) | doi:10.1257/000282803321455151 | Intraday jump and volatility response to scheduled releases. Justifies the section F calendars. | P2, P4 | V |

Coverage gap: I found no rigorous peer-reviewed treatment of **digital-option pricing in the final minutes with discrete averaging-window settlement**, such as Kalshi's 60-second BRTI average. The BTC contracts are effectively short-dated Asian-style digitals. Standard Asian-option and Brownian-bridge results apply, but PMV will have to derive them. #2 is the closest. (INFERENCE.)

### E.3 Calibration and scoring

| # | Citation | Locator | Relevance to PMV | Phase | St |
|---|---|---|---|---|---|
| 28 | Gneiting, Raftery (2007), *Strictly Proper Scoring Rules, Prediction, and Estimation*, JASA | doi:10.1198/016214506000001437 | The basis for Brier and log loss. | P3, P5, P8 | V |
| 29 | Platt (1999), *Probabilistic Outputs for SVMs…*, in Advances in Large Margin Classifiers (MIT Press) | (book chapter; no DOI checked) | Logistic calibration. | P3 | S |
| 30 | Zadrozny, Elkan (2002), *Transforming classifier scores into accurate multiclass probability estimates*, KDD | doi:10.1145/775047.775151 | Isotonic calibration. | P3 | V |
| 31 | Niculescu-Mizil, Caruana (2005), *Predicting good probabilities with supervised learning*, ICML | doi:10.1145/1102351.1102430 | Calibrating boosted trees. | P3, P4 | V |
| 32 | Kull, Silva Filho, Flach (2017), *Beta calibration*, AISTATS, PMLR 54:623–631 | https://proceedings.mlr.press/v54/kull17a.html | A better fit than Platt when probabilities sit near 0 or 1, which is common in late-window contracts. | P3 | S |
| 33 | Guo, Pleiss, Sun, Weinberger (2017), *On Calibration of Modern Neural Networks*, ICML | arXiv:1706.04599 | Temperature scaling and ECE pitfalls for the GRU/TCN candidates. | P4 | V |

### E.4 Validation, overfitting, dependence, sequential monitoring

| # | Citation | Locator | Relevance to PMV | Phase | St |
|---|---|---|---|---|---|
| 34 | López de Prado (2018), *Advances in Financial Machine Learning*, Wiley | ISBN 978-1-119-48208-6 | Purged/embargoed and combinatorial purged CV, and labelling. | P2, P5 | S |
| 35 | Bailey, Borwein, López de Prado, Zhu (2016), *The probability of backtest overfitting*, J. Comput. Finance | doi:10.21314/JCF.2016.322 | PBO via CSCV. | P5 | V |
| 36 | Bailey, López de Prado (2014), *The Deflated Sharpe Ratio*, J. Portfolio Mgmt 40(5) | doi:10.3905/jpm.2014.40.5.094 | Multiple-testing haircut. | P5 | V |
| 37 | White (2000), *A Reality Check for Data Snooping*, Econometrica; Hansen (2005), *A Test for Superior Predictive Ability*, JBES | doi:10.1111/1468-0262.00152; doi:10.1198/073500105000000063 | Data-snooping control across candidate models. | P5 | V |
| 38 | Diebold, Mariano (1995), *Comparing Predictive Accuracy*, JBES | doi:10.1080/07350015.1995.10524599 | Model vs market-price loss comparison. | P3, P5 | V |
| 39 | Politis, Romano (1994), *The Stationary Bootstrap*, JASA; Cameron, Gelbach, Miller (2008), *Bootstrap-Based Improvements for Inference with Clustered Errors*, REStat | doi:10.1080/01621459.1994.10476870; doi:10.1162/rest.90.3.414 | Block and cluster bootstrap. Many decision points share one contract outcome, so the effective sample size is about the number of contracts, not the number of rows. | P3, P5 | V |
| 40 | Howard, Ramdas, McAuliffe, Sekhon (2021), *Time-uniform, nonparametric, nonasymptotic confidence sequences*, Ann. Statist.; Waudby-Smith, Ramdas (2024), *Estimating means of bounded random variables by betting*, JRSS-B; Ramdas, Grünwald, Vovk, Shafer (2023), *Game-theoretic statistics and safe anytime-valid inference*, Stat. Sci. | arXiv:1810.08240; arXiv:2010.09686; arXiv:2210.01948 | Always-valid monitoring of edge and calibration. Supports defensible RED/YELLOW triggers. | P8, P11 | V |
| 41 | Page (1954), *Continuous Inspection Schemes*, Biometrika | doi:10.1093/biomet/41.1-2.100 | CUSUM drift and change detection. | P8 | V |

### E.5 Sizing, ruin, overround, advantage play

| # | Citation | Locator | Relevance to PMV | Phase | St |
|---|---|---|---|---|---|
| 42 | Kelly (1956), *A New Interpretation of Information Rate*, BSTJ | doi:10.1002/j.1538-7305.1956.tb03809.x | Kelly. | P4.5 | V |
| 43 | Baker, McHale (2013), *Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion*, Decision Analysis | doi:10.1287/deca.2013.0271 | Shrunken Kelly under estimation error. Directly maps to uncertainty-adjusted sizing. | P4.5 | V |
| 44 | Thorp (2006), *The Kelly Criterion in Blackjack, Sports Betting and the Stock Market*, Handbook of Asset and Liability Mgmt; MacLean, Thorp, Ziemba (eds., 2011), *The Kelly Capital Growth Investment Criterion*, World Scientific | (books; DOIs not checked) | Card-counting origin of Kelly, fractional Kelly, drawdown properties. | P4.5 | S |
| 45 | Shin (1993), *Measuring the Incidence of Insider Trading in a Market for State-Contingent Claims*, Econ. J.; Štrumbelj (2014), *On determining probability forecasts from betting odds*, IJF | doi:10.2307/2234240; doi:10.1016/j.ijforecast.2014.02.008 | Margin removal. For a binary YES/NO book, the "overround" is effectively the bid-ask spread plus fees. Shin-style de-biasing is a candidate market-implied-probability baseline. | P3 | V |
| 46 | Asmussen, Albrecher (2010), *Ruin Probabilities* (2nd ed., World Scientific) | (book) | Ruin theory for the Gate 4.5 risk-of-ruin analysis. | P4.5 | S |

### E.6 Open-source software (documentation and metadata only; nothing installed or run)
Metadata is from the GitHub API on 2026-10-16.

| Project | License | Maintenance (last push) | Fit for PMV | Risks |
|---|---|---|---|---|
| QuantLib (lballabio/QuantLib) | QuantLib license (BSD-style; GitHub shows NOASSERTION) | active 2026-10-15 | Digital/Asian option pricing references | C++ and heavy. Only a few formulas are needed, so reimplementing them may be simpler. |
| LEAN (QuantConnect/Lean) | Apache-2.0 | active | Event-driven backtest reference | No native Kalshi/Polymarket support. C#. Cloud-oriented ecosystem. |
| vectorbt (polakowo/vectorbt) | Apache-2.0 **with Commons Clause** (NOASSERTION) | active | Fast vectorized research sweeps | Commons Clause restricts commercial use (verify). Vectorized fills hide execution realism. |
| Backtrader (mementum/backtrader) | GPL-3.0 | stale (2024-08) | Not recommended | Unmaintained, and GPL obligations. |
| NautilusTrader | LGPL-3.0 | very active | Production-grade event-driven engine. A Polymarket adapter exists per the project docs (UNRESOLVED here). A candidate reference for the Phase 9 architecture. | LGPL linkage terms. Large dependency surface. |
| hftbacktest (nkaz001) | MIT | 2025-12 | Queue-position- and latency-aware L2/L3 replay. The best fit for fill realism on recorded books. | Single maintainer. Crypto-venue oriented, so needs adaptation to binary books. |
| mlfinlab (Hudson & Thames) | proprietary / commercial (NOASSERTION; public repo stale 2023) | — | Purged CV reference only | License does not allow free use. Do not use. |
| timeseriescv (sam31415) | MIT | stale 2022 | Purged/combinatorial CV, small and readable | Unmaintained. Vendor or reimplement with tests. |
| skfolio | BSD-3-Clause | active | Has CombinatorialPurgedCV (per its docs, UNRESOLVED here) | Portfolio-oriented. |
| pypbo (esvhd) | **AGPL-3.0** | 2026-07 | PBO/CSCV reference | AGPL is incompatible with closed production use. Reimplement the formulas instead. |
| properscoring | Apache-2.0 | **archived** | Brier/CRPS | Archived. Prefer scoringrules or sklearn. |
| scoringrules (frazane) | Apache-2.0 | active | Proper scoring rules | Young project. |
| netcal (EFS-OpenSource/calibration-framework) | Apache-2.0 | 2026-04 | Calibration methods, ECE, reliability diagrams | Large dependency tree (torch). |
| betacal (betacal/python) | MIT | 2024 | Beta calibration (#32) | Tiny and lightly maintained. Trivial to reimplement. |
| venn-abers (ip200) | MIT | active | Calibration with validity guarantees | Niche. |
| confseq (gostevehoward) | MIT | 2026-01 | Confidence sequences (#40) for monitoring | Small. C++ core. |
| ruptures | BSD-2-Clause | active | Offline change-point detection for drift research | Offline only. Online CUSUM should be reimplemented. |
| arch (bashtage) | NCSA (NOASSERTION) | active | Stationary/block bootstrap, SPA test, volatility models | Good fit. |
| jon-becker/prediction-market-analysis | MIT | active | Kalshi/Polymarket indexers (reference) | Unknown correctness. Review before reuse. |

---

## F. Regulatory and reference sources (ranked by relevance)

| Rank | Source | URL | Why it matters to PMV | Status |
|---|---|---|---|---|
| 1 | CFTC: KalshiEX designated as a contract market (Nov 2020) | https://www.cftc.gov/PressRoom/PressReleases/8302-20 | The legal basis of the Kalshi venue | VERIFIED-BY-DOC (page title) |
| 2 | CFTC 2026 event-contract rulemaking track: ANPRM on prediction markets (Mar 12, 2026); Part 40.11 NPRM (Jun 10, 2026); event-contract swap-definition NPRM (Oct 9, 2026); withdrawal of the 2024 proposal (press release 9179-26) | https://www.cftc.gov/PressRoom/PressReleases/9194-26, …/9249-26, …/9310-26, …/9179-26 | Product-listing and reporting rules may change during the project. Re-verify before Phase 12. | VERIFIED-BY-DOC (titles and dates). Contents read only via search summary. |
| 3 | CFTC staff and enforcement prediction-markets advisories (Mar 2026) | https://www.cftc.gov/PressRoom/PressReleases/9193-26 (and 9185-26) | Manipulation and insider-trading enforcement posture (see #4 in E.1) | VERIFIED-BY-DOC (title, 9193-26) |
| 4 | CFTC 2022 Polymarket (Blockratize) order, $1.4M penalty | https://www.cftc.gov/PressRoom/PressReleases/8478-22 | Basis of the international Polymarket US-person restriction. QCX/Polymarket US is a separate DCM (Sept 2025 no-action letter, per secondary sources). **Account and jurisdiction eligibility for Polymarket international vs Polymarket US is a blocking venue question for the venue agent.** | VERIFIED-BY-DOC (title). QCX facts are secondary (S). |
| 5 | Scheduled macro release calendars: BLS (CPI, employment), BEA (GDP, PCE), FOMC meeting calendar | https://www.bls.gov/schedule/news_release/ (403 anti-bot); https://www.bea.gov/news/schedule (200); https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (proxy refused) | Hypothesis H-macro: gold (and to a lesser degree BTC) short-horizon volatility jumps at scheduled 08:30/10:00/14:00 ET releases (#27). Time-to-next-release and in-window-release flags are **ex-ante-known** features that need no outcome data. Store release-time schedules only, not released values. | partial |
| 6 | FRED/ALFRED release-dates API (vintage-aware) | https://fred.stlouisfed.org/docs/api/fred/releases_dates.html (connection did not complete); alfred.stlouisfed.org (proxy refused) | Machine-readable historical release timestamps. ALFRED gives point-in-time vintages if released values are ever used (lookahead-safe). | UNRESOLVED |
| 7 | CFTC Commitments of Traders (COMEX gold) | https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm (200); publicreporting.cftc.gov (proxy refused) | Weekly positions (Tuesday as-of, Friday release). Too coarse for 15m–1h, so a regime covariate at most. Release-lag discipline is required. **Low priority.** | VERIFIED-BY-DOC (page reachable) |
| 8 | eCFR 17 CFR 40.11 (event contracts) | https://www.ecfr.gov/current/title-17/chapter-I/part-40/section-40.11 (proxy refused) | Rule text | inaccessible |
| 9 | NFA | https://www.nfa.futures.org/ (200) | Relevant only if PMV ever operates through an FCM or IB. Low priority. | reachable |

The SEC appears to matter only through the joint CFTC–SEC crypto-asset statement (press release 9198-26, title only). No PMV-specific SEC hypothesis was identified, so it is not padded here.

---

## G. Incidental exposure (no values recorded anywhere in PMV files)

- **G-1.** The DegenHedge/kalshi-btc-15m README contains headline aggregate outcome statistics of a vendor signal record on KXBTC15M (Jan–Oct 2026). Incidental exposure: that README, no values recorded.
- **G-2.** A WebSearch result summary quoted third-party aggregate performance and calibration claims on KXBTC15M (quanterraos.com, botforkalshi.com, turbinefi.com). Incidental exposure: search summary, no values recorded. Those pages were not opened.
- **G-3.** Paper abstracts (arXiv 2607.26245, 2606.04217, 2604.24366, 2608.00666, 2605.31431) and search summaries of Kalshi's calibration paper contain aggregate statistics over 2021–2026 market data. Treated as literature. No values recorded.
- **Assessment:** all of the above are aggregates over periods before 2026-10-16, and none is a per-observation value. Under the owner direction (historical data is development-only; holdout is prospective), they do not contaminate a prospective protected window. They are recorded so that the first real protected scope starts after 2026-10-16. No contamination event appears warranted. The owner should decide whether to log G-1/G-2 in HOLDOUT_ACCESS_LOG.md as a precaution.

---

## Ranked recommendations (evidence-based; none is an approved requirement)

1. **R-1. Polymarket trades: use the on-chain fill archive (D-P1), verified against Polygon RPC.** Use it for development of the Polymarket crypto up/down trade-flow and outcome studies. Prefer re-derivation from chain (primary) over any packager. Use packagers only as cross-checks. Remember that block time is not decision time.
2. **R-2. Kalshi trades: use D-K1/D-K2 as development cross-checks, not primary sources.** The primary should be Kalshi's own historical endpoints (venue agent). Never use the "at time of fetch" quote fields as history. Use the DegenHedge `windows` table only to check settlement and strike reconstruction.
3. **R-3. Pin every open dataset before anyone reads it.** Record the HF revision SHA (listed above). Apply a fixed UTC development cut-off in the owner-run release tool (Step 11 F-08) before agent exposure, because several datasets update continuously into the present.
4. **R-4. Historical depth: three candidates.**
   - pmxt (via Joseph3222) and aliplayer1 for Polymarket, to be evaluated only after a gap and clock audit run by deterministic tooling.
   - No open multi-month Kalshi depth exists.
   - **Prospective capture remains the only defensible depth source for Kalshi and for any holdout.**
5. **R-5. Read OpenMarket (#3) and Lee et al. (#2) before Phase 3 design.** #3 is a public null result on essentially the PMV hypothesis. PMV's baseline must include "the market's own book-implied probability". Beating that baseline after fees is the real bar.
6. **R-6. Do not use** the following, because of redistribution or provenance problems:
   - Cryptolake mirror (D-B2), OANDA mirror (D-G2), and papylove (D-K4) until provenance is known;
   - all broker XAU/USD tick sets except as auxiliary proxies;
   - the DegenHedge `signals` table;
   - mlfinlab and pypbo code.
7. **R-7. Gold is a data gap.** Recommend escalating to the owner: open data cannot support gold development. Decide between licensed CME/vendor data and capture-only (fewer historical samples).
8. **R-8. Build the macro release-time calendar (F-5/F-6)** as an ex-ante feature source. Times only, no values.
9. **R-9. Software:** hftbacktest (MIT) and NautilusTrader (LGPL) as execution-realism and architecture references. arch (bootstrap/SPA), scoringrules/sklearn (scoring), and confseq (monitoring) are suitable dependencies after review. Reimplement purged CV, PBO, and DSR with tests rather than importing unmaintained or AGPL code.

## Inaccessible sources
- archive.pmxt.dev: refused by the sandbox proxy.
- www.ecfr.gov, www.federalreserve.gov, alfred.stlouisfed.org, publicreporting.cftc.gov: refused by the proxy.
- fred.stlouisfed.org/docs: connection did not complete (the root returned 200).
- www.bls.gov: HTTP 403 anti-bot. Not bypassed.
- kalshi.com research PDF: not attempted (kalshi.com is bot-blocked, AR-3).
- zenodo.org API: intermittent rate-limiting and empty responses, so Zenodo discovery is incomplete.
- export.arxiv.org API: HTTP 429. arXiv abstract pages were used instead.
- AisotTechnologies card: gated (HTTP 401). Not requested.
- aliplayer1 pipeline GitHub repository: 404.
- SSRN and ScienceDirect pages: not fetched. Citations come from Crossref and search results.

## ACCESS REQUESTS
Each is a proposal only. No alternative route was tried.

| ID | Domain / resource | Purpose | Intended data | Recommendation |
|---|---|---|---|---|
| AR-D1 | archive.pmxt.dev (landing and documentation pages only) | Verify pmxt archive provenance, license, capture method, and coverage | Documentation only. No archive files. | Temporary (docs only). Later file acquisition must go through the owner-run release tool. |
| AR-D2 | www.ecfr.gov (17 CFR Part 40, 40.11) | Read the rule text for event contracts | Regulation text | Permanent (regulatory reference, no market data) |
| AR-D3 | www.federalreserve.gov (FOMC calendars page) | Ex-ante macro-event schedule for H-macro | Meeting dates and times only | Permanent |
| AR-D4 | fred.stlouisfed.org/docs and api.stlouisfed.org; alfred.stlouisfed.org | Release-dates API docs and later deterministic retrieval of release timestamps | Release dates and times. Vintages only under the guard. | Docs temporary. API access is a later data-access decision. |
| AR-D5 | publicreporting.cftc.gov (COT Socrata docs) | COT schema and release-lag semantics | Documentation only | Temporary. Low priority. |
| AR-D6 | www.bls.gov (release schedule) | H-macro schedule | Schedule only | The 403 is a site anti-bot control. Do not bypass. The owner could download the schedule manually, or BEA/FRED could substitute. |
