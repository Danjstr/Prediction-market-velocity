# PMV cloud-native architecture: canonical design (B09, 2026-10-18)

**Status.**
- This document is research and recommendation. It is not an approved requirement, not a gate record, and not a provisioning plan to execute.
- It authorizes no cloud resource, account, credential, or data acquisition. Adopting any part of it is the owner's decision (§13).
- It describes the current design only. Review findings, their dispositions, and the proposals this design superseded are in `research/governance/b09_cloud_architecture_reviews.md`.

**Related records:**
- `docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md` (direction and decisions);
- `research/cloud/pmv_cloud_cost_model.md` (costs);
- `research/data_sources/master_source_inventory.md` (sources).

**Evidence limits.**
- The container's fixed network allowlist refuses the official cloud documentation hosts.
- Every cloud product fact, limit, and price here is therefore SECONDARY: web-search summaries, official projects' GitHub pages, or reviewer recollection.
- Each such fact is re-verified before the stage that relies on it (§14).

## 1. Verdict and provider recommendation

**Advisory verdict: GCP ARCHITECTURE APPROVED WITH CHANGES.** This is an agent recommendation in the form the owner requested. Approval is the owner's (D-B09-14).

**Provider: KEEP GCP.** No factor makes AWS or Azure materially better for PMV. Revisit only if measured runtime latency shows millisecond placement matters, or if a key vendor's S3-only delivery makes egress dominate.

| Factor | GCP | AWS | Azure | Effect on PMV |
|---|---|---|---|---|
| Object storage, single region | about $0.020/GB-month (S) | about $0.023 (S) | about $0.018–0.021 (S) | Immaterial at 0.1–5 TB |
| Internet egress | about $0.12/GB (S) | about $0.09/GB (S) | about $0.087/GB (S) | Immaterial; data stays in the cloud |
| Batch compute | Batch: no service fee, Spot, fixed machine types, GPUs (S) | AWS Batch | Azure Batch | Comparable; GCP is simplest for one person |
| GPUs | T4, L4, A100 in US regions. New projects start at 0 quota; no GPUs on the free trial (S) | Broadest fleet | Narrower | One L4 suffices |
| Operating from a Chromebook | Cloud Shell, a browser terminal with gcloud and Terraform (S) | CloudShell | Cloud Shell | GCP has the least friction |
| Isolation primitives | Projects and IAM deny without an Organization. VPC-SC and organization policies need one (S) | Accounts plus SCPs | Subscriptions | Sufficient for PMV's accident-focused threat model (`docs/protected_information.md` F-05) under the staged model (§2) |
| Venue proximity | `us-east5` is near AWS us-east-2, where Kalshi is reported to run (S) | Same metro | — | A minutes-scale strategy does not need sub-millisecond placement |
| Lock-in | BigQuery and Vertex are proprietary, but optional here | Similar | Similar | Parquet, containers, Terraform, and PMV's ledger keep the design portable |

**Design summary.**

| Element | Design |
|---|---|
| Projects | `pmv-ops`, `pmv-vault`, `pmv-dev`; `pmv-backup` at Stage B (the Stage A backup bucket sits inside `pmv-vault`, in a second region); `pmv-runtime` only at Phase 11 |
| Canonical raw storage | GCS (`vault-raw`) |
| Normalized and feature data | Content-addressed Parquet plus manifests in GCS |
| BigQuery | Optional, non-canonical |
| Historical acquisition | The B07 pipeline on cloud compute with a persistent disk; finished files sealed and uploaded create-only (§6) |
| Prospective capture | Dedicated cloud VMs that keep B08 semantics (§7) |
| Training | GCP Batch (§8) |
| Orchestration | Deterministic Python (§9) |
| IaC and CI/CD | Terraform; GitHub Actions with Workload Identity Federation; `main`-only, owner-reviewed deployment (§10) |
| Chromebook | Git and Claude Code only. No bulk dataset. No reusable GCP credential available to Claude Code, and no GitHub credential beyond the repository deploy key (A4) |

## 2. Security controls by timing boundary

A control is required **no earlier than** its boundary. Nothing required at a later boundary blocks legitimate work at an earlier one.

### 2.1 Before first historical byte — Stage A

**A Google Cloud Organization is NOT required at Stage A.**

**Residual risk.** A sufficiently privileged Google project administrator can technically override some controls, for example by removing a deny policy or granting themselves access.
- The owner explicitly accepts this residual administrative risk for pre-`T0` historical development acquisition, provided the controls below are in place (owner direction, 2026-10-18; D-B09-12).
- The controls are fail-closed against accidental grants and ordinary mistakes, which is PMV's adopted threat model (F-05).

**Governance basis.** No binding PMV rule requires an Organization at this stage. The approved controls are:
- F-01: raw data stays outside agent-readable storage;
- A-7: protected storage is written outside agent sessions;
- A-8: release is separate.

Stage A meets all three in cloud form once D-B09-10 adopts the vault as the successor location.

