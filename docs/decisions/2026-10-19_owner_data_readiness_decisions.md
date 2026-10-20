# Owner decisions: PMV data-readiness review (2026-10-19)

**Approver:** the project owner, in "OWNER DECISIONS — PMV DATA-READINESS REVIEW", issued on 2026-10-19 after reviewing the seven-specialist data-readiness report (DR-1 to DR-15). After reviewing the proposed changes, the owner issued "OWNER REVIEW OF PROPOSED DR-1 TO DR-15 CHANGES + FINAL OWNER DECISIONS + BTC POC SCOPE REVISION" the same day (DR-16 to DR-23, and refinements). The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record, an acquisition approval for any specific source, a capture approval, a licence determination, or a `T0` declaration.** Cloud provisioning, bulk acquisition, prospective capture, and B11 implementation each still need their own step. The owner directed: "Do not provision GCP yet. Do not start bulk acquisition yet. Do not declare T0."

## Background: the review the decisions rest on

- **Scope.** An owner-only, read-only data-readiness review ("PMV OWNER DATA-READINESS DEEP REVIEW"), followed by a one-time owner reconnaissance authorization ("OWNER AUTHORIZATION — TEMPORARY DATA-READINESS SAMPLING"). That authorization waived PMV's *internal* terms-first sequencing for tiny temporary samples only. It did not override external vendor restrictions.
- **The question.** Is the data obtainable now sufficient to seriously build and test the short-horizon BTC/gold hypothesis? Profitability was not assessed.
- **Reviewers.** The seven existing PMV roles reviewed independently: Quant / Business Lead, Data Scientist, Statistician, ML Engineer, API / Execution Engineer, Risk & Performance Engineer, and Reliability / Red-Team. Each read the governing documents first, then inspected the evidence itself.
- **Evidence.**
  - **Actual data:** one Kraken REST `Trades` sample (XBTUSD, 1,000 rows; exposure row X-12).
  - **Kalshi:** official OpenAPI 3.34.0 and AsyncAPI 2.0.0 specifications only. The data hosts are sandbox-denied, so no Kalshi row was observed.
  - **Gold:** schema only. Databento sample data requires a new account, so the review stopped there.
  - **Kraken L2:** the B10 profile plus official documentation. There was no new live capture, because the only WebSocket client then built proxy credentials, which the owner has since rejected (DR-10).
  - Temporary samples were deleted after the review.
- **Verdicts.** All seven roles: **GO WITH CONDITIONS** for cloud setup and BTC Stage 1, with gold exploratory. None would wait for an optional source. All three that addressed it judged a new live Kraken L2 capture unnecessary for the decision.
- **Main findings carried into the decisions below.**
  - The Kraken tape is `trade_id`-contiguous, with a deterministic page-boundary duplicate, float times that cannot serve as a join key, and frequent same-timestamp taker sweeps (DR-4).
  - Kalshi labels, payout, and fee-change history are historical. Executable price history is 1-minute candle bid/ask with no size. Book, quoted size, and receipt time are prospective only.
  - The Kalshi fee formula is not in the API specification (DR-9).
  - Kalshi historical and live candle schemas differ, in names and in the meaning of `mean`.
  - The Kalshi WebSocket requires an API key even for public channels (DR-12).
  - Final-minute settlement-reference fidelity is the largest data risk (DR-7).
  - `pmv.market_data` cannot yet represent historical rows (no `known_at` policy, candle type, or acquisition provenance), and no calibration or walk-forward code exists yet. These are implementation items for later batches.

## Owner decisions (verbatim)

### DR-1. Cloud setup: approved

> PMV may proceed to cloud-foundation work.
>
> This is approval for infrastructure, acquisition pipelines, prospective capture infrastructure, normalization, feature engineering and baseline research.
>
> It is NOT approval for:
> - real-money trading;
> - protected evaluation;
> - T0/T0-m;
> - economic/EV claims unsupported by fee and execution evidence.

### DR-2. BTC Stage 1: approved with Kalshi pilot gate

