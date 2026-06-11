"""
Document Loader — Loads and chunks Terraform AWS documentation into ChromaDB.

Handles text chunking, embedding generation via sentence-transformers,
and ChromaDB collection management for the RAG pipeline.
"""

import hashlib
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings


# Default ChromaDB storage path
CHROMA_DB_DIR = Path(__file__).resolve().parent.parent.parent / "chroma_db"
COLLECTION_NAME = "terraform_aws_docs"


def get_chroma_client(persist_dir: str | None = None) -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client."""
    db_path = persist_dir or str(CHROMA_DB_DIR)
    return chromadb.PersistentClient(
        path=db_path,
        settings=Settings(anonymized_telemetry=False),
    )


def chunk_document(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """
    Split a document into overlapping chunks for embedding.

    Uses section headers (## ) as natural split points, then falls back
    to character-level chunking for sections that exceed chunk_size.
    """
    # Split on markdown headers
    sections = re.split(r"\n(?=### )", text)
    chunks: list[str] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # Sub-chunk long sections with overlap
            start = 0
            while start < len(section):
                end = start + chunk_size
                chunk = section[start:end]
                chunks.append(chunk.strip())
                start += chunk_size - overlap

    return [c for c in chunks if len(c) > 50]  # Filter trivially small chunks


def generate_chunk_id(doc_name: str, chunk_index: int) -> str:
    """Generate a deterministic ID for a chunk."""
    content = f"{doc_name}:{chunk_index}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def load_documents_to_chromadb(force_reload: bool = False) -> chromadb.Collection:
    """
    Load all Terraform AWS documentation into ChromaDB.

    Uses ChromaDB's built-in embedding function (default: all-MiniLM-L6-v2)
    for the MVP. In production, switch to sentence-transformers with a
    larger model for better retrieval quality.

    Args:
        force_reload: If True, deletes the existing collection and reloads.

    Returns:
        The ChromaDB collection containing all document chunks.
    """
    from data.terraform_aws_docs import ALL_DOCUMENTS

    client = get_chroma_client()

    # Check if collection already exists and is populated
    try:
        collection = client.get_collection(COLLECTION_NAME)
        if collection.count() > 0 and not force_reload:
            return collection
        # Force reload — delete and recreate
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # Collection doesn't exist yet

    # Create collection with default embedding function
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Chunk and load all documents
    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metadata: list[dict] = []

    for doc_name, doc_text in ALL_DOCUMENTS.items():
        chunks = chunk_document(doc_text)
        for i, chunk in enumerate(chunks):
            chunk_id = generate_chunk_id(doc_name, i)
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadata.append({
                "source": doc_name,
                "chunk_index": i,
                "total_chunks": len(chunks),
            })

    # Batch insert into ChromaDB
    if all_chunks:
        collection.add(
            documents=all_chunks,
            ids=all_ids,
            metadatas=all_metadata,
        )

    return collection


def get_collection() -> chromadb.Collection:
    """Get the existing Terraform docs collection, loading if necessary."""
    return load_documents_to_chromadb()
