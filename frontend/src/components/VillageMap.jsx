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

import { analyzeContourFile } from "../services/catchmentService";

import "./VillageMap.css";

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const DEFAULT_CENTER = {
  lat: 21.1904,
  lng: 81.2849,
};

/* -------------------------------------------------------
   SEARCH
------------------------------------------------------- */

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

/* -------------------------------------------------------
   MAIN MAP
------------------------------------------------------- */

function VillageMap() {
  const [points, setPoints] = useState([]);
  const [polygon, setPolygon] = useState([]);

  const [isDrawing, setIsDrawing] =
    useState(false);

  const [mousePosition, setMousePosition] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState(null);

  const [analysis, setAnalysis] =
    useState(null);

  const [selectedCandidate, setSelectedCandidate] =
    useState(null);

  /* ---------------------------------------------------
     DRAWING
  --------------------------------------------------- */

  const startDrawing = useCallback(() => {
    setPoints([]);
    setPolygon([]);
    setMousePosition(null);
    setError(null);
    setAnalysis(null);
    setSelectedCandidate(null);

    setIsDrawing(true);
  }, []);

  const handleMapClick = useCallback(
    (event) => {
      if (!isDrawing) {
        return;
      }

      const latLng =
        event.detail.latLng;

      if (!latLng) {
        return;
      }

      const clickedPoint = {
        lat: latLng.lat,
        lng: latLng.lng,
      };

      if (points.length >= 3) {
        const firstPoint = points[0];

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

      setPoints((previous) => [
        ...previous,
        clickedPoint,
      ]);
    },
    [isDrawing, points]
  );

  const handleMouseMove = useCallback(
    (event) => {
      if (!isDrawing) {
        return;
      }

      const latLng =
        event.detail.latLng;

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

  /* ---------------------------------------------------
     FILE ANALYSIS
  --------------------------------------------------- */

  const handleFileAnalysis = useCallback(
    async (file) => {
      try {
        setLoading(true);
        setError(null);
        setAnalysis(null);
        setSelectedCandidate(null);

        const result =
          await analyzeContourFile(file);

        console.log(
          "Catchment analysis:",
          result
        );

        setAnalysis(result);
      } catch (err) {
        console.error(err);

        setError(
          err.message ||
            "Terrain analysis failed."
        );
      } finally {
        setLoading(false);
      }
    },
    []
  );

  /* ---------------------------------------------------
     CANDIDATE SELECTION
  --------------------------------------------------- */

  const handleCandidateSelect =
    useCallback((candidate) => {
      setSelectedCandidate(candidate);
    }, []);

  /* ---------------------------------------------------
     CLEAR
  --------------------------------------------------- */

  const clearMap = useCallback(() => {
    setPoints([]);
    setPolygon([]);
    setMousePosition(null);

    setIsDrawing(false);

    setAnalysis(null);
    setSelectedCandidate(null);

    setError(null);
  }, []);

  /* ---------------------------------------------------
     CANDIDATES
  --------------------------------------------------- */

  const candidates =
    analysis?.analysis?.candidates ||
    analysis?.suitability?.candidates ||
    analysis?.hydrology?.pond_candidates ||
    [];

  return (
    <APIProvider
      apiKey={API_KEY}
      libraries={["places"]}
    >
      <div className="application">

        {/* -------------------------------------------
            MAP
        -------------------------------------------- */}

        <div className="map-container">
          <Map
            defaultCenter={DEFAULT_CENTER}
            defaultZoom={12}
            gestureHandling="greedy"
            mapTypeControl
            fullscreenControl
            streetViewControl
            zoomControl
            onClick={handleMapClick}
            onMousemove={handleMouseMove}
          >

            {/* DRAWING POINTS */}

            {points.map(
              (point, index) => (
                <Marker
                  key={index}
                  position={point}
                />
              )
            )}

            {/* DRAWING LINE */}

            {points.length >= 2 && (
              <Polyline
                path={points}
                strokeColor="#1976D2"
                strokeOpacity={1}
                strokeWeight={3}
              />
            )}

            {/* LIVE LINE */}

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

            {/* FINAL POLYGON */}

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

            {/* POND CANDIDATES */}

            {candidates.map(
              (candidate) => (
                <Marker
                  key={`candidate-${candidate.rank}`}
                  position={{
                    lat: candidate.latitude,
                    lng: candidate.longitude,
                  }}
                  title={`Candidate #${candidate.rank}`}
                  onClick={() =>
                    handleCandidateSelect(
                      candidate
                    )
                  }
                />
              )
            )}

          </Map>

          {/* SEARCH */}

          <MapControl
            position={
              ControlPosition.TOP_CENTER
            }
          >
            <SearchBox />
          </MapControl>

          {/* TOOLBAR */}

          <MapControl
            position={
              ControlPosition.TOP_LEFT
            }
          >
            <MapToolbar
              isDrawing={isDrawing}
              hasPolygon={
                polygon.length >= 4
              }
              loading={loading}
              onStartDrawing={
                startDrawing
              }
              onClear={clearMap}
            />
          </MapControl>

          {/* FILE UPLOAD */}

          <div className="upload-wrapper">
            <FileUpload
              onAnalyze={
                handleFileAnalysis
              }
              loading={loading}
            />
          </div>

          {/* ERROR */}

          {error && (
            <div className="map-error">
              <strong>
                Analysis failed
              </strong>

              <span>{error}</span>

              <button
                onClick={() =>
                  setError(null)
                }
              >
                ×
              </button>
            </div>
          )}

          {/* LOADING */}

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
        </div>

        {/* -------------------------------------------
            RIGHT SIDEBAR
        -------------------------------------------- */}

        <aside className="analysis-sidebar">

          <AnalysisPanel
            analysis={analysis}
          />

          {analysis && (
            <CandidateList
              candidates={candidates}
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

/* -------------------------------------------------------
   DISTANCE
------------------------------------------------------- */

function calculateDistance(
  point1,
  point2
) {
  const R = 6371000;

  const lat1 =
    (point1.lat * Math.PI) / 180;

  const lat2 =
    (point2.lat * Math.PI) / 180;

  const deltaLat =
    ((point2.lat - point1.lat) *
      Math.PI) /
    180;

  const deltaLng =
    ((point2.lng - point1.lng) *
      Math.PI) /
    180;

  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) *
      Math.cos(lat2) *
      Math.sin(deltaLng / 2) ** 2;

  const c =
    2 *
    Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a)
    );

  return R * c;
}

export default VillageMap;