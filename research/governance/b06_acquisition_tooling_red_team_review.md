# B06 acquisition-readiness tooling: Reliability / Red-Team review (A-4 tool review)

- Date: 2026-10-16. Reviewer: Reliability / Red-Team (development agent).
- Subject: uncommitted code on branch `b06/governance-continuity-sync`: `src/pmv/acquisition/{hosts,records,formats,strict_parse,archive,quarantine,backup}.py`; `tests/unit/test_acquisition_*.py`; `tests/failure_injection/test_acquisition_faults.py`.
- Governing text: `docs/external_access.md` §1, §2 (A-1 to A-8), §4.
- Method: code reading, the existing test suite (223 passed, Python 3.13.5), and adversarial probes. The probes used only synthetic inputs built in `$TMPDIR`. There was no network access, no real data, and no change to `src/` or `tests/`.
- Independence: I did not write this code. I authored the batch 4 red-team review that produced the A-4 requirements.

## Summary

The basic controls are sound. Traversal, absolute paths, links, devices and FIFOs are refused, and so are pax `path` overrides. Zip local-header name lies, zip size lies and overlapping zip entries are all refused. The tests include a plain 1000:1 ratio bomb, and it is refused. URL user information, ports, IDNA, percent-encoded hosts and encoded dot segments are refused. Records reject bool-as-int and enum coercion.

Four problems are serious:
1. Tar metadata headers (pax and GNU long-name) are decompressed into memory without limit, and the ratio check never counts them. This is a working decompression-bomb bypass.
2. Corrupt compressed tars are **accepted**, and the member list is silently truncated.
3. A corrupt zip deflate stream escapes rollback, so partial files are left behind.
4. JSON parsing has unbounded memory amplification. A 57 MB synthetic document caused an OOM kill.

The host-class guard does not implement the substring and path patterns of §1.1 rule 8, although its docstring says it mirrors §1.

## Findings

