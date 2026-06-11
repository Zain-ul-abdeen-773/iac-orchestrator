"""
Context Retriever Node — RAG-based retrieval for Terraform documentation.

Implements the LangGraph node function that embeds the user prompt,
queries ChromaDB for relevant Terraform documentation chunks, and
updates the state with grounding context for the Architect agent.
"""

from typing import Any

from src.agents.schemas import AgentState
from src.rag.document_loader import get_collection


def retrieve_context(state: AgentState) -> dict[str, Any]:
    """
    Context Retriever (Node A) — RAG similarity search.

    Takes the user_prompt and executes a similarity search against the
    local ChromaDB collection loaded with Terraform AWS documentation.

    Updates rag_context with the top 3 most relevant document chunks,
    providing the Architect with grounded, current syntax examples.
    """
    user_prompt = state["user_prompt"]

    try:
        collection = get_collection()

        # Query ChromaDB for top 3 most relevant chunks
        results = collection.query(
            query_texts=[user_prompt],
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )

        # Format retrieved context
        context_parts: list[str] = []

        if results and results["documents"] and results["documents"][0]:
            for i, (doc, metadata, distance) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ):
                source = metadata.get("source", "unknown")
                similarity = 1 - distance  # ChromaDB cosine distance → similarity
                context_parts.append(
                    f"--- Retrieved Context #{i + 1} "
                    f"(source: {source}, relevance: {similarity:.2f}) ---\n"
                    f"{doc}"
                )

        if context_parts:
            rag_context = "\n\n".join(context_parts)
        else:
            rag_context = (
                "No relevant Terraform documentation found in the knowledge base. "
                "Proceed with your best knowledge of current AWS Terraform provider syntax."
            )

    except Exception as e:
        rag_context = (
            f"RAG retrieval failed: {e}. "
            "Proceed with your best knowledge of current AWS Terraform provider syntax."
        )

    return {"rag_context": rag_context}