> Initial BTC stack:
>
>     Kalshi + Kraken
>
> Before bulk Kalshi acquisition, perform a bounded historical pilot sufficient to establish:
>
> - KXBTC15M history exists and is sufficiently deep;
> - historical trades are populated;
> - 1-minute candles are populated;
> - yes_bid / yes_ask are usable;
> - tail asks in approximately the 0.85–0.99 region are not systematically absent or sentinel values;
> - trade volume can be reconciled reasonably with candle volume;
> - result / settlement fields are usable as labels;
> - timestamps have sufficient fidelity for chronological joins;
> - block trades and provisional/deleted markets can be handled deterministically.
>
> If the pilot materially fails these checks, stop before bulk acquisition and return to the owner.

*Annotation (2026-10-20). The owner decision record `docs/decisions/2026-10-20_b12_pmv2_strategy_pivot.md` (PV-13 to PV-15) extends this pilot for PMV 2.0. The text above is unchanged and still binding. The pilot now also measures P10–P16 and lifecycle incidence, runs the old-strategy control C1, and applies the pre-registered stop conditions S-1 to S-6 (`research/kalshi/b12_btc_kalshi_pilot.md` §5.4–§5.6). The "tail asks in approximately the 0.85–0.99 region" check stays as a data-quality check for the settlement arm. It is no longer the pilot's central question.*

### DR-3. Kraken: approved after terms classification

> Kraken XBTUSD historical trades remain the initial BTC underlying source.
>
> Before bulk acquisition:
> - snapshot/classify the governing published terms;
> - resolve whether intended private PMV ML/research use is permitted.
>
> Initial acquisition architecture:
>
>     historical archive
>     +
>     REST gap-fill / validation
>
> On the FIRST archive file, verify:
> - timestamp precision;
> - trade_id behavior;
> - duplicate/page behavior;
> - reconciliation with REST;
> - whether taker-event aggregation is required.
>
> The 2024 owner-review sample showed same-timestamp sweep clusters.
>
> Therefore:
> - do not equate raw print count with independent trade intensity;
> - design a taker-event aggregation representation.

### DR-4. B10 Kraken correction

> The prior B10 statement that consecutive Kraken trades did not share timestamps is no longer reliable.
>
> The 2024 sample contained 164 same-timestamp clusters and 999 unique prints collapsed to approximately 538 apparent taker events.
>
> Record this as an observed representation discrepancy that must be accounted for in feature engineering.
>
> Do not erase the old observation; annotate/correct it.

### DR-5. Gold: exploratory only (superseded for current work by DR-17: gold shelved for now)

> Gold is NOT yet promoted to the same readiness level as BTC.
>
> Allowed:
> - acquisition planning;
> - canonical schema design;
> - roll/contract handling design;
> - Databento integration planning;
> - small permitted GC/MGC validation sample when available.
>
> Before substantive gold modeling:
> - inspect actual GC/MGC observations;
> - verify the relevant Kalshi gold series and history;
> - resolve DET-1 / exact Kalshi gold settlement-reference mechanics.
>
> No gold:
> - calibration claim;
> - label-window claim;
> - settlement-distance feature;
> - EV claim
>
> until those are resolved.

### DR-6. Optional sources

> Do NOT delay Stage 1 for:
>
> - Tardis
> - Pyth
> - Polymarket
> - Coinbase
> - CME DataMine
> - deeper Databento books
>
> No additional vendor is required now.
>
> CME DataMine remains DROP while Databento supplies the required CME MDP3 information.

### DR-7. CF Benchmarks / BRTI

> BRTI does NOT block initial BTC signal research.
>
> Continue obtaining pricing/licensing information.
>
> Its primary current value is settlement-reference fidelity in the final 1–2 minutes, not basic BTC velocity generation.
>
> Kraken may be used for initial signal research.
>
> Any strong claim about the sharpest final-minute/tail bands remains provisional until the Kraken-vs-reference fidelity test passes.
>
> When the cloud capture path exists, preserve the option to capture the Kalshi CFB/reference channel if:
> - terms permit;
> - credentials are appropriately isolated;
> - owner authorizes the capture.
>
> Do not purchase BRTI yet without owner approval.

