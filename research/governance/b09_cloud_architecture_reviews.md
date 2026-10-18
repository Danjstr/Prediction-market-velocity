# B09 cloud architecture and source inventory: advisory reviews and dispositions (2026-10-18)

**Status:** governance evidence. Advisory only. No reviewer makes an owner decision.

**Subjects:**
- first drafts of `research/cloud/pmv_cloud_architecture_review.md`;
- `research/cloud/pmv_cloud_cost_model.md`;
- `research/data_sources/` inventory files;
- `docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md`.

**Reviewers.** All ran as `claude-opus-5-5`, with fresh context and read-only. None authored the drafts. These are development reviews, not independent audits.

**Owner corrections.** The owner's corrections of 2026-10-18 (decision record §1.2) override any disposition below that conflicts with them, notably:
- the Kalshi licence classification;
- the training backend;
- the Organization timing;
- the B07/B08 direction;
- BigQuery;
- control timing.

**Disposition codes:**

| Code | Meaning |
|---|---|
| ADOPTED | Incorporated into the canonical design or inventory |
| BOUNDARY:X | Required at the named timing boundary of architecture §2. It does not affect the next action. Boundaries: HIST (first historical byte), REL (first development release), T0M (`T0 − m` / protected capture), EVAL (protected evaluation), LIVE (live trading) |
| OWNER | Raised as an owner decision in decision record §7 |
| NOTED | Acknowledged; no change needed |

## Round 1: verdicts

| Review | Verdict | BLOCKING |
|---|---|---|
| Data / API Engineering | REVISE | DA-B9C-01 (for CLOUD-1) |
| ML Engineer | APPROVE WITH CHANGES | none |
| Reliability / Red-Team | REVISE | RT-B9C-01 (for adoption and CLOUD-1) |
| Statistician | PROCEED WITH CONDITIONS | none |
| Quant / Business Lead | REVISE | none |

## Data / API Engineering (DA-B9C)

| ID | Sev | Finding (short) | Disposition |
|---|---|---|---|
| 01 | BLOCKING | BigQuery public datasets are queryable by any identity with `bigquery.jobs.create`, an embargo bypass | ADOPTED (architecture §2.1 A12): extraction only by a vault identity; job creation not granted to agent or day-to-day identities |
| 02 | MAJOR | "Scheduled query into dev or vault" contradicts the release rule | ADOPTED: vault only |
| 03 | MAJOR | Free sources with unread terms were classed NEEDS_OWNER_CREDENTIAL | ADOPTED: reclassified as NEEDS_LICENCE_CLARIFICATION |
| 04 | MAJOR | No status precedence rule | ADOPTED (inventory §3) |
| 05 | MAJOR | CLOUD DIRECT presented as tested | ADOPTED: "documented, untested from GCP"; connectivity check before A-1; never route around geo restrictions |
| 06 | MAJOR | Per-IP rate limits behind a shared NAT | ADOPTED (architecture §6.3) |
| 07 | MAJOR | Kalshi historical cutoff moves; gold needs the live tier | ADOPTED (architecture §6.3; inventory §7) |
| 08 | MAJOR | Create-only role cannot verify an ambiguous upload | ADOPTED: own-prefix read-back (architecture §6.2) |
| 09 | MAJOR | Parallel journal writers fork the chain | ADOPTED: per-writer chains plus a sealer |
| 10 | MAJOR | No canonical-session rule for redundant collectors | ADOPTED; BOUNDARY:T0M (B6), and before any live capture |
| 11 | MAJOR | Venue connector undesigned | ADOPTED as a work item before live capture (CLOUD-4) |
| 12 | MAJOR | Kalshi capture key can trade | ADOPTED: cloud F-03 successor before any venue credential (B7) |
| 13 | MAJOR | Live COMEX capture missing from the inventory | ADOPTED: G-26 |
| 14 | MINOR | Offshore perps, DVOL, and macro calendar missing | ADOPTED: B-34, B-35, X-1 |
| 15 | MINOR | Rows with two statuses | ADOPTED: PM-06a/b, PM-30a/b, G-7a/b; DET-1 replaces G-25 |
| 16 | MINOR | Within-group sort order | ADOPTED |
| 17 | MINOR | Incomplete CDI summary | ADOPTED: CDI is in every matrix row; the separate summary was removed |
| 18 | MINOR | "F" tag reads as verified; "best practicality" overclaim | ADOPTED: FS tag; "potentially best" |
| 19 | MINOR | Shared-core VMs, clock, and maintenance | ADOPTED; BOUNDARY:T0M and live capture |
| 20 | MINOR | Object names may leak scope | ADOPTED: opaque feed IDs; segment-open date |
| 21 | NOTE | Acquisition order should be conditional on which permission arrives first | ADOPTED (inventory §7) |
| 22 | NOTE | Kraken archive host unverified | ADOPTED: noted in B-2 |

