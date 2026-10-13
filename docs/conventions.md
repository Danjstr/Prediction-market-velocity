# Engineering Conventions

Engineering conventions only. Project governance lives in PROJECT_BRIEF.md, CLAUDE.md, and START_HERE.md.

## Layout

- Package code: `src/pmv/<subpackage>/`. Subpackages are created when they first receive code.
- Tests: `tests/unit/`, `tests/integration/`, `tests/replay/`, `tests/failure_injection/`.
- Configuration files: `configs/`. Documentation: `docs/`. Developer scripts: `scripts/`.

## Environment and Dependencies

- Python 3.13 only, as pinned in `pyproject.toml` and `.python-version`.
- `uv` manages the environment. Create or refresh it with `uv sync --locked`.
- Add dependencies only with `uv add` (runtime) or `uv add --group dev` (development), and commit `pyproject.toml` and `uv.lock` together.
- Never `pip install` into the project environment.
- Runtime dependencies stay empty until a specific need exists.

## Checks

- `scripts/check.sh` runs the secret scan (`scripts/scan_secrets.sh`), lock verification, formatting, linting, type checking, and tests.
- It must pass before a commit. CI runs the same script.
- CI (`.github/workflows/ci.yml`) runs `scripts/check.sh` with the same pinned uv (`scripts/uv.pin`) and Betterleaks. GitHub Actions are pinned to full commit SHAs, with the release version in a comment. CI has read-only permissions, no secrets, no caching, and no uploaded artifacts.

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

## Raw Data

- Raw captures live only in the external store described in `docs/raw_data.md`, never in Git. Its root, disk thresholds, retention class, and backup policy are explicit configuration with no defaults.
- Payload bytes are preserved exactly and never parsed, normalized, deduplicated, or logged by the raw layer.
- Finalized captures are never modified in place; corrections create new captures.
- Raw-storage metadata (manifests, frame headers, events, quarantine records) uses closed schemas with no free text, and logs carry only capture IDs, counts, sizes, hashes, and enumerated reasons.

## Experiments

- Every research run is recorded through the experiment store described in `docs/experiments.md`, outside Git. Its root is explicit configuration with no default.
- Run specs, ledger entries, and manifests use closed schemas with no free text; logs carry only run IDs, counts, sizes, hashes, and enumerated codes, never artifact or spec contents.
- Inputs are exact, hash-pinned raw captures or artifacts of completed runs. Dirty or unknown code makes a run exploratory and ineligible as evidence.
- The authoritative ledger is append-only; nothing rewrites it except the operator-only torn-tail repair, which preserves the removed bytes first.

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
