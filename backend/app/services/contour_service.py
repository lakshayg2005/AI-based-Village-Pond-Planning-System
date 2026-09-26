from __future__ import annotations

import math

import numpy as np
from contourpy import LineType, contour_generator
from pyproj import Transformer
from scipy.ndimage import gaussian_filter

from .terrain_service import TerrainResult

# Contour spacings (metres) tried from finest to coarsest.
NICE_INTERVALS_M = (0.5, 1, 2, 5, 10, 20, 50, 100, 200)
TARGET_MAX_LEVELS = 15


def choose_interval(min_elevation: float, max_elevation: float) -> float:
    relief = max_elevation - min_elevation
    for interval in NICE_INTERVALS_M:
        if relief / interval <= TARGET_MAX_LEVELS:
            return float(interval)
    return float(NICE_INTERVALS_M[-1])


def dem_contours(terrain: TerrainResult) -> tuple[dict, float]:
    """Contour lines (GeoJSON, WGS84) derived from the DEM, for display.

    The DEM is lightly smoothed first: interpolated 30 m terrain data is
    blocky, and the smoothing only affects the drawn lines, never the
    hydrology.
    """
    elevation = np.asarray(terrain.elevation_grid_m, dtype=np.float64)
    smoothed = gaussian_filter(elevation, sigma=1.0, mode="nearest")

    interval = choose_interval(float(smoothed.min()), float(smoothed.max()))
    first = math.ceil(float(smoothed.min()) / interval) * interval
    levels = np.arange(first, float(smoothed.max()) + 1e-9, interval)

    half = terrain.grid_resolution_m / 2.0
    generator = contour_generator(
        x=terrain.x_m + half,
        y=terrain.y_m + half,
        z=smoothed,
        line_type=LineType.Separate,
    )
    to_lonlat = Transformer.from_crs(
        terrain.crs, "EPSG:4326", always_xy=True
    )

    features = []
    for level in levels:
        for line in generator.lines(float(level)):
            if len(line) < 4:
                continue
            lon, lat = to_lonlat.transform(line[:, 0], line[:, 1])
            coordinates = np.column_stack((lon, lat)).round(6).tolist()
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                    "properties": {"elevation": float(level)},
                }
            )

    return {"type": "FeatureCollection", "features": features}, interval
