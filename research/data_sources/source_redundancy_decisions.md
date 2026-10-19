# PMV source redundancy decisions and minimum viable source set (B10, 2026-10-19)

**Status: evidence-based recommendations, not approved requirements.** These verdicts are reconnaissance results. They approve no acquisition, purchase, licence, capture, or connector. Every acquisition still needs per-source owner approval and the gate A-1 to A-8 (`docs/external_access.md` §2). The licence outreach M1 to M5 (`owner_source_action_sheet.md`) still governs whether any source is usable.

**What B10 can and cannot establish.** It can establish information availability, uniqueness, reconstructibility, engineering cost, timing fidelity, and settlement fidelity. It **cannot** show that any feature or source improves calibration or net EV. Every source whose value depends on predictive usefulness stays CONDITIONAL until it passes the normal development walk-forward process. A promotion test is one more degree of freedom: it is logged in the experiment ledger, its comparison and threshold are fixed before it runs, and it uses development data only (never the protected holdout).

Inputs: `source_feature_value_matrix.md`; `schema_profiles/*.md`. Revised after the B10 reviews (`research/governance/b10_reviews.md`).

## Promotion-test protocol (applies to every CONDITIONAL source)

Proposed; owner decision B10-D8 adopts it and sets the numbers. Each promotion test is preregistered in the experiment ledger before any look at its outcome, and states:
1. **One primary estimand.** For example, Δ tail log loss in fixed probability × remaining-time strata, or net EV at the primary H-5 latency rung. Secondary metrics are reported, never decisive. No OR-logic across metrics.
2. **A minimum effect δ and decision rule.** A block-bootstrap (by day) lower confidence bound against δ.
3. **A power and minimum-detectable-effect statement** for the planned development span, using distinct settlement instants or days as the unit (not markets: overlapping series share settlement instants).
4. **Three outcomes:** PROMOTE, REJECT, or UNDERPOWERED-DEFER. An underpowered test never silently becomes a permanent DROP.
5. **An error-rate budget** (FWER or FDR) across all promotion tests. The Databento depth ladder (TBBO → MBP-1 → MBP-10 → MBO) and the Kraken book family each count as **one** family.
6. **A ledger entry for every look**, counted as development-pool degrees of freedom (`docs/phase2.md`).

**Relation to S-9 (`docs/phase2.md`).** Promotion is an **acquisition decision only**. Archive-validated results are discovery evidence; any feature from a promoted source still needs the receipt-time (RECEIPT + PIT_CAPTURED) selection comparison before it can enter an audit candidate. Consequence: a reference source (BRTI or Pyth) can enter a cycle-1 candidate only if PMV captures it prospectively, with power, before `T0 − m`. The Kalshi CFB and `pyth_value` channels are live-only, so deferring them decides by default that cycle 1 cannot use them. That is an explicit owner decision (B10-D9), required before cycle registration.

## Verdict definitions

| Verdict | Meaning |
|---|---|
| CORE | Needed now: it provides important information unavailable with adequate fidelity from cheaper or core sources |
| CONDITIONAL | It provides unique information, but its incremental predictive or economic value has not been demonstrated |
| REDUNDANT | Its useful fields can be reconstructed adequately from another retained source |
| DROP | Its expected incremental value does not justify cost, licensing, engineering, synchronization, or storage complexity |

## Verdicts

### Prediction market

