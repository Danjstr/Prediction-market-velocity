"""Installed-environment identity and conformance (Phase 0 Step 10).

Two separate questions:

- ``fingerprint`` -- what Python/package environment is actually installed? The canonical
  environment document (schema ``pmv.environment`` v1) records the interpreter identity and,
  for every third-party distribution, its name, version, and an aggregate SHA-256 of the
  bytes of every file its RECORD lists with a hash. Every listed file is re-hashed and must
  match RECORD. The fingerprint is the SHA-256 of the canonical document.
- ``verify`` -- does that environment conform to the approved project? The lock matches
  ``pyproject.toml``; the installed set matches ``uv.lock`` exactly (pinned uv, offline);
  the Python version satisfies ``requires-python`` and ``.python-version``; the interpreter
  runs in this repository's ``.venv`` without system or user site-packages; and PMV is
  installed editable from this repository.

The document deliberately excludes anything location-, user-, or time-dependent: paths,
HOME, usernames, hostnames, the virtual-environment location, timestamps, caches, ``.pyc``
files, environment-variable values, and PMV's own install metadata (its code identity is the
Git commit and dirty state in the execution identity). Generated console-script launchers
(whose shebang embeds the absolute interpreter path) are excluded; shipped binaries are not.

Limits: a matching fingerprint does NOT prove identical standard-library bytes, system
libraries (libc, libm, OpenSSL), kernel, CPU behavior, native runtimes outside packaged
files, timezone data, bit-for-bit numerical results, or resistance to a malicious root
user. See docs/reproducibility.md.

No network, no LLM, no service, and no ledger.
"""

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import site
import subprocess
import sys
import sysconfig
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from itertools import dropwhile
from pathlib import Path, PurePosixPath
from typing import Final

from pmv.integrity import (
    FormatError,
    canonical_line,
    is_sha256,
    parse_canonical_json,
    sha256_hex,
)

DOCUMENT_SCHEMA: Final = "pmv.environment"
DOCUMENT_VERSION: Final = 1
PROJECT_NAME: Final = "prediction-market-velocity"
MAX_DOCUMENT_BYTES: Final = 1_048_576
_NAME: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_VERSION: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+!_-]{0,63}")
_RECORD_HASH: Final = re.compile(r"sha256=([A-Za-z0-9_-]{43})")
_LAUNCHER_GROUPS: Final = ("console_scripts", "gui_scripts")
_UV_ENVIRONMENT: Final = ("PATH", "HOME", "UV_CACHE_DIR")
# The only files PMV's editable install may own besides its one .pth. No entry points: an
# entry_points.txt here could load code (for example a pytest plugin) without a fingerprint.
_PROJECT_DIST_INFO: Final = frozenset(
    {
        "INSTALLER",
        "METADATA",
        "RECORD",
        "REQUESTED",
        "WHEEL",
        "direct_url.json",
        "uv_build.json",
        "uv_cache.json",
    }
)


class ReproducibilityError(Exception):
    """The environment cannot be identified or does not conform. Messages are fixed text:
    they never contain paths, environment values, or package file contents."""


@dataclass(frozen=True, slots=True)
class EnvironmentCapture:
    """A canonical environment document and its SHA-256 (the environment fingerprint)."""

    document: bytes
    sha256: str


# ----- fingerprint -----


