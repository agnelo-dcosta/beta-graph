"""MCP server for 5-day weather forecast via OpenWeatherMap."""

import asyncio

from fastmcp import FastMCP
from fastmcp.server import Context

from beta_graph.servers.weather.forecast import fetch_forecast

mcp = FastMCP("weather-forecast")


@mcp.tool()
async def get_weather_forecast(
    latitude: float,
    longitude: float,
    days: int = 5,
    units: str = "imperial",
    ctx: Context | None = None,
) -> dict:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude (-90 to 90).
        longitude: Longitude (-180 to 180).
        days: Number of days of forecast (1-5). OpenWeatherMap free API provides up to 5 days.
        units: 'imperial' (F, mph), 'metric' (C, m/s), or 'standard' (Kelvin). Default imperial.
        ctx: MCP context, injected by server (do not pass).

    Returns:
        Forecast data with daily summaries.
    """
    if ctx:
        await ctx.info(f"Fetching {days}-day weather for ({latitude:.2f}, {longitude:.2f})")
    try:
        result = await asyncio.to_thread(
            fetch_forecast,
            latitude=latitude,
            longitude=longitude,
            days=days,
            units=units,
        )
    except Exception as e:
        if ctx:
            await ctx.error(f"Weather forecast failed: {e}")
        raise
    if ctx:
        await ctx.info("Weather forecast received")
    return result


def main():
    import os
    import sys
    if "--http" in sys.argv:
        port = int(os.getenv("WEATHER_MCP_PORT", "8003"))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
