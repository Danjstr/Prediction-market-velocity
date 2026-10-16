"""G-1 confinement: the seccomp allowlist, the resource limits, and parent hardening."""

import ctypes
import resource
import struct

import pytest

from pmv.acquisition import confinement
from pmv.acquisition.confinement import (
    ALLOWED_FCNTL,
    ALLOWED_IOCTL,
    ALLOWED_SYSCALLS,
    ConfinementError,
    WorkerLimits,
    filter_program,
    harden_parent,
    verify_limits,
)

# Calls a compromised worker could use against files, the network, or other processes,
# including the trusted parent (RT-B7-01). None may be on the allowlist.
NEVER_ALLOWED = {
    "open": 2,
    "openat": 257,
    "openat2": 437,
    "socket": 41,
    "connect": 42,
    "execve": 59,
    "fork": 57,
    "clone": 56,
    "clone3": 435,
    "ptrace": 101,
    "kill": 62,
    "tkill": 200,
    "tgkill": 234,
    "prlimit64": 302,
    "setrlimit": 160,
    "setpriority": 141,
    "sched_setaffinity": 203,
    "sched_setscheduler": 144,
    "sched_setattr": 314,
    "ioprio_set": 251,
    "move_pages": 279,
    "migrate_pages": 256,
    "get_robust_list": 274,
    "process_vm_writev": 311,
    "io_uring_setup": 425,
    "inotify_init1": 294,
    "fanotify_init": 300,
    "syslog": 103,
    "shmget": 29,
    "msgget": 68,
    "semget": 64,
    "getxattr": 191,
    "setxattr": 188,
    "memfd_create": 319,
    "prctl": 157,
    "unlinkat": 263,
    "fchmod": 91,
    "ftruncate": 77,
    "flock": 73,
    "pidfd_open": 434,
    "bpf": 321,
    "uselib": 134,
}
# fcntl commands and ioctl requests that act on other processes or inject input.
FORBIDDEN_FCNTL = {4, 8, 10, 15, 1024, 1026, 5, 6, 7}  # F_SETFL, SETOWN, SETSIG, ...
FORBIDDEN_IOCTL = {0x5412, 0x5421, 0x5452}  # TIOCSTI, FIONBIO, FIOASYNC


def test_the_allowlist_excludes_every_dangerous_call() -> None:
    allowed = set(ALLOWED_SYSCALLS.values())
    assert not allowed & set(NEVER_ALLOWED.values())
    assert confinement.FCNTL not in allowed
    assert confinement.IOCTL not in allowed
    assert not set(ALLOWED_FCNTL) & FORBIDDEN_FCNTL
    assert not set(ALLOWED_IOCTL) & FORBIDDEN_IOCTL


def _records(program: bytes) -> list[tuple[int, int, int, int]]:
    assert len(program) % 8 == 0
    return [struct.unpack("HBBI", program[i : i + 8]) for i in range(0, len(program), 8)]


def _run(program: bytes, nr: int, arg1: int = 0, arch: int = 0xC000003E) -> int:
    """A tiny classic-BPF interpreter for the subset the filter uses."""
    data = (
        struct.pack("<iI", nr, arch)
        + struct.pack("<Q", 0)
        + struct.pack("<6Q", 0, arg1, 0, 0, 0, 0)
    )
    records = _records(program)
    pc, acc = 0, 0
    for _ in range(10_000):
        code, jt, jf, k = records[pc]
        if code == 0x20:
            acc = struct.unpack_from("<I", data, k)[0]
        elif code == 0x15:
            pc += jt if acc == k else jf
        elif code == 0x35:
            pc += jt if acc >= k else jf
        elif code == 0x05:
            pc += k
        elif code == 0x04:
            acc = (acc + k) & 0xFFFFFFFF
        elif code == 0x44:
            acc |= k
        elif code == 0x06:
            return k
        elif code == 0x16:
            return acc
        else:
            raise AssertionError(f"unexpected BPF code {code:#x}")
        pc += 1
    raise AssertionError("BPF program did not terminate")


ALLOW, EPERM, KILL = 0x7FFF0000, 0x00050001, 0x80000000


def test_filter_allows_exactly_the_allowlist() -> None:
    program = filter_program()
    for number in ALLOWED_SYSCALLS.values():
        assert _run(program, number) == ALLOW
    for number in NEVER_ALLOWED.values():
        assert _run(program, number) == EPERM
    for number in range(0, 460):
        expected = ALLOW if number in ALLOWED_SYSCALLS.values() else None
        result = _run(program, number)
        if expected is not None:
            assert result == expected
        elif number not in (confinement.FCNTL, confinement.IOCTL):
            assert result == EPERM


def test_fcntl_and_ioctl_are_filtered_by_command() -> None:
    program = filter_program()
    for command in ALLOWED_FCNTL:
        assert _run(program, confinement.FCNTL, command) == ALLOW
    for command in FORBIDDEN_FCNTL:
        assert _run(program, confinement.FCNTL, command) == EPERM
    for request in ALLOWED_IOCTL:
        assert _run(program, confinement.IOCTL, request) == ALLOW
    for request in FORBIDDEN_IOCTL:
        assert _run(program, confinement.IOCTL, request) == EPERM
    # A high word in the command never matches an allowed low word.
    assert _run(program, confinement.FCNTL, (1 << 32) | 1) == EPERM


def test_other_architectures_and_x32_are_killed() -> None:
    program = filter_program()
    assert _run(program, 0, arch=0x40000003) == KILL  # i386
    assert _run(program, 0x40000000) == KILL
    assert _run(program, 0x40000000 + 2) == KILL


def test_diagnostic_program_reports_the_denied_number() -> None:
    program = filter_program(diagnostic=True)
    assert _run(program, 41) == 0x00050000 | (confinement.DIAGNOSTIC_ERRNO_BASE + 41)
    assert _run(program, 0) == ALLOW


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
    with pytest.raises(ConfinementError, match="not applied"):
        verify_limits(WorkerLimits().as_parameters())


def test_parent_hardening_disables_core_dumps() -> None:
    harden_parent()
    assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
    libc = ctypes.CDLL(None, use_errno=True)
    assert libc.prctl(3, 0, 0, 0, 0) == 0  # PR_GET_DUMPABLE


def test_install_filter_refuses_unsupported_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(confinement, "supported", lambda: False)
    with pytest.raises(ConfinementError, match="x86-64 only"):
        confinement.install_filter()
