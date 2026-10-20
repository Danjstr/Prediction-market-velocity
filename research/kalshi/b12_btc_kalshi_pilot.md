# B12 — BTC Kalshi historical pilot and data-science readiness (amended for PMV 2.0)

**Branch:** `b12/btc-kalshi-pilot`, created 2026-10-19 directly from the final B11 tip `c986f49227a47b855a547db96e65356f3674a9b8` (not from the `main` merge `92e46c1`).

**Charters:**
- owner "START B12 — BTC KALSHI HISTORICAL PILOT + DATA-SCIENCE READINESS" (2026-10-19), which implements the DR-2 pilot gate (`docs/decisions/2026-10-19_owner_data_readiness_decisions.md`);
- amended by owner "APPROVE PMV 2.0 WITH REVIEW MODIFICATIONS / BEGIN B12 STRATEGY AMENDMENT + REVISED BTC FEASIBILITY PILOT" (2026-10-20; record `docs/decisions/2026-10-20_b12_pmv2_strategy_pivot.md`, PV-13 to PV-15).

**Purpose after the amendment (PV-13).** The pilot is **no longer intended to validate PMV 2.0 by itself**. It must establish:
- contract and label integrity;
- timestamp behavior;
- available history;
- spread behavior;
- quote staleness;
- trade activity;
- executable cost floors;
- whether coarse 60/120-second movement is large enough even in principle;
- whether historical lead/lag analysis is meaningful;
- an old-strategy settlement comparator.

P1–P9 are kept where still valid. P10–P16, early-close and pause incidence, the old-strategy control C1–C3, the stop conditions S-1 to S-6, and the pilot discipline rules were **added on 2026-10-20, before any Kalshi row was seen** (§5.4 to §5.8).

**Status: BLOCKED BEFORE THE FIRST KALSHI OBSERVATION.** No Kalshi market observation has been fetched, viewed, or profiled in B12. Every empirical question in the charter (§§6–11) is still **UNKNOWN**. This record holds three things:
- the access blockers;
- the tooling built so the pilot can run deterministically once access is granted;
- a **pre-registered** pilot protocol, written before any data was seen, with provisional designs that the pilot must confirm or refute.

Evidence labels used throughout: **OBSERVED DIRECTLY**, **OFFICIAL DOCUMENTATION**, **INFERENCE**, **UNKNOWN**. In B12 nothing is yet OBSERVED DIRECTLY for Kalshi.

## 1. Lineage verification (OBSERVED DIRECTLY, 2026-10-19)

- On `b11/btc-poc-owner-decisions`, `git rev-parse HEAD` returned `c986f49227a47b855a547db96e65356f3674a9b8`, and there were no tracked changes. The untracked entries were only the sandbox masking placeholders named in `docs/conventions.md`.
- `git ls-remote origin refs/heads/b11/*` returned `c986f49…` for `b11/btc-poc-owner-decisions`, and no `b12/*` branch existed on `origin`.
- `git switch -c b12/btc-kalshi-pilot` was run at that HEAD, and `git merge-base --is-ancestor c986f49 HEAD` returned 0.
- `docs/BRANCH_TIMELINE.md` is **not** changed. A session never designates its own branch as active; that needs the owner (START_HERE.md "Repository Continuity").

## 2. Blockers found (the B12 stop conditions apply)

### 2.1 AR-B12-1 — the Kalshi REST data host is unreachable from the development sandbox (BLOCKING)

- **Request:** one unauthenticated metadata `GET /trade-api/v2/series/KXBTC15M` against `api.elections.kalshi.com` and `external-api.kalshi.com`.
- **Outcome:** refused by the Claude Code auto-mode permission classifier before any connection was made. Both hosts are also in the session sandbox's `deniedHosts` (`api.elections.kalshi.com` exactly; `external-api.kalshi.com` through `*-api.*`). The B10 profiles recorded the same deny (`CONNECT tunnel failed, response 403`).
- **Not attempted:** no alternative route, mirror, cache, subagent, or other tool (docs/external_access.md §1.1 rule 4).
- **Host class:** `live-data` by pattern (§1.1 rules 1 and 8). The pilot would read only the **historical tier**: markets settled before `/historical/cutoff` `market_settled_ts`. The tool enforces this (§4).
- **Narrowest grant proposed.** The owner chooses one:
  - **(A)** A one-time, owner-run pilot. The owner runs `research/data_sources/recon_tools/kalshi_pilot_sample.py --direct …` (or through the owner-side Layer B route) on the owner's machine, under the §5 protocol. The raw output stays in the git-ignored `/workspace/.recon_tmp/kalshi_pilot` (or an owner-chosen location the agent can read). The agent then runs only the offline profiler.
  - **(B)** A temporary Layer A and Layer B allowance for exactly `external-api.kalshi.com`, path prefixes `/trade-api/v2/historical/` and `/trade-api/v2/series/` and `/trade-api/v2/events`, for this batch only, removed at B12 close (B10-D10 precedent, and P-5 before any `T0 − m`).
  - **Recommendation:** **(A)**. It needs no change to sandbox policy and fits "historical data … fetched only by deterministic project tooling". The agent never makes the live-class request.
