#!/usr/bin/env python3
"""Internal fixed worker bootstrap. Never an agent-facing execution interface."""
import ctypes
import os
import sys


def main():
    if os.name != "posix" or os.geteuid() == 0 or len(sys.argv) < 4 or sys.argv[2] != "--":
        return 3
    import resource
    timeout = int(sys.argv[1])
    if not 1 <= timeout <= 300:
        return 3
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 2))
    # Linux workers cannot regain privilege through setid/file capabilities.
    if not sys.platform.startswith("linux") or ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        return 3
    os.execve(sys.argv[3], sys.argv[3:], os.environ)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
