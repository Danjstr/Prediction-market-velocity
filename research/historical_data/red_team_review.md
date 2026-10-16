**Status: fresh-context Reliability / Red-Team review of Phase 1 batch 3 (branch `phase1/historical-data-strategy`). Documentation and design only. This is NOT a gate record, NOT an owner decision, and NOT an independent Phase 5 review.** Written 2026-10-16. No market data, dataset, sample, or API host was fetched for it. The reviewer made no network requests and ran no git write operations. This file is the only file it edited.

# Red-Team review: historical data strategy, Phase 2 design, PIT metadata, and batch 3 process events

## Independence and scope disclosure

- **Prior involvement.** This session had no part in writing any batch 3 artifact. Earlier Red-Team sessions, which ran on the same model family, wrote two things this design relies on: the Phase 0 guard findings S-1 to S-6 (`docs/protected_information.md`, including the S-2 `post_fetch_scope_check` that `docs/phase2.md` §1 now cites) and the batch 2 review `research/kalshi/red_team_review.md`. Where this review touches those components, they get no benefit of the doubt.
- **Pre-assertion.** `docs/phase2.md` (Status) and `docs/phase1.md` (batch 3 outputs) say that "Reliability / Red-Team reviewed provenance, licensing, revision, timestamp, and archive risks". That text was written before this review existed. It must not be read as this review's conclusions (RT-B3-15).
- **Documents read:** the batch 3 decision record; `docs/phase2.md`; `research/historical_data/point_in_time_metadata_architecture.md`; `statistician_review.md`; the three `inventory_*.md` files; `feasibility_summary.md` (it appeared during this review); `docs/protected_information.md`; `docs/holdout_access.md` (event types); `docs/backup_and_recovery.md` (raw-data boundary); `HOLDOUT_ACCESS_LOG.md` (Holdout Rules); the guard `CATALOG` in `src/pmv/protected_scope.py`; and `git diff main` for CLAUDE.md, PROJECT_BRIEF.md, START_HERE.md, `docs/conventions.md`, `docs/market_data.md`, `docs/phase1.md`, and `research/sources.md`.
- **Concurrent edits.** Other sessions changed files while this review ran. `feasibility_summary.md` was created, and the `research/historical_data/_sources_*.md` files were removed and merged into `research/sources.md`. Findings refer to the state observed around 02:40 UTC.
- **Not independently verified:** every external fact in the inventories, including vendor terms, retention, timestamp semantics, and dates. This review judges whether the design is safe *given* those claims, and flags the claims whose failure would matter. Library-security facts cited here (pyarrow CVE-2023-47248; Python tarfile extraction filters, PEP 706) come from general knowledge and were not re-fetched. Verify them before relying on them.
- **Severity vocabulary.** BLOCKING, MAJOR, and MINOR are this review's own, as the review charter asked. They are not Phase 5 classifications, not Gate 10 "critical", and not failure-register likelihood or impact. No cross-vocabulary mapping is implied.

## Headline table

| ID | Area | Finding | Severity |
|---|---|---|---|
| RT-B3-01 | Durability | An acquired historical file is often **irreplaceable** (moving Kalshi cutoff, Polymarket 7-day retention, retroactive vendor renormalization, deletable HF repos, subscription-bounded vendors). No backup or restore policy covers it, and `docs/backup_and_recovery.md` expressly excludes raw data | **BLOCKING** for any acquisition |
| RT-B3-02 | Release / embargo | A "bounded download ending before `T0 − m`" is necessary but **not sufficient**. The cut must be content-level, per row and per equivalent observable, decided by the trusted tool, failing closed. No agent-facing release may happen before a cycle, `T0`, and `m` are committed and H-2 is implemented | **BLOCKING** for any release to agents |
| RT-B3-03 | Untrusted files | Acquired archives (tar.zst, zip, Parquet, pickle, DBN, notebooks, bundled "validators") will be parsed by owner-side tooling **outside the Claude sandbox**, as a user in the `sudo` and `disk` groups. There is no safe-parsing requirement | **BLOCKING** for any parser or acquisition tool |
| RT-B3-04 | Provenance | Quality tiers conflict with the inventories' recommendations (mirror-of-mirror sets are put forward as development candidates). No deterministic Q1-reconciliation admission test exists. "VERIFIED-BY-DOC" can rest on LLM-summarized WebFetch output, and one such summary was hallucinated. A provider checksum served from the same host is integrity, not provenance | MAJOR |
| RT-B3-05 | Equivalence catalog | Settlement references and their inputs are missing from the catalog: Pyth gold and BTC, Chainlink, BRTI via DataMine or the Kalshi passthrough, BRTI constituents, CME event contracts, 1OZ/MGC, tokenized gold, vendor archives, Kalshi `live_data`, PolyBolt. Mixed-content archives are not handled. The guard fails closed on these, but the H-2 release tool has no specified catalog | MAJOR (BLOCKING for the release tool) |
| RT-B3-06 | Licensing | No defined licence determination, no split between acquisition-time and production-time licence conditions, and no licence lineage on model artifacts | MAJOR (acquisition-blocking items listed) |
| RT-B3-07 | Timestamps | `docs/phase2.md` §4 calls `vendor_capture_time` "an upper bound for synthetic availability". The direction is wrong and favors the hypothesis. Polygon block-time stamping (seconds, after the match), set against ms/ns underlying timestamps, manufactures the S-8 lead-lag artifact on the prediction-market side, which the `L` ladder does not probe. Coarse timestamps have no interval or ceiling rule | MAJOR |
| RT-B3-08 | Revisions | `docs/phase2.md` §12 says "Labels use the final official version" of an underlying, which conflicts with contracts that settle on the first-published value. Archive tapes are bust-filtered survivors. Archive labels can predate an amendment. There is no chain-finality rule and no upstream-revision detection. Moving tier boundaries can create gaps that cannot be detected | MAJOR |
| RT-B3-09 | Pre-cycle exposure | The DegenHedge card and the search summaries exposed agents to aggregate outcome information about the exact product and hypothesis (calibration against entry price). It is recorded only in uncommitted research notes. Its scope is misdescribed (KXBTC15M only, when it is the BTC observable family, and gold coarsely). Status lines claim "no real observation was shown to any agent" | MAJOR |
| RT-B3-10 | Post-`T0` erosion | Live-updating datasets, cards, papers, and search summaries will carry protected-period aggregates. Web research is rule-governed, not intercepted. The batch 3 base rate is one full exposure in one research pass | MAJOR (BLOCKING for adopting H-1 without conditions) |
| RT-B3-11 | Process events | An attempt on an API host, a terms-barred fetch whose output contained a live index value, attempts on live-value hosts that another document says were "not attempted", and 29 to 50+ proxy refusals that depend on owner clicks | MAJOR (one serious near miss) |
| RT-B3-12 | Governance consistency | CLAUDE.md "at all" against routine incidental exposure. CLAUDE.md and HOLDOUT_ACCESS_LOG.md "oldest/newest ~70/30" against S-11 ("power governs"). PROJECT_BRIEF "before any inspection" against START_HERE "before outcome-dependent inspection". "Guard allows" against the F-08 release path. The S-6 collection rule is stretched to cover acquisition | MAJOR |
| RT-B3-13 | Pressure | Retention urgency ("pull early") is pushing toward acquisition ahead of licence, backup, and release controls | MAJOR |
| RT-B3-14 | Duplicates | Copies of one upstream are treated as cross-checks, but they are not independent. The overlap calibration window forces capture to start long before `T0`. Lossy keys across archives. Re-entry routes | MAJOR |
| RT-B3-15 | Documentation integrity | Pre-written review claims, dangling `_sources_*.md` references, H-8 missing from "H-1 to H-7", inconsistent refusal counts, a stray `.claude/.cc-writes` directory under `research/` | MINOR |
| RT-B3-16 | Calendars | CME 1OZ weekend trade-date assignment, ET-defined Kalshi gold and Pyth candles, and an ambiguous-hour exclusion that is systematic | MINOR |

