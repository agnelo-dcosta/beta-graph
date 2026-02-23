"""LangGraph agent using WTA trails, geocoding (Google Maps), and weather via MCP servers."""

import asyncio
import os
import sys
from pathlib import Path

from langchain.agents import create_agent as create_agent_graph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.callbacks import Callbacks
from langchain_mcp_adapters.client import MultiServerMCPClient

DEFAULT_API_KEY_FILE = "keys/google_api_key"

# MCP server config - connect to running HTTP servers (start with run_servers.py)
MCP_SERVERS = {
    "wta-trails": {
        "transport": "sse",
        "url": os.getenv("WTA_MCP_URL", "http://localhost:8001/sse"),
    },
    "weather": {
        "transport": "sse",
        "url": os.getenv("WEATHER_MCP_URL", "http://localhost:8003/sse"),
    },
}

SYSTEM_PROMPT = """You are a helpful hiking assistant that uses WTA (Washington Trails Association) trails, geocoding, and weather forecasts.

IMPORTANT - Washington-only + ambiguous places:
- WTA trails are in Washington state only. We do NOT support other states.
- For ambiguous place names (e.g. "Leavenworth", "North Bend", "Vancouver") that exist in multiple states, ASK the user: "Do you mean [Place], Washington?" before searching.
- If they confirm Washington (or say yes), pass location as "Place, WA" to search_trails.
- If they say a different state, respond: "We currently only support trails in Washington state."
- For clearly Washington places (Seattle, Olympic NP, Snoqualmie, etc.), assume WA and pass "Place, WA".

When users ask for trails:
- You can search by trail name directly – no location needed. E.g. "Sitka Spruce Washington", "Hall of Mosses" → use search_trails(query="Sitka Spruce" or "Hall of Mosses", location=None). All WTA trails are in Washington, so "Washington" just confirms the state – no need to ask for a more specific place.
- Pass location when they name a specific place (city, park, region): e.g. "hikes near Olympic National Park", "North Bend trails" → use location="Olympic National Park, WA" or "North Bend, WA".
- When they give coordinates (e.g. "hikes near 47.5, -122.3" or "trails at 48°N 121°W"), use search_trails with latitude and longitude directly: latitude=47.5, longitude=-122.3. Do NOT ask for a place name – use the coordinates.
- For "how to get to [coordinates]" or "how do I reach [coordinates]": search with the coordinates. Results are sorted by distance (closest first). Pick the CLOSEST trail that has meaningful data (description, length, or getting_there). Skip trails with no description, no length, and no getting_there – they may be waypoints, not hikable trails. Present that trail as step-by-step directions: 1) Drive – ALWAYS include getting_there (driving directions to trailhead). 2) Park – use parking_pass_entry_fee. 3) Hike – "[Trail name] (X.X mi from the coordinates)" with a SUMMARIZED description. Do NOT paste the full description verbatim. Extract and present only key points: wayfinding (e.g. head for iron bridge, parking area), route (distances, where it dead-ends), landmarks (Castle Rock, cliff face), hazards (river current, bridge collects water), and climbing/bouldering if mentioned (e.g. bolts, climbing routes, boulder fields). Skip flowery prose, rhetorical questions, and marketing fluff. Then add length, elevation gain, features, conditions, trip reports. If all trails lack data, say so. Lead with this how-to-reach format, then optionally list other nearby trails.
- If they give only one coordinate (e.g. "47.5" or "latitude -122.3"), ask: "I need both latitude and longitude to find trails. Could you provide the other coordinate (e.g. 47.5, -122.3)?"
- If they say "X Washington" and X is a trail/feature name, treat Washington as the state (understood) – search by X only, don't ask for Olympic NP or Leavenworth.
- search_trails returns trails with: description (narrative for wayfinding – landmarks, route cues), Length, Elevation gain, Parking/Pass, Alerts, Getting there, Features, Conditions, trip_reports, distance_miles (when location given). Always include length_mi and elevation_gain_ft when available. When presenting trail descriptions, SUMMARIZE to key points only – wayfinding, route, landmarks, hazards, and climbing/bouldering if mentioned. Do NOT paste the full description verbatim.
- Present only the info that is available. Do NOT say things like "I don't have X" or "X is not available" – simply omit missing fields.
- Tell them what pass they need, any alerts, and getting there when present. Present 2–3 options when possible.
- Always include parking pass requirements and alerts when available.
- When trip_reports are present (up to 5 recent reports within 6 weeks), SUMMARIZE the description text for the user. Synthesize into 1–2 short paragraphs. Focus on key details for hike prep: trail conditions, obstacles (trees down, mud, washouts), water levels, fall colors, road access, bugs, snow. Prioritize the most recent reports. Do not quote reports verbatim – summarize the experiences. If the summary would be nonsensical, empty, or unhelpful, omit it entirely – do not include it.

Weather – always include when recommending trails:
- When presenting trail recommendations, call get_weather_forecast and include the forecast. Use the trail's location.latitude and location.longitude (or geocode the place name if no trails returned).
- For "hikes near X": search trails, then get_weather_forecast for that area (geocode X or use first trail's coordinates), and include weather in your response.
- For "hikes near X with good weather": geocode X, search trails, fetch weather, recommend trails that match good conditions.

Always give clear, actionable recommendations. If a trail lacks certain fields (getting there, conditions, etc.), omit them – never say they are unavailable or missing."""