### DR-8. Prospective capture: approved in principle

> Once the cloud capture architecture and credential isolation are complete, prepare to capture:
>
> KALSHI
> - orderbook_snapshot
> - orderbook_delta
> - trade
> - ticker
> - market_lifecycle_v2
> - periodic REST series fee state
> - price_ranges / relevant market metadata
> - PMV receipt timestamps
>
> KRAKEN
> - trades
> - book
> - PMV receipt timestamps
>
> Do not start capture until its specific deployment gate is satisfied.

### DR-9. Fees / economics

> No net-EV, break-even, sizing, or capacity claim may be made until the relevant Kalshi fee schedule is obtained and versioned for the development period.
>
> Owner still needs to provide:
> - Kalshi fee-schedule PDF;
> - relevant KXBTC15M contract terms;
> - relevant gold contract terms when gold work advances.

### DR-10. Proxy-auth carve-out: rejected (made strict by DR-16)

> PMV code/tests may not reconstruct authenticated proxy URLs or Proxy-Authorization from runtime sandbox credentials.
>
> Use:
> - Layer A static managed-policy verification;
> - owner-side unauthenticated Layer B CONNECT test.
>
> Combined sandbox testing may only occur if runtime authentication is handled transparently without PMV code inspecting credentials.

### DR-11. Pre-T0-m P-5: approved

> Add the canonical pre-T0-m requirement:
>
> Before any T0-m:
> - classify every Layer A and Layer B allowlist entry;
> - remove or explicitly justify live-data, live-display and protected-observable hosts;
> - verify Layer A managed policy;
> - verify the owner-side Layer B CONNECT check;
> - require all applicable automated refusal checks to pass.
>
> Do not hard-code a particular test count.

### DR-12. Credential separation

> Prospective capture credentials must be isolated from future trading credentials.
>
> No trading credentials are required for the capture/research stage.
>
> Agents must not receive reusable cloud or venue secrets.

### DR-13. Owner-review exposure ledger

> Persist the relevant owner-review exposures in the durable exposure register.
>
> At minimum include:
> - the new 1,000-row Kraken REST sample;
> - current Kalshi specification exposure where required;
> - any other ledger item that existing governance says must be persisted.
>
> All observations from this review remain DEVELOPMENT-EXPOSED.

### DR-14. Local transcript

> This Claude session now contains actual Kraken sample values.
>
> Treat the session transcript as development-exposed material.
>
> Do not use it as protected evidence.
> Do not share it publicly.
> Do not inspect runtime-secret values.

### DR-15. /proc defense-in-depth

> The previously identified /proc sandbox path-normalization issue remains non-blocking future hardening.
>
> Do not delay cloud work because of it.

## Owner review of the proposed changes and final decisions (2026-10-19, second direction)

The owner approved the proposed DR-1 to DR-15 changes in principle, with required changes before commit. New decisions are numbered DR-16 to DR-23. Where the second direction restates an earlier decision, it is recorded as a refinement. **Where the two differ, the second direction governs.**

### DR-16. Final proxy handling: strict (refines DR-10)

