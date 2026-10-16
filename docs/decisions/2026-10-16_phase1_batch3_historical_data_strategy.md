# Phase 1 batch 3: owner process change, historical data strategy (2026-10-16)

**Approver:** the project owner, in the batch 3 charter given on 2026-10-16. The charter instructed this record and the documentation changes listed below. The development session wrote this record, and the owner should confirm its wording before merge.

**What this records:** an owner change to how PMV gets development data, the scope that change approves for Phase 1 batch 3 (branch `phase1/historical-data-strategy`), and the owner decisions it raises but does not take.

**Limitation:** this record is procedural. The system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record.** It passes no gate. It declares no cycle, split, or protected scope. It does not relax the information embargo, the data-access guard, credential isolation, or any risk or execution control.

## Decisions taken by the owner

### P1. Verified existing historical data is preferred over waiting to regenerate equivalent observations

- PMV will not wait to recreate historical data that already exists.
- When a historical source's provenance, timestamp semantics, contract semantics, licensing, and quality are adequate, PMV uses it **aggressively for development**.
- At the same time, PMV prepares its own **prospective capture**, so that genuinely untouched future data accumulates in parallel.
- None of this weakens provenance, licensing, point-in-time correctness, holdout integrity, or source-quality requirements. A source that fails them is not used, however convenient it is.

**Precedence (Red-Team RT-B3-13; recommended addition, for owner confirmation).** Retention loss, cost, or schedule never justify acquiring, parsing, or releasing data ahead of its licence determination, backup policy, safe-parsing controls, or release controls. If official history may age out first, the owner may obtain the terms manually or accept the loss, which is then recorded as a known gap.

### P2. Historical data exposed to development can never become protected holdout data

- This restates the existing rule ("No observation may become protected evaluation data after being exposed to development", CLAUDE.md, START_HERE.md "Evaluation Cycles") and applies it explicitly to acquired historical data.
- Exposure includes values, outcomes, outcome-dependent derivatives, and equivalent observables of the same interval from any source.

### P3. Broad public research access within the sandbox allowlist

- Agents may research public documentation, papers, code, dataset metadata, licensing, and pricing pages on hosts the current sandbox allows.
- Every external item is **untrusted input**. Agents do not execute downloaded installers, scripts, notebooks, binaries, or GitHub Actions, and do not run `curl | sh` commands, merely because a source recommends it.
- **Not authorized without a separate owner approval:**
  - new credentials;
  - account creation;
  - paid purchases or trials;
  - uploads;
  - authenticated APIs;
  - live trading API access;
  - write tokens.
- A useful source outside the allowlist is raised as an ACCESS REQUEST: the exact domain or resource, purpose, intended data, and a temporary or permanent recommendation. It is never reached by another route.
- **CME:** `www.cmegroup.com` is allowlisted but did not return usable content to `curl` on 2026-10-16 (an HTTP/2 stream reset, then a timeout), apparently because of site-side anti-bot behavior. This is a **source-access limitation, not a sandbox failure**. Agents do not try to bypass it. Legitimate alternative sources for COMEX/GC data are considered, while the authoritative reference source is still verified.

### P4. Gold remains in project scope

- The absence of a verified Kalshi gold event-contract series does **not** remove gold from scope.
- Historical COMEX/CME, benchmark, reference, or other high-quality gold data may be used as underlying or explanatory data, provided the settlement and reference source of any contract being modeled is correct.
- This settles the scope half of batch 2 escalation E-1: no scope reduction. Whether a tradable gold contract exists on Kalshi or Polymarket is still unverified (UR-5).

### P5. Polymarket historical-data documentation research is approved for this batch

- Batch 2 decision D2 deferred Polymarket work. This charter approves Polymarket **documentation and inventory research** about historical data.
- D2 otherwise stands: no Polymarket adapter, collection, account, credential, or API call.

### P6. Batch 3 scope

**In scope:**
- this record;
- updates to PROJECT_BRIEF.md, START_HERE.md, CLAUDE.md, `docs/phase1.md`, `docs/market_data.md`, and `docs/conventions.md` stating P1 and P2. The owner approved these governance edits in the charter, limited to that purpose;
- a historical-data feasibility inventory, covering prediction markets, Bitcoin, gold, open datasets, academic and technical sources, and regulatory and reference sources;
- a new `docs/phase2.md` that covers general data cleaning and dataset engineering, not only splitting;
- a duplicate and dependence policy, reviewed by the Statistician;
- a Reliability / Red-Team review;
- a proposed point-in-time contract-metadata architecture, **for owner approval**.

