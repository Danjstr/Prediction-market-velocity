# B07 Acquisition Pipeline: Independent Reliability / Red-Team Review

- **Date:** 2026-10-16
- **Reviewer:** Reliability / Red-Team Engineer (independent development reviewer; not part of any runtime)
- **Subject:** commit `f160647` ("B07: G-1 to G-6 acquisition pipeline hardening"), reviewed against its parent `c0d2a2b` (final B06), on branch `b07/phase1-acquisition-pipeline-hardening`. Scope is `git diff c0d2a2b f160647 -- src tests`. The B06 directory-fsync change in `quarantine.py` (RT-B6-28) is re-reviewed in full.
- **Method:** I read every changed module in `src/pmv/acquisition/` (`confinement`, `worker_protocol`, `parse_worker`, `isolation`, `readers`, `fetch`, `plan`, `state`, `pipeline`, `receipts`, `synthetic`, and the diffs to `quarantine`, `archive`, and `backup`), plus the relevant parts of `hosts.py`, `safe_fs.py`, and `config.py`. I ran targeted tests one process at a time: `tests/unit/test_acquisition_isolation.py` (18 passed), and `tests/failure_injection/test_acquisition_{pipeline_faults,isolation_faults,b07_regressions}.py` (60 passed). I also wrote synthetic probes under `$TMPDIR/rt7/`, run with `.venv/bin/python -I`. All data was synthetic. There was no network access, no real market data, and no credentials. I did not read `~/pmv-protected` or `~/pmv-credentials`. I edited nothing under `src/` or `tests/`.
- **Independence:** I did not write, design, or repair any B07 code. I knew the prior B06 findings only from `research/governance/b06_acquisition_tooling_red_team_review.md`. I did not trust the commit message or the docstrings: every claim below was checked against the code or a probe. Limits: I could not test power loss, a real network transport, or the A-7 protected store root (it is outside my sandbox). Those items are assessed by reading the code only.

## Summary

B07 is a substantial, mostly careful implementation:
- The protocol parser, the parent-as-only-writer extraction, the strict URL and redirect handling, the O_TMPFILE+linkat storage, the bound journal, and the crash recovery are solid.
- Every new fault test passes.
- I found no path that makes a row agent-visible through the pipeline's own outputs.
- I found no way to store unverified or partial bytes.

Two findings change the verdict.

1. **RT-B7-01 (BLOCKING).** The seccomp denylist does not stop a compromised worker from affecting other processes. I demonstrated this with a confined fake worker that installs the real `confinement.install_filter()`:
   - `fcntl(F_SETOWN, getppid())` plus `F_SETSIG` plus `O_ASYNC` on its stdout pipe delivers an arbitrary signal to the trusted parent every time the parent reads.
   - `prlimit64(getppid(), RLIMIT_CORE, unlimited)` raises the parent's core limit.
   - Together, through the real `isolation.run_worker`, these made the parent dump core into its working directory (`core_pattern` is `core` on this host). The core file contained a sentinel from the parent's memory 103 times.

   A parser exploit is therefore not contained. It can write the parent's memory, which during a real run holds protected plaintext, outside the protected store. That breaks A-7, and A-8 too if the owner launched the tool from an agent-readable directory. The docstrings and `docs/acquisition_readiness.md` state that "signals to other processes" are denied. That statement is false.

2. **RT-B7-02 (MAJOR).** The claim "a real run always refuses today" depends on honest callers:
   - The set of reviewed production transports is a constructor argument.
   - A transport declares itself non-synthetic.
   - The Git `Repository` is injectable.

   With a `SyntheticTransport` subclass marked `synthetic=False`, passed in `production_transports`, and a `StaticRepository`, every A-1 to A-6 cross-check and every real-mode check passed. Only the location of the A-7 store root refused the run.

The other findings are MINOR. Each fails closed, or is an overstated claim, or affects durability or operations.

## Findings

