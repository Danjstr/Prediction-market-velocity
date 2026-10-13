#!/bin/bash -p
# Scan for committed or about-to-be-committed secrets with the pinned Betterleaks binary.
#
# A self-test runs first. Then four scans: full Git history, staged changes, unstaged
# changes to tracked files, and untracked files that Git does not ignore. Ignored files
# are never read. The scanner always runs with --redact, the repository config, an
# explicit validated ignore file, an empty environment, and no network; network
# validation is never enabled. Git runs with an empty environment too. Raw scanner output
# is never printed: only rule IDs, files, lines, commits, and fingerprints, none of which
# contain secret values.
#
# Exit status: 0 clean, 1 secret detected, 2 scanner malfunction (any other failure,
# including interruption).
set -Eeuo pipefail
umask 077
unset CDPATH
export PATH=/usr/bin:/bin
export LC_ALL=C

work=""
final_status=""

malfunction() {
    trap - ERR
    printf 'RESULT: SCANNER MALFUNCTION: %s\n' "$1" >&2
    exit 2
}

finish() {
    local status=$?
    trap - ERR EXIT INT TERM HUP
    [[ -z "$work" ]] || rm -rf -- "$work" || true
    case "$status:$final_status" in
        0:clean | 1:secret | 2:*) ;;
        *)
            printf 'RESULT: SCANNER MALFUNCTION: unexpected exit status %s\n' "$status" >&2
            status=2
            ;;
    esac
    exit "$status"
}

trap finish EXIT
trap 'malfunction "unexpected failure at line $LINENO"' ERR
trap 'malfunction "interrupted"' INT TERM HUP