- **Exposure:** none yet. When the pilot runs, every fetched interval goes into `docs/exposure_register.md` Part A, from the tool's `manifest.jsonl`: the close-time span per market and the retrieval times.

### 2.2 AR-B12-2 — governing Kalshi terms are unobtainable by agents (BLOCKING for the charter's step 4)

- The charter requires inspecting and recording the current published API and access terms before any market observation is pulled.
- Those terms are the Developer Agreement (`https://kalshi.com/developer-agreement`) and the Terms of Service (`https://kalshi.com/terms`). `kalshi.com` is `live-display`, is sandbox-denied, and returned a bot challenge in batch 2 (AR-3). It is therefore not fetchable (B09 §2, docs/external_access.md §1.1 rules 2–4).
- `https://docs.kalshi.com/getting_started/terms.md` was fetched under this charter (`docs` class; 2026-10-19T18:31:30Z; HTTP 200; 5,005 bytes). It is a **glossary** ("Kalshi Glossary"). It is not legal terms and contains no access or usage terms (OBSERVED DIRECTLY). It held no BTC observation.
- **Owner action needed:** supply copies of the Developer Agreement and the Terms of Service (URL, retrieval date, SHA-256). The session will then quote only the operative clauses and classify them: explicit prohibition → STOP; otherwise → continue, per the charter. A-2 stays unassessed (B09 §5). This charter does not change that, and B12 is not an acquisition approval.

### 2.3 Conflict to surface: the data-access guard refuses all real observations (not blocking under the B10 precedent)

- CLAUDE.md: "Project market data is obtained only through the deterministic data-access controls."
- `pmv.data_access_guard` returns `PROTECTED_SCOPE_NOT_DECLARED` for every real request until a protected scope is declared (`src/pmv/data_access_guard.py`, `Guard._window`). The B10 and owner-review samples (X-7, X-12) were owner-authorized reconnaissance outside the guard. The B12 pilot tool follows that precedent, and does not call the guard.
- **Recommendation:** the owner confirms, in the B12 decision record, that the B12 charter authorizes this bounded reconnaissance outside the guard, as for X-12. The alternative is a guard-level "owner reconnaissance" provision, a material control change that needs Red-Team review. This is a proposed clarification, not an applied one.

## 3. What is known before the pilot (OFFICIAL DOCUMENTATION only; from repo snapshots)

These are the documented expectations the pilot must test. Sources: `research/kalshi/api_documentation_findings.md` §§3, 5, 7, 8, 11; `research/data_sources/schema_profiles/kalshi_markets.md`, `kalshi_trades.md` (OpenAPI 3.34.0, retrieved 2026-10-19).

| Topic | Documented expectation | Pilot must establish |
|---|---|---|
| Series identity | `KXBTC15M` appears in Kalshi docs only as an example ticker and a changelog mention; `product_metadata.cadence` may be `fifteen_min` | Actual series metadata; any renamed or versioned predecessor (from `/series?category=Crypto` and cadence) |
| History tiers | Markets settled before `market_settled_ts` and trades before `trades_created_ts` are historical; depth and lag are undocumented | Earliest settled KXBTC15M market (depth probes); cutoff lag |
| Trades | `trade_id`, `count_fp`, `yes_price_dollars`, `no_price_dollars`, `taker_outcome_side`, `taker_book_side`, `created_time` (RFC 3339; precision undocumented), `is_block_trade` | Precision, ordering, duplicates, pagination signal (`null` vs `""`), block-trade frequency |
| Candles | Historical schema: `end_period_ts` (inclusive end), `yes_bid`/`yes_ask`/`price` OHLC (no `_dollars` suffix), `volume`, `open_interest`; sampling rule for bid/ask undocumented; a synthetic pre-start candle can be prepended | Population of bid/ask; null and sentinel representation; empty-book representation; minute completeness; final-minute presence |
| Labels | `result` ∈ {yes, no, scalar, ''}; no `void`; `settlement_value_dollars` after determination; `expiration_value` string; `is_provisional` markets may be removed | Label determinism; strike re-derivation; provisional or removed markets |
| Metadata mutability | Strikes and `close_time` can change intra-life (`metadata_updated`, `close_date_updated`); REST returns current state | Whether historical metadata shows `updated_time` after close; how the strike relates to the reference at open |