Overall recommendation: **proceed with conditions** for further design and documentation work. **Revise** before any acquisition, parsing, or release batch. The three BLOCKING findings block the next *implementation* batch only if that batch acquires, parses, or releases real data. They do not block synthetic-fixture implementation of the Phase 2 design.

---

## Findings

### RT-B3-01 (BLOCKING for any acquisition): acquired historical data is irreplaceable and has no backup

**Failure scenario.**
1. PMV pulls Kalshi `/historical/trades` for KXBTC15M while retention is short. The secondary source says about 100 days.
2. The cutoff advances, so the venue no longer serves the oldest data.
3. The single protected-store copy is lost to a disk failure, an accidental re-download that a tool "dedupes" by overwriting, or host loss.

The data then cannot be recovered. The same holds for:
- Databento's pre-2026-08-08 normalization, which can no longer be obtained once the retroactive renormalization has happened;
- Polymarket 1-minute price history (about 7 days);
- HF repos, which can be deleted or rewritten;
- Tardis data, if retention after the subscription is not permitted;
- the SII release that predates the "missing V2 sell-side fills" fix, which development results would cite.

Every result built on the lost acquisition then becomes irreproducible. CLAUDE.md "Reproducibility" says such results "should not drive production decisions".

**Why current text is insufficient.**
- `docs/backup_and_recovery.md` says it "does not provide a backup for raw market data". It ties the raw backup prerequisite to "irreplaceable **live** capture".
- `docs/conventions.md` and `docs/phase2.md` §1 make acquired files immutable raw data, but name no backup.
- The isolated environment holds no `~/pmv-protected`, so acquisition is necessarily owner-side, and nothing defines its durability.

**Fix.**
- Add to `docs/conventions.md` "Historical Data Sourcing":
  > An acquisition that cannot be re-obtained byte-identically from its provider on demand is irreplaceable raw data. The approved raw-data backup policy and its restore smoke test (START_HERE.md Gate 1, `docs/raw_data.md`) apply before it is made. The acquisition manifest records `reproducible_from_provider: yes|no|unknown`, and `unknown` is treated as `no`.
- The backup must preserve the acquisition manifest and the provider version markers with the bytes.
- Restore testing must verify SHA-256 against the manifest, not just that the file exists.

### RT-B3-02 (BLOCKING for any agent-facing release): bounded downloads are not enough

**Are bounded downloads ending before `T0 − m` enough while `T0` is in the future? No.** A requested window is a claim about the request, not about the content.
1. **Before `T0` is declared, "`T0 − m`" is undefined.** Data released then would be inspected before a cycle exists, which breaches START_HERE.md "Evaluation Cycles": the `cycle_id` comes before the first outcome-dependent inspection. Release therefore needs a committed cycle with `T0` and `m` first. That is cheap under prospective formation.
2. **Bulk files cannot be range-requested.** Examples: the Jon-Becker 36 GiB tarball, the SII full release, Kraken quarterly archives, HF repos updated every 3 hours. The file is fetched whole and cut afterwards, so the cut is the control, not the request.
3. **Live-updating sources keep growing past `T0`:** aliplayer1 (every 3 h), TimeSeventeen (daily), RooseveltHonaker, rogerdehe, the Kalshi live tier. Pinning an HF revision is necessary, but a revision's commit time is not the maximum observation time of its content.
4. **One endpoint can mix observation times with as-of state.**
   - Gamma `outcomePrices` and `updatedAt`.
   - Kalshi market objects (`result`, status).
   - The settlement point that `prices-history` appends.
   - Fetch-time quotes in TrevorJS and Jon-Becker.
   - Cumulative volume on contracts whose life crosses `T0 − m`.
   - Cards and READMEs that summarize "to present".

   After `T0`, an acquisition of "pre-`T0`" history can still carry post-`T0` information through these fields.
5. **Lookbacks and labels.** A row before `T0 − m` can be safe while its contract's information interval `I(k)` crosses the boundary. Policy 2 in `docs/phase2.md` purges such contracts, but only if the release tool knows each contract's `I(k)`. For `POST_HOC` rows, `I(k)` comes from post-hoc metadata.

