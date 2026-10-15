# Mission

Build a production-quality autonomous quantitative trading system for short-horizon prediction markets, initially focused on Bitcoin and gold on Kalshi and Polymarket.

# Source of Truth

PROJECT_BRIEF.md is the authoritative source of truth for project requirements.

If CLAUDE.md, an agent instruction, a research note, or implementation decision appears to conflict with PROJECT_BRIEF.md, stop and surface the conflict rather than silently choosing one.

Do not invent new strategy assumptions that are not supported by PROJECT_BRIEF.md or an explicitly approved later decision.

# Challenge, Escalation, and Scope Expansion

The project-control documents define the currently approved requirements. They are not intended to restrict critical thinking, research, or the discovery of better approaches.

Every Claude session and development agent is explicitly permitted and expected to challenge the current requirements when evidence or expert judgment suggests that:
- a requirement may be suboptimal;
- an assumption may be incorrect;
- an important analysis is missing;
- a useful data source is outside the current scope;
- a different methodology may produce a more reliable result;
- a different architecture may improve safety, reliability, profitability, or maintainability;
- an additional experiment or validation step would materially strengthen the evidence;
- the current scope excludes something that could materially benefit the project;
- a requirement creates an unintended conflict, blind spot, or failure mode.

Agents may research such ideas even when they are not explicitly listed in PROJECT_BRIEF.md, provided the research is relevant to the project's objectives.

Agents should not treat silence in the documentation as a prohibition on investigation.

However, agents must distinguish clearly between:
1. approved requirements;
2. evidence-based recommendations;
3. proposed changes or scope expansions;
4. exploratory research.

An agent must not silently replace, override, or materially alter an approved requirement.

When an agent believes a requirement should change, it must surface the issue to the user with:
- the current requirement;
- the concern;
- the evidence or reasoning;
- the proposed alternative;
- expected benefits;
- important risks or tradeoffs;
- whether the recommendation is urgent, optional, or blocking.

Material changes to the approved strategy, architecture, validation methodology, risk framework, production behavior, or project scope require user approval before they become project requirements.

Agents are encouraged to say:

> "I recommend changing the current requirement because..."

Agents must not suppress a better recommendation merely because it falls outside the existing documents.

The objective is not blind compliance with the initial design.

The objective is to build the strongest defensible system while preserving explicit human control over material changes.

If evidence shows that part of the existing project design is inferior, unnecessary, unsafe, economically weak, or statistically unsound, agents should say so clearly.

PROJECT_BRIEF.md remains authoritative for what is currently approved, but it is always open to explicit revision after review and user approval.

# Critical Runtime Independence

The final production system must operate completely independently of:
- Claude;
- ChatGPT;
- any LLM;
- any AI-agent framework;
- agent-to-agent communication.

No LLM or agent inference is permitted or required in the production runtime.

Agents are temporary developers, researchers, reviewers, and auditors only.

Their goal is to make themselves operationally unnecessary by converting their work into:
- deterministic code;
- trained standalone models;
- tests;
- configurations;
- mathematical rules;
- automated risk controls;
- automated monitoring;
- automated execution;
- automated recovery logic.

If all Claude accounts and agents disappeared after development, the finished software must continue to collect data, calculate features, make predictions, calculate edge, size positions, execute trades, reconcile state, monitor itself, pause when unhealthy, and recover safely.

# Strategy Scope

- Focus on approximately 15-minute to 1-hour prediction markets.
- Initial assets: Bitcoin and gold.
- No sentiment-analysis strategy.
- Primary research direction: short-horizon velocity and related quantitative market dynamics.
- Support entering partway through a market window and forecasting only the remaining horizon.
- Time remaining must be treated as a first-class variable.

# Prediction Objective

Velocity prediction is intermediate.

The final useful output is:

**P(contract resolves in our favor | information observable at decision time)**

No future information may enter features.

# Economics

Do not optimize for prediction accuracy alone.

A model is only useful if it produces positive expected value after:
- fees;
- spread;
- slippage;
- latency;
- execution uncertainty;
- model uncertainty.

Prefer executable prices over midpoint assumptions where possible.

Prefer conservative assumptions.

# Data

Collect and preserve as much relevant historical and live data as practical from:
- Kalshi;
- Polymarket;
- underlying Bitcoin markets;
- relevant gold/reference markets;
- other quantitative sources when justified.

Preserve raw data whenever practical.

Keep raw, normalized, feature, label, prediction, and simulated-trade layers separable.

Do not silently repair missing or corrupt data.

Flag anomalies and preserve provenance.

Historical venue data may not provide sufficient temporal resolution for the shortest forecasting horizons. Begin collecting high-frequency live data as early as practical so future research has richer replayable data.