| Source / dataset | Verdict | Reason |
|---|---|---|
| Kalshi series/events/markets metadata (live and `/historical/markets`), fee-change history, contract terms (owner download) | **CORE** | Labels (`result`), contract semantics, reference-end time, strikes, fees for break-even, and the realized reference (`expiration_value`). Nothing else carries them |
| Kalshi historical trades (`/markets/trades`, `/historical/trades`) | **CORE** | Prediction-market trade flow and aggressor side. Dedupe by `trade_id` across the live/historical cutoff |
| Kalshi 1-minute candlesticks (live and historical) | **CORE** | The `yes_bid`/`yes_ask` OHLC and `open_interest` are the only historical quote and OI evidence. Needed for coarse executable-ask estimates in development. The candle's trade-price OHLC, VWAP, and volume are REDUNDANT with trades (QA only), but come in the same response |
| Kalshi WebSocket `orderbook_delta` + `trade` + `market_lifecycle_v2`, PMV capture | **CORE** (prospective; capture needs its own authorization) | The only source of Kalshi L2, quoted size, and receipt time, and of protected prospective evaluation data |
| Kalshi WS `ticker` | **REDUNDANT as a feature source; capture as an integrity cross-check** (revised after reviews S-B10-08, API-B10-11) | Its best bid/ask is derivable from book + trades, and it is unsequenced. But it carries `open_interest_fp`, `dollar_volume`, and `dollar_open_interest`, which are not derivable at tick resolution. Kalshi books have no checksum, so `ticker` is the only independent live check of the reconstructed book. Live only; cheap |
| Kalshi REST order-book snapshots | DROP as a research series; **keep as a reconciliation probe** | Current state only, no timestamp, no sequence: cannot be aligned to the stream. Periodic reads bracketed by PMV receipt times, in quiet periods or after a resync, are a second check of book reconstruction |
| Kalshi WS `cfbenchmarks_value(_5hz)` and `pyth_value` channels | CONDITIONAL | See BRTI and Pyth below. Possibly the cheapest faithful reference capture, pending entitlement price and rights (M1) |
| Polymarket (Gamma, CLOB, Data API, market WS, Chainlink stream) | CONDITIONAL, **deferred** | Another crowd's estimate of a nearly identical event on a different reference (Chainlink TWAP vs BRTI). US persons are close-only. No historical book. Terms not read |

**Polymarket promotion experiment.** Only after Kalshi-only research passes the M-0 go/no-go (D-B09-18): with PMV-captured Kalshi and Polymarket data over the same windows, test whether cross-venue features (Polymarket mid minus Kalshi mid; lead-lag of mid changes) improve walk-forward late-window calibration (tail log loss, reliability of the top probability bins) and net EV beyond Kalshi + underlying features. Fix the test before it runs; log it as a degree of freedom. A reference-basis gap (Chainlink vs BRTI) is a cross-venue trading question, not a prediction feature; it needs its own economic and eligibility review.

### BTC