> PMV code must NOT read or parse:
>
>     HTTP_PROXY
>     HTTPS_PROXY
>     ALL_PROXY
>
> or their lowercase variants.
>
> This prohibition applies EVEN if the code intends only to extract a hostname or port.
>
> Reason:
>
> Those variables may contain a credential-bearing URL. Loading/parsing the string at all unnecessarily exposes PMV code to secret material.
>
> Therefore PMV diagnostic/recon code must never:
>
> - read those proxy variables;
> - parse them;
> - inspect their hostname;
> - inspect their port;
> - inspect username/password;
> - reconstruct userinfo;
> - construct Proxy-Authorization.
>
> Safe alternatives:
>
> A. OWNER-SIDE LAYER B
>
> Use the owner-verified unauthenticated route directly:
>
>     pmv-egress-proxy:3128
>
> B. SAFE PMV-SPECIFIC CONFIGURATION
>
> If code needs an explicit configurable proxy destination, use credential-free PMV-specific settings such as:
>
>     PMV_EGRESS_PROXY_HOST
>     PMV_EGRESS_PROXY_PORT
>
> These settings must contain only safe host/port metadata and no userinfo.
>
> C. COMBINED SANDBOX PROBE
>
> If Claude/runtime networking cannot route/authenticate transparently without PMV code reading a runtime proxy variable, mark that probe:
>
>     NOT APPLICABLE / SKIPPED
>
> Do not weaken the secret rule merely to make the probe work.
>
> Update tests and the static diagnostic guard so this rule cannot regress.

The owner also approved keeping the DR-10 compliance code fixes: "These are direct compliance changes required by owner decision DR-10, not unrelated implementation work."

### DR-17. Active BTC proof of concept; gold shelved for now (supersedes DR-5 for current work)

> ACTIVE POC:
>
>     BITCOIN
>
> Gold is:
>
>     SHELVED FOR NOW
>
> Do NOT describe gold as:
>
> - cancelled;
> - abandoned;
> - permanently dropped.
>
> Reason:
>
> The owner wants PMV to prove or disprove the velocity/path concept on Bitcoin before expanding active research, data acquisition, engineering, and modeling scope.
>
> For the current POC:
>
> - no new gold acquisition;
> - no GC/MGC pipeline implementation;
> - no gold feature/model work;
> - no requirement to resolve gold DET-1 now.
>
> Preserve all existing gold research, evidence, and documentation.
>
> Gold may be reconsidered later.

### DR-18. Current BTC POC data stack

> PREDICTION MARKET:
>
>     Kalshi short-horizon BTC markets
>
> UNDERLYING:
>
>     Kraken XBTUSD / BTCUSD trade data
>
> PROSPECTIVE CAPTURE:
>
>     Kalshi:
>         order book
>         trades
>         ticker
>         lifecycle
>         relevant metadata
>         PMV receipt timestamps
>
>     Kraken:
>         trades
>         book
>         PMV receipt timestamps
>
> BRTI:
>
>     conditional settlement-reference-fidelity source;
>     does NOT block initial BTC signal research.
>
> No additional vendor is required merely to begin the BTC proof of concept.

### DR-19. Future market expansion policy

> After the BTC proof of concept reaches its defined decision point, PMV should NOT automatically proceed to gold.
>
> Instead, the EXISTING PMV specialists will perform a fresh review of available prediction-market families and determine which markets are structurally compatible with the velocity/path methodology.
>
> Candidate-market evaluation should consider at least:
>
> - continuously observable underlying price;
> - objective/verifiable settlement;
> - reliable reference source;
> - recurring standardized markets;
> - short enough horizons;
> - sufficient historical depth;
> - sufficient prediction-market liquidity;
> - sufficient underlying-market liquidity;
> - timestamp quality;
> - quote/book availability;
> - settlement-reference fidelity;
> - fee/execution economics;
> - whether the outcome is meaningfully driven by continuous price path rather than primarily by discrete qualitative/news events.
>
> Gold remains a future candidate alongside other compatible markets.

### DR-20. Model architecture policy

> SHARED PMV PLATFORM
> +
> MARKET-FAMILY-SPECIFIC FITTED MODELS
>
> Shared infrastructure includes:
>
> - acquisition;
> - canonical schemas;
> - point-in-time alignment;
> - reusable velocity/path feature primitives;
> - chronological splitting;
> - walk-forward evaluation;
> - calibration;
> - economics;
> - risk controls;
> - execution;
> - monitoring;
> - reproducibility.
>
> Fitted models should NOT pool unrelated asset families by default.
>
> Examples of possible specialization:
>
>     BTC 15-minute
>     BTC 1-hour
>     future ETH family
>     future gold family
>
> Do NOT train a totally new model for every individual recurring contract by default.
>
> The normal specialization unit is a sufficiently homogeneous recurring market family/series.
>
> Whether BTC 15-minute and BTC 1-hour can share a model is an EMPIRICAL question.
>
> Every future market-family model must independently earn promotion.

