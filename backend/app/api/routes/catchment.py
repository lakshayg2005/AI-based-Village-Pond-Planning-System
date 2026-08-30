from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from ...schemas.catchment import CatchmentAnalyzeResponse
from ...services.accumulation_service import (
    accumulation_statistics,
    calculate_flow_accumulation,
)
from ...services.catchment_service import (
    catchment_to_geojson,
    delineate_catchment,
)
from ...services.flow_service import analyze_flow
from ...services.kml_parser import parse_kml_bytes
from ...services.suitability_service import detect_pond_candidates
from ...services.terrain_service import reconstruct_dem

router = APIRouter(
    prefix="/api/catchment",
    tags=["Catchment Analysis"],
)

_ALLOWED_EXTENSIONS = {".kml", ".kmz"}


@router.post(
    "/analyze",
    response_model=CatchmentAnalyzeResponse,
)
async def analyze_catchment(
    file: UploadFile = File(
        ...,
        description="Contour map in KML or KMZ format",
    ),
    grid_resolution_m: float = Query(
        10.0,
        gt=0,
        le=100,
        description="DEM cell size in metres",
    ),
    sample_spacing_m: float | None = Query(
        None,
        gt=0,
        le=100,
    ),
    interpolation_method: str = Query(
        "linear",
        pattern="^(linear|nearest)$",
    ),
    max_slope_percent: float = Query(
        8.0,
        gt=0,
        le=100,
    ),
    minimum_accumulation: int = Query(
        10,
        ge=1,
    ),
    max_candidates: int = Query(
        10,
        ge=1,
        le=100,
    ),
    minimum_distance_cells: int = Query(
        10,
        ge=0,
    ),
) -> CatchmentAnalyzeResponse:
    filename = file.filename or ""

    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .kml and .kmz files are supported",
        )

    try:
        # ---------------------------------------------------------
        # 1. Read and parse contour file
        # ---------------------------------------------------------

        data = await file.read()

        if not data:
            raise ValueError("Uploaded file is empty")

        contours = parse_kml_bytes(
            data,
            filename,
        )

        if not contours:
            raise ValueError(
                "No valid LineString contours with numeric elevations were found"
            )

        # ---------------------------------------------------------
        # 2. Reconstruct DEM
        # ---------------------------------------------------------

        terrain = reconstruct_dem(
            contours,
            grid_resolution_m=grid_resolution_m,
            sample_spacing_m=sample_spacing_m,
            method=interpolation_method,
        )

        # ---------------------------------------------------------
        # 3. Sink filling + D8 flow direction
        # ---------------------------------------------------------

        flow = analyze_flow(
            terrain.elevation_grid_m,
            cell_size_x_m=terrain.grid_resolution_m,
            cell_size_y_m=terrain.grid_resolution_m,
        )

        # ---------------------------------------------------------
        # 4. Flow accumulation
        # ---------------------------------------------------------

        accumulation = calculate_flow_accumulation(
            flow.flow_direction,
        )

        accumulation_stats = accumulation_statistics(
            accumulation,
        )

        # ---------------------------------------------------------
        # 5. Pond suitability
        # ---------------------------------------------------------

        candidates = detect_pond_candidates(
            elevation_m=flow.filled_dem_m,
            slope_percent=terrain.slope_grid_percent,
            flow_accumulation=accumulation,
            max_slope_percent=max_slope_percent,
            minimum_accumulation=minimum_accumulation,
            max_candidates=max_candidates,
            minimum_distance_cells=minimum_distance_cells,
        )

        # ---------------------------------------------------------
        # 6. Geographic coordinate conversion
        # ---------------------------------------------------------

        # terrain.x_m / terrain.y_m are projected coordinates.
        # Convert candidate grid locations back to lon/lat.
        from pyproj import Transformer

        inverse_transformer = Transformer.from_crs(
            terrain.crs,
            "EPSG:4326",
            always_xy=True,
        )

        candidate_responses = []

        for rank, candidate in enumerate(
            candidates,
            start=1,
        ):
            x = terrain.x_m[candidate.col] + terrain.grid_resolution_m / 2.0

            y = terrain.y_m[candidate.row] + terrain.grid_resolution_m / 2.0

            longitude, latitude = inverse_transformer.transform(
                x,
                y,
            )

            candidate_responses.append(
                {
                    "rank": rank,
                    "row": candidate.row,
                    "col": candidate.col,
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                    "elevation_m": candidate.elevation_m,
                    "slope_percent": candidate.slope_percent,
                    "flow_accumulation": candidate.flow_accumulation,
                    "score": candidate.score,
                }
            )

        # ---------------------------------------------------------
        # 7. Catchment delineation for each candidate
        # ---------------------------------------------------------

        catchment_responses = []

        for candidate in candidates:
            catchment = delineate_catchment(
                flow_direction=flow.flow_direction,
                outlet_row=candidate.row,
                outlet_col=candidate.col,
                cell_size_x_m=terrain.grid_resolution_m,
                cell_size_y_m=terrain.grid_resolution_m,
            )

            catchment_responses.append(
                {
                    "area_m2": catchment.area_m2,
                    "area_hectares": catchment.area_hectares,
                    "cell_count": catchment.cell_count,
                    "geometry": catchment_to_geojson(catchment),
                }
            )

        # ---------------------------------------------------------
        # 8. Terrain statistics
        # ---------------------------------------------------------

        elevations = {round(c.elevation_m, 6) for c in contours}

        cell_count = int(terrain.elevation_grid_m.size)

        nan_percentage = 100.0 * (cell_count - terrain.valid_cell_count) / cell_count

        height, width = terrain.elevation_grid_m.shape

        # ---------------------------------------------------------
        # 9. Final response
        # ---------------------------------------------------------

        return CatchmentAnalyzeResponse(
            status="success",
            message=(
                "Contour terrain parsed, reconstructed, "
                "validated, slope calculated, sink-filled, "
                "processed with D8 flow direction, flow "
                "accumulation calculated, pond candidates "
                "ranked, and catchments delineated"
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
                "flow_accumulation": accumulation_stats,
                "pond_candidates": candidate_responses,
            },
            accumulation=accumulation_stats,
            suitability={
                "max_slope_percent": max_slope_percent,
                "minimum_accumulation": minimum_accumulation,
                "candidate_count": len(candidates),
                "candidates": candidate_responses,
            },
            analysis={
                "suitability": {
                    "max_slope_percent": max_slope_percent,
                    "minimum_accumulation": minimum_accumulation,
                    "candidate_count": len(candidates),
                },
                "candidates": candidate_responses,
                "catchments": catchment_responses,
            },
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Terrain analysis failed: {exc}",
        ) from exc