**Can acquisition happen safely before F-08?**
- **Acquisition:** yes, under conditions. It must be done by a deterministic tool, owner-run, outside Claude, into the protected store, licence-cleared (RT-B3-06), backed up (RT-B3-01), and parsed safely (RT-B3-03). It is then a collection, not an exposure. Today `T0` lies in the future, so every byte fetched now predates any prospective protected interval, and holdout risk at fetch time is nil.
- **Release:** no.
- **Tooling, if built before H-2 is decided:** it should already have the H-2 shape, so that nothing needs retrofitting.

**Fix: required release-tool properties (a condition of H-2).**
- Extract each row's observation time from a catalogued field. A row whose time cannot be determined fails closed for the whole file.
- Each file gets an equivalent-observable set: the **union** over its content, derived from the source catalog and not from the caller (RT-B3-05).
- A row is released iff its observation time and every equivalent observable it carries are `< B − m`, and its contract's `I(k)` ends before `B − m`.
- Label-channel and as-of fields are released only for contracts that are development-eligible under Policy 2.
- Anything fetched after `T0` is additionally checked for as-of fields. Those fields are released only where their as-of time is `< B − m`. Otherwise they are stripped and ledgered.
- The first release is durably recorded (S-4 scope freeze).
- Release output is content-hashed and appended to the acquisition manifest.

### RT-B3-03 (BLOCKING for any parser or acquisition tool): malicious and malformed files are unhandled

**Failure scenarios.** The acquisition and parse tooling runs owner-side, outside the Claude sandbox, as a user that the threat model says is in the `sudo` and `disk` groups, on the host that holds `~/pmv-credentials`.
- A **tar archive** with `../` or absolute members, or with symlink or hardlink members pointing into `~/.ssh`, `~/pmv-credentials`, `.git/hooks`, or the repository. Extraction overwrites files or plants code.
- A **zip or zstd bomb.** The 36 GiB `tar.zst` is the extreme case. A small-ratio bomb fills the protected-store disk, and a full disk silently truncates later raw writes, including live capture.
- **Pickle** or `.pt` files in HF repos, which run code on load.
- **Parquet or Arrow** files exploiting deserialization flaws in the reader (pyarrow CVE-2023-47248 affected 0.14.0 to 14.0.0, with arbitrary code execution through extension types; verify the current advisories).
- Pandas or HF `datasets` loaders with `trust_remote_code`, which execute dataset loading scripts.
- **Notebooks**, and the "stdlib validator" DegenHedge ships. Running them violates P3 anyway, but a convenience script will be tempted to.
- DuckDB or Polars reading a URL or `httpfs` path inside a file manifest. That reaches the network during "parsing" and breaks the no-network derivation rule (`docs/phase2.md` §15).
- CSV or JSON that is merely malformed: huge integers, NaN or Infinity, duplicate keys, BOMs, mixed encodings. The result is silent float coercion, which breaks the `Decimal` rule.

**Fix.** Add to `docs/conventions.md`, or a new acquisition section of `docs/raw_data.md`:
> Acquired files are untrusted. Raw bytes are stored and hashed before any parsing. Parsing uses only allowlisted formats (CSV, JSON or JSONL, Parquet, DBN, plain text) with pinned, patched readers. Pickle, PyTorch, joblib, notebooks, scripts, and executables are refused. No dataset-provided code is run, and `trust_remote_code` is never set. Archives are extracted with Python's `filter="data"` (PEP 706) or an equivalent: no absolute or `..` paths, no symlinks, hardlinks, or device members, and limits on total size, member count, and compression ratio, with a disk-space precheck. Parsing runs in a separate process with no network access, no read access to `~/pmv-credentials`, `~/.ssh`, or the repository's `.git`, and write access only to its output directory. Readers never resolve remote paths.

- Add fault-injection fixtures before any real file is parsed: a path-traversal tar, a symlink tar, a 1000:1 bomb, a pickle-in-Parquet-named file, and a disk-full condition.
- Add the acquisition tool's dependencies (`huggingface_hub`, `databento`, `tardis-dev`, any web3 or RPC client) to the locked dependency set with hashes. Each is a reviewed addition. No `pip install` from a README.

### RT-B3-04 (MAJOR): source trust and provenance

**Failure scenarios.**
1. **Mirror-of-mirror.**
   - Lineage that is unclear or broken: BrockMisner (said to mirror aliplayer1, whose pipeline repo returns 404) and its forks obadiaha, heaouwtj, notkali, Radim462, and bmoney1321.
   - Packagings of another party's capture: rhinot (Jon-Becker) and Joseph3222 (pmxt).

   A fork can differ silently, through truncation, re-timestamping, or a fabricated or "filled" BBO. It would pass a schema check.
2. **Poisoning.**
   - An anonymous uploader is easiest. A fabricated or quietly "improved" (survivor-cleaned) dataset is plausible, and DegenHedge is commercially motivated.
   - For on-chain data, a packager that differs from the chain is caught only if PMV actually verifies against the chain. The inventories say a sample is to be verified, but no rule fixes the sample, the threshold, or what happens on failure.
3. **Tier conflict.**
   - `docs/phase2.md` §14 says Q4 ("third-party dump, Kaggle, HF … without traceable provenance or licence") is "not used for development evidence".
   - The inventories and `feasibility_summary.md` nonetheless list aliplayer1 and BrockMisner, pmxt through Joseph3222, `lerchen3`, and papylove as development or depth candidates "after a gap/clock audit".

   A gap audit is a quality check, not provenance. Under §14 these sources are Q4 until lineage is proven.
4. **The research instrument hallucinates.**
   - `inventory_underlying_btc_gold.md` §0 records that a WebFetch summary of a CFTC filing was fabricated.
   - WebFetch returns an LLM summary, not bytes, so "VERIFIED-BY-DOC" claims that came only through WebFetch are model-mediated.
   - It is not stated which `research/sources.md` hashes are of raw bytes (curl) and which are of tool output.
5. **Same-host checksums.** The Kraken SHA-256 files and HF LFS hashes protect against corruption, not against a compromised or revised source.
6. **Silent and announced revisions.**
   - The Databento renormalization of 2026-08-08.
   - Binance Vision "may be updated at a later date".
   - The SII release fix.

   A dataset may carry no version marker (DBN metadata versions the encoding, not the normalization), so `provider-side version markers` in the manifest may be empty.

