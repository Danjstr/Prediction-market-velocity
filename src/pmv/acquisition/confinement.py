"""Kernel-enforced confinement for the isolated parse worker (G-1).

Two layers, both applied before the worker reads a byte of untrusted input:

1. **Resource limits, set by the trusted parent** (``WorkerLimits.apply``, run in the child
   between ``fork`` and ``exec``): address space, CPU seconds, zero file size (no regular
   file can be written or extended), a small descriptor count, and no core dumps (a core
   file could hold protected plaintext). The worker re-reads them at start and refuses to
   run if any is looser than the parent asked for. The parent also hardens itself
   (``harden_parent``): no core dumps and not dumpable, so even a disturbed parent cannot
   write its memory to disk.
2. **A seccomp allowlist, installed by the worker's trusted bootstrap** (``install_filter``)
   after its imports and warm-up and before it reads input, with ``no_new_privs`` set
   first. Only the syscalls in ``ALLOWED_SYSCALLS`` run: reading and seeking its
   descriptors, writing, memory management, ``futex``, signal masks on itself, clocks,
   ``getrandom``, ``fstat``-family calls, ``close``, and exit. ``fcntl`` is allowed only for
   ``F_GETFD``, ``F_SETFD``, ``F_GETFL``, and ``F_DUPFD_CLOEXEC`` (so no ``F_SETOWN``,
   ``F_SETSIG``, ``O_ASYNC``, leases, notifications, or locks), and ``ioctl`` only for
   ``TCGETS``, ``FIOCLEX``, and ``FIONCLEX``. Everything else fails with ``EPERM``: opening or
   changing any file, every socket call, ``exec``, ``fork``, ``clone``, ``io_uring``,
   ``ptrace``, signals and resource or scheduling changes to any process (including the
   parent: ``kill``, ``prlimit64``, ``setpriority``, ``sched_set*``, ``ioprio_set``), inotify,
   ``syslog``, SysV IPC, extended attributes, and every other syscall. Any architecture other
   than x86-64, and the x32 syscall ABI, kills the process. A seccomp filter cannot be
   removed.

**What this does not do.** ``fstat``-family calls (``newfstatat``, ``statx``) are allowed,
because the C library implements ``fstat`` with them; with a path argument they reveal
file metadata (existence, size, times, owner), never content. There is no network
namespace: network isolation rests on every socket call being denied. The worker runs as
the same user as the parent, so filesystem permissions are not an extra boundary. It is
supported on Linux x86-64 only; elsewhere ``install_filter`` raises and the parent refuses
to parse (fail closed).
"""

import ctypes
import errno
import platform
import resource
import struct
import sys
from dataclasses import dataclass
from typing import Final

_PR_SET_DUMPABLE: Final = 4
_PR_SET_NO_NEW_PRIVS: Final = 38
_PR_GET_NO_NEW_PRIVS: Final = 39
_PR_SET_SECCOMP: Final = 22
_SECCOMP_MODE_FILTER: Final = 2
_AUDIT_ARCH_X86_64: Final = 0xC000003E
_X32_SYSCALL_BIT: Final = 0x40000000
_RET_KILL_PROCESS: Final = 0x80000000
_RET_ERRNO: Final = 0x00050000
_RET_ALLOW: Final = 0x7FFF0000
_BPF_LD_W_ABS: Final = 0x20
_BPF_JEQ_K: Final = 0x15
_BPF_JGE_K: Final = 0x35
_BPF_JA: Final = 0x05
_BPF_RET_K: Final = 0x06
_BPF_RET_A: Final = 0x16
_BPF_ALU_ADD_K: Final = 0x04
_BPF_ALU_OR_K: Final = 0x44
_SECCOMP_DATA_NR: Final = 0
_SECCOMP_DATA_ARCH: Final = 4
_SECCOMP_DATA_ARG1_LOW: Final = 24
_SECCOMP_DATA_ARG1_HIGH: Final = 28
# A diagnostic-only errno base: denied syscall N fails with errno DIAGNOSTIC_ERRNO_BASE + N.
DIAGNOSTIC_ERRNO_BASE: Final = 2000

