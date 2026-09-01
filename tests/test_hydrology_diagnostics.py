import numpy as np

from app.services.hydrology_diagnostics_service import (
    analyze_hydrology,
)


def test_hydrology_diagnostics_counts_boundary_and_interior_no_flow():
    flow = np.array(
        [
            [0, 4, 0],
            [4, 4, 0],
            [0, 0, 0],
        ],
        dtype=np.uint8,
    )

    accumulation = np.array(
        [
            [1, 2, 3],
            [1, 4, 5],
            [1, 1, 1],
        ],
        dtype=np.int64,
    )

    result = analyze_hydrology(
        flow,
        accumulation,
    )

    assert result.total_cells == 9
    assert result.flowing_cells == 3
    assert result.no_flow_cells == 6

    assert result.boundary_cells == 8
    assert result.boundary_no_flow_cells == 6

    assert result.interior_cells == 1
    assert result.interior_no_flow_cells == 0


def test_hydrology_diagnostics_accumulation_statistics():
    flow = np.array(
        [
            [4, 4, 0],
            [4, 4, 0],
            [4, 4, 0],
        ],
        dtype=np.uint8,
    )

    accumulation = np.array(
        [
            [1, 2, 11],
            [1, 20, 101],
            [1, 200, 1001],
        ],
        dtype=np.int64,
    )

    result = analyze_hydrology(
        flow,
        accumulation,
    )

    assert result.accumulation_min == 1
    assert result.accumulation_max == 1001

    assert result.cells_with_accumulation_gt_10 == 5
    assert result.cells_with_accumulation_gt_100 == 3
    assert result.cells_with_accumulation_gt_1000 == 1


def test_hydrology_diagnostics_rejects_shape_mismatch():
    flow = np.zeros((3, 3), dtype=np.uint8)
    accumulation = np.ones((4, 4), dtype=np.int64)

    try:
        analyze_hydrology(flow, accumulation)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "identical shapes" in str(exc)