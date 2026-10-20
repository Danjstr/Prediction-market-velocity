# B12 — BTC Kalshi historical pilot and data-science readiness

**Branch:** `b12/btc-kalshi-pilot`, created 2026-10-19 directly from the final B11 tip `c986f49227a47b855a547db96e65356f3674a9b8` (not from the `main` merge `92e46c1`).
**Charter:** owner "START B12 — BTC KALSHI HISTORICAL PILOT + DATA-SCIENCE READINESS" (2026-10-19). It implements the DR-2 pilot gate (`docs/decisions/2026-10-19_owner_data_readiness_decisions.md`).
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
| `src/pmv/pilot/kalshi_btc.py` | Offline profiler: `python -m pmv.pilot.kalshi_btc DIR [--show]`. Produces an aggregate-only JSON report covering native field types, nulls, numeric-string decimals, timestamp digits, ordering, duplicates, pagination, label integrity, candle coverage, the late-window × ask-band table (YES and NO sides, with distinct contracts and settlement instants), trade activity by remaining-time band, and trade↔candle reconciliation under both boundary conventions and offsets of −60, 0, and +60 s, with and without block trades. `--show` prints head and tail raw rows to the terminal only. Strict parsing: floats, bools, and offset-less times are refused and counted as malformed, never repaired. |
| `tests/unit/test_pilot_kalshi_btc.py`, `tests/unit/test_kalshi_pilot_sample_tool.py` | Deterministic tests on invented fixtures. The tool tests are offline (`fetch` is stubbed) and cover templates, the scope guard, the cutoff refusal, pagination termination, cumulative ceilings, and non-echo of proxy settings. They found and fixed one real defect: the trades request had dropped its `ticker` filter. |

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
```

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

**Not run.** The charter asks the seven specialists to review "the ACTUAL derived evidence". None exists yet, and a verdict on documentation alone would contradict the charter's §6 ("Do not issue conclusions from schema documentation alone"). The review runs after the §5 pilot has produced `b12_profile.json`.

## 11. Batch accounting (docs/external_access.md §1.3)

- Incidental exposures to real observations: **0**. The docs glossary page held only illustrative non-BTC ticker examples.
- Refused host attempts: **1** (`live-data` class; `api.elections.kalshi.com` and `external-api.kalshi.com`, refused by the permission classifier before any connection).
- Terms events: **0** (no terms page was reachable).
- Raw pilot data: none exists, so there is nothing to delete.
