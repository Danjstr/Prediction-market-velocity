# H-2 Per-Row Release Tool: Design and Deferral (Phase 1, B06)

**Status: PROPOSED DESIGN. Not an approved requirement.** No code exists. The bar on writing it before steps 1 and 3 of "Prerequisite chain" comes from the approved records (RT-B3-05 as adopted by H-2), not from this document. This document restates, in one place, the properties the H-2 release tool must have. Every property comes from an approved decision or review record cited inline; nothing here adds a new requirement. If this document and a cited record disagree, the record governs.

Reviews: `research/governance/b06_release_design_statistician_review.md` (development Statistician, self-review; verdict REVISE, findings applied in this revision).

Sources: H-2 in `docs/decisions/2026-10-16_phase1_batch4_acquisition_safety_decisions.md`; RT-B3-02 and RT-B3-05 in `research/historical_data/red_team_review.md`; S-4 and the guard prerequisites in `docs/protected_information.md`; Policy 2 and the identifier glossary in `docs/phase2.md`; A-8 in `docs/external_access.md`.

## Why the code is deferred

The B06 continuation charter (`docs/decisions/2026-10-16_b06_governance_continuity_sync.md`, "B06 continuation") asked for this tool "where implementation is permitted before cycle/T0 registration". Three approved records make implementation premature today:
1. **RT-B3-05**, whose catalog H-2 adopts, requires that E-U1 be "adopted in full as a reviewed code change **before the release tool exists**", and that the tool and the guard share **one** catalog keyed by `source_id`. E-U1 (`research/historical_data/inventory_underlying_btc_gold.md` §5) is an open owner escalation. The guard's current catalog (`src/pmv/protected_scope.py` `CATALOG`, keyed by `(Provider, Family)`) is not that catalog, and changing it is a reviewed control change.
2. **The quantitative equivalence criterion (P-3)** must be approved before cycle registration, and therefore before any release. It does not change the release tool's cut, which is family-blind at `B − m` (R-6), so it gates release, not implementation.
3. **No release can occur before a cycle is registered.** RT-B3-02 item 1: before a cycle with `T0` and `m` is registered, `B − m` is undefined, and any release would precede the cycle's first outcome-dependent inspection. Cycle registration requires P-1 to P-4 first. This bars release, not implementation: the tool reads `B` and `m` from the verified registry and is testable against synthetic registries.

Implementation waits on E-U1 and the shared catalog (item 1). Release additionally waits on cycle registration (items 2 and 3).

Building against a placeholder catalog or boundary would bake in assumptions the owner has not approved and would later need retrofitting, which RT-B3-02 ("Tooling, if built before H-2 is decided … should already have the H-2 shape") warns against. Until the tool exists, A-8 and H-2 hold: **nothing is released**, and the guard (empty registry, every real request refused) remains the only access path.

## Required properties

Notation (from `docs/phase2.md` Policy 2): `B` is the protected start (for the first cycle, `T0`), `m` the protected-scope margin, `I(k) = [first_decision(k) − max_lookback, ref_end(k) + Δ_label]` the contract information interval.

