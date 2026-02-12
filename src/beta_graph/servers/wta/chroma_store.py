"""Chroma vector store for WTA trail embeddings."""

import json
import math

from beta_graph.shared.chroma import get_chroma_client, get_embedding_function
from beta_graph.servers.wta.config import CHROMA_COLLECTION_NAME
from beta_graph.servers.wta.models import WTATrail


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


class WTAVectorStore:
    """Store and query WTA trails in Chroma."""

    def __init__(self) -> None:
        self.client = get_chroma_client()
        self.ef = get_embedding_function()
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=self.ef,
            metadata={"description": "WTA hiking trails"},
        )

    def _trail_to_metadata(self, trail: WTATrail) -> dict:
        """Convert WTATrail to Chroma-safe metadata (location grouped, no flat lat/lon)."""
        out: dict = {}
        # Scalars
        out["name"] = trail.name
        out["slug"] = trail.slug
        out["url"] = trail.url
        out["description"] = trail.description[:500] if trail.description else ""
        out["length_mi"] = trail.length_mi
        out["elevation_gain_ft"] = trail.elevation_gain_ft
        out["highest_point_ft"] = trail.highest_point_ft
        out["calculated_difficulty"] = trail.calculated_difficulty
        out["permits_required"] = trail.permits_required
        out["rating"] = trail.rating
        out["region"] = trail.region
        out["parking_pass_entry_fee"] = trail.parking_pass_entry_fee
        out["getting_there"] = (trail.getting_there[:500] if trail.getting_there else None)
        # Location - only grouped object
        if trail.location:
            out["location"] = json.dumps({"latitude": trail.location.latitude, "longitude": trail.location.longitude})
        # Lists as JSON
        if trail.features:
            out["features"] = json.dumps(trail.features)
        if trail.alerts:
            out["alerts"] = json.dumps(trail.alerts)
        if trail.trip_reports:
            out["trip_reports"] = json.dumps([tr.model_dump() for tr in trail.trip_reports])
        # Drop None values
        return {k: v for k, v in out.items() if v is not None}

    def add_trails(self, trails: list[WTATrail]) -> int:
        """Upsert trails into Chroma. Uses slug as ID."""
        if not trails:
            return 0
        ids = [t.slug for t in trails]
        documents = [t.to_searchable_text() for t in trails]
        metadatas = [self._trail_to_metadata(t) for t in trails]
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(trails)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
        center_lat: float | None = None,
        center_lon: float | None = None,
        radius_miles: float | None = None,
    ) -> list[dict]:
        """Semantic search. Optionally filter by distance from center.

        If center_lat/lon and radius_miles are set, fetches more results and
        filters by haversine distance (Chroma has no native geo filter).
        """
        count = self.collection.count()
        if count == 0:
            return []

        # When filtering by distance, fetch a larger pool so nearby trails are included
        # (semantic search may rank distant trails higher)
        fetch_n = n_results * 20 if (center_lat and center_lon and radius_miles) else n_results
        fetch_n = min(fetch_n, count)

        results = self.collection.query(
            query_texts=[query],
            n_results=fetch_n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        trails: list[dict] = []
        if not results.get("metadatas") or not results["metadatas"][0]:
            return trails

        for i, meta in enumerate(results["metadatas"][0]):
            meta = dict(meta) if isinstance(meta, dict) else {}
            loc = _parse_json_field(meta.get("location"))
            if isinstance(loc, dict):
                lat, lon = loc.get("latitude"), loc.get("longitude")
            else:
                lat, lon = meta.get("latitude"), meta.get("longitude")

            if center_lat is not None and center_lon is not None and radius_miles is not None:
                if lat is None or lon is None:
                    continue
                dist = _haversine_miles(center_lat, center_lon, float(lat), float(lon))
                if dist > radius_miles:
                    continue
                meta["distance_miles"] = round(dist, 2)

            # Expand JSON fields for consumers
            if "features" in meta and isinstance(meta["features"], str):
                meta["features"] = _parse_json_field(meta["features"]) or []
            if "trip_reports" in meta and isinstance(meta["trip_reports"], str):
                meta["trip_reports"] = _parse_json_field(meta["trip_reports"]) or []
            if "alerts" in meta and isinstance(meta["alerts"], str):
                meta["alerts"] = _parse_json_field(meta["alerts"]) or []
            if "location" in meta and isinstance(meta["location"], str):
                meta["location"] = _parse_json_field(meta["location"]) or {}
            # Drop flat lat/lon so output has only grouped location
            meta.pop("latitude", None)
            meta.pop("longitude", None)

            distances = results.get("distances", [[]])[0]
            score = 1 - (distances[i] / 2) if distances and i < len(distances) else None
            trails.append({
                **meta,
                "score": round(score, 3) if score is not None else None,
                "snippet": results["documents"][0][i] if results["documents"] else None,
            })
            if len(trails) >= n_results:
                break

        return trails

    def list_all(self) -> list[dict]:
        """List all stored trails."""
        res = self.collection.get(include=["metadatas"])
        metas = res["metadatas"] or []
        out = []
        for m in metas:
            m = dict(m) if isinstance(m, dict) else {}
            for k in ("features", "alerts", "trip_reports"):
                if k in m and isinstance(m[k], str):
                    m[k] = _parse_json_field(m[k]) or []
            if "location" in m and isinstance(m["location"], str):
                m["location"] = _parse_json_field(m["location"]) or {}
            m.pop("latitude", None)
            m.pop("longitude", None)
            out.append(m)
        return out

    def count(self) -> int:
        return self.collection.count()
