# Raw Capture Storage (Phase 0 Step 5)

Raw source data is preserved byte for byte, with provenance, in a filesystem store outside Git. Implementation: `src/pmv/raw_format.py`, `src/pmv/raw_manifest.py`, `src/pmv/raw_storage.py`. Manifest schema document: `schemas/raw_manifest_v1.json`.

This step stores and verifies raw captures only. It does not connect to any venue or source, normalize, deduplicate, or interpret payloads.

## Configuration

`[raw_storage]` in `configs/<environment>.toml`, all optional and all currently unset:

| Key | Meaning |
|---|---|
| `root` | Absolute path of the store. Must be outside the Git working tree, owned by the current user, and not writable by group or others. No default. **In every non-`test` environment it must resolve inside `~/pmv-protected/raw`** (see below). |
| `warning_free_bytes` | At or below this many available bytes: structured warning and a `disk_warning` event; capture continues. |
| `hard_stop_free_bytes` | At or below this: no new captures; an active capture stops accepting payloads, records `disk_hard_stop`, and finalizes its captured prefix. Must leave room for finalization. |
| `retention_class` | Identifier recorded in manifests, or unset. |
| `backup_policy_id` | Identifier recorded in manifests, or unset. |

`warning_free_bytes > hard_stop_free_bytes > 0`. Capture operations fail closed while `root` or either threshold is unset. Free space is read with `statvfs` before each append and before finalization; this narrows but cannot close the window in which the disk can still fill (btrfs free space is approximate, and btrfs metadata exhaustion can affect even renames).

### Real raw data lives in the protected area (owner-approved 2026-10-14, Step 11 F-01)

Real market captures are holdout-eligible plaintext. The deterministic collector may write future observations, but Claude and development agents must never be able to inspect the unreleased raw dataset.

- **The rule.** In the `development`, `shadow`, and `production` environments, `[raw_storage].root` must resolve inside `~/pmv-protected/raw`, either that directory or a descendant. It is checked both lexically (after `..`) and after resolving symlinks, so siblings, `../` traversal, and symlink escapes are refused.
- **Agent sessions cannot read it.** `~/pmv-protected` is denied to the built-in Read and Edit tools and to the Bash sandbox (`.claude/settings.json`). The collector therefore runs outside Claude Code.
- **Where it is enforced.** `pmv.config.load_config` refuses a non-test configuration with a root outside the protected location, so every entrypoint that loads a real configuration fails closed, including a future collector. `python -m pmv.data_access_guard check-config`, run by `scripts/check.sh`, loads every committed `configs/*.toml` and reports any violation.
- **What is exempt.** The low-level store (`RawCaptureStore`, `RawStorageConfig`) is deliberately not restricted, so unit tests and synthetic fixtures keep using temporary directories. The `test` environment is likewise exempt.
- **What agents work with.** Agents work only with synthetic fixtures until the H-2 per-row release tool (F-08, decided in batch 4) is built, reviewed, and approved (`docs/release_tool_design.md`).

## Layout

```
<root>/
  .capture_ids/<capture_id>                         permanent ID reservation (source_id, feed_id)
  .inprogress/<capture_id>/                         active or interrupted capture
  quarantine/<capture_id>/                          quarantined capture + quarantine.json
  raw/v1/<source_id>/<feed_id>/YYYY/MM/DD/<capture_id>/
      records.pmvraw                                raw object (0400)
      manifest.json                                 authoritative manifest (0400); directory 0500
  catalog/captures.v1.jsonl                         rebuildable index
  catalog/storage-events.v1.jsonl                   authoritative post-finalization facts
```

`YYYY/MM/DD` is the UTC date of the capture start, the same instant embedded in the capture ID: `YYYYMMDDTHHMMSS.ffffffZ_<32 lowercase hex>` (128 random bits). Reservations are permanent; an ID is never reused, even after quarantine.

