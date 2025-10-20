from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import allure
import pytest

# Guard and timeout values
PROMPTFOO_TIMEOUT = 60  # seconds
PROMPTFOO_OPT_IN_FILE = ".enable_promptfoo"


@pytest.mark.llm
def test_promptfoo_eval(settings, tmp_path: Path) -> None:
    """
    Run Promptfoo evaluation as an integration test.
    - Requires npx available (Node.js).
    - Requires opt-in via an empty .enable_promptfoo file located beside the env file
      (to avoid accidental long-running runs in CI/local dev).
    - Times out after PROMPTFOO_TIMEOUT seconds to avoid hanging the test runner.
    """
    if shutil.which("npx") is None:
        pytest.skip("npx not available; install Node.js to run promptfoo evaluations")

    # Simple opt-in guard to avoid accidental runs
    env_dir = Path(settings.env_file).parent if settings.env_file else Path(".")
    if not (env_dir / PROMPTFOO_OPT_IN_FILE).exists() and not Path(PROMPTFOO_OPT_IN_FILE).exists():
        pytest.skip("Promptfoo evaluation is disabled; create a .enable_promptfoo file to opt in")

    report_path = tmp_path / "promptfoo_report.json"
    command = [
        "npx",
        "promptfoo",
        "eval",
        "--config",
        str(settings.promptfoo_config),
        "--output",
        str(report_path),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PROMPTFOO_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        allure.attach(str(exc), name="promptfoo_timeout", attachment_type=allure.attachment_type.TEXT)
        pytest.fail(f"promptfoo eval timed out after {PROMPTFOO_TIMEOUT}s")

    # Attach outputs for diagnostics
    allure.attach(completed.stdout or "<no stdout>", name="promptfoo_stdout", attachment_type=allure.attachment_type.TEXT)
    allure.attach(completed.stderr or "<no stderr>", name="promptfoo_stderr", attachment_type=allure.attachment_type.TEXT)

    if completed.returncode != 0:
        pytest.fail(
            f"promptfoo eval failed with code {completed.returncode}\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}"
        )

    if not report_path.exists():
        pytest.fail("promptfoo did not produce the expected report file")

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        # Attach raw to make parsing errors actionable
        raw = report_path.read_text(encoding="utf-8", errors="replace") if report_path.exists() else "<no file>"
        allure.attach(raw, name="promptfoo_report_raw", attachment_type=allure.attachment_type.TEXT)
        pytest.fail(f"Unable to parse promptfoo report: {exc}")

    allure.attach(json.dumps(data, indent=2), name="promptfoo_report", attachment_type=allure.attachment_type.JSON)

    # Basic failure detection: any prompt with testFailCount or testErrorCount > 0
    prompts = data.get("results", {}).get("prompts", [])
    failing = [
        (prompt.get("label", prompt.get("raw", "<unknown>")), prompt.get("metrics", {}))
        for prompt in prompts
        if prompt.get("metrics", {}).get("testFailCount", 0) > 0 or prompt.get("metrics", {}).get("testErrorCount", 0) > 0
    ]
    assert not failing, f"Promptfoo reported failures: {failing}"