| # | Control |
|---|---|
| A1 | Owner decision D-B09-10: `pmv-vault` becomes the cloud successor to the local protected raw store (F-01), with matching edits to `docs/raw_data.md`, `docs/protected_information.md`, `docs/phase2.md`, and A-7 |
| A2 | Separate `pmv-vault` and `pmv-dev` projects, plus `pmv-ops` (Terraform state, Artifact Registry, restricted logs). Billing account upgraded beyond the free trial |
| A3 | Per-stage service accounts with least privilege (§10). Writers can create objects and read back their own prefix, nothing more |
| A4 | **Credential isolation.** No cloud credential in any OS user or shell where Claude Code runs. The only GitHub credential there is the existing single-repository deploy key, which cannot administer the repository, bypass "Protect Main", approve environments, edit secrets, or create tokens. Owner cloud work happens only in Cloud Shell or a separate browser profile. Claude Code is never run inside Cloud Shell, which holds the owner's full credential (D-B09-11) |
| A5 | **No service-account keys.** Key creation is denied to every principal through A7, with no exceptions |
| A6 | The owner's day-to-day identity has no vault data role and no act-as on vault accounts. Stage A break-glass is a logged owner edit of the deny policy, reverted afterwards. Pre-cycle break-glass reads are recorded in `docs/exposure_register.md` Part A |
| A7 | **IAM deny policy on `pmv-vault`**, scoped per bucket through resource tags (RT-B9C-01). It denies:<br>(a) data reads;<br>(b) act-as and mutation paths: impersonation, signing, HMAC keys, job mutation, run overrides, and VM mutation (instance metadata and startup scripts, `setServiceAccount`, instance and template updates);<br>(c) disk paths to raw data: OS Login and SSH, serial port, snapshot and image creation, disk attach;<br>(d) service-account key creation;<br>(e) changes to bucket policy, retention, versioning, IAM, tag bindings, and the deny policy itself;<br>(f) object delete on vault buckets.<br>Exceptions, per category:<br>- (a): the named service accounts, for their own data paths;<br>- (b) and (e): `sa-deployer-vault` only, as Terraform needs;<br>- (f): no principal except break-glass;<br>- break-glass in all categories, as in A6.<br>Configuration covers what IAM deny cannot express: no external IPs; no SSH ingress rule; project SSH keys blocked; no OS Login admin or IAP grants; serial port off; the default Compute service account's Editor grant removed, with a service account set explicitly on every VM and job |
| A8 | `vault-raw`: create-only writes (`ifGenerationMatch=0`), object versioning, default soft delete, no age-based deletion, no Bucket Lock |
| A9 | Sealed-object uploader (§6.2) |
| A10 | Data Access audit logs on vault Storage. Vault logs go to a restricted log bucket in `pmv-ops` and are excluded from the vault `_Default` bucket. A closed, value-free log schema (counts, durations, hashes, enumerations without outcome, side, strike, or per-market labels) |
| A11 | Public access prevention and uniform bucket-level access on every bucket |
| A12 | Historical acquisition, including any extraction from BigQuery public datasets of protected equivalents, runs only as a vault service account |
| A13 | Budget alerts; GPU quota at 0 or 1; BigQuery quotas if it is ever enabled |
| A14 | The source's own gate, A-1 to A-6: licence determination (A-2) and a cloud A-3 backup policy with a synthetic restore test (D-B09-13). At Stage A the backup bucket (`vault-backup`) lives inside `pmv-vault`, in a second region, under the A7 deny, and restore tests target a vault-class scratch bucket under the same deny (RT-B9C4-01). Licence retention and deletion duties are a source-selection criterion |
| A15 | **Terraform discipline** (RT-B9C2-04, RT-B9C3-08):<br>- **bootstrap:** a one-time owner apply from Cloud Shell creates the projects, the WIF pool, the deployer accounts, and the deny policy. After that, vault applies run only as `sa-deployer-vault`, through CI with environment approval, or by logged owner impersonation of the deployer from Cloud Shell. If impersonation is used, the owner's token-creator grant on `sa-deployer-vault` is the named transitive act-as path, under the accepted Stage A residual risk (RT-B9C4-02);<br>- applied from a verified `main` commit, using the exact saved plan the owner reviewed, in the same workflow run after environment approval;<br>- no `external`, `local-exec`, or `http` data sources;<br>- no unpinned or third-party modules;<br>- provider lock file with hashes;<br>- separate state per environment;<br>- no `pull_request_target` or `workflow_run` triggers in deploy-capable workflows;<br>- third-party GitHub Actions in deploy-capable workflows pinned by commit SHA |
| A16 | **Run path** (RT-B9C3-01):<br>- each chartered historical acquisition is a Terraform-defined VM, or a Batch job if the provider supports it (S), with a named persistent disk, applied from `main` after owner plan review;<br>- `sa-deployer-vault` is the only identity with act-as on vault runtime accounts;<br>- no human identity holds act-as on vault accounts;<br>- no scheduler-triggered vault runs at Stage A. If a scheduler is added later, its caller becomes a named, narrow A7 exception |
| A17 | **Dev isolation from outside data** (RT-B9C2-02, S-B9C3-01):<br>- `pmv-dev` has no default network, egress deny-all, no Cloud NAT, and Private Google Access only;<br>- Terraform enables only an enumerated API set: Storage, Batch, Compute, Logging, Monitoring, Artifact Registry. BigQuery, Vertex AI/Gemini, Cloud Build, and Storage Transfer stay disabled unless chartered;<br>- residual gap: with Storage enabled, Private Google Access can still read public GCS buckets. Only a VPC-SC perimeter closes this, so it is covered by B1, or by B1's no-Organization residual-risk record (RT-B9C4-06);<br>- vault acquisition egress is limited per source, on top of the A-1 fetcher allowlist |
| A18 | The Gemini for Google Cloud / Cloud Assist API is never enabled in any PMV project |
| A19 | **Controlled release.** No data leaves the vault except through the H-2 release path (§2.2). Until that path exists, nothing is released |

