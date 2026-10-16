"""Kernel-enforced confinement for the isolated parse worker (G-1).

Two layers, both applied before the worker reads a byte of untrusted input:

1. **Resource limits, set by the trusted parent** (``WorkerLimits.apply``, run in the child
   between ``fork`` and ``exec``): address space, CPU seconds, zero file size (no regular
   file can be written or extended), a small descriptor count, and no core dumps (a core
   file could hold protected plaintext). The worker re-reads them at start and refuses to
   run if any is looser than the parent asked for.
2. **A seccomp filter, installed by the worker's trusted bootstrap** (``install_filter``)
   after its imports and before it reads input, with ``no_new_privs`` set first. It denies
   every syscall in ``DENIED_SYSCALLS`` with ``EPERM``: opening, creating, renaming,
   linking, or deleting any file; changing modes, owners, or timestamps; every socket
   call; ``exec``, ``fork``, and ``clone``; ``io_uring`` (which could open files outside the
   filter); ``ptrace`` and cross-process memory access; signals to other processes;
   namespace, mount, module, key, and BPF calls. Any architecture other than x86-64, and
   the x32 syscall ABI, kills the process. A seccomp filter cannot be removed.

**What this does not do.** It is a denylist, not an allowlist: a syscall not listed is
allowed. It does not hide the filesystem's metadata (``stat`` still works), so a
compromised worker can learn whether a path exists, but it cannot open, read, or write a
file other than the descriptors it inherited (the input, opened read-only, and the
output pipe). It does not create a network namespace; network isolation rests on the
socket denial. It is supported on Linux x86-64 only; elsewhere ``install_filter`` raises
and the parent refuses to parse (fail closed). The worker runs as the same user as the
parent, so filesystem permissions are not an extra boundary.
"""

import ctypes
import errno
import platform
import resource
import struct
import sys
from dataclasses import dataclass
from typing import Final

_PR_SET_NO_NEW_PRIVS: Final = 38
_PR_GET_NO_NEW_PRIVS: Final = 39
_PR_SET_SECCOMP: Final = 22
_PR_GET_SECCOMP: Final = 21
_SECCOMP_MODE_FILTER: Final = 2
_AUDIT_ARCH_X86_64: Final = 0xC000003E
_X32_SYSCALL_BIT: Final = 0x40000000
_RET_KILL_PROCESS: Final = 0x80000000
_RET_ERRNO: Final = 0x00050000
_RET_ALLOW: Final = 0x7FFF0000
_BPF_LD_W_ABS: Final = 0x20
_BPF_JEQ_K: Final = 0x15
_BPF_JGE_K: Final = 0x35
_BPF_RET_K: Final = 0x06
_SECCOMP_DATA_NR: Final = 0
_SECCOMP_DATA_ARCH: Final = 4

# x86-64 syscall numbers (linux/arch/x86/entry/syscalls/syscall_64.tbl).
DENIED_SYSCALLS: Final[dict[str, int]] = {
    # files: open, create, rename, link, delete, change
    "open": 2,
    "creat": 85,
    "openat": 257,
    "openat2": 437,
    "open_by_handle_at": 304,
    "name_to_handle_at": 303,
    "open_tree": 428,
    "mkdir": 83,
    "mkdirat": 258,
    "mknod": 133,
    "mknodat": 259,
    "rmdir": 84,
    "unlink": 87,
    "unlinkat": 263,
    "rename": 82,
    "renameat": 264,
    "renameat2": 316,
    "link": 86,
    "linkat": 265,
    "symlink": 88,
    "symlinkat": 266,
    "truncate": 76,
    "ftruncate": 77,
    "fallocate": 285,
    "chmod": 90,
    "fchmod": 91,
    "fchmodat": 268,
    "fchmodat2": 452,
    "chown": 92,
    "fchown": 93,
    "lchown": 94,
    "fchownat": 260,
    "utime": 132,
    "utimes": 235,
    "futimesat": 261,
    "utimensat": 280,
    "setxattr": 188,
    "lsetxattr": 189,
    "fsetxattr": 190,
    "removexattr": 197,
    "lremovexattr": 198,
    "fremovexattr": 199,
    "flock": 73,
    "memfd_create": 319,
    "memfd_secret": 447,
    "userfaultfd": 323,
    # network
    "socket": 41,
    "connect": 42,
    "accept": 43,
    "sendto": 44,
    "recvfrom": 45,
    "sendmsg": 46,
    "recvmsg": 47,
    "bind": 49,
    "listen": 50,
    "socketpair": 53,
    "accept4": 288,
    "recvmmsg": 299,
    "sendmmsg": 307,
    # processes
    "clone": 56,
    "fork": 57,
    "vfork": 58,
    "execve": 59,
    "execveat": 322,
    "clone3": 435,
    "ptrace": 101,
    "process_vm_readv": 310,
    "process_vm_writev": 311,
    "process_madvise": 440,
    "kcmp": 312,
    "kill": 62,
    "tkill": 200,
    "tgkill": 234,
    "rt_sigqueueinfo": 129,
    "rt_tgsigqueueinfo": 297,
    "pidfd_open": 434,
    "pidfd_getfd": 438,
    "pidfd_send_signal": 424,
    # io_uring can perform opens and network I/O outside this filter
    "io_uring_setup": 425,
    "io_uring_enter": 426,
    "io_uring_register": 427,
    # namespaces, mounts, privileges, kernel state
    "unshare": 272,
    "setns": 308,
    "mount": 165,
    "umount2": 166,
    "pivot_root": 155,
    "chroot": 161,
    "move_mount": 429,
    "fsopen": 430,
    "fsconfig": 431,
    "fsmount": 432,
    "fspick": 433,
    "init_module": 175,
    "finit_module": 313,
    "delete_module": 176,
    "kexec_load": 246,
    "kexec_file_load": 320,
    "bpf": 321,
    "perf_event_open": 298,
    "add_key": 248,
    "request_key": 249,
    "keyctl": 250,
    "acct": 163,
    "swapon": 167,
    "swapoff": 168,
    "reboot": 169,
    "iopl": 172,
    "ioperm": 173,
    "shmget": 29,
    "msgget": 68,
    "semget": 64,
    "mq_open": 240,
}


