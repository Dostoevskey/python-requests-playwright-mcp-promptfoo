#!/usr/bin/env python3
"""Health check utilities with enhanced API validation and retry logic."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv


@dataclass
class CheckResult:
    name: str
    success: bool
    detail: str
    elapsed: float


def _retry_with_backoff(
    func,
    *args,
    retries: int = 5,
    backoff: float = 1.0,
    max_backoff: float = 10.0,
    **kwargs
) -> any:
    """Generic retry wrapper with exponential backoff."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                wait = min(backoff * (2 ** (attempt - 1)), max_backoff)
                print(f"  Attempt {attempt}/{retries} failed: {exc}. Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise
    if last_exc:
        raise last_exc


def check_backend_api(base_url: str, timeout: float = 10.0) -> CheckResult:
    """Validate backend API is ready by checking /articles endpoint."""
    name = "backend_api"
    start = time.perf_counter()
    
    def _test():
        # Check articles endpoint (should return 200 with empty or populated list)
        resp = requests.get(f"{base_url}/articles", timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Articles endpoint returned {resp.status_code}")
        data = resp.json()
        if "articles" not in data:
            raise RuntimeError("Response missing 'articles' key")
        return f"HTTP {resp.status_code}, {len(data['articles'])} articles"
    
    try:
        detail = _retry_with_backoff(_test, retries=5, backoff=1.0)
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=True, detail=detail, elapsed=elapsed)
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=False, detail=str(exc), elapsed=elapsed)


def check_frontend(url: str, timeout: float = 10.0) -> CheckResult:
    """Check if frontend is responding."""
    name = "frontend"
    start = time.perf_counter()
    
    def _test():
        resp = requests.get(url, timeout=timeout)
        if resp.status_code not in (200, 304):
            raise RuntimeError(f"Frontend returned {resp.status_code}")
        return f"HTTP {resp.status_code}"
    
    try:
        detail = _retry_with_backoff(_test, retries=5, backoff=1.0)
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=True, detail=detail, elapsed=elapsed)
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=False, detail=str(exc), elapsed=elapsed)


def check_database_via_api(base_url: str, timeout: float = 10.0) -> CheckResult:
    """Validate database is accessible via API (tests full stack)."""
    name = "database_via_api"
    start = time.perf_counter()
    
    def _test():
        # Try to fetch tags (lightweight endpoint that hits database)
        resp = requests.get(f"{base_url}/tags", timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Tags endpoint returned {resp.status_code}")
        data = resp.json()
        if "tags" not in data:
            raise RuntimeError("Response missing 'tags' key")
        return f"HTTP {resp.status_code}, {len(data['tags'])} tags"
    
    try:
        detail = _retry_with_backoff(_test, retries=5, backoff=1.0)
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=True, detail=detail, elapsed=elapsed)
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return CheckResult(name=name, success=False, detail=str(exc), elapsed=elapsed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="config/demo.env", help="Path to environment file")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend check")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    env_path = Path(args.env_file)
    if not env_path.exists():
        print(f"❌ Environment file not found: {env_path}", file=sys.stderr)
        return 1
    
    load_dotenv(env_path, override=True)
    
    api_base_url = os.environ.get("API_BASE_URL")
    frontend_url = os.environ.get("FRONTEND_URL")
    
    if not api_base_url:
        print("❌ API_BASE_URL not set in environment", file=sys.stderr)
        return 1
    
    print(f"🔍 Running health checks against {api_base_url}")
    print()
    
    checks = []
    
    # Check backend API with actual validation
    print("  Checking backend API...")
    result = check_backend_api(api_base_url)
    checks.append(result)
    status = "✓" if result.success else "✗"
    print(f"  {status} {result.name}: {result.detail} ({result.elapsed:.2f}s)")
    
    # Check database via API
    print("  Checking database connectivity...")
    result = check_database_via_api(api_base_url)
    checks.append(result)
    status = "✓" if result.success else "✗"
    print(f"  {status} {result.name}: {result.detail} ({result.elapsed:.2f}s)")
    
    # Check frontend if requested
    if not args.skip_frontend and frontend_url:
        print("  Checking frontend...")
        result = check_frontend(frontend_url)
        checks.append(result)
        status = "✓" if result.success else "✗"
        print(f"  {status} {result.name}: {result.detail} ({result.elapsed:.2f}s)")
    
    print()
    
    failed = [c for c in checks if not c.success]
    if failed:
        print(f"❌ {len(failed)}/{len(checks)} checks failed")
        if args.verbose:
            for check in failed:
                print(f"   - {check.name}: {check.detail}")
        return 1
    
    print(f"✅ All {len(checks)} health checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
