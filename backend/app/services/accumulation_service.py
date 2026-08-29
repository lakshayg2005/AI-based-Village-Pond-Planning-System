from __future__ import annotations

import numpy as np

from .flow_service import D8_OFFSETS


# Map D8 direction code -> row/column offset.
D8_DIRECTION_TO_OFFSET = {
    direction_code: (dr, dc)
    for dr, dc, direction_code, _ in D8_OFFSETS
}


def _validate_flow_direction(flow_direction: np.ndarray) -> np.ndarray:
    """Validate a D8 flow-direction grid."""

    flow = np.asarray(flow_direction)

    if flow.ndim != 2:
        raise ValueError("Flow direction must be a 2-D array")

    valid_codes = {0, 1, 2, 4, 8, 16, 32, 64, 128}

    invalid_codes = set(np.unique(flow).tolist()) - valid_codes

    if invalid_codes:
        raise ValueError(
            f"Invalid D8 direction codes: {sorted(invalid_codes)}"
        )

    return flow.astype(np.uint8, copy=False)


def calculate_flow_accumulation(
    flow_direction: np.ndarray,
) -> np.ndarray:
    """
    Calculate D8 flow accumulation.

    Each cell initially contributes one unit of flow
    (representing itself).

    If several upstream cells eventually drain into a cell,
    their contributions are accumulated there.

    Returns
    -------
    np.ndarray
        Integer accumulation grid.

    Example:

        1  1  1
        1  2  1
        1  3  1

    means the bottom-center cell receives flow from
    two upstream cells in addition to itself.
    """

    flow = _validate_flow_direction(flow_direction)

    rows, cols = flow.shape

    accumulation = np.ones(
        (rows, cols),
        dtype=np.int64,
    )

    # Number of incoming flow connections for each cell.
    indegree = np.zeros(
        (rows, cols),
        dtype=np.int32,
    )

    # Build the flow graph.
    for row in range(rows):
        for col in range(cols):

            direction = int(flow[row, col])

            # Direction 0 means no outgoing flow.
            if direction == 0:
                continue

            dr, dc = D8_DIRECTION_TO_OFFSET[direction]

            nr = row + dr
            nc = col + dc

            # Ignore flow that exits the raster.
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            indegree[nr, nc] += 1

    # Start with cells that have no upstream neighbors.
    queue = [
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if indegree[row, col] == 0
    ]

    head = 0

    processed = 0

    while head < len(queue):

        row, col = queue[head]
        head += 1

        processed += 1

        direction = int(flow[row, col])

        if direction == 0:
            continue

        dr, dc = D8_DIRECTION_TO_OFFSET[direction]

        nr = row + dr
        nc = col + dc

        if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
            continue

        accumulation[nr, nc] += accumulation[row, col]

        indegree[nr, nc] -= 1

        if indegree[nr, nc] == 0:
            queue.append((nr, nc))

    # A properly conditioned D8 grid should be acyclic.
    # If cells remain unprocessed, the flow graph contains
    # a cycle, which indicates invalid flow-direction data.
    if processed < rows * cols:
        raise ValueError(
            "Flow-direction grid contains a cycle. "
            "Check sink filling and D8 flow directions."
        )

    return accumulation


def accumulation_statistics(
    accumulation: np.ndarray,
) -> dict[str, float | int]:
    """Return basic statistics for a flow-accumulation grid."""

    values = np.asarray(accumulation)

    if values.ndim != 2:
        raise ValueError("Accumulation must be a 2-D array")

    return {
        "min": int(values.min()),
        "max": int(values.max()),
        "mean": float(values.mean()),
        "total_cells": int(values.size),
        "cells_gt_10": int(np.count_nonzero(values > 10)),
        "cells_gt_100": int(np.count_nonzero(values > 100)),
        "cells_gt_1000": int(np.count_nonzero(values > 1000)),
    }