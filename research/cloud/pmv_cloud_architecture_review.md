# PMV cloud-native architecture: canonical design (B09, 2026-10-18)

**Status:** research and recommendation. It is not an approved requirement, not a gate record, and not a provisioning plan that may be executed. Nothing in this document authorizes a cloud resource, account, credential, or data acquisition. Adopting any part of it is the owner's decision (decision record §7).

**Related documents:**
- `docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md`: owner direction and decisions.
- `research/cloud/pmv_cloud_cost_model.md`: cost model.
- `research/data_sources/master_source_inventory.md`: data sources.
- `research/governance/b09_cloud_architecture_reviews.md`: review findings and dispositions. It holds every finding ID and the list of superseded proposals. This document gives only the current design.

**Evidence limits:**
- The container's fixed network allowlist refuses the official cloud documentation hosts.
- Every cloud product fact, limit, and price here is therefore SECONDARY: from web-search summaries, GitHub pages of official projects, or reviewer recollection.
- That includes IAM deny-policy coverage, VPC Service Controls prerequisites, Batch and Cloud Run limits, GPU availability, soft-delete defaults, and lifecycle semantics.
- Each fact is re-verified on the official page before the stage that relies on it (§14).

## 1. Verdict

**Advisory verdict, in the owner's requested form: GCP ARCHITECTURE APPROVED WITH CHANGES.** This is an agent recommendation. Approval is the owner's (D-B09-14).

| Topic | Design |
|---|---|
| Provider | GCP (§2) |
| Data separation | By information class. `pmv-vault` holds every unreleased real observation. `pmv-dev` holds only formally released rows and their derivatives (§4, §6) |
| Security | Staged (§3). **Stage A** (pre-`T0` historical development) needs no Google Cloud Organization; the owner accepts the residual administrative risk. **Stage B** (before `T0 − m`) strengthens isolation |
| Canonical storage | GCS |
| Canonical normalized and feature format | Content-addressed Parquet plus manifests in GCS |
| BigQuery | Optional, non-canonical, not required for the first pipeline |
| Historical acquisition | Batch or Compute Engine with a cloud-side persistent disk where B07 semantics require it. Cloud Run Jobs only for small, bounded paginated pulls |
| Prospective capture | Dedicated cloud VMs, never the Chromebook |
| B07/B08 | Reviewed filesystem semantics preserved. Output is sealed and uploaded create-only to GCS (owner-approved direction; implementation not yet started) |
| Training | GCP Batch for CPU and GPU. Vertex AI deferred, added only if a measured need appears |
| Orchestration | Deterministic Python pipeline runner, plus Cloud Scheduler and Workflows only where needed |
| Infrastructure as code | Terraform |
| CI/CD | GitHub Actions with Workload Identity Federation. Deployments only from `main`, through protected environments |
| Chromebook | Control and development terminal only. No bulk dataset. No reusable cloud credential available to Claude Code |

## 2. Provider recommendation

**Recommendation: keep GCP.** No factor makes AWS or Azure materially better for PMV.

Revisit only in two cases:
- measured runtime latency shows millisecond placement matters (a small runtime footprint could then live elsewhere without moving the data platform);
- a key vendor delivers only to S3, at an egress cost that dominates.

| Factor | GCP | AWS | Azure | Effect on PMV |
|---|---|---|---|---|
| Object storage, single region | about $0.020/GB-month (S) | about $0.023 (S) | about $0.018–0.021 (S) | Immaterial at 0.1–5 TB |
| Internet egress | about $0.12/GB (S) | about $0.09/GB (S) | about $0.087/GB (S) | Immaterial; data stays in the cloud |
| Batch compute | Batch: no service fee, Spot, fixed machine types, GPUs (S). Cloud Run Jobs for small tasks | AWS Batch | Azure Batch | Comparable. GCP is simplest for one person |
| GPUs | T4, L4, A100 in several US regions. New projects start at 0 GPU quota, and the free trial allows no GPUs (S) | Broadest fleet | Narrower | One L4 suffices |
| Operating from a Chromebook | Cloud Shell: browser terminal with gcloud and Terraform (S) | CloudShell | Cloud Shell | GCP has the least friction |
| Isolation primitives | Projects and IAM deny policies work without an Organization. VPC-SC and organization policies need one (S) | Accounts plus SCPs | Subscriptions | Sufficient for PMV's accident-focused threat model (`docs/protected_information.md` F-05) under the staged model |
| Venue proximity | `us-east5` (Columbus) is near AWS us-east-2, where Kalshi is reported to run (S) | Same metro | — | A minutes-scale strategy does not need sub-millisecond placement |
| Lock-in | BigQuery and Vertex are proprietary, but both are optional here | Similar | Similar | Parquet, containers, Terraform, and PMV's ledger keep the design portable |

## 3. Security controls by timing boundary

Each control is required **no earlier than** the boundary listed. Nothing required at a later boundary blocks work at an earlier one. The control IDs are cited by the decision record and the reviews file.

### 3.1 Stage A: required before the first historical byte

**A Google Cloud Organization is NOT required at Stage A.**

