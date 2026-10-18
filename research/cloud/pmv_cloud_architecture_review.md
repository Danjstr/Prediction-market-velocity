# PMV cloud-native architecture: canonical current design (B09, 2026-10-18)

**Status:** research and recommendation. **Not an approved requirement**, not a gate record, and not a provisioning plan that may be executed. No cloud resource, account, credential, or data acquisition is authorized by this document. Adopting any of it is the owner's decision (decision record §7).

**Related documents:**
- owner direction and decisions: `docs/decisions/2026-10-18_b09_cloud_native_data_strategy.md`;
- costs: `research/cloud/pmv_cloud_cost_model.md`;
- data sources: `research/data_sources/master_source_inventory.md`;
- reviews and dispositions: `research/governance/b09_cloud_architecture_reviews.md`.

**This document is the single current design.** It replaces the first draft of 2026-10-18 and the interim rewrite. Where a review finding changed the design, the finding ID is cited inline. Earlier proposals that were superseded are listed in the reviews file, not here.

**Evidence limits.**
- The container's fixed network allowlist refuses every official cloud documentation host.
- Every cloud product fact, limit, and price here is **SECONDARY** (web-search summaries, GitHub pages of official projects, or reviewer recollection). That includes IAM deny-policy coverage, VPC Service Controls prerequisites, Cloud Run and Batch limits, GPU availability, soft-delete defaults, and lifecycle semantics.
- Each fact is re-verified on the official page before the stage that relies on it (§15).

## 0. Verdict and decisions in brief

**Advisory verdict, in the owner's requested form: GCP ARCHITECTURE APPROVED WITH CHANGES.** This is an agent recommendation. Approval is the owner's.

**Provider: KEEP GCP** (§1).

| Topic | Current recommendation |
|---|---|
| Data separation | By **information class**: a `pmv-vault` project holds every unreleased real observation; a `pmv-dev` project holds only formally released rows and their derivatives (§3, §4) |
| Security model | **Staged** (§4.1). Stage A (historical development, pre-`T0`): separate projects, least-privilege IAM, no agent vault access, no keys, create-only raw, audit logs. The owner accepts that, without an Organization, a project administrator can technically override IAM and deny controls. Stage B (before `T0 − m` and protected evaluation): revisit and require stronger isolation (Organization if feasible, VPC-SC, organization policies, administrator separation, backup parity) |
| B07/B08 stores | **Design direction (owner-approved; implementation not yet):** run the reviewed filesystem stores on cloud compute with a cloud-side persistent disk; seal finished files and segments; upload them create-only to GCS with checksum and read-back verification. GCS becomes the durable canonical store. No native object-store rewrite (§5) |
| Canonical data | Content-addressed Parquet plus manifests in GCS. **BigQuery optional and non-canonical**, not required for the first pipeline (§6) |
| Training backend | **GCP Batch is the initial PMV training backend**, for CPU and GPU, with one container image and one deterministic training entry point. **Vertex AI deferred, not rejected** (§8) |
| Orchestration | A minimal deterministic Python pipeline runner plus Cloud Scheduler. No Composer and no Vertex Pipelines (§9) |
| IaC and CI | Terraform; GitHub Actions with Workload Identity Federation bound to `main` and protected environments; no service-account keys (§10) |
| Regions | Home `us-central1` (data, training); capture `us-east5`, near Kalshi's reported AWS us-east-2 (§12) |
| Timing | Every control is assigned to the boundary at which it is required (§2). Nothing needed only later blocks earlier legitimate work |

## 1. Provider choice: KEEP GCP

| Factor | GCP | AWS | Azure | Effect on PMV |
|---|---|---|---|---|
| Object storage, single region | about $0.020/GB-month (S) | about $0.023 (S) | about $0.018–0.021 (S) | Immaterial at 0.1–5 TB |
| Internet egress | about $0.12/GB (S) | about $0.09/GB (S) | about $0.087/GB (S) | Immaterial: data stays in the cloud |
| Batch compute | Batch: no service fee, Spot, fixed machine types, GPUs (S); Cloud Run Jobs for small tasks | AWS Batch | Azure Batch | Comparable; GCP simplest for one person |
| GPUs | T4, L4, A100 in several US regions; new projects start at 0 GPU quota; **no GPUs on the free trial** (S) | Broadest fleet | Narrower | One L4 suffices |
| Operating from a Chromebook | Cloud Shell: browser terminal with gcloud and Terraform (S) | CloudShell | Cloud Shell | GCP least friction |
| Isolation primitives | Projects and IAM deny policies without an Organization; VPC-SC and organization policies need one (S) | Accounts plus SCPs | Subscriptions | Sufficient for PMV's accident-focused threat model (`docs/protected_information.md` F-05), with the Stage B upgrade |
| Venue proximity | `us-east5` (Columbus) near AWS us-east-2, where Kalshi is reported to run (S) | Same metro | — | A minutes-scale strategy does not need sub-millisecond placement |
| Lock-in | BigQuery and Vertex are proprietary, but both are optional here | Similar | Similar | Parquet, containers, Terraform, and PMV's ledger keep the design portable |

**KEEP GCP.** Nothing makes AWS or Azure materially better for PMV.

Revisit only if either of these happens:
- measured runtime latency shows millisecond placement matters (a small runtime footprint could then sit elsewhere without moving the data platform);
- a key vendor's S3-only delivery makes egress dominate.

