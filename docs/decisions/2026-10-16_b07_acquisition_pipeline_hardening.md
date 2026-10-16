# B07: Phase 1 acquisition pipeline hardening (2026-10-16)

**Approver:** the project owner, in the B07 batch charter issued on 2026-10-16 in the isolated environment. The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

## Charter (summary of the owner's instructions)

- **Branch.**
  - Create `b07/phase1-acquisition-pipeline-hardening` directly from final B06 `c0d2a2b04e7ad3aee5d170aa21071d615bd5c318`, not from `main`. B06 was merged to `main` by PR #5 (`231432690b2a`).
  - B07 becomes the **current active ground-truth branch**; future B08 starts from final B07.
  - One branch, one eventual B07 → `main` pull request. Claude does not merge, does not delete B06, and creates no other branch.
- **Objective.** Continue Phase 1 by closing as much of the source-neutral A-4 gap as is safe with synthetic data only:
  - G-1: isolated untrusted-parser execution;
  - G-2, G-3, G-5: safe, pinned, bounded Parquet, DBN, and compressed handling;
  - G-4: deterministic fetcher semantics with redirect re-authorization, behind synthetic transports;
  - G-6: source-neutral end-to-end pipeline into quarantine and protected raw storage;
  - the remaining parts of RT-B6-26 and RT-B6-27, and an explicit re-review of the RT-B6-28 directory-fsync fix.
- **Prohibited.**
  - Real data or observations, and any market-data, venue, exchange, vendor, live-data, or trading host.
  - Credentials, accounts, or spending.
  - Approving a source or making a licence determination.
  - Gate 1 PASS, `T0`, or opening a holdout.
  - Modeling.
  - Choosing E-U1, implementing H-2 before its prerequisites, or choosing the A-3 policy.
  - Fabricating A-1, A-2, A-5, or A-6 approvals.
  - Merging.
- **Dependencies.** No parser dependency may be installed without owner approval. If support needs one, the batch identifies it, records its security and licensing implications, implements the fail-closed interface, and stops for approval.
- **Invariants preserved.** These are unchanged:
  - the strategy objective (PROJECT_BRIEF.md §3);
  - runtime LLM independence;
  - the A-1 to A-8 acquisition gate;
  - the observation classes and the protected-information and holdout rules;
  - F-09 and the host-class rules;
  - the safe-format policy.
- **Reviews.** An independent Reliability / Red-Team review with no unresolved BLOCKING or MAJOR finding. A Statistician review only if B07 touches release, holdout, `T0`, or equivalence semantics. A fresh cold-start review.

## Designation

Under this charter, B07 is the current active ground-truth branch (`docs/BRANCH_TIMELINE.md`). B06 is a historical checkpoint, preserved.

## Design decisions recorded by this batch

None of these changes an approved requirement. Each implements an existing rule, or is marked as an interpretation for owner confirmation.

| ID | Decision | Basis |
|---|---|---|
| B7-1 | **Isolation model (G-1).** Untrusted parsing and extraction run in a separate worker process. Before exec, the parent applies rlimits: address space, CPU, file size 0, descriptors, no core dumps. The worker installs a seccomp **allowlist**, with argument-filtered `fcntl` and `ioctl`, plus `no_new_privs`, before reading input. It was a denylist until Red-Team round 1 showed that a confined worker could still act on its parent (RT-B7-01). The parent makes itself non-dumpable, with no core dumps. It gets no environment, `/` as its working directory, a new session, and only the input descriptor (read-only), the output pipe, and `/dev/null`. The parent enforces a versioned framed protocol, a wall-clock deadline, output caps, and a clean exit, and never accepts a partial result. It is supported on Linux x86-64 only and fails closed elsewhere. `fstat`-family metadata calls stay allowed. There is no network namespace: network isolation rests on denying every socket call. | A-4 ("separate process with no network access, no read access to … no privilege escalation, write access only to its output directory") |
| B7-2 | **Readers (G-2, G-3, G-5).** CSV, JSON, JSONL, and text are read by project code on the Python standard library only. Each file needs an expected schema (exact ordered CSV columns with value types, or required JSON keys with allowed types), and values are checked, never coerced. gzip, bzip2, and xz single files are decoded strictly, with size and expansion-ratio caps. Parquet, DBN, and zstd are **registered but not adopted**, and are refused (B7-6). | A-4; safe-format policy; CLAUDE.md "no silent repair" |
| B7-3 | **Raw bytes are what is stored.** The protected store keeps exactly the received bytes. Decompressed and extracted plaintext exists only in the acquisition's scratch directory under the same store root, for verification, and is deleted afterwards. | A-7; CLAUDE.md "preserve raw data" |
| B7-4 | **No production transport.** The fetcher runs behind an injectable `Transport`, and only a synthetic transport exists. A real-mode run requires a reviewed production transport, so it refuses today. Building that transport needs its own review: TLS verification, DNS and IP pinning, and refusal of private and link-local ranges (the remainder of G-4). | Charter §5, §13 (no real request) |
| B7-5 | **Credentialed acquisition unsupported.** The pipeline refuses any approval with `credential_required`, because credential isolation (F-03) is not built. The fetcher alone supports a single first-hop credential header, never resent after a redirect, for future use. | F-03; charter §5 |
| B7-6 | **Reader dependencies deferred pending owner approval.** See the table below. | Charter §10 |
| B7-7 | **"Size class" interpretation (A-3).** A restore test covers a planned file when its artifact type (`csv`, `csv+gzip`, `tar.gz`, …) matches and its size class is at least the file's. Size class is the number of decimal digits of the byte count. This is a **proposed interpretation for owner confirmation**, not an approved definition. | A-3 ("same format and size class") |
| B7-8 | **Synthetic and real modes.** Synthetic runs accept only `synthetic_` records, reserved test domains, synthetic transports and backup targets, and no store root inside `~/pmv-protected`. Real runs refuse synthetic records and require all of the following: the protected raw root; a clean committed tool tree; every cited decision and review file committed unchanged; the F-09 commit as an ancestor of `HEAD`; no acquisition-code change since the A-4 review; an A-4 record that says A-4 is satisfied; the owner's real backup target; and a reviewed production transport. | Charter §14 ("real-source execution must refuse when owner-controlled records are absent") |

