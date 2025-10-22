from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

import allure
import pytest
import yaml
from jinja2 import Template

from src.utils.logger import get_logger
from src.utils.ollama_client import OllamaRunner

LOGGER = get_logger(__name__)

SUITE_DIR = Path(__file__).resolve().parent / "suites" / "articles"
PROMPTS_FILE = SUITE_DIR / "prompts.yaml"
GENERATOR_MODELS = ["gemma3:4b", "deepseek-r1:8b"]
JUDGE_MODEL = "gpt-oss:20b"
default_fake = "1" if os.environ.get("CI", "").lower() in {"1", "true", "yes"} else "0"
FAKE_OLLAMA = os.environ.get("USE_FAKE_OLLAMA", default_fake).lower() in {"1", "true", "yes"}


@pytest.mark.llm
def test_local_article_generation(settings) -> None:
    if not PROMPTS_FILE.exists():
        pytest.skip(f"Prompt definitions missing; ensure {PROMPTS_FILE} is present")

    runner = OllamaRunner(settings.ollama_base_url)

    missing_models = [model for model in GENERATOR_MODELS + [JUDGE_MODEL] if not runner.ensure_model(model)]
    if missing_models:
        pytest.skip(f"Missing Ollama models: {', '.join(missing_models)}")

    data = yaml.safe_load(PROMPTS_FILE.read_text())
    prompt_template = next(prompt["template"] for prompt in data["prompts"] if prompt["id"] == "concise_article")
    template = Template(prompt_template)

    for scenario in data["scenarios"]:
        vars_ = scenario["vars"]
        rendered_prompt = template.render(**vars_)
        LOGGER.info("Evaluating LLM scenario %s", scenario["id"])
        allure.attach(
            rendered_prompt,
            name=f"prompt_{scenario['id']}",
            attachment_type=allure.attachment_type.TEXT,
        )
        if FAKE_OLLAMA:
            attempt_configs = [(120, 0.0)]
        else:
            attempt_configs = [
                (160, 0.5),
                (140, 0.4),
                (120, 0.35),
                (100, 0.3),
                (200, 0.25),
                (180, 0.2),
            ]

        for model in GENERATOR_MODELS:
            attempt_log: list[str] = []
            output = ""
            success = False
            last_judge_text = ""
            LOGGER.debug("Running generator model %s for scenario %s", model, scenario["id"])
            for index, (max_tokens, temp) in enumerate(attempt_configs, start=1):
                result = runner.generate(model, rendered_prompt, options={"temperature": temp, "num_predict": max_tokens})
                output = result.output.strip()
                output = re.sub(r"-{2,}\s*", " ", output)
                output = re.sub(r"\s+", " ", output).strip()
                length = len(output)
                note = f"attempt {index} (num_predict={max_tokens}, temp={temp}): raw={length} chars"
                if length > 500:
                    trimmed = output[:500].rsplit(" ", 1)[0].strip()
                    output = trimmed
                    length = len(output)
                    note += f", trimmed={length}"
                if length < 300:
                    attempt_log.append(f"{note} -> too short")
                    continue
                judge_pass, judge_text = runner.evaluate_with_judge(JUDGE_MODEL, output, vars_["topic"])
                last_judge_text = judge_text
                note += f", judge={'PASS' if judge_pass else 'FAIL'}"
                attempt_log.append(note)
                if judge_pass:
                    success = True
                    LOGGER.info(
                        "Scenario %s model %s satisfied judge on attempt %d",
                        scenario["id"],
                        model,
                        index,
                    )
                    break
            if not success:
                allure.attach(
                    "\n".join(attempt_log),
                    name=f"{scenario['id']}_{model}_attempts",
                    attachment_type=allure.attachment_type.TEXT,
                )
                allure.attach(
                    last_judge_text,
                    name=f"{scenario['id']}_{model}_judge_reason",
                    attachment_type=allure.attachment_type.TEXT,
                )
                LOGGER.error("Scenario %s failed for model %s", scenario["id"], model)
                pytest.fail(f"{model} could not satisfy judge for scenario {scenario['id']}")

            allure.attach(
                textwrap.shorten(output, width=800, placeholder="..."),
                name=f"{scenario['id']}_{model}",
                attachment_type=allure.attachment_type.TEXT,
            )
            allure.attach(
                "\n".join(attempt_log),
                name=f"{scenario['id']}_{model}_lengths",
                attachment_type=allure.attachment_type.TEXT,
            )
            if last_judge_text:
                allure.attach(
                    last_judge_text,
                    name=f"{scenario['id']}_{model}_judge",
                    attachment_type=allure.attachment_type.TEXT,
                )
