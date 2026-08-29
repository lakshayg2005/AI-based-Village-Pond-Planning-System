import numpy as np

from app.services.suitability_service import (
    calculate_candidate_score,
    detect_pond_candidates,
)


def test_candidate_score_prefers_high_accumulation():
    slope = np.array(
        [
            [2.0, 2.0],
            [2.0, 2.0],
        ]
    )

    accumulation = np.array(
        [
            [10, 100],
            [20, 1000],
        ]
    )

    score = calculate_candidate_score(
        slope,
        accumulation,
        max_slope_percent=8.0,
    )

    assert score.shape == slope.shape
    assert score[1, 1] > score[0, 0]


def test_steep_slope_is_rejected():
    slope = np.array(
        [
            [2.0, 20.0],
            [3.0, 30.0],
        ]
    )

    accumulation = np.array(
        [
            [100, 1000],
            [200, 2000],
        ]
    )

    score = calculate_candidate_score(
        slope,
        accumulation,
        max_slope_percent=8.0,
    )

    assert score[0, 1] == 0.0
    assert score[1, 1] == 0.0

    assert score[0, 0] > 0
    assert score[1, 0] > 0


def test_candidate_detection_filters_low_accumulation():
    elevation = np.array(
        [
            [100, 99, 98],
            [99, 98, 97],
            [98, 97, 96],
        ],
        dtype=float,
    )

    slope = np.full(
        (3, 3),
        3.0,
        dtype=float,
    )

    accumulation = np.array(
        [
            [1, 2, 3],
            [2, 5, 4],
            [3, 4, 100],
        ],
        dtype=int,
    )

    candidates = detect_pond_candidates(
        elevation,
        slope,
        accumulation,
        minimum_accumulation=10,
        max_candidates=5,
        minimum_distance_cells=0,
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.row == 2
    assert candidate.col == 2
    assert candidate.flow_accumulation == 100


def test_candidate_detection_applies_distance_suppression():
    elevation = np.array(
        [
            [100, 99, 98, 97, 96],
            [99, 98, 97, 96, 95],
            [98, 97, 96, 95, 94],
            [97, 96, 95, 94, 93],
            [96, 95, 94, 93, 92],
        ],
        dtype=float,
    )

    slope = np.full(
        (5, 5),
        3.0,
        dtype=float,
    )

    accumulation = np.ones(
        (5, 5),
        dtype=int,
    )

    accumulation[2, 2] = 100
    accumulation[2, 3] = 90

    candidates = detect_pond_candidates(
        elevation,
        slope,
        accumulation,
        minimum_accumulation=10,
        max_candidates=10,
        minimum_distance_cells=3,
    )

    # The two strong cells are close enough that only the
    # strongest one should survive.
    assert len(candidates) == 1
    assert candidates[0].row == 2
    assert candidates[0].col == 2  