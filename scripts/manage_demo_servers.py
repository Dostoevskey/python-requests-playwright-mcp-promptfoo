#!/usr/bin/env python3
"""Manage the demo application's frontend and backend dev servers."""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.logger import configure_logging, get_logger  # noqa: E402
from scripts.port_utils import ensure_ports_available  # noqa: E402

STATE_DIR = ROOT_DIR / ".demo-app-cache"
STATE_FILE = STATE_DIR / "demo_servers.json"
LOG_DIR = ROOT_DIR / "logs"
DEMO_SRC_DIR = ROOT_DIR / "demo-app" / "src"


@dataclass
class ServerProcess:
    name: str
    command: list[str]
    env: dict[str, str]
    log_path: Path
    health_url: str


def read_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def write_state(data: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2))


def remove_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def start_server(proc: ServerProcess, logger) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = proc.log_path.open("ab")
    logger.info("Starting %s with command: %s", proc.name, " ".join(proc.command))
    process = subprocess.Popen(
        proc.command,
        cwd=DEMO_SRC_DIR,
        env=proc.env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return process.pid


def wait_for_health(url: str, timeout: float, logger) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if response.ok:
                logger.debug("Health check succeeded for %s", url)
                return True
        except requests.RequestException:
            time.sleep(1)
            continue
        time.sleep(1)
    logger.error("Timed out waiting for %s", url)
    return False


def start(env_file: Path, timeout: float) -> None:
    configure_logging(force=True)
    logger = get_logger("manage_servers")
    if not env_file.exists():
        logger.error("Environment file %s not found", env_file)
        raise SystemExit(1)

    load_dotenv(env_file, override=True)
    configure_logging(force=True)
    logger.info("Loaded environment from %s", env_file)

    current_state = read_state()
    if current_state:
        logger.warning("Servers already appear to be running (state file: %s)", STATE_FILE)
        raise SystemExit(1)

    api_port = os.getenv("API_PORT", "3001")
    frontend_port = os.getenv("FRONTEND_PORT", "3000")

    def _port(value: str, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning("Invalid port value '%s'; falling back to %s", value, fallback)
            return fallback

    base_env = os.environ.copy()
    base_env.setdefault("NODE_ENV", "development")

    backend_env = base_env.copy()
    backend_env["PORT"] = api_port

    frontend_env = base_env.copy()
    frontend_env["FRONTEND_PORT"] = frontend_port
    frontend_env.setdefault("BROWSER", "none")

    logger.debug("Using backend port %s and frontend port %s", api_port, frontend_port)

    processes = [
        ServerProcess(
            name="backend",
            command=["npm", "run", "dev", "-w", "backend"],
            env=backend_env,
            log_path=LOG_DIR / "backend-dev.log",
            health_url=os.getenv("BACKEND_HEALTH_ENDPOINT", f"http://localhost:{api_port}/api/articles"),
        ),
        ServerProcess(
            name="frontend",
            command=["npm", "run", "dev", "-w", "frontend"],
            env=frontend_env,
            log_path=LOG_DIR / "frontend-dev.log",
            health_url=os.getenv("FRONTEND_HEALTH_ENDPOINT", f"http://localhost:{frontend_port}/#/"),
        ),
    ]

    ensure_ports_available([_port(api_port, 3001), _port(frontend_port, 3000)], logger)

    state: Dict[str, Any] = {}
    try:
        for proc in processes:
            pid = start_server(proc, logger)
            state[proc.name] = {"pid": pid, "log": str(proc.log_path)}
        write_state(state)
        all_ready = True
        for proc in processes:
            if not wait_for_health(proc.health_url, timeout, logger):
                all_ready = False
                break
        if not all_ready:
            logger.error("One or more services failed readiness; stopping servers")
            stop(env_file)
            raise SystemExit(1)

        logger.info("Demo servers are running (front: %s, back: %s)", frontend_port, api_port)
    except Exception:
        logger.exception("Failed to start demo servers")
        stop(env_file)
        raise


def stop(env_file: Path) -> None:
    configure_logging(force=True)
    logger = get_logger("manage_servers")
    state = read_state()
    if not state:
        logger.info("No running servers recorded; nothing to stop.")
        return

    for name, info in state.items():
        pid = info.get("pid")
        if not pid:
            continue
        try:
            logger.info("Stopping %s (pid=%s)", name, pid)
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            logger.warning("%s process %s not found", name, pid)
        except PermissionError:
            logger.error("Permission denied stopping %s (pid=%s)", name, pid)

    # Wait briefly for processes to exit.
    deadline = time.time() + 10
    while time.time() < deadline:
        remaining = []
        for name, info in state.items():
            pid = info.get("pid")
            if not pid:
                continue
            if Path(f"/proc/{pid}").exists():
                remaining.append((name, pid))
        if not remaining:
            break
        time.sleep(0.5)

    remove_state()
    logger.info("Demo servers stopped.")


def status(env_file: Path) -> None:
    configure_logging(force=True)
    logger = get_logger("manage_servers")
    state = read_state()
    if not state:
        logger.info("Demo servers are not running.")
        return
    rows = []
    for name, info in state.items():
        pid = info.get("pid")
        alive = Path(f"/proc/{pid}").exists()
        rows.append(f"{name}: pid={pid} alive={alive} log={info.get('log')}")
    logger.info("Server status:\n%s", "\n".join(rows))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices={"start", "stop", "status"}, help="Action to perform")
    parser.add_argument("--env-file", default="config/demo.env", type=Path, help="Environment file for configuration")
    parser.add_argument("--timeout", type=float, default=30.0, help="Seconds to wait for readiness on start")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.action == "start":
        start(args.env_file, args.timeout)
    elif args.action == "stop":
        stop(args.env_file)
    else:
        status(args.env_file)


if __name__ == "__main__":
    main()
