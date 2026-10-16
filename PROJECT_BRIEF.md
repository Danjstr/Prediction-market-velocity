# Project Brief: Prediction Market Velocity

This document is the source of truth for project requirements. Agents must not add strategy assumptions that are not supported here.

---

## 1. Mission

Build a production-quality autonomous quantitative trading system for short-horizon prediction markets, initially focused on Bitcoin and gold markets on Kalshi and Polymarket.

---

## 2. Critical Architectural Requirement: Agent Independence

The AI agents are temporary developers, researchers, reviewers, and auditors only.

The final trading system MUST operate completely independently of Claude, ChatGPT, all LLMs, and all agent frameworks.

There must be:
- no Claude call in the live trading loop;
- no LLM API call per prediction;
- no agent required to approve trades;
- no agent required for feature calculation;
- no agent required for prediction;
- no agent required for position sizing;
- no agent required for order placement;
- no agent required for monitoring or circuit breakers.

The agents' goal is to make themselves operationally irrelevant by encoding their work into:
- deterministic software;
- trained standalone machine-learning models;
- automated risk logic;
- automated execution;
- automated monitoring;
- automated pause/circuit-breaker logic.

**Test:** If every Claude account and agent disappeared after development, the finished software must continue operating normally.

---

## 3. Core Trading Hypothesis

- Focus on approximately 15-minute to 1-hour prediction markets for assets such as Bitcoin and gold.
- Do **NOT** build a sentiment-analysis strategy.
- The central research direction is short-horizon price velocity and related quantitative market dynamics.

**Key hypothesis:** entering partway through a prediction window may reduce the forecasting horizon.

| Market length | Entry point | Remaining horizon to forecast |
|---|---|---|
| ~15 min | ~8 min in | ~7 min |
| ~15 min | ~10 min in | ~5 min |

The model should continuously update as market information arrives.

**Objective:** find a small but repeatable positive expected-value edge. Even small profits per trade may compound if:
- the edge is real;
- transaction costs do not consume it;
- position sizing is conservative;
- the system survives losing streaks.

---

## 4. Model Output

Velocity prediction is an intermediate goal. The useful final prediction is:

> **P(contract resolves in our favor | information observable at decision time)**

### Potential quantitative inputs
- returns
- price velocity
- acceleration/deceleration
- realized volatility
- volatility change
- order-flow imbalance
- order-book imbalance
- bid/ask spread
- depth
- liquidity
- volume
- trade intensity
- distance from settlement threshold
- time remaining
- changes in prediction-market price
- cross-market quantitative information

**Rule:** No future information may enter the features.

---

## 5. Economic Edge

A statistically accurate predictor is not enough.

The system must evaluate whether the probability estimate creates positive expected value relative to the **executable market price** after accounting for:
- fees;
- spread;
- slippage;
- latency;
- execution uncertainty;
- model uncertainty.

The system should prefer conservative estimates.

---

## 6. Data

Collect as much relevant historical and live data as practical from:
- Kalshi;
- Polymarket;
- underlying Bitcoin markets;
- relevant gold/reference markets;
- other quantitative sources when justified.

Preserve raw market data whenever practical so events can be reconstructed and replayed.

Historical data alone may not contain enough resolution for 5–15 minute forecasting, so **high-frequency live data collection should begin as early as possible.**

### Verified existing historical data
PMV prefers verified existing historical data to waiting to regenerate equivalent observations. When a historical source's provenance, timestamp semantics, contract semantics, licensing, and quality are adequate, it is used for development, while prospective PMV capture accumulates genuinely untouched data in parallel. This preference never weakens provenance, licensing, point-in-time correctness, holdout integrity, or source-quality requirements. Historical data exposed to development can never later become protected holdout data. Owner record: `docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`.

### External resources
Agents may extensively reference:
- open-source code;
- academic research;
- public datasets;
- quantitative libraries;
- official exchange SDKs;
- open-weight models.

External work must be checked for:
- correctness;
- licensing;
- security;
- leakage;
- maintenance status;
- applicability.

