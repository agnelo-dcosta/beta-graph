"""MCP server for 5-day weather forecast via OpenWeatherMap."""

from fastmcp import FastMCP

from beta_graph.servers.weather.forecast import fetch_forecast

mcp = FastMCP("weather-forecast")


@mcp.tool()
def get_weather_forecast(latitude: float, longitude: float, days: int = 5, units: str = "imperial") -> dict:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of days of forecast (1-5). OpenWeatherMap free API provides up to 5 days.
        units: 'imperial' (F, mph), 'metric' (C, m/s), or 'standard' (Kelvin). Default imperial.

    Returns:
        Forecast data with daily summaries.
    """
    return fetch_forecast(latitude=latitude, longitude=longitude, days=days, units=units)


def main():
    import sys
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="0.0.0.0", port=8001)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