| ID | Severity | Location | Description | Synthetic reproduction | Recommended fix |
|---|---|---|---|---|---|
| RT-B7-01 | **BLOCKING** | `confinement.py` `DENIED_SYSCALLS` / `install_filter`; `isolation.run_worker`; `pipeline.py` (parent process) | **Seccomp escape to other same-uid processes.** The denylist omits several syscalls that act on other processes:<ul><li>`fcntl` with `F_SETOWN`/`F_SETOWN_EX`/`F_SETSIG` plus `O_ASYNC`, which delivers any signal, including SIGKILL, SIGSTOP, and SIGABRT, to any same-uid pid or process group;</li><li>`prlimit64` on another pid;</li><li>`setpriority`, `sched_set*`, and `ioprio_set` on another pid.</li></ul>The parent never protects itself: no `PR_SET_DUMPABLE 0` and no `RLIMIT_CORE 0`. A compromised worker can therefore (a) kill or stop the parent; a stopped parent never reaches its own wall-clock deadline, so the run hangs holding the lock. (b) It can make the parent dump core with unlimited size into the parent's cwd, or into a system coredump store. That core holds parent memory: quarantine chunks, extracted DATA payloads, and verification buffers. The result is protected plaintext outside the protected store (A-7). If the cwd is the repository, the plaintext is agent-readable (A-8). (c) It can do the same to any other process of the owner's uid. This defeats the containment purpose of G-1. The only precondition is code execution in the worker, which is exactly the threat G-1 exists for: a memory-safety bug in zlib, bz2, liblzma, or CPython. | `$TMPDIR/rt7/scripts/evil_worker.py` + `drive.py`: under the real filter, `prlimit_core_parent` returned 0 and the parent's limit became `(-1, -1)`. `F_SETSIG` gave hundreds of SIGUSR1 deliveries to the parent. `setpriority(parent)` returned 0. `evil2.py` + `parent_demo.py` used `isolation.run_worker(..., command=[...])`: the parent died with SIGABRT, and `core.7` (13.7 MB) appeared in the parent's cwd containing the sentinel 103 times. The core was deleted after the check. | <ol><li>Replace the denylist with an allowlist: read, write, pread64, lseek, fstat, mmap/munmap/mremap/brk/madvise, futex, rt_sig*, getrandom, clock_*, exit_group, plus whatever the warm-up proves necessary. Kill or return EPERM for everything else. At minimum, deny `prlimit64` (or any pid ≠ 0), `fcntl` with F_SETOWN, F_SETOWN_EX, F_SETSIG, F_SETLEASE, F_NOTIFY, or F_SETFL with O_ASYNC, `setpriority`, `sched_setaffinity`, `sched_setscheduler`, `sched_setparam`, `sched_setattr`, `ioprio_set`, `migrate_pages`, `move_pages`, `get_robust_list`, `ioctl`, `inotify_*`, `fanotify_*`, `syslog`, `uselib`, and SysV IPC (`shmat`, `shmctl`, `shmdt`, `msgsnd`, `msgrcv`, `msgctl`, `semop`, `semtimedop`, `semctl`).</li><li>Independently, the acquisition parent should set `prctl(PR_SET_DUMPABLE, 0)` and `RLIMIT_CORE=(0,0)` on itself before handling any untrusted bytes. Real mode should also refuse a cwd outside the protected root.</li><li>Add the probe above as a regression fixture, and extend `_PROBES` with `prlimit64(ppid)`, F_SETSIG/F_SETOWN, and `setpriority(ppid)`.</li></ol> |
| RT-B7-02 | **MAJOR** | `pipeline.py` `AcquisitionPipeline.__init__` / `_real_failures` | **Real-mode gates are caller-satisfiable.** `production_transports` is a constructor argument. `transport.synthetic` is set by the transport itself. `repository` is any object with the `Repository` methods. A transport defined outside `src/pmv/acquisition/` would not even trigger the "acquisition code changed since review" check. The docstring claims "No production transport exists, so a real run always refuses today", and `docs/acquisition_readiness.md` says the same. In fact only the A-7 store-root location and the absence of a caller willing to pass these arguments stop it. That is a G-4 control bypassable with a few lines of code. | `$TMPDIR/rt7/scripts/realmode.py`: I renamed the `synthetic_` identifiers, used `FakeProdTransport(SyntheticTransport)` with `synthetic=False`, `production_transports={FakeProdTransport}`, and `StaticRepository(all True)`. `_parse`, `_cross_checks`, and `_real_failures` all returned `[]`. Only `_root_failures` refused. | <ol><li>In REAL mode, ignore injected collaborators. Use a module-level, reviewed, hash-pinned registry of production transport classes (empty today), and a `GitRepository` built from the tool's own checkout (`Path(__file__)`).</li><li>Refuse any transport whose class is defined outside the reviewed package.</li><li>Include the transport module in the `unchanged_since` check.</li><li>Reword the docstring and the readiness doc until then.</li></ol> |
| RT-B7-03 | MINOR | `readers.LineReader._take` / `readline` | **Quadratic CPU per buffered chunk.** Each `_take` copies the rest of a buffer of up to 1 MiB. Cost is about O(chunk / line length) per byte. Legitimate large files therefore exceed the worker's 120 s CPU cap. The pipeline then classifies that as a terminal content rejection (see RT-B7-04). The failure is closed, but realistic historical files of a few hundred MiB or more cannot be verified. | `$TMPDIR/rt7/scripts/quad.py`: CSV with 2-byte lines took 30.6 s CPU at 1 MiB, 99 s at 2 MiB, and 138 s at 4 MiB. `quad2.py`: 64-byte lines took 6.7 s at 8 MiB (about 0.84 s/MiB, so the 120 s cap is reached at about 140 MiB). | Use an offset-based buffer (`memoryview`, or `bytearray` with a read index and periodic compaction), or `io.BufferedReader.readline`. Add a throughput regression test. |
| RT-B7-04 | MINOR | `pipeline._isolated`, `_ENVIRONMENTAL` | **Environmental worker failures become terminal content rejections.** `TIMEOUT`, `CPU_LIMIT`, and `SIGNALED` (including a host OOM kill on a 2.7 GB machine with a 768 MiB worker address-space default) are journaled as `rejected`. That state is terminal for the acquisition ID. The failure is closed, but a load spike permanently rejects a good file and forces a new acquisition record. | Code reading. Combine with RT-B7-03 for a deterministic case. | Treat these as retryable environmental failures (a `PipelineError` with the state unchanged), with a bounded retry count. Reserve `rejected` for worker refusals and protocol violations. Size `WorkerLimits` against measured free RAM. |
| RT-B7-05 | MINOR | `readers.decoded_source` (gzip) | **gzip is not strict as documented.** `gzip.GzipFile` silently accepts trailing NUL padding after the last member. The docstring and readiness doc say "every byte after a stream must start another complete stream". The raw bytes are still hashed in full, so integrity is unaffected. | `$TMPDIR/rt7/scripts/gzpad.py`: `gzip.compress(...)+b"\0"*4096` was ACCEPTED. Trailing `XYZ` was refused. | Decode gzip with `zlib.decompressobj(31)` through `_StrictStreams`, as bz2 and xz are, or document the padding exception. |
| RT-B7-06 | MINOR | `fetch.Fetcher._receive` | **"On any failure nothing is named" is false after the link.** If `fsync(directory_fd)` or the post-link `stat`/inode check fails, the name remains in quarantine while the fetch reports `WRITE_FAILED`. The bytes are complete and hash-checked. The next run handles them as an orphan (moved aside, journaled `discarded`), so the failure is closed. | Code reading. | Reword the claim, or unlink the name (and fsync) on a post-link failure. |
| RT-B7-07 | MINOR | `quarantine.Quarantine.receive` (RT-B6-28 re-review); `pipeline._move_aside` | **Remaining directory-durability gaps.** `release` now has the correct order: data fsync, link, destination dir fsync, journal, unlink, source dir fsync (verified). The pipeline's `_store_copy`, `_write_new`, `fetch`, and `_ensure_dir` are also correctly ordered. Two gaps remain. (a) `receive` journals `received` without fsyncing the quarantine directory after the create, and removes files on failure without a directory fsync. Receipts are session-scoped, so this fails closed. (b) `_move_aside` unlinks the source before fsyncing the target directory. On a filesystem without ordered metadata, a power loss could lose both names. The relevant bytes are rejected or orphaned copies, not stored data. | Code reading (power loss not simulated). | `receive`: fsync the directory before the journal append. `_move_aside`: link, fsync the target dir, unlink, fsync the source dir. |
| RT-B7-08 | MINOR | `receipts.recover_torn_tail` | **The attestation is a string pattern only.** The tool does not check that the cited `docs/decisions/*.md` exists or is committed. A crash between `ftruncate` and the `tail_recovered` append leaves a truncated journal whose evidence file nothing references. The evidence file is preserved beside the journal. Truncation of a full valid entry missing only its newline is preserved as evidence, and pipeline recovery handles the resulting state regression (store `recovered=True`, orphan path). | Code reading. | Verify the attestation file through `GitRepository.committed_unchanged`. Write a `.pending` marker before truncation, or append-then-truncate through a new journal file. |
| RT-B7-09 | MINOR | `pipeline._root_failures` (synthetic) | **The synthetic store-root guard needs both conditions.** It refuses only when the root is inside `~/pmv-protected` both lexically and after resolution. A root under a symlinked parent that resolves into the protected tree is accepted, so synthetic runs could write synthetic data into the protected store. | Code reading (`protected_raw_root_problem` returns non-None if either test fails). | In synthetic mode, refuse if either the lexical or the resolved path is inside the protected root. |
| RT-B7-10 | MINOR | `parse_worker.worker_identity`; `isolation._check_hello` | **Identity and verification evidence are weaker than stated.** (a) The identity covers six module sources, the Python version, and the zlib version. It does not cover `pmv.integrity`, `pmv.safe_fs`, the interpreter binary, or site-packages `.pth` code, which runs before confinement under `-I`. (b) The worker asserts `records`, `decoded_bytes`, `decoded_sha256`, and `input_sha256` itself, and a compromised worker can echo the expected values. The parent's own hashes (`check_integrity`, `_store_copy`, `_fd_sha256`) protect the stored bytes, but the "verification binds to exact bytes" wording overstates what the worker result proves. (c) Extraction frames are written to scratch before the HELLO identity is checked. They are rolled back on mismatch. | Code reading. | Add `pmv.integrity` and the interpreter (`sys.executable` hash, `sys.prefix`) to the identity. Check HELLO as soon as it arrives. Reword "binds" as "is reported for". |
| RT-B7-11 | MINOR | `confinement.py` docstring; `docs/acquisition_readiness.md` "Isolation" | **Overstated documentation (apart from RT-B7-01).** Under the filter, `inotify_init1` succeeded (path-based watches of file activity), `syslog` succeeded (kernel log readable), and `getxattr`, `ioctl` (inode flag changes on the read-only input), and SysV IPC attach are reachable. "Cannot open, read, or write a file other than the descriptors it inherited" is true for file content, but metadata and attribute channels remain. Platform support (Linux x86-64 only, failing closed elsewhere) and "no network namespace" are stated correctly. | `evil_worker.py` output: `inotify_init1` returned fd 3, `syslog(10)` returned 262144, and `setpriority(parent)` returned 0. | Fixed by the allowlist in RT-B7-01. Until then, list these channels in "Limits of this isolation". |

