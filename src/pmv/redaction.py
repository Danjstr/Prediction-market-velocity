"""Detection and redaction of secret-like values.

Redaction is a safety net, not the primary control: secrets are wrapped in ``Secret``
where they are loaded and are never deliberately logged. Pattern-based text redaction
is best-effort and cannot recognize every possible secret.
"""

import re
from itertools import pairwise
from typing import Final, NoReturn

REDACTED: Final = "[REDACTED]"

# Names containing any of these words are treated as secret.
_SECRET_WORDS: Final = frozenset(
    {
        "apikey",
        "auth",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "credentials",
        "jwt",
        "mnemonic",
        "passphrase",
        "passwd",
        "password",
        "pem",
        "privkey",
        "pwd",
        "secret",
        "secrets",
        "signature",
        "token",
        "tokens",
    }
)
# Names containing any of these adjacent word pairs are treated as secret.
_SECRET_WORD_PAIRS: Final = frozenset(
    {
        ("access", "key"),
        ("api", "key"),
        ("private", "key"),
        ("secret", "key"),
        ("seed", "phrase"),
        ("signing", "key"),
    }
)
# Public identifiers whose names would otherwise match. Polymarket outcome tokens are
# identified by a public ``token_id``.
_NON_SECRET_NAMES: Final = frozenset({"token_id", "token_ids"})

_NAME_WORD_BOUNDARY: Final = re.compile(r"[^0-9A-Za-z]+|(?<=[a-z0-9])(?=[A-Z])")

_SECRET_TEXT_PATTERNS: Final = (
    # PEM private-key blocks, including truncated ones.
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)",
        re.DOTALL,
    ),
    # Bearer tokens.
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    # JSON Web Tokens.
    re.compile(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"),
    # User credentials embedded in URLs.
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),
    # 0x-prefixed 32-byte hex values, the form of wallet private keys.
    re.compile(r"\b0x[0-9a-fA-F]{64}\b"),
)
# ``name=value`` or ``name: value`` for any identifier. Whether the value is redacted is
# decided only by ``is_secret_key``, the single classifier for secret-looking names.
# A colon followed by ``//`` is a URL scheme, not an assignment.
_ASSIGNMENT: Final = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_.-]*)([\"']?\s*(?:=|:(?!//))\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)


class Secret[T]:
    """Holds a secret value that ``str``, ``repr``, formatting, and logging never reveal."""

    __slots__ = ("_value",)

    def __init__(self, value: T) -> None:
        self._value = value

    def reveal(self) -> T:
        """Return the raw value. Call only where the raw value is required."""
        return self._value

    def __repr__(self) -> str:
        return f"Secret({REDACTED})"

    def __str__(self) -> str:
        return REDACTED

    def __reduce__(self) -> NoReturn:
        raise TypeError("Secret values cannot be pickled")


def is_secret_key(name: str) -> bool:
    """Return whether a field or key name looks like it holds a secret."""
    words = [word.lower() for word in _NAME_WORD_BOUNDARY.split(name) if word]
    if "_".join(words) in _NON_SECRET_NAMES:
        return False
    if any(word in _SECRET_WORDS for word in words):
        return True
    return any(pair in _SECRET_WORD_PAIRS for pair in pairwise(words))


def redact_text(text: str) -> str:
    """Replace recognizable secret values in free text with ``REDACTED``."""
    for pattern in _SECRET_TEXT_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return _redact_assignments(text)


def _redact_assignments(text: str) -> str:
    # After a non-secret name, scanning resumes inside its value, so an assignment
    # nested in a value (for example a URL query string) is still examined.
    pieces: list[str] = []
    position = 0
    while (match := _ASSIGNMENT.search(text, position)) is not None:
        if is_secret_key(match[1]):
            pieces.append(text[position : match.start(3)])
            pieces.append(REDACTED)
            position = match.end()
        else:
            pieces.append(text[position : match.end(2)])
            position = match.end(2)
    pieces.append(text[position:])
    return "".join(pieces)
