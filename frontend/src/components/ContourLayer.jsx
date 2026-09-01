import { useEffect } from "react";
import { useMap } from "@vis.gl/react-google-maps";

/**
 * Returns a color based on contour elevation.
 *
 * Low elevation  -> Green
 * Mid elevation  -> Yellow / Orange
 * High elevation -> Red
 */
function getElevationColor(
  elevation,
  minElevation,
  maxElevation
) {
  const min = Number(minElevation);
  const max = Number(maxElevation);
  const value = Number(elevation);

  if (
    !Number.isFinite(value) ||
    !Number.isFinite(min) ||
    !Number.isFinite(max)
  ) {
    return "#795548";
  }

  // Avoid division by zero when all contours have the same elevation.
  const range = max - min;

  if (range <= 0) {
    return "#2E7D32";
  }

  // Normalize elevation to 0–1.
  const t = Math.max(
    0,
    Math.min(1, (value - min) / range)
  );

  /*
   * Terrain color stops:
   *
   * 0.00 = dark green
   * 0.25 = green
   * 0.50 = yellow
   * 0.75 = orange
   * 1.00 = red
   */
  const stops = [
    {
      position: 0.0,
      color: [46, 125, 50],
    },
    {
      position: 0.25,
      color: [139, 195, 74],
    },
    {
      position: 0.5,
      color: [255, 235, 59],
    },
    {
      position: 0.75,
      color: [255, 152, 0],
    },
    {
      position: 1.0,
      color: [198, 40, 40],
    },
  ];

  let lower = stops[0];
  let upper = stops[stops.length - 1];

  for (let i = 0; i < stops.length - 1; i++) {
    if (
      t >= stops[i].position &&
      t <= stops[i + 1].position
    ) {
      lower = stops[i];
      upper = stops[i + 1];
      break;
    }
  }

  const localT =
    (t - lower.position) /
    (upper.position - lower.position);

  const r = Math.round(
    lower.color[0] +
      (upper.color[0] - lower.color[0]) * localT
  );

  const g = Math.round(
    lower.color[1] +
      (upper.color[1] - lower.color[1]) * localT
  );

  const b = Math.round(
    lower.color[2] +
      (upper.color[2] - lower.color[2]) * localT
  );

  return `rgb(${r}, ${g}, ${b})`;
}

function ContourLayer({
  contours,
  visible = true,
}) {
  const map = useMap();

  useEffect(() => {
    if (!map || !contours || !visible) {
      return undefined;
    }

    if (
      contours.type !== "FeatureCollection" ||
      !Array.isArray(contours.features)
    ) {
      return undefined;
    }

    /*
     * -------------------------------------------------------
     * Find elevation range
     * -------------------------------------------------------
     */
    const elevations = contours.features
      .map(
        (feature) =>
          Number(feature?.properties?.elevation)
      )
      .filter((value) =>
        Number.isFinite(value)
      );

    if (elevations.length === 0) {
      console.warn(
        "No valid contour elevations found."
      );
      return undefined;
    }

    const minElevation = Math.min(...elevations);
    const maxElevation = Math.max(...elevations);

    console.log(
      "========== CONTOUR ELEVATION COLORS =========="
    );
    console.log(
      "Contour count:",
      contours.features.length
    );
    console.log(
      "Minimum elevation:",
      minElevation
    );
    console.log(
      "Maximum elevation:",
      maxElevation
    );

    const polylines = [];

    const bounds =
      new google.maps.LatLngBounds();

    /*
     * -------------------------------------------------------
     * Render every contour
     * -------------------------------------------------------
     */
    contours.features.forEach(
      (feature) => {
        if (
          feature?.geometry?.type !==
          "LineString"
        ) {
          return;
        }

        const coordinates =
          feature.geometry.coordinates;

        if (
          !Array.isArray(coordinates) ||
          coordinates.length < 2
        ) {
          return;
        }

        const path = [];

        coordinates.forEach(
          ([lng, lat]) => {
            if (
              !Number.isFinite(lng) ||
              !Number.isFinite(lat)
            ) {
              return;
            }

            const point = {
              lat,
              lng,
            };

            path.push(point);
            bounds.extend(point);
          }
        );

        if (path.length < 2) {
          return;
        }

        const elevation =
          Number(
            feature.properties?.elevation
          );

        const strokeColor =
          getElevationColor(
            elevation,
            minElevation,
            maxElevation
          );

        /*
         * Make higher contours slightly thicker.
         *
         * This is optional, but makes elevation
         * differences easier to see.
         */
        const normalizedElevation =
          Number.isFinite(elevation) &&
          maxElevation > minElevation
            ? (elevation - minElevation) /
              (maxElevation - minElevation)
            : 0.5;

        const strokeWeight =
          1.2 +
          normalizedElevation * 1.0;

        const polyline =
          new google.maps.Polyline({
            map,
            path,
            strokeColor,
            strokeOpacity: 0.9,
            strokeWeight,
            clickable: false,
            zIndex: 5,
          });

        polyline.contourElevation =
          elevation;

        polylines.push(polyline);
      }
    );

    console.log(
      `Rendered ${polylines.length} elevation-colored contour lines.`
    );

    /*
     * -------------------------------------------------------
     * Fit map to contour extent
     * -------------------------------------------------------
     */
    if (
      polylines.length > 0 &&
      !bounds.isEmpty()
    ) {
      map.fitBounds(bounds, 60);
    }

    /*
     * -------------------------------------------------------
     * Cleanup
     * -------------------------------------------------------
     */
    return () => {
      polylines.forEach(
        (polyline) => {
          polyline.setMap(null);
        }
      );
    };
  }, [
    map,
    contours,
    visible,
  ]);

  return null;
}

export default ContourLayer;    