#!/usr/bin/env python3
"""Health check utilities with simple retry/backoff wrappers."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

import requests


@dataclass
class CheckResult:
    name: str
    success: bool
    detail: str
    elapsed: float


def _retry_request(url: str, timeout: float = 10.0, retries: int = 3, backoff: float = 0.5) -> requests.Response:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001 - allow broad capture for retry
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff * attempt)
            else:
                raise
    if last_exc:
        raise last_exc


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
    # Use retry wrapper to handle transient failures
    resp = _retry_request(url, timeout=timeout, retries=int(os.environ.get("HEALTHCHECK_RETRIES", 3)), backoff=float(os.environ.get("HEALTHCHECK_BACKOFF", 0.5)))
    return f"HTTP {resp.status_code}"


def check_backend() -> str:
    url = os.environ["BACKEND_HEALTH_ENDPOINT"] if os.environ.get("BACKEND_HEALTH_ENDPOINT") else os.environ.get("API_BASE_URL")
    timeout = float(os.environ.get("HEALTHCHECK_TIMEOUT", 10))
    resp = _retry_request(url, timeout=timeout, retries=int(os.environ.get("HEALTHCHECK_RETRIES", 3)), backoff=float(os.environ.get("HEALTHCHECK_BACKOFF", 0.5)))
    return f"HTTP {resp.status_code}"
