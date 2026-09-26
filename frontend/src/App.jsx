import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import MapView from "./components/MapView";
import ResultsPanel from "./components/ResultsPanel";
import Sidebar from "./components/Sidebar";
import { parseContourFile } from "./services/contourService";
import {
  analyzeArea,
  analyzeContourFile,
  fetchServerInfo,
} from "./services/api";
import { polygonAreaKm2, toClosedRing } from "./utils/geo";
import "./App.css";

const DEFAULT_MAX_AREA_KM2 = 25;

const DEFAULT_PARAMS = {
  rainfall: "",
  runoff: "",
  maxSlope: 8,
  maxPonds: 10,
};

function boundsOfFeatureCollection(collection) {
  let minLat = Infinity;
  let minLng = Infinity;
  let maxLat = -Infinity;
  let maxLng = -Infinity;

  for (const feature of collection?.features ?? []) {
    for (const [lng, lat] of feature.geometry?.coordinates ?? []) {
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLng = Math.min(minLng, lng);
      maxLng = Math.max(maxLng, lng);
    }
  }

  return Number.isFinite(minLat)
    ? [[minLat, minLng], [maxLat, maxLng]]
    : null;
}

function terrainBounds(result) {
  const b = result?.terrain?.bounds;
  return b ? [[b.min_lat, b.min_lng ?? b.min_lon], [b.max_lat, b.max_lon]] : null;
}

export default function App() {
  const [mode, setMode] = useState("area");
  const [phase, setPhase] = useState("idle"); // idle | drawing | ready
  const [vertices, setVertices] = useState([]);
  const [file, setFile] = useState(null);
  const [contours, setContours] = useState(null);
  const [params, setParams] = useState(DEFAULT_PARAMS);

  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedRank, setSelectedRank] = useState(null);

  const [layers, setLayers] = useState({ catchments: true, ponds: true, contours: true });
  const [fitTarget, setFitTarget] = useState(null);
  const [maxAreaKm2, setMaxAreaKm2] = useState(DEFAULT_MAX_AREA_KM2);

  const abortRef = useRef(null);

  useEffect(() => {
    fetchServerInfo().then((info) => {
      if (info?.max_area_km2) setMaxAreaKm2(info.max_area_km2);
    });
  }, []);

  useEffect(() => {
    if (!loading) return undefined;
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.round((Date.now() - started) / 1000)),
      500
    );
    return () => clearInterval(timer);
  }, [loading]);

  const areaKm2 = useMemo(() => polygonAreaKm2(vertices), [vertices]);
  const areaTooLarge = phase === "ready" && areaKm2 > maxAreaKm2;

  const resetResults = useCallback(() => {
    setResult(null);
    setSelectedRank(null);
    setError(null);
  }, []);

  // ---- drawing ---------------------------------------------------------------
  const startDrawing = useCallback(() => {
    resetResults();
    setVertices([]);
    setPhase("drawing");
  }, [resetResults]);

  const finishDrawing = useCallback(() => {
    if (vertices.length >= 3) setPhase("ready");
  }, [vertices.length]);

  const clearArea = useCallback(() => {
    resetResults();
    setVertices([]);
    setPhase("idle");
  }, [resetResults]);

  const addVertex = useCallback((vertex) => setVertices((v) => [...v, vertex]), []);
  const undoVertex = useCallback(() => setVertices((v) => v.slice(0, -1)), []);

  // ---- mode / file -----------------------------------------------------------
  const changeMode = useCallback(
    (next) => {
      if (next === mode) return;
      resetResults();
      setMode(next);
      if (next === "file") {
        setPhase(vertices.length >= 3 ? "ready" : "idle");
      }
    },
    [mode, resetResults, vertices.length]
  );

  const chooseFile = useCallback(
    async (selected) => {
      resetResults();
      setFile(null);
      setContours(null);
      if (!selected) return;

      const name = selected.name.toLowerCase();
      if (!name.endsWith(".kml") && !name.endsWith(".kmz")) {
        setError("Please choose a .kml or .kmz file.");
        return;
      }

      setFile(selected);

      // Preview the contours right away; failure here is non-fatal because
      // the server parses the file itself.
      try {
        const geo = await parseContourFile(selected);
        setContours(geo);
        const bounds = boundsOfFeatureCollection(geo);
        if (bounds) setFitTarget({ bounds });
      } catch {
        setContours(null);
      }
    },
    [resetResults]
  );

  // ---- analysis ---------------------------------------------------------------
  const run = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current = controller;

    resetResults();
    setElapsed(0);
    setLoading(true);

    try {
      const data =
        mode === "area"
          ? await analyzeArea(toClosedRing(vertices), params, controller.signal)
          : await analyzeContourFile(file, params, controller.signal);

      setResult(data);
      setSelectedRank(data.analysis?.candidates?.[0]?.rank ?? null);

      const bounds =
        mode === "area"
          ? [
              [Math.min(...vertices.map((v) => v.lat)), Math.min(...vertices.map((v) => v.lng))],
              [Math.max(...vertices.map((v) => v.lat)), Math.max(...vertices.map((v) => v.lng))],
            ]
          : terrainBounds(data);
      if (bounds) setFitTarget({ bounds });
    } catch (err) {
      if (err.name !== "AbortError") setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [mode, vertices, file, params, resetResults]);

  const cancel = useCallback(() => abortRef.current?.abort(), []);

  const selectRank = useCallback(
    (rank) => {
      setSelectedRank(rank);
      const candidate = result?.analysis?.candidates?.find((c) => c.rank === rank);
      if (candidate) {
        setFitTarget({
          bounds: [
            [candidate.latitude - 0.002, candidate.longitude - 0.002],
            [candidate.latitude + 0.002, candidate.longitude + 0.002],
          ],
        });
      }
    },
    [result]
  );

  const toggleLayer = useCallback(
    (key) => setLayers((current) => ({ ...current, [key]: !current[key] })),
    []
  );

  const canRun =
    !loading &&
    (mode === "area" ? phase === "ready" && !areaTooLarge : Boolean(file));

  // Keep the drawn area visible while in upload mode only if it exists;
  // hide it from the map to avoid confusion.
  const mapVertices = mode === "area" ? vertices : [];

  return (
    <div className="app">
      <Sidebar
        mode={mode}
        onModeChange={changeMode}
        area={{
          phase,
          vertices,
          areaKm2,
          maxAreaKm2,
          areaTooLarge,
          onStart: startDrawing,
          onUndo: undoVertex,
          onFinish: finishDrawing,
          onClear: clearArea,
        }}
        file={file}
        onFile={chooseFile}
        params={params}
        onParamsChange={setParams}
        canRun={canRun}
        loading={loading}
        elapsed={elapsed}
        error={error}
        onRun={run}
        onCancel={cancel}
      >
        {result && (
          <ResultsPanel
            result={result}
            selectedRank={selectedRank}
            onSelectRank={selectRank}
          />
        )}
      </Sidebar>

      <MapView
        drawing={mode === "area" && phase === "drawing"}
        vertices={mapVertices}
        areaTooLarge={areaTooLarge}
        onAddVertex={addVertex}
        onFinishDrawing={finishDrawing}
        contours={mode === "file" ? contours : result?.map_data?.contours ?? null}
        contourInterval={mode === "area" ? result?.terrain?.contour_interval_m : null}
        result={result}
        selectedRank={selectedRank}
        onSelectRank={selectRank}
        layers={layers}
        onToggleLayer={toggleLayer}
        fitTarget={fitTarget}
      />
    </div>
  );
}