| ID | Sev | Location | Description | Reproduction (synthetic) | Recommended fix |
|---|---|---|---|---|---|
| RT-B6-01 | BLOCKING | `archive.py:158` (`for info in archive`), budget at `:137` | `tarfile` reads every pax (`x`/`g`) and GNU `L`/`K` header's data fully into memory before yielding a member. These headers are never passed to `_Budget`, so the ratio, total-size and member limits do not see them. This bypasses the A-4 decompression-bomb limit, and the A-4 fixture does not cover it. | A 407,832-byte `.tar.gz` holds one pax `x` header of 400 MiB zeros and then a 3-byte `a.csv`. It was **accepted**, and max RSS went from 27 to 534 MB. A 200 MiB GNU long-name header took RSS to 438 MB before the refusal. Scaling the header size exhausts RAM. | Wrap the decompressed stream in a byte-counting reader that is capped at `max_ratio × archive_size` and `max_total_bytes`, covering headers as well as data. Or parse tar headers with a bounded custom reader, or cap the size of extended headers (for example 64 KiB) before tarfile reads them. Run extraction under a memory rlimit (see gap G-1). Add fixtures. |
| RT-B6-02 | MAJOR | `archive.py:158`, `:192-264` | Corruption is silently accepted. (a) A garbage header block mid-tar ends iteration as if the archive had ended, so later members disappear and no error is raised. (b) A gzip CRC or trailer failure is never detected, because the stream is not read to EOF. Trailing data after the end-of-archive blocks is also ignored. This breaks "never silently drop malformed data". It is caught only if the archive hash is checked against an *independent* expected hash. | `a.csv` + 512×`\x01` + `b.csv`: accepted, and only `a.csv` was returned. A valid `.tar.gz` with its CRC byte flipped: accepted. A `.tar.gz`/`.tar.xz` with 40 bytes corrupted mid-stream: accepted, with only the first member. | After iterating, require two zero end blocks at the expected offset. Read the compressed stream to EOF so the CRC is verified. Refuse any non-zero trailing data. Use `tarfile.open(..., errorlevel=2)` and treat `InvalidHeaderError` at a non-zero offset as a refusal. |
| RT-B6-03 | MAJOR | `archive.py:255-266`; module docstring | A corrupt zip deflate stream raises `zlib.error`, which is not caught. There is no rollback, the exception is not `ArchiveRefusedError`, and a partial file is left in the destination. The same applies to `lzma.LZMAError` and `ValueError` paths. This contradicts the claim that a failure "removes everything this call created". | A zip with two deflated members, the second with bytes 2-11 of its compressed data inverted: raw `zlib.error`, and `a.csv` and a partial `b.csv` remained. | Catch every exception (`BaseException`, re-raised after cleanup) around `_write_members` and roll back. Write into a staging subdirectory and rename it into place only on success, as a completion marker, so a crash mid-extraction cannot look complete. |
| RT-B6-04 | MAJOR | `strict_parse.py:18`, `:60-81`, `:84` | Memory and CPU are unbounded inside the 256 MiB limit. `[{},{},...]` amplifies about 50× in RSS. The pure-Python bracket scan costs about 1 s/MB. On this 2.7 GB host the OOM killer can take a co-resident collector, which is irreplaceable data. | A 5.7 MB JSON document gave +281 MB RSS and took 5.8 s. A 57 MB JSON document: the process was killed (rc 137). | Add a lower per-file limit for whole-document JSON, and prefer JSONL with a per-line byte cap. Add a per-document element-count cap. Enforce RLIMIT_AS and RLIMIT_CPU in the parse subprocess (G-1). |
| RT-B6-05 | MAJOR | `hosts.py:29-47`, docstring `:10-13` | §1.1 rule 8 says a host whose first label *contains* `api`, `stream`, `ws`, `feed`, `quote`, `ticker`, `price`, `marketdata`, `rpc` or `md` is `live-data`. Any path containing `/api/`, `/v<digits>/`, `/graphql`, `/ws` or `/stream`, or a `.json`/`.jsonl`/`.csv` endpoint, is also `live-data`, unless the owner has classified that exact host **and path prefix**. The code only matches exact labels or `*-x`/`x-*` patterns, ignores paths, and keys decisions by host only. | `restricted_class_pattern` returns None for `api2`, `apis`, `openapi`, `feed`, `quotes`, `ticker`, `prices`, `marketdata`, `md`, `ws1`, `streamer`, `rpc2`, `data2`, `clob-staging`, `websocket`, `eu.api.*` and `polygon-mainnet.g.alchemy.com`. `UrlAllowlist.build(["https://files.vendor.com/api/v2/trades.json"])` succeeds without a decision. | Implement rule 8 literally (substring match on the first label, plus path patterns). Key decisions by (host, path-prefix). Validate each decision against the committed §1.5 table. |
| RT-B6-06 | MINOR | `hosts.py:100-111` | Server-normalization confusions pass the prefix check: `..;` segments (Tomcat/Spring traversal), double encoding `%252e%252e`, IIS `%u002e`, and `;` path parameters. Their impact depends on the server, and the host is still pinned. | `https://files.vendor.com/datasets/btc/..;/live/api` was ALLOWED under prefix `/datasets/btc/`. | Refuse `;`, `%25`, and `%` not followed by two hex digits. Or allow only unreserved characters plus `/`. |
| RT-B6-07 | MINOR | `quarantine.py:129-144` | TOCTOU: the file is hashed and sniffed by path and then renamed by name, so a swap between the check and the rename releases unverified bytes. This needs a concurrent writer in the quarantine directory. | `check_format` was monkeypatched to `os.replace` the file after the checks passed. The released bytes were `b'\x80\x04EVIL'`. | Hash, sniff and `fstat` through one fd. After the rename, `fstat` the target and compare st_dev/st_ino with the hashed fd, then re-hash. Keep quarantine writable only by the intake process. |
| RT-B6-08 | MINOR | `formats.py:88-127` | Sniffing is magic-only. Protocol 0 and 1 pickles (ASCII) pass as CSV/TEXT. `PAR1`+pickle+`PAR1` passes as Parquet. Notebook JSON passes as `.json`. Shebang-less scripts, Mach-O, PDF and 7z pass as text. This is harmless only while no reader ever deserializes them, so the A-4 "pickle disguised as Parquet" fixture is weaker than it looks. | `pickle.dumps(os.system, protocol=1)` as `x.txt`, and `b"PAR1"+pickle.dumps([1],4)+b"PAR1"` as `x.parquet`: both PASS. | Rely on the pinned readers (G-2) for real validation. Validate the Parquet footer and metadata length. Add the Mach-O, 7z, PDF and RAR signatures. |
| RT-B6-09 | MINOR | `strict_parse.py:60-81` | JSON accepts exponents (`1E+999999999`), `-0.0` and lone surrogates (`"\ud800"`). `parse_decimal_field` rejects exponents, so the two are inconsistent. A huge exponent can raise later in Decimal arithmetic or quantize. | All three were accepted. | Reject exponents, or bound them. Reject lone surrogates. |
| RT-B6-10 | MINOR | `strict_parse.py:96-118` | The CSV parser accepts CR-only line endings, embedded newlines and whitespace-distinct headers (`a` vs ` a`). | `b"a, a\n1,2\n"` gives the header `('a',' a')`. | Refuse untrimmed headers, and pin the line terminator per source. |
| RT-B6-11 | MINOR | `archive.py:139-153` | The case-fold uniqueness claim misses implicit parent directories. File `A` and member `a/x.csv` are both accepted, which would collide on a case-insensitive filesystem. | A tar holding `a/x.csv` and `A` was accepted. | Track case-folded names for implicit directories as well. |
| RT-B6-12 | MINOR | `archive.py:17`; `records.py:515`; `quarantine.py` | Integration gaps: nothing calls `check_format` on extracted members, though the docstring claims it. Receipts exist only in memory, so a crash loses the hash-on-receipt record. The manifest is not cross-checked against the approval (source URL in the allowlist, `approval_id`, formats, size against expectation). `acquisition_gate_failures` takes caller-asserted booleans and string-only decision paths, and does not check existence or commit. If the manifest hash is derived from the receipt, the release hash check is tautological. | Code reading. | Add an orchestrator, persist receipts, add the cross-checks, and verify the cited decision files in git. |
| RT-B6-13 | MINOR | `backup.py:144-161` | It does not require the backup and restore directories to be distinct (or on different devices). If they are the same, a raw `FileExistsError` is raised. The "restore" is a local copy, not a restore from the actual backup medium. There is no free-space precheck and no directory fsync. | Code reading. | Require distinct directories, record the device/medium, and run A-3 against the real backup target. |