### DR-21. Model development order

> For the selected BTC family, preserve the simple-to-complex progression.
>
> At minimum:
>
> B0:
>     analytic/statistical underlying-price benchmark where appropriate
>
> B1:
>     prediction market's own implied probability
>
> Then:
>
>     logistic / regularized probability model
>
> Then if justified:
>
>     boosted-tree model
>
> Only after simpler models and sufficient sequential data exist should PMV consider:
>
>     CNN
>     RNN
>     other sequence models
>
> Complexity must earn its place out of sample.

### DR-22. Sensitive Claude transcripts: purge after the durable record (owner action)

> Use the PURGE-AFTER-DURABLE-RECORD approach.
>
> The affected local Claude transcripts contain sensitive runtime credential material.
>
> Until cleanup:
>
> - treat them as sensitive;
> - do not share them;
> - exclude them from backups where practical;
> - do not inspect the credential value;
> - do not copy the credential into Git or another record.
>
> After:
>
> 1. the sanitized durable Git governance record is committed;
> 2. the commit is verified;
> 3. the necessary non-secret incident information exists durably;
>
> the OWNER will identify the exact affected transcript files and delete/purge those specific local transcript files where practical.
>
> Important:
>
> - Claude must NOT delete local transcript files in this task.
> - Claude must NOT inspect the credential values.
> - Claude must NOT search for or print the secret to identify the transcripts.
> - Identification must use safe metadata such as session/time/path information.
> - Do not delete unrelated Claude history.
>
> Record this as an OWNER ACTION to perform after the B11 governance commit is verified.

Procedure: `docs/owner_actions/README.md` §4. The non-secret incident information is already durable:
- the two B10 credential-print events: `docs/decisions/2026-10-19_b10_source_reconnaissance.md`, process deviations;
- the B10 runtime-secret investigation and hardening: same record, "Owner correction: runtime-secret hardening".

This record holds no credential value.

### DR-23. B11 branch

> Create:
>
>     b11/btc-poc-owner-decisions
>
> DIRECTLY from c028882.

- Base: `c0288820748e21f606f7dd258c95d7711b69e15a`, the final B10 tip.
- Purpose, verbatim: "durable owner data-readiness decisions; BTC active proof-of-concept scope; gold shelved for now; market-family-specific model policy; proxy-security compliance; owner-review exposure registration; Kraken timestamp/taker-event correction; P-5 pre-T0-m control; transcript-cleanup owner action."
- "No cloud provisioning in this branch."

### Refinements and reaffirmations in the second direction

- **DR-2 (pilot gate), refined.** "Before bulk Kalshi acquisition, establish that the selected recurring BTC market family has":
  - sufficient historical depth;
  - populated trades and 1-minute candles;
  - usable `yes_bid`/`yes_ask`;
  - meaningful tail observations;
  - usable result/settlement labels;
  - timestamps suitable for chronological alignment;
  - deterministic handling of block, provisional, and deleted markets;
  - reasonable trade-volume versus candle-volume reconciliation.

  "Pay particular attention to the intended strategy region: approximately 0.85–0.99 market prices and especially late-window observations." On material failure: "STOP BEFORE BULK ACQUISITION / RETURN TO OWNER".
- **DR-3 and DR-4 (Kraken), reaffirmed.**
  - The first archive file also verifies gaps.
  - "Feature engineering must NOT equate: one row == one independent trade event by default."
  - The cause of the discrepancy is unresolved among "an era-specific representation change; a delivery-path difference; or an earlier analytical mistake".
  - "PMV should develop a deterministic taker-event aggregation representation."
