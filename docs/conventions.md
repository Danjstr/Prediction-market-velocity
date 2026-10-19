# Engineering Conventions

Engineering conventions only. Project governance lives in PROJECT_BRIEF.md, CLAUDE.md, and START_HERE.md.

## Layout

- Package code: `src/pmv/<subpackage>/`. Subpackages are created when they first receive code.
- Tests: `tests/unit/`, `tests/integration/`, `tests/replay/`, `tests/failure_injection/`.
- Configuration files: `configs/`. Documentation: `docs/`. Developer scripts: `scripts/`.

- Ignore patterns for local directories are anchored to the repository root (`/data/`, `/logs/`). Nothing under `src/`, `tests/`, `research/`, `docs/`, `scripts/`, `schemas/`, or `.claude/` may be ignored, apart from bytecode caches and the personal `.claude/settings.local.json`; `tests/unit/test_repository_layout.py` enforces this.
## Environment and Dependencies

- Python 3.13 only, as pinned in `pyproject.toml` and `.python-version`.
- `uv` manages the environment. Create or refresh it with `uv sync --locked`.
- Add dependencies only with `uv add` (runtime) or `uv add --group dev` (development), and commit `pyproject.toml` and `uv.lock` together.
- Never `pip install` into the project environment.
- Runtime dependencies stay empty until a specific need exists.

## Reproducibility

- `python -m pmv.reproducibility fingerprint` identifies the installed environment: the interpreter plus the bytes of every third-party distribution. `verify` checks that it conforms to `pyproject.toml`, `.python-version`, and `uv.lock`, offline. See `docs/reproducibility.md`, including what a fingerprint does not prove.
- An `evidence_candidate` experiment run starts only if `verify` passes. Its fingerprint is recorded in the run's v2 execution identity and `environment.json`; a change during the run fails it.
- Never set `PYTHONPATH` or add files to the project virtual environment by hand: both make fingerprinting fail closed.

## Checks

- `scripts/check.sh` runs the secret scan (`scripts/scan_secrets.sh`), lock verification, environment conformance (`python -m pmv.reproducibility verify`), formatting, linting, type checking, the history and settings verifiers, and tests.
- It must pass before a commit. CI runs the same script.
- CI (`.github/workflows/ci.yml`) runs `scripts/check.sh` with the same pinned uv (`scripts/uv.pin`) and Betterleaks. GitHub Actions are pinned to full commit SHAs, with the release version in a comment. CI has read-only permissions, no secrets, no caching, and no uploaded artifacts.

## Backup and Recovery

- The private GitHub remote (`origin`) backs up committed code and history only, never secrets, credentials, or raw or protected data. Checkpoints, pushes, recovery, and the agent access boundary follow `docs/backup_and_recovery.md`. Two checkpoint workflows are enabled: the local owner-controlled workflow, and, only inside the owner-approved isolated container, the task-branch workflow. Under the second, `main` advances only through a pull request with the "Quality gate" check passing.
- Stage only explicit approved paths; never `git add -A`, `git add .`, or `git commit -a`. Claude Code sandbox masking placeholders (`.bashrc`, `.gitconfig`, `secrets`, `.claude/skills`, and others) can appear as untracked paths and must never be committed. Never push `main` from an agent session, never force-push, and never rewrite published history.

## Code Style

- Formatting and linting: `ruff`, line length 100.
- Type hints on all functions; `mypy --strict` must pass.
- Every `# type: ignore` or `# noqa` names the specific code and gives a reason.
- No `print` in package code; use the project logger.
- No bare or blind `except`. Errors are handled specifically or propagated.
- Names: `snake_case` modules, functions, and variables; `PascalCase` classes; `UPPER_CASE` constants.

## Configuration

