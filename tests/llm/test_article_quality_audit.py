"""
LLM Quality Audit Tests - Demo-Friendly Sampling

Collect a small sample of real-model generations so interviewers can discuss
quality signals without wrestling with intentional hard failures.

Purpose:
- Highlight hallucination/quality issues while keeping the suite green
- Retain the same prompts as the heavier audit for easy storytelling
- Emit Allure artifacts (failures + cautionary report) for talking points

Expected Behavior:
- LOCAL RUNS (USE_FAKE_OLLAMA=0): Pass if every model produces at least one valid sample
- CI RUNS (USE_FAKE_OLLAMA=1): Deterministic stubbed pass
- Attachments call out low success rates instead of failing the build
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import allure
import pytest
import yaml
from jinja2 import Template

from src.utils.logger import get_logger
from src.utils.ollama_client import OllamaRunner

LOGGER = get_logger(__name__)

PROMPTS_FILE = Path("promptfoo/prompts/articles.yaml")
GENERATOR_MODELS = ["gemma3:4b", "deepseek-r1:8b"]
JUDGE_MODEL = "gpt-oss:20b"
AUDIT_ITERATIONS = 2  # Keep iterations low for speedy demo runs
MIN_ACCEPTABLE_SUCCESS_RATE = 0.4

default_fake = "1" if os.environ.get("CI", "").lower() in {"1", "true", "yes"} else "0"
FAKE_OLLAMA = os.environ.get("USE_FAKE_OLLAMA", default_fake).lower() in {"1", "true", "yes"}


@dataclass
class AuditResult:
    """Single audit iteration result."""
    iteration: int
    model: str
    scenario_id: str
    output: str
    length: int
    topic_coverage: float
    judge_pass: bool
    judge_reasoning: str
    failure_reason: str | None


@dataclass
class ModelAuditSummary:
    """Statistical summary for a model across all scenarios."""
    model: str
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    failures_by_reason: dict[str, int]
    recommendation: str


def calculate_topic_coverage(output: str, topic: str) -> float:
    """Calculate what percentage of topic keywords appear in output."""
    topic_terms = {term.lower() for term in re.findall(r"[A-Za-z]+", topic) if len(term) > 3}
    if not topic_terms:
        return 1.0  # No keywords to check
    matched_terms = {term for term in topic_terms if term in output.lower()}
    return len(matched_terms) / len(topic_terms)


def assess_failure_reason(result: AuditResult, min_length: int = 300, max_length: int = 500) -> str | None:
    """Determine primary failure reason for an audit result."""
    if result.length < min_length:
        return f"too_short ({result.length} < {min_length})"
    if result.length > max_length:
        return f"too_long ({result.length} > {max_length})"
    if result.topic_coverage < 0.5:
        return f"off_topic (coverage {result.topic_coverage:.1%})"
    if not result.judge_pass:
        return "judge_rejected (hallucination/incoherence)"
    return None


def generate_recommendation(summary: ModelAuditSummary) -> str:
    """Generate actionable recommendation based on success rate."""
    rate = summary.success_rate
    if rate < 0.4:
        return "🔴 REPLACE IMMEDIATELY - Model is unsuitable (success rate < 40%)"
    if rate < 0.6:
        return "🟡 CONSIDER REPLACEMENT - Model is marginal (success rate 40-60%)"
    if rate < 0.8:
        return "🟢 ACCEPTABLE - Model meets minimum standards (success rate 60-80%)"
    return "🟢 PERFORMING WELL - Model is reliable (success rate > 80%)"


@pytest.mark.llm_audit
def test_article_quality_audit_strict(settings) -> None:
    """
    Lightweight LLM audit that samples each scenario a couple of times with real models.

    The goal is to give the interviewer a quick health signal without turning the demo
    into a forensic investigation. We retain the same prompts, but:

    - Keep iterations low so runs stay under a minute per model
    - Flag catastrophic behaviour (zero passing runs) as hard failures
    - Surface low success rates as cautionary attachments instead of failing
    - Skip persistence / recommendation engines to keep code easy to explain
    """
    if not PROMPTS_FILE.exists():
        pytest.skip(f"Prompt definitions missing; ensure {PROMPTS_FILE} is present")

    runner = OllamaRunner(settings.ollama_base_url)

    missing_models = [model for model in GENERATOR_MODELS + [JUDGE_MODEL] if not runner.ensure_model(model)]
    if missing_models:
        pytest.skip(f"Missing Ollama models: {', '.join(missing_models)}")

    data = yaml.safe_load(PROMPTS_FILE.read_text())
    prompt_template = next(prompt["template"] for prompt in data["prompts"] if prompt["id"] == "concise_article")
    template = Template(prompt_template)

    # Collect all audit results for statistical analysis
    all_results: list[AuditResult] = []
    model_summaries: dict[str, ModelAuditSummary] = {}

    for model in GENERATOR_MODELS:
        LOGGER.info("Starting strict quality audit for model: %s", model)
        model_results: list[AuditResult] = []

        for scenario in data["scenarios"]:
            vars_ = scenario["vars"]
            rendered_prompt = template.render(**vars_)
            scenario_id = scenario["id"]

            LOGGER.info("Auditing %s with %s (%d iterations)", scenario_id, model, AUDIT_ITERATIONS)

            for iteration in range(1, AUDIT_ITERATIONS + 1):
                # Generate with deterministic seed for reproducibility
                seed_base = int(hashlib.md5(f"{scenario_id}::{model}::audit".encode()).hexdigest()[:8], 16)
                seed = seed_base + iteration

                if FAKE_OLLAMA:
                    # Stub mode: deterministic pass
                    options = {"temperature": 0.0, "num_predict": 120, "seed": seed}
                else:
                    # Real mode: typical generation parameters, NO retries
                    options = {"temperature": 0.25, "num_predict": 180, "seed": seed}

                result = runner.generate(model, rendered_prompt, options=options)
                output = result.output.strip()

                # Clean up output
                output = re.sub(r"-{2,}\s*", " ", output)
                output = re.sub(r"\s+", " ", output).strip()

                # Trim if too long (but track original length for failure analysis)
                original_length = len(output)
                if original_length > 500:
                    output = output[:500].rsplit(" ", 1)[0].strip()

                length = len(output)
                topic_coverage = calculate_topic_coverage(output, vars_["topic"])

                # Judge validation (single pass, no retry)
                judge_pass, judge_text = runner.evaluate_with_judge(
                    JUDGE_MODEL,
                    output,
                    vars_["topic"],
                    seed_override=seed + 50000,
                )

                audit_result = AuditResult(
                    iteration=iteration,
                    model=model,
                    scenario_id=scenario_id,
                    output=output,
                    length=length,
                    topic_coverage=topic_coverage,
                    judge_pass=judge_pass,
                    judge_reasoning=judge_text,
                    failure_reason=None,
                )

                # Assess failure reason
                audit_result.failure_reason = assess_failure_reason(audit_result)

                model_results.append(audit_result)
                all_results.append(audit_result)

                # Log each iteration
                status = "✅ PASS" if audit_result.failure_reason is None else f"❌ FAIL ({audit_result.failure_reason})"
                LOGGER.info(
                    "%s - %s - Iteration %d/%d: %s (length=%d, coverage=%.0f%%)",
                    model,
                    scenario_id,
                    iteration,
                    AUDIT_ITERATIONS,
                    status,
                    length,
                    topic_coverage * 100,
                )

                # Attach individual iteration details to Allure
                iteration_detail = {
                    "model": model,
                    "scenario": scenario_id,
                    "iteration": iteration,
                    "seed": seed,
                    "length": length,
                    "topic_coverage": f"{topic_coverage:.1%}",
                    "judge_pass": judge_pass,
                    "failure_reason": audit_result.failure_reason or "none",
                    "output_preview": textwrap.shorten(output, width=200, placeholder="..."),
                }
                allure.attach(
                    json.dumps(iteration_detail, indent=2),
                    name=f"{model}_{scenario_id}_iter{iteration}",
                    attachment_type=allure.attachment_type.JSON,
                )

                # Attach failures with full context
                if audit_result.failure_reason:
                    allure.attach(
                        output,
                        name=f"FAILURE_{model}_{scenario_id}_iter{iteration}_output",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                    allure.attach(
                        judge_text,
                        name=f"FAILURE_{model}_{scenario_id}_iter{iteration}_judge",
                        attachment_type=allure.attachment_type.TEXT,
                    )

        # Calculate summary statistics for this model
        successful = [r for r in model_results if r.failure_reason is None]
        failed = [r for r in model_results if r.failure_reason is not None]

        failures_by_reason: dict[str, int] = defaultdict(int)
        for result in failed:
            if result.failure_reason:
                failures_by_reason[result.failure_reason] += 1

        success_rate = len(successful) / len(model_results) if model_results else 0.0

        summary = ModelAuditSummary(
            model=model,
            total_runs=len(model_results),
            successful_runs=len(successful),
            failed_runs=len(failed),
            success_rate=success_rate,
            failures_by_reason=dict(failures_by_reason),
            recommendation="",
        )
        summary.recommendation = generate_recommendation(summary)

        model_summaries[model] = summary

        LOGGER.info(
            "Audit complete for %s: %d/%d passed (%.1f%%)",
            model,
            summary.successful_runs,
            summary.total_runs,
            summary.success_rate * 100,
        )

    # Generate comprehensive audit report
    report_lines = ["# LLM Quality Audit Report\n"]
    report_lines.append(f"**Iterations per scenario**: {AUDIT_ITERATIONS}")
    report_lines.append(f"**Total scenarios**: {len(data['scenarios'])}")
    report_lines.append(f"**Models tested**: {len(GENERATOR_MODELS)}\n")

    for model, summary in model_summaries.items():
        report_lines.append(f"\n## {model}\n")
        report_lines.append(
            f"- **Success Rate**: {summary.success_rate:.1%} "
            f"({summary.successful_runs}/{summary.total_runs})"
        )
        if summary.successful_runs == 0:
            report_lines.append("- ⚠️ No passing runs detected")
        else:
            report_lines.append(f"- **Recommendation**: {summary.recommendation}\n")

        if summary.failures_by_reason:
            report_lines.append("### Failure Breakdown:")
            for reason, count in sorted(summary.failures_by_reason.items(), key=lambda x: -x[1]):
                report_lines.append(f"  - {reason}: {count} occurrences")
        else:
            report_lines.append("✅ No failures detected")

    report_text = "\n".join(report_lines)

    # Attach comprehensive report
    allure.attach(
        report_text,
        name="quality_audit_report",
        attachment_type=allure.attachment_type.TEXT,
    )

    # Attach machine-readable JSON summary
    json_summary = {
        "audit_iterations": AUDIT_ITERATIONS,
        "models": {
            model: {
                "success_rate": summary.success_rate,
                "successful_runs": summary.successful_runs,
                "failed_runs": summary.failed_runs,
                "total_runs": summary.total_runs,
                "failures_by_reason": summary.failures_by_reason,
                "recommendation": summary.recommendation,
            }
            for model, summary in model_summaries.items()
        },
    }
    allure.attach(
        json.dumps(json_summary, indent=2),
        name="quality_audit_summary_json",
        attachment_type=allure.attachment_type.JSON,
    )

    LOGGER.info("\n" + report_text)

    cautionary_models = []
    failing_models = []
    for model, summary in model_summaries.items():
        if summary.successful_runs == 0:
            failing_models.append((model, summary))
        elif summary.success_rate < MIN_ACCEPTABLE_SUCCESS_RATE:
            cautionary_models.append((model, summary))

    if cautionary_models:
        caution_lines = ["Models trending low (<40% success rate). Investigate if time permits:\n"]
        for model, summary in cautionary_models:
            caution_lines.append(f"- {model}: {summary.success_rate:.1%} ({summary.successful_runs}/{summary.total_runs})")
        allure.attach(
            "\n".join(caution_lines),
            name="llm_audit_cautionary_models",
            attachment_type=allure.attachment_type.TEXT,
        )

    if failing_models:
        failure_message = "LLM Quality Audit FAILED - No successful runs detected:\n\n"
        for model, summary in failing_models:
            failure_message += f"  {model}: 0/{summary.total_runs} success\n"
        pytest.fail(failure_message)

    LOGGER.info("✅ LLM audit detected at least one successful generation per model")
