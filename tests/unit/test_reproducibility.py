"""Tests for the installed-environment fingerprint and conformance checks (Step 10)."""

import base64
import hashlib
import io
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from pmv import reproducibility
from pmv.integrity import canonical_line, sha256_hex
from pmv.reproducibility import (
    PROJECT_NAME,
    ReproducibilityError,
    build_document,
    check_project_install,
    check_python_version,
    check_virtual_environment,
    parse_document,
    satisfies,
    validate_document,
)

REPO = Path(__file__).resolve().parents[2]
INTERPRETER: dict[str, object] = {
    "byteorder": "little",
    "cache_tag": "cpython-313",
    "flags": {"dev_mode": False, "hash_randomization": 1, "optimize": 0, "utf8_mode": 0},
    "gil_disabled": False,
    "implementation": "cpython",
    "platform": "linux-x86_64",
    "soabi": "cpython-313-x86_64-linux-gnu",
    "version": "3.13.5",
}


def record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class Site:
    """A synthetic venv: <root>/lib/python3.13/site-packages plus <root>/bin."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "lib" / "python3.13" / "site-packages"
        self.path.mkdir(parents=True)
        (root / "bin").mkdir()

    def dist(
        self,
        name: str,
        version: str,
        files: Mapping[str, bytes],
        *,
        launchers: Sequence[str] = (),
        dist_name: str | None = None,
        extra_rows: Sequence[str] = (),
    ) -> Path:
        info = self.path / f"{(dist_name or name).replace('-', '_')}-{version}.dist-info"
        info.mkdir()
        everything: dict[str, bytes] = dict(files)
        everything[f"{info.name}/METADATA"] = (
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
        )
        if launchers:
            text = "[console_scripts]\n" + "".join(f"{item} = pkg:main\n" for item in launchers)
            everything[f"{info.name}/entry_points.txt"] = text.encode()
        rows = []
        for path, data in everything.items():
            target = self.path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            rows.append(f"{path},{record_hash(data)},{len(data)}")
        rows.append(f"{info.name}/RECORD,,")
        rows.extend(extra_rows)
        (info / "RECORD").write_text("\n".join(rows) + "\n", encoding="utf-8")
        return info

    def project(self, pth: bytes = b"/somewhere/src") -> Path:
        return self.dist(
            PROJECT_NAME,
            "0.0.0",
            {"_editable_impl_prediction_market_velocity.pth": pth},
            dist_name="prediction_market_velocity",
        )

    def standard(self) -> "Site":
        self.project()
        self.dist("numpy", "2.0.0", {"numpy/__init__.py": b"x = 1\n", "numpy/core.so": b"\x7fELF"})
        self.dist(
            "pytest",
            "9.1.1",
            {"pytest/__init__.py": b"", "../../../bin/pytest": b"#!/venv-a/bin/python\n"},
            launchers=("pytest",),
        )
        return self

    def document(self, **changes: Any) -> dict[str, object]:
        options: dict[str, Any] = {
            "interpreter": INTERPRETER,
            "environ": {"HOME": "/home/someone"},
            "user_site_enabled": False,
        }
        options.update(changes)
        return build_document(self.path, **options)

    def fingerprint(self, **changes: Any) -> str:
        return sha256_hex(canonical_line(self.document(**changes)))


@pytest.fixture
def site(tmp_path: Path) -> Site:
    return Site(tmp_path / "venv-a").standard()


def rewrite(site: Site, path: str, data: bytes) -> None:
    """Change an installed file and update its RECORD row, as an installer would."""
    (site.path / path).write_bytes(data)
    for record in site.path.glob("*.dist-info/RECORD"):
        rows = record.read_text(encoding="utf-8").splitlines()
        updated = [
            f"{path},{record_hash(data)},{len(data)}" if row.startswith(path + ",") else row
            for row in rows
        ]
        record.write_text("\n".join(updated) + "\n", encoding="utf-8")


# ----- stability -----


def test_the_same_environment_gives_the_same_fingerprint(site: Site) -> None:
    first = site.document()
    assert site.document() == first
    validate_document(first)
    distributions = first["distributions"]
    assert isinstance(distributions, list)
    assert [item["name"] for item in distributions] == ["numpy", "pytest"]
    assert first["project"] == {"editable": True, "name": PROJECT_NAME, "version": "0.0.0"}


def test_location_creation_order_home_and_timestamps_do_not_matter(
    site: Site, tmp_path: Path
) -> None:
    other = Site(tmp_path / "elsewhere" / "venv-b")
    other.dist(
        "pytest",
        "9.1.1",
        {"pytest/__init__.py": b"", "../../../bin/pytest": b"#!/elsewhere/venv-b/bin/python\n"},
        launchers=("pytest",),
    )
    other.dist("numpy", "2.0.0", {"numpy/__init__.py": b"x = 1\n", "numpy/core.so": b"\x7fELF"})
    other.project(b"/a/different/checkout/src")
    for path in other.path.rglob("*"):
        os.utime(path, (1, 1))
    assert other.fingerprint(environ={"HOME": "/root", "USER": "x"}) == site.fingerprint()


def test_a_regenerated_launcher_shebang_does_not_matter_but_a_shipped_binary_does(
    site: Site,
) -> None:
    before = site.fingerprint()
    rewrite(site, "../../../bin/pytest", b"#!/moved/venv/bin/python\n")
    assert site.fingerprint() == before
    site.dist("ruff", "0.17.0", {"../../../bin/ruff": b"binary-v1"})
    with_ruff = site.fingerprint()
    rewrite(site, "../../../bin/ruff", b"binary-v2")
    assert site.fingerprint() != with_ruff


def test_bytecode_caches_are_ignored(site: Site) -> None:
    before = site.fingerprint()
    cache = site.path / "numpy" / "__pycache__"
    cache.mkdir()
    (cache / "core.cpython-313.pyc").write_bytes(b"\x00compiled")
    assert site.fingerprint() == before


# ----- sensitivity -----


def test_package_bytes_and_versions_change_the_fingerprint(site: Site, tmp_path: Path) -> None:
    before = site.fingerprint()
    rewrite(site, "numpy/core.so", b"\x7fELF-patched")
    assert site.fingerprint() != before
    newer = Site(tmp_path / "venv-c")
    newer.project()
    newer.dist("numpy", "2.0.1", {"numpy/__init__.py": b"x = 1\n", "numpy/core.so": b"\x7fELF"})
    newer.dist(
        "pytest",
        "9.1.1",
        {"pytest/__init__.py": b"", "../../../bin/pytest": b"#!/x\n"},
        launchers=("pytest",),
    )
    reference = Site(tmp_path / "venv-d").standard()
    assert newer.fingerprint() != reference.fingerprint()


@pytest.mark.parametrize(
    "change",
    [
        {"version": "3.13.6"},
        {"soabi": "cpython-313t-x86_64-linux-gnu"},
        {"platform": "linux-aarch64"},
        {"cache_tag": "cpython-314"},
        {"gil_disabled": True},
        {"byteorder": "big"},
        {"flags": {"dev_mode": False, "hash_randomization": 1, "optimize": 2, "utf8_mode": 0}},
        {"flags": {"dev_mode": True, "hash_randomization": 1, "optimize": 0, "utf8_mode": 0}},
    ],
)
def test_interpreter_identity_changes_the_fingerprint(
    site: Site, change: dict[str, object]
) -> None:
    assert site.fingerprint(interpreter={**INTERPRETER, **change}) != site.fingerprint()


# ----- fail closed -----


def test_duplicate_normalized_names_fail_closed(site: Site) -> None:
    site.dist("NumPy", "1.0.0", {"numpy_old/__init__.py": b""}, dist_name="NumPy")
    with pytest.raises(ReproducibilityError, match="share a normalized name"):
        site.document()


@pytest.mark.parametrize(
    "row",
    [
        "numpy/a.py,sha256=abc",
        "numpy/a.py,md5=AAAAAAAAAAAAAAAAAAAAAA,3",
        "/etc/passwd,,",
        "numpy/../../x.py,,",
        "numpy/__init__.py,,",
    ],
)
def test_malformed_record_rows_fail_closed(tmp_path: Path, row: str) -> None:
    site = Site(tmp_path / "venv")
    site.project()
    site.dist("numpy", "2.0.0", {"numpy/__init__.py": b"x"}, extra_rows=(row,))
    with pytest.raises(ReproducibilityError, match="RECORD"):
        site.document()


def test_a_missing_record_fails_closed(site: Site) -> None:
    next(site.path.glob("numpy-*.dist-info/RECORD")).unlink()
    with pytest.raises(ReproducibilityError, match="no RECORD"):
        site.document()


def test_tampered_or_missing_files_fail_closed(site: Site) -> None:
    (site.path / "numpy" / "core.so").write_bytes(b"tampered")
    with pytest.raises(ReproducibilityError, match="does not match its RECORD hash"):
        site.document()
    (site.path / "numpy" / "core.so").unlink()
    with pytest.raises(ReproducibilityError, match="missing or unreadable"):
        site.document()


@pytest.mark.parametrize(
    "path",
    ["evil.py", "zz_inject.pth", "numpy/backdoor.py", "unowned_dir/module.py"],
)
def test_files_no_distribution_owns_fail_closed(site: Site, path: str) -> None:
    target = site.path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"import os\n")
    with pytest.raises(ReproducibilityError, match="no distribution owns"):
        site.document()


@pytest.mark.parametrize("pth", [b"import os; os.system('x')\n", b"/a\n/b\n", b"/a;import os\n"])
def test_the_project_pth_may_only_add_one_path(tmp_path: Path, pth: bytes) -> None:
    site = Site(tmp_path / "venv")
    site.project(pth)
    with pytest.raises(ReproducibilityError, match="exactly one path"):
        site.document()


def test_the_project_must_be_installed(tmp_path: Path) -> None:
    site = Site(tmp_path / "venv")
    site.dist("numpy", "2.0.0", {"numpy/__init__.py": b""})
    with pytest.raises(ReproducibilityError, match="not installed"):
        site.document()


def test_python_path_injection_and_user_site_fail_closed(site: Site) -> None:
    with pytest.raises(ReproducibilityError, match="PYTHONPATH"):
        site.document(environ={"PYTHONPATH": "/opt/injected"})
    assert site.document(environ={"PYTHONPATH": ""}) == site.document()
    with pytest.raises(ReproducibilityError, match="user site-packages"):
        site.document(user_site_enabled=True)


# ----- leak hygiene -----


def test_no_environment_values_paths_or_secrets_appear(site: Site) -> None:
    sentinel = "PMV-SYNTHETIC-SECRET-VALUE-NOT-REAL"
    data = canonical_line(
        site.document(environ={"HOME": "/home/sentinel-user", "API_TOKEN": sentinel})
    )
    for forbidden in (sentinel, "sentinel-user", str(site.root), "venv-a", "somewhere"):
        assert forbidden.encode() not in data


def test_the_real_document_has_no_home_or_venv_paths() -> None:
    data = reproducibility.capture().document
    for forbidden in (str(Path.home()), str(REPO), os.environ.get("USER", "\0")):
        assert forbidden.encode() not in data


# ----- the closed document schema -----


def test_documents_round_trip_and_reject_tampering(site: Site) -> None:
    data = canonical_line(site.document())
    assert parse_document(data) == site.document()
    with pytest.raises(ReproducibilityError):
        parse_document(data[:-1])
    with pytest.raises(ReproducibilityError):
        parse_document(data.replace(b'"schema_version":1', b'"schema_version":2'))
    with pytest.raises(ReproducibilityError):
        parse_document(data.replace(b'{"distributions"', b'{"extra":1,"distributions"'))
    unsorted = dict(site.document())
    unsorted["distributions"] = list(reversed(unsorted["distributions"]))  # type: ignore[call-overload]
    with pytest.raises(ReproducibilityError, match="sorted"):
        validate_document(unsorted)


# ----- conformance -----


@pytest.mark.parametrize(
    ("version", "specifier", "expected"),
    [
        ("3.13.5", ">=3.13,<3.14", True),
        ("3.12.9", ">=3.13,<3.14", False),
        ("3.14.0", ">=3.13,<3.14", False),
        ("3.13.5", "==3.13.*", True),
        ("3.14.1", "==3.13.*", False),
        ("3.13.5", "~=3.13", False),
        ("3.13.5", ">=3.13.5", True),
        ("3.13.5rc1", ">=3.13", False),
    ],
)
def test_python_specifiers(version: str, specifier: str, expected: bool) -> None:
    assert satisfies(version, specifier) is expected


def test_incompatible_python_versions_fail(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.13,<3.14"\n', encoding="ascii"
    )
    (tmp_path / ".python-version").write_text("3.13\n", encoding="ascii")
    check_python_version("3.13.5", tmp_path)
    with pytest.raises(ReproducibilityError, match="requires-python"):
        check_python_version("3.12.9", tmp_path)
    (tmp_path / ".python-version").write_text("3.13.4\n", encoding="ascii")
    with pytest.raises(ReproducibilityError, match=r"\.python-version"):
        check_python_version("3.13.5", tmp_path)
    (tmp_path / "pyproject.toml").unlink()
    with pytest.raises(ReproducibilityError, match="unreadable"):
        check_python_version("3.13.5", tmp_path)


def test_the_project_install_and_venv_must_be_this_repository(tmp_path: Path) -> None:
    check_project_install(REPO)
    check_virtual_environment(REPO)
    with pytest.raises(ReproducibilityError, match="not imported from this repository"):
        check_project_install(tmp_path)
    with pytest.raises(ReproducibilityError, match="not imported from this repository"):
        check_project_install(REPO, module_file=str(tmp_path / "pmv" / "__init__.py"))
    with pytest.raises(ReproducibilityError, match=r"project \.venv"):
        check_virtual_environment(tmp_path)


@pytest.mark.parametrize(
    ("failing", "message"),
    [
        (("lock", "--check"), "uv.lock is not consistent"),
        (("sync", "--locked", "--check"), "does not match uv.lock exactly"),
    ],
)
def test_a_stale_lock_or_a_mismatched_environment_fails(
    failing: tuple[str, ...], message: str
) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(_root: Path, arguments: Sequence[str]) -> int:
        calls.append(tuple(arguments))
        return 1 if tuple(arguments) == failing else 0

    with pytest.raises(ReproducibilityError, match=message):
        reproducibility.verify(REPO, runner=runner)
    assert calls[-1] == failing


def test_a_stale_lock_is_detected_by_the_real_pinned_uv(tmp_path: Path) -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH")
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    shutil.copy2(REPO / "scripts" / "uv.pin", project / "scripts" / "uv.pin")
    (project / "pyproject.toml").write_text(
        '[project]\nname = "synthetic"\nversion = "0.0.0"\nrequires-python = ">=3.13"\n'
        "dependencies = []\n",
        encoding="ascii",
    )
    assert reproducibility._run_uv(project, ("lock",)) == 0
    assert reproducibility._run_uv(project, ("lock", "--check")) == 0
    (project / "pyproject.toml").write_text(
        '[project]\nname = "synthetic"\nversion = "0.0.1"\nrequires-python = ">=3.12"\n'
        "dependencies = []\n",
        encoding="ascii",
    )
    assert reproducibility._run_uv(project, ("lock", "--check")) != 0


# ----- the real environment -----


def test_the_real_environment_is_deterministic_and_conforms() -> None:
    first = reproducibility.capture()
    assert reproducibility.capture() == first
    assert reproducibility.fingerprint() == first.sha256
    parse_document(first.document)
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH")
    assert reproducibility.verify(REPO) == first


def test_the_command_line_prints_only_bounded_output(monkeypatch: pytest.MonkeyPatch) -> None:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        assert reproducibility.main(["fingerprint"]) == 0
    assert out.getvalue() == reproducibility.fingerprint() + "\n"
    monkeypatch.setenv("PYTHONPATH", "/opt/PMV-SENTINEL-PATH")
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        assert reproducibility.main(["fingerprint", "--document"]) == 1
    assert err.getvalue() == (
        "ReproducibilityError: PYTHONPATH is set; code outside the environment could run\n"
    )
    assert out.getvalue() == ""


def test_the_schema_document_matches_the_validator(site: Site) -> None:
    schema = json.loads((REPO / "schemas" / "environment_v1.json").read_text(encoding="utf-8"))
    document = site.document()
    assert set(schema["required"]) == set(document) == set(schema["properties"])
    interpreter = schema["properties"]["interpreter"]
    assert set(interpreter["required"]) == set(INTERPRETER) == set(interpreter["properties"])
    flags = INTERPRETER["flags"]
    assert isinstance(flags, dict)
    assert set(interpreter["properties"]["flags"]["required"]) == set(flags)
    item = schema["properties"]["distributions"]["items"]
    distributions, project = document["distributions"], document["project"]
    assert isinstance(distributions, list)
    assert isinstance(project, dict)
    assert set(item["required"]) == set(distributions[0])
    assert set(schema["properties"]["project"]["required"]) == set(project)


# ----- Step 10 Red-Team corrections -----


def test_a_hashless_record_row_cannot_launder_code(site: Site) -> None:
    site.dist("pluginhost", "1.0.0", {"pluginhost/__init__.py": b""}, extra_rows=("zz_evil.pth,,",))
    (site.path / "zz_evil.pth").write_bytes(b"import os\n")
    with pytest.raises(ReproducibilityError, match="has no hash"):
        site.document()


@pytest.mark.parametrize(
    ("files", "launchers"),
    [
        ({"zz_evil_plugin.py": b"import os\n"}, ()),
        ({}, ("evil",)),
    ],
)
def test_the_project_may_own_only_its_pth_and_known_dist_info(
    tmp_path: Path, files: dict[str, bytes], launchers: tuple[str, ...]
) -> None:
    site = Site(tmp_path / "venv")
    site.dist(
        PROJECT_NAME,
        "0.0.0",
        {"_editable_impl_prediction_market_velocity.pth": b"/somewhere/src", **files},
        dist_name="prediction_market_velocity",
        launchers=launchers,
    )
    with pytest.raises(ReproducibilityError, match="unexpected file"):
        site.document()


def test_the_project_dist_info_files_are_integrity_checked(site: Site) -> None:
    metadata_file = next(site.path.glob("prediction_market_velocity-*.dist-info/METADATA"))
    metadata_file.write_bytes(metadata_file.read_bytes() + b"Extra: 1\n")
    with pytest.raises(ReproducibilityError, match="does not match its RECORD hash"):
        site.document()


@pytest.mark.parametrize("where", ["evilpkg", "numpy/hidden"])
def test_unowned_symlinked_directories_fail_closed(site: Site, tmp_path: Path, where: str) -> None:
    outside = tmp_path / "outside" / "evilpkg"
    outside.mkdir(parents=True)
    (outside / "__init__.py").write_bytes(b"import os\n")
    (site.path / where).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ReproducibilityError, match="symlink"):
        site.document()


def test_unreadable_metadata_fails_with_fixed_text_only(site: Site) -> None:
    record = next(site.path.glob("numpy-*.dist-info/RECORD"))
    record.write_bytes(record.read_bytes() + b"numpy/\xff.py,,\n")
    with pytest.raises(ReproducibilityError) as raised:
        site.document()
    assert str(raised.value) == "the installed environment could not be read"
    assert str(site.root) not in str(raised.value)


def test_sourceless_bytecode_listed_in_record_is_hashed(site: Site) -> None:
    site.dist("compiled", "1.0.0", {"compiled/mod.pyc": b"\x00code-v1"})
    before = site.fingerprint()
    rewrite(site, "compiled/mod.pyc", b"\x00code-v2")
    assert site.fingerprint() != before


def test_a_package_file_named_like_a_launcher_is_still_hashed(site: Site) -> None:
    site.dist("tool", "1.0.0", {"tool/pytest": b"v1"}, launchers=("pytest",))
    before = site.fingerprint()
    rewrite(site, "tool/pytest", b"v2")
    assert site.fingerprint() != before


def test_negative_interpreter_flags_are_rejected(site: Site) -> None:
    document = site.document()
    interpreter = dict(INTERPRETER)
    interpreter["flags"] = {
        "dev_mode": False,
        "hash_randomization": 1,
        "optimize": -1,
        "utf8_mode": 0,
    }
    with pytest.raises(ReproducibilityError, match="flags"):
        validate_document({**document, "interpreter": interpreter})


def test_the_virtual_environment_must_exclude_system_site_packages(tmp_path: Path) -> None:
    venv = tmp_path / ".venv"
    venv.mkdir()
    base = str(tmp_path / "base")
    config = venv / "pyvenv.cfg"
    config.write_text("home = /usr/bin\ninclude-system-site-packages = false\n", encoding="utf-8")
    check_virtual_environment(tmp_path, prefix_path=str(venv), base_prefix_path=base)
    for text in ("include-system-site-packages = true\n", "home = /usr/bin\n"):
        config.write_text(text, encoding="utf-8")
        with pytest.raises(ReproducibilityError, match="system site-packages"):
            check_virtual_environment(tmp_path, prefix_path=str(venv), base_prefix_path=base)
    with pytest.raises(ReproducibilityError, match="not running in a virtual environment"):
        check_virtual_environment(tmp_path, prefix_path=str(venv), base_prefix_path=str(venv))


def test_the_editable_install_record_must_point_at_this_repository(tmp_path: Path) -> None:
    good_url = json.dumps({"dir_info": {"editable": True}, "url": REPO.as_uri()})
    src = str(REPO / "src")
    module = str(REPO / "src" / "pmv" / "__init__.py")
    check_project_install(REPO, module_file=module, direct_url=good_url, pth_text=src)
    for url, pth in (
        (json.dumps({"dir_info": {"editable": True}, "url": tmp_path.as_uri()}), src),
        (json.dumps({"dir_info": {}, "url": REPO.as_uri()}), src),
        (good_url, str(tmp_path / "src")),
        (good_url, f"{src}\n{tmp_path}"),
    ):
        with pytest.raises(ReproducibilityError, match="editable"):
            check_project_install(REPO, module_file=module, direct_url=url, pth_text=pth)


def fake_uv(tmp_path: Path, version: str) -> Path:
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    log = tmp_path / "uv-env.txt"
    script = bin_dir / "uv"
    script.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "uv {version}"; exit 0; fi\n'
        f'env > "{log}"\n'
        "exit 0\n",
        encoding="ascii",
    )
    script.chmod(0o755)
    return bin_dir


def test_uv_must_match_the_pinned_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(fake_uv(tmp_path, "9.9.9")) + ":/usr/bin:/bin")
    with pytest.raises(ReproducibilityError, match="pinned"):
        reproducibility._run_uv(REPO, ("lock", "--check"))


def test_uv_runs_with_a_minimal_isolated_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pinned = (
        (REPO / "scripts" / "uv.pin").read_text(encoding="ascii").split("version=")[1].split()[0]
    )
    monkeypatch.setenv("PATH", str(fake_uv(tmp_path, pinned)) + ":/usr/bin:/bin")
    monkeypatch.setenv("PMV_SYNTHETIC_SECRET", "PMV-SENTINEL-NOT-REAL")
    assert reproducibility._run_uv(REPO, ("lock", "--check")) == 0
    seen = dict(
        line.split("=", 1)
        for line in (tmp_path / "uv-env.txt").read_text().splitlines()
        if "=" in line
    )
    assert "PMV_SYNTHETIC_SECRET" not in seen
    assert seen["UV_OFFLINE"] == "1"
    assert seen["XDG_CONFIG_HOME"] == seen["XDG_CONFIG_DIRS"]
    assert not os.path.exists(seen["XDG_CONFIG_HOME"])
    allowed = {"PATH", "HOME", "UV_CACHE_DIR", "LC_ALL", "UV_OFFLINE", "UV_NO_PROGRESS"}
    allowed |= {"XDG_CONFIG_HOME", "XDG_CONFIG_DIRS", "PWD", "SHLVL", "_", "OLDPWD"}
    assert set(seen) <= allowed


def test_the_store_seam_runs_verify_only_for_conformance(monkeypatch: pytest.MonkeyPatch) -> None:
    from pmv import experiments

    marker = reproducibility.EnvironmentCapture(b"x\n", "0" * 64)
    calls: list[str] = []

    def fake_verify(_root: Path) -> reproducibility.EnvironmentCapture:
        calls.append("verify")
        return marker

    def fake_capture() -> reproducibility.EnvironmentCapture:
        calls.append("capture")
        return marker

    monkeypatch.setattr(reproducibility, "verify", fake_verify)
    monkeypatch.setattr(reproducibility, "capture", fake_capture)
    assert experiments.capture_environment(REPO, verify_conformance=True) is marker
    assert experiments.capture_environment(REPO, verify_conformance=False) is marker
    assert calls == ["verify", "capture"]