### 2.2 Before first development release

| # | Control |
|---|---|
| R1 | H-2 release tool built and reviewed, per the prerequisite chain in `docs/release_tool_design.md`: E-U1, the shared `source_id` catalog, P-3, and a cycle registered with `T0` and `m` |
| R2 | **The release job** (RT-B9C3-02, S-B9C-02):<br>- a fixed, Terraform-deployed Cloud Run Job or Workflow. It is not a Batch job, because job-create plus act-as would allow any command;<br>- the owner-admin identity holds only `run.jobs.run` or `workflows.executions.create`. Overrides (`run.jobs.runWithOverrides`) are denied, and there is no act-as. The permission is added no earlier than R1;<br>- the job verifies each raw object's SHA-256 against its manifest and refuses mismatches;<br>- inputs (`B`, `m`, catalog) come from the verified registry at a pinned commit;<br>- it releases raw rows only;<br>- it writes to a staging prefix that dev cannot read;<br>- the commit marker is written after the holdout-log binding (R-8 write-ahead);<br>- dev admits only objects listed under a committed manifest |
| R3 | Dev loaders refuse any row that is absent from a release manifest, or whose information time is at or after `T0 − m` |
| R4 | Object creation in `pmv-dev` is denied except to `sa-release` (staging prefix) and the dev stage accounts |
| R5 | Dev normalization is rebuilt from released raw rows, with the same normalizer image digest as the vault |
| R6 | Separate service accounts and prefixes for features and labels. As-of joins keyed on availability time. A canary leakage test |
| R7 | Experiment records carry the release manifest hash, `cycle_id`, fold-spec hash, and image digest. Fold specs are preregistered. Search budgets count failed and preempted trials |
| R8 | Data-reading vault jobs have no internet egress |
| R9 | No label tables in BigQuery. If BigQuery is enabled, cross-project and public-dataset reads are blocked by a technical control |
| R10 | Owner decision D-B09-20 on the selection rule (§5.3) |

### 2.3 Before T0-m / protected capture — Stage B

Stage B uses `T0 − m` rather than `T0` on purpose. The Protected Information Rule embargoes the protected families from `T0 − m`, so the stricter boundary applies.

| # | Control |
|---|---|
| B1 | **Stage B isolation decision (owner).** Preferred design, if feasible:<br>- a Google Cloud Organization (Cloud Identity Free with an owner domain);<br>- a VPC-SC perimeter around vault, backup, and dev, with egress to foreign projects denied;<br>- organization policies: key creation disabled, public access prevention, resource locations, console AI assistants disabled;<br>- separate administrator and break-glass identities, with the day-to-day identity not Owner of vault or backup.<br>If an Organization is not feasible, the owner records the residual risk for the protected interval, explicitly including dev's reach to public GCS buckets (A17) |
| B2 | Fault-injection test: an owner-role principal is refused on every A7 path |
| B3 | Backup project. If the backup moves from `vault-backup` to a separate `pmv-backup` project, that project carries the vault's deny, logging, and perimeter controls. Restore tests go only into a vault-class scratch bucket |
| B4 | Telemetry visible to agents or the owner is reduced to health states and gap flags (D-B09-19) |
| B5 | F-09 fail-closed agent web access (ruling E-B4-4). Every break-glass read is logged in HOLDOUT_ACCESS_LOG.md, and treated as contamination if it could reach development |
| B6 | **Capture safeguards:**<br>- the venue connector has been reviewed;<br>- availability time comes only from a pre-designated primary collector;<br>- clock monitoring;<br>- dedicated-core VMs;<br>- an alert path with a dead-man heartbeat |
| B7 | **Cloud F-03 successor for venue credentials:**<br>- the collector has no order code paths;<br>- the egress allowlist excludes order paths;<br>- the capture secret is treated as `trading-private` |
| B8 | Single-provider durability for irreplaceable capture: a backup payment method, hardware keys and account recovery, and optionally an off-provider copy where licences allow |
| B9 | Equivalent-capture start dates are a power-driven input to choosing `T0` (master inventory §7a). Decided at cycle registration |

