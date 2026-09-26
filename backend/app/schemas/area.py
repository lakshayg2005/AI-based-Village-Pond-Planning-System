from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .catchment import (
    CatchmentAnalysis,
    FlowAccumulationStats,
    HydrologyStats,
    SuitabilityResponse,
)


class AreaAnalyzeRequest(BaseModel):
    polygon: dict[str, Any] | list[list[float]] = Field(
        ...,
        description=(
            "GeoJSON Polygon/Feature, or a list of [longitude, latitude] "
            "points, describing the land area to analyse"
        ),
    )
    rainfall_mm: float | None = Field(
        None,
        gt=0,
        le=12000,
        description="Annual rainfall override; looked up automatically if omitted",
    )
    runoff_coefficient: float | None = Field(
        None,
        gt=0,
        le=1,
        description="Fraction of rain that runs off; estimated from slope if omitted",
    )
    max_slope_percent: float = Field(8.0, gt=0, le=100)
    minimum_accumulation: int = Field(10, ge=1)
    max_candidates: int = Field(10, ge=1, le=50)
    minimum_distance_cells: int = Field(10, ge=0)


class AreaAnalyzeResponse(BaseModel):
    status: str
    message: str
    area: dict[str, Any]
    terrain: dict[str, Any]
    rainfall: dict[str, Any]
    summary: dict[str, Any]
    timings: dict[str, float] | None = None
    hydrology: HydrologyStats
    accumulation: FlowAccumulationStats
    suitability: SuitabilityResponse
    analysis: CatchmentAnalysis
    map_data: dict[str, Any]