def normalize_name(name: str) -> str:
    """PEP 503 normalized distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def interpreter_identity() -> dict[str, object]:
    """Interpreter facts that change how Python code executes (no paths)."""
    gil = sysconfig.get_config_var("Py_GIL_DISABLED")
    soabi = sysconfig.get_config_var("SOABI")
    return {
        "byteorder": sys.byteorder,
        "cache_tag": sys.implementation.cache_tag,
        "flags": {
            "dev_mode": bool(sys.flags.dev_mode),
            "hash_randomization": int(sys.flags.hash_randomization),
            "optimize": int(sys.flags.optimize),
            "utf8_mode": int(sys.flags.utf8_mode),
        },
        "gil_disabled": bool(gil),
        "implementation": sys.implementation.name,
        "platform": sysconfig.get_platform(),
        "soabi": soabi if isinstance(soabi, str) else None,
        "version": platform.python_version(),
    }


def environment_document() -> dict[str, object]:
    """The canonical environment document of the running interpreter."""
    return build_document(
        Path(sysconfig.get_paths()["purelib"]),
        interpreter=interpreter_identity(),
        environ=os.environ,
        user_site_enabled=site.ENABLE_USER_SITE is True,
    )


def fingerprint() -> str:
    """The environment fingerprint: SHA-256 of the canonical environment document."""
    return sha256_hex(canonical_line(environment_document()))


def build_document(
    site_dir: Path,
    *,
    interpreter: Mapping[str, object],
    environ: Mapping[str, str],
    user_site_enabled: bool,
) -> dict[str, object]:
    """Build and validate the document for one site-packages directory.

    Fails closed on: a non-empty PYTHONPATH or enabled user site-packages (code outside the
    described environment could run); duplicate normalized names; a missing or malformed
    RECORD, including any row without a hash other than the RECORD's own row; a listed file
    that is missing, a symlink, or does not match its RECORD hash; any file or symlink in
    site-packages that no RECORD owns (``__pycache__`` directories excepted); a PMV install
    that owns anything but its single-path ``.pth`` and its known dist-info files; and any
    error reading the environment (reported as fixed text, never a path).
    """
    try:
        return _build_document(
            site_dir,
            interpreter=interpreter,
            environ=environ,
            user_site_enabled=user_site_enabled,
        )
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError, TypeError):
        raise ReproducibilityError("the installed environment could not be read") from None


def _build_document(
    site_dir: Path,
    *,
    interpreter: Mapping[str, object],
    environ: Mapping[str, str],
    user_site_enabled: bool,
) -> dict[str, object]:
    if environ.get("PYTHONPATH", ""):
        raise ReproducibilityError("PYTHONPATH is set; code outside the environment could run")
    if user_site_enabled:
        raise ReproducibilityError("user site-packages is enabled")
    distributions: dict[str, dict[str, object]] = {}
    project: dict[str, object] | None = None
    owned: set[str] = set()
    for dist in metadata.distributions(path=[str(site_dir)]):
        name, version = _name_and_version(dist)
        if name in distributions or (name == PROJECT_NAME and project is not None):
            raise ReproducibilityError("two installed distributions share a normalized name")
        rows = _record_rows(dist)
        owned.update(path for path, _digest in rows if not path.startswith("../"))
        if name == PROJECT_NAME:
            _check_project_rows(dist, rows)
            _check_project_pth(site_dir, rows)
            for path, digest in rows:
                if digest is not None:
                    _verified_sha256(dist, path, digest)
            project = {"editable": True, "name": name, "version": version}
            continue
        launchers = _launchers(dist)
        files: list[list[str]] = []
        for path, digest in rows:
            if digest is None or _is_bytecode(path):
                continue
            if path.startswith("../") and PurePosixPath(path).name in launchers:
                continue
            files.append([path, _verified_sha256(dist, path, digest)])
        distributions[name] = {
            "files_sha256": sha256_hex(canonical_line({"files": sorted(files)})),
            "name": name,
            "version": version,
        }
    if project is None:
        raise ReproducibilityError("the PMV project is not installed in the environment")
    _check_unowned(site_dir, owned)
    document: dict[str, object] = {
        "distributions": [distributions[name] for name in sorted(distributions)],
        "interpreter": dict(interpreter),
        "project": project,
        "schema": DOCUMENT_SCHEMA,
        "schema_version": DOCUMENT_VERSION,
    }
    validate_document(document)
    return document


def _name_and_version(dist: metadata.Distribution) -> tuple[str, str]:
    raw_name, version = dist.metadata["Name"], dist.version
    if not isinstance(raw_name, str) or not isinstance(version, str):
        raise ReproducibilityError("a distribution has no name or version")
    name = normalize_name(raw_name)
    if _NAME.fullmatch(name) is None or _VERSION.fullmatch(version) is None:
        raise ReproducibilityError("a distribution name or version is malformed")
    return name, version


def _dist_info_name(dist: metadata.Distribution) -> str:
    location = getattr(dist, "_path", None)
    if not isinstance(location, Path) or not location.name.endswith(".dist-info"):
        raise ReproducibilityError("a distribution is not an installed .dist-info directory")
    return location.name


def _record_rows(dist: metadata.Distribution) -> list[tuple[str, str | None]]:
    """RECORD rows; only the RECORD's own row may lack a SHA-256 hash."""
    own_record = f"{_dist_info_name(dist)}/RECORD"
    text = dist.read_text("RECORD")
    if not text:
        raise ReproducibilityError("an installed distribution has no RECORD")
    rows: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        if len(row) != 3 or not row[0]:
            raise ReproducibilityError("a RECORD row is malformed")
        path, digest, _size = row
        parts = PurePosixPath(path).parts
        inner = parts[len(parts) - len(tuple(dropwhile(lambda part: part == "..", parts))) :]
        # Only leading "../" (installer data such as bin/) is allowed; never ".." inside.
        if path.startswith("/") or "\\" in path or path in seen or not inner or ".." in inner:
            raise ReproducibilityError("a RECORD path is malformed")
        seen.add(path)
        if digest == "":
            if path != own_record:
                raise ReproducibilityError("a RECORD row other than RECORD itself has no hash")
            rows.append((path, None))
            continue
        match = _RECORD_HASH.fullmatch(digest)
        if match is None:
            raise ReproducibilityError("a RECORD hash is malformed or not SHA-256")
        rows.append((path, match.group(1)))
    return rows


