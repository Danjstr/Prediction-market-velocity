"""G-1 failure injection: the trusted parent against misbehaving workers.

Each test runs a fake worker (a small synthetic script) in place of the real one, under the
same launcher, limits, and protocol checks. The parent must refuse every malformed,
truncated, oversized, trailing, mismatched, crashed, signaled, timed-out, or
resource-exhausted outcome, and must never accept a partial result.
"""

import os
import sys
import textwrap
from pathlib import Path

import pytest

from pmv.acquisition import worker_protocol as wp
from pmv.acquisition.archive import ArchiveRefusedError
from pmv.acquisition.confinement import WorkerLimits
from pmv.acquisition.isolation import (
    IsolationError,
    IsolationFailure,
    WorkerRefusedError,
    isolated_extract,
    run_worker,
)

FAKE = textwrap.dedent(
    """
    import os, sys, time, signal
    from pmv.acquisition import worker_protocol as wp
    from pmv.acquisition.isolation import expected_identity
    from pmv.integrity import canonical_json

    def out(data):
        view = memoryview(data)
        while view:
            view = view[os.write(1, view):]

    def hello(**changes):
        value = {"protocol": wp.PROTOCOL, "version": wp.PROTOCOL_VERSION,
                 "confined": True, "identity": expected_identity()}
        value.update(changes)
        return wp.frame(wp.HELLO, canonical_json(value))

    def result(value):
        return wp.frame(wp.RESULT, canonical_json(value))

    OK = {"status": "ok"}
    mode = sys.argv[1]
    if mode == "sleep":
        time.sleep(60)
    elif mode == "crash":
        out(wp.MAGIC + hello()); os._exit(3)
    elif mode == "signal":
        out(wp.MAGIC + hello()); os.kill(os.getpid(), signal.SIGSEGV)
    elif mode == "cpu":
        while True:
            pass
    elif mode == "write_file":
        with open(sys.argv[2], "wb") as handle:
            handle.write(b"x" * 4096)
            handle.flush()
        out(wp.MAGIC + hello() + result(OK))
    elif mode == "garbage":
        out(b"NOT-THE-MAGIC-AT-ALL")
    elif mode == "bad_type":
        out(wp.MAGIC + hello() + b"Z" + (0).to_bytes(4, "big"))
    elif mode == "bad_json":
        out(wp.MAGIC + wp.HELLO + (9).to_bytes(4, "big") + b"{not json")
    elif mode == "huge_frame":
        out(wp.MAGIC + hello() + wp.RESULT + (100 * 1024 * 1024).to_bytes(4, "big"))
    elif mode == "truncated":
        frame = result(OK)
        out(wp.MAGIC + hello() + frame[: len(frame) - 2])
    elif mode == "no_result":
        out(wp.MAGIC + hello())
    elif mode == "no_hello":
        out(wp.MAGIC + result(OK))
    elif mode == "flood":
        out(wp.MAGIC + hello())
        chunk = wp.frame(wp.DATA, b"x" * wp.MAX_DATA_PAYLOAD)
        for _ in range(64):
            out(chunk)
    elif mode == "version":
        out(wp.MAGIC + hello(version=2) + result(OK))
    elif mode == "protocol":
        out(wp.MAGIC + hello(protocol="other") + result(OK))
    elif mode == "identity":
        out(wp.MAGIC + hello(identity={"python": "0"}) + result(OK))
    elif mode == "trailing":
        out(wp.MAGIC + hello() + result(OK) + b"x")
    elif mode == "two_results":
        out(wp.MAGIC + hello() + result(OK) + result(OK))
    elif mode == "not_confined":
        refused = {"status": "refused", "code": "confinement_failed", "record": None}
        out(wp.MAGIC + hello(confined=False) + result(refused))
    elif mode == "unexpected_frame":
        out(wp.MAGIC + hello() + wp.frame(wp.DATA, b"x") + result(OK))
    elif mode == "bad_refusal":
        out(wp.MAGIC + hello() + result({"status": "refused", "code": "made_up", "record": None}))
    elif mode == "refused":
        value = {"status": "refused", "code": "parse_failed", "record": 7}
        out(wp.MAGIC + hello() + result(value))
    elif mode == "environment":
        fds = sorted(int(name) for name in os.listdir("/proc/self/fd"))
        value = {"status": "ok", "env": sorted(os.environ), "cwd": os.getcwd(), "fds": fds}
        out(wp.MAGIC + hello() + result(value))
    elif mode.startswith("extract_"):
        file_frame = wp.frame(wp.FILE, canonical_json({"name": "a.csv", "size": 4}))
        good = (file_frame + wp.frame(wp.DATA, b"a\\n1\\n")
                + wp.frame(wp.END_FILE, canonical_json(
                    {"sha256": "5" * 64})))
        if mode == "extract_partial":
            out(wp.MAGIC + hello() + file_frame + wp.frame(wp.DATA, b"a\\n")); os._exit(9)
        elif mode == "extract_traversal":
            bad = wp.frame(wp.FILE, canonical_json({"name": "../x.csv", "size": 1}))
            out(wp.MAGIC + hello() + bad + wp.frame(wp.DATA, b"x"))
        elif mode == "extract_hash_lie":
            out(wp.MAGIC + hello() + good)
        elif mode == "extract_overrun":
            out(wp.MAGIC + hello() + file_frame + wp.frame(wp.DATA, b"a\\n1\\n2\\n"))
        elif mode == "extract_summary_lie":
            import hashlib
            digest = hashlib.sha256(b"a\\n1\\n").hexdigest()
            end = wp.frame(wp.END_FILE, canonical_json({"sha256": digest}))
            summary = {"status": "ok", "files": 2, "directories": 0, "total_bytes": 4}
            out(wp.MAGIC + hello() + file_frame + wp.frame(wp.DATA, b"a\\n1\\n") + end
                + result(summary))
    """
)

