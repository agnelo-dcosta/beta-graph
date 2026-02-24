"""Chroma vector store for Mountain Project climb embeddings."""

import json
import math

from beta_graph.shared.chroma import get_chroma_client, get_embedding_function
from beta_graph.servers.climb.config import CHROMA_COLLECTION_NAME
from beta_graph.servers.climb.models import MPClimb


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in miles between two points."""
    R = 3959
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _parse_json_field(val: str | dict | list | None) -> dict | list | None:
    """Parse JSON string to dict/list for metadata."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


class ClimbVectorStore:
    """Store and query Mountain Project climbs in Chroma."""

    def __init__(self) -> None:
        self.client = get_chroma_client()
        self.ef = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.ef,
            metadata={"description": "Mountain Project climbing routes"},
        )

    def _climb_to_metadata(self, climb: MPClimb) -> dict:
        """Convert MPClimb to Chroma-safe metadata."""
        out: dict = {}
        out["name"] = climb.name
        out["route_id"] = climb.route_id
        out["url"] = climb.url
        out["description"] = climb.description[:500] if climb.description else ""
        out["difficulty"] = climb.difficulty
        out["climb_type"] = climb.climb_type
        out["rating"] = climb.rating
        out["votes"] = climb.votes
        out["pitches"] = climb.pitches
        out["length_ft"] = climb.length_ft
        out["protection"] = climb.protection
        out["area_name"] = climb.area_name
        out["area_path"] = climb.area_path
        out["parent_area"] = climb.parent_area
        out["elevation_ft"] = climb.elevation_ft
        if climb.location:
            out["location"] = json.dumps({
                "latitude": climb.location.latitude,
                "longitude": climb.location.longitude,
            })
        return {k: v for k, v in out.items() if v is not None}

    def add_climbs(self, climbs: list[MPClimb]) -> int:
        """Upsert climbs into Chroma. Uses route_id as ID."""
        if not climbs:
            return 0
        ids = [c.route_id for c in climbs]
        documents = [c.to_searchable_text() for c in climbs]
        metadatas = [self._climb_to_metadata(c) for c in climbs]
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(climbs)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
        center_lat: float | None = None,
        center_lon: float | None = None,
        radius_miles: float | None = None,
    ) -> list[dict]:
        """Semantic search. Optionally filter by distance from center."""
        count = self.collection.count()
        if count == 0:
            return []

        fetch_n = n_results * 50 if (center_lat and center_lon and radius_miles) else n_results
        fetch_n = min(fetch_n, count)

        results = self.collection.query(
            query_texts=[query],
            n_results=fetch_n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        climbs: list[dict] = []
        if not results.get("metadatas") or not results["metadatas"][0]:
            return climbs

        distances_scores = results.get("distances", [[]])[0]
        for i, meta in enumerate(results["metadatas"][0]):
            meta = dict(meta) if isinstance(meta, dict) else {}
            loc = _parse_json_field(meta.get("location"))
            lat = lon = None
            if isinstance(loc, dict):
                lat, lon = loc.get("latitude"), loc.get("longitude")

            if center_lat is not None and center_lon is not None and radius_miles is not None:
                if lat is None or lon is None:
                    continue
                dist = _haversine_miles(center_lat, center_lon, float(lat), float(lon))
                if dist > radius_miles:
                    continue
                meta["distance_miles"] = round(dist, 2)
            else:
                meta["distance_miles"] = None

            if "location" in meta and isinstance(meta["location"], str):
                meta["location"] = _parse_json_field(meta["location"]) or {}

            score = 1 - (distances_scores[i] / 2) if distances_scores and i < len(distances_scores) else None
            climbs.append({
                **meta,
                "score": round(score, 3) if score is not None else None,
                "snippet": results["documents"][0][i] if results["documents"] else None,
            })

        if center_lat is not None and center_lon is not None and radius_miles is not None:
            climbs.sort(key=lambda t: (t.get("distance_miles") is None, t.get("distance_miles") or float("inf")))

        return climbs[:n_results]

    def list_all(self) -> list[dict]:
        """List all stored climbs."""
        res = self.collection.get(include=["metadatas"])
        metas = res["metadatas"] or []
        out = []
        for m in metas:
            m = dict(m) if isinstance(m, dict) else {}
            if "location" in m and isinstance(m["location"], str):
                m["location"] = _parse_json_field(m["location"]) or {}
            out.append(m)
        return out

    def count(self) -> int:
        return self.collection.count()