def _launchers(dist: metadata.Distribution) -> frozenset[str]:
    return frozenset(point.name for point in dist.entry_points if point.group in _LAUNCHER_GROUPS)


def _is_bytecode(path: str) -> bool:
    """Cached bytecode only. A sourceless .pyc listed with a hash is code and is hashed."""
    return "__pycache__" in PurePosixPath(path).parts


def _verified_sha256(dist: metadata.Distribution, path: str, recorded: str) -> str:
    """Hash the installed bytes; they must match the RECORD digest."""
    location = Path(str(dist.locate_file(path)))
    digest = hashlib.sha256()
    try:
        fd = os.open(location, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise ReproducibilityError("a file listed in RECORD is missing or unreadable") from None
    try:
        while chunk := os.read(fd, 1_048_576):
            digest.update(chunk)
    finally:
        os.close(fd)
    if base64.urlsafe_b64encode(digest.digest()).rstrip(b"=").decode("ascii") != recorded:
        raise ReproducibilityError("an installed file does not match its RECORD hash")
    return digest.hexdigest()


def _check_project_rows(
    dist: metadata.Distribution, rows: Sequence[tuple[str, str | None]]
) -> None:
    """PMV owns exactly one top-level .pth and only its known dist-info files."""
    info = _dist_info_name(dist)
    for path, _digest in rows:
        parts = PurePosixPath(path).parts
        top_level_pth = len(parts) == 1 and path.endswith(".pth")
        known = len(parts) == 2 and parts[0] == info and parts[1] in _PROJECT_DIST_INFO
        if not (top_level_pth or known):
            raise ReproducibilityError("the PMV install owns an unexpected file")


def _check_project_pth(site_dir: Path, rows: Sequence[tuple[str, str | None]]) -> None:
    """PMV's editable .pth must be one path line: it may add a path, never run code."""
    pth = [path for path, _digest in rows if path.endswith(".pth")]
    if len(pth) != 1 or "/" in pth[0]:
        raise ReproducibilityError("the PMV editable install is not a single .pth path")
    try:
        text = (site_dir / pth[0]).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ReproducibilityError("the PMV editable .pth is unreadable") from None
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1 or lines[0].lstrip().startswith("import") or ";" in lines[0]:
        raise ReproducibilityError("the PMV editable .pth must hold exactly one path")


def _check_unowned(site_dir: Path, owned: set[str]) -> None:
    """Every file and symlink in site-packages must be owned; os.walk never follows symlinked
    directories, so an unowned one is refused instead of silently skipped."""

    def refuse(_error: OSError) -> None:
        raise ReproducibilityError("site-packages could not be fully read")

    for directory, subdirs, names in os.walk(site_dir, onerror=refuse):
        for name in subdirs:
            if os.path.islink(os.path.join(directory, name)):
                relative = Path(directory, name).relative_to(site_dir).as_posix()
                if relative not in owned:
                    raise ReproducibilityError("site-packages contains a symlink no one owns")
        subdirs[:] = sorted(
            name
            for name in subdirs
            if name != "__pycache__" and not os.path.islink(os.path.join(directory, name))
        )
        for name in names:
            relative = Path(directory, name).relative_to(site_dir).as_posix()
            if relative not in owned:
                raise ReproducibilityError("site-packages contains a file no distribution owns")


# ----- the closed document schema -----


def validate_document(document: object) -> None:
    """Validate a parsed environment document against the closed v1 schema."""
    if not isinstance(document, Mapping) or set(document) != {
        "distributions",
        "interpreter",
        "project",
        "schema",
        "schema_version",
    }:
        raise ReproducibilityError("the environment document fields do not match v1")
    version = document["schema_version"]
    if (
        document["schema"] != DOCUMENT_SCHEMA
        or isinstance(version, bool)
        or version != DOCUMENT_VERSION
    ):
        raise ReproducibilityError("the environment document schema is not supported")
    _validate_interpreter(document["interpreter"])
    project = document["project"]
    if (
        not isinstance(project, Mapping)
        or set(project) != {"editable", "name", "version"}
        or project["editable"] is not True
        or project["name"] != PROJECT_NAME
        or not isinstance(project["version"], str)
        or _VERSION.fullmatch(project["version"]) is None
    ):
        raise ReproducibilityError("the environment document project entry is malformed")
    items = document["distributions"]
    if not isinstance(items, list):
        raise ReproducibilityError("the environment document distributions are malformed")
    names: list[str] = []
    for item in items:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"files_sha256", "name", "version"}
            or not isinstance(item["name"], str)
            or _NAME.fullmatch(item["name"]) is None
            or item["name"] == PROJECT_NAME
            or not isinstance(item["version"], str)
            or _VERSION.fullmatch(item["version"]) is None
            or not is_sha256(item["files_sha256"])
        ):
            raise ReproducibilityError("an environment document distribution is malformed")
        names.append(item["name"])
    if names != sorted(set(names)):
        raise ReproducibilityError("environment document distributions must be sorted, unique")