## 4. Tooling delivered (not yet run on real data)

| File | Role |
|---|---|
| `research/data_sources/recon_tools/kalshi_pilot_sample.py` | Bounded fetch. Fixed public endpoint templates only; `KXBTC15M` scope guard; historical tier only (a market at or after `market_settled_ts` is refused); cumulative ceilings of **10 MB** and **10,000 rows** across invocations, enforced from `manifest.jsonl` before any response is written; at most 10 trade pages per market; raw bytes plus a SHA-256 manifest under the git-ignored `/workspace/.recon_tmp/kalshi_pilot`; credential-free CONNECT through `PMV_EGRESS_PROXY_HOST`/`PORT`, or `--direct` (owner-run). It never reads the runtime proxy variables (DR-16). |
| `src/pmv/pilot/kalshi_btc.py` | Offline profiler: `python -m pmv.pilot.kalshi_btc DIR [--show] [--fee-scenario NAME=COEFFICIENT ...]`. **2026-10-20 additions:** P10 to P16a, lifecycle incidence, and C1 (§5.4 to §5.5), with labelled fee scenarios: default spread-only, each marked `SCENARIO_NOT_AUTHORITATIVE`. **Defect fixed:** a trade without `taker_outcome_side`, a field Kalshi added on 2026-05-06, was counted as malformed and dropped. That would have hidden every older trade from P13. It is now kept, and its absence is counted. **Original features:** Produces an aggregate-only JSON report covering native field types, nulls, numeric-string decimals, timestamp digits, ordering, duplicates, pagination, label integrity, candle coverage, the late-window × ask-band table (YES and NO sides, with distinct contracts and settlement instants), trade activity by remaining-time band, and trade↔candle reconciliation under both boundary conventions and offsets of −60, 0, and +60 s, with and without block trades. `--show` prints head and tail raw rows to the terminal only. Strict parsing: floats, bools, and offset-less times are refused and counted as malformed, never repaired. |
| `tests/unit/test_pilot_kalshi_btc.py`, `tests/unit/test_kalshi_pilot_sample_tool.py` | Deterministic tests on invented fixtures, including the 2026-10-20 measurements. The tool tests are offline (`fetch` is stubbed) and cover templates, the scope guard, the cutoff refusal, pagination termination, cumulative ceilings, and non-echo of proxy settings. They found and fixed one real defect: the trades request had dropped its `ticker` filter. |

## 5. Pre-registered pilot protocol (written before any Kalshi row was seen)

Every threshold below is a **development hypothesis** for this pilot gate. None is an empirical truth, and the owner may amend any of them **before** the pilot runs. They decide only whether to proceed to bulk acquisition. They are not strategy thresholds.

### 5.1 Commands, in order (owner-run under option A)

```
T=research/data_sources/recon_tools/kalshi_pilot_sample.py
python3 -I $T --direct discover                      # cutoff, series, fee changes, Crypto series list
python3 -I $T --direct depth --close-date <D>        # D in: earliest plausible launch month, then +3 months steps (≤ 6 probes)
python3 -I $T --direct markets-page                  # one page of 200 settled markets (ticker selection)
python3 -I $T --direct market --ticker <T_i>         # i = 1..12 (selection rule below)
python3 -I $T --direct --out /workspace/.recon_tmp/kalshi_pilot_repeat market --ticker <T_1>   # replay determinism
uv run --locked python -m pmv.pilot.kalshi_btc /workspace/.recon_tmp/kalshi_pilot > /workspace/.recon_tmp/b12_profile.json
# after DR-9: add the versioned schedule as a scenario (S-1b), e.g. --fee-scenario dr9_v1=<coefficient>
```

**Fee scenarios (PV-21).**
- `spread_only` (no fee) is always run. It is the most generous cost floor.
- The only other scenario that may feed a stop condition is the **authoritative, versioned** Kalshi schedule (DR-9). If that schedule is not of the form `coefficient × P × (1 − P)` per contract, the profiler is extended, with tests, before it is used. The new form is not approximated.
- Any other scenario is exploratory, labelled as such, and never cited.
- No fee number in this protocol is canonical.

### 5.2 Market selection (fixed in advance)