LIMITS = WorkerLimits(wall_clock_seconds=20.0)


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    path = tmp_path / "fake_worker.py"
    path.write_text(FAKE, encoding="utf-8")
    return path


def _run(fake: Path, mode: str, *extra: str, **kwargs: object) -> object:
    return run_worker(
        wp.Operation.PROBE,
        {},
        input_fd=None,
        limits=kwargs.pop("limits", LIMITS),  # type: ignore[arg-type]
        command=[sys.executable, "-I", str(fake), mode, *extra],
        **kwargs,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("mode", "failure"),
    [
        ("crash", IsolationFailure.ABNORMAL_EXIT),
        ("signal", IsolationFailure.SIGNALED),
        ("garbage", IsolationFailure.PROTOCOL_MISMATCH),
        ("bad_type", IsolationFailure.MALFORMED_OUTPUT),
        ("bad_json", IsolationFailure.MALFORMED_OUTPUT),
        ("huge_frame", IsolationFailure.MALFORMED_OUTPUT),
        ("truncated", IsolationFailure.TRUNCATED_OUTPUT),
        ("no_result", IsolationFailure.TRUNCATED_OUTPUT),
        ("no_hello", IsolationFailure.PROTOCOL_MISMATCH),
        ("version", IsolationFailure.PROTOCOL_MISMATCH),
        ("protocol", IsolationFailure.PROTOCOL_MISMATCH),
        ("identity", IsolationFailure.IDENTITY_MISMATCH),
        ("trailing", IsolationFailure.TRAILING_OUTPUT),
        ("two_results", IsolationFailure.TRAILING_OUTPUT),
        ("not_confined", IsolationFailure.NOT_CONFINED),
        ("unexpected_frame", IsolationFailure.MALFORMED_OUTPUT),
        ("bad_refusal", IsolationFailure.MALFORMED_OUTPUT),
    ],
)
def test_misbehaving_worker_is_refused(fake: Path, mode: str, failure: IsolationFailure) -> None:
    with pytest.raises(IsolationError) as caught:
        _run(fake, mode)
    assert caught.value.failure is failure