| Source / dataset | Verdict | Reason |
|---|---|---|
| Kraken downloadable trade archive (`Kraken_Trades_Full` + quarterly increments) | **CORE, conditional on timestamp precision** | The full free BTC tape since the first trade, with side (taker side inferred), taker order type, and `trade_id` (support article, 2026-10-12; corrects B09). Archive timestamp precision is UNKNOWN: if it is integer seconds, final-minute velocity and window alignment degrade, and REST `Trades` paging (sub-second; about 9 months at about 1 call per 1–2 s is feasible) becomes the primary path for the development span |
| Kraken REST `Trades` | REDUNDANT as a source; keep as a **delivery path** | Same upstream and fields as the archive. Use it only to fill from the archive cutoff to the present, and to reconcile. The cursor repeats one trade per page: dedupe by `trade_id` (B10 finding) |
| Kraken OHLCVT (archive and REST) | **REDUNDANT** | Every field is a deterministic function of trades. Keep one quarterly OHLCVT increment as a **QA reference** to validate bars rebuilt from trades. Do not make it a research dependency |
| Kraken WS v2 `trade`, PMV capture | **CORE** (prospective) | Receipt-time-true trade flow. Also the production runtime's live BTC input |
| Kraken WS v2 `book` (L2, **depth 10 preferred**), PMV capture | CONDITIONAL for **use**; **recommend capture** alongside `trade` | Spread, depth, imbalance, microprice, and queue changes are not derivable from trades. Kraken has no historical L2, so this information cannot be obtained later. The CRC32 checksum verifies the **top-10 state** at each message (176/176 in B10). It does not verify event-stream completeness, levels beyond 10, or stalls (review API-B10-01; capture requirements in `kraken_l2.md`). Conditions for capture-but-not-use (review S-B10-10): non-use is enforced by release controls and logged access; a separate connection, or proof that book volume cannot cause backpressure on the CORE trade channel; top-10 tagged as verified. Pre-`T0 − m` capture is unlikely to power a tail test, so L2 realistically serves cycle 2 |
| Kraken `level3` | DROP | Needs an authenticated API credential (a new secret surface) for marginal value at this horizon |
| CF Benchmarks BRTI (direct licence or Kalshi CFB channel) | CONDITIONAL | Expected unique value (untested): **settlement fidelity** (the exact level in settlement units, the venue-to-index basis, and how much of the final-minute average is already realized). Relative to Kraken alone, BRTI also aggregates multi-venue price discovery, so 'not a new velocity signal' holds only when all constituents are retained (review S-B10-09) |
| Tardis.dev (historical Kraken L2, quotes, `local_timestamp`) | CONDITIONAL | The only economical **historical** BTC book and vendor receipt time. Archive-class data: discovery and training only under S-9. Book features must be truncated to PMV's live depth (Tardis records depth 1000) for training/serving parity. It does not add aggressor side (the free archive has it) and has no Kraken L3. **New licence question:** clause 9.5 excludes LLMs and requires written flow-down terms before disclosure to an "external service provider", including for free samples. This conflicts with PMV's agent-assisted development unless resolved |
| Coinbase (public API and licensed data) | **DROP** (for now) | Ordinary terms need prior written consent for ML use. No free history. The maker-side convention is a correctness hazard. Its unique contributions (largest BRTI weight; cross-exchange lead-lag) are **untested**. The BRTI test addresses only the reference-fidelity part; the cross-venue information experiment below addresses the rest. The loss of live-only Coinbase L2/L3 is recorded as accepted |

**BRTI proxy measurement and promotion experiment (free, development data only; revised after reviews S-B10-01, -02, -06, -12).**

*Part A: model-free proxy-error measurement, run **before** M-0 as an M-0 interpretability precondition.*
1. Fix the proxy construction before looking at any `expiration_value`: the rulebook regime per date (300 s average; trimmed 60 s mean from 2024-11-27; plain 60 s mean; CRYPTOSHORT), tick handling, and the no-data rule (DET-2).
2. Define the error **per contract type**:
   - up/down series (close average vs open reference): the **differential** error (basis drift over the window), because a constant Kraken–BRTI basis cancels. The legal decision-time proxy is "Kraken close average + (published strike − Kraken open average)", if DET-2 confirms that the strike is the BRTI open average;
   - fixed-strike or range series (for example KXBTCD): the **level** error.
3. Test the point-in-time availability of the strike (`floor_strike`): historical REST metadata is POST_HOC under H-4, and `metadata_updated` can change strikes.
4. Express the error in units of σ·√τ for the ≤1-minute and 1–2-minute remaining-time bands, conditioned on the strategy-relevant region (candidate probability band × remaining-time band), not on all markets.
5. Dependence: the unit is the distinct settlement instant (15-minute and hourly series share instants; one window's close average is likely the next window's strike). Block-bootstrap by day. Stratify by rulebook regime and BRTI constituent changes (2024-11-27, 2025-03/07, 2026-07/08).
6. Any bias correction is estimated walk-forward from settlements already published (after `settlement_ts`) before the decision. Never fit it over the full span.

*Preregistered consequence for M-0 (proposed amendment to D-B09-18 K2; owner decision B10-D8).* If the measured differential error exceeds a fixed bound (in σ·√τ units, set before Part A runs), an M-0 failure is recorded as **UNINFORMATIVE**, not FAILED. K2 then permits a BRTI route (the Kalshi CFB channel, or a licence) instead of stopping the project on a measurement artifact.

