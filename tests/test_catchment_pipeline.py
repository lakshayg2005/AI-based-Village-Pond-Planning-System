import io

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_full_catchment_pipeline():

    kml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>

        <Placemark>
          <name>100m contour</name>
          <ExtendedData>
            <Data name="elevation">
              <value>100</value>
            </Data>
          </ExtendedData>
          <LineString>
            <coordinates>
              81.10,21.20,0
              81.11,21.20,0
              81.12,21.20,0
              81.13,21.20,0
            </coordinates>
          </LineString>
        </Placemark>

        <Placemark>
          <name>110m contour</name>
          <ExtendedData>
            <Data name="elevation">
              <value>110</value>
            </Data>
          </ExtendedData>
          <LineString>
            <coordinates>
              81.10,21.21,0
              81.11,21.21,0
              81.12,21.21,0
              81.13,21.21,0
            </coordinates>
          </LineString>
        </Placemark>

        <Placemark>
          <name>120m contour</name>
          <ExtendedData>
            <Data name="elevation">
              <value>120</value>
            </Data>
          </ExtendedData>
          <LineString>
            <coordinates>
              81.10,21.22,0
              81.11,21.22,0
              81.12,21.22,0
              81.13,21.22,0
            </coordinates>
          </LineString>
        </Placemark>

      </Document>
    </kml>
    """

    response = client.post(
        "/api/catchment/analyze",
        files={
            "file": (
                "test.kml",
                io.BytesIO(kml),
                "application/vnd.google-earth.kml+xml",
            )
        },
        params={
            "minimum_accumulation": 1,
            "max_candidates": 5,
            "minimum_distance_cells": 1,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "success"

    assert "terrain" in data
    assert "hydrology" in data
    assert "accumulation" in data
    assert "analysis" in data

    assert data["accumulation"]["total_cells"] > 0

    assert (
        data["accumulation"]["max"]
        >= data["accumulation"]["min"]
    )

    assert (
        data["analysis"]["suitability"]["candidate_count"]
        == len(data["analysis"]["candidates"])
    )

    assert (
        len(data["analysis"]["catchments"])
        == len(data["analysis"]["candidates"])
    )

    for candidate in data["analysis"]["candidates"]:
        assert -180 <= candidate["longitude"] <= 180
        assert -90 <= candidate["latitude"] <= 90
        assert candidate["flow_accumulation"] >= 1
        assert 0 <= candidate["score"] <= 1

    for catchment in data["analysis"]["catchments"]:
        assert catchment["area_m2"] >= 0
        assert catchment["area_hectares"] >= 0
        assert catchment["cell_count"] >= 0
        assert "type" in catchment["geometry"]