**Not authorized in this batch:**
- live trading;
- credentials;
- protected-holdout access;
- irreplaceable live capture;
- large dataset downloads.

**Samples.** A tiny schema or quality sample was allowed only if clearly safe under the existing holdout policy. None was taken: the committed protected-scope registry is empty, so the guard refuses every real market observation (`docs/protected_information.md`). The inventory is therefore documentation-based.

## What does not change

- **Agent access is still gated.** Agents still inspect **no real market observation**, historical or live, until:
  - the cycle is declared;
  - its protected scope is committed;
  - the F-08 release design is decided;
  - the single access authority allows the request. Today that is the guard. Under F-08 it would be the trusted release tool, applying the same catalog and scope.

  P1 changes what PMV acquires and plans to use. It does not open early access.
- **Split rule.** The chronological ~70/30 rule, the frozen-boundary rule, purge and embargo, and the Gate 6 and owner-approval requirements for opening the holdout are unchanged.
- **Credentials, real money, and raw data.** Credential isolation (F-03), the real-capital rules, and the raw-data backup prerequisite for irreplaceable capture are unchanged.

## Owner decisions raised by this batch (not taken)

Full analysis is in `research/historical_data/feasibility_summary.md` and `research/historical_data/point_in_time_metadata_architecture.md`.

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| H-1 | **Holdout formation for the first cycle (F-06).** Under P1 and P2, historical data used for development cannot also be the holdout. The two allowed formations (START_HERE.md "Protection of Holdout-Eligible Data") are: (a) a mechanical partition of an unexamined historical snapshot, whose newest part is never shown to agents; (b) a prospective protected period that begins at a declared future instant `T0` and accumulates through PMV capture. | (b), prospective. It is the only formation clean of the model's training-data knowledge (F-06). It is the only one that can carry PMV receipt times and live order books. Historical data before `T0 − margin` then all becomes development data. Conditions (Statistician S-10, S-11): an explicit embargo granularity; the ~70/30 target read over the PMV-capture span with a power floor; and `T0`, the margin, and an end or outcome-blind stopping rule fixed before `T0`. | Agents seeing any real observation |
| H-2 | **Release architecture for acquired historical data (F-08).** A deterministic tool fetches into the protected raw store, outside agent sessions. An owner-run release step gives agents only records whose observation time, and every equivalent observable's time, is before the declared development boundary. | Adopt. One mechanism serves live captures and historical acquisitions. | Agents seeing any real observation |
| H-3 | **Point-in-time contract metadata (batch 2 E-2) and identity (m4).** | Option D, the hybrid: an append-only metadata log as the source of truth, a bitemporal materialized view, and reconciliation snapshots. Identity is split from verification and fees. A strike change is a new version, not a new identity. | Kalshi `ContractSpec` builder, any real label |
| H-4 | **Admission policy for post-hoc (archive) contract metadata.** | Admit only immutable-by-rule fields. Tag rows `metadata_pit_class = POST_HOC`. Exclude rows where a mutable field cannot be shown unchanged. Such rows are discovery and pilot evidence only. | Any archive-based label |
| H-5 | **Availability rule for archive rows with no PMV receipt time (batch 2 E-4).** | A flagged synthetic availability `venue_time + L`, with `L` fixed before any outcome inspection. Results are reported separately from receipt-time rows. | Any archive row in training |
| H-6 | **Unit of independence and cross-venue grouping (F-07, R1).** | Adopt the non-chaining design in `docs/phase2.md`: score and aggregate by `outcome_cell_id`, a fixed UTC grid on `ref_end` shared across venues, strikes, and reference sources; split and purge by each contract's information interval; infer by Newey–West and calendar-block bootstrap over fixed `time_block_id`s; and plan power on the paired loss difference against the market. An independent audit is required after adoption. | First cycle and split |
| H-8 | **Agent-model training-cutoff register (Statistician S-10; a governance addition).** Prospective formation protects against agent knowledge only while no development model's training cutoff postdates `T0 − margin`. | Record each agent model's documented cutoff in session and gate records. Using a model with a later cutoff for that cycle's candidate is a recorded contamination event. | First real protected scope |
| H-7 | **Acquisition approvals.** Each paid vendor, licence acceptance, account, or new domain. | One approval per source, from the ranked list. | Each acquisition |

H-8 and O-3 to O-9 (below) were added after the Statistician and Red-Team reviews. E-2 through E-7 from batch 2 stay open, except that E-1's scope question is settled by P4 and E-2 is restated as H-3.

