"""G-1 confinement: the seccomp program, the resource limits, and their verification."""

import resource
import struct

import pytest

from pmv.acquisition import confinement
from pmv.acquisition.confinement import (
    DENIED_SYSCALLS,
    ConfinementError,
    WorkerLimits,
    filter_program,
    verify_limits,
)

CRITICAL = (
    "open",
    "openat",
    "openat2",
    "creat",
    "socket",
    "connect",
    "execve",
    "execveat",
    "fork",
    "vfork",
    "clone",
    "clone3",
    "ptrace",
    "io_uring_setup",
    "unlink",
    "unlinkat",
    "rename",
    "renameat2",
    "link",
    "linkat",
    "fchmod",
    "kill",
    "tgkill",
)


def test_every_critical_syscall_is_denied() -> None:
    assert set(CRITICAL) <= set(DENIED_SYSCALLS)
    assert len(set(DENIED_SYSCALLS.values())) == len(DENIED_SYSCALLS)


def _records(program: bytes) -> list[tuple[int, int, int, int]]:
    assert len(program) % 8 == 0
    return [struct.unpack("HBBI", program[i : i + 8]) for i in range(0, len(program), 8)]


def test_filter_checks_architecture_and_x32_before_syscall_numbers() -> None:
    records = _records(filter_program())
    load_arch, check_arch, kill_arch, load_nr, check_x32, kill_x32 = records[:6]
    assert load_arch == (0x20, 0, 0, 4)
    assert check_arch == (0x15, 1, 0, 0xC000003E)
    assert kill_arch == (0x06, 0, 0, 0x80000000)
    assert load_nr == (0x20, 0, 0, 0)
    assert check_x32 == (0x35, 0, 1, 0x40000000)
    assert kill_x32 == (0x06, 0, 0, 0x80000000)


def test_every_denied_number_jumps_to_the_errno_return() -> None:
    records = _records(filter_program())
    jumps = records[6:-2]
    allow, deny = records[-2:]
    assert allow == (0x06, 0, 0, 0x7FFF0000)
    assert deny == (0x06, 0, 0, 0x00050000 | 1)
    assert sorted(k for _, _, _, k in jumps) == sorted(set(DENIED_SYSCALLS.values()))
    for index, (code, true_offset, false_offset, _number) in enumerate(jumps):
        assert code == 0x15
        assert false_offset == 0
        # pc after this jump is index+1; +true_offset must land on the deny record.
        assert index + 1 + true_offset == len(jumps) + 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"address_space_bytes": 1024},
        {"cpu_seconds": 0},
        {"open_files": 4},
        {"wall_clock_seconds": 0.0},
    ],
)
def test_limits_reject_nonsense(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must be"):
        WorkerLimits(**kwargs)  # type: ignore[arg-type]


def test_limits_forbid_file_writes_and_core_dumps() -> None:
    limits = WorkerLimits().rlimits()
    assert limits[resource.RLIMIT_FSIZE] == (0, 0)
    assert limits[resource.RLIMIT_CORE] == (0, 0)


def test_verify_limits_refuses_an_unlimited_process() -> None:
    # This test process runs without the worker's limits, as an unconfined worker would.
    with pytest.raises(ConfinementError, match="not applied"):
        verify_limits(WorkerLimits().as_parameters())


def test_install_filter_refuses_unsupported_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(confinement, "supported", lambda: False)
    with pytest.raises(ConfinementError, match="x86-64 only"):
        confinement.install_filter()