[[ $# -eq 0 ]] || malfunction "scan_secrets.sh takes no arguments"

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || exit 2
pin_file="$repo_root/scripts/betterleaks.pin"
config_file="$repo_root/.betterleaks.toml"
ignore_name=".betterleaksignore"
leak_status=3
canary_rule="pmv-scanner-canary"
probe_rule="private-key"
# SHA-256 of the complete runtime-assembled probe text, so the self-test proves the
# probe is byte-for-byte the upstream fixture before relying on it.
probe_sha256="72c3c536557d98879c2c9bdfa39d31d2a49f92545cfd3f3f1a7cac9699f95b89"

pin_value() {
    local matches
    matches="$(grep -E "^$1=" "$pin_file")" \
        || malfunction "pin '$1' is missing from scripts/betterleaks.pin"
    [[ "$matches" != *$'\n'* ]] || malfunction "pin '$1' is duplicated in scripts/betterleaks.pin"
    printf '%s' "${matches#*=}"
}

# Preconditions. Every failure is a malfunction, never a pass.
version="$(pin_value version)" || exit 2
binary_sha256="$(pin_value binary_sha256)" || exit 2
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || malfunction "malformed version pin"
[[ "$binary_sha256" =~ ^[0-9a-f]{64}$ ]] \
    || malfunction "binary_sha256 is not pinned; review it and record it in scripts/betterleaks.pin"
[[ "${HOME:-}" == /* ]] || malfunction "HOME must be an absolute path"
binary="$HOME/.local/share/pmv-tools/betterleaks/$version/betterleaks"
[[ -f "$binary" && ! -L "$binary" ]] \
    || malfunction "Betterleaks $version is not installed; run scripts/install_betterleaks.sh"
actual_sha256="$(/usr/bin/env -i /usr/bin/sha256sum -- "$binary")" \
    || malfunction "cannot hash the installed binary"
[[ "${actual_sha256%% *}" == "$binary_sha256" ]] \
    || malfunction "the installed binary does not match the pinned SHA-256"
[[ -f "$config_file" && ! -L "$config_file" ]] || malfunction ".betterleaks.toml is missing"
for variable in BETTERLEAKS_CONFIG BETTERLEAKS_CONFIG_TOML GITLEAKS_CONFIG GITLEAKS_CONFIG_TOML; do
    [[ ! -v "$variable" ]] || malfunction "$variable is set; scanner config overrides are not allowed"
done
# Git runs with an empty environment, so personal global ignore rules are not applied.
# Refuse to run if any exist, rather than scan files that only they would ignore.
for global_git_file in "$HOME/.gitconfig" "$HOME/.config/git/config"; do
    if [[ -f "$global_git_file" ]] && grep -qi 'excludesfile' -- "$global_git_file"; then
        malfunction "personal global Git excludes are not honored here; move them into the repository .gitignore"
    fi
done
[[ ! -e "$HOME/.config/git/ignore" ]] \
    || malfunction "personal global Git excludes are not honored here; move them into the repository .gitignore"

work="$(/usr/bin/env -i /usr/bin/mktemp -d /tmp/pmv-secret-scan.XXXXXXXX)" \
    || malfunction "cannot create a private directory"
mkdir -- "$work/home" "$work/tmp" "$work/out" "$work/run" "$work/ignore"

# Run Git with an empty environment, so variables such as GIT_DIR, GIT_WORK_TREE,
# GIT_INDEX_FILE, or GIT_CONFIG_* cannot change which repository, index, worktree, or
# configuration is used.
clean_git() {
    /usr/bin/env -i PATH=/usr/bin:/bin HOME="$work/home" LC_ALL=C \
        GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 /usr/bin/git "$@"
}

# Run a command from an empty directory with an empty environment, inside a user and
# network namespace that has no network interfaces except loopback.
isolated() {
    (cd -- "$work/run" && /usr/bin/env -i PATH=/usr/bin:/bin HOME="$work/home" \
        TMPDIR="$work/tmp" LC_ALL=C.UTF-8 \
        /usr/bin/unshare --user --map-current-user --net -- "$@")
}

interfaces="$(isolated /bin/sh -c 'tail -n +3 /proc/net/dev | cut -d: -f1 | tr -d " "')" \
    || malfunction "network isolation with unshare is unavailable"
[[ "$interfaces" == "lo" ]] || malfunction "the isolated namespace has unexpected network interfaces"

shallow="$(clean_git -C "$repo_root" rev-parse --is-shallow-repository)" \
    || malfunction "cannot determine whether the repository is a shallow clone"
[[ "$shallow" == "false" ]] \
    || malfunction "the repository is a shallow clone; the history scan requires full history"

# Read a redacted JSON report. Prints only rule IDs, files, lines, commits, and
# fingerprints. Any malformed or unexpected report makes it exit nonzero.
report_tool() {
    /usr/bin/env -i /usr/bin/python3 -I - "$@" <<'PY'
import json
import sys

# Field types in the v1.9.0 JSON report (report/finding.go): RuleID, File, Commit, and
# Fingerprint are always-present strings (File and Commit are "" when not applicable);
# StartLine is an always-present integer.
STRING_FIELDS = ("RuleID", "File", "Commit", "Fingerprint")

mode, path = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    findings = json.load(handle)
if not isinstance(findings, list):
    sys.exit("report is not a JSON list")
for finding in findings:
    if not isinstance(finding, dict):
        sys.exit("a finding is not a JSON object")
    for field in STRING_FIELDS:
        if not isinstance(finding.get(field), str):
            sys.exit(f"a finding has a missing or non-string {field}")
    if not finding["RuleID"] or not finding["Fingerprint"]:
        sys.exit("a finding has an empty RuleID or Fingerprint")
    line = finding.get("StartLine")
    if not isinstance(line, int) or isinstance(line, bool) or line < 0:
        sys.exit("a finding has a missing or invalid StartLine")
if mode == "count":
    print(len(findings))
elif mode == "rules":
    print("\n".join(sorted({finding["RuleID"] for finding in findings})))
elif mode == "files":
    rule = sys.argv[3]
    sys.stdout.write("".join(f"{f['File']}\0" for f in findings if f["RuleID"] == rule))
elif mode == "fingerprint":
    rule, file = sys.argv[3], sys.argv[4]
    matches = [f["Fingerprint"] for f in findings if f["RuleID"] == rule and f["File"] == file]
    if len(matches) != 1:
        sys.exit("expected exactly one matching finding")
    print(matches[0])
elif mode == "summary":
    for f in findings:
        print(
            f"  finding: rule={f['RuleID']!r} file={f['File']!r} line={f['StartLine']}"
            f" commit={f['Commit']!r} fingerprint={f['Fingerprint']!r}"
        )
else:
    sys.exit("unknown report mode")
PY
}

# validate_ignore_file <file>: accept only blank lines, comments, and commit-specific
# fingerprints (commit:path:rule:line). Path-wide three-part entries are refused.
validate_ignore_file() {
    /usr/bin/env -i /usr/bin/python3 -I - "$1" <<'PY' \
        || malfunction "$ignore_name may contain only commit-specific fingerprints"
import re
import sys

entry = re.compile(r"[0-9a-f]{40}:[^:\n]+:[a-z0-9-]+:[1-9][0-9]*")
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle.read().splitlines():
        text = line.strip()
        if text and not text.startswith("#") and entry.fullmatch(text) is None:
            sys.exit(1)
PY
}

# resolve_ignore <directory>: set resolved_ignore to the ignore file passed explicitly with
# -i. A directory without one gets an empty private file, because a missing -i path is
# silently ignored by the scanner.
resolve_ignore() {
    local directory="$1"
    [[ ! -e "$directory/.gitleaksignore" && ! -L "$directory/.gitleaksignore" ]] \
        || malfunction ".gitleaksignore is not supported; use $ignore_name"
    if [[ -e "$directory/$ignore_name" || -L "$directory/$ignore_name" ]]; then
        [[ -f "$directory/$ignore_name" && ! -L "$directory/$ignore_name" ]] \
            || malfunction "$ignore_name must be a regular file"
        validate_ignore_file "$directory/$ignore_name"
        resolved_ignore="$directory/$ignore_name"
    else
        resolved_ignore="$work/ignore/empty$ignore_name"
        : >"$resolved_ignore"
    fi
}

scan_count=0
# scan <label> <ignore file> <subcommand> [arguments...]: run one scan and set
# scan_findings, scan_rules (newline-separated), and scan_report.
scan() {
    local label="$1" ignore_path="$2" subcommand="$3" argument prefix status=0
    shift 3
    for argument in "$subcommand" "$@"; do
        case "$argument" in
            validate | --validation*) malfunction "refusing a validation argument in the $label scan" ;;
        esac
    done
    scan_count=$((scan_count + 1))
    prefix="$work/out/$scan_count"
    isolated "$binary" "$subcommand" --config "$config_file" --gitleaks-ignore-path "$ignore_path" \
        --redact --ignore-gitleaks-allow --no-banner --log-level warn \
        --exit-code "$leak_status" --report-format json --report-path "$prefix.json" "$@" \
        >"$prefix.stdout" 2>"$prefix.stderr" || status=$?
    if [[ $status -ne 0 && $status -ne $leak_status ]]; then
        malfunction "the $label scan failed with exit status $status; scanner diagnostics were captured privately and are deleted on exit"
    fi
    [[ -f "$prefix.json" ]] || malfunction "the $label scan wrote no report"
    scan_findings="$(report_tool count "$prefix.json")" \
        || malfunction "the $label scan report is malformed"
    scan_rules="$(report_tool rules "$prefix.json")" \
        || malfunction "the $label scan report is malformed"
    if [[ $status -eq 0 && $scan_findings -ne 0 ]] || [[ $status -eq $leak_status && $scan_findings -eq 0 ]]; then
        malfunction "the $label scan exit status and report disagree"
    fi
    scan_report="$prefix.json"
}

# untracked_files <repo>: set `untracked` to absolute paths of untracked, non-ignored
# regular files. The list stays NUL-delimited from Git to the argument array; symlinks
# and other non-regular entries are counted in `skipped` and never followed.
untracked_files() {
    local repo="$1" entry
    local -a listed=()
    clean_git -C "$repo" ls-files -z --others --exclude-standard >"$work/untracked.list" \
        || malfunction "could not list untracked files"
    mapfile -d '' -t listed <"$work/untracked.list"
    untracked=()
    skipped=0
    for entry in "${listed[@]}"; do
        if [[ -L "$repo/$entry" || ! -f "$repo/$entry" ]]; then
            skipped=$((skipped + 1))
        else
            untracked+=("$repo/$entry")
        fi
    done
}

declare -A scope_findings scope_reports scope_rules
record_scope() {
    scope_findings[$1]=$scan_findings
    scope_reports[$1]=$scan_report
    scope_rules[$1]=$scan_rules
}

scan_repository() {
    local repo="$1"
    resolve_ignore "$repo"
    scan history "$resolved_ignore" git "$repo"
    record_scope history
    scan staged "$resolved_ignore" git --pre-commit --staged "$repo"
    record_scope staged
    scan unstaged "$resolved_ignore" git --pre-commit "$repo"
    record_scope unstaged
    untracked_files "$repo"
    if [[ ${#untracked[@]} -gt 0 ]]; then
        scan untracked "$resolved_ignore" dir -- "${untracked[@]}"
        record_scope untracked
    else
        scope_findings[untracked]=0 scope_reports[untracked]="" scope_rules[untracked]=""
    fi
}

# ----- Self-test -----

synthetic_values=()

# make_canary <label>: set `canary` to a synthetic value generated at runtime. The digest
# fragment is converted to uppercase explicitly to match the rule's character class.
make_canary() {
    local digest
    digest="$(printf 'pmv scanner canary %s' "$1" | /usr/bin/env -i /usr/bin/sha256sum)" \
        || malfunction "cannot generate a canary"
    digest="${digest:0:32}"
    canary="PMVCANARY_${digest^^}"
    synthetic_values+=("$canary")
}

test_git() {
    clean_git -C "$test_repo" -c user.name=pmv-self-test -c user.email=self-test@invalid \
        -c commit.gpgsign=false -c init.defaultBranch=main "$@" >/dev/null
}

has_rule() { # has_rule <rule> <newline-separated rules>
    grep -qxF -- "$1" <<<"$2"
}

self_test_scopes() {
    local root="$work/self-test-scopes" name scope expected reported decoy
    local -a odd_names=('space name.txt' $'tab\tname.txt' $'new\nline.txt' 'glob[*]?.txt' '-leading-dash.txt')
    test_repo="$root/repo"
    decoy="$root/decoy"
    mkdir -p -- "$test_repo" "$decoy"
    make_canary scopes
    test_git init --quiet
    printf 'clean line\n' >"$test_repo/tracked.txt"
    printf 'history %s\n' "$canary" >"$test_repo/history.txt"
    printf '*.ignored\n' >"$test_repo/.gitignore"
    test_git add tracked.txt history.txt .gitignore
    test_git commit --quiet -m "self-test history"
    test_git rm --quiet history.txt
    test_git commit --quiet -m "self-test removal"
    printf 'staged %s\n' "$canary" >"$test_repo/staged.txt"
    test_git add staged.txt
    printf 'unstaged %s\n' "$canary" >>"$test_repo/tracked.txt"
    for name in "${odd_names[@]}"; do
        printf 'untracked %s\n' "$canary" >"$test_repo/$name"
    done
    printf 'ignored %s\n' "$canary" >"$test_repo/secret.ignored"
    printf 'outside %s\n' "$canary" >"$root/outside.txt"
    ln -s -- "$root/outside.txt" "$test_repo/link.txt"

    # A decoy repository and configuration that would change the untracked-file list if
    # Git inherited this environment.
    clean_git -C "$decoy" init --quiet
    printf 'decoy %s\n' "$canary" >"$decoy/decoy.txt"
    printf '[core]\n\texcludesFile = %s\n' "$root/hide-everything" >"$root/decoy.gitconfig"
    printf '*\n' >"$root/hide-everything"
    export GIT_DIR="$decoy/.git" GIT_WORK_TREE="$decoy" GIT_INDEX_FILE="$decoy/.git/index"
    export GIT_CONFIG_GLOBAL="$root/decoy.gitconfig" GIT_CONFIG_SYSTEM="$root/decoy.gitconfig"
    export GIT_CONFIG_PARAMETERS="'core.excludesfile=$root/hide-everything'"
    scan_repository "$test_repo"
    unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_PARAMETERS

    for scope in history staged unstaged untracked; do
        has_rule "$canary_rule" "${scope_rules[$scope]}" \
            || malfunction "self-test: the canary was not detected in the $scope scan"
    done
    [[ $skipped -eq 1 ]] || malfunction "self-test: the symlink was not skipped"
    expected="$(printf '%s\0' "${odd_names[@]/#/$test_repo/}" | sort -z | sha256sum)" \
        || malfunction "self-test: cannot build the expected file list"
    reported="$(report_tool files "${scope_reports[untracked]}" "$canary_rule" | sort -z | sha256sum)" \
        || malfunction "self-test: the untracked report is malformed"
    [[ "$reported" == "$expected" ]] \
        || malfunction "self-test: untracked findings do not match the five unusual filenames exactly"
}

self_test_clean() {
    local root="$work/self-test-clean"
    mkdir -- "$root"
    printf 'nothing secret here\n' >"$root/clean.txt"
    resolve_ignore "$root"
    scan "self-test clean" "$resolved_ignore" dir -- "$root/clean.txt"
    [[ $scan_findings -eq 0 ]] || malfunction "self-test: clean input produced findings"
}

self_test_default_rule() {
    # The true-positive fixture of the default private-key rule in Betterleaks v1.9.0
    # (cmd/generate/config/rules/privatekey.go), rebuilt at runtime from eight-character
    # fragments so no committed line contains the fixture body or a key-block marker.
    local root="$work/self-test-default" label="PRIVATE KEY" line_one line_two digest
    local -a first=(MIIEvQIB ADANBgkq hkiG9w0B AQEFAASC BKcwggSj AgEAAoIB AQDAC4AW kdwKYSd8)
    local -a second=(Ks14IReL cYgADhoX k56ZzXI=)
    printf -v line_one '%s' "${first[@]}"
    printf -v line_two '%s' "${second[@]}"
    mkdir -- "$root"
    printf -- '-----BEGIN %s-----\n%s\n%s\n-----END %s-----\n' \
        "$label" "$line_one" "$line_two" "$label" >"$root/probe.txt"
    digest="$(/usr/bin/env -i /usr/bin/sha256sum -- "$root/probe.txt")" \
        || malfunction "self-test: cannot hash the probe"
    [[ "${digest%% *}" == "$probe_sha256" ]] \
        || malfunction "self-test: the assembled probe is not the upstream fixture"
    synthetic_values+=("$line_one" "$line_two")
    resolve_ignore "$root"
    scan "self-test default rule" "$resolved_ignore" dir -- "$root/probe.txt"
    has_rule "$probe_rule" "$scan_rules" \
        || malfunction "self-test: the default $probe_rule rule did not detect its upstream fixture"
}

self_test_fingerprint_ignore() {
    local root="$work/self-test-ignore" fingerprint remaining expected
    test_repo="$root/repo"
    mkdir -p -- "$test_repo"
    test_git init --quiet
    make_canary ignore-first
    printf 'first %s\n' "$canary" >"$test_repo/first.txt"
    test_git add first.txt
    test_git commit --quiet -m "self-test first finding"
    make_canary ignore-second
    printf 'second %s\n' "$canary" >"$test_repo/second.txt"
    test_git add second.txt
    test_git commit --quiet -m "self-test second finding"

    resolve_ignore "$test_repo"
    scan "self-test ignore before" "$resolved_ignore" git "$test_repo"
    fingerprint="$(report_tool fingerprint "$scan_report" "$canary_rule" first.txt)" \
        || malfunction "self-test: could not obtain exactly one fingerprint for the first finding"
    printf '# self-test exception\n%s\n' "$fingerprint" >"$test_repo/$ignore_name"
    resolve_ignore "$test_repo"
    [[ "$resolved_ignore" == "$test_repo/$ignore_name" ]] \
        || malfunction "self-test: the ignore file was not selected"
    scan "self-test ignore after" "$resolved_ignore" git "$test_repo"
    remaining="$(report_tool files "$scan_report" "$canary_rule" | sha256sum)" \
        || malfunction "self-test: the ignore report is malformed"
    expected="$(printf 'second.txt\0' | sha256sum)"
    [[ "$remaining" == "$expected" ]] \
        || malfunction "self-test: the fingerprint did not suppress exactly the first finding"
}

self_test_no_raw_output() {
    local value status
    for value in "${synthetic_values[@]}"; do
        status=0
        grep -rqF -e "$value" -- "$work/out" || status=$?
        case "$status" in
            0) malfunction "self-test: synthetic secret text appeared in scanner output" ;;
            1) ;;
            *) malfunction "self-test: cannot inspect scanner output" ;;
        esac
    done
}

self_test_scopes
self_test_clean
self_test_default_rule
self_test_fingerprint_ignore
self_test_no_raw_output
rm -rf -- "$work/out" "$work"/self-test-*
mkdir -- "$work/out"
echo "secret scan self-test passed"

# ----- Repository scan -----

scan_repository "$repo_root"
total=0
for scope in history staged unstaged untracked; do
    echo "$scope: ${scope_findings[$scope]} finding(s)"
    if [[ ${scope_findings[$scope]} -gt 0 ]]; then
        summary="$(report_tool summary "${scope_reports[$scope]}")" \
            || malfunction "the $scope report is malformed"
        printf '%s\n' "$summary"
        total=$((total + scope_findings[$scope]))
    fi
done
[[ $skipped -eq 0 ]] || echo "untracked: skipped $skipped symlink(s) or non-regular file(s)"
if [[ $total -gt 0 ]]; then
    printf 'RESULT: SECRET DETECTED: %s finding(s); values are redacted. Do not commit.\n' "$total" >&2
    final_status=secret
    exit 1
fi
echo "RESULT: CLEAN"
final_status=clean
exit 0