*Part B: promotion test, run alongside M-0.* Promote BRTI to CORE if replacing the proxy with the exact reference improves the primary estimand (protocol above) by at least δ. Part B needs the reference itself, so it can run only on captured CFB data or licensed history.

**Cross-venue information experiment (new; review S-B10-09).** Whether multi-venue price discovery (BRTI itself as a feature, or a second constituent such as Coinbase, Bitstamp, or Gemini) adds information beyond Kraken alone is untested. Run it on PMV-captured Kalshi CFB data, or on a licensed second constituent, under the protocol above. As a replacement path if the Kraken-only proxy fails, assess the licence and history of one or two further free BRTI constituents (Bitstamp, Gemini, Bullish, Crypto.com, LMAX) before any Coinbase consent request.

**Tardis promotion experiment (revised, review S-B10-10).** Only if (a) a prospective test of Kraken book features on PMV-captured L2 ends **UNDERPOWERED-DEFER with a promising point estimate**, so that more history is needed for discovery and training, or (b) latency and staleness rules need historical receipt-time evidence before PMV capture is long enough; **and** (c) the clause 9.5 and external-service-provider question is resolved in writing. Tardis data serve discovery and training only (archive class under S-9); selection still runs on receipt-time folds. Book features are truncated to PMV's live depth. Smallest slice: Spot plan, quarterly.

**Coinbase reconsideration.** Only if the BRTI test fails and BRTI cannot be licensed. Then test whether a Kraken + Coinbase proxy closes the error, under written Coinbase consent.

### Gold

| Source / dataset | Verdict | Reason |
|---|---|---|
| Databento GLBX.MDP3 `trades` for GC and MGC | **CORE** (for the gold track) | COMEX is expected to be where intraday gold price discovery happens (an expectation, not tested here): price, size, aggressor side, `ts_event`, `ts_recv`. Cheapest schema (48 B per trade). Use explicit contracts or `GC.v.0`/`MGC.v.0`, not `c.0` alone |
| Databento `definition` + `statistics` (+ `status`) | **CORE** (small) | Contract identity, expiry, tick, and multiplier; roll handling; settlement and open-interest statistics (key causal use on `ts_recv`); session state |
| Databento `tbbo` or `bbo-1s` | CONDITIONAL | Top of book at trades (TBBO) or on a time grid (BBO). Promote only if spread or touch features are hypothesized and a trades-only gold model shows that quote state is needed |
| Databento `mbp-1` | CONDITIONAL | Every top-of-book event between trades. Promote only if TBBO/BBO is shown to be insufficient for a hypothesized quote-dynamics feature |
| Databento `mbp-10`, `mbo` | CONDITIONAL (low priority) | Promote only if top-of-book features show meaningful incremental out-of-sample value and depth features then add more. MBO (with snapshots) derives MBP-10 locally, so if depth is ever needed, buy MBO and derive, not both |
| Databento `ohlcv-*` | REDUNDANT | Derivable from trades. Note: bar `ts_event` is the bar **start**, so a bar is usable only after its end |
| CME DataMine (direct) | **DROP** | Same CME MDP3 data as Databento through a costlier, unreachable delivery path. Its DataMine-only items (volume by type, block-trade records, official EOD settlement files, PCAP) are not needed for 15–60 minute research |
| Pyth gold (Pyth Pro history, or Kalshi `pyth_value` capture) | CONDITIONAL, **high priority after DET-1** | A different economic object: a publisher-median spot reference "derived from futures". If Kalshi gold settles on it, labels and distance-to-strike live in its units. COMEX alone leaves a carry and roll basis, and no feature source during the CME daily break and at weekends while the GOLD index runs 24/7 |
| Databento live (Standard plan) | CONDITIONAL | Needed only once the gold track shows an edge and moves toward shadow or live runtime |

