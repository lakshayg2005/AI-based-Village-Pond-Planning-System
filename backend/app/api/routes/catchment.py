from __future__ import annotations
from pyproj import Transformer
from shapely.geometry import Point
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
from ...services.geojson_service import (
    make_feature,
    make_feature_collection,
    transform_geojson_to_wgs84,
)

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
        15,
        ge=1,
        le=100,
    ),
    minimum_distance_cells: int = Query(
        10,
        ge=0,
    ),
) -> CatchmentAnalyzeResponse:

    # =========================================================
    # Validate file extension
    # =========================================================

    filename = file.filename or ""

    extension = (
        "." + filename.rsplit(".", 1)[-1].lower()
        if "." in filename
        else ""
    )

    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .kml and .kmz files are supported",
        )

    try:
        # =====================================================
        # 1. Read and parse contour file
        # =====================================================

        data = await file.read()

        if not data:
            raise ValueError("Uploaded file is empty")

        contours = parse_kml_bytes(
            data,
            filename,
        )

        if not contours:
            raise ValueError(
                "No valid LineString contours with numeric "
                "elevations were found"
            )

        # =====================================================
        # 2. Reconstruct DEM
        # =====================================================

        terrain = reconstruct_dem(
            contours,
            grid_resolution_m=grid_resolution_m,
            sample_spacing_m=sample_spacing_m,
            method=interpolation_method,
        )

        # =====================================================
        # 3. Sink filling + D8 flow direction
        # =====================================================

        flow = analyze_flow(
            terrain.elevation_grid_m,
            cell_size_x_m=terrain.grid_resolution_m,
            cell_size_y_m=terrain.grid_resolution_m,
        )

        # =====================================================
        # 4. Flow accumulation
        # =====================================================

        accumulation = calculate_flow_accumulation(
            flow.flow_direction,
        )

        accumulation_stats = accumulation_statistics(
            accumulation,
        )

        # =====================================================
        # 5. Pond suitability
        # =====================================================

        candidates = detect_pond_candidates(
            elevation_m=flow.filled_dem_m,
            slope_percent=terrain.slope_grid_percent,
            flow_accumulation=accumulation,
            flow_direction=flow.flow_direction,
            max_slope_percent=max_slope_percent,
            minimum_accumulation=minimum_accumulation,
            max_candidates=max_candidates,
            minimum_distance_cells=minimum_distance_cells,
        )

        # =====================================================
        # 6. Geographic coordinate conversion
        #
        # Terrain coordinates are projected coordinates.
        # Convert candidate cell centers to WGS84.
        # =====================================================

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
            x = (
                terrain.x_m[candidate.col]
                + terrain.grid_resolution_m / 2.0
            )

            y = (
                terrain.y_m[candidate.row]
                + terrain.grid_resolution_m / 2.0
            )

            longitude, latitude = inverse_transformer.transform(
                x,
                y,
            )

            candidate_responses.append(
                {
                    "rank": rank,
                    "row": int(candidate.row),
                    "col": int(candidate.col),
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                    "elevation_m": float(candidate.elevation_m),
                    "slope_percent": float(candidate.slope_percent),
                    "flow_accumulation": int(
                        candidate.flow_accumulation
                    ),
                    "score": float(candidate.score),
                    # Advanced suitability diagnostics
                    "basin_score": float(candidate.basin_score),
                    "storage_score": float(candidate.storage_score),
                    "channel_penalty": float(candidate.channel_penalty),
                    "non_channel_score": float(candidate.non_channel_score),
                    "local_relief_score": float(candidate.local_relief_score),
                    "reason": candidate.reason,
                }
            )

        # =====================================================
        # 7. Catchment delineation
        # =====================================================

        catchment_responses = []
        catchment_features = []

        for rank, candidate in enumerate(
            candidates,
            start=1,
        ):
            # -------------------------------------------------
            # Debug information
            # -------------------------------------------------

            print(
                "\n========== CATCHMENT INPUT DEBUG =========="
            )

            print(
                "Terrain CRS:",
                terrain.crs,
            )

            print(
                "Terrain X range:",
                terrain.x_m.min(),
                terrain.x_m.max(),
            )

            print(
                "Terrain Y range:",
                terrain.y_m.min(),
                terrain.y_m.max(),
            )

            print(
                "Terrain grid shape:",
                terrain.elevation_grid_m.shape,
            )

            print(
                "Candidate row:",
                candidate.row,
            )

            print(
                "Candidate col:",
                candidate.col,
            )

            print(
                "Candidate projected X:",
                terrain.x_m[candidate.col],
            )

            print(
                "Candidate projected Y:",
                terrain.y_m[candidate.row],
            )

            print(
                "==========================================="
            )

            # -------------------------------------------------
            # IMPORTANT:
            #
            # delineate_catchment() requires:
            #
            # flow_direction
            # outlet_row
            # outlet_col
            # cell_size_x_m
            # cell_size_y_m
            # x_m
            # y_m
            #
            # The previous route was missing x_m and y_m.
            # -------------------------------------------------

            catchment = delineate_catchment(
                flow_direction=flow.flow_direction,
                outlet_row=int(candidate.row),
                outlet_col=int(candidate.col),
                cell_size_x_m=terrain.grid_resolution_m,
                cell_size_y_m=terrain.grid_resolution_m,
                x_m=terrain.x_m,
                y_m=terrain.y_m,
            )

            # -------------------------------------------------
            # Candidate cell center
            # -------------------------------------------------

            candidate_x = (
                terrain.x_m[candidate.col]
                + terrain.grid_resolution_m / 2.0
            )

            candidate_y = (
                terrain.y_m[candidate.row]
                + terrain.grid_resolution_m / 2.0
            )

            candidate_point = Point(
                candidate_x,
                candidate_y,
            )

            # -------------------------------------------------
            # Catchment alignment diagnostics
            # -------------------------------------------------

            print(
                "========== CATCHMENT ALIGNMENT DEBUG =========="
            )

            print(
                "Candidate row/col:",
                candidate.row,
                candidate.col,
            )

            print(
                "Candidate XY:",
                candidate_x,
                candidate_y,
            )

            print(
                "Catchment bounds:",
                catchment.polygon.bounds,
            )

            print(
                "Candidate inside catchment:",
                catchment.polygon.contains(
                    candidate_point
                ),
            )

            print(
                "Candidate touches catchment:",
                catchment.polygon.touches(
                    candidate_point
                ),
            )

            print(
                "Candidate intersects catchment:",
                catchment.polygon.intersects(
                    candidate_point
                ),
            )

            print(
                "Catchment area:",
                catchment.polygon.area,
            )

            expected_raster_area = (
                catchment.cell_count
                * terrain.grid_resolution_m
                * terrain.grid_resolution_m
            )

            print(
                "Expected raster area:",
                expected_raster_area,
            )

            print(
                "Catchment cell count:",
                catchment.cell_count,
            )

            polygon_area_ratio = (
                catchment.polygon.area
                / expected_raster_area
                if expected_raster_area > 0
                else 0.0
            )

            print(
                "Catchment polygon area / raster area:",
                polygon_area_ratio,
            )

            print(
                "================================================"
            )

            # -------------------------------------------------
            # Convert catchment polygon to GeoJSON
            # -------------------------------------------------

            geometry_projected = catchment_to_geojson(
                catchment,
            )

            print(
                "========== PROJECTED CATCHMENT =========="
            )

            print(
                "Geometry type:",
                geometry_projected.get("type"),
            )

            geometry_type = geometry_projected.get("type")

            coordinates = geometry_projected.get(
                "coordinates",
                [],
            )

            if geometry_type == "Polygon":
                if coordinates:
                    print(
                        "First coordinate:",
                        coordinates[0][0],
                    )

            elif geometry_type == "MultiPolygon":
                if coordinates:
                    print(
                        "First coordinate:",
                        coordinates[0][0][0],
                    )

            print(
                "========================================="
            )

            # -------------------------------------------------
            # Convert projected geometry -> WGS84
            # -------------------------------------------------

            geometry_wgs84 = transform_geojson_to_wgs84(
                geometry_projected,
                terrain.crs,
            )

            # -------------------------------------------------
            # Catchment properties
            # -------------------------------------------------

            properties = {
                "rank": rank,
                "area_m2": float(
                    catchment.area_m2
                ),
                "area_hectares": float(
                    catchment.area_hectares
                ),
                "cell_count": int(
                    catchment.cell_count
                ),
                "outlet_latitude": candidate_responses[
                    rank - 1
                ]["latitude"],
                "outlet_longitude": candidate_responses[
                    rank - 1
                ]["longitude"],
                "candidate_score": float(
                    candidate.score
                ),
            }

            # -------------------------------------------------
            # API-friendly catchment object
            # -------------------------------------------------

            catchment_responses.append(
                {
                    "rank": rank,
                    "area_m2": float(
                        catchment.area_m2
                    ),
                    "area_hectares": float(
                        catchment.area_hectares
                    ),
                    "cell_count": int(
                        catchment.cell_count
                    ),
                    "geometry": geometry_wgs84,
                }
            )

            # -------------------------------------------------
            # GeoJSON Feature for frontend/map
            # -------------------------------------------------

            catchment_features.append(
                make_feature(
                    geometry_wgs84,
                    properties,
                )
            )

        # =====================================================
        # 8. Catchment FeatureCollection
        # =====================================================

        catchment_geojson = make_feature_collection(
            catchment_features
        )

        # =====================================================
        # 9. Candidate FeatureCollection
        # =====================================================

        candidate_features = []

        for candidate in candidate_responses:
            candidate_features.append(
                make_feature(
                    {
                        "type": "Point",
                        "coordinates": [
                            candidate["longitude"],
                            candidate["latitude"],
                        ],
                    },
                    {
                        "rank": candidate["rank"],
                        "elevation_m": candidate[
                            "elevation_m"
                        ],
                        "slope_percent": candidate[
                            "slope_percent"
                        ],
                        "flow_accumulation": candidate[
                            "flow_accumulation"
                        ],
                        "score": candidate["score"],
                        "basin_score": candidate["basin_score"],
                        "storage_score": candidate["storage_score"],
                        "channel_penalty": candidate["channel_penalty"],
                        "non_channel_score": candidate["non_channel_score"],
                        "reason": candidate["reason"],
                    },
                )
            )

        candidate_geojson = make_feature_collection(
            candidate_features
        )

        # =====================================================
        # 10. Map-ready data
        # =====================================================

        map_data = {
            "candidates": candidate_geojson,
            "catchments": catchment_geojson,
        }

        # =====================================================
        # 11. Terrain statistics
        # =====================================================

        elevations = {
            round(c.elevation_m, 6)
            for c in contours
        }

        cell_count = int(
            terrain.elevation_grid_m.size
        )

        nan_percentage = (
            100.0
            * (
                cell_count
                - terrain.valid_cell_count
            )
            / cell_count
            if cell_count > 0
            else 0.0
        )

        height, width = (
            terrain.elevation_grid_m.shape
        )

        # =====================================================
        # 12. Final debug
        # =====================================================

        print(
            "========== CATCHMENT CRS DEBUG =========="
        )

        print(
            "Terrain CRS:",
            terrain.crs,
        )

        if catchment_features:
            first_geometry = (
                catchment_features[0]["geometry"]
            )

            print(
                "First catchment geometry type:",
                first_geometry.get("type"),
            )

            first_coordinates = first_geometry.get(
                "coordinates",
                [],
            )

            if first_coordinates:
                print(
                    "First catchment first coordinate:",
                    first_coordinates[:1],
                )

        print(
            "========================================="
        )

        # =====================================================
        # 13. Final API response
        # =====================================================

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

                "elevation_levels": len(
                    elevations
                ),

                "min_elevation_m": (
                    terrain.min_elevation_m
                ),

                "max_elevation_m": (
                    terrain.max_elevation_m
                ),

                "grid_resolution_m": (
                    terrain.grid_resolution_m
                ),

                "contour_sample_count": (
                    terrain.sample_count
                ),

                "valid_dem_cells": (
                    terrain.valid_cell_count
                ),

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
                    "valid_cell_count": (
                        terrain.valid_cell_count
                    ),
                    "nan_percentage": (
                        nan_percentage
                    ),
                    "resolution_m": (
                        terrain.grid_resolution_m
                    ),
                    "crs": terrain.crs,
                },

                "slope": {
                    "min_percent": (
                        terrain.slope_min_percent
                    ),
                    "max_percent": (
                        terrain.slope_max_percent
                    ),
                    "mean_percent": (
                        terrain.slope_mean_percent
                    ),
                },

                "contour_validation": {
                    "rmse_m": (
                        terrain.contour_rmse_m
                    ),
                    "max_abs_error_m": (
                        terrain.contour_max_abs_error_m
                    ),
                    "p95_abs_error_m": (
                        terrain.contour_p95_abs_error_m
                    ),
                },
            },

            hydrology={
                "dem_filled": (
                    flow.filled_cell_count > 0
                ),

                "filled_cell_count": (
                    flow.filled_cell_count
                ),

                "max_fill_depth_m": (
                    flow.max_fill_depth_m
                ),

                "valid_cell_count": (
                    flow.valid_cell_count
                ),

                "flowing_cell_count": (
                    flow.flowing_cell_count
                ),

                "no_flow_cell_count": (
                    flow.no_flow_cell_count
                ),

                "d8_algorithm": (
                    "D8 steepest-descent"
                ),

                "flow_accumulation": (
                    accumulation_stats
                ),

                "pond_candidates": (
                    candidate_responses
                ),
            },

            accumulation=accumulation_stats,

            suitability={
                "max_slope_percent": (
                    max_slope_percent
                ),

                "minimum_accumulation": (
                    minimum_accumulation
                ),

                "candidate_count": len(
                    candidates
                ),

                "candidates": (
                    candidate_responses
                ),
            },

            analysis={
                "suitability": {
                    "max_slope_percent": (
                        max_slope_percent
                    ),

                    "minimum_accumulation": (
                        minimum_accumulation
                    ),

                    "candidate_count": len(
                        candidates
                    ),
                },

                "candidates": (
                    candidate_responses
                ),

                "catchments": (
                    catchment_responses
                ),
            },

            map_data=map_data,
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