def _validate_interpreter(value: object) -> None:
    keys = {
        "byteorder",
        "cache_tag",
        "flags",
        "gil_disabled",
        "implementation",
        "platform",
        "soabi",
        "version",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ReproducibilityError("the environment document interpreter is malformed")
    texts = ("cache_tag", "implementation", "platform", "version")
    if (
        value["byteorder"] not in ("little", "big")
        or not all(isinstance(value[key], str) and value[key] for key in texts)
        or not (value["soabi"] is None or isinstance(value["soabi"], str))
        or not isinstance(value["gil_disabled"], bool)
    ):
        raise ReproducibilityError("the environment document interpreter is malformed")
    flags = value["flags"]
    if (
        not isinstance(flags, Mapping)
        or set(flags) != {"dev_mode", "hash_randomization", "optimize", "utf8_mode"}
        or not isinstance(flags["dev_mode"], bool)
        or any(
            isinstance(flags[key], bool) or not isinstance(flags[key], int) or flags[key] < 0
            for key in ("hash_randomization", "optimize", "utf8_mode")
        )
    ):
        raise ReproducibilityError("the environment document interpreter flags are malformed")


def parse_document(data: bytes) -> dict[str, object]:
    """Parse and validate canonical environment-document bytes (one line, newline-ended)."""
    if len(data) > MAX_DOCUMENT_BYTES or not data.endswith(b"\n"):
        raise ReproducibilityError("the environment document is not one canonical line")
    try:
        document = parse_canonical_json(data[:-1])
    except FormatError:
        raise ReproducibilityError("the environment document is not canonical JSON") from None
    validate_document(document)
    return document


# ----- conformance -----

Runner = Callable[[Path, Sequence[str]], int]


def verify(repo_root: Path, *, runner: Runner | None = None) -> EnvironmentCapture:
    """Verify conformance to the approved project, then capture the environment."""
    root = Path(os.path.realpath(repo_root))
    check_python_version(platform.python_version(), root)
    check_virtual_environment(root)
    check_project_install(root)
    run = runner or _run_uv
    if run(root, ("lock", "--check")) != 0:
        raise ReproducibilityError("uv.lock is not consistent with pyproject.toml")
    if run(root, ("sync", "--locked", "--check")) != 0:
        raise ReproducibilityError("the installed environment does not match uv.lock exactly")
    return capture()


def capture() -> EnvironmentCapture:
    """The canonical document of the running environment and its fingerprint."""
    data = canonical_line(environment_document())
    return EnvironmentCapture(data, sha256_hex(data))


def check_python_version(version: str, repo_root: Path) -> None:
    """``version`` must satisfy pyproject ``requires-python`` and ``.python-version``."""
    try:
        with (repo_root / "pyproject.toml").open("rb") as handle:
            requires = tomllib.load(handle)["project"]["requires-python"]
        pinned = (repo_root / ".python-version").read_text(encoding="ascii").strip()
    except (OSError, KeyError, TypeError, UnicodeError, tomllib.TOMLDecodeError):
        raise ReproducibilityError("the project Python requirements are unreadable") from None
    if not isinstance(requires, str) or not satisfies(version, requires):
        raise ReproducibilityError("the Python version does not satisfy requires-python")
    if re.fullmatch(r"[0-9]+(\.[0-9]+){0,2}", pinned) is None or not (
        version == pinned or version.startswith(pinned + ".")
    ):
        raise ReproducibilityError("the Python version does not match .python-version")


def satisfies(version: str, specifier: str) -> bool:
    """A minimal ``>=``/``<``/``==``/``<=``/``>``/``!=`` checker for release versions;
    anything it does not understand fails closed."""
    try:
        actual = tuple(int(part) for part in version.split("."))
    except ValueError:
        return False
    for clause in specifier.split(","):
        match = re.fullmatch(r"\s*(>=|<=|==|!=|<|>)\s*([0-9]+(?:\.[0-9]+)*)(\.\*)?\s*", clause)
        if match is None:
            return False
        operator, number, wildcard = match.groups()
        wanted = tuple(int(part) for part in number.split("."))
        if wildcard and operator not in ("==", "!="):
            return False
        left = actual[: len(wanted)] if wildcard else actual
        width = max(len(left), len(wanted))
        a = left + (0,) * (width - len(left))
        b = wanted + (0,) * (width - len(wanted))
        results = {"==": a == b, "!=": a != b, ">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b}
        if not results[operator]:
            return False
    return True


def check_virtual_environment(
    repo_root: Path, *, prefix_path: str | None = None, base_prefix_path: str | None = None
) -> None:
    """The interpreter runs in ``<repo>/.venv``, isolated from system site-packages."""
    prefix = Path(os.path.realpath(prefix_path or sys.prefix))
    if prefix == Path(os.path.realpath(base_prefix_path or sys.base_prefix)):
        raise ReproducibilityError("the interpreter is not running in a virtual environment")
    if prefix != repo_root / ".venv":
        raise ReproducibilityError("the interpreter is not running in the project .venv")
    try:
        config = (prefix / "pyvenv.cfg").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise ReproducibilityError("the virtual environment configuration is unreadable") from None
    settings = {
        key.strip().lower(): value.strip().lower()
        for key, _sep, value in (line.partition("=") for line in config.splitlines())
    }
    if settings.get("include-system-site-packages") != "false":
        raise ReproducibilityError("the virtual environment includes system site-packages")


def check_project_install(
    repo_root: Path,
    *,
    module_file: str | None = None,
    direct_url: str | None = None,
    pth_text: str | None = None,
) -> None:
    """PMV is imported from this repository's ``src``, installed editable from it, and its
    ``.pth`` adds exactly ``<repo>/src``."""
    location = Path(os.path.realpath(module_file or _pmv_file()))
    if not location.is_relative_to(repo_root / "src" / "pmv"):
        raise ReproducibilityError("PMV is not imported from this repository")
    try:
        if direct_url is None or pth_text is None:
            dist = metadata.distribution(PROJECT_NAME)
            direct_url = direct_url if direct_url is not None else dist.read_text("direct_url.json")
            if pth_text is None:
                pth = [path for path, _digest in _record_rows(dist) if path.endswith(".pth")]
                if len(pth) != 1:
                    raise ReproducibilityError("the PMV editable install is not a single .pth path")
                pth_text = Path(str(dist.locate_file(pth[0]))).read_text(encoding="utf-8")
        info = json.loads(direct_url or "null")
    except (metadata.PackageNotFoundError, ValueError, OSError):
        raise ReproducibilityError("the PMV install record is unreadable") from None
    if (
        not isinstance(info, dict)
        or info.get("dir_info") != {"editable": True}
        or info.get("url") != repo_root.as_uri()
    ):
        raise ReproducibilityError("PMV is not installed editable from this repository")
    lines = [line.strip() for line in pth_text.splitlines() if line.strip()]
    if len(lines) != 1 or Path(os.path.realpath(lines[0])) != repo_root / "src":
        raise ReproducibilityError("the PMV editable .pth does not point at this repository")


def _pmv_file() -> str:
    import pmv

    return pmv.__file__ or ""


def _run_uv(repo_root: Path, arguments: Sequence[str]) -> int:
    """Run the pinned uv offline with a minimal environment; output is never printed."""
    uv = shutil.which("uv")
    if uv is None:
        raise ReproducibilityError("uv is not on PATH")
    pinned = _pinned_uv(repo_root)
    with tempfile.TemporaryDirectory(prefix="pmv-uv-config-") as empty:
        environment = {key: os.environ[key] for key in _UV_ENVIRONMENT if key in os.environ}
        # User and system uv.toml files must not change what uv checks.
        environment.update(
            {
                "LC_ALL": "C",
                "UV_OFFLINE": "1",
                "UV_NO_PROGRESS": "1",
                "XDG_CONFIG_HOME": empty,
                "XDG_CONFIG_DIRS": empty,
            }
        )
        return _uv_subprocess(uv, repo_root, arguments, environment, pinned)


def _uv_subprocess(
    uv: str,
    repo_root: Path,
    arguments: Sequence[str],
    environment: Mapping[str, str],
    pinned: str,
) -> int:
    try:
        version = subprocess.run(  # noqa: S603 - the pinned project tool, fixed arguments
            [uv, "--version"], env=environment, capture_output=True, text=True, timeout=60
        )
        if version.returncode != 0 or version.stdout.split()[:2] != ["uv", pinned]:
            raise ReproducibilityError("uv does not match the version pinned in scripts/uv.pin")
        completed = subprocess.run(  # noqa: S603 - the pinned project tool, fixed arguments
            [uv, *arguments],
            cwd=repo_root,
            env=environment,
            capture_output=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ReproducibilityError("uv could not be run") from None
    return completed.returncode


def _pinned_uv(repo_root: Path) -> str:
    try:
        lines = (repo_root / "scripts" / "uv.pin").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError):
        raise ReproducibilityError("scripts/uv.pin is unreadable") from None
    versions = [line.removeprefix("version=") for line in lines if line.startswith("version=")]
    if len(versions) != 1:
        raise ReproducibilityError("scripts/uv.pin does not pin exactly one uv version")
    return versions[0]


# ----- command line -----


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pmv.reproducibility", description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("fingerprint", help="print the environment fingerprint")
    show.add_argument(
        "--document", action="store_true", help="print the canonical environment document"
    )
    commands.add_parser("verify", help="verify conformance to the approved project")
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if arguments.command == "verify":
            result = verify(arguments.repo)
            sys.stdout.write(f"environment verified: fingerprint {result.sha256}\n")
            return 0
        result = capture()
    except ReproducibilityError as exc:
        sys.stderr.write(f"ReproducibilityError: {exc}\n")
        return 1
    sys.stdout.write(result.document.decode("ascii") if arguments.document else result.sha256)
    if not arguments.document:
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
