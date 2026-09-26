import { fmtArea, fmtDec, fmtInt, fmtVolume } from "../utils/geo";

const MONTH_LABELS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

function MonthlyChart({ monthly }) {
  const values = Object.values(monthly ?? {});
  const max = Math.max(...values, 1);

  return (
    <div className="monthly">
      <span className="monthly-title">Water collected by month (m³)</span>
      <svg viewBox="0 0 240 70" role="img" aria-label="Monthly runoff">
        {values.map((value, i) => {
          const h = (value / max) * 46;
          return (
            <g key={i}>
              <rect x={i * 20 + 3} y={52 - h} width="14" height={h} rx="2" fill="#0284c7">
                <title>{`${fmtInt(value)} m³`}</title>
              </rect>
              <text x={i * 20 + 10} y="66" textAnchor="middle" fontSize="8" fill="#64748b">
                {MONTH_LABELS[i]}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function PondCard({ candidate, selected, onSelect }) {
  const v = candidate.volume;

  return (
    <article className={`pond-card${selected ? " selected" : ""}`}>
      <button className="pond-head" onClick={onSelect} aria-expanded={selected}>
        <span className="rank">{candidate.rank}</span>
        <span className="pond-title">
          <strong>{v ? fmtVolume(v.annual_runoff_m3) : "—"}</strong>
          <small>water per year</small>
        </span>
        <span className="pond-catch">
          <strong>{fmtArea(candidate.catchment_area_m2 ?? 0)}</strong>
          <small>catchment</small>
        </span>
      </button>

      {selected && v && (
        <div className="pond-body">
          <dl>
            <div><dt>Suggested pond size</dt><dd>{fmtArea(v.recommended_pond.surface_area_m2)} × {fmtDec(v.recommended_pond.depth_m)} m deep</dd></div>
            <div><dt>Pond capacity</dt><dd>{fmtVolume(v.recommended_pond.storage_capacity_m3)}</dd></div>
            <div><dt>Fills per year</dt><dd>~{fmtDec(v.times_filled_per_year)}×</dd></div>
            <div><dt>Water (litres)</dt><dd>{fmtInt(v.annual_runoff_litres)} L</dd></div>
            <div><dt>Runoff coefficient</dt><dd>{fmtDec(v.runoff_coefficient)}</dd></div>
            <div><dt>Ground slope</dt><dd>{fmtDec(candidate.slope_percent)}%</dd></div>
            <div><dt>Elevation</dt><dd>{fmtDec(candidate.elevation_m)} m</dd></div>
            <div><dt>Location</dt><dd>{candidate.latitude.toFixed(5)}, {candidate.longitude.toFixed(5)}</dd></div>
          </dl>
          <MonthlyChart monthly={v.monthly_runoff_m3} />
        </div>
      )}
    </article>
  );
}

function downloadJson(result) {
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "pond-analysis.json";
  link.click();
  URL.revokeObjectURL(url);
}

export default function ResultsPanel({ result, selectedRank, onSelectRank }) {
  const candidates = result.analysis?.candidates ?? [];
  const rainfall = result.rainfall;
  const best = candidates[0];

  return (
    <section className="results">
      <h2>
        <span className="step-num done">3</span> Results
      </h2>

      {candidates.length === 0 ? (
        <p className="alert warn">
          No suitable pond site was found. Try a larger area or raise the maximum slope.
        </p>
      ) : (
        <>
          <div className="summary">
            <div className="stat hero">
              <span>Top-ranked site collects</span>
              <strong>{fmtVolume(best.volume?.annual_runoff_m3 ?? 0)}</strong>
              <small>per year from {fmtArea(best.catchment_area_m2 ?? 0)} of land</small>
            </div>
            <div className="stat">
              <span>Pond sites</span>
              <strong>{candidates.length}</strong>
            </div>
            {rainfall && (
              <div className="stat">
                <span>Rainfall</span>
                <strong>{fmtInt(rainfall.annual_mm)} mm</strong>
              </div>
            )}
          </div>

          {rainfall && !rainfall.measured && rainfall.source !== "User supplied" && (
            <p className="alert warn">{rainfall.source}</p>
          )}

          <div className="pond-list">
            {candidates.map((candidate) => (
              <PondCard
                key={candidate.rank}
                candidate={candidate}
                selected={candidate.rank === selectedRank}
                onSelect={() => onSelectRank(candidate.rank === selectedRank ? null : candidate.rank)}
              />
            ))}
          </div>
        </>
      )}

      <details className="about">
        <summary>How this was calculated</summary>
        <ul>
          {result.terrain?.source && (
            <li>Terrain: {result.terrain.source}, {result.terrain.grid_resolution_m} m grid.</li>
          )}
          <li>Rainwater flow is traced downhill (D8) to find the land draining to each site.</li>
          <li>Water per year = runoff coefficient × annual rainfall × catchment area.</li>
          {rainfall && <li>Rainfall: {rainfall.source}{rainfall.years !== "n/a" ? ` (${rainfall.years} average)` : ""}.</li>}
          <li>Pond size assumes a surface of 3% of the catchment and a tapered profile.</li>
        </ul>
      </details>

      <button className="btn ghost wide" onClick={() => downloadJson(result)}>
        ⬇ Download full result (JSON)
      </button>
    </section>
  );
}
