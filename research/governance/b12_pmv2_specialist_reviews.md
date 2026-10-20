# B12: PMV 2.0 strategy pivot, eight-specialist review (2026-10-20)

**Scope.** This is the owner-facing strategy assessment of the proposed "PMV 2.0" pivot. Each of the eight existing PMV roles reviewed it independently and read-only. The owner then approved PMV 2.0 with modifications (`docs/decisions/2026-10-20_b12_pmv2_strategy_pivot.md`). This file preserves the reviews' findings in Git, as a summary and not a transcript. It is development research, not a gate record.

**Evidence limits:**
- No Kalshi observation has been fetched.
- Every Kalshi liquidity, spread, depth, and opportunity-count figure is UNKNOWN.
- **Every fee-dependent number below uses an unverified illustrative taker formula, 0.07·P·(1−P) per contract.** It is not canonical (PV-21; DR-9). Numbers are INFERENCE or synthetic arithmetic unless labelled otherwise.
- No market data was read. Simulations used synthetic parameters only.

**Independence.**
- The Independent Statistical Auditor ran in a fresh context, in parallel with the others, without seeing their reports.
- The Red-Team disclosed that earlier Red-Team rounds shaped the capture and book-integrity controls it cited.
- No review is cognitively independent of the others in the Phase 6 sense: all are the same model family.

## Verdicts

On "Proceed with a limited PMV 2.0 BTC feasibility program" (not live trading):

| Role | Verdict | Defining conditions |
|---|---|---|
| Quant / Business Lead | GO WITH CONDITIONS | Old and new strategies as nested arms; fees and terms before any EV claim; the cost-floor test first; no maker fills credited; a capped, preregistered configuration set |
| Data Scientist | GO WITH CONDITIONS | Objective amended with the settlement model nested; executable labels mandatory (mid-only results never count); prospective capture as the critical path; a fixed grid with a multiplicity correction |
| Statistician | GO WITH CONDITIONS | Research only, on prospective capture; the settlement hypothesis kept as a competitor; cheap historical tests first; a preregistered estimand and trial budget; `T0` registration delayed until development capture exists |
| ML Engineer | GO WITH CONDITIONS | Two-stage target; no modeling until a perfect-foresight ceiling screen passes; execution claims stay "simulated, unvalidated" until Phase 12; the settlement strategy kept |
| API / Execution Engineer | GO WITH CONDITIONS | Objective text amended; capture only under the DR-8 gates; per-row release before agents analyze captured rows; no economic claim from history alone; fee schedule and terms supplied |
| Risk & Performance Engineer | GO WITH CONDITIONS | Worst-case-premium caps; a forced-flat cutoff; L2 capture before any exit-risk claim; preregistered kill criteria; banking as policy only |
| Reliability / Red-Team | GO WITH CONDITIONS | Development-only; no cycle or `T0`; the capture span designated development; P-5 before capture; the failure register created |
| Independent Statistical Auditor | GO WITH CONDITIONS (measurement only) | No modeling or P&L claims until falsification tests run; the old-strategy calibration test run in parallel as a control; preregistration; STOP accepted if the lead/lag edge is below round-trip cost |

**Shared prior.** The Auditor, the Quant / Business Lead, and the Red-Team each stated that both strategies are more likely than not to show no durable net edge at PMV's latency and cost.

## 1. The original settlement strategy

- **The payoff-ratio argument is misleading** (all statistical roles).
  - Expected value is `p_true − price − cost`, and the payoff ratio drops out of it.
  - The per-trade standard deviation √(p(1−p)) is small at high prices. At the same absolute edge, a 0.95 contract has a higher per-trade Sharpe ratio (≈0.051 at a 1-point edge) than a 0.50 contract (≈0.02).
- **The real problems:**
  - **Calibration precision equals the edge size** (dEV/dp = 1).
    - A 3-point tail error (estimate 0.97, truth 0.94) corresponds to a volatility ratio of Φ⁻¹(0.97)/Φ⁻¹(0.94) ≈ 1.21: a **21% error** in the 1–3-minute volatility forecast.
    - If volatility is 20% above the assumed level, a nominal 0.95 is about 0.915 (Statistician).
  - **Regime mixture.** If 90% of days carry a true 1-point edge and 10% are 1.5×-volatility shock days, the mixture EV is about −0.02¢ per trade.
  - **Sample size.** For a one-sided test at α = 0.05 and power 0.8, at a 0.95 entry, the independent settled trades needed are:

    | True edge | Trades needed (no clustering) |
    |---|---|
    | 2 points | ≈583 |
    | 1 point | ≈2,550 |
    | 0.5 point | ≈10,600 |

    At about 10 effective trades per day (assumed), a 1-point edge needs about 250 days, or more than 2 years at a design effect of 3.
  - **No stated edge source.** Neither strategy record states the hypothesized counterparty error. Late-window states are close to deterministic functions of public information (distance to strike, volatility, time remaining, and the observed part of the final-minute settlement average), which a B0 digital benchmark should price well. The Auditor rated this the largest conceptual gap.