**Residual risk.** A sufficiently privileged Google project administrator can technically override some controls. For example, they could remove a deny policy or grant themselves access. The owner explicitly accepts this residual administrative risk for pre-`T0` historical development acquisition, provided the controls below are in place (owner direction, 2026-10-18; D-B09-12). The controls are fail-closed against accidental grants and ordinary mistakes, which is the threat model PMV adopted (F-05).

**Why no Organization is needed now.** No binding PMV governance rule requires one for historical development acquisition. The approved controls are:
- F-01: raw data stays outside agent-readable storage;
- A-7: protected storage is written outside agent sessions;
- A-8: release is a separate step.

Stage A meets all three in cloud form once D-B09-10 adopts the vault as the successor location.

| # | Control |
|---|---|
| A1 | Owner decision D-B09-10: `pmv-vault` becomes the cloud successor to the local protected raw store (F-01). Includes the matching governance edits to `docs/raw_data.md`, `docs/protected_information.md`, `docs/phase2.md`, and A-7 |
| A2 | Separate `pmv-vault` and `pmv-dev` projects, plus `pmv-ops` for Terraform state, the container registry, and restricted logs. Billing account upgraded beyond the free trial |
| A3 | Per-stage service accounts with least-privilege IAM (§10). Writers are create-only, plus read-back of their own prefix |
| A4 | **No agent credential with vault access.** No cloud credential in any shell where Claude Code runs. The only GitHub credential permitted there is the existing single-repository deploy key. It cannot administer the repository, bypass the "Protect Main" ruleset, approve environments, edit secrets, or create tokens. No `gh` or personal token. Owner cloud administration happens in Cloud Shell or a separate browser profile, never in a Claude Code shell (D-B09-11) |
| A5 | **No service-account keys.** Key creation is in the A7 deny for every principal, with no exceptions |
| A6 | The owner's day-to-day identity holds no vault data-read role and no act-as on vault accounts. At Stage A, break-glass is a logged owner edit of the deny policy, reverted afterwards (there is no separate principal without an Organization). Pre-cycle break-glass reads are recorded in `docs/exposure_register.md` Part A |
| A7 | **IAM deny policy on `pmv-vault`, scoped per bucket.** Exceptions are enumerated per category: the named service accounts for their own data paths; `sa-deployer-vault` for (b) act-as and (e) policy changes needed to apply Terraform; break-glass as in A6. It denies:<br>(a) data reads;<br>(b) act-as paths: impersonation, signing, HMAC keys, job mutation, run overrides;<br>(c) disk paths to raw data: OS Login and SSH, serial port, snapshot and image creation, disk attach;<br>(d) service-account key creation;<br>(e) changes to bucket policy, retention, versioning, and IAM; tag-binding create and delete (per-bucket scoping rests on resource tags); and changes to the deny policy itself;<br>(f) object delete on `vault-raw`, for every principal except break-glass.<br>Terraform also removes the default Compute Engine service account's automatic Editor grant (or disables the account), and sets the service account explicitly on every VM and job (SECONDARY).<br>Where IAM deny cannot express a control, configuration enforces it: no external IPs, no SSH ingress rule, project SSH keys blocked, no OS Login admin or IAP-tunnel grants, serial port disabled (SECONDARY; verified at CLOUD-1) |
| A8 | Raw storage: create-only writes (`ifGenerationMatch=0`), object versioning, default soft delete, no age-based deletion of raw or quarantine objects, and no Bucket Lock |
| A9 | Sealed-object uploader writing directly to `vault-raw`, with CRC32C on upload and SHA-256 verification by download-and-hash (§5.2) |
| A10 | Data Access audit logs on for vault Storage. Vault logs are routed to a restricted log bucket in `pmv-ops` and excluded from the vault `_Default` bucket. Logging uses a closed, value-free schema: counts, durations, hashes, and enumerations that exclude outcome, side, strike, and per-market labels |
| A11 | Public access prevention and uniform bucket-level access on every bucket |
| A12 | Historical acquisition runs as a vault service account, including any extraction from BigQuery public datasets of protected equivalents. The BigQuery API stays disabled in `pmv-dev` until chartered (see A17), so no dev or day-to-day path can query those datasets |
| A13 | Cost controls: budget alerts, GPU quota at 0 or 1, and BigQuery custom quotas if BigQuery is enabled |
| A14 | The source's own gate, A-1 to A-6, including the A-2 licence determination and a cloud A-3 backup policy with a synthetic restore test (D-B09-13). Licence retention and deletion duties are a source-selection criterion |
| A15 | Terraform for all of the above:<br>- applied only from a verified `main` commit, applying the exact saved plan the owner reviewed (same workflow run, after environment approval);<br>- no `external`, `local-exec`, or `http` data sources;<br>- no unpinned or third-party modules;<br>- provider lock file committed with hashes;<br>- separate state per environment, so the dev deployer cannot write vault state;<br>- deploy-capable workflows never use `pull_request_target` or `workflow_run` triggers |
| A16 | **Run paths and launcher identities, named explicitly.**<br>- At Stage A, each chartered historical acquisition is a Terraform-defined VM (or Batch job, if the provider supports it; SECONDARY), with a named persistent disk, applied from `main` after owner plan review. Its startup runs the B07 pipeline. This is the run path and the audit trail.<br>- `sa-deployer-vault` is the only identity with `actAs` on vault runtime accounts.<br>- Scheduler-triggered runs are not used at Stage A. If added later, the scheduler caller becomes a named, narrowly scoped A7 exception.<br>- No human identity holds act-as on vault accounts. Release and protected evaluation come later (R2, E2) |
| A17 | **Network egress and API allowlist.** `pmv-dev` has no default network, egress deny-all, no Cloud NAT, and Private Google Access only. Private Google Access still reaches Google APIs that return outside data, so Terraform also enables only an enumerated API set in `pmv-dev`: Storage, Batch, Compute, Logging, Monitoring, Artifact Registry. BigQuery, Vertex AI and Gemini, Cloud Build, and Storage Transfer stay disabled unless separately chartered. If BigQuery is later enabled, cross-project and public-dataset reads are blocked by a technical control, not by policy text (S-B9C3-01). Vault acquisition egress is limited per source, in addition to the A-1 fetcher allowlist |
| A18 | The Gemini for Google Cloud / Cloud Assist API is never enabled in the vault, backup, ops, or dev projects |
| A19 | **Controlled release.** No data leaves the vault except through the H-2 release path. Until that path exists (§3.2), nothing is released |