class ConfinementError(Exception):
    """Confinement could not be applied or verified. The worker must not parse."""


@dataclass(frozen=True, slots=True)
class WorkerLimits:
    """Resource limits the parent applies to the worker process before it starts."""

    address_space_bytes: int = 768 * 1024 * 1024
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


def filter_program() -> bytes:
    """The seccomp BPF program, as packed ``struct sock_filter`` records."""

    def statement(code: int, k: int) -> bytes:
        return struct.pack("HBBI", code, 0, 0, k)

    def jump(code: int, k: int, true_offset: int, false_offset: int) -> bytes:
        return struct.pack("HBBI", code, true_offset, false_offset, k)

    numbers = sorted(set(DENIED_SYSCALLS.values()))
    count = len(numbers)
    if count > 250:
        raise ConfinementError("too many denied syscalls for one jump table")
    program = [
        statement(_BPF_LD_W_ABS, _SECCOMP_DATA_ARCH),
        jump(_BPF_JEQ_K, _AUDIT_ARCH_X86_64, 1, 0),
        statement(_BPF_RET_K, _RET_KILL_PROCESS),
        statement(_BPF_LD_W_ABS, _SECCOMP_DATA_NR),
        jump(_BPF_JGE_K, _X32_SYSCALL_BIT, 0, 1),
        statement(_BPF_RET_K, _RET_KILL_PROCESS),
    ]
    # Each JEQ jumps over the remaining JEQs and the ALLOW to the final ERRNO.
    for index, number in enumerate(numbers):
        program.append(jump(_BPF_JEQ_K, number, count - index, 0))
    program.append(statement(_BPF_RET_K, _RET_ALLOW))
    program.append(statement(_BPF_RET_K, _RET_ERRNO | errno.EPERM))
    return b"".join(program)


class _SockFprog(ctypes.Structure):
    _fields_ = (("len", ctypes.c_ushort), ("filter", ctypes.c_void_p))


def supported() -> bool:
    return sys.platform == "linux" and platform.machine() == "x86_64"


def install_filter() -> None:
    """Set ``no_new_privs`` and install the seccomp filter on this process. Irreversible."""
    if not supported():
        raise ConfinementError("seccomp confinement is supported on Linux x86-64 only")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise ConfinementError("no_new_privs could not be set")
    program = filter_program()
    buffer = ctypes.create_string_buffer(program, len(program))
    fprog = _SockFprog(len(program) // 8, ctypes.cast(buffer, ctypes.c_void_p))
    if libc.prctl(_PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0) != 0:
        raise ConfinementError("the seccomp filter could not be installed")
    if libc.prctl(_PR_GET_NO_NEW_PRIVS, 0, 0, 0, 0) != 1:
        raise ConfinementError("no_new_privs is not set")
    if libc.prctl(_PR_GET_SECCOMP, 0, 0, 0, 0) != _SECCOMP_MODE_FILTER:
        raise ConfinementError("the seccomp filter is not active")


# Side-effect-free probes: each call is denied (EPERM) under the filter, and otherwise
# fails with a different errno because its arguments are invalid. None can succeed.
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
