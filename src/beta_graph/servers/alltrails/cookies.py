"""Load AllTrails cookies from file for requests-based scraping.

Paste your Cookie header value (from Postman or browser dev tools) into the cookie file.
Cookies expire; refresh when scraping fails. Set ALLTRAILS_COOKIE_FILE to override path.
"""

import os
from pathlib import Path

DEFAULT_COOKIE_FILE = "keys/alltrails_cookies"


def get_cookie_file_path() -> Path:
    """Return the cookie file path from env or default (relative to cwd)."""
    path = os.getenv("ALLTRAILS_COOKIE_FILE", DEFAULT_COOKIE_FILE)
    return Path(path)


def load_cookies_from_file() -> str | None:
    """Load the Cookie header value from the cookie file.

    The file should contain the raw Cookie header string (e.g. copied from Postman).
    Multiple lines are joined with a space.

    Returns:
        Cookie string for the Cookie header, or None if file is missing/empty.
    """
    path = get_cookie_file_path()
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            return None
        # Join multi-line (e.g. from paste) into single header value
        cookie_str = " ".join(line.strip() for line in content.splitlines() if line.strip())
        # HTTP headers must be ASCII/latin-1; strip Unicode chars (e.g. ellipsis from copy-paste)
        cookie_str = cookie_str.encode("ascii", errors="ignore").decode("ascii")
        return cookie_str if cookie_str else None
    except OSError:
        return None


def create_session_with_cookies():
    """Create a requests Session with standard headers and optional cookies from file.

    Returns:
        Configured Session. Adds Cookie header if cookie file exists.
    """
    from requests import Session

    session = Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    cookies = load_cookies_from_file()
    if cookies:
        session.headers["Cookie"] = cookies
    return session