## Remaining before A-4 can pass (not implemented; expected gaps)

- **G-1** Parsing and extraction do not yet run in a separate process with no network, no read access to `~/pmv-credentials`, `~/.ssh` or `.git`, no privilege escalation, write access only to the output directory, and memory/CPU/file-size rlimits. Several of the findings above rely on this missing containment.
- **G-2** There are no pinned, patched Parquet or DBN readers. Only magic bytes are checked. Compressed DBN (`.dbn.zst`) and `.csv.gz` have no supported path.
- **G-3** Dependency hash-lock and per-dependency review are not yet evidenced for the reader stack.
- **G-4** There is no fetcher. Still missing: re-classification of every redirect (rule 10), refusal of cross-host redirects, DNS/IP pinning (SSRF and private ranges), download size caps, Content-Length lies, and a free-disk precheck at intake.
- **G-5** "Readers never resolve remote paths" cannot be tested until readers exist.
- **G-6** The orchestrated pipeline (fetch → quarantine → manifest → extract → per-member format check → release into the protected raw store, run outside agent sessions) and its fault-injection tests do not exist (A-7).
- **G-7** Not in this code: the A-3 owner backup policy, an off-device restore test, and the committed F-09 denies.

## Verdict

**May this code be recorded as "A-4 tooling reviewed: no unresolved BLOCKING finding"? NO.** RT-B6-01 is BLOCKING. RT-B6-02 to RT-B6-05 are MAJOR and should be fixed before any real acquisition. Gaps G-1 to G-7 must also be closed before A-4 can pass. Recommendation: **revise**.

## Re-verification (round 2)

- **Date:** 2026-10-16.
- **Scope:** the revised uncommitted `src/pmv/acquisition/*`, plus the new `tests/failure_injection/test_acquisition_review_regressions.py`.
- **Suite:** 277 passed (targeted run; `check.sh` not run).
- **Probes:** p1–p6 were re-run unchanged, except that p4 was renamed to the new `host_restriction` API. New probes p7–p10 target the new code.
- **Rules:** synthetic inputs in `$TMPDIR` only, no network, and no edits to `src/` or `tests/`.

### Dispositions

