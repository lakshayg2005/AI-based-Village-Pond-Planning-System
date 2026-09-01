from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from pyproj import Transformer

from ...schemas.catchment_v2 import CatchmentV2Response
from ...services.kml_parser import parse_kml_bytes
from ...services.terrain_service import reconstruct_dem
from ...services.accumulation_service import calculate_flow_accumulation
from ...services.flow_service import calculate_d8_flow_direction
from ...services.depression_service import detect_depressions
from ...services.depression_catchment_service import (
    calculate_catchment_for_depression,
    catchment_statistics,
)
from ...services.channel_service import (
    detect_channels,
    channel_penalty_at,
)


router = APIRouter(
    prefix="/api/v2/catchment",
    tags=["Catchment Analysis V2"],
)


_ALLOWED_EXTENSIONS = {
    ".kml",
    ".kmz",
}


def _feature(
    geometry: dict,
    properties: dict,
) -> dict:
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }


def _feature_collection(
    features: list[dict],
) -> dict:
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _cell_polygon(
    terrain,
    row: int,
    col: int,
    transformer: Transformer,
) -> list[list[float]]:
    resolution = terrain.grid_resolution_m

    x0 = terrain.x_m[col]
    y0 = terrain.y_m[row]

    x1 = x0 + resolution
    y1 = y0 + resolution

    points = [
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x0, y1),
        (x0, y0),
    ]

    result = []

    for x, y in points:
        lon, lat = transformer.transform(x, y)

        result.append(
            [
                float(lon),
                float(lat),
            ]
        )

    return result


def _mask_to_geojson(
    terrain,
    mask: np.ndarray,
    transformer: Transformer,
) -> dict:
    """
    Convert a raster mask into a compact GeoJSON geometry.

    Instead of generating one polygon per cell, contiguous raster
    regions are traced into polygons. This dramatically reduces
    GeoJSON size for large catchments/depressions/channels.
    """

    mask = np.asarray(mask, dtype=bool)

    if mask.ndim != 2:
        raise ValueError("Mask must be 2-D")

    if not np.any(mask):
        return {
            "type": "Polygon",
            "coordinates": [],
        }

    try:
        import rasterio.features
        from affine import Affine

        resolution = float(
            terrain.grid_resolution_m
        )

        x_values = np.asarray(
            terrain.x_m,
            dtype=np.float64,
        )

        y_values = np.asarray(
            terrain.y_m,
            dtype=np.float64,
        )

        x_origin = float(x_values[0])
        y_origin = float(y_values[0])

        transform = Affine(
            resolution,
            0.0,
            x_origin,
            0.0,
            resolution,
            y_origin,
        )

        shapes = rasterio.features.shapes(
            mask.astype(np.uint8),
            mask=mask,
            connectivity=8,
            transform=transform,
        )

        polygons = []

        for geometry, value in shapes:
            if int(value) != 1:
                continue

            coordinates = geometry.get(
                "coordinates",
                [],
            )

            converted_rings = []

            for ring in coordinates:
                converted_ring = []

                for x, y in ring:
                    lon, lat = transformer.transform(
                        float(x),
                        float(y),
                    )

                    converted_ring.append(
                        [
                            float(lon),
                            float(lat),
                        ]
                    )

                if len(converted_ring) >= 4:
                    converted_rings.append(
                        converted_ring
                    )

            if not converted_rings:
                continue

            polygons.append(
                converted_rings
            )

        if not polygons:
            return {
                "type": "Polygon",
                "coordinates": [],
            }

        if len(polygons) == 1:
            return {
                "type": "Polygon",
                "coordinates": polygons[0],
            }

        return {
            "type": "MultiPolygon",
            "coordinates": polygons,
        }

    except ImportError:
        # Fallback for installations without rasterio.
        # This is slower and produces larger GeoJSON, but keeps
        # the endpoint functional.
        polygons = []

        rows, cols = mask.shape

        for row in range(rows):
            for col in range(cols):
                if not mask[row, col]:
                    continue

                polygon = _cell_polygon(
                    terrain,
                    row,
                    col,
                    transformer,
                )

                polygons.append(
                    [polygon]
                )

        if len(polygons) == 1:
            return {
                "type": "Polygon",
                "coordinates": polygons[0],
            }

        return {
            "type": "MultiPolygon",
            "coordinates": polygons,
        }


