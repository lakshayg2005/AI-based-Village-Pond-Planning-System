import JSZip from "jszip";

/**
 * Parse a KML/KMZ contour file directly in the browser.
 *
 * Returns:
 * {
 *   type: "FeatureCollection",
 *   features: [
 *     {
 *       type: "Feature",
 *       properties: {
 *         elevation: 267
 *       },
 *       geometry: {
 *         type: "LineString",
 *         coordinates: [[lng, lat], ...]
 *       }
 *     }
 *   ]
 * }
 */

export async function parseContourFile(file) {
  if (!file) {
    throw new Error("No contour file provided.");
  }

  const fileName = file.name.toLowerCase();

  let kmlText;

  if (fileName.endsWith(".kml")) {
    kmlText = await file.text();
  } else if (fileName.endsWith(".kmz")) {
    kmlText = await extractKMLFromKMZ(file);
  } else {
    throw new Error("Only .kml and .kmz files are supported.");
  }

  return parseKML(kmlText);
}

/**
 * Extract the KML file from a KMZ archive.
 */
async function extractKMLFromKMZ(file) {
  const zip = await JSZip.loadAsync(file);

  const kmlFiles = Object.keys(zip.files).filter(
    (name) =>
      name.toLowerCase().endsWith(".kml") &&
      !zip.files[name].dir
  );

  if (kmlFiles.length === 0) {
    throw new Error("No KML file found inside the KMZ archive.");
  }

  // Prefer doc.kml when available.
  const kmlFile =
    kmlFiles.find(
      (name) => name.toLowerCase() === "doc.kml"
    ) || kmlFiles[0];

  return await zip.files[kmlFile].async("text");
}

/**
 * Parse KML XML and extract LineString contours.
 */
function parseKML(kmlText) {
  const parser = new DOMParser();

  const xml = parser.parseFromString(
    kmlText,
    "application/xml"
  );

  const parserError = xml.querySelector("parsererror");

  if (parserError) {
    throw new Error("Invalid KML XML.");
  }

  const features = [];

  const placemarks = Array.from(
    xml.getElementsByTagName("Placemark")
  );

  placemarks.forEach((placemark, index) => {
    const lineStrings = Array.from(
      placemark.getElementsByTagName("LineString")
    );

    lineStrings.forEach((lineString) => {
      const coordinatesElement =
        lineString.getElementsByTagName("coordinates")[0];

      if (!coordinatesElement) {
        return;
      }

      const coordinatesText =
        coordinatesElement.textContent?.trim();

      if (!coordinatesText) {
        return;
      }

      const coordinates = coordinatesText
        .split(/\s+/)
        .map((coordinate) => {
          const parts = coordinate.split(",");

          const lng = Number(parts[0]);
          const lat = Number(parts[1]);

          if (
            !Number.isFinite(lng) ||
            !Number.isFinite(lat)
          ) {
            return null;
          }

          return [lng, lat];
        })
        .filter(Boolean);

      if (coordinates.length < 2) {
        return;
      }

      const nameElement =
        placemark.getElementsByTagName("name")[0];

      const name =
        nameElement?.textContent?.trim() ||
        `Contour ${index + 1}`;

      const elevation =
        extractElevation(
          placemark,
          name
        );

      features.push({
        type: "Feature",
        properties: {
          name,
          elevation,
        },
        geometry: {
          type: "LineString",
          coordinates,
        },
      });
    });
  });

  if (features.length === 0) {
    throw new Error(
      "No contour LineString features were found in the file."
    );
  }

  console.log(
    `Parsed ${features.length} contour lines.`
  );

  return {
    type: "FeatureCollection",
    features,
  };
}

/**
 * Try to extract elevation from common KML formats.
 */
function extractElevation(placemark, name) {
  // 1. Look for <SimpleData name="elevation">
  const simpleDataElements = Array.from(
    placemark.getElementsByTagName("SimpleData")
  );

  for (const element of simpleDataElements) {
    const fieldName =
      element.getAttribute("name")?.toLowerCase();

    if (
      fieldName === "elevation" ||
      fieldName === "elev" ||
      fieldName === "height" ||
      fieldName === "z"
    ) {
      const value = Number(
        element.textContent?.trim()
      );

      if (Number.isFinite(value)) {
        return value;
      }
    }
  }

  // 2. Look for <Data name="elevation">
  const dataElements = Array.from(
    placemark.getElementsByTagName("Data")
  );

  for (const element of dataElements) {
    const fieldName =
      element.getAttribute("name")?.toLowerCase();

    if (
      fieldName === "elevation" ||
      fieldName === "elev" ||
      fieldName === "height" ||
      fieldName === "z"
    ) {
      const valueElement =
        element.getElementsByTagName("value")[0];

      const value = Number(
        valueElement?.textContent?.trim()
      );

      if (Number.isFinite(value)) {
        return value;
      }
    }
  }

  // 3. Try to extract elevation from the Placemark name.
  //
  // Example:
  // "Contour 267"
  // "Elevation: 267m"
  // "267"
  const match = name.match(
    /(?:elevation|elev|height|contour)?\s*[:=_-]?\s*(-?\d+(?:\.\d+)?)\s*(?:m|meter|meters)?/i
  );

  if (match) {
    const value = Number(match[1]);

    if (Number.isFinite(value)) {
      return value;
    }
  }

  return null;
}

/**
 * Calculate geographic bounds.
 */
export function getContourBounds(geojson) {
  if (
    !geojson ||
    geojson.type !== "FeatureCollection"
  ) {
    return null;
  }

  const bounds = {
    minLat: Infinity,
    maxLat: -Infinity,
    minLng: Infinity,
    maxLng: -Infinity,
  };

  geojson.features.forEach((feature) => {
    const coordinates =
      feature?.geometry?.coordinates;

    if (!coordinates) {
      return;
    }

    coordinates.forEach(([lng, lat]) => {
      if (
        !Number.isFinite(lng) ||
        !Number.isFinite(lat)
      ) {
        return;
      }

      bounds.minLng = Math.min(
        bounds.minLng,
        lng
      );

      bounds.maxLng = Math.max(
        bounds.maxLng,
        lng
      );

      bounds.minLat = Math.min(
        bounds.minLat,
        lat
      );

      bounds.maxLat = Math.max(
        bounds.maxLat,
        lat
      );
    });
  });

  if (
    bounds.minLat === Infinity ||
    bounds.minLng === Infinity
  ) {
    return null;
  }

  return bounds;
}