- **Judgement.** Difficult, not statistically unrealistic, for edges of 2 points or more. Unrealistic for a first cycle at 0.5–1 point. The old strategy has never been tested. The Auditor judged it **more testable than PMV 2.0 with obtainable data**, because settlement labels and coarse candle asks exist historically.

## 2. PMV 2.0

- **Cost hurdle.** A round trip pays two legs. Illustratively, with a 1¢ spread, it costs about 4.5¢ near a price of 0.50 and about 1.7¢ at 0.95.
- **Moves versus cost.** Under a local Black–Scholes approximation, the 60-second executable move has a standard deviation of about 12–18¢ near the money and about 3–5¢ at 0.95. Near-the-money contracts move a lot, which is the proposal's real advantage.
- **Required skill.**
  - Trading only the top 5–20% of signals, the required correlation with the future move is about 0.1–0.5, i.e. a predictive R² of about 3–25% (Statistician, Auditor).
  - The only plausible mechanism at that strength is **stale-quote lag** of Kalshi quotes behind BRTI or Kraken. That is a race against market makers who probably quote off BRTI and multi-exchange feeds.
- **Exits create no EV.** In a zero-skill synthetic simulation, mean P&L equalled minus the costs under every stop, target, and timeout configuration (optional stopping). Exit rules only reshape the distribution.
- **Payoff symmetry is only partial.**
  - With a 5¢ stop, the 1st-percentile loss was −13 to −17¢: 2.5–3.4× the stop, from gaps, jumps, and exit fees.
  - Each 1¢ of slippage error per side moves EV by 2¢ per round trip.
  - A 5% exit-failure rate costs about 2.5¢ per trade, comparable to the whole plausible edge.
  - **The only guaranteed loss bound is premium at risk.**
- **Effective sample size.**
  - Within a contract, the effective sample is about (window length ÷ horizon), however densely rows are sampled.
  - Strikes in one event add about zero independent units.
  - The gain over the settlement design is about 2–5× (Auditor, Quant Lead), and 5–10× only under favorable dependence (Statistician). It is not the 100× suggested by row counts.
- **Multiple testing.** A realistic grid of horizons × entries × exits × stops × feature families × models × strata × side has 1,800 to about 115,000 configurations. With about 1,000 effective trials, the best result from pure noise has t ≈ 3.3.
- **Policy-dependent labels.** "E[P&L | policy]" labels change whenever a stop or target changes, which is a leakage and selection channel. Hence the recommended two-stage design (ML Engineer, endorsed by the Statistician and Auditor).
- **Historical untestability.** Kalshi has no historical order book, candles are 1-minute, and Kraken has no historical L2. A PMV 2.0 backtest built on candles would be unfalsifiable: any exit could be assumed filled at a candle extreme. The Auditor rated this BLOCKING for any such backtest claim.
- **Fill validation.**
  - Maker fills, queue position, adverse selection, and own impact cannot be validated before Phase 12.
  - Demo liquidity is documented as unrepresentative.
  - The holdout can therefore bound executable EV, not confirm it.
- **Calendar cost.** Both the development data and the protected data must come from prospective capture, roughly doubling the time to a holdout.

## 3. Execution mechanics

OFFICIAL DOCUMENTATION, as reported by the API / Execution review from `docs.kalshi.com` pages fetched 2026-10-20 and logged in `research/sources.md`. These are review findings, not yet verified into `research/kalshi/api_documentation_findings.md`.

- **Book.** A single unified book: selling YES is equivalent to buying NO at 1 − price.
- **Orders.**
  - V2 order creation offers `time_in_force` ∈ {`fill_or_kill`, `good_till_canceled`, `immediate_or_cancel`}, plus `post_only` and `cancel_order_on_pause`.
  - `reduce_only` is rejected unless the order is IOC.
  - There is no v2 market order.
  - Order groups support a rolling contract-limit auto-cancel.
- **Close.**
  - After `close_time`, every order operation, cancels included, is rejected (`MARKET_INACTIVE`).
  - `close_time` can move earlier.
  - No WebSocket event announces the scheduled close.
  - Exits are impossible during the Thursday trading pause.
- **Book visibility.** The book is aggregated by price level. Cancellations can only be inferred from negative deltas without a coincident trade. There is no book checksum.
- **Fees.** Fill messages carry `fee_cost` and `is_taker`. Fees are rounded up to $0.000001, with a rounding fee and a per-order accumulator. **The fee formula itself is UNKNOWN** (DR-9).
- **Open questions:**
  - `client_order_id` idempotency after a timeout;
  - cancel-on-disconnect;
  - netting behavior without subaccount netting.
- **Specification change.** The OpenAPI specification changed between 2026-10-19 and 2026-10-20 with no version bump (PV-20).

## 4. Data implications

