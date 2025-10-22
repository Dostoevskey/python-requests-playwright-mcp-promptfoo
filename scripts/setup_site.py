#!/usr/bin/env python3
"""Utility helpers to prepare or tear down the local demo site."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.logger import configure_logging, get_logger  # noqa: E402
from scripts.port_utils import ensure_ports_available  # noqa: E402


def _unique_ports(values: Iterable[int]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _gather_ports(args: argparse.Namespace) -> list[int]:
    candidates: list[int] = []
    for value in args.ports or []:
        candidates.append(value)

    api_port = os.getenv("API_PORT")
    frontend_port = os.getenv("FRONTEND_PORT")
    if not candidates:
        if api_port and api_port.isdigit():
            candidates.append(int(api_port))
        if frontend_port and frontend_port.isdigit():
            candidates.append(int(frontend_port))
    return _unique_ports(candidates)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices={"prepare", "start", "stop"}, help="What to do with the demo site")
    parser.add_argument("--env-file", default="config/demo.env", help="Path to env file with port settings")
    parser.add_argument("--ports", nargs="*", type=int, help="Override ports to validate/clean up")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout for server readiness when starting")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(force=True)
    logger = get_logger("setup_site")

    if args.env_file and Path(args.env_file).exists():
        load_dotenv(args.env_file, override=True)
        logger.info("Loaded environment from %s", args.env_file)

    ports = _gather_ports(args)
    if ports:
        logger.info("Ensuring ports available: %s", ports)
        ensure_ports_available(ports, logger)

    if args.action == "prepare":
        return

    manage_script = ROOT_DIR / "scripts" / "manage_demo_servers.py"
    command = [sys.executable, str(manage_script), args.action, "--env-file", args.env_file]
    if args.action == "start":
        command += ["--timeout", str(args.timeout)]
    logger.info("Executing %s", " ".join(command))
    subprocess.check_call(command)


if __name__ == "__main__":
    main()
