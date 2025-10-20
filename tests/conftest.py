from __future__ import annotations

import json
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


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        ENV_OPTION,
        action="store",
        default="config/demo.env",
        help="Path to environment configuration file",
    )


@pytest.fixture(scope="session")
def settings(pytestconfig: pytest.Config) -> Settings:
    env_path = Path(pytestconfig.getoption(ENV_OPTION))
    if not env_path.exists():
        pytest.exit(f"Environment file not found: {env_path}", returncode=1)

    load_dotenv(env_path, override=True)
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

    allure.attach(json.dumps(settings_obj.__dict__, indent=2), name="settings", attachment_type=allure.attachment_type.JSON)

    return settings_obj


@pytest.fixture(scope="session")
def backend_ready(settings: Settings) -> Iterator[None]:
    try:
        status = wait_for_http("backend", settings.backend_health_endpoint)
    except ReadinessTimeoutError as exc:
        pytest.skip(f"Backend not ready: {exc}")
    else:
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
        pytest.skip(f"Frontend not ready: {exc}")
    else:
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
        pytest.skip(f"Database not ready: {exc}")
    else:
        allure.attach(
            json.dumps(status.__dict__, indent=2),
            name="database_health",
            attachment_type=allure.attachment_type.JSON,
        )
    yield


@pytest.fixture(scope="session")
def api_client(settings: Settings, backend_ready: None) -> ApiClient:  # noqa: D401
    """API client pointing at the Conduit backend."""
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


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ui: UI tests requiring Playwright")
    config.addinivalue_line("markers", "api: API contract tests")
    config.addinivalue_line("markers", "llm: Prompt evaluation tests")
