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
search_trails returns trails WITH user review snippets - use them to answer questions about trail conditions, mud, snow, crowds, difficulty, etc.
When they care about weather, use get_weather_forecast with the trail's latitude and longitude to check conditions.
Combine both when they want "pleasant weather" or similar - search trails, then fetch weather for each trail's coordinates, and recommend trails with good conditions (e.g. low rain chance, comfortable temps).
Always give clear, actionable recommendations using the review information when relevant."""


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
    try:
        agent = create_agent()
        messages = []
        if initial_prompt and not chat_mode:
            messages = [HumanMessage(content=initial_prompt)]
            print(f">> {initial_prompt}\n")
            result = agent.invoke({"messages": messages})
            messages = result.get("messages", [])
            last = next((_extract_ai_content(m) for m in reversed(messages) if isinstance(m, AIMessage)), None)
            print(last or "(No response)")
            return
        print("Trail + weather agent (chat mode). Type 'quit' or 'exit' to stop.\n")
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
            result = agent.invoke({"messages": messages})
            messages = result.get("messages", [])
            if verbose:
                print("--- DEBUG ---")
                for i, m in enumerate(messages[-5:]):
                    print(f"  {i}: {getattr(m, 'type', '?')}: {str(getattr(m, 'content', ''))[:60]}...")
                print("---\n")
            last = next((_extract_ai_content(m) for m in reversed(messages) if isinstance(m, AIMessage)), None)
            print(last or "(No response)")
            print()
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    run_cli()