---

## 7. Train / Test Design

Use a **chronological** split. Never randomly shuffle the time series.

| Segment | Share (approx.) | Purpose |
|---|---|---|
| Oldest | 70% | Development / training |
| Newest | 30% | Protected final out-of-sample holdout |

### Within the development 70%
Use rolling/walk-forward validation for:
- feature selection;
- model selection;
- architecture selection;
- hyperparameter tuning;
- probability calibration;
- strategy thresholds.

### Holdout protection
- The final 30% must remain untouched until the model and strategy are frozen.
- The final 30% must not become a repeatedly queried validation set.
- The split is frozen once as explicit immutable partition boundaries on an identified dataset snapshot. Approximately 70/30 is the design target; later-arriving data never moves the frozen boundaries.
- Opening the holdout requires explicit user approval for the specific frozen candidate, in addition to the technical release gates.
- Once outcome-dependent information from the holdout has been revealed, it is consumed and can never again serve as untouched data for a changed candidate.
- No observation may become protected evaluation data after its values, outcomes, or outcome-dependent derivatives have been exposed to development.
- Historical data from any source, once exposed to development, stays development data permanently. When development relies on historical data, the formation of the protected set (a quarantined, unexamined snapshot, or a prospective protected period) is decided for each cycle before any outcome-dependent inspection.
- Each holdout is evaluated once, against a preregistered evaluation plan with PASS, FAIL, and INCONCLUSIVE criteria. Any authorized evaluation that reveals outcomes consumes the holdout; only PASS permits the evaluated frozen candidate to continue.

### Leakage control
Use purging and/or embargo around temporal boundaries so that the following cannot leak information across the boundary:
- feature lookbacks;
- overlapping labels;
- 15-minute to 1-hour prediction horizons.

---

## 8. Model Families

Do not assume deep learning is automatically superior. Evaluate strong baselines as well as neural models.

Candidates may include:
- logistic/statistical models;
- gradient-boosted trees;
- temporal convolutional networks (TCN);
- CNN-based temporal models;
- GRU;
- LSTM;
- other justified sequence models.

Model selection should be based on:
- out-of-sample predictive performance;
- probability calibration;
- after-cost economic performance;
- latency;
- robustness;
- stability;
- operating cost;
- implementation complexity.

**The simplest model that produces the strongest reliable economic result should win.**

---

## 9. Risk Modulator

- Never bet all available capital.
- Confidence may increase position size, but **hard risk caps always override confidence.**
- A sequence of bad trades must not be able to wipe out the bankroll.
- The user's risk appetite — bankroll, starting capital, maximum drawdown, risk-of-ruin tolerance, any loss budget, and capital-scaling policy — is a user-approved input, not something optimized from historical returns.
- No real capital is committed before the limited live pilot, and then only with explicit user approval.

Research appropriate methods, including:
- fractional Kelly;
- uncertainty-adjusted Kelly;
- maximum per-trade exposure;
- total exposure limits;
- correlated-position limits;
- asset-specific limits;
- drawdown controls;
- risk-of-ruin analysis.

---

## 10. Advantage-Gambling Mathematics

The Statistician should understand mathematical ideas used by successful professional gamblers and advantage players, including:
- expected value;
- house edge;
- overround/vig;
- offered odds versus true probability;
- Kelly criterion;
- fractional Kelly;
- bankroll management;
- risk of ruin;
- variance;
- drawdowns;
- losing-streak distributions;
- Bayesian updating;
- sequential decisions;
- correlated wagers;
- line shopping;
- arbitrage;
- near-arbitrage;
- probability calibration;
- historical advantage-play concepts such as card counting.

The purpose is not gambling folklore. The relevant lesson is:

> Find measurable cases where true probability differs favorably from offered price, size exposure properly, preserve capital, and repeat.

---

## 11. Pause / Circuit Breaker

### Required controls
- manual PAUSE;
- manual KILL;
- automatic exposure reduction;
- automatic hard halt.