def _candidate_score(
    slope_percent: float,
    max_slope_percent: float,
    accumulation: int,
    depression_depth: float,
    channel_penalty: float,
    catchment_area_m2: float,
) -> float:

    slope_score = max(
        0.0,
        1.0
        - (
            slope_percent
            / max(
                max_slope_percent,
                1e-9,
            )
        ),
    )

    accumulation_score = min(
        1.0,
        np.log1p(
            max(
                accumulation,
                1,
            )
        )
        / np.log1p(1000),
    )

    depth_score = min(
        1.0,
        max(
            depression_depth,
            0.0,
        )
        / 2.0,
    )

    catchment_score = min(
        1.0,
        np.log1p(
            max(
                catchment_area_m2,
                1.0,
            )
        )
        / np.log1p(100_000.0),
    )

    raw = (
        0.20 * slope_score
        + 0.20 * accumulation_score
        + 0.30 * depth_score
        + 0.30 * catchment_score
    )

    # Strong channel penalty, but NOT a hard rejection.
    score = raw * (
        1.0
        - 0.80 * np.clip(
            channel_penalty,
            0.0,
            1.0,
        )
    )

    return float(
        np.clip(
            score,
            0.0,
            1.0,
        )
    )


def _find_best_candidate_cell(
    depression,
    dem: np.ndarray,
    slope: np.ndarray,
    accumulation: np.ndarray,
    channel_result,
    max_slope_percent: float,
) -> tuple[int, int, float] | None:
    """
    Find the best pond location INSIDE the depression.

    We do not use the depression centroid because the centroid
    may lie on a steep or channel-like raster cell.

    Priority:
        1. Prefer cells below max allowed slope.
        2. Prefer low slope.
        3. Prefer high accumulation.
        4. Prefer strong channel separation.
        5. Prefer lower elevation.
    """

    rows, cols = np.where(
        depression.mask
    )

    if len(rows) == 0:
        return None

    valid = (
        np.isfinite(
            dem[rows, cols]
        )
        & np.isfinite(
            slope[rows, cols]
        )
        & np.isfinite(
            accumulation[rows, cols]
        )
    )

    rows = rows[valid]
    cols = cols[valid]

    if len(rows) == 0:
        return None

    slopes = slope[rows, cols]
    accs = accumulation[rows, cols]
    elevations = dem[rows, cols]

    # First try cells satisfying the user's slope limit.
    acceptable = (
        slopes <= max_slope_percent
    )

    if np.any(acceptable):
        rows = rows[acceptable]
        cols = cols[acceptable]
        slopes = slopes[acceptable]
        accs = accs[acceptable]
        elevations = elevations[acceptable]

    # Normalize accumulation.
    log_acc = np.log1p(
        np.maximum(
            accs,
            0,
        )
    )

    if log_acc.max() > 0:
        acc_score = (
            log_acc
            / log_acc.max()
        )
    else:
        acc_score = np.zeros_like(
            log_acc,
            dtype=np.float64,
        )

    # Lower slope is better.
    slope_score = 1.0 - np.clip(
        slopes
        / max(
            max_slope_percent,
            1e-9,
        ),
        0.0,
        1.0,
    )

    # Lower elevation is preferred.
    elevation_range = (
        float(elevations.max())
        - float(elevations.min())
    )

    if elevation_range > 1e-9:
        low_elevation_score = (
            float(elevations.max())
            - elevations
        ) / elevation_range
    else:
        low_elevation_score = np.ones_like(
            elevations,
            dtype=np.float64,
        )

    # Channel separation.
    channel_scores = np.array(
        [
            channel_penalty_at(
                channel_result,
                int(row),
                int(col),
            )
            for row, col in zip(
                rows,
                cols,
            )
        ],
        dtype=np.float64,
    )

    channel_score = 1.0 - channel_scores

    combined = (
        0.40 * slope_score
        + 0.25 * acc_score
        + 0.20 * channel_score
        + 0.15 * low_elevation_score
    )

    best_index = int(
        np.argmax(combined)
    )

    return (
        int(rows[best_index]),
        int(cols[best_index]),
        float(combined[best_index]),
    )


