function MapToolbar({
  isDrawing,
  hasPolygon,
  loading,

  gridSize,
  contourInterval,

  onGridSizeChange,
  onContourIntervalChange,

  onStartDrawing,
  onClear,
  onGenerateContours,
}) {
  return (
    <div className="map-toolbar">
      {!isDrawing && !hasPolygon && (
        <button className="draw-button" onClick={onStartDrawing}>
          ✏️ Draw Polygon
        </button>
      )}

      {isDrawing && (
        <div className="drawing-status">
          <span>📍 Click points on the map</span>

          <small>Click the first point to close</small>
        </div>
      )}

      {hasPolygon && !isDrawing && (
        <>
          <div className="terrain-settings">
            <label>Grid Size</label>

            <select
              value={gridSize}
              onChange={(e) => onGridSizeChange(Number(e.target.value))}
            >
              <option value={20}>20 × 20</option>

              <option value={30}>30 × 30</option>

              <option value={50}>50 × 50</option>

              <option value={75}>75 × 75</option>

              <option value={100}>100 × 100</option>
            </select>

            <label>Contour Interval</label>

            <select
              value={contourInterval}
              onChange={(e) => onContourIntervalChange(Number(e.target.value))}
            >
              <option value={1}>1 m</option>

              <option value={2}>2 m</option>

              <option value={5}>5 m</option>

              <option value={10}>10 m</option>

              <option value={20}>20 m</option>

              <option value={50}>50 m</option>
            </select>
          </div>

          <button
            className="contour-button"
            onClick={onGenerateContours}
            disabled={loading}
          >
            {loading ? "⏳ Generating..." : "📐 Generate Contours"}
          </button>
        </>
      )}

      {(isDrawing || hasPolygon) && (
        <button className="clear-button" onClick={onClear}>
          🗑 Clear
        </button>
      )}
    </div>
  );
}

export default MapToolbar;
