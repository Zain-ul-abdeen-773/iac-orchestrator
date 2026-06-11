# 🤖 Autonomous Multi-Agent IaC Orchestrator

> *Where probabilistic AI meets deterministic infrastructure — a self-healing, security-first Terraform generation pipeline.*

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Web_Backend-009688?style=flat-square&logo=fastapi&logoColor=white)
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
4. [Interfaces: CLI & Web UI](#4-interfaces-cli--cyberpunk-web-ui)
5. [Required Tech Stack & Integrations](#5-required-tech-stack--integrations)
6. [IDE Agent Execution Directives](#6-ide-agent-execution-directives)
7. [Extended Features & Proposed Additions](#7-extended-features--proposed-additions)

---

## 1. Project Vision & Architecture

Traditional LLM-based code generation struggles significantly with IaC because cloud providers constantly update their APIs, leading to **hallucinated, deprecated, or syntactically invalid** configuration arguments. Furthermore, IaC deployments have a zero-tolerance policy for syntax errors and security misconfigurations.

This project solves those problems by moving beyond simple text generation — combining **probabilistic LLM agents** with **strictly deterministic DevOps tools**. By anchoring the creative flexibility of AI to the unforgiving reality of local CLI binaries, the system creates a **self-healing deployment pipeline**.

To achieve state-of-the-art reliability and production-readiness, this system implements four core pillars:

| Pillar | Mechanism | Purpose |
|---|---|---|
| 🔍 **RAG** | ChromaDB + Terraform AWS Docs | Prevent stale/hallucinated resource arguments |
| 🔩 **Structured Tool Calling** | Pydantic + Anthropic/OpenAI APIs | Eliminate fragile regex parsing |
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
│  ┌─────────────┐    ┌──────────────┐    ┌──────────┐  ┌──────────┐   │
│  │  Context    │───▶│   Cloud      │───▶│ SecOps   │─▶│ FinOps   │   │
│  │  Retriever  │    │  Architect   │    │ Adversary│  │  Agent   │   │
│  │   (RAG)     │◀───│   Agent      │    │  Agent   │  │          │   │
│  └─────────────┘    └──────────────┘    └──────────┘  └────┬─────┘   │
│                            ▲                               │         │
│                            │  [FAIL — self heal loop]      │         │
│                            │                               ▼         │
│                     ┌──────┴──────────────────────────────────────┐  │
│                     │         Deterministic Gatekeeper            │  │
│                     │   terraform validate │ checkov │ infracost  │  │
│                     └─────────────────────────────────────────────┘  │
│                                      │                               │
│                         [score ≥ 90 AND exit_code=0]                 │
│                                      │                               │
│                                      ▼                               │
│                                    END ✅                             │
│                    (or END ❌ if iteration_count ≥ 5)                 │
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
    terraform_valid: bool       # Gatekeeper syntax validation flag
```

### 2.2 Node Definitions

#### Node A — Context Retriever (RAG)
Takes the `user_prompt` and executes a similarity search against a local vector database (ChromaDB) loaded with official Terraform AWS Provider documentation. Updates `rag_context` with valid resource block examples.

#### Node B — Cloud Architect Agent
The core generation engine. Ingests the `user_prompt`, `rag_context`, and crucially, all historical critiques/logs from previous failed iterations. **Structured Output** is strictly enforced using Pydantic models to ensure standard responses and reasoning steps.

#### Node C — SecOps Adversary Agent
Red-team logic auditing and threat modeling. Analyzes the current HCL code for vulnerabilities that static linters miss (e.g., `0.0.0.0/0` ingress rules, missing VPC flow logs). Updates `security_critique` with actionable, line-number-specific feedback.

#### Node D — FinOps Cost Agent
Budget optimization and resource right-sizing. Analyzes the current code alongside any available Infracost data to suggest structural savings (e.g., graviton instances over intel, or `gp3` vs `io1` volumes).

#### Node E — Deterministic Gatekeeper
Executes factual reality checks using standard industry binaries. This node acts as the **compiler** — completely separated from AI hallucination.
1. Writes the string payload to `workspace/main.tf`
2. Runs `terraform fmt`
3. Runs `terraform init` & `terraform validate`
4. Runs `checkov` & computes `security_score`
5. Runs `infracost` & computes `monthly_cost`

---

## 3. Graph Routing Logic (Edges)

The true power of this system lies in its **cyclic routing**. After Node E (Gatekeeper) executes, the LangGraph conditional edge evaluates the current state to determine the next step:

| Condition | Route | Description |
|---|---|---|
| ✅ `score ≥ 90` AND `valid = True` AND `iterations < 5` | `END` | Artifact is secure, valid, deployment-ready |
| ❌ Any threshold missed AND `iterations < 5` | `Architect` | Full error context injected; Architect rewrites |
| ⛔ `iterations ≥ 5` | `END` (flagged) | Timeout safety catch — prevents infinite API billing |

---

## 4. Interfaces: CLI & Cyberpunk Web UI

The Orchestrator supports both a CLI and a dynamic Web application.

### 🌐 Live Cyberpunk Web Dashboard (FastAPI + Server-Sent Events)
A dynamic, asynchronous frontend implemented in `index.html` and served by `FastAPI` (`server.py`). 
- **Real-Time Streaming**: The backend pushes node execution events (RAG, Architect, SecOps, FinOps, Gatekeeper) over SSE directly to the browser.
- **Dynamic Syntax Highlighting**: Renders Terraform HCL live as the Architect iterates.
- **Progressive Timers**: Shows elapsed execution time during heavy LLM generation.
- **Security & Cost Dashboards**: Visually processes red-team critiques and cost metrics.

**To Run:**
```bash
uvicorn server:app --reload
```
Navigate to `http://localhost:8000`.

### 🖥️ Rich CLI Terminal Interface
For developers who prefer the terminal, `main.py` provides a beautiful interactive CLI using the `rich` library.
- Displays live-updating tables for shifting cost estimations and security scores.
- Renders agent debate logs inline with custom color-coded styles.

**To Run:**
```bash
python main.py
```

---

## 5. Required Tech Stack & Integrations

### Python Libraries
| Category | Library | Purpose |
|---|---|---|
| Orchestration | `langgraph`, `langchain-core` | State graph management and primitives |
| LLM Integration | `langchain-openai`, `langchain-aws` | LLM adapters (OpenAI, Bedrock/Claude) |
| Web Backend | `fastapi`, `uvicorn`, `sse-starlette` | Async Web UI & SSE Event Streaming |
| Vector DB | `chromadb`, `sentence-transformers` | Embeddings and RAG storage |
| Validation | `pydantic` | Structured output enforcement |
| Terminal UI | `rich` | Aesthetic formatting |

### System CLI Tools (must be on `$PATH`)
| Tool | Vendor | Role |
|---|---|---|
| `terraform` | HashiCorp | Syntax validation and initialization |
| `checkov` | Palo Alto Networks | Cloud security static analysis |
| `infracost` | Infracost Inc. | HCL parsing and cost estimation |

---

## 6. IDE Agent Execution Directives

> **To the AI Coding Assistant (Cursor / Copilot / etc.):** Ensure the following patterns are strictly maintained when interacting with this repository.

1. **Subprocess Resilience**: Tools in `src/tools/gatekeeper.py` MUST NOT crash the graph if they throw a non-zero exit code. They must capture `stderr` and inject it back into the LangGraph state.
2. **Structured LLM Output**: The Architect node MUST use `.with_structured_output()` to prevent markdown block pollution in HCL generation.
3. **Async Streaming**: All UI components (both CLI `.stream()` and FastAPI SSE `.astream()`) rely on the update dictionaries emitted by the graph nodes. Do not alter the node output keys (`architect_reflection`, `security_critique`, etc.) without updating the frontend renderers in `index.html`.

---

## 7. Extended Features & Proposed Additions

- **GitOps Auto-PR**: Automatically open a Pull Request against a target repository on `END ✅` with the full agent debate log as the PR description.
- **Drift Detection Agent**: Compare deployed live state to desired `current_code` state and trigger a regeneration cycle if drift exceeds thresholds.
- **Compliance Auditor Agent**: Implement Open Policy Agent (OPA) to evaluate code against standard frameworks (HIPAA, SOC2, PCI-DSS).
- **Prompt Caching**: Use semantic caching (GPTCache) to bypass LLM generation for frequently requested architectures.
- **Multi-Cloud Support**: Parameterize the Retriever and Gatekeeper to ingest and evaluate Azure or GCP Terraform resources.

---

*Built with FastAPI · LangGraph · Terraform · Checkov · Infracost · ChromaDB · Claude 4.5 Opus*
