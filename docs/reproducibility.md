# Reproducibility (Phase 0 Step 10)

This document describes how the installed Python environment is identified and checked, and how that identity makes a future experiment run evidence-eligible.

**The v2 reproducibility mechanism is implemented and synthetically testable, but real evidentiary use is not yet authorized pending Step 11 resolution of the remaining execution-boundary issues** (cached bytecode, working-directory shadowing, and gate verification of run files; see `docs/gate0_readiness.md`).
- Implementation: `src/pmv/reproducibility.py`.
- Environment document schema: `schemas/environment_v1.json`.
- Experiment integration: `docs/experiments.md`.

The Python validators are authoritative.

## Two separate questions

| Command | Question | Result |
|---|---|---|
| `python -m pmv.reproducibility fingerprint` | What environment is actually installed? | The SHA-256 of the canonical environment document. `--document` prints the document itself. |
| `python -m pmv.reproducibility verify` | Does it conform to the approved project? | Exit 0 and the fingerprint, or one fixed-text error line |

Both work offline. They need no remote, no GitHub, no secrets, no agent and no LLM, and they keep no ledger. `scripts/check.sh` runs `verify` after `uv sync --locked`.

## The environment document (`pmv.environment` v1)

**Interpreter:**
- implementation and full version;
- `cache_tag`, `SOABI`, `sysconfig.get_platform()`, byte order, and whether the GIL is disabled;
- the `sys.flags` values that change how code executes: `optimize`, `utf8_mode`, `dev_mode`, `hash_randomization`. The `PYTHONHASHSEED` value is never recorded.

**Distributions:** every third-party distribution in the project virtual environment, sorted by PEP 503 normalized name. Each entry holds:
- the name and version;
- `files_sha256`: the SHA-256 of `{"files": [[path, sha256], …]}`, built from every file its `RECORD` lists with a hash and sorted by path.

Every listed file is re-hashed from disk and must match its `RECORD` digest. Every `RECORD` row must carry a SHA-256 hash, except the row for that `RECORD` file itself. Otherwise editing `RECORD` could make a new file look owned without hashing it. Two kinds of file are excluded:
- **cached bytecode** (anything under `__pycache__`). A sourceless `.pyc` listed with a hash is code, and is hashed like any other file;
- **generated console- and GUI-script launchers**, meaning `RECORD` files outside site-packages whose name is one of the distribution's `console_scripts`/`gui_scripts` entry points. Their shebang embeds the absolute interpreter path. Shipped binaries such as `bin/ruff` are kept.

**Project:** only `{name, version, editable: true}`.
- PMV's own install metadata (`.pth`, `direct_url.json`) contains absolute paths, so it is excluded from the document.
- PMV's code identity is the Git commit and dirty state in the execution identity.
- PMV may own only its one top-level `.pth` and a fixed set of dist-info files (`INSTALLER`, `METADATA`, `RECORD`, `REQUESTED`, `WHEEL`, `direct_url.json`, `uv_build.json`, `uv_cache.json`).
  - It has no `entry_points.txt`, so it cannot register a plugin.
  - Each hashed file still has to match its `RECORD` digest.
  - The `.pth` must hold exactly one path line and no code. `verify` also requires that path to be `<repo>/src`.

**Never included:**
- paths, HOME, usernames and hostnames;
- the virtual-environment or checkout location;
- timestamps and caches;
- environment-variable values and credentials.

`pyproject.toml` and `uv.lock` hashes are also left out. The execution identity already records `uv_lock_sha256` and the clean commit, so the fingerprint stays "what is installed", not "what was intended".

### Fail-closed conditions

The fingerprint is refused when:
- `PYTHONPATH` is non-empty, or user site-packages is enabled (code outside the described environment could run). Only the variable's presence is checked; its value is never read into output.
- two distributions share a normalized name;
- a `RECORD` is missing or malformed (a bad row, a non-SHA-256 hash, an absolute path, or `..` inside a path);
- a listed file is missing, is a symlink, or doesn't match its hash;
- site-packages contains a file, or a symlinked directory, that no `RECORD` owns, including an injected `.pth` (`__pycache__` directories excepted), or a directory cannot be read;
- any other error reading the environment occurs. It is reported as one fixed-text error and never as a traceback or path;
- PMV is missing, or its `.pth` holds anything but one path.

The `PYTHONPATH` rule deliberately checks presence only, with no general `sys.path` classification. An unexpected entry from an owned third-party `.pth` file is already covered, because that file's bytes are hashed.

## Conformance (`verify`)

`verify` checks the following, then captures the document:
1. **Python version:** it satisfies `requires-python` in `pyproject.toml` and matches `.python-version`. A small specifier checker fails closed on any form it doesn't understand.
2. **Virtual environment:** the interpreter runs in `<repo>/.venv` with `include-system-site-packages = false`.
3. **PMV install:** PMV is imported from `<repo>/src/pmv` and installed editable from this repository (`direct_url.json`).
4. **Lock consistency:** `uv lock --check`.
5. **Exact environment:** `uv sync --locked --check`, so nothing is missing and nothing is extra.

