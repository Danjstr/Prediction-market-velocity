# B09 (continued): cloud-native data strategy, source inventory, and cloud architecture review (2026-10-18)

**Approver:** the project owner, in the "OWNER DIRECTION — B09 SOURCE INVENTORY + CLOUD-NATIVE ARCHITECTURE REVIEW" issued on 2026-10-18 in the isolated environment, on B09 at `f78d7e2`. The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record, an acquisition approval, a licence determination, or a provisioning approval.** It records one owner architecture decision (§1) and one research authorization (§2), reports what the review did, and returns an owner-decision packet (§7). It changes no code, control, holdout rule, or governance document.

Analyses:
- `research/data_sources/master_source_inventory.md` (source inventory, status matrix, coverage map, acquisition order);
- `research/cloud/pmv_cloud_architecture_review.md` (architecture verdict and design);
- `research/cloud/pmv_cloud_cost_model.md` (cost model);
- `research/governance/b09_cloud_architecture_reviews.md` (five advisory reviews and dispositions).

## Direction (summary of the owner's instructions)

- **Priority change inside B09.** Before any bulk acquisition: (A) a comprehensive available/unavailable data-source inventory; (B) a review and challenge of the proposed GCP storage and training architecture.
- **Branch.** Stay on `b09/kalshi-source-qualification`. Do not merge `main`. Do not create B10. Do not open the B09 pull request yet.
- **Prohibited in this task:** provisioning cloud resources, bulk-downloading or streaming market data, saving large market responses locally, creating raw-data directories or databases on the Chromebook, creating accounts or credentials, using API keys, paid purchases, accepting terms, private or trading API calls, WebSocket capture, scraping behind access controls, and training models.
- **Stop point.** Return the inventory, the architecture verdict, and the plan to the owner, then stop.

## 1. Owner architecture decision: PMV is cloud-native

Recorded as directed. Operative text, from the owner's direction:

> PMV is now explicitly CLOUD-NATIVE.
>
> The owner's Chromebook:
> - may contain the Git repository;
> - may run Claude Code;
> - may run lightweight development/unit tests;
> - may administer cloud resources;
> - may view small reports/metadata;
>
> but it must NOT be the primary or intermediate storage location for bulk PMV market datasets and must NOT be relied on for production-scale model training.
>
> Bulk historical/live data, normalized datasets, feature artifacts, model artifacts, and protected-holdout data must live in managed cloud infrastructure.
>
> Do not treat /workspace, /home, /tmp, or any Chromebook-mounted directory as the future PMV data lake.
>
> This decision supersedes any earlier assumption that real PMV datasets would be persisted primarily on the Chromebook.

Also from the direction:
- the intended acquisition flow is source → cloud acquisition worker → cloud raw bucket, never source → Chromebook → upload. "The Chromebook should never be a bulk-data relay";
- the proposed baseline provider is Google Cloud Platform, to be reviewed rather than accepted blindly;
- owner-only actions (billing account, payment details, accepting provider terms) stay manual.

### 1.1 What this decision supersedes, and what it does not change by itself

The decision is in force as an owner architecture direction. It conflicts with approved text that places the protected raw store on the local machine. CLAUDE.md requires such conflicts to be surfaced, not silently resolved:

