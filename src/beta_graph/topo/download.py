"""Download map/satellite images for GPS coordinates.

Uses free tile providers:
- USGS Imagery: US only, orthoimagery (aerial/satellite, no overlay). Default.
- USGS Topo: US only, topographic map overlay.
- OpenTopoMap: Global, contours, terrain, OSM data.

Output saved to topo-images/ as {lat}_{lon}_z{zoom}.png
"""

import math
from pathlib import Path

import requests
from PIL import Image
from io import BytesIO

# OpenTopoMap: free, global, no key. Max zoom 17.
OPEN_TOPO_TEMPLATE = "https://{sub}.tile.opentopomap.org/{z}/{x}/{y}.png"
OPEN_TOPO_SUBS = ("a", "b", "c")  # Round-robin for polite usage

# USGS: same Export API, different MapServer.
USGS_TOPO_URL = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/export"
USGS_IMAGERY_URL = "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export"

# Default output dir relative to project root
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2].parents[0] / "topo-images"
TILE_SIZE = 256


def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert WGS84 lat/lon to XYZ tile indices (slippy map convention)."""
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int(
        (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )
    return x, y


def _fetch_tile(url: str) -> Image.Image:
    """Download a single tile, return PIL Image."""
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return Image.open(BytesIO(r.content)).convert("RGB")


def download_topo_map(
    lat: float,
    lon: float,
    *,
    zoom: int = 17,
    grid_size: int = 3,
    provider: str = "usgs-imagery",
    output_dir: Path | None = None,
) -> Path:
    """Download a map or satellite image centered on (lat, lon) and save to disk.

    Args:
        lat: Latitude (WGS84).
        lon: Longitude (WGS84).
        zoom: Tile zoom level (1–17). Higher = more detail.
        grid_size: Number of tiles per side (OpenTopoMap only; e.g. 3 = 3x3 grid).
        provider: "usgs-imagery" (satellite, default), "usgs" (topo), or "opentopomap".
        output_dir: Where to save. Default: project topo-images/.

    Returns:
        Path to saved image file.

    Raises:
        requests.HTTPError: On download failure.
    """
    out = output_dir or DEFAULT_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    if provider in ("usgs-imagery", "usgs"):
        export_url = USGS_IMAGERY_URL if provider == "usgs-imagery" else USGS_TOPO_URL
        suffix = "imagery" if provider == "usgs-imagery" else "usgs"
        return _download_usgs(lat, lon, zoom=zoom, output_dir=out, export_url=export_url, suffix=suffix)
    return _download_opentopomap(lat, lon, zoom=zoom, grid_size=grid_size, output_dir=out)


def _download_opentopomap(
    lat: float,
    lon: float,
    zoom: int,
    grid_size: int,
    output_dir: Path,
) -> Path:
    """Download OpenTopoMap tiles, stitch, save."""
    cx, cy = lat_lon_to_tile(lat, lon, zoom)
    half = grid_size // 2
    x_min = cx - half
    y_min = cy - half

    width = grid_size * TILE_SIZE
    height = grid_size * TILE_SIZE
    canvas = Image.new("RGB", (width, height))

    for dy in range(grid_size):
        for dx in range(grid_size):
            tx = x_min + dx
            ty = y_min + dy
            sub = OPEN_TOPO_SUBS[(tx + ty) % len(OPEN_TOPO_SUBS)]
            url = OPEN_TOPO_TEMPLATE.format(sub=sub, z=zoom, x=tx, y=ty)
            img = _fetch_tile(url)
            canvas.paste(img, (dx * TILE_SIZE, dy * TILE_SIZE))

    path = output_dir / f"{lat:.5f}_{lon:.5f}_z{zoom}.png"
    canvas.save(path)
    return path


def _lon_lat_to_web_mercator(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 to Web Mercator (EPSG:3857) in meters."""
    x = math.radians(lon) * 6378137.0
    lat_rad = math.radians(lat)
    y = 6378137.0 * math.log(math.tan(math.pi / 4 + lat_rad / 2))
    return x, y


def _download_usgs(
    lat: float,
    lon: float,
    zoom: int,
    output_dir: Path,
    *,
    export_url: str,
    suffix: str,
) -> Path:
    """Export a region from USGS MapServer. US coverage only."""
    # Approx meters per pixel at zoom (Web Mercator). 256px tiles.
    # Level 0: ~156543 m/px. Each zoom halves it.
    base_res = 156543.033928
    meters_per_pixel = base_res / (2**zoom)
    # Fetch a 768x768 region (3 tiles) centered on point
    half_m = 384 * meters_per_pixel
    mx, my = _lon_lat_to_web_mercator(lon, lat)
    bbox = f"{mx - half_m},{my - half_m},{mx + half_m},{my + half_m}"
    size = "768,768"

    params = {
        "bbox": bbox,
        "size": size,
        "format": "png",
        "transparent": "false",
        "f": "image",
    }
    r = requests.get(export_url, params=params, timeout=30)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content)).convert("RGB")
    path = output_dir / f"{lat:.5f}_{lon:.5f}_z{zoom}_{suffix}.png"
    img.save(path)
    return path
