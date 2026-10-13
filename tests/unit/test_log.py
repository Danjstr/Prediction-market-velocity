"""Tests for structured JSON logging."""

import io
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from pmv.config import Environment, LoggingConfig, LogLevel, load_config
from pmv.log import configure_logging, fields, get_logger, log_context
from pmv.redaction import REDACTED, Secret

LOGGER_NAME = "pmv.tests"


def fake_value(number: int) -> str:
    """Return an unmistakably fake secret value, assembled at runtime from short parts."""
    return "-".join(("FAKE", "TEST", "VALUE", str(number)))


class SensitiveObject:
    def __repr__(self) -> str:
        return "SENSITIVE"

    def __str__(self) -> str:
        return "SENSITIVE"


class BrokenStream(io.StringIO):
    def write(self, s: str, /) -> int:
        raise OSError("disk full")


@pytest.fixture(autouse=True)
def reset_pmv_logger() -> Iterator[None]:
    yield
    logger = logging.getLogger("pmv")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


@pytest.fixture
def stream() -> io.StringIO:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.DEBUG), stream=buffer)
    return buffer


def parse(buffer: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


def test_record_is_one_json_line_with_core_fields(stream: io.StringIO) -> None:
    get_logger(LOGGER_NAME).info("unit.event", extra=fields(count=3))
    (record,) = parse(stream)
    assert record["schema"] == 1
    assert record["level"] == "INFO"
    assert record["logger"] == LOGGER_NAME
    assert record["event"] == "unit.event"
    assert record["fields"] == {"count": 3}
    assert "context" not in record


def test_timestamp_is_utc_with_z_suffix(stream: io.StringIO) -> None:
    get_logger(LOGGER_NAME).info("unit.event")
    (record,) = parse(stream)
    timestamp = record["ts"]
    assert isinstance(timestamp, str)
    assert timestamp.endswith("Z")
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - parsed) < timedelta(minutes=1)


def test_records_below_configured_level_are_dropped() -> None:
    buffer = io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.WARNING), stream=buffer)
    logger = get_logger(LOGGER_NAME)
    logger.info("unit.hidden")
    logger.warning("unit.shown")
    assert [record["event"] for record in parse(buffer)] == ["unit.shown"]


def test_reconfiguring_replaces_previous_handler() -> None:
    first, second = io.StringIO(), io.StringIO()
    configure_logging(LoggingConfig(level=LogLevel.INFO), stream=first)
    configure_logging(LoggingConfig(level=LogLevel.INFO), stream=second)
    get_logger(LOGGER_NAME).info("unit.event")
    assert first.getvalue() == ""
    assert len(parse(second)) == 1


def test_secrets_are_redacted_from_fields_and_context(stream: io.StringIO) -> None:
    logger = get_logger(LOGGER_NAME)
    with log_context(session_token="hunter1"):  # noqa: S106 - fake secret under test
        logger.info(
            "unit.event",
            extra=fields(
                endpoint="https://user:hunter2@example.com",
                api_key="hunter3",
                nested={"password": fake_value(4)},
                wrapped=Secret("hunter5"),
                note="token=hunter6",
            ),
        )
    output = stream.getvalue()
    for secret in ("hunter1", "hunter2", "hunter3", fake_value(4), "hunter5", "hunter6"):
        assert secret not in output
    (record,) = parse(stream)
    assert record["context"] == {"session_token": REDACTED}
    assert record["fields"] == {
        "endpoint": f"https://{REDACTED}@example.com",
        "api_key": REDACTED,
        "nested": {"password": REDACTED},
        "wrapped": REDACTED,
        "note": f"token={REDACTED}",
    }


def test_exception_traceback_is_recorded_and_redacted(stream: io.StringIO) -> None:
    try:
        raise ValueError("password=hunter2")
    except ValueError:
        get_logger(LOGGER_NAME).exception("unit.failed")
    assert "hunter2" not in stream.getvalue()
    (record,) = parse(stream)
    exception = record["exception"]
    assert isinstance(exception, dict)
    assert exception["type"] == "ValueError"
    assert "Traceback" in exception["traceback"]


def test_unknown_objects_are_never_rendered(stream: io.StringIO) -> None:
    get_logger(LOGGER_NAME).info("unit.event", extra=fields(obj=SensitiveObject()))
    assert "SENSITIVE" not in stream.getvalue()
    (record,) = parse(stream)
    assert record["fields"] == {"obj": "<unserializable SensitiveObject>"}


def test_non_string_mapping_keys_are_never_rendered(stream: io.StringIO) -> None:
    get_logger(LOGGER_NAME).info(
        "unit.event", extra=fields(nested={SensitiveObject(): "value", 7: "seven"})
    )
    assert "SENSITIVE" not in stream.getvalue()
    (record,) = parse(stream)
    assert record["fields"] == {
        "nested": {"<SensitiveObject key #0>": REDACTED, "<int key #1>": REDACTED}
    }


def test_values_follow_numeric_and_time_conventions(stream: io.StringIO) -> None:
    get_logger(LOGGER_NAME).info(
        "unit.event",
        extra=fields(
            price=Decimal("0.53"),
            ratio=float("nan"),
            at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            naive=datetime(2026, 1, 2),  # noqa: DTZ001 - verifies naive datetimes are flagged
        ),
    )
    (record,) = parse(stream)
    assert record["fields"] == {
        "price": "0.53",
        "ratio": "nan",
        "at": "2026-01-02T03:04:05Z",
        "naive": "naive-datetime:2026-01-02T00:00:00",
    }