| ID | Disposition | Evidence |
|---|---|---|
| RT-B6-01 | PARTIALLY FIXED | **Fixed path:** the direct pax and GNU long-name bombs from p1/p2 are now refused by the 64 KiB cap, and RSS stays flat. **Open path:** the cap can be bypassed through a pre-scan/`tarfile` parser differential (RT-B6-14), so memory amplification of about 250× the archive size is still reachable. |
| RT-B6-02 | FIXED | All of these are now refused: a mid-archive garbage block, a bad gzip CRC, corrupt gzip and xz streams, a truncated stream, and trailing data after the end marker (p2, p3). |
| RT-B6-03 | FIXED | A corrupt zip deflate stream now raises `ArchiveRefusedError`, and the destination is left empty. `BaseException` paths roll back. |
| RT-B6-04 | PARTIALLY FIXED | The 16 MiB whole-document cap and `iter_jsonl` per-line cap hold. The worst-case 16 MiB `[{},...]` still grew RSS by 805 MB. This is now bounded, and the residual depends on the G-1 rlimit. |
| RT-B6-05 | FIXED (minor residual RT-B6-16) | Every host-label case from round 1 is now restricted. `/api/`, `/v2/`, and `.csv`/`.json` paths need an exact host-and-prefix decision. |
| RT-B6-06 | FIXED | `..;`, `%252e`, `%u002e`, `;` parameters, and all `%` are refused. |
| RT-B6-07 | FIXED (quarantine side) | The p6 race now releases the hashed bytes `b'a,b\n1,2\n'`. Residual: the partial copy in the destination is re-opened by name, so it is only safe while the destination has a single writer. |
| RT-B6-08 | PARTIALLY FIXED | Mach-O, PDF, 7z, RAR, wasm, and SQLite signatures are now refused. Still accepted: protocol 0/1 pickles as CSV/TEXT, `PAR1`+pickle+`PAR1` as Parquet, and notebook JSON. This remains dependent on G-2 readers. MINOR. |
| RT-B6-09 | FIXED (minor residual RT-B6-15) | Exponent bound, integer-digit bound, and lone-surrogate refusal work. `-0.0` is still accepted (acceptable). |
| RT-B6-10 | FIXED | A bare CR and a padded header (`" a"`) are both refused. |
| RT-B6-11 | FIXED | A file `A` alongside `a/x.csv` is refused as a case-fold collision. |
| RT-B6-12 | PARTIALLY FIXED | Extracted members are now format-checked (but see RT-B6-18). `manifest_gate_failures` was added. **Still open:** receipts remain in memory only, and gate flags and decision paths are caller-asserted. The docstrings now state these limitations honestly. These items roll into G-6. |
| RT-B6-13 | PARTIALLY FIXED | Source, backup, and restore directories must now be disjoint. **Still open:** a real-medium restore and directory fsync belong to G-7. |

### New findings

| ID | Sev | Location | Description | Reproduction | Fix |
|---|---|---|---|---|---|
| RT-B6-14 | BLOCKING | `archive.py:229-277` vs `tarfile` | **Parser differential.** The pre-scan and `tarfile` interpret the same bytes differently, so the pre-scan's guarantees do not bind the parser that actually extracts. (a) A directory member (`5`, or `\0` with a trailing slash) with nonzero size: the pre-scan skips its data, but `tarfile` parses that data as further headers. (b) `tarfile._proc_pax` parses the whole block-padded buffer, while the pre-scan checks only `data[:size]`. A `size=` record placed in the padding is therefore honored by `tarfile` and never seen by the pre-scan. The member-count cross-check can be balanced: a hidden member can swallow the next real one. | p7-B: a 2.3 MB `.tar.gz` holds a directory member whose data hides a 300 MiB GNU long-name header. RSS grew 27→617 MB before the name was refused, so the 64 KiB cap was bypassed. p7-A with `check_formats=False`: the archive was accepted as `[('hidden.csv', 1024)]`, a member the pre-scan never saw. p7-C: the size override in the padding was applied (`a.csv` read past its declared 3 bytes), and only the format check refused it. | Refuse nonzero size on directory members, and refuse any non-zero padding after metadata. Better: extract from the pre-scan's own validated header walk (one parser), not from a second `tarfile` parse. |
| RT-B6-15 | MINOR | `strict_parse.py:63-67` | `Decimal("1e99999999999999999999")` raises a raw `decimal.InvalidOperation`, not `StrictParseError`. It still fails closed, but callers that catch only `StrictParseError` will crash. | p9 `hugeexp`. | Catch `ArithmeticError` in `_parse_float`. |
| RT-B6-16 | MINOR | `hosts.py:51-52` | Path patterns are case-sensitive: `/API/`, `/V2/`, `/GraphQL` and `/WS` are allowed. `.csv/` and `.ndjson` endpoints are allowed. Chain-RPC hosts without the tokens are not caught (`*.alchemy.com`, `*.infura.io`), and neither is `eu.api.*`. This complies with the doc text but is weaker than its intent. | p9, p4. | Lower-case the path before matching. Add `.ndjson` and trailing-slash forms. Rely on exact A-1 approval for RPC hosts. |
| RT-B6-17 | MINOR | `archive.py:431-440` | The pre-scan and `tarfile` open the archive path separately, so a writer that swaps the file between the two reads defeats the pre-scan. | Code reading. | Open once and pass the same fd/handle to both. |
| RT-B6-18 | MINOR | `archive.py:400-413` | The per-member format check is head-only. NUL and invalid UTF-8 after byte 8 are accepted (quarantine uses `check_text_stream`; archive does not). | p10: `x.csv` with `\x00\xff\xfe` at its end was accepted. | Call `check_text_stream` for text formats. |
| — | MINOR (carried) | `archive.py:156` | A zip with prepended junk is still accepted (p2 `zip_prefixed`). | p2. | Require the first local header at offset 0, and require the central directory offset to be consistent. |

