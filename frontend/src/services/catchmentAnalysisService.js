import { analyzeContourFile } from "./catchmentService";
import { analyzeContourFileV2 } from "./catchmentV2Service";

/**
 * Change this ONE value to switch implementations.
 *
 * "v1" -> existing pipeline
 * "v2" -> depression-aware pond pipeline
 */
export const CATCHMENT_VERSION = "v1";

/**
 * Run the selected catchment analysis implementation.
 */
export async function analyzeContourFileByVersion(file) {
  if (!file) {
    throw new Error("No contour file provided.");
  }

  if (CATCHMENT_VERSION === "v2") {
    return await analyzeContourFileV2(file);
  }

  return await analyzeContourFile(file);
}