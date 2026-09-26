import io

import numpy as np
from fastapi.testclient import TestClient

from app.api.routes import catchment
from app.main import app
from app.services.kml_parser import ContourFeature
from app.services import terrain_service
from app.services.terrain_service import reconstruct_dem

client = TestClient(app)


def test_upload_larger_than_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(catchment, "MAX_UPLOAD_BYTES", 100)

    response = client.post(
        "/api/catchment/analyze",
        files={"contour_map": ("big.kml", io.BytesIO(b"x" * 500), "application/xml")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def _contours(size_deg):
    """Three parallel contour lines spanning `size_deg` degrees."""
    xs = np.linspace(81.0, 81.0 + size_deg, 20)
    return [
        ContourFeature(
            elevation_m=100.0 + 10.0 * i,
            coordinates=[(float(x), 21.0 + size_deg * i / 2.0) for x in xs],
        )
        for i in range(3)
    ]


def test_large_map_is_coarsened_to_respect_cell_budget(monkeypatch):
    monkeypatch.setattr(terrain_service, "MAX_GRID_CELLS", 10_000)

    terrain = reconstruct_dem(_contours(0.2), grid_resolution_m=10.0)

    assert terrain.elevation_grid_m.size <= 12_000
    assert terrain.grid_resolution_m > 10.0


def test_small_map_keeps_requested_resolution():
    terrain = reconstruct_dem(_contours(0.01), grid_resolution_m=10.0)
    assert terrain.grid_resolution_m == 10.0
