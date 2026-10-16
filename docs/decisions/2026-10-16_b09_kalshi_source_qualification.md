# B09: Kalshi official historical data, source qualification and owner-decision packet (2026-10-16)

**Approver:** the project owner, in the B09 batch charter issued on 2026-10-16 in the isolated environment, after B08 was merged. The development session wrote this record. It is procedural: the system does not cryptographically prove who approved it (F-42 in `docs/decisions/2026-10-14_phase0_step11_owner_decisions.md`).

**This is not a gate record, an acquisition approval, or a licence determination.** It:
- decides none of A-1 to A-6;
- authorizes no request to any Kalshi host;
- changes no production code, control, holdout rule, or approved requirement.

The analysis behind it is in `research/kalshi/b09_source_qualification.md`.

## Charter (summary of the owner's instructions)

- **Branch.** Create `b09/kalshi-source-qualification` directly from final B08 `5806d8c83afc6c1788db438394c7a0b978b16350`, not from `main`, even though `main` contains B08 through merge commit `a6b5411` (PR #7). Required chain: B05 → B06 → B07 → B08 → B09. B08 stays preserved. No merge or rebase of `main` into B09. All B09 work stays on this branch. There is no B10.
- **Objective.** Kalshi official historical source qualification:
  - determine whether Kalshi's own historical API data should become PMV's first authorized historical source;
  - prepare the owner decisions needed for A-1 to A-6;
  - produce a durable qualification record and an owner-decision packet.
- **Prohibited.** In particular:
  - acquiring or requesting any market observation (trades, candles, order books, market tickers), opening a WebSocket, or using live data;
  - authenticating, creating or using an API key or account, or accepting terms on the owner's behalf;
  - calling trading or private endpoints;
  - contacting Polymarket, Databento, Tardis, or exchange data endpoints;
  - installing dependencies, or implementing production transport or pagination;
  - changing A-4 semantics, or marking A-2 as passed;
  - opening the final pull request before the owner's decisions are recorded.
- **External access.** Every request is classified first under `docs/external_access.md` and F-09. Where policy does not authorize an exact host and path, B09 reports OWNER EXTERNAL-ACCESS APPROVAL REQUIRED and makes no request.
- **Stop.** B09 stops at the owner-decision boundary and returns the packet below.

## Designation

Under this charter, B09 is the current active ground-truth branch (`docs/BRANCH_TIMELINE.md`). The operative charter lines are: "B09 MUST be created directly from final B08, NOT from main" and "All B09 work stays on: b09/kalshi-source-qualification". The full charter text is not in Git; this record summarizes it, so the owner is asked to confirm the designation when recording the D-B09 decisions (RT-B9-11). The charter's "No B10" means no B10 is created in this batch; it does not change the timeline rule that a future successor starts from final B09. B08 is a historical checkpoint, preserved, and merged by PR #7 (`a6b5411`). This follows the B08 precedent (B08 record, "Designation").

## Continuity verified (2026-10-16, before the first B09 commit)

After `git fetch origin`:
- `b08/prospective-capture-hardening` and `origin/b08/prospective-capture-hardening` were both at `5806d8c83afc6c1788db438394c7a0b978b16350`;
- `git merge-base --is-ancestor 9a6b212 5806d8c` returned 0 (B07 → B08);
- no `b09/*` branch existed locally or on `origin`;
- B09 was created from final B08 with `git switch -c` and pushed with an explicit `git push origin b09/kalshi-source-qualification`;
- `git merge-base --is-ancestor 5806d8c HEAD` returned 0.

## Status that B09 does not change

- Phase 1. Gate 1 is undecided.
- **Historical acquisition is not authorized. Live capture is not authorized.**
- No cycle, `T0`, split, protected scope, or open holdout exists. No real observation has been acquired, captured, or released to agents.
- A-1 to A-6 stay owner-controlled and unresolved. A-7 and A-8 (protected storage; release is separate) are unchanged. Neither one is an approval of A-1 to A-6.

## What B09 did

- **External requests.** None, other than `git fetch` and `git push` to `origin`. No Kalshi host, other external host, or search engine was contacted. Analysis §1 explains why even `docs.kalshi.com` was not fetched: the expiry of AR-1 is unrecorded, and the terms-first rule 3 applies.
- **Market data.** No market-data endpoint was contacted. No credential was used.
- **Exposures.** No incidental exposure occurred, so there is no new entry in `docs/exposure_register.md`.
- **Evidence.** The batch 2 documentation snapshot already in Git (2026-10-15, hashed). Facts from it are tagged DOC-1015 and need re-verification before A-1.
- **Outputs.**
  - the analysis (`research/kalshi/b09_source_qualification.md`);
  - this record;
  - status updates in `docs/phase1.md` and `docs/BRANCH_TIMELINE.md`;
  - the Reliability / Red-Team review (`research/governance/b09_source_qualification_red_team_review.md`, added in the commit after `703fd7f`), and the fixes for its findings.

## Provisional verdict

**NOT CURRENTLY QUALIFIABLE — EVIDENCE MISSING.** This is not a rejection: technically, it is the strongest candidate for official BTC labels and trade prints. What is missing is evidence: the governing terms (AR-3), current documentation re-verification (AR-B9-1), gold existence (UR-5), and retention depth (UR-11).

| Item | Readiness |
|---|---|
| A-1 | Candidate drafted (analysis §3). Not approvable yet |
| A-2 | **Not assessable.** Every question is NOT YET EVIDENCED. Website versus API data, documentation versus data, and upstream licensors are structurally AMBIGUOUS. Nothing is CLEARLY PERMITTED |
| A-3 | Three options prepared (analysis §7). No choice, medium, or restore test |
| A-4 | Not satisfied under either reading. The scope decision is open (analysis §8) |
| A-5 | Design ready for review (analysis §9) |
| A-6 | Design ready for review (analysis §10) |

BTC support is plausible but unverified. Gold support is unknown. PMV is **not** narrowed to Bitcoin (P4).

## AR-3: documents the owner must supply

Git requires the terms, Developer Agreement, fee schedule, rulebook, contract terms, and help-center eligibility articles to be obtained by the owner (`docs/phase1.md` AR-3, option 1). `kalshi.com` is bot-challenged and sandbox-denied, and it is `live-display` under §1.1 rule 2. No web copy was substituted.

Every item below is **NOT YET OWNER-SUPPLIED / NOT YET AR-3 EVIDENCE**. URLs come from links in the batch 2 documentation snapshot, or are SECONDARY where marked. The issuing entity and effective date are whatever each document states; they are unknown until supplied.

| # | Document | Known URL or locator | Questions it bears on |
|---|---|---|---|
| 1 | Kalshi Developer Agreement | `https://kalshi.com/developer-agreement` (welcome page: API use binds the user to it) | A-2 rows A–T; acceptance by conduct; termination; modification |
| 2 | Kalshi Terms of Service | `https://kalshi.com/terms` (the AsyncAPI `license.url`) | A-2 rows R and S; precedence against item 1 |
| 3 | Member or customer agreement, and any API, market-data, or data-licensing terms, plus every document incorporated by reference in items 1 and 2 | Unknown. `https://kalshi.com/market-data` is one page to check. It may show market values: the owner may visit it, but should not relay any values to agents | Precedence, data-use scope, row T |
| 4 | Fee schedule | `https://kalshi.com/docs/kalshi-fee-schedule.pdf` | Fees (UR-3), F-17 |
| 5 | Kalshi rulebook, and the contract terms for each BTC short-horizon series and any gold series (current, and the original filing) | Each series' `contract_terms_url` and `contract_url`. SECONDARY locator: `https://kalshi-public-docs.s3.amazonaws.com/contract_terms/CRYPTO15M.pdf`. Or follow the links from the kalshi.com market-rules page in a normal browser | UR-4, UR-5, settlement lineage, AR-2 |
| 6 | Help-center articles on eligibility, location attestation, and demo accounts | `help.kalshi.com` (for example the demo-account article linked from `getting_started/demo_env.md`) | F-16, E-6 |
| 7 | Upstream terms for the settlement references, if the owner wants row T assessed | CF Benchmarks licence and methodology (AR-9, owner-supplied); Pyth terms (AR-8) | A-2 row T |

**How to supply them (proposal).**
- Download each in a normal browser.
- Record the exact URL, the UTC retrieval time, any displayed effective or "last updated" date, and the SHA-256 of the saved bytes.
- Keep the copies in an owner-chosen location. **Do not commit full agreements** unless the owner determines that their licence allows it. Commit only the metadata, the hashes, and short operative quotations. The A-2 record needs `terms_url`, `terms_sha256`, and `operative_terms_quoted`.

## Owner-decision packet

Only decisions that need the owner's action next. None is taken here. They were revised after the Red-Team review (RT-B9-01, -02, -09): D-B09-2 was narrowed, and D-B09-9 was added.

**D-B09-1. Kalshi official historical data as the first-source candidate.**
- *Recommended:* keep it as the **first candidate**, conditional on A-2. Do not select it for acquisition yet.
- *Strongest reason:* it is the primary source of official settlement values and trade prints, free, and unauthenticated.
- *Downside:* there is no historical book, candles are 1-minute, retention is unknown, and gold is unknown. It is discovery-grade only.
- *If deferred:* nothing proceeds on the historical side. If the tier truncates, old history may age out; that is a recorded gap, never a reason to skip a gate (RT-B3-13).
- *Unlocks:* focusing AR-3, AR-B9-1, and the A-2 work on this source.

**D-B09-2. A-1 hosts and path families.**
- *Recommended:* **defer** until D-B09-9 is ruled, A-2 is resolved, and AR-B9-1 has re-verified the documentation. **D-B09-2 cannot be approved before D-B09-9.** Review the candidate now (analysis §3): one host `external-api.kalshi.com`; exact endpoint templates (not broad prefixes) for the historical tier plus series and fee-change metadata; events only with `exclude_markets=true` and a settled-only filter; live tier, private endpoints, WebSocket, and demo excluded.
- *Strongest reason:* approving hosts before knowing whether the use is permitted would invert the gate.
- *Downside:* it delays the transport and pagination work by one decision cycle.
- *If deferred:* nothing is lost now; the tooling cannot acquire this source anyway.
- *Unlocks (on approval):* the owner host classification in `docs/external_access.md` §1.5 for the acquisition tool only, and the endpoint-template record (S2).

**D-B09-3. Supply the AR-3 documents.**
- *Recommended:* supply items 1–5 above now, and items 6–7 when F-16 or row T is taken up.
- *Strongest reason:* A-2, F-16, fees, and the BTC contract rules are all blocked on these documents, and agents cannot obtain them.
- *Downside:* owner time, and the copyright care described above.
- *If deferred:* A-2 stays not assessable and the verdict cannot change.
- *Unlocks:* a proposed A-2 issue matrix from verbatim terms, and a precedence analysis.

**D-B09-4. A-2 resolution route, including acceptance of the Developer Agreement.**
- *Recommended:* after reading the supplied documents, if storage, backups, backtesting, ML training, derived features, or retention of model parameters are not clearly permitted, the owner sends the clarification request below (or a revised one) and records Kalshi's written answer. A-2 is not resolved by interpretation.
- *Separately:* the owner decides whether to accept the Developer Agreement at all. Under its own wording, unauthenticated API use is acceptance.
- *Strongest reason:* silence and general API permission are not permission to train models (charter §10).
- *Downside:* Kalshi may answer slowly or not at all, and the historical tier may truncate meanwhile.
- *If deferred:* no acquisition.
- *Unlocks:* an owner A-2 record (`licence_id`) and, if the answer is favorable, the L-ACQ check.

**D-B09-5. A-3 backup option.**
- *Recommended:* **Option 1** (encrypted external drive, offline) now for historical acquisitions, **with the owner explicitly accepting that acquired files stay single-site even though they count as irreplaceable** (`reproducible_from_provider: unknown`). **Option 3** (adding an off-site copy) before irreplaceable prospective capture, and only after A-2 shows that third-party off-site storage is permitted. The alternative is to require Option 3 for historical acquisitions too.
- *Strongest reason:* Option 1 works with the existing directory-based backup code unchanged, and adds no third-party licence question.
- *Downside:* it is single-site, with no protection from theft or fire.
- *If deferred:* A-3 stays open. That blocks historical acquisition and live capture.
- *Unlocks:* the A-3 policy record, then a restore test on the real medium with a synthetic JSON file of the same size class. It also needs a confirmation or replacement of the B7-7 "size class" reading.

**D-B09-6. A-4: global or source-specific.**
- *Recommended:* **source-specific**, with an A-4 record scoped to the formats and compressions it covers (never a bare flag), and the fault fixtures kept global (analysis §8).
- *Strongest reason:* fail-closed is preserved, because unadopted readers stay refused. A JSON-only source does not need Parquet, DBN, or zstd, which would add attack surface.
- *Downside:* a governance edit to `docs/external_access.md` A-4, a code change to the A-4 record and pipeline check, and a Red-Team re-review. Each new format adds a separate review later.
- *If deferred:* under the global reading, A-4 cannot pass until the B7-6 dependencies are adopted, so a JSON-only source waits on unneeded readers.
- *Unlocks:* the scoped-record code change and its review, in a future chartered batch.

**D-B09-7. Paginated REST design.**
- *Recommended:* approve analysis §4.2 (S1–S21) as the **design basis** for a future chartered implementation batch. It adds a separate governed request type, so static-URL query refusal stays as it is. It is followed by a Red-Team review. This is not acquisition.
- *Strongest reason:* Kalshi's historical API cannot be acquired without cursor and query support. The design keeps every parameter, value, cursor, and derived ticker owner-bounded and fail-closed.
- *Downside:* it widens a deliberate safety rule (in a new, separately reviewed code path), and it adds engineering and review.
- *If deferred:* this source stays unacquirable.
- *Unlocks:* implementation of S1–S21 together with the production transport (B7-4), on synthetic data, then review.

**D-B09-9. Classifying a Kalshi API host for acquisition: the rule 1 conflict (RT-B9-02).**
- *Current requirement:* `docs/external_access.md` §1.1 rule 1 lets the owner classify an `api`-pattern host and path prefix otherwise, but ends: "No such classification ever covers a path that returns market observations". Kalshi's `/historical/*` paths return market observations. CLAUDE.md's Host-Class Rule says the strictest class applies and ambiguity fails closed.
- *Concern:* the A-1 route in analysis §3 (and the B06/B07 `host_class_decisions` mechanism) assumes a §1.5 classification can authorize the acquisition tool. Read literally, rule 1 forbids that for any API source. The tension predates B09.
- *Options:*
  - (a) amend rule 1 (a governance edit): it would allow an acquisition-tool-only classification of exact historical-data templates for an owner-approved A-1 source, never for agents, never for live-tier paths, and never from a cycle's `T0 − m` for protected families;
  - (b) confirm that, under current rules, an API-only source such as this cannot be acquired.
- *Recommended:* (a), with that narrow wording and a Red-Team review of the amendment.
- *Strongest reason:* rule 1 exists to stop agents reading live data. It was not meant to bar a gated, owner-approved tool from a historical API. Without (a), no official venue API is ever acquirable.
- *Downside:* it weakens a fail-closed sentence, so the wording must be exact.
- *If deferred:* D-B09-2 cannot be approved, and this source stays unacquirable.
- *Unlocks:* D-B09-2.
- *Urgency:* blocking for D-B09-2 only.

**D-B09-8. External access for re-verification (AR-B9-1) and the status of AR-1.**
- *Recommended:*
  - record that AR-1 has **expired** with batch 2 (closing E-7's request for an expiry);
  - approve AR-B9-1 as a one-time, exact-path `docs.kalshi.com` fetch (analysis §1.2), to be used **after** the AR-3 documents are supplied, so terms-first rule 3 is satisfied;
  - optionally, rule whether rule 3 applies to `docs.kalshi.com` at all.
- *Strongest reason:* A-1 and the pagination design rest on a documentation snapshot from 2026-10-15 that must be re-verified. Agents should not decide this ambiguity themselves.
- *Downside:* another owner step.
- *If deferred:* A-1 cannot be approved on current documentation.
- *Unlocks:* re-verification of DOC-1015 facts, recorded in `research/sources.md` with new hashes.

## Draft clarification request to Kalshi (not sent; for the owner)

Agents do not contact Kalshi. The owner may adapt and send this after reading the supplied documents. It contains no account identifiers.

> Subject: Permitted use of historical API data for private research and own-account trading
>
> Hello,
>
> I am (or intend to be) a Kalshi member. I would like to confirm whether the following uses of data from Kalshi's public historical API endpoints (for example the historical markets, trades, and candlesticks endpoints) are permitted under the Developer Agreement and Kalshi's other applicable terms. Could you tell me which of these are permitted, and under which terms?
>
> 1. Retrieving historical API data programmatically, at a modest rate within published limits.
> 2. Storing it privately, and keeping encrypted backup copies, including any restriction on third-party (cloud) storage.
> 3. Cleaning and normalizing it.
> 4. Constructing derived features from it.
> 5. Backtesting trading strategies with it.
> 6. Training statistical and machine-learning models on it.
> 7. Retaining the derived features and model parameters, including after any account closure or end of API access.
> 8. Using the resulting system solely to trade my own Kalshi account.
> 9. Processing the data with third-party software tools and service providers, including hosted AI assistants used in developing the system, without giving them any right to redistribute it.
>
> I do not intend to redistribute, publish, sell, or share the data or derived datasets with third parties. Please also tell me:
> - whether any deletion or retention obligations apply;
> - whether settlement values derived from third-party reference indices (for example CF Benchmarks or Pyth) carry additional restrictions;
> - which document governs if the Developer Agreement and the Terms of Service differ.
>
> Thank you.

## What B09 still has to do after the owner's decisions

- Record the decisions here.
- Update the status documents.
- Run `./scripts/check.sh` and a cold-start review.
- Open the B09 → `main` pull request only when ready. Merging is the owner's decision.

No code changes in B09 unless the owner charters them.
