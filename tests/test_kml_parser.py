from pathlib import Path

from app.services.kml_parser import parse_kml_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KML_PATH = PROJECT_ROOT / "contours_1m.kml"


def test_parse_sample_kml():
    contours = parse_kml_file(KML_PATH)

    assert len(contours) == 1355
    elevations = sorted({round(c.elevation_m, 6) for c in contours})
    assert len(elevations) == 32
    assert elevations[0] == 267.0
    assert elevations[-1] == 298.0
    assert all(c.coordinates for c in contours)
