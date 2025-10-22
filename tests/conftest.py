from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import allure
import pytest
from dotenv import load_dotenv

from src.health.checks import (
    ReadinessTimeoutError,
    build_postgres_dsn,
    ensure_all_ready,
    wait_for_database,
    wait_for_http,
)
from src.utils.api_client import ApiClient
from src.utils.logger import configure_logging, get_logger


session_logger = get_logger(__name__)


@dataclass
class Settings:
    env_file: Path
    api_base_url: str
    frontend_url: str
    backend_health_endpoint: str
    frontend_health_endpoint: str
    database_dsn: str
    default_password: str
    ollama_base_url: str
    promptfoo_config: Path


ENV_OPTION = "--env-file"
ENV_ENVVAR = "DEMO_ENV_FILE"


def pytest_addoption(parser: pytest.Parser) -> None:
    default_env = os.environ.get(ENV_ENVVAR, "config/demo.env")
    parser.addoption(
        ENV_OPTION,
        action="store",
        default=default_env,
        help="Path to environment configuration file",
    )
    session_logger.debug("Registered pytest option %s with default %s", ENV_OPTION, default_env)


@pytest.fixture(scope="session")
def settings(pytestconfig: pytest.Config) -> Settings:
    raw_env = pytestconfig.getoption(ENV_OPTION)
    env_path = Path(raw_env) if raw_env else Path(os.environ.get(ENV_ENVVAR, "config/demo.env"))
    if not env_path.exists():
        pytest.exit(f"Environment file not found: {env_path}", returncode=1)

    load_dotenv(env_path, override=True)
    configure_logging(force=True)
    session_logger.info("Loaded environment configuration from %s", env_path)
    api_base_url = os.environ.get("API_BASE_URL")
    frontend_url = os.environ.get("FRONTEND_URL")
    if not api_base_url or not frontend_url:
        pytest.exit("API_BASE_URL and FRONTEND_URL must be defined in env file", returncode=1)

    promptfoo_path = Path(os.environ.get("PROMPTFOO_CONFIG", "config/promptfoo.yaml"))

    settings_obj = Settings(
        env_file=env_path,
        api_base_url=api_base_url,
        frontend_url=frontend_url,
        backend_health_endpoint=os.environ.get("BACKEND_HEALTH_ENDPOINT", f"{api_base_url}/articles"),
        frontend_health_endpoint=os.environ.get("FRONTEND_HEALTH_ENDPOINT", frontend_url),
        database_dsn=os.environ.get("DATABASE_URL", build_postgres_dsn()),
        default_password=os.environ.get("DEFAULT_PASSWORD", "Password123!"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        promptfoo_config=promptfoo_path,
    )

    serializable = {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in settings_obj.__dict__.items()
    }

    allure.attach(
        json.dumps(serializable, indent=2),
        name="settings",
        attachment_type=allure.attachment_type.JSON,
    )

    session_logger.debug(
        "Settings initialised: api_base=%s, frontend=%s",
        settings_obj.api_base_url,
        settings_obj.frontend_url,
    )

    return settings_obj


@pytest.fixture(scope="session")
def backend_ready(settings: Settings) -> Iterator[None]:
    try:
        status = wait_for_http("backend", settings.backend_health_endpoint)
    except ReadinessTimeoutError as exc:
        session_logger.error("Backend not ready: %s", exc)
        pytest.skip(f"Backend not ready: {exc}")
    else:
        session_logger.info("Backend ready: %s", status.detail)
        allure.attach(
            json.dumps(status.__dict__, indent=2),
            name="backend_health",
            attachment_type=allure.attachment_type.JSON,
        )
    yield


@pytest.fixture(scope="session")
def frontend_ready(settings: Settings) -> Iterator[None]:
    try:
        status = wait_for_http("frontend", settings.frontend_health_endpoint)
    except ReadinessTimeoutError as exc:
        session_logger.error("Frontend not ready: %s", exc)
        pytest.skip(f"Frontend not ready: {exc}")
    else:
        session_logger.info("Frontend ready: %s", status.detail)
        allure.attach(
            json.dumps(status.__dict__, indent=2),
            name="frontend_health",
            attachment_type=allure.attachment_type.JSON,
        )
    yield


@pytest.fixture(scope="session")
def database_ready(settings: Settings) -> Iterator[None]:
    try:
        status = wait_for_database("database", settings.database_dsn)
    except ReadinessTimeoutError as exc:
        session_logger.error("Database not ready: %s", exc)
        pytest.skip(f"Database not ready: {exc}")
    else:
        session_logger.info("Database ready: %s", status.detail)
        allure.attach(
            json.dumps(status.__dict__, indent=2),
            name="database_health",
            attachment_type=allure.attachment_type.JSON,
        )
    yield


@pytest.fixture(scope="session")
def api_client(settings: Settings, backend_ready: None) -> ApiClient:  # noqa: D401
    """API client pointing at the Conduit backend."""
    session_logger.debug("Creating API client for %s", settings.api_base_url)
    return ApiClient(settings.api_base_url)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("-m"):
        return
    # enforce marker usage is known
    markers = {"api", "ui", "llm"}
    for item in items:
        for mark in item.iter_markers():
            if mark.name in markers:
                break
        else:
            continue
    session_logger.debug("Collected %d tests with marker filter", len(items))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ui: UI tests requiring Playwright")
    config.addinivalue_line("markers", "api: API contract tests")
    config.addinivalue_line("markers", "llm: Prompt evaluation tests")
    session_logger.debug("Pytest configured with custom markers")


@pytest.fixture(autouse=True)
def _capture_test_logs(request: pytest.FixtureRequest) -> Iterator[None]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    test_logger = get_logger(request.node.nodeid)
    test_logger.addHandler(handler)
    yield
    test_logger.removeHandler(handler)
    handler.close()
    log_content = stream.getvalue().strip()
    rep_call = getattr(request.node, "rep_call", None)
    if rep_call and rep_call.failed and log_content:
        allure.attach(
            log_content,
            name=f"logs::{request.node.nodeid}",
            attachment_type=allure.attachment_type.TEXT,
        )


@pytest.fixture(autouse=True)
def _log_test_lifecycle(request: pytest.FixtureRequest) -> Iterator[None]:
    test_logger = get_logger(request.node.nodeid)
    test_logger.info("TEST START :: %s", request.node.nodeid)
    yield
    rep_call = getattr(request.node, "rep_call", None)
    if rep_call is None:
        rep_setup = getattr(request.node, "rep_setup", None)
        outcome = rep_setup.outcome.upper() if rep_setup else "SKIPPED"
    else:
        outcome = rep_call.outcome.upper()
    log_fn = test_logger.error if outcome == "FAILED" else test_logger.info
    log_fn("TEST END :: %s :: %s", request.node.nodeid, outcome)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
    hook_logger = get_logger("pytest")
    if rep.when == "setup":
        hook_logger.debug("Setup %s -> %s", item.nodeid, rep.outcome)
    elif rep.when == "call":
        hook_logger.info("Test %s %s", item.nodeid, rep.outcome.upper())
    elif rep.when == "teardown":
        hook_logger.debug("Teardown %s -> %s", item.nodeid, rep.outcome)
