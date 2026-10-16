# Historical Acquisition Readiness Tooling (Phase 1; B06 and B07)

This document describes the source-neutral tooling for the historical acquisition gate in `docs/external_access.md` §2. It was built and tested with synthetic data only:
- no real dataset has been acquired;
- no market-data, venue, vendor, or trading host has been contacted;
- no real observation has passed through this code.

Code: `src/pmv/acquisition/`.

Tests:
- `tests/unit/test_acquisition_*.py`;
- `tests/failure_injection/test_acquisition_*.py`;
- `tests/integration/test_acquisition_pipeline.py`.

Reviews:
- `research/governance/b06_acquisition_tooling_red_team_review.md` (B06, rounds 1 to 4b);
- `research/governance/b07_acquisition_pipeline_red_team_review.md` (B07).

Decision record: `docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md`.

**This tooling does not satisfy the acquisition gate by itself, and acquisition is not authorized.** It is a set of deterministic, fail-closed building blocks and a pipeline that composes them. Every condition in §2 still needs its own owner record, and the gaps listed under "Remaining A-4 gaps" must close first.

## What exists

| Gate item | Module | What it enforces |
|---|---|---|
| A-1 hosts and prefixes; §1.1 rules 1 and 8 | `hosts.py` (B06) | Each approval gets an exact `https` host and path-prefix allowlist. Refused outright: user information, queries, fragments, percent-encoding, `;`, dot segments, IP literals, and IDNA. A host is restricted if any of these holds: <ul><li>a label (the first, or any left of the registrable domain) contains `api`, `stream`, `ws`, `feed`, `quote`, `ticker`, `price`, `marketdata`, `rpc`, or `md`;</li><li>a label starts with `clob`, `data`, `assets`, or `trad`;</li><li>it is under a named venue, settlement-reference, chain-explorer, or RPC-provider domain.</li></ul>A path is restricted if it contains `/api/`, `/v<n>/`, `/graphql`, `/ws`, or `/stream`, or ends in `.json`, `.jsonl`, `.ndjson`, or `.csv` (case-insensitive). A restricted host or path needs an owner decision for that exact host and prefix. |
| A-1, A-2, A-5, A-6 records | `records.py` (B06) | Approval, licence, acquisition-manifest, and source-quality records, with exact key sets and no coercion. Unknown counts as no. Licence lineage is required. |
| A-1, A-3, A-4, A-5 plan and evidence | `plan.py` (B07) | The acquisition plan: every file's URL, kind, format, compression, required expected schema, size cap, and, where the provider publishes them, its size and SHA-256. An archive also lists its expected members. Also parsed: A-3 backup-policy and restore-test records, A-4 review records, and the authorizing-bundle hash that every journal entry is bound to. |
| A-4 formats | `formats.py` (B06) | Only CSV, JSON, JSONL, Parquet, DBN, and text are allowed. The declared format, extension, and content signature must agree. Executable and serialized-object formats are refused. |
| A-4 readers (G-2, G-3, G-5) | `readers.py` (B07) | One registered reader per format, with a pinned identity (name, version, implementation, registry version) recorded in provenance. <ul><li>CSV, JSON, JSONL, and text use project code on the standard library only: streaming, bounded lines, a required expected schema, and checked value types.</li><li>gzip, bzip2, and xz single files are decoded strictly (xz container only, with a decoder memory limit) under size and ratio caps.</li><li>**Parquet, DBN, and zstd are not adopted and are refused** (governed deferral below).</li></ul> |
| A-4 strict parsing | `strict_parse.py` (B06) | Strict UTF-8 and `Decimal`. Refused: NaN and Infinity, duplicate keys, out-of-range numbers, lone surrogates, excessive depth, ragged CSV, padded or duplicate headers, and bare CR. |
| A-4 archives | `archive.py` (B06) | Tar (plain, gz, bz2, xz) through one project-owned header walker, and zip. Refused: links, devices, traversal, case collisions, corrupt, truncated, or trailing-data archives, and archives over the bomb limits. B07 added only fd-based entry points for the worker. |
| A-4 isolation (G-1) | `confinement.py`, `worker_protocol.py`, `parse_worker.py`, `isolation.py` (B07) | All untrusted parsing and extraction runs in a separate worker process (details below). |
| A-1, A-4 fetch (G-4) | `fetch.py` (B07) | Fetching runs behind an injectable `Transport`. **No production transport exists** (details below). |
| A-4, A-5 quarantine and receipts | `quarantine.py`, `receipts.py` (B06; extended in B07) | <ul><li>Hash-on-receipt intake.</li><li>`O_TMPFILE` and `linkat` release, which never names an unverified copy.</li><li>Directory fsyncs in order (RT-B6-28).</li><li>A durable, append-only, hash-chained journal.</li><li>B07 v2 entries bind each event to an `acquisition_id` and the SHA-256 of its authorizing bundle, with a closed detail schema per event (RT-B6-27).</li><li>Owner-attested torn-tail recovery (RT-B6-26 d).</li><li>B06 `Quarantine.receive` no longer leaves a partial file when its source fails.</li></ul> |
| A-3 verification | `backup.py` (B06) | Backup copy and restore verified against SHA-256 and size. It proves the mechanism only; real A-3 evidence needs the owner's policy and real medium. |
| G-6 state machine | `state.py` (B07) | Explicit states, replayed from the journal (below). There is no state, event, or transition that makes a row agent-visible. |
| G-6, A-7 pipeline | `pipeline.py` (B07) | The orchestrator (below). |
| Synthetic dry runs | `synthetic.py` (B07) | A scripted transport and synthetic records (all `synthetic_`, reserved `.example` hosts, placeholder decision paths). They are accepted only in synthetic mode. |

