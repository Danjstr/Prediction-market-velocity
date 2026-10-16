"""Per-source URL allowlists and host-class refusal (A-1; ``docs/external_access.md`` §1.1).

An acquisition approval lists the exact ``https`` hosts and URL path prefixes the
acquisition tool may contact. ``UrlAllowlist.check`` accepts a URL only if all of these
hold:
- it is a plain ``https`` URL on port 443, with no user information, query, or fragment;
- its host equals an approved host exactly;
- its path starts with an approved prefix.

Anything ambiguous is refused: IP literals, percent-encoding of any kind, ``;`` path
parameters, dot segments, backslashes, doubled slashes, control characters, and
non-ASCII hosts.

Rules 1 and 8 of §1.1 are applied mechanically. A URL is restricted when either of these
holds:
- **Host:** the host's first label contains ``api``, ``stream``, ``ws``, ``feed``,
  ``quote``, ``ticker``, ``price``, ``marketdata``, ``rpc``, or ``md``, or starts with
  ``clob``, ``data``, ``assets``, or ``trad``;
- **Path:** the path contains ``/api/``, ``/v<digits>/``, ``/graphql``, ``/ws``, or
  ``/stream``, or ends in ``.json``, ``.jsonl``, or ``.csv``.

A restricted URL is allowed only under an approved prefix for which the owner has
classified that exact host and path prefix in a committed decision record. This mirrors
the F-09 denies; it does not replace them.
"""

import ipaddress
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

_LABEL: Final = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_PATH_CHARS: Final = re.compile(r"[A-Za-z0-9._~!$&'()*+,=:@/-]*")
_DECISION_PATH: Final = re.compile(r"docs/decisions/[A-Za-z0-9._/-]{1,200}\.md")

HOST_LABEL_SUBSTRINGS: Final = (
    "api",
    "stream",
    "ws",
    "feed",
    "quote",
    "ticker",
    "price",
    "marketdata",
    "rpc",
    "md",
)
HOST_LABEL_PREFIXES: Final = ("clob", "data", "assets", "trad")
# Venue, settlement-reference, chain-data, and RPC-provider domains: restricted with every
# subdomain, whatever the label (F-09 Layer B and known RPC providers).
RESTRICTED_DOMAINS: Final = (
    "kalshi.com",
    "kalshi.co",
    "polymarket.com",
    "cfbenchmarks.com",
    "chain.link",
    "pyth.network",
    "pythdata.app",
    "polygonscan.com",
    "etherscan.io",
    "alchemy.com",
    "infura.io",
    "quicknode.com",
    "quiknode.pro",
    "ankr.com",
    "chainstack.com",
    "getblock.io",
    "blastapi.io",
    "drpc.org",
    "llamarpc.com",
    "publicnode.com",
)
_PATH_PATTERNS: Final = re.compile(r"/api/|/v[0-9]+/|/graphql|/ws|/stream")
_PATH_ENDPOINTS: Final = (".json", ".jsonl", ".ndjson", ".csv")


class HostPolicyError(Exception):
    """A host, URL, or allowlist violates the acquisition host policy."""


def validate_host(host: str) -> str:
    """Return ``host`` if it is a lowercase ASCII DNS name with at least two labels."""
    if not isinstance(host, str) or not host or len(host) > 253:
        raise HostPolicyError("host must be a non-empty DNS name")
    if host != host.lower() or not host.isascii():
        raise HostPolicyError("host must be lowercase ASCII")
    if host.endswith("."):
        raise HostPolicyError("host must not end with a dot")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise HostPolicyError("IP-literal hosts are refused")
    labels = host.split(".")
    if len(labels) < 2 or any(_LABEL.fullmatch(label) is None for label in labels):
        raise HostPolicyError("host is not a valid DNS name")
    if labels[-1].isdigit() or any(label.startswith("xn--") for label in labels):
        raise HostPolicyError("numeric top-level labels and IDNA labels are refused")
    return host


def host_restriction(host: str) -> str | None:
    """Return why ``host`` is in a restricted class (§1.1 rules 1 and 8), or None."""
    labels = validate_host(host).split(".")
    for domain in RESTRICTED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return f"host is under restricted domain {domain!r}"
    # The first label always, and every label left of the registrable domain.
    candidates = [labels[0], *labels[: max(len(labels) - 2, 0)]]
    for label in candidates:
        for token in HOST_LABEL_SUBSTRINGS:
            if token in label:
                return f"host label contains {token!r}"
        for token in HOST_LABEL_PREFIXES:
            if label.startswith(token):
                return f"host label starts with {token!r}"
    return None


