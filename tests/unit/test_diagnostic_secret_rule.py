"""Static guard for the permanent PMV diagnostic rule (B10 runtime-secret hardening, 2026-10-19).

Repository code and runbooks must never print, log, or serialize proxy variables, proxy
credentials, or runtime sandbox tokens. Ordinary diagnostics must not use commands that dump
the whole environment or the full request/response exchange (``docs/conventions.md``,
"Diagnostics and Runtime Secrets"). This test scans Git-tracked code, automation, and
configuration files, plus fenced shell and Python blocks in Markdown, for those forms.

It is a backstop for review, not a proof: it cannot see every indirect form, for example a
command assembled from fragments at runtime. It reads only repository files and makes no
network call. It reports file, line, and rule name, never the matched text. Exemptions are
exact (file, rule, line) triples, each justified below.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
THIS_FILE = "tests/unit/test_diagnostic_secret_rule.py"
SHELL_SUFFIXES = {".sh", ".bash", ".yml", ".yaml"}
CONFIG_SUFFIXES = {".toml", ".ini", ".cfg"}
SHELL_FENCES = {"bash", "sh", "shell", "console", "zsh", "yaml", "yml"}
PYTHON_FENCES = {"python", "py", "python3"}

# Names whose values must never be output. GIT_SSH_COMMAND and CLOUDSDK_PROXY_* carried the
# second B10 leak (review RT3-B10-07).
_GUARDED_NAME = r"(?:HTTPS?_PROXY|ALL_PROXY|Proxy-Authorization|GIT_SSH_COMMAND|CLOUDSDK_PROXY_\w*)"
# Stop at a shell separator so that a later pipeline stage is not attributed to the command.
_SAME_COMMAND = r"[^\n|;&)]*"
_ENV_DUMP_ARG = r"(?:dict\(\s*)?os\.environ(?:\.copy\(\))?\s*\)?"

# Rules for every scanned file and block.
RULES: dict[str, re.Pattern[str]] = {
    "printenv": re.compile(r"\bprintenv\b"),
    "export-p": re.compile(r"\bexport\s+-p\b"),
    "declare-p-or-x": re.compile(r"\b(?:declare|typeset)\s+-[A-Za-z]*[px]"),
    "compgen-v": re.compile(r"\bcompgen\s+-[A-Za-z]*v"),
    "curl-verbose-or-trace": re.compile(
        r"\bcurl\b" + _SAME_COMMAND + r"\s(?:--verbose|--trace(?:-ascii)?|-[A-Za-z]*v[A-Za-z]*)"
        r"(?=\s|$|['\"])"
    ),
    "wget-debug": re.compile(r"\bwget\b" + _SAME_COMMAND + r"\s(?:--debug|-d)(?=\s|$|['\"])"),
    "pytest-locals": re.compile(
        r"showlocals|\bpytest\b" + _SAME_COMMAND + r"\s-l(?=\s|$|['\"])", re.IGNORECASE
    ),
    "proc-environ": re.compile(r"/proc/[^\s'\"]*environ"),
    # Owner decision DR-10 (2026-10-19): PMV code never builds a proxy authorization header.
    "proxy-auth-construction": re.compile(
        r"Proxy-Authorization\s*:\s*(?:Basic|Bearer|Digest|Negotiate)\b", re.IGNORECASE
    ),
}
# Python output of the environment or of secret-bearing names.
PYTHON_RULES: dict[str, re.Pattern[str]] = {
    "python-environ-dump": re.compile(
        r"\b(?:print|pprint|json\.dumps?|repr|str|write)\(\s*" + _ENV_DUMP_ARG
    ),
    "python-environ-log": re.compile(
        r"\b(?:log\w*|logger)\.\w+\([^\n]*\bos\.environ\b(?!\s*(?:\.get\b|\[))"
    ),
    "python-environ-fstring": re.compile(r"\{\s*" + _ENV_DUMP_ARG + r"\s*[}!:]"),
    "python-output-secret-name": re.compile(
        r"\b(?:print|pprint|log\w*\.\w+|logger\.\w+|\w+\.write)\([^\n]*" + _GUARDED_NAME,
        re.IGNORECASE,
    ),
    "python-subprocess-env": re.compile(r"\(\s*\[?\s*[\"'](?:env|printenv|set|export)[\"']"),
    # Owner decision DR-16 (2026-10-19): never read or parse the runtime proxy variables, not
    # even for a host or port. Writing them in a test (monkeypatch.setenv) is not a read.
    "python-proxy-var-read": re.compile(
        r"(?:environ(?:\.get|\.pop|\.setdefault)?\s*[\[(]|getenv\s*\()\s*[\"']"
        r"(?:HTTPS?|ALL)_PROXY[\"']",
        re.IGNORECASE,
    ),
    "python-proxy-discovery": re.compile(
        r"\b(?:getproxies(?:_environment)?|proxy_bypass_environment)\s*\("
    ),
    # DR-16: urllib's default opener and ProxyHandler read the runtime proxy variables
    # in-process (getproxies, proxy_bypass) and build a proxy authorization header from them.
    "python-urllib-env-proxy": re.compile(
        r"\b(?:urlopen|urlretrieve|build_opener|install_opener|ProxyHandler)\s*\("
    ),
}
# Shell and workflow forms, where these are command invocations.
_CMD_START = r"(?:^|[;&|(`:]|\$\()\s*"
_CMD_END = r"\s*(?:$|[|>;&)`])"
SHELL_RULES: dict[str, re.Pattern[str]] = {
    "env-dump": re.compile(_CMD_START + r"env(?:\s+(?:-0|--null))?" + _CMD_END, re.MULTILINE),
    "set-dump": re.compile(_CMD_START + r"set" + _CMD_END, re.MULTILINE),
    "export-dump": re.compile(_CMD_START + r"export" + _CMD_END, re.MULTILINE),
    "ps-environment": re.compile(r"\bps\s+[A-Za-z]*e[A-Za-z]*\b"),
    # Owner decision DR-16: no expansion of the runtime proxy variables in any command.
    "shell-proxy-var-expansion": re.compile(r"\$\{?(?:HTTPS?|ALL)_PROXY\b", re.IGNORECASE),
    "echo-secret-name": re.compile(
        r"\b(?:echo|printf)\b" + _SAME_COMMAND + r"\$\{?" + _GUARDED_NAME, re.IGNORECASE
    ),
}

# Justified exemptions: (path, rule, stripped line).
EXEMPTIONS = {
    # The egress refusal test names the local-variable traceback option only to refuse it.
    (
        "tests/integration/test_live_host_egress_refusal.py",
        "pytest-locals",
        "(``-l``/``--showlocals``) enabled.",
    ),
    (
        "tests/integration/test_live_host_egress_refusal.py",
        "pytest-locals",
        'if os.environ.get("PMV_EGRESS_PROBE") == "1" and request.config.getoption("showlocals"):',
    ),
}

_FENCE = re.compile(r"^(\s*)(```|~~~)\s*([A-Za-z0-9_+-]*)[^\n]*$")


def _tracked_files() -> list[str]:
    result = subprocess.run(  # noqa: S603 - fixed test git invocation
        ["/usr/bin/git", "-C", str(REPO), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return sorted(p for p in result.stdout.decode().split("\0") if p)


def _kind(rel: str) -> str | None:
    path = Path(rel)
    if path.suffix == ".md":
        return "markdown"
    if path.suffix == ".py":
        return "python"
    if path.suffix in SHELL_SUFFIXES or (path.parts[0] == "scripts" and path.suffix == ""):
        return "shell"
    if path.suffix in CONFIG_SUFFIXES:
        return "config"
    return None


def _rules_for(kind: str) -> dict[str, re.Pattern[str]]:
    rules = dict(RULES)
    if kind == "python":
        rules.update(PYTHON_RULES)
    elif kind == "shell":
        rules.update(SHELL_RULES)
    return rules


def _markdown_blocks(text: str) -> list[tuple[int, str, str]]:
    """Return (first line number, kind, body) for fenced shell and Python blocks."""
    blocks = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        opening = _FENCE.match(lines[i])
        if not opening:
            i += 1
            continue
        marker, language = opening.group(2), opening.group(3).lower()
        start = i + 1
        i = start
        while i < len(lines) and not lines[i].lstrip().startswith(marker):
            i += 1
        kind = "shell" if language in SHELL_FENCES else ""
        kind = "python" if language in PYTHON_FENCES else kind
        if kind:
            body = "\n".join(line.strip() for line in lines[start:i])
            blocks.append((start + 1, kind, body))
        i += 1
    return blocks


def _scan(rel: str, kind: str, text: str, first_line: int = 1) -> list[str]:
    found = []
    lines = text.split("\n")
    if kind == "shell":
        # Blank shell and YAML comment lines (line numbers are kept), so prose is not scanned.
        text = "\n".join("" if line.lstrip().startswith("#") else line for line in lines)
    for name, pattern in _rules_for(kind).items():
        for match in pattern.finditer(text):
            index = text.count("\n", 0, match.start())
            if (rel, name, lines[index].strip()) in EXEMPTIONS:
                continue
            found.append(f"{rel}:{first_line + index}: {name}")
    return found


def _violations(rel: str, text: str) -> list[str]:
    kind = _kind(rel)
    if kind is None:
        return []
    if kind != "markdown":
        return _scan(rel, kind, text)
    found = []
    for first_line, block_kind, body in _markdown_blocks(text):
        found.extend(_scan(rel, block_kind, body, first_line))
    return found


def test_scan_covers_code_config_and_runbooks() -> None:
    files = _tracked_files()
    kinds = {_kind(rel) for rel in files}
    assert {"python", "shell", "config", "markdown"} <= kinds
    assert "scripts/check.sh" in files
    assert "pyproject.toml" in files


SHELL_HITS = [
    "printenv",
    "env | grep x",
    "env -0",
    "x=$(env)",
    "  run: env",
    "set > out",
    "export",
    "export -p",
    "declare -p",
    "declare -x",
    "typeset -p",
    "compgen -v",
    "ps eww 1",
    "curl -sv https://example.com",
    "curl --verbose https://example.com",
    "curl --trace-ascii t https://example.com",
    'curl -H "Proxy-Authorization: Basic $TOKEN" https://example.com',
    'curl -x "$HTTPS_PROXY" https://example.com',
    "p=${https_proxy#*@}",
    "wget --debug https://example.com",
    "pytest --showlocals",
    "uv run pytest -q -l",
    "cat /proc/self/environ",
    'echo "$HTTPS_PROXY"',
    "printf %s ${ALL_PROXY}",
    "echo $GIT_SSH_COMMAND",
    "echo $CLOUDSDK_PROXY_PASSWORD",
    "echo $https_proxy",
]
PYTHON_HITS = [
    "print(os.environ)",
    "print(dict(os.environ))",
    "print(os.environ.copy())",
    "json.dumps(os.environ)",
    "sys.stdout.write(str(os.environ))",
    "log.info('x', os.environ)",
    "logger.debug(os.environ)",
    "msg = f'{os.environ}'",
    "print(os.environ['HTTPS_PROXY'])",
    "logger.info(os.environ.get('GIT_SSH_COMMAND'))",
    "sys.stderr.write(headers['proxy-authorization'])",
    "subprocess.run(['env'])",
    "subprocess.run('env', shell=True)",
    "open('/proc/self/environ')",
    "addopts = '--showlocals'",
    'headers += f"Proxy-Authorization: Basic {token}"',
    'proxy = os.environ.get("HTTPS_PROXY")',
    "proxy = os.environ['http_proxy']",
    'host = urllib.parse.urlsplit(os.getenv("ALL_PROXY")).hostname',
    "proxies = urllib.request.getproxies()",
    "with urllib.request.urlopen(request, timeout=30) as response:",
    "opener = urllib.request.build_opener()",
    "handler = urllib.request.ProxyHandler()",
    "auth = 'proxy-authorization: basic ' + token",
]
SHELL_ALLOWED = [
    "set -euo pipefail",
    "#!/usr/bin/env bash",
    "curl -s -o /dev/null -w '%{http_code}' https://example.com",
    "curl -s https://example.com | grep -v foo",
    "uv run --locked pytest",
    "uv run --locked pytest | tail -l",
    "export UV_CACHE_DIR",
    "ps aux",
    "# make_canary <label>: set `canary` to a value",
    'export PMV_EGRESS_PROXY_HOST="pmv-egress-proxy"',
]
PYTHON_ALLOWED = [
    'os.environ.get("PMV_ENV")',
    "load_secrets(specs, os.environ)",
    'log.info("event", extra=fields(mode=os.environ.get("PMV_ENV")))',
    'print("done")',
    'config = {"env": "dev"}',
    'subprocess.run(["git", "status"])',
    """cases = [('export NAME="FAKE VALUE"', "FAKE VALUE")]""",
    'monkeypatch.setenv("HTTPS_PROXY", dummy)',
    'host = os.environ.get("PMV_EGRESS_PROXY_HOST", "")',
    "conn = http.client.HTTPSConnection(proxy_host, proxy_port, timeout=30)",
    "conn.set_tunnel(HOST, 443)",
]


def test_rules_detect_forbidden_diagnostics() -> None:
    for sample in SHELL_HITS:
        assert _violations("scripts/example.sh", sample), sample
    for sample in PYTHON_HITS:
        assert _violations("src/example.py", sample), sample
    assert _violations("pyproject.toml", 'addopts = "--showlocals"')
    runbook = "Text.\n\n```bash\nprintenv\n```\n\n```python\nprint(os.environ)\n```\n"
    assert _violations("docs/example.md", runbook) == [
        "docs/example.md:4: printenv",
        "docs/example.md:8: python-environ-dump",
    ]


def test_rules_allow_ordinary_forms() -> None:
    for sample in SHELL_ALLOWED:
        assert not _violations("scripts/example.sh", sample), sample
    for sample in PYTHON_ALLOWED:
        assert not _violations("src/example.py", sample), sample
    prose = "Never use env or printenv.\n\n```text\nprintenv\n```\n"
    assert not _violations("docs/example.md", prose)


def test_exemptions_are_exact_lines() -> None:
    rel = "tests/integration/test_live_host_egress_refusal.py"
    assert not _violations(rel, "(``-l``/``--showlocals``) enabled.")
    assert _violations(rel, 'pytest.main(["--showlocals"])')


def test_repository_has_no_forbidden_diagnostics() -> None:
    found = []
    for rel in _tracked_files():
        if rel == THIS_FILE or _kind(rel) is None:
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        found.extend(_violations(rel, path.read_text(encoding="utf-8", errors="replace")))
    assert not found, "forbidden diagnostic forms:\n" + "\n".join(found)
