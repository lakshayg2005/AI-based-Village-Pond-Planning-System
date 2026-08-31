import{
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

import { analyzeContourFile } from "../services/catchmentService";

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
      console.warn(
        "Google Places library is not loaded."
      );
      return;
    }

    const searchElement =
      new google.maps.places.PlaceAutocompleteElement();

    searchElement.placeholder =
      "Search for a village, city, place...";

    searchElement.style.width = "400px";
    searchElement.style.height = "48px";

    const handleSelect = async (event) => {
      try {
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

    containerRef.current.innerHTML = "";

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
    "catchment-analysis.json";

  document.body.appendChild(link);

  link.click();

  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

/* =========================================================
   GEOJSON MAP LAYER

   Renders:
   1. Catchment polygons
   2. Candidate points

   Both are supplied by the backend.
========================================================= */

function GeoJsonLayer({
  analysis,
  candidates,
  selectedCandidate,
  onCandidateSelect,
}) {
  const map = useMap();

  useEffect(() => {
    if (!map || !analysis?.map_data) {
      return;
    }

    const candidateGeoJSON =
      analysis.map_data.candidates;

    const catchmentGeoJSON =
      analysis.map_data.catchments;

    /* -----------------------------------------------------
       DEBUG
    ----------------------------------------------------- */

    console.log(
      "========== GEOJSON MAP DATA =========="
    );

    console.log(
      "Candidate GeoJSON:",
      candidateGeoJSON
    );

    console.log(
      "Catchment GeoJSON:",
      catchmentGeoJSON
    );

    /* -----------------------------------------------------
       VALIDATION
    ----------------------------------------------------- */

    if (
      candidateGeoJSON &&
      candidateGeoJSON.type !==
        "FeatureCollection"
    ) {
      console.error(
        "Candidate GeoJSON is not a FeatureCollection:",
        candidateGeoJSON
      );
    }

    if (
      catchmentGeoJSON &&
      catchmentGeoJSON.type !==
        "FeatureCollection"
    ) {
      console.error(
        "Catchment GeoJSON is not a FeatureCollection:",
        catchmentGeoJSON
      );
    }

    /* -----------------------------------------------------
       DEBUG CATCHMENTS
    ----------------------------------------------------- */

    if (
      catchmentGeoJSON?.features?.length
    ) {
      console.log(
        "Catchment feature count:",
        catchmentGeoJSON.features.length
      );

      catchmentGeoJSON.features.forEach(
        (feature, index) => {
          const coordinates =
            feature.geometry?.coordinates;

          const flattened = [];

          const collectCoordinates = (
            coords
          ) => {
            if (
              Array.isArray(coords) &&
              coords.length >= 2 &&
              typeof coords[0] ===
                "number" &&
              typeof coords[1] ===
                "number"
            ) {
              flattened.push(coords);
              return;
            }

            if (Array.isArray(coords)) {
              coords.forEach(
                collectCoordinates
              );
            }
          };

          collectCoordinates(
            coordinates
          );

          const lats =
            flattened.map(
              (coordinate) =>
                coordinate[1]
            );

          const lngs =
            flattened.map(
              (coordinate) =>
                coordinate[0]
            );

          console.log(
            `========== CATCHMENT ${
              index + 1
            } ==========`
          );

          console.log({
            rank:
              feature.properties?.rank,

            area_m2:
              feature.properties?.area_m2,

            area_hectares:
              feature.properties
                ?.area_hectares,

            geometry:
              feature.geometry?.type,

            coordinateCount:
              flattened.length,

            minLatitude:
              lats.length
                ? Math.min(...lats)
                : null,

            maxLatitude:
              lats.length
                ? Math.max(...lats)
                : null,

            minLongitude:
              lngs.length
                ? Math.min(...lngs)
                : null,

            maxLongitude:
              lngs.length
                ? Math.max(...lngs)
                : null,

            firstCoordinate:
              flattened[0],

            lastCoordinate:
              flattened[
                flattened.length - 1
              ],
          });
        }
      );
    }

    /* -----------------------------------------------------
       DEBUG CANDIDATES
    ----------------------------------------------------- */

    if (
      candidateGeoJSON?.features?.length
    ) {
      console.log(
        "Candidate feature count:",
        candidateGeoJSON.features.length
      );

      candidateGeoJSON.features.forEach(
        (feature, index) => {
          console.log(
            `Candidate ${index + 1}:`,
            {
              geometry:
                feature.geometry?.type,

              rank:
                feature.properties?.rank,

              properties:
                feature.properties,

              coordinates:
                feature.geometry?.coordinates,
            }
          );
        }
      );
    }

    /* -----------------------------------------------------
       CLEAR PREVIOUS GEOJSON
    ----------------------------------------------------- */

    map.data.forEach((feature) => {
      map.data.remove(feature);
    });

    /* -----------------------------------------------------
       ADD CATCHMENTS
    ----------------------------------------------------- */

    if (
      catchmentGeoJSON?.features?.length
    ) {
      console.log(
        "RAW CATCHMENT COORDINATES:",
        JSON.stringify(
          catchmentGeoJSON.features[0]?.geometry?.coordinates,
          null,
          2
        )
      );
      console.log(
        "RAW CANDIDATE COORDINATES:",
        JSON.stringify(
          candidateGeoJSON?.features?.[0]?.geometry?.coordinates,
          null,
          2
        )
      ); 
      console.log(
        "CATCHMENT CRS:",
        catchmentGeoJSON?.crs
      );
      
      console.log(
        "CANDIDATE CRS:",
        candidateGeoJSON?.crs
      ); 
      const addedCatchments =
        map.data.addGeoJson(
          catchmentGeoJSON
        );

      console.log(
        "Catchment GeoJSON features added:",
        addedCatchments?.length
      );
    }

    /* -----------------------------------------------------
       ADD CANDIDATES
    ----------------------------------------------------- */

    if (
      candidateGeoJSON?.features?.length
    ) {
      const addedCandidates =
        map.data.addGeoJson(
          candidateGeoJSON
        );

      console.log(
        "Candidate GeoJSON features added:",
        addedCandidates?.length
      );
    }

    /* -----------------------------------------------------
       GEOJSON STYLING
    ----------------------------------------------------- */

    map.data.setStyle((feature) => {
      const geometry =
        feature.getGeometry();

      const rank =
        feature.getProperty("rank");

      /* ---------------------------------------------------
         CANDIDATE POINT
      --------------------------------------------------- */

      if (
        geometry?.getType() ===
        "Point"
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
              ? 10
              : 7,

            fillColor: isSelected
              ? "#D32F2F"
              : "#1976D2",

            fillOpacity: 1,

            strokeColor:
              "#FFFFFF",

            strokeWeight: 2,
          },

          zIndex: isSelected
            ? 1000
            : 100,
        };
      }

      /* ---------------------------------------------------
         CATCHMENT POLYGON
      --------------------------------------------------- */

      return {
        fillColor: "#2196F3",

        fillOpacity: 0.18,

        strokeColor:
          "#1565C0",

        strokeOpacity: 1,

        strokeWeight: 2,

        zIndex: 10,
      };
    });

    /* -----------------------------------------------------
       CANDIDATE CLICK HANDLER
    ----------------------------------------------------- */

    const handleDataClick = (
      event
    ) => {
      const geometry =
        event.feature.getGeometry();

      if (
        geometry?.getType() !==
        "Point"
      ) {
        return;
      }

      const rank =
        event.feature.getProperty(
          "rank"
        );

      console.log(
        "Clicked GeoJSON candidate:",
        {
          rank,
          feature:
            event.feature,
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

    /* -----------------------------------------------------
       CLEANUP
    ----------------------------------------------------- */

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
  ]);

  return null;
}

/* =========================================================
   MAIN VILLAGE MAP
========================================================= */

function VillageMap() {
  /* -------------------------------------------------------
     DRAWING STATE
  ------------------------------------------------------- */

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

  /* -------------------------------------------------------
     ANALYSIS STATE
  ------------------------------------------------------- */

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
           CLOSE POLYGON WHEN CLICKING NEAR FIRST POINT
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
      [isDrawing, points]
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
     FILE ANALYSIS
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
            "========== STARTING BACKEND ANALYSIS =========="
          );

          const result =
            await analyzeContourFile(
              file
            );

          console.log(
            "========== BACKEND ANALYSIS =========="
          );

          console.log(
            "Complete backend response:",
            result
          );

          console.log(
            "Backend map_data:",
            result?.map_data
          );

          console.log(
            "Backend candidates GeoJSON:",
            result?.map_data
              ?.candidates
          );

          console.log(
            "Backend catchments GeoJSON:",
            result?.map_data
              ?.catchments
          );

          console.log(
            "======================================"
          );

          setAnalysis(result);
        } catch (err) {
          console.error(
            "Terrain analysis error:",
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
          "Selected candidate:",
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
     GET CANDIDATES

     Supports the different response structures that
     your backend has used during development.
  ======================================================= */

  const candidates =
    analysis?.analysis
      ?.candidates ||

    analysis?.suitability
      ?.candidates ||

    analysis?.hydrology
      ?.pond_candidates ||

    [];

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
            LEFT / MAIN MAP
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
            ============================================== */}

            {points.map(
              (point, index) => (
                <Marker
                  key={index}
                  position={point}
                />
              )
            )}

            {/* =============================================
                USER DRAWING LINE
            ============================================== */}

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
            ============================================== */}

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
                FINAL USER DRAWN POLYGON
            ============================================== */}

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
                BACKEND GEOJSON

                Catchments + Candidates
            ============================================== */}

            <GeoJsonLayer
              analysis={analysis}

              candidates={
                candidates
              }

              selectedCandidate={
                selectedCandidate
              }

              onCandidateSelect={
                handleCandidateSelect
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
              LOADING INDICATOR
          ================================================= */}

          {loading && (
            <div className="analysis-loading">

              <div className="spinner" />

              <strong>
                Processing terrain...
              </strong>

              <span>
                DEM → Slope → Hydrology →
                Pond candidates
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
          ================================================ */}

          {analysis && (
            <button
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
          ================================================ */}

          <AnalysisPanel
            analysis={
              analysis
            }
          />

          {/* ===============================================
              CANDIDATE LIST
          ================================================ */}

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
   DISTANCE CALCULATION

   Haversine distance in meters.
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
    ((point2.lat - point1.lat) *
      Math.PI) /
    180;

  const deltaLng =
    ((point2.lng - point1.lng) *
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
