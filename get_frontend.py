import os
import sys
from ask_claude import ask_claude

def main():
    with open("frontend-design.md", "r", encoding="utf-8") as f:
        guidelines = f.read()

    prompt = f"""The following are frontend design guidelines for my project:

<frontend-design>
{guidelines}
</frontend-design>

My project "IaC Orchestrator" is currently a terminal-based application that uses AI agents (Cloud Architect, SecOps Adversary, FinOps Cost Optimizer, Gatekeeper) to generate, validate, and secure AWS Terraform code based on a user's prompt. 

I want to build a web-based UI for it.
I need a stunning frontend interface (dashboard) that visualizes this multi-agent pipeline. It should have:
1. An input area for the user's infrastructure prompt.
2. A visualization of the AI agent pipeline (RAG -> Architect -> SecOps -> FinOps -> Gatekeeper) with status indicators.
3. Areas to display the generated Terraform code, security findings, cost estimate, and validation results.

Please write a complete, self-contained `index.html` file using HTML, CSS (Vanilla), and JS (Vanilla) that implements this dashboard. 
Follow the frontend-design guidelines strictly! Pick a bold, modern, "industrial/utilitarian" or "cyberpunk/hacker" aesthetic that fits a cloud infrastructure/security tool. Use striking typography and micro-animations.

Provide ONLY the raw code inside a single ```html codeblock so I can easily save it. Do not include introductory or concluding text outside the codeblock.
"""

    print("Asking Claude for the frontend...", file=sys.stderr)
    try:
        response = ask_claude(prompt)
        with open("claude_frontend_response.txt", "w", encoding="utf-8") as f:
            f.write(response)
        print("Response successfully saved to claude_frontend_response.txt", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