| Category | Items |
|---|---|
| Mandatory, unchanged | Kalshi historical markets, settlements, candles, trades, fee changes; Kraken historical trades; the DR-9 fee schedule; terms |
| Mandatory, now the critical path | Prospective Kalshi book snapshots and deltas with `seq`, trades, and lifecycle events; Kraken book (checksum) and trades; all with PMV receipt times on one host clock |
| Newly important | The Kalshi `cfbenchmarks_value_5hz` channel (entitlement UNKNOWN); an order-latency measurement plan |
| Deferred | Tardis (Kraken book history only; conditional); Polymarket; Coinbase (pending BRTI evidence); BRTI licensed history (settlement-arm fidelity only) |

## 5. Code observations (ML Engineer, Red-Team)

- `src/pmv/market_data/books.py`:
  - continuity requires a venue sequence, so a Kraken book (CRC32, no sequence) would be permanently unusable until a checksum-continuity mode exists;
  - books are keyed by `ContractSpec`, so a spot book needs an instrument-spec abstraction;
  - `reconstruct_as_of` replays the whole prefix per call, which is O(N × decisions). A streaming engine is needed, with the batch reconstructor kept as its test oracle.
- `src/pmv/market_data/labels.py` is settlement-only. Keep it, and add executable labels.
- No live collector, execution, order-state, risk, sizing, or KILL code exists yet.
- The failure register is missing (`docs/failure_modes/` is empty).

## 6. Banking (synthetic simulations)

- **Banking creates no EV.** Under a positive edge, sweeps sharply cut expected P&L by truncating compounding (Risk & Performance: +603 to +184 in one configuration).
- **The protection comes from the static cap plus a finite loss budget.** The "owner sweep" and "static $100 cap" policies had near-identical loss tails.
- **Sweeps raise active-pool depletion frequency:**

  | Source | Without sweep | With sweep |
  |---|---|---|
  | Risk & Performance, zero edge | 0.42 | 0.49 |
  | Statistician, small edge | 40% | 73% |

  Ruin must therefore be defined on total strategy equity against the loss budget.
- **Replenishment is the dominant risk dial.** Under a negative edge, unlimited refills moved P(total loss > 20%) from 0 to 0.77 and doubled the expected loss.
- **Recommendations** (the owner preserved the L1/L2/L3 baseline and recorded the sub-steps only as PROPOSED):
  - 2–3× capacity sub-steps;
  - promotion weighted to measured round-trip capacity;
  - finite refills booked as losses;
  - a protected reserve floor the software cannot withdraw;
  - a high-water mark never reset by sweeps;
  - sweeps of finalized cash only;
  - a separate tax reserve;
  - no transfer permission on runtime keys;
  - the reserve held outside software reach.

## 7. Commercial

- **"1–2% daily" compounds to about 38× to 1,377× a year.** It is incompatible with any capacity-limited venue. Unanimous view: not a requirement (now PV-11).
- **Illustrative value** (1% net per trade, 20 trades a day, notional 25% of the pool):

  | Level | Annual value |
  |---|---|
  | L1 | ≈ $1.8k |
  | L2 | ≈ $18k |
  | L3 | ≈ $180k, only if capacity holds (UNKNOWN, doubtful) |

  - The cloud capture scenario M costs about $2.2k a year (`research/cloud/pmv_cloud_cost_model.md`).
  - L1 is a paid measurement stage, not a business.
- **Tax.** High turnover is especially exposed to classifications that treat gains and losses asymmetrically. The scenario must be modeled and verified by authoritative sources before any scaling.

## 8. Disagreements and how the owner resolved them

| Question | Positions | Owner resolution |
|---|---|---|
| Supersede the old strategy? | All roles kept it in some form. The Quant Lead and the Auditor: neither strategy "superseded" until evidence; run them as nested arms. The Data Scientist, ML Engineer, and Red-Team: superseded as primary, kept as a comparator. | Superseded as primary; kept as a nested arm and control (PV-2, PV-4) |
| Nested A→B→C or factorial ablation? | ML Engineer: factorial. Others: nested acceptable. | Factorial (PV-8) |
| Primary learned target | ML Engineer: two-stage. Data Scientist: fixed-horizon executable P&L. Red-Team: taker markout. | Two-stage (PV-5), taker-only baseline (PV-6) |
| Banking tiers | Most: 2–3× sub-steps. | Owner L1/L2/L3 baseline; sub-steps PROPOSED (PV-9) |

## 9. Fastest falsification tests (pre-registered in B12 where historical)

1. The fee schedule and terms (owner-supplied).
2. The historical cost-hurdle / perfect-foresight ceiling (B12 P15; stop condition S-1).
3. The historical old-strategy tail-calibration control (B12 C1, and C2/C3 when Kraken data exists).
4. Span D:
   - Kalshi quote reaction lag to Kraken and BRTI moves against PMV's measured latency, with a reversed-shift placebo;
   - depth persistence across latency;
   - exit fillability in the final minutes;
   - the zero-skill simulator check;
   - the day-level ICC.
