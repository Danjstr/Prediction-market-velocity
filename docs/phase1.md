# Phase 1: Data Feasibility, Historical Acquisition, and Prospective Capture — Plan and Status

Working record for Phase 1. The authoritative requirements are START_HERE.md (Phase 1, Gate 1, Project-Wide Controls), CLAUDE.md, and PROJECT_BRIEF.md; where this file summarizes them, they win. This is not a gate record and not an owner-decision record.

## Current status and next step (as of 2026-10-20, B12)

**Active scope (owner decisions DR-17 to DR-21; PROJECT_BRIEF.md §1 "Active scope"):**
- **ACTIVE POC: BTC.** Kalshi short-horizon BTC markets, with Kraken XBTUSD/BTCUSD trades as the underlying.
- **GOLD: SHELVED FOR NOW.** Not cancelled, abandoned, or permanently dropped. Existing gold research is preserved. No new gold acquisition, pipeline, feature, or model work.
- **FUTURE EXPANSION: SPECIALIST MARKET-SELECTION REVIEW AFTER BTC POC.**
- **MODEL POLICY: SHARED PLATFORM + MARKET-FAMILY-SPECIFIC MODELS.**
- **PRIMARY RESEARCH DIRECTION: PMV 2.0** (owner decision, 2026-10-20). PMV forecasts short-horizon executable prices and tests round trips before settlement. The settlement strategy is superseded as primary and kept as a nested arm.

The current active branch is B12, `b12/btc-kalshi-pilot`, branched from the final B11 tip `c986f49`. The B11 paragraph below is historical.

**B12, 2026-10-20 (PMV 2.0 strategy amendment and revised BTC feasibility pilot).**
- **Review.** Eight PMV specialists reviewed the owner's PMV 2.0 proposal. All eight returned GO WITH CONDITIONS for a limited, measurement-first feasibility program. Summary: `research/governance/b12_pmv2_specialist_reviews.md`.
- **Owner approval.** The owner approved PMV 2.0 as the primary research direction, with modifications PV-1 to PV-23 (`docs/decisions/2026-10-20_b12_pmv2_strategy_pivot.md`):
  - a corrected rationale, so the payoff ratio is not the reason;
  - hold-to-settlement as a nested arm;
  - the two-stage target;
  - a taker-only baseline;
  - day-block statistical units with a finite trial budget and at most three horizons;
  - the factorial feature comparison;
  - the banking baseline L1/L2/L3 as ceilings, with finite refills;
  - net cents per contract × contracts per day as the commercial measure, replacing any daily-growth target;
  - prospective capture as the critical development dataset (Span D, development only, never protected);
  - premium-at-risk and stop-risk caps.
- **Amended documents.** PROJECT_BRIEF.md, CLAUDE.md, START_HERE.md (phase order unchanged), `docs/phase2.md`, and three agent files. The 2026-10-16 objective is annotated, not deleted.
- **Pilot.** The B12 Kalshi pilot is re-scoped (`research/kalshi/b12_btc_kalshi_pilot.md`): P1–P9 are kept; P10–P16, lifecycle incidence, the old-strategy control C1–C3, and stop conditions S-1 to S-6 were pre-registered before any Kalshi row was seen. The profiler implements them on synthetic tests.
- **Not done.** No Kalshi observation, no Kraken acquisition, no capture, no cloud, no paid resource, no `T0`.
- **Owner pre-commit review (2026-10-20):**
  - B12 is approved as the active numbered branch, and the four-commit plan is approved.
  - Fixes applied before commit: C1 uniqueness; observed timestamp resolution; S-1 now means "OWNER NO-GO REVIEW REQUIRED", never an automatic advance. A CLI single-report test was added; the suspected duplicate output was not real.
- **Owner items:**
  - O-PV-1 (empty-bid forced exit) stays OPEN until Gate 4.5;
  - O-PV-2: the banking baseline is kept, the sub-steps are PROPOSED ONLY, and the sweep, refill, and promotion parameters are NOT FROZEN;
  - O-PV-3: 324 is RESOLVED as an absolute maximum, not a target;
  - O-PV-4 (cycle deferrals) stays OPEN until the first protected cycle is designed;
  - still open from before: AR-B12-1, AR-B12-2, the guard-exception confirmation, DR-9, DR-3, the DR-8 capture preconditions, P-5 before capture, and DR-22.
- **Next:**
  - the owner reviews the B12 commit set;
  - the owner resolves AR-B12-1 and AR-B12-2 and supplies the fee schedule;
  - then the owner-run pilot (§5.1);
  - then the eight-specialist review of the profile.

**B11, 2026-10-19 (historical).** The active branch was B11, `b11/btc-poc-owner-decisions`. It is a governance-only branch, with no cloud provisioning.