### Isolation (G-1)

**What the parent sets up:**
- **Resource limits, before exec:** address space, CPU seconds, file size 0 (no regular file can be written), descriptor count, and no core dumps.
- **Launch:** the worker starts with `python -I`, an empty environment, `/` as its working directory, and a new session.
- **Descriptors:** exactly three — the input, opened read-only by the parent; the output pipe; and `/dev/null`. The worker is never given a path.

**What the worker does before reading any input:**
1. Imports every module it can use, and runs a warm-up on built-in synthetic bytes.
2. Confirms the limits are in force.
3. Sets `no_new_privs` and installs a seccomp **allowlist** (RT-B7-01). Only these run:
   - reading, seeking, and `fstat` on its descriptors, and writing;
   - memory management, `futex`, signal masks on itself, clocks, `getrandom`, `close`, and exit;
   - `fcntl` only for `F_GETFD`, `F_SETFD`, `F_GETFL`, and `F_DUPFD_CLOEXEC`;
   - `ioctl` only for `TCGETS`, `FIOCLEX`, and `FIONCLEX`.

   Every other call fails with EPERM. That includes:
   - any file open or change, any socket, `exec`, `fork`, `clone`, `io_uring`, and `ptrace`;
   - signals, resource limits, scheduling, or I/O priority aimed at any process, the parent included (`kill`, `prlimit64`, `setpriority`, `sched_set*`, `ioprio_set`, `F_SETOWN`, `F_SETSIG`, `O_ASYNC`);
   - inotify, `syslog`, SysV IPC, and extended attributes.

   Any architecture other than x86-64, and the x32 ABI, kills the process. The worker's syscall set was established by running every operation under a diagnostic build of the filter.

The parent also hardens itself before launching a worker: no core dumps, and not dumpable. A disturbed parent therefore cannot write protected plaintext to disk.

**What the parent enforces on the output:**
- a versioned framed protocol: magic, then `HELLO` with the protocol, version, `confined: true`, and the code identity (source SHA-256s of every worker module, the Python version, and reader identities);
- payload and output caps;
- a single final `RESULT`, with no trailing or truncated output;
- exit status 0;
- a wall-clock deadline, after which the process group is killed.

Partial results are never accepted. Refusals are closed codes with a record number, never content. `verify_isolation` probes 28 denied calls in the real worker, including the cross-process ones. The worker identity also pins the interpreter binary and the site `.pth` startup hooks, and the parent checks it before acting on any frame.

**Archives.** The worker decompresses and walks the archive. The parent is the only writer, and it re-validates every name, limit, and member hash itself.

**Limits of this isolation (stated, not hidden):**
- `newfstatat` and `statx` are allowed because the C library implements `fstat` with them. Given a path, they reveal metadata (existence, size, times, owner), never content.
- There is no network namespace: network isolation rests on every socket call being denied.
- The worker runs as the same user as the parent.
- Linux x86-64 only: elsewhere parsing refuses.
- The worker reports the hash of what it read. The parent checks it, but that is a consistency check. The stored bytes are protected by the parent's own hashes (RT-B7-10).

