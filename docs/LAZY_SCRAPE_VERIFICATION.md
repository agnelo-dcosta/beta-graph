# Lazy Scrape Verification

## How It Works

When `search_wta_trails` returns **0 results** for a **location-based** query:
1. Geocode location → `center_lat/lon`
2. Search Chroma with distance filter → 0 trails (e.g. Olympic not loaded)
3. **Lazy scrape triggers**: start background thread, return "retry in 2–3 minutes"

## Bug: Daemon Thread + Single-Shot Exit

**Root cause**: The scrape runs in a `daemon=True` thread. When the main process exits (e.g. one-shot `run_agent.py "Olympic hikes"`), daemon threads are terminated immediately. The scrape never completes.

| Mode | Process exits after response? | Scrape completes? |
|------|------------------------------|-------------------|
| **Single-shot** (`run_agent.py "Olympic hikes"`) | Yes, immediately | **No** – daemon killed |
| **Chat mode** (`run_agent.py` then type) | No, waits for input | Yes |
| **MCP server** (wta-trails) | No, long-running | Yes |

## Fix Applied

Changed `daemon=True` → `daemon=False` in `handlers.py` and `wta/server.py`. The process now waits for the scrape thread to finish before exiting. In single-shot mode, after printing the retry message, the process will stay alive 2–3 minutes while trails load (user sees logs).

## Manual Verification

```bash
# 1. Ensure Olympic not loaded
python3 -c "
import sys; sys.path.insert(0,'src')
from beta_graph.shared.chroma import get_chroma_client
from beta_graph.servers.wta.config import CHROMA_COLLECTION_NAME
c = get_chroma_client().get_collection(CHROMA_COLLECTION_NAME)
print('Total:', c.count())
"

# 2. Run agent single-shot (will take ~2-3 min if scrape triggers)
python3 scripts/run_agent.py "Olympic National Park hikes"

# 3. Verify trails loaded (re-run step 1 – count should increase)
```