### Reader dependencies awaiting owner approval (B7-6)

No dependency was added or installed. `uv.lock` is unchanged, and the project still has no runtime dependency. Exact versions were **not** selected: the batch had no network access to check current releases and advisories. A version is chosen, hash-pinned in `uv.lock`, and reviewed at approval time.

| Need | Candidate package (not installed) | Licence | Security notes | Proposed non-code-executing path |
|---|---|---|---|---|
| Parquet (G-2) | `pyarrow` (Apache Arrow) | Apache-2.0 | A large native (C++) parsing surface. CVE-2023-47248 (0.14.0 to 14.0.0) allowed arbitrary code execution through `PyExtensionType` pickles. Any pinned version must be past every published advisory, and extension-type deserialization must be disabled. | Read only inside the G-1 worker, from the inherited descriptor (never a path or URI, so no filesystem or remote resolution), with Thrift size limits, no extension types, and an explicit expected schema |
| DBN (G-2) | `databento-dbn` (Rust `dbn` crate bindings) | Apache-2.0 (verify at approval) | A native (Rust) decoder. Version and schema-version pinning are needed because DBN versions change record layouts. | Decode inside the G-1 worker from the inherited descriptor, with a pinned DBN version and an expected schema and record type |
| zstd (`.dbn.zst`, G-5) | `zstandard`, or a move to Python 3.14 (`compression.zstd` is stdlib there) | BSD-3-Clause (verify) | A native decoder, so it needs a decoder memory limit and frame-size bounds. A Python upgrade is a governance change because `requires-python` pins 3.13. | Strict single-frame-sequence decoding with size and ratio caps, as for gzip, bzip2, and xz |

Until the owner approves, any plan containing these formats or codecs is refused before transport ("A-4: no adopted reader").

## Not changed

- No requirement in the holdout, protected-information, acquisition, risk, or real-capital rules was relaxed.
- No gate status changed: Gate 0 passed, and Gate 1 is undecided. No cycle, `T0`, split, or protected scope exists.
- No real market observation was accessed, no network host was contacted for data, and no credential was used.
- `.claude/settings.json`, the agent files, PROJECT_BRIEF.md, START_HERE.md, CLAUDE.md, and the hash-pinned HOLDOUT_ACCESS_LOG.md body were not modified.

## Optional owner decision carried forward

**B6S-14** (independent statistical audit of the H-2 release rules before the first real release; `docs/release_tool_design.md`) remains **optional and unadopted**. It is neither discarded nor turned into a requirement. B07 does not touch release semantics.

## Environment note

The isolated sandbox blocks writes to `.git/config` (a `/dev/null` placeholder at `.git/config.lock`). `git push -u` therefore pushed B07 but could not record upstream tracking. Pushes use an explicit `git push origin b07/phase1-acquisition-pipeline-hardening`. Changing git configuration is the owner's decision (`docs/backup_and_recovery.md`).