**Fix.**
- **Admission rule** (`docs/phase2.md` §14):
  > A Q2/Q3 source is admitted for development evidence only after a deterministic reconciliation against a Q1 source on a preregistered, tool-drawn sample from the development window, with thresholds fixed before the run. Failure leaves the source at Q4. A source whose lineage to a Q1 origin cannot be documented end to end is Q4, whatever its quality metrics.
- Mark every inventory recommendation that names a Q4 source as "Q4 until lineage proven".
- **Verification standard** (`research/sources.md` conventions):
  > VERIFIED-BY-DOC requires a verbatim quote and the SHA-256 of the raw retrieved bytes. A WebFetch or WebSearch summary is SECONDARY at best.

  Re-tag the existing claims that rest only on WebFetch summaries.
- **Manifest:** require `vendor_version_marker` *or* an explicit `none_available`. For `none_available` sources, record the request date and treat any later fetch as a possibly revised new acquisition, never a confirmation.
- **On-chain verification:** check against at least two independent RPC providers, or one provider plus block-hash verification, and only below a recorded finality depth.

### RT-B3-05 (MAJOR; BLOCKING for the H-2 release tool): equivalence catalog gaps

**What the code says.** `CATALOG` maps only these to BTC or gold: Coinbase, Binance, Kraken, and Bitstamp spot; CF Benchmarks; CME BTC and gold futures; Binance perpetuals; generic public datasets; FX-vendor gold spot; LBMA; ETFs; and the two venues' contracts. Unknown pairs fail closed, so **the guard does not leak through these gaps today**. The leak routes are elsewhere.

**Failure scenarios.**
1. **The H-2 release tool needs its own catalog.**
   - Its specification says "every equivalent observable's time" but defines no catalog.
   - If it treats unlisted families as unrelated (the natural default for a cutter, as opposed to a refuser), it releases leaks such as:
     - the Pyth gold candles that settle KXGOLD15M;
     - the Chainlink TWAP that settles Polymarket BTC;
     - DataMine CRYPTOCURRENCY BRTI seconds;
     - CME BTC and gold **event contracts** (Databento GLBX since 2025-09-25), which are near-copies of the protected contracts;
     - 1OZ and MGC;
     - PAXG and XAUT;
     - Tardis or Kaiko files of the BRTI constituents Gemini, itBit, LMAX, Bullish, and Crypto.com.
2. **Mixed-content files.** aliplayer1 bundles Polymarket markets, Binance spot, and Chainlink. mileswangs bundles Chainlink and on-chain fills. A caller- or card-asserted family ("polymarket") misses the embedded BTC reference series.
3. **Reconstruction combinations** (prerequisite 3, still open): ETH/BTC with ETH/USD reconstructs BTC/USD, and XAU/XAG with silver reconstructs gold. ETH and silver are allowed by default today.
4. **Venue endpoints that are not contracts:** Kalshi `GET /live_data/events/{event_ticker}` (BTC price charts) and PolyBolt `price.crypto` and `price.equity` are BTC and gold observables served by venues.

**Fix.**
- Adopt E-U1 in full as a reviewed code change before the release tool exists.
- Specify that the release tool and the guard share **one** catalog, keyed by `source_id`, with content-derived families.
- Unknown `source_id`s, or unknown fields within a known `source_id`, fail closed **in the release tool too**.
- Decide prerequisite 3 (ETH and silver) before the first release.

### RT-B3-06 (MAJOR): licensing has no defined determination, stage, or lineage

**Failure scenarios.**
- An agent "determines" that a CC-BY card licence suffices for a Kalshi-derived HF set. The card licence was chosen by a scraper bound by the Kalshi Developer Agreement, which PMV has not read (AR-3). TrevorJS, RooseveltHonaker, and DegenHedge `windows` are all derived from Kalshi.
- A model trained on Binance Vision data (CC BY-NC-SA, which "prohibits use for live proprietary trading execution") is promoted. Production then depends on a prohibited use.
- Features derived from BRTI or CME data enter production with no DDLA or derived-data licence, or with no CME non-display (automated-use) licence for real-time feeds.
- A Tardis subscription lapses, and its terms require deleting retained data. Development results then cannot be reproduced.
- Acquiring the Cryptolake or OANDA mirrors would itself take part in apparent breach, whatever later use is intended.

**What must be resolved, and when.**

| Before acquisition (L-ACQ) | Before a production model depends on it (L-PROD) |
|---|---|
| The terms permit automated retrieval by the intended method (CF Benchmarks site: no; OANDA site: scrapers banned) | Derived-data and derived-work rights (CME DDLA; CF Benchmarks "use to … settle … financial instruments"; IBA usage licence) |
| The terms permit the intended development use **and retention**, including after any subscription ends | Commercial and live-trading use permitted (fails for Binance Vision and every CC-BY-NC set) |
| The redistributor had the right to grant the licence. Unknown counts as no for venue-derived third-party copies until the venue terms are read | Real-time and non-display licences for production feeds (Kalshi `pyth_value`, Chainlink, CME) |
| Kalshi Developer Agreement (blocks K1 **and** every Kalshi-derived copy) | Attribution and share-alike obligations on derived datasets and artifacts |
| Polymarket ToS (blocks Gamma, Data API, and CLOB off-chain data; on-chain fills need only the indexer or RPC terms) | Jurisdiction (F-16) for the venue whose data trains the model |

**Fix.**
- Add `licence_id` with flags `acq_ok` and `prod_ok` to the source catalog.
- Every model and dataset manifest lists the `licence_id`s of its inputs.
- A Phase 6 or Phase 8 check fails closed if any input lacks `prod_ok`, so that a production model can always be rebuilt from `prod_ok` inputs only.
- A licence determination is an owner record in `docs/decisions/` that cites the terms snapshot hash. Agents propose; they do not determine.
- "Do not acquire" stands for Binance Vision, Cryptolake, OANDA, papylove, and the DegenHedge `signals` table until the owner decides otherwise.

### RT-B3-07 (MAJOR): timestamp failures that favor the hypothesis

1. **The direction of `vendor_capture_time` is wrong.**
   - `docs/phase2.md` §4 table: `vendor_capture_time` … "and an upper bound for synthetic availability".
   - Databento's capture servers are colocated with CME, and Tardis collectors sit in vendor regions. PMV's own receipt can only be later, so vendor capture is a **lower** bound on PMV availability.
   - Read as an upper bound, it licenses `available_at ≤ ts_recv`. That makes CME or BTC underlying moves "available" earlier than PMV could see them, which is exactly the S-8 artifact.
   - **Text fix:** replace with "and a **lower** bound for synthetic availability: `available_at ≥ vendor_capture_time + L_vendor→PMV`, where `L_vendor→PMV ≥ 0` is preregistered."
2. **The lead-lag artifact on the prediction-market side.**
   - Polymarket fills carry block time: seconds precision, after off-chain matching, with sub-second to multi-second delay.
   - The underlying sources carry ms or ns exchange or capture times.
   - A prediction-market price change stamped at block time looks *later* than it was available on the CLOB WebSocket. The underlying then appears to lead, and "prediction market under-reacts to velocity" appears supported.
   - The `L` ladder in `docs/phase2.md` §4 scales the underlying `L`. It cannot correct a bias already in the prediction-market `event_time`.
   - **Fix:** treat each on-chain fill's information time as the interval `[block_time − D_max, block_time + 1 s)`, with `D_max` the documented or overlap-measured match-to-block delay. Run every archive lead-lag result at both ends of the interval. An effect that appears only at the late end is a timing artifact. Kalshi `created_time` gets the same treatment until its precision and semantics are verified (UNRESOLVED, batch 2 §6).
3. **Coarse precision.** "Never padded into false precision" is right but incomplete. Add: a timestamp of precision `p` stands for the interval `[t, t + p)`. For **availability**, use the upper end `t + p` (plus `L`). For **label-side alignment**, carry the interval, and flag a fixing-window boundary that falls inside it.
4. **Third-party recorder clocks** (lerchen3, pmxt, aliplayer1, mileswangs) are undisciplined or undocumented. Measure the offset per acquisition from paired exchange timestamps, and give such receipt times their own class, `THIRD_PARTY_RECEIPT`, distinct from both `RECEIPT` and `SYNTHETIC_ARCHIVE`. They are never `RECEIPT`.
5. **H-5 and the first cycle.** With no PMV latency measurement yet, the "deliberately large default" must be fixed *per source, per side* in the preregistration before any archive outcome is seen. Record the sign of each asymmetry, not just its magnitude.

### RT-B3-08 (MAJOR): source revisions; the `docs/phase2.md` rules are necessary but not sufficient

1. **Label rule conflict.**
   - `docs/phase2.md` §12, under "Underlying revisions", says "Labels use the final official version".
   - The inventory reports that Polymarket GC markets settle on the CME settlement "as first published, regardless of later correction".
   - Labels must come from the venue's official resolution. Any reference recomputation must use the version the contract rule names.
   - **Text fix:** "Labels are the venue's official resolution. Reference-recomputation audits use the reference version the contract rule names (for example, the first-published CME settlement), not a later correction unless the rule says so."
2. **Bust survivorship.** Archive trade tapes are as-of the fetch, so busted or cancelled trades are already gone. A live system would have seen them and could have acted on them. Archive features are therefore cleaner than live features: an optimistic bias that varies with volatility. **Fix:** tag archive trade rows `revision_visibility = POST_HOC`, and measure the bust rate on the overlap window (S-9) before relying on archive trade features.
3. **Amendments after the archive snapshot.** A `POST_HOC` label fetched before a Kalshi `amended` result, or before a UMA dispute resolved, is stale. **Fix:** admit an archive label only if the market's finalization plus the documented dispute or amendment window ended before `fetch_started_at`. Two independent acquisitions (venue and an independent copy) that disagree give `duplicate_conflict`, with exclusion.
4. **Chain finality and reorganizations.** Record the finalized block height at acquisition. Rows above it are excluded and re-fetched later.
5. **Upstream revision detection.** Nothing detects that an upstream file changed. Re-check provider checksums and ETags without re-downloading content. A change triggers a new acquisition and a re-run under the S-15 rule. After `T0`, any such re-fetch goes through the RT-B3-02 cut.
6. **Moving Kalshi tier boundary.** Records can migrate between the live and historical tiers. `trade_id` is not a sequence, so completeness cannot be proven by continuity. **Fix:** fetch both tiers across the boundary, record `/historical/cutoff` before and after, dedupe by `trade_id`, and classify the boundary interval `undeterminable` (§8) unless the two tiers overlap.
7. **Index methodology and constituents** (BRTI added Bullish on 2025-07-14 and Crypto.com on 2025-03-31, SECONDARY) are versioned reference metadata and belong in `outcome_reference_event_id`.

### RT-B3-09 (MAJOR): the pre-cycle exposure has happened; its consequence is understated and its record is not durable

**Facts.**
- Two research agents read in full the DegenHedge `kalshi-btc-15m` README, with aggregate KXBTC15M outcome statistics for 2026-01-10 to 2026-10-04: signal win rate against entry price, and strike and BTC price ranges.
- Search summaries carried third-party Brier and edge claims on KXBTC15M, and recent gold price levels.
- The BRTI page fetch (`inventory_underlying_btc_gold.md` §6) returned a line matching a live index value. It was "filtered unread", but anything a fetch tool returns is in the model's context, so "unread" is not a credible claim.

**Consequences.**
1. **H-1 option (a) is foreclosed for both assets, not only for KXBTC15M.**
   - KXBTC15M outcomes are functions of the BTC path, so the exposure is to the **BTC observable family** over 2026-01-10 to 2026-10-04. That covers Polymarket BTC up/down, BRTI, and spot.
   - Adding F-06 (agent-model knowledge to about mid-2026) and the coarse recent gold levels, **no snapshot ending on or before 2026-10-16 can be an "unexamined" holdout for either asset**.
   - (b) is therefore not merely preferred. It is the only formation consistent with START_HERE.md "Protection of Holdout-Eligible Data". The owner still decides, but the decision record should say so.
2. **The exposed content is strategy-relevant.** Win rate against entry price is a calibration and favourite-longshot statistic for the exact product. It is development-influencing, so it is a research degree of freedom (S-15) and must be disclosed to the eventual Phase 5 auditors.
3. **It must be durably recorded.**
   - CLAUDE.md says that when exposure "could influence development, record a contamination event under HOLDOUT_ACCESS_LOG.md".
   - `contamination_recorded` needs a cycle, and none exists. That is a **governance gap**, not a reason to record nothing.
   - Today the disclosure lives only in uncommitted research files.

**Fix.**
- Add a "Pre-cycle exposure register" section to the batch 3 decision record. Committed and append-only, it records for each exposure: the date, the sessions or roles involved, the source and its SHA-256 (already in `research/sources.md`), the observable family, the period covered, and the granularity (aggregate or point).
- Add the binding rule: "The first cycle's protected interval start `B` satisfies `B − m` > the latest end of any registered pre-cycle exposure for that observable family (currently 2026-10-16 for BTC and gold). `cycle_registered` cites the register by hash."
- Correct the status claims:
  - `docs/phase2.md` Status ("No real observation has been shown to any agent");
  - `docs/phase1.md` batch 3 ("no market-data or trading API host was contacted … no real observation was shown to any agent");
  - `feasibility_summary.md` §7 ("Neither involved market data"; "rules out … KXBTC15M").

  Proposed replacement text is under "Exact text fixes" below.
- The owner decides whether to treat the register as a structural extension of HOLDOUT_ACCESS_LOG.md. That is governance-controlled and needs approval.

### RT-B3-10 (MAJOR; BLOCKING for adopting H-1 without conditions): embargo erosion after `T0`

**Failure scenario.**
1. `T0` is declared, and accumulation runs for months. S-5 suggests about 510 days to power after-cost EV.
2. A research agent opens an HF card, a Kaggle page, an arXiv abstract, or a search summary on KXBTC15M or Polymarket BTC up/down. Those sources are refreshed "to present", so the agent reads aggregate outcome statistics for the protected period.
3. Web research is not intercepted ("Governed by rules, not code", `docs/protected_information.md`).
4. The batch 3 base rate is one full exposure in one research pass.

The likelihood over a long accumulation is high (an evidence-based judgment, not a fabricated probability). Each event consumes the holdout once it is recorded. Worse, it may go unrecognized.

**Fix (a condition of H-1, alongside S-10 and H-8):**
- **Embargo granularity text:**
  > From `T0 − m` until the holdout is consumed, agents do not open dataset cards, READMEs, viewers, vendor pages, dashboards, papers, or search results whose subject is BTC, gold, or BTC/gold prediction-market data covering any part of `[T0 − m, E + m + lag)`. Aggregate statistics of the protected interval are protected information.
- **Deterministic support.** During accumulation, add host-level denies, owner-approved in settings, for `huggingface.co/datasets`, `kaggle.com/datasets`, and the vendor and dashboard hosts in the inventories. Dataset metadata is then retrieved only by the owner-run tool, pinned to pre-`T0` revisions.
- **Literature** published after `T0` on these products is read only through owner-screened copies, or not at all until consumption.
- **Contamination procedure:** after `T0`, any such exposure is `contamination_recorded`, with no judgment call about "aggregate only".

### RT-B3-11 (MAJOR): process events this batch

| Event | Classification | Reason | Recommendation |
|---|---|---|---|
| A request to `api.exchange.bullish.com` (an exchange API host) for a "docs path"; refused by the proxy; no content | **Serious near miss** (incident-review mandate) | A hard batch rule (no market-data or trading API host) failed at the agent level. Only the network layer stopped it. A refusal that depends on an owner click is not deterministic | Write an incident record: timeline, cause (host-class confusion), detection (proxy), corrective actions. Before any credentialed or market-data work, implement F-09 as committed deterministic denies with pattern rules (`api.*`, `*-api.*`, `clob.*`, `data-api.*`, `gamma-api.*`, `*rpc*`, `archive.*`, `assets.*`, `data.*`, S3 `/reporting/`). Correct the batch claims (below) |
| `www.cfbenchmarks.com` pages fetched before their terms (which bar automated access) were read; the output contained a live BRTI-value line | **MAJOR** (terms breach, plus an incidental live observable) | The terms violation was inadvertent and stopped promptly. "Neither involved market data" is inaccurate | Disclose it to the owner as a terms event. Keep only the hashes and the minimal quoted terms text. The owner may wish to add `cfbenchmarks.com` to the deny list. Rule: for any **data-licensor** domain, check `robots.txt` and the terms through owner-supplied copies first |
| Attempts on live-value hosts (`data.chain.link`, `pythdata.app`, `polygonscan.com`, `degenhedge.com`, `predictionmarketspicks.com`) listed as proxy-refused in `inventory_prediction_markets.md` §6, while `inventory_underlying_btc_gold.md` §7 and `feasibility_summary.md` §5 say live-value pages were "not attempted" | **MAJOR** (inconsistent records, attempted live-value access) | Records disagree about what was attempted, and the attempted pages display live prices | Reconcile the records, and state plainly which hosts were attempted. Add live-value hosts to the deny list |
| 29 (prediction-market inventory) and "more than 50" (summary) proxy refusals, recorded as "user denied" | **MAJOR (systemic)** | The control is an owner click. Prompt fatigue makes a mistaken allow likely at the 50th prompt, and one allow of a data host is an exposure | A committed denylist, so that prompts arise only for documentation domains. ACCESS REQUESTs name the host class (`docs`, `data`, `api`, `live-display`). Owner prompts for `data`, `api`, and `live-display` hosts are denied by default |
| A hallucinated WebFetch summary (CFTC GOLDPERP) was detected and discarded | **MAJOR** (provenance) | Shows that model-mediated retrieval fabricates facts | RT-B3-04 verification standard |

### RT-B3-12 (MAJOR): internal inconsistencies in the governance edits

1. **CLAUDE.md** says "Before a real protected scope is declared, agents do not inspect real market observations at all." The new P1 text says historical data is preferred and used for development.
   - The letter is reconciled: the new text says it "does not open agent access … before the protected scope and release controls allow it".
   - In practice the absolute "at all" was breached in this batch through documentation (RT-B3-09), and it will be breached again.
   - **Proposed owner-approved amendment:** "Before a real protected scope is declared, agents do not deliberately inspect real market observations. Incidental exposure through documentation, cards, or search results is recorded in the pre-cycle exposure register and constrains the first protected interval."
