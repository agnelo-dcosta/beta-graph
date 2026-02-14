"""Weather forecast logic - shared by MCP server and agent tools."""

from datetime import datetime

import requests

from beta_graph.servers.weather.config import get_api_key

BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"


def fetch_forecast(
    latitude: float, longitude: float, days: int = 5, units: str = "imperial"
) -> dict:
    """Fetch weather forecast from OpenWeatherMap. Returns dict with location, forecast, units."""
    api_key = get_api_key()
    if not api_key:
        return {"error": "OpenWeatherMap API key not found. Add to keys/openweathermap_api_key or set OPENWEATHERMAP_API_KEY env var."}

    try:
        resp = requests.get(
            BASE_URL,
            params={"lat": latitude, "lon": longitude, "appid": api_key, "units": units},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"error": str(e)}

    daily: dict = {}
    for item in data.get("list", []):
        dt = item.get("dt")
        if not dt:
            continue
        day = datetime.utcfromtimestamp(dt).strftime("%Y-%m-%d")
        if day not in daily:
            daily[day] = {"date": day, "temps": [], "conditions": [], "pop": []}
        daily[day]["temps"].append(item.get("main", {}).get("temp"))
        if item.get("weather"):
            daily[day]["conditions"].append(item["weather"][0].get("description", ""))
        daily[day]["pop"].append(item.get("pop", 0))

    n = max(1, min(days, 5))
    days_sorted = sorted(daily.keys())[:n]
    forecast = []
    for day in days_sorted:
        d = daily[day]
        temps = [t for t in d["temps"] if t is not None]
        conditions = list(set(c for c in d["conditions"] if c))
        pop = d["pop"]
        forecast.append({
            "date": day,
            "temp_min": round(min(temps), 1) if temps else None,
            "temp_max": round(max(temps), 1) if temps else None,
            "temp_avg": round(sum(temps) / len(temps), 1) if temps else None,
            "conditions": conditions[:3],
            "pop_max": round(max(pop) * 100) if pop else None,
        })

    return {"location": data.get("city", {}).get("name"), "forecast": forecast, "units": units}