**Live capture of development data before `T0 − m`** needs §2.1 plus B6 to B8, but not B1 to B5. This rests on `T0` being a declared future time fixed at cycle registration (H-1). Data captured before `T0 − m` is development data and can never become protected.

### 2.4 Before protected evaluation

| # | Control |
|---|---|
| E1 | Stage B controls in force and verified |
| E2 | **The protected-evaluation job:**<br>- a fixed Cloud Run Job or Workflow with its own service account and frozen Gate 6 image digests;<br>- reads only `[T0 − max_lookback, E + Δ_label]` and the frozen candidate;<br>- writes only to `vault-eval-results`;<br>- the owner-admin identity holds only the execute permission;<br>- every invocation is logged |
| E3 | Gate 6 re-normalization of the protected interval with the frozen candidate's normalizer digest, plus a parity hash check on overlap rows before the boundary. All candidate training data is under that digest |
| E4 | Results reach agents only through a logged owner release (START_HERE.md Phase 7; HOLDOUT_ACCESS_LOG.md) |
| E5 | Frozen candidates are stored outside any project a kill switch can disable, under event-based holds |

### 2.5 Before live trading

| # | Control |
|---|---|
| L1 | A separate `pmv-runtime` project. Venue trading credentials live only in its Secret Manager |
| L2 | Each runtime deployment needs explicit owner approval and goes through a `main`-only protected environment |
| L3 | Training-serving parity: one feature library, replay parity tests, CPU-serving acceptance |
| L4 | L-PROD licence re-check for every input `licence_id` |
| L5 | All START_HERE.md Phase 8–12 requirements, unchanged |

## 3. Architecture

```
                         ┌───────────── pmv-ops ─────────────┐
                         │ Terraform state · Artifact Registry │
                         │ restricted log bucket · budgets      │
                         └─────────────────────────────────────┘
 external sources ─► ┌──────────────────── pmv-vault ─────────────────────────────┐
                     │ Historical: VM/Batch + persistent disk runs B07 → sealed     │
                     │ Prospective: capture VMs run venue connector + B08 → sealed  │
                     │     │ sealed-object uploader (create-only, CRC32C, read-back)│
                     │     ▼                                                        │
                     │ gs://<p>-vault-raw   (immutable raw · manifests · journals)  │
                     │     ├─ vault normalizer → gs://<p>-vault-ops (operational)   │
                     │     ├─ H-2 release job (fixed; owner-admin execute) ─────────┼─► pmv-dev
                     │     └─ protected-eval job (Gate 6) → vault-eval-results      │
                     └──────────────────────────────────────────────────────────────┘
                     ┌──────────────────── pmv-dev (no internet egress) ───────────┐
                     │ dev-released · dev-normalized · dev-features · dev-labels    │
                     │ dev-artifacts · scratch · Batch (CPU/GPU, Spot)              │
                     └──────────────────────────────────────────────────────────────┘
                     vault-backup bucket inside pmv-vault (second region) at Stage A; pmv-backup at Stage B
                     pmv-runtime (Phase 11+)

 Chromebook: git and Claude Code only; owner cloud work in Cloud Shell or a separate
 browser profile; no dataset on disk.
```

- **Naming.** `<p>` is a globally unique prefix. No bucket, object, metric, or log name encodes a ticker, a strike, or a date that reveals scope (`docs/protected_information.md` prerequisite 4). Feed IDs are opaque.
- **Regions.** See §11.

## 4. Storage and data formats

| Bucket | Project | Holds |
|---|---|---|
| `vault-raw` | vault | Every unreleased real observation: acquisitions, capture segments, manifests, journals, quarantine. No landing bucket: B07 and B08 quarantine and check on disk before upload |
| `vault-ops` | vault | Vault normalizer output. Operational only, never an evaluation or release input. QA from it follows A10 and B4 |
| `vault-eval-results` | vault | Protected-evaluation outputs (Stage B onward) |
| `dev-released` | dev | Released raw rows and release manifests |
| `dev-normalized`, `dev-features`, `dev-labels`, `dev-artifacts` | dev | Derivatives of released rows; models, calibrators, run manifests |
| scratch | dev | Temporary outputs. Soft delete 0, no versioning, lifecycle deletion |
| Terraform state | ops | Versioned, separate per environment. No pull-request identity can read it |
| `vault-backup` | vault (second region) | Coldline copy of vault raw, under the A7 deny. It moves to `pmv-backup` only with B3 parity |

Storage policy:
- one home region; Standard class for active data;
- buckets split by security boundary and lifecycle, with the source as a path segment;
- retention policy unlocked, with its duration an owner input under A-3;
- event-based holds on Gate 6 inputs.

**Raw layout** (mirrors `docs/raw_data.md`; the path date is the UTC date the segment opened):

