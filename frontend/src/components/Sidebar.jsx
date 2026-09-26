import { useRef } from "react";
import { fmtArea } from "../utils/geo";

const MIN_RELIABLE_M2 = 50000;

function AreaSection({
  phase,
  vertices,
  areaKm2,
  maxAreaKm2,
  areaTooLarge,
  onStart,
  onUndo,
  onFinish,
  onClear,
  disabled,
}) {
  return (
    <section className="step">
      <h2>
        <span className="step-num">1</span> Select your land
      </h2>

      {phase === "idle" && (
        <>
          <p className="help">
            Outline the land you want to analyse. Terrain data is fetched for
            that area automatically, so no files are needed.
          </p>
          <button className="btn primary" onClick={onStart} disabled={disabled}>
            ✏️ Draw area on map
          </button>
        </>
      )}

      {phase === "drawing" && (
        <>
          <p className="help">
            Click on the map to add corner points ({vertices.length} so far).
            You need at least 3.
          </p>
          <div className="btn-row">
            <button className="btn primary" onClick={onFinish} disabled={vertices.length < 3}>
              ✓ Finish
            </button>
            <button className="btn" onClick={onUndo} disabled={vertices.length === 0}>
              ↶ Undo
            </button>
            <button className="btn ghost" onClick={onClear}>
              Cancel
            </button>
          </div>
        </>
      )}

      {phase === "ready" && (
        <>
          <div className={`area-readout${areaTooLarge ? " bad" : ""}`}>
            <span>Selected area</span>
            <strong>{fmtArea(areaKm2 * 1e6)}</strong>
          </div>
          {areaTooLarge && (
            <p className="alert error">
              This is above the {fmtArea(maxAreaKm2 * 1e6)} limit. Please draw a smaller area.
            </p>
          )}
          {!areaTooLarge && areaKm2 * 1e6 < MIN_RELIABLE_M2 && (
            <p className="alert warn">
              This area is very small. Terrain data is about 30 m resolution, so
              results are more reliable for areas of {fmtArea(MIN_RELIABLE_M2)} or more.
            </p>
          )}
          <div className="btn-row">
            <button className="btn" onClick={onStart} disabled={disabled}>
              Redraw
            </button>
            <button className="btn ghost" onClick={onClear} disabled={disabled}>
              Clear
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function UploadSection({ file, onFile, disabled }) {
  const inputRef = useRef(null);

  return (
    <section className="step">
      <h2>
        <span className="step-num">1</span> Upload a contour map
      </h2>
      <p className="help">
        Use your own KML/KMZ contour file. The whole map is analysed.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".kml,.kmz"
        hidden
        onChange={(event) => {
          onFile(event.target.files?.[0] ?? null);
          event.target.value = "";
        }}
      />

      <button className="btn" onClick={() => inputRef.current?.click()} disabled={disabled}>
        📂 {file ? "Choose a different file" : "Choose KML / KMZ file"}
      </button>

      {file && (
        <div className="file-chip">
          <span title={file.name}>{file.name}</span>
          <small>{(file.size / 1048576).toFixed(1)} MB</small>
          <button onClick={() => onFile(null)} disabled={disabled} aria-label="Remove file">
            ×
          </button>
        </div>
      )}
    </section>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function Settings({ params, onChange, disabled }) {
  const set = (key) => (event) => {
    const raw = event.target.value;
    onChange({ ...params, [key]: raw === "" ? "" : Number(raw) });
  };

  return (
    <section className="step">
      <h2>
        <span className="step-num">2</span> Settings
      </h2>

      <div className="fields">
        <Field label="Annual rainfall (mm)" hint="Leave blank to look it up automatically">
          <input type="number" min="1" step="10" placeholder="Auto" value={params.rainfall}
            onChange={set("rainfall")} disabled={disabled} />
        </Field>
        <Field label="Runoff coefficient (0–1)" hint="Blank = estimated from slope">
          <input type="number" min="0.05" max="1" step="0.05" placeholder="Auto" value={params.runoff}
            onChange={set("runoff")} disabled={disabled} />
        </Field>
        <Field
          label="Max land steepness (slope %)"
          hint="Ponds need fairly flat land. 8 means the ground rises 8 m over 100 m; steeper sites are skipped."
        >
          <input type="number" min="1" max="100" step="1" value={params.maxSlope}
            onChange={set("maxSlope")} disabled={disabled} />
        </Field>
        <Field label="Number of pond sites" hint="Best sites to return">
          <input type="number" min="1" max="20" step="1" value={params.maxPonds}
            onChange={set("maxPonds")} disabled={disabled} />
        </Field>
      </div>
    </section>
  );
}

export default function Sidebar({
  mode,
  onModeChange,
  area,
  file,
  onFile,
  params,
  onParamsChange,
  canRun,
  loading,
  elapsed,
  error,
  onRun,
  onCancel,
  children,
}) {
  return (
    <aside className="sidebar">
      <header className="brand">
        <div className="brand-mark">💧</div>
        <div>
          <h1>Pond Planner</h1>
          <p>Find the best pond site and how much water it can collect</p>
        </div>
      </header>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={mode === "area"} className={mode === "area" ? "active" : ""}
          onClick={() => onModeChange("area")} disabled={loading}>
          Draw an area
        </button>
        <button role="tab" aria-selected={mode === "file"} className={mode === "file" ? "active" : ""}
          onClick={() => onModeChange("file")} disabled={loading}>
          Upload KML/KMZ
        </button>
      </div>

      {mode === "area" ? (
        <AreaSection {...area} disabled={loading} />
      ) : (
        <UploadSection file={file} onFile={onFile} disabled={loading} />
      )}

      <Settings params={params} onChange={onParamsChange} disabled={loading} />

      <div className="run-bar">
        {error && <p className="alert error" role="alert">{error}</p>}

        {loading ? (
          <button className="btn danger wide" onClick={onCancel}>
            Cancel ({elapsed}s)
          </button>
        ) : (
          <button className="btn primary wide big" onClick={onRun} disabled={!canRun}>
            🔍 Find pond sites
          </button>
        )}

        {loading && (
          <p className="help center">
            {mode === "area"
              ? "Fetching terrain and analysing water flow… A new area can take up to a minute the first time; repeat areas are much faster."
              : "Reading contours and analysing water flow… large files can take about 30 s."}
          </p>
        )}
      </div>

      {children}
    </aside>
  );
}
