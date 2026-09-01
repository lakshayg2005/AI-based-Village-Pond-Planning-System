const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

/**
 * Run the V2 depression-aware catchment analysis.
 *
 * Backend endpoint:
 * POST /api/v2/catchment/analyze
 */
export async function analyzeContourFileV2(
  file,
  options = {}
) {
  if (!file) {
    throw new Error("No contour file provided.");
  }

  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams();

  if (options.gridResolutionM != null) {
    params.set(
      "grid_resolution_m",
      String(options.gridResolutionM)
    );
  }

  if (options.sampleSpacingM != null) {
    params.set(
      "sample_spacing_m",
      String(options.sampleSpacingM)
    );
  }

  if (options.interpolationMethod) {
    params.set(
      "interpolation_method",
      options.interpolationMethod
    );
  }

  if (options.minimumDepressionDepthM != null) {
    params.set(
      "minimum_depression_depth_m",
      String(options.minimumDepressionDepthM)
    );
  }

  if (options.minimumDepressionAreaM2 != null) {
    params.set(
      "minimum_depression_area_m2",
      String(options.minimumDepressionAreaM2)
    );
  }

  if (options.maxSlopePercent != null) {
    params.set(
      "max_slope_percent",
      String(options.maxSlopePercent)
    );
  }

  if (options.maxCandidates != null) {
    params.set(
      "max_candidates",
      String(options.maxCandidates)
    );
  }

  const query = params.toString();

  const url =
    `${API_BASE_URL}/api/v2/catchment/analyze` +
    (query ? `?${query}` : "");

  console.log(
    "========================================"
  );
  console.log("V2 CATCHMENT ANALYSIS");
  console.log("URL:", url);
  console.log("File:", file.name);
  console.log(
    "========================================"
  );

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let message =
      "V2 catchment analysis failed.";

    try {
      const error = await response.json();

      if (error?.detail) {
        message =
          typeof error.detail === "string"
            ? error.detail
            : JSON.stringify(error.detail);
      }
    } catch {
      // Backend did not return JSON.
    }

    throw new Error(
      `${message} (HTTP ${response.status})`
    );
  }

  const result = await response.json();

  console.log(
    "========== V2 RESPONSE =========="
  );
  console.log(result);

  return result;
}