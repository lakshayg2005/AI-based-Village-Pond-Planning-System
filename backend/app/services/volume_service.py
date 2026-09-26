from __future__ import annotations

from .rainfall_service import RainfallResult

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

DEFAULT_RUNOFF_COEFFICIENT = 0.4
DEFAULT_POND_DEPTH_M = 3.0
# Farm-pond rule of thumb: pond surface is a few percent of its catchment.
POND_AREA_FRACTION = 0.03


def suggest_runoff_coefficient(mean_slope_percent: float) -> float:
    """Steeper catchments shed more of the rain; flat ones soak more in."""
    if mean_slope_percent < 2:
        return 0.25
    if mean_slope_percent < 6:
        return 0.35
    if mean_slope_percent < 12:
        return 0.45
    return 0.55


def estimate_water_volume(
    catchment_area_m2: float,
    rainfall: RainfallResult,
    runoff_coefficient: float,
    pond_depth_m: float = DEFAULT_POND_DEPTH_M,
) -> dict:
    """Expected yearly runoff reaching the pond and the pond sized for it.

    runoff (m^3) = C x rainfall depth (m) x catchment area (m^2)
    """
    annual_runoff_m3 = (
        runoff_coefficient * (rainfall.annual_mm / 1000.0) * catchment_area_m2
    )

    monthly_runoff = [
        runoff_coefficient * (mm / 1000.0) * catchment_area_m2
        for mm in rainfall.monthly_mm
    ]

    pond_area_m2 = POND_AREA_FRACTION * catchment_area_m2
    # A pond is not a box: assume a tapered profile holding ~half of that.
    storage_capacity_m3 = pond_area_m2 * pond_depth_m * 0.5

    return {
        "annual_runoff_m3": float(annual_runoff_m3),
        "annual_runoff_litres": float(annual_runoff_m3 * 1000.0),
        "runoff_coefficient": float(runoff_coefficient),
        "annual_rainfall_mm": float(rainfall.annual_mm),
        "monthly_runoff_m3": {
            month: float(value)
            for month, value in zip(MONTHS, monthly_runoff)
        },
        "recommended_pond": {
            "surface_area_m2": float(pond_area_m2),
            "depth_m": float(pond_depth_m),
            "storage_capacity_m3": float(storage_capacity_m3),
        },
        "times_filled_per_year": float(
            annual_runoff_m3 / storage_capacity_m3
            if storage_capacity_m3 > 0
            else 0.0
        ),
    }
