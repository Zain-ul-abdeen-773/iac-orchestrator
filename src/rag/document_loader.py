"""
Document Loader — Loads Terraform documentation into ChromaDB from multiple sources.

Primary source: Terraform Registry API (real, versioned docs)
Fallback source: Static mock documentation (for offline/air-gapped environments)

Handles text chunking, embedding generation, and ChromaDB collection management.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from src.rag.registry_client import (
    DEFAULT_RESOURCE_SLUGS,
    ProviderDoc,
    TerraformRegistryClient,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────

CHROMA_DB_DIR = Path(__file__).resolve().parent.parent.parent / "chroma_db"
COLLECTION_NAME = "terraform_aws_docs"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / ".cache"

# Metadata file to track what's loaded
METADATA_FILE = CACHE_DIR / "registry_metadata.json"


# ─────────────────────────────────────────────────────────────────────
#  ChromaDB Client
# ─────────────────────────────────────────────────────────────────────


def get_chroma_client(persist_dir: str | None = None) -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client."""
    db_path = persist_dir or str(CHROMA_DB_DIR)
    return chromadb.PersistentClient(
        path=db_path,
        settings=Settings(anonymized_telemetry=False),
    )


# ─────────────────────────────────────────────────────────────────────
#  Text Chunking
# ─────────────────────────────────────────────────────────────────────


def chunk_document(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[str]:
    """
    Split a document into overlapping chunks for embedding.

    Strategy:
    1. Split on markdown headers (## and ###) as natural boundaries
    2. Keep HCL code blocks intact when possible
    3. Fall back to character-level splitting with overlap for long sections
    """
    # Split on markdown headers (## or ###)
    sections = re.split(r"\n(?=#{2,3} )", text)
    chunks: list[str] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            # Try to split on code block boundaries first
            code_blocks = re.split(r"(```[\s\S]*?```)", section)
            current_chunk = ""

            for block in code_blocks:
                if len(current_chunk) + len(block) <= chunk_size:
                    current_chunk += block
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())

                    # If the block itself exceeds chunk_size, split it with overlap
                    if len(block) > chunk_size:
                        start = 0
                        while start < len(block):
                            end = start + chunk_size
                            chunks.append(block[start:end].strip())
                            start += chunk_size - overlap
                    else:
                        current_chunk = block

            if current_chunk.strip():
                chunks.append(current_chunk.strip())

    # Filter trivially small chunks
    return [c for c in chunks if len(c) > 80]


def generate_chunk_id(source: str, chunk_index: int) -> str:
    """Generate a deterministic ID for a chunk."""
    content = f"{source}:{chunk_index}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────
#  Registry-Based Loading (Primary)
# ─────────────────────────────────────────────────────────────────────