### Still-missing A-4 items

Unchanged: G-1 (isolated, rlimited, no-network parse process), G-2 (pinned Parquet/DBN readers), G-3 (dependency hash-lock and review), G-4 (fetcher: redirects, DNS/IP pinning, size caps), G-5 (remote-path test), G-6 (end-to-end pipeline and persisted receipts), G-7 (A-3 policy, off-device restore, committed F-09 denies).

### Verdict (round 2)

- **Reviewed code: "no unresolved BLOCKING finding"? NO.** RT-B6-14 (BLOCKING) is open. RT-B6-01 cannot close until RT-B6-14 is fixed.
- **A-4 satisfied? NO,** independently of the above. G-1 to G-7 remain. Even after RT-B6-14 is fixed, only the narrower statement "reviewed code has no unresolved BLOCKING finding" could be recorded, never "A-4 satisfied".
- **Recommendation:** revise.

## Re-verification (round 3)

- **Date:** 2026-10-16.
- **Scope:** the revised uncommitted `src/pmv/acquisition/*`, which now uses its own tar walker (`_walk_tar`) with no `tarfile` in the extraction path, plus the round-2 regression tests.
- **Suite:** 301 passed (targeted; `check.sh` not run).
- **Probes:** p1–p10 re-run. New probes p11–p13 attack the walker: compressed multi-stream input, trailing data, GNU vs ustar header fields, prefix/NUL/size-field tricks, pax and long-name combinations, all typeflags, and an archive swapped between the two passes.
- **Rules:** synthetic inputs in `$TMPDIR` only, no network, no edits to `src/` or `tests/`.
- **Governance:** the coordinator reports that the governance-document edits are owner-authorized under `docs/decisions/2026-10-16_b06_governance_continuity_sync.md`. They are not reviewed here.

### Dispositions

| ID | Disposition | Evidence |
|---|---|---|
| RT-B6-01 | FIXED | The 400 MiB pax bomb (p1) and the 200 MiB GNU long-name header (p2) are refused before any allocation, with RSS flat at 27/223 MB. |
| RT-B6-02 | FIXED | Mid-archive garbage, a bad gzip CRC, corrupt gz/xz streams, a truncated stream, trailing data after the end marker, and a missing or single end block are all refused (p2, p3, p11). |
| RT-B6-03 | FIXED | A corrupt zip deflate stream is refused and the destination is left empty. |
| RT-B6-04 | FIXED (residual to G-1) | The default cap is now 4 MiB. The 16 MiB worst case is refused. The worst case within the cap is about 200 MB RSS. |
| RT-B6-05, -06, -16 | FIXED | Path patterns are matched case-insensitively. `.ndjson` and `x.csv/` are restricted. `eu.api.*`, `*.alchemy.com`, `*.infura.io` and `gamma-api.polymarket.com` are restricted (p4, p9). Residual: `RESTRICTED_DOMAINS` is a finite list. Exchange and price-display domains (for example coinbase, binance, kraken, cmegroup) depend on exact A-1 listing. |
| RT-B6-07 | FIXED | p6 releases only the hashed bytes. The copy is checked through its writing fd. |
| RT-B6-08 | OPEN, MINOR (unchanged) | Protocol 0/1 pickle as CSV/TEXT, `PAR1`+pickle+`PAR1`, and notebook JSON all still pass `check_format`. This rests on G-2. |
| RT-B6-09, -10, -11, -15, -18 | FIXED | A huge exponent gives `StrictParseError`. Bare CR and padded headers are refused. Case-fold collisions are refused. A NUL after byte 8 in an extracted CSV is refused. |
| RT-B6-12, -13 | PARTIALLY FIXED (unchanged) | The remaining items belong to G-6 and G-7. |
| RT-B6-14 | FIXED | Directory entries with nonzero size are refused. Non-zero padding after metadata is refused, which kills the pax-override-in-padding trick. Types other than 0/NUL/5/x/L are refused (1, 2, 7, g, K, S, V, M, N, D tested). Prefix `..` and `/etc` are refused. Base-256, internal-space and NUL-led size fields are refused. Because one parser now serves both passes, the round-2 differential no longer exists. |
| RT-B6-17 | FIXED (residual → RT-B6-19) | The two passes now compare entry lists and raw-archive hashes. |
| zip-prefix (carried) | FIXED | A zip with leading data is refused. |

