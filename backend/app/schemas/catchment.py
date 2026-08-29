from __future__ import annotations

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


class HydrologyStats(BaseModel):
    dem_filled: bool
    filled_cell_count: int = Field(ge=0)
    max_fill_depth_m: float = Field(ge=0)
    valid_cell_count: int = Field(ge=0)
    flowing_cell_count: int = Field(ge=0)
    no_flow_cell_count: int = Field(ge=0)
    d8_algorithm: str


class CatchmentAnalyzeResponse(BaseModel):
    status: str
    message: str
    terrain: TerrainStats
    hydrology: HydrologyStats
