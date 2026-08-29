import numpy as np

from app.services.accumulation_service import (
    calculate_flow_accumulation,
    accumulation_statistics,
)


def test_flow_accumulation_simple_eastward_flow():
    """
    Every cell flows east.

    Expected:

        1  2  3
        1  2  3
        1  2  3
    """

    flow = np.array(
        [
            [4, 4, 0],
            [4, 4, 0],
            [4, 4, 0],
        ],
        dtype=np.uint8,
    )

    accumulation = calculate_flow_accumulation(flow)

    expected = np.array(
        [
            [1, 2, 3],
            [1, 2, 3],
            [1, 2, 3],
        ],
        dtype=np.int64,
    )

    np.testing.assert_array_equal(
        accumulation,
        expected,
    )


def test_flow_accumulation_converging_flow():
    """
    Several cells converge toward the center/bottom.

             1
           ↘
        1 → 1 → 1
           ↘
             1
    """

    flow = np.array(
        [
            [8, 16, 16],
            [4, 8, 16],
            [4, 0, 32],
        ],
        dtype=np.uint8,
    )

    accumulation = calculate_flow_accumulation(flow)

    assert accumulation.shape == flow.shape

    assert np.all(accumulation >= 1)

    # At least one downstream cell should have
    # accumulation greater than one.
    assert np.max(accumulation) > 1


def test_accumulation_statistics():
    accumulation = np.array(
        [
            [1, 2, 3],
            [1, 2, 3],
        ],
        dtype=np.int64,
    )

    stats = accumulation_statistics(accumulation)

    assert stats["min"] == 1
    assert stats["max"] == 3
    assert stats["total_cells"] == 6
    assert stats["cells_gt_10"] == 0