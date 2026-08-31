from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TerrainBounds(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class DEMStats(BaseModel):
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    cell_count: int = Field(ge=1)
    valid_cell_count: int = Field(ge=1)
    nan_percentage: float = Field(ge=0, le=100)
    resolution_m: float = Field(gt=0)
    crs: str


class SlopeStats(BaseModel):
    min_percent: float = Field(ge=0)
    max_percent: float = Field(ge=0)
    mean_percent: float = Field(ge=0)


class ContourValidation(BaseModel):
    rmse_m: float = Field(ge=0)
    max_abs_error_m: float = Field(ge=0)
    p95_abs_error_m: float = Field(ge=0)


class TerrainStats(BaseModel):
    contour_count: int = Field(ge=1)
    elevation_levels: int = Field(ge=1)
    min_elevation_m: float
    max_elevation_m: float
    grid_resolution_m: float = Field(gt=0)
    contour_sample_count: int = Field(ge=1)
    valid_dem_cells: int = Field(ge=1)
    crs: str
    bounds: TerrainBounds
    dem: DEMStats
    slope: SlopeStats
    contour_validation: ContourValidation


class FlowAccumulationStats(BaseModel):
    min: int = Field(ge=1)
    max: int = Field(ge=1)
    mean: float = Field(ge=1)
    total_cells: int = Field(ge=1)
    cells_gt_10: int = Field(ge=0)
    cells_gt_100: int = Field(ge=0)
    cells_gt_1000: int = Field(ge=0)


class PondCandidateResponse(BaseModel):
    rank: int = Field(ge=1)
    row: int = Field(ge=0)
    col: int = Field(ge=0)

    longitude: float
    latitude: float

    elevation_m: float
    slope_percent: float
    flow_accumulation: int = Field(ge=1)
    score: float = Field(ge=0, le=1)


class HydrologyStats(BaseModel):
    dem_filled: bool
    filled_cell_count: int = Field(ge=0)
    max_fill_depth_m: float = Field(ge=0)
    valid_cell_count: int = Field(ge=0)
    flowing_cell_count: int = Field(ge=0)
    no_flow_cell_count: int = Field(ge=0)
    d8_algorithm: str
    flow_accumulation: FlowAccumulationStats
    pond_candidates: list[PondCandidateResponse]


class CatchmentResponse(BaseModel):
    rank: int = Field(ge=1)
    area_m2: float = Field(ge=0)
    area_hectares: float = Field(ge=0)
    cell_count: int = Field(ge=0)
    geometry: dict[str, Any]


class SuitabilityStats(BaseModel):
    max_slope_percent: float = Field(gt=0)
    minimum_accumulation: int = Field(ge=1)
    candidate_count: int = Field(ge=0)

class SuitabilityResponse(BaseModel):
    max_slope_percent: float = Field(gt=0)
    minimum_accumulation: int = Field(ge=1)
    candidate_count: int = Field(ge=0)
    candidates: list[PondCandidateResponse] 


class CatchmentAnalysis(BaseModel):
    suitability: SuitabilityStats
    candidates: list[PondCandidateResponse]
    catchments: list[CatchmentResponse]


class CatchmentAnalyzeResponse(BaseModel):
    status: str
    message: str
    terrain: TerrainStats
    hydrology: HydrologyStats
    accumulation: FlowAccumulationStats
    suitability: SuitabilityResponse
    analysis: CatchmentAnalysis
    map_data: dict[str, Any]