```
gs://<p>-vault-raw/
  acquisitions/v1/<source_id>/<acquisition_id>/<file> and acquisition.json
  journals/v1/<writer_id>/<seq>-<sha256>.jsonl ; journals/v1/checkpoints/...
  captures/v3/<source_id>/<feed_id>/<yyyy>/<mm>/<dd>/<session_id>/<segment_seq>.pmvseg
  quarantine/<id>/...
```

| Layer | Format |
|---|---|
| Raw | Source-native bytes unchanged, plus frame format v3 segments. Never forced into Parquet. The Chromebook transforms nothing |
| Normalized | Content-addressed Parquet (zstd) plus manifests, partitioned by UTC date, one dataset per `(source_id, schema_version, normalizer digest)`. Prices and sizes as DECIMAL or scaled integers. Manifests list raw paths, generations, SHA-256s, normalizer digest, and commit |
| Features and labels | Parquet stored once by date, in separate prefixes written by separate service accounts. No fitted transforms in shared tables |
| Training input | Fold manifests (partition hashes, boundaries, purge and embargo, label availability, `V ≥ T + max_lookback + max contract life`), hashed and registered before results. One tested loader |
| Artifacts | LightGBM text or JSON, ONNX or safetensors, JSON or npz calibrators. Never pickle. Manifests carry SHA-256, feature schema version, run ID, and image digest |

**BigQuery is optional and non-canonical.** It is not required for the first pipeline. Possible later uses are metadata, bounded QA, selective development queries, and catalog analysis, with byte caps and custom quotas. It never holds vault, protected, or label data.

## 5. Vault isolation and information embargo

### 5.1 Information classes

- A development job's metrics, logs, and weights reach agents. Under R-13 they carry the information time of their inputs. A development job that reads unreleased data is therefore exposure.
- Project boundaries, not buckets inside one project, separate unreleased data from development data, because project-level roles silently cover every bucket in a project.
- Protected data is vault data cut by information time. It needs no separate "holdout bucket".

### 5.2 The cut is by information time

- A row's information time is its latest catalogued time field, plus interval ends and `max_clock_error` (R-3).
- As-of fields and record versions are cut by `known_at` (R-7). Contracts follow Policy 2 (R-6).
- `[T0 − m, T0)` is embargoed but never protected-eligible.
- Historical data fetched after `T0 − m` carries current-state metadata and is cut field by field.
- Object prefixes are coarse defense in depth only.

**Who can do what**

| Actor | Vault data | Dev data |
|---|---|---|
| Agents | Never | Value-safe outputs of submitted jobs, once H-2 release exists |
| Development jobs | Never | By stage |
| Vault service accounts | Prefix-scoped | Release job writes the staging prefix only |
| Owner, day-to-day | No data role; no act-as | Yes |
| Owner, break-glass | Logged (A6, B5) | Yes |

### 5.3 Historical and prospective data

**Historical data.**
- Historical data that is legitimately acquired (A-1 to A-8) and formally released as development data (H-2) may be used for model development, model selection, features, calibration research, and walk-forward testing.
- Prospective formation (H-1) makes all admissible pre-`T0 − m` data development data.
- **Once exposed as development data, it is permanently ineligible for protected holdout use.**

**Prospective capture** should begin early. It supplies receipt-time truth, execution-realistic observations with live books, future protected-holdout material, and additional statistical power. **It does not invalidate the historical-development path.**

**Interpretation to confirm (D-B09-20, before the first development release).**
- The Phase 2 working-design rule S-9 (`docs/phase2.md`, not owner-adopted) computes "any validation result used for selection" on receipt-time folds, including "the comparison that selects ... for the audit candidate". It treats archive-validated folds as "discovery only".
- The owner's words were "development/model selection". Read as development-stage selection (exploration, pilot choice, narrowing, all logged), they fit S-9. Read as also covering the final audit-candidate comparison, they depart from it.
- Options:
  - **(a)** Keep S-9. The cost is calendar time for a powered receipt-time comparison.
  - **(b)** Let archive-validated folds decide the audit candidate. The risk is that an artifact-driven candidate consumes a holdout cycle.
  - **(c)** Allow archive selection only when receipt folds are underpowered, with a preregistered receipt-time non-inferiority check and a stated artifact bound.
- The development Statistician, who wrote S-9, recommends (a). The Independent Statistical Auditor reviews it at Gate 2 (H-6).
- Released rows carry `availability_class` and `metadata_pit_class` under every option.

## 6. Historical acquisition architecture

### 6.1 Compute and run path

- The B07 pipeline runs unchanged on a cloud-side persistent disk (A16 run path): quarantine, hash on receipt, the isolated seccomp parse worker, promotion inside the store.
  - Its filesystem semantics are preserved: no-replace renames, directory fsync, `O_TMPFILE` linking, `flock`, modes, and device and owner checks.
  - GCS FUSE is not used.