| Approved text | Says | Conflict | Proposed handling |
|---|---|---|---|
| Step 11 F-01 (`docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`) | Real raw data lives in the protected area `~/pmv-protected/raw` | The cloud decision moves bulk raw data to managed cloud storage | Owner decision D-B09-10: a cloud successor to F-01 (the vault project, §3 of the architecture review), keeping F-01's purpose (agents cannot read unreleased raw) |
| `docs/raw_data.md`, `docs/protected_information.md`, `docs/phase2.md` §1, `docs/external_access.md` A-7 | The raw store root must resolve inside `~/pmv-protected/raw`; A-7 "protected raw store" | Same | Amend after D-B09-10, as a reviewed documentation change |
| Code: `pmv.config.load_config`, `python -m pmv.data_access_guard check-config`, the B07 acquisition pipeline and B08 capture store (filesystem only) | Enforce the local root; filesystem semantics (fsync, rename, append) | The stores are filesystem-based by design | Owner-approved design direction (§1.2 item 4; architecture §6.2): keep B07/B08 unchanged on a cloud-side persistent disk and add a sealed-object uploader to GCS (CLOUD-2, Red-Team reviewed). The configuration rule that enforces the local root is amended after D-B09-10. Until then, **no real acquisition can run anywhere**, which is already the case |
| `docs/backup_and_recovery.md` "Policy boundary" and A-3 | Raw backup policy not yet defined | The B09 D-B09-5 recommendation (Option 1, an encrypted external drive) is a local, single-site design | Recommend withdrawing D-B09-5 Option 1 in favour of a cloud A-3 policy (a separate backup project and region, versioning, unlocked retention, restore test), D-B09-13. The owner rules |
| START_HERE.md, CLAUDE.md, PROJECT_BRIEF.md | Do not name a storage location; CLAUDE.md "Agent Cost Discipline" mentions the Chromebook only as a resource limit | No direct conflict found | None needed now. If the owner wants the cloud-native principle in a governing document, that is a separate governance edit |
| `.claude/settings.json` | Denies `~/pmv-protected`, `~/pmv-credentials`, `~/.ssh`, `~/.aws` | Does not deny `~/.config/gcloud` or application-default credentials, which would carry the owner's cloud identity once the owner uses `gcloud` on the Chromebook | Owner action (architecture §2.1 A4 and §10): add the credential rule and denies before any cloud credential exists on the Chromebook. D-B09-11 |

Until those follow-on decisions and edits are made, the approved local-path rules stay as written. They block nothing real today, because no real data may be acquired or captured anyway (A-1 to A-6 unresolved).

### 1.2 Owner corrections of 2026-10-18 (second direction, after the interim output)

The owner reviewed the interim output and directed the following before the decision boundary. Summary of operative points:
1. **Kalshi licence status.** Do not conclude from SECONDARY Data Terms evidence that every Kalshi-derived source needs written ML permission. Keep website data, official API data, PMV's own capture, third-party archives, and upstream reference data distinct. Unless authoritative governing evidence establishes the prohibition for a surface, classify it NEEDS_LICENCE_CLARIFICATION, and record which agreement is believed to govern it and what is unverified. Website Data Terms must not silently control API data.
2. **Training backend.** "GCP BATCH IS THE INITIAL PMV TRAINING BACKEND", with the same deterministic entry point in CPU and GPU containers. Vertex AI is deferred, not rejected, and added only on a demonstrated need (managed HPO, experiment/registry features, distributed training, a GPU capability Batch cannot economically provide). Do not build both.
3. **No Organization precondition for historical development acquisition.** Stage A (historical development, pre-`T0`): separate vault and dev projects, separate service accounts, least-privilege IAM, no agent vault credentials, no service-account keys, owner administration outside Claude Code, raw into the vault, development sees only formally released rows, access and audit logging, immutable create-only raw. Document that without an Organization a project administrator can technically override IAM and deny controls; **the owner is willing to accept that administrative override risk for pre-`T0` historical development acquisition if the rest of the controls are in place.** Stage B (before `T0` and protected prospective holdout): revisit and require stronger isolation (Organization if feasible, VPC-SC, organization policies, administrator separation, protected-evaluation isolation, backup perimeter parity). If an existing binding rule required an Organization earlier, cite and escalate it.
4. **B07/B08.** The owner approves the **design direction, not implementation**: run the acquisition and capture stores on cloud compute with a cloud-side persistent disk; seal completed files and segments; upload create-only to GCS; verify checksum and read-back; GCS becomes durable canonical storage; the Chromebook is never a bulk-data relay. No native object-store rewrite.
5. **BigQuery** optional and non-canonical; canonical data is content-addressed Parquet plus manifests in GCS; not required for the first pipeline.
6. **One canonical architecture document**, without superseded copies, and without losing review findings.
7. **Finish the master source inventory** with the required columns and sources.
8. **Prospective capture clarification.** Capture-first must not be read to mean historical development data cannot be used for model selection. Verbatim: "Historical observations that are validly acquired and formally released as development-only may be used for development/model selection." once exposed they can never become protected holdout. Capture begins early for receipt-time truth, protected evaluation, execution realism, and power, without invalidating the historical-development path.
9. **Security versus speed.** Classify controls by boundary: before first historical byte; before first dev release; before `T0 − m` / protected capture; before protected evaluation; before live trading. Later controls must not block earlier legitimate work.
10. **Reviews.** One focused Red-Team re-review, one focused Statistician consistency check; no new swarm. Resolve every BLOCKING finding; MAJOR findings may remain only if assigned to a later boundary.
11. **Final report** in compact form, with the decisions that need owner approval.

