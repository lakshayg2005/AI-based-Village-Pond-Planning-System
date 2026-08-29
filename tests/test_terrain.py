from pathlib import Path

import numpy as np

from app.services.kml_parser import parse_kml_file
from app.services.terrain_service import reconstruct_dem


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KML_PATH = PROJECT_ROOT / "contours_1m.kml"


def test_reconstruct_dem_and_validate_contours():
    contours = parse_kml_file(KML_PATH)
    terrain = reconstruct_dem(contours, grid_resolution_m=10.0)

    assert terrain.elevation_grid_m.ndim == 2
    assert terrain.elevation_grid_m.size > 0
    assert terrain.valid_cell_count == terrain.elevation_grid_m.size
    assert np.isfinite(terrain.elevation_grid_m).all()
    assert np.isfinite(terrain.slope_grid_percent).all()

    assert terrain.min_elevation_m >= min(c.elevation_m for c in contours) - 1e-6
    assert terrain.max_elevation_m <= max(c.elevation_m for c in contours) + 1e-6
    assert terrain.slope_min_percent >= 0
    assert terrain.slope_mean_percent >= terrain.slope_min_percent
    assert terrain.slope_max_percent >= terrain.slope_mean_percent

    # A contour-derived DEM should reproduce its input contour elevations closely.
    assert terrain.contour_rmse_m < 1.0
    assert terrain.contour_p95_abs_error_m < 1.0
    assert terrain.contour_max_abs_error_m < 5.0
