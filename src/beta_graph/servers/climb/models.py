"""Data models for Mountain Project climb/route data."""

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Climb/area location coordinates."""

    latitude: float = Field(description="Latitude")
    longitude: float = Field(description="Longitude")


class MPClimb(BaseModel):
    """A climbing route from Mountain Project."""

    name: str = Field(description="Route name")
    route_id: str = Field(description="Mountain Project route ID")
    url: str = Field(description="Direct link to route on Mountain Project")
    difficulty: str | None = Field(default=None, description="YDS/French grade e.g. 5.8+, V2, 5.11c")
    climb_type: str | None = Field(default=None, description="Trad, Sport, Boulder, Ice, Aid, Mixed, Alpine")
    rating: float | None = Field(default=None, description="Star rating from votes")
    votes: int | None = Field(default=None, description="Number of rating votes")
    pitches: int | None = Field(default=None, description="Number of pitches")
    length_ft: float | None = Field(default=None, description="Route length in feet")
    description: str = Field(default="", description="Route description")
    protection: str | None = Field(default=None, description="Protection/beta")
    location: Location | None = Field(default=None, description="GPS coordinates")
    area_name: str | None = Field(default=None, description="Parent area (e.g. Castle Rock)")
    area_path: str | None = Field(default=None, description="Full area hierarchy e.g. Tumwater Canyon > Castle Rock > Upper Castle")
    parent_area: str | None = Field(default=None, description="Parent area name (e.g. Tumwater Canyon)")
    elevation_ft: float | None = Field(default=None, description="Elevation at area in feet")

    def to_searchable_text(self) -> str:
        """Create text for embedding from climb fields."""
        parts = [
            self.name,
            self.description,
            f"Difficulty: {self.difficulty}" if self.difficulty else "",
            f"Type: {self.climb_type}" if self.climb_type else "",
            f"Rating: {self.rating}" if self.rating else "",
            f"Pitches: {self.pitches}" if self.pitches else "",
            f"Area: {self.area_name}" if self.area_name else "",
            f"Area path: {self.area_path}" if self.area_path else "",
            f"Parent: {self.parent_area}" if self.parent_area else "",
            f"Protection: {self.protection}" if self.protection else "",
        ]
        return "\n".join(p for p in parts if p).strip()
