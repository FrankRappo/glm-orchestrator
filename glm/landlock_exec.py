#!/usr/bin/env python3
"""Run a command under a bounded Linux Landlock ruleset.

This is defense in depth, not an absolute security boundary, a container, or a
hostname/network-protocol filter.  Landlock restrictions apply to the executed
process and its descendants; they do not alter the caller or other processes.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import platform
import resource
import stat
import sys


SYS_CREATE_RULESET = 444
SYS_ADD_RULE = 445
SYS_RESTRICT_SELF = 446
CREATE_VERSION = 1
RULE_PATH_BENEATH = 1
RULE_NET_PORT = 2
PR_SET_NO_NEW_PRIVS = 38

FS_EXECUTE = 1 << 0
FS_WRITE_FILE = 1 << 1
FS_READ_FILE = 1 << 2
FS_READ_DIR = 1 << 3
FS_REMOVE_DIR = 1 << 4
FS_REMOVE_FILE = 1 << 5
FS_MAKE_CHAR = 1 << 6
FS_MAKE_DIR = 1 << 7
FS_MAKE_REG = 1 << 8
FS_MAKE_SOCK = 1 << 9
FS_MAKE_FIFO = 1 << 10
FS_MAKE_BLOCK = 1 << 11
FS_MAKE_SYM = 1 << 12
FS_REFER = 1 << 13
FS_TRUNCATE = 1 << 14
FS_IOCTL_DEV = 1 << 15
FS_V1 = (1 << 13) - 1
FS_WRITE_DIR = (
    FS_WRITE_FILE | FS_REMOVE_DIR | FS_REMOVE_FILE | FS_MAKE_CHAR | FS_MAKE_DIR
    | FS_MAKE_REG | FS_MAKE_SOCK | FS_MAKE_FIFO | FS_MAKE_BLOCK | FS_MAKE_SYM
)
NET_BIND_TCP = 1 << 0
NET_CONNECT_TCP = 1 << 1
SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0
SCOPE_SIGNAL = 1 << 1


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


class NetPortAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("port", ctypes.c_uint64)]


LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.syscall.restype = ctypes.c_long
LIBC.prctl.restype = ctypes.c_int


def _fail(message: str) -> "NoReturn":
    print(f"landlock-exec: {message}", file=sys.stderr)
    raise SystemExit(2)


def _syscall(number: int, *args: object) -> int:
    result = LIBC.syscall(number, *args)
    if result < 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))
    return int(result)


def _platform_ok() -> bool:
    return sys.platform.startswith("linux") and platform.machine().lower() in {"x86_64", "amd64"}


def _abi() -> int:
    if not _platform_ok():
        raise OSError(errno.ENOSYS, "Landlock wrapper supports Linux x86_64 only")
    return _syscall(SYS_CREATE_RULESET, 0, 0, CREATE_VERSION)


def _fs_mask(abi: int) -> int:
    mask = FS_V1
    if abi >= 2:
        mask |= FS_REFER
    if abi >= 3:
        mask |= FS_TRUNCATE
    if abi >= 5:
        mask |= FS_IOCTL_DEV
    return mask


def _open_path(path: str) -> tuple[str, int, int]:
    if not path.startswith("/") or os.path.normpath(path) != path:
        _fail(f"path must be absolute and canonical: {path!r}")
    if path == "/":
        _fail("refusing a rule for filesystem root '/'")
    fd = os.open("/", os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = path[1:].split("/")
        for index, part in enumerate(parts):
            new_fd = os.open(part, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = new_fd
            mode = os.fstat(fd).st_mode
            if stat.S_ISLNK(mode):
                _fail(f"symlink path component is not allowed: {path!r}")
            if index != len(parts) - 1 and not stat.S_ISDIR(mode):
                _fail(f"non-directory path component: {path!r}")
        return path, fd, os.fstat(fd).st_mode
    except BaseException:
        os.close(fd)
        raise


def _probe() -> int:
    try:
        abi = _abi()
    except OSError as exc:
        print(json.dumps({"supported": False, "executable_supported": False,
                          "abi": None, "filesystem": False, "network_tcp": False,
                          "scoping": False, "error": exc.strerror}, sort_keys=True))
        return 1
    print(json.dumps({"supported": abi >= 1, "executable_supported": abi >= 6,
                      "abi": abi, "filesystem": abi >= 1,
                      "network_tcp": abi >= 4, "scoping": abi >= 6}, sort_keys=True))
    return 0 if abi >= 6 else 1


def _add_path_rule(ruleset_fd: int, fd: int, mode: int, writable: bool, fs_mask: int) -> None:
    if stat.S_ISDIR(mode):
        access = FS_EXECUTE | FS_READ_FILE | FS_READ_DIR
        if writable:
            access |= FS_WRITE_DIR | FS_REFER | FS_TRUNCATE | FS_IOCTL_DEV
    else:
        access = FS_EXECUTE | FS_READ_FILE
        if writable:
            access |= FS_WRITE_FILE | FS_TRUNCATE | FS_IOCTL_DEV
    attr = PathBeneathAttr(access & fs_mask, fd)
    _syscall(SYS_ADD_RULE, ruleset_fd, RULE_PATH_BENEATH, ctypes.byref(attr), 0)


def _install(read_only: list[str], read_write: list[str], ports: list[int]) -> None:
    if os.geteuid() == 0:
        _fail("refusing to sandbox-exec with effective UID 0")
    try:
        abi = _abi()
    except OSError as exc:
        _fail(f"Landlock unavailable: {exc}")
    if abi < 6:
        _fail(f"execution requires Landlock ABI 6 or newer for process scoping (kernel reports {abi})")
    if ports and abi < 4:
        _fail(f"TCP restrictions require Landlock ABI 4 or newer (kernel reports {abi})")

    # A descriptor opened by the caller can retain access outside the ruleset.
    # Preserve only standard input/output/error before opening our rule FDs.
    soft_limit = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
    os.closerange(3, 1_048_576 if soft_limit == resource.RLIM_INFINITY else soft_limit)

    opened: list[tuple[int, int, bool]] = []
    try:
        for writable, paths in ((False, read_only), (True, read_write)):
            for path in paths:
                try:
                    _, fd, mode = _open_path(path)
                except OSError as exc:
                    _fail(f"cannot safely open {path!r}: {exc}")
                opened.append((fd, mode, writable))

        fs_mask = _fs_mask(abi)
        attr = RulesetAttr(fs_mask, NET_BIND_TCP | NET_CONNECT_TCP if ports else 0,
                           SCOPE_ABSTRACT_UNIX_SOCKET | SCOPE_SIGNAL if abi >= 6 else 0)
        attr_size = 24 if abi >= 6 else (16 if abi >= 4 else 8)
        ruleset_fd = _syscall(SYS_CREATE_RULESET, ctypes.byref(attr), attr_size, 0)
        try:
            for fd, mode, writable in opened:
                _add_path_rule(ruleset_fd, fd, mode, writable, fs_mask)
            for port in ports:
                net_attr = NetPortAttr(NET_CONNECT_TCP, port)
                _syscall(SYS_ADD_RULE, ruleset_fd, RULE_NET_PORT, ctypes.byref(net_attr), 0)
            if LIBC.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code))
            _syscall(SYS_RESTRICT_SELF, ruleset_fd, 0)
        finally:
            os.close(ruleset_fd)
    finally:
        for fd, _, _ in opened:
            os.close(fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute a command with an allowlist-based Landlock ruleset.",
        epilog=("Limits: defense in depth only; this is not a container, an absolute security "
                "guarantee, or a hostname/network-protocol filter. Landlock does not mediate "
                "file metadata changes (including chmod, chown, xattrs, timestamps, or stat), "
                "pathname Unix sockets, or UDP. TCP ports are numeric. Use a dedicated UID or "
                "stronger isolation where those limits matter."),
    )
    parser.add_argument("--probe", action="store_true", help="print kernel support JSON and exit")
    parser.add_argument("--read-only", action="append", default=[], metavar="PATH")
    parser.add_argument("--read-write", action="append", default=[], metavar="PATH")
    parser.add_argument("--connect-port", action="append", default=[], type=int, metavar="PORT")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(args_list)
    if args.probe:
        if args.read_only or args.read_write or args.connect_port or args.command:
            _fail("--probe cannot be combined with sandbox rules or a command")
        return _probe()
    if "--" not in args_list or not args.command:
        _fail("a nonempty command after '--' is required")
    command = args.command[1:] if args.command[0] == "--" else args.command
    if not command:
        _fail("a nonempty command after '--' is required")
    for port in args.connect_port:
        if not 1 <= port <= 65535:
            _fail(f"TCP port out of range: {port}")
    _install(args.read_only, args.read_write, args.connect_port)
    os.execvp(command[0], command)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