### 3.2 Required before the first development release

| # | Control |
|---|---|
| R1 | The H-2 release tool is built and reviewed, following the prerequisite chain in `docs/release_tool_design.md`: E-U1 catalog, shared `source_id` catalog, P-3, and a registered cycle with `T0` and `m` |
| R2 | The release job is a controlled path:<br>- it is a Cloud Run Job or Workflow with a fixed, Terraform-deployed definition. Batch is not used for it, because a principal with job-create and act-as could submit any command (RT-B9C3-02). The owner-admin identity holds only the execute permission (`run.jobs.run` or `workflows.executions.create`), with overrides denied, and no act-as. That permission is added no earlier than R1;<br>- its inputs (`B`, `m`, catalog) come from the verified registry at a pinned commit;<br>- it releases raw rows only;<br>- it writes to a staging prefix that dev cannot read;<br>- the commit marker is written only after the holdout-log binding (R-8 write-ahead), and `dev-released` and the R3 loader admit only objects listed under a committed manifest |
| R3 | Dev loaders refuse rows that are not in a release manifest, and rows whose information time is at or after `T0 − m` |
| R4 | Object creation in `pmv-dev` is denied except for `sa-release` (staging only) and the dev stage accounts |
| R5 | Dev normalization is rebuilt from released raw rows with the same normalizer image digest as the vault |
| R6 | Features and labels use separate service accounts and prefixes. As-of joins are keyed on availability time. A canary test checks for leakage |
| R7 | Experiment records carry the release manifest hash, `cycle_id`, fold-spec hash, and image digest. Fold specs are preregistered. Hyperparameter-search budgets count failed and preempted trials |
| R8 | Data-reading vault jobs have no internet egress |
| R9 | No label tables in BigQuery |
| R10 | Owner decision D-B09-20 on the selection rule (§11) |

### 3.3 Stage B: required before `T0 − m` and protected capture

Isolation is strengthened before any protected data exists. Using `T0 − m` instead of the owner's "before `T0`" is a deliberate tightening: the Protected Information Rule embargoes the protected families from `T0 − m`.

| # | Control |
|---|---|
| B1 | **Stage B isolation decision (owner).** Preferred design, if feasible:<br>- a Google Cloud Organization (Cloud Identity Free, with a domain the owner controls);<br>- a VPC-SC perimeter around vault and backup;<br>- organization policies: key creation disabled, public access prevention, resource locations, console AI assistants disabled;<br>- separate administrator and break-glass identities, with the day-to-day identity not Owner of the vault or backup projects.<br>If an Organization is not feasible, the owner records the residual risk for the protected interval |
| B2 | Fault-injection test confirming that an owner-role principal is refused on every A7 path |
| B3 | Backup parity: `pmv-backup` has the vault's deny, logging, and perimeter controls. Restore tests go only into a vault-class scratch bucket |
| B4 | Telemetry coarsening: from `T0 − m`, capture telemetry is reduced to health states and gap flags (D-B09-19) |
| B5 | F-09 fail-closed agent web access from `T0 − m` (existing ruling E-B4-4). From `T0 − m`, every break-glass vault read is also logged in HOLDOUT_ACCESS_LOG.md, and treated as contamination if the owner could pass it into development (S-B9C3-02). The Stage B perimeter (or an equivalent control) also covers `pmv-dev`, with egress to foreign projects denied (S-B9C3-01) |
| B6 | Capture safeguards:<br>- the venue connector has been reviewed;<br>- availability time comes only from a pre-designated primary collector;<br>- clocks are monitored;<br>- dedicated-core VMs;<br>- an alert path with a dead-man heartbeat |
| B7 | Cloud F-03 successor for venue credentials: the collector build has no order code paths, the egress allowlist excludes order paths, and the capture secret is treated as `trading-private` |
| B8 | Single-provider durability decision for irreplaceable capture: a backup payment method, hardware keys and account recovery, and optionally an off-provider copy where licences allow |
| B9 | Each historical feature family's equivalent-capture start date is a power-driven input to choosing `T0` (master inventory §7a). Decided at cycle registration |