### New findings

| ID | Sev | Location | Description | Reproduction | Fix |
|---|---|---|---|---|---|
| RT-B6-19 | MINOR | `archive.py:515-545` | The second (writing) pass does not re-apply the budget and is compared with the plan only at the end. A file swapped between passes can write up to the walker's stream limit (about ratio × original size), outside the disk-free precheck, before rollback. This needs a concurrent writer to the archive in quarantine. It fails closed and rolls back. | p13: the plan was 4 bytes, the swap wrote 20,000,000 bytes, then "archive changed between validation and extraction" was raised and the destination was left empty. | Compare each yielded entry with `planned[i]` before writing it, and refuse extra entries immediately. Cap bytes at the planned total. |
| RT-B6-20 | MINOR | `archive.py:196-208` | Python's bz2 and xz readers silently ignore trailing non-stream bytes after the last compressed stream, so the "no trailing data" claim does not hold at the container level. gzip refuses this. The raw-file hash still covers those bytes, and nothing is extracted from them. xz with trailing zero bytes is refused while bz2 is accepted, an inconsistency that is harmless. | p11: `bz2_trailing_garbage` and `xz_trailing_garbage` were accepted. | Use `BZ2Decompressor`/`LZMADecompressor` directly and refuse non-empty `unused_data` after the final stream. Or document it as accepted, since it is hash-covered. |
| RT-B6-21 | MINOR | `archive.py:332-339` | Name ambiguity. Both a pax `path` and a GNU long name are accepted, and pax wins. Duplicate pax `path` keys are accepted, and the last wins. For `ustar  ` (GNU) magic, bytes 345+ (atime/ctime) are read as a ustar prefix. Other tools may name the member differently, which matters for owner inspection and provenance comparisons. This is not an escape, because every name still passes `safe_member_name`. | p12: `L_then_pax`/`pax_then_L` gave `pax.csv`, and `pax_dup_path_keys` gave `two.csv`. p11: a GNU header with an atime field gave `14737327162/a.csv`. | Refuse duplicate pax keys, refuse pax `path` together with `L`, and ignore the prefix field for GNU magic (or refuse a non-zero prefix under GNU magic). |
| RT-B6-22 | MINOR | `quarantine.py` | After the fd-based check, the partial is still renamed by name. A writer in the destination directory could swap it between the check and the rename. The destination is the protected store, so this is low likelihood. | Code reading. | `fstat` the target after the rename and compare dev/inode with the checked fd, or use `linkat` from the fd. |

### Still-missing A-4 items

G-1 to G-7 are unchanged:
- G-1: an isolated, rlimited, no-network parse process.
- G-2: pinned Parquet/DBN readers.
- G-3: dependency hash-lock and review.
- G-4: a fetcher.
- G-5: the remote-path test.
- G-6: the end-to-end pipeline and persisted receipts.
- G-7: the A-3 policy, an off-device restore, and committed F-09 denies.

### Verdict (round 3)

- **Reviewed code: "A-4 tooling reviewed: no unresolved BLOCKING finding"? YES.** This applies to the code in scope at this working-tree state only. The open findings are MINOR: RT-B6-08, -19, -20, -21 and -22. Any later change to `src/pmv/acquisition/` requires re-review.
- **A-4 satisfied? NO.** G-1 to G-7 remain unimplemented. This verdict must not be recorded or read as A-4 passing, or as permission to acquire.