**How they were applied.**
- Corrections 1, 2, 4, 5, 6, 7, and 9 are applied in the canonical documents.
- Correction 3 is applied as the Stage A/B model (architecture §2.1). No binding PMV rule requires an Organization for historical development acquisition. The earlier "Organization before the first real byte" was a Red-Team recommendation, now assigned to the Stage B boundary.
- Correction 8 raised one interpretation question, which is not resolved silently. The Phase 2 working design (`docs/phase2.md`, S-9) is a working-design rule, not an owner-adopted requirement. It restricts validation used for selection, and in particular the **audit-candidate selection comparison**, to receipt-time (`RECEIPT` + `PIT_CAPTURED`) folds. Archive-validated folds are "discovery only" under it.
  - If the owner's "development/model selection" means development-stage selection (exploration, pilot choice, narrowing candidates, all logged), it fits within S-9.
  - If it also covers the final audit-candidate comparison, it departs from S-9.
  - Historical development data remains usable for exploration, training, pilot models, and hypothesis generation either way. This is owner decision D-B09-20 (architecture §5.3).

## 2. Research authorization for this review

Recorded as directed. The owner authorized public web research against official developer documentation, API documentation, data catalogs, pricing pages, legal/terms pages, help and support documentation, reputable vendor documentation, and reputable public technical descriptions needed to determine source coverage. It is **research only**, and expressly excludes acquisition, live collection, API-key use, credential or account creation, purchases, accepting commercial terms, private or trading API calls, WebSocket capture, scraping behind access controls, bypassing paywalls or authentication, and large downloads to the Chromebook.

**How it was applied alongside existing rules.** The authorization does not, by its words, waive the host-class rule or the terms-first rule (CLAUDE.md; `docs/external_access.md` §1.1 rule 3). The session therefore:
- kept every `live-data`, `live-display`, and `trading-private` host denied;
- did not open Hugging Face or Kaggle dataset cards for BTC, gold, or prediction-market data (they count as exposure);
- did not fetch `docs.kalshi.com` or `docs.polymarket.com` content, because their terms live only on denied `live-display` hosts (`kalshi.com`, `polymarket.com`), so terms-first cannot be satisfied (the B09 precedent for `docs.kalshi.com`). Kalshi and Polymarket facts come from the 2026-10-15 and 2026-10-16 snapshots already in Git, and from web-search summaries marked SECONDARY. Re-verification stays with D-B09-8 and AR-6;
- read terms pages first for other vendors, where a terms page was reachable and could not display values.

The owner may rule that this authorization does override terms-first for documentation hosts (decision D-B09-17).

**Network reality.** The isolated container's egress allowlist is fixed and cannot be widened from a session. Every official cloud documentation host and most vendor documentation hosts were refused (list in §5). Facts from those hosts come from web-search summaries and are SECONDARY until re-verified.

## 3. Continuity verified (2026-10-18, before this work)

- `git status --short --branch`: `b09/kalshi-source-qualification`, no tracked changes; the untracked paths listed are sandbox placeholders (`docs/backup_and_recovery.md`), never staged.
- `git rev-parse HEAD`: `f78d7e205555227a7369fe8947cf8ea0b772f321`, equal to `origin/b09/kalshi-source-qualification`.
- `git merge-base --is-ancestor 5806d8c HEAD` returned 0.

## 4. Status that this work does not change

- Phase 1. Gate 1 undecided. A-1 to A-6 unresolved. A-4 not satisfied.
- **Historical acquisition is not authorized. Live capture is not authorized. No cloud resource exists or is authorized.**
- No cycle, `T0`, split, protected scope, or open holdout exists. No real observation has been acquired, captured, or released.
- D-B09-1 to D-B09-9 remain pending. D-B09-5 is affected by §1.1 (see D-B09-13).