# Holdout Protection

Use a chronological split:
- oldest ~70% = development/training;
- newest ~30% = protected final holdout.

Never randomly shuffle the time series.

Within the 70%, use walk-forward or rolling validation.

The final 30% must not be used for:
- feature selection;
- architecture selection;
- hyperparameter tuning;
- threshold tuning;
- repeated profitability checks;
- iterative model selection;
- calibration selection;
- strategy design;
- risk-parameter tuning;
- audit-candidate repair.

Before the final holdout is opened, everything listed in START_HERE.md Phase 6 must be frozen and Gate 6 must pass.

Use purge/embargo logic so lookbacks and labels cannot cross temporal boundaries.

Every access to the final holdout must be recorded in HOLDOUT_ACCESS_LOG.md.

The chronological split is frozen once, in Phase 2 of START_HERE.md, as explicit immutable partition boundaries on an identified dataset snapshot. Later-arriving data never moves those boundaries. Never recalculate "70/30" over an expanding dataset after the split is frozen.

Opening the protected holdout requires both the Gate 6 checks in START_HERE.md and explicit user approval for that specific candidate and frozen split. Passing a checklist is never permission by itself.

Once outcome-dependent protected information has been revealed, the holdout is consumed. A consumed holdout must never again be treated as untouched data, and must never be relabeled as development or validation data. See START_HERE.md Phase 7.

No observation may become protected evaluation data after being exposed to development.

The primary protection for the final holdout is an information embargo: protected observations, outcomes, and equivalent information capable of reconstructing them stay unavailable to development agents until authorized final evaluation, regardless of source or representation. Local protected plaintext additionally stays outside development-agent-readable storage until authorized release; filesystem/path isolation is defense in depth and does not replace the embargo. See Project-Wide Controls in START_HERE.md.

## Protected Information Rule

Agents may freely research code, repositories, documentation, papers, and methodology online. Agents must never access, request, reconstruct, or infer protected holdout observations or outcomes before authorized final evaluation, from any source: project files, copies, venue or alternate-provider APIs, websites, datasets, or equivalent observables such as the underlying asset prices that determine a protected contract. Before a real protected scope is declared, agents do not inspect real market observations at all.

Project market data is obtained only through the deterministic data-access guard, which refuses overlapping, equivalent, or undeterminable requests. Agents may propose data needs; they never override the guard. When uncertain, treat information as protected. If protected information is exposed accidentally, stop using it, do not investigate further, and escalate; when it could influence development, record a contamination event under HOLDOUT_ACCESS_LOG.md. See docs/protected_information.md.

# Modeling

Do not assume deep learning is superior.

Benchmark simple models first.

Candidate families may include:
- logistic/statistical models;
- gradient-boosted trees;
- TCN;
- temporal CNN;
- GRU;
- LSTM;
- other justified sequence models.

Select based on:
- out-of-sample predictive quality;
- calibration;
- after-cost economics;
- robustness;
- latency;
- operating cost;
- simplicity;
- stability.

The simplest reliable model with the strongest economic result should win.

# Risk

No prediction may override hard risk limits.

Never allow all capital to be exposed at once.

Research appropriate use of:
- fractional Kelly;
- uncertainty-adjusted sizing;
- maximum per-trade exposure;
- total exposure caps;
- correlated exposure caps;
- asset-specific caps;
- drawdown controls;
- risk-of-ruin limits.

Hard limits always override model confidence.

User risk appetite — bankroll definition, starting live capital, maximum acceptable drawdown, risk-of-ruin tolerance, any absolute loss budget, and capital-scaling policy — is a user-approved governance input, never a parameter optimized from historical returns. All six must be approved by Gate 4.5 of START_HERE.md. Undefined values block Gate 4.5 and all live sizing and trading.

# Real Capital and Venue Access

No real-capital order may be intentionally submitted during research, data collection, model development, backtesting, audit, replay, fault injection, paper or shadow testing, or Phases 0–11 of START_HERE.md.

Use sandbox, demo, mock, replay, or shadow environments where available.

Phase 12 is the earliest phase at which real-capital trading may begin, and it requires explicit user approval. The initial live allocation must follow the user-approved starting-capital and risk policy.

No agent may treat a passed gate as permission to deploy capital.

Protective handling of already-existing external exposure is not permission to originate new speculative exposure.

Before relying on a venue, verify from current official sources its API availability and permitted usage, account and jurisdiction eligibility, market access, authentication requirements, terms and restrictions, and live-trading limitations. Never design around restrictions or assume historical access still applies. Re-verify before Phase 12.

# Pause / Kill / Drift

The final runtime must include:
- manual PAUSE;
- manual KILL;
- automatic exposure reduction;
- automatic hard halt.

