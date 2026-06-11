"""
DevOpsCLI — Subprocess wrappers for deterministic infrastructure validation.

Wraps Terraform, Checkov, and Infracost CLI tools with resilient error handling.
Every method captures stdout/stderr and never raises on subprocess failure —
errors are returned cleanly to the LangGraph state for the Architect to self-heal.
"""

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    """Standardized result from a CLI tool invocation."""

    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    parsed_data: dict[str, Any] = field(default_factory=dict)
    error_summary: str = ""


class DevOpsCLI:
    """
    Robust Python wrapper around DevOps CLI binaries.

    All methods use subprocess.run with capture_output=True and text=True.
    JSON parsing failures are handled gracefully — never crashes the pipeline.
    """

    def __init__(self, workspace_dir: str = "workspace"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.main_tf_path = self.workspace_dir / "main.tf"

    # ──────────────────────────────────────────────
    #  File I/O
    # ──────────────────────────────────────────────

    def write_terraform_code(self, hcl_code: str) -> Path:
        """Write the HCL payload to workspace/main.tf."""
        self.main_tf_path.write_text(hcl_code, encoding="utf-8")
        return self.main_tf_path

    # ──────────────────────────────────────────────
    #  Terraform CLI
    # ──────────────────────────────────────────────

    def run_terraform_init(self) -> ToolResult:
        """
        Run `terraform init` to initialize provider plugins.
        Uses -backend=false for validation-only workflows.
        """
        return self._run_command(
            ["terraform", "init", "-backend=false", "-no-color"],
            tool_name="terraform init",
        )

    def run_terraform_fmt(self) -> ToolResult:
        """Run `terraform fmt` to standardize HCL formatting."""
        result = self._run_command(
            ["terraform", "fmt", "-no-color", str(self.main_tf_path)],
            tool_name="terraform fmt",
        )
        # Re-read the formatted file if fmt succeeded
        if result.success and self.main_tf_path.exists():
            result.parsed_data["formatted_code"] = self.main_tf_path.read_text(
                encoding="utf-8"
            )
        return result

    def run_terraform_validate(self) -> ToolResult:
        """
        Run `terraform validate` to catch missing variables,
        incorrect block types, and undeclared dependencies.
        Returns JSON output for structured error extraction.
        """
        result = self._run_command(
            ["terraform", "validate", "-json", "-no-color"],
            tool_name="terraform validate",
        )
        # Parse the JSON diagnostic output
        self._try_parse_json(result, result.stdout)
        return result

    # ──────────────────────────────────────────────
    #  Checkov — Security Static Analysis
    # ──────────────────────────────────────────────

    def run_checkov(self) -> ToolResult:
        """
        Run Checkov against workspace/main.tf and calculate a security score.

        Scoring algorithm (per spec):
            - Base score: 100
            - Subtract 10 per MEDIUM severity finding
            - Subtract 25 per HIGH or CRITICAL severity finding
        """
        result = self._run_command(
            [
                "checkov",
                "-f", str(self.main_tf_path),
                "-o", "json",
                "--quiet",
                "--compact",
            ],
            tool_name="checkov",
        )

        # Parse Checkov JSON output and compute score
        self._try_parse_json(result, result.stdout)

        if result.parsed_data:
            score, findings = self._calculate_security_score(result.parsed_data)
            result.parsed_data["security_score"] = score
            result.parsed_data["findings_summary"] = findings
        else:
            # If JSON parsing failed, set score to 0
            result.parsed_data["security_score"] = 0.0
            result.parsed_data["findings_summary"] = (
                "Failed to parse Checkov output — treating as full failure."
            )

        return result

    def _calculate_security_score(
        self, checkov_data: dict[str, Any]
    ) -> tuple[float, str]:
        """
        Calculate security score from Checkov JSON output.

        Returns (score, human-readable findings summary).
        """
        score = 100.0
        findings_lines: list[str] = []

        # Checkov output can be a list of check-type results or a single dict
        results_list = checkov_data if isinstance(checkov_data, list) else [checkov_data]

        for check_result in results_list:
            if not isinstance(check_result, dict):
                continue

            failed_checks = check_result.get("results", {}).get("failed_checks", [])

            for check in failed_checks:
                severity = check.get("severity", "MEDIUM").upper()
                check_id = check.get("check_id", "UNKNOWN")
                check_name = check.get("check_name", "Unknown check")
                resource = check.get("resource", "unknown")

                if severity in ("HIGH", "CRITICAL"):
                    score -= 25
                    findings_lines.append(
                        f"  🔴 [{severity}] {check_id}: {check_name} (resource: {resource})"
                    )
                else:
                    score -= 10
                    findings_lines.append(
                        f"  🟡 [{severity}] {check_id}: {check_name} (resource: {resource})"
                    )

        score = max(score, 0.0)

        if findings_lines:
            summary = f"Security Score: {score}/100\nFindings:\n" + "\n".join(
                findings_lines
            )
        else:
            summary = f"Security Score: {score}/100 — No findings detected."

        return score, summary

    # ──────────────────────────────────────────────
    #  Infracost — Cost Estimation
    # ──────────────────────────────────────────────

    def run_infracost(self) -> ToolResult:
        """
        Run Infracost breakdown on the workspace and extract totalMonthlyCost.
        """
        result = self._run_command(
            [
                "infracost",
                "breakdown",
                "--path", str(self.workspace_dir),
                "--format", "json",
                "--no-color",
            ],
            tool_name="infracost",
        )

        self._try_parse_json(result, result.stdout)

        if result.parsed_data:
            monthly_cost = self._extract_monthly_cost(result.parsed_data)
            result.parsed_data["monthly_cost"] = monthly_cost
        else:
            result.parsed_data["monthly_cost"] = 0.0

        return result

    def _extract_monthly_cost(self, infracost_data: dict[str, Any]) -> float:
        """Extract totalMonthlyCost from Infracost JSON output."""
        try:
            cost_str = infracost_data.get("totalMonthlyCost", "0")
            return float(cost_str)
        except (ValueError, TypeError):
            return 0.0

    # ──────────────────────────────────────────────
    #  Tool Availability Check
    # ──────────────────────────────────────────────

    @staticmethod
    def check_tool_availability() -> dict[str, bool]:
        """
        Check which CLI tools are available on $PATH.
        Returns a dict of tool_name → is_available.
        """
        tools = {
            "terraform": ["terraform", "version"],
            "checkov": ["checkov", "--version"],
            "infracost": ["infracost", "--version"],
        }
        availability: dict[str, bool] = {}

        for name, cmd in tools.items():
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                availability[name] = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                availability[name] = False

        return availability

    # ──────────────────────────────────────────────
    #  Internal Helpers
    # ──────────────────────────────────────────────

    def _run_command(self, cmd: list[str], tool_name: str) -> ToolResult:
        """
        Execute a subprocess command with full error capture.
        Never raises — always returns a ToolResult.
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.workspace_dir),
                timeout=120,
                env={**os.environ},
            )
            return ToolResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                error_summary="" if result.returncode == 0 else (
                    f"{tool_name} failed (exit code {result.returncode}): "
                    f"{result.stderr[:500]}"
                ),
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                exit_code=-1,
                error_summary=(
                    f"'{tool_name}' is not installed or not on $PATH. "
                    f"Please install it to enable this validation step."
                ),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                exit_code=-2,
                error_summary=f"'{tool_name}' timed out after 120 seconds.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                exit_code=-99,
                error_summary=f"Unexpected error running '{tool_name}': {e}",
            )

    @staticmethod
    def _try_parse_json(result: ToolResult, raw_output: str) -> None:
        """
        Attempt to parse JSON from raw CLI output.
        Handles JSONDecodeError gracefully per spec requirements.
        """
        if not raw_output.strip():
            return
        try:
            result.parsed_data = json.loads(raw_output)
        except json.JSONDecodeError:
            result.error_summary += (
                f" | JSON parse failed — raw output: {raw_output[:300]}"
            )
