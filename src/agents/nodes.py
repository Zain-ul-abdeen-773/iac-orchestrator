"""
Agent Node Functions — LangGraph node implementations for each agent.

Each function takes the current AgentState, performs its specialized task,
and returns a partial state update dictionary.
"""

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import (
    ARCHITECT_SYSTEM_PROMPT,
    FINOPS_SYSTEM_PROMPT,
    SECOPS_SYSTEM_PROMPT,
)
from src.agents.schemas import (
    AgentState,
    ArchitectOutput,
    FinOpsOutput,
    SecOpsOutput,
)
from src.tools.gatekeeper import DevOpsCLI


def _get_llm():
    """
    Initialize the LLM based on the LLM_PROVIDER environment variable.
    Supports 'openai' (default) and 'anthropic'.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model_name = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        return ChatAnthropic(model=model_name, temperature=0.1, max_tokens=8192)
    else:
        from langchain_openai import ChatOpenAI

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(model=model_name, temperature=0.1, max_tokens=8192)


# ─────────────────────────────────────────────────────────────────────
#  Node B — Cloud Architect Agent
# ─────────────────────────────────────────────────────────────────────


def run_architect(state: AgentState) -> dict[str, Any]:
    """
    Cloud Architect agent — the core generation engine.

    Uses structured output via .with_structured_output(ArchitectOutput)
    to enforce Pydantic schema compliance. Ingests all historical
    critiques and linter logs from previous failed iterations.
    """
    llm = _get_llm()
    structured_llm = llm.with_structured_output(ArchitectOutput)

    # Build the human message with all available context
    context_parts = [
        f"## User Infrastructure Request\n{state['user_prompt']}",
        f"## Terraform AWS Documentation (RAG Context)\n{state.get('rag_context', 'No context retrieved yet.')}",
    ]

    # Inject historical feedback for self-healing iterations
    iteration = state.get("iteration_count", 0)
    if iteration > 0:
        context_parts.append(
            f"\n## ⚠️ SELF-HEALING ITERATION {iteration}\n"
            f"The previous code FAILED validation. You MUST fix ALL issues below.\n"
        )

        if state.get("linter_logs"):
            context_parts.append(
                f"### Linter / Validation Errors\n```\n{state['linter_logs']}\n```"
            )
        if state.get("security_critique"):
            context_parts.append(
                f"### Security Critique (from SecOps Red Team)\n{state['security_critique']}"
            )
        if state.get("finops_critique"):
            context_parts.append(
                f"### Cost Optimization Feedback (from FinOps)\n{state['finops_critique']}"
            )
        if state.get("current_code"):
            context_parts.append(
                f"### Previous Code (to fix)\n```hcl\n{state['current_code']}\n```"
            )

    messages = [
        SystemMessage(content=ARCHITECT_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(context_parts)),
    ]

    response: ArchitectOutput = structured_llm.invoke(messages)

    return {
        "current_code": response.terraform_code,
        "architect_reflection": response.thought_process,
        "iteration_count": iteration + 1,
    }


# ─────────────────────────────────────────────────────────────────────
#  Node C — SecOps Adversary Agent
# ─────────────────────────────────────────────────────────────────────


def run_secops(state: AgentState) -> dict[str, Any]:
    """
    SecOps Adversary agent — red-team threat analysis.

    Analyzes the current Terraform code for security vulnerabilities,
    misconfigurations, and architectural weaknesses.
    """
    llm = _get_llm()
    structured_llm = llm.with_structured_output(SecOpsOutput)

    messages = [
        SystemMessage(content=SECOPS_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"## Terraform Code to Audit\n"
                f"```hcl\n{state.get('current_code', 'No code generated yet.')}\n```\n\n"
                f"## Original User Request (for context)\n{state['user_prompt']}"
            )
        ),
    ]

    response: SecOpsOutput = structured_llm.invoke(messages)

    return {
        "security_critique": (
            f"## Security Findings\n{response.security_issues}\n\n"
            f"## Risk Summary\n{response.risk_summary}"
        ),
    }


# ─────────────────────────────────────────────────────────────────────
#  Node D — FinOps Cost Agent
# ─────────────────────────────────────────────────────────────────────


def run_finops(state: AgentState) -> dict[str, Any]:
    """
    FinOps Cost agent — budget optimization and resource right-sizing.

    Analyzes the current code alongside any available Infracost data
    to suggest cost savings.
    """
    llm = _get_llm()
    structured_llm = llm.with_structured_output(FinOpsOutput)

    cost_context = ""
    if state.get("monthly_cost", 0) > 0:
        cost_context = (
            f"\n\n## Current Estimated Monthly Cost\n"
            f"${state['monthly_cost']:.2f}/month (from Infracost)\n"
        )

    messages = [
        SystemMessage(content=FINOPS_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"## Terraform Code to Optimize\n"
                f"```hcl\n{state.get('current_code', 'No code generated yet.')}\n```\n\n"
                f"## Original User Request\n{state['user_prompt']}"
                f"{cost_context}"
            )
        ),
    ]

    response: FinOpsOutput = structured_llm.invoke(messages)

    return {
        "finops_critique": (
            f"## Cost Optimizations\n{response.cost_optimizations}\n\n"
            f"## Cost Summary\n{response.cost_summary}"
        ),
    }


# ─────────────────────────────────────────────────────────────────────
#  Node E — Deterministic Gatekeeper
# ─────────────────────────────────────────────────────────────────────


def run_gatekeeper(state: AgentState) -> dict[str, Any]:
    """
    Deterministic Gatekeeper — executes factual reality checks using CLI tools.

    Acts as the 'compiler' — completely separated from AI hallucination.
    Runs: terraform fmt → terraform init → terraform validate → checkov → infracost.
    """
    cli = DevOpsCLI()
    logs: list[str] = []
    terraform_valid = False
    security_score = 0.0
    monthly_cost = 0.0

    # 1. Write the current code to workspace/main.tf
    cli.write_terraform_code(state.get("current_code", ""))
    logs.append("📝 Wrote current_code to workspace/main.tf")

    # 2. Run terraform fmt
    fmt_result = cli.run_terraform_fmt()
    if fmt_result.success:
        logs.append("✅ terraform fmt — formatting applied")
    else:
        logs.append(f"⚠️ terraform fmt — {fmt_result.error_summary}")

    # 3. Run terraform init
    init_result = cli.run_terraform_init()
    if init_result.success:
        logs.append("✅ terraform init — providers initialized")
    else:
        logs.append(f"❌ terraform init — {init_result.error_summary}")
        # If init fails, validate and subsequent steps will also fail
        # but we continue to collect as much diagnostic info as possible

    # 4. Run terraform validate
    validate_result = cli.run_terraform_validate()
    if validate_result.success:
        terraform_valid = True
        logs.append("✅ terraform validate — code is syntactically valid")
    else:
        logs.append(f"❌ terraform validate — {validate_result.error_summary}")
        if validate_result.stdout:
            logs.append(f"   Diagnostic output: {validate_result.stdout[:500]}")
        if validate_result.stderr:
            logs.append(f"   Stderr: {validate_result.stderr[:500]}")

    # 5. Run Checkov (security scan)
    checkov_result = cli.run_checkov()
    security_score = checkov_result.parsed_data.get("security_score", 0.0)
    findings = checkov_result.parsed_data.get("findings_summary", "")
    if checkov_result.success or security_score > 0:
        logs.append(f"🛡️ Checkov — {findings}")
    else:
        logs.append(f"⚠️ Checkov — {checkov_result.error_summary or 'No output'}")
        if not checkov_result.error_summary:
            # Checkov returns non-zero when findings exist — that's expected
            logs.append(f"   Findings: {findings}")

    # 6. Run Infracost
    infracost_result = cli.run_infracost()
    monthly_cost = infracost_result.parsed_data.get("monthly_cost", 0.0)
    if infracost_result.success:
        logs.append(f"💰 Infracost — Estimated monthly cost: ${monthly_cost:.2f}")
    else:
        logs.append(f"⚠️ Infracost — {infracost_result.error_summary}")

    return {
        "linter_logs": "\n".join(logs),
        "security_score": security_score,
        "monthly_cost": monthly_cost,
        "terraform_valid": terraform_valid,
    }