# x86-64 syscall numbers (linux/arch/x86/entry/syscalls/syscall_64.tbl).
ALLOWED_SYSCALLS: Final[dict[str, int]] = {
    "read": 0,
    "write": 1,
    "close": 3,
    "fstat": 5,
    "lseek": 8,
    "mmap": 9,
    "mprotect": 10,
    "munmap": 11,
    "brk": 12,
    "rt_sigaction": 13,
    "rt_sigprocmask": 14,
    "rt_sigreturn": 15,
    "pread64": 17,
    "readv": 19,
    "writev": 20,
    "sched_yield": 24,
    "mremap": 25,
    "madvise": 28,
    "getpid": 39,
    "exit": 60,
    "getrlimit": 97,
    "sigaltstack": 131,
    "gettid": 186,
    "futex": 202,
    "clock_gettime": 228,
    "clock_getres": 229,
    "clock_nanosleep": 230,
    "exit_group": 231,
    "newfstatat": 262,
    "getrandom": 318,
    "statx": 332,
}
FCNTL: Final = 72
IOCTL: Final = 16
# fcntl commands: F_GETFD, F_SETFD, F_GETFL, F_DUPFD_CLOEXEC.
ALLOWED_FCNTL: Final = (1, 2, 3, 1030)
# ioctl requests: TCGETS (isatty), FIONCLEX, FIOCLEX.
ALLOWED_IOCTL: Final = (0x5401, 0x5450, 0x5451)


class ConfinementError(Exception):
    """Confinement could not be applied or verified. The worker must not parse."""


@dataclass(frozen=True, slots=True)
class WorkerLimits:
    """Resource limits the parent applies to the worker process before it starts."""

    address_space_bytes: int = 512 * 1024 * 1024
    cpu_seconds: int = 120
    open_files: int = 32
    wall_clock_seconds: float = 300.0

    def __post_init__(self) -> None:
        if not (64 * 1024 * 1024 <= self.address_space_bytes <= 16 * 1024**3):
            raise ValueError("address_space_bytes must be between 64 MiB and 16 GiB")
        if not (1 <= self.cpu_seconds <= 24 * 3600):
            raise ValueError("cpu_seconds must be between 1 and 86400")
        if not (8 <= self.open_files <= 256):
            raise ValueError("open_files must be between 8 and 256")
        if not (0 < self.wall_clock_seconds <= 24 * 3600):
            raise ValueError("wall_clock_seconds must be positive and at most a day")

    def rlimits(self) -> dict[int, tuple[int, int]]:
        return {
            resource.RLIMIT_AS: (self.address_space_bytes, self.address_space_bytes),
            resource.RLIMIT_CPU: (self.cpu_seconds, self.cpu_seconds + 1),
            resource.RLIMIT_FSIZE: (0, 0),
            resource.RLIMIT_NOFILE: (self.open_files, self.open_files),
            resource.RLIMIT_CORE: (0, 0),
        }

    def apply(self) -> None:
        """Set every limit on the current process. Runs in the child before ``exec``."""
        for which, value in self.rlimits().items():
            resource.setrlimit(which, value)

    def as_parameters(self) -> dict[str, int]:
        return {
            "address_space_bytes": self.address_space_bytes,
            "cpu_seconds": self.cpu_seconds,
            "open_files": self.open_files,
        }


def verify_limits(expected: dict[str, int]) -> None:
    """Refuse unless every limit of this process is at least as strict as ``expected``."""
    limits = WorkerLimits(
        address_space_bytes=expected["address_space_bytes"],
        cpu_seconds=expected["cpu_seconds"],
        open_files=expected["open_files"],
    )
    for which, (soft, hard) in limits.rlimits().items():
        actual_soft, actual_hard = resource.getrlimit(which)
        for actual, wanted in ((actual_soft, soft), (actual_hard, hard)):
            if actual == resource.RLIM_INFINITY or actual > wanted:
                raise ConfinementError("a resource limit was not applied")


