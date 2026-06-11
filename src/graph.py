"""
LangGraph State Machine — Core orchestration graph for the IaC pipeline.

Compiles the directed cyclic graph that routes state between specialized agents
and the deterministic Gatekeeper until all thresholds are met or the maximum
iteration limit is reached.
"""

import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.nodes import run_architect, run_finops, run_gatekeeper, run_secops
from src.agents.schemas import AgentState
from src.rag.retriever import retrieve_context


# ─────────────────────────────────────────────────────────────────────
#  Pipeline Configuration
# ─────────────────────────────────────────────────────────────────────

MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "5"))
SECURITY_SCORE_THRESHOLD = float(os.getenv("SECURITY_SCORE_THRESHOLD", "90"))


# ─────────────────────────────────────────────────────────────────────
#  Conditional Routing — Post-Gatekeeper Decision Tree
# ─────────────────────────────────────────────────────────────────────


def route_after_gatekeeper(state: AgentState) -> str:
    """
    Evaluate the current state after the Gatekeeper node and determine
    the next step in the pipeline.

    Routing Decision Tree:
    ┌─────────────────────────────────────────────────────┐
    │  security_score >= 90                               │
    │  AND terraform validate exit_code == 0              │
    │  AND iteration_count < MAX_ITERATIONS  ──▶  END ✅  │
    │                                                     │
    │  Any condition above fails                          │
    │  AND iteration_count < MAX_ITERATIONS  ──▶  🔁      │
    │                                         (self-heal) │
    │  iteration_count >= MAX_ITERATIONS     ──▶  END ❌  │
    └─────────────────────────────────────────────────────┘
    """
    iteration_count = state.get("iteration_count", 0)
    security_score = state.get("security_score", 0.0)
    terraform_valid = state.get("terraform_valid", False)

    # Safety catch — prevent infinite loops / API billing
    if iteration_count >= MAX_ITERATIONS:
        return "end"

    # Success criteria
    if security_score >= SECURITY_SCORE_THRESHOLD and terraform_valid:
        return "end"

    # Self-heal — loop back to Architect with full error context
    return "architect"


# ─────────────────────────────────────────────────────────────────────
#  Graph Construction
# ─────────────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """
    Build and return the compiled LangGraph state machine.

    Graph topology:
        START → retrieve → architect → secops → finops → gatekeeper
                              ↑                              │
                              └──── [FAIL — self-heal] ──────┘
                                                             │
                                            [PASS or MAX] → END
    """
    graph = StateGraph(AgentState)

    # ── Add Nodes ──
    graph.add_node("retrieve", retrieve_context)
    graph.add_node("architect", run_architect)
    graph.add_node("secops", run_secops)
    graph.add_node("finops", run_finops)
    graph.add_node("gatekeeper", run_gatekeeper)

    # ── Wire Linear Edges ──
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "architect")
    graph.add_edge("architect", "secops")
    graph.add_edge("secops", "finops")
    graph.add_edge("finops", "gatekeeper")

    # ── Conditional Routing (Cyclic Edge) ──
    graph.add_conditional_edges(
        "gatekeeper",
        route_after_gatekeeper,
        {
            "architect": "architect",  # Self-heal loop
            "end": END,               # Success or max iterations
        },
    )

    return graph


def compile_graph():
    """Build and compile the graph, returning the runnable app."""
    graph = build_graph()
    return graph.compile()


# Pre-compiled graph instance for import convenience
app = compile_graph()
