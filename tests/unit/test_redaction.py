"""Tests for secret detection and redaction."""

import pickle

import pytest

from pmv.redaction import REDACTED, Secret, is_secret_key, redact_text


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "api_key",
        "apiKey",
        "API-KEY",
        "x-api-key",
        "privateKey",
        "private_key",
        "client_secret",
        "auth_token",
        "Authorization",
        "seed_phrase",
        "passphrase",
        "credentials",
        "cookie",
        "signature",
    ],
)
def test_secret_like_names_are_detected(name: str) -> None:
    assert is_secret_key(name)


@pytest.mark.parametrize(
    "name",
    [
        "market_id",
        "ticker",
        "seed",
        "author",
        "key",
        "price",
        "token_id",
        "tokenId",
        "keyboard",
        "run_id",
    ],
)
def test_ordinary_names_are_not_detected(name: str) -> None:
    assert not is_secret_key(name)


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("password=hunter2", "hunter2"),
        ("api_key: 'abc123def'", "abc123def"),
        ('{"token": "tok-999-secret"}', "tok-999-secret"),
        ("Authorization: Bearer abcdefghijklmnop", "abcdefghijklmnop"),
        ("postgres://user:hunter2@db.example/x", "hunter2"),
        ("wallet 0x" + "ab" * 32, "ab" * 32),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl", "c2lnbmF0dXJl"),
        ("-----BEGIN PRIVATE KEY-----\nMIIEvQ\n-----END PRIVATE KEY-----", "MIIEvQ"),
    ],
)
def test_secret_values_in_text_are_redacted(text: str, secret: str) -> None:
    result = redact_text(text)
    assert secret not in result
    assert REDACTED in result


@pytest.mark.parametrize(
    "text",
    [
        "config.loaded",
        "sha256 " + "ab" * 32,
        "token_id=12345",
        "basic statistics",
        "https://api.example.com/markets?limit=5",
    ],
)
def test_ordinary_text_is_unchanged(text: str) -> None:
    assert redact_text(text) == text


def test_secret_is_never_revealed_by_string_conversion() -> None:
    secret = Secret("hunter2")
    for rendered in (str(secret), repr(secret), f"{secret}", f"{secret!r}"):
        assert "hunter2" not in rendered
    assert secret.reveal() == "hunter2"


def test_secret_cannot_be_pickled() -> None:
    with pytest.raises(TypeError, match="cannot be pickled"):
        pickle.dumps(Secret("hunter2"))