**Live capture before `T0 − m`.** Capturing development data before `T0 − m` needs all of §3.1 plus B6 to B8, but not B1 to B5. This rests on `T0` being a declared future time, fixed at cycle registration (H-1). Data captured before `T0 − m` is development data and can never become protected.

### 3.4 Required before protected evaluation

| # | Control |
|---|---|
| E1 | Stage B controls in force and verified |
| E2 | Protected-evaluation job:<br>- its own service account;<br>- frozen image digests from Gate 6;<br>- reads only `[T0 − max_lookback, E + Δ_label]` and the frozen candidate;<br>- writes only to `vault-eval-results`;<br>- a Cloud Run Job or Workflow with a fixed definition; the owner-admin identity holds only the execute permission, with no act-as and no overrides, and each invocation is logged |
| E3 | Gate 6 re-normalization of the protected interval with the frozen candidate's normalizer digest, plus a parity hash check on the overlap rows before the boundary. All candidate training data is under that digest; data under older digests is re-derived or excluded |
| E4 | Results reach agents only through a logged owner release (START_HERE.md Phase 7; HOLDOUT_ACCESS_LOG.md) |
| E5 | Frozen candidates are stored outside any project a kill switch can disable, under event-based holds |

### 3.5 Required before live trading

| # | Control |
|---|---|
| L1 | A separate `pmv-runtime` project. Venue trading credentials exist only in its Secret Manager |
| L2 | Each runtime deployment needs explicit owner approval and goes through a `main`-only protected environment |
| L3 | Training-serving parity: one feature library, replay parity tests, and CPU-serving acceptance |
| L4 | L-PROD licence re-check for every input `licence_id` |
| L5 | All START_HERE.md Phase 8–12 requirements, unchanged |

## 4. Architecture diagram

```
                         ┌───────────── pmv-ops ─────────────┐
                         │ Terraform state · Artifact Registry │
                         │ restricted log bucket · budgets      │
                         └─────────────────────────────────────┘
 external sources ─► ┌──────────────────── pmv-vault ─────────────────────────────┐
                     │ Historical: Batch/VM with cloud-side persistent disk runs    │
                     │   the B07 pipeline unchanged → sealed files                  │
                     │ Prospective: capture VM runs venue connector + B08 store     │
                     │   → sealed segments                                          │
                     │     │ sealed-object uploader (create-only, CRC32C, read-back)│
                     │     ▼                                                        │
                     │ gs://<p>-vault-raw (immutable raw · manifests · journals)    │
                     │     ├─ vault normalizer (operational only)                   │
                     │     ├─ H-2 release job (owner-admin; raw rows; staging) ─────┼─► pmv-dev
                     │     └─ protected-eval job (Gate 6) → vault-eval-results      │
                     └──────────────────────────────────────────────────────────────┘
                     ┌──────────────────── pmv-dev ─────────────────────────────────┐
                     │ dev-released · dev-normalized · dev-features · dev-labels     │
                     │ dev-artifacts · Batch (CPU/GPU, Spot) · optional BigQuery     │
                     │ no internet egress                                            │
                     └───────────────────────────────────────────────────────────────┘
                     pmv-backup (second region; added with the A-3 policy; parity at Stage B)
                     pmv-runtime (Phase 11+)

 Chromebook: git and Claude Code only; no reusable cloud or GitHub credential in
 Claude's shells; owner cloud work in Cloud Shell or a separate browser profile.
```

Naming rules:
- `<p>` is a globally unique prefix chosen at CLOUD-1.
- No bucket, object, metric, or log name encodes a ticker, strike, or scope-revealing date (`docs/protected_information.md` prerequisite 4).
- Feed IDs in object paths are opaque.

## 5. Storage

### 5.1 Buckets and projects

| Bucket | Project | Holds |
|---|---|---|
| `vault-raw` | vault | Every unreleased real observation: acquisitions, capture segments, manifests, journals, quarantine. There is no separate landing bucket: B07/B08 do quarantine and A-4 checks on disk before upload |
| `vault-ops` | vault | Operational normalized output of the vault normalizer. It stays in the vault and is never an evaluation or release input. Any QA from it follows A10 and B4 |
| `vault-eval-results` | vault | Protected-evaluation outputs (Stage B onward) |
| `dev-released` | dev | Released raw rows and release manifests |
| `dev-normalized`, `dev-features`, `dev-labels`, `dev-artifacts` | dev | Derivatives of released rows; models, calibrators, run manifests |
| scratch | dev | Fold copies and temporary outputs. Soft delete 0, no versioning, lifecycle deletion |
| Terraform state | ops | Versioned. Not readable by pull-request identities |
| `backup-vault-raw` | backup | Coldline copy of vault raw, in a second region |

- **Region:** one home region, not multi-region.
- **Storage class:** Standard for active data. Coldline only for the backup copy.
- **Bucket split:** buckets are split by security boundary and lifecycle, not by source. The source is a path segment.

### 5.2 Raw layout and the B07/B08 sealed-object path

