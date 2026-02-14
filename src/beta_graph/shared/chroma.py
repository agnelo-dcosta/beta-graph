"""Shared Chroma client and embedding utilities."""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from beta_graph.shared.config import (
    CHROMA_PERSIST_DIR,
    CHROMA_SERVER_HOST,
    CHROMA_SERVER_PORT,
)


def get_chroma_client():
    """Get Chroma client - local persist or HTTP (for GCP).

    Uses PersistentClient when CHROMA_SERVER_HOST is unset; otherwise HttpClient.
    Respects CHROMA_PERSIST_DIR, CHROMA_SERVER_HOST, CHROMA_SERVER_PORT env vars.

    Returns:
        Chroma client instance.
    """
    if CHROMA_SERVER_HOST:
        return chromadb.HttpClient(
            host=CHROMA_SERVER_HOST,
            port=CHROMA_SERVER_PORT,
            settings=Settings(anonymized_telemetry=False),
        )
    return chromadb.PersistentClient(
        path=str(CHROMA_PERSIST_DIR),
        settings=Settings(anonymized_telemetry=False),
    )


def get_embedding_function():
    """Return Chroma embedding function using sentence-transformers.

    Uses all-MiniLM-L6-v2 model. Runs locally, no API key required.

    Returns:
        Chroma SentenceTransformerEmbeddingFunction.
    """
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2",
    )
