"""Chroma vector store for AllTrails trail embeddings."""

import json

from beta_graph.shared.chroma import get_chroma_client, get_embedding_function
from beta_graph.servers.alltrails.config import CHROMA_COLLECTION_NAME
from beta_graph.servers.alltrails.models import Trail


class TrailVectorStore:
    """Store and query trails in Chroma using sentence-transformers embeddings."""

    def __init__(self) -> None:
        """Initialize Chroma client, embedding function, and collection."""
        self.client = get_chroma_client()
        self.ef = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.ef,
            metadata={"description": "AllTrails hiking trails"},
        )

    def _trail_to_metadata(self, trail: Trail) -> dict:
        """Convert Trail to Chroma-safe metadata (str, int, float, bool only).

        Args:
            trail: Trail instance to convert.

        Returns:
            Dict with serializable values only; reviews and location are JSON-encoded.
        """
        d = trail.model_dump(mode="json")
        if d.get("reviews"):
            d["reviews"] = json.dumps([r if isinstance(r, dict) else r.model_dump() for r in d["reviews"]])
        if d.get("location"):
            d["location"] = json.dumps(d["location"]) if isinstance(d["location"], dict) else d["location"]
        if d.get("tags"):
            d["tags"] = json.dumps([t if isinstance(t, dict) else t.model_dump() for t in d["tags"]])
        if d.get("trailGeoStats"):
            g = d["trailGeoStats"]
            if isinstance(g, dict):
                g = {k: v for k, v in g.items() if v is not None}
            d["trailGeoStats"] = json.dumps(g) if g else None
        return {k: v for k, v in d.items() if v is not None and isinstance(v, (str, int, float, bool))}

    def add_trails(self, trails: list[Trail]) -> int:
        """Upsert trails into Chroma. Uses slug as ID. Replaces existing trails with same slug.

        Args:
            trails: List of Trail instances to add.

        Returns:
            Number of trails added.
        """
        if not trails:
            return 0
        ids = [t.slug for t in trails]
        documents = [t.to_searchable_text() for t in trails]
        metadatas = [self._trail_to_metadata(t) for t in trails]
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(trails)

    def search(self, query: str, n_results: int = 5, where: dict | None = None) -> list[dict]:
        """Semantic search over stored trails.

        Args:
            query: Natural language query.
            n_results: Maximum number of results. Default 5.
            where: Optional Chroma metadata filter.

        Returns:
            List of dicts with trail metadata, score, and snippet.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        trails = []
        if results["metadatas"] and results["metadatas"][0]:
            for i, meta in enumerate(results["metadatas"][0]):
                distances = results.get("distances", [[]])[0]
                score = 1 - (distances[i] / 2) if distances and i < len(distances) else None
                trails.append({
                    **meta,
                    "score": round(score, 3) if score is not None else None,
                    "snippet": results["documents"][0][i] if results["documents"] else None,
                })
        return trails

    def list_all(self) -> list[dict]:
        """List all stored trails.

        Returns:
            List of metadata dicts for each trail.
        """
        res = self.collection.get(include=["metadatas"])
        return res["metadatas"] or []

    def count(self) -> int:
        """Return the number of trails in the collection."""
        return self.collection.count()

    def clear(self) -> None:
        """Delete all trails and recreate an empty collection."""
        self.client.delete_collection(CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.ef,
            metadata={"description": "AllTrails hiking trails"},
        )
