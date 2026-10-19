# B10 reviews and dispositions (2026-10-19)

Three existing PMV specialist agents reviewed the uncommitted B10 working tree. Each was told not to edit files, make network requests, or run `check.sh`. All ran as `claude-opus-5-5` (exposure register Part B, M-1). The full reports are in the session record. This file lists every finding and how it was handled.

| Reviewer | Verdict | BLOCKER | MAJOR | MINOR | NOTE |
|---|---|---|---|---|---|
| Statistician | CONSISTENT WITH CONDITIONS | 0 | 9 | 5 | 1 |
| API / Execution Engineer | PROCEED WITH CONDITIONS (revise before commit) | 0 | 1 | 11 | 6 |
| Reliability / Red-Team | Revise before commit (no BLOCKER) | 0 | 4 | 8 | 4 |

**Rule applied:** every BLOCKER and MAJOR is fixed in the documents or assigned to a named owner decision. There were no BLOCKERs. MINORs were fixed where they changed a claim.

Abbreviations used below:
- **RD:** `research/data_sources/source_redundancy_decisions.md`
- **record:** `docs/decisions/2026-10-19_b10_source_reconnaissance.md`

## Statistician

| ID | Sev. | Finding (short) | Disposition |
|---|---|---|---|
| S-B10-01 | MAJOR | The BRTI test measured level error; for up/down contracts a constant basis cancels, so the differential error matters. The strike is a legal BRTI anchor. Proxy construction must be fixed beforehand | **Fixed.** RD BRTI Part A: per-contract-type error, strike point-in-time check, proxy fixed first |
| S-B10-02 | MAJOR | Ordering trap: a noisy proxy can make M-0 fail falsely, and K2 would then stop the project; the candle ask biases toward a false "go" | **Fixed / owner.** Part A runs before M-0; preregistered UNINFORMATIVE outcome; bias directions tabulated. K2 amendment is B10-D8 |
| S-B10-03 | MAJOR | The 1-minute candle ask as executable price is under-specified: staleness asymmetry, unknown sampling, no size, the ≤1-minute band | **Fixed.** RD "Stage 1 executable-price convention" (next-minute ask high; freshest-admissible baseline; taker-print check; ≤1-minute band not evaluable at the ask) |
| S-B10-04 | MAJOR | Promotion tests ignore S-9; deferring the live-only CFB/`pyth_value` channels silently excludes them from cycle 1 | **Fixed / owner.** RD "Relation to S-9"; B10-D9 before cycle registration |
| S-B10-05 | MAJOR | Promotion experiments are not well posed: no primary estimand, δ, power, error budget, or third outcome; D-B09-18 has no such threshold | **Fixed / owner.** RD "Promotion-test protocol"; numbers in B10-D8; the D-B09-18 misattribution removed |
| S-B10-06 | MAJOR | Dependence and leakage in the BRTI/Pyth tests: shared settlement instants, the strike chain, full-span corrections, materiality on irrelevant windows | **Fixed.** RD Part A items 4–6 and Pyth item 2 |
| S-B10-07 | MAJOR | Gold: stale Pyth windows fix outcomes mechanically; no numeric threshold; differential basis; low power | **Fixed.** RD Pyth experiment rewritten (stale-window rule, σ·√τ threshold, power, likely UNDERPOWERED-DEFER) |
| S-B10-08 | MAJOR | Irreversibility analysed only for Kraken L2 | **Fixed.** RD irreversibility table; `ticker` now captured as an integrity cross-check; REST book kept as a reconciliation probe; accepted losses recorded |
| S-B10-09 | MAJOR | "BRTI is not a new velocity signal" holds only with all constituents; the Coinbase DROP rationale is untested; no cross-venue path | **Fixed.** Rationales reworded as untested; cross-venue information experiment added; other free constituents named as the replacement path |
| S-B10-10 | MINOR | Capture-but-not-use conditions; the Tardis trigger was contradictory | **Fixed.** RD Kraken book row conditions; Tardis trigger rewritten (UNDERPOWERED-DEFER with a promising estimate; discovery only) |
| S-B10-11 | MINOR | Stage 1 biases not stated together; the archive CORE verdict assumed timestamp precision | **Fixed.** RD "What Stage 1 cannot show"; archive verdict made conditional, with the REST fallback |
| S-B10-12 | MINOR | The `expiration_value` prohibition was too broad | **Fixed.** Matrix note 13 limited to the current and unpublished values |
| S-B10-13 | MINOR | Matrix cells DIRECT where PROXY | **Fixed.** K-H reference cells → PROXY; vendor receipt → PROXY; daily cleared volume → PROXY |
| S-B10-14 | MINOR | Review file missing | **Fixed.** This file |
| S-B10-15 | NOTE | Recoverable verdicts fine; continuous-symbol mapping; label expectations | **Noted.** COMEX price-discovery and Polymarket statements labelled as expectations in RD; record the `GC.v.0` per-date mapping at acquisition |

## API / Execution Engineer