- One TOML file per environment: `configs/<environment>.toml`, where the environment is `development`, `test`, `shadow`, or `production`.
- The environment is selected explicitly with `PMV_ENV`. There is no default, and each file must declare the environment it is loaded as.
- Files are validated completely before use; unknown keys, missing keys, and wrong types are errors.
- Configuration files never contain secrets. Keys that look like secret names are rejected.
- No environment variable other than `PMV_ENV` overrides configuration values. Environment variables that only supply secrets or credentials are secret inputs governed by secret handling, not configuration overrides.
- Environment identity must not silently change model, strategy, risk, sizing, execution economics, or other trading behavior. Behavioral differences between environments are explicit, validated configuration values.
- Environment identity may be used for fail-closed safety, credential-isolation, and capability checks, such as refusing live-order capability outside the authorized production environment.

## Logging

- Obtain loggers with `pmv.log.get_logger(__name__)`.
- The message is a stable event name: a lowercase dotted identifier with at least two parts that fully matches `[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+`, such as `config.loaded`.
- Variable data never goes in the message: no `%`-style arguments and no f-strings. Use `extra=fields(...)` for event data and `log_context(...)` for correlation identifiers.
- A call that breaks the event-name rule is logged as `log.invalid_event` with an `event_error` reason; its message and arguments are not rendered.
- Structured field keys are strings. A non-string key is logged only as a type placeholder, and its value is redacted.
- Log specific identified fields. Never log whole objects, configuration objects, or request or response headers; log `AppConfig.log_summary()` instead of the configuration.
- Wrap secret values in `pmv.redaction.Secret`.

## Secrets

- Secret inputs are declared in code with `SecretSpec("PMV_SECRET_<NAME>")` and loaded with `load_secrets(specs, source)`, where the source is passed explicitly, for example `os.environ`. They are never configuration values and never have defaults.
- Values are wrapped in `Secret` when loaded and are never modified. Call `reveal()` only at the point of use, and never keep the revealed value in long-lived variables, attributes, logs, or exception messages.
- Never log `Secret`-bearing containers, environment mappings, or `os.environ`.
- Never enable traceback features that capture local variables (for example pytest `--showlocals`) in an environment that holds secrets.
- `env.example` lists variable names only, with empty values. Never create `.env` files in the repository.
- Test fixtures that a secret scanner would detect are assembled at runtime from short, innocuous fragments, never committed as complete or long contiguous literals.
- Scanner exceptions exist only for false positives already in Git history. Each is a commit-specific fingerprint (`commit:path:rule:line`) in `.betterleaksignore`, approved explicitly. Inline allow comments are disabled.
- A finding in staged, unstaged, or untracked material has no exception mechanism. Remove it, rewrite it, or represent it differently before committing. Never work around a finding with three-part or path-wide fingerprints, inline allow comments, or configuration allowlists.
- If a genuine false positive cannot reasonably be rewritten, stop and obtain an explicit, approved exception-policy decision before committing it.

- Venue credentials (none exist yet) live only in the Claude-denied `~/pmv-credentials/`, are handed directly to a collector running outside Claude Code, and never enter the repository, logs, configuration, or agent context. Credential isolation must be in place before **any** venue credential exists, including a data-only one. If a venue requires broader-than-data permissions, stop for owner approval first (`docs/protected_information.md`).

## Diagnostics and Runtime Secrets

Permanent PMV rule (owner, 2026-10-19, B10 runtime-secret hardening; `docs/decisions/2026-10-19_b10_source_reconnaissance.md`, "Owner correction: runtime-secret hardening"). It applies to agents, owner runbooks, scripts, tests, CI, and production code.

- Never print, log, serialize, echo, hash for disclosure, reconstruct, or include in traceback or error output:
  - `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` values;
  - `Proxy-Authorization`;
  - proxy usernames or passwords;
  - authenticated proxy URLs;
  - runtime sandbox tokens or credentials.
