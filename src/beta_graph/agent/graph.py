"""LangGraph agent using WTA trails, geocoding (Google Maps), and weather via MCP servers."""

import asyncio
import os
from pathlib import Path

from langchain.agents import create_agent as create_agent_graph
from langchain_google_genai import ChatGoogleGenerativeAI
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
- If they say "X Washington" and X is a trail/feature name, treat Washington as the state (understood) – search by X only, don't ask for Olympic NP or Leavenworth.
- search_trails returns trails with: Parking/Pass, Alerts, Getting there, Features, Conditions, distance_miles (when location given).
- Present only the info that is available. Do NOT say things like "I don't have X" or "X is not available" – simply omit missing fields.
- Tell them what pass they need, any alerts, and getting there when present. Present 2–3 options when possible.
- Always include parking pass requirements and alerts when available.
- When trails have distance_miles and it's large (e.g. >15 mi), say so: "These are X miles from [place] – the closest options in our database."

When they care about weather:
- Use geocode if they give a place name. Use get_weather_forecast with the trail's or place's latitude and longitude.

For "hikes near X with good weather": geocode X, search trails, fetch weather for each trail's coordinates, recommend trails with good conditions.

Always give clear, actionable recommendations. If a trail lacks certain fields (getting there, conditions, etc.), omit them – never say they are unavailable or missing."""


def _get_api_key() -> str | None:
    """Get Gemini API key from env or file."""
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
    client = MultiServerMCPClient(MCP_SERVERS)
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
    """CLI entry for hiking agent. Uses MCP servers (wta-trails, weather)."""
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