## 2. Controls by required timing boundary (mandatory classification)

A control is required **no earlier** than the boundary listed. Nothing below a later boundary blocks work at an earlier one.

### 2.1 REQUIRED BEFORE FIRST HISTORICAL BYTE (Stage A)

| # | Control | Why now |
|---|---|---|
| A1 | Owner decisions D-B09-10 (cloud successor to F-01, the vault as the protected raw store) and the matching governance edits to `docs/raw_data.md`, `docs/protected_information.md`, `docs/phase2.md`, and A-7 | Approved text still places real raw data in `~/pmv-protected/raw` |
| A2 | Separate `pmv-vault` and `pmv-dev` projects (plus `pmv-ops` for state and logs). Billing account upgraded beyond the free trial | Information-class boundary |
| A3 | Per-stage service accounts with least-privilege IAM (§7). Writers create-only, plus read-back of their own prefix | No overwrite, no broad read |
| A4 | **No agent credential with vault access.** No cloud or GitHub credential in any shell where Claude Code runs. Owner cloud administration happens in Cloud Shell or a separate browser profile, never in a Claude Code shell (D-B09-11) | The owner's credential is the largest leak path (§4.3) |
| A5 | **No service-account keys**, anywhere. Enforced in Stage A by including `iam.serviceAccountKeys.create` in the A7 deny for all principals, with no exceptions (RT-B9C2-10) | Key leakage |
| A6 | The owner's day-to-day identity holds no vault data-read role. Vault reads happen only through the named service accounts; break-glass is a separate, logged grant | Keeps the owner, a contamination path, out of raw data by default |
| A7 | IAM deny policy on `pmv-vault`, scoped per bucket, with exceptions only for the named service accounts and break-glass (RT-B9C-01, RT-B9C2-01, -07). It covers:<br>(a) **data reads**;<br>(b) **act-as paths**: impersonation, signing, HMAC keys, job mutation, run overrides, except the launcher identity defined in A16;<br>(c) **paths to raw data on persistent disks**: OS Login and SSH, serial port, snapshot and image creation, disk attach;<br>(d) **service-account key creation** (no exceptions);<br>(e) **bucket policy, retention, versioning, and IAM changes**;<br>(f) **object delete on `vault-raw`** (`sa-vault-promote` may delete only in `vault-landing`, after verified promotion).<br>Where IAM deny cannot express a control, configuration enforces it (all SECONDARY, verified at CLOUD-1): no external IPs; no SSH ingress firewall rule; project SSH keys blocked; no OS Login admin or IAP-tunnel grants; serial port disabled.<br>**Stage A limitation, accepted by the owner:** without an Organization, a project administrator can technically remove the deny or grant themselves access | Fail-closed against accidental grants and ordinary mistakes, including an owner SSH-ing in to debug a stuck acquisition |
| A8 | Raw storage: create-only writes (`ifGenerationMatch=0`); object versioning; default soft delete; no age-based deletion of landing or raw; quarantine never deleted; Bucket Lock not used | B07/B08 immutability principles |
| A9 | Sealed-object uploader with CRC32C and SHA-256 read-back verification; the local copy is deleted only after verification (§5) | Durable canonical storage without rewriting B07/B08 |
| A10 | Data Access audit logs on for vault Storage. Vault logs routed to a restricted log bucket, and excluded from the vault project's `_Default` bucket so that the restricted bucket holds the only copy (RT-B9C2-11). A closed, value-free logging schema | Access is logged; logs do not carry values |
| A11 | Public access prevention and uniform bucket-level access on every bucket | Basic hygiene |
| A12 | Historical acquisition runs as a vault service account. That includes any extraction from BigQuery public datasets of protected equivalents. `bigquery.jobs.create` is not granted to agent or day-to-day identities (DA-B9C-01, RT-B9C-10) | Closes the public-dataset embargo bypass |
| A13 | Budget alerts; GPU quota kept at 0 or 1; BigQuery custom quotas if BigQuery is enabled | Cost control |
| A14 | The source's own gate: A-1 to A-6 for that source, including the A-2 licence determination and a cloud A-3 backup policy with a synthetic restore test (D-B09-13). Retention and deletion duties after a subscription ends are a source-selection criterion (S-B9C-12) | Existing acquisition gate |
| A15 | Terraform for all of the above (RT-B9C2-04):<br>- applied only from a verified `main` commit, from Cloud Shell or a `main`-bound protected environment, **after the owner reviews the plan**;<br>- no `external`, `local-exec`, or `http` data sources, and no unpinned or third-party modules;<br>- provider lock file committed with hashes.<br>Agent Red-Team review of `infra/` does not replace the owner's plan review | No undocumented click-ops; agent-written infrastructure code cannot run arbitrary commands with owner credentials |
| A16 | **Launcher identities, stated explicitly** (RT-B9C2-03). Attaching a vault service account to a VM, Batch job, or Scheduler job requires `iam.serviceAccounts.actAs` on it.<br>- `sa-deployer-vault` holds `actAs` on the vault runtime accounts **only** to create their job and VM definitions. It runs only from `main` through the owner-reviewed protected environment.<br>- Running the release and protected-evaluation jobs is restricted to the owner-admin identity (R2, E2).<br>- These are the only act-as exceptions in the A7 deny. Because they are the real path to vault data, each is `main`-bound and owner-approved | The design otherwise contradicts itself (nothing could launch a vault job), and the real path to data must be named |
| A17 | **Network egress** (RT-B9C2-02). `pmv-dev` has a custom VPC with no default network, an egress deny-all firewall, no Cloud NAT, and Private Google Access only. Dev jobs therefore cannot fetch live or real observations from the internet into agent-visible outputs. Vault acquisition egress is limited per source, in addition to the A-1 fetcher allowlist. Delivered in CLOUD-1, before any job runs in either project | Agent-written code in dev jobs runs outside the container's allowlist and the host-class rule |
| A18 | The Gemini for Google Cloud / Cloud Assist API is never enabled in `pmv-vault` or `pmv-backup` (Terraform-managed service list) (RT-B9C2-05) | Console AI assistants are an LLM path to vault metadata and logs |