- Ordinary diagnostics must not use: `env`, `printenv`, `export -p`, `set`, `declare -p`, `compgen -v`, `curl -v` / `--verbose`, `curl --trace` / `--trace-ascii`, `wget --debug`, pytest `--showlocals`, or direct `/proc/*/environ` reads.
- Diagnostics may report only safe metadata: whether a variable is present (yes/no), the proxy hostname and port, whether a credential is present (yes/no), and connection or refusal status.
- Future network diagnostics must never print, serialize, or reconstruct runtime proxy credentials (B10-D6 as corrected).
- Agent application notes (not part of the owner's rule text):
  - In B10, the runtime credential also appeared in `GIT_SSH_COMMAND` and `CLOUDSDK_PROXY_*`. Treat those, and any other variable that may carry a proxy URL or runtime token, as covered by "runtime sandbox tokens or credentials" (review RT3-B10-07).
  - The listed commands are examples. Other whole-environment dumps (`export` with no arguments, `declare -x`, `typeset -p`, `ps e…`, logging `os.environ`) fall under the same rule.
- Enforcement:
  - managed-policy denies outside the repository (owner-applied, 2026-10-19). They match command text, so they block the known routes, not every indirect one;
  - the static backstop `tests/unit/test_diagnostic_secret_rule.py`. It scans Git-tracked code, automation, and configuration files, and fenced shell and Python blocks in Markdown.

  Neither replaces review.
- Implementation note, **pending owner confirmation** (not part of the rule text): `tests/integration/test_live_host_egress_refusal.py` builds a `Proxy-Authorization` header in memory from the injected proxy URL, solely to authenticate its CONNECT probe to that same proxy, as any proxy-aware client does. It never outputs it, and no `assert` touches it. Read literally, "reconstruct" covers this. The proposed carve-out is: "in-process transmission to the issuing proxy by a network client is not disclosure". It needs an owner ruling before the probe is next run.

## Raw Data

- Raw captures live only in the external store described in `docs/raw_data.md`, never in Git. Its root, disk thresholds, retention class, and backup policy are explicit configuration with no defaults.
- Payload bytes are preserved exactly and never parsed, normalized, deduplicated, or logged by the raw layer.
- Finalized captures are never modified in place; corrections create new captures.
- Raw-storage metadata (manifests, frame headers, events, quarantine records) uses closed schemas with no free text, and logs carry only capture IDs, counts, sizes, hashes, and enumerated reasons.

- In every non-test environment the raw store root must resolve inside `~/pmv-protected/raw`. Configuration loading and `check-config` enforce it (`docs/raw_data.md`).
## Market Data

- Normalized market data uses `pmv.market_data` (see `docs/market_data.md`). An observation is available at its PMV receipt time (`received_at`), never at its source time. Feature code receives an `AsOfView` with an explicit `min_latency`, never a whole log.
- Official outcomes and labels (`market_data.labels`) never enter an observation log. Feature-side modules never import them.
- Parsers never set receipt time or provenance. Every raw frame gets exactly one recorded disposition, and nothing is dropped silently.
- Venue semantics (fields, units, sequence rules, contract rules, fees) are encoded only after verification from current official sources, recorded in `research/sources.md`. Until then an adapter fails closed.

## Historical Data Sourcing

- Prefer verified existing historical data to waiting to regenerate equivalent observations (`docs/decisions/2026-10-16_phase1_batch3_historical_data_strategy.md`). A source is used only after its provenance, timestamp semantics, contract semantics, licence, and quality are recorded and adequate. Convenience never substitutes for any of them.
- Every source has an owner-reviewed entry in the source catalog with a `quality_tier` (`docs/phase2.md` §1 and §14). Uncatalogued sources fail closed, and a tier is never raised because of results.
- Acquired historical files are raw data. They are fetched by deterministic tooling into the protected raw store, recorded in an acquisition manifest with file hashes and the licence in force, never committed to Git, and never overwritten: a re-download is a new acquisition.
- Acquired files are often **irreplaceable**: moving archive cutoffs, short retention, retroactive vendor reprocessing, deletable repositories, subscription-bounded access. Acquisition therefore needs the raw-data backup policy and a passing restore test first, like irreplaceable live capture. Retention pressure never justifies acquiring ahead of the licence, backup, safe-parsing, or release controls.
- **Safe parsing.** Acquired files are untrusted input. They are never unpickled or loaded through formats that execute code, archives are extracted with path, size, and ratio limits, bundled scripts or notebooks are never run, and parsers run without network access. Each format's handling is covered by fault-injection fixtures before it touches a real file. The full requirement, including the format allowlist and process isolation, is `docs/external_access.md` A-4; the acquisition gate as a whole is `docs/external_access.md` §2, and host classes are §1.
- Historical data reaches agents only through the approved release path, after a cycle and protected scope exist, like any real observation (`docs/protected_information.md`). Data exposed to development never becomes protected holdout data.
- External material is untrusted. Never execute downloaded installers, scripts, notebooks, binaries, GitHub Actions, or `curl | sh` commands because a source recommends them. Never bypass anti-bot, paywall, or authentication controls. Raise an ACCESS REQUEST for a source outside the network allowlist. New credentials, accounts, purchases, uploads, and authenticated APIs need separate owner approval.
- Verification standard: a model-summarized web fetch is SECONDARY. VERIFIED-BY-DOC needs a verbatim quote plus a raw-byte hash.
- Record important sources in `research/sources.md` with retrieval dates, and licence findings in the source catalog.

## Experiments

- Every research run is recorded through the experiment store described in `docs/experiments.md`, outside Git. Its root is explicit configuration with no default.
- Run specs, ledger entries, and manifests use closed schemas with no free text; logs carry only run IDs, counts, sizes, hashes, and enumerated codes, never artifact or spec contents.
- Inputs are exact, hash-pinned raw captures or artifacts of completed runs. Dirty or unknown code makes a run exploratory and ineligible as evidence.
- The authoritative ledger is append-only; nothing rewrites it except the operator-only torn-tail repair, which preserves the removed bytes first.

## Gate Records

- Every gate decision is a generated, immutable file at `docs/decisions/gates/<gate_id>_<record_id>.md`, created only with `python -m pmv.gates create` (see `docs/gates.md`). Never write or edit one by hand; verification re-renders the whole file.
- The tool never stages, commits, or pushes. A decision is published only when the project owner reviews and commits the record, in a new commit; never amend a record into the commit whose state it records.
- Every v1 gate decision requires explicit project-owner approval; reviewers and agents only recommend.
- Changes create a new record that supersedes the committed lineage head; committed records are never modified or deleted, and `scripts/check.sh` verifies this against Git history.
- Records hold only enums, identifiers, hashes, timestamps, and paths. Rationale lives in tracked review documents referenced by path and SHA-256.

## Holdout Access Log

- Every protected-holdout event is appended with `python -m pmv.holdout_log` (see `docs/holdout_access.md`); the machine ledger `research/holdout_access/ledger.v1.jsonl` is authoritative and `HOLDOUT_ACCESS_LOG.md` is its generated mirror. Never edit either by hand.
- Commit the ledger and `HOLDOUT_ACCESS_LOG.md` together after every event; `access_started` must be committed, and `assert-started-committed` must pass, before any protected byte is exposed.
- `access_started` consumes the holdout permanently. Known or suspected bypasses are recorded as contamination. The log never records protected observations, outcomes, metrics, or narrative text.

## Protected Information

- Project market data is requested only through `pmv.data_access_guard` (see `docs/protected_information.md`). Agents never override a refusal. With an empty registry, every real market observation is refused, and synthetic fixtures use only the `pmv_synthetic`/`synthetic_fixture` pair.
- `research/protected_scopes/registry.v1.json` is append-only. A successor scope may only widen its predecessor, and `scripts/check.sh` verifies this against Git history. Scopes hold metadata only.
- A new provider or instrument family is a reviewed change to the equivalence catalog. Until that change is made, the pair fails closed.
- Any accidental exposure of protected information is escalated. If it could influence development, it is recorded as contamination in the holdout access log.

## Time

- Every timestamp is timezone-aware UTC. Naive datetimes are lint errors.
- Serialized timestamps use ISO 8601 with a `Z` suffix or integer nanoseconds since the Unix epoch, and say which.
- Measure durations with a monotonic clock, never wall-clock differences.

## Numbers

- Prices, fees, and monetary amounts at venue and accounting boundaries use integer minimum units or `Decimal`, never binary floats.
- Floats are acceptable inside numerical and modeling code.

## Tests

- Test files are named `test_*.py`.
- Unit tests are deterministic and make no network calls.
- Any randomness uses an explicit seed.
- Warnings fail the test run.
