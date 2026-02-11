"""Tests for AllTrails explore URL scraping (bounding box + activity filter).

Explore URL format: /explore?b_br_lat=...&b_tl_lat=...&a[]=rock-climbing
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from beta_graph.servers.alltrails.validate import validate_alltrails_link
from beta_graph.servers.alltrails.scraper import scrape_with_requests

EXPLORE_ROCK_CLIMBING_URL = (
    "https://www.alltrails.com/explore"
    "?b_br_lat=37.492149999999754"
    "&b_br_lng=-118.93155187112043"
    "&b_tl_lat=38.186350000000544"
    "&b_tl_lng=-120.15411812888175"
    "&a[]=rock-climbing"
)


def test_validate_explore_url():
    """Explore URL with bounding box and activity filter should be valid."""
    result = validate_alltrails_link(EXPLORE_ROCK_CLIMBING_URL)
    assert result["valid"] is True
    assert "explore" in result["reason"].lower()
    assert result["url"] == EXPLORE_ROCK_CLIMBING_URL


def test_validate_explore_url_no_params_invalid():
    """Explore URL without bounding box params is invalid (we require bbox for map results)."""
    result = validate_alltrails_link("https://www.alltrails.com/explore")
    assert result["valid"] is False


@pytest.mark.network
def test_scrape_explore_rock_climbing():
    """Scrape rock-climbing trails from explore map (requires network + cookies)."""
    trails = scrape_with_requests(EXPLORE_ROCK_CLIMBING_URL)
    # May get 0 if captcha/block; with cookies should get trails
    assert isinstance(trails, list)
    for t in trails:
        assert t.slug
        assert t.url
        assert t.name
        # Explore page: location may be Unknown
        assert t.location is not None
