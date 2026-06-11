"""
Demo Runner — Executes the IaC Orchestrator pipeline non-interactively.

Runs a single prompt through the full pipeline and displays results.
Used for testing and demonstration purposes.
"""

import os
import sys

# Fix Windows console encoding for Unicode/emoji support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ["PYTHONIOENCODING"] = "utf-8"

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.theme import Theme

# Create a force-terminal console for proper rendering
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

console = Console(theme=CUSTOM_THEME, force_terminal=True)

# Monkey-patch the main module's console for compatibility
import main as main_module
main_module.console = console


def run_demo():
    """Run a demo of the IaC Orchestrator with a sample prompt."""
    main_module.print_banner()

    provider = os.getenv("LLM_PROVIDER", "openai")
    console.print(f"[info]Using LLM provider: [bold]{provider}[/bold][/info]\n")

    # Check tools
    main_module.print_tool_status()

    # Demo prompt
    demo_prompt = "Deploy a secure S3 bucket with encryption, versioning, and access logging in us-east-1"

    console.print(f"\n[bold]DEMO MODE - Running with prompt:[/bold]")
    console.print(f"[cyan]{demo_prompt}[/cyan]\n")

    # Run the pipeline
    main_module.run_pipeline(demo_prompt)


if __name__ == "__main__":
    run_demo()