- Use 12 settled markets over 4 distinct UTC dates, chosen from the depth probes: the earliest month with data, two middle months, and the most recent fully historical week.
- On each date, take the markets whose window ends at 00:15, 08:15, and 16:15 UTC (three liquidity regimes).
- If one event has several strike markets, take the one listed first (record the rule). Never select by price, outcome, or volume.
- Add one market whose window overlaps the Thursday 03:00–05:00 ET maintenance window, if one exists in the sampled dates, to observe pause behavior.
- Stop early only at the 10 MB / 10,000-row ceiling. The tool enforces it.

### 5.3 Pass/fail criteria (map to the charter's §18 stop conditions)

"Contracts" means distinct settled markets. Rows within one contract are not independent.

| ID | Criterion | Pass | Stop and return to owner |
|---|---|---|---|
| P1 | `yes_ask` usable (strictly inside (0, 1)) on in-window candles | ≥ 80% overall, and ≥ 70% of contracts have a usable ask in the `<=1m` band | < 50% in the `<=1m` or `>1-2m` bands, or asks only as sentinels or nulls |
| P2 | Final-minute candle present (`end_period_ts == close_time`) | ≥ 10 of 12 contracts | ≤ 6 of 12, or systematically absent |
| P3 | Labels | Every finalized market has `result` ∈ {yes, no} and a consistent `settlement_value_dollars` | Any unexplained conflict |
| P4 | Strike re-derivation from `expiration_value` | Agreement on every checkable market; each disagreement explained by documented rule text | Unexplained disagreement |
| P5 | Point-in-time metadata | Strike and close time are knowable at decision time (rule text, or strike equal to an at-open reference) | Strike is only knowable post hoc, with no rule to reconstruct it |
| P6 | Trade↔candle volume, best (convention, offset) | Exact minute match ≥ 95% and relative volume error ≤ 2% | No convention reaches 80% exact |
| P7 | History depth | ≥ 6 months of settled KXBTC15M history before the cutoff | < 3 months |
| P8 | Replay determinism | The repeat fetch of `T_1` gives identical rows (byte-identical or row-identical after key sort) | Rows differ without a documented reason |
| P9 | Terms (§2.2) | No explicit prohibition of private research use or storage | Explicit prohibition |

A result between "pass" and "stop" is **GO WITH CONDITIONS**, with the condition named.

*2026-10-20 note.* P1–P9 stay valid under PMV 2.0:
- P1 now also serves as the two-sided-quote coverage check for P10 and P15;
- P5 still gates B0 and distance-to-strike, which both strategies need;
- P9 is extended by S-5.

### 5.4 PMV 2.0 descriptive measurements P10–P16 (pre-registered 2026-10-20, before any row was seen)

**Common definitions:**
- **Decision point:** an in-window minute boundary `E` (a candle `end_period_ts`, with `open_time < E ≤ close_time`).
- **Two-sided quote:** usable YES bid and ask closes (strictly inside (0, 1)) with bid < ask. Crossed or locked quotes are counted, never repaired.
- **Remaining-time bands:** ≤1, >1–2, >2–3, >3–5, >5–10, >10 minutes.
- **Price bands** on the YES mid: <0.10, 0.10–0.29, 0.30–0.69, 0.70–0.89, 0.90–0.96, ≥0.97.
- **Reporting:** every table reports distinct contracts and settlement instants next to rows.
- **Status of the results:** all are descriptive. None is an edge, profitability, or calibration claim.

| ID | Measurement | Report key |
|---|---|---|
| P10 | Spread at minute boundaries, by remaining-time band × price band: quantiles, the count at or below 1¢ and 2¢, and the quote-state counts | `p10_spread` |
| P11 | Share of adjacent minutes with an unchanged close bid/ask (with and without volume), and with a zero bid and ask OHLC range, by band × price band. Missing minutes are never bridged | `p11_quote_staleness` |
| P12 | Trades per contract-minute and inter-trade gap quantiles by remaining-time band; block-trade share | `p12_trade_arrival` |
| P13 | The raw-string precision profile (fractional digits shown). The **observed** timing resolution, which formatting alone does not establish (`.000` carries no sub-second information): the fraction class (none / all-zero / non-zero), the distribution of significant non-zero fractional digits, the whole-minute share, and `observed_resolution` (below). Also same-timestamp print groups and their size distribution, and `taker_outcome_side` population (yes / no / absent / invalid) by UTC month | `p13_trade_timestamps` |
| P14 | Print-to-print absolute price change and gap for consecutive non-block prints less than 60 s apart, by band; share of print-minutes with two or more prints | `p14_print_dispersion` |
| P15 | **Cost-hurdle / perfect-foresight ceiling** (below) | `p15_cost_hurdle` |
| P16a | Kalshi-side lead/lag measurability, from the **observed** resolution (P13), never the digit count, and from event dispersion. Over the last 300 s of each contract: the share of whole seconds with a non-block print; the share of distinct print times among non-block prints (identical stamps carry no ordering); inter-print gaps; and the minimum resolvable lag (0 s for `sub_second`, 2 s for `whole_second`, undefined otherwise) | `p16a_lead_lag_measurability` |
| P16b | Aligned Kraken cross-correlation at the available precision (lags 0–120 s, with a reversed-shift placebo and day-blocked intervals). **Not run in B12:** it needs the DR-3 Kraken archive file for the sampled dates. Pre-registered here | — |
| L | Early-close and pause incidence: window durations, close times off the 15-minute grid or different from `expected_expiration_time`, `can_close_early`, and overlaps with the documented Thursday 03:00–05:00 ET pause, with the candles and trades seen inside each overlap | `lifecycle_incidence` |