```
gs://<p>-vault-raw/
  acquisitions/v1/<source_id>/<acquisition_id>/<file> and acquisition.json
  journals/v1/<writer_id>/<seq>-<sha256>.jsonl ; journals/v1/checkpoints/...
  captures/v3/<source_id>/<feed_id>/<yyyy>/<mm>/<dd>/<session_id>/<segment_seq>.pmvseg
  quarantine/<id>/...
```

- **Filesystem stores unchanged.** The B07 acquisition store and the B08 segmented capture store keep their filesystem semantics on a cloud-side persistent disk: no-replace renames, directory fsync, `O_TMPFILE` linking, `flock`, modes, and device and owner checks. GCS FUSE is not used.
- **Upload path.** After a file or segment is final and recorded in its manifest:
  1. The uploader verifies the local file's SHA-256 against the manifest.
  2. It writes the file create-only to `vault-raw`, with CRC32C.
  3. An ambiguous result (timeout, then a 412) is resolved by read-back of the uploader's own prefix. GCS stores no SHA-256, so read-back means downloading and hashing the object.
     - On a match, the upload is verified.
     - On a mismatch, the local copy is kept and uploaded under `quarantine/`, because create-only cannot replace the taken name, and an alert is raised.
  4. After verification, a defined retirement step removes the local copy in a way the store's own integrity checks accept.

  A maximum segment age bounds the data at risk if a zonal disk is lost. Acquisitions that need B07 resume semantics use a VM with a named persistent disk, not Spot, because Batch-created disks may be deleted when a job ends (SECONDARY).
- **Journals.** One hash chain per writer. A single sealer (`sa-journal-sealer`) merges the chains into checkpoints. Parallel tasks never assign sequence numbers in a shared chain.
- **Path date.** The date in an object path is the UTC date the segment opened.
- **Retention.** Versioning on raw, artifacts, and state. Soft delete at its default on raw. An unlocked retention policy, whose duration is an owner input under A-3. No Bucket Lock: it is irreversible and would conflict with licence deletion duties. Event-based holds on Gate 6 inputs.

### 5.3 Formats and BigQuery

| Layer | Format |
|---|---|
| Raw | Source-native bytes, unchanged, plus frame format v3 segments. Never forced into Parquet. The Chromebook transforms nothing |
| Normalized | Content-addressed Parquet (zstd) plus manifests, partitioned by UTC date. One dataset per `(source_id, schema_version, normalizer digest)`. Prices and sizes as DECIMAL or scaled integers. Manifests list raw paths, generations, SHA-256s, the normalizer digest, and the commit |
| Features and labels | Parquet, stored once and partitioned by date, in separate prefixes written by separate service accounts. Shared tables hold no fitted transforms |
| Training input | Fold manifests, not fold copies. A manifest lists partition paths and hashes, boundaries, purge and embargo widths, the label-availability rule, and the constraint `V ≥ T + max_lookback + max contract life`. It is hashed and registered before results. One tested loader. Partitions are copied to local SSD and memory-mapped as Arrow |
| Artifacts | Safe formats only: LightGBM text or JSON, ONNX or safetensors, JSON or npz calibrators. Never pickle. Manifests carry the SHA-256, feature schema version, run ID, and image digest |

**BigQuery is optional and non-canonical.**
- At the start, DuckDB or Polars inside jobs cover QA and exploration.
- Possible later uses: metadata, bounded QA, selective development queries, and catalog or index analysis. Each query is capped with `maximum_bytes_billed`, with custom daily quotas as the real cap.
- Never used for vault or protected data or for label tables. Dev identities never query public datasets of protected equivalents.

## 6. Vault isolation and the information embargo

**Why projects.**
- A development job's metrics, logs, and weights reach agents. Under R-13 they are derived artifacts whose information time is the latest of their inputs. A development job that reads unreleased data therefore counts as exposure.
- Project-level roles silently cover any bucket in the same project, so separating buckets within one project is not fail-closed.
- Protected data is simply vault data cut by information time. It needs no separate "holdout bucket" beside development data.

**The cut is by information time, not by object date.**
- A row's information time is its latest catalogued time field, plus interval ends and `max_clock_error` (R-3).
- As-of fields and record versions are cut by `known_at` (R-7).
- Contracts are eligible under Policy 2 (R-6).
- `[T0 − m, T0)` is embargoed but never protected-eligible.
- Historical data fetched after `T0 − m` carries current-state metadata and is cut field by field.
- Object prefixes are coarse defense in depth only.

**Credential separation (D-B09-11).**
- No cloud credential (gcloud, application-default credentials, Terraform, Docker helpers) may exist in any OS user or shell where Claude Code runs. The only GitHub credential there is the single-repository deploy key described in A4.
- Owner cloud work happens in Cloud Shell or a separate browser profile. Claude Code is never run inside Cloud Shell.
- As defense in depth, the owner applies `.claude/settings.json` denies for `~/.config/gcloud`, application-default credential paths, `~/.config/gh`, `~/.docker/config.json`, and `~/.terraform.d`. No `GOOGLE_APPLICATION_CREDENTIALS` or `CLOUDSDK_*` variables are inherited.
- A denylist is never complete, so the rule above is the primary control.

**Who can do what.**

