from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from ...schemas.area import AreaAnalyzeRequest, AreaAnalyzeResponse
from ...services.analysis_pipeline import run_hydrology
from ...services.concurrency import run_exclusive
from ...services.dem_service import (
    AreaError,
    TileFetchError,
    build_terrain_from_polygon,
    parse_polygon,
    polygon_mask,
)
from ...services.rainfall_service import (
    RainfallError,
    fallback_rainfall,
    get_annual_rainfall,
    manual_rainfall,
)

router = APIRouter(
    prefix="/api",
    tags=["Area Analysis"],
)


def _analyse(request: AreaAnalyzeRequest, polygon, rainfall):
    terrain, dem_info = build_terrain_from_polygon(polygon)
    mask = polygon_mask(terrain, polygon)

    if not mask.any():
        raise AreaError("Selected area is too small to analyse")

    output = run_hydrology(
        terrain,
        max_slope_percent=request.max_slope_percent,
        minimum_accumulation=request.minimum_accumulation,
        max_candidates=request.max_candidates,
        minimum_distance_cells=request.minimum_distance_cells,
        analysis_mask=mask,
        rainfall=rainfall,
        runoff_coefficient=request.runoff_coefficient,
    )

    height, width = terrain.elevation_grid_m.shape
    flow = output.flow

    return terrain, dem_info, output, flow, (height, width)


@router.post(
    "/analyze-area",
    response_model=AreaAnalyzeResponse,
)
async def analyze_area(request: AreaAnalyzeRequest) -> AreaAnalyzeResponse:
    try:
        polygon = parse_polygon(request.polygon)
    except AreaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    centroid = polygon.centroid

    if request.rainfall_mm is not None:
        rainfall = manual_rainfall(request.rainfall_mm)
    else:
        try:
            rainfall = await asyncio.to_thread(
                get_annual_rainfall, centroid.y, centroid.x
            )
        except RainfallError:
            rainfall = fallback_rainfall()

    try:
        terrain, dem_info, output, flow, (height, width) = (
            await run_exclusive(_analyse, request, polygon, rainfall)
        )
    except AreaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TileFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    candidates = output.candidate_responses
    best = candidates[0] if candidates else None

    summary = {
        "pond_count": len(candidates),
        "best_pond": (
            {
                "rank": 1,
                "latitude": best["latitude"],
                "longitude": best["longitude"],
                "catchment_area_m2": best["catchment_area_m2"],
                "catchment_area_hectares": best["catchment_area_hectares"],
                "annual_runoff_m3": best["volume"]["annual_runoff_m3"],
                "storage_capacity_m3": best["volume"]["recommended_pond"][
                    "storage_capacity_m3"
                ],
            }
            if best
            else None
        ),
    }

    message = (
        f"Found {len(candidates)} suitable pond location(s) in the selected area."
        if candidates
        else "No suitable pond location found. Try a larger area or a "
        "higher maximum slope."
    )

    return AreaAnalyzeResponse(
        status="success",
        message=message,
        area={
            "area_km2": dem_info.area_km2,
            "centroid": {"latitude": centroid.y, "longitude": centroid.x},
        },
        terrain={
            "source": dem_info.source,
            "zoom": dem_info.zoom,
            "tile_count": dem_info.tile_count,
            "grid_resolution_m": dem_info.resolution_m,
            "width": width,
            "height": height,
            "cell_count": width * height,
            "crs": terrain.crs,
            "min_elevation_m": terrain.min_elevation_m,
            "max_elevation_m": terrain.max_elevation_m,
            "slope_mean_percent": terrain.slope_mean_percent,
            "slope_max_percent": terrain.slope_max_percent,
            "bounds": {
                "min_lon": terrain.bounds_lonlat[0],
                "min_lat": terrain.bounds_lonlat[1],
                "max_lon": terrain.bounds_lonlat[2],
                "max_lat": terrain.bounds_lonlat[3],
            },
        },
        rainfall={
            "annual_mm": rainfall.annual_mm,
            "monthly_mm": rainfall.monthly_mm,
            "source": rainfall.source,
            "measured": rainfall.measured,
            "years": rainfall.years,
        },
        summary=summary,
        hydrology={
            "dem_filled": flow.filled_cell_count > 0,
            "filled_cell_count": flow.filled_cell_count,
            "max_fill_depth_m": flow.max_fill_depth_m,
            "valid_cell_count": flow.valid_cell_count,
            "flowing_cell_count": flow.flowing_cell_count,
            "no_flow_cell_count": flow.no_flow_cell_count,
            "d8_algorithm": "D8 steepest-descent",
            "flow_accumulation": output.accumulation_stats,
            "pond_candidates": candidates,
        },
        accumulation=output.accumulation_stats,
        suitability={
            "max_slope_percent": request.max_slope_percent,
            "minimum_accumulation": request.minimum_accumulation,
            "candidate_count": len(candidates),
            "candidates": candidates,
        },
        analysis={
            "suitability": {
                "max_slope_percent": request.max_slope_percent,
                "minimum_accumulation": request.minimum_accumulation,
                "candidate_count": len(candidates),
            },
            "candidates": candidates,
            "catchments": output.catchment_responses,
        },
        map_data=output.map_data,
    )
