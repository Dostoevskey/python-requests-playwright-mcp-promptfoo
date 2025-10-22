#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Iterable, Set

__all__ = ["ensure_ports_available", "ensure_port_available"]


def _collect_pids_with_lsof(port: int) -> Set[int]:
    if shutil.which("lsof") is None:
        return set()
    result = subprocess.run(
        ["lsof", "-nP", "-i", f"TCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        int(pid)
        for pid in result.stdout.strip().splitlines()
        if pid.strip().isdigit()
    }


def _collect_pids_with_ss(port: int) -> Set[int]:
    if shutil.which("ss") is None:
        return set()
    result = subprocess.run(
        ["ss", "-ltnp", f"sport = :{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: Set[int] = set()
    for line in result.stdout.splitlines():
        if "pid=" in line:
            try:
                pid_str = line.split("pid=")[1].split(",")[0]
                pids.add(int(pid_str))
            except (IndexError, ValueError):
                continue
    return pids


def _collect_pids_with_fuser(port: int) -> Set[int]:
    if shutil.which("fuser") is None:
        return set()
    result = subprocess.run(
        ["fuser", f"{port}/tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        int(pid)
        for pid in result.stdout.replace("\n", " ").split()
        if pid.strip().isdigit()
    }


def _collect_listeners(port: int) -> Set[int]:
    pids = set()
    for collector in (_collect_pids_with_lsof, _collect_pids_with_ss, _collect_pids_with_fuser):
        pids.update(collector(port))
    return pids


def ensure_port_available(port: int, logger, grace_period: float = 3.0) -> None:
    listeners = _collect_listeners(port)
    if not listeners:
        return

    logger.warning("Port %s is occupied by %s; attempting to terminate", port, ", ".join(map(str, listeners)))
    for pid in listeners:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            logger.error("Permission denied when terminating pid %s on port %s", pid, port)

    deadline = time.time() + grace_period
    remaining = {pid for pid in listeners if Path(f"/proc/{pid}").exists()}
    while remaining and time.time() < deadline:
        time.sleep(0.2)
        remaining = {pid for pid in remaining if Path(f"/proc/{pid}").exists()}

    for pid in list(remaining):
        logger.warning("Force killing pid %s on port %s", pid, port)
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue


def ensure_ports_available(ports: Iterable[int], logger) -> None:
    for port in ports:
        ensure_port_available(port, logger)
