const EARTH_RADIUS_M = 6378137;

/**
 * Area of a polygon on the sphere, in km².
 * `points` is an array of { lat, lng }; the ring need not be closed.
 */
export function polygonAreaKm2(points) {
  if (!points || points.length < 3) return 0;

  const rad = (deg) => (deg * Math.PI) / 180;
  let sum = 0;

  for (let i = 0; i < points.length; i++) {
    const p1 = points[i];
    const p2 = points[(i + 1) % points.length];
    sum +=
      rad(p2.lng - p1.lng) *
      (2 + Math.sin(rad(p1.lat)) + Math.sin(rad(p2.lat)));
  }

  return (Math.abs(sum) * EARTH_RADIUS_M * EARTH_RADIUS_M) / 2 / 1e6;
}

/** Closed GeoJSON ring ([lng, lat] pairs) from vertex objects. */
export function toClosedRing(points) {
  const ring = points.map((p) => [p.lng, p.lat]);
  ring.push(ring[0]);
  return ring;
}

/** Green (low) → yellow → red (high) for contour elevation. */
export function elevationColor(value, min, max) {
  if (!Number.isFinite(value) || max <= min) return "#2e7d32";
  const t = Math.min(1, Math.max(0, (value - min) / (max - min)));
  const stops = [
    [46, 125, 50],
    [139, 195, 74],
    [253, 216, 53],
    [251, 140, 0],
    [198, 40, 40],
  ];
  const scaled = t * (stops.length - 1);
  const i = Math.min(Math.floor(scaled), stops.length - 2);
  const f = scaled - i;
  const rgb = stops[i].map((c, k) => Math.round(c + (stops[i + 1][k] - c) * f));
  return `rgb(${rgb.join(",")})`;
}

/** Light-to-dark blue scale for water volume, t in [0, 1]. */
export function volumeColor(t) {
  const from = [191, 219, 254];
  const to = [30, 58, 138];
  const c = Math.min(1, Math.max(0, t));
  const rgb = from.map((v, k) => Math.round(v + (to[k] - v) * c));
  return `rgb(${rgb.join(",")})`;
}

const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export const fmtInt = (value) => number.format(value ?? 0);
export const fmtDec = (value) => decimal.format(value ?? 0);

export function fmtVolume(m3) {
  if (m3 >= 1e6) return `${decimal.format(m3 / 1e6)} million m³`;
  return `${number.format(m3)} m³`;
}

export function fmtArea(m2) {
  if (m2 >= 10000) return `${decimal.format(m2 / 10000)} ha`;
  return `${number.format(m2)} m²`;
}