### Fetch (G-4)

The fetcher (`fetch.py`):
- checks the exact allowlist before any request;
- re-classifies every redirect from scratch and refuses it before a second request if it leaves scope or the host, loops, or exceeds the redirect count;
- sends a credential header only on the first hop and only to its host;
- accepts status 200 only, with identity content encoding, a required plain `Content-Length`, the size cap, the expected size and provider SHA-256, a deadline across chunks, and a free-disk precheck;
- treats every transport outcome outside the transport's contract as a failure;
- writes the body into an unnamed `O_TMPFILE` inode, named with `linkat` only after every check passes, so a partial file never has a name.

**No production transport exists**, so the fetcher cannot reach the network.

### States (G-6)

Each planned file moves only along these transitions:

`approved_for_fetch` → `received` → `integrity_verified` → `parser_verified` → `backup_verified` → `stored`

Also allowed: `fetch_failed` and retry, `rejected`, and `discarded` for unjournaled bytes set aside. Replay fails closed on a different authorizing bundle, an illegal transition such as a duplicate receipt, a file not in the plan, or anything after `completed`.

### The pipeline (G-6, A-7)

**Before any transport,** the pipeline validates every machine-checkable prerequisite. Any absent, malformed, inconsistent, or stale prerequisite refuses the run:
- A-1 to A-6 consistency;
- an allowlisted URL for every planned file;
- an adopted reader for every planned format;
- restore-test coverage under the backup policy;
- an A-4 review record with no BLOCKING or MAJOR finding;
- no credential;
- the mode rules (decision record B7-8);
- a passing isolation self-test.

**Mode rules.** A real-mode run also needs a reviewed production transport, which does not exist, so it **always refuses today**. The caller cannot override this: the transport registry is a code constant (empty), and Git facts are read from the tool's own checkout, never from an injected repository (RT-B7-02).

**Storage.** The pipeline stores exactly the received bytes, 0400, in `<store_root>/acquisitions/v1/store/<source_id>/<acquisition_id>/`. That directory is sealed 0500, with a canonical `acquisition.json` provenance record. The record holds:
- the binding hash and per-document hashes;
- the tool commit and worker identity;
- per-file URL, final URL, sizes, hashes, hash source, and retrieval time;
- verification summaries (counts and hashes only);
- backup evidence.

Scratch plaintext lives under the same root and is deleted after verification. Nothing is written for agents. The caller gets a report of states, closed codes, sizes, and hashes only.

**Recovery.** An interrupted run resumes from the journal. The pipeline never replaces an accepted artifact or record.

The A-4 fault-injection fixtures named in §2 are all built at test time in temporary directories, and no hostile file is committed:
- a path-traversal tar;
- symlink and hardlink tars;
- a decompression bomb of at least 1000:1;
- pickle disguised as Parquet;
- a remote-path manifest;
- NaN and duplicate-key JSON;
- a full disk.

B07 added fault injection for:
- every G-1 worker failure: timeout, crash, signal, CPU limit, file-size limit, malformed, truncated, oversized, trailing, protocol or version mismatch, identity mismatch, not confined, and partial or lying extraction;
- every G-4 case in the charter;
- G-6 crashes at every durable boundary, including real `SIGKILL`s, conflicts, interrupted writes, tampering, and concurrency.

## Status of G-1 to G-7 (after B07)

| Gap | Status |
|---|---|
| G-1 isolated parsing | **Implemented** (B7-1). Its stated limits are in "Isolation" above. |
| G-2 pinned readers | **Partly.** CSV, JSON, JSONL, and text are adopted (stdlib only, pinned identities). **Parquet and DBN are deferred** pending owner approval of a dependency (B7-6). Until then they are refused. |
| G-3 dependency hash-lock and review | **Satisfied for the adopted readers**, which have no third-party dependency: `uv.lock` is unchanged, and the worker identity pins the source hashes and Python version. Open for any Parquet, DBN, or zstd dependency (B7-6). |
| G-4 fetcher | **Semantics implemented** with synthetic transports. **The production network transport is open:** TLS verification, DNS and IP pinning, refusal of private and link-local addresses, and its own review (B7-4). |
| G-5 compressed inputs, no remote paths | gzip, bzip2, and xz single files and archives are implemented and bounded. Readers never receive a path or URI: they read only the inherited descriptor. **zstd is deferred** (B7-6). |
| G-6 end-to-end pipeline | **Implemented** (pipeline, state machine, bound journal, recovery), on synthetic data. Real execution is blocked by G-4 (transport), G-7, and the per-source records. |
| G-7 owner inputs | **Open:** the A-3 backup policy and a restore test on the real backup medium; per-source A-1, A-2, A-5, and A-6. The F-09 denies are done (`8517fc2`). |

