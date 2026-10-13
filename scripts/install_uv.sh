#!/bin/bash -p
# Install the pinned uv release into a versioned directory outside the repository.
#
# Follows scripts/install_betterleaks.sh: the archive's size and SHA-256 are verified
# before it is listed or extracted, only expected entries are accepted, and the download
# and every archive and hashing command run with a minimal environment. Nothing
# downloaded is executed here.
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

clean() {
    /usr/bin/env -i PATH=/usr/bin:/bin LC_ALL=C "$@"
}

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)" || exit 2
pin_file="$repo_root/scripts/uv.pin"

pin_value() {
    local matches
    matches="$(grep -E "^$1=" "$pin_file")" || fail "pin '$1' is missing from scripts/uv.pin"
    [[ "$matches" != *$'\n'* ]] || fail "pin '$1' is duplicated in scripts/uv.pin"
    printf '%s' "${matches#*=}"
}

version="$(pin_value version)" || exit 2
archive="$(pin_value archive)" || exit 2
archive_sha256="$(pin_value archive_sha256)" || exit 2
archive_size="$(pin_value archive_size)" || exit 2
prefix="uv-x86_64-unknown-linux-gnu"

[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "malformed version pin"
[[ "$archive" == "$prefix.tar.gz" ]] || fail "unexpected archive pin"
[[ "$archive_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "malformed archive_sha256 pin"
[[ "$archive_size" =~ ^[1-9][0-9]*$ ]] || fail "malformed archive_size pin"
[[ "$(clean /usr/bin/uname -s) $(clean /usr/bin/uname -m)" == "Linux x86_64" ]] \
    || fail "only Linux x86_64 is supported"
[[ "${HOME:-}" == /* ]] || fail "HOME must be an absolute path"

install_dir="$HOME/.local/share/pmv-tools/uv/$version"
[[ ! -e "$install_dir" ]] || fail "$install_dir already exists; remove it deliberately to reinstall"

work=""
cleanup() { [[ -z "$work" ]] || rm -rf -- "$work" || true; }
trap cleanup EXIT
work="$(clean /usr/bin/mktemp -d /tmp/pmv-uv-install.XXXXXXXX)" || fail "cannot create a temporary directory"

url="https://github.com/astral-sh/uv/releases/download/${version}/${archive}"
mkdir -- "$work/curl-home"
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

clean /usr/bin/tar --list --gzip --file "$work/$archive" >"$work/names.list" \
    || fail "cannot list the archive"
clean /usr/bin/tar --list --verbose --gzip --file "$work/$archive" >"$work/kinds.list" \
    || fail "cannot list the archive"
mapfile -t names <"$work/names.list"
mapfile -t kinds < <(cut -c1 -- "$work/kinds.list")
[[ ${#names[@]} -gt 0 && ${#names[@]} -eq ${#kinds[@]} ]] || fail "inconsistent archive listing"
for index in "${!names[@]}"; do
    case "${names[$index]}:${kinds[$index]}" in
        "$prefix/:d" | "$prefix/uv:-" | "$prefix/uvx:-") ;;
        *) fail "unexpected archive entry: $(printf '%q' "${names[$index]}")" ;;
    esac
done
[[ -z "$(printf '%s\n' "${names[@]}" | sort | uniq -d)" ]] || fail "archive has duplicate entries"
for required in "$prefix/uv" "$prefix/uvx"; do
    printf '%s\n' "${names[@]}" | grep -qxF -- "$required" || fail "archive is missing $required"
done
echo "archive entries: ${names[*]}"

mkdir -- "$work/payload"
clean /usr/bin/tar --extract --gzip --file "$work/$archive" --directory "$work/payload" \
    --no-same-owner --no-same-permissions "$prefix/uv" "$prefix/uvx" \
    || fail "cannot extract the archive"
for binary in uv uvx; do
    [[ -f "$work/payload/$prefix/$binary" && ! -L "$work/payload/$prefix/$binary" ]] \
        || fail "extracted $binary is missing"
    chmod 0500 -- "$work/payload/$prefix/$binary"
done
mkdir -p -- "$(dirname -- "$install_dir")"
mv -- "$work/payload/$prefix" "$install_dir"
echo "installed: $install_dir/uv"
