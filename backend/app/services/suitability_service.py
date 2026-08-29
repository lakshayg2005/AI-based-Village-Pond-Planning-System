from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class PondCandidate:
    """A potential pond outlet/location."""

    row: int
    col: int
    elevation_m: float
    slope_percent: float
    flow_accumulation: int
    score: float


def _normalize(values: np.ndarray) -> np.ndarray:
    """
    Min-max normalize values to [0, 1].

    Constant arrays are mapped to zero.
    """
    values = np.asarray(values, dtype=float)

    minimum = np.min(values)
    maximum = np.max(values)

    if maximum <= minimum:
        return np.zeros_like(values, dtype=float)

    return (values - minimum) / (maximum - minimum)


def calculate_candidate_score(
    slope_percent: np.ndarray,
    flow_accumulation: np.ndarray,
    max_slope_percent: float = 8.0,
) -> np.ndarray:
    """
    Calculate a preliminary pond suitability score.

    Higher flow accumulation is preferred.

    Lower slope is preferred, but slopes above max_slope_percent
    are considered unsuitable.

    Score:

        60% flow accumulation
        40% slope suitability

    This is a screening score, not an engineering design score.
    """

    slope = np.asarray(slope_percent, dtype=float)
    accumulation = np.asarray(flow_accumulation, dtype=float)

    if slope.shape != accumulation.shape:
        raise ValueError(
            "Slope and flow accumulation must have the same shape"
        )

    if max_slope_percent <= 0:
        raise ValueError(
            "max_slope_percent must be greater than zero"
        )

    # Log transformation prevents extremely large accumulation
    # values from dominating the entire score.
    accumulation_score = _normalize(
        np.log1p(np.maximum(accumulation, 0))
    )

    # Flat terrain receives the highest slope score.
    # max_slope_percent receives zero.
    slope_score = 1.0 - np.clip(
        slope / max_slope_percent,
        0.0,
        1.0,
    )

    score = (
        0.60 * accumulation_score
        + 0.40 * slope_score
    )

    # Anything above the configured slope threshold is unsuitable.
    score = np.where(
        slope <= max_slope_percent,
        score,
        0.0,
    )

    return score


def detect_pond_candidates(
    elevation_m: np.ndarray,
    slope_percent: np.ndarray,
    flow_accumulation: np.ndarray,
    *,
    max_slope_percent: float = 8.0,
    minimum_accumulation: int = 10,
    max_candidates: int = 10,
    minimum_distance_cells: int = 10,
) -> list[PondCandidate]:
    """
    Detect and rank preliminary pond candidates.

    Candidates must satisfy:

        slope <= max_slope_percent
        flow accumulation >= minimum_accumulation

    Non-maximum suppression is then applied so that several
    candidates do not appear immediately next to each other.
    """

    elevation = np.asarray(elevation_m, dtype=float)
    slope = np.asarray(slope_percent, dtype=float)
    accumulation = np.asarray(flow_accumulation)

    if not (
        elevation.shape
        == slope.shape
        == accumulation.shape
    ):
        raise ValueError(
            "Elevation, slope, and flow accumulation "
            "must have identical shapes"
        )

    if max_candidates <= 0:
        raise ValueError("max_candidates must be greater than zero")

    if minimum_accumulation < 1:
        raise ValueError(
            "minimum_accumulation must be at least 1"
        )

    if minimum_distance_cells < 0:
        raise ValueError(
            "minimum_distance_cells cannot be negative"
        )

    score = calculate_candidate_score(
        slope,
        accumulation,
        max_slope_percent=max_slope_percent,
    )

    eligible = (
        (slope <= max_slope_percent)
        & (accumulation >= minimum_accumulation)
        & np.isfinite(elevation)
        & np.isfinite(slope)
        & np.isfinite(accumulation)
        & (score > 0)
    )

    rows, cols = elevation.shape

    candidate_indices = np.argwhere(eligible)

    # Sort by score from highest to lowest.
    candidate_indices = sorted(
        candidate_indices.tolist(),
        key=lambda rc: score[rc[0], rc[1]],
        reverse=True,
    )

    selected: list[PondCandidate] = []

    for row, col in candidate_indices:

        # Non-maximum suppression:
        # don't select candidates too close to an already
        # selected candidate.
        too_close = False

        for existing in selected:
            distance = np.hypot(
                row - existing.row,
                col - existing.col,
            )

            if distance < minimum_distance_cells:
                too_close = True
                break

        if too_close:
            continue

        selected.append(
            PondCandidate(
                row=int(row),
                col=int(col),
                elevation_m=float(elevation[row, col]),
                slope_percent=float(slope[row, col]),
                flow_accumulation=int(accumulation[row, col]),
                score=float(score[row, col]),
            )
        )

        if len(selected) >= max_candidates:
            break

    return selected