const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Analyze an uploaded KML/KMZ contour file.
 *
 * Backend:
 * POST /api/catchment/analyze
 * Content-Type: multipart/form-data
 */
export async function analyzeContourFile(file) {
  if (!file) {
    throw new Error("Please select a KML or KMZ file.");
  }

  const fileName = file.name.toLowerCase();

  if (!fileName.endsWith(".kml") && !fileName.endsWith(".kmz")) {
    throw new Error("Only KML and KMZ files are supported.");
  }

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/api/catchment/analyze`, {
    method: "POST",
    body: formData,
  });

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error(
      `Backend returned an invalid response (${response.status}).`
    );
  }

  if (!response.ok) {
    throw new Error(
      data?.detail ||
        data?.message ||
        `Analysis failed with status ${response.status}`
    );
  }

  if (data.status !== "success") {
    throw new Error(data.message || "Terrain analysis failed.");
  }

  return data;
}