### 2.2 REQUIRED BEFORE FIRST DEVELOPMENT RELEASE

| # | Control |
|---|---|
| R1 | The H-2 release tool built and reviewed. Prerequisite chain in `docs/release_tool_design.md`: E-U1 catalog, shared `source_id` catalog, P-3, cycle registration with `T0` and `m` |
| R2 | The release job is a controlled path: run only by an owner-admin identity; overrides denied; inputs (`B`, `m`, catalog) read from the verified registry at a pinned commit; **raw rows only** (S-B9C-02); a staging prefix unreadable by dev, with a commit marker written only after the holdout-log binding (R-8 write-ahead; RT-B9C-07, S-B9C-15) |
| R3 | Dev loaders refuse rows not in a release manifest, and rows whose information time is at or after `T0 − m` (ML-B9C-09) |
| R4 | A deny on object creation in `pmv-dev` except for `sa-release` (staging) and the dev stage accounts (RT-B9C-03) |
| R5 | Dev normalization rebuilt from released raw rows with the same normalizer image digest as the vault (ML-B9C-04, S-B9C-02) |
| R6 | Separate feature and label service accounts and prefixes; as-of join rules; canary test (S-B9C-11) |
| R7 | Experiment-record fields (release manifest hash, `cycle_id`, fold-spec hash, image digest); preregistered fold specs; HP-search budgets counting failed and preempted trials (S-B9C-08, S-B9C-10) |
| R8 | Data-reading vault jobs have no internet egress: private VPC with Private Google Access (RT-B9C-03) |
| R9 | No label tables in BigQuery. If BigQuery is used, label-touching query history goes into the ledger as degrees of freedom (S-B9C-08) |

### 2.3 REQUIRED BEFORE `T0 − m` / PROTECTED CAPTURE (Stage B)

| # | Control |
|---|---|
| B1 | **Stage B isolation decision (owner):** a Google Cloud Organization if feasible (Cloud Identity Free with an owner domain); VPC-SC perimeter around vault and backup; organization policies (key creation disabled, public access prevention, resource locations, console AI assistants disabled); separate administrator and break-glass identities, with the day-to-day identity not Owner of vault or backup (RT-B9C-02, RT-B9C-12). If an Organization is not feasible, the owner records the residual risk explicitly for the protected interval |
| B2 | Verification of the A7 deny, which is in place from the first historical byte: a fault-injection test in which an owner-role principal is refused on every act-as and disk path (RT-B9C-01). With an Organization, the controls move into organization policies |
| B3 | Backup perimeter parity: `pmv-backup` has the same deny, logging, and perimeter controls as the vault. Restore tests go only into a vault-class scratch bucket (RT-B9C-04) |
| B4 | Telemetry coarsening: from `T0 − m`, capture telemetry visible to agents and the owner is reduced to health states and gap flags (S-B9C-01; proposed amendment to `docs/external_access.md` §3, owner decision) |
| B5 | F-09 fail-closed agent web access from `T0 − m` (existing ruling E-B4-4) |
| B6 | Capture safeguards. Venue connector reviewed (DA-B9C-11). Canonical-session rule: availability time from a pre-designated primary only (DA-B9C-10, S-B9C-09). Clock monitoring. Dedicated-core VMs. Alert path with a dead-man heartbeat (RT-B9C-14) |
| B7 | Cloud F-03 successor for venue credentials, in place before any venue credential exists in the cloud. The collector build has no order code paths; the egress allowlist excludes order paths; the capture secret is treated as `trading-private` (DA-B9C-12, RT-B9C-11). **This applies to any live capture, even before `T0`** |
| B8 | Single-provider durability decision for irreplaceable capture: backup payment method, hardware keys and account recovery, optional off-provider copy where licences allow (RT-B9C-04) |
| B9 | Prospective equivalents (master inventory §7a). Each historical feature family's equivalent capture start (`C0`) is a power-driven input to choosing `T0`. A feature whose equivalent starts too late can be in the protected test but cannot be selected under D-B09-20 (a) (S-B9C-04, S-B9C2-08). Decided at cycle registration |

Live capture of **non-protected development data before `T0 − m`** needs all of §2.1 plus B6 to B8, but not B1 to B5.
- This rests on `T0` being a declared future time fixed at cycle registration (H-1).
- Data captured under Stage A controls before `T0 − m` is development data. It can never become protected.

