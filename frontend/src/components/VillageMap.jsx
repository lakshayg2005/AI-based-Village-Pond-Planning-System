import {
  APIProvider,
  Map,
  Polygon,
  Polyline,
  Marker,
  MapControl,
  ControlPosition,
  useMap,
} from "@vis.gl/react-google-maps";

import {
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";

import MapToolbar from "./MapToolbar";
import FileUpload from "./FileUpload";
import CandidateList from "./CandidateList";
import AnalysisPanel from "./AnalysisPanel";

import {
  analyzeContourFileByVersion,
  CATCHMENT_VERSION,
} from "../services/catchmentAnalysisService";

import "./VillageMap.css";

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const DEFAULT_CENTER = {
  lat: 21.1904,
  lng: 81.2849,
};

/* =========================================================
   SEARCH BOX
   ========================================================= */

function SearchBox() {
  const map = useMap();
  const containerRef = useRef(null);

  useEffect(() => {
    if (!map || !containerRef.current) {
      return;
    }

    if (!window.google?.maps?.places) {
      console.warn("Google Places library is not loaded.");
      return;
    }

    containerRef.current.innerHTML = "";

    const searchElement =
      new google.maps.places.PlaceAutocompleteElement();

    searchElement.placeholder =
      "Search for a village, city, place...";

    searchElement.style.width = "400px";
    searchElement.style.height = "48px";

    const handleSelect = async (event) => {
      try {
        if (!event?.placePrediction) {
          return;
        }

        const place =
          event.placePrediction.toPlace();

        await place.fetchFields({
          fields: [
            "displayName",
            "location",
            "viewport",
          ],
        });

        if (!place.location) {
          return;
        }

        if (place.viewport) {
          map.fitBounds(place.viewport);
        } else {
          map.panTo(place.location);
          map.setZoom(15);
        }
      } catch (error) {
        console.error(
          "Place search failed:",
          error
        );
      }
    };

    searchElement.addEventListener(
      "gmp-select",
      handleSelect
    );

    containerRef.current.appendChild(
      searchElement
    );

    return () => {
      searchElement.removeEventListener(
        "gmp-select",
        handleSelect
      );

      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [map]);

  return (
    <div
      ref={containerRef}
      className="map-search"
    />
  );
}

/* =========================================================
   DOWNLOAD ANALYSIS JSON
   ========================================================= */

function downloadAnalysisJSON(analysis) {
  if (!analysis) {
    return;
  }

  const json = JSON.stringify(
    analysis,
    null,
    2
  );

  const blob = new Blob(
    [json],
    {
      type: "application/json",
    }
  );

  const url =
    URL.createObjectURL(blob);

  const link =
    document.createElement("a");

  link.href = url;
  link.download =
    "catchment-analysis-v1.json";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

/* =========================================================
   GEOJSON HELPERS
   ========================================================= */

function isFeatureCollection(value) {
  return (
    value &&
    value.type === "FeatureCollection" &&
    Array.isArray(value.features)
  );
}

function normalizeFeatureCollection(value) {
  if (!value) {
    return null;
  }

  if (isFeatureCollection(value)) {
    return value;
  }

  if (value.type === "Feature") {
    return {
      type: "FeatureCollection",
      features: [value],
    };
  }

  return null;
}

function getGeoJSONBounds(geojson) {
  const bounds = {
    minLat: Infinity,
    maxLat: -Infinity,
    minLng: Infinity,
    maxLng: -Infinity,
  };

  if (!isFeatureCollection(geojson)) {
    return null;
  }

  const collectCoordinates = (coords) => {
    if (
      Array.isArray(coords) &&
      coords.length >= 2 &&
      typeof coords[0] === "number" &&
      typeof coords[1] === "number"
    ) {
      const lng = coords[0];
      const lat = coords[1];

      bounds.minLng =
        Math.min(bounds.minLng, lng);

      bounds.maxLng =
        Math.max(bounds.maxLng, lng);

      bounds.minLat =
        Math.min(bounds.minLat, lat);

      bounds.maxLat =
        Math.max(bounds.maxLat, lat);

      return;
    }

    if (Array.isArray(coords)) {
      coords.forEach(collectCoordinates);
    }
  };

  geojson.features.forEach((feature) => {
    if (feature?.geometry?.coordinates) {
      collectCoordinates(
        feature.geometry.coordinates
      );
    }
  });

  if (
    bounds.minLat === Infinity ||
    bounds.minLng === Infinity
  ) {
    return null;
  }

  return bounds;
}

/* =========================================================
   MAP LAYER TOGGLE - V1 ONLY
   ========================================================= */

function LayerControl({
  visibility,
  onToggle,
  counts,
}) {
  return (
    <div className="layer-control">
      <div className="layer-control-title">
        Map Layers
      </div>

      <label className="layer-option">
        <input
          type="checkbox"
          checked={visibility.candidates}
          onChange={() =>
            onToggle("candidates")
          }
        />

        <span className="layer-color candidate-color" />

        <span className="layer-label">
          Pond Candidates
        </span>

        <span className="layer-count">
          {counts.candidates}
        </span>
      </label>

      <label className="layer-option">
        <input
          type="checkbox"
          checked={visibility.catchments}
          onChange={() =>
            onToggle("catchments")
          }
        />

        <span className="layer-color catchment-color" />

        <span className="layer-label">
          Catchment Areas
        </span>

        <span className="layer-count">
          {counts.catchments}
        </span>
      </label>
    </div>
  );
}

/* =========================================================
   GEOJSON MAP LAYER - V1 ONLY

   V1 supports:
   - Pond candidates
   - Catchments
   ========================================================= */

function GeoJsonLayer({
  analysis,
  candidates,
  selectedCandidate,
  onCandidateSelect,
  visibility,
}) {
  const map = useMap();

  useEffect(() => {
    if (!map) {
      return undefined;
    }

    /* -------------------------------------------------------
       CLEAR OLD FEATURES
       ------------------------------------------------------- */

    map.data.forEach((feature) => {
      map.data.remove(feature);
    });

    if (!analysis?.map_data) {
      return undefined;
    }

    /* -------------------------------------------------------
       V1 GEOJSON
       ------------------------------------------------------- */

    const candidateGeoJSON =
      normalizeFeatureCollection(
        analysis.map_data.candidates
      );

    const catchmentGeoJSON =
      normalizeFeatureCollection(
        analysis.map_data.catchments
      );

    console.log(
      "========== V1 GEOJSON MAP DATA =========="
    );

    console.log(
      "Candidates:",
      candidateGeoJSON?.features?.length || 0
    );

    console.log(
      "Catchments:",
      catchmentGeoJSON?.features?.length || 0
    );

    console.log(
      "Layer visibility:",
      visibility
    );

    /* -------------------------------------------------------
       ADD CATCHMENTS
       ------------------------------------------------------- */

    if (
      visibility.catchments &&
      catchmentGeoJSON?.features?.length
    ) {
      map.data.addGeoJson(
        catchmentGeoJSON
      );
    }

    /* -------------------------------------------------------
       ADD CANDIDATES
       ------------------------------------------------------- */

    if (
      visibility.candidates &&
      candidateGeoJSON?.features?.length
    ) {
      map.data.addGeoJson(
        candidateGeoJSON
      );
    }

    /* -------------------------------------------------------
       STYLE V1 FEATURES
       ------------------------------------------------------- */

    map.data.setStyle((feature) => {
      const geometry =
        feature.getGeometry();

      const geometryType =
        geometry?.getType();

      const layerType =
        feature.getProperty(
          "layer_type"
        );

      const rank =
        feature.getProperty("rank");

      /* -----------------------------------------------------
         CANDIDATE POINT
         ----------------------------------------------------- */

      if (
        geometryType === "Point"
      ) {
        const isSelected =
          Number(
            selectedCandidate?.rank
          ) === Number(rank);

        return {
          icon: {
            path:
              google.maps.SymbolPath.CIRCLE,

            scale: isSelected
              ? 11
              : 7,

            fillColor:
              isSelected
                ? "#D32F2F"
                : "#1976D2",

            fillOpacity: 1,

            strokeColor:
              "#FFFFFF",

            strokeWeight: 2,
          },

          zIndex:
            isSelected
              ? 1000
              : 100,
        };
      }

      /* -----------------------------------------------------
         V1 CATCHMENT
         ----------------------------------------------------- */

      if (
        layerType === "catchment"
      ) {
        return {
          fillColor:
            "#2196F3",

          fillOpacity:
            0.12,

          strokeColor:
            "#1565C0",

          strokeOpacity:
            0.8,

          strokeWeight:
            2,

          zIndex: 10,
        };
      }

      /* -----------------------------------------------------
         DEFAULT V1 CATCHMENT
         ----------------------------------------------------- */

      return {
        fillColor:
          "#2196F3",

        fillOpacity:
          0.08,

        strokeColor:
          "#1565C0",

        strokeOpacity:
          0.75,

        strokeWeight:
          1.5,

        zIndex: 10,
      };
    });

    /* -------------------------------------------------------
       CANDIDATE CLICK
       ------------------------------------------------------- */

    const handleDataClick = (event) => {
      const feature =
        event.feature;

      const geometry =
        feature.getGeometry();

      if (
        geometry?.getType() !==
        "Point"
      ) {
        return;
      }

      const rank =
        feature.getProperty("rank");

      console.log(
        "Clicked V1 candidate:",
        {
          rank,
          feature,
        }
      );

      const candidate =
        candidates.find(
          (item) =>
            Number(item.rank) ===
            Number(rank)
        );

      if (candidate) {
        onCandidateSelect(
          candidate
        );
      }
    };

    const listener =
      map.data.addListener(
        "click",
        handleDataClick
      );

    /* -------------------------------------------------------
       FIT MAP TO V1 ANALYSIS EXTENT
       ------------------------------------------------------- */

    const boundsSources = [
      catchmentGeoJSON,
      candidateGeoJSON,
    ];

    const bounds = {
      minLat: Infinity,
      maxLat: -Infinity,
      minLng: Infinity,
      maxLng: -Infinity,
    };

    let hasBounds = false;

    boundsSources.forEach(
      (collection) => {
        const collectionBounds =
          getGeoJSONBounds(
            collection
          );

        if (!collectionBounds) {
          return;
        }

        hasBounds = true;

        bounds.minLat =
          Math.min(
            bounds.minLat,
            collectionBounds.minLat
          );

        bounds.maxLat =
          Math.max(
            bounds.maxLat,
            collectionBounds.maxLat
          );

        bounds.minLng =
          Math.min(
            bounds.minLng,
            collectionBounds.minLng
          );

        bounds.maxLng =
          Math.max(
            bounds.maxLng,
            collectionBounds.maxLng
          );
      }
    );

    if (hasBounds) {
      const googleBounds =
        new google.maps.LatLngBounds(
          {
            lat: bounds.minLat,
            lng: bounds.minLng,
          },
          {
            lat: bounds.maxLat,
            lng: bounds.maxLng,
          }
        );

      map.fitBounds(
        googleBounds,
        60
      );
    }

    /* -------------------------------------------------------
       CLEANUP
       ------------------------------------------------------- */

    return () => {
      listener?.remove?.();

      map.data.forEach(
        (feature) => {
          map.data.remove(
            feature
          );
        }
      );
    };
  }, [
    map,
    analysis,
    candidates,
    selectedCandidate,
    onCandidateSelect,
    visibility,
  ]);

  return null;
}

/* =========================================================
   MAIN VILLAGE MAP
   ========================================================= */

function VillageMap() {
  /* =======================================================
     DRAWING STATE
     ======================================================= */

  const [
    points,
    setPoints,
  ] = useState([]);

  const [
    polygon,
    setPolygon,
  ] = useState([]);

  const [
    isDrawing,
    setIsDrawing,
  ] = useState(false);

  const [
    mousePosition,
    setMousePosition,
  ] = useState(null);

  /* =======================================================
     ANALYSIS STATE
     ======================================================= */

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState(null);

  const [
    analysis,
    setAnalysis,
  ] = useState(null);

  const [
    selectedCandidate,
    setSelectedCandidate,
  ] = useState(null);

  /* =======================================================
     V1 MAP LAYER VISIBILITY
     ======================================================= */

  const [
    layerVisibility,
    setLayerVisibility,
  ] = useState({
    candidates: true,
    catchments: true,
  });

  /* =======================================================
     TOGGLE MAP LAYER
     ======================================================= */

  const toggleLayer =
    useCallback(
      (layerName) => {
        setLayerVisibility(
          (previous) => ({
            ...previous,
            [layerName]:
              !previous[layerName],
          })
        );
      },
      []
    );

  /* =======================================================
     START DRAWING
     ======================================================= */

  const startDrawing =
    useCallback(() => {
      setPoints([]);
      setPolygon([]);
      setMousePosition(null);
      setError(null);
      setAnalysis(null);
      setSelectedCandidate(null);
      setIsDrawing(true);
    }, []);

  /* =======================================================
     MAP CLICK / DRAW POLYGON
     ======================================================= */

  const handleMapClick =
    useCallback(
      (event) => {
        if (!isDrawing) {
          return;
        }

        const latLng =
          event.detail?.latLng;

        if (!latLng) {
          return;
        }

        const clickedPoint = {
          lat: latLng.lat,
          lng: latLng.lng,
        };

        /* -------------------------------------------------
           CLOSE POLYGON
           ------------------------------------------------- */

        if (points.length >= 3) {
          const firstPoint =
            points[0];

          const distance =
            calculateDistance(
              firstPoint,
              clickedPoint
            );

          if (distance <= 30) {
            setPolygon([
              ...points,
              firstPoint,
            ]);

            setIsDrawing(false);
            setMousePosition(null);

            return;
          }
        }

        /* -------------------------------------------------
           ADD POINT
           ------------------------------------------------- */

        setPoints(
          (previous) => [
            ...previous,
            clickedPoint,
          ]
        );
      },
      [
        isDrawing,
        points,
      ]
    );

  /* =======================================================
     MOUSE MOVE
     ======================================================= */

  const handleMouseMove =
    useCallback(
      (event) => {
        if (!isDrawing) {
          return;
        }

        const latLng =
          event.detail?.latLng;

        if (!latLng) {
          return;
        }

        setMousePosition({
          lat: latLng.lat,
          lng: latLng.lng,
        });
      },
      [isDrawing]
    );

  /* =======================================================
     FILE ANALYSIS - V1
     ======================================================= */

  const handleFileAnalysis =
    useCallback(
      async (file) => {
        try {
          setLoading(true);
          setError(null);
          setAnalysis(null);
          setSelectedCandidate(null);

          console.log(
            "========================================"
          );

          console.log(
            "CATCHMENT VERSION:",
            CATCHMENT_VERSION
          );

          console.log(
            "STARTING V1 BACKEND ANALYSIS"
          );

          const result =
            await analyzeContourFileByVersion(
              file
            );

          console.log(
            "========== V1 BACKEND ANALYSIS =========="
          );

          console.log(
            "Complete backend response:",
            result
          );

          console.log(
            "Terrain:",
            result?.terrain
          );

          console.log(
            "Hydrology:",
            result?.hydrology
          );

          console.log(
            "Accumulation:",
            result?.accumulation
          );

          console.log(
            "Suitability:",
            result?.suitability
          );

          console.log(
            "Candidates:",
            result?.candidates
          );

          console.log(
            "Map data:",
            result?.map_data
          );

          console.log(
            "Map candidates:",
            result?.map_data?.candidates
          );

          console.log(
            "Map catchments:",
            result?.map_data?.catchments
          );

          console.log(
            "========================================"
          );

          setAnalysis(result);
        } catch (err) {
          console.error(
            "V1 terrain analysis error:",
            err
          );

          setError(
            err?.message ||
              "Terrain analysis failed."
          );
        } finally {
          setLoading(false);
        }
      },
      []
    );

  /* =======================================================
     CANDIDATE SELECTION
     ======================================================= */

  const handleCandidateSelect =
    useCallback(
      (candidate) => {
        console.log(
          "Selected V1 candidate:",
          candidate
        );

        setSelectedCandidate(
          candidate
        );
      },
      []
    );

  /* =======================================================
     CLEAR MAP
     ======================================================= */

  const clearMap =
    useCallback(() => {
      setPoints([]);
      setPolygon([]);
      setMousePosition(null);
      setIsDrawing(false);
      setAnalysis(null);
      setSelectedCandidate(null);
      setError(null);
    }, []);

  /* =======================================================
     GET V1 CANDIDATES
     ======================================================= */

  const candidates =
    analysis?.suitability?.candidates ||
    analysis?.candidates ||
    analysis?.hydrology?.pond_candidates ||
    [];

  /* =======================================================
     LAYER COUNTS
     ======================================================= */

  const layerCounts = {
    candidates:
      analysis?.map_data?.candidates
        ?.features?.length ||
      candidates.length,

    catchments:
      analysis?.map_data?.catchments
        ?.features?.length || 0,
  };

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <APIProvider
      apiKey={API_KEY}
      libraries={["places"]}
    >
      <div className="application">

        {/* =================================================
            MAIN MAP
            ================================================= */}

        <div className="map-container">

          <Map
            defaultCenter={
              DEFAULT_CENTER
            }
            defaultZoom={12}
            gestureHandling="greedy"
            mapTypeControl
            fullscreenControl
            streetViewControl
            zoomControl
            onClick={
              handleMapClick
            }
            onMousemove={
              handleMouseMove
            }
          >

            {/* =============================================
                USER DRAWING POINTS
                ============================================= */}

            {points.map(
              (point, index) => (
                <Marker
                  key={`draw-point-${index}`}
                  position={point}
                />
              )
            )}

            {/* =============================================
                USER DRAWING LINE
                ============================================= */}

            {points.length >= 2 && (
              <Polyline
                path={points}
                strokeColor="#1976D2"
                strokeOpacity={1}
                strokeWeight={3}
              />
            )}

            {/* =============================================
                LIVE DRAWING LINE
                ============================================= */}

            {isDrawing &&
              points.length >= 1 &&
              mousePosition && (
                <Polyline
                  path={[
                    points[
                      points.length - 1
                    ],
                    mousePosition,
                  ]}
                  strokeColor="#1976D2"
                  strokeOpacity={0.6}
                  strokeWeight={2}
                />
              )}

            {/* =============================================
                FINAL USER POLYGON
                ============================================= */}

            {polygon.length >= 4 && (
              <Polygon
                paths={polygon}
                fillColor="#2196F3"
                fillOpacity={0.18}
                strokeColor="#1565C0"
                strokeOpacity={1}
                strokeWeight={3}
              />
            )}

            {/* =============================================
                V1 BACKEND GEOJSON
                ============================================= */}

            <GeoJsonLayer
              analysis={analysis}
              candidates={candidates}
              selectedCandidate={
                selectedCandidate
              }
              onCandidateSelect={
                handleCandidateSelect
              }
              visibility={
                layerVisibility
              }
            />
          </Map>

          {/* =================================================
              SEARCH
              ================================================= */}

          <MapControl
            position={
              ControlPosition.TOP_CENTER
            }
          >
            <SearchBox />
          </MapControl>

          {/* =================================================
              TOOLBAR
              ================================================= */}

          <MapControl
            position={
              ControlPosition.TOP_LEFT
            }
          >
            <MapToolbar
              isDrawing={
                isDrawing
              }
              hasPolygon={
                polygon.length >= 4
              }
              loading={
                loading
              }
              onStartDrawing={
                startDrawing
              }
              onClear={
                clearMap
              }
            />
          </MapControl>

          {/* =================================================
              V1 MAP LAYER CONTROL
              ================================================= */}

          {analysis && (
            <div className="map-layer-control-wrapper">
              <LayerControl
                visibility={
                  layerVisibility
                }
                onToggle={
                  toggleLayer
                }
                counts={
                  layerCounts
                }
              />
            </div>
          )}

          {/* =================================================
              FILE UPLOAD
              ================================================= */}

          <div className="upload-wrapper">
            <FileUpload
              onAnalyze={
                handleFileAnalysis
              }
              loading={
                loading
              }
            />
          </div>

          {/* =================================================
              V1 LOADING INDICATOR
              ================================================= */}

          {loading && (
            <div className="analysis-loading">
              <div className="spinner" />

              <strong>
                Processing terrain...
              </strong>

              <span>
                DEM → Slope → D8 Hydrology
                → Flow Accumulation
                → Pond Suitability
              </span>
            </div>
          )}

          {/* =================================================
              ERROR
              ================================================= */}

          {error && (
            <div className="map-error">
              <strong>
                Analysis failed
              </strong>

              <span>
                {error}
              </span>

              <button
                type="button"
                onClick={() =>
                  setError(null)
                }
              >
                ×
              </button>
            </div>
          )}
        </div>

        {/* =================================================
            RIGHT SIDEBAR
            ================================================= */}

        <aside className="analysis-sidebar">

          {/* ===============================================
              DOWNLOAD JSON
              =============================================== */}

          {analysis && (
            <button
              type="button"
              className="download-json-button"
              onClick={() =>
                downloadAnalysisJSON(
                  analysis
                )
              }
            >
              ↓ Download JSON
            </button>
          )}

          {/* ===============================================
              ANALYSIS PANEL
              =============================================== */}

          <AnalysisPanel
            analysis={analysis}
          />

          {/* ===============================================
              CANDIDATE LIST
              =============================================== */}

          {analysis && (
            <CandidateList
              candidates={
                candidates
              }
              selectedRank={
                selectedCandidate?.rank
              }
              onSelect={
                handleCandidateSelect
              }
            />
          )}
        </aside>
      </div>
    </APIProvider>
  );
}

/* =========================================================
   HAVERSINE DISTANCE
   ========================================================= */

function calculateDistance(
  point1,
  point2
) {
  const R = 6371000;

  const lat1 =
    (point1.lat * Math.PI) /
    180;

  const lat2 =
    (point2.lat * Math.PI) /
    180;

  const deltaLat =
    ((point2.lat -
      point1.lat) *
      Math.PI) /
    180;

  const deltaLng =
    ((point2.lng -
      point1.lng) *
      Math.PI) /
    180;

  const a =
    Math.sin(
      deltaLat / 2
    ) ** 2 +
    Math.cos(lat1) *
      Math.cos(lat2) *
      Math.sin(
        deltaLng / 2
      ) ** 2;

  const c =
    2 *
    Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a)
    );

  return R * c;
}

export default VillageMap;