- **DR-6 and DR-7 (optional sources, BRTI): reaffirmed.**
- **DR-8 (prospective capture), refined.** Capture is approved in principle once all of these hold:
  - "cloud capture architecture exists";
  - "capture/dev separation exists";
  - "raw protected storage exists";
  - "restore is tested";
  - "credential isolation exists";
  - "source-specific deployment gates are satisfied".

  "Do not begin capture in this governance task. No trading credentials are needed for capture."
- **DR-9 (fees), refined.** The owner still needs to provide the Kalshi fee schedule and the relevant BTC market or contract terms. "Gold terms are shelved with gold work for now."
- **DR-11 (P-5): reaffirmed.**
- **DR-12 (credentials), reaffirmed.** "No trading credentials are authorized at this stage."
- **DR-13, DR-14 (exposures): reaffirmed.** "Exposure accounting is independent of current research priority. Do not erase or roll back historical gold exposure": the conservative X-14 entry and date stand. "No owner-review observation is protected holdout evidence."
- **Historical text:** "KEEP superseded historical text. Annotate rather than rewrite history."
- **DR-15 (/proc): reaffirmed.**

### Annotations to the first-direction decisions

- **DR-5** is superseded for current work by DR-17: gold is shelved, not exploratory. Its verbatim text above is kept for the record.
- **DR-9**'s "relevant gold contract terms when gold advances" is shelved with gold work.
- **DR-10** is made strict by DR-16.

## Owner final B11 sign-off (2026-10-19, third direction)

In "OWNER FINAL B11 SIGN-OFF", the owner approved the B11 change set, including the governance edits, subject to one correction:

> I explicitly approve the governance edits to:
>
> - CLAUDE.md
> - PROJECT_BRIEF.md
> - START_HERE.md
>
> and the rest of the proposed B11 files.

The owner also approved the stricter verification additions: the `kraken_rest_trades_sample.py` credential-free CONNECT fix; the `python-urllib-env-proxy` guard; the `docs/conventions.md` clarification that in-process proxy discovery counts as PMV code reading the runtime proxy variables; and the matching decision-record and `docs/BRANCH_TIMELINE.md` updates.

**Correction: the blanket `curl` exception is removed.** The owner's replacement rule, verbatim:

> Tracked PMV code, tests, automation, and recon tooling must not depend on HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, or lowercase equivalents, either directly or indirectly through a child process or in-process network library.
>
> If tracked PMV code invokes an external network client, it must prevent inheritance/use of those runtime proxy variables and, where proxy routing is required, use only explicitly supplied credential-free PMV routing metadata such as PMV_EGRESS_PROXY_HOST / PMV_EGRESS_PROXY_PORT.
>
> Owner-operated manual networking outside tracked PMV code is governed by the sandbox/network controls and is not an exception that tracked PMV code may rely on.

## Applied in this record's commit (branch `b11/btc-poc-owner-decisions`)

