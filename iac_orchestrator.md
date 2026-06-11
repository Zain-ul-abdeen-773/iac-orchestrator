# 🤖 Autonomous Multi-Agent IaC Orchestrator

> *Where probabilistic AI meets deterministic infrastructure — a self-healing, security-first Terraform generation pipeline.*

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-4B8BBE?style=flat-square)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?style=flat-square&logo=terraform)
![Checkov](https://img.shields.io/badge/Checkov-Security-E34F26?style=flat-square)
![Infracost](https://img.shields.io/badge/Infracost-FinOps-00B09B?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 📑 Table of Contents

1. [Project Vision & Architecture](#1-project-vision--architecture)
2. [The Multi-Agent State Machine](#2-the-multi-agent-state-machine-langgraph)
   - [State Schema Definition](#21-state-schema-definition)
   - [Node Definitions](#22-node-definitions)
3. [Graph Routing Logic](#3-graph-routing-logic-edges)
4. [Required Tech Stack & Integrations](#4-required-tech-stack--integrations)
5. [IDE Agent Execution Directives](#5-ide-agent-execution-directives)
6. [➕ Extended Features & Proposed Additions](#6--extended-features--proposed-additions)
   - [Node F: Drift Detection Agent](#node-f-drift-detection-agent)
   - [Node G: Compliance Auditor Agent](#node-g-compliance-auditor-agent)
   - [GitOps Auto-PR Integration](#gitops-auto-pr-integration)
   - [Web UI via Streamlit/Gradio](#web-ui-via-streamlitgradio)
   - [Prompt Caching Layer](#prompt-caching-layer)
   - [OpenTelemetry Pipeline Observability](#opentelemetry-pipeline-observability)
   - [Multi-Cloud Provider Support](#multi-cloud-provider-support)
   - [Notification Agent](#notification-agent)

---

## 1. Project Vision & Architecture

Traditional LLM-based code generation struggles significantly with IaC because cloud providers constantly update their APIs, leading to **hallucinated, deprecated, or syntactically invalid** configuration arguments. Furthermore, IaC deployments have a zero-tolerance policy for syntax errors and security misconfigurations.

This project solves those problems by moving beyond simple text generation — combining **probabilistic LLM agents** with **strictly deterministic DevOps tools**. By anchoring the creative flexibility of AI to the unforgiving reality of local CLI binaries, the system creates a **self-healing deployment pipeline**.

To achieve state-of-the-art reliability and production-readiness, this system implements four core pillars:

| Pillar | Mechanism | Purpose |
|---|---|---|
| 🔍 **RAG** | ChromaDB + Terraform AWS Docs | Prevent stale/hallucinated resource arguments |
| 🔩 **Structured Tool Calling** | Pydantic + OpenAI/Anthropic APIs | Eliminate fragile regex parsing |
| 🧠 **Chain-of-Thought Reflection** | Architect's `thought_process` field | Reduce logical errors and syntax hallucinations |
| 🛡️ **Multi-Dimensional Auditing** | Terraform CLI + Checkov + Infracost | Catch syntax, security, and budget violations |

---

## 2. The Multi-Agent State Machine (LangGraph)

The core orchestration relies on a **directed cyclic graph**. Instead of a linear single-pass generation, the state is passed cyclically between specialized agents and the deterministic Gatekeeper node until all strict programmatic thresholds are met — or the maximum iteration limit is reached.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        LANGGRAPH STATE MACHINE                       │
│                                                                      │
│   START                                                              │
│     │                                                                │
│     ▼                                                                │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────┐  ┌──────────┐  │
│  │  Context    │───▶│   Cloud      │───▶│ SecOps   │─▶│ FinOps   │  │
│  │  Retriever  │    │  Architect   │    │ Adversary│  │  Agent   │  │
│  │   (RAG)     │◀───│   Agent      │    │  Agent   │  │          │  │
│  └─────────────┘    └──────────────┘    └──────────┘  └────┬─────┘  │
│                            ▲                               │        │
│                            │  [FAIL — self heal loop]      │        │
│                            │                               ▼        │
│                     ┌──────┴──────────────────────────────────────┐ │
│                     │         Deterministic Gatekeeper             │ │
│                     │   terraform validate │ checkov │ infracost   │ │
│                     └─────────────────────────────────────────────┘ │
│                                      │                              │
│                         [score ≥ 90 AND exit_code=0]                │
│                                      │                              │
│                                      ▼                              │
│                                    END ✅                            │
│                    (or END ❌ if iteration_count ≥ 5)                │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.1 State Schema Definition

Use `typing.TypedDict` and `pydantic` to enforce strict state typing. This prevents the graph from passing malformed payloads between nodes.

```python
from typing import TypedDict, List, Dict, Any
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    user_prompt: str            # The original request (e.g., "Deploy an EKS cluster")
    rag_context: str            # Retrieved text snippets from Terraform AWS docs
    current_code: str           # The raw HCL payload generated by the Architect
    architect_reflection: str   # The LLM's step-by-step reasoning for the current code iteration
    security_critique: str      # Hostile feedback and red-team findings from the SecOps Agent
    finops_critique: str        # Budget optimization feedback from the FinOps Agent
    linter_logs: str            # Raw stderr/stdout and JSON crash reports from CLI tools
    security_score: float       # 0-100 quantitative score calculated from Checkov's output
    monthly_cost: float         # Projected monthly USD cost parsed from Infracost
    iteration_count: int        # Failsafe counter to prevent infinite API billing loops (max 5)
```

### 2.2 Node Definitions

#### Node A — Context Retriever (RAG)

**Task:** Takes the `user_prompt` and executes a similarity search against a local vector database (e.g., ChromaDB or FAISS) loaded with official Terraform AWS Provider documentation.

**Output:** Updates `rag_context` with valid resource block examples. For instance, if the user asks for a secure S3 bucket, this node retrieves the exact current syntax for `aws_s3_bucket`, `aws_s3_bucket_public_access_block`, and `aws_s3_bucket_server_side_encryption_configuration`.

---

#### Node B — Cloud Architect Agent

**Role:** The core generation engine responsible for writing the infrastructure payload.

**Input:** `user_prompt`, `rag_context`, and crucially, all historical critiques/logs from previous failed iterations.

**AI Technique — Structured Output:** This agent **MUST** be constrained using OpenAI/Anthropic tool-calling APIs to return a specific Pydantic model. It is **forbidden** from returning raw markdown or conversational text.

```python
class ArchitectOutput(BaseModel):
    thought_process: str = Field(
        description="Step-by-step reasoning on how to build this architecture, "
                    "or a detailed plan on how to fix the specific errors found in "
                    "the previous linter_logs."
    )
    terraform_code: str = Field(
        description="The complete, raw, syntactically valid HCL code. "
                    "Do not include markdown formatting."
    )
```

---

#### Node C — SecOps Adversary Agent

**Role:** Red-team logic auditing and threat modeling.

**Input:** `current_code`

**Task:** Identify logical architecture flaws that static linters often miss. Examples:
- `0.0.0.0/0` ingress rules on sensitive management ports (SSH/22, RDP/3389)
- Overly broad wildcard (`*`) permissions in inline IAM policies
- Missing VPC flow logs on sensitive networks
- Unencrypted EBS volumes or RDS storage
- S3 buckets without versioning or lifecycle policies

**Output:** Updates `security_critique` with **actionable, line-number-specific** feedback.

---

#### Node D — FinOps Cost Agent

**Role:** Budget optimization and resource right-sizing.

**Input:** `user_prompt`, `current_code`, raw Infracost JSON output (from Gatekeeper)

**Task:** Suggest structural architectural changes to save money without compromising the user's core intent. Examples:
- *"Switch the `io1` EBS volume to `gp3` to save ~20%"*
- *"Recommend `t4g.micro` (ARM Graviton) instead of `t3.micro` for baseline savings"*
- *"Flag unattached Elastic IPs — they incur a cost when unused"*
- *"Consider Reserved Instances for predictable workloads"*

**Output:** Updates `finops_critique`.

---

#### Node E — Deterministic Gatekeeper

**Role:** Executes factual reality checks using standard industry binaries. This node acts as the **compiler** — completely separated from AI hallucination.

**Actions:**

1. Writes the string payload from `current_code` to `workspace/main.tf`
2. Runs `terraform fmt` → standardizes formatting
3. Runs `terraform validate` → catches missing variables, incorrect block types, undeclared dependencies
4. Runs `checkov -f workspace/main.tf -o json` → parses JSON to calculate `security_score`:
   - Base score: **100**
   - Subtract **10** per `MEDIUM` severity finding
   - Subtract **25** per `HIGH` / `CRITICAL` finding
5. Runs `infracost breakdown --path workspace/ --format json` → extracts `totalMonthlyCost`

**Output:** Updates `linter_logs` with syntax errors, populates `security_score` and `monthly_cost`.

> ⚠️ **Critical:** If a subprocess fails (non-zero exit code), it **MUST NOT** crash the application. It must capture `stderr` and return it cleanly to the LangGraph state for the Architect to review.

---

## 3. Graph Routing Logic (Edges)

The true power of this system lies in its **cyclic routing**. After Node E (Gatekeeper) executes, the LangGraph conditional edge evaluates the current state to determine the next step:

```
AFTER GATEKEEPER RUNS:

  ┌─────────────────────────────────────────────────────────┐
  │                  ROUTING DECISION TREE                  │
  │                                                         │
  │  security_score >= 90                                   │
  │  AND terraform validate exit_code == 0                  │
  │  AND iteration_count < 5          ──────▶  END ✅        │
  │                                                         │
  │  Any condition above fails                              │
  │  AND iteration_count < 5          ──────▶  Architect 🔁  │
  │                                           (self-heal)   │
  │  iteration_count >= 5             ──────▶  END ❌        │
  │                                           (flagged)     │
  └─────────────────────────────────────────────────────────┘
```

| Condition | Route | Description |
|---|---|---|
| ✅ `score ≥ 90` AND `exit_code = 0` AND `iterations < 5` | `END` | Artifact is secure, valid, deployment-ready |
| ❌ Any threshold missed AND `iterations < 5` | `Architect` | Full error context injected; Architect rewrites |
| ⛔ `iterations ≥ 5` | `END` (flagged) | Timeout safety catch — prevents infinite API billing |

---

## 4. Required Tech Stack & Integrations

### Python Libraries

| Category | Library | Purpose |
|---|---|---|
| Orchestration | `langgraph` | State graph management |
| Orchestration | `langchain-core` | Base chain primitives |
| LLM Integration | `langchain-openai` / `langchain-anthropic` | LLM provider adapters |
| Vector DB | `chromadb` | Local, lightweight RAG vector store |
| Embeddings | `sentence-transformers` | Embedding generation for RAG |
| Validation | `pydantic` | Architect structured output enforcement |
| Terminal UI | `rich` | Aesthetic terminal formatting and live tables |

### System CLI Tools (must be on `$PATH`)

| Tool | Vendor | Role |
|---|---|---|
| `terraform` | HashiCorp | Syntax validation and initialization |
| `checkov` | Palo Alto Networks / Prisma | Cloud security static analysis |
| `infracost` | Infracost Inc. | HCL parsing and cost estimation |
| `opa` *(optional)* | CNCF / Open Policy Agent | Custom corporate Rego policy enforcement |

---

## 5. IDE Agent Execution Directives

> **To the AI Coding Assistant (Cursor / Copilot / etc.):** Execute the following steps sequentially to scaffold, wire, and build this system. Ensure you handle edge cases, particularly around subprocess execution.

### Step 1 — Initialization & Mock Environment

- Initialize a Python project with `pyproject.toml` or `requirements.txt`. Explicitly include all Python libraries listed in Section 4.
- Create the standard directory structure:

```
project-root/
├── src/
│   ├── agents/        # LLM node logic and prompt templates
│   ├── tools/         # Python subprocess wrappers and JSON parsers
│   └── rag/           # Vector store setup and querying logic
├── workspace/         # Temporary directory for .tf file generation and CLI execution
├── main.py            # Entrypoint
└── pyproject.toml
```

---

### Step 2 — The Subprocess Tooling (`src/tools/gatekeeper.py`)

Write a robust Python class named `DevOpsCLI`.

- Implement **async methods** for `run_terraform_validate()`, `run_checkov()`, and `run_infracost()`
- Use Python's `subprocess` module with `capture_output=True` and `text=True`
- Write **resilient JSON parsers**: extract exact error lines and failure IDs from Checkov; extract `totalMonthlyCost` from Infracost
- Handle `JSONDecodeError` exceptions gracefully in case CLI tools return raw strings instead of JSON

```python
# Pattern for every subprocess call
result = subprocess.run(
    ["checkov", "-f", "workspace/main.tf", "-o", "json"],
    capture_output=True,
    text=True
)
if result.returncode != 0:
    # Do NOT raise — return stderr to state
    return {"error": result.stderr, "score": 0}
```

---

### Step 3 — Agent Construction (`src/agents/nodes.py`)

- Implement the **Architect node** using `.with_structured_output(ArchitectOutput)` — strictly required to prevent markdown blocks from breaking file writes
- Inject a system prompt declaring the agent a *"Senior Cloud Architect fixing errors in a CI/CD pipeline"*
- Implement **SecOps** and **FinOps** agents using standard prompt templates
- Their system prompts must command them to be **ruthless, highly specific, and pedantic** regarding AWS best practices

---

### Step 4 — RAG Implementation (`src/rag/document_loader.py`)

- Create a script to mock-load Terraform AWS documentation (For MVP: create a localized text file with standard AWS resource definitions — VPCs, EC2s, RDS instances — and load them into a local ChromaDB collection)
- Create the **retriever node function** that:
  1. Embeds the `user_prompt`
  2. Fetches the **top 3 most relevant context chunks**
  3. Passes them into the Architect's initial state

---

### Step 5 — LangGraph Compilation (`src/graph.py`)

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(AgentState)

# Add nodes
graph.add_node("retrieve", retrieve_context)
graph.add_node("architect", run_architect)
graph.add_node("secops", run_secops)
graph.add_node("finops", run_finops)
graph.add_node("gatekeeper", run_gatekeeper)

# Wire edges
graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "architect")
graph.add_edge("architect", "secops")
graph.add_edge("secops", "finops")
graph.add_edge("finops", "gatekeeper")

# Conditional routing
graph.add_conditional_edges("gatekeeper", route_after_gatekeeper, {
    "architect": "architect",
    "end": END
})

app = graph.compile()
```

---

### Step 6 — Entrypoint (`main.py`)

- Build a **rich, interactive CLI interface** using the `rich` library for aesthetic terminal formatting and live layout
- Take user input for infrastructure requirements
- Execute the compiled graph using `.astream_events()` or `.stream()` to allow users to **watch iterative refinement loops in real time**
- Use terminal spinners and **live-updating tables** to display:
  - Shifting cost estimations per iteration
  - Security score deltas per loop
  - Agent debate logs (SecOps critique vs Architect response)

---

## 6. ➕ Extended Features & Proposed Additions

> The following additions extend the MVP into a production-grade, enterprise-ready platform. Each is designed to integrate cleanly into the existing LangGraph state machine.

---

### Node F: Drift Detection Agent

**Motivation:** Deployed infrastructure frequently diverges from its desired IaC state due to manual console changes or hotfixes. This agent closes the loop between generation and runtime.

**Mechanism:** After deployment, this agent runs `terraform plan` against live provider state and diffs the output against `current_code`. If drift exceeds a configurable threshold (e.g., >3 resource mutations), it triggers a **re-generation cycle** with the drifted state injected as context.

**State addition:**
```python
drift_report: str   # Output of terraform plan showing live vs desired delta
drift_detected: bool
```

---

### Node G: Compliance Auditor Agent

**Motivation:** Enterprise environments must comply with frameworks like HIPAA, SOC 2, PCI-DSS, or CIS Benchmarks. Checkov covers a subset but lacks business-context awareness.

**Mechanism:** This agent receives `current_code` and a user-specified `compliance_profile` (e.g., `"hipaa"`, `"pci-dss"`). It cross-references the generated HCL against a curated checklist of compliance controls and emits a structured compliance gap report.

**Tools:** Integrates with `opa` (Open Policy Agent) using custom **Rego policies** per compliance framework.

**State addition:**
```python
compliance_profile: str       # e.g., "hipaa", "soc2", "cis-aws"
compliance_gaps: List[str]    # Human-readable list of unmet controls
compliance_pass: bool
```

---

### GitOps Auto-PR Integration

**Motivation:** The current system ends at artifact generation. Closing the loop to actual version-controlled deployment is the final production-readiness step.

**Mechanism:** On `END ✅`, a post-processing step uses the **GitHub REST API** (via `PyGithub`) to:
1. Create a new branch `iac/auto-gen-{timestamp}` in a target repository
2. Commit `workspace/main.tf` to it
3. Open a Pull Request with the full agent debate log (SecOps critiques, FinOps suggestions, iteration history) as the PR description

**Libraries:** `PyGithub`, `gitpython`

---

### Web UI via Streamlit/Gradio

**Motivation:** Not all users are comfortable with terminal interfaces. A visual dashboard makes the agent pipeline accessible to DevOps teams and non-engineers alike.

**Proposed Stack:** `Streamlit` (preferred for rapid development)

**Features:**
- Natural language input box for infrastructure requirements
- Real-time streaming agent logs in a scrollable panel
- Live-updating **security score gauge** and **cost estimation card**
- Diff viewer showing HCL changes between each iteration
- One-click download of the final `main.tf` artifact

---

### Prompt Caching Layer

**Motivation:** Repeated similar infrastructure requests (e.g., "Deploy a standard VPC") send the same RAG context and system prompts to the LLM on every iteration, wasting tokens and API budget.

**Mechanism:** Implement a **semantic cache** using `GPTCache` or a simple Redis + cosine similarity lookup. If an incoming `user_prompt` has cosine similarity > 0.92 with a cached prompt, return the cached `ArchitectOutput` directly and bypass the LLM call.

**Impact:** Can reduce API costs by 30–60% for teams running repetitive infrastructure patterns.

---

### OpenTelemetry Pipeline Observability

**Motivation:** Production agentic pipelines need introspection. Without tracing, debugging a failed 5-iteration loop is guesswork.

**Mechanism:** Instrument every node with **OpenTelemetry spans** using `opentelemetry-sdk`. Export traces to a local **Jaeger** instance (Docker Compose sidecar). Each span captures:
- Node name and execution duration
- Token usage per LLM call
- Subprocess exit codes and runtimes
- Score deltas across iterations

**Libraries:** `opentelemetry-sdk`, `opentelemetry-exporter-jaeger`

---

### Multi-Cloud Provider Support

**Motivation:** The current design is AWS-specific. Enterprise users often operate across AWS, Azure, and GCP simultaneously.

**Proposed Extension:**
- Parameterize the RAG loader to ingest **Azure Terraform Provider** or **Google Cloud Terraform Provider** documentation based on a `cloud_provider` flag
- Extend the Gatekeeper to conditionally invoke `tflint` with the appropriate provider ruleset
- Extend Infracost — it natively supports AWS, Azure, and GCP cost estimation

**State addition:**
```python
cloud_provider: str   # "aws" | "azure" | "gcp" | "multi"
```

---

### Notification Agent

**Motivation:** Long-running pipelines (especially those hitting the 5-iteration limit) should not require a human to watch the terminal.

**Mechanism:** A lightweight post-processing hook that fires after `END` (success or failure) and sends a structured summary via:
- **Slack** (via `slack_sdk` webhook) — with a formatted message showing final security score, monthly cost, iteration count, and a link to the GitOps PR
- **Email** (via `smtplib`) — for async/scheduled pipeline runs

---

## 🗺️ Full System Architecture Overview

```
                        USER INPUT
                            │
                            ▼
              ┌─────────────────────────┐
              │    main.py  (Rich CLI)  │
              │    or Streamlit Web UI  │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │   LangGraph State Graph │
              │                         │
              │  ┌───────────────────┐  │
              │  │  Context Retriever│  │◀─── ChromaDB (Terraform Docs)
              │  │      (RAG)        │  │
              │  └────────┬──────────┘  │
              │           │             │
              │  ┌────────▼──────────┐  │
              │  │  Cloud Architect  │◀─┤── rag_context + all critiques
              │  │  (Structured LLM) │  │
              │  └────────┬──────────┘  │
              │           │             │
              │  ┌────────▼──────────┐  │
              │  │  SecOps Adversary │  │
              │  │  (Red-Team LLM)   │  │
              │  └────────┬──────────┘  │
              │           │             │
              │  ┌────────▼──────────┐  │
              │  │   FinOps Agent    │  │
              │  │  (Cost LLM)       │  │
              │  └────────┬──────────┘  │
              │           │             │
              │  ┌────────▼──────────┐  │
              │  │   Gatekeeper      │  │
              │  │  terraform CLI    │  │
              │  │  checkov          │  │
              │  │  infracost        │  │
              │  └────────┬──────────┘  │
              └───────────┼─────────────┘
                          │
              ┌───────────▼─────────────┐
              │  score≥90 & valid?       │
              │  YES ──▶ END ✅          │
              │  NO  ──▶ Loop back       │
              │  ≥5 iterations ──▶ ❌    │
              └─────────────────────────┘
                          │
              ┌───────────▼─────────────┐
              │  Post-Processing        │
              │  ├─ GitOps Auto-PR      │
              │  ├─ Slack Notification  │
              │  └─ OTel Trace Export   │
              └─────────────────────────┘
```

---

## ⚡ Quick Start (Summary)

```bash
# 1. Clone and install
git clone https://github.com/your-org/iac-orchestrator
cd iac-orchestrator
pip install -r requirements.txt

# 2. Install CLI tools
brew install terraform infracost
pip install checkov

# 3. Set environment variables
export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY
export INFRACOST_API_KEY=...

# 4. Run
python main.py
# > Describe your infrastructure: Deploy a secure, private EKS cluster in us-east-1
```

---

## 📌 Design Principles

> *"Give the LLM a paintbrush. Give the pipeline a compiler."*

- **Hallucination is a distribution problem** — RAG grounds generation in real, versioned documentation
- **Security is not optional** — Checkov thresholds are hard gates, not soft warnings
- **Cycles beat passes** — a system that can self-heal across 5 iterations will always outperform one that generates once
- **Structured outputs over parsing** — regex on LLM output is a liability; Pydantic contracts are an asset
- **Determinism at the boundary** — CLI tools (Terraform, Checkov, Infracost) are the single source of truth for correctness

---

*Built with LangGraph · Terraform · Checkov · Infracost · ChromaDB · Pydantic · Rich*