## ML Engineer (ML-B9C)

| ID | Sev | Finding (short) | Disposition |
|---|---|---|---|
| 01 | MAJOR | B07/B08 are filesystem-bound; do not rewrite them for object storage | ADOPTED; the owner approved this design direction (architecture §6.2) |
| 02 | MAJOR | Main-only images make the owner the throughput limit | OWNER (D-B09-15, optional dev-experiment tier) |
| 03 | MAJOR | Three training backends | ADOPTED and owner-confirmed: GCP Batch only; Vertex deferred, not rejected |
| 04 | MAJOR | Two normalizers can diverge | ADOPTED with S-B9C-02: one normalizer digest; release raw rows; Gate 6 re-normalization with a parity check |
| 05 | MAJOR | Per-fold shard copies | ADOPTED: fold manifests |
| 06 | MAJOR | Reproducibility under-specified; no ML dependencies yet | ADOPTED (architecture §8); BOUNDARY:REL for training |
| 07 | MAJOR | Training-serving parity and artifact formats missing | ADOPTED; parity BOUNDARY:LIVE, formats at the first training |
| 08 | MINOR | Ledger is single-writer | ADOPTED: ledger ingest stage |
| 09 | MINOR | Dev loader second layer | ADOPTED (BOUNDARY:REL, R3) |
| 10 | MINOR | Keep the orchestration minimal | ADOPTED |
| 11 | MINOR | BigQuery optional | ADOPTED and owner-confirmed |
| 12 | MINOR | Missing cost lines (NAT, IPs, registry growth) | ADOPTED (cost model) |
| 13 | MINOR | Seccomp worker inside Cloud Run's sandbox | ADOPTED: Batch/VM; Cloud Run only after the self-test passes |
| 14 | MINOR | Effort understated | ADOPTED: about 3–4 months to the first experiment |
| 15–18 | NOTE | CPU benchmark before GPU; no Claude in Cloud Shell; LLM-free; arithmetic checked | ADOPTED / NOTED |

## Reliability / Red-Team (RT-B9C)