| Actor | Vault data | Dev data |
|---|---|---|
| Agents | Never | Value-safe outputs of submitted jobs, once H-2 release exists |
| Development jobs | Never | By stage |
| Vault service accounts (acquire, capture, sealer, normalize, release, protected eval, backup copy) | Prefix-scoped | Release job writes the staging prefix only |
| Owner, day-to-day | No data role (deny). At Stage B, also not project Owner | Yes |
| Owner, break-glass | Audited grant. Pre-cycle reads recorded in the exposure register | Yes |

## 7. Ingestion and capture

**Historical acquisition.**
- Batch or a Compute Engine VM runs the B07 pipeline unchanged on a persistent disk: quarantine, hash on receipt, the isolated seccomp parse worker, promotion, then the uploader.
- Cloud Run Jobs handle only small, bounded paginated pulls that fit their memory-backed disk, and only after the parse worker's confinement self-test passes in that sandbox.
- Storage Transfer Service handles S3-delivered vendors. It needs an AWS-side credential; its agent requirements are unverified.

**Rate limits are per egress IP.**
- Each source gets one global limiter, set below its documented limit.
- A 429 response is surfaced as a signal, not just retried.
- Static NAT addresses are recorded.

**Reachability is documented, not tested.**
- A chartered connectivity check per source, from the approved egress address and with no data retained, precedes A-1.
- No region or egress path is ever chosen to get around a venue's geographic or eligibility restriction.
- Host-level egress rules are defense in depth. The fetcher's allowlist remains the A-1 control.

**Kalshi.**
- Record `/historical/cutoff` before and after each acquisition, and fail closed if it moved.
- Accept and log both cursor terminal values.
- Reconcile historical and live tiers on ticker plus trade ID.
- Gold labels need live-tier access under their own charter.

**Prospective capture.**
- Runs on dedicated-core Compute Engine VMs, on demand, never Spot.
- A venue connector must be built and reviewed first. It covers:
  - market discovery: a new 15-minute contract opens every 15 minutes;
  - snapshot plus delta, with re-snapshot on any gap;
  - heartbeats and reconnect;
  - maintenance windows;
  - a method allowlist with no order paths;
  - REST cross-checks.
- Chrony offset is recorded per segment.
- Two collectors run in two zones. Availability time comes only from a primary designated in advance; secondary data is flagged as gap fill. Per-key connection limits are verified before two collectors share one key.
- Capture VMs have an egress allowlist.
- Raw bytes go to GCS through the uploader, not through Pub/Sub.

## 8. Training: GCP Batch

**GCP Batch is the initial PMV training backend, for CPU and GPU.**
- One container image per commit, built from `uv.lock`, with CPU and GPU variants from the same lock.
- One deterministic training entry point.
- Spot VMs, a pinned machine type and minimum CPU platform, local SSD, and jobs that end themselves.

**Vertex AI is deferred, not rejected.** It is added only if PMV demonstrates a concrete need for one of:
- managed HPO;
- experiment or model-registry features beyond PMV's ledger;
- easier distributed training;
- a GPU capability Batch cannot economically provide.

Batch and Vertex are not both built.

**Order of work.** Logistic and statistical baselines first, then gradient boosting. Sequence models only if the baselines leave measurable, calibrated, after-cost room.

**GPUs.**
- Only where a CPU epoch takes more than about 10–15 minutes, after a CPU benchmark of a small TCN or GRU.
- One L4 or T4 first.
- The free trial allows no GPUs, and new projects start at 0 GPU quota (S).

**Checkpoints.** A checkpoint holds the model, optimizer, RNG, and loader position. A preempted trial resumes from its checkpoint and is never re-drawn. Preemptions are recorded.

**Hyperparameter search.**
- A preregistered (configuration × fold) budget that counts failed and preempted trials.
- The full search history is recorded.
- Tuning is nested inside the training window.
- Selection follows `docs/phase2.md` and D-B09-20.
- Deflation by block bootstrap of the whole selection procedure (Policy 8).

**Reproducibility.**
- Base image pinned by digest. Thread count fixed. Machine type and CPU platform recorded.
- Deterministic GBM and torch settings.
- A bit-for-bit CPU reproduction test in CI on synthetic data. GPU run-to-run spread is measured.
- The ML and data dependency stack is added as a reviewed, hash-locked step before the first training stage.

**Ledger.** Parallel tasks write immutable run manifests. A single ingest stage appends them to the authoritative ledger in a fixed order.

**Calibration.** Calibrators are fitted on a later time slice inside the training window, never in-sample.

**Normalizer parity.** The frozen candidate's normalizer digest serves its development data and the Gate 6 re-normalization (E3).

## 9. Orchestration

- A minimal deterministic pipeline runner: ordered stages with input and output manifests. A stage is skipped when its output hashes match. The runner works the same on synthetic data locally and as a cloud job.
- Cloud Scheduler triggers jobs directly. Workflows is used only where a concrete cross-service retry need exists.
- No Composer and no Vertex Pipelines.
- No step involves an LLM.

## 10. IAM, CI/CD, and secrets

There is no administrator service account.

