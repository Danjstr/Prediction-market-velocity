# Phase 1: Data Feasibility, Historical Acquisition, and Prospective Capture — Plan and Status

Working record for Phase 1. The authoritative requirements are START_HERE.md (Phase 1, Gate 1, Project-Wide Controls), CLAUDE.md, and PROJECT_BRIEF.md; where this file summarizes them, they win. This is not a gate record and not an owner-decision record.

## Current status and next step (as of 2026-10-16, B06)

- **Phase:** Phase 1. No cycle, `T0`, split, or protected scope exists. No real market observation has been acquired, captured, or released to agents. The guard refuses every real request.
- **Strategy:** late-window, high-confidence (PROJECT_BRIEF.md §3; START_HERE.md "Strategy at a Glance").
- **Gate status:** Gate 0 passed. Gate 1 has not been decided.
- **Active branch:** `b06/governance-continuity-sync` (B06; `docs/BRANCH_TIMELINE.md`). It contains batch 4 (B05, `a1752b4`), the B06 governance continuity sync (`docs/decisions/2026-10-16_b06_governance_continuity_sync.md`), and the B06 acquisition-readiness tooling (`docs/acquisition_readiness.md`). It integrates into `main` through one pull request; merging is the owner's decision.
- **Owner actions pending outside agent sessions** (`docs/owner_actions/README.md`):
  1. apply the F-09 host-class settings patch. This is a priority blocker for any historical acquisition;
  2. apply the agent-file split-wording patch.
- **Blockers before the first historical acquisition** (`docs/external_access.md` §2):
  - a per-source owner approval naming its hosts (A-1);
  - an owner licence determination from verbatim terms (A-2);
  - the raw backup policy and a restore test on the real backup medium (A-3);
  - a reviewed safe-parsing acquisition tool with passing fault-injection fixtures (A-4);
  - provenance and source-quality entries (A-5, A-6);
  - committed F-09 denies.
- **A-4 status (B06):** the source-neutral building blocks and every named fault-injection fixture exist, tested on synthetic data only. The Reliability / Red-Team review and its re-verification are in `research/governance/b06_acquisition_tooling_red_team_review.md`. **A-4 is not satisfied.** Still missing:
  - parser process isolation with resource limits;
  - pinned, reviewed Parquet and DBN readers;
  - the fetcher, with redirect re-checks and size caps;
  - the end-to-end pipeline into the protected raw store (`docs/acquisition_readiness.md`).
- **Blockers before agents see any real observation:** a registered cycle with `T0` and `m` (which first requires the pre-T0 owner checklist P-1 to P-4 in START_HERE.md); and the H-2 per-row release tool, built, reviewed, and approved through an owner governance change (`docs/protected_information.md`).
- **Recommended next steps:**
  - **Owner:**
    1. review and merge the B06 pull request;
    2. apply the F-09 settings patch and the agent-file patch on the active branch;
    3. approve a raw-data backup policy (A-3);
    4. pursue the licence terms for the first candidate source (Kalshi official historical data; AR-3).
  - **Agents (no network, synthetic data only, from the active branch):** close the remaining A-4 gaps (parser process isolation, pinned readers, fetcher design with redirect re-checks, the pipeline into the protected raw store), then request a fresh Red-Team review.
  - F-09 is required before any acquisition, collection, or post-`T0 − m` web research. It does not gate no-network tooling work.

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
| F-09 network and WebFetch denies for market-data hosts | Phase 1 real collection, and any agent web research (WebFetch or WebSearch) after a cycle's `T0 − m` | Owner (settings are governance) | Policy **decided** (batch 4 O-6, host classes in `docs/external_access.md`). Deterministic denies in `.claude/settings.json` not yet committed |
| F-11 capture segmentation and salvage; F-12 frame v2 timing and direction (with F-27); F-26; F-33 | Phase 1 real collection | API / Execution, Reliability | Open |
| F-37, RT-4: demo data treated as real; collectors refuse the test environment | Phase 1 real collection | API / Execution | Open |
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

## Batch 2 (`phase1/kalshi-venue-verification`): Kalshi venue verification

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
- E-2: the point-in-time versioning decision;
- UR-4: the contract rules;
- UR-6 and UR-7: sequence scope and delta semantics. They need a recorded test, using a differential two-connection comparison, once a credential and collector are approved. Demo can falsify but cannot confirm production behavior, and a demo account or key needs its own owner classification (E-6).

**Remaining Phase 1 blockers added by batch 2:**
- E-1: gold scope;
- E-3: a market-data credential is needed for WS book capture, because the WebSocket requires a signed key;
- E-4: an availability rule for historical archive rows;
- AR-3: terms and contract documents;
- E-6: classification of demo accounts and keys;
- E-7: network egress scope and the F-09 denies;
- Red-Team blocking conditions for the parser and collector: RT-B2-01, 02, 03, and 06 in `research/kalshi/red_team_review.md`.

## Batch 3 (`phase1/historical-data-strategy`): historical data strategy

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

## Batch 4 (`phase1/acquisition-safety-decisions`): owner decisions and acquisition safety

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

## Recommended next batches

*Historical lists from batches 1 and 2. They are superseded by "Current status and next step" at the top of this file. F-06 and F-08 have since been decided (batch 4 H-1 and H-2).*

1. **Venue verification: done as far as `docs.kalshi.com` allows (batch 2).** The verified parser, `ContractSpec` builder, and resolution parser remain blocked by E-2, UR-4, UR-6, and UR-7 (see "Batch 2" above).
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

1. **Owner decisions:** E-1 (gold scope), E-2 (point-in-time versioning option), AR-3 (how the terms and contract documents are obtained), and E-3 (whether, and under which F-03 controls, a read-scope market-data credential is ever created). Also the earlier open items.
2. **Raw format v2 and collector hardening (no network needed),** now informed by documented Kalshi behavior:
   - per-subscription `use_yes_price` and connection metadata in frames;
   - fail-closed handling of terminal errors 10 and 25;
   - scheduled Thursday maintenance disconnects;
   - F-11, F-12, F-33, F-37 / RT-4.
3. **Kalshi parser against documented-schema fixtures (no network needed, after E-2):**
   - strict schema validation pinned to the recorded spec hashes;
   - relative-delta handling kept behind an explicit, tested assumption flag until UR-7 is tested;
   - metadata and outcome-field quarantine.
4. **Contract-rule verification (after AR-3):** BTC series rules, and gold if any exist. Then AR-2.

## Methodology recommendations for owner decision (Statistician review, 2026-10-15)

These would change approved validation methodology, so they are proposals, not adopted rules. Both feed F-07.

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