**Deliberate tightening.** The owner placed Stage B "before `T0`". This design uses `T0 − m`, which is stricter, because the Protected Information Rule embargoes the protected families from `T0 − m` (RT-B9C2-09).

### 2.4 REQUIRED BEFORE PROTECTED EVALUATION

| # | Control |
|---|---|
| E1 | The Stage B controls in force and verified |
| E2 | Protected-evaluation job: its own service account; frozen image digests from Gate 6; reads only `[T0 − max_lookback, E + Δ_label]` plus the frozen candidate; writes only to `vault-eval-results`; triggered only by owner-admin, with a logged invocation |
| E3 | Gate 6 re-normalization of the protected interval with the frozen normalizer, plus a parity hash check on pre-boundary overlap rows (ML-B9C-04, S-B9C-02) |
| E4 | Results released to agents only by a logged owner release (START_HERE.md Phase 7; HOLDOUT_ACCESS_LOG.md) |
| E5 | Frozen candidates stored outside any project a kill switch can disable, with event-based holds (RT-B9C-13) |

### 2.5 REQUIRED BEFORE LIVE TRADING

| # | Control |
|---|---|
| L1 | A separate `pmv-runtime` project, with venue trading credentials in its Secret Manager only |
| L2 | Runtime deployment by explicit per-release owner approval, through a `main`-only protected environment |
| L3 | Training-serving parity: one feature library, replay parity tests, CPU-serving acceptance (ML-B9C-07) |
| L4 | L-PROD licence re-check for every input `licence_id` (`docs/external_access.md` §2) |
| L5 | All START_HERE.md Phase 8–12 requirements, which this document does not change |

## 3. Architecture

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
                     └───────────────────────────────────────────────────────────────┘
                     pmv-backup (second region; added with the A-3 policy; parity at Stage B)
                     pmv-runtime (Phase 11+)

 Chromebook: git and Claude Code only; no cloud or GitHub credential in Claude's shells;
 owner cloud work in Cloud Shell or a separate browser profile; no dataset on disk.
```

`<p>` is a globally unique prefix chosen at CLOUD-1. No bucket, object, metric, or log name encodes a ticker, a strike, or a scope-revealing date (`docs/protected_information.md` prerequisite 4). Feed IDs in paths are opaque.

## 4. Vault isolation and the information embargo

### 4.1 Why projects and information classes

Under PMV's rules, every real observation is holdout-eligible and agent-invisible until H-2 releases it (A-8). A development job's metrics, logs, and weights reach agents. Under R-13, these are derived artifacts whose information time is the latest of their inputs. A development job reading unreleased data is therefore exposure. The proposed "raw development" bucket would have breached this on day one.

The vault/dev boundary is placed between projects for three reasons:
- project-level roles silently cover any bucket in the same project;
- the separation of buckets in one project (Option A) is not fail-closed;
- protected data is simply vault data cut by information time. It needs no separate "holdout bucket" beside development data.

### 4.2 The cut is by information time

- Each row's information time is its latest catalogued time field, plus interval ends and `max_clock_error` (R-3).
- As-of fields and record versions are cut by `known_at` (R-7). Contracts are eligible under Policy 2 (R-6).
- The margin `[T0 − m, T0)` is embargoed but never protected-eligible.
- Historical data fetched after `T0 − m` carries current-state metadata and is cut field by field (S-B9C-03).
- Object prefixes keyed to receipt date are coarse defense in depth only.

### 4.3 Credential paths (Stage A)

The owner's Chromebook runs Claude Code. Any credential in a shell Claude Code can use is a credential agents can use.

**Rule proposed for D-B09-11:**
- no cloud credential (gcloud, application-default credentials, Terraform, Docker helpers) in any OS user or shell where Claude Code runs;
- no GitHub credential (`gh`) there either;
- owner cloud work happens in Cloud Shell or a separate browser profile;
- Claude Code never runs inside Cloud Shell (RT-B9C-06, ML-B9C-16).

**Defense in depth (owner-applied edit to `.claude/settings.json`):**
- deny `~/.config/gcloud`, application-default credential paths, `~/.config/gh`, `~/.docker/config.json`, and `~/.terraform.d`;
- no inherited `GOOGLE_APPLICATION_CREDENTIALS` or `CLOUDSDK_*` variables.

A denylist is never complete; the rule is primary.

### 4.4 What Stage A accepts, and what Stage B adds

- **Stage A** is fail-closed against accidental grants and ordinary mistakes, the threat model PMV adopted (F-05). It is **not** fail-closed against the project administrator. Without an Organization, the Gmail account that creates a project is its Owner and can remove deny policies (RT-B9C-02). The owner has said they accept this risk for pre-`T0` historical development acquisition.
- **Stage B** adds the Organization-dependent controls (B1 to B3) before protected capture and evaluation.
- No binding PMV governance rule requires an Organization for historical development acquisition. The relevant approved controls are:
  - `docs/protected_information.md` F-01: raw data outside agent-readable storage;
  - A-7: protected storage written by a tool outside agent sessions;
  - A-8: release is separate.

  Stage A satisfies all three in cloud form once D-B09-10 adopts the vault as the successor location. The Red-Team proposal to require an Organization before the first byte (RT-B9C-02) was a review recommendation, not an approved rule. It is moved to the Stage B boundary under the owner's direction.

### 4.5 Who can do what

| Actor | Vault data | Dev data |
|---|---|---|
| Agents | Never | Value-safe outputs of submitted jobs, once H-2 release exists |
| Development jobs | Never | By stage |
| Vault service accounts (acquire, capture, promote, normalize, release, protected eval, backup copy) | Prefix-scoped | Release job writes the staging prefix only |
| Owner, day-to-day | No data role (deny); at Stage B, also not project Owner | Yes |
| Owner, break-glass | Audited grant. Pre-cycle reads are recorded in `docs/exposure_register.md` Part A (S-B9C-14) | Yes |

## 5. B07/B08 on cloud compute (design direction approved; implementation not yet)

- **Unchanged reviewed code.** The B07 acquisition store and the B08 segmented capture store keep their filesystem semantics: no-replace renames, directory fsync, `O_TMPFILE` linking, `flock`, modes, device and owner checks. They run on cloud compute with a **cloud-side persistent disk**: Batch or a Compute Engine VM for historical work, capture VMs for prospective capture. GCS FUSE is not used; the code already refuses unsupported filesystems (ML-B9C-01).
- **Sealed-object uploader** (new, small, Red-Team reviewed). After a file or segment is final and recorded in its manifest:
  - it uploads create-only (`ifGenerationMatch=0`) with CRC32C;
  - an ambiguous result (timeout, then 412) is resolved by read-back of its own prefix, comparing CRC32C and SHA-256 with the local file. A match is verified; a mismatch is quarantined and alerted (DA-B9C-08, RT-B9C-08);
  - it verifies SHA-256 against the manifest, then deletes the local copy;
  - a maximum segment age bounds the data at risk on zonal disk loss.
- **Journals.** One hash chain per writer (task or session); a single sealer merges chains into checkpoints. Parallel tasks never assign sequence numbers in a shared chain (DA-B9C-09, RT-B9C-19).
- **Promotion.** `sa-vault-promote` moves files from landing to raw after the A-4 checks in the isolated worker. It deletes landing objects explicitly after verified promotion. No lifecycle rule deletes landing, raw, or quarantine (RT-B9C-09).
- **Cloud Run Jobs** only for small paginated pulls that fit their memory-backed disk, and only after the parse worker's confinement self-test passes in that sandbox (ML-B9C-13).
- **The Chromebook is never a relay.** Sources go to cloud workers, then to GCS.

**Object layout** (mirrors `docs/raw_data.md`):

```
gs://<p>-vault-raw/
  acquisitions/v1/<source_id>/<acquisition_id>/<file> and acquisition.json
  journals/v1/<writer_id>/<seq>-<sha256>.jsonl ; journals/v1/checkpoints/...
  captures/v3/<source_id>/<feed_id>/<yyyy>/<mm>/<dd>/<session_id>/<segment_seq>.pmvseg
  quarantine/<id>/...
