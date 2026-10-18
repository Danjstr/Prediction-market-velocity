# PMV cloud cost model (B09, 2026-10-18)

**Status:** an order-of-magnitude planning estimate, not a quote or a budget approval. No resource exists. Every unit price is **SECONDARY**: web-search summaries retrieved 2026-10-18, some of which cite the official pricing URL. The official pricing pages are refused by the container's network allowlist, so nothing below is VERIFIED-BY-FETCH. Each price is re-checked on the official page (§6) before the owner commits. Architecture: `research/cloud/pmv_cloud_architecture_review.md`.

Prices are in USD, list price, GCP `us-central1` unless stated, before taxes and before any committed-use discount. GB and GiB are not distinguished here: the difference (7%) is below the accuracy of this model.

**Confidence labels** (H, M, L) describe agreement between SECONDARY sources. They are not verification: an H price is still unverified until checked on the official page.

## 1. Unit prices used (SECONDARY)

| Item | Price | Confidence |
|---|---|---|
| GCS Standard, regional | $0.020 / GB-month | M |
| GCS Nearline / Coldline / Archive, regional | $0.010 / $0.004 / $0.0012 per GB-month; minimum durations 30 / 90 / 365 days; retrieval $0.01 / $0.02 / $0.05 per GB | M |
| GCS Class A / Class B operations | $0.005 / $0.0004 per 1,000 | H |
| GCS soft delete | On by default, 7 days, billed at the storage-class rate | H |
| Inter-region transfer inside North America | $0.02 / GB | M |
| Internet egress (Premium tier, North America) | $0.12 / GB for the first TB; 100 GB/month free from GCS | M |
| BigQuery on-demand queries | $6.25 / TiB scanned; first 1 TiB per month free | H |
| BigQuery storage (logical) | $0.023 / GB-month active; $0.016 long-term | H |
| Cloud Run (instance billing) | $0.000018 per vCPU-second; $0.000002 per GiB-second; free 240k vCPU-s and 450k GiB-s per month per billing account | M |
| Compute Engine e2-medium (2 vCPU, 4 GB) | about $0.034/h on demand (about $24/month) | M |
| Balanced persistent disk | about $0.10 / GB-month (session estimate; not in the research summary) | L |
| L4 GPU (G2 machine, one GPU) | about $0.70–0.85/h on demand for the machine; Spot roughly 40–60% lower (varies) | M (L for Spot) |
| A100 40 GB (a2-highgpu-1g, whole VM) | $3.67/h on demand; Spot about $1.80/h | M |
| Vertex AI custom training (not adopted; for comparison) | Compute price plus a management fee of roughly 10–15% that gets no Spot discount | L–M |
| GCP Batch | No service fee; underlying Compute Engine VMs, Spot, and GPUs are billed | H |
| Cloud NAT | Per-gateway or per-VM hourly charge plus about $0.045/GB processed (session and reviewer recollection; unverified) | L |
| Static external IPv4 address | A few dollars per month each (unverified) | L |
| Cloud Logging | $0.50 / GiB ingested beyond 50 GiB per project per month | M–H |
| Secret Manager | $0.06 per active secret version per month | H |
| Artifact Registry | $0.10 / GB-month beyond 0.5 GB | H |
| Cloud Scheduler | $0.10 per job per month, 3 free | H |
| Cloud Composer 3 (for comparison) | about $350–400/month idle | M |

## 2. Storage

Assumptions:
- raw is append-only, so soft delete and versioning add almost nothing;
- normalized Parquet is about 0.3–1.0 × raw size (JSON compresses well; DBN and zstd are already compact). 0.6 × raw is used here;
- features are about 0.3 × raw;
- the backup copy of vault raw is in a second region, in Coldline, because it is written once and read only for restore tests and disaster recovery;
- operations: raw written as files of at least several MB, so operation charges stay small. Writing one object per API page or per tick would change that (§5).

| Monthly, steady state | 100 GB raw | 1 TB raw | 5 TB raw |
|---|---|---|---|
| Vault raw (Standard) | $2 | $20 | $100 |
| Normalized (0.6×, Standard; vault and dev copies of released data overlap, so 1× is used for both together) | $1.20 | $12 | $60 |
| Features and fold shards (0.3×) | $0.60 | $6 | $30 |
| Backup of vault raw (Coldline, second region) | $0.40 | $4 | $20 |
| Model artifacts, images, Terraform state, logs bucket | about $1 | about $2 | about $5 |
| **Storage subtotal** | **about $5** | **about $44** | **about $215** |
| One-time: copy raw to the backup region ($0.02/GB) | $2 | $20 | $100 |
| One-time: full restore test from Coldline (retrieval $0.02/GB plus transfer $0.02/GB) | $4 | $40 | $200 |