def harden_parent() -> None:
    """Make the calling (trusted) process unable to dump core, permanently (RT-B7-01).

    A disturbed parent must never write its memory, which can hold protected plaintext, to
    disk. Sets ``RLIMIT_CORE`` to zero (soft and hard) and clears the dumpable flag, which
    also stops same-user processes from tracing it. Idempotent; affects only this process.
    """
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform == "linux":
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(_PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
            raise ConfinementError("the parent could not be made non-dumpable")


def filter_program(*, diagnostic: bool = False) -> bytes:
    """The seccomp BPF program, as packed ``struct sock_filter`` records.

    ``diagnostic`` (development only, never used by the worker) makes a denied syscall fail
    with errno ``DIAGNOSTIC_ERRNO_BASE + number`` instead of ``EPERM``, to identify it.
    """
    program: list[tuple[int, int, int, int] | tuple[str, str, str, int]] = []

    def op(code: int, k: int) -> None:
        program.append((code, 0, 0, k))

    def branch(code: int, k: int, true_label: str, false_label: str) -> None:
        program.append(("branch", true_label, false_label, (code << 32) | k))

    labels: dict[str, int] = {}

    def label(name: str) -> None:
        labels[name] = len(program)

    op(_BPF_LD_W_ABS, _SECCOMP_DATA_ARCH)
    branch(_BPF_JEQ_K, _AUDIT_ARCH_X86_64, "next", "kill")
    op(_BPF_LD_W_ABS, _SECCOMP_DATA_NR)
    branch(_BPF_JGE_K, _X32_SYSCALL_BIT, "kill", "next")
    for number in sorted(set(ALLOWED_SYSCALLS.values())):
        branch(_BPF_JEQ_K, number, "allow", "next")
    branch(_BPF_JEQ_K, FCNTL, "fcntl", "next")
    branch(_BPF_JEQ_K, IOCTL, "ioctl", "next")
    label("deny_nr")
    if diagnostic:
        op(_BPF_ALU_ADD_K, DIAGNOSTIC_ERRNO_BASE)
        op(_BPF_ALU_OR_K, _RET_ERRNO)
        op(_BPF_RET_A, 0)
    else:
        op(_BPF_RET_K, _RET_ERRNO | errno.EPERM)
    for name, commands in (("fcntl", ALLOWED_FCNTL), ("ioctl", ALLOWED_IOCTL)):
        label(name)
        op(_BPF_LD_W_ABS, _SECCOMP_DATA_ARG1_HIGH)
        branch(_BPF_JEQ_K, 0, "next", "deny")
        op(_BPF_LD_W_ABS, _SECCOMP_DATA_ARG1_LOW)
        for command in commands:
            branch(_BPF_JEQ_K, command, "allow", "next")
        program.append(("jump", "deny", "", 0))
    label("deny")
    op(_BPF_RET_K, _RET_ERRNO | errno.EPERM)
    label("allow")
    op(_BPF_RET_K, _RET_ALLOW)
    label("kill")
    op(_BPF_RET_K, _RET_KILL_PROCESS)

    encoded: list[bytes] = []
    for index, item in enumerate(program):
        if item[0] == "branch":
            _, true_label, false_label, packed = item
            code, k = int(packed) >> 32, int(packed) & 0xFFFFFFFF
            offsets = []
            for target in (true_label, false_label):
                offset = 0 if target == "next" else labels[str(target)] - index - 1
                if not 0 <= offset <= 255:
                    raise ConfinementError("seccomp jump out of range")
                offsets.append(offset)
            encoded.append(struct.pack("HBBI", code, offsets[0], offsets[1], k))
        elif item[0] == "jump":
            offset = labels[str(item[1])] - index - 1
            encoded.append(struct.pack("HBBI", _BPF_JA, 0, 0, offset))
        else:
            code, jt, jf, k = (int(value) for value in item)
            encoded.append(struct.pack("HBBI", code, jt, jf, k))
    return b"".join(encoded)


class _SockFprog(ctypes.Structure):
    _fields_ = (("len", ctypes.c_ushort), ("filter", ctypes.c_void_p))


def supported() -> bool:
    return sys.platform == "linux" and platform.machine() == "x86_64"


def install_filter(*, diagnostic: bool = False) -> None:
    """Set ``no_new_privs`` and install the seccomp allowlist on this process. Irreversible."""
    if not supported():
        raise ConfinementError("seccomp confinement is supported on Linux x86-64 only")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise ConfinementError("no_new_privs could not be set")
    if libc.prctl(_PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) != 1:
        raise ConfinementError("no_new_privs is not set")
    program = filter_program(diagnostic=diagnostic)
    buffer = ctypes.create_string_buffer(program, len(program))
    fprog = _SockFprog(len(program) // 8, ctypes.cast(buffer, ctypes.c_void_p))
    if libc.prctl(_PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0) != 0:
        raise ConfinementError("the seccomp filter could not be installed")
    # prctl itself is now denied; prove the filter is active by a call it must refuse.
    libc.syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    status = libc.syscall(
        ctypes.c_long(41), ctypes.c_long(9999), ctypes.c_long(0), ctypes.c_long(0)
    )
    expected = errno.EPERM if not diagnostic else DIAGNOSTIC_ERRNO_BASE + 41
    if status != -1 or ctypes.get_errno() != expected:
        raise ConfinementError("the seccomp filter is not active")


# Side-effect-free probes: each call is denied (EPERM) under the filter, and otherwise
# fails with a different errno or is a harmless query. None can change anything.
_PROBES: Final[dict[str, tuple[int, tuple[int, ...]]]] = {
    "open": (2, (0, 0, 0)),
    "openat": (257, (-100, 0, 0, 0)),
    "openat2": (437, (-100, 0, 0, 0)),
    "socket": (41, (9999, 0, 0)),
    "connect": (42, (-1, 0, 0)),
    "execve": (59, (0, 0, 0)),
    "execveat": (322, (-1, 0, 0, 0, 0)),
    "clone": (56, (0x800, 0, 0, 0, 0)),
    "clone3": (435, (0, 0)),
    "io_uring_setup": (425, (0, 0)),
    "unlinkat": (263, (-1, 0, 0)),
    "fchmod": (91, (-1, 0)),
    "kill": (62, (0, 0x7FFFFFFF)),
    "ptrace": (101, (-1, 0, 0, 0)),
    "prlimit64": (302, (0, 4, 0, 0)),
    "setpriority": (141, (99, 0, 0)),
    "sched_setaffinity": (203, (0, 0, 0)),
    "ioprio_set": (251, (99, 0, 0)),
    "fcntl_setsig": (72, (-1, 10, 0)),
    "fcntl_setown": (72, (-1, 8, 0)),
    "fcntl_setfl": (72, (-1, 4, 0)),
    "ioctl_tiocsti": (16, (-1, 0x5412, 0)),
    "inotify_init1": (294, (0x7FFFFFFF,)),
    "syslog": (103, (-1, 0, 0)),
    "shmget": (29, (0, 0, 0)),
    "getxattr": (191, (0, 0, 0, 0)),
    "rt_sigqueueinfo": (129, (0, 0, 0)),
    "memfd_create": (319, (0, 0)),
}


def probe() -> dict[str, bool]:
    """Report, for each probe, whether the kernel denied it with EPERM."""
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    results: dict[str, bool] = {}
    for name, (number, arguments) in _PROBES.items():
        ctypes.set_errno(0)
        status = libc.syscall(ctypes.c_long(number), *(ctypes.c_long(a) for a in arguments))
        results[name] = status == -1 and ctypes.get_errno() == errno.EPERM
    return results


def probe_names() -> tuple[str, ...]:
    return tuple(_PROBES)