| Account | Project | Can | Cannot |
|---|---|---|---|
| `sa-acq-hist` | vault | Create under `acquisitions/` and its own journal; read back its own objects; read its source secrets | Read others' objects; delete; update; reach dev |
| `sa-capture` | vault | Create under `captures/` and its own journal; read back its own objects; read its venue data secret once approved; write value-free metrics | Call order endpoints (blocked in code and egress); reach dev |
| `sa-journal-sealer` | vault | Read journal segments; create checkpoint objects | Read data objects; delete; reach dev |
| `sa-vault-normalize` | vault | Read raw; write `vault-ops` | Write dev |
| `sa-release` | vault → dev | Read raw and the catalog; write the `dev-released` staging prefix; append the release ledger. Runs as a fixed Cloud Run Job or Workflow | Run except on owner-admin execution (from R1); overrides |
| `sa-protected-eval` | vault | Read the bounded protected window and the frozen candidate; write `vault-eval-results`. Runs as a fixed Cloud Run Job or Workflow | Write dev; run except on owner-admin execution (from E1) |
| `sa-backup-copy` | vault → backup | Read raw; create in backup | Delete |
| `sa-dev-normalize`, `sa-dev-features`, `sa-dev-labels` | dev | One stage each | Reach vault. The features account cannot read labels |
| `sa-dev-train`, `sa-dev-eval` | dev | Read through the fold loader; write artifacts and reports; use GPUs within quota | Reach vault; read secrets; query public datasets |
| `sa-dev-submit` (optional, D-B09-15) | dev | Submit Batch jobs as `sa-dev-train` from any-branch images, within quotas | Anything outside dev |
| `sa-deployer-dev`, `sa-deployer-vault` | ops | Terraform apply for one environment from `main`, after owner plan review. `sa-deployer-vault` holds `actAs` on vault runtime accounts only to define their jobs and VMs (A16) | Read data; run release or evaluation jobs |

**Terraform.**
- Manages: projects (after the owner creates billing), APIs, buckets and their policies, service accounts, IAM and deny policies, Artifact Registry with cleanup policies, Secret Manager containers (never values), Batch templates, Scheduler, VMs, networks, log routing, audit configuration, and budgets.
- Owner-manual: billing, payment, provider terms, and secret values (entered through stdin, never left in shell history). At Stage B, also the Organization and identity setup.
- Apply rules are in A15. `infra/` is created only when CLOUD-1 is chartered. Changes to `infra/` and `.github/` get Red-Team review.

**GitHub Actions with Workload Identity Federation.**
- No keys. The attribute condition pins repository, repository ID, owner ID, `refs/heads/main`, and the environment. Optionally it also pins `job_workflow_ref`.
- Agents can push branches that contain workflow files. Therefore:
  - deploy environments have deployment-branch policies restricted to `main`, with the owner as required reviewer;
  - `terraform plan` runs only on `main`, or with an identity that cannot read state or vault resources;
  - pull-request runs never receive a deploy-capable identity.
- "Protect Main" requires a pull request and the Quality gate check, but no approving review is recorded. Adding one is an owner ruleset decision.

**Artifact identity.** Images are tagged with the commit SHA and referenced by digest. Every job records its digest and commit in its output manifest.

**Secret Manager.**
- One secret per credential, in the project of the account that uses it, with per-secret grants.
- Read at job start, rotated through versioning, with access logged.
- Never entered through an agent session.
- The cloud F-03 successor (B7) governs venue credentials.

## 11. Historical and prospective data

**Historical data is development data.**
- Data legitimately acquired (A-1 to A-8) and formally released as development data (H-2) may be used for model development, model selection, features, calibration research, and walk-forward testing.
- Prospective formation (H-1) makes all admissible data before `T0 − m` development data, historical and captured alike.
- **Once exposed as development data, it is permanently ineligible for use as protected holdout** (CLAUDE.md "Holdout Protection").

**Prospective capture begins early.** It supplies:
- receipt-time truth;
- execution-realistic observations with live books;
- future protected-holdout material;
- additional statistical power.

It **does not invalidate the historical-development path.**

**One interpretation for the owner (D-B09-20), decided before the first development release.**
- The Phase 2 working-design rule S-9 in `docs/phase2.md` is not owner-adopted. It computes "any validation result used for selection" on receipt-time (`RECEIPT` + `PIT_CAPTURED`) folds, and specifically "the comparison that selects ... for the audit candidate". It treats archive-validated folds as "discovery only".
- The owner's words were "development/model selection":
  - read as development-stage selection (exploration, pilot choice, narrowing candidates, all logged), they fit within S-9;
  - read as also covering the final audit-candidate comparison, they depart from it.
- The options:
  - **(a) keep S-9:** archive results screen and narrow candidates as logged hypotheses; receipt-time folds decide the audit candidate. The cost is calendar time: enough pre-`T0` capture is needed for a powered receipt-time comparison;
  - **(b) amend S-9:** archive-validated folds may decide the audit candidate;
  - **(c) middle option:** archive selection only when receipt folds are underpowered, with a preregistered receipt-time non-inferiority check and a stated overlap-window artifact bound.
- The development Statistician, who wrote S-9, recommends (a). The Independent Statistical Auditor reviews the rule at Gate 2 (H-6).
- Under every option, historical data is used for development from the first release onward, and released rows carry `availability_class` and `metadata_pit_class`.

