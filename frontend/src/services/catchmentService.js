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

  // Must match the FastAPI parameter name.
  formData.append("contour_map", file);

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
    console.error("Catchment API error:", response.status, data);

    let detailMessage;

    if (Array.isArray(data?.detail)) {
      detailMessage = data.detail
        .map((item) => {
          if (typeof item === "string") {
            return item;
          }

          if (item?.msg) {
            const location = Array.isArray(item.loc)
              ? item.loc.join(" → ")
              : "";

            return location
              ? `${location}: ${item.msg}`
              : item.msg;
          }

          return JSON.stringify(item);
        })
        .join("; ");
    } else if (typeof data?.detail === "string") {
      detailMessage = data.detail;
    } else if (typeof data?.message === "string") {
      detailMessage = data.message;
    } else {
      detailMessage = `Analysis failed with status ${response.status}`;
    }

    throw new Error(detailMessage);
  }

  if (data.status !== "success") {
    throw new Error(data.message || "Terrain analysis failed.");
  }

  return data;
}