from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(slots=True)
class ChannelResult:
    mask: np.ndarray
    threshold: int
    channel_cell_count: int
    channel_percentage: float
    normalized_score: np.ndarray


def _validate(
    accumulation: np.ndarray,
    slope_percent: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:

    acc = np.asarray(
        accumulation,
        dtype=np.float64,
    )

    slope = np.asarray(
        slope_percent,
        dtype=np.float64,
    )

    if acc.ndim != 2:
        raise ValueError(
            "Accumulation must be 2-D"
        )

    if slope.shape != acc.shape:
        raise ValueError(
            "Slope and accumulation grids "
            "must have identical shapes"
        )

    return acc, slope


def detect_channels(
    accumulation: np.ndarray,
    slope_percent: np.ndarray,
    threshold: int | None = None,
    minimum_slope_percent: float = 0.05,
) -> ChannelResult:

    acc, slope = _validate(
        accumulation,
        slope_percent,
    )

    positive = acc[
        np.isfinite(acc)
        & (acc > 0)
    ]

    if positive.size == 0:
        threshold_value = 1

    elif threshold is not None:
        threshold_value = max(
            int(threshold),
            1,
        )

    else:
        # Use a high percentile rather than an extremely
        # low threshold. This keeps the channel mask focused
        # on the strongest drainage corridors.
        threshold_value = max(
            int(
                np.percentile(
                    positive,
                    95,
                )
            ),
            10,
        )

    high_acc = (
        acc >= threshold_value
    )

    sloped = (
        slope >= minimum_slope_percent
    )

    candidate = (
        high_acc
        & sloped
    )

    # ---------------------------------------------------------
    # Connectivity.
    # ---------------------------------------------------------

    labels, count = ndimage.label(
        candidate,
        structure=np.ones(
            (3, 3),
            dtype=np.uint8,
        ),
    )

    channel = np.zeros_like(
        candidate,
        dtype=bool,
    )

    for label_id in range(
        1,
        count + 1,
    ):
        component = (
            labels == label_id
        )

        component_size = int(
            component.sum()
        )

        # Require a meaningful connected corridor.
        if component_size >= 5:
            channel |= component

    # ---------------------------------------------------------
    # Local channel density.
    # ---------------------------------------------------------

    density = ndimage.uniform_filter(
        channel.astype(np.float64),
        size=5,
        mode="nearest",
    )

    # ---------------------------------------------------------
    # Accumulation intensity.
    # ---------------------------------------------------------

    log_acc = np.log1p(
        np.maximum(
            acc,
            0,
        )
    )

    finite_log = log_acc[
        np.isfinite(log_acc)
    ]

    if finite_log.size:
        # Robust normalization prevents one extreme cell from
        # dominating the entire score.
        scale = float(
            np.percentile(
                finite_log,
                99,
            )
        )

        if scale > 0:
            acc_score = np.clip(
                log_acc / scale,
                0.0,
                1.0,
            )
        else:
            acc_score = np.zeros_like(
                acc,
                dtype=np.float64,
            )

    else:
        acc_score = np.zeros_like(
            acc,
            dtype=np.float64,
        )

    # ---------------------------------------------------------
    # Continuous channel likelihood.
    #
    # This is deliberately NOT identical to channel.mask.
    # A candidate can therefore be close to a channel without
    # being automatically rejected.
    # ---------------------------------------------------------

    normalized_score = np.clip(
        0.65 * acc_score
        + 0.35 * density,
        0.0,
        1.0,
    )

    total_cells = channel.size

    percentage = (
        100.0
        * float(channel.sum())
        / max(
            total_cells,
            1,
        )
    )

    return ChannelResult(
        mask=channel,
        threshold=threshold_value,
        channel_cell_count=int(
            channel.sum()
        ),
        channel_percentage=percentage,
        normalized_score=normalized_score,
    )


def channel_penalty_at(
    channel_result: ChannelResult,
    row: int,
    col: int,
    radius: int = 2,
) -> float:

    rows, cols = (
        channel_result.mask.shape
    )

    if not (
        0 <= row < rows
        and 0 <= col < cols
    ):
        return 0.0

    r0 = max(
        0,
        row - radius,
    )

    r1 = min(
        rows,
        row + radius + 1,
    )

    c0 = max(
        0,
        col - radius,
    )

    c1 = min(
        cols,
        col + radius + 1,
    )

    local_score = (
        channel_result
        .normalized_score[
            r0:r1,
            c0:c1,
        ]
    )

    if local_score.size == 0:
        return 0.0

    return float(
        np.clip(
            np.max(local_score),
            0.0,
            1.0,
        )
    )