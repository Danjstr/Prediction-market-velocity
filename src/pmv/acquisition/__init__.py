"""Source-neutral historical-acquisition readiness controls (``docs/external_access.md`` §2).

This package holds deterministic, fail-closed building blocks for the historical
acquisition gate. Nothing in it contacts a network host, and no real observation has
passed through it. It is exercised only with synthetic fixtures:

- ``hosts``: per-source host and URL-prefix allowlists, with host-class refusal (A-1, F-09);
- ``records``: approval, licence, acquisition-manifest, and source-quality records
  (A-1, A-2, A-5, A-6);
- ``formats``: the parse-format allowlist and content sniffing (A-4);
- ``strict_parse``: strict JSON, JSONL, CSV, and decimal parsing (A-4);
- ``archive``: bounded, link-free, traversal-free archive extraction (A-4);
- ``quarantine``: hash-on-receipt intake and manifest-gated release from quarantine (A-4, A-5);
- ``receipts``: the durable, hash-chained receipt journal for intake and release (A-5);
- ``backup``: backup copy and restore verification against a manifest (A-3).

Passing these controls is necessary but never sufficient: every acquisition still needs
the owner approvals and records listed in ``docs/external_access.md`` §2.
"""
