# Historical Acquisition Readiness Tooling (Phase 1, B06)

This document describes the source-neutral tooling for the historical acquisition gate in `docs/external_access.md` §2. It was built and tested only with synthetic data:
- no real dataset has been acquired;
- no market-data or trading host has been contacted;
- no real observation has passed through this code.

Code: `src/pmv/acquisition/`. Tests: `tests/unit/test_acquisition_*.py`, plus `tests/failure_injection/test_acquisition_faults.py` and `test_acquisition_review_regressions.py`. Review: `research/governance/b06_acquisition_tooling_red_team_review.md`.

**This tooling does not satisfy the acquisition gate by itself.** It is a set of deterministic, fail-closed building blocks. Every condition in §2 still needs its own owner record, and the gaps listed below must be closed first.

## What exists

| Gate item | Module | What it enforces |
|---|---|---|
| A-1 hosts and prefixes; §1.1 rules 1 and 8 | `hosts.py` | Each approval gets an exact `https` host and path-prefix allowlist. Refused outright: user information, queries, fragments, percent-encoding, `;`, dot segments, IP literals, and IDNA. A restricted host needs an owner decision for that exact host and prefix. Restricted hosts are those with a label (the first, or any left of the registrable domain) containing `api`, `stream`, `ws`, `feed`, `quote`, `ticker`, `price`, `marketdata`, `rpc`, or `md`, or starting with `clob`, `data`, `assets`, or `trad`. Every subdomain of a named venue, settlement-reference, chain-explorer, or RPC-provider domain is also restricted. The same applies to a restricted path (case-insensitive) (`/api/`, `/v<n>/`, `/graphql`, `/ws`, `/stream`, `.json`, `.jsonl`, `.ndjson`, `.csv`). |
| A-1, A-2, A-5, A-6 records | `records.py` | Approval, licence, acquisition-manifest, and source-quality records with exact key sets and no coercion. Unknown counts as no. A paid or credentialed acquisition needs a separate decision. Licence lineage is required. The tool tree must be clean. Non-primary sources need their mirror lineage, and non-Q1 sources need a reconciliation primary. Copies of one upstream count once. `acquisition_gate_failures` lists unmet gate conditions; `manifest_gate_failures` cross-checks a manifest against its approval. |
| A-4 formats | `formats.py` | Only CSV, JSON, JSONL, Parquet, DBN, and text are allowed. The declared format, extension, and content signatures must agree. Pickle, NumPy, zip, executables, scripts, compressed streams, PDF, SQLite, and similar files are refused. Text files are validated in full (`check_text_stream`). |
| A-4 strict parsing | `strict_parse.py` | Strict UTF-8, with `Decimal` instead of `float`. Refused: NaN and Infinity, duplicate keys, out-of-range exponents and integers, lone surrogates, excessive depth, ragged CSV, padded or duplicate headers, and bare CR. Default caps are 4 MiB per document and 1 MiB per JSONL line (`iter_jsonl`). |
| A-4 archives | `archive.py` | Tar (plain, gz, bz2, xz) and zip only, never `extractall`. Tar is read by one project-owned header walker, not `tarfile`. It runs a validation pass and an extraction pass bound by the raw-archive SHA-256. It requires ustar checksums, zero padding, and allowlisted pax keys, caps metadata headers, and refuses corrupt, truncated, or trailing-data archives. Links, devices, sparse members, and encrypted members are refused, as are traversal and case collisions. Limits cover member count, size, total, depth, and ratio. A free-disk precheck runs first. Any failure rolls back everything written. Every extracted file is format-checked. |
| A-4, A-5 quarantine | `quarantine.py` | An empty quarantine directory is required. Files are hashed on receipt. Release copies through one descriptor while hashing, verifies against the receipt and the manifest, format-checks the copy, then renames it without overwriting. A failure leaves the file in quarantine. |
| A-3 verification | `backup.py` | Backup copy and restore are verified against the manifest SHA-256 and size. Every file is reported as verified, mismatched, missing, or unexpected. Source, backup, and restore directories must be disjoint. The module also generates deterministic synthetic same-format CSV and JSONL fixtures. |

The A-4 fault-injection fixtures named in §2 are all built at test time, in temporary directories. No hostile file is committed. They cover:
- a path-traversal tar;
- symlink and hardlink tars;
- a decompression bomb of at least 1000:1;
- pickle disguised as Parquet;
- a remote-path manifest;
- NaN and duplicate-key JSON;
- a full disk.

## Review status

The Reliability / Red-Team review ran three rounds on 2026-10-16 (`research/governance/b06_acquisition_tooling_red_team_review.md`). Round 3 verdict: **no unresolved BLOCKING finding in the reviewed code**, for the committed B06 state only. Any later change to `src/pmv/acquisition/` needs a fresh review. This is not A-4 passing and not permission to acquire.

Open MINOR findings, to fix in the next tooling batch:
- **RT-B6-08.** Content that resembles pickle or a notebook inside a text or `PAR1` wrapper passes signature sniffing. It is inert while nothing deserializes it; pinned readers (G-2) close it.
- **RT-B6-19.** The writing pass does not re-apply the size budget, so a file swapped between passes is written in full before the hash mismatch rolls it back.
- **RT-B6-20.** bz2 and xz ignore junk after the last compressed stream. The junk is covered by the archive hash and never extracted.
- **RT-B6-21.** A pax path together with a GNU long name, duplicate pax `path` keys, and GNU-format prefix fields resolve names in a way other tar tools may not. Every name still passes the name check.
- **RT-B6-22.** The verified partial file is renamed by name within the destination.

## Still missing before A-4 can pass

From the Red-Team review (G-1 to G-7):
1. **Process isolation for parsing (G-1).** Parsing must run in a separate process with no network, no access to `~/pmv-credentials`, `~/.ssh`, or `.git`, and with memory and CPU limits. The in-process caps above are defense in depth, not a substitute.
2. **Pinned readers (G-2, G-3, G-5).** Parquet and DBN content is only signature-checked today. Reading it needs pinned, patched, hash-locked, individually reviewed reader dependencies that never resolve remote paths. Compressed single files (`.csv.gz`, `.dbn.zst`) have no supported path yet.
3. **Fetcher (G-4).** No network fetcher exists. It needs per-redirect re-checks against the allowlist, no cross-host redirects, a download size cap, and a free-disk check at intake.
4. **End-to-end pipeline (G-6).** Fetch, quarantine, verify, and write to the protected raw store (A-7), by a tool running outside agent sessions, with persisted receipts.
5. **Owner inputs (G-7).** These are the backup policy and a restore test on the real backup medium (A-3), committed F-09 denies, and the per-source records (A-1, A-2, A-5, A-6).
6. **Provider checksums.** Where a provider publishes checksums, the manifest hash must come from them. Otherwise the receipt hash only proves that the bytes did not change after intake.

## Recovery

All of this is deterministic code in Git. It holds no state. Recovery is the standard repository recovery (`docs/backup_and_recovery.md`). Quarantine and restore directories are working areas: after an interruption they are discarded and the acquisition re-run from the provider, or, where `reproducible_from_provider` is not `yes`, from the verified backup.
