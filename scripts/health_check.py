#!/usr/bin/env python3
"""Health check orchestrator for the RealWorld demo stack."""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable

import requests
from dotenv import load_dotenv

try:
    import psycopg2
except ImportError as exc:  # pragma: no cover - psycopg2 is optional for linting
    psycopg2 = None  # type: ignore[assignment]
    _PSYCOPG2_IMPORT_ERROR = exc
else:
    _PSYCOPG2_IMPORT_ERROR = None


@dataclass
class CheckResult:
    name: str
    success: bool
    detail: str
    elapsed: float


def _timed(check_fn: Callable[[], str]) -> CheckResult:
    name = check_fn.__name__.replace("check_", "")
    start = time.perf_counter()
    try:
        detail = check_fn()
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=False, detail=str(exc), elapsed=elapsed)
    elapsed = time.perf_counter() - start
    return CheckResult(name=name, success=True, detail=detail, elapsed=elapsed)


def check_frontend() -> str:
    url = os.environ["FRONTEND_HEALTH_ENDPOINT"]
    timeout = float(os.environ.get("HEALTHCHECK_TIMEOUT", 10))
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return f"HTTP {resp.status_code}"


def check_backend() -> str:
    url = os.environ["BACKEND_HEALTH_ENDPOINT"]
    timeout = float(os.environ.get("HEALTHCHECK_TIMEOUT", 10))
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return f"HTTP {resp.status_code}"


def check_database() -> str:
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not installed; install requirements before running DB checks"
        ) from _PSYCOPG2_IMPORT_ERROR
    query = os.environ.get("DB_HEALTH_QUERY", "SELECT 1;")
    conn = psycopg2.connect(
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        connect_timeout=int(os.environ.get("DB_CONNECT_TIMEOUT", "5")),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    return f"Query returned: {row}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="config/demo.env", help="Path to .env file")
    parser.add_argument(
        "--timeout", type=float, default=60, help="Overall timeout to wait for readiness"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5,
        help="Interval between retries while waiting for services",
    )
    parser.add_argument(
        "--skip-frontend", action="store_true", help="Skip frontend readiness check"
    )
    parser.add_argument(
        "--skip-backend", action="store_true", help="Skip backend readiness check"
    )
    parser.add_argument("--skip-db", action="store_true", help="Skip database readiness check")
    return parser.parse_args()


def wait_for(check: Callable[[], CheckResult], timeout: float, interval: float) -> CheckResult:
    deadline = time.time() + timeout
    last_result: CheckResult | None = None
    while time.time() < deadline:
        result = check()
        if result.success:
            return result
        last_result = result
        time.sleep(interval)
    return last_result or CheckResult(name=check.__name__, success=False, detail="Timed out", elapsed=timeout)


def main() -> int:
    args = parse_args()
    if not os.path.exists(args.env_file):
        print(f"Environment file not found: {args.env_file}", file=sys.stderr)
        return 1

    load_dotenv(args.env_file, override=True)

    checks: list[Callable[[], CheckResult]] = []
    if not args.skip_frontend:
        checks.append(lambda: _timed(check_frontend))
    if not args.skip_backend:
        checks.append(lambda: _timed(check_backend))
    if not args.skip_db:
        checks.append(lambda: _timed(check_database))

    overall_success = True
    for create_check in checks:
        result = wait_for(create_check, timeout=args.timeout, interval=args.interval)
        status = "OK" if result.success else "FAIL"
        print(f"[{status}] {result.name} in {result.elapsed:.2f}s -> {result.detail}")
        overall_success &= result.success

    return 0 if overall_success else 2


if __name__ == "__main__":
    raise SystemExit(main())