A full restore test is not needed every time. The A-3 restore test can be a representative sample (a size-class test), with a full restore drill once a year.

## 3. Compute

### 3.1 Ingestion

| Workload | Estimate |
|---|---|
| Historical pulls: Cloud Run Job, 2 vCPU / 4 GiB, 20 task-hours per month | 144k vCPU-s and 288k GiB-s: inside the free tier, otherwise about $3 |
| A one-off large vendor download (1 TB through a job) | Compute under $5. Inbound transfer is free |
| Prospective capture: 2 × e2-medium collectors in two zones, plus 2 × 20 GB disks | about $48 + $4 = **about $52 per month per collector pair**. One pair can carry several feeds; Kalshi and Polymarket in different regions mean two pairs (about $104) |
| Capture upload to the home region, 5 GB/day | 150 GB/month × $0.02 = $3 |

### 3.2 Training (per run)

| Example | Shape | Estimate |
|---|---|---|
| CPU baseline (logistic plus GBM walk-forward, 2 h) | Cloud Run Job, 8 vCPU / 32 GiB: about $0.75/h | **about $1.50** |
| Modest single-GPU experiment (2 h) | One L4 on Batch, on demand | **about $1.50–2**, plus billed image-pull and startup minutes |
| Several-hour deep-learning run (8 h) | One L4: on demand about $6–7, Spot about $3. One A100 40 GB: on demand about $29, Spot about $15 | **$3–30**, depending on the GPU |
| Repeated hyperparameter search, small | 50 trials × 1 h on Spot L4 | **about $15–25** |
| Repeated hyperparameter search, careless | 200 trials × 2 h on on-demand A100 | **about $1,470**. This is the trap the budget and quotas exist for |

### 3.3 Analysis and operations

| Item | Light use | Heavy use |
|---|---|---|
| BigQuery queries | 1–2 TiB/month: $0–6 | 20 TiB/month: about $120 |
| BigQuery storage (metadata and ledgers, under 50 GB) | under $1 | under $2 |
| Cloud Logging (value-free logs; Data Access audit logs for the vault only) | inside the 50 GiB free tier | $10–50 if Data Access logging is enabled on high-read buckets |
| Secret Manager (about 10 secrets) | $0.60 | $1 |
| Artifact Registry (about 5–20 GB of images) | $0.50 | $2 |
| Scheduler, Workflows | under $1 | under $2 |
| Monitoring | inside the free tier | a few dollars |
| Internet egress (reports to the Chromebook) | inside the 100 GB free tier | inside the free tier |
| Cloud NAT and static addresses (ingestion and capture egress control) | about $5–15 | about $20–40 |
| Artifact Registry growth (GPU images of 5–10 GB each if one is kept per commit) | controlled by a cleanup policy that keeps ledger-referenced digests | $5–20 without cleanup |

## 4. Monthly scenarios

| Scenario | Content | Rough monthly cost |
|---|---|---|
| **S. Bootstrap** | 100 GB raw, historical only, CPU baselines weekly, light BigQuery, no capture | **about $10–20** |
| **M. Working project** | 1 TB raw, one Kalshi collector pair (dedicated-core machines), CPU training most days, a few GPU experiments, light metadata queries | storage $44 + capture $70 + training $40 + queries $5 + NAT/addresses $15 + operations $5 = **about $180** |
| **L. Full development** | 5 TB raw, two collector pairs, regular GPU runs and one preregistered HP search a month, heavy queries | storage $215 + capture $140 + training $150 + queries $60 + NAT/addresses $30 + operations and logs $30 = **about $600–700** |

Capture assumes dedicated-core machines rather than shared-core e2 (Data/API review DA-B9C-19), roughly $30–35 per collector per month (unverified). A second collector pair (Polymarket) is budgeted only if Polymarket is explicitly in scope after F-16.

**Data purchases dominate cloud costs.** One month of a paid order-book archive or of CME futures depth can cost more than several months of scenario M infrastructure. Vendor costs are in the master inventory, and they belong in the business case, not in the cloud budget alone.

## 5. Cost traps and controls