- Acquisitions that need B07 resume semantics use a VM with a named persistent disk, not Spot. Batch-created disks may be deleted when a job ends (S).
- Cloud Run Jobs may handle only small, bounded paginated pulls. They must fit the memory-backed disk, and the parse worker's confinement self-test must pass in that sandbox first.
- Storage Transfer Service may copy S3-delivered vendors, as a vault service account. It needs an AWS-side credential; agent requirements are unverified.

### 6.2 Sealed-object uploader (A9)

After a file is final and in its manifest, the uploader:
1. verifies the local SHA-256 against the manifest;
2. uploads create-only to `vault-raw` with CRC32C;
3. resolves an ambiguous result (timeout, then 412) by downloading and hashing its own object, since GCS stores no SHA-256. A match counts as verified. A mismatch keeps the local copy, uploads it under `quarantine/`, and raises an alert;
4. after verification only, retires the local copy through a step the store's integrity checks accept.

`acquisition.json` and each segment manifest are uploaded last, as the commit marker. Readers ignore acquisitions without one. The vault normalizer and the release job verify each object's SHA-256 against the manifest and refuse mismatches, because a mismatched object cannot be removed under its canonical name (RT-B9C4-03).

Journals and checkpoints:
- **Journals:** one hash chain per writer.
- **`sa-journal-sealer`:** merges the chains into checkpoints. Parallel tasks never assign sequence numbers in a shared chain.

### 6.3 Source handling

- **Rate limits are per egress IP:** one limiter per source, set below its documented limit. A 429 is a surfaced signal. Static NAT addresses are recorded.
- **Reachability from GCP is untested.** A chartered connectivity check per source, retaining no data, precedes A-1. No region or egress path is ever chosen to get around a venue's geographic or eligibility restriction.
- **Kalshi:**
  - record `/historical/cutoff` before and after each run, and fail closed if it moved;
  - accept and log both cursor terminal values;
  - reconcile tiers on ticker plus trade ID;
  - gold labels need live-tier access under their own charter.

## 7. Prospective capture architecture

**Machines.** Dedicated-core Compute Engine VMs, on demand, never Spot, in the capture region (§11). They run the B08 segmented store unchanged, with its semantics preserved, and seal segments into the uploader (§6.2).

**Venue connector.** It must be built and reviewed before any live capture (B6). It needs:
- dynamic market discovery, because a new 15-minute contract opens every 15 minutes;
- snapshot plus delta, with a re-snapshot on any gap;
- heartbeats and reconnect;
- handling of maintenance windows;
- a method allowlist with no order paths;
- REST cross-checks.

**Timing and redundancy.**
- Chrony offset is recorded per segment.
- Two collectors run in two zones. Availability time is taken only from a pre-designated primary; secondary data is flagged as gap fill.
- Per-key connection limits are verified before two collectors share one key.
- A maximum segment age bounds the data at risk.

**Network and credentials.** Capture VMs have an egress allowlist that excludes order paths. Venue credentials follow B7.

## 8. Training architecture

**GCP Batch is the initial training backend, for CPU and GPU.**
- One container image per commit, built from `uv.lock`, with CPU and GPU variants from the same lock.
- One deterministic training entry point.
- Spot where appropriate, a pinned machine type and minimum CPU platform, local SSD, and jobs that end themselves.

**Vertex AI deferred** until a measured requirement exists: managed HPO, registry or experiment features beyond the ledger, distributed training, or a GPU capability Batch cannot economically provide. The two systems are not both built.

**Order of work.**
- Logistic and statistical baselines first, then gradient boosting.
- Sequence models only if the baselines leave measurable, calibrated, after-cost room.
- GPUs only where a CPU epoch exceeds about 10–15 minutes, after a CPU benchmark. Start with one L4 or T4.

**Spot and search.**
- Checkpoints include the model, optimizer, RNG, and loader position.
- A preempted trial resumes from its checkpoint and is never re-drawn.
- Search budgets are preregistered as configuration × fold evaluations, counting failed and preempted trials.
- Tuning is nested inside the training window. Selection follows D-B09-20.
- Results are deflated by block bootstrap of the whole selection procedure (Policy 8).

**Calibration** is fitted on a later slice inside the training window. **Normalizer parity:** the frozen candidate's normalizer digest is used for its development data and at Gate 6 (E3).

## 9. Orchestration and reproducibility

**Orchestration.**
- A minimal deterministic Python pipeline runner: ordered stages with input and output manifests, skipping any stage whose outputs already match by hash.
- It runs identically on synthetic data locally and as a cloud job.
- Cloud Scheduler and Workflows are used only where useful. No Composer and no Vertex Pipelines initially.
- No step involves an LLM.

**Reproducibility.**
- Base images are pinned by digest.
- Thread count is fixed; machine type and CPU platform are recorded.
- GBM and torch run with deterministic settings.
- A bit-for-bit CPU reproduction test runs in CI on synthetic data. GPU spread is measured.
- The ML and data dependency stack is added as a reviewed, hash-locked step before the first training stage.

**Ledger.** Parallel tasks write immutable run manifests. A single ingest stage appends them to the authoritative ledger in a fixed order.