Monitor:
- realized net P&L;
- predicted vs realized edge;
- calibration;
- Brier/log loss;
- rolling EV;
- drawdown;
- feature drift;
- model-output drift;
- slippage;
- latency;
- fill quality;
- data-feed health;
- API health;
- reconciliation health.

Do not halt based on a few random losses.

Use statistically defensible rolling windows, minimum samples, confidence intervals, sequential testing, or change-detection logic.

Suggested states:
- GREEN
- YELLOW
- ORANGE
- RED

Technical uncertainty may trigger immediate RED.

Recovery from RED must require evidence of recovery and should not immediately restore full sizing.

# Statistical Standards

Assume every apparent edge may be false.

Investigate:
- lookahead bias;
- leakage;
- overlapping labels;
- nonstationarity;
- regime dependence;
- autocorrelation;
- heteroskedasticity;
- repeated tuning;
- multiple testing;
- effective sample size;
- calibration;
- selection bias;
- execution-selection bias.

A backtest is not proof of edge.

# Advantage-Player Mathematics

The Statistician must understand:
- expected value;
- house edge;
- vig/overround;
- offered odds vs true probability;
- Kelly criterion;
- fractional Kelly;
- bankroll management;
- risk of ruin;
- variance;
- drawdown;
- losing-streak distributions;
- Bayesian updating;
- sequential decisions;
- correlated wagers;
- line shopping;
- arbitrage;
- near-arbitrage;
- probability calibration;
- mathematical logic of historical advantage play such as card counting.

The goal is not gambling folklore.

The goal is to identify measurable mispricing, size appropriately, preserve capital, and repeat.

# Open Source and Research

Agents are encouraged to use:
- open-source repositories;
- public implementations;
- research papers;
- official SDKs;
- quantitative libraries;
- public datasets;
- open-weight models.

Do not blindly copy.

Check:
- license;
- security;
- correctness;
- maintenance;
- assumptions;
- leakage;
- fit for this project.

Record important external sources in research/sources.md when that file exists.

# Coding Rules

- Production code must be modular and testable.
- Use types where practical.
- Never hard-code outputs to pass tests.
- Never delete a failing test just to make CI green.
- Never weaken risk controls to improve backtest results.
- Never conceal warnings.
- Never silently drop malformed data.
- Never commit credentials.
- Use environment variables or appropriate secret management.
- Never expose production or live-order credentials, wallet or private-key material, or equivalent secrets to Claude, LLM, or development-agent environments.
- Critical execution and risk components require strong tests.

# Reproducibility

Every important experiment should record:
- git commit;
- dataset version;
- date range;
- feature set;
- target definition;
- model;
- hyperparameters;
- seed where applicable;
- cost assumptions;
- evaluation metrics.

Results that cannot be reproduced should not drive production decisions.

# Development Behavior

Before major changes:
1. inspect existing code;
2. understand the current design;
3. identify assumptions;
4. propose the change;
5. implement;
6. run relevant tests;
7. report what changed;
8. report unresolved risks.

Explicit user approval is required before modifying governance, control, or agent documents (PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md, the structure of HOLDOUT_ACCESS_LOG.md, `.claude/agents/`, and `.claude/settings.json`), and before any material change, as defined in START_HERE.md, to approved requirements. Routine implementation inside an explicitly approved phase or task may proceed without separate governance approval for each file edit. Ordinary Claude Code permission prompts remain in force.

Before substantive work, read docs/backup_and_recovery.md. Development autonomy is bounded by the current approved execution environment: local sessions remain owner-controlled; unattended autonomous development is permitted only inside the owner-approved isolated environment described there, and only for development work (no real venue credentials, real-money execution, or irreplaceable live-data capture). Stage intended files by explicit path; never use `git add -A`. Agents must remain within the project and approved project-specific paths and must not access personal files, credentials, browser/email/payment data, unrelated repositories, or unapproved external services. At the end of each meaningful approved work batch, follow the applicable verified checkpoint procedure. Never force-push, rewrite published history, weaken access boundaries, or bypass a failed check to obtain a backup.

When reviewing another agent's work, be skeptical.

Do not optimize for agreement.

Optimize for correctness.

If evidence contradicts the core hypothesis, report it clearly.

Compliance with current requirements does not excuse failure to identify and escalate a better approach.

The project is allowed to conclude that no durable edge exists.

# Release Test

Before production can be considered complete, ask:

> "If every Claude account and every development agent disappeared tomorrow, could the software still collect data, validate it, generate features, run the standalone model, calculate edge, size positions, execute, reconcile, monitor, pause, recover, and record results?"

If the answer is no, the project is not complete.
