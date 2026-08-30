import { useRef, useState } from "react";

function FileUpload({ onAnalyze, loading }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [localError, setLocalError] = useState(null);

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0];

    setLocalError(null);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    const name = selectedFile.name.toLowerCase();

    if (!name.endsWith(".kml") && !name.endsWith(".kmz")) {
      setFile(null);
      setLocalError("Please select a .kml or .kmz file.");
      return;
    }

    setFile(selectedFile);
  };

  const handleAnalyze = async () => {
    if (!file) {
      setLocalError("Please select a KML or KMZ file first.");
      return;
    }

    setLocalError(null);
    await onAnalyze(file);
  };

  const clearFile = () => {
    setFile(null);
    setLocalError(null);

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div className="file-upload-panel">
      <div className="file-upload-header">
        <span className="file-upload-icon">📁</span>

        <div>
          <h3>Upload Terrain Data</h3>
          <p>KML or KMZ contour file</p>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".kml,.kmz,application/vnd.google-earth.kml+xml,application/vnd.google-earth.kmz"
        onChange={handleFileChange}
        hidden
      />

      <button
        className="select-file-button"
        onClick={() => inputRef.current?.click()}
        disabled={loading}
      >
        📂 Choose KML / KMZ
      </button>

      {file && (
        <div className="selected-file">
          <div>
            <strong>{file.name}</strong>

            <small>
              {(file.size / (1024 * 1024)).toFixed(2)} MB
            </small>
          </div>

          <button
            className="remove-file-button"
            onClick={clearFile}
            disabled={loading}
          >
            ×
          </button>
        </div>
      )}

      {localError && (
        <div className="upload-error">
          {localError}
        </div>
      )}

      <button
        className="analyze-file-button"
        onClick={handleAnalyze}
        disabled={!file || loading}
      >
        {loading ? "⏳ Analyzing Terrain..." : "🔍 Analyze Terrain"}
      </button>
    </div>
  );
}

export default FileUpload;