**Artifact identity.** Images are tagged with the commit SHA and referenced by digest. Every job records its digest and commit in its output manifest.

## 10. IAM, credentials, CI/CD, and Terraform

There is no administrator service account.

| Account | Project | Can | Cannot |
|---|---|---|---|
| `sa-acq-hist` | vault | Create under `acquisitions/`, `quarantine/`, and its own journal; read back its own objects; read its source secrets | Read others' objects; delete; update; reach dev |
| `sa-capture` | vault | Create under `captures/`, `quarantine/`, and its own journal; read back its own objects; read its venue data secret once approved; write value-free metrics | Call order endpoints; reach dev |
| `sa-journal-sealer` | vault | Read journal segments; create checkpoints | Read data objects; delete |
| `sa-vault-normalize` | vault | Read raw; write `vault-ops` | Write dev |
| `sa-release` | vault → dev | Read raw and the catalog; write dev staging; append the release ledger | Run except by owner-admin execution (from R1); overrides |
| `sa-protected-eval` | vault | Read the bounded protected window and the frozen candidate; write `vault-eval-results` | Write dev; run except by owner-admin execution (from E1) |
| `sa-backup-copy` | vault | Read raw; create in `vault-backup` | Delete |
| `sa-dev-normalize`, `sa-dev-features`, `sa-dev-labels` | dev | One stage each | Reach vault. Features cannot read labels |
| `sa-dev-train`, `sa-dev-eval` | dev | Read through the fold loader; write artifacts and reports; use GPUs within quota | Reach vault; read secrets; query public datasets |
| `sa-dev-submit` (optional, D-B09-15) | dev | Submit Batch jobs as `sa-dev-train` from any-branch images, within quotas | Anything outside dev |
| `sa-deployer-dev`, `sa-deployer-vault` | ops | Terraform apply for one environment (A15). `sa-deployer-vault` is the only act-as holder on vault runtime accounts (A16) | Read data; execute release or evaluation |

**Credentials.**
- A4 is the primary control.
- As defense in depth, the owner may apply `.claude/settings.json` denies for `~/.config/gcloud`, application-default credential paths, `~/.config/gh`, `~/.docker/config.json`, and `~/.terraform.d`, and avoid inherited `GOOGLE_APPLICATION_CREDENTIALS` or `CLOUDSDK_*` variables.
- These are documented owner actions; agents do not apply them.

**Secret Manager.**
- One secret per credential, in the project of the account that uses it, with per-secret grants.
- Secrets are read at job start, rotated through versioning, and their access is logged.
- No secret is ever entered through an agent session.

**CI/CD.** GitHub Actions with Workload Identity Federation, and no keys.
- The attribute condition pins the repository, repository ID, owner ID, `refs/heads/main`, and the environment. Pinning `job_workflow_ref` is optional.
- Deploy environments use deployment-branch policies restricted to `main`, with the owner as required reviewer.
- `terraform plan` runs only on `main`, or with an identity that cannot read state or vault resources.
- Pull-request runs never receive a deploy-capable identity.
- "Protect Main" requires a pull request and the Quality gate check. Adding a required approving review is an owner ruleset decision.

**Terraform.**
- It manages projects (after the owner creates billing), APIs, buckets and policies, service accounts, IAM and deny policies, networks, Artifact Registry with cleanup, Secret Manager containers (never values), VMs and job definitions, log routing, audit configuration, and budgets.
- Owner-manual items: billing, payment, provider terms, and secret values (entered through stdin). At Stage B, also Organization and identity setup.
- `infra/` is created only when CLOUD-1 is chartered. Changes to `infra/` and `.github/` get Red-Team review.

## 11. Cost controls and regions

| Scenario (details in `research/cloud/pmv_cloud_cost_model.md`; prices SECONDARY) | Rough monthly cost |
|---|---|
| Bootstrap: 100 GB raw, historical only, CPU baselines | about $10–20 |
| Working project: 1 TB, one Kalshi collector pair, CPU training most days, a few GPU runs | about $180 |
| Full development: 5 TB, two collector pairs, regular GPU runs | about $600–700 |

**Controls.**
- Starting budget about $100/month for CLOUD-1 to CLOUD-3.
- Budget alerts. Quotas are the hard limiters: GPU, Batch, and BigQuery if enabled.
- A dev-only kill switch, scoped by IAM, never applied to capture.
- Scratch buckets without soft delete or versioning. Objects are written as files of several MB.
- Standard class for data that is reread. Artifact Registry cleanup.
- Data purchases and owner time dominate cloud cost.

**Regions.**
- Home region `us-central1` for vault, dev, and training (S).
- Capture region `us-east5`, near Kalshi's reported AWS us-east-2. `us-east4` if Polymarket US becomes relevant.
- Runtime region decided at Phase 11 from measured latency.
- Backup in a second US region.
- Service availability is re-verified at CLOUD-0.

## 12. Cloud implementation roadmap