Source, feed, and endpoint identifiers match `[a-z][a-z0-9_]{0,63}` and come from our code or configuration, never from URLs or server-provided strings.

## Historical acquisitions (B07)

Historical files acquired by the acquisition pipeline (`src/pmv/acquisition/pipeline.py`; `docs/acquisition_readiness.md`) are kept in their own tree. They are not capture frames. In a real run, the store root must resolve inside `~/pmv-protected/raw`. A synthetic run refuses any root inside `~/pmv-protected`.

```
<store_root>/acquisitions/v1/
  journal.jsonl                                      hash-chained receipt and state journal
  .lock                                              one run at a time
  work/<acquisition_id>/{quarantine,evidence,scratch}/  working area (scratch: derived plaintext, deleted)
  store/<source_id>/<acquisition_id>/<file>          exact received bytes (0400); directory 0500 when complete
  store/<source_id>/<acquisition_id>/acquisition.json   provenance record (0400)
  rejected/<acquisition_id>/  orphans/<acquisition_id>/  set-aside bytes, never deleted
```

Storing is not releasing (A-8): nothing here is agent-visible. No real acquisition has run.

## Segmented prospective capture, frame format v2 (B08)

Real collection uses the segmented v2 store (`src/pmv/capture_store.py`, format `src/pmv/capture_format.py`), not the v1 store. **Raw format v1 no longer starts a capture outside the `test` environment** (`LegacyFormatRefusedError`): v1 lacks monotonic receipt time and message direction (Step 11 F-12). Reading and verifying v1 captures is unchanged. Decision record: `docs/decisions/2026-10-16_b08_prospective_capture_hardening.md`.

Nothing here authorizes live capture. Every demo or production session needs an owner-approved endpoint in `pmv.capture_environment.APPROVED_CAPTURE_ENDPOINTS`, **which is empty**, so every real session refuses.

### Sessions and segments (F-11)

A **session** is one collector run against one source endpoint. It is written as a hash-chained sequence of bounded, immutable **segments**. A segment rolls over when it reaches the session's explicit `SegmentPolicy`:
- a byte bound, at most `MAX_SEGMENT_BYTES` (128 MiB);
- a frame-count bound;
- a monotonic-duration bound.

There are no defaults. A crash can damage only the open segment.

```
<root>/capture/v2/
  sessions/<session_id>                             permanent session reservation (closed schema)
  open/<segment_id>/segment.pmvraw.partial          the open segment, flock-locked while live
  quarantine/<segment_id>/                          interrupted or stopped segments + quarantine.json
  salvage/<segment_id>/{salvaged.pmvraw,salvage.json}   salvaged valid prefixes (0400, dir 0500)
  segments/<source>/<feed>/YYYY/MM/DD/<session_id>/<index>/{segment.pmvraw,manifest.json}
                                                    finalized segments (0400, dir 0500)
  normalized/<session_id>/<key>/{observations.json,labels.json}   normalized artifacts
```

`session_id` has the capture-ID form. `segment_id` is `<session_id>.<index>`, with a six-digit index.

**Segment finalization order.** Each step is synced before the next:
1. sync the object;
2. re-read and fully verify it against the running size, hash, and frame count;
3. rename the partial object (no-replace);
4. write the manifest (`pmv.capture.segment_manifest` v1, closed schema), then rename it (no-replace);
5. make both files 0400;
6. create the destination path;
7. confirm the open directory's identity;
8. move it into `segments/` with `RENAME_NOREPLACE`;
9. make it 0500.

A segment is accepted exactly when its directory is in `segments/`.

**Recovery** never resumes a segment:
- `recover()` moves every unlocked directory in `open/` to `quarantine/`, with a closed-schema record, whatever it contains.
- A live (locked) segment is never touched.
- A session whose open segment was quarantined has ended. The collector starts a new session.
- Interrupted salvage or artifact writes leave `.staging-*` directories. These are reported (`stale_staging`), never read, renamed, or deleted by the tool.
- `reconcile()` verifies every finalized segment and tightens any left 0700 by a crash.

