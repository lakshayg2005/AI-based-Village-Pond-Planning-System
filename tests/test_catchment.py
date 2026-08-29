import numpy as np

from app.services.catchment_service import (
    delineate_catchment,
)


def test_simple_eastward_catchment():
    """
    Every cell in the bottom row flows east toward the outlet.

        X  X  X
        X  X  X
        →  →  outlet

    Only the bottom row drains to the selected outlet.
    """

    flow = np.array(
        [
            [0, 0, 0],
            [0, 0, 0],
            [4, 4, 0],
        ],
        dtype=np.uint8,
    )

    result = delineate_catchment(
        flow_direction=flow,
        outlet_row=2,
        outlet_col=2,
        cell_size_x_m=10,
        cell_size_y_m=10,
    )

    assert result.mask.shape == flow.shape

    assert result.mask[2, 2]

    # Bottom row contains three contributing cells.
    assert result.cell_count == 3

    assert result.area_m2 == 300.0
    assert result.area_hectares == 0.03

    assert result.polygon.area == 300.0