| Stage | Content | Controls | Rough effort |
|---|---|---|---|
| CLOUD-0 | Owner: billing upgraded, budget, regions confirmed, administration only from Cloud Shell or a separate browser profile, credential rule adopted | Prerequisites for A2, A4, A13 | Days |
| CLOUD-1 (first implementation batch) | Terraform for `pmv-ops`, `pmv-vault`, `pmv-dev`: `vault-raw` and `vault-ops`; empty dev buckets; per-environment state; service accounts; deny policy and run path; audit logs and restricted log bucket; dev network and API allowlist; Gemini API off; Artifact Registry; Secret Manager containers; budgets; GPU quota 0; WIF with `main`-only environments. Red-Team IAM review before any data | Delivers A2–A8, A10, A11, A13, A15–A18. A1 is an owner decision | 1–2 weeks |
| CLOUD-2 | Sealed-object uploader, per-writer journals and sealer, B07 pipeline on a VM, per-source rate limiter, A-3 cloud backup in `vault-backup` with a synthetic restore test. Synthetic data only. Red-Team review | A9, A14 (backup), A12 | 2–3 weeks |
| CLOUD-3 | First cloud-to-cloud historical acquisition, for whichever source's licence clears first (master inventory §7) | All of §2.1, plus A-1 to A-6 for that source | About 1 week |
| CLOUD-4 | Venue connector and capture VM image (synthetic and fixture tests), then live capture of licensed feeds | §2.1 plus B6–B8 | 2–3 weeks, plus decisions |
| CLOUD-5 | H-2 release job; first released development rows | §2.2 | Gated by H-2 and cycle registration |
| CLOUD-6 | Feature library, fold loader, Batch template, ledger ingest, baselines. Built on synthetic data from CLOUD-1 onward | R5–R7 | 2–4 weeks |
| CLOUD-7 | GPU training on Batch, if baselines justify it | — | — |
| Stage B | Organization (if feasible), VPC-SC, organization policies, administrator separation, backup parity, telemetry coarsening | §2.3 | Before `T0 − m` |
| CLOUD-8 | Protected-evaluation path | §2.4 | Gate 6 path |
| CLOUD-9 | `pmv-runtime`: shadow, then live | §2.5 | Phase 11–12 |

The first real experiment is about 3–4 months away. The governance track (licences, H-2, cycle registration) sets the date. The proposed gates K1–K4 (D-B09-18) decide whether paid data and later stages happen.

## 13. Owner decisions required

Full text: decision record §7. D-B09-1 to D-B09-9 (2026-10-16) remain pending; withdrawing D-B09-5 in favour of D-B09-13 is recommended.

| # | Decision |
|---|---|
| D-B09-10 | `pmv-vault` as the cloud successor to F-01, with governance edits |
| D-B09-11 | Credential rule (A4), plus owner-applied `.claude/settings.json` denies |
| D-B09-12 | Record the Stage A risk acceptance; commit to the Stage B decision before `T0 − m` |
| D-B09-13 | Cloud backup policy (A-3), including the retention duration |
| D-B09-14 | Adopt this architecture as the design basis |
| D-B09-15 | Optional dev-experiment tier (recommend deferring) |
| D-B09-16 | Charter CLOUD-0/1 (§12) |
| D-B09-17 | Terms-first ruling and disclosed fetches; allowlist GCP documentation hosts for re-verification |
| D-B09-18 | Kill and spend gates K1–K4 and the M-0 go/no-go milestone |
| D-B09-19 | Telemetry coarsening from `T0 − m` |
| D-B09-20 | Selection-rule interpretation (§5.3) |
| D-B09-21 | Gold in cycle 1 (recommend exploratory only) |
| D-B09-22 | Licence letters and terms copies (critical path) |

## 14. Evidence re-verification requirements

Before the stage that relies on each item, verify it on the official page (D-B09-17 would allowlist the GCP documentation hosts):

| Item | Needed by |
|---|---|
| IAM deny-policy permission names, tag-conditioned scoping, and coverage of act-as, VM-mutation, disk, and key paths; whether basic Owner implies object read; service-agent exceptions | CLOUD-1 |
| Default Compute service account behavior without an Organization; project-level API enablement controls | CLOUD-1 |
| Terraform Google provider support for Batch jobs (A16) | CLOUD-1 |
| GCS create-only preconditions, checksums, soft-delete defaults, versioning, retention, lifecycle conditions | CLOUD-1/2 |
| Batch disk lifecycle; Cloud Run Jobs limits and sandbox behavior for the parse worker | CLOUD-2 |
| GPU types, Spot availability, and quota in the chosen regions; free-trial restrictions | CLOUD-0 and CLOUD-7 |
| VPC-SC and organization-policy prerequisites; Cloud Identity Free | Stage B |
| All prices in the cost model | Before each budget commitment |
| Per source: licence permission for third-party cloud storage (A-2); reachability from cloud IPs; venue regions, key scopes, connection limits | Before A-1 for that source |