| ID | Sev. | Finding (short) | Disposition |
|---|---|---|---|
| API-B10-01 | MAJOR | The Kraken L2 "self-verifying" claim is overstated: the checksum verifies the top-10 state, not stream completeness, levels beyond 10, or stalls | **Fixed.** `kraken_l2.md`, record item 3, RD book row, P2 (depth 10 preferred, capture requirements) |
| API-B10-02 | MINOR | Pagination overlap observed, not documented; dedupe alone hides gaps | **Fixed.** `kraken_historical_trades.md` collector rules; record item 2 |
| API-B10-03 | MINOR | The 0.08% identical-timestamp figure was the four duplicate rows | **Fixed.** Corrected to zero among unique trades; the profiler now dedupes first |
| API-B10-04 | MINOR | The REST time is a float64 repr; join on `trade_id` | **Fixed.** Profile and record item 2 |
| API-B10-05 | MINOR | Checksum fixed-dp formatting is inferred, not documented | **Fixed.** `kraken_l2.md` |
| API-B10-06 | MINOR | `forecast_percentile_history` (5 s, authenticated) omitted; synthetic candle hazard | **Fixed.** `kalshi_trades.md`, matrix note 2 |
| API-B10-07 | MINOR | Candle and bar availability timing; spread exactness; `previous` derivable; Databento OHLCV buckets on `ts_recv` | **Fixed.** `kalshi_trades.md`, `kraken_ohlcvt.md`, `databento_gc_mbo.md` qualifiers |
| API-B10-08 | MINOR | The Kalshi key need only be `read`-scoped, but `read` exposes private data | **Fixed.** `kalshi_orderbook.md` |
| API-B10-09 | MINOR | Databento era qualifiers (MDP 2, ms timestamps, CMBP-1, `ts_in_delta` presence) | **Fixed.** `databento_gc_trades.md`, `databento_gc_mbo.md`, record item 6 |
| API-B10-10 | MINOR | Wrong or inconsistent matrix cells | **Fixed.** All listed cells changed; notes 33–34 added; Coinbase live-only marked |
| API-B10-11 | MINOR | Kalshi `ticker` and REST book have integrity value | **Fixed.** As S-B10-08 |
| API-B10-12 | MINOR | WS tool robustness (byte cap, frame cap, try/finally, frame checks) | **Fixed.** `kraken_ws_sample.py`; disclosed as a post-use edit |
| API-B10-13 | NOTE | REST tool acceptable | Noted |
| API-B10-14 | MINOR | Sample total was about 411 KB, not "under 400 KB" | **Fixed.** Record |
| API-B10-15 | NOTE | Tardis depth-1000 vs PMV depth parity | **Fixed.** RD Tardis row and experiment |
| API-B10-16 | NOTE | Proxy credential necessarily in the agent environment | Noted under B10-D6 |
| API-B10-17 | NOTE | Untracked sandbox placeholder files; review file missing | Staging by explicit path only; this file created |
| API-B10-18 | NOTE | Claims verified correct | Noted |

## Reliability / Red-Team

| ID | Sev. | Finding (short) | Disposition |
|---|---|---|---|
| RT-B10-01 | MAJOR | The wildcard F-09 denies did not stop allowlisted live-data hosts (`api.kraken.com`, `ws.kraken.com`, `api.exchange.coinbase.com`) | **Disclosed / owner.** Record tension table; B10-D10 (revert the allowlist at close; deterministic egress check, BLOCKING before `T0 − m`) |
| RT-B10-02 | MAJOR | The live-data use was authorized only generically ("None (in scope)" was wrong) | **Fixed / owner.** Record row revised; B10-D1(b) |
| RT-B10-03 | MAJOR | Terms-first glossed over for Kraken; the brief omitted terms-first | **Fixed / owner.** Record rows added; B10-D11 (no Kraken requests until M2) |
| RT-B10-04 | MAJOR | `raw.githubusercontent.com` fetches (fixtures and source files) conflict with rules 9 and 11 | **Disclosed / owner.** Record row; B10-D1(c); fixtures registered as X-11 |
| RT-B10-05 | MINOR | "No gold observation" overstated (unidentified fixture) | **Fixed.** Exposure register and record wording; X-11 |
| RT-B10-06 | MINOR | "No value recorded" inaccurate (derived statistics; transcripts) | **Fixed.** Wording qualified in the register and the record |
| RT-B10-07 | MINOR | Proxy credential persists in the local transcript | **Fixed.** Record wording; B10-D6 urgency raised |
| RT-B10-08 | MINOR | The CME hosts were retried by a subagent | **Fixed.** Record and `cme_datamine.md` |
| RT-B10-09 | MINOR | Review file missing | **Fixed.** This file |
| RT-B10-10 | MINOR | "A-4 is not satisfied" dropped from the timeline | **Fixed.** `docs/BRANCH_TIMELINE.md` |
| RT-B10-11 | MINOR | Tools edited after producing the evidence; unguarded `--out` | **Fixed.** Provenance note in the record; `--out` confined to `/workspace/.recon_tmp/` (tested) |
| RT-B10-12 | MINOR | Vendor documentation copies left in `$TMPDIR` | **Fixed.** Deleted at batch close |
| RT-B10-13 | NOTE | Exposure rows correct; X-10 Kalshi period missing | **Fixed.** "Undated; treated as 2026-10-19" |
| RT-B10-14 | NOTE | Cleanup and layout test pass; suggested a test case for `.recon_tmp/` | **Fixed.** Case added to `tests/unit/test_repository_layout.py` |
| RT-B10-15 | NOTE | No stray `.claude` directories; sandbox placeholder files | Noted; explicit-path staging |
| RT-B10-16 | NOTE | Coinbase and Databento probes were HEAD only; provenance complete | Noted |

## Not re-reviewed

The fixes were applied by the lead session after the reviews, and the reviewers did not re-review them. The owner may request a focused re-review of the revised RD protocol sections (S-B10-01 to S-B10-07) before adopting B10-D3 or B10-D8.
