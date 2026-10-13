"""Explicit, allowlisted loading of secret inputs.

Secrets are never configuration values. Each one is declared with a ``SecretSpec`` and
read by name from a mapping the caller passes in explicitly, such as ``os.environ``.
The loader looks up only the declared names; it never iterates over or copies the
mapping. Every value is wrapped in ``Secret`` immediately and is never modified.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, NoReturn

from pmv.redaction import Secret

_SECRET_NAME: Final = re.compile(r"PMV_SECRET_[A-Z0-9]+(?:_[A-Z0-9]+)*")


class SecretInputError(Exception):
    """A required secret input is missing or unusable. Messages name inputs, never values."""


@dataclass(frozen=True, slots=True)
class SecretSpec:
    """Declares one required secret input by its non-confidential name."""

    name: str

    def __post_init__(self) -> None:
        if _SECRET_NAME.fullmatch(self.name) is None:
            # The rejected name is not echoed, in case a value was passed by mistake.
            raise ValueError("secret input names must match PMV_SECRET_<UPPER_SNAKE_CASE>")


class LoadedSecrets:
    """Secret inputs loaded for a set of specs. Its string forms list names only."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Secret[str]]) -> None:
        self._values: Mapping[str, Secret[str]] = MappingProxyType(dict(values))

    def get(self, spec: SecretSpec) -> Secret[str]:
        """Return the loaded secret for ``spec``."""
        try:
            return self._values[spec.name]
        except KeyError:
            raise SecretInputError(f"secret input {spec.name} was not loaded") from None

    @property
    def names(self) -> tuple[str, ...]:
        """Return the names of the loaded secret inputs, sorted."""
        return tuple(sorted(self._values))

    def __repr__(self) -> str:
        return f"LoadedSecrets(names={list(self.names)!r})"

    def __str__(self) -> str:
        return repr(self)

    def __reduce__(self) -> NoReturn:
        raise TypeError("LoadedSecrets cannot be pickled")


def load_secrets(specs: Iterable[SecretSpec], source: Mapping[str, str]) -> LoadedSecrets:
    """Load every declared secret input from ``source``, such as ``os.environ``.

    Only the declared names are looked up. Values are never stripped or otherwise
    changed. Every problem is reported in one error that names inputs, never values.
    """
    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        raise ValueError("secret input specs must have unique names")
    missing: list[str] = []
    not_text: list[str] = []
    blank: list[str] = []
    values: dict[str, Secret[str]] = {}
    for name in names:
        # Checked at runtime despite the type hint. An unexpected value is never
        # converted to text, because its str() or repr() could expose it. Only an exact
        # str is accepted; a subclass could override strip() or other methods.
        raw: object = source.get(name)
        if raw is None:
            missing.append(name)
        elif not isinstance(raw, str) or type(raw) is not str:
            not_text.append(name)
        elif raw.strip() == "":
            blank.append(name)
        else:
            values[name] = Secret(raw)
    problems: list[str] = []
    if missing:
        problems.append(f"missing: {', '.join(missing)}")
    if not_text:
        problems.append(f"not a string: {', '.join(not_text)}")
    if blank:
        problems.append(f"empty or whitespace-only: {', '.join(blank)}")
    if problems:
        raise SecretInputError("required secret inputs are unusable; " + "; ".join(problems))
    return LoadedSecrets(values)
