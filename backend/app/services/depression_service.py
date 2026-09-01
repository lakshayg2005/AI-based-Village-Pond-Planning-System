from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(slots=True)
class Depression:
    id: int
    mask: np.ndarray
    cell_count: int
    area_m2: float
    minimum_elevation_m: float
    spill_elevation_m: float
    depth_m: float
    centroid_row: int
    centroid_col: int


def _validate_dem(
    dem: np.ndarray,
) -> np.ndarray:

    array = np.asarray(
        dem,
        dtype=np.float64,
    )

    if array.ndim != 2:
        raise ValueError(
            "DEM must be a 2-D array"
        )

    if (
        array.shape[0] < 3
        or array.shape[1] < 3
    ):
        raise ValueError(
            "DEM must contain at least "
            "3 rows and 3 columns"
        )

    if not np.isfinite(array).all():
        raise ValueError(
            "DEM contains NaN or infinite values"
        )

    return array


def _boundary_mask(
    mask: np.ndarray,
) -> np.ndarray:

    eroded = ndimage.binary_erosion(
        mask,
        structure=np.ones(
            (3, 3),
            dtype=bool,
        ),
        border_value=0,
    )

    return (
        mask
        & ~eroded
    )


def _find_spill_elevation(
    dem: np.ndarray,
    component: np.ndarray,
) -> float:
    """
    Estimate spill elevation from cells immediately outside
    the depression boundary.

    Important:
    the depression's own cells are NOT used as spill candidates.
    """

    boundary = _boundary_mask(
        component
    )

    rows, cols = np.where(
        boundary
    )

    if len(rows) == 0:
        return float(
            np.max(
                dem[component]
            )
        )

    outside_values = []

    for row, col in zip(
        rows,
        cols,
    ):

        r0 = max(
            0,
            row - 1,
        )

        r1 = min(
            dem.shape[0],
            row + 2,
        )

        c0 = max(
            0,
            col - 1,
        )

        c1 = min(
            dem.shape[1],
            col + 2,
        )

        neighborhood_mask = np.ones(
            (r1 - r0, c1 - c0),
            dtype=bool,
        )

        local_component = component[
            r0:r1,
            c0:c1,
        ]

        outside = (
            neighborhood_mask
            & ~local_component
        )

        values = dem[
            r0:r1,
            c0:c1,
        ][outside]

        values = values[
            np.isfinite(values)
        ]

        if values.size:
            outside_values.extend(
                values.tolist()
            )

    if not outside_values:
        return float(
            np.max(
                dem[component]
            )
        )

    # Use the lowest outside elevation that would act as a
    # plausible escape/spill point.
    return float(
        np.min(
            outside_values
        )
    )


