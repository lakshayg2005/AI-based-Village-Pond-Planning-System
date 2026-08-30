function MapToolbar({
  isDrawing,
  hasPolygon,
  loading,
  onStartDrawing,
  onClear,
}) {
  return (
    <div className="map-toolbar">
      {!isDrawing && !hasPolygon && (
        <button
          className="draw-button"
          onClick={onStartDrawing}
        >
          ✏️ Draw Polygon
        </button>
      )}

      {isDrawing && (
        <div className="drawing-status">
          <span>📍 Click points on the map</span>

          <small>
            Click near the first point to close
          </small>
        </div>
      )}

      {hasPolygon && !isDrawing && (
        <div className="polygon-ready">
          <span>✓ Area selected</span>

          <small>
            Polygon analysis will be enabled in Part 4.
          </small>
        </div>
      )}

      {(isDrawing || hasPolygon) && (
        <button
          className="clear-button"
          onClick={onClear}
          disabled={loading}
        >
          🗑 Clear
        </button>
      )}
    </div>
  );
}

export default MapToolbar;