## 12. Regions and Chromebook workflow

- **Home region:** `us-central1` for vault, dev, and training (S): broad GPU availability, all needed services, low prices.
- **Capture region:** `us-east5` (Columbus), near Kalshi's reported AWS us-east-2. `us-east4` instead if Polymarket US becomes relevant. Uploads to the home region cost about $0.02/GB (S).
- **Runtime region:** decided at Phase 11 from measured latency.
- **Backup region:** a second US region.
- Service availability in each region is re-verified at CLOUD-0.

| Task | How | Never |
|---|---|---|
| Edit code | Claude Code; commit and push task branches with the repository deploy key | Datasets on disk; cloud credentials or broader GitHub credentials in Claude's shells |
| Submit jobs | CI on `main`, Cloud Shell, or the optional dev-experiment tier | Agents running jobs with owner credentials |
| Logs and metrics | Console or Cloud Shell; value-free logs | Raw payload downloads |
| Experiments | Jobs run to completion without the laptop | Keeping the Chromebook awake |
| Infrastructure | Terraform from a verified `main` commit after plan review | Undocumented click-ops |

## 13. Cost reference

Details are in `research/cloud/pmv_cloud_cost_model.md`. All prices are SECONDARY.

| Scenario | Content | Rough monthly cost |
|---|---|---|
| Bootstrap | 100 GB raw, historical only, CPU baselines | about $10–20 |
| Working project | 1 TB, one Kalshi collector pair, CPU training most days, a few GPU runs | about $180 |
| Full development | 5 TB, two collector pairs, regular GPU runs | about $600–700 |

- Recommended starting budget: about $100 per month for CLOUD-1 to CLOUD-3.
- **Data purchases and owner time cost far more than the cloud itself.**
- Budgets do not cap spend. Quotas are the hard limiters, and the dev-only kill switch is scoped by IAM.

## 14. Facts not verified in this review

- Every SECONDARY cloud fact: deny-policy permission names and coverage, service-agent exceptions, VPC-SC prerequisites, Batch and Cloud Run behavior, GPU availability, soft-delete defaults, and lifecycle conditions.
- For each source: licence permission for third-party cloud storage (A-2), and reachability from cloud IPs.
- Venue hosting regions, key scopes, and connection limits.

## 15. Implementation roadmap

| Stage | Content | Controls delivered or required (§3) | Rough effort |
|---|---|---|---|
| CLOUD-0 | Owner steps: billing account upgraded, budget, regions confirmed, administration only from Cloud Shell or a separate browser profile, credential rule adopted | Prerequisites for A2, A4, A13 | Days |
| CLOUD-1 (first implementation batch) | Terraform for `pmv-ops`, `pmv-vault`, `pmv-dev`:<br>- buckets (A8, A11);<br>- service accounts (A3);<br>- deny policy (A5, A7) and launcher identities (A16);<br>- audit logs and the restricted log bucket (A10);<br>- network egress (A17) and the AI-assistant API kept off (A18);<br>- Artifact Registry and Secret Manager containers;<br>- budgets (A13);<br>- WIF with `main`-only environments.<br>Red-Team review of the IAM model before any data | Delivers A2–A8, A10, A11, A13, A15–A18. A1 is an owner decision. A9, A12, A14, and A19 come in CLOUD-2/3. The CLOUD-1 Red-Team IAM review confirms the run path (A16), the deny exceptions per category (A7), and the default-service-account handling | 1–2 weeks |
| CLOUD-2 | Sealed-object uploader; per-writer journals and sealer; the B07 pipeline on Batch/VM; a per-source rate limiter; the A-3 cloud backup with a synthetic restore test. Synthetic data only. Red-Team review | A9; the backup part of A14 | 2–3 weeks |
| CLOUD-3 | First cloud-to-cloud historical acquisition, for whichever source's licence clears first (master inventory §7) | All of §3.1, plus A-1 to A-6 for that source | About 1 week |
| CLOUD-4 | Venue connector and capture VM image (synthetic and fixture tests), then live capture of licensed feeds | §3.1 plus B6 to B8 | 2–3 weeks, plus licence and credential decisions |
| CLOUD-5 | H-2 release job; first released development rows | §3.2 | Gated by H-2 and cycle registration |
| CLOUD-6 | Feature library, fold loader, Batch template, ledger ingest, baselines. Built on synthetic data in parallel from CLOUD-1; run on released data after CLOUD-5 | R5 to R7 | 2–4 weeks |
| CLOUD-7 | GPU training on Batch Spot, only if baselines justify it | — | — |
| Stage B | Organization (if feasible), VPC-SC, organization policies, administrator separation, backup parity, telemetry coarsening | §3.3 B1 to B5 and B9 | Before `T0 − m` |
| CLOUD-8 | Protected-evaluation path | §3.4 | Gate 6 path |
| CLOUD-9 | `pmv-runtime`: shadow, then live | §3.5 | Phase 11–12 |

The first real experiment is realistically about 3–4 months away. The governance track (licences, H-2, cycle registration) sets the date. The proposed kill and spend gates K1–K4 (D-B09-18) decide whether paid data and the later stages happen at all.