def _cache_registry_docs(docs: list[ProviderDoc], version: str) -> None:
    """Cache fetched registry docs to disk for faster subsequent loads."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Save each doc
    for doc in docs:
        cache_file = CACHE_DIR / f"{doc.slug}.md"
        cache_file.write_text(doc.content, encoding="utf-8")

    # Save metadata
    metadata = {
        "version": version,
        "doc_count": len(docs),
        "slugs": [d.slug for d in docs],
        "subcategories": list(set(d.subcategory for d in docs)),
    }
    METADATA_FILE.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    logger.info(f"Cached {len(docs)} docs to {CACHE_DIR}")


def _load_cached_docs() -> list[ProviderDoc] | None:
    """Load previously cached registry docs if available."""
    if not METADATA_FILE.exists():
        return None

    try:
        metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        docs: list[ProviderDoc] = []

        for slug in metadata.get("slugs", []):
            cache_file = CACHE_DIR / f"{slug}.md"
            if cache_file.exists():
                content = cache_file.read_text(encoding="utf-8")
                docs.append(ProviderDoc(
                    doc_id="cached",
                    title=slug,
                    slug=slug,
                    category="resources",
                    subcategory="",
                    path="",
                    content=content,
                ))

        if docs:
            logger.info(
                f"Loaded {len(docs)} cached docs "
                f"(provider v{metadata.get('version', 'unknown')})"
            )
            return docs

    except Exception as e:
        logger.warning(f"Failed to load cached docs: {e}")

    return None


def fetch_registry_docs(
    slugs: list[str] | None = None,
    force_refresh: bool = False,
    provider: str = "aws",
    namespace: str = "hashicorp",
) -> list[ProviderDoc]:
    """
    Fetch Terraform documentation from the Registry API.

    Uses disk cache to avoid repeated API calls. Pass force_refresh=True
    to bypass the cache and fetch fresh docs.

    Args:
        slugs: Resource slugs to fetch. Defaults to DEFAULT_RESOURCE_SLUGS.
        force_refresh: Force re-fetching from the API.
        provider: Provider name (default: 'aws').
        namespace: Provider namespace (default: 'hashicorp').

    Returns:
        List of ProviderDoc objects with full markdown content.
    """
    if slugs is None:
        slugs = DEFAULT_RESOURCE_SLUGS

    # Try cache first
    if not force_refresh:
        cached = _load_cached_docs()
        if cached:
            return cached

    # Fetch from Registry API
    logger.info(f"Fetching docs from Terraform Registry for {namespace}/{provider}...")
    client = TerraformRegistryClient(
        namespace=namespace,
        provider=provider,
        request_delay=0.25,
    )

    result = client.fetch_docs_by_slugs(slugs=slugs)

    if result.errors:
        for err in result.errors:
            logger.warning(f"Registry fetch warning: {err}")

    if result.docs:
        logger.info(
            f"Successfully fetched {len(result.docs)}/{len(slugs)} docs "
            f"(provider v{result.provider_version})"
        )
        # Cache for future use
        _cache_registry_docs(result.docs, result.provider_version)
        return result.docs

    logger.warning("No docs fetched from registry — will use static fallback")
    return []


# ─────────────────────────────────────────────────────────────────────
#  Static Fallback Loading
# ─────────────────────────────────────────────────────────────────────


def _load_static_docs() -> dict[str, str]:
    """Load static mock Terraform documentation as fallback."""
    try:
        from data.terraform_aws_docs import ALL_DOCUMENTS
        return ALL_DOCUMENTS
    except ImportError:
        logger.warning("Static docs not available")
        return {}


# ─────────────────────────────────────────────────────────────────────
#  ChromaDB Loading (Unified)
# ─────────────────────────────────────────────────────────────────────


def load_documents_to_chromadb(
    force_reload: bool = False,
    use_registry: bool = True,
    registry_slugs: list[str] | None = None,
) -> chromadb.Collection:
    """
    Load Terraform documentation into ChromaDB.

    Data source priority:
    1. Terraform Registry API (real docs — if use_registry=True)
    2. Disk cache (previously fetched registry docs)
    3. Static mock documentation (fallback for offline environments)

    Args:
        force_reload: Delete existing collection and reload from scratch.
        use_registry: Attempt to fetch from the Terraform Registry API.
        registry_slugs: Specific resource slugs to fetch from registry.

    Returns:
        ChromaDB collection containing all document chunks.
    """
    client = get_chroma_client()

    # Check if collection already exists and is populated
    try:
        collection = client.get_collection(COLLECTION_NAME)
        if collection.count() > 0 and not force_reload:
            logger.info(f"Using existing ChromaDB collection ({collection.count()} docs)")
            return collection
        # Force reload — delete and recreate
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # Collection doesn't exist yet

    # Create collection with cosine similarity
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Gather documents
    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metadata: list[dict[str, Any]] = []

    # ── Try Registry API first ──
    if use_registry:
        try:
            registry_docs = fetch_registry_docs(
                slugs=registry_slugs,
                force_refresh=force_reload,
            )

            for doc in registry_docs:
                chunks = chunk_document(doc.content)
                for i, chunk in enumerate(chunks):
                    chunk_id = generate_chunk_id(f"registry:{doc.slug}", i)
                    all_chunks.append(chunk)
                    all_ids.append(chunk_id)
                    all_metadata.append({
                        "source": f"registry:{doc.slug}",
                        "subcategory": doc.subcategory,
                        "slug": doc.slug,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "origin": "terraform_registry",
                    })

            if registry_docs:
                logger.info(
                    f"Loaded {len(registry_docs)} registry docs → "
                    f"{len(all_chunks)} chunks"
                )

        except Exception as e:
            logger.warning(f"Registry loading failed: {e} — falling back to static docs")

    # ── Fall back to static docs if registry didn't provide enough ──
    if len(all_chunks) == 0:
        logger.info("Using static fallback documentation")
        static_docs = _load_static_docs()

        for doc_name, doc_text in static_docs.items():
            chunks = chunk_document(doc_text)
            for i, chunk in enumerate(chunks):
                chunk_id = generate_chunk_id(f"static:{doc_name}", i)
                all_chunks.append(chunk)
                all_ids.append(chunk_id)
                all_metadata.append({
                    "source": f"static:{doc_name}",
                    "subcategory": doc_name,
                    "slug": doc_name,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "origin": "static_mock",
                })

    # ── Batch insert into ChromaDB ──
    if all_chunks:
        # ChromaDB has a batch size limit — insert in batches of 500
        batch_size = 500
        for i in range(0, len(all_chunks), batch_size):
            end = min(i + batch_size, len(all_chunks))
            collection.add(
                documents=all_chunks[i:end],
                ids=all_ids[i:end],
                metadatas=all_metadata[i:end],
            )

        logger.info(
            f"ChromaDB collection loaded: {collection.count()} chunks total"
        )
    else:
        logger.warning("No documents loaded into ChromaDB!")

    return collection


def get_collection() -> chromadb.Collection:
    """Get the existing Terraform docs collection, loading if necessary."""
    return load_documents_to_chromadb()