| ID | Sev | Finding (short) | Disposition |
|---|---|---|---|
| 01 | BLOCKING | Act-as paths bypass the deny (impersonation, signing, HMAC, job or VM mutation, overrides, SSH, snapshots) | ADOPTED: the A7 deny covers act-as, disk, SSH, snapshot, serial-port, key-creation, and policy-change paths from the first historical byte (wording corrected after RT-B9C2-01). Launcher identities are named (A16). The owner-role fault-injection test verifies it at T0M (B2) |
| 02 | MAJOR | Without an Organization, the owner can remove the deny | Owner direction: Stage A accepts this administrative-override risk for pre-`T0` historical development, with the other controls in place. The Organization, VPC-SC, organization policies, and administrator separation are BOUNDARY:T0M (B1). No binding rule requires an Organization earlier (architecture §2.1) |
| 03 | MAJOR | Logs, tracebacks, and egress as leak paths | ADOPTED: restricted log bucket and closed schema at HIST (A10); no internet egress for data-reading vault jobs and the dev create-deny at REL (R4, R8) |
| 04 | MAJOR | Backup project parity; single-provider risk | Backup parity BOUNDARY:T0M (B3); durability decision OWNER (D-B09-13) |
| 05 | MAJOR | Agents can push workflow files; environment policy; plan identity; review claim | ADOPTED (architecture §10); the review-claim correction is recorded |
| 06 | MAJOR | Credential paths beyond gcloud | ADOPTED: credential rule OWNER (D-B09-11) at HIST (A4) |
| 07 | MAJOR | Release-job trigger, overrides, and write-ahead | ADOPTED; BOUNDARY:REL (R2) |
| 08 | MAJOR | Ambiguous upload | ADOPTED (same fix as DA-08) |
| 09 | MAJOR | Lifecycle cannot condition on manifests; bucket-policy changes | ADOPTED: no age-based deletion; policy-change denies (the GCS landing bucket and promotion account were later removed, RT-B9C3-06) |
| 10 | MAJOR | Public BigQuery datasets into dev | ADOPTED (same fix as DA-01/02) |
| 11 | MAJOR | Trading-capable capture key | ADOPTED: B7 before any venue credential |
| 12 | MAJOR | Console AI assistants as an LLM path | Organization-policy enforcement at BOUNDARY:T0M (B1). From the first historical byte, Terraform keeps the Gemini for Google Cloud API disabled in vault and backup (A18, after RT-B9C2-05) |
| 13 | MINOR | Kill-switch scope; frozen artifacts location | ADOPTED (cost model; EVAL E5) |
| 14 | MINOR | Alert path; per-key limits | ADOPTED; BOUNDARY:T0M and live capture |
| 15 | MINOR | Invented retention period; egress overclaim; missing costs | ADOPTED: retention is an owner input under A-3 |
| 16 | MINOR | Metric labels may encode outcomes | ADOPTED: closed enumeration |
| 17 | MINOR | Overclaims and gate language | ADOPTED: the verdict is labelled advisory; SECONDARY marked; Tardis "reportedly"; D-B09-5 "recommend withdrawing, owner to rule" |
| 18 | MINOR | Placeholders and dangling references | ADOPTED: decision record completed; this file created |
| 19 | NOTE | Journal race; service-agent exceptions; state secrets | ADOPTED |

## Statistician (S-B9C)

| ID | Sev | Finding (short) | Disposition |
|---|---|---|---|
| 01 | MAJOR | Telemetry counts after `T0 − m` are observations | OWNER (D-B09-19; proposed amendment to `docs/external_access.md` §3); BOUNDARY:T0M (B4) |
| 02 | MAJOR | Release raw rows only; normalizer drift | ADOPTED (REL R2, R5; EVAL E3) |
| 03 | MAJOR | Split by information time, not object date | ADOPTED (architecture §5.2) |
| 04 | MAJOR | Prospective equivalent for every historical feature source | ADOPTED (inventory §7a; G-26 added) |
| 05 | MAJOR | Capture is the binding constraint; choose `T0` after a power estimate | ADOPTED. Reconciled under owner correction 8: capture early does **not** bar historical development (architecture §5.3) |
| 06 | MAJOR | Gold feasibility in cycle 1 | OWNER (INV-4 / D-B09-21), required before cycle registration |
| 07 | MAJOR | BRTI vintages; labels from official resolution only | ADOPTED (inventory §7 step 4) |
| 08 | MAJOR | Untracked degrees of freedom (ad-hoc queries, HP search) | ADOPTED (architecture §4, §8; REL R7, R9) |
| 09 | MAJOR | Redundant collectors bias receipt time | ADOPTED (with DA-10) |
| 10 | MINOR | Fold spec registration | ADOPTED |
| 11 | MINOR | Label-channel service accounts; as-of joins; canary test | ADOPTED |
| 12 | MINOR | Reproducibility record; licence deletion duties | ADOPTED |
| 13 | MINOR | Universe completeness | ADOPTED (inventory §5) |
| 14 | MINOR | Placeholder references; pre-cycle break-glass; PM-26 counts as exposure | ADOPTED |
| 15 | NOTE | Release staging and write-ahead | ADOPTED (REL R2) |

## Quant / Business Lead (BIZ-B9C)

