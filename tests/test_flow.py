import numpy as np

from app.services.flow_service import (
    calculate_d8_flow_direction,
    fill_sinks,
    analyze_flow,
)
def test_fill_sinks_fills_central_depression():
    dem = np.array(
        [
            [10, 10, 10, 10, 10],
            [10, 8, 8, 8, 10],
            [10, 8, 2, 8, 10],
            [10, 8, 8, 8, 10],
            [10, 10, 10, 10, 10],
        ],
        dtype=float,
    )

    filled = fill_sinks(dem)

    # The central depression must be filled up to the
    # lowest elevation at which water can escape the basin.
    assert filled[2, 2] == 10.0

    # The surrounding cells should also be raised if necessary
    # to create a continuous drainage surface.
    assert np.all(filled >= dem)

    # The original DEM must not be modified.
    assert dem[2, 2] == 2.0

    assert np.isfinite(filled).all()