**Observed resolution (P13; pre-registered 2026-10-20 in the owner's pre-commit review, before any data was seen).** The classes are checked in this order:

| Class | Rule |
|---|---|
| `coarser_than_second` | At least 50% of stamps fall exactly on a minute |
| `sub_second` | At least 50% of stamps carry a non-zero fractional part |
| `whole_second` | Under 1% carry a non-zero fractional part, however many digits are shown |
| `mixed` | Anything else |
| `unknown` | No parsed stamp |

**P15 definition.** For each decision point `E` with a two-sided quote, and each horizon `h` ∈ {60, 120} s:
- **Horizon limits.** The 1-minute grid cannot represent 30 s, so the 30-second horizon is prospective-only. An exit boundary after `close_time` is counted as `crosses_close`, never scored, because settlement is not an exit. A missing or one-sided exit quote is counted.
- **Close-to-close:**
  - YES net = bid(E+h) − ask(E) − fee(ask(E)) − fee(bid(E+h));
  - NO net = bid(E) − ask(E+h) − fee(1 − bid(E)) − fee(1 − ask(E+h)).

  Perfect foresight takes the better side.
- **Generous:** as close-to-close, but the exit uses the best bid high (YES) or ask low (NO) over the bars in (E, E+h]. That is an intra-minute extreme of unknown size and timing, so it is an upper bound.
- **Mid diagnostic:** |mid(E+h) − mid(E)| > spread(E) + 2 × fee(mid(E)).
- **Per cell** (h × band × price band) and per fee scenario, report:
  - the share of decision points with a positive close-to-close ceiling;
  - the share with a positive generous ceiling;
  - the share where the mid move exceeds cost;
  - the number of contracts with a positive generous ceiling;
  - quantiles of the best close-to-close net.
- **What P15 is not.** A positive ceiling is necessary, never sufficient. It ignores latency, depth, queue position, adverse selection, and the fact that a touch is not a fill. **No profitability claim may be made from P15.**

### 5.5 Old-strategy settlement control (PV-14)

| ID | Control | In B12 |
|---|---|---|
| C1 | Market tail calibration. **At most one row per contract × band** (≤1, >1–2, >2–3, >3–5 minutes): the **earliest** in-window minute in that band at which either side's executable ask is at least 0.85. If both sides qualify in that same minute, the side with the higher ask is used, and YES on a tie. If the other side qualifies later in the band, it is not used, and that case is counted. This rule was amended in the owner's pre-commit review on 2026-10-20, before any data was seen: the earlier per-side rule could put two rows from one flipping contract into one cell. Per band × ask band: wins, mean ask, win frequency (Wilson 95%), gap = frequency − mean ask with a 95% **day-block** bootstrap interval (2,000 resamples, seed 20261020, whole UTC close dates), and the gap net of each scenario's mean fee | Computed (`c1_old_strategy_control`). **Descriptive only:** 12 markets are far below the power needed for any calibration claim |
| C2 | B0 analytic digital fair value (Kraken σ known at decision time, distance to the knowable strike, remaining time, the 60-second averaging caveat) versus the executable ask | Pre-registered; runs with P16b. Needs Kraken prices and P5 |
| C3 | Market-implied σ (inverted from the ask) versus subsequently realized Kraken σ over the remaining window | Pre-registered; runs with P16b. Needs Kraken prices and P5 |

**Inferential use.** C1–C3 are used inferentially only on the development pool after bulk acquisition, under these same definitions.
- If the settlement arm shows a lower day-block bound above zero after the authoritative fee, it **continues on its own merits** (PV-14).
- Positive evidence is never suppressed because PMV 2.0 is primary.

### 5.6 Stop conditions (pre-registered 2026-10-20, before any row was seen; PV-15)

Every threshold here is a development hypothesis. The owner may amend it only **before** the pilot runs. None is chosen after seeing results.

**Mechanical evaluation.** The profiler evaluates S-1, S-2, and S-3 itself, with the thresholds below as named constants (report key `stop_screen`), so no analyst judgement enters them. S-4 to S-6 are reported as `MANUAL`: they rest on the P1–P9 checks, the terms, and the fee schedule.

**Liquid cell.** A P15 cell counts as liquid only if **all** of the following hold:
- it has at least 3 contracts and at least 20 decision points;
- the P12 trades-per-contract-minute for its remaining-time band is at least 1.0;
- the P11 unchanged-close-quote share for its band × price band is at most 0.80.

| ID | Condition | Consequence |
|---|---|---|
| S-1a | Under `spread_only`, the **generous** P15 ceiling is positive at fewer than 5% of decision points in **every** liquid cell, at both horizons | **HISTORICAL COST-HURDLE SCREEN FAILED — OWNER NO-GO REVIEW REQUIRED.** No automatic advance to prospective capture. See the note below. |
| S-1b | After DR-9: the same test under the authoritative schedule | As S-1a |
| S-2 | P13 `observed_resolution` is `coarser_than_second`, or the P16a late-window seconds-with-print share is below 0.05. A `mixed` or `unknown` resolution gives UNDETERMINED and goes to the owner | **Historical lead/lag analysis stops.** P16b is not run, and the question becomes prospective-only (Span D). A `whole_second` result limits P16b to lags of 2 s or more. |
| S-3 | A band × price-band cell fails the liquid-cell test | **Remove the cell from the opportunity universe.** If no liquid cell remains, the S-1a consequence applies. |
| S-4 | P3, P4, or P5 stop (labels, strike re-derivation, point-in-time strike); or close-time changes, early closes, or off-grid closes in more than 1 of 12 markets without a documented rule | **Stop.** Contract and settlement metadata are not point-in-time safe. |
| S-5 | P9 explicit prohibition in the terms; or the DR-9 fee schedule is not obtained | **Stop** for a terms prohibition. Without DR-9, **stop cost analysis**: P15 is reported under `spread_only` only, S-1b cannot be evaluated, and no Stage C economics begin. |
| S-6 | Any P1, P2, P6, P7, or P8 stop | As registered in §5.3 |

**S-1 semantics (owner's pre-commit review, 2026-10-20).** The bounded pilot is too small to falsify the whole PMV 2.0 program on its own.
- **If S-1 fails,** PMV does **not** advance to prospective capture. It returns "HISTORICAL COST-HURDLE SCREEN FAILED — OWNER NO-GO REVIEW REQUIRED". The owner may then:
  - terminate the 30–120-second path;
  - enlarge the development-only historical feasibility sample under a new approved protocol;
  - change the candidate opportunity strata for a principled reason;
  - or stop PMV 2.0.
- **Failure of a generous perfect-foresight ceiling is strong negative evidence.** No threshold may be tuned after the result is seen.
- **If S-1 does not fail,** that is not evidence of edge. Advancing still needs owner approval.

**Outcomes of the pilot:**
- a **pass** of the 30–120-second track means only that S-1a, S-1b (when evaluable), S-3, S-4, and S-5 did not stop it;
- with owner approval, that supports **Stage C**, prospective Span D capture under DR-8, P-5, and terms;
- it never supports an edge claim.

### 5.7 Pilot discipline and trial budget

- **Fixed tables.** The tables in §5.3 to §5.5 are the complete pre-registered set.
- **Exploratory additions.** Any table or cut added after the data is seen is labelled exploratory, logged as a research degree of freedom, and never used by a stop condition.
- **Market selection** is the §5.2 rule, unchanged. Neither the band edges nor the horizons are changed after the data is seen.
- **Exposure.** Every row fetched is development-exposed. It is registered in `docs/exposure_register.md` Part A after the run, and can never become protected (PV-16).
- **Specialist review.** After the run, all eight specialists review `b12_profile.json`, with the Independent Statistical Auditor in fresh context.

### 5.8 What this pilot cannot answer

- 30-second horizons.
- Any intra-minute executable path, depth, queue position, or fill probability.
- Exit fillability near close.
- Adverse selection.
- Sub-second lead/lag.
- Any edge, profitability, or calibration claim, given 12 markets.

All of these are Span D questions (`docs/phase2.md`, PMV 2.0 section).

## 6. Provisional historical known-at policy (to be confirmed by the pilot)

Historical Kalshi data has **no receipt time** (OFFICIAL DOCUMENTATION). Event time is never assumed to equal known-at time. Every rule below is conservative and versioned as `KA-B12-v0`.

| Field | event_time | known_at_time (historical) | safe_asof_time used for features | Basis |
|---|---|---|---|---|
| Trade print | `created_time` | `created_time` + unknown publication lag | `created_time + 2 s`; sensitivity ladder 1, 2, 5, 10 s | OFFICIAL DOCUMENTATION (field); INFERENCE (lag) |
| 1-min candle (bid/ask/price OHLC, volume, OI) | the interval ending at `end_period_ts` (inclusive end; convention to be fixed by P6) | ≥ `end_period_ts` | `end_period_ts + 60 s`: a decision at `t` may use only bars with `end_period_ts ≤ t − 60` | OFFICIAL DOCUMENTATION (inclusive end; live candle mutable); INFERENCE (lag) |
| `open_time`, `close_time` | set at listing; `close_time` can move | UNKNOWN historically (REST returns the final value) | Scheduled 15-minute grid only if P5 confirms `close_time` matches the grid for all sampled markets; deviations are flagged | OFFICIAL DOCUMENTATION (mutability) |
| `floor_strike` / `cap_strike` / `strike_type` | UNKNOWN (may be set or changed intra-life) | UNKNOWN | **Not usable** until P5 shows a rule (for example strike = reference at open) that makes it knowable at `open_time` | OFFICIAL DOCUMENTATION (`metadata_updated` can change strikes) |
| `result`, `expiration_value`, `settlement_value_dollars`, `settlement_ts`, `status` | at or after determination | post-settlement | **Never features.** Label and audit only | Post-settlement by definition |
| `updated_time` | last non-trading metadata change | at `updated_time` | Audit only (flags post-hoc mutation) | OFFICIAL DOCUMENTATION |
| Series and event fees (`/series/fee_changes`) | `scheduled_ts` (effective) | announcement time UNKNOWN | Economics only, applied by effective date; never a predictive feature | OFFICIAL DOCUMENTATION; DR-9 (fee schedule still owner-pending) |
| Current-state quote fields on the market object (`yes_bid_dollars`, `volume_fp`, …) | request time | request time | **Never used historically** (current state, not history) | OFFICIAL DOCUMENTATION |
| Kraken trade | trade `time` (float s → integer µs) | time + unknown delivery lag | `time + 1 s` primary; ladder 0.25, 1, 2, 5 s | B10 profile (OBSERVED DIRECTLY, earlier exposure X-7/X-12); INFERENCE (lag) |

Prospective capture (DR-8) replaces these assumed lags with measured receipt times. Historical results must be reported at more than one rung of the ladder.

## 7. Kalshi decision time ↔ Kraken BTC join design (provisional; no new Kraken data)

Built on the existing development-exposed Kraken evidence (`research/data_sources/schema_profiles/kraken_historical_trades.md`; X-7, X-12). **No additional Kraken sample is needed** for B12: every open Kraken question (archive timestamp precision, archive versus REST `trade_id`) belongs to DR-3's first-archive-file check.

1. **Time basis.** UTC epoch integer microseconds everywhere. Kalshi RFC 3339 times are parsed with a required offset. Kraken float seconds are converted to µs with round-half-even and the rule is recorded. A float time is never used as a join key.
2. **Ordering.** Kraken rows are ordered by `trade_id` (a per-book sequence, +1 contiguous); time is checked to be non-decreasing in that order. Page-boundary duplicates are dropped only after an identity assertion. A `trade_id` gap fails closed.
3. **Taker-event aggregation (DR-3/DR-4).** Consecutive prints are merged into one taker event when they have the same µs timestamp (or are within 1 µs, for float artifacts), the same side, and the same order type, with prices monotone in the aggressor's direction. Each event carries its start time, side, total volume, VWAP, first and last price, and print count. The raw prints are kept. Intensity features count events, not prints.
4. **As-of join.** For decision time `t_d` (Kalshi bar close `E`, usable at `E + 60 s`), Kraken inputs are the events with `time ≤ t_d − L_k`, where `L_k` follows the §6 ladder. The join is backward-only, never nearest-neighbor.
5. **Staleness.** `age = t_d − time(last Kraken event ≤ t_d − L_k)`. Above a hypothesized 30 s, Kraken features are flagged stale, and the row is excluded from evaluation, not imputed. Kraken status and maintenance gaps are flagged explicitly.
6. **Lookback windows (hypotheses, frozen before any protected evaluation).** 15, 30, 60, 120, 300, and 900 s, plus "since the contract's `open_time`". Returns are log returns between taker-event VWAPs (Kraken trades carry no mid).
7. **Reference fidelity (DR-7).** Kraken is one BRTI constituent, not the settlement reference. The documented, not verified, 60-second averaging for 15-minute closes (`api_documentation_findings.md` §11, INFERENCE) means B0 should model the terminal value as the average of the last 60 s. Any `<=1m` result stays provisional until the Kraken-versus-reference fidelity test passes.

## 8. Feature-feasibility matrix (PROVISIONAL; each status is conditional on the named pilot check)

| Feature | Provisional status | Depends on | Note |
|---|---|---|---|
| Kalshi implied probability | READY WITH DERIVATION | P1 | Bar-close bid/ask mid, or last trade; 1-minute resolution only |
| Kalshi bid / ask | READY WITH DERIVATION | P1 | Bar close only; intra-minute path unknown, so entry price is bounded, not exact |
| Kalshi spread | READY WITH DERIVATION | P1 | Exact only at bar boundaries (OFFICIAL DOCUMENTATION) |
| Probability return / velocity / acceleration | READY WITH DERIVATION | P1, P2 | Minute grid; acceleration needs 3 bars, which is thin inside a 15-minute contract |
| Trade intensity | READY WITH DERIVATION | trade activity profile | Whether one taker order produces several prints is UNKNOWN for Kalshi |
| Signed / taker flow | READY WITH DERIVATION | `taker_outcome_side` populated | Field added 2026-05-06 (changelog); population before then is UNKNOWN |
| Remaining time | READY | P5 (`close_time` grid) | First-class variable |
| Distance to strike | UNKNOWN | P5 | Not usable until the strike is knowable at decision time |
| Kalshi staleness | READY WITH DERIVATION | P1 unchanged-quote profile | Time since last trade or quote change |
| BTC return / velocity / acceleration | READY WITH DERIVATION | DR-3 first archive file | From taker events |
| Realized volatility | READY WITH DERIVATION | same | |
| Signed volume, taker-event intensity, trade-flow imbalance | READY WITH DERIVATION | taker-event aggregation | Events, not prints (DR-4) |
| Kraken staleness | READY WITH DERIVATION | — | §7 item 5 |
| Kalshi L2 depth, quoted size; Kraken L2 depth; microprice; book imbalance | PROSPECTIVE ONLY | DR-8 capture | No historical book on either venue (OFFICIAL DOCUMENTATION; Kraken via B10) |

## 9. Model readiness (provisional)

- **B0** (analytic terminal probability from Kraken volatility, remaining time, and distance to strike) needs the strike to be knowable at decision time (P5). Without it, B0 cannot be specified point-in-time.
- **B1** (market-implied probability) needs P1 and P2.
- **B2** (regularized logistic) needs B0 and B1 inputs plus the Kalshi microstructure features.
- **B3** (boosted trees) only if B2 leaves structured residual signal out of sample. Sequence models stay deferred (DR-21).
- **Effective units** (INFERENCE, arithmetic only). The independent unit is the **settlement instant**, not the minute row. Adjacent 15-minute windows also share a BTC volatility regime, so the effective count is lower than the instant count. A ±1 percentage-point 95% interval on calibration at p ≈ 0.95 needs about `1.96² × 0.95 × 0.05 / 0.01² ≈ 1,825` independent qualifying contracts per probability band, before any dependence correction. At 96 windows per day, that implies months of history *with qualifying late-window tail observations*. The pilot's per-contract tail coverage (P1, plus the §10-style table) gives the first estimate of that fraction. No power claim is made here.

## 10. Specialist review

**Not run.** After the PMV 2.0 amendment, all eight specialists review the pilot (§5.7). The original charter asked the seven specialists to review "the ACTUAL derived evidence". None exists yet, and a verdict on documentation alone would contradict the charter's §6 ("Do not issue conclusions from schema documentation alone"). The review runs after the §5 pilot has produced `b12_profile.json`.

## 11. Batch accounting (docs/external_access.md §1.3)

- Incidental exposures to real observations: **0**. The docs glossary page held only illustrative non-BTC ticker examples.
- Refused host attempts: **1** (`live-data` class; `api.elections.kalshi.com` and `external-api.kalshi.com`, refused by the permission classifier before any connection).
- Terms events: **0** (no terms page was reachable).
- Raw pilot data: none exists, so there is nothing to delete.
- **2026-10-20 (PMV 2.0 review).** The API / Execution review fetched `docs`-class pages from `docs.kalshi.com` (`openapi.yaml`, `llms.txt`, and eight guide and reference pages) into a temporary directory outside the repository. They contained no observations, so there was no exposure. The fetches are logged in `research/sources.md`. The OpenAPI specification had changed since the 2026-10-19 snapshot (PV-20). No venue API host, stream, or live-display page was contacted.