| ID | Sev | Finding (short) | Disposition |
|---|---|---|---|
| 01 | MAJOR | No kill or spend gates | OWNER (D-B09-18, proposed K1–K4) |
| 02 | MAJOR | Kalshi request omits live-use and "commercial" questions | ADOPTED (inventory §2) |
| 03 | MAJOR | A near-free go/no-go exists and was not named | ADOPTED as a proposal: milestone M-0 in D-B09-18 |
| 04 | MAJOR | Gold reference costs out of proportion | ADOPTED in INV-4 and K4; OWNER |
| 05 | MAJOR | No break-even framework | ADOPTED (cost model §5a, inputs unmeasured) |
| 06 | MAJOR | Tardis books mismatched to Kalshi's 1-minute resolution | ADOPTED: new trigger (inventory §4.4) |
| 07 | MINOR | BRTI value overstated before a free proxy test | ADOPTED (inventory §7 step 4) |
| 08 | MINOR | Excluding Coinbase weakens the BRTI proxy | ADOPTED (B-5/B-7 next action) |
| 09 | MINOR | Polymarket spend deprioritised; state why | ADOPTED |
| 10 | MINOR | Cloud build may outrun legal data | ADOPTED: minimal CLOUD-1; Stage A/B |
| 11–12 | NOTE | Capture is the best-value spend; GPU lines premature | NOTED |

## Superseded proposals (recorded so nothing is lost)

| First-draft proposal | Replaced by | Why |
|---|---|---|
| Object-store backends for B07/B08 | Unchanged filesystem stores on cloud disks plus a sealed-object uploader | ML-B9C-01; owner direction |
| Cloud Run Jobs or Batch for CPU training, Vertex Spot for GPU | GCP Batch for both; Vertex deferred | ML-B9C-03; owner direction |
| Organization as a precondition for the first real byte | Stage A without one (risk accepted); Organization at Stage B | Owner direction (2026-10-18) |
| Release of normalized rows | Raw rows only | S-B9C-02 |
| `vault-normalized` as an evaluation input | Operational only; Gate 6 re-normalization with frozen code | S-B9C-02, ML-B9C-04 |
| Retention "for example 1 year" | Owner input under A-3 | RT-B9C-15 |
| GCS `vault-landing` bucket plus `sa-vault-promote` | The uploader writes directly to `vault-raw`; B07/B08 already quarantine and check on disk | RT-B9C3-06 |
| Release and protected evaluation as Batch jobs triggered by owner-admin | Fixed Cloud Run Job or Workflow; owner-admin holds only the execute permission, no act-as | RT-B9C3-02 |
| Kalshi capture last in the acquisition order | Prospective capture as early as licences allow | S-B9C-05 |
| "If confirmed, every Kalshi source is PROHIBITED" | Per-surface NEEDS_LICENCE_CLARIFICATION | Owner correction 1 |

## Round 2 (focused re-reviews after the owner's corrections)

| Review | Verdict | BLOCKING |
|---|---|---|
| Reliability / Red-Team (focused re-review; same reviewer role as round 1, so not independent of its own recommendations) | **RESOLVED** | none |
| Statistician (focused consistency check) | **CONSISTENT WITH CONDITIONS** | none |

Both reviewers confirmed that nothing blocks the next action: owner decisions, plus a CLOUD-1 Terraform foundation with no data. The Red-Team confirmed that the owner's Stage A risk acceptance is recorded accurately, and that the Stage A controls are adequate for the accepted threat model (F-05) once RT-B9C2-01 to -03 are fixed. They are fixed below.

### Red-Team round 2 (RT-B9C2)

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| 01 | MAJOR | SSH, OS Login, serial-port, snapshot, image, and disk-attach paths sat only at T0M, although raw data lives on vault disks from the first historical byte | ADOPTED: added to A7 at HIST, with configuration controls where IAM deny cannot express them; B2 is now verification |
| 02 | MAJOR | `pmv-dev` egress unrestricted; agent-written jobs could fetch live data | ADOPTED: A17 in CLOUD-1 (no default network, egress deny-all, no NAT, Private Google Access); vault egress per source |
| 03 | MAJOR | Act-as contradiction: no identity could launch vault jobs | ADOPTED: A16 names `sa-deployer-vault` (`actAs` to define jobs and VMs, `main`-bound, owner-reviewed) and the owner-admin trigger as the only exceptions |
| 04 | MAJOR | Owner applies agent-written Terraform with full credentials | ADOPTED: A15 (verified `main` commit; owner plan review; no `external`/`local-exec`/`http`; pinned modules; lock file with hashes) |
| 05 | MINOR | Dangling "owner actions" reference; AI-assistant API | ADOPTED: A18; RT-B9C-12 disposition corrected |
| 06 | MINOR | Decision record §1.1 still proposed object-store backends; wrong section refs | ADOPTED |
| 07 | MINOR | Object-delete deny conflicted with promotion; double listing | ADOPTED: per-bucket scoping in A7 |
| 08 | MINOR | CLOUD-1 row claimed A1–A13 | ADOPTED: CLOUD-1 delivers A2–A8, A10, A11, A13, A15–A18 |
| 09 | MINOR | `T0` vs `T0 − m`; live-capture note | ADOPTED: deliberate tightening recorded; live capture before `T0 − m` needs architecture §2.1 plus B6–B8 |
| 10 | MINOR | No enforcement of "no keys" without an Organization | ADOPTED: key creation in the A7 deny, no exceptions |
| 11 | NOTE | `_Default` log bucket duplicate | ADOPTED: excluded (A10) |

