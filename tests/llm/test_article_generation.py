from __future__ import annotations

import textwrap
from pathlib import Path

import allure
import pytest
import yaml
from jinja2 import Template

from src.utils.ollama_client import OllamaRunner

PROMPTS_FILE = Path("promptfoo/prompts/articles.yaml")
GENERATOR_MODELS = ["gemma3:4b", "deepseek-r1:8b"]
JUDGE_MODEL = "gpt-oss:20b"


@pytest.mark.llm
def test_local_article_generation(settings) -> None:
    if not PROMPTS_FILE.exists():
        pytest.skip("Prompt definitions missing; ensure promptfoo/prompts/articles.yaml is present")

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
        allure.attach(
            rendered_prompt,
            name=f"prompt_{scenario['id']}",
            attachment_type=allure.attachment_type.TEXT,
        )
        for model in GENERATOR_MODELS:
            result = runner.generate(model, rendered_prompt, options={"temperature": 0.6, "num_predict": 512})
            output = result.output.strip()
            allure.attach(
                textwrap.shorten(output, width=800, placeholder="..."),
                name=f"{scenario['id']}_{model}",
                attachment_type=allure.attachment_type.TEXT,
            )
            length = len(output)
            assert 300 <= length <= 500, f"{model} produced {length} characters for {scenario['id']}"
            assert runner.evaluate_with_judge(JUDGE_MODEL, output, vars_["topic"]), (
                f"{model} failed judge validation for scenario {scenario['id']}"
            )