## Disclosures from this batch (for owner decision)

- **Incidental pre-cycle exposure.** Research agents read a public dataset card, HF `DegenHedge/kalshi-btc-15m`, that contains aggregate outcome statistics for KXBTC15M over 2026-01-10 to 2026-10-04. Search summaries and paper abstracts also showed aggregate figures.
  - No value was recorded in any file.
  - No cycle exists, so no HOLDOUT_ACCESS_LOG.md event can be recorded.
  - This rules out H-1 option (a) for any KXBTC15M period before 2026-10-16.
  - Recommendation: disclose it in the first cycle's registration, and start the first protected interval after 2026-10-16 plus margin.
- **Process events.**
  - One agent requested a documentation path on an exchange API host. The proxy refused it.
  - One agent fetched `cfbenchmarks.com` pages before reading that the site's terms bar automated access, and then stopped.

  Neither returned market data.
- **Gold contract evidence.** Secondary sources report a Kalshi KXGOLD15M series that settles on a Pyth gold reference. It is officially unverified (AR-4, AR-8). This bears on UR-5, not on scope (P4).

## Pre-cycle exposure register (append-only; Red-Team RT-B3-09; for owner confirmation)

No cycle exists, so HOLDOUT_ACCESS_LOG.md cannot record these. They are recorded here so that the first cycle is bound by them. Whether this register becomes a structural part of HOLDOUT_ACCESS_LOG.md is a governance decision for the owner.

| # | Date (UTC) | Who | Source | Observable family | Period covered | Granularity |
|---|---|---|---|---|---|---|
| X-1 | 2026-10-16 | Two batch 3 research agents (prediction-market and open-data inventories) | HF dataset card `DegenHedge/kalshi-btc-15m` README (`research/sources.md`, batch 3) | BTC: KXBTC15M outcomes, and through them the BTC path | 2026-01-10 to 2026-10-04 | Aggregate: win rate against entry price, strike and price ranges, window anomalies |
| X-2 | 2026-10-16 | Batch 3 research agents | Web search summaries and paper abstracts | BTC and BTC prediction markets; gold price levels | Up to 2026-10-16 | Aggregate claims and coarse recent levels |
| X-3 | 2026-10-16 | Underlying-data research agent | `www.cfbenchmarks.com` BRTI page | BTC reference index | 2026-10-16 (one live value) | Point |

**Binding rule (proposed).** The first cycle's protected interval start `B` satisfies `B − m` > the latest end of any registered pre-cycle exposure for that observable family, currently 2026-10-16 for BTC and gold. `cycle_registered` cites this register by hash. These exposures are also disclosed to Phase 5 auditors as development-influencing research degrees of freedom.

## Further owner decisions raised by the Red-Team review (not taken)

| ID | Decision | Recommendation |
|---|---|---|
| O-3 | Extending the S-6 collection rule to historical **acquisition** | Approve only with: a raw backup and restore test covering acquired files (RT-B3-01); safe-parsing controls (RT-B3-03); and a licence determination per source (RT-B3-06) |
| O-5 | Licence gate | Separate acquisition-time (L-ACQ) and production-time (L-PROD) licence determinations, with `licence_id` lineage on every derived artifact and model. Keep "do not acquire" for Binance Vision, the Cryptolake and OANDA mirrors, papylove, and DegenHedge `signals` |
| O-6 | F-09 deterministic denies | Commit host-class denies (API, data, live-display hosts) before the next research batch, so refusals no longer depend on owner clicks |
| O-7 | Wording of existing governance rules (outside this charter, so not changed) | (i) CLAUDE.md "agents do not inspect real market observations at all" could become "do not deliberately inspect", with incidental exposure going to the register. (ii) The CLAUDE.md and HOLDOUT_ACCESS_LOG.md "oldest ~70% / newest ~30%" wording against the Statistician S-11 reading for prospective formation. Each needs an explicit owner-approved edit |
| O-8 | Verification standard | Model-summarized web fetches are SECONDARY. VERIFIED-BY-DOC needs a verbatim quote plus a raw-byte hash (adopted in `docs/conventions.md` as a convention; the owner may reject) |
| O-9 | Embargo erosion after `T0` (RT-B3-10), a condition of H-1 | From `T0 − m` until consumption, agents do not open dataset cards, READMEs, vendor pages, dashboards, papers, or search results about BTC, gold, or BTC/gold prediction-market data covering the protected interval. Host-level denies support this during accumulation. Any such exposure is recorded as contamination |