def test_timeout_kills_the_worker(fake: Path) -> None:
    with pytest.raises(IsolationError) as caught:
        _run(fake, "sleep", limits=WorkerLimits(wall_clock_seconds=1.0))
    assert caught.value.failure is IsolationFailure.TIMEOUT


def test_cpu_limit_is_enforced_outside_the_worker(fake: Path) -> None:
    with pytest.raises(IsolationError) as caught:
        _run(fake, "cpu", limits=WorkerLimits(cpu_seconds=1, wall_clock_seconds=30.0))
    assert caught.value.failure is IsolationFailure.CPU_LIMIT


def test_file_size_limit_stops_any_file_write(fake: Path, tmp_path: Path) -> None:
    target = tmp_path / "written"
    with pytest.raises(IsolationError) as caught:
        _run(fake, "write_file", str(target))
    # CPython ignores SIGXFSZ, so the write fails with EFBIG and the worker exits abnormally.
    assert caught.value.failure in (IsolationFailure.SIGNALED, IsolationFailure.ABNORMAL_EXIT)
    assert not target.exists() or target.stat().st_size == 0


def test_oversized_output_is_refused(fake: Path) -> None:
    with pytest.raises(IsolationError) as caught:
        _run(fake, "flood", max_output_bytes=4 * 1024 * 1024, on_frame=lambda _k, _p: None)
    assert caught.value.failure is IsolationFailure.OVERSIZED_OUTPUT


def test_refusal_is_reported_with_its_closed_code(fake: Path) -> None:
    with pytest.raises(WorkerRefusedError) as caught:
        _run(fake, "refused")
    assert caught.value.code is wp.RefusalCode.PARSE_FAILED
    assert caught.value.record == 7


def test_worker_gets_no_environment_and_only_three_descriptors(
    fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PMV_SENTINEL_SECRET", "not-a-secret")
    run = _run(fake, "environment")
    result = run.result  # type: ignore[attr-defined]
    assert result["env"] == [] or result["env"] == ["LC_CTYPE"]
    assert result["cwd"] == "/"
    # 0 stdin, 1 stdout, 2 stderr, plus the descriptor listdir itself opened.
    assert len(result["fds"]) <= 4
    assert result["fds"][:3] == [0, 1, 2]


# --- partial results are never accepted ---------------------------------------------------


def _extract(fake: Path, tmp_path: Path, mode: str) -> Path:
    archive = tmp_path / "a.tar"
    archive.write_bytes(bytes(1024))
    destination = tmp_path / "out"
    destination.mkdir()
    with pytest.raises((IsolationError, ArchiveRefusedError)):
        isolated_extract(
            archive,
            destination,
            worker_limits=LIMITS,
            command=[sys.executable, "-I", str(fake), mode],
        )
    return destination


@pytest.mark.parametrize(
    "mode",
    [
        "extract_partial",
        "extract_traversal",
        "extract_hash_lie",
        "extract_overrun",
        "extract_summary_lie",
    ],
)
def test_partial_or_lying_extraction_leaves_nothing(fake: Path, tmp_path: Path, mode: str) -> None:
    destination = _extract(fake, tmp_path, mode)
    assert list(destination.iterdir()) == []
    assert not (tmp_path / "x.csv").exists()


def test_parent_survives_a_worker_that_exits_without_reading(fake: Path) -> None:
    # The parent never blocks on a worker that ignores its input.
    fd = os.open(fake, os.O_RDONLY)
    try:
        with pytest.raises(IsolationError):
            run_worker(
                wp.Operation.PROBE,
                {},
                input_fd=fd,
                limits=LIMITS,
                command=[sys.executable, "-I", str(fake), "no_result"],
            )
    finally:
        os.close(fd)