## Per-item assessment

| Item | Assessment |
|---|---|
| G-1 isolated parsing | **Not satisfied.** The process separation, rlimits, empty environment, `-I`, `cwd=/`, new session, `close_fds`, read-only fd 0, `/dev/null` fd 2, warm-up before the filter, `no_new_privs`, and limit self-check are all implemented and verified. The protocol enforcement is sound. But the seccomp layer does not contain a compromised worker (RT-B7-01, BLOCKING). |
| G-2 pinned readers | Partly satisfied, as claimed. CSV, JSON, JSONL, and text are stdlib-only with fixed identities, and Parquet and DBN are refused (`READER_NOT_ADOPTED`, checked in both the plan cross-check and the worker). The performance defect (RT-B7-03) makes large files unverifiable. |
| G-3 expected schemas | Satisfied for the adopted formats. Exact ordered CSV header, per-column types with no coercion, JSON exact keys or explicit `additional_keys`, bool ≠ int, Decimal numbers, BOM refused, mixed line endings and bare CR refused, trailing data refused. |
| G-4 fetch | The fetch semantics are satisfied: allowlist before the transport, per-redirect reclassification, cross-host refusal, loop and count limits, closed codes, Content-Length, encoding, and size checks, a deadline, and O_TMPFILE+linkat. A minor overclaim remains (RT-B7-06). The **production transport does not exist**, and the "real run refuses" gate is caller-satisfiable (RT-B7-02, MAJOR). |
| G-5 bounded decompression | Satisfied, with one strictness gap. Size and ratio caps hold for gzip, bz2, and xz. zstd, snappy, lz4, and brotli are refused. gzip accepts NUL padding (RT-B7-05). |
| G-6 end-to-end pipeline | Implemented. Prerequisites are checked before the transport. The state machine is replayed from the bound journal. Every crash point has a deterministic resume (60 fault tests pass, and the code reading agrees). The real-mode gating is weak (RT-B7-02). Environmental failures become terminal rejections (RT-B7-04). |
| RT-B6-26 (rest) | **Mostly closed for the pipeline.** (a)/(b): the pipeline's store path recovers an unjournaled store (`recovered=True`) and never replaces anything. (c): `receive` now unlinks on Python exceptions, but not on SIGKILL. The pipeline's `recover_quarantine` covers that case by moving orphans aside. The v1 `Quarantine` class is not used by the pipeline. (d): owner-attested torn-tail recovery exists (RT-B7-08 MINOR). (g): fixed. |
| RT-B6-27 | **Closed for v2 entries.** Every pipeline entry carries `acquisition_id` and the authorizing-bundle hash, and replay refuses a mismatched bundle. v1 entries stay unbound, as documented. Re-acquisition hashes are still not compared automatically (an orphan's hash is journaled in `discarded` for a human to compare). |
| RT-B6-28 | **Fixed in `release`** (order verified). Gaps remain in `receive` and `_move_aside` (RT-B7-07 MINOR). The new pipeline and fetch paths have correct durability ordering. |
| Parser isolation | Separate process, with the parent as the only writer. Fails by RT-B7-01. |
| Process / resource limits | Applied before exec and re-verified by the worker. The FSIZE=0, CORE=0, NOFILE, AS, and CPU limits work, and so does the wall-clock killpg. The worker can raise the parent's limits (RT-B7-01). The 768 MiB address-space default exceeds the free RAM on this host (RT-B7-04). |
| Parser / dependency identity | Stdlib only. Identities are pinned and checked in HELLO. Coverage is incomplete (RT-B7-10). |
| Unsafe deserialization | None found. No pickle, eval, or third-party parsers. JSON goes through `strict_parse` with Decimal. Only CSV, JSON, JSONL, and text are interpreted. |
| URL / redirect authorization | Strong. The netloc must equal the bare host; userinfo, `@`, query, fragment, `%`, `\`, `//`, dot segments, and control characters are refused. `urljoin` results are rechecked by the same allowlist, scheme-relative and cross-host redirects are refused, and a case-changed host is refused (netloc mismatch). The transport must send `request.url` verbatim (a contract for the future transport). |
| Credential / header behavior | Correct. A credential goes only to its exact host on the first hop, never after a redirect, and its `repr` is redacted. The pipeline refuses `credential_required` (F-03). |
| Archive / compression attack surfaces | Good. Names, depth, counts, sizes, ratio, case collisions, and member hashes are re-validated by the parent. Tar is two-pass with a consistency check, and there is a disk precheck. Members are re-verified in a fresh worker. The gzip padding exception is noted (RT-B7-05). |
| Crash / restart behavior | Deterministic and fail-closed at every injected point. Two directory-ordering nits remain (RT-B7-07). |
| Idempotency | Satisfied. Resume from the journal; never replace a stored file or record; at most one fetch attempt per file per run and `max_attempts` in total; `ALREADY_COMPLETED` re-verifies and seals. |
| Provenance integrity | Good. The record binds every authorizing document's hash, the received hashes, `final_url`, redirects, and the tool commit, and evidence files are hash-bound in the journal. The tool commit comes from the injectable repository (RT-B7-02). |
| Receipt integrity | Good. Hash chain, closed v2 detail schemas, byteless events only where valid, `released` refused when bound, and size cap at append. |
| A-7 protected-store boundary | **Not satisfied.** The pipeline writes only under its store root, and scratch plaintext stays under that root and is deleted. But a compromised worker can make the parent write its memory outside the root (RT-B7-01). The synthetic guard has a symlink gap (RT-B7-09). |
| A-8 no-release boundary | Satisfied by the pipeline's own outputs. `PipelineReport` and errors carry only states, closed codes, sizes, hashes, and owner-record key names, never values. The worker channel carries only closed codes. RT-B7-01 is the exception: if the owner's cwd is agent-readable, a core dump becomes an agent-visible copy of protected bytes. |
| Fail-closed behavior | Broadly satisfied. Every absent, malformed, or inconsistent prerequisite refuses before the transport. Every protocol deviation, mismatch, or conflict refuses. The exceptions are the bypassable real-mode gate (RT-B7-02) and the over-eager terminal rejection (RT-B7-04, which errs toward closed). |

**Docstring overstatements:**
- "signals to other processes" are denied: false (RT-B7-01).
- "a real run always refuses today": false given caller-supplied collaborators (RT-B7-02).
- gzip "strict": NUL padding is accepted (RT-B7-05).
- fetch "nothing is named on any failure": false after the link (RT-B7-06).
- the worker's verification "binds to exact bytes": worker-asserted (RT-B7-10).
- "cannot open, read, or write a file": metadata and attribute channels remain (RT-B7-11).

These are stated correctly: the filter is a denylist, `stat` metadata is visible, there is no network namespace, and support is Linux x86-64 only, failing closed elsewhere.

## Verdict

- **Reviewed code: no unresolved BLOCKING finding? NO.** RT-B7-01 is open.
- **MAJOR open? YES.** RT-B7-02.
- **A-4 satisfied? NO.** These remain:
  1. RT-B7-01 must be fixed and re-reviewed.
  2. The Parquet and DBN readers and zstd are not adopted; owner dependency approval is pending.
  3. There is no reviewed production transport (G-4), and the real-mode transport and repository gating must not be injectable (RT-B7-02).
  4. G-7 owner inputs are still open: the real A-3 backup policy and a restore test on the real medium, plus the per-source A-1, A-2, A-5, and A-6 records.
  5. The isolation requirement should be re-verified once the filter is an allowlist.
- **Recommendation: revise.** Fix RT-B7-01 and RT-B7-02. The MINOR findings may be fixed now or tracked. Any further change to `src/pmv/acquisition/` requires re-review. Acquisition stays unauthorized.

## Re-verification (round 2)

- **Date:** 2026-10-16
- **Subject:** remediation commit `b146099` on top of `f160647` (`git diff f160647 b146099 -- src tests`). I also read the working-tree text of `docs/acquisition_readiness.md` ("Isolation (G-1)") and the B7-1 row of `docs/decisions/2026-10-16_b07_acquisition_pipeline_hardening.md`. These doc changes are **not in `b146099`**: they are uncommitted working-tree edits at the time of review.
- **Independence:** unchanged. The coordinator wrote the remediation, and I did not contribute code. I recommended the allowlist, `harden_parent`, and the code-level transport registry in round 1. I therefore reviewed those designs with extra skepticism and did not credit them on intent.
- **Method:**
  - Re-ran every round-1 probe in `$TMPDIR/rt7/scripts`: `evil_worker.py`+`drive.py`, `evil2.py`+`parent_demo.py`, `quad.py`, `quad2.py`, `gzpad.py`, and an updated `realmode2.py`.
  - Wrote new probes:
    - `bpfsim.py`, an independent BPF interpreter. It decodes the emitted program and checks it against the intended policy for:
      - syscall numbers 0–599, x32 numbers, negative numbers, and 0x7FFFFFFF;
      - three foreign architectures;
      - `fcntl`/`ioctl` commands 0–1999 plus TIOCSTI and other known requests, each with arg1 high word 0, 1, and 0xFFFFFFFF;
      - arg0/arg2 independence.
    - `paths.py` and `zipprobe.py`: every worker decode and extract path under the real allowlist.
    - `mem.py`: memory exhaustion of a valid JSON under a 256 MiB worker limit.
  - Ran targeted tests one at a time, all passing:
    - `tests/failure_injection/test_acquisition_b07_regressions.py` with `tests/unit/test_acquisition_confinement.py`: 27 passed.
    - `tests/integration/test_acquisition_pipeline.py` with `tests/failure_injection/test_acquisition_pipeline_faults.py`: 90 passed. This also shows that `PR_SET_DUMPABLE 0` does not break the `/proc/self/fd` `linkat` path.
  - Synthetic data only. No network, and no edits outside this file.

### Evidence

- **Attack against the parent (`evil_worker.py` under the new filter).** Every call was refused with EPERM: `prlimit64(ppid)` (EPERM; the parent's limit was unchanged), `fcntl F_SETOWN/F_SETSIG/O_ASYNC`, `setpriority(ppid)`, `sched_setaffinity`, `inotify_init1`, `syslog`, `getxattr`, `shmat`, `msgsnd`, `move_pages`, and `uselib`. The parent received no signals.
- **Forced core dump through the real `run_worker` (`parent_demo.py`).** The worker failed (`abnormal_exit`). The parent survived, and no core file was written. `harden_parent` sets `RLIMIT_CORE=(0,0)` and `PR_SET_DUMPABLE 0`. It runs before any untrusted byte is held, because `_prerequisites` calls `verify_isolation`, and so `run_worker`, before any fetch.
- **BPF program (`bpfsim.py`).** The program has 56 instructions, and I found 0 mismatches:
  - the allowlisted numbers return ALLOW, and every other number returns EPERM;
  - `nr >= 0x40000000`, including negative numbers read as unsigned, returns KILL;
  - a foreign architecture returns KILL;
  - `fcntl`/`ioctl` return ALLOW only when arg1's high word is 0 and its low word is a listed command; any non-zero high word returns EPERM;
  - arg0 and arg2 are ignored;
  - jump offsets are resolved in range (the assembler refuses offsets outside 0–255), and the unconditional `JA` targets `deny` correctly.

  The kernel reads `fcntl`/`ioctl` commands as `unsigned int`, so requiring a zero high word is stricter than necessary, which is safe.
- **Functional coverage under the allowlist (`paths.py`, `zipprobe.py`).**
  - Verification of `.jsonl`, `.jsonl.gz`, `.jsonl.bz2`, and `.jsonl.xz`, and extraction of `tar.gz`, `tar.bz2`, `tar.xz`, and deflate `zip`, all succeed.
  - LZMA and bzip2 zip members, and non-ASCII member names, are refused. The in-process extractor refuses the same inputs (it is policy, not an allowlist artifact).
- **Reader throughput (`quad.py`, `quad2.py`).** 8 MiB of 64-byte lines now takes 0.96 s CPU (it was 6.7 s). 4 MiB of 2-byte lines takes 19 s (it was 138 s). Cost is now linear. The remaining cost is per-record Python overhead: about 0.12 s/MiB for realistic lines, so about 1 GB per 120 s CPU cap.
- **Real-mode gate (`realmode2.py`).**
  - The pipeline used `GitRepository` even though a `StaticRepository` was passed in.
  - With the empty registry, a transport whose class claims `__module__="pmv.acquisition.fetch"` and a matching name is refused (G-4), together with the real Git facts.
  - When I simulated a future registry entry by monkeypatching `PRODUCTION_TRANSPORTS`, the spoofed class passed the G-4 check (RT-B7-12).

### Dispositions

| ID | Round-1 severity | Disposition | Notes |
|---|---|---|---|
| RT-B7-01 | BLOCKING | **FIXED, verified** | The filter is an allowlist with argument-filtered `fcntl`/`ioctl`. The post-install self-check proves a denied call returns EPERM. `harden_parent` runs before any untrusted bytes. The probe set has 28 entries. The regression test runs the round-1 attack against its parent. Both round-1 attacks fail, and the BPF matches its policy exactly. Residual: `newfstatat`/`statx` reveal path metadata (stated). Same-uid processes outside the worker are outside this control. |
| RT-B7-02 | MAJOR | **FIXED, verified** (residual: RT-B7-12) | The constructor argument is gone. Real mode always uses `GitRepository(TOOL_ROOT)`, and the code-level registry is empty, so a real run refuses on G-4 whatever the caller supplies. In-process monkeypatching of module constants is inherent to any code-level check and out of scope. |
| RT-B7-03 | MINOR | **FIXED, verified** | Linear. A throughput regression test was added. |
| RT-B7-04 | MINOR | **FIXED, with MINOR residual (accepted)** | `TIMEOUT`, `CPU_LIMIT`, `SIGNALED`, and `ABNORMAL_EXIT` now stop the run with the state kept, not rejected. **Is "retry by owner rerun, no automatic counter" acceptable? Yes, as a fail-closed design.** Nothing is stored or rejected, and a person decides. Residual: (a) these failures leave **no journal trace**, so a deterministic crasher reruns indefinitely without evidence of how often it failed. Journal a non-terminal `parser_failed` event with the closed code, and list it in the recovery runbook. (b) `RESOURCE_EXHAUSTED` and `INTERNAL_ERROR` refusals are still terminal rejections. An `INTERNAL_ERROR` can come from an EPERM on a library path the warm-up never exercised. With default reader limits (4 MiB JSON, 512 MiB address space) this did not occur in my probes, but treating `INTERNAL_ERROR` as environmental would be more conservative. |
| RT-B7-05 | MINOR | **ACCEPTED as documented** | gzip zero padding is still accepted (re-verified). The docs now state it, and the raw hash covers the padding. |
| RT-B7-06 | MINOR | **FIXED, verified by reading and the regression test** | After a post-link failure, the name is unlinked only if it is still our inode, and the directory is fsynced. A crash in that window still leaves an orphan, which recovery handles (stated). |
| RT-B7-07 | MINOR | **FIXED, by reading** | `receive` fsyncs the directory before the journal append. `_move_aside` now does link, fsync target, unlink, fsync source. Power loss is not simulated. |
| RT-B7-08 | MINOR | **FIXED, with MINOR residual** | A `committed` predicate is required. Interrupted recovery resumes from a name-and-hash-checked evidence file, and ambiguous evidence or symlinks refuse. Residuals: the predicate is caller-supplied, and a planted `journal.torn-<N>-<hash>` file beside an intact journal would let an owner-run call append a `tail_recovered` entry for a tail that never existed. Both require local write access and an owner run, and the evidence stays visible. |
| RT-B7-09 | MINOR | **FIXED, by reading** | `_inside` refuses a store root that is inside the protected root literally **or** after resolution. |
| RT-B7-10 | MINOR | **FIXED, with MINOR residual (RT-B7-13)** | The identity now includes `pmv.integrity`, the executable SHA-256, and the `.pth` hooks. HELLO is checked on arrival, before any frame is acted on (regression test). The claims are reworded. |
| RT-B7-11 | MINOR | **FIXED** | Covered by the allowlist, and the stated limits are updated. |

### New findings

| ID | Severity | Location | Description | Synthetic reproduction | Recommended fix |
|---|---|---|---|---|---|
| RT-B7-12 | MINOR | `pipeline._real_failures`, `PRODUCTION_TRANSPORTS` | The registry matches the **string** `f"{__module__}.{__qualname__}"` plus a `pmv.acquisition.` module prefix. Both attributes are writable on any class, so once a transport is registered, a caller-defined class can impersonate it. It is harmless today because the registry is empty. | `realmode2.py`: with a simulated registry entry, a `SyntheticTransport` subclass renamed to that entry passed the G-4 check. | Register class **objects** imported from the reviewed module, and test `type(transport) is RegisteredClass`, or compare `inspect.getsourcefile(kind)` against the package directory. Do this before the first transport is added. |
| RT-B7-13 | MINOR | `parse_worker._startup_hooks_sha256`; worker launch | The startup-hook pin covers only `.pth` files in purelib and platlib. Under `-I`, `site` still imports `sitecustomize` from `sys.path`, which includes site-packages and `/workspace/src` via the editable `.pth`. Code imported by `import`-lines in `.pth` files is also not hashed. Real mode's clean-tree check does not cover `.venv`. That code runs before confinement in both worker and parent, and both would compute the same identity, so the pin would not detect it. | Code reading of `site.py` semantics; I did not plant a file in the shared venv. | Launch the worker with `-I -S` and insert the package root into `sys.path` explicitly, or also hash any importable `sitecustomize`/`usercustomize` and the modules named by `.pth` import lines. Document that the owner's real run must use an owner-controlled interpreter environment. |

No regressions found. The remaining docs nit: the fetch section's "so a partial file never has a name" is accurate, but the doc edits must be committed for the reviewed state to include them.

### Verdict (round 2)

- **Reviewed code (`b146099`): no unresolved BLOCKING finding? YES.**
- **MAJOR open? NO.** The open findings are all MINOR: RT-B7-12 and RT-B7-13, plus the residuals of RT-B7-04, RT-B7-05 (accepted), RT-B7-08, and RT-B7-10.
- **A-4 satisfied? NO.** These remain:
  1. The Parquet and DBN readers and zstd are not adopted; owner dependency approval is pending.
  2. There is no reviewed production transport (G-4). RT-B7-12 should be fixed before the first one is registered.
  3. G-7 owner inputs are open: the real A-3 backup policy and a restore test on the real medium, plus the per-source A-1, A-2, A-5, and A-6 records.
  4. The doc updates must be committed.

  A fresh A-4 record must cite the final reviewed commit.
- **Recommendation: proceed with conditions.** The isolation and pipeline code is acceptable for continued synthetic development. Fix RT-B7-12 and RT-B7-13, and journal environmental parser failures (the RT-B7-04 residual), before any real acquisition. Any further change to `src/pmv/acquisition/` requires re-review. Acquisition remains unauthorized.

## Re-verification (round 3)

- **Date:** 2026-10-16
- **Subject:** commit `ae693e2`. Scope is `git diff b146099 ae693e2 -- src tests` only.
- **Independence:** unchanged from rounds 1 and 2. The coordinator wrote this remediation; I wrote no code.
- **Method:**
  - Ran targeted tests one at a time: `tests/failure_injection/test_acquisition_b07_regressions.py` (17 passed) and `tests/unit/test_acquisition_isolation.py` (18 passed). These cover the new `-I -S` launch end to end. Worker identity still matches the parent's expected identity under `runpy`.
  - Wrote new probes in `$TMPDIR/rt7`:
    - `shadowroot/`: a package root holding a `pmv` symlink and a sourceless `csv.pyc`, launched with the exact `isolation._BOOTSTRAP` under `env -i python -I -S -c`.
    - `realmode3.py`: a name-spoofing class checked against a monkeypatched registry entry.
  - Synthetic data only, no network.

### Bootstrap analysis (RT-B7-13)

- **argv.** The launch is `python -I -S -c BOOT <root> <params>`, so `sys.argv` starts as `['-c', root, params]`. The bootstrap deletes `argv[1]`. `runpy.run_module(..., alter_sys=True)` then sets `argv[0]` to the module file, and `main` requires exactly two elements.
  - Both values are separate argv elements with no shell.
  - Arguments after `-c` are never parsed as interpreter options.
  - The parameters are canonical JSON generated by the parent.

  No injection path found.
- **Identity under `runpy`.** `sys.modules[__name__]` resolves to the temporary `__main__` module, whose `__file__` is `parse_worker.py`. The parent hashes the same file through a normal import. The regression tests confirm the two match.
- **Flags.** The worker refuses unless `sys.flags.isolated == 1 and sys.flags.no_site == 1`. Under `-S`, no site directory is on the path, so no `.pth`, `sitecustomize`, or `usercustomize` runs.
- **What still runs before confinement.** Interpreter start-up, the bootstrap, imports of `pmv.*` and the stdlib, and the warm-up. **One new hole: the package root is inserted at `sys.path[0]`, ahead of the stdlib** (RT-B7-14).

### Dispositions

| ID | Disposition |
|---|---|
| RT-B7-12 | **FIXED, verified.** `PRODUCTION_TRANSPORTS` is a `frozenset[type]` compared with `is`. A class renamed to `pmv.acquisition.fetch.HttpsTransport` is refused against a registered class of that name (`realmode3.py`). |
| RT-B7-13 | **FIXED for site and `.pth` code, verified**, but it introduces RT-B7-14. |
| RT-B7-04 | **(b) FIXED** (code reading): `INTERNAL_ERROR`, `RESOURCE_EXHAUSTED`, `LIMITS_NOT_APPLIED`, and `CONFINEMENT_FAILED` refusals now raise `PipelineError` and keep the state. **(a) Open, MINOR, documented:** there is no non-terminal journal event. It is now more relevant, because an input that deterministically triggers `INTERNAL_ERROR` stops every rerun and leaves no durable trace. |
| RT-B7-08 | Residual open, MINOR, documented (unchanged). |
| RT-B7-05 | Accepted, documented (unchanged). |

### New finding

| ID | Severity | Location | Description | Synthetic reproduction | Recommended fix |
|---|---|---|---|---|---|
| RT-B7-14 | MINOR | `isolation._BOOTSTRAP` (`sys.path.insert(0, root)`) | The package root (`src/` in this checkout) now comes **before** the stdlib on the worker's path. Any module there with a stdlib name runs in the worker before seccomp. That includes a **sourceless `.pyc`** such as `src/csv.pyc`. That file is matched by the `*.pyc` gitignore rule, so the real-mode clean-tree check does not see it. Worker identity hashes only `pmv` sources, so it does not pin the file either. Before B07-r3, the editable `.pth` appended `src/` after the stdlib, so this precedence is a regression. Exploiting it requires write access to the tool checkout, but it evades both tamper checks. A pre-existing residual applies to parent and worker alike: timestamp-validated `__pycache__` files for `pmv` modules can differ from the hashed sources. | `shadowroot/csv.pyc` (compiled from a marker module, source deleted) next to a `pmv` symlink. Launching with the exact bootstrap printed `SHADOW csv.pyc executed before confinement`. | Use `sys.path.append(root)`, so the stdlib wins. Then assert `importlib.util.find_spec('pmv').origin` is under `root`. For defense in depth, refuse to launch if `root` contains any entry other than the expected top-level packages. Optionally run the worker with `-X frozen_modules=on` and `--check-hash-based-pycs always`, or verify that the loaded `pmv` modules were loaded from source. |

### Verdict (round 3)

- **Reviewed code (`ae693e2`): no unresolved BLOCKING finding? YES.**
- **MAJOR open? NO.** The open MINOR findings are RT-B7-14, RT-B7-04(a), the RT-B7-08 residual, and the accepted RT-B7-05.
- **A-4 satisfied? NO.** These remain:
  - the Parquet and DBN readers and zstd (owner dependency approval);
  - a reviewed production transport (G-4);
  - the G-7 owner inputs (real A-3 backup policy and restore test, and the per-source A-1, A-2, A-5, and A-6 records);
  - a fresh A-4 record citing the final reviewed commit.
- **Recommendation: proceed with conditions.** Fix RT-B7-14 (a one-line change plus a check) and RT-B7-04(a) before any real acquisition. Any further change to `src/pmv/acquisition/` requires re-review. Acquisition remains unauthorized.

## Re-verification (round 4)

- **Date:** 2026-10-16
- **Subject:** commit `cd9ef17`. Scope is `git diff ae693e2 cd9ef17 -- src tests`.
- **Independence:** unchanged. The coordinator wrote this remediation; I wrote no code.
- **Method:**
  - Ran targeted tests one at a time: `tests/failure_injection/test_acquisition_b07_regressions.py` (18 passed), then `tests/unit/test_acquisition_state.py` (34 passed).
  - Re-ran the shadow-root probe (`$TMPDIR/rt7/shadowroot/`, exact `_BOOTSTRAP`, `env -i python -I -S -c`) with:
    - a planted `csv.py`;
    - a sourceless `csv.pyc`;
    - planted `nt.py`, `_winapi.py`, and `_wmi.py`.
  - Wrote `unresolved.py`, which appends a logging finder to the end of `sys.meta_path` in front of the real bootstrap. It lists every module name the worker looks up that the stdlib cannot resolve, during the `probe` and `verify` (csv+gzip) operations.
  - Checked the `STAGE_FAILED` transitions programmatically.
  - Synthetic data only, no network. The planted files were removed afterwards.

### Dispositions

| ID | Disposition |
|---|---|
| RT-B7-14 | **PARTIALLY FIXED; still open, MINOR.** The root is now appended, and the bootstrap exits 71 unless `pmv` resolves to `<root>/pmv/__init__.py`. Stdlib shadowing is closed: neither the planted `csv.py` nor the sourceless `csv.pyc` executed. **But the worker still imports from the root any name the stdlib looks up and does not have on Linux.** `unresolved.py` shows the worker probing `nt`, `_winapi`, and `_wmi` (in both `probe` and `verify`), from stdlib `try/except ImportError` paths (`platform`, `os`/`ntpath`-style checks). Planted as `nt.py`, `_winapi.py`, and `_wmi.py` in the package root, each one **executed before confinement**: `nt` ran several times, and the worker still exited 0. As a sourceless `.pyc` such a file is hidden by the `*.pyc` gitignore rule from the real-mode clean-tree check, and worker identity does not pin it. Exploiting it still needs write access to the tool checkout. **Fix:** do not put the root on `sys.path`. Instead, install a meta-path finder that answers only for `pmv` and `pmv.*`, using `importlib.machinery.PathFinder.find_spec(name, [root])` for the top-level package. Alternatively, launch from a dedicated directory that contains only `pmv`, or refuse to launch if the root contains any top-level entry other than the expected package directories (no `*.py`, `*.pyc`, `*.so`, or `*.pth`). Add `nt`/`_winapi`/`_wmi` plants to the regression test. |
| RT-B7-04(a) | **FIXED, verified.** `STAGE_FAILED` is bound (v2 only) and carries the receipt's size and hash. Its detail schema is closed (`stage`, `code`). It is allowed only as a **self-transition** from RECEIVED, INTEGRITY_VERIFIED, PARSER_VERIFIED, or BACKUP_VERIFIED; I verified that no `STAGE_FAILED` transition changes state. It is refused in NONE, APPROVED, FETCH_FAILED, STORED, and REJECTED, and after `completed`. It therefore cannot skip a stage or alter state, and replay stays a pure function of the journal. It does not disturb `record()`, which takes the stage events by type, or REJECTED recovery, which reads `last.detail` only in the REJECTED state. `_Run.stop` appends before raising, for environmental parser stops and the unverified-backup stop. A backup target that *raises* is still not journaled; that is acceptable because it fails closed. Repeated stops grow the journal toward its 64 MiB cap, which also fails closed. |
| RT-B7-08 | Residual still open, MINOR, documented. |
| RT-B7-05 | Accepted, documented. |
| `__pycache__` timestamp residual | Still open, MINOR, documented. It is pre-existing and affects parent and worker alike: timestamp-validated bytecode can differ from the hashed sources. |

No other regressions were found in this diff.

### Final verdict (round 4)

- **Reviewed code (`cd9ef17`): no unresolved BLOCKING finding? YES.**
- **MAJOR open? NO.** The open findings are all MINOR: RT-B7-14 (non-stdlib names imported from the package root before confinement), the RT-B7-08 residual, and the `__pycache__` residual. RT-B7-05 is accepted. All of them need local write access to the tool checkout or the journal directory, or fail closed.
- **A-4 satisfied? NO.** These remain:
  - the Parquet and DBN readers and zstd (owner dependency approval);
  - a reviewed production transport (G-4);
  - the G-7 owner inputs (real A-3 backup policy and restore test on the real medium, and the per-source A-1, A-2, A-5, and A-6 records);
  - a fresh A-4 record citing the final reviewed commit.
- **Recommendation: proceed with conditions.** The code is acceptable for continued synthetic development. Close RT-B7-14 (restrict the worker's import resolution to `pmv` only) before any real acquisition. Any further change to `src/pmv/acquisition/` requires re-review. Acquisition remains unauthorized.

## Re-verification (round 5, final)

- **Date:** 2026-10-16
- **Subject:** commit `4170b3c`. Scope is `git diff cd9ef17 4170b3c -- src tests`.
- **Independence:** unchanged. The coordinator implemented the fix I suggested in round 4, so I reviewed it with extra skepticism.
- **Method:**
  - Ran targeted tests one at a time: `tests/failure_injection/test_acquisition_b07_regressions.py` (18 passed), then `tests/unit/test_acquisition_isolation.py` (18 passed).
  - Re-ran `unresolved.py` against the real bootstrap.
  - Re-ran the shadow-root probe with the exact `_BOOTSTRAP` under `env -i python -I -S -c`. I planted the following in the root:
    - `csv.py`, `nt.py`, `_winapi.py`, `_wmi.py`, `sitecustomize.py`, and `encodings_extra.py`;
    - **sourceless** `csv.pyc`, `nt.pyc`, `_winapi.pyc`, and `_wmi.pyc`.
  - Reviewed `PmvOnly`, `pmv/__init__.py`, and `FileFinder` precedence by reading the code.
  - Synthetic data only, no network. The plants were removed afterwards.

### Evidence

- **Plants:** none of the planted `.py` or `.pyc` files executed (no marker output), and the worker ran to completion (exit 0).
- **Unresolved names:** the worker still *probes* `nt`, `_winapi`, and `_wmi`, and `pmv` is unresolved by the stdlib finders until `PmvOnly` answers. With the root off `sys.path`, those probes now resolve to nothing.

### Finder analysis

- **Top-level `pmv`.** `PmvOnly` answers only for `name == "pmv"`, searching `[root]`, and for names starting with `"pmv."`, searching the `path` the import system passes. That `path` is the parent package's `__path__`, which is `[<root>/pmv]` and so on down.
- **Other names.** Any other name, including `pmvx`, stdlib names, and the `nt` family, gets `None`. Relative imports resolve to absolute `pmv.*` names before any finder is consulted.
- **Missing `path`.** A `pmv.*` lookup with `path=None` would search `sys.path`, which does not contain the root. Only the trusted bootstrap and pmv code run before confinement, and neither passes an unusual `path`.
- **`__path__` tricks.** `pmv/__init__.py` does not call `extend_path` or modify `__path__`, and no `pmv` module does.
- **Origin check.** A planted `pmv/__init__.<ext>.so`, or a `pmv.py`, either changes `pmv`'s origin, so the bootstrap exits 71, or loses to the package directory.

### Dispositions

| ID | Disposition |
|---|---|
| RT-B7-14 | **FIXED, verified.** No name other than `pmv`/`pmv.*` can be loaded from the package root before (or after) confinement. Stdlib shadowing and the non-stdlib names the stdlib probes for (`nt`, `_winapi`, `_wmi`, `sitecustomize`) are both closed, for `.py` and for sourceless `.pyc`. |
| Residual (MINOR, documented) | Inside the `pmv` tree, the standard `FileFinder` order still prefers an extension module (`*.so`) over `*.py` for a submodule, and timestamp-validated `__pycache__` bytecode is still trusted. Both are pre-existing and apply equally to the parent process. Worker identity hashes `.py` sources only. An untracked `*.so` is **not** gitignored, so the real-mode clean-tree check would refuse it. `*.pyc` is ignored, but with a matching `.py` source present only the `__pycache__` timestamp residual applies. Optional hardening: run with `--check-hash-based-pycs always` and `sys.dont_write_bytecode`, or verify `__spec__.origin` endswith `.py` for each loaded `pmv` module before installing the filter. |
| RT-B7-04(a) | Fixed (round 4). |
| RT-B7-08 | Residual still open, MINOR, documented. |
| RT-B7-05 | Accepted, documented. |
| RT-B7-01 to RT-B7-13 (others) | As dispositioned in rounds 2 to 4. No regressions found. |

### Final verdict

- **Reviewed code (`4170b3c`): no unresolved BLOCKING finding? YES.**
- **MAJOR open? NO.** These remain, all MINOR and documented:
  - the RT-B7-08 residual (a planted torn-tail evidence file combined with a caller-supplied `committed` predicate);
  - RT-B7-05 (gzip zero padding, accepted);
  - the `pmv`-tree bytecode and extension-precedence residual.

  Each needs local write access to the tool checkout or the journal directory, or fails closed.
- **A-4 satisfied? NO.** These remain:
  - the Parquet and DBN readers and zstd (owner dependency approval);
  - a reviewed production transport (G-4);
  - the G-7 owner inputs (real A-3 backup policy and restore test on the real medium, and the per-source A-1, A-2, A-5, and A-6 records);
  - a fresh A-4 record citing the final reviewed commit.
- **Recommendation: proceed with conditions.** The B07 acquisition code at `4170b3c` is acceptable as reviewed tooling for synthetic development. Acquisition remains unauthorized until the A-4 items above and the owner approvals exist. Any further change to `src/pmv/acquisition/` requires re-review.