## 5. What the review did

### 5.1 External requests

- **Hosts reachable** through the fixed allowlist (checked with HEAD requests by the lead session):
  - `databento.com`;
  - `docs.kraken.com`;
  - `docs.cdp.coinbase.com`;
  - `github.com`;
  - `docs.gemini.com` (redirects to a refused host);
  - `www.bitstamp.net`;
  - `www.lbma.org.uk`;
  - `arxiv.org`;
  - `huggingface.co`;
  - `docs.polymarket.com` and `docs.kalshi.com` (HEAD only; see §5.3).
- **Hosts refused by the proxy** (attempt ended, no mirror tried):
  - `cloud.google.com`, `docs.cloud.google.com`, `status.cloud.google.com`;
  - `aws.amazon.com`, `azure.microsoft.com`, `learn.microsoft.com`;
  - `developer.hashicorp.com`, `www.terraform.io`, `registry.terraform.io`, `docs.github.com`;
  - `tardis.dev`, `docs.tardis.dev`;
  - `pyth.network`, `www.pyth.network`, `docs.pyth.network`;
  - `docs.chain.link`, `www.cmegroup.com`, `datamine.cmegroup.com`;
  - `www.kraken.com`, `support.kraken.com`;
  - `www.coinbase.com`, `help.coinbase.com`;
  - `dune.com`, `docs.dune.com`, `docs.goldsky.com`;
  - `polygon.io`, `massive.com`, `www.dukascopy.com`, `docs.bitstamp.net`;
  - `kalshi-public-docs.s3.amazonaws.com`;
  - `www.backblaze.com`, `developers.cloudflare.com`, `modal.com`, `lambda.ai`, `www.runpod.io`;
  - `legal.databento.com`, `developer.gemini.com`, `www.pmxt.dev`.
- **Pages fetched** by research agents: listed in `research/sources.md`, "B09 cloud and source-inventory review". All are tool-summarized (FETCHED-SUMMARY), so SECONDARY under O-8.
- **Web searches:** about 60 queries across the four research agents. None targeted current, recent, or interval-specific prices, outcomes, or dataset statistics.
- **No** market-data endpoint, API host, WebSocket, RPC, cloud bucket, or Hugging Face/Kaggle dataset card was requested.

### 5.2 Exposures

Three incidental exposures were reported by research agents in search-result summaries. They are entered in `docs/exposure_register.md` Part A as rows X-4 to X-6:
- X-4: Kalshi gold aggregate volume and fees for September 2026, plus one window reference value around August 2026;
- X-5: Polymarket aggregate row counts and volume totals, undated;
- X-6: one undated Pyth gold-index snapshot.

No value was recorded in any PMV file. As of row X-6, the latest exposure end is 2026-10-18 for both BTC and gold. This only constrains `T0`, which is in the future in any case.

### 5.3 Process events (disclosed)

- **Lead session reachability probe.** Before deciding not to fetch Kalshi and Polymarket documentation, the lead session sent HEAD requests to `docs.polymarket.com` (200) and `docs.kalshi.com` (308), among about 50 hosts. HEAD returns headers only; no page content was received. It was still a request to hosts whose terms-first status is unresolved. No further request was made to either.
- **Terms-first deviation.**
  - The terms hosts for Kraken and Coinbase (`kraken.com`, `coinbase.com`) are refused. The BTC research agent nonetheless fetched documentation pages on `docs.kraken.com` and `docs.cdp.coinbase.com` after checking their `robots.txt`, taking the terms content from SECONDARY summaries.
  - CLAUDE.md asks for a licensor's terms before fetching from it.
  - These were documentation pages only, with no market data. The owner may rule on this (D-B09-17).
  - Databento's terms page was unreadable (404 or a JavaScript shell; `legal.databento.com` refused). Its blog pages were fetched following the batch 3 precedent (terms event TE-G1).
