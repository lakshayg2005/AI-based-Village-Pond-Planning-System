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
            <div><dt>Land steepness</dt><dd>{fmtDec(candidate.slope_percent)}%</dd></div>
            <div><dt>Elevation</dt><dd>{fmtDec(candidate.elevation_m)} m</dd></div>
            <div><dt>Location</dt><dd>{candidate.latitude.toFixed(5)}, {candidate.longitude.toFixed(5)}</dd></div>
          </dl>
          <MonthlyChart monthly={v.monthly_runoff_m3} />
        </div>
      )}
    </article>
  );
}

function Method({ result, best, rainfall }) {
  const pond = best?.volume?.recommended_pond;
  const depth = pond?.depth_m;
  const share =
    pond && best.catchment_area_m2
      ? Math.round((pond.surface_area_m2 / best.catchment_area_m2) * 100)
      : null;

  return (
    <details className="about">
      <summary>How this was calculated &amp; assumptions</summary>

      <h4>Method</h4>
      <ol>
        <li>
          {result.terrain?.source
            ? `Ground heights come from ${result.terrain.source}, on a ${result.terrain.grid_resolution_m} m grid.`
            : `Ground heights are rebuilt from your contour lines on a ${result.terrain?.grid_resolution_m} m grid.`}
        </li>
        <li>Rain is traced downhill from every cell (D8 steepest descent) to find where water gathers.</li>
        <li>Sites on gentle slopes where a lot of water gathers are ranked highest.</li>
        <li>The catchment of a site is all the land whose rain flows to it.</li>
        <li>
          Water per year = runoff coefficient × annual rainfall × catchment area.
          {rainfall && ` Rainfall: ${rainfall.source}${rainfall.years !== "n/a" ? `, ${rainfall.years} average` : ""}.`}
        </li>
      </ol>

      <h4>Assumptions (and why)</h4>
      <ul>
        {depth && (
          <li>
            <b>Pond depth {depth} m.</b> A typical farm pond: deep enough to
            keep water through the dry season and lose less to evaporation,
            yet shallow enough to dig with ordinary machinery.
          </li>
        )}
        {share && (
          <li>
            <b>Pond surface = {share}% of its catchment.</b> A common
            rule of thumb for farm ponds; a bigger pond than the catchment can
            fill would sit empty.
          </li>
        )}
        <li>
          <b>Pond volume = half of surface × depth.</b> Pond sides slope
          inwards, so a real pond holds about half of a straight-sided box.
        </li>
        <li>
          <b>Runoff coefficient 0.25 (flat) to 0.55 (steep).</b> We have no
          soil or land-cover data, so it is estimated from the catchment
          slope: steeper land sheds more of the rain. You can enter your own
          value in Settings.
        </li>
        <li>
          <b>Rainfall is a long-term average.</b> A single year can be much
          wetter or drier, especially with monsoon rains.
        </li>
        <li>
          <b>Terrain is about 30 m resolution.</b> Small features such as
          field bunds, roads, drains and existing ponds are not visible, so
          check candidate sites on the ground before building.
        </li>
        <li>
          <b>Water per year is the total runoff reaching the site,</b> not the
          pond size. Evaporation and seepage are not subtracted, and the
          pond can refill several times a year.
        </li>
      </ul>
    </details>
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

      <Method result={result} best={best} rainfall={rainfall} />

      <button className="btn ghost wide" onClick={() => downloadJson(result)}>
        ⬇ Download full result (JSON)
      </button>
    </section>
  );
}
