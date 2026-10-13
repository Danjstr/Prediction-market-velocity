#!/bin/bash -p
# CI only: make sure the secret scan's network namespace can be created on an ephemeral
# GitHub-hosted runner. First probes the exact operation scripts/scan_secrets.sh uses.
# Only if that fails, and only if Ubuntu's AppArmor restriction on unprivileged user
# namespaces is active, is that single setting lifted and the probe repeated. The scan
# still verifies its own namespace independently. Refuses to run anywhere else.
set -Eeuo pipefail
unset CDPATH
export PATH=/usr/bin:/bin
export LC_ALL=C

fail() {
    trap - ERR
    printf 'PREPARE FAILED: %s\n' "$1" >&2
    exit 2
}
trap 'fail "unexpected failure at line $LINENO"' ERR
trap 'fail "interrupted"' INT TERM HUP

[[ "${GITHUB_ACTIONS:-}" == "true" && "${RUNNER_ENVIRONMENT:-}" == "github-hosted" \
    && "${RUNNER_OS:-}" == "Linux" && "${RUNNER_ARCH:-}" == "X64" ]] \
    || fail "refusing to run outside an ephemeral GitHub-hosted Linux X64 runner"

# The exact namespace the scan uses; succeeds only if loopback is the only interface.
probe() {
    local interfaces
    interfaces="$(/usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C \
        /usr/bin/unshare --user --map-current-user --net -- \
        /bin/sh -c 'tail -n +3 /proc/net/dev | cut -d: -f1 | tr -d " "' 2>/dev/null)" || return 1
    [[ "$interfaces" == "lo" ]]
}

if probe; then
    echo "network namespace probe: available; no kernel setting changed"
    exit 0
fi
echo "network namespace probe: unavailable"

setting=/proc/sys/kernel/apparmor_restrict_unprivileged_userns
[[ -r "$setting" ]] \
    || fail "probe failed and kernel.apparmor_restrict_unprivileged_userns does not exist; changing nothing"
value="$(<"$setting")"
[[ "$value" =~ ^[0-9]+$ ]] || fail "unexpected value of kernel.apparmor_restrict_unprivileged_userns"
[[ "$value" != 0 ]] \
    || fail "probe failed although the AppArmor restriction is already off; changing nothing else"
echo "kernel.apparmor_restrict_unprivileged_userns is $value; setting it to 0"
sudo -n /usr/sbin/sysctl -q -w kernel.apparmor_restrict_unprivileged_userns=0 \
    || fail "could not change kernel.apparmor_restrict_unprivileged_userns"

probe || fail "network namespace probe still fails after lifting the AppArmor restriction"
echo "network namespace probe: available after lifting the AppArmor restriction"