```

The date in the path is the segment-open UTC date.

**Immutability settings:**
- versioning on raw, artifacts, and state;
- soft delete at its default on raw and 0 on scratch;
- retention policy unlocked, with its **duration an owner input under A-3** (RT-B9C-15);
- **no Bucket Lock** (irreversible; would conflict with licence deletion duties);
- event-based holds on Gate 6 inputs;
- bucket update, delete, IAM, and retention changes denied except to break-glass; object delete on `vault-raw` denied; `sa-vault-promote` may delete only in `vault-landing` after verified promotion. These denies are in place from the first historical byte (A7) and verified at Stage B (B2).

## 6. Data formats and BigQuery

| Layer | Format |
|---|---|
| Raw | Source-native bytes unchanged (JSON pages, DBN/zstd, CSV/zip) and frame format v3 segments. Never forced into Parquet. The Chromebook transforms nothing |
| Normalized | **Content-addressed Parquet (zstd) plus manifests in GCS**, partitioned by UTC date, one dataset per `(source_id, schema_version, normalizer digest)`. Prices and sizes stored as DECIMAL or scaled integers. Manifests list raw object paths, generations, SHA-256s, normalizer digest, and commit |
| Features and labels | Parquet stored once, by date, in separate prefixes written by separate service accounts. No fitted transforms in shared tables |
| Training input | **Fold manifests, not fold copies** (ML-B9C-05, S-B9C-10). A manifest holds partition paths and hashes, train/validation boundaries, purge and embargo widths, the label-availability rule, and `V ≥ T + max_lookback + max contract life`. It is hashed and registered before results. One tested loader applies the boundaries. Jobs copy partitions to local SSD and memory-map Arrow |
| Artifacts | Safe formats only: LightGBM text/JSON, ONNX or safetensors, JSON/npz calibrators. Never pickle. Manifests carry SHA-256, feature schema version, run ID, and image digest |

**BigQuery: optional and non-canonical. Not required for the first acquisition or training pipeline.** DuckDB or Polars inside jobs cover QA and exploration at the start.

- **Possible later uses:** metadata, bounded QA, selective development queries, and catalog or index analysis. Each query is capped with `maximum_bytes_billed`; custom daily quotas are the real cap, since byte caps may not bind on external tables (S).
- **Never:** vault or protected data; label tables; queries of public datasets of protected equivalents from development identities.

## 7. Service accounts

There is no administrator service account. Deployer identities have no data access and no act-as rights on data accounts.

| Account | Project | Can | Cannot |
|---|---|---|---|
| `sa-acq-hist` | vault | Create under `acquisitions/` and its own journal; read back own objects; read its source secrets | Read others' objects, delete, update; reach dev |
| `sa-capture` | vault | Create under `captures/` and its own journal; read back own objects; read its venue data secret once approved; write value-free metrics | Order endpoints (blocked in code and egress); reach dev |
| `sa-vault-promote` | vault | Read landing; create in raw; move to quarantine | Delete raw; reach dev |
| `sa-vault-normalize` | vault | Read raw; write operational normalized output | Write dev |
| `sa-release` | vault → dev | Read raw and catalog; write `dev-released` staging; append release ledger | Run except on owner-admin trigger; overrides |
| `sa-protected-eval` | vault | Read the bounded protected window and frozen candidate; write `vault-eval-results` | Write dev; run except on owner-admin trigger |
| `sa-backup-copy` | vault → backup | Read raw; create in backup | Delete |
| `sa-dev-normalize`, `sa-dev-features`, `sa-dev-labels` | dev | One stage each | Reach vault; features cannot read labels |
| `sa-dev-train`, `sa-dev-eval` | dev | Read through the fold loader; write artifacts and reports; GPU within quota | Reach vault; read secrets; query public datasets |
| `sa-dev-submit` (optional, D-B09-15) | dev | Submit Batch jobs as `sa-dev-train` from any-branch images within quotas | Anything outside dev |
| `sa-deployer-dev`, `sa-deployer-vault` | ops | Terraform apply for one environment from `main` after owner plan review. `sa-deployer-vault` holds `actAs` on vault runtime accounts only to define their jobs and VMs (A16) | Data reads; running release or evaluation jobs; anything outside its environment |

## 8. Model training: GCP Batch

- **GCP Batch is the initial PMV training backend**, for CPU and GPU:
  - one container image per commit, built from `uv.lock`, with CPU and GPU variants from the same lock;
  - one deterministic training entry point;
  - Spot VMs, pinned machine type and minimum CPU platform, local SSD, jobs that end themselves.
- **Vertex AI is deferred, not rejected.** Add it only if PMV demonstrates a concrete need for:
  - managed HPO;
  - experiment or model-registry features beyond PMV's ledger;
  - easier distributed training;
  - a GPU capability Batch cannot economically provide.

  Both systems are not built at the start.
- **Order of work:** logistic and statistical baselines, then gradient boosting, then sequence models only if baselines leave measurable, calibrated, after-cost room (CLAUDE.md "Modeling").
- **GPUs:**
  - used only where a CPU epoch exceeds about 10–15 minutes, after a CPU benchmark of a small TCN or GRU;
  - one L4 or T4 first;
  - the free trial allows no GPUs and new projects start at 0 quota (S), so the owner upgrades billing and requests one GPU well before.
- **Checkpoints and preemption:** checkpoints include model, optimizer, RNG, and loader position. A preempted trial resumes from its checkpoint and is never re-drawn. Preemptions are recorded.
- **Hyperparameter search** (S-B9C-08): preregistered (configuration × fold) budget counting failed and preempted trials; full search history recorded; tuning nested inside the training window; selection rules per `docs/phase2.md`; deflation by block bootstrap of the whole selection (Policy 8).
- **Reproducibility contract** (ML-B9C-06):
  - base image pinned by digest;
  - fixed thread count; recorded machine type and CPU platform;
  - `deterministic=True` for GBMs and full torch determinism settings;
  - a bit-for-bit CPU reproduction test in CI on synthetic data; GPU run-to-run spread measured;
  - the ML and data dependency stack (Arrow, Polars or DuckDB, LightGBM, torch, the GCS client) added as a reviewed, hash-locked step before the first training stage. None is a runtime dependency today.
- **Ledger** (ML-B9C-08): parallel tasks write immutable run manifests. A single ingest stage verifies them and appends them to the authoritative ledger in a fixed order.
- **Calibration:** calibrators fitted on a later time slice inside the training window, never in-sample.
- **Normalizer parity:** one normalizer digest for development and for Gate 6 re-normalization (§2.4 E3).
- **Training-serving parity:** before live trading (§2.5 L3).

## 9. Orchestration

- A minimal deterministic pipeline runner: ordered stages with input and output manifests, skipping a stage when output hashes match. It runs identically on synthetic data locally and as a cloud job.
- Cloud Scheduler triggers jobs directly. Workflows is added only for a concrete cross-service retry need.
- No Composer (about $350+/month idle, S), and no Vertex Pipelines.
- No step involves an LLM.

## 10. IaC, CI/CD, and secrets

- **Terraform** manages projects (after the owner creates billing), APIs, buckets and policies, service accounts, IAM and deny policies, Artifact Registry with cleanup policies, Secret Manager containers (never values), Batch templates, Scheduler, VMs, log routing, audit configuration, budgets, and alerts.
- **Owner-manual:** billing, payment, provider terms, secret values (entered through stdin, never shell history), and, at Stage B, Organization and identity setup.
- **State** is in a versioned `pmv-ops` bucket that no pull-request identity can read. A state scan keeps secrets out. `infra/` is created only when CLOUD-1 is chartered. Changes to `infra/` and `.github/` get Red-Team review.
- **GitHub Actions with Workload Identity Federation.** No keys. The attribute condition pins repository, repository ID, owner ID, `refs/heads/main`, and the environment. The google-github-actions/auth README advises always setting a condition (tool-summarized fetch).
- **Agents can push branches containing workflow files** (RT-B9C-05). Therefore:
  - deploy environments have deployment-branch policies restricted to `main`, with the owner as required reviewer;
  - `terraform plan` runs only on `main`, or with an identity that cannot read state or vault resources;
  - pull-request runs never get a deploy-capable identity.
- **Branch protection.** "Protect Main" requires a pull request and the Quality gate check. A required approving review is not recorded (`docs/backup_and_recovery.md`). Adding one is an owner ruleset decision.
- **Optional dev-experiment tier** (D-B09-15, ML-B9C-02): any-branch images in a dev-only registry, submitted through `sa-dev-submit` within hard quotas, with no vault rights.
- **Artifact identity:** images tagged with the commit SHA and referenced by digest. Every job records its digest and commit in its output manifest.
- **Secret Manager:** one secret per credential, in the using account's project, with per-secret grants. Read at job start. Rotation through versioning. Access logged. Never entered through an agent session. The cloud F-03 successor (§2.3 B7) governs venue credentials.

## 11. Ingestion and capture specifics

- **Rate limits are per egress IP.** One global limiter per source, below the documented limit. A 429 is surfaced as a signal. Static NAT addresses recorded (DA-B9C-06).
- **Cloud reachability is documented, not tested.** A chartered connectivity check per source, from the approved egress, with no data retained, precedes A-1. **No region or egress path is ever chosen to get around a venue's geographic or eligibility restriction** (DA-B9C-05).
- **Egress allowlists** are host-level defense in depth. The fetcher's allowlist remains the A-1 control (RT-B9C-15).
- **Kalshi:** record `/historical/cutoff` before and after each acquisition (fail closed if it moved); accept and log both cursor terminal values; reconcile tiers on ticker plus trade ID; gold labels need live-tier access under their own charter (DA-B9C-07).
- **Capture:**
  - a venue connector built and reviewed before any live capture. It covers discovery of each new 15-minute contract, snapshot and delta handling, re-snapshot on gaps, heartbeats, reconnect, maintenance windows, a method allowlist, and REST cross-checks (DA-B9C-11);
  - dedicated-core VMs;
  - clock offset recorded per segment;
  - two collectors with a pre-designated primary.

## 12. Regions

- **Home `us-central1`** for vault, dev, and training (S): broad GPU availability, all needed services, low prices.
- **Capture `us-east5`** (Columbus), near Kalshi's reported AWS us-east-2. `us-east4` if Polymarket US becomes relevant. Uploads to the home region cost about $0.02/GB (S).
- **Runtime region** decided at Phase 11 from measured latency.
- **Backup** in a second US region.
- Availability of each service in each region is re-verified at CLOUD-0.

## 13. Chromebook workflow

| Task | How | Never |
|---|---|---|
| Edit code | Claude Code; commit and push task branches | Datasets on disk; cloud or GitHub credentials in Claude's shells |
| Submit jobs | CI on `main`, Cloud Shell, or the optional dev-experiment tier | Agents running jobs with owner credentials |
| Logs and metrics | Console or Cloud Shell; value-free logs | Raw payload downloads |
| Experiments | Jobs run to completion without the laptop | Keeping the Chromebook awake |
| Infrastructure | Terraform from Cloud Shell or a `main`-bound environment | Undocumented click-ops |

## 14. Historical development data and prospective capture (reconciled with PMV policy)

**What is settled.**
- Historical observations that are validly acquired (A-1 to A-8) and formally released as development-only (H-2) are development data. Prospective formation (H-1, `docs/phase2.md` "The split") makes all admissible data before `T0 − m` development data, historical and captured alike.
- Once exposed or released for development, a historical observation can **never** become protected holdout (CLAUDE.md "Holdout Protection").
- Prospective capture should begin early because it gives:
  - receipt-time truth;
  - the only future protected evaluation data;
  - execution-realistic data with live books;
  - statistical power in the receipt-time tier.
- **It does not invalidate the historical-development path.** The Statistician's "capture as step 1" (S-B9C-05) concerns scheduling and power, not admissibility.

**What the current Phase 2 working design says about selection** (`docs/phase2.md`, "A cycle's development data may mix historical archive rows and PMV-captured rows (S-9)").
- S-9 is a working-design rule, not an owner-adopted requirement. `docs/phase2.md` is a working design, and S-9 carries no "adopted" tag. Batch 4 recorded B4S-4 only as a clarification. B4S-4 itself said that archive-based audit-candidate selection "should be an explicit owner decision".
- The general rule: "Any validation result used for selection (features, model family, hyperparameters, calibration, thresholds, policy) is computed on `RECEIPT` + `PIT_CAPTURED` rows only. Archive-validated folds are discovery only."
- The narrower clause: "the comparison that selects among candidate features, model families, hyperparameters, calibration, thresholds, or policy for the audit candidate is computed on `RECEIPT` + `PIT_CAPTURED` folds".
- Historical (`SYNTHETIC_ARCHIVE`, `POST_HOC`) rows may be used in training, pilot models, and historical predictive studies, and to generate hypotheses, which are logged as degrees of freedom.
- Archive rows stay in the candidate's training set only if a preregistered ablation shows improvement on receipt-validated folds. After-cost EV claims rest on `RECEIPT` rows with live books.

**Interpretation to confirm.** The owner's direction of 2026-10-18 says: "Historical observations that are validly acquired and formally released as development-only may be used for development/model selection."
- **Development-stage reading:** "model selection" means exploration, pilot-model choice, and narrowing candidate families. Each choice carried forward is logged. Under this reading the direction fits within S-9.
- **Audit-candidate reading:** it also covers the comparison that decides the audit candidate's features, family, hyperparameters, calibration, thresholds, or policy. Under this reading it departs from S-9.

This is owner decision D-B09-20. The options:
- **(a) Keep S-9.** Archive results may screen and narrow candidates as logged hypotheses. They do not decide what enters the audit candidate, which is decided on receipt-time folds. Archive screening that drops candidates before the receipt-time comparison is a selection funnel, controlled through the experiment ledger.
  - *Cost:* calendar time. A powered receipt-time comparison needs enough pre-`T0` capture.
- **(b) Amend S-9** so that archive-validated folds may decide the audit candidate under stated conditions.
  - *Risk:* this does not endanger holdout integrity, because the prospective holdout stays the confirmatory test. The risk is economic: picking a candidate that looks good only because of archive artifacts (the timing artifact, POST_HOC leakage, survivorship), which then fails and consumes a prospective holdout cycle.
- **(c) Middle option.** Archive-validated selection is allowed only when receipt-time folds are underpowered, and only if:
  - a preregistered receipt-time non-inferiority check passes (the chosen candidate is not significantly worse than the runner-up on receipt folds);
  - the overlap-window artifact bound is stated.

The development Statistician, who wrote S-9, recommends (a). The data domain and calendar time are confounded: archive rows are older and receipt rows newer. **Separation of duties:** S-9 is part of the Gate 2 split and validation design, which the Independent Statistical Auditor must review (START_HERE.md Gate 2; H-6). D-B09-20 is decided before the first development release, so that choosing the rule does not itself become a degree of freedom.

Under every option, historical data is acquired, released, and used for development from the first release onward. Released rows carry `availability_class` and `metadata_pit_class`, which every option needs.

## 15. What this design could not verify

- Every SECONDARY cloud fact: deny-policy permission names and coverage, service-agent exceptions, VPC-SC prerequisites, Batch and Cloud Run behavior, GPU availability, soft-delete defaults, and lifecycle conditions.
- Per-source licence permission for third-party cloud storage (A-2), and per-source cloud-IP reachability.
- Venue hosting regions, key scopes, and connection limits.

## 16. Staged roadmap

| Stage | Content | Required controls (§2) | Rough effort |
|---|---|---|---|
| CLOUD-0 | Owner: billing account upgraded, budget, region confirmation, administration from Cloud Shell or a separate browser profile, credential rule adopted | A2, A4, A13 prerequisites | Days |
| CLOUD-1 (first implementation batch) | Terraform for `pmv-ops`, `pmv-vault`, `pmv-dev`; buckets with A8/A11 settings; per-stage service accounts; IAM deny (A7) and launcher identities (A16); audit logs and restricted log bucket (A10); dev and vault network egress (A17); AI-assistant API off (A18); Artifact Registry; Secret Manager containers; budgets; WIF with `main`-only environments. Red-Team review of the IAM model before any data | Delivers A2–A8, A10, A11, A13, A15–A18. A1 is an owner decision and governance edit; A9, A12, and A14 come in CLOUD-2/3 (RT-B9C2-08) | 1–2 weeks |
| CLOUD-2 | Sealed-object uploader, per-writer journals and sealer, B07 pipeline on Batch/VM, per-source rate limiter, A-3 cloud backup with a synthetic restore test into a vault-class bucket. Synthetic data only. Red-Team review | A8–A10, A14 | 2–3 weeks |
| CLOUD-3 | First cloud-to-cloud historical acquisition for whichever source's licence clears first (master inventory §7) | All of §2.1 plus A-1 to A-6 for that source | About 1 week |
| CLOUD-4 | Venue connector and capture VM image (synthetic and fixture tests), then live capture of licensed feeds | §2.3 B6–B8 | 2–3 weeks, plus licence and credential decisions |
| CLOUD-5 | H-2 release job; first released development rows | §2.2 | Gated by H-2 and cycle registration |
| CLOUD-6 | Feature library, fold loader, Batch template, ledger ingest, baselines. Built on synthetic data in parallel from CLOUD-1, run on released data after CLOUD-5 | §2.2 R5–R7 | 2–4 weeks |
| CLOUD-7 | GPU training on Batch Spot, only if baselines justify it | — | — |
| Stage B | Organization (if feasible), VPC-SC, organization policies, administrator separation, backup parity, telemetry coarsening | §2.3 B1–B5 | Before `T0 − m` |
| CLOUD-8 | Protected-evaluation path | §2.4 | Gate 6 path |
| CLOUD-9 | `pmv-runtime`: shadow, then live | §2.5 | Phase 11–12 |

The first real experiment is realistically about 3–4 months away (ML Engineer estimate). The governance track (licences, H-2, cycle registration) decides the date.

The proposed kill and spend gates K1–K4 (decision record) decide whether paid data and later stages happen at all.
