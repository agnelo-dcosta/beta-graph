"""LangGraph agent using Gemini for trail + weather queries."""

import os
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from beta_graph.agent.tools import get_trail_count, get_weather_forecast, search_trails

TOOLS = [search_trails, get_weather_forecast, get_trail_count]

DEFAULT_API_KEY_FILE = "keys/google_api_key"

SYSTEM_PROMPT = """You are a helpful assistant that uses tools to search for hiking trails and get weather forecasts.

When users ask for trails (e.g. moderate hike, waterfall, family friendly), use search_trails to find matching trails.
When they care about weather, use get_weather_forecast with the trail's latitude and longitude to check conditions.
Combine both when they want "pleasant weather" or similar - search trails, then fetch weather for each trail's coordinates, and recommend trails with good conditions (e.g. low rain chance, comfortable temps).
Always give clear, actionable recommendations."""


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


def create_agent(model: str = "gemini-2.5-flash", temperature: float = 0):
    """Create the trail+weather ReAct agent with Gemini."""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "Gemini API key not found. Set GOOGLE_API_KEY env var or add key to keys/google_api_key. "
            "Get one at https://aistudio.google.com/apikey"
        )
    llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key,
    )
    return create_react_agent(llm, tools=TOOLS, prompt=SYSTEM_PROMPT)


def run_cli():
    """CLI entry for beta-graph-agent script."""
    import sys
    from langchain_core.messages import AIMessage, HumanMessage
    args = [a for a in sys.argv[1:] if a != "--verbose"]
    verbose = "--verbose" in sys.argv
    prompt = " ".join(args) if args else "Find me moderate hikes with pleasant weather."
    print(f">> {prompt}\n")
    try:
        agent = create_agent()
        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        messages = result.get("messages", [])
        if verbose:
            print("--- DEBUG: message sequence ---")
            for i, msg in enumerate(messages):
                mt = getattr(msg, "type", type(msg).__name__)
                content = getattr(msg, "content", "") or ""
                preview = (str(content)[:80] + "..." if len(str(content)) > 80 else str(content))
                print(f"  {i}: {mt}: {preview}")
            print("--- end debug ---\n")
        last_ai_content = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
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
                content_str = str(content).strip() if content else ""
                if content_str:
                    last_ai_content = content_str
                    break
        if last_ai_content:
            print(last_ai_content)
        else:
            print("(No text response from agent)")
            if not verbose:
                print("Run with --verbose to see what happened.")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    run_cli()
