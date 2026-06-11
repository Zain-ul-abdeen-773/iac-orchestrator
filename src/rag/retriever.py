"""
Context Retriever Node — RAG-based retrieval for Terraform documentation.

Implements the LangGraph node function that embeds the user prompt,
queries ChromaDB for relevant Terraform documentation chunks, and
updates the state with grounding context for the Architect agent.

Supports both Registry API-sourced docs (with subcategory metadata)
and static fallback docs.
"""

import logging
from typing import Any

from src.agents.schemas import AgentState
from src.rag.document_loader import get_collection

logger = logging.getLogger(__name__)


def retrieve_context(state: AgentState) -> dict[str, Any]:
    """
    Context Retriever (Node A) — RAG similarity search.

    Takes the user_prompt and executes a similarity search against the
    local ChromaDB collection loaded with Terraform AWS documentation
    (sourced from the Terraform Registry API or static fallback).

    Updates rag_context with the top 5 most relevant document chunks,
    providing the Architect with grounded, current syntax examples.
    """
    user_prompt = state["user_prompt"]
    n_results = 5  # Fetch more results for better coverage

    try:
        collection = get_collection()

        # Query ChromaDB for the most relevant chunks
        results = collection.query(
            query_texts=[user_prompt],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        # Format retrieved context with source attribution
        context_parts: list[str] = []

        if results and results["documents"] and results["documents"][0]:
            seen_slugs: set[str] = set()

            for i, (doc, metadata, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                slug = metadata.get("slug", "unknown")
                source = metadata.get("source", "unknown")
                subcategory = metadata.get("subcategory", "")
                origin = metadata.get("origin", "unknown")
                similarity = 1 - distance  # Cosine distance → similarity

                # Track unique slugs for diversity
                seen_slugs.add(slug)

                # Build header with source info
                source_label = f"aws_{slug}" if origin == "terraform_registry" else source
                header = f"--- Context #{i + 1}: {source_label}"
                if subcategory:
                    header += f" ({subcategory})"
                header += f" | relevance: {similarity:.2f} ---"

                context_parts.append(f"{header}\n{doc}")

            logger.info(
                f"Retrieved {len(context_parts)} chunks from {len(seen_slugs)} "
                f"unique resources for prompt: '{user_prompt[:80]}...'"
            )

        if context_parts:
            rag_context = "\n\n".join(context_parts)
        else:
            rag_context = (
                "No relevant Terraform documentation found in the knowledge base. "
                "Proceed with your best knowledge of current AWS Terraform provider syntax."
            )

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        rag_context = (
            f"RAG retrieval failed: {e}. "
            "Proceed with your best knowledge of current AWS Terraform provider syntax."
        )

    return {"rag_context": rag_context}
