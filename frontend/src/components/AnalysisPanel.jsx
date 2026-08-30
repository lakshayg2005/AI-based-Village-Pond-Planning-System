function StatCard({ label, value, unit }) {
    return (
      <div className="stat-card">
        <span className="stat-label">{label}</span>
  
        <div className="stat-value">
          {value ?? "—"}
          {unit && <span className="stat-unit">{unit}</span>}
        </div>
      </div>
    );
  }
  
  function formatNumber(value, decimals = 2) {
    if (value === null || value === undefined) {
      return "—";
    }
  
    if (typeof value !== "number") {
      return value;
    }
  
    return value.toLocaleString(undefined, {
      maximumFractionDigits: decimals,
    });
  }
  
  function AnalysisPanel({ analysis }) {
    if (!analysis) {
      return (
        <div className="analysis-empty">
          <div className="analysis-empty-icon">🌄</div>
  
          <h2>No Analysis Yet</h2>
  
          <p>
            Upload a KML/KMZ contour file to generate terrain,
            slope, hydrology and pond-site analysis.
          </p>
        </div>
      );
    }
  
    const terrain = analysis.terrain || {};
    const dem = terrain.dem || {};
    const slope = terrain.slope || {};
    const validation = terrain.contour_validation || {};
    const hydrology = analysis.hydrology || {};
    const accumulation = analysis.accumulation || {};
    const suitability = analysis.suitability || {};
  
    return (
      <div className="analysis-panel">
        <div className="analysis-title">
          <div>
            <span className="eyebrow">ANALYSIS COMPLETE</span>
            <h2>Terrain Analysis</h2>
          </div>
  
          <span className="success-badge">✓ Success</span>
        </div>
  
        {/* TERRAIN */}
  
        <section className="analysis-section">
          <h3>🌄 Terrain</h3>
  
          <div className="stats-grid">
            <StatCard
              label="Contours"
              value={formatNumber(terrain.contour_count, 0)}
            />
  
            <StatCard
              label="Elevation Levels"
              value={formatNumber(terrain.elevation_levels, 0)}
            />
  
            <StatCard
              label="Minimum Elevation"
              value={formatNumber(terrain.min_elevation_m)}
              unit="m"
            />
  
            <StatCard
              label="Maximum Elevation"
              value={formatNumber(terrain.max_elevation_m)}
              unit="m"
            />
  
            <StatCard
              label="Grid Resolution"
              value={formatNumber(terrain.grid_resolution_m)}
              unit="m"
            />
  
            <StatCard
              label="Valid DEM Cells"
              value={formatNumber(dem.valid_cell_count, 0)}
            />
          </div>
        </section>
  
        {/* SLOPE */}
  
        <section className="analysis-section">
          <h3>📐 Slope</h3>
  
          <div className="stats-grid">
            <StatCard
              label="Minimum"
              value={formatNumber(slope.min_percent)}
              unit="%"
            />
    
            <StatCard
              label="Maximum"
              value={formatNumber(slope.max_percent)}
              unit="%"
            />
  
            <StatCard
              label="Mean"
              value={formatNumber(slope.mean_percent)}
              unit="%"
            />
          </div>
        </section>
  
        {/* VALIDATION */}
  
        <section className="analysis-section">
          <h3>✓ Contour Validation</h3>
  
          <div className="stats-grid">
            <StatCard
              label="RMSE"
              value={formatNumber(validation.rmse_m, 3)}
              unit="m"
            />
  
            <StatCard
              label="P95 Error"
              value={formatNumber(validation.p95_abs_error_m, 3)}
              unit="m"
            />
  
            <StatCard
              label="Maximum Error"
              value={formatNumber(validation.max_abs_error_m, 3)}
              unit="m"
            />
          </div>
        </section>
  
        {/* HYDROLOGY */}
  
        <section className="analysis-section">
          <h3>💧 Hydrology</h3>
  
          <div className="stats-grid">
            <StatCard
              label="Filled Cells"
              value={formatNumber(hydrology.filled_cell_count, 0)}
            />
  
            <StatCard
              label="Max Fill Depth"
              value={formatNumber(hydrology.max_fill_depth_m)}
              unit="m"
            />
  
            <StatCard
              label="Flowing Cells"
              value={formatNumber(hydrology.flowing_cell_count, 0)}
            />
  
            <StatCard
              label="No-Flow Cells"
              value={formatNumber(hydrology.no_flow_cell_count, 0)}
            />
          </div>
  
          <div className="algorithm-badge">
            D8 · Steepest Descent
          </div>
        </section>
  
        {/* FLOW ACCUMULATION */}
  
        <section className="analysis-section">
          <h3>🌊 Flow Accumulation</h3>
  
          <div className="stats-grid">
            <StatCard
              label="Minimum"
              value={formatNumber(accumulation.min, 0)}
            />
  
            <StatCard
              label="Maximum"
              value={formatNumber(accumulation.max, 0)}
            />
  
            <StatCard
              label="Mean"
              value={formatNumber(accumulation.mean)}
            />
  
            <StatCard
              label="Cells > 10"
              value={formatNumber(accumulation.cells_gt_10, 0)}
            />
  
            <StatCard
              label="Cells > 100"
              value={formatNumber(accumulation.cells_gt_100, 0)}
            />
  
            <StatCard
              label="Cells > 1000"
              value={formatNumber(accumulation.cells_gt_1000, 0)}
            />
          </div>
        </section>
  
        {/* SUITABILITY */}
  
        <section className="analysis-section">
          <h3>🎯 Pond Suitability</h3>
  
          <div className="stats-grid">
            <StatCard
              label="Max Slope"
              value={formatNumber(suitability.max_slope_percent)}
              unit="%"
            />
  
            <StatCard
              label="Minimum Accumulation"
              value={formatNumber(suitability.minimum_accumulation, 0)}
            />
  
            <StatCard
              label="Candidates"
              value={formatNumber(suitability.candidate_count, 0)}
            />
          </div>
        </section>
      </div>
    );
  }
  
  export default AnalysisPanel;