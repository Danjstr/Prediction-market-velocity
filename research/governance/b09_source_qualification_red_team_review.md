# B09 Red-Team review: Kalshi source qualification

- **Reviewer:** an independent Reliability / Red-Team agent, fresh context, read-only.
- **Network:** none. No file change and no heavy process.
- **Subject:** `703fd7f`, parent final B08 `5806d8c`. Line numbers in the findings refer to that commit.
- **Verdict at `703fd7f`:** no BLOCKING finding; two MAJOR findings (RT-B9-01, RT-B9-02). Both are in proposed designs that are not approved and were not acted on, so no exposure has occurred. The reviewer asked that both be fixed before the owner decides D-B09-2 or D-B09-7.

The findings are reproduced as the reviewer reported them. The disposition column is the lead session's, applied in the commit that adds this file. Those fixes are documentation edits only, and have not been re-reviewed (see "Re-review").

| ID | Severity | Finding (summary) | Disposition |
|---|---|---|---|
| RT-B9-01 | MAJOR | The candidate A-1 prefixes `/trade-api/v2/series/` and `/trade-api/v2/events` are matched at segment boundaries (`hosts.py:187-189`). They therefore also cover live endpoints: live candles, `/events/{t}` with nested current markets and quote fields, `/events?status=open`, `/events/multivariate`, and `/events/{t}/metadata`. Nothing makes a status or `exclude_markets` filter mandatory, and nothing refuses unsettled markets in a response. AR-B9-1 omitted the events pages | **Fixed in docs.** Analysis §3 now uses exact endpoint templates. `/events` is allowed only with plan-fixed `exclude_markets=true` and a settled-only filter, if those exist; otherwise it is excluded. S7 ends a series `incomplete` with a quarantine flag on any unsettled market or out-of-window record, and never drops one. AR-B9-1 adds `get-events.md` and `get-event.md` (18 paths). D-B09-2 is narrowed to match |
| RT-B9-02 | MAJOR | An unsurfaced governance conflict. `external_access.md` §1.1 rule 1 says "No such classification ever covers a path that returns market observations", yet the A-1 route relies on a §1.5 classification of `/historical/*`. The tension predates B09 (the B06/B07 `host_class_decisions`) | **Escalated.** New owner decision D-B09-9: amend rule 1 narrowly, or confirm that the source cannot be acquired. D-B09-2 is not approvable before it. Analysis §3 and §12 note the conflict |
| RT-B9-03 | MINOR | Out-of-window data could enter the store. There was no check against `date_range_end` or `T0 − m`, the timestamp units are UNRESOLVED, windows could be "variable", and an empty series counted as `complete` | **Fixed in docs.** All windows are plan-fixed. Units must be confirmed under AR-B9-1 first. S7 adds checks for out-of-window records and an undeclared empty series. A-6 check 2 extended |
| RT-B9-04 | MINOR | The review file and its timeline row were claimed before they existed | **Fixed.** This file. The timeline row is split between `703fd7f` and this commit |
| RT-B9-05 | MINOR | "About 100 days" was attributed to TrevorJS; it comes from jdkatz21. It is likely a cutoff lag, not retention. Gold may have nothing in the historical tier yet | **Fixed.** Citation corrected, lag separated from retention, and the gold implication added to §11 |
| RT-B9-06 | MINOR | The candidate A-1 table omitted `approval_id` and `f09_settings_commit` | **Fixed.** Both added |
| RT-B9-07 | MINOR | The licence-schema gap was overstated: `storage`, `retention_after_subscription`, and `internal_model_development` exist | **Fixed.** The existing fields are mapped to rows; "no dedicated field" is used for the rest |
| RT-B9-08 | MINOR | The draft clarification request omitted row O (processing by tools and AI assistants) | **Fixed.** Neutral question 9 added. The request is still unsent |
| RT-B9-09 | MINOR | The A-3 recommendation of Option 1 leaves irreplaceable acquired files single-site | **Fixed.** D-B09-5 and analysis §7 now require explicit owner acceptance of that risk, or Option 3 for historical acquisitions too |
| RT-B9-10 | MINOR | Gaps an implementer would get wrong: <ul><li>TLS verification, proxy environment variables, cookies;</li><li>automatic resume after rate limiting;</li><li>cutoff changes across a resume;</li><li>series linkage when `series_ticker` is not required on Market;</li><li>percent-encoding against today's allowlist;</li><li>an ambiguous cursor grammar;</li><li>`source_ids: any` in the scoped A-4 record</li></ul> | **Fixed in docs.** Added S19a–S19d. Resume is owner-initiated only. Encoding-free grammars are preferred. The `any` wildcard was dropped from §8 |
| RT-B9-11 | NOTE | The designation is inferred from a summarized charter. The charter text is not in Git. "No B10" conflicts with the timeline's "(B10)" | **Addressed.** The operative charter lines are quoted. The owner is asked to confirm the designation when recording the D-B09 decisions. The B10 wording is reconciled in the record |
| RT-B9-12 | NOTE | The CVE caveat was missing. `kalshi.com/market-data` may be live-display. Other wording | **Fixed.** CVE caveat added. Item 3 now says the owner may visit that page but should not relay values |
| RT-B9-13 | NOTE | AR-B9-1 named no requesting agent | **Fixed.** Requester added |

## Checks the reviewer recorded as passed (summary)

1. No acquisition or prohibited contact is claimed, and the claims are consistent. Absence of traffic cannot be proven from the repository.
2. No credential was used or proposed; B7-5 is preserved.
3. No legal ambiguity was converted into permission. Every A-2 row is NOT YET EVIDENCED or AMBIGUOUS. The draft request is neutral and unsent.
4. A-1 to A-6, Gate 1, acquisition, live capture, `T0`, cycle, and holdout statuses are not overclaimed anywhere.
5. The pagination design is fail-closed in its core. Its gaps are RT-B9-01, RT-B9-03, and RT-B9-10.
6. A-7 and A-8 are intact.
7. The A-4 claims match the code (`pipeline.py:686-690`; `readers.py`). Unadopted formats stay refused.
8. Nothing was decided for the owner.
9. The decision not to fetch `docs.kalshi.com` is well grounded (AR-1 duration, E-7, rule 3). The AR-3 list is a consistent superset of Git's AR-3, and no web copy was substituted.
10. The DOC-1015 facts match `api_documentation_findings.md`, except RT-B9-05 and RT-B9-07. The A-3 options are consistent with `raw_data.md` and `backup_and_recovery.md`.
11. No conflict with PROJECT_BRIEF.md or CLAUDE.md. Gold stays in scope (P4).

## Re-review

The fixes are documentation only, and no code changed. A re-review of the fixed design (§4 S1–S21 and S19a–S19d; analysis §3) is recommended **before** the owner approves D-B09-2 or D-B09-7, and is required when those designs are implemented (`src/pmv/acquisition/` changes need a fresh review).