2. **CLAUDE.md "Holdout Protection"** ("oldest ~70% = development; newest ~30% = protected") and the HOLDOUT_ACCESS_LOG.md Holdout Rules ("The oldest approximately 70% of the chronological data …") conflict with S-11.
   - S-11 applies the 70/30 target to the PMV-capture span only.
   - Under S-11, "power governs", which can push the protected span past 30% of the capture span. Measured against all chronological data including years of history, the protected share would be far under 30%.
   - START_HERE.md Phase 2 ("across the planned collection span") is ambiguous enough to bear S-11's reading. CLAUDE.md and the HOLDOUT_ACCESS_LOG.md restatement are not.
   - `docs/phase2.md` labels S-11 as an "owner interpretation, material". It needs an explicit owner-approved edit of CLAUDE.md and START_HERE.md, not a design-document reading. Repeated phrases such as "Use only the development 70%" also need a definition under prospective formation.
3. **Two standards for fixing formation.** PROJECT_BRIEF.md (new bullet): formation "is decided for each cycle **before any inspection**". START_HERE.md: "**before outcome-dependent** inspection". The stricter wording is safer, but the two must say the same thing.
4. **Two access authorities.** The decision record ("What does not change") lists "the guard allows the request" as a release condition. Under F-08 the release tool is the access path, and the guard prerequisites "become unnecessary". The texts should name one authority: "the trusted release tool, which applies the guard's catalog and scope".
5. **Collection rule stretched to acquisition.**
   - The approved collection rule (S-6) covers deterministic **collection**. `feasibility_summary.md` §1.8 extends it to historical **acquisition**.
   - That extension is reasonable, but it is an interpretation of a protected-information rule.
   - It also skips the raw-backup prerequisite, which the S-6 text ties to "irreplaceable live capture" (RT-B3-01).
   - The owner should approve it explicitly, with the RT-B3-01, RT-B3-03, and RT-B3-06 conditions.
6. **Tier rule against recommendations.** The `docs/phase2.md` §14 Q4 rule conflicts with the inventories' recommendations (RT-B3-04 item 3).

### RT-B3-13 (MAJOR): the "use aggressively" pressure is already eroding controls

**Evidence from this batch.**
- A card was read in full before filtering.
- A terms-barred site was fetched before its terms were read.
- An API host was requested.
- More than 50 owner prompts were raised.
- "Pull early … prompt guarded acquisition" appears while the Developer Agreement is unread.
- Q4 sources are recommended as development candidates.

No single item is fatal. The direction is the risk.

**Fix:** add to the decision record (P1) a precedence rule:
> Retention loss, cost, or schedule never justify acquiring, parsing, or releasing data ahead of its licence determination, backup policy, safe-parsing controls, or release controls. If official history may age out first, the owner may (i) obtain the terms manually, or (ii) accept the loss. The loss is recorded as a known gap.

Add a per-batch metric to batch records: counts of incidental exposures, refused host attempts by class, and terms events.

### RT-B3-14 (MAJOR): duplicate contamination and dependence across archives

1. **False corroboration.** TrevorJS, Jon-Becker, RooseveltHonaker, DegenHedge `windows`, and bennett-tan all derive from the Kalshi API. Agreement between them is not independent verification of K1. **Fix:** reconciliation reports carry an `upstream_lineage` field. Only pairs with disjoint lineage count as cross-verification (for example, Polygon chain against the Polymarket Data API, or Databento against CME settlement).
2. **Lossy keys.** TrevorJS dropped orphan trades and deduped 21,950 trades, and candles drop `trade_id`. Exact-key dedupe across archives then fails, and near-duplicate detection (§6) becomes the de facto rule. That is a research degree of freedom. Freeze its tolerance per pool before inspection (S-15).
3. **Timing forced by the overlap calibration window (S-9).**
   - The window must be captured live, then acquired from the archive after the archive publishes it (Kalshi tier lag, SII release cadence), and all before `T0 − m`.
   - So `C0` (capture start) must precede `T0` by at least the window length plus the archive publication lag plus `m`.
   - Record this as a constraint on `T0` in H-1.
   - The later acquisition of the window must go through the RT-B3-02 cut, because the archive will by then extend past `T0`.
4. **Re-entry.**
   - *Protected into development:* the third-party archives of the protected period (RT-B3-10), and the PMV-capture-derived dashboards S-10 notes.
   - *Development into protected:* impossible under P2 only if exposure is recorded. That is a further reason for the RT-B3-09 register.
   - *Lockbox:* the optional historical lockbox is development data, consumed on use. Record its opening in the experiment ledger with the same discipline as a holdout event, so that it is not opened "just once more".
5. **Cross-venue near-copies.** CME BTC and gold event contracts, Polymarket US, and polymarket.com contracts on the same window are equivalent observables of each other's outcomes. They belong in the catalog (RT-B3-05) and share the `outcome_cell_id` (H-6). They are not independent samples.

### RT-B3-15 (MINOR): documentation integrity

- `docs/phase2.md` Status and `docs/phase1.md` cite this review's conclusions before it existed. Replace them with a neutral pointer.
- Both inventories (line 3) say hashes are in `research/historical_data/_sources_*.md`. Those files were removed during this review and merged into `research/sources.md` "Phase 1 batch 3". Update the pointers.
- `docs/phase1.md` says "H-1 to H-7", but the decision record also raises H-8. List H-8.
- Refusal counts differ: 29 (prediction-market inventory) against "more than 50" (summary). Give one reconciled count.
- `research/historical_data/.claude/.cc-writes` (a Claude Code artifact) exists under a research path. Stage files by explicit path only, and confirm that the layout and secret-scan checks are unaffected.
- `feasibility_summary.md` was cited before it existed, and the Statistician review notes this. It exists now. No further action beyond this note.

### RT-B3-16 (MINOR): calendars and DST

