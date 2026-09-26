from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import httpx

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
YEARS_TO_AVERAGE = 5

# Used only when the rainfall service is unreachable; flagged in the response.
FALLBACK_ANNUAL_MM = 1000.0


class RainfallError(RuntimeError):
    """Rainfall could not be retrieved."""


@dataclass(slots=True)
class RainfallResult:
    annual_mm: float
    monthly_mm: list[float]  # 12 values, January..December
    source: str
    measured: bool
    years: str


def manual_rainfall(annual_mm: float) -> RainfallResult:
    return RainfallResult(
        annual_mm=float(annual_mm),
        monthly_mm=[float(annual_mm) / 12.0] * 12,
        source="User supplied",
        measured=False,
        years="n/a",
    )


def fallback_rainfall() -> RainfallResult:
    result = manual_rainfall(FALLBACK_ANNUAL_MM)
    result.source = (
        "Default value (rainfall service unavailable); "
        "please enter rainfall manually"
    )
    return result


@lru_cache(maxsize=256)
def _fetch(lat_key: float, lon_key: float, year0: int, year1: int):
    response = httpx.get(
        ARCHIVE_URL,
        params={
            "latitude": lat_key,
            "longitude": lon_key,
            "start_date": f"{year0}-01-01",
            "end_date": f"{year1}-12-31",
            "daily": "precipitation_sum",
            "timezone": "UTC",
        },
        timeout=20.0,
    )
    response.raise_for_status()
    daily = response.json()["daily"]
    return daily["time"], daily["precipitation_sum"]


def get_annual_rainfall(latitude: float, longitude: float) -> RainfallResult:
    """Average yearly rainfall (mm) at a point from the last full years of
    ERA5 reanalysis via Open-Meteo (free, no API key).

    Coordinates are rounded to 0.25 deg, ERA5's native resolution, which also
    makes the result cacheable for nearby areas.
    """
    year1 = date.today().year - 1
    year0 = year1 - YEARS_TO_AVERAGE + 1
    lat_key = round(latitude * 4) / 4
    lon_key = round(longitude * 4) / 4

    try:
        times, values = _fetch(lat_key, lon_key, year0, year1)
    except Exception as exc:
        raise RainfallError(f"Rainfall lookup failed: {exc}") from exc

    month_totals = [0.0] * 12
    valid_days = 0
    for day, value in zip(times, values):
        if value is None:
            continue
        month_totals[int(day[5:7]) - 1] += float(value)
        valid_days += 1

    if valid_days < 365:
        raise RainfallError("Rainfall lookup returned too little data")

    years = year1 - year0 + 1
    monthly = [total / years for total in month_totals]

    return RainfallResult(
        annual_mm=float(sum(monthly)),
        monthly_mm=monthly,
        source="Open-Meteo ERA5 reanalysis",
        measured=True,
        years=f"{year0}-{year1}",
    )
