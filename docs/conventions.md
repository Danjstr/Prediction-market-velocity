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
