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

import { useState, useCallback, useEffect, useRef } from "react";

import MapToolbar from "./MapToolbar";
import { contourLines } from "../services/contourService";

import "./VillageMap.css";

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const DEFAULT_CENTER = {
  lat: 21.1904,
  lng: 81.2849,
};

function SearchBox() {
  const map = useMap();

  const containerRef = useRef(null);

  useEffect(() => {
    if (!map || !containerRef.current) {
      return;
    }

    const searchElement = new google.maps.places.PlaceAutocompleteElement();

    searchElement.placeholder = "Search for a village, city, place...";

    searchElement.style.width = "400px";

    searchElement.style.height = "48px";

    searchElement.addEventListener("gmp-select", async (event) => {
      const place = event.placePrediction.toPlace();

      await place.fetchFields({
        fields: ["displayName", "location", "viewport"],
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
    });

    containerRef.current.innerHTML = "";

    containerRef.current.appendChild(searchElement);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [map]);

  return <div ref={containerRef} className="map-search" />;
}

function VillageMap() {
  const [gridSize, setGridSize] = useState(30);

  const [contourInterval, setContourInterval] = useState(10);
  /*
   * Points currently being drawn
   */
  const [points, setPoints] = useState([]);

  /*
   * Final polygon
   */
  const [polygon, setPolygon] = useState([]);

  /*
   * Whether drawing mode is active
   */
  const [isDrawing, setIsDrawing] = useState(false);

  /*
   * Current mouse position
   */
  const [mousePosition, setMousePosition] = useState(null);

  /*
   * Contour lines returned by backend
   */
  const [contours, setContours] = useState([]);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState(null);

  /*
   * Start drawing
   */
  const startDrawing = useCallback(() => {
    setPoints([]);

    setPolygon([]);

    setContours([]);

    setMousePosition(null);

    setError(null);

    setIsDrawing(true);
  }, []);

  /*
   * Handle map click
   */
  const handleMapClick = useCallback(
    (event) => {
      if (!isDrawing) {
        return;
      }

      const latLng = event.detail.latLng;

      if (!latLng) {
        return;
      }

      const clickedPoint = {
        lat: latLng.lat,

        lng: latLng.lng,
      };

      /*
       * If user has at least
       * 3 points and clicks
       * close to the first point,
       * close the polygon.
       */

      if (points.length >= 3) {
        const firstPoint = points[0];

        const distance = calculateDistance(firstPoint, clickedPoint);

        /*
         * 30 meter closing radius
         */

        if (distance <= 30) {
          setPolygon([...points, firstPoint]);

          setIsDrawing(false);

          setMousePosition(null);

          return;
        }
      }

      /*
       * Add new point
       */

      setPoints((previous) => [...previous, clickedPoint]);
    },
    [isDrawing, points],
  );

  /*
   * Track mouse while drawing
   */
  const handleMouseMove = useCallback(
    (event) => {
      if (!isDrawing) {
        return;
      }

      const latLng = event.detail.latLng;

      if (!latLng) {
        return;
      }

      setMousePosition({
        lat: latLng.lat,

        lng: latLng.lng,
      });
    },
    [isDrawing],
  );

  /*
   * Generate contour lines
   */
  const generateContours = useCallback(async () => {
    if (polygon.length < 4) {
      alert("Close the polygon first.");

      return;
    }

    try {
      setLoading(true);

      setError(null);

      const result = await contourLines(polygon, gridSize, contourInterval);

      setContours(result.contours);

      console.log("DEM elevation data:", result.elevations);

      console.log("Min elevation:", result.min_elevation);

      console.log("Max elevation:", result.max_elevation);
    } catch (err) {
      console.error(err);

      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [polygon, gridSize, contourInterval]);

  /*
   * Clear map
   */
  const clearMap = useCallback(() => {
    setPoints([]);

    setPolygon([]);

    setContours([]);

    setMousePosition(null);

    setIsDrawing(false);

    setError(null);
  }, []);

  return (
    <APIProvider apiKey={API_KEY} libraries={["places"]}>
      <div className="village-map">
        <Map
          defaultCenter={DEFAULT_CENTER}
          defaultZoom={12}
          gestureHandling="greedy"
          mapTypeControl={true}
          fullscreenControl={true}
          streetViewControl={true}
          zoomControl={true}
          onClick={handleMapClick}
          onMousemove={handleMouseMove}
        >
          {/* =========================
                        POINT MARKERS
                    ========================= */}

          {points.map((point, index) => (
            <Marker key={index} position={point} />
          ))}

          {/* =========================
                        DRAWN LINES
                    ========================= */}

          {points.length >= 2 && (
            <Polyline
              path={points}
              strokeColor="#1976D2"
              strokeOpacity={1}
              strokeWeight={3}
            />
          )}

          {/* =========================
                        LIVE LINE
                    ========================= */}

          {isDrawing && points.length >= 1 && mousePosition && (
            <Polyline
              path={[points[points.length - 1], mousePosition]}
              strokeColor="#1976D2"
              strokeOpacity={0.6}
              strokeWeight={2}
            />
          )}

          {/* =========================
                        FINAL POLYGON
                    ========================= */}

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

          {/* =========================
                        CONTOUR LINES
                    ========================= */}

          {contours.map((contour, index) => (
            <Polyline
              key={`contour-${index}`}
              path={contour.coordinates.map(([lng, lat]) => ({
                lat,
                lng,
              }))}
              strokeColor="#E65100"
              strokeOpacity={0.8}
              strokeWeight={2}
            />
          ))}
        </Map>

        {/* =========================
                    SEARCH
                ========================= */}

        <MapControl position={ControlPosition.TOP_CENTER}>
          <SearchBox />
        </MapControl>

        {/* =========================
                    TOOLBAR
                ========================= */}

        <MapControl position={ControlPosition.TOP_LEFT}>
          <MapToolbar
            isDrawing={isDrawing}
            hasPolygon={polygon.length >= 4}
            loading={loading}
            gridSize={gridSize}
            contourInterval={contourInterval}
            onGridSizeChange={setGridSize}
            onContourIntervalChange={setContourInterval}
            onStartDrawing={startDrawing}
            onClear={clearMap}
            onGenerateContours={generateContours}
          />
        </MapControl>

        {/* =========================
                    ERROR
                ========================= */}

        {error && <div className="map-error">{error}</div>}
      </div>
    </APIProvider>
  );
}

function calculateDistance(point1, point2) {
  const R = 6371000;

  const lat1 = (point1.lat * Math.PI) / 180;

  const lat2 = (point2.lat * Math.PI) / 180;

  const deltaLat = ((point2.lat - point1.lat) * Math.PI) / 180;

  const deltaLng = ((point2.lng - point1.lng) * Math.PI) / 180;

  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

export default VillageMap;
