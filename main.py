"""
IaC Orchestrator — Rich Interactive CLI Entrypoint

A beautiful, real-time terminal interface for the multi-agent Terraform
generation pipeline. Uses the Rich library for aesthetic formatting,
live-updating tables, spinners, and color-coded agent debate logs.
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Load environment variables
load_dotenv()

# ─────────────────────────────────────────────────────────────────────
#  Rich Theme & Console
# ─────────────────────────────────────────────────────────────────────

CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "agent.architect": "bold blue",
    "agent.secops": "bold red",
    "agent.finops": "bold yellow",
    "agent.gatekeeper": "bold magenta",
    "agent.retriever": "bold cyan",
    "score.high": "bold green",
    "score.mid": "bold yellow",
    "score.low": "bold red",
})

console = Console(theme=CUSTOM_THEME)


# ─────────────────────────────────────────────────────────────────────
#  UI Components
# ─────────────────────────────────────────────────────────────────────


def print_banner():
    """Display the application banner."""
    banner = Text()
    banner.append("╔══════════════════════════════════════════════════════════════╗\n", style="bold cyan")
    banner.append("║  ", style="bold cyan")
    banner.append("🤖 Autonomous Multi-Agent IaC Orchestrator", style="bold white")
    banner.append("              ║\n", style="bold cyan")
    banner.append("║  ", style="bold cyan")
    banner.append("   Self-Healing • Security-First • Cost-Optimized", style="dim white")
    banner.append("       ║\n", style="bold cyan")
    banner.append("╚══════════════════════════════════════════════════════════════╝", style="bold cyan")
    console.print(banner)
    console.print()


def print_tool_status():
    """Check and display CLI tool availability."""
    from src.tools.gatekeeper import DevOpsCLI

    console.print("[bold]🔧 Checking CLI Tool Availability...[/bold]")
    availability = DevOpsCLI.check_tool_availability()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Tool", style="cyan", width=15)
    table.add_column("Status", width=15)
    table.add_column("Purpose", style="dim")

    tools_info = {
        "terraform": "Syntax validation & initialization",
        "checkov": "Cloud security static analysis",
        "infracost": "HCL parsing & cost estimation",
    }

    all_available = True
    for tool, purpose in tools_info.items():
        available = availability.get(tool, False)
        status = "[success]✅ Available[/success]" if available else "[warning]⚠️ Missing[/warning]"
        if not available:
            all_available = False
        table.add_row(tool, status, purpose)

    console.print(table)

    if not all_available:
        console.print(
            "\n[warning]⚠️  Some tools are missing. The pipeline will still run, "
            "but validation steps for missing tools will be skipped.[/warning]\n"
        )
    else:
        console.print("\n[success]✅ All tools available — full pipeline enabled.[/success]\n")

    return availability


def get_score_style(score: float) -> str:
    """Get Rich style based on security score."""
    if score >= 90:
        return "score.high"
    elif score >= 60:
        return "score.mid"
    else:
        return "score.low"


def build_status_table(iteration: int, score: float, cost: float, tf_valid: bool) -> Table:
    """Build a live-updating status table for the current pipeline state."""
    table = Table(
        title="📊 Pipeline Status",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        expand=True,
    )
    table.add_column("Metric", style="bold", width=25)
    table.add_column("Value", width=30)
    table.add_column("Status", width=20)

    # Iteration
    iter_status = "[success]OK[/success]" if iteration < 5 else "[error]MAX REACHED[/error]"
    table.add_row("🔄 Iteration", f"{iteration} / 5", iter_status)

    # Security Score
    score_style = get_score_style(score)
    score_status = "[success]PASS ✅[/success]" if score >= 90 else "[error]FAIL ❌[/error]"
    table.add_row("🛡️  Security Score", f"[{score_style}]{score:.0f}/100[/{score_style}]", score_status)

    # Terraform Validation
    tf_status = "[success]VALID ✅[/success]" if tf_valid else "[error]INVALID ❌[/error]"
    table.add_row("🔩 Terraform Valid", "Yes" if tf_valid else "No", tf_status)

    # Monthly Cost
    table.add_row("💰 Est. Monthly Cost", f"${cost:.2f}", "—")

    return table


def print_node_header(node_name: str):
    """Print a styled header when a node starts executing."""
    styles = {
        "retrieve": ("🔍 Context Retriever (RAG)", "agent.retriever"),
        "architect": ("🏗️  Cloud Architect Agent", "agent.architect"),
        "secops": ("🛡️  SecOps Adversary Agent", "agent.secops"),
        "finops": ("💰 FinOps Cost Agent", "agent.finops"),
        "gatekeeper": ("🔩 Deterministic Gatekeeper", "agent.gatekeeper"),
    }
    label, style = styles.get(node_name, (node_name, "bold"))
    console.print(f"\n[{style}]{'─' * 60}[/{style}]")
    console.print(f"[{style}]  {label}[/{style}]")
    console.print(f"[{style}]{'─' * 60}[/{style}]")


def print_node_output(node_name: str, state_update: dict):
    """Print formatted output for a completed node."""
    if node_name == "retrieve":
        context = state_update.get("rag_context", "")
        preview = context[:200] + "..." if len(context) > 200 else context
        console.print(f"  [dim]Retrieved context ({len(context)} chars):[/dim]")
        console.print(f"  [dim]{preview}[/dim]")

    elif node_name == "architect":
        reflection = state_update.get("architect_reflection", "")
        code = state_update.get("current_code", "")
        iteration = state_update.get("iteration_count", 0)
        console.print(f"  [agent.architect]Iteration:[/agent.architect] {iteration}")
        console.print(f"  [agent.architect]Reasoning:[/agent.architect]")
        # Print first few lines of reflection
        for line in reflection.split("\n")[:5]:
            console.print(f"    [dim]{line}[/dim]")
        if len(reflection.split("\n")) > 5:
            console.print(f"    [dim]... ({len(reflection.split(chr(10)))} lines total)[/dim]")
        console.print(f"  [agent.architect]Generated HCL:[/agent.architect] {len(code)} chars")

    elif node_name == "secops":
        critique = state_update.get("security_critique", "")
        console.print(f"  [agent.secops]Security Analysis:[/agent.secops]")
        for line in critique.split("\n")[:8]:
            console.print(f"    {line}")
        if len(critique.split("\n")) > 8:
            console.print(f"    [dim]... (truncated)[/dim]")

    elif node_name == "finops":
        critique = state_update.get("finops_critique", "")
        console.print(f"  [agent.finops]Cost Analysis:[/agent.finops]")
        for line in critique.split("\n")[:8]:
            console.print(f"    {line}")
        if len(critique.split("\n")) > 8:
            console.print(f"    [dim]... (truncated)[/dim]")

    elif node_name == "gatekeeper":
        logs = state_update.get("linter_logs", "")
        score = state_update.get("security_score", 0)
        cost = state_update.get("monthly_cost", 0)
        console.print(f"  [agent.gatekeeper]Validation Results:[/agent.gatekeeper]")
        for line in logs.split("\n"):
            console.print(f"    {line}")
        score_style = get_score_style(score)
        console.print(f"\n  [{score_style}]Security Score: {score:.0f}/100[/{score_style}]")
        console.print(f"  Monthly Cost: ${cost:.2f}")


def print_final_result(final_state: dict):
    """Display the final pipeline result with the generated Terraform code."""
    score = final_state.get("security_score", 0)
    iterations = final_state.get("iteration_count", 0)
    cost = final_state.get("monthly_cost", 0)
    tf_valid = final_state.get("terraform_valid", False)
    code = final_state.get("current_code", "")

    console.print("\n")

    # Success or failure banner
    if score >= 90 and tf_valid:
        console.print(Panel(
            Align.center(Text("✅ PIPELINE SUCCEEDED", style="bold green")),
            border_style="green",
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            Align.center(Text("❌ PIPELINE ENDED — THRESHOLDS NOT MET", style="bold red")),
            border_style="red",
            padding=(1, 2),
        ))

    # Final status table
    console.print(build_status_table(iterations, score, cost, tf_valid))

    # Generated code
    if code:
        console.print("\n[bold]📄 Generated Terraform Code:[/bold]")
        console.print(Panel(
            code,
            title="workspace/main.tf",
            border_style="cyan",
            expand=True,
        ))

        # Save the final code
        output_path = Path("workspace") / "main.tf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        console.print(f"\n[success]💾 Saved to {output_path.resolve()}[/success]")

    # Architect reflection
    reflection = final_state.get("architect_reflection", "")
    if reflection:
        console.print("\n[bold]🧠 Architect's Final Reasoning:[/bold]")
        console.print(Panel(reflection, border_style="blue", expand=True))


# ─────────────────────────────────────────────────────────────────────
#  Main Pipeline Execution
# ─────────────────────────────────────────────────────────────────────


def run_pipeline(user_prompt: str):
    """
    Execute the full IaC Orchestrator pipeline with real-time Rich output.

    Uses LangGraph's .stream() to iterate through nodes and display
    live updates for each agent's execution.
    """
    from src.graph import app

    console.print(f"\n[bold]🚀 Starting pipeline for:[/bold] {user_prompt}\n")

    # Initialize the state
    initial_state = {
        "user_prompt": user_prompt,
        "rag_context": "",
        "current_code": "",
        "architect_reflection": "",
        "security_critique": "",
        "finops_critique": "",
        "linter_logs": "",
        "security_score": 0.0,
        "monthly_cost": 0.0,
        "iteration_count": 0,
        "terraform_valid": False,
    }

    # Stream through the graph
    final_state = initial_state.copy()

    try:
        for event in app.stream(initial_state, stream_mode="updates"):
            for node_name, state_update in event.items():
                print_node_header(node_name)

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(f"Processing {node_name}...", total=None)
                    # The node already executed — just show the spinner briefly
                    time.sleep(0.3)

                print_node_output(node_name, state_update)
                final_state.update(state_update)

    except KeyboardInterrupt:
        console.print("\n[warning]⚠️  Pipeline interrupted by user.[/warning]")
    except Exception as e:
        console.print(f"\n[error]❌ Pipeline error: {e}[/error]")
        console.print_exception()

    # Display final results
    print_final_result(final_state)


# ─────────────────────────────────────────────────────────────────────
#  CLI Entry Point
# ─────────────────────────────────────────────────────────────────────


def main():
    """Main entry point for the IaC Orchestrator CLI."""
    print_banner()

    # Check for API keys
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        console.print(
            "[error]❌ OPENAI_API_KEY not set. "
            "Copy .env.example to .env and add your key.[/error]"
        )
        sys.exit(1)
    elif provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        console.print(
            "[error]❌ ANTHROPIC_API_KEY not set. "
            "Copy .env.example to .env and add your key.[/error]"
        )
        sys.exit(1)

    console.print(f"[info]Using LLM provider: [bold]{provider}[/bold][/info]\n")

    # Check CLI tools
    print_tool_status()

    # Get user input
    console.print("[bold]Describe your infrastructure requirement:[/bold]")
    console.print("[dim](e.g., 'Deploy a secure, private EKS cluster in us-east-1')[/dim]\n")

    try:
        user_prompt = console.input("[bold cyan]▶ [/bold cyan]")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Goodbye![/dim]")
        sys.exit(0)

    if not user_prompt.strip():
        console.print("[error]❌ Empty prompt. Please describe your infrastructure.[/error]")
        sys.exit(1)

    # Run the pipeline
    run_pipeline(user_prompt.strip())


if __name__ == "__main__":
    main()
