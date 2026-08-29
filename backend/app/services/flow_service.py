from __future__ import annotations

from dataclasses import dataclass
import heapq

import numpy as np


# D8 direction codes.
#
# The codes follow the common GIS convention:
#
#       NW  N  NE
#       128 1  2
#
#       W   X   E
#        64     4
#
#       SW  S  SE
#        32 16  8
#
# The DEM array is assumed to be indexed as [row, column],
# where row 0 corresponds to the minimum Y coordinate.
D8_OFFSETS = (
    (-1, 0, 1, 1.0),       # N
    (-1, 1, 2, np.sqrt(2)),    # NE
    (0, 1, 4, 1.0),        # E
    (1, 1, 8, np.sqrt(2)),     # SE
    (1, 0, 16, 1.0),       # S
    (1, -1, 32, np.sqrt(2)),   # SW
    (0, -1, 64, 1.0),      # W
    (-1, -1, 128, np.sqrt(2)), # NW
)


@dataclass(slots=True)
class FlowResult:
    """
    Result of hydrological preprocessing and D8 flow-direction analysis.
    """

    original_dem_m: np.ndarray
    filled_dem_m: np.ndarray
    flow_direction: np.ndarray

    filled_cell_count: int
    max_fill_depth_m: float

    valid_cell_count: int
    flowing_cell_count: int
    no_flow_cell_count: int


def _validate_dem(dem: np.ndarray) -> np.ndarray:
    """Validate and normalize the DEM to a 2-D float64 array."""

    array = np.asarray(dem, dtype=np.float64)

    if array.ndim != 2:
        raise ValueError("DEM must be a 2-D array")

    if array.shape[0] < 3 or array.shape[1] < 3:
        raise ValueError("DEM must contain at least 3 rows and 3 columns")

    if not np.isfinite(array).all():
        raise ValueError("DEM contains NaN or infinite values")

    return array


def fill_sinks(dem: np.ndarray) -> np.ndarray:
    """
    Fill depressions in a DEM using the Priority-Flood algorithm.

    Boundary cells are treated as drainage outlets. Interior cells lower
    than the lowest connected spill elevation are raised to that spill
    elevation.

    This function does not artificially raise terrain outside depressions.
    """

    source = _validate_dem(dem)
    filled = source.copy()

    rows, cols = source.shape
    visited = np.zeros(source.shape, dtype=bool)

    priority_queue: list[tuple[float, int, int]] = []

    def push_boundary(row: int, col: int) -> None:
        if visited[row, col]:
            return

        visited[row, col] = True
        elevation = float(filled[row, col])
        heapq.heappush(priority_queue, (elevation, row, col))

    # Add all boundary cells.
    for col in range(cols):
        push_boundary(0, col)
        push_boundary(rows - 1, col)

    for row in range(1, rows - 1):
        push_boundary(row, 0)
        push_boundary(row, cols - 1)

    while priority_queue:
        current_elevation, row, col = heapq.heappop(priority_queue)

        for dr, dc, _, _ in D8_OFFSETS:
            nr = row + dr
            nc = col + dc

            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            if visited[nr, nc]:
                continue

            visited[nr, nc] = True

            neighbor_elevation = float(filled[nr, nc])

            if neighbor_elevation < current_elevation:
                filled[nr, nc] = current_elevation
                neighbor_elevation = current_elevation

            heapq.heappush(
                priority_queue,
                (neighbor_elevation, nr, nc),
            )

    return filled


def calculate_d8_flow_direction(
    dem: np.ndarray,
    cell_size_x_m: float = 1.0,
    cell_size_y_m: float = 1.0,
) -> np.ndarray:
    """
    Calculate D8 flow direction.

    Each cell flows toward the neighboring cell with the steepest
    positive downhill gradient.

    Direction codes:

        N  = 1
        NE = 2
        E  = 4
        SE = 8
        S  = 16
        SW = 32
        W  = 64
        NW = 128

    A value of 0 means the cell has no strictly downhill neighbor.
    """

    elevation = _validate_dem(dem)

    if cell_size_x_m <= 0 or cell_size_y_m <= 0:
        raise ValueError("Cell dimensions must be greater than zero")

    rows, cols = elevation.shape

    flow_direction = np.zeros(
        elevation.shape,
        dtype=np.uint8,
    )

    for row in range(rows):
        for col in range(cols):
            current = elevation[row, col]

            best_gradient = 0.0
            best_direction = 0

            for dr, dc, direction_code, _ in D8_OFFSETS:

                nr = row + dr
                nc = col + dc

                if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                    continue

                neighbor = elevation[nr, nc]

                if neighbor >= current:
                    continue

                if dr != 0 and dc != 0:
                    distance = np.hypot(
                        cell_size_x_m,
                        cell_size_y_m,
                    )
                elif dr != 0:
                    distance = cell_size_y_m
                else:
                    distance = cell_size_x_m

                drop = current - neighbor
                gradient = drop / distance

                if gradient > best_gradient:
                    best_gradient = gradient
                    best_direction = direction_code

            flow_direction[row, col] = best_direction

    return flow_direction


def analyze_flow(
    dem: np.ndarray,
    cell_size_x_m: float = 1.0,
    cell_size_y_m: float = 1.0,
) -> FlowResult:
    """
    Run sink filling followed by D8 flow-direction calculation.
    """

    original = _validate_dem(dem)

    filled = fill_sinks(original)

    flow_direction = calculate_d8_flow_direction(
        filled,
        cell_size_x_m=cell_size_x_m,
        cell_size_y_m=cell_size_y_m,
    )

    fill_difference = filled - original

    filled_cells = int(np.count_nonzero(fill_difference > 1e-9))
    max_fill_depth = float(np.max(fill_difference))

    valid_cells = int(np.count_nonzero(np.isfinite(filled)))
    flowing_cells = int(np.count_nonzero(flow_direction > 0))
    no_flow_cells = valid_cells - flowing_cells

    return FlowResult(
        original_dem_m=original.astype(np.float32),
        filled_dem_m=filled.astype(np.float32),
        flow_direction=flow_direction,
        filled_cell_count=filled_cells,
        max_fill_depth_m=max_fill_depth,
        valid_cell_count=valid_cells,
        flowing_cell_count=flowing_cells,
        no_flow_cell_count=no_flow_cells,
    )