**Owner data-readiness decisions, 2026-10-19 (after B10 merged by PR #9, `4019a75`).** Seven PMV specialists reviewed the obtainable data (one owner-authorized 1,000-row Kraken trade sample, exposure row X-12; Kalshi specifications; gold schema only). All seven returned GO WITH CONDITIONS. The owner then recorded decisions DR-1 to DR-15 (`docs/decisions/2026-10-19_owner_data_readiness_decisions.md`):
- **Approved:**
  - cloud-foundation work (DR-1): infrastructure, acquisition pipelines, capture infrastructure, normalization, features, and baselines;
  - BTC Stage 1 on Kalshi plus Kraken (DR-2), with a **bounded Kalshi KXBTC15M pilot gate** before bulk Kalshi acquisition;
  - Kraken archive plus REST gap-fill, after terms classification (DR-3);
  - prospective Kalshi and Kraken capture in principle (DR-8);
  - pre-T0 checklist **P-5** (DR-11).
- **Gold:** first ruled exploratory only (DR-5), then **shelved for now** (DR-17). Optional sources do not delay Stage 1, and CME DataMine stays DROP (DR-6). BRTI does not block initial research (DR-7).
- **Not approved:**
  - real money, protected evaluation, or `T0`/`T0 − m`;
  - EV, break-even, sizing, or capacity claims before the fee schedule is versioned (DR-9).
- The proxy-authentication carve-out is **rejected** (DR-10). PMV code never reads or parses the runtime proxy variables (DR-16).
- **Owner action pending (DR-22):** after the B11 commit is verified, the owner purges the specific local transcripts that contain the runtime credential (`docs/owner_actions/README.md` §4).
- **Next:** a charter for the cloud-foundation batch (DR-1). The Kalshi pilot (DR-2) needs Kalshi M1 / A-2 first. Kraken bulk acquisition needs the terms classification (DR-3). Nothing is provisioned, acquired, or captured yet.

**B10, 2026-10-19 (data source reconnaissance).** Under the owner's B10 charter, B10 (`b10/source-reconnaissance`, branched from final B09 `8b4e026`; B09 merged by PR #8, `bbcdd6b`) ran a bounded read-only reconnaissance: connectivity pass, 19 schema profiles, tiny samples inspected and deleted (Kraken REST trades for 2023-03-01; a 200-message Kraken WS capture; official non-gold Databento fixtures), the source × information value matrix, source verdicts, and a minimum viable source set. Record: `docs/decisions/2026-10-19_b10_source_reconnaissance.md`; results: `research/data_sources/source_redundancy_decisions.md`, `source_feature_value_matrix.md`, `schema_profiles/`.
- Stage 1, the BTC hypothesis test: Kalshi metadata, trades, and 1-minute candles, plus the Kraken trade archive. Free once Kalshi clears (M1, A-2) and the published Kraken terms are snapshotted and classified for private own-account use (B10-D11 as replaced; correspondence only if a material ambiguity remains).
- Stage 2, gold: Databento GC/MGC `trades`, `definition`, and `statistics`.
- Everything else is CONDITIONAL with a stated promotion experiment, REDUNDANT, or DROP.
- **Owner rulings (2026-10-19):** D1, D3, D6, D7, and D10 approved; D2 approved with clarification; D5 conditional; D8 in principle (thresholds frozen at cycle registration); D9 deferred; D4 not approved as written (default: licensed rows stay outside agent context unless the terms clearly permit it); D11 replaced (Kraken bulk acquisition waits for a published-terms snapshot and classification, not for vendor correspondence).
- **Owner correction (2026-10-19, runtime-secret hardening):**
  - D6 is resolved by control hardening. The exposed credential was not a PMV Squid credential (most likely a sandbox/runtime credential; issuer and lifetime not proven); there is no PMV Squid password to rotate.
  - D10 removal of `api.kraken.com`, `ws.kraken.com`, and `api.exchange.coinbase.com` from both egress layers is not required to close B10. It is required before any `T0 − m` (`docs/owner_actions/README.md` §3).
  - `tests/integration/test_live_host_egress_refusal.py` (with `PMV_EGRESS_PROBE=1`) still fails its Layer A check by design until then. Its applicable checks must pass before any `T0 − m` (P-5, owner decision DR-11).
  - A permanent diagnostic rule is in `docs/conventions.md`.
- Nothing was acquired, licensed, provisioned, or captured. **B10 is now the active branch**; the B09 bullet below is historical.

**B09 continued, 2026-10-18 (cloud-native direction).** The owner made PMV explicitly cloud-native: the Chromebook is a control and development terminal only, never the primary or intermediate store for bulk data and never a bulk-data relay. Within B09 the owner ordered a master data-source inventory and a review of the proposed GCP architecture before any acquisition. Record: `docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md`. Results:
- inventory: `research/data_sources/master_source_inventory.md`. Licensing is the dominant blocker. No market-data source is AVAILABLE_NOW. Every Kalshi surface PMV would use is NEEDS_LICENCE_CLARIFICATION;
- architecture (advisory): GCP ARCHITECTURE APPROVED WITH CHANGES; KEEP GCP (`research/cloud/pmv_cloud_architecture_review.md`). Staged security, Stage A for historical development and Stage B before `T0 − m`. GCP Batch as the training backend. B07/B08 stores on cloud disks with a sealed-object uploader (direction approved, implementation not);
- costs: `research/cloud/pmv_cloud_cost_model.md`;
- owner decisions D-B09-10 to D-B09-22 are pending, alongside D-B09-1 to D-B09-9;
- the approved local raw-store rule (Step 11 F-01, `~/pmv-protected/raw`) remains in force until D-B09-10 and the matching governance edits. Nothing is provisioned, acquired, or authorized.
- procurement: `research/data_sources/owner_source_action_sheet.md`, synchronized with owner-verified facts on 2026-10-18. Next: owner outreach M1 (Kalshi), M2 (Kraken), M3 (Databento), M4 (CF Benchmarks quote), M5 (Polymarket, if needed). The minimum viable dataset (Kalshi history, Kraken archive, Databento GC/MGC) targets about $0–$160 in market data, subject to permissions and the Databento estimator. No purchase, acquisition, `T0`, or holdout exists.


- **Phase:** Phase 1. No cycle, `T0`, split, or protected scope exists. No real market observation has been acquired, captured, or released to agents. The guard refuses every real request.
- **Strategy:** late-window, high-confidence (PROJECT_BRIEF.md §3; START_HERE.md "Strategy at a Glance"). B07 and B08 did not change it.
- **Gate status:** Gate 0 passed. Gate 1 has not been decided. **Historical acquisition is not authorized. Live capture is not authorized.**
- **Active branch:** `b10/source-reconnaissance` (B10; `docs/BRANCH_TIMELINE.md`; record `docs/decisions/2026-10-19_b10_source_reconnaissance.md`). Previously `b09/kalshi-source-qualification` (B09; record `docs/decisions/2026-10-16_b09_kalshi_source_qualification.md`), now merged by PR #8:
  - B09 was branched directly from final B08 (`5806d8c`), not from `main`, and contains everything through B08.
  - B08 was merged into `main` by PR #7 (merge commit `a6b5411`) and is a preserved historical checkpoint. B07 was merged by PR #6 (`2a46ffd`).
  - **B09 is source qualification only:** Kalshi official historical data as a candidate first source, and the owner-decision packet for A-1 to A-6. It acquires no data, contacts no Kalshi host, and changes no code. Its provisional verdict is NOT CURRENTLY QUALIFIABLE — EVIDENCE MISSING (the AR-3 terms, AR-B9-1 re-verification, gold existence, and retention depth).
  - A-1 to A-6 remain owner-controlled and unresolved. The owner's decisions D-B09-1 to D-B09-9 are pending.
  - B09 integrates through one pull request, opened after the owner's decisions are recorded. Merging is the owner's decision.
- **Blockers before the first historical acquisition** (`docs/external_access.md` §2):
  - a per-source owner approval naming its hosts (A-1);
  - an owner licence determination from verbatim terms (A-2);
  - the raw backup policy and a restore test on the real backup medium (A-3);
  - A-4 satisfied, which is not the case (below);
  - provenance and source-quality entries (A-5, A-6);
  - committed F-09 denies (done: `8517fc2`, behavioral check passed 2026-10-16).
- **A-4 status (B07):** see `docs/acquisition_readiness.md` and `docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md`. **A-4 is not satisfied.**
  - Implemented and tested on synthetic data only:
    - G-1: isolated, rlimited, seccomp-confined parse worker;
    - G-2 and G-3 for CSV, JSON, JSONL, and text: stdlib readers with pinned identities and required schemas;
    - G-4: fetcher semantics with per-redirect re-authorization, behind a synthetic transport;
    - G-5 for gzip, bzip2, and xz;
    - G-6: the end-to-end pipeline into the protected raw store, with a state machine, bound journal, and crash recovery.
  - Still open:
    - Parquet, DBN, and zstd readers, which need owner approval of a dependency (decision record B7-6);
    - the production network transport (B7-4);
    - the G-7 owner inputs;
    - a review record stating A-4 is satisfied.
- **Blockers before agents see any real observation:**
  - a registered cycle with `T0` and `m`, which first requires the pre-T0 owner checklist P-1 to P-4 in START_HERE.md, and B10-D10 egress tightening verified by the refusal test and the Layer B check (`docs/owner_actions/README.md` §3), in force before the cycle's `T0 − m`;
  - the H-2 per-row release tool, built, reviewed, and approved through an owner governance change (`docs/protected_information.md`).

  The release tool's code is deliberately **not yet written**: RT-B3-05 requires the owner's E-U1 catalog decision and a reviewed shared catalog first (`docs/release_tool_design.md`). B07 storage never releases anything (A-8).
- **Recommended next steps:**
  - **Owner:**
    0. B09: decide D-B09-1 to D-B09-9 (`docs/decisions/2026-10-16_b09_kalshi_source_qualification.md`, "Owner-decision packet"), including supplying the AR-3 documents listed there, and D-B09-10 to D-B09-22 (`docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md` §7: cloud successor to F-01, credential rule, Stage A/B isolation, cloud backup policy, architecture adoption, first cloud batch, kill and spend gates, licence letters). B08 is merged (PR #7, `a6b5411`);
    1. select the first historical source, and supply its terms (AR-3), so that A-1 and A-2 can be prepared (the post-B07 audit found no further source-neutral acquisition engineering worth doing before this);
    2. decide whether to approve the reader dependencies listed in decision record B7-6 (Parquet, DBN, zstd), or to defer those formats;
    3. approve a raw-data backup policy (A-3) and confirm or replace the "size class" reading (B7-7);
    4. pursue the licence terms for the first candidate source (Kalshi official historical data; AR-3);
    5. decide E-U1 (equivalence-catalog expansion), the first step before the H-2 release tool;
    6. prepare the pre-T0 checklist decisions P-1 to P-4 (START_HERE.md), and P-5, the egress tightening and refusal checks (owner decision DR-11);
    7. optionally decide B6S-14 (independent statistical audit of the release rules before the first release; not adopted).
  - **Agents** (no network, synthetic data only, from the active branch, in a batch chartered by the owner):
    - B08 (done; merged by PR #7): raw frame format v3 and collector hardening (F-11, F-12/F-27, F-33, F-37/RT-4), order-book continuity after rejected frames, and normalized capture artifacts;
    - B09 (in progress; stopped at the owner-decision boundary): Kalshi source qualification, the master data-source inventory, and the cloud architecture review, documentation only;
    - before live capture is authorized: timestamp plausibility and clock-sync state (RT-B8-05, B8S-03);
    - before real segmented-capture data is used for research: the exclusion ledger (B8S-01), trading status after a reset (B8S-02), and an end marker for sessions that are not `complete` (B8S-04);
    - before long real sessions are normalized: memory bounds (RT-B8-06);
    - after source selection: the production transport design and its review (B7-4), and any source-specific acquisition support (for Kalshi, the paginated REST design S1–S21 in `research/kalshi/b09_source_qualification.md` §4, if the owner approves D-B09-7);
    - after owner approval: the Parquet, DBN, and zstd readers inside the G-1 worker.

## Owner direction for Phase 1 (batch charter, 2026-10-15)

- First venue: Kalshi. Polymarket is deferred until separately approved and verified. Batch 3 (P5) approves Polymarket historical-data documentation research only.
- Underlyings: Bitcoin and gold.
- Horizon: 15-minute markets first, with an architecture that supports roughly 15 minutes to 1 hour.
- Strategy: quantitative short-horizon price-path and velocity prediction, not sentiment.
- Production runtime: free of LLMs and agents.
- Not authorized: real venue credentials, real-money execution, protected or holdout exposure, and irreplaceable live-data capture.

This direction came from the batch 1 charter. The Polymarket deferral, AR-1, and the batch 2 authorization limits are now recorded in `docs/decisions/2026-10-16_phase1_batch2_owner_decisions.md`. PROJECT_BRIEF.md §1 and §6 still name both venues; the deferral sequences the work and does not change the brief.

## What Phase 1 requires (START_HERE.md)

1. **Verify current official documentation** for Kalshi, Polymarket (deferred, above), BTC reference feeds, and gold reference feeds. Determine historical depth, timestamp resolution, trade data, order-book data, market metadata, settlement metadata, rate limits, WebSocket behavior, sequence handling, authentication, and latency characteristics.
2. **Build the ingestion architecture.** Preserve raw data, and capture contract identity per "Data and Contract Identity".
3. **Before any outcome-dependent inspection,** create the `cycle_id` and record the split-formation method, the declared development subset, and the protected interval.
4. **Begin high-frequency live capture** once the raw-data backup and retention policy exists and a backup-and-restore smoke test has passed.
5. **Reliability review** of disconnects, reconnects, stale messages, duplicates, missing messages, sequence gaps, timestamp anomalies, and persistence failures.
6. **Gate 1:**
   - data sufficient to construct valid short-horizon training observations;
   - per venue relied on, verification from current official sources of: API availability and permitted use, account eligibility, jurisdiction, market access, authentication, terms, and live-trading limits, with sources and retrieval dates;
   - raw-data backup policy and restore smoke test.

## Prerequisites and open decisions

From `docs/gate0_readiness.md` ("Deferred findings and deadlines") and `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`. Status is as of this batch.

| Item | Must be resolved before | Owner | Status |
|---|---|---|---|
| F-16 venue and jurisdiction eligibility, and whether in-scope gold contracts exist | Any venue account or credential, or any real collection or trading integration | Owner, with API / Execution research | Open. Batch 2 documentation findings are in `research/kalshi/venue_verification.md` §5. The terms, Developer Agreement, and eligibility could not be retrieved (AR-3). No gold event-contract series is documented (E-1). |
| F-06 prospective holdout as the default formation | Agents see any real observation | Owner | **Decided** (batch 4 H-1): prospective. `T0`, `m`, and the cycle conditions are not yet declared |
| F-08 release architecture (trusted collector plus release by receipt time) | Agents see any real observation | Owner | **Decided** (batch 4 H-2): owner-controlled, fail-closed, per-row release. The release tool is not built |
| F-07 power-based holdout size and unit of independence | First real protected scope or cycle | Owner, with Statistician | Unit of independence **decided** (batch 4 H-6). Power floor and holdout size open, fixed per cycle before `T0` (H-1) |
| F-17 minimum economic thresholds and kill criteria | Substantive strategy or model work on real data | Owner, with Quant / Business Lead | Open |
| F-03 credential isolation implementation | Any venue credential, including data-only | Owner | Open. No credential exists |
| F-09 network and WebFetch denies for market-data hosts | Phase 1 real collection, and any agent web research (WebFetch or WebSearch) after a cycle's `T0 − m` | Owner (settings are governance) | Policy **decided** (batch 4 O-6, host classes in `docs/external_access.md`). Deterministic denies **committed** in `8517fc2` (B06), behavioral check passed 2026-10-16 |
| F-11 capture segmentation and salvage; F-12 frame timing and direction (with F-27); F-33 | Phase 1 real collection | API / Execution, Reliability | **Implemented in B08** on synthetic data (frame format v3) and Red-Team reviewed. Owner decided B8-1 to B8-7 on 2026-10-16. Open before live capture is authorized: timestamp plausibility and clock-sync state (RT-B8-05, B8S-03). Open before long real sessions are normalized: memory bounds (RT-B8-06) |
| F-26 storage-event claims and restore dependency | Phase 1 real collection | API / Execution, Reliability | Open (not in B08 scope) |
| F-37, RT-4: demo data treated as real; collectors refuse the test environment | Phase 1 real collection | API / Execution | **Implemented in B08** (B8-4 and B8-5 confirmed; B8-6 confirmed for now, revisitable after E-6). Owner-approved endpoints (`APPROVED_CAPTURE_ENDPOINTS`) are empty, and E-6 (demo accounts and keys) is open |
| F-32 collector host and alert recipient | Phase 1 real collection | Owner | Open |
| F-21b per-gate scope and minimum-reviewer table | Phase 1 real collection | Owner | Open |
| Raw-data backup and retention policy, plus restore smoke test | First live capture, and no later than Gate 1 | Owner | Open |
| F-15, F-24, F-30; Step 9 S-2, S-4, S-6 per F-08 | Agents see real observations | Various | Open |

**Consequence.** Until these are resolved, Phase 1 work is limited to documentation research (subject to access approval), synthetic fixtures, and deterministic infrastructure. No real observation may be shown to agents, and no real capture may begin. The S-6 collection rule in `docs/protected_information.md` allows collection in principle; it does not override these prerequisites.

## Interpretation that needs owner confirmation (S-6)

START_HERE.md Phase 1 lists properties to "determine" (historical depth, timestamp resolution, and so on). `docs/protected_information.md` forbids agents from inspecting real observations before the split and protected scope exist.

This batch reads the requirement as follows:
- these properties are determined from official documentation;
- empirical confirmation comes only from deterministic collector **metadata**, produced outside agent sessions and containing no prices, quantities, outcomes, or contract identifiers. Examples: message counts, inter-arrival statistics, gap and reconnect counts, timestamp-field presence and resolution;
- such metadata needs the owner-approved release design (F-08) before agents see it.

This is a recommendation, not an approved rule.

## Batch 1 (B02, `phase1/kalshi-data-foundation`): venue-neutral data foundation

Done without credentials, real data, or network access:

- `src/pmv/market_data/`: canonical contract identity, observations, timestamp semantics, decision-time views and feature rows, labels kept apart from observations, deterministic validation, the raw-to-normalized replay boundary, deterministic order-book reconstruction with enumerated faults (point-in-time from an `AsOfView`), a synthetic adapter, and a fail-closed Kalshi boundary. See `docs/market_data.md`.
- Tests:
  - `tests/unit/test_market_data_*.py`;
  - `tests/replay/test_market_data_replay.py`: raw frames encoded and read back with the real raw format;
  - structural boundary tests: no network imports, no wall-clock reads, and feature-side modules never import labels.

No Kalshi field, endpoint, unit, fee, rule, or eligibility fact is encoded. `pmv.market_data.kalshi.REQUIRED_VERIFICATIONS` lists what must be verified first.

## Batch 2 (B03, `phase1/kalshi-venue-verification`): Kalshi venue verification

This was documentation research only, under AR-1 (owner decisions D1–D3 in `docs/decisions/2026-10-16_phase1_batch2_owner_decisions.md`). No credential was used, no API host was contacted, no market value was retrieved, and no code changed.

- **Summary:** `research/kalshi/venue_verification.md`. It covers verified facts, unresolved facts, project assumptions, versioning options, F-16 findings, and escalations E-1 to E-5.
- **Detail:**
  - `research/kalshi/api_documentation_findings.md`: API / Execution;
  - `research/kalshi/statistician_review.md`: the development Statistician, as self-review;
  - `research/kalshi/red_team_review.md`: Reliability / Red-Team.
- **Sources:** `research/sources.md` lists 60 docs.kalshi.com files with retrieval times and SHA-256 hashes, plus the kalshi.com pages that could not be retrieved.

**Status of `pmv.market_data.kalshi.REQUIRED_VERIFICATIONS`** (documentation level only; nothing is verified by test):

| Status | Items |
|---|---|
| Documented | `authentication_for_market_data`, `rest_market_and_event_metadata_schema`, `websocket_channels_and_message_schema` (with conflicts), `orderbook_representation_and_price_units` (sort-order conflict), `trade_print_schema_and_identifiers`, `early_close_and_extension_semantics` (mechanics), `lifecycle_status_messages_and_result_fields` (no WS dispute or amend events) |
| Partly documented | `timestamp_fields_and_resolution` (REST timezone and precision missing), `rate_limits` (unauthenticated limits missing), `historical_data_depth_and_resolution` (resolution yes, retention no, no historical book), `fee_schedule_and_effective_dates` (fields and endpoints yes, rates no), `demo_environment_scope_and_fidelity` (fidelity warning yes, scope no) |
| Unresolved | `api_terms_and_permitted_use`, `account_and_jurisdiction_eligibility`, `websocket_sequence_and_snapshot_semantics`, `sequence_number_scope_per_subscription_or_market`, `orderbook_delta_semantics_absolute_or_relative` (relative is a strong inference only), `btc_and_gold_series_availability`, `contract_rules_settlement_source_and_timing`, `settlement_reference_window_or_averaging`, `tie_rounding_and_void_rules` |

`KalshiNormalizer` therefore stays fail-closed. No Kalshi parser, `ContractSpec` builder, or label parser was written. They stay blocked by:
- E-2: the point-in-time versioning decision (decided in batch 4 as H-3, Option D; implementation open);
- UR-4: the contract rules;
- UR-6 and UR-7: sequence scope and delta semantics. They need a recorded test, using a differential two-connection comparison, once a credential and collector are approved. Demo can falsify but cannot confirm production behavior, and a demo account or key needs its own owner classification (E-6).

**Remaining Phase 1 blockers added by batch 2:**
- E-1: gold scope;
- E-3: a market-data credential is needed for WS book capture, because the WebSocket requires a signed key;
- E-4: an availability rule for historical archive rows (decided in batch 4 as H-5);
- AR-3: terms and contract documents;
- E-6: classification of demo accounts and keys;
- E-7: network egress scope and the F-09 denies;
- Red-Team blocking conditions for the parser and collector: RT-B2-01, 02, 03, and 06 in `research/kalshi/red_team_review.md`.

## Batch 3 (B04, `phase1/historical-data-strategy`): historical data strategy

**Charter (owner, 2026-10-16).** Recorded in `docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`, decisions P1–P6:
- **P1.** Verified existing historical data is preferred over waiting to regenerate equivalent observations. Prospective PMV capture is prepared in parallel.
- **P2.** Historical data exposed to development can never become protected holdout data.
- **P3.** Broad public research within the sandbox allowlist, with external material treated as untrusted.
- **P4.** Gold stays in scope.
- **P5.** Polymarket historical-data documentation research is approved.
- **P6.** This batch is inventory and design only.

This was documentation research and design only. No credential was used, no market-data API returned content, and no dataset or sample was downloaded. One request to an exchange API host (`api.exchange.bullish.com`) was attempted and refused by the proxy (`research/historical_data/incident_2026-10-16_api_host_request.md`). Agents were incidentally exposed to aggregate outcome statistics and to a page containing a live reference-index value (cfbenchmarks.com). Nothing was recorded or used. The committed protected-scope registry is empty, so even a "tiny sample" was not safe under existing policy, and none was taken.

**Outputs:**
- the historical source inventory (`research/historical_data/`):
  - `inventory_prediction_markets.md`: Kalshi, Polymarket, and prediction-market archives;
  - `inventory_underlying_btc_gold.md`: BTC exchanges, vendors, and reference indices; COMEX/CME, LBMA, and other gold sources;
  - `inventory_open_academic_regulatory.md`: open datasets, literature and software, regulatory sources;
  - `feasibility_summary.md`: ranked acquisition recommendations, inaccessible sources, and access requests;
- the Phase 2 design: `docs/phase2.md`, covering general cleaning and dataset engineering, identity, duplicates, and dependence;
- `research/historical_data/point_in_time_metadata_architecture.md`: the proposal for H-3, H-4, and H-5;
- reviews:
  - `research/historical_data/statistician_review.md`;
  - `research/historical_data/red_team_review.md`;
- `research/historical_data/incident_2026-10-16_api_host_request.md`: the API-host near-miss incident record.

**Owner decisions raised:** H-1 to H-8, plus the Red-Team items O-2 to O-8 (decision record, "Owner decisions raised by this batch"). P4 settles the scope half of E-1. H-3 restates E-2. H-5 restates E-4.

**Key findings** (detail in `research/historical_data/feasibility_summary.md`):
- **No official historical order books.** Neither Kalshi nor Polymarket publishes them. Historical depth exists only in paid or license-unclear third-party captures. Book-dependent evidence and the protected holdout must therefore come from prospective capture.
- **Discovery-grade official history.** Kalshi's historical trades, candles, and settlements, and Polymarket's on-chain fills and resolutions, are primary sources usable for discovery-grade development, under H-4 and H-5.
- **Settlement and fee regime breaks.**
  - Kalshi BTC rulebook changes (CFTC filings).
  - Polymarket's Chainlink TWAP from 2026-08-07, V2 from 2026-04-28, and taker fees from 2026-01-05.

  These partition the history.
- **Gold.**
  - KXGOLD15M is reported by secondary sources only: Pyth-settled, about 2 months of history.
  - The COMEX intraday development source is Databento GLBX.MDP3 (paid).
  - Open data cannot support gold. P4 keeps gold in scope; evidence will be thin.
- **Licensing is unresolved for most sources.** No acquisition precedes a licence determination.
- **Counter-evidence.** A public 2026 study (OpenMarket, arXiv 2607.26245) reports no after-cost edge for a closely related Polymarket BTC 15-minute design.
- **Incidental pre-cycle exposure.** Aggregate KXBTC15M outcome statistics (2026-01 to 2026-10) appeared in a dataset card read by research agents. No values were recorded. With F-06, this rules out any BTC-family or gold-family snapshot holdout ending on or before 2026-10-16, and the first protected interval must start after 2026-10-16 plus margin (pre-cycle exposure register in the decision record).

**Source-access limitations recorded:** `www.cmegroup.com` (allowlisted, but anti-bot behavior returns no usable content) and `kalshi.com` (Vercel challenge, AR-3). Neither is bypassed.

## ACCESS REQUESTS

### AR-1: Kalshi official documentation (blocking for the Kalshi adapter and F-16)

**Status: APPROVED 2026-10-15** (temporary, read-only, documentation only; `docs/decisions/2026-10-16_phase1_batch2_owner_decisions.md` D1). Used in batch 2. `docs.kalshi.com` was retrieved. `kalshi.com` returned a bot challenge (HTTP 429) and was not retrieved (see AR-3).


- **Resources.**
  - `docs.kalshi.com`: API reference, covering REST market, event, and series metadata; the WebSocket channels, message schemas, sequence and snapshot semantics; authentication requirements, including for public market data; rate limits; historical-data endpoints and depth; the demo environment; and any OpenAPI or AsyncAPI specification files it publishes.
  - `kalshi.com`: the documentation, legal, and help pages for terms of service and API or developer terms; account and jurisdiction eligibility; the fee schedule and its effective dates; and the contract rule pages for BTC and gold series, covering settlement source, determination timing, rounding, ties, and voids.
- **Why.**
  - Phase 1 requires verification from current official sources.
  - Gate 1 and F-16 require eligibility and terms verification before any account, credential, or collection.
  - The Kalshi parser and `ContractSpec` builder cannot be written without verified semantics, and the batch charter forbids guessing them.
- **What will be retrieved.** Documentation text and published schema files only. Each source is recorded in `research/sources.md` (title, URL, retrieval date, status), and rule-text SHA-256s are recorded for `VERIFIED_OFFICIAL` specs.
- **Excluded.** No market-data API host is called, no live or historical market values are retrieved, and no account or credential is created.
- **Example values.** Documentation may contain example payloads with market values. They are not used as data.
- **Access.** Temporary, read-only, for the venue-verification task. Phase 12 re-verification is a new request.
- **Hosts that must stay blocked.** The Kalshi trading and market-data API hosts, consistent with F-09.

### AR-3: Kalshi terms, fee schedule, and contract-rule documents (blocking for F-16, fees, and the BTC spec builder)

- **Problem.** AR-1 approved `kalshi.com`, but every `kalshi.com` page tried on 2026-10-16 (`/terms`, `/developer-agreement`, `/fee-schedule`, `/docs/kalshi-fee-schedule.pdf`) returned HTTP 429 with a "Vercel Security Checkpoint" JavaScript challenge. Agents do not circumvent bot protection. `www.kalshi.com` is not on the network allowlist.
- **Needed documents.**
  - Terms of service.
  - Developer Agreement (docs.kalshi.com says API use binds the user to it).
  - Fee-schedule PDF (`Series.fee_type` points to it).
  - The Kalshi rulebook.
  - The contract terms for the BTC series, and for any gold series, behind each series' `contract_terms_url` and `contract_url`.
  - Help-center eligibility and demo-account articles (`help.kalshi.com`).
- **Options, for the owner to choose (not decided here).**
  1. **Preferred.** The owner downloads the documents in a normal browser and places them in a repository path the owner chooses, for example `research/kalshi/source_documents/`, with retrieval date and URL. They are legal and rule documents, not market observations.
  2. Allowlist `help.kalshi.com` (read-only, documentation only). This is a new domain and needs owner approval.
  3. Contract-terms documents may be hosted on a domain named only in a `GET /series/{ticker}` response (`contract_terms_url`). Learning that URL requires a market-data API call, which is not authorized. Under option 1 the owner can follow the links from the kalshi.com market rules page instead.
- **Excluded.** API hosts, market pages showing live prices, account login, and any attempt to bypass the challenge.

**Status after B09 (2026-10-16):** still open. B09 lists the exact documents the owner is asked to supply (`docs/decisions/2026-10-16_b09_kalshi_source_qualification.md`, "AR-3: documents the owner must supply"). No web copy was substituted for them.

### AR-B9-1: one-time re-verification of Kalshi API documentation (B09; owner decision D-B09-8)

- **Host and paths:** `docs.kalshi.com`, an exact list of 18 paths covering the historical-tier, pagination, rate-limit, series, and events pages, `llms.txt`, and the two spec files (`research/kalshi/b09_source_qualification.md` §1.2).
- **Class:** `docs`.
- **Purpose:** re-verify the 2026-10-15 snapshot facts that A-1 and the paginated REST design rely on.
- **Why it is not covered today:** AR-1 was approved as temporary, for the batch 2 work, and its expiry was never recorded (E-7). §1.1 rule 3 of `docs/external_access.md` also requires the licensor's terms first, and they are not yet owner-supplied (AR-3).
- **Status:** not approved; no request made.

### AR-4 to AR-16: batch 3 documentation access requests

These are listed in `research/historical_data/feasibility_summary.md` §6, and none is used. The high-priority ones are:
- AR-4: Kalshi contract-terms PDFs, or owner-supplied copies;
- AR-6: Polymarket US docs and legal, if the owner is a US person;
- AR-8: Pyth documentation, for gold;
- AR-9: CF Benchmarks methodology, owner-supplied because the site terms bar automated access. AR-9 takes over the BTC half of AR-2;
- AR-10: CME rulebook, specifications, and licence documents, owner-supplied, because `www.cmegroup.com` gives no usable content to automated clients.

Each is documentation only. Any data acquisition is a separate request under H-2 and H-7.

### AR-2: settlement reference-source documentation (conditional on AR-1)

Once AR-1 identifies the official settlement sources for Kalshi BTC and gold contracts (for example, a CF Benchmarks index for BTC), request read-only access to that provider's **methodology documentation** domain only. The purpose is to define `resolution_source_id` semantics and the BTC/gold reference-feed requirements. No price data is requested. The domains are named after AR-1, not guessed now.

**Status after batch 2:** still conditional. The docs.kalshi.com pages link to CF Benchmarks documentation (`docs.cfbenchmarks.com`) for the BRTI passthrough. They do **not** state that any contract settles on BRTI or on any averaging window. Gold settlement sources are undocumented. AR-2 is not raised until the contract terms (AR-3) name the settlement sources.

## Batch 4 (B05, `phase1/acquisition-safety-decisions`): owner decisions and acquisition safety

Governance and policy only. No real market dataset was acquired or inspected, and no code changed. Owner decisions H-1 to H-8, O-3, O-5, O-6 (as clarified), and O-9 are recorded in `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`. The batch also:
- replaced the CLAUDE.md "do not inspect real market observations at all" rule with five observation classes;
- reconciled the "oldest 70% / newest 30%" wording with the prospective holdout;
- added the host-class rule and the historical acquisition gate (`docs/external_access.md`);
- created the exposure register (`docs/exposure_register.md`).

**Owner rulings on the batch 4 reviews (2026-10-16):**
- B4S-1 and B4S-8 were confirmed.
- Approved: E-B4-1, E-B4-3, E-B4-4 (modified), E-B4-6 (modified), E-B4-8, and E-B4-9(a). E-B4-5 was approved as a pre-T0 analysis requirement.
- E-B4-7 was rejected as proposed; the reconstruction-based principle was adopted instead.
- E-B4-2 and E-B4-9(b) were deferred, but are mandatory decisions before `T0`.
- All four review tightenings were approved.
- The owner also directed that the late-window, high-confidence strategy objective be recorded (PROJECT_BRIEF.md §3).

Full rulings and the pre-T0 checklist are in the decision record.

## B07 (`b07/phase1-acquisition-pipeline-hardening`): acquisition pipeline hardening

**Charter (owner, 2026-10-16).** Recorded in `docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md`. Synthetic data only: no real data, network host, credential, approval, licence determination, gate decision, `T0`, holdout access, or modeling.

**Done:**
- **G-1.** An isolated parse worker:
  - resource limits applied by the parent before exec;
  - launch with `python -I -S` and an empty environment, with a finder that loads only `pmv` from the package root;
  - `no_new_privs` and a seccomp **allowlist** (argument-filtered `fcntl` and `ioctl`) installed before any input is read;
  - a framed protocol enforced by a parent that has made itself non-dumpable.
- **G-2, G-3, G-5.** Stdlib readers with pinned identities and required schemas, and bounded gzip, bzip2, and xz decoding. Parquet, DBN, and zstd are deferred for owner dependency approval.
- **G-4.** Fetcher semantics behind an injectable transport. No production transport exists.
- **G-6.** The plan and evidence records, the explicit state machine, and the orchestrator into the protected raw store, with crash and restart recovery.
- **RT-B6-26 and RT-B6-27.** Torn-tail recovery and the bound journal.
- **RT-B6-28.** Re-reviewed: correct in `release`; the gaps in `receive` and move-aside are fixed (RT-B7-07).

Tests and review:
- 376 new synthetic tests, including fault injection at every pipeline boundary and real `SIGKILL`s.
- The independent Red-Team review is in `research/governance/b07_acquisition_pipeline_red_team_review.md`. It ran five rounds: round 1 found one BLOCKING finding (RT-B7-01, worker-to-parent channels under a denylist) and one MAJOR finding (RT-B7-02, injectable real-mode gate). Both were fixed. The final verdict at `4170b3c` is no BLOCKING and no MAJOR finding, with documented MINOR residuals. A-4 is still not satisfied.
- No Statistician review was triggered: B07 does not touch release, holdout, `T0`, or equivalence semantics.

## B08 (`b08/prospective-capture-hardening`): prospective-capture hardening

**Charter (owner, 2026-10-16).** Recorded in `docs/decisions/2026-10-16_b08_prospective_capture_hardening.md`. Synthetic data only. No acquisition, live capture, network host, credential, source selection, A-1 to A-6 decision, transport, dependency, gate decision, `T0`, holdout, release code, or modeling.

**Done** (`docs/raw_data.md` "Segmented prospective capture, frame format v3"; `docs/market_data.md`):
- **F-12 with F-27:** raw frame format v3, `PMVRAW3` (the `PMVRAW2` draft is refused):
  - hash-chained segment headers carrying the clock domain;
  - the venue and deployment environment on every frame, matched against the segment (owner decision B8-2, as modified);
  - payload direction, connection, and monotonic receipt time;
  - one session-wide sequence.
  - v1 now starts captures only in `test`.
- **F-11:** bounded, immutable segments, plus the following:
  - recovery quarantines and never resumes;
  - deterministic salvage (`longest_valid_frame_prefix_v1`), which never modifies quarantined bytes;
  - chain reading never bridges a gap.
- **F-33:** a real process is killed at every named durable boundary.
- **F-37 and RT-4:**
  - environment authorization that the store re-derives;
  - demo data is protected like real data and refused by every segmented-capture loader;
  - the approved-endpoint registry is empty, so live capture refuses;
  - record-creating CLIs refuse `--environment test`.
- **Order-book continuity:** rejected frames break every book (`frame_rejected`), and solicited snapshots never recover one (RT-B2-03).
- **Normalized artifacts:** deterministic and content-addressed by derivation. They carry per-file digests, a session cross-check, and re-derivation (`verify_artifact`).

**Reviews:**
- Independent Reliability / Red-Team (`research/governance/b08_prospective_capture_red_team_review.md`):
  - round 1 found **BLOCKING** RT-B8-01 (artifact integrity) and **MAJOR** RT-B8-02 (a re-issuable authorization);
  - both were fixed and re-verified in round 2;
  - the round-2 MINORs RT-B8-12 to RT-B8-14 were fixed afterwards, and round 3 verified them.
- Statistician (`research/governance/b08_statistician_review.md`): PASS WITH CONDITIONS, with no look-ahead.
- Cold-start review: `research/governance/b08_cold_start_review.md`.

**Still open.** The authoritative list is the decision record, "Outcome" → "Residuals and conditions":
- **Before live capture is authorized:**
  - RT-B8-05 and B8S-03: timestamp plausibility and clock-sync state;
  - the RT-B8-12 residual: a writer may wait up to about 1 s under lock contention.
- **Before long real sessions are normalized:** RT-B8-06, memory bounds.
- **Before real segmented-capture data is used for research:**
  - B8S-01: the exclusion ledger;
  - B8S-02: trading status after a reset;
  - B8S-04: an end marker for a session that is not `complete`.
- **Before experiments on segmented-capture artifacts:**
  - B8S-05: pin the parser version;
  - record `artifact_digest` and load with `expected_digest` (the RT-B8-01 residual).
- **Before a real venue parser:** B8S-06, parser tests for the skip list and for solicited replies.
- **Before any `APPROVED_CAPTURE_ENDPOINTS` entry:** re-review RT-B8-13.
- **B8S-07 (note):** concurrent connections in one session share book keys. That is conservative today; revisit if a session ever multiplexes feeds.
- **F-26:** not in B08 scope.

**Not changed:**
- `src/pmv/acquisition/` (the B07 review still covers it).
- Gate 1 is still undecided.
- Historical acquisition and live capture are still not authorized.

## Recommended next batches

*Historical lists from batches 1 and 2. They are superseded by "Current status and next step" at the top of this file. F-06 and F-08 have since been decided (batch 4 H-1 and H-2).*

1. **Venue verification: done as far as `docs.kalshi.com` allows (batch 2).** The verified parser, `ContractSpec` builder, and resolution parser remain blocked by the H-3 implementation (E-2 decided as Option D), UR-4, UR-6, and UR-7 (see "Batch 2" above).
2. **Raw format v2 and collector hardening (no network needed).**
   - F-12: monotonic receive time and message direction in frame v2, with F-27;
   - F-11: capture segmentation and salvage;
   - F-37 and RT-4: collectors refuse the test environment and demo data is treated as real;
   - F-33: durability-ordering tests.
   - carry rejected and skipped frame dispositions into the book engine, so a rejected frame breaks book continuity directly (red-team review of `books`).
3. **Normalized-capture artifacts (no network needed).** Content-addressed, versioned normalized outputs keyed by raw capture hash plus parser identity, with a closed schema.
4. **Owner decisions:** F-06, F-08, F-16, F-07, F-17, F-09, F-03, F-32, F-21b, and the raw-data backup policy. Real collection and agent-visible data stay blocked until they are resolved.
5. **Point-in-time contract-spec versioning (Statistician M1; blocking before the Kalshi spec builder).** Needs the owner's identity-design decision (`docs/market_data.md`, review m4).
6. **Exclusion ledger and policy recording (Statistician M4).** Persistent counts of exclusions and faults by reason, regime, and period, keyed by policy IDs.

### Recommended next batches after batch 2

1. **Owner decisions:** E-1 (gold scope), E-2 (point-in-time versioning option; since decided as H-3), AR-3 (how the terms and contract documents are obtained), and E-3 (whether, and under which F-03 controls, a read-scope market-data credential is ever created). Also the earlier open items.
2. **Raw format v2 and collector hardening (no network needed),** now informed by documented Kalshi behavior:
   - per-subscription `use_yes_price` and connection metadata in frames;
   - fail-closed handling of terminal errors 10 and 25;
   - scheduled Thursday maintenance disconnects;
   - F-11, F-12, F-33, F-37 / RT-4.
3. **Kalshi parser against documented-schema fixtures (no network needed, after the H-3 implementation):**
   - strict schema validation pinned to the recorded spec hashes;
   - relative-delta handling kept behind an explicit, tested assumption flag until UR-7 is tested;
   - metadata and outcome-field quarantine.
4. **Contract-rule verification (after AR-3):** BTC series rules, and gold if any exist. Then AR-2.

## Methodology recommendations for owner decision (Statistician review, 2026-10-15)

These would change approved validation methodology, so they are proposals, not adopted rules. Both feed F-07. *Status (batch 4): R1 was adopted as H-6 (unit of independence), and R2 is reflected in `docs/phase2.md` Policy 2. The text below is the original proposal.*

- **R1: unit of independence.**
  - *Current state.* No unit is defined, and `spec_key` is the de facto row key.
  - *Concern.* Decision rows inside one contract share one label. Strikes in one event share one outcome, and back-to-back windows share the price path. A fee or rule correction gives the same market a new `spec_key`.
  - *Proposal.* Group by outcome-reference event (underlying plus reference time) for splits, cluster or block bootstrap, and effective-sample-size accounting.
  - *Benefit.* Honest uncertainty and no cross-split leakage.
  - *Cost.* Far fewer effective samples.
  - *Urgency.* Blocking before the first real protected scope or cycle (F-07).
- **R2: purge and embargo by label end.**
  - *Proposal.* Each label ends at the later of `outcome_reference_time` and the resolution's receipt, not at `close_time`. Whole contracts and events stay on one side of a frozen boundary, and feature lookbacks are purged too.
  - *Urgency.* Required at the Phase 2 split freeze.

