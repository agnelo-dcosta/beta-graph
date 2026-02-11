"""Data models for AllTrails trail data."""

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Location/place for a trail."""

    postalCode: str | None = Field(default=None, description="Postal/ZIP code")
    city_id: int | None = Field(default=None, description="City ID")
    city: str | None = Field(default=None, description="City name")
    region: str | None = Field(default=None, description="Region/state code (e.g. WA)")
    regionName: str | None = Field(default=None, description="Region/state name (e.g. Washington)")
    country: str | None = Field(default=None, description="Country code (e.g. US)")
    country_name: str | None = Field(default=None, description="Country name (e.g. United States)")
    latitude: float | None = Field(default=None, description="Latitude")
    longitude: float | None = Field(default=None, description="Longitude")
    directions_url: str | None = Field(default=None, description="Google Maps Directions link")


class Tag(BaseModel):
    """Trail tag/category (e.g. Forests, Lakes, Views)."""

    name: str = Field(default="", description="Tag name")
    uid: str = Field(default="", description="Tag unique ID")
    description: str = Field(default="", description="Tag description")


class TrailGeoStats(BaseModel):
    """Trail geometry stats in human-readable units (miles, feet, hours/min)."""

    length_mi: float | None = Field(default=None, description="Length in miles")
    elevation_gain_ft: float | None = Field(default=None, description="Elevation gain in feet")
    elevation_max_ft: float | None = Field(default=None, description="Max elevation in feet")
    duration_formatted: str | None = Field(default=None, description="Duration e.g. 3 h 7 min")


class TrailReview(BaseModel):
    """User review/comment on a trail. No author info; photos kept when present."""

    text: str = Field(default="", description="Review content")
    date: str | None = Field(default=None, description="Review date")
    rating: str | None = Field(default=None, description="Star rating if shown")
    photo_urls: list[str] = Field(default_factory=list, description="Photo URLs when present")


class Trail(BaseModel):
    """A hiking trail from AllTrails."""

    name: str = Field(description="Trail name")
    url: str = Field(description="Direct link to trail on AllTrails")
    slug: str = Field(description="URL slug / identifier")
    trailId: int | None = Field(default=None, description="Numeric trail ID from AllTrails (e.g. 10014686)")
    rating: str | None = Field(default=None, description="Star rating and review count, e.g. 4.7(26725)")
    difficulty: str | None = Field(default=None, description="Easy, Moderate, Hard")
    trailGeoStats: TrailGeoStats | None = Field(default=None, description="Geo stats: length_mi, elevation_gain_ft, elevation_max_ft, duration_formatted")
    tags: list[Tag] = Field(default_factory=list, description="Trail tags (Forests, Lakes, etc.)")
    est_time: str | None = Field(default=None, description="Estimated hike time (e.g. 3 h 7 min)")
    description: str = Field(default="", description="Trail description/summary")
    location: Location | None = Field(default=None, description="Location (city, region, coords, directions_url)")

    # User comments (from trail detail page)
    reviews: list[TrailReview] = Field(default_factory=list, description="User reviews")

    def to_searchable_text(self) -> str:
        """Create text for embedding from trail fields.

        Combines name, difficulty, length, rating, description, location, and review snippets
        for semantic search.

        Returns:
            Concatenated string suitable for embedding.
        """
        loc_str = ""
        if self.location:
            parts_list = [p for p in (self.location.city, self.location.regionName, self.location.country_name) if p]
            loc_str = ", ".join(parts_list) if parts_list else ""
        length_str = ""
        if self.trailGeoStats and self.trailGeoStats.length_mi is not None:
            length_str = f"{self.trailGeoStats.length_mi:.1f} mi"
        elev_str = ""
        if self.trailGeoStats and self.trailGeoStats.elevation_gain_ft is not None:
            elev_str = f"{int(self.trailGeoStats.elevation_gain_ft)} ft"
        tag_names = [t.name for t in self.tags if t.name] if self.tags else []
        parts = [
            self.name,
            f"Difficulty: {self.difficulty}" if self.difficulty else "",
            f"Length: {length_str}" if length_str else "",
            f"Elevation gain: {elev_str}" if elev_str else "",
            f"Rating: {self.rating}" if self.rating else "",
            self.description,
            loc_str,
        ]
        if tag_names:
            parts.append("Tags: " + ", ".join(tag_names))
        if self.reviews:
            review_snippets = [r.text[:200] for r in self.reviews[:5]]
            parts.append("Reviews: " + " | ".join(review_snippets))
        return "\n".join(p for p in parts if p).strip()