| # | Property | Source |
|---|---|---|
| R-1 | Owner-run, outside agent sessions, deterministic, and fail-closed. One mechanism serves PMV captures and historical acquisitions | H-2 |
| R-2 | Eligibility is cut **per row** and per equivalent observable, never only by file, download, or request window | H-2; RT-B3-02 |
| R-3 | Each row's **information time** is the **latest end** of every catalogued time-bearing field of its `source_id`. For an interval or aggregate record (bar, candle, window average, settlement, coarse-precision timestamp `t` of precision `p`, on-chain block time), it is the end of the interval, `t + p`, or `block_time + 1 s`, as applicable. The catalogued `max_clock_error` for that source is then added. If any row's information time cannot be determined, the whole file fails closed | RT-B3-02; Statistician B6S-1 |
| R-4 | Each file's equivalent-observable set is the **union** over its content, derived from the catalog, never from the caller or a dataset card. Mixed-content files are handled field by field | RT-B3-02; RT-B3-05 items 1–2 |
| R-5 | An unknown `source_id`, or an unknown field within a known `source_id`, fails closed | RT-B3-05 |
| R-6 | A row is released iff (a) its information time (R-3) **and** the time of every equivalent observable it carries are `< B − m`; (b) **every** contract the row is attributable to is development-eligible under Policy 2 (`ref_end + Δ_label < B − m`), and every such contract's `outcome_cell_id` is wholly development-eligible (`floor_G(ref_end) + G + max Δ_label over the cell < B − m`); and (c) for any label-channel field, the label's observation or receipt time is `< B − m` (for `RECEIPT` rows the finalization receipt; for `POST_HOC` rows the synthetic finalization time `ref_end + max(settlement timer) + dispute allowance + L_label`, Policy 3, fixed before inspection). A resolution version (dispute or amendment) whose `known_at ≥ B − m` is not released; the latest version known before `B − m` is released only if it is final, otherwise the contract's label is withheld and ledgered as `label_after_boundary`. A row attributable to no contract (for example an underlying print) is subject to the time conditions only. A row whose contract attribution, `ref_end`, or `first_decision` cannot be determined from trusted lifecycle metadata fails closed. The time conditions apply to **every** time-bearing field, whatever its family or equivalence classification; classification (R-4) drives embargo bookkeeping and guard behavior, never whether a field after `B − m` is released | RT-B3-02; Policy 2; Policy 3; H-1; H-6 |
| R-6a | Before any release, the tool verifies from the registered cycle that `m ≥` the registered maximum feature lookback cap, the longest catalogued contract life, the averaging window, and the settlement timer plus dispute allowance (Policy 3); that `m + min Δ_label ≥ G` (Policy 2); and that `max_clock_error` is recorded for every source used. Any failed or undeterminable check refuses the whole release. Because protected contracts stay clear of released rows only if the lookback is at most `m`, a feature or model whose lookback exceeds the registered cap is ineligible as the cycle's candidate. **Proposed:** registering the lookback cap at cycle registration is the Statistician's recommended mechanism for the Policy 3 bound, for owner confirmation at step 6a | Policy 2; Policy 3; Statistician B6S-4 |
| R-7 | Label-channel and as-of fields are released only for development-eligible contracts. For **every** acquisition or capture whose fetch or receipt time is `≥ B − m` (and, by default, every acquisition), each as-of field is released only where its as-of time is `< B − m`; otherwise it is stripped and the stripping is ledgered. A record version (vendor correction, revision, bust-filtered survivor set, resolution amendment) is released only in the version whose `known_at < B − m`. If that version cannot be identified, the record fails closed | RT-B3-02 (which names after-`T0` fetches; widened to the margin per Statistician B6S-5) |
| R-8 | The first release for a cycle is durably recorded, and that record freezes the cycle's protected scope (no further widening). The record is written durably and bound to the holdout log (`src/pmv/holdout_log.py`) **before** any release output becomes agent-readable (write-ahead). An interrupted release produces no agent-readable output and is retried or ledgered as failed | S-4 |
| R-9 | Release output is content-hashed, and the hash is appended to the acquisition manifest (or capture record) | RT-B3-02 |
| R-10 | One shared catalog with the guard. While both controls exist, a row reaches an agent only if every applicable control allows it; any disagreement fails closed | RT-B3-05; H-2; `docs/protected_information.md` "Batch 4" |
| R-11 | Every release is logged. Released periods bind every later protected interval. **Open design question (for the owner at step 4):** where the release log lives, and whether it is entered in `docs/exposure_register.md` or cited by hash in every later `cycle_registered` event, so that the H-1 binding check is mechanical | CLAUDE.md Protected Information Rule class 1; CLAUDE.md Holdout Protection; H-1 formation (a) |
| R-12 | No value, label, or outcome appears in refusal reasons, logs, or ledgers produced for agents. Agent-facing release reports give only the released set, its hash, and aggregate refusal counts by reason, with no per-period breakdown at or after `B − m`. Per-row ledgers of withheld post-boundary rows stay owner-side, in the protected store | `docs/protected_information.md` (guard refusal discipline); Statistician B6S-11 |
| R-13 | Only raw rows, fields, and records cut under R-3 to R-7 are released. A derived artifact is released only if it is a deterministic function of already-released rows, so agents can recompute it; otherwise every derived value counts as a row whose information time is the latest information time of its inputs. File-level metadata, headers, vendor summaries, manifests, and cards are not released unless catalogued as fields with information times and cut under R-6 | RT-B3-02 item 4 (cards and summaries "to present"); Statistician B6S-6 |
| R-14 | Every withheld or purged development contract is reason-coded in the exclusion ledger (`split_boundary_purge`, `label_after_boundary`), and its rate is reported by stratum (`docs/phase2.md` §13), because disputes and late finalizations cluster near the strike | Policy 2; Statistician B6S-13 |