## Remaining A-4 gaps

1. **Parquet, DBN, and zstd readers.** These need owner approval of the dependency candidates in the B07 decision record, then pinning, review, and isolated integration. Until then those formats cannot be acquired.
2. **Production transport (G-4).** A separately reviewed network transport is needed. Until then real-mode runs refuse.
3. **A review that records A-4 as satisfied.** The B07 Red-Team verdict is in the review file. Even with no BLOCKING or MAJOR finding, A-4 is not satisfied while items 1 and 2 remain. A real run also requires an A-4 review record that says A-4 is satisfied, and an unchanged acquisition-code tree since that review.
4. **Provider checksums.** Where a provider publishes checksums, the plan must carry them (`provider_sha256`). Otherwise the receipt hash proves only that the bytes did not change after intake.
5. **Owner inputs (G-7).** Listed in the status table above.

## Agent release (H-2) is separate

Storage in the protected raw store makes nothing agent-visible (A-8). The H-2 per-row release tool is not built. Its properties and prerequisite chain are in `docs/release_tool_design.md`; it waits on the owner's E-U1 decision.

## Recovery runbook (RT-B6-26)

All of this is deterministic code in Git. The pipeline's only state is its journal and store, under the owner's store root. Repository recovery is the standard procedure in `docs/backup_and_recovery.md`.

| Situation | What happens | Owner action |
|---|---|---|
| Crash or kill during a pipeline run | The next run resumes from the last journaled state. A received file without its journal entry is moved to `orphans/<acquisition_id>/` and journaled as `discarded`, never deleted. Scratch plaintext is deleted. A store copy without its `stored` entry is accepted only if its bytes match the receipt. | Re-run the same acquisition. |
| Fetch failure | Journaled as `fetch_failed` with a closed code. The next run retries, once per run and at most `max_attempts` in total. | Re-run, or fix the cause. |
| Content refused (integrity, signature, parse, schema) | Journaled as `rejected`. The bytes move to `rejected/<acquisition_id>/`. The acquisition is terminal. | Inspect owner-side only. Start a new acquisition ID if appropriate. |
| Store or record conflict (a different file already at the target) | The run stops (`store_conflict_never_replaced` or `record_conflict_never_replaced`). Nothing is replaced. | Investigate as a possible integrity incident. |
| Backup or isolation environment failure, including a worker timeout, CPU limit, crash, or out-of-memory kill | The run stops. The state is kept, and nothing is rejected (RT-B7-04). | Fix the environment or raise the limits, and re-run. If a file keeps exhausting the worker, decide owner-side whether it is unacquirable. |
| Torn journal tail (crash mid-append) | The journal refuses to open. | Run `pmv.acquisition.receipts.recover_torn_tail(path, "docs/decisions/<record>.md", committed=GitRepository(repo).committed_unchanged)` with a committed owner record attesting the crash. If the recovery itself is interrupted, run it again: it completes from the preserved evidence file. The torn bytes are preserved in a read-only evidence file, and a `tail_recovered` entry is appended. A torn tail cannot be told apart from tampering by the bytes alone; the attestation is the owner's. |
| Journal reaches 64 MiB | Appends refuse (fail closed). Segmentation is not implemented. A synthetic single-file acquisition writes about 4.2 KB of journal (7 entries), so the cap is roughly 15,000 single-file acquisitions. | Start a new store root with an owner decision. Accepted residual. |
| B06 `Quarantine` session interrupted | That class is still session-scoped. Its quarantine is discarded, and the source is re-acquired. The journal keeps the earlier receipt. The pipeline does not use it. | As before. |

## Review status

- **B06 tooling.** Red-Team rounds 1 to 4b found no BLOCKING and no MAJOR finding in the B06 code. RT-B6-08 (G-2), RT-B6-26, RT-B6-27, and RT-B6-28 were carried into B07.
- **B07.** See `research/governance/b07_acquisition_pipeline_red_team_review.md` for the verdict, findings, and dispositions. Any later change to `src/pmv/acquisition/` needs a fresh review.
- **This is not A-4 passing and not permission to acquire.**