| Decision | Change |
|---|---|
| DR-4 | `research/data_sources/schema_profiles/kraken_historical_trades.md`: the 2023 statement is kept and annotated with the 2024 discrepancy |
| DR-10, DR-16 | `tests/integration/test_live_host_egress_refusal.py`. The runtime proxy variables are **not read or parsed at all**, and no proxy authorization header is built. The probe destination comes only from `PMV_EGRESS_PROXY_HOST` / `PMV_EGRESS_PROXY_PORT`, which are validated as a bare host and port, and values are never echoed. Unset, or `407`, means the combined probe is skipped as not applicable, never passed. New offline tests: (a) a recording-environment test proves that none of the six runtime proxy variable names is ever looked up; (b) a bare-CONNECT test proves no credential is sent; (c) userinfo or scheme in the PMV setting is rejected without echoing it. |
| DR-10, DR-16 | `research/data_sources/recon_tools/kraken_ws_sample.py`: the same changes. The tool exits unless the PMV settings are set, and stops on `407`. |
| DR-10, DR-16 | `research/data_sources/recon_tools/kraken_rest_trades_sample.py`: found in the B11 verification pass. It used the default `urllib.request.urlopen`, whose `ProxyHandler` reads the runtime proxy variables in-process (`getproxies`, `proxy_bypass`) and builds a proxy authorization header from any userinfo. It now uses `http.client` with an explicit, credential-free CONNECT tunnel (`set_tunnel`) to `PMV_EGRESS_PROXY_HOST` / `PMV_EGRESS_PROXY_PORT`, accepts only the fixed Trades endpoint, and reports failures by status or exception type only. It was not run. |
| DR-10, DR-16 | `tests/unit/test_diagnostic_secret_rule.py`: new rules `proxy-auth-construction`, `python-proxy-var-read`, `python-proxy-discovery` (`getproxies`, `proxy_bypass_environment`), `python-urllib-env-proxy` (`urlopen`, `urlretrieve`, `build_opener`, `install_opener`, `ProxyHandler`), and `shell-proxy-var-expansion`, with hit and allowed self-tests. The three files at `c028882` are flagged by these rules; the current files are not. |
| DR-10, DR-16 | `docs/conventions.md`: the strict rule, including that in-process library proxy discovery counts as PMV code reading the variables. At the owner's final B11 sign-off, the draft exemption for "a standard client that applies the runtime proxy itself, such as `curl`" was **removed**. Tracked PMV code, tests, automation, and recon tooling must not depend on the runtime proxy variables directly or indirectly, through a child process or an in-process library. A spawned network client must not inherit them, and uses only credential-free PMV routing metadata where routing is needed. Owner-operated manual networking is not an exception that tracked code may rely on. The two tracked `curl` calls (`scripts/install_uv.sh`, `scripts/install_betterleaks.sh`) already run under `env -i` and comply. No static guard rule was added for child-process inheritance, because no tracked violation exists and a line-based pattern would misflag those compliant multi-line `env -i` invocations; review remains the control. `docs/owner_actions/README.md` §3 step 5 and `docs/external_access.md` §1.4: updated accordingly. |
| DR-11 | `START_HERE.md`: **P-5** added to the mandatory pre-T0 checklist (a governance edit approved by DR-11). Hard-coded test counts are removed from current-tense instructions. |
| DR-13 | `docs/exposure_register.md` Part A rows X-12 to X-14 and an "As of row X-14" summary |
| DR-17 to DR-21 | `PROJECT_BRIEF.md` §1 "Active scope", a §3 pointer, and §8 "Model architecture and development order"; `START_HERE.md` "Strategy at a Glance"; `CLAUDE.md` Strategy Scope and Modeling (additive bullets; the original text is kept); `docs/phase1.md` status; `research/data_sources/source_redundancy_decisions.md` status note |
| DR-22 | `docs/owner_actions/README.md` §4 (owner action, after the B11 commit is verified) |
| DR-23 | `docs/BRANCH_TIMELINE.md`: B11 is the current active ground-truth branch; B10 is historical, merged by PR #9 |
| All | superseded pending items annotated in `docs/decisions/2026-10-19_b10_source_reconnaissance.md` and `docs/owner_actions/README.md` |

Not changed:
- agent files and settings;
- historical BTC+gold text in earlier records and documents, which is kept as written;
- no provisioning, acquisition, capture, `T0`, or transcript deletion.

## Open owner items after this record

1. The Kalshi fee schedule and the relevant BTC market or contract terms (DR-9; DET-2).
2. Kraken published-terms snapshot and classification (DR-3; B10-D11).
3. Kalshi M1 / A-2 clearance before the DR-2 pilot pulls any data.
4. CF Benchmarks pricing and licensing information (DR-7; B10-D9 stays deferred).
5. A charter for the cloud-foundation batch (DR-1).
6. The credential design for prospective capture (DR-8, DR-12; open items E-3 and F-03). The Kalshi WebSocket requires an API key even for public channels.
7. **The transcript purge (DR-22)**, after the B11 commit is verified (`docs/owner_actions/README.md` §4).