## Inputs the tool will read (all trusted, none caller-asserted)

- the committed protected-scope registry and its cycle (`B`, `m`, `E`), verified as the guard verifies it (`python -m pmv.protected_scope verify-history`);
- the shared source catalog: per `source_id`, every field's role (observation time, observable value, label channel, as-of), its equivalent-observable families, and its time field;
- the contract-lifecycle metadata needed for `I(k)` (H-3 point-in-time metadata; `POST_HOC` rows use the synthetic finalization rule in Policy 3);
- the acquisition record (`acquisition.json`) and receipt journal written by the acquisition pipeline (`src/pmv/acquisition/pipeline.py`, `receipts.py`), so only verified raw bytes are cut. Since B07, pipeline journal entries are bound to the acquisition and to the hash of its authorizing bundle (RT-B6-27). Entries from the B06 `Quarantine` class (v1) stay unbound and are not a release input.

## Prerequisite chain (each step gates the next)

| Step | What | Who decides | Gate |
|---|---|---|---|
| 1 | Owner decision on E-U1 (catalog expansion: settlement references and their inputs, venue non-contract endpoints, near-copy contracts, tokenized gold) | Owner | Before step 2 |
| 2 | P-3 criterion proposed (Statistician, development data only) and approved (owner) | Owner | Before step 6a; may run in parallel with steps 3 to 5 |
| 3 | Shared `source_id` catalog implemented as a reviewed change to the guard, Red-Team reviewed with no unresolved BLOCKING finding | Owner approval of the control change | Before step 4 |
| 4 | Release tool implemented and tested on synthetic data only, against properties R-1 to R-14, with fault injection (unknown source, unknown field, undeterminable time, mixed-content file, as-of field past the boundary, contract crossing `B − m`, catalog/guard disagreement, interrupted release) | Development | Before step 5 |
| 5 | Reliability / Red-Team review with no unresolved BLOCKING finding; Statistician review of R-3 to R-7, R-13 against Policy 2 (development self-review, not independent; the development Statistician co-authored Policy 2) | Reviewers | Before step 6a |
| 6a | Cycle registration with `T0`, `m`, `C0`, `T_end` or the stopping rule, and the registered lookback cap (R-6a). Requires P-1 to P-4, guard prerequisites 4 and 6, and committed F-09 denies | Owner | Before any release |
| 6b | Before the first release: either guard prerequisites 1, 3, 7, 8, and 9 are resolved in the guard, or step 7 has retired them. Without one of these the guard refuses every real request and no release is possible | Owner | Before the first release |
| 7 | Owner-approved governance change retiring guard prerequisites 1, 3, 7, 8, 9 | Owner | Required before the first release unless those prerequisites are resolved in the guard instead (6b); until then both controls apply |

Steps 1 to 5 may proceed before `T0` and need no real observation. Step 4 may start once steps 1 and 3 are done, in any later batch, on the active ground-truth branch.

**Open owner escalation (Statistician B6S-14; optional, strongly recommended, not blocking).** A release cannot be undone, and the only statistical review before the first release is development self-review. H-6 schedules the independent statistical audit at Gate 2, after the first releases. Proposal: the Independent Statistical Auditor reviews R-3 to R-7, R-13, and the step 4 fault-injection results before step 6b, and Gate 2 cites that review. Tradeoff: one extra review, slightly delaying the first development data. This is **not** adopted; it needs owner approval.

## What exists now that the tool will build on

- `src/pmv/acquisition/`: verified intake (hash-on-receipt, durable receipt journal, manifest-gated release from quarantine into the protected raw store). That release is a **storage** step, not an agent release (A-8).
- `src/pmv/data_access_guard.py` and `src/pmv/protected_scope.py`: the registry, its history verification, and the current refusal semantics.
- `src/pmv/holdout_log.py`: the tamper-evident holdout log, where the S-4 first-release record is expected to be bound (`docs/protected_information.md`, S-4).