### Statistician round 2 (S-B9C2)

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| 01 | MINOR | "Conflict" is an ambiguity | ADOPTED: the selection discussion (now architecture §5.3) reframed as an interpretation to confirm; decision record §1.2 reworded |
| 02 | MINOR | S-9 stated too narrowly; pilot selection as a funnel | ADOPTED: both S-9 lines quoted; option (a) wording; funnel controlled through the ledger |
| 03 | MINOR | Tradeoffs of (a) and (b) not given; a middle option exists | ADOPTED: costs and risks stated; option (c) added to D-B09-20 |
| 04 | MINOR | Separation of duties | ADOPTED: the development Statistician wrote S-9; Independent Statistical Auditor review at Gate 2 (H-6) |
| 05 | NOTE | Owner quote inconsistent | ADOPTED: verbatim quote in both places |
| 06 | MINOR | "Labels official only" missing from the inventory | ADOPTED: inventory §7 step 4 |
| 07 | NOTE | S-04 and S-12 had no boundary | ADOPTED: B9 (equivalents, at cycle registration); A14 (deletion duties as a selection criterion) |
| 08 | MAJOR under (a); boundary: cycle registration | §7a timing too weak for selectability | ADOPTED: equivalent-capture start is a power-driven input to `T0` (inventory §7a; architecture B9). Assigned to cycle registration; does not affect the next action |
| 09 | MINOR | M-0 rules | ADOPTED in D-B09-18 (conservative latency rung, preregistered, logged, not selection evidence, ask-quote check) |

**Remaining MAJOR findings:** only S-B9C2-08. It is assigned to cycle registration and does not affect the next action. No BLOCKING finding remains.

## Round 3 (final focused re-reviews after the canonical rewrite)

| Review | Verdict | BLOCKING |
|---|---|---|
| Reliability / Red-Team (same reviewer role; not independent of its own earlier recommendations) | **RESOLVED** | none |
| Statistician (focused consistency check) | **CONSISTENT WITH CONDITIONS** | none |

The Red-Team confirmed that all round-2 findings survived the rewrite, that Stage A is adequate for the accepted threat model (F-05), that the Stage B placement is correct, and that no Stage B control blocks historical acquisition. The Statistician confirmed:
- the historical-development statement;
- the permanent development-only status of released data;
- the information-time split;
- the prospective semantics, including the `T0 − m` tightening;
- normalization parity.

### Red-Team round 3 (RT-B9C3)

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| 01 | MAJOR | No stated run path for historical acquisition; the A7 deny might leave none | ADOPTED (A16): each chartered acquisition is a Terraform-defined VM (or Batch job if supported) with a named disk, applied from `main` after owner plan review. `sa-deployer-vault` is the only act-as holder. No scheduler-triggered runs at Stage A |
| 02 | MAJOR | "Overrides denied" cannot be enforced on Batch | ADOPTED (R2, E2): release and protected evaluation are fixed Cloud Run Jobs or Workflows; owner-admin holds only the execute permission, no act-as |
| 03 | MINOR | The owner-admin act-as exception is unnecessary at Stage A and contradicts A6 | ADOPTED: no human act-as on vault accounts; execute permission added no earlier than R1/E1; Stage A break-glass is a logged owner edit of the deny policy |
| 04 | MINOR | "No GitHub credential" contradicts the deploy key | ADOPTED (A4, §6, D-B09-11): the single-repository deploy key is the only permitted GitHub credential, with its limits stated |
| 05 | MINOR | Default Compute service account; tag-based deny scoping; per-category exceptions | ADOPTED (A7) |
| 06 | MINOR | Landing and raw buckets contradict each other | ADOPTED: no landing bucket; the uploader writes directly to `vault-raw`; `sa-vault-promote` removed; `vault-ops` holds the operational normalizer output |
| 07 | MINOR | Upload path details | ADOPTED (architecture §6.2): download-and-hash read-back; pre-upload manifest check; mismatch kept locally and uploaded under `quarantine/`; retirement step accepted by the store's integrity checks; `sa-journal-sealer`; named disks, not Spot, for resumable acquisitions |
| 08 | MINOR | WIF and Terraform hardening | ADOPTED (A15, §10): apply the exact saved plan; no `pull_request_target` or `workflow_run`; state per environment; optional `job_workflow_ref` pin |
| 09 | NOTE | A18 should cover ops; the A12 wording on `bigquery.jobs.create` | ADOPTED: A18 covers all projects; BigQuery API disabled in dev until chartered (A12, A17) |