- **Data-file rule.** The BTC agent requested `databento.com/sitemaps/index.xml.gz`, a site sitemap and not market data. The output was discarded unread. This breaches `docs/external_access.md` §1.1 rule 9 (no `.gz` requests).
- **Bitstamp.** `robots.txt` disallows `/api/` subpaths, which hold its docs. They were respected, and nothing further was fetched.
- **Models.** Every session and subagent ran as `claude-opus-5-5`, already recorded as M-1 in `docs/exposure_register.md` Part B.

### 5.4 Outputs

- `research/data_sources/master_source_inventory.md`, `inventory_pm_gold_detail.md`, `inventory_btc_detail.md`
- `research/cloud/pmv_cloud_architecture_review.md` (canonical design), `research/cloud/pmv_cloud_cost_model.md`
- `research/governance/b09_cloud_architecture_reviews.md` (round 1 and round 2 reviews with dispositions)
- `docs/exposure_register.md` (rows X-4 to X-6), `research/sources.md` (B09 section), `docs/phase1.md` and `docs/BRANCH_TIMELINE.md` (status)
- This record

## 6. Verdicts

- **Source inventory: complete for this review.** The headline is that licensing is the dominant blocker. No market-data source is AVAILABLE_NOW. Every Kalshi surface PMV would use is NEEDS_LICENCE_CLARIFICATION. Prospective capture remains the only source of receipt-time books and of protected evaluation.
- **Cloud architecture (advisory): GCP ARCHITECTURE APPROVED WITH CHANGES; KEEP GCP.** The canonical design is in the architecture document. It is a recommendation; adopting it is D-B09-14.

## 7. Owner-decision packet (B09 cloud and data)

None of these is taken here. D-B09-1 to D-B09-9 (the 2026-10-16 record) remain pending.
- D-B09-4 is extended by INV-1: per-surface questions, including live use.
- D-B09-5 (Option 1, an external drive) is a local, single-site design. **We recommend withdrawing it in favour of D-B09-13; the owner rules.**

