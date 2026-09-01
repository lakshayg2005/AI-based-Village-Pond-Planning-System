from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class HydrologyDiagnostics:
    """Diagnostic information about a D8 flow-direction grid."""

    total_cells: int
    flowing_cells: int
    no_flow_cells: int

    boundary_cells: int
    boundary_no_flow_cells: int

    interior_cells: int
    interior_no_flow_cells: int

    accumulation_min: int
    accumulation_max: int
    accumulation_mean: float

    cells_with_accumulation_gt_10: int
    cells_with_accumulation_gt_100: int
    cells_with_accumulation_gt_1000: int


def analyze_hydrology(
    flow_direction: np.ndarray,
    accumulation: np.ndarray,
) -> HydrologyDiagnostics:
    """
    Analyze the quality and structure of a D8 flow-direction grid.

    This function is diagnostic only. It does not modify the
    flow-direction or accumulation arrays.
    """

    flow = np.asarray(flow_direction)

    if flow.ndim != 2:
        raise ValueError("Flow direction must be a 2-D array")

    accumulation = np.asarray(accumulation)

    if accumulation.ndim != 2:
        raise ValueError("Accumulation must be a 2-D array")

    if flow.shape != accumulation.shape:
        raise ValueError(
            "Flow direction and accumulation must have identical shapes"
        )

    rows, cols = flow.shape

    total_cells = int(flow.size)

    flowing_cells = int(np.count_nonzero(flow > 0))
    no_flow_cells = total_cells - flowing_cells

    # Boundary mask.
    boundary = np.zeros(flow.shape, dtype=bool)

    boundary[0, :] = True
    boundary[-1, :] = True
    boundary[:, 0] = True
    boundary[:, -1] = True

    boundary_cells = int(np.count_nonzero(boundary))
    boundary_no_flow_cells = int(
        np.count_nonzero(boundary & (flow == 0))
    )

    interior_cells = total_cells - boundary_cells
    interior_no_flow_cells = int(
        np.count_nonzero((~boundary) & (flow == 0))
    )

    if accumulation.size == 0:
        raise ValueError("Accumulation cannot be empty")

    accumulation_min = int(np.min(accumulation))
    accumulation_max = int(np.max(accumulation))
    accumulation_mean = float(np.mean(accumulation))

    cells_with_accumulation_gt_10 = int(
        np.count_nonzero(accumulation > 10)
    )

    cells_with_accumulation_gt_100 = int(
        np.count_nonzero(accumulation > 100)
    )

    cells_with_accumulation_gt_1000 = int(
        np.count_nonzero(accumulation > 1000)
    )

    return HydrologyDiagnostics(
        total_cells=total_cells,
        flowing_cells=flowing_cells,
        no_flow_cells=no_flow_cells,
        boundary_cells=boundary_cells,
        boundary_no_flow_cells=boundary_no_flow_cells,
        interior_cells=interior_cells,
        interior_no_flow_cells=interior_no_flow_cells,
        accumulation_min=accumulation_min,
        accumulation_max=accumulation_max,
        accumulation_mean=accumulation_mean,
        cells_with_accumulation_gt_10=cells_with_accumulation_gt_10,
        cells_with_accumulation_gt_100=cells_with_accumulation_gt_100,
        cells_with_accumulation_gt_1000=cells_with_accumulation_gt_1000,
    )