### Statistician round 3 (S-B9C3)

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| 01 | MAJOR | Private Google Access still reaches Google APIs that return outside data (BigQuery public datasets, public buckets, Vertex/Gemini, Cloud Build, Storage Transfer) | ADOPTED in CLOUD-1 (A17): enumerated API allowlist in `pmv-dev`, with BigQuery, Vertex/Gemini, Cloud Build, and Storage Transfer disabled unless chartered; a technical control on public datasets if BigQuery is enabled; the Stage B perimeter also covers dev (B1) |
| 02 | MINOR | Break-glass after `T0 − m` | ADOPTED (B5): logged in HOLDOUT_ACCESS_LOG.md; contamination if it could reach development |
| 03 | MINOR | How released rows become readable | ADOPTED (R2): only objects under a committed manifest |
| 04 | NOTE | Vault normalizer output has no rule | ADOPTED: `vault-ops`, kept in the vault, never an evaluation or release input; QA follows A10 and B4 |
| 05 | NOTE | "One normalizer digest" | ADOPTED (E3, §8): the frozen candidate's normalizer digest; data under older digests is re-derived or excluded |
| 06 | NOTE | Option (a) cost; inventory wording | ADOPTED: cost added in §11 |

**Remaining MAJOR findings after round 3:** S-B9C2-08 only, assigned to cycle registration. It does not affect the next action. **No BLOCKING finding remains.**

## Round 4 (final focused Red-Team re-review of the from-scratch canonical rebuild)

**Verdict: RESOLVED.** No BLOCKING finding. The reviewer confirmed that all round 1–3 fixes are present in substance and found no harmful duplication. Same reviewer role as earlier rounds. No Statistician re-check was run, because the rebuild did not change the statistical design.

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| 01 | MAJOR | `pmv-backup` had no deny controls at Stage A; the owner's basic Owner role would expose the backup copy | ADOPTED: at Stage A the backup is a `vault-backup` bucket inside `pmv-vault` (second region) under the A7 deny; restore targets under the same deny; a separate `pmv-backup` only with B3 parity |
| 02 | MAJOR | The Terraform apply identity contradicted A16 | ADOPTED (A15): one-time owner bootstrap apply; afterwards vault applies only as `sa-deployer-vault` (CI, or logged impersonation, with the token-creator grant named as the transitive path under the accepted residual risk); decision record §8 updated |
| 03 | MINOR | Uploader ordering, quarantine permission, mismatched canonical objects | ADOPTED (§6.2, §10, R2): retire only after verification; writers may create under `quarantine/`; manifests uploaded last as commit markers; normalizer and release verify SHA-256 against manifests |
| 04 | MINOR | Cloud Shell prohibition dropped | ADOPTED (A4, D-B09-11) |
| 05 | MINOR | Saved-plan binding; Action pinning | ADOPTED (A15) |
| 06 | MINOR | Dev reaches public GCS buckets without VPC-SC | ADOPTED: stated in A17; B1's no-Organization residual record must cover it (boundary T0M) |
| 07 | MINOR | Small regressions (A7(f) wording, VM mutation, R2 permission names, scheduler note, "Cannot" entries) | ADOPTED |
| 08 | NOTE | Stale references in this file | ADOPTED |

**Remaining MAJOR findings:** S-B9C2-08 only, assigned to cycle registration. **No BLOCKING finding remains.**
