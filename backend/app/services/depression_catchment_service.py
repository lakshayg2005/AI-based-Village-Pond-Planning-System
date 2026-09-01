from __future__ import annotations

from collections import deque

import numpy as np

from .flow_service import D8_OFFSETS


DIRECTION_TO_OFFSET = {
    direction: (dr, dc)
    for dr, dc, direction, _ in D8_OFFSETS
}


def _validate_flow(
    flow_direction: np.ndarray,
) -> np.ndarray:

    flow = np.asarray(
        flow_direction,
        dtype=np.uint8,
    )

    if flow.ndim != 2:
        raise ValueError(
            "Flow direction must be 2-D"
        )

    return flow


def calculate_catchment_for_depression(
    flow_direction: np.ndarray,
    depression_mask: np.ndarray,
) -> np.ndarray:
    """
    Return all cells whose D8 downstream path reaches
    the supplied depression.

    The algorithm builds a reverse flow graph and performs
    BFS starting from every cell belonging to the depression.
    """

    flow = _validate_flow(
        flow_direction
    )

    target = np.asarray(
        depression_mask,
        dtype=bool,
    )

    if flow.shape != target.shape:
        raise ValueError(
            "Flow and depression masks "
            "must have identical shapes"
        )

    rows, cols = flow.shape

    # ---------------------------------------------------------
    # Reverse graph.
    #
    # If:
    #
    #   A -> B
    #
    # then B has A as an upstream cell.
    # ---------------------------------------------------------

    upstream: dict[
        tuple[int, int],
        list[tuple[int, int]],
    ] = {}

    for row in range(rows):
        for col in range(cols):

            direction = int(
                flow[row, col]
            )

            if direction == 0:
                continue

            offset = DIRECTION_TO_OFFSET.get(
                direction
            )

            if offset is None:
                continue

            dr, dc = offset

            nr = row + dr
            nc = col + dc

            if (
                nr < 0
                or nr >= rows
                or nc < 0
                or nc >= cols
            ):
                continue

            upstream.setdefault(
                (nr, nc),
                [],
            ).append(
                (row, col)
            )

    # ---------------------------------------------------------
    # BFS backwards from depression.
    # ---------------------------------------------------------

    catchment = target.copy()

    initial_cells = np.where(
        target
    )

    queue = deque(
        zip(
            initial_cells[0],
            initial_cells[1],
        )
    )

    while queue:

        row, col = queue.popleft()

        for (
            upstream_row,
            upstream_col,
        ) in upstream.get(
            (row, col),
            [],
        ):

            if catchment[
                upstream_row,
                upstream_col,
            ]:
                continue

            catchment[
                upstream_row,
                upstream_col,
            ] = True

            queue.append(
                (
                    upstream_row,
                    upstream_col,
                )
            )

    return catchment


def catchment_statistics(
    catchment: np.ndarray,
    cell_size_m: float,
) -> dict[str, float | int]:

    mask = np.asarray(
        catchment,
        dtype=bool,
    )

    if cell_size_m <= 0:
        raise ValueError(
            "cell_size_m must be greater than zero"
        )

    cells = int(
        mask.sum()
    )

    area_m2 = (
        cells
        * cell_size_m
        * cell_size_m
    )

    return {
        "cell_count": cells,
        "area_m2": float(area_m2),
        "area_hectares": float(
            area_m2 / 10_000.0
        ),
    }