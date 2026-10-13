# Raw Capture Storage (Phase 0 Step 5)

Raw source data is preserved byte for byte, with provenance, in a filesystem store outside Git. Implementation: `src/pmv/raw_format.py`, `src/pmv/raw_manifest.py`, `src/pmv/raw_storage.py`. Manifest schema document: `schemas/raw_manifest_v1.json`.

This step stores and verifies raw captures only. It does not connect to any venue or source, normalize, deduplicate, or interpret payloads.

## Configuration

`[raw_storage]` in `configs/<environment>.toml`, all optional and all currently unset:

| Key | Meaning |
|---|---|
| `root` | Absolute path of the store. Must be outside the Git working tree, owned by the current user, and not writable by group or others. No default. |
| `warning_free_bytes` | At or below this many available bytes: structured warning and a `disk_warning` event; capture continues. |
| `hard_stop_free_bytes` | At or below this: no new captures; an active capture stops accepting payloads, records `disk_hard_stop`, and finalizes its captured prefix. Must leave room for finalization. |
| `retention_class` | Identifier recorded in manifests, or unset. |
| `backup_policy_id` | Identifier recorded in manifests, or unset. |

`warning_free_bytes > hard_stop_free_bytes > 0`. Capture operations fail closed while `root` or either threshold is unset. Free space is read with `statvfs` before each append and before finalization; this narrows but cannot close the window in which the disk can still fill (btrfs free space is approximate, and btrfs metadata exhaustion can affect even renames).

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
