#!/bin/bash -p
# Install the pinned Betterleaks release into a versioned directory outside the repository.
#
# The archive's size and SHA-256 are verified before it is listed or extracted, and its
# listing must contain only expected regular files. The download and every archive and
# hashing command run with a minimal environment, so inherited settings such as proxies,
# ~/.curlrc, or TAR_OPTIONS cannot change them. The binary is never executed here and is
# never placed on PATH.
set -Eeuo pipefail
umask 077
unset CDPATH
export PATH=/usr/bin:/bin
export LC_ALL=C

fail() {
    trap - ERR
    printf 'INSTALL FAILED: %s\n' "$1" >&2
    exit 2
}
trap 'fail "unexpected failure at line $LINENO"' ERR
trap 'fail "interrupted"' INT TERM HUP

# Run a command with a minimal environment; there is no fallback to the user environment.
clean() {
    /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C "$@"
}

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || exit 2
pin_file="$repo_root/scripts/betterleaks.pin"

pin_value() {
    local matches
    matches="$(grep -E "^$1=" "$pin_file")" || fail "pin '$1' is missing from scripts/betterleaks.pin"
    [[ "$matches" != *$'\n'* ]] || fail "pin '$1' is duplicated in scripts/betterleaks.pin"
    printf '%s' "${matches#*=}"
}

version="$(pin_value version)" || exit 2
archive="$(pin_value archive)" || exit 2
archive_sha256="$(pin_value archive_sha256)" || exit 2
archive_size="$(pin_value archive_size)" || exit 2
binary_sha256="$(pin_value binary_sha256)" || exit 2

[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "malformed version pin"
[[ "$archive" == "betterleaks_${version}_linux_x64.tar.gz" ]] || fail "archive pin does not match version"
[[ "$archive_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "malformed archive_sha256 pin"
[[ "$archive_size" =~ ^[1-9][0-9]*$ ]] || fail "malformed archive_size pin"
[[ "$binary_sha256" == "UNSET" || "$binary_sha256" =~ ^[0-9a-f]{64}$ ]] \
    || fail "malformed binary_sha256 pin"
[[ "$(clean /usr/bin/uname -s) $(clean /usr/bin/uname -m)" == "Linux x86_64" ]] \
    || fail "only Linux x86_64 is supported"
[[ "${HOME:-}" == /* ]] || fail "HOME must be an absolute path"

install_dir="$HOME/.local/share/pmv-tools/betterleaks/$version"
[[ ! -e "$install_dir" ]] || fail "$install_dir already exists; remove it deliberately to reinstall"

work=""
cleanup() { [[ -z "$work" ]] || rm -rf -- "$work" || true; }
trap cleanup EXIT
work="$(clean /usr/bin/mktemp -d /tmp/pmv-betterleaks-install.XXXXXXXX)" \
    || fail "cannot create a temporary directory"

url="https://github.com/betterleaks/betterleaks/releases/download/v${version}/${archive}"
mkdir -- "$work/curl-home"
# Sanitized download: no inherited proxy, credential, scanner, Git, or other variables;
# --disable (which must come first) stops ~/.curlrc from loading. There is deliberately
# no fallback to the user environment.
/usr/bin/env -i PATH=/usr/bin:/bin HOME="$work/curl-home" LC_ALL=C \
    /usr/bin/curl --disable --fail --silent --show-error --location --max-redirs 5 \
    --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 300 \
    --output "$work/$archive" "$url" \
    || fail "download failed in the sanitized environment; not retrying with the user environment"

actual_size="$(clean /usr/bin/stat -c %s -- "$work/$archive")"
[[ "$actual_size" == "$archive_size" ]] || fail "archive size does not match the pin"
actual_sha256="$(clean /usr/bin/sha256sum -- "$work/$archive")"
[[ "${actual_sha256%% *}" == "$archive_sha256" ]] \
    || fail "archive SHA-256 does not match the pin; refusing to list or extract it"
echo "archive verified: $archive size=$actual_size sha256=$archive_sha256"

# Every entry must be a regular file with a plain name from the expected set: no
# directories, links, absolute paths, parent-directory components, or duplicates.
clean /usr/bin/tar --list --gzip --file "$work/$archive" >"$work/names.list" \
    || fail "cannot list the archive"
clean /usr/bin/tar --list --verbose --gzip --file "$work/$archive" >"$work/kinds.list" \
    || fail "cannot list the archive"
mapfile -t names <"$work/names.list"
mapfile -t kinds < <(cut -c1 -- "$work/kinds.list")
[[ ${#names[@]} -gt 0 && ${#names[@]} -eq ${#kinds[@]} ]] || fail "inconsistent archive listing"
for index in "${!names[@]}"; do
    case "${names[$index]}" in
        betterleaks | LICENSE | README.md) ;;
        *) fail "unexpected archive entry: $(printf '%q' "${names[$index]}")" ;;
    esac
    [[ "${kinds[$index]}" == "-" ]] || fail "archive entry ${names[$index]} is not a regular file"
done
[[ -z "$(printf '%s\n' "${names[@]}" | sort | uniq -d)" ]] || fail "archive has duplicate entries"
printf '%s\n' "${names[@]}" | grep -qx betterleaks || fail "archive does not contain the binary"
echo "archive entries: ${names[*]}"

mkdir -- "$work/payload"
clean /usr/bin/tar --extract --gzip --file "$work/$archive" --directory "$work/payload" \
    --no-same-owner --no-same-permissions "${names[@]}" || fail "cannot extract the archive"
binary="$work/payload/betterleaks"
[[ -f "$binary" && ! -L "$binary" ]] || fail "extracted binary is missing"
actual_binary_sha256="$(clean /usr/bin/sha256sum -- "$binary")"
actual_binary_sha256="${actual_binary_sha256%% *}"
if [[ "$binary_sha256" != "UNSET" && "$actual_binary_sha256" != "$binary_sha256" ]]; then
    fail "binary SHA-256 does not match the pin"
fi
chmod 0500 -- "$binary"
for name in "${names[@]}"; do
    [[ "$name" == betterleaks ]] || chmod 0400 -- "$work/payload/$name"
done
mkdir -p -- "$(dirname -- "$install_dir")"
mv -- "$work/payload" "$install_dir"

echo "installed: $install_dir/betterleaks"
echo "binary sha256: $actual_binary_sha256"
if [[ "$binary_sha256" == "UNSET" ]]; then
    echo "binary_sha256 is not pinned yet; scans stay disabled until it is reviewed and recorded."
fi
