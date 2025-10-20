from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import allure
import pytest
from dotenv import load_dotenv


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


def _redact(value: Any) -> Any:
    """Simple redaction helper for Allure attachments.
    Masks known sensitive keys or values to avoid leaking secrets into test reports.
    """
    if isinstance(value, str):
        lower = value.lower()
        # naive checks for secrets
        if "password" in lower or "secret" in lower or "token" in lower or "database" in lower or "dsn" in lower:
            return "***REDACTED***"
    return value


def _redact_settings(d: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for k, v in d.items():
        if k.upper() in ("DATABASE_URL", "DATABASE_DSN", "DEFAULT_PASSWORD", "OLLAMA_API_KEY", "OLLAMA_BASE_URL"):
            redacted[k] = "***REDACTED***"
        elif isinstance(v, dict):
            redacted[k] = _redact_settings(v)
        else:
            redacted[k] = _redact(v)
    return redacted


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ui: UI tests requiring Playwright")
    config.addinivalue_line("markers", "api: API contract tests")
    config.addinivalue_line("markers", "llm: Prompt evaluation tests")


@ pytest.fixture(scope="session")
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
        database_dsn=os.environ.get("DATABASE_URL", ""),
        default_password=os.environ.get("DEFAULT_PASSWORD", "Password123!"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        promptfoo_config=promptfoo_path,
    )

    serializable = {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in settings_obj.__dict__.items()
    }

    # Redact sensitive fields before attaching
    redacted = _redact_settings(serializable)

    allure.attach(
        json.dumps(redacted, indent=2),
        name="settings",
        attachment_type=allure.attachment_type.JSON,
    )

    return settings_obj
