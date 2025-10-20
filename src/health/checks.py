"""Reusable health-check helpers for pytest fixtures."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable

import requests

try:  # pragma: no cover - optional import
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]


@dataclass
class ServiceStatus:
    name: str
    healthy: bool
    detail: str
    elapsed: float


class ReadinessTimeoutError(RuntimeError):
    """Raised when a service does not become ready within the timeout."""


def _ping(url: str, timeout: float) -> ServiceStatus:
    start = time.perf_counter()
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    elapsed = time.perf_counter() - start
    return ServiceStatus(name=url, healthy=True, detail=f"HTTP {response.status_code}", elapsed=elapsed)


def wait_for_http(name: str, url: str, timeout: float = 60, interval: float = 5) -> ServiceStatus:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status = _ping(url, timeout=interval)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(interval)
            continue
        status.name = name
        return status
    raise ReadinessTimeoutError(f"{name} did not become ready: {last_error}")


def wait_for_database(
    name: str,
    dsn: str,
    timeout: float = 60,
    interval: float = 5,
    query: str = "SELECT 1;",
) -> ServiceStatus:
    if psycopg2 is None:  # pragma: no cover
        raise RuntimeError("psycopg2 required for database health checks")
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            start = time.perf_counter()
            conn = psycopg2.connect(dsn, connect_timeout=int(interval))
            with conn.cursor() as cursor:
                cursor.execute(query)
                cursor.fetchone()
            conn.close()
            elapsed = time.perf_counter() - start
            return ServiceStatus(name=name, healthy=True, detail="Query ok", elapsed=elapsed)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(interval)
    raise ReadinessTimeoutError(f"{name} database timeout: {last_error}")


def build_postgres_dsn() -> str:
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ["DB_NAME"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


def ensure_all_ready(checks: Iterable[ServiceStatus]) -> None:
    problems = [c for c in checks if not c.healthy]
    if problems:
        details = "; ".join(f"{c.name}: {c.detail}" for c in problems)
        raise ReadinessTimeoutError(details)


__all__ = [
    "ServiceStatus",
    "ReadinessTimeoutError",
    "wait_for_http",
    "wait_for_database",
    "build_postgres_dsn",
    "ensure_all_ready",
]
