"""Structured logging: one redacted JSON object per line, timestamped in UTC.

Record fields:
    schema     log schema version (integer)
    ts         record creation time, ISO 8601 UTC with microseconds and a ``Z`` suffix
    level      DEBUG, INFO, WARNING, ERROR, or CRITICAL
    logger     dotted logger name inside the ``pmv`` namespace
    event      stable event name: a lowercase dotted identifier such as ``config.loaded``
    event_error  why the call's message was rejected (only when it was)
    context    correlation fields bound with ``log_context`` (only when bound)
    fields     structured fields passed with ``extra=fields(...)`` (only when given)
    exception  exception type and traceback (only when logged with exc_info)
    stack      stack trace (only when logged with stack_info)

An invalid message (not an event name, or given %-style arguments) is replaced by
``log.invalid_event`` and is never rendered. Every string passes through redaction,
values under secret-like names are replaced, and objects without a known JSON form are
rendered as their type name only.
"""

import contextlib
import json
import logging
import math
import re
import sys
import traceback
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, TextIO, override

from pmv.config import LoggingConfig
from pmv.redaction import REDACTED, Secret, is_secret_key, redact_text

LOG_SCHEMA_VERSION: Final = 1
ROOT_LOGGER_NAME: Final = "pmv"
INVALID_EVENT: Final = "log.invalid_event"

# Event names are lowercase dotted identifiers with at least two parts. Matched with
# fullmatch, which also rejects a trailing newline that a "$" anchor would allow.
_EVENT_NAME: Final = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+")
# Module-style logger names inside the pmv namespace, such as ``pmv.data.feed``.
_LOGGER_NAME: Final = re.compile(r"pmv(?:\.[a-z_][a-z0-9_]*)*")

_FIELDS_ATTRIBUTE: Final = "pmv_fields"
_MAX_DEPTH: Final = 8
_EMPTY_CONTEXT: Final[Mapping[str, object]] = MappingProxyType({})
_context: ContextVar[Mapping[str, object]] = ContextVar("pmv_log_context", default=_EMPTY_CONTEXT)


def get_logger(name: str) -> logging.Logger:
    """Return the logger for a module-style name inside ``pmv``; pass ``__name__``.

    Name validation is defense in depth. Records from loggers created directly with
    ``logging.getLogger`` still have their logger names redacted.
    """
    if _LOGGER_NAME.fullmatch(name) is None:
        # The rejected name is not echoed, because it may contain sensitive text.
        raise ValueError("logger name must be a module-style name inside the 'pmv' namespace")
    return logging.getLogger(name)


def fields(**values: object) -> dict[str, object]:
    """Build the ``extra`` argument that attaches structured fields to one log call.

    Example: ``logger.info("config.loaded", extra=fields(**config.log_summary()))``.
    """
    return {_FIELDS_ATTRIBUTE: values}


@contextlib.contextmanager
def log_context(**values: object) -> Iterator[None]:
    """Attach correlation fields, such as a run ID, to every record logged in the block."""
    token = _context.set(MappingProxyType({**_context.get(), **values}))
    try:
        yield
    finally:
        _context.reset(token)


def configure_logging(config: LoggingConfig, stream: TextIO | None = None) -> None:
    """Route ``pmv`` records at ``config.level`` or above to ``stream`` as JSON lines.

    The default stream is standard error. Handlers from an earlier call are replaced,
    so repeated calls never duplicate output.
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.addHandler(JsonLinesHandler(sys.stderr if stream is None else stream))
    logger.setLevel(config.level.value)
    logger.propagate = False


class JsonFormatter(logging.Formatter):
    """Formats a record as one redacted JSON object."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        try:
            return _to_json(_build_payload(record))
        except Exception as exc:  # noqa: BLE001 - a failed format must still emit a safe record
            return _to_json(
                {
                    "schema": LOG_SCHEMA_VERSION,
                    "ts": _utc_timestamp(record.created),
                    "level": "ERROR",
                    "logger": ROOT_LOGGER_NAME,
                    "event": "log.format_error",
                    "fields": {
                        "source_logger": redact_text(record.name),
                        "error_type": type(exc).__name__,
                    },
                }
            )


class JsonLinesHandler(logging.Handler):
    """Writes each formatted record as one line to a text stream."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self._stream = stream
        self.setFormatter(JsonFormatter())

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except (OSError, ValueError):
            self.handleError(record)

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        # The standard implementation prints the raw message and arguments, bypassing
        # redaction. Report the failure without them, with the logger name redacted.
        logger_name = redact_text(record.name)
        with contextlib.suppress(OSError, ValueError):
            sys.stderr.write(f"pmv logging: failed to write a record from logger {logger_name!r}\n")


def _build_payload(record: logging.LogRecord) -> dict[str, object]:
    event, event_error = _validated_event(record)
    payload: dict[str, object] = {
        "schema": LOG_SCHEMA_VERSION,
        "ts": _utc_timestamp(record.created),
        "level": record.levelname,
        "logger": redact_text(record.name),
        "event": event,
    }
    if event_error is not None:
        payload["event_error"] = event_error
    context = _context.get()
    if context:
        payload["context"] = _sanitize_mapping(context, 0)
    record_fields = getattr(record, _FIELDS_ATTRIBUTE, None)
    if isinstance(record_fields, Mapping) and record_fields:
        payload["fields"] = _sanitize_mapping(record_fields, 0)
    exception = record.exc_info[1] if record.exc_info else None
    if exception is not None:
        payload["exception"] = {
            "type": type(exception).__name__,
            "traceback": redact_text("".join(traceback.format_exception(exception))),
        }
    if record.stack_info:
        payload["stack"] = redact_text(record.stack_info)
    return payload


def _validated_event(record: logging.LogRecord) -> tuple[str, str | None]:
    """Return the event name and, when the call was invalid, the reason.

    An invalid message and its arguments are never rendered, so they cannot leak.
    """
    if not isinstance(record.msg, str):
        return INVALID_EVENT, "message_not_a_string"
    if record.args:
        return INVALID_EVENT, "message_arguments_not_allowed"
    if _EVENT_NAME.fullmatch(record.msg) is None:
        return INVALID_EVENT, "invalid_event_name"
    return record.msg, None


def _sanitize_mapping(mapping: Mapping[Any, object], depth: int) -> dict[str, object]:
    result: dict[str, object] = {}
    for index, (key, value) in enumerate(mapping.items()):
        if not isinstance(key, str):
            # Never call str() or repr() on an arbitrary key object. Its value is
            # redacted because the key cannot be checked for a secret-like name.
            result[f"<{type(key).__name__} key #{index}>"] = REDACTED
            continue
        name = redact_text(key)
        result[name] = REDACTED if is_secret_key(name) else _sanitize(value, depth + 1)
    return result


def _sanitize(value: object, depth: int) -> object:
    if isinstance(value, Secret):
        return REDACTED
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            return f"naive-datetime:{value.isoformat()}"
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return _sanitize(value.value, depth)
    if depth >= _MAX_DEPTH:
        return "<max-depth>"
    if isinstance(value, Mapping):
        return _sanitize_mapping(value, depth)
    if isinstance(value, list | tuple):
        return [_sanitize(item, depth + 1) for item in value]
    return f"<unserializable {type(value).__name__}>"


def _utc_timestamp(created: float) -> str:
    moment = datetime.fromtimestamp(created, tz=UTC)
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _to_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
