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

- `scripts/check.sh` runs lock verification, formatting, linting, type checking, and tests.
- It must pass before a commit. CI runs the same script.

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