def detect_depressions(
    dem: np.ndarray,
    cell_size_m: float,
    minimum_depth_m: float = 0.15,
    minimum_area_m2: float = 100.0,
    maximum_depth_m: float = 20.0,
) -> list[Depression]:

    elevation = _validate_dem(
        dem
    )

    if cell_size_m <= 0:
        raise ValueError(
            "cell_size_m must be greater than zero"
        )

    rows, cols = elevation.shape

    # ---------------------------------------------------------
    # 1. Local minima
    # ---------------------------------------------------------

    minimum_filter = ndimage.minimum_filter(
        elevation,
        size=3,
        mode="nearest",
    )

    minima = np.isclose(
        elevation,
        minimum_filter,
        atol=1e-9,
    )

    # Boundary cells cannot be pond locations.
    minima[0, :] = False
    minima[-1, :] = False
    minima[:, 0] = False
    minima[:, -1] = False

    # ---------------------------------------------------------
    # 2. Label local minima
    # ---------------------------------------------------------

    labels, count = ndimage.label(
        minima,
        structure=np.ones(
            (3, 3),
            dtype=np.uint8,
        ),
    )

    depressions: list[Depression] = []

    # ---------------------------------------------------------
    # 3. Process every minimum
    # ---------------------------------------------------------

    for label_id in range(
        1,
        count + 1,
    ):

        seed = (
            labels == label_id
        )

        if not np.any(seed):
            continue

        seed_rows, seed_cols = np.where(
            seed
        )

        minimum_elevation = float(
            elevation[seed].min()
        )

        # -----------------------------------------------------
        # Estimate spill from a local ring.
        # -----------------------------------------------------

        r0 = max(
            1,
            int(seed_rows.min()) - 4,
        )

        r1 = min(
            rows - 1,
            int(seed_rows.max()) + 5,
        )

        c0 = max(
            1,
            int(seed_cols.min()) - 4,
        )

        c1 = min(
            cols - 1,
            int(seed_cols.max()) + 5,
        )

        local = elevation[
            r0:r1,
            c0:c1,
        ]

        if local.size == 0:
            continue

        # Do not use an excessively low percentile. The previous
        # 20th percentile could underestimate the true spill.
        local_spill = float(
            np.percentile(
                local,
                50,
            )
        )

        boundary_spill = (
            _find_spill_elevation(
                elevation,
                seed,
            )
        )

        spill = max(
            local_spill,
            boundary_spill,
        )

        depth = (
            spill
            - minimum_elevation
        )

        if depth < minimum_depth_m:
            continue

        if depth > maximum_depth_m:
            continue

        # -----------------------------------------------------
        # Build basin.
        # -----------------------------------------------------

        threshold = (
            minimum_elevation
            + depth
        )

        basin = (
            elevation <= threshold + 1e-9
        )

        basin_labels, basin_count = (
            ndimage.label(
                basin,
                structure=np.ones(
                    (3, 3),
                    dtype=np.uint8,
                ),
            )
        )

        selected = None

        for basin_id in range(
            1,
            basin_count + 1,
        ):

            component = (
                basin_labels == basin_id
            )

            if np.any(
                component & seed
            ):
                selected = component
                break

        if selected is None:
            continue

        # Never allow a depression to touch the raster boundary.
        if (
            np.any(
                selected[0, :]
            )
            or np.any(
                selected[-1, :]
            )
            or np.any(
                selected[:, 0]
            )
            or np.any(
                selected[:, -1]
            )
        ):
            continue

        cell_count = int(
            selected.sum()
        )

        area_m2 = (
            cell_count
            * cell_size_m
            * cell_size_m
        )

        if area_m2 < minimum_area_m2:
            continue

        selected_rows, selected_cols = np.where(
            selected
        )

        centroid_row = int(
            round(
                float(
                    selected_rows.mean()
                )
            )
        )

        centroid_col = int(
            round(
                float(
                    selected_cols.mean()
                )
            )
        )

        depressions.append(
            Depression(
                id=len(depressions) + 1,
                mask=selected,
                cell_count=cell_count,
                area_m2=area_m2,
                minimum_elevation_m=minimum_elevation,
                spill_elevation_m=spill,
                depth_m=depth,
                centroid_row=centroid_row,
                centroid_col=centroid_col,
            )
        )

    # ---------------------------------------------------------
    # Remove highly overlapping/nested depressions.
    # ---------------------------------------------------------

    depressions.sort(
        key=lambda item: (
            -item.depth_m,
            -item.area_m2,
        )
    )

    accepted: list[Depression] = []

    occupied = np.zeros(
        elevation.shape,
        dtype=bool,
    )

    for depression in depressions:

        overlap = (
            depression.mask
            & occupied
        )

        overlap_ratio = (
            float(
                overlap.sum()
            )
            / max(
                depression.cell_count,
                1,
            )
        )

        if overlap_ratio > 0.80:
            continue

        accepted.append(
            depression
        )

        occupied |= (
            depression.mask
        )

    # ---------------------------------------------------------
    # Re-number.
    # ---------------------------------------------------------

    for index, depression in enumerate(
        accepted,
        start=1,
    ):
        depression.id = index

    return accepted