import io

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_catchment_analyze_returns_hydrology_and_suitability():
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
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["status"] == "success"

    # Terrain
    assert data["terrain"]["contour_count"] == 3
    assert data["terrain"]["dem"]["cell_count"] > 0
    assert data["terrain"]["slope"]["max_percent"] >= 0

    # Hydrology
    assert "flow_accumulation" in data["hydrology"]
    assert data["hydrology"]["flow_accumulation"]["total_cells"] > 0

    # Suitability
    assert "suitability" in data
    assert data["suitability"]["candidate_count"] >= 0
    assert isinstance(data["suitability"]["candidates"], list)