| # | Decision | Recommendation | Urgency |
|---|---|---|---|
| D-B09-10 | **Cloud successor to F-01.** Adopt the `pmv-vault` project as the protected raw store; amend `docs/raw_data.md`, `docs/protected_information.md`, `docs/phase2.md`, and A-7 accordingly (reviewed documentation change); later code change for configuration enforcement | Approve | Before the first historical byte |
| D-B09-11 | **Credential rule.** No cloud credential in any shell where Claude Code runs. The only GitHub credential there is the existing single-repository deploy key (it cannot administer the repository, bypass "Protect Main", approve environments, edit secrets, or create tokens). Owner cloud work happens in Cloud Shell or a separate browser profile, and Claude Code is never run inside Cloud Shell. Plus owner-applied `.claude/settings.json` denies for `~/.config/gcloud`, ADC paths, `~/.config/gh`, `~/.docker/config.json`, `~/.terraform.d` | Approve | Before any cloud credential exists on the Chromebook |
| D-B09-12 | **Stage A risk acceptance and Stage B commitment.** Record acceptance of the administrator-override risk for pre-`T0` historical development without an Organization. Commit to deciding the Stage B isolation (Organization if feasible, VPC-SC, organization policies, administrator separation, backup parity) before `T0 − m` | Approve as directed | Before the first historical byte (A); before `T0 − m` (B) |
| D-B09-13 | **Cloud A-3 backup policy.** At Stage A, a `vault-backup` bucket inside `pmv-vault` in a second region (Coldline), under the vault deny; a separate `pmv-backup` project only with Stage B parity; versioning, retention duration (owner sets), restore test of a synthetic file into a vault-class bucket; single-provider durability measures (backup payment method, hardware keys, account recovery; optional off-provider copy of irreplaceable capture where licences allow). Withdraws D-B09-5 Option 1 | Approve | Before the first historical byte (policy and synthetic restore test) |
| D-B09-14 | **Adopt the canonical architecture as the design basis:** GCP; vault/dev/ops (+backup, runtime later) projects; regions `us-central1` and `us-east5`; B07/B08 on cloud disks with the sealed-object uploader (direction already approved); GCP Batch as the training backend with Vertex deferred; BigQuery optional; the control timing classification | Approve | Before CLOUD-1 is chartered |
| D-B09-15 | **Optional dev-experiment tier** (any-branch images, dev-only submit identity, hard quotas) | Defer until CLOUD-6; approve then if experiment throughput is limited by owner steps | Not urgent |
| D-B09-16 | **Charter the first cloud implementation batch** (CLOUD-0 owner steps plus CLOUD-1 Terraform foundation, §8 below), with a starting budget of about $100/month across projects | Approve after D-B09-10 to D-B09-14 | Next batch |
| D-B09-17 | **External access for research.** (a) Rule whether the 2026-10-18 research authorization overrides terms-first for documentation hosts whose terms live on refused or live-display hosts, and whether the §5.3 Kraken/Coinbase documentation fetches are accepted. (b) Access request AR-B9-2: allowlist the official cloud documentation and pricing hosts (`cloud.google.com`, `docs.cloud.google.com`) for re-verification of the SECONDARY cloud facts before CLOUD-1 | (a) Owner ruling; (b) approve, documentation only | Before CLOUD-1 |
| D-B09-18 | **Kill and spend gates (proposed; thresholds are development hypotheses):** **M-0** go/no-go milestone on free Kalshi history once licensed (late-window calibration gap at the ask after the actual fee formula, with a lower confidence bound above costs plus a margin, and a simple spot-distance model beating the market-implied baseline on tail log loss in walk-forward). **K1** no paid data and no build beyond the bootstrap scenario if Kalshi refuses or does not answer by an owner-set date; then an explicit pivot-or-stop decision. **K2** stop before buying Tardis, BRTI, or Pyth if M-0 fails. **K3** no recurring subscription above a set fraction of conservatively estimated monthly net profit at measured capacity. **K4** no paid gold reference data until DET-1 is resolved and late-window gold volume justifies it | Adopt the gate structure; set thresholds before M-0 runs. M-0 rules: it uses the H-5 conservative primary latency rung; its thresholds are fixed before data inspection; it is logged as a degree of freedom and never reused as selection evidence; a failed M-0 is informative, a passed M-0 is weak evidence (archive artifacts mostly flatter); it is computed at the ask only if PM-01 candles give ask quotes at decision resolution, otherwise the trade-price bias is stated (S-B9C2-09) | Before any paid data |
| D-B09-19 | **Telemetry coarsening after `T0 − m`** (proposed amendment to `docs/external_access.md` §3) | Approve in principle | Before `T0 − m` |
| D-B09-20 | **Selection rule for historical development data** (`docs/phase2.md` S-9, a working-design rule). Options: (a) keep it: archive results screen and narrow candidates as logged hypotheses, and the audit candidate is decided on receipt-time folds (cost: calendar time); (b) amend it so archive-validated folds may decide the audit candidate (risk: an artifact-driven candidate consumes a holdout cycle); (c) archive selection only when receipt folds are underpowered, with a preregistered receipt-time non-inferiority check and a stated overlap-window artifact bound (architecture §5.3) | (a), recommended by the development Statistician, who wrote S-9. The Independent Statistical Auditor reviews it at Gate 2 (H-6) | Before the first development release |
| D-B09-21 | **Gold in cycle 1** (INV-4): exploratory only; or a separate gold cycle; or a stated per-asset power floor | Exploratory only in cycle 1 | Before cycle registration |
| D-B09-22 | **Licence letters and terms copies** (INV-1, INV-3, INV-6). Kalshi extended clarification per surface (including live use and "commercial"); Kraken permission (`marketdata@kraken.com`); CME/Databento written DS-45 scope; optional Coinbase consent and Polymarket licensing enquiry. Supply copies of: Kalshi Developer Agreement, ToS, Data Terms, contract terms; Kraken notice and support articles; Coinbase Market Data Terms; Databento terms; Tardis licence; CME DS-45 and DataMine terms | Send now; agents draft on request | Critical path for every acquisition |

## 8. Recommended first cloud implementation batch (for D-B09-16)

**CLOUD-0 (owner, manual):**
- billing account upgraded beyond the free trial;
- budget alerts;
- region confirmation (`us-central1`, `us-east5`);
- Cloud Shell as the administration surface;
- adopt D-B09-11.

