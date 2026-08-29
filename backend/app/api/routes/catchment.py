from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ...schemas.catchment import CatchmentAnalyzeResponse
from ...services.kml_parser import parse_kml_bytes
from ...services.terrain_service import reconstruct_dem
from ...services.flow_service import analyze_flow

router = APIRouter(prefix="/api/catchment", tags=["Catchment Analysis"])

_ALLOWED_EXTENSIONS = {".kml", ".kmz"}


@router.post("/analyze", response_model=CatchmentAnalyzeResponse)
async def analyze_catchment(
    file: UploadFile = File(..., description="Contour map in KML or KMZ format"),
    grid_resolution_m: float = Query(10.0, gt=0, le=100, description="DEM cell size in metres"),
    sample_spacing_m: float | None = Query(None, gt=0, le=100),
    interpolation_method: str = Query("linear", pattern="^(linear|nearest)$"),
) -> CatchmentAnalyzeResponse:
    filename = file.filename or ""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .kml and .kmz files are supported")

    try:
        data = await file.read()
        if not data:
            raise ValueError("Uploaded file is empty")

        contours = parse_kml_bytes(data, filename)
        if not contours:
            raise ValueError("No valid LineString contours with numeric elevations were found")

        terrain = reconstruct_dem(
            contours,
            grid_resolution_m=grid_resolution_m,
            sample_spacing_m=sample_spacing_m,
            method=interpolation_method,
        )
        flow = analyze_flow(
            terrain.elevation_grid_m,
            cell_size_x_m=terrain.grid_resolution_m,
            cell_size_y_m=terrain.grid_resolution_m,
        )
        elevations = {round(c.elevation_m, 6) for c in contours}
        cell_count = int(terrain.elevation_grid_m.size)
        nan_percentage = 100.0 * (cell_count - terrain.valid_cell_count) / cell_count
        height, width = terrain.elevation_grid_m.shape

        return CatchmentAnalyzeResponse(
            status="success",
            message=(
                "Contour terrain parsed, reconstructed, validated, "
                "slope calculated, sink-filled, and processed with D8 flow direction"
            ),
            terrain={
                "contour_count": len(contours),
                "elevation_levels": len(elevations),
                "min_elevation_m": terrain.min_elevation_m,
                "max_elevation_m": terrain.max_elevation_m,
                "grid_resolution_m": terrain.grid_resolution_m,
                "contour_sample_count": terrain.sample_count,
                "valid_dem_cells": terrain.valid_cell_count,
                "crs": terrain.crs,
                "bounds": {
                    "min_lon": terrain.bounds_lonlat[0],
                    "min_lat": terrain.bounds_lonlat[1],
                    "max_lon": terrain.bounds_lonlat[2],
                    "max_lat": terrain.bounds_lonlat[3],
                },
                "dem": {
                    "width": width,
                    "height": height,
                    "cell_count": cell_count,
                    "valid_cell_count": terrain.valid_cell_count,
                    "nan_percentage": nan_percentage,
                    "resolution_m": terrain.grid_resolution_m,
                    "crs": terrain.crs,
                },
                "slope": {
                    "min_percent": terrain.slope_min_percent,
                    "max_percent": terrain.slope_max_percent,
                    "mean_percent": terrain.slope_mean_percent,
                },
                "contour_validation": {
                    "rmse_m": terrain.contour_rmse_m,
                    "max_abs_error_m": terrain.contour_max_abs_error_m,
                    "p95_abs_error_m": terrain.contour_p95_abs_error_m,
                },
            },
            hydrology={
                "dem_filled": flow.filled_cell_count > 0,
                "filled_cell_count": flow.filled_cell_count,
                "max_fill_depth_m": flow.max_fill_depth_m,
                "valid_cell_count": flow.valid_cell_count,
                "flowing_cell_count": flow.flowing_cell_count,
                "no_flow_cell_count": flow.no_flow_cell_count,
                "d8_algorithm": "D8 steepest-descent",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Terrain analysis failed: {exc}") from exc
