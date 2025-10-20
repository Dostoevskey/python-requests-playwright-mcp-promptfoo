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

    for config_path in settings.promptfoo_configs:
        with allure.step(f"promptfoo eval: {config_path}"):
            report_path = tmp_path / f"promptfoo_report_{config_path.parent.name}.json"
            command = [
                "npx",
                "promptfoo",
                "eval",
                "--config",
                str(config_path),
                "--output",
                str(report_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            allure.attach(
                completed.stdout,
                name=f"promptfoo_stdout_{config_path.parent.name}",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                completed.stderr,
                name=f"promptfoo_stderr_{config_path.parent.name}",
                attachment_type=allure.attachment_type.TEXT,
            )

            if completed.returncode != 0:
                pytest.fail(f"promptfoo eval failed for {config_path} with code {completed.returncode}")

            data = json.loads(report_path.read_text())
            allure.attach(
                json.dumps(data, indent=2),
                name=f"promptfoo_report_{config_path.parent.name}",
                attachment_type=allure.attachment_type.JSON,
            )

            prompts = data.get("results", {}).get("prompts", [])
            failing = [
                (prompt.get("label", prompt.get("raw", "<unknown>")), prompt.get("metrics", {}))
                for prompt in prompts
                if prompt.get("metrics", {}).get("testFailCount", 0) > 0
                or prompt.get("metrics", {}).get("testErrorCount", 0) > 0
            ]
            assert not failing, f"Promptfoo reported failures for {config_path}: {failing}"