Steps 4 and 5 run the uv version pinned in `scripts/uv.pin`. They run offline, with a minimal environment (`PATH`, `HOME` and `UV_CACHE_DIR`, and empty `XDG_CONFIG_HOME`/`XDG_CONFIG_DIRS`, so user and system `uv.toml` files don't apply), and never print uv's output.

uv decides whether the editable PMV install is fresh partly from file modification times under `src/` and `pyproject.toml`. After editing them, `uv sync --check` can report the environment as outdated, and `verify` then fails closed until `uv sync --locked` runs again. That rebuild needs the build backend (hatchling) in the uv cache or from the network.

## What a matching fingerprint shows, and what it does not

**It shows** the same:
- CPython build line (version, ABI and platform) and execution flags;
- exact set of third-party distributions and versions;
- installed bytes for every hashed file, including compiled extensions;

that there is no unowned file or symlinked directory in site-packages, and that PMV is installed editable from the repository.

**It does not show:**
- identical standard-library bytes (for example the Debian `python3.13` package);
- identical libc, libm, OpenSSL or other system libraries;
- the same kernel, CPU behavior, native runtimes outside packaged files (for example a system BLAS), or timezone database;
- bit-for-bit numerical reproducibility or deterministic model behavior;
- resistance to a malicious root user;
- that the installed files came from the exact wheels hashed in `uv.lock`. uv checks those hashes at install time; afterwards the link is the version-level check in `uv sync --check`;
- **cached bytecode.** `__pycache__/*.pyc` files are not hashed, and Python trusts a cached `.pyc` whose header matches the source file's modification time and size. Tampered cached bytecode, in site-packages or in the Git-ignored `src/pmv/__pycache__`, can run without changing the fingerprint or the Git identity. Hardening evidence runs against this is deferred to Step 11 (options: no bytecode writes plus a purge, or hash-checked bytecode). **This must be resolved before any real v2 `evidence_candidate` may count as evidence;**
- **the working directory.** `python -m …` puts the working directory first on `sys.path`, ahead of site-packages. An untracked or Git-ignored `.py` file there can shadow a module without making the tree dirty. Evidence runs must be started from a clean repository root. Enforcing this (for example Python's safe-path mode) is deferred to Step 11. **This must be resolved before any real v2 `evidence_candidate` may count as evidence.**

Fingerprints differ legitimately between machines. CI's Python comes from `actions/setup-python`, not the Debian interpreter, so a CI fingerprint will not equal a local one. A fingerprint identifies one environment, not a project-wide approved value. Reproducing a run means rebuilding the environment from that commit's `uv.lock` on the same Python patch release and platform, then comparing fingerprints.

This is intentionally not an OS image, container, Nix, Docker or SBOM system.

## Experiment evidence (integration with Step 6)

- **Versions:**
  - Execution identity **v2** (`pmv.experiment.execution_identity`, `schema_version` 2) records `installed_environment_sha256`: the SHA-256 of the run's `environment.json`.
  - Ledger entry **v2** (`schemas/experiment_ledger_entry_v2.json`) carries v2 identities and adds the failure code `environment_changed`.
  - Writers emit v2.
  - v1 identities and v1 entries are still verified exactly as Step 6 defined them, with a null fingerprint and never eligible. Entry versions never go backwards.
  - The run-spec, run-manifest, checkpoint and store formats are unchanged.
- **Start:**
  - An `evidence_candidate` start runs `verify` first. If verification fails, the start is **refused** with a bounded error before anything is written: the run is never silently demoted.
  - Otherwise the canonical document is written once to `runs/<run_id>/environment.json` (read-only, like `run_spec.json`) and its hash goes into the v2 identity.
  - A start retried after a failed attempt must see the same environment: a different `environment.json` refuses the start. If an earlier attempt wrote one and this attempt cannot capture the environment at all, the start is also refused.
  - Other run classes need no verification. They record a fingerprint when one can be computed and null when it cannot; they are never eligible either way.
- **Completion:** the fingerprint is recomputed. If it changed, or can no longer be computed, the run fails with `environment_changed`. A changed Git or `uv.lock` identity still fails with `code_identity_changed`.
- **Eligibility at start:** the existing Step 6 rules, plus a fingerprint. That means:
  - a clean commit and a `uv.lock` hash (a dirty tree is never eligible);
  - verification passed (the start was not refused);
  - a v2 identity that holds the fingerprint;
  - eligible inputs.

  The ledger verifier refuses a v2 `run_started` that claims a clean `evidence_candidate` without a fingerprint.

  Limit: neither the ledger nor `environment.json` records that `verify` itself passed. That rests on the store code, which tests check, refusing the start otherwise. Recording it explicitly would be a format addition and is an open Step 11 decision.
- **Later:**
  - `verify_run` requires `environment.json` to exist exactly when a fingerprint was recorded, to hash to it, and to be a valid document.
  - Later changes to the environment, `uv.lock` or code never alter a past run's eligibility at start; they only produce new identities for new runs.

## Performance

Fingerprinting re-hashes every listed installed file, about 0.8 s for the current development environment. `verify` (which also runs uv twice) takes about 2.5 s. This is deliberate: it is what backs the integrity claim. If future ML environments make it too expensive, change it through a new document version, not silently.
