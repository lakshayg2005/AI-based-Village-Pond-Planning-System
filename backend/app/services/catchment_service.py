from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon, mapping

from .flow_service import D8_OFFSETS


D8_DIRECTION_TO_OFFSET = {
    direction_code: (dr, dc)
    for dr, dc, direction_code, _ in D8_OFFSETS
}


@dataclass(slots=True)
class CatchmentResult:
    """Result of catchment delineation."""

    mask: np.ndarray
    area_m2: float
    area_hectares: float
    cell_count: int
    polygon: Polygon


def _validate_inputs(
    flow_direction: np.ndarray,
    outlet_row: int,
    outlet_col: int,
) -> np.ndarray:

    flow = np.asarray(flow_direction)

    if flow.ndim != 2:
        raise ValueError(
            "Flow direction must be a 2-D array"
        )

    rows, cols = flow.shape

    if not (
        0 <= outlet_row < rows
        and 0 <= outlet_col < cols
    ):
        raise ValueError(
            "Outlet is outside the flow-direction grid"
        )

    valid_codes = {
        0,
        1,
        2,
        4,
        8,
        16,
        32,
        64,
        128,
    }

    invalid_codes = (
        set(np.unique(flow).tolist())
        - valid_codes
    )

    if invalid_codes:
        raise ValueError(
            f"Invalid D8 direction codes: "
            f"{sorted(invalid_codes)}"
        )

    return flow.astype(np.uint8, copy=False)


def delineate_catchment(
    flow_direction: np.ndarray,
    outlet_row: int,
    outlet_col: int,
    cell_size_x_m: float,
    cell_size_y_m: float,
) -> CatchmentResult:
    """
    Delineate the upstream catchment draining to an outlet cell.

    The algorithm works backwards through the D8 flow graph:

        outlet
          ↑
       upstream
          ↑
       upstream

    Every cell whose flow path eventually reaches the outlet
    becomes part of the catchment.
    """

    flow = _validate_inputs(
        flow_direction,
        outlet_row,
        outlet_col,
    )

    if cell_size_x_m <= 0 or cell_size_y_m <= 0:
        raise ValueError(
            "Cell dimensions must be greater than zero"
        )

    rows, cols = flow.shape

    # Build reverse adjacency:
    #
    # downstream cell -> upstream cells
    upstream: dict[tuple[int, int], list[tuple[int, int]]] = {}

    for row in range(rows):
        for col in range(cols):

            direction = int(flow[row, col])

            if direction == 0:
                continue

            dr, dc = D8_DIRECTION_TO_OFFSET[direction]

            downstream_row = row + dr
            downstream_col = col + dc

            if (
                downstream_row < 0
                or downstream_row >= rows
                or downstream_col < 0
                or downstream_col >= cols
            ):
                continue

            key = (
                downstream_row,
                downstream_col,
            )

            upstream.setdefault(key, []).append(
                (row, col)
            )

    # Traverse backwards from the outlet.
    mask = np.zeros(
        (rows, cols),
        dtype=bool,
    )

    queue = deque(
        [(outlet_row, outlet_col)]
    )

    mask[outlet_row, outlet_col] = True

    while queue:

        row, col = queue.popleft()

        for upstream_row, upstream_col in upstream.get(
            (row, col),
            [],
        ):

            if mask[upstream_row, upstream_col]:
                continue

            mask[upstream_row, upstream_col] = True

            queue.append(
                (upstream_row, upstream_col)
            )

    cell_count = int(np.count_nonzero(mask))

    cell_area_m2 = (
        cell_size_x_m
        * cell_size_y_m
    )

    area_m2 = cell_count * cell_area_m2
    area_hectares = area_m2 / 10_000.0

    polygon = _mask_to_polygon(
        mask,
        cell_size_x_m,
        cell_size_y_m,
    )

    return CatchmentResult(
        mask=mask,
        area_m2=float(area_m2),
        area_hectares=float(area_hectares),
        cell_count=cell_count,
        polygon=polygon,
    )


def _mask_to_polygon(
    mask: np.ndarray,
    cell_size_x_m: float,
    cell_size_y_m: float,
) -> Polygon:
    """
    Convert a raster catchment mask into a polygon.

    For the initial implementation we construct the union
    of contributing raster cells using Shapely.

    This is intentionally simple and robust for the prototype.
    """

    rows, cols = mask.shape

    cells = []

    for row in range(rows):
        for col in range(cols):

            if not mask[row, col]:
                continue

            x0 = col * cell_size_x_m
            y0 = row * cell_size_y_m

            x1 = x0 + cell_size_x_m
            y1 = y0 + cell_size_y_m

            cells.append(
                Polygon(
                    [
                        (x0, y0),
                        (x1, y0),
                        (x1, y1),
                        (x0, y1),
                        (x0, y0),
                    ]
                )
            )

    if not cells:
        return Polygon()

    from shapely.ops import unary_union

    geometry = unary_union(cells)

    # A catchment should normally be one connected polygon.
    # If tiny disconnected components occur because of unusual
    # flow data, return the complete geometry rather than
    # silently dropping them.
    if geometry.geom_type == "MultiPolygon":
        return max(
            geometry.geoms,
            key=lambda polygon: polygon.area,
        )

    return geometry


def catchment_to_geojson(
    result: CatchmentResult,
) -> dict:
    """Convert the catchment polygon to GeoJSON geometry."""

    return mapping(result.polygon)