**Salvage** (`salvage(segment_id)`) is an explicit, deterministic step under rule `longest_valid_frame_prefix_v1`:
- It copies the longest prefix of a quarantined object made only of complete, fully valid frames: lengths, canonical closed headers, sequence continuity, and payload SHA-256.
- It records the original object's name, size, and SHA-256, the prefix, the tail size, and its disposition (`none`, `incomplete_frame`, or `invalid_frame`).
- It never changes the quarantined bytes. It never repairs anything, and it never uses anything after the first bad frame.
- An object with no valid header is refused (`SalvageRefusedError`).
- Repeating salvage verifies and returns the existing result. A changed input is an integrity failure.
- A salvaged segment always **ends** its session's readable chain.

**Reading.** `read_session` follows the chain from segment 0. Each segment must name its predecessor's SHA-256 and last sequence, and match the session's reservation: source, environments, clock domain, and start. The read stops at the first segment that is not finalized, and reports why:

| Status | Meaning |
|---|---|
| `complete` | The last segment ends with `session_closed` |
| `open` | The next segment is still open |
| `ends_with_salvage` | The chain ends at a salvaged prefix |
| `truncated` | The chain ends at a missing, quarantined but unsalvaged, or never-opened segment |

A gap is never bridged: later segments are reported as `unreachable_indices`. `iter_frames` re-verifies every byte, and enforces session-wide sequence continuity and connection discipline.

### Frame format v2 (F-12, F-27)

Magic `PMVRAW2\n`; v1 framing (4-byte header length, 8-byte payload length, canonical JSON header, payload). A v1 object is never read as v2, or the reverse.

| Kind | Fields |
|---|---|
| `segment` (first frame only) | `session_id`, `segment_index`, `previous_segment_sha256` and `previous_last_sequence` (null for segment 0), `source_id`, `feed_id`, `endpoint_id`, `transport`, `deployment_environment`, `venue_environment` (`synthetic`, `demo`, `production`), `clock_domain`, `session_started_at`, `written_at`, `monotonic_ns` |
| `payload` | `direction` (`inbound` or `outbound`), `connection`, `observed_at`, `monotonic_ns`, `source_timestamp` (inbound only, caller-supplied), `payload_sha256`, `malformed` (inbound only), `written_at` |
| `event` | `event_type`, `connection` (required for connection events), `written_at`, `monotonic_ns` |

Event types:
- `connection_opened` and `connection_closed`;
- `gap` and `rate_limit`;
- `disk_warning` and `disk_hard_stop`;
- `source_clock_regression`, `local_clock_regression`, and `monotonic_regression`;
- `session_closed`, which must be the object's last frame.

Rules:
- **Ordering.** One `sequence` counter covers a whole session, across segments. Sequence, not any clock, is the ordering authority. Regressions of any clock are recorded as events, never repaired or reordered.
- **Monotonic time.** `monotonic_ns` is `CLOCK_MONOTONIC`. It is comparable only within one `clock_domain` (the boot identity, `/proc/sys/kernel/random/boot_id`). It measures intervals and order within a session, and it is never a timestamp.
- **Environment identity** is carried by each segment's hash-chained header, which every frame of that segment sits behind (interpretation B8-2).
- **Venue sequence numbers** stay inside payloads. The raw layer never parses payloads (B8-3).
- **Outbound frames** hold application-level messages PMV sent (for example subscriptions). Handshake and authentication material never passes through the store (F-03).

### Environment boundaries (F-37, RT-4)

`pmv.capture_environment.authorize_capture` is the only producer of the `CaptureAuthorization` a session needs:

| Deployment | May capture | Store root |
|---|---|---|
| `test` | `synthetic` only, on RFC 2606 reserved hosts (`.example`, `.test`, `.invalid`) | Never inside the protected raw location, lexically or after symlinks |
| `development` | `demo` or `production`, from an approved endpoint | Inside the protected raw location |
| `shadow`, `production` | `production`, from an approved endpoint | Inside the protected raw location |