def test_context_applies_only_inside_its_block(stream: io.StringIO) -> None:
    logger = get_logger(LOGGER_NAME)
    with log_context(run_id="run-1"):
        with log_context(market_id="m-1"):
            logger.info("unit.inner")
        logger.info("unit.outer")
    logger.info("unit.after")
    inner, outer, after = parse(stream)
    assert inner["context"] == {"run_id": "run-1", "market_id": "m-1"}
    assert outer["context"] == {"run_id": "run-1"}
    assert "context" not in after


def test_config_objects_are_not_rendered_but_summaries_are(
    stream: io.StringIO, tmp_path: Path
) -> None:
    path = tmp_path / "test.toml"
    path.write_text(
        'schema_version = 1\nenvironment = "test"\n\n[logging]\nlevel = "INFO"\n', encoding="utf-8"
    )
    config = load_config(path, Environment.TEST)
    logger = get_logger(LOGGER_NAME)
    logger.info("unit.object", extra=fields(config=config))
    logger.info("config.loaded", extra=fields(**config.log_summary()))
    as_object, as_summary = parse(stream)
    assert as_object["fields"] == {"config": "<unserializable AppConfig>"}
    assert as_summary["fields"] == config.log_summary()


@pytest.mark.parametrize(
    "name",
    ["pmv", "pmv.config", "pmv.data.feed", "pmv.execution.order_state", "pmv._internal"],
)
def test_module_style_logger_names_are_accepted(name: str) -> None:
    assert get_logger(name).name == name


@pytest.mark.parametrize(
    "name",
    [
        "pmv.token=hunter2",
        "pmv.Foo",
        "pmv.data-feed",
        "pmvx",
        "other",
        "",
        "pmv.",
        "pmv..config",
        "pmv.1config",
        "pmv.config\n",
    ],
)
def test_malformed_logger_names_are_rejected_without_echo(name: str) -> None:
    with pytest.raises(ValueError, match="module-style name") as excinfo:
        get_logger(name)
    assert "hunter2" not in str(excinfo.value)


@pytest.mark.parametrize("name", ["config.loaded", "unit.sub.event", "a1.b_2"])
def test_valid_event_names_are_kept(stream: io.StringIO, name: str) -> None:
    get_logger(LOGGER_NAME).info(name)
    (record,) = parse(stream)
    assert record["event"] == name
    assert "event_error" not in record


@pytest.mark.parametrize(
    "name",
    [
        "unit",
        "Unit.event",
        "unit.Event",
        "unit event",
        "unit.event.",
        ".unit.event",
        "unit..event",
        "unit.event\n",
        "1unit.event",
        "unit-x.event",
    ],
)
def test_invalid_event_names_are_replaced(stream: io.StringIO, name: str) -> None:
    get_logger(LOGGER_NAME).info(name)
    (record,) = parse(stream)
    assert record["event"] == "log.invalid_event"
    assert record["event_error"] == "invalid_event_name"


def test_message_arguments_and_free_text_are_never_rendered(stream: io.StringIO) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.info("unit.event %s", "hunter2")
    logger.info("unit.event %(password)s", {"password": fake_value(3)})
    logger.info("connect password hunter4")
    output = stream.getvalue()
    for secret in ("hunter2", fake_value(3), "hunter4"):
        assert secret not in output
    records = parse(stream)
    assert [record["event"] for record in records] == ["log.invalid_event"] * 3
    assert [record["event_error"] for record in records] == [
        "message_arguments_not_allowed",
        "message_arguments_not_allowed",
        "invalid_event_name",
    ]


def test_non_string_messages_are_never_rendered(stream: io.StringIO) -> None:
    get_logger(LOGGER_NAME).info(SensitiveObject())
    assert "SENSITIVE" not in stream.getvalue()
    (record,) = parse(stream)
    assert record["event"] == "log.invalid_event"
    assert record["event_error"] == "message_not_a_string"


def test_formatting_failure_emits_safe_record(
    stream: io.StringIO, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(record: logging.LogRecord) -> dict[str, object]:
        raise RuntimeError("password=hunter2")

    monkeypatch.setattr("pmv.log._build_payload", fail)
    get_logger(LOGGER_NAME).info("unit.event")
    assert "hunter2" not in stream.getvalue()
    (record,) = parse(stream)
    assert record["event"] == "log.format_error"
    assert record["fields"] == {"source_logger": LOGGER_NAME, "error_type": "RuntimeError"}


def test_write_failure_reports_without_record_contents(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LoggingConfig(level=LogLevel.INFO), stream=BrokenStream())
    get_logger(LOGGER_NAME).info("unit.event", extra=fields(note="hunter2"))
    error_output = capsys.readouterr().err
    assert "failed to write a record" in error_output
    assert "hunter2" not in error_output


def test_write_failure_redacts_logger_name(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LoggingConfig(level=LogLevel.INFO), stream=BrokenStream())
    logging.getLogger("pmv.token=hunter2").info("unit.event")
    error_output = capsys.readouterr().err
    assert "failed to write a record" in error_output
    assert "hunter2" not in error_output