def _format_server_log(params, context) -> str:
    """Format MCP log notification for display."""
    level = getattr(params, "level", "info")
    data = getattr(params, "data", "")
    if isinstance(data, dict) and "msg" in data:
        msg = str(data["msg"])
    else:
        msg = str(data)
    server = getattr(context, "server_name", "server")
    tool = getattr(context, "tool_name", "")
    prefix = f"[{server}"
    if tool:
        prefix += f"/{tool}"
    prefix += f"]"
    # Emphasize warnings and errors
    if level in ("warning", "error", "critical"):
        return f"  {prefix} [{level.upper()}] {msg}"
    return f"  {prefix} {msg}"


async def _on_logging_message(params, context):
    """Print server log messages so the client can see them."""
    line = _format_server_log(params, context)
    print(line, file=sys.stderr, flush=True)


def _get_api_key() -> str | None:
    """Get Gemini API key from env or file. Skips comment lines (starting with #)."""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip()
    path = Path(os.getenv("GOOGLE_API_KEY_FILE", DEFAULT_API_KEY_FILE))
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        except OSError:
            return None
    return None


async def _create_agent_with_mcp_tools():
    """Load tools from MCP servers and create agent."""
    callbacks = Callbacks(on_logging_message=_on_logging_message)
    client = MultiServerMCPClient(MCP_SERVERS, callbacks=callbacks)
    tools = await client.get_tools()

    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "Gemini API key not found. Set GOOGLE_API_KEY or add to keys/google_api_key. "
            "Get one at https://aistudio.google.com/apikey"
        )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=api_key,
    )
    return create_agent_graph(llm, tools=tools, system_prompt=SYSTEM_PROMPT)


def _extract_ai_content(msg) -> str | None:
    """Extract text content from an AIMessage."""
    content = getattr(msg, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for p in content:
            if hasattr(p, "text"):
                parts.append(str(p.text))
            elif isinstance(p, dict) and "text" in p:
                parts.append(str(p["text"]))
            elif isinstance(p, str):
                parts.append(p)
        content = " ".join(parts)
    return str(content).strip() if content else None


def run_cli():
    """CLI entry for beta-graph-agent script. No args = chat loop; with args = single shot."""
    import sys
    from langchain_core.messages import AIMessage, HumanMessage
    args = [a for a in sys.argv[1:] if a not in ("--verbose", "--chat")]
    verbose = "--verbose" in sys.argv
    chat_mode = "--chat" in sys.argv or not args
    initial_prompt = " ".join(args) if args else None

    async def _run():
        agent = await _create_agent_with_mcp_tools()
        messages = []

        if initial_prompt and not chat_mode:
            messages = [HumanMessage(content=initial_prompt)]
            print(f">> {initial_prompt}\n")
            result = await agent.ainvoke({"messages": messages})
            messages = result.get("messages", [])
            last = next(
                (_extract_ai_content(m) for m in reversed(messages) if isinstance(m, AIMessage)),
                None,
            )
            print(last or "(No response)")
            return

        print("WTA + Weather agent (MCP). Type 'quit' or 'exit' to stop.\n")

        while True:
            try:
                prompt = input(">> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not prompt:
                continue
            if prompt.lower() in ("quit", "exit", "q"):
                break
            messages.append(HumanMessage(content=prompt))
            result = await agent.ainvoke({"messages": messages})
            messages = result.get("messages", [])
            if verbose:
                print("--- DEBUG ---")
                for i, m in enumerate(messages[-5:]):
                    print(
                        f"  {i}: {getattr(m, 'type', '?')}: {str(getattr(m, 'content', ''))[:60]}..."
                    )
                print("---\n")
            last = next(
                (_extract_ai_content(m) for m in reversed(messages) if isinstance(m, AIMessage)),
                None,
            )
            print(last or "(No response)")
            print()

    try:
        asyncio.run(_run())
    except Exception as e:
        err = str(e)
        print(f"Error: {e}")
        if "ConnectError" in type(e).__name__ or "connection" in err.lower():
            print("\nMake sure all MCP servers are running first:")
            print("  python3 scripts/run_servers.py")
            print("  (or run each server in a separate terminal)")
        raise


if __name__ == "__main__":
    run_cli()