- Demo data is protected like real data and is never loaded as data, for any use (`require_data_use`; RT-B2-09).
- Synthetic data is loaded only for tests. Production data is loaded only for research, and that still happens only through the H-2 release path.
- The CLIs that create project records (`python -m pmv.gates create` and `python -m pmv.holdout_log record`) refuse `--environment test` (RT-4).

### Limits

- **Process crashes only.** Fault-injection tests kill a real process at every named boundary (`capture_store.FAULT_POINTS`). They do not model power loss.
- **Durability.** A frame is durable after `sync()` or segment finalization. Frames written before a process crash are kept by the kernel and are salvageable.
- **Memory.** Salvage and the normalized-artifact reader hold one object in memory, bounded by `MAX_SEGMENT_BYTES` plus one frame, and by 1 GiB respectively. Normalization holds one session's observations in memory.
- **No index.** The directory tree is authoritative. Listing sessions walks `segments/`.
- **F-26 is still open:** storage-event claims and their restore dependency.
- **Not proven by tests.** Session records and segment manifests do not prove where bytes came from beyond PMV's own records; the collector must be trusted for that (live capture is not authorized).

## Raw object format `pmv.raw.frames` v1

File magic `PMVRAW1\n`, then frames. Each frame: 4-byte big-endian header length, 8-byte big-endian payload length, canonical JSON header (sorted keys, no spaces, ASCII, no floats), payload bytes.

- Payload frame header (closed): `frame_version`, `kind="payload"`, `sequence`, `received_at`, `written_at`, `source_timestamp` (or null), `payload_sha256`, `malformed`.
- Event frame header (closed): `frame_version`, `kind="event"`, `sequence`, `written_at`, `event_type` (`reconnect`, `rate_limit`, `gap`, `disk_warning`, `disk_hard_stop`, `source_clock_regression`, `local_clock_regression`). Event frames have an empty payload.
- One sequence counter covers both kinds: it starts at 0 and increases by exactly 1. Sequence, not wall-clock time, is the ordering authority.
- `MAX_HEADER_BYTES = 65,536`; `MAX_PAYLOAD_BYTES = 67,108,864` (64 MiB). Readers check every declared length against the maximum and against the bytes remaining before reading it.
- A payload larger than the maximum stops the capture and quarantines it with the payload's size and SHA-256; the raw layer never produces an apparently complete capture that omitted bytes.
- Timestamps are timezone-aware UTC, `YYYY-MM-DDTHH:MM:SS.ffffffZ`. Source, received, and written times are distinct and never substituted. Clock regressions are recorded as events; nothing is reordered or discarded.
- The preserved boundary is the application-level byte sequence delivered to PMV by the HTTP/WebSocket/client layer, not TLS records or packets.
- Malformed, duplicate, and out-of-order payloads are preserved. Callers flag malformed payloads with `malformed=True`; the raw layer never parses payloads.

## Manifest

Closed schema `pmv.raw.manifest` v1 (see `schemas/raw_manifest_v1.json`). Unknown fields, other versions, floats, and noncanonical bytes are rejected. Every string has an exact format or a fixed set of values, so free text (and therefore credentials) cannot be stored. Canonical bytes are `canonical JSON + "\n"`; the manifest's SHA-256 is recorded in the catalog, never inside the manifest. Provenance records the code commit and whether the working tree was dirty (both null if Git identity cannot be determined), the configuration and raw-storage-configuration SHA-256s, the environment, Python version, and platform. It never records a hostname.

## Lifecycle and finalization

States: reserved → in progress → finalized or quarantined. Interrupted captures are quarantined by recovery, never resumed; a replacement gets a new ID. A finalized capture is never modified in place.

Finalization order:

1. Reserve the ID (exclusive create, synced, parent synced).
2. Create `.inprogress/<id>` (0700, parent synced), open it, take an exclusive `flock` held for the capture's whole life, and confirm the name still refers to the locked directory (`st_dev`, `st_ino`).
3. Write `records.pmvraw.partial` (0600) with unbuffered short-write-safe writes; the running hash, size, and sequence advance only after a complete frame. Any write error poisons the capture: no further appends, finalize refused, quarantine is the way out.
4. Sync and close; re-read with the full frame validator; require size, SHA-256, and record count to equal the running values.
5. Rename `.partial` to `records.pmvraw` (no-replace), sync the directory.
6. Write `manifest.json.tmp` exclusively, sync, rename to `manifest.json` (no-replace), sync the directory.
7. Make both files 0400, sync the directory.
8. Create missing `raw/v1/...` path components one at a time (0700), syncing each parent; all on the root's filesystem.
9. Confirm the directory identity again, then `renameat2(.inprogress/<id> → DD/<id>, RENAME_NOREPLACE)`; sync both parents.
10. Make the capture directory 0500, sync it and its parent, release the lock.
11. Append the catalog entry. If this fails, the capture remains finalized and `reconcile()` adds the entry later.

Moves never fall back to a plain rename; if `RENAME_NOREPLACE` is unavailable the store fails closed. Opening the store probes `RENAME_NOREPLACE` and `flock` under the root.

The store re-walks the configured root by path and compares the identity (`st_dev`, `st_ino`) of the root and each managed directory with those opened at startup: at capture start, before building and before and after the final move, around quarantine moves, during recovery, reconcile, and permission tightening, and around catalog and storage-event appends. A mismatch fails closed with "the raw storage root or a managed directory was moved or replaced".

## Recovery and reconciliation

- `recover_incomplete()` opens each `.inprogress` entry without following symlinks and tries a non-blocking lock. Locked entries are active and untouched. If the name no longer refers to the locked directory, the entry is reported as moved concurrently and untouched. Orphans are quarantined: a closed-schema `quarantine.json` is written and synced (an existing valid record is kept), then the directory is moved with `RENAME_NOREPLACE` and both parents are synced. If the record cannot be written, the capture stays in `.inprogress`.
- Reservations with no data are reported as `reserved_no_data` and kept.
- `reconcile()` verifies every finalized capture, adds missing catalog entries, and tightens to 0500 a fully verified capture left at 0700 by a crash between the final move and the permission change. Captures that fail verification are reported, never repaired or deleted. Conflicting catalog entries are an integrity failure.

## Catalog and storage events

Both ledgers are appended under an exclusive `flock` with a single write of one canonical JSON line, then synced. A failed or short write is rolled back by truncating to the size recorded before the append; if rollback fails, the damaged bytes are left in place and an integrity failure is raised.

- `captures.v1.jsonl` is rebuildable. A torn tail left by an earlier crash is isolated with a newline and reported; readers skip malformed lines.
- `storage-events.v1.jsonl` is authoritative and never rebuilt or rewritten. Each entry carries `ledger_seq` (from 0, +1), `prev_entry_sha256` (null for the first), and `entry_sha256` (SHA-256 of the canonical entry without `entry_sha256`). Readers verify canonical encoding, the closed schema, sequence continuity, every hash, and every link. This detects altered, reordered, duplicated, and interior-deleted entries and broken links. It does **not** detect complete entries removed from the end, because there is no separately anchored ledger head in Step 5. A malformed or torn entry is an integrity failure; appends are refused until an explicit recovery procedure is approved.

## Limits

- Fault-injection tests kill a real process at every finalization boundary. They demonstrate process-crash behavior, not host power loss. Durability across power loss depends on the ChromeOS VM and btrfs honoring `fsync`, which cannot be verified from inside the VM.
- Permissions are defense in depth, not write-once storage; the owner can change or delete files.
- Free-space checks cannot prevent `ENOSPC`.
- A backup-and-restore smoke test must succeed before or at the first irreplaceable live capture; no backup destination or retention policy is selected yet.
