from __future__ import annotations

from typing import Any

from pyproj import Transformer


def transform_geojson_to_wgs84(
    geometry: dict[str, Any],
    source_crs: str,
) -> dict[str, Any]:
    """
    Transform a GeoJSON geometry from source_crs to EPSG:4326.

    Output coordinates are always:
        [longitude, latitude]
    """

    transformer = Transformer.from_crs(
        source_crs,
        "EPSG:4326",
        always_xy=True,
    )

    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if not geometry_type or coordinates is None:
        raise ValueError("Invalid GeoJSON geometry")

    def transform_coords(coords):
        if isinstance(coords[0], (int, float)):
            x, y = coords[:2]
            lon, lat = transformer.transform(x, y)
            return [float(lon), float(lat)]

        return [transform_coords(item) for item in coords]

    return {
        "type": geometry_type,
        "coordinates": transform_coords(coordinates),
    }


def make_feature(
    geometry: dict[str, Any],
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": properties or {},
        "geometry": geometry,
    }


def make_feature_collection(
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": features,
    }
