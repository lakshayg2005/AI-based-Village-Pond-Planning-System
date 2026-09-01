from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class V2Candidate(BaseModel):
    rank: int = Field(ge=1)

    row: int = Field(ge=0)
    col: int = Field(ge=0)

    longitude: float
    latitude: float

    elevation_m: float
    slope_percent: float

    flow_accumulation: int = Field(ge=1)

    depression_id: int = Field(ge=1)

    depression_area_m2: float = Field(ge=0)
    depression_depth_m: float = Field(ge=0)

    spill_elevation_m: float

    catchment_area_m2: float = Field(ge=0)
    catchment_area_hectares: float = Field(ge=0)

    channel_score: float = Field(ge=0, le=1)
    river_penalty: float = Field(ge=0, le=1)

    score: float = Field(ge=0, le=1)

    reason: str


class V2Depression(BaseModel):
    id: int = Field(ge=1)

    cell_count: int = Field(ge=1)
    area_m2: float = Field(ge=0)

    minimum_elevation_m: float
    spill_elevation_m: float

    depth_m: float = Field(ge=0)

    centroid_row: int = Field(ge=0)
    centroid_col: int = Field(ge=0)

    centroid_longitude: float
    centroid_latitude: float

    geometry: dict[str, Any]


class V2Catchment(BaseModel):
    depression_id: int = Field(ge=1)

    area_m2: float = Field(ge=0)
    area_hectares: float = Field(ge=0)

    cell_count: int = Field(ge=0)

    geometry: dict[str, Any]


class V2ChannelStats(BaseModel):
    threshold: int = Field(ge=1)

    channel_cell_count: int = Field(ge=0)

    channel_percentage: float = Field(
        ge=0,
        le=100,
    )


class V2Statistics(BaseModel):
    depression_count: int = Field(ge=0)

    accepted_depression_count: int = Field(ge=0)

    river_excluded_count: int = Field(ge=0)

    candidate_count: int = Field(ge=0)


class CatchmentV2Response(BaseModel):
    status: str

    message: str

    algorithm: str

    terrain: dict[str, Any]

    statistics: V2Statistics

    depressions: list[V2Depression]

    candidates: list[V2Candidate]

    catchments: list[V2Catchment]

    channels: V2ChannelStats

    map_data: dict[str, Any]