### Monitoring
Monitor live performance against frozen validation benchmarks. Metrics should include:
- realized net P&L;
- predicted versus realized edge;
- calibration;
- Brier score / log loss;
- rolling expected value;
- drawdown;
- feature drift;
- model-output drift;
- slippage;
- latency;
- fill quality;
- data-feed health;
- API health;
- order reconciliation.

### Halt discipline
- Do not halt merely because of a few random losses.
- Use statistically meaningful rolling windows, minimum sample requirements, confidence intervals, sequential/change-detection methods, or other defensible rules.

### Suggested states

| State | Behavior |
|---|---|
| GREEN | Normal operation |
| YELLOW | Reduced sizing |
| ORANGE | Only unusually strong opportunities |
| RED | Stop opening new trades |

- Technical uncertainty, such as stale data, broken feeds, corrupt features, unreconciled orders, or unknown state, should be capable of **immediately** triggering RED.
- Recovery from RED should require evidence of recovery and should not jump instantly back to full sizing.

---

## 12. Agent Team

| # | Role | Focus |
|---|---|---|
| 1 | Quant / Business Lead | profitability; economic viability; expected value; transaction costs; market selection; capital efficiency |
| 2 | Data Scientist | feature research; target construction; signal discovery; time-horizon research; walk-forward experiments |
| 3 | Statistician / Statistical Research Lead | statistical edge discovery; statistical method development; hypothesis and experiment design; repair or replacement of weak statistical approaches; testing proposed replacements; attacking false edges; statistical validity; uncertainty; calibration; leakage; dependence; effective sample size; multiple testing; regime analysis; risk of ruin; advantage-player mathematics; adversarial self-testing; constructive participation in Phase 4.5 risk-policy design; not the final independent auditor of work it materially helped create |
| 4 | Machine Learning Engineer | training pipelines; model architecture; production inference; reproducibility; model deployment; training-serving parity |
| 5 | API / Execution Engineer | Kalshi; Polymarket; historical data; WebSockets; order books; timestamps; authentication; rate limits; order submission; fills; cancellations; reconciliation; latency |
| 6 | Risk & Performance Engineer | position sizing; hard risk caps; drawdown controls; drift monitoring; circuit breakers; pause/kill logic; capital preservation |
| 7 | Reliability / Red-Team Engineer | extensive external research; finding gaps in final code; real-world failure modes; outages; network failures; stale/duplicate/missing data; clock drift; partial fills; ambiguous order state; restart recovery; corrupted state; dependency failures; extreme volatility; risk-control bypasses; failure injection; deployment-blocking issues |
| 8 | Independent Statistical Auditor | independent statistical validation; fresh-context review; review of prior independent-audit history; leakage; dependence; effective sample size; multiple testing; calibration; uncertainty; economic-edge credibility; sizing validity; drawdown and risk of ruin; holdout-protection compliance; independence disclosures; blocking statistical findings; development-time only, not a production runtime dependency |

---

## 13. Agent Development Principle

Agents are allowed to research, debate, review, write code, and test during development.

They must **NOT** become a dependency of production runtime.

Every successful agent contribution should ultimately become:
- code;
- model weights;
- tests;
- configurations;
- mathematical rules;
- monitoring;
- documentation.

---

## 14. Final Runtime Target

```
Market feeds
  → data validation
  → feature generation
  → standalone trained model
  → probability calibration
  → edge calculation
  → deterministic risk modulator
  → trade/no-trade decision
  → execution
  → reconciliation
  → performance/drift monitoring
  → automatic circuit breaker
```

**No LLM or agent inference is permitted or required anywhere in this production runtime chain.**

---

## 15. Success Criterion

The project is not complete merely because a backtest is profitable.

A successful system must:
- demonstrate credible out-of-sample edge;
- remain profitable after realistic costs;
- preserve capital under adverse sequences;
- execute reliably;
- detect degradation;
- halt safely;
- recover safely;
- operate independently of agents and LLMs.
