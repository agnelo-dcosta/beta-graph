"""Validate AllTrails URLs before scraping."""

import re
from urllib.parse import urlparse

# Path must look like a region page: /us/state/city or /explore/us/state/city
# Or /poi/us/state/place-name or /explore with bounding box query params (b_br_lat, etc.)
REGION_PATH_PATTERN = re.compile(
    r"^/(?:explore/)?(?:parks/)?(?:poi/)?(?:us|ca|uk|au|[a-z]{2})/[a-z0-9-]+(?:/[a-z0-9-]+)*",
    re.I,
)
EXPLORE_MAP_PATTERN = re.compile(r"^/explore$", re.I)

ALLOWED_SCHEMES = ("https",)


def validate_alltrails_link(url: str) -> dict:
    """Validate an AllTrails region URL before scraping.

    Checks: non-empty, HTTPS, alltrails.com domain, region path pattern, not blocked paths.

    Args:
        url: URL string to validate.

    Returns:
        Dict with keys: valid (bool), reason (str), url (str).
    """
    if not url or not isinstance(url, str):
        return {
            "valid": False,
            "reason": "URL is required and must be a non-empty string",
            "url": url or "",
        }

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception as e:
        return {"valid": False, "reason": f"Invalid URL format: {e}", "url": url}

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return {"valid": False, "reason": "URL must use HTTPS", "url": url}

    netloc = parsed.netloc.lower().replace("www.", "").strip()
    if not netloc or netloc != "alltrails.com":
        return {"valid": False, "reason": "URL must be from alltrails.com", "url": url}

    path = parsed.path.rstrip("/") or "/"
    if any(blocked in path.lower() for blocked in ("/api", "/members", "/register", "/users/auth")):
        return {
            "valid": False,
            "reason": "URL is in a restricted AllTrails area (API, members, etc.)",
            "url": url,
        }

    if REGION_PATH_PATTERN.match(path):
        return {"valid": True, "reason": "Valid AllTrails region page", "url": url}

    # /explore with bounding box params (e.g. ?b_br_lat=...&b_tl_lat=...&a[]=rock-climbing)
    if EXPLORE_MAP_PATTERN.match(path):
        q = parsed.query.lower()
        if "b_br_lat" in q or "b_tl_lat" in q or "b_br_lng" in q or "b_tl_lng" in q:
            return {"valid": True, "reason": "Valid AllTrails explore map page", "url": url}

    return {
        "valid": False,
        "reason": "URL must be from an AllTrails region/explore page (e.g. /us/washington/north-bend or /explore?b_br_lat=...).",
        "url": url,
    }
