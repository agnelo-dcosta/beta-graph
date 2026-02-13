"""Data models for WTA trail data."""

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Trail location coordinates."""

    latitude: float = Field(description="Latitude")
    longitude: float = Field(description="Longitude")


class TripReportCondition(BaseModel):
    """Conditions from a trip report."""

    type_of_hike: str | None = Field(default=None, description="Day hike, Overnight, etc.")
    trail_conditions: str | None = Field(default=None, description="Trail in good condition, etc.")
    road: str | None = Field(default=None, description="Road suitable for all vehicles, etc.")
    bugs: str | None = Field(default=None, description="No bugs, etc.")
    snow: str | None = Field(default=None, description="Snow free, Snow on trail, etc.")


class TripReport(BaseModel):
    """A single trip report for a trail."""

    description: str = Field(default="", description="Report narrative/description")
    date: str | None = Field(default=None, description="Report date")
    condition: TripReportCondition = Field(default_factory=TripReportCondition)
    photos: list[str] = Field(default_factory=list, description="Photo URLs")


class WTATrail(BaseModel):
    """A hiking trail from Washington Trails Association."""

    name: str = Field(description="Trail name")
    slug: str = Field(description="URL slug / identifier")
    url: str = Field(description="Direct link to trail on WTA")
    description: str = Field(default="", description="Trail description")
    location: Location = Field(description="Trail coordinates (required)")
    length_mi: float | None = Field(default=None, description="Length in miles (roundtrip)")
    elevation_gain_ft: float | None = Field(default=None, description="Elevation gain in feet")
    highest_point_ft: float | None = Field(default=None, description="Highest point in feet (snow level, altitude)")
    calculated_difficulty: str | None = Field(default=None, description="WTA calculated difficulty: Easy, Moderate, Hard, etc.")
    permits_required: str | None = Field(default=None, description="Permits needed: wilderness, overnight, Enchantments, etc.")
    rating: float | None = Field(default=None, description="Aggregate rating 0-5")
    region: str | None = Field(default=None, description="Region or area name")
    features: list[str] = Field(default_factory=list, description="Dogs allowed, Lakes, Mountain views, etc.")
    parking_pass_entry_fee: str | None = Field(default=None, description="Parking pass or entry fee")
    getting_there: str | None = Field(default=None, description="Directions / getting there")
    alerts: list[str] = Field(default_factory=list, description="Trail alerts, closures, warnings (e.g. unsanctioned, closed for maintenance)")
    trip_reports: list[TripReport] = Field(default_factory=list, description="Trip reports with conditions")

    def to_searchable_text(self) -> str:
        """Create text for embedding from trail fields."""
        parts = [
            self.name,
            self.description,
            f"Length: {self.length_mi:.1f} mi" if self.length_mi else "",
            f"Elevation gain: {int(self.elevation_gain_ft)} ft" if self.elevation_gain_ft else "",
            f"Highest point: {int(self.highest_point_ft)} ft" if self.highest_point_ft else "",
            f"Difficulty: {self.calculated_difficulty}" if self.calculated_difficulty else "",
            f"Permits: {self.permits_required}" if self.permits_required else "",
            f"Rating: {self.rating}" if self.rating else "",
            f"Region: {self.region}" if self.region else "",
        ]
        if self.features:
            parts.append("Features: " + ", ".join(self.features))
        if self.parking_pass_entry_fee:
            parts.append(f"Parking: {self.parking_pass_entry_fee}")
        if self.getting_there:
            parts.append(f"Getting there: {self.getting_there[:300]}")
        if self.alerts:
            parts.append("Alerts: " + " | ".join(self.alerts[:5]))
        for tr in self.trip_reports[:5]:
            desc = tr.description
            if desc and not any(j in desc.lower()[:80] for j in ("menu", "home", "our work", "explore")):
                parts.append(desc[:200])
            cond = tr.condition
            cond_parts = []
            if cond.type_of_hike:
                cond_parts.append(cond.type_of_hike)
            if cond.trail_conditions:
                cond_parts.append(f"Trail: {cond.trail_conditions}")
            if cond.road:
                cond_parts.append(f"Road: {cond.road}")
            if cond.bugs:
                cond_parts.append(f"Bugs: {cond.bugs}")
            if cond.snow:
                cond_parts.append(f"Snow: {cond.snow}")
            if cond_parts:
                parts.append(" | ".join(cond_parts))
        return "\n".join(p for p in parts if p).strip()