| Trap | Control |
|---|---|
| Budgets notify; they do not cap spend, and billing data lags by hours | Budget alerts at 50 / 90 / 100 / 150% of a monthly budget per project. Hard limiters are quotas: GPU quota per region (keep it at 1 GPU until needed), BigQuery `QueryUsagePerDay` and per-user custom quotas (for example 2 TiB/day, far below the 200 TiB/day default), Cloud Run max instances |
| The disable-billing "kill switch" stops everything, including capture | Use it only on `pmv-dev` (training and analysis), never on `pmv-vault` capture. Capture gets alerts, not a kill switch. The kill-switch identity is scoped by IAM to `pmv-dev` only, and frozen Gate 6 artifacts live outside the project it can disable |
| Forgotten GPU VMs and disks | Training runs as Batch jobs that end themselves, never as interactive VMs. A daily job lists running GPU resources and alerts |
| Soft delete and versioning on churny buckets | Scratch and fold-shard buckets: soft delete 0, no versioning, lifecycle delete after N days. Keep protection on raw and artifacts only |
| Millions of tiny objects (one per API page or per message) | Batch pages into files of several MB per object, or into PMV's segment format. Class A writes cost $5 per million |
| Cold storage classes for data that is reread | Standard for anything training or normalization reads. Coldline only for the backup copy |
| `SELECT *` over external Parquet; byte caps may not bind on external tables | Hive-partitioned layouts, explicit column lists, custom daily quotas as the real cap. Test the cap behavior on synthetic data at CLOUD-5 |
| Cross-region compute | Training in the home region next to the data. Copy only the fold shards if another region must be used |
| Data Access audit logs on high-read buckets | Enable them on `pmv-vault` (low read volume, high value), not on dev fold shards |
| Composer, GKE, always-on services | Not used. Scheduler plus Workflows cost cents |
| Free trial | No GPUs and no quota increases on the trial. Upgrade the billing account before GPU work. GPU quota requests on new accounts can take days or be refused |
| Bucket Lock | Irreversible: storage of locked data cannot be stopped until retention expires. Not used now |
| Large HP searches | A preregistered search budget (trials × hours) is part of the experiment design and is also a statistical control |

## 5a. Break-even framework (proposal; inputs not yet measured)

The cloud costs above are small next to data subscriptions and owner time. Whether any spend is justified depends on capacity and edge, which are unknown until the go/no-go milestone (decision record, proposed K2) measures them. The framework, to be filled from free Kalshi history:

| Input | Source | Status |
|---|---|---|
| Fixed monthly cost by tier (cloud scenario; each data subscription; amortized one-off purchases) | This model; master inventory | Estimates |
| Executable late-window volume per day at the candidate price band, after the strategy's own filters | Free Kalshi trades and 1-minute candles (PM-01) | Unmeasured |
| Net edge per contract after fees, spread, slippage, and latency | Go/no-go analysis | Unmeasured |
| Fill rate and capital turnover (about $0.85–0.97 at risk per contract, recycled every 15–60 minutes) | Go/no-go analysis | Unmeasured |
| Tax scenarios (pre-tax and tax-adjusted, CLAUDE.md "Economics") | Owner-supplied assumptions | Not set |

Required monthly net profit to carry a fixed cost `C` at net edge `e` per contract is `C / e` contracts. For illustration only, not data: carrying $3,500 per month of gold reference data at 1¢ net edge needs about 350,000 contracts per month (Business Lead review BIZ-B9C-04). Owner engineering time is the largest unpriced cost.

**Recommended starting budget:** about $100/month across all projects for CLOUD-1 to CLOUD-3 (scenario S plus slack), raised by owner decision when capture or GPU work starts. Paid data is budgeted separately, per purchase (A-1).

## 6. Re-verify before committing

From the official pages, once reachable (owner, or a later session with those hosts allowlisted):
1. GCS regional prices in the chosen regions, soft-delete defaults, and the 2026 multi-region changes.
2. Inter-region and internet egress rates.
3. Cloud Run Jobs billing mode, rates, limits (168 h task maximum; 1 h with a GPU), and the launch stage of GPU support for Jobs.
4. GPU prices, Spot prices, zone availability, and actual quota grants in the chosen region (`gcloud compute accelerator-types list`).
5. Batch Spot support and pricing for the chosen machine and GPU shape (and the Vertex management fee, only if Vertex is ever reconsidered).
6. BigQuery prices and `maximum_bytes_billed` behavior on external tables.
7. Logging and Monitoring prices, including the postponed alerting charges.
8. Free-trial restrictions at the time of sign-up.
