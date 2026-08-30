from __future__ import annotations

import os
import tempfile
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator
import xml.etree.ElementTree as ET


@dataclass(slots=True)
class ContourFeature:
    elevation_m: float
    coordinates: list[tuple[float, float]]  # (longitude, latitude)


_KML_NS = "http://www.opengis.net/kml/2.2"
_TAG_PLACEMARK = f"{{{_KML_NS}}}Placemark"
_TAG_NAME = f"{{{_KML_NS}}}name"
_TAG_COORDINATES = f"{{{_KML_NS}}}coordinates"
_TAG_LINESTRING = f"{{{_KML_NS}}}LineString"


def _numeric_elevation(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.strip())
    return float(match.group()) if match else None


def _parse_coordinates(text: str | None) -> list[tuple[float, float]]:
    if not text:
        return []
    result: list[tuple[float, float]] = []
    for token in text.split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        if -180 <= lon <= 180 and -90 <= lat <= 90:
            result.append((lon, lat))
    return result


def _iter_xml_stream(stream: BinaryIO) -> Iterator[ContourFeature]:
    context = ET.iterparse(stream, events=("end",))
    for _, element in context:
        if element.tag != _TAG_PLACEMARK:
            continue

        # Only process Placemarks that actually contain a LineString.
        line_strings = element.findall(f".//{_TAG_LINESTRING}")
        elevation = _numeric_elevation(element.findtext(_TAG_NAME))
        if elevation is None:
            element.clear()
            continue

        for line in line_strings:
            coords = _parse_coordinates(line.findtext(_TAG_COORDINATES))
            if len(coords) >= 2:
                yield ContourFeature(elevation_m=elevation, coordinates=coords)
        element.clear()


def _open_kml(path: str | Path):
    path = Path(path)
    if path.suffix.lower() == ".kmz":
        archive = zipfile.ZipFile(path)
        names = [n for n in archive.namelist() if n.lower().endswith(".kml")]
        if not names:
            archive.close()
            raise ValueError("KMZ archive does not contain a KML file")
        return archive, archive.open(names[0], "r")
    return None, path.open("rb")


def parse_kml_file(path: str | Path) -> list[ContourFeature]:
    """Parse KML/KMZ LineString contours without loading the whole XML tree."""
    archive, stream = _open_kml(path)
    try:
        return list(_iter_xml_stream(stream))
    finally:
        stream.close()
        if archive is not None:
            archive.close()


def parse_kml_bytes(
    data: bytes,
    filename: str = "contours.kml",
) -> list[ContourFeature]:
    """Parse uploaded KML/KMZ bytes safely on Windows."""

    suffix = ".kmz" if filename.lower().endswith(".kmz") else ".kml"

    fd, temp_path = tempfile.mkstemp(suffix=suffix)

    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(data)

        # The temporary file is now closed before another
        # function attempts to open it.
        return parse_kml_file(temp_path)

    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass