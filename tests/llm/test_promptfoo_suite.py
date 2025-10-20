from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import allure
import pytest


@pytest.mark.llm
def test_promptfoo_eval(settings, tmp_path: Path) -> None:
    if shutil.which("npx") is None:
        pytest.skip("npx not available; install Node.js to run promptfoo evaluations")

    report_path = tmp_path / "promptfoo_report.json"
    command = [
        "npx",
        "promptfoo",
        "eval",
        "--config",
        str(settings.promptfoo_config),
        "--output",
        str(report_path),
        "--format",
        "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    allure.attach(completed.stdout, name="promptfoo_stdout", attachment_type=allure.attachment_type.TEXT)
    allure.attach(completed.stderr, name="promptfoo_stderr", attachment_type=allure.attachment_type.TEXT)

    if completed.returncode != 0:
        pytest.fail(f"promptfoo eval failed with code {completed.returncode}")

    data = json.loads(report_path.read_text())
    allure.attach(json.dumps(data, indent=2), name="promptfoo_report", attachment_type=allure.attachment_type.JSON)
    assert data["summary"]["fail"] == 0, "Prompt evaluations should pass all assertions"