def path_restriction(path: str) -> str | None:
    """Return why ``path`` matches a §1.1 rule 8 path pattern, or None."""
    lowered = path.lower()
    match = _PATH_PATTERNS.search(lowered)
    if match is not None:
        return f"path contains {match.group(0)!r}"
    if lowered.rstrip("/").endswith(_PATH_ENDPOINTS):
        return "path is a .json, .jsonl, or .csv endpoint"
    return None


def _check_path(path: str) -> str:
    if not path.startswith("/"):
        raise HostPolicyError("URL path must be absolute")
    if "\\" in path or "//" in path:
        raise HostPolicyError("URL path contains a backslash or an empty segment")
    if "%" in path or ";" in path:
        raise HostPolicyError("URL path contains percent-encoding or a path parameter")
    if _PATH_CHARS.fullmatch(path) is None:
        raise HostPolicyError("URL path contains a disallowed character")
    if any(segment in {".", ".."} for segment in path.split("/")):
        raise HostPolicyError("URL path contains a dot segment")
    return path


def _split_url(url: str) -> tuple[str, str]:
    if not isinstance(url, str) or not url.isascii() or len(url) > 2048:
        raise HostPolicyError("URL must be ASCII text of at most 2048 characters")
    if any(ord(char) < 0x21 or ord(char) == 0x7F for char in url):
        raise HostPolicyError("URL contains whitespace or control characters")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise HostPolicyError("only https URLs are allowed")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise HostPolicyError("URL user information is refused")
    if parts.query or parts.fragment or "?" in url or "#" in url:
        raise HostPolicyError("URL queries and fragments are refused")
    try:
        port = parts.port
    except ValueError:
        raise HostPolicyError("URL port is malformed") from None
    host = parts.hostname or ""
    if port not in (None, 443) or parts.netloc not in {host, f"{host}:443"}:
        raise HostPolicyError("URL authority must be a bare host on port 443")
    return validate_host(host), _check_path(parts.path or "/")


@dataclass(frozen=True, slots=True)
class UrlPrefix:
    host: str
    path_prefix: str

    @classmethod
    def parse(cls, text: str) -> "UrlPrefix":
        host, path = _split_url(text)
        return cls(host=host, path_prefix=path)

    @property
    def text(self) -> str:
        return f"https://{self.host}{self.path_prefix}"

    def covers(self, host: str, path: str) -> bool:
        if host != self.host:
            return False
        if self.path_prefix.endswith("/"):
            return path.startswith(self.path_prefix)
        return path == self.path_prefix or path.startswith(self.path_prefix + "/")


@dataclass(frozen=True, slots=True)
class UrlAllowlist:
    """The exact hosts and path prefixes one approved acquisition may contact."""

    prefixes: tuple[UrlPrefix, ...]
    host_class_decisions: Mapping[str, str]

    @classmethod
    def build(
        cls,
        prefixes: Iterable[str],
        host_class_decisions: Mapping[str, str] | None = None,
    ) -> "UrlAllowlist":
        """Build an allowlist.

        ``host_class_decisions`` maps an approved prefix (exact host and path prefix, as
        listed) to the committed owner decision record that classifies it. A prefix whose
        host or path is restricted must have one.
        """
        parsed = tuple(UrlPrefix.parse(text) for text in prefixes)
        if not parsed:
            raise HostPolicyError("an allowlist needs at least one URL prefix")
        if len(set(parsed)) != len(parsed):
            raise HostPolicyError("duplicate URL prefixes")
        decisions = dict(host_class_decisions or {})
        listed = {prefix.text for prefix in parsed}
        for key, decision in decisions.items():
            if key not in listed:
                raise HostPolicyError("a host-class decision names a prefix outside the allowlist")
            if not isinstance(decision, str) or _DECISION_PATH.fullmatch(decision) is None:
                raise HostPolicyError("a host-class decision must cite a docs/decisions record")
            if ".." in decision:
                raise HostPolicyError("a host-class decision must cite a docs/decisions record")
        for prefix in parsed:
            reason = host_restriction(prefix.host) or path_restriction(prefix.path_prefix)
            if reason is not None and prefix.text not in decisions:
                raise HostPolicyError(
                    f"prefix {prefix.text} is restricted ({reason}); "
                    "an owner host-class decision for this exact host and prefix is required"
                )
        return cls(prefixes=parsed, host_class_decisions=decisions)

    def check(self, url: str) -> str:
        """Return ``url`` if this allowlist permits it; raise HostPolicyError otherwise."""
        host, path = _split_url(url)
        covering = [prefix for prefix in self.prefixes if prefix.covers(host, path)]
        if not covering:
            raise HostPolicyError("URL is outside the approved hosts and prefixes")
        reason = host_restriction(host) or path_restriction(path)
        if reason is not None and not any(
            prefix.text in self.host_class_decisions for prefix in covering
        ):
            raise HostPolicyError(
                f"URL is restricted ({reason}) and no owner host-class decision covers it"
            )
        return url
