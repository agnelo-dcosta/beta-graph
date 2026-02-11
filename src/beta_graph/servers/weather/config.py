"""Weather server configuration."""

import os
from pathlib import Path

DEFAULT_API_KEY_FILE = "keys/openweathermap_api_key"


def get_api_key() -> str | None:
    """Load OpenWeatherMap API key from file or env.

    Tries OPENWEATHERMAP_API_KEY env var first, then keys/openweathermap_api_key file.
    """
    key = os.getenv("OPENWEATHERMAP_API_KEY")
    if key:
        return key.strip()
    path = Path(os.getenv("OPENWEATHERMAP_API_KEY_FILE", DEFAULT_API_KEY_FILE))
    if path.is_file():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        except OSError:
            return None
    return None