**CLOUD-1 (agents write Terraform. The owner performs a one-time bootstrap apply from Cloud Shell: projects, WIF pool, deployer accounts, deny policy. Later vault applies run only as `sa-deployer-vault`, through CI with environment approval or by logged owner impersonation. A Red-Team review precedes any data):**
- projects `pmv-ops`, `pmv-vault`, `pmv-dev`;
- APIs:
  - Cloud Storage;
  - IAM;
  - Cloud Resource Manager;
  - Secret Manager;
  - Artifact Registry;
  - Cloud Logging and Monitoring;
  - Batch;
  - Compute Engine;
  - Cloud Run;
  - Cloud Scheduler;
  - IAM Credentials;
  - Security Token Service;
- buckets:
  - `vault-raw` and `vault-ops`. `vault-raw` has create-only writers, versioning, default soft delete, no age-based deletion, public access prevention, uniform access, and per-bucket deny scoping. There is no landing bucket;
  - dev buckets (empty);
  - the Terraform state bucket;
- service accounts per architecture §10, with least-privilege roles, the vault deny policy (A7, including disk, SSH, snapshot, serial-port, and key-creation paths), and explicit launcher identities (A16);
- network: `pmv-dev` has no default network, egress deny-all, no NAT, and Private Google Access only. An enumerated API allowlist leaves BigQuery, Vertex/Gemini, Cloud Build, and Storage Transfer disabled. Vault egress is limited per source (A17);
- the run path for chartered acquisitions: a Terraform-defined VM applied from `main` after plan review. `sa-deployer-vault` is the only act-as holder, and no human holds act-as (A16). The default Compute service account's Editor grant is removed;
- the Gemini for Google Cloud API kept disabled in every project (A18);
- Terraform rules (A15):
  - applied from a verified `main` commit, using the exact saved plan the owner reviewed;
  - no `external`, `local-exec`, or `http` data sources;
  - provider lock file with hashes;
  - separate state per environment;
  - no `pull_request_target` or `workflow_run` triggers in deploy workflows;
- Data Access audit logs on vault Storage; a restricted log bucket and routing;
- Artifact Registry (main-only repository);
- Secret Manager containers (no values);
- budget alerts and GPU quota 0;
- Workload Identity Federation with `main`-only protected environments.

**Excluded from CLOUD-1:**
- data;
- venue credentials;
- BigQuery;
- Vertex;
- VPC-SC and the Organization (Stage B);
- the capture VMs (CLOUD-4).

## 9. Status after this work

- **B09 CLOUD/DATA ARCHITECTURE REVIEW COMPLETE — OWNER CLOUD BUILD DECISION REQUIRED.**
- Round 2 to round 4 re-reviews (Red-Team RESOLVED each time; Statistician CONSISTENT WITH CONDITIONS in rounds 2 and 3) left no BLOCKING finding.
- The only remaining MAJOR finding, S-B9C2-08, is assigned to cycle registration (`research/governance/b09_cloud_architecture_reviews.md`).
- Nothing is provisioned, acquired, or authorized.
- B09 stays open: no pull request and no B10 until the owner directs.

## 10. Procurement packet (owner task, 2026-10-18)

At the owner's direction, after the architecture review, B09 produced `research/data_sources/owner_source_action_sheet.md`. It is documentation only:
- an owner core matrix with owner-facing statuses;
- re-verified prices and contacts (official pages where reachable; otherwise OWNER_VERIFY);
- procurement tiers;
- minimum, better, and ideal datasets;
- ready-to-send permission and licence messages M1 to M6.

No account, purchase, licence acceptance, or data download was made.

New findings recorded there:
- **Kalshi Developer Agreement.** It reportedly limits API use and storage to facilitating the member's own trading on Kalshi (S). This sharpens D-B09-22, M1.
- **Databento usage-based billing.** It may be marked "personal use" only, with commercial use on the Standard plan (FS, needs confirmation). See M3.
- **The $20,000–$35,000 CME figure** corresponds to CME's historical redistribution licence, which PMV does not need.
- **Pyth $99/month package.** A package offered through Polymarket's docs may cover XAU (S).
- **Recommendation:** drop Coinbase and CME DataMine for now.

Research agents ran as `claude-opus-5-5`. They made no new exposures, and every refused host was left untried.
