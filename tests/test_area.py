import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import dem_service
from app.services.dem_service import (
    AreaError,
    _decode_terrarium,
    build_terrain_from_polygon,
    parse_polygon,
    polygon_area_km2,
    polygon_mask,
)
from app.services.rainfall_service import manual_rainfall
from app.services.volume_service import (
    estimate_water_volume,
    suggest_runoff_coefficient,
)

# ~1 km x 1 km square near the equator-ish mid latitudes.
SQUARE = [
    [81.281, 21.259],
    [81.291, 21.259],
    [81.291, 21.268],
    [81.281, 21.268],
    [81.281, 21.259],
]


def _fake_tile(zoom, x, y):
    """A gently tilted plane with a shallow valley, in tile-pixel space."""
    rows, cols = np.mgrid[0:256, 0:256].astype(np.float32)
    valley = 4.0 * np.abs(cols - 128) / 128.0
    return 300.0 - 0.02 * rows + valley


@pytest.fixture
def fake_tiles(monkeypatch):
    monkeypatch.setattr(dem_service, "_load_tile", _fake_tile)
    monkeypatch.setattr(dem_service, "_prune_cache", lambda: None)


def test_decode_terrarium_matches_formula():
    from io import BytesIO
    from PIL import Image

    # elevation = R*256 + G + B/256 - 32768 -> R=128, G=10, B=128 => 10.5 m
    image = Image.new("RGB", (2, 2), (128, 10, 128))
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    assert np.allclose(_decode_terrarium(buffer.getvalue()), 10.5)


def test_parse_polygon_accepts_geojson_and_rings():
    ring = parse_polygon(SQUARE)
    feature = parse_polygon(
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [SQUARE]},
        }
    )
    assert ring.equals(feature)
    assert 0.9 < polygon_area_km2(ring) < 1.2


@pytest.mark.parametrize(
    "bad", [[[0, 0], [1, 1]], [[500, 500], [501, 500], [501, 501], [500, 500]]]
)
def test_parse_polygon_rejects_bad_input(bad):
    with pytest.raises(AreaError):
        parse_polygon(bad)


def test_area_limit_enforced(fake_tiles):
    big = parse_polygon(
        [[81.0, 21.0], [81.3, 21.0], [81.3, 21.3], [81.0, 21.3]]
    )
    with pytest.raises(AreaError):
        build_terrain_from_polygon(big)


def test_terrain_grid_and_mask(fake_tiles):
    polygon = parse_polygon(SQUARE)
    terrain, info = build_terrain_from_polygon(polygon)

    assert terrain.elevation_grid_m.shape == (len(terrain.y_m), len(terrain.x_m))
    assert np.all(np.diff(terrain.y_m) > 0) and np.all(np.diff(terrain.x_m) > 0)
    assert info.tile_count >= 1

    mask = polygon_mask(terrain, polygon)
    inside_km2 = mask.sum() * terrain.grid_resolution_m**2 / 1e6
    assert inside_km2 == pytest.approx(info.area_km2, rel=0.15)


def test_volume_formula():
    rainfall = manual_rainfall(1000.0)
    volume = estimate_water_volume(10_000.0, rainfall, 0.5)

    # 0.5 * 1.0 m * 10,000 m^2
    assert volume["annual_runoff_m3"] == pytest.approx(5000.0)
    assert sum(volume["monthly_runoff_m3"].values()) == pytest.approx(5000.0)
    assert volume["recommended_pond"]["surface_area_m2"] == pytest.approx(300.0)


def test_runoff_coefficient_increases_with_slope():
    values = [suggest_runoff_coefficient(s) for s in (1, 4, 8, 20)]
    assert values == sorted(values)


def test_analyze_area_endpoint(fake_tiles):
    client = TestClient(app)
    response = client.post(
        "/api/analyze-area",
        json={
            "polygon": SQUARE,
            "rainfall_mm": 1000,
            "runoff_coefficient": 0.5,
            "minimum_accumulation": 1,
            "max_candidates": 3,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["area"]["area_km2"] > 0.9
    assert body["rainfall"]["annual_mm"] == 1000
    assert body["summary"]["pond_count"] == len(body["analysis"]["candidates"])

    for candidate, catchment in zip(
        body["analysis"]["candidates"], body["analysis"]["catchments"]
    ):
        # Volume must follow C x P x A exactly.
        expected = 0.5 * 1.0 * catchment["area_m2"]
        assert candidate["volume"]["annual_runoff_m3"] == pytest.approx(expected)


def test_analyze_area_rejects_oversized_polygon(fake_tiles):
    client = TestClient(app)
    response = client.post(
        "/api/analyze-area",
        json={"polygon": [[81, 21], [81.3, 21], [81.3, 21.3], [81, 21.3]]},
    )
    assert response.status_code == 422
    assert "limit" in response.json()["detail"]


def test_health():
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}
