# Stage 1 — Catchment Analysis Milestone 2

This milestone extends the KML terrain pipeline with DEM validation and slope calculation.

## Endpoint

`POST /api/catchment/analyze`

Upload a `.kml` or `.kmz` contour file as multipart form field `file`.

Optional query parameters:

- `grid_resolution_m` — DEM cell size in metres; default `10`
- `sample_spacing_m` — contour sampling spacing in metres; defaults to half the DEM resolution
- `interpolation_method` — `linear` or `nearest`; default `linear`

## Pipeline

```text
KML/KMZ
  ↓
parse elevation-tagged LineStrings
  ↓
project WGS84 → local UTM
  ↓
sample contour elevations
  ↓
interpolate regular DEM
  ↓
validate DEM against contour samples
  ↓
calculate slope (% rise)
  ↓
return terrain statistics
```

## Validation metrics

The API reports:

- contour count and unique elevation levels
- DEM width/height/cell count
- DEM resolution and CRS
- valid/NaN cell statistics
- elevation range
- slope minimum/maximum/mean
- contour reconstruction RMSE and maximum absolute error

The uploaded sample is used as test data only. Its observed values are not hard-coded into the implementation.

## Testing

From the project root:

```powershell
python -m pip install -r requirements-stage1.txt
python -m pip install pytest
python -m pytest -q
```

`pytest.ini` permanently adds `backend` to the test import path, so setting `PYTHONPATH` manually is no longer necessary.

## Existing FastAPI application

The supplied `backend/app/main_integration.py` shows the one router integration line required in the existing application:

```python
from app.api.routes.catchment import router as catchment_router
app.include_router(catchment_router)
```

Do not replace existing authentication, CORS, or database setup when integrating this router.

## Next milestone

After DEM validation is confirmed, implement the hydrological stage incrementally:

```text
DEM
 ↓
sink filling
 ↓
D8 flow direction
 ↓
flow accumulation
 ↓
pond candidate detection
 ↓
catchment delineation
```