**Pyth promotion experiment (revised, review S-B10-07).** After DET-1 names the feed and rule:
1. Preregister detection of stale-reference windows (Pyth carries prices forward when markets are closed or publishers are too few: use `feedUpdateTimestamp` and `marketSession`) and their treatment (exclude, or a separate stratum) **before** analysis. With "at or above" ties, a stale start and end fix the outcome mechanically and would inflate high-confidence calibration.
2. Using development-period Kalshi gold `expiration_value` (the settlement statistic at settlement instants), estimate the COMEX-to-reference basis walk-forward from settlements already published. For up/down contracts, use the **differential** basis (drift over the window); for fixed-strike contracts, the level basis.
3. Express the implied distance-to-strike error in σ·√τ units against a numeric threshold fixed in advance, and measure the effect on the primary estimand.
4. Attach a power statement. KXGOLD15M reportedly launched about 2026-08 and the GOLD index (3153) has existed only since about 2026-06 (SECONDARY), so the likely outcome is **UNDERPOWERED-DEFER**, consistent with D-B09-21 (gold exploratory in cycle 1).

**Deeper Databento book promotion experiment.** Only if MBP-1/TBBO features fail to explain what a deeper-book hypothesis targets, and deeper-book features then show incremental walk-forward value on the primary estimand (protocol above; the whole depth ladder is one family) on development data.

## Irreversibility: information lost if not captured (review S-B10-08)

Recoverable later (can be bought or derived): Kraken OHLCVT, Databento OHLCV and deeper schemas, CME DataMine, Tardis history, BRTI licensed history (if CF Benchmarks sells it).

| Live-only information | Current verdict | If not captured |
|---|---|---|
| Kalshi L2, quoted size, receipt time (WS book) | CORE capture (P1) | Lost permanently |
| Kalshi `ticker` (tick-level OI, dollar volume, independent BBO check) | Capture as integrity cross-check (P1) | Lost permanently |
| Kalshi CFB and `pyth_value` channels (reference as Kalshi receives it, with `received_at`) | CONDITIONAL; capture decision B10-D9 before cycle registration | Lost permanently; cycle 1 cannot use reference features or audit protected labels against them |
| Kraken L2 book | Capture recommended (P2) | Lost permanently (Tardis sells history only from its own collector) |
| Polymarket books and sub-minute prices (1-minute history ages out after about 7 days) | Deferred | Lost permanently; **accepted cost** |
| Kraken `level3`; Coinbase L2/L3 | DROP | Lost permanently; **accepted cost** |

## Minimum viable source set (recommendation)

Optimized against vendor count, duplicated information, paid feeds, connector count, cleaning complexity, synchronization, timestamp ambiguity, storage, and model degrees of freedom. Not optimized for data volume.

### Stage 1: BTC hypothesis test (free once licensed; M1 Kalshi, M2 Kraken)

| # | Dataset | Exact scope | Connector |
|---|---|---|---|
| 1 | Kalshi markets/events/series metadata + fee changes | BTC 15-minute (and approved horizon) series; all settled markets in the development span, from the live and historical tiers | Kalshi REST pager (one connector for 1–3) |
| 2 | Kalshi trades | Same markets | same |
| 3 | Kalshi 1-minute candlesticks | Same markets (bid/ask OHLC, OI) | same |
| 4 | Kalshi contract terms | KXBTC15M (and siblings) rule text | owner download |
| 5 | Kraken trade archive, XBTUSD only | Development span, plus REST `Trades` gap fill to the archive cutoff | Archive file fetch (host `assets.kraken.com`) + REST pager |

That is two vendors, two historical connectors, zero paid data. It can run an **informative** M-0 go/no-go (D-B09-18) only if two conditions hold: the BRTI proxy measurement (Part A) bounds the proxy error, and the executable-price convention below is preregistered.

**Stage 1 executable-price convention (proposed; review S-B10-03; D-B09-18 permits M-0 at the ask only if candles give ask quotes at decision resolution).**
- Features use only candles with `end_period_ts` ≤ decision time (the live candle is mutable).
- The market baseline uses the freshest admissible prediction-market state: the close of the minute containing the decision. This is conservative against the model.
- The entry price is the **ask high of the next minute** (primary H-5 rung). The ask close is a diagnostic only.
- NO-side ask = 1 − YES bid, with high and low swapped.
- A second, size-bearing check: realized taker-buy prints (`taker_book_side`, `count_fp`), with their selection caveat.
- No capacity claim (quoted size is absent historically).
- The ≤1-minute remaining-time band is **not evaluable at the ask from candles** (at most one candle, overlapping the settlement averaging window). If this cannot be fixed, that band is reported at trade prices with the bias stated (S-B9C2-09).

**What Stage 1 cannot show, and bias direction (review S-B10-11).**

| Limit | Bias direction |
|---|---|
| Kraken-only proxy of BRTI (single venue) | Toward a false **no-go** (noise reduces sharpness in the operating region) |
| Stale 1-minute Kalshi baseline versus sub-second BTC features | Toward a false **go** (artificial under-reaction of the market baseline) |
| 1-minute ask; no quoted size | Toward a false **go** (fills at tail prices assumed); no capacity evidence |
| No receipt time (archive event time only) | Toward a false **go**; the H-5 latency ladder is mandatory |
| Kraken archive timestamp precision UNKNOWN | Degrades final-minute velocity if it is integer seconds |
| `is_provisional` markets can be removed from the API | Survivorship: inflates opportunity frequency |
| Kalshi history depth (about 2026-01 for 15-minute BTC, SECONDARY) | Low power; limited regime coverage |
| Development period inside the agent models' knowledge window (S-10) | Contamination risk for development choices, not for the holdout |

### Stage 2: gold track (after M3; exploratory in cycle 1 per D-B09-21)

| # | Dataset | Exact scope |
|---|---|---|
| 6 | Databento GLBX.MDP3 `trades` | GC and MGC, front and next contracts across rolls, development span (run the cost estimator first) |
| 7 | Databento `definition`, `statistics`, `status` | Same instruments and span |
| 8 | Kalshi gold metadata, trades, candles, contract terms | KXGOLD15M (existence and rule: DET-1) |

### Prospective capture (only when separately authorized; starts the protected-evaluation clock)

| # | Stream |
|---|---|
| P1 | Kalshi WS `orderbook_delta`, `trade`, `market_lifecycle_v2`, and `ticker` (integrity cross-check) for the approved series; optional periodic REST order-book reconciliation probes |
| P2 | Kraken WS v2 `trade` + `book` (depth 10 preferred) for BTC/USD (book captured, use CONDITIONAL; capture requirements in `kraken_l2.md`) |
| P3 | (Gold, later) Databento live trades, or Kalshi `pyth_value` once DET-1 and pricing allow |
| P4 | Kalshi CFB channel (and `pyth_value`): **owner decision B10-D9 before cycle registration**, because deferral excludes reference features from cycle 1 |

### Not worth acquiring yet

- Kraken OHLCVT full archive (one quarterly file for QA only);
- Tardis (any plan, including free first-of-month files, until the clause 9.5 question is answered);
- Coinbase data;
- CME DataMine;
- Databento `tbbo`, `bbo-*`, `mbp-1`, `mbp-10`, `mbo`, `ohlcv-*`;
- CF Benchmarks BRTI licence (request the quote only, M4);
- Pyth Pro;
- Kalshi CFB and Pyth WS entitlements (but see B10-D9: live-only; decide before cycle registration);
- Polymarket data of any kind;
- Kraken `level3`.

## Model degrees of freedom

The Stage 1 set yields a small, interpretable feature family:
- distance-to-strike and time remaining;
- BTC realized volatility and trade-flow velocity, all from one trade tape;
- Kalshi price, coarse ask, trade flow, and OI.

Each CONDITIONAL source adds feature families and therefore comparisons. Adding them only through logged promotion tests keeps the multiple-testing burden explicit (development pool degrees of freedom, `docs/phase2.md`).