- The CME 1OZ "weekend trades assigned next business-day trade date" means trade date differs from UTC date. Never join on trade date for intraday alignment.
- KXGOLD15M (weekdays, ET) and the Pyth "1-minute candle close" (ET timestamping, SECONDARY) need ET-to-UTC conversion with versioned calendars.
- Polymarket gold settles at 4:59 PM ET.
- Excluding ambiguous fall-back hours is correct, but it is systematic: about one hour a year, the same hour each time. Ledger it by reason so that it is not mistaken for a gap.
- The 16:00–17:00 CT CME break is `out_of_session`, never `feed_outage`.

---

## Blocking conditions for the next implementation batch

These apply only if the batch acquires, parses, or releases real data. Synthetic-fixture implementation of `docs/phase2.md`, H-3, and H-6 is not blocked.

1. **No acquisition** until all of the following:
   - the raw backup and restore policy covers acquired files, with a passing restore test (RT-B3-01);
   - an owner licence determination exists for that source at L-ACQ (RT-B3-06);
   - safe-parsing controls and their fault-injection fixtures pass (RT-B3-03);
   - the owner explicitly approves applying the S-6 collection rule to acquisition (RT-B3-12 item 5).
2. **No agent-facing release** until all of the following:
   - H-1 is decided, with `T0` and `m` committed and the cycle registered, citing the pre-cycle exposure register (RT-B3-09);
   - H-2 is adopted and the release tool implements the RT-B3-02 properties with a single content-derived catalog that includes E-U1 (RT-B3-05);
   - the scope freeze on first exposure (S-4) is durably recorded.
3. **No parser runs on a real file** without the RT-B3-03 controls.
4. **No acquisition tool reaches a host** outside a committed, owner-approved per-source host list. F-09 denies for API, data, and live-display host classes are in place first (RT-B3-11).
5. **The incident record** for the API-host near miss exists, and the inaccurate batch claims are corrected (RT-B3-09, RT-B3-11).

## Recommended owner decisions

| # | Decision | Recommendation |
|---|---|---|
| O-1 | H-1 formation | (b) prospective. Record that (a) is foreclosed for BTC and gold for periods ≤ 2026-10-16 (RT-B3-09). Add the RT-B3-10 embargo-granularity text and the RT-B3-14 constraint on `T0` (`C0 + overlap window + archive lag + m ≤ T0`) to the S-10, S-11, and H-8 conditions |
| O-2 | Pre-cycle exposure register | Create it now in the batch 3 decision record, append-only, and bind the first cycle to it |
| O-3 | Acquisition under S-6 | Approve only with the RT-B3-01, RT-B3-03, and RT-B3-06 conditions |
| O-4 | H-2 | Adopt, with the RT-B3-02 properties and one shared catalog (E-U1 plus RT-B3-05 items) |
| O-5 | Licence gate | Adopt L-ACQ and L-PROD with `licence_id` lineage on every artifact. Keep "do not acquire" for Binance Vision, Cryptolake, OANDA, papylove, and DegenHedge `signals` |
| O-6 | F-09 | Commit deterministic denies for API, data, and live-display host classes before the next research batch, to end click-based refusal |
| O-7 | CLAUDE.md, START_HERE.md, HOLDOUT_ACCESS_LOG.md wording | Approve or reject the RT-B3-12 amendments ("deliberately inspect"; the S-11 70/30 reading; one standard, "before any outcome-dependent inspection"; one release authority) |
| O-8 | Verification standard | Treat WebFetch and WebSearch summaries as SECONDARY. VERIFIED-BY-DOC needs a verbatim quote plus a raw-byte hash |

## Exact text fixes requested

1. `docs/phase2.md` §4 table, `vendor_capture_time` row, "Use" column: replace "and an upper bound for synthetic availability" with "and a **lower** bound for synthetic availability: `available_at ≥ vendor_capture_time + L_vendor→PMV`, with `L_vendor→PMV ≥ 0` preregistered".
2. `docs/phase2.md` §4, append: "A timestamp of precision `p` denotes `[t, t + p)`. Availability uses `t + p + L`. On-chain fills use the information interval `[block_time − D_max, block_time + 1 s)`, and archive lead-lag results are reported at both ends."
3. `docs/phase2.md` §12, "Underlying revisions": replace "Labels use the final official version." with "Labels are the venue's official resolution. Reference-recomputation audits use the reference version the contract rule names (for example, the first-published settlement), not a later correction unless the rule says so."
4. `docs/phase2.md` Status, and `docs/phase1.md` batch 3 paragraph: replace "no market-data or trading API host was contacted … no real observation was shown to any agent" with "No market-data API returned content. One request to an exchange API host (`api.exchange.bullish.com`) was attempted and refused by the proxy (incident record pending). No dataset or sample was downloaded. Agents were incidentally exposed to aggregate outcome statistics (`feasibility_summary.md` §7) and to a page containing a live reference-index value (cfbenchmarks.com). Nothing was recorded or used."
5. `feasibility_summary.md` §7: replace "Neither involved market data." with "The cfbenchmarks.com page output contained a live BRTI value. Nothing was recorded." Replace "rules out using any KXBTC15M period before 2026-10-16" with "rules out using any BTC-family period (and, given search summaries with recent gold levels and F-06, any gold-family period) ending on or before 2026-10-16".
6. `docs/conventions.md` "Historical Data Sourcing", add the RT-B3-01 irreplaceability sentence and the RT-B3-03 safe-parsing paragraph.
7. Decision record: add the "Pre-cycle exposure register" section and binding rule (RT-B3-09), and the precedence rule (RT-B3-13).
8. Inventories, line 3: point hashes to `research/sources.md` "Phase 1 batch 3".

## Unresolved unknowns

- Kalshi historical retention and cutoff lag; the Kalshi Developer Agreement; Polymarket ToS; the KXBTC15M and KXGOLD15M rulebooks (UR-4, UR-5).
- The Polygon match-to-block delay distribution (needed for `D_max`); Kalshi `created_time` precision.
- Vendor retention-after-subscription terms (Tardis); Databento normalization version markers.
- The BRTI restatement policy; the Pyth blended-index methodology.
- Whether the HF hosting platform permits history rewrites that would invalidate pinned revisions (pinning by commit SHA plus LFS SHA-256 still detects that).
