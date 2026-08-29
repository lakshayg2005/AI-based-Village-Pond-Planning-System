from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from pyproj import CRS, Transformer
from scipy.interpolate import RegularGridInterpolator, griddata
from shapely.geometry import LineString

from .kml_parser import ContourFeature


@dataclass(slots=True)
class TerrainResult:
    elevation_grid_m: np.ndarray
    x_m: np.ndarray
    y_m: np.ndarray
    crs: str
    bounds_lonlat: tuple[float, float, float, float]
    min_elevation_m: float
    max_elevation_m: float
    grid_resolution_m: float
    sample_count: int
    valid_cell_count: int
    slope_grid_percent: np.ndarray
    slope_min_percent: float
    slope_max_percent: float
    slope_mean_percent: float
    contour_rmse_m: float
    contour_max_abs_error_m: float
    contour_p95_abs_error_m: float


def _utm_crs(lons: np.ndarray, lats: np.ndarray) -> CRS:
    lon = float(np.mean(lons))
    lat = float(np.mean(lats))
    zone = int(math.floor((lon + 180.0) / 6.0) + 1)
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def _sample_contour_points(
    contours: list[ContourFeature],
    transformer: Transformer,
    spacing_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []

    for contour in contours:
        line = LineString(contour.coordinates)
        projected = LineString([transformer.transform(x, y) for x, y in line.coords])
        length = projected.length
        if length == 0:
            continue

        distances = np.arange(0.0, length, spacing_m)
        if len(distances) == 0 or not np.isclose(distances[-1], length):
            distances = np.append(distances, length)

        for distance in distances:
            point = projected.interpolate(float(distance))
            xs.append(point.x)
            ys.append(point.y)
            zs.append(contour.elevation_m)

    return np.asarray(xs), np.asarray(ys), np.asarray(zs)


def _calculate_slope_percent(
    elevation_grid_m: np.ndarray,
    resolution_m: float,
) -> np.ndarray:
    """Calculate slope from a regular metric DEM as percent rise."""
    if elevation_grid_m.shape[0] < 2 or elevation_grid_m.shape[1] < 2:
        raise ValueError("DEM must contain at least 2 rows and 2 columns to calculate slope")

    # np.gradient returns dZ/dy and dZ/dx for a 2-D array. Because the grid is in
    # UTM metres, one metre in x/y has the same unit and slope is dimensionless.
    dz_dy, dz_dx = np.gradient(elevation_grid_m.astype(np.float64), resolution_m, resolution_m)
    slope_percent = np.hypot(dz_dx, dz_dy) * 100.0
    return slope_percent.astype(np.float32)


def _validate_against_contours(
    x_m: np.ndarray,
    y_m: np.ndarray,
    elevation_grid_m: np.ndarray,
    sample_x: np.ndarray,
    sample_y: np.ndarray,
    sample_z: np.ndarray,
) -> tuple[float, float, float]:
    """Measure how closely the reconstructed DEM reproduces contour elevations."""
    interpolator = RegularGridInterpolator(
        (y_m, x_m),
        elevation_grid_m,
        method="linear",
        bounds_error=False,
        fill_value=np.nan,
    )
    predicted = interpolator(np.column_stack((sample_y, sample_x)))
    errors = predicted - sample_z
    finite = np.isfinite(errors)
    if not np.any(finite):
        raise ValueError("Could not validate reconstructed DEM against contour samples")

    errors = errors[finite]
    abs_errors = np.abs(errors)
    return (
        float(np.sqrt(np.mean(errors**2))),
        float(np.max(abs_errors)),
        float(np.percentile(abs_errors, 95)),
    )


def reconstruct_dem(
    contours: list[ContourFeature],
    grid_resolution_m: float = 10.0,
    sample_spacing_m: float | None = None,
    method: str = "linear",
) -> TerrainResult:
    """Create a local metric DEM from elevation-tagged contour lines.

    The output is intentionally an in-memory terrain representation. A later DEM
    provider (OpenZenith/GeoTIFF) can feed the same hydrology services.
    """
    if not contours:
        raise ValueError("No valid LineString contours were found in the uploaded file")
    if grid_resolution_m <= 0:
        raise ValueError("grid_resolution_m must be greater than zero")
    if method not in {"linear", "nearest"}:
        raise ValueError("method must be 'linear' or 'nearest'")

    all_lon = np.fromiter((p[0] for c in contours for p in c.coordinates), dtype=float)
    all_lat = np.fromiter((p[1] for c in contours for p in c.coordinates), dtype=float)
    if len(all_lon) < 2:
        raise ValueError("Not enough contour coordinates to reconstruct terrain")

    crs = _utm_crs(all_lon, all_lat)
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    spacing = sample_spacing_m or max(grid_resolution_m / 2.0, 1.0)
    sample_x, sample_y, sample_z = _sample_contour_points(contours, transformer, spacing)
    if len(sample_z) < 3:
        raise ValueError("Not enough contour samples to interpolate terrain")

    # Remove exact duplicate XY samples; duplicate points can make Qhull/griddata
    # unstable while adding no information.
    points = np.column_stack((sample_x, sample_y))
    _, unique_idx = np.unique(points, axis=0, return_index=True)
    unique_idx.sort()
    sample_x = sample_x[unique_idx]
    sample_y = sample_y[unique_idx]
    sample_z = sample_z[unique_idx]

    min_x, max_x = float(sample_x.min()), float(sample_x.max())
    min_y, max_y = float(sample_y.min()), float(sample_y.max())
    x = np.arange(min_x, max_x + grid_resolution_m, grid_resolution_m)
    y = np.arange(min_y, max_y + grid_resolution_m, grid_resolution_m)
    grid_x, grid_y = np.meshgrid(x, y)

    grid_z = griddata(
        np.column_stack((sample_x, sample_y)),
        sample_z,
        (grid_x, grid_y),
        method=method,
    )

    # Linear interpolation is undefined outside the convex hull. Fill only those
    # cells with nearest-neighbour values so the DEM is complete without claiming
    # unsupported extrapolation from a distant model.
    if method == "linear" and np.isnan(grid_z).any():
        nearest = griddata(
            np.column_stack((sample_x, sample_y)),
            sample_z,
            (grid_x, grid_y),
            method="nearest",
        )
        grid_z = np.where(np.isnan(grid_z), nearest, grid_z)

    if not np.isfinite(grid_z).all():
        raise ValueError("DEM interpolation produced invalid cells")

    slope_grid = _calculate_slope_percent(grid_z, grid_resolution_m)
    contour_rmse, contour_max_error, contour_p95_error = _validate_against_contours(
        x, y, grid_z, sample_x, sample_y, sample_z
    )

    min_lon, min_lat = inverse.transform(min_x, min_y)
    max_lon, max_lat = inverse.transform(max_x, max_y)

    return TerrainResult(
        elevation_grid_m=grid_z.astype(np.float32),
        x_m=x,
        y_m=y,
        crs=crs.to_string(),
        bounds_lonlat=(float(min_lon), float(min_lat), float(max_lon), float(max_lat)),
        min_elevation_m=float(np.nanmin(grid_z)),
        max_elevation_m=float(np.nanmax(grid_z)),
        grid_resolution_m=float(grid_resolution_m),
        sample_count=int(len(sample_z)),
        valid_cell_count=int(np.count_nonzero(np.isfinite(grid_z))),
        slope_grid_percent=slope_grid,
        slope_min_percent=float(np.nanmin(slope_grid)),
        slope_max_percent=float(np.nanmax(slope_grid)),
        slope_mean_percent=float(np.nanmean(slope_grid)),
        contour_rmse_m=contour_rmse,
        contour_max_abs_error_m=contour_max_error,
        contour_p95_abs_error_m=contour_p95_error,
    )