@router.post(
    "/analyze",
    response_model=CatchmentV2Response,
)
async def analyze_catchment_v2(
    file: UploadFile = File(
        ...,
        description=(
            "Contour map in KML or KMZ format"
        ),
    ),
    grid_resolution_m: float = Query(
        10.0,
        gt=0,
        le=100,
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
    minimum_depression_depth_m: float = Query(
        0.15,
        gt=0,
        le=20,
    ),
    minimum_depression_area_m2: float = Query(
        100.0,
        gt=0,
    ),
    maximum_depression_depth_m: float = Query(
        20.0,
        gt=0,
        le=100,
    ),
    max_slope_percent: float = Query(
        8.0,
        gt=0,
        le=100,
    ),
    channel_accumulation_threshold: int | None = Query(
        None,
        ge=1,
    ),
    max_candidates: int = Query(
        10,
        ge=1,
        le=100,
    ),
) -> CatchmentV2Response:

    filename = file.filename or ""

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only .kml and .kmz files "
                "are supported"
            ),
        )

    try:
        # =====================================================
        # 1. Read KML/KMZ
        # =====================================================

        data = await file.read()

        if not data:
            raise ValueError(
                "Uploaded file is empty"
            )

        contours = parse_kml_bytes(
            data,
            filename,
        )

        if not contours:
            raise ValueError(
                "No valid contours found"
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

        dem = np.asarray(
            terrain.elevation_grid_m,
            dtype=np.float64,
        )

        slope_grid = np.asarray(
            terrain.slope_grid_percent,
            dtype=np.float64,
        )

        # =====================================================
        # 3. Detect depressions
        # =====================================================

        depressions = detect_depressions(
            dem,
            cell_size_m=terrain.grid_resolution_m,
            minimum_depth_m=minimum_depression_depth_m,
            minimum_area_m2=minimum_depression_area_m2,
            maximum_depth_m=maximum_depression_depth_m,
        )

        # =====================================================
        # 4. D8 flow
        # =====================================================

        flow_direction = calculate_d8_flow_direction(
            dem,
            cell_size_x_m=terrain.grid_resolution_m,
            cell_size_y_m=terrain.grid_resolution_m,
        )

        # =====================================================
        # 5. Flow accumulation
        # =====================================================

        accumulation = calculate_flow_accumulation(
            flow_direction,
        )

        # =====================================================
        # 6. Channel detection
        # =====================================================

        channel_result = detect_channels(
            accumulation,
            slope_grid,
            threshold=channel_accumulation_threshold,
        )

        transformer = Transformer.from_crs(
            terrain.crs,
            "EPSG:4326",
            always_xy=True,
        )

        depression_responses = []
        catchment_responses = []
        candidate_records = []

        depression_features = []
        catchment_features = []
        candidate_features = []

        slope_rejected_count = 0

        # =====================================================
        # 7. Process every depression
        # =====================================================

        for depression in depressions:

            # -------------------------------------------------
            # Depression geometry
            # -------------------------------------------------

            depression_geometry = _mask_to_geojson(
                terrain,
                depression.mask,
                transformer,
            )

            # -------------------------------------------------
            # Minimum elevation cell
            # -------------------------------------------------

            depression_rows, depression_cols = np.where(
                depression.mask
            )

            minimum_index = int(
                np.argmin(
                    dem[
                        depression_rows,
                        depression_cols,
                    ]
                )
            )

            minimum_row = int(
                depression_rows[
                    minimum_index
                ]
            )

            minimum_col = int(
                depression_cols[
                    minimum_index
                ]
            )

            minimum_x = (
                terrain.x_m[minimum_col]
                + terrain.grid_resolution_m / 2.0
            )

            minimum_y = (
                terrain.y_m[minimum_row]
                + terrain.grid_resolution_m / 2.0
            )

            minimum_lon, minimum_lat = (
                transformer.transform(
                    minimum_x,
                    minimum_y,
                )
            )

            depression_response = {
                "id": depression.id,
                "cell_count": depression.cell_count,
                "area_m2": depression.area_m2,
                "minimum_elevation_m": (
                    depression.minimum_elevation_m
                ),
                "spill_elevation_m": (
                    depression.spill_elevation_m
                ),
                "depth_m": depression.depth_m,
                "centroid_row": depression.centroid_row,
                "centroid_col": depression.centroid_col,
                "centroid_longitude": float(
                    minimum_lon
                ),
                "centroid_latitude": float(
                    minimum_lat
                ),
                "geometry": depression_geometry,
            }

            depression_responses.append(
                depression_response
            )

            depression_features.append(
                _feature(
                    depression_geometry,
                    {
                        "depression_id": depression.id,
                        "area_m2": depression.area_m2,
                        "depth_m": depression.depth_m,
                        "spill_elevation_m": (
                            depression.spill_elevation_m
                        ),
                    },
                )
            )

            # =================================================
            # Catchment
            # =================================================

            catchment_mask = (
                calculate_catchment_for_depression(
                    flow_direction,
                    depression.mask,
                )
            )

            catchment_stats = catchment_statistics(
                catchment_mask,
                terrain.grid_resolution_m,
            )

            catchment_geometry = _mask_to_geojson(
                terrain,
                catchment_mask,
                transformer,
            )

            catchment_response = {
                "depression_id": depression.id,
                "area_m2": float(
                    catchment_stats["area_m2"]
                ),
                "area_hectares": float(
                    catchment_stats["area_hectares"]
                ),
                "cell_count": int(
                    catchment_stats["cell_count"]
                ),
                "geometry": catchment_geometry,
            }

            catchment_responses.append(
                catchment_response
            )

            catchment_features.append(
                _feature(
                    catchment_geometry,
                    {
                        "depression_id": depression.id,
                        "area_m2": float(
                            catchment_stats["area_m2"]
                        ),
                        "area_hectares": float(
                            catchment_stats["area_hectares"]
                        ),
                    },
                )
            )

            # =================================================
            # Candidate cell
            # =================================================

            best_cell = _find_best_candidate_cell(
                depression=depression,
                dem=dem,
                slope=slope_grid,
                accumulation=accumulation,
                channel_result=channel_result,
                max_slope_percent=max_slope_percent,
            )

            if best_cell is None:
                slope_rejected_count += 1
                continue

            candidate_row, candidate_col, _ = (
                best_cell
            )

            candidate_elevation = float(
                dem[
                    candidate_row,
                    candidate_col,
                ]
            )

            candidate_slope = float(
                slope_grid[
                    candidate_row,
                    candidate_col,
                ]
            )

            candidate_accumulation = int(
                accumulation[
                    candidate_row,
                    candidate_col,
                ]
            )

            channel_penalty = float(
                channel_penalty_at(
                    channel_result,
                    candidate_row,
                    candidate_col,
                )
            )

            # -------------------------------------------------
            # We no longer hard-reject channel cells.
            #
            # Channels are penalized in the score instead.
            # This prevents candidate_count = 0 simply because
            # the channel detector is conservative/aggressive.
            # -------------------------------------------------

            candidate_x = (
                terrain.x_m[candidate_col]
                + terrain.grid_resolution_m / 2.0
            )

            candidate_y = (
                terrain.y_m[candidate_row]
                + terrain.grid_resolution_m / 2.0
            )

            candidate_lon, candidate_lat = (
                transformer.transform(
                    candidate_x,
                    candidate_y,
                )
            )

            score = _candidate_score(
                slope_percent=candidate_slope,
                max_slope_percent=max_slope_percent,
                accumulation=candidate_accumulation,
                depression_depth=depression.depth_m,
                channel_penalty=channel_penalty,
                catchment_area_m2=float(
                    catchment_stats["area_m2"]
                ),
            )

            reason = (
                "Depression with contributing "
                "catchment; candidate selected "
                "from lowest-slope cells inside "
                "the depression; channel penalty "
                "applied."
            )

            candidate_records.append(
                {
                    "row": candidate_row,
                    "col": candidate_col,
                    "longitude": float(candidate_lon),
                    "latitude": float(candidate_lat),
                    "elevation_m": candidate_elevation,
                    "slope_percent": candidate_slope,
                    "flow_accumulation": candidate_accumulation,
                    "depression_id": depression.id,
                    "depression_area_m2": (
                        depression.area_m2
                    ),
                    "depression_depth_m": (
                        depression.depth_m
                    ),
                    "spill_elevation_m": (
                        depression.spill_elevation_m
                    ),
                    "catchment_area_m2": float(
                        catchment_stats["area_m2"]
                    ),
                    "catchment_area_hectares": float(
                        catchment_stats[
                            "area_hectares"
                        ]
                    ),
                    "channel_score": channel_penalty,
                    "river_penalty": channel_penalty,
                    "score": score,
                    "reason": reason,
                }
            )

        # =====================================================
        # 8. Rank candidates
        # =====================================================

        candidate_records.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        candidate_records = candidate_records[
            :max_candidates
        ]

        for rank, candidate in enumerate(
            candidate_records,
            start=1,
        ):
            candidate["rank"] = rank

            candidate_features.append(
                _feature(
                    {
                        "type": "Point",
                        "coordinates": [
                            candidate["longitude"],
                            candidate["latitude"],
                        ],
                    },
                    {
                        "rank": rank,
                        "depression_id": (
                            candidate[
                                "depression_id"
                            ]
                        ),
                        "score": candidate["score"],
                        "slope_percent": (
                            candidate[
                                "slope_percent"
                            ]
                        ),
                        "flow_accumulation": (
                            candidate[
                                "flow_accumulation"
                            ]
                        ),
                        "catchment_area_hectares": (
                            candidate[
                                "catchment_area_hectares"
                            ]
                        ),
                        "river_penalty": (
                            candidate[
                                "river_penalty"
                            ]
                        ),
                    },
                )
            )

        # =====================================================
        # 9. Channel GeoJSON
        # =====================================================

        channel_geometry = _mask_to_geojson(
            terrain,
            channel_result.mask,
            transformer,
        )

        channel_feature = _feature(
            channel_geometry,
            {
                "threshold": channel_result.threshold,
            },
        )

        # =====================================================
        # 10. Terrain metadata
        # =====================================================

        height, width = dem.shape

        terrain_data = {
            "width": int(width),
            "height": int(height),
            "cell_count": int(dem.size),
            "resolution_m": float(
                terrain.grid_resolution_m
            ),
            "crs": str(terrain.crs),
        }

        # =====================================================
        # 11. Final response
        # =====================================================

        return CatchmentV2Response(
            status="success",
            message=(
                "Depression-preserving pond "
                "detection completed with "
                "individual catchment delineation "
                "and channel-aware pond ranking."
            ),
            algorithm=(
                "Depression-preserving D8 "
                "catchment analysis with "
                "channel-aware pond ranking"
            ),
            terrain=terrain_data,
            statistics={
                "depression_count": len(
                    depressions
                ),
                "accepted_depression_count": len(
                    depression_responses
                ),
                "river_excluded_count": 0,
                "slope_rejected_count": (
                    slope_rejected_count
                ),
                "candidate_count": len(
                    candidate_records
                ),
                "channel_cell_count": (
                    channel_result.channel_cell_count
                ),
                "channel_percentage": (
                    channel_result.channel_percentage
                ),
            },
            depressions=depression_responses,
            candidates=candidate_records,
            catchments=catchment_responses,
            channels={
                "threshold": channel_result.threshold,
                "channel_cell_count": (
                    channel_result.channel_cell_count
                ),
                "channel_percentage": (
                    channel_result.channel_percentage
                ),
            },
            map_data={
                "depressions": _feature_collection(
                    depression_features
                ),
                "catchments": _feature_collection(
                    catchment_features
                ),
                "candidates": _feature_collection(
                    candidate_features
                ),
                "channels": _feature_collection(
                    [channel_feature]
                ),
            },
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "V2 catchment analysis failed: "
                f"{exc}"
            ),
        ) from exc