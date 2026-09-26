import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { elevationColor, fmtArea, fmtVolume, volumeColor } from "../utils/geo";
import PlaceSearch from "./PlaceSearch";

const INDIA_CENTRE = [21.0, 80.0];
const CLOSE_RADIUS_PX = 14;

const AREA_STYLE = { color: "#d97706", weight: 2.5, dashArray: "6 5", fillColor: "#f59e0b", fillOpacity: 0.08 };
const AREA_TOO_BIG = { ...AREA_STYLE, color: "#dc2626", fillColor: "#dc2626" };

/** Volume → 0..1 within the current result set, for the colour scale. */
function volumeScale(candidates) {
  const values = candidates
    .map((c) => c.volume?.annual_runoff_m3)
    .filter((v) => Number.isFinite(v));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (value) => (max > min ? (value - min) / (max - min) : 0.6);
}

function pondIcon(rank, selected) {
  return L.divIcon({
    className: "",
    html: `<div class="pond-pin${selected ? " selected" : ""}">${rank}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function popupHtml(candidate) {
  const v = candidate.volume;
  const rows = [
    ["Catchment", fmtArea(candidate.catchment_area_m2 ?? 0)],
    v && ["Water per year", fmtVolume(v.annual_runoff_m3)],
    v && ["Suggested pond", fmtVolume(v.recommended_pond.storage_capacity_m3)],
    ["Ground slope", `${candidate.slope_percent.toFixed(1)}%`],
    ["Elevation", `${candidate.elevation_m.toFixed(1)} m`],
  ].filter(Boolean);

  return (
    `<div class="pond-popup"><strong>Pond site #${candidate.rank}</strong>` +
    rows.map(([k, val]) => `<div><span>${k}</span><b>${val}</b></div>`).join("") +
    "</div>"
  );
}

export default function MapView({
  drawing,
  vertices,
  areaTooLarge,
  onAddVertex,
  onFinishDrawing,
  contours,
  result,
  selectedRank,
  onSelectRank,
  layers,
  onToggleLayer,
  fitTarget,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const groups = useRef({});
  const handlers = useRef({});

  // Always call the latest callbacks from long-lived Leaflet listeners.
  useEffect(() => {
    handlers.current = { drawing, vertices, onAddVertex, onFinishDrawing, onSelectRank };
  });

  // ---- create the map once ------------------------------------------------
  useEffect(() => {
    const map = L.map(containerRef.current, {
      center: INDIA_CENTRE,
      zoom: 5,
      preferCanvas: true,
      zoomControl: false,
    });

    L.control.zoom({ position: "bottomright" }).addTo(map);

    const street = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    });
    const satellite = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" }
    );
    street.addTo(map);
    L.control.layers({ Street: street, Satellite: satellite }, null, { position: "topright" }).addTo(map);
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);

    for (const name of ["draw", "contours", "catchments", "footprints", "ponds"]) {
      groups.current[name] = L.layerGroup().addTo(map);
    }

    map.on("click", (event) => {
      const h = handlers.current;
      if (!h.drawing) return;

      // Clicking near the first vertex closes the polygon.
      if (h.vertices.length >= 3) {
        const first = map.latLngToContainerPoint(h.vertices[0]);
        if (first.distanceTo(event.containerPoint) <= CLOSE_RADIUS_PX) {
          h.onFinishDrawing();
          return;
        }
      }
      h.onAddVertex({ lat: event.latlng.lat, lng: event.latlng.lng });
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ---- crosshair cursor while drawing --------------------------------------
  useEffect(() => {
    containerRef.current?.classList.toggle("is-drawing", drawing);
  }, [drawing]);

  // ---- selected area / drawing in progress ---------------------------------
  useEffect(() => {
    const group = groups.current.draw;
    if (!group) return;
    group.clearLayers();
    if (vertices.length === 0) return;

    const style = areaTooLarge ? AREA_TOO_BIG : AREA_STYLE;

    if (drawing) {
      L.polyline(vertices, { ...style, dashArray: "4 6" }).addTo(group);
    } else if (vertices.length >= 3) {
      L.polygon(vertices, style).addTo(group);
    }

    if (drawing) {
      vertices.forEach((vertex, index) => {
        L.circleMarker(vertex, {
          radius: index === 0 && vertices.length >= 3 ? 8 : 5,
          color: "#fff",
          weight: 2,
          fillColor: index === 0 ? "#16a34a" : style.color,
          fillOpacity: 1,
        }).addTo(group);
      });
    }
  }, [vertices, drawing, areaTooLarge]);

  // ---- uploaded contour lines ----------------------------------------------
  useEffect(() => {
    const group = groups.current.contours;
    if (!group) return;
    group.clearLayers();
    if (!contours?.features?.length) return;

    const elevations = contours.features
      .map((f) => Number(f.properties?.elevation))
      .filter(Number.isFinite);
    const min = Math.min(...elevations);
    const max = Math.max(...elevations);

    L.geoJSON(contours, {
      style: (feature) => ({
        color: elevationColor(Number(feature.properties?.elevation), min, max),
        weight: 1.2,
        opacity: 0.85,
      }),
      interactive: false,
    }).addTo(group);
  }, [contours]);

  // ---- analysis result: catchments, pond footprints and pins ---------------
  useEffect(() => {
    const { catchments, footprints, ponds } = groups.current;
    if (!catchments) return;
    catchments.clearLayers();
    footprints.clearLayers();
    ponds.clearLayers();

    const candidates = result?.analysis?.candidates ?? [];
    if (candidates.length === 0) return;

    const scale = volumeScale(candidates);
    const byRank = new Map(candidates.map((c) => [c.rank, c]));

    for (const catchment of result.analysis.catchments) {
      const candidate = byRank.get(catchment.rank);
      const selected = catchment.rank === selectedRank;
      const t = scale(candidate?.volume?.annual_runoff_m3 ?? 0);

      L.geoJSON(catchment.geometry, {
        style: {
          color: selected ? "#0f172a" : volumeColor(Math.min(1, t + 0.25)),
          weight: selected ? 3 : 1.5,
          fillColor: volumeColor(t),
          fillOpacity: selected ? 0.55 : 0.32,
        },
      })
        .on("click", () => handlers.current.onSelectRank(catchment.rank))
        .addTo(catchments);
    }

    for (const candidate of candidates) {
      const selected = candidate.rank === selectedRank;
      const centre = [candidate.latitude, candidate.longitude];
      const pondArea = candidate.volume?.recommended_pond?.surface_area_m2;

      if (pondArea) {
        L.circle(centre, {
          radius: Math.sqrt(pondArea / Math.PI),
          color: "#0369a1",
          weight: 2,
          fillColor: "#38bdf8",
          fillOpacity: 0.7,
          interactive: false,
        }).addTo(footprints);
      }

      L.marker(centre, {
        icon: pondIcon(candidate.rank, selected),
        zIndexOffset: selected ? 1000 : 0,
        riseOnHover: true,
      })
        .bindPopup(popupHtml(candidate), { closeButton: false })
        .on("click", () => handlers.current.onSelectRank(candidate.rank))
        .addTo(ponds);
    }
  }, [result, selectedRank]);

  // ---- layer visibility -----------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const visibility = {
      contours: layers.contours,
      catchments: layers.catchments,
      footprints: layers.ponds,
      ponds: layers.ponds,
    };
    for (const [name, visible] of Object.entries(visibility)) {
      const group = groups.current[name];
      if (!group) continue;
      if (visible && !map.hasLayer(group)) group.addTo(map);
      if (!visible && map.hasLayer(group)) map.removeLayer(group);
    }
  }, [layers]);

  // ---- move the camera --------------------------------------------------------
  useEffect(() => {
    if (fitTarget?.bounds && mapRef.current) {
      mapRef.current.fitBounds(fitTarget.bounds, { padding: [30, 30], maxZoom: 17 });
    }
  }, [fitTarget]);

  // ---- leaflet needs a nudge when the window/sidebar size changes ------------
  useEffect(() => {
    const observer = new ResizeObserver(() => mapRef.current?.invalidateSize());
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const candidates = result?.analysis?.candidates ?? [];
  const volumes = candidates.map((c) => c.volume?.annual_runoff_m3).filter(Number.isFinite);

  return (
    <div className="map-wrap">
      <div ref={containerRef} className="map" />

      <PlaceSearch onSelect={(bounds) => mapRef.current?.fitBounds(bounds, { maxZoom: 16 })} />

      <div className="map-legend">
        <strong>Map layers</strong>
        {[
          ["catchments", "Catchment areas"],
          ["ponds", "Pond sites"],
          ["contours", "Contour lines"],
        ].map(([key, label]) => (
          <label key={key}>
            <input type="checkbox" checked={layers[key]} onChange={() => onToggleLayer(key)} />
            {label}
          </label>
        ))}

        {volumes.length > 0 && (
          <div className="legend-scale">
            <span>Water per year</span>
            <div className="legend-bar" />
            <div className="legend-ends">
              <small>{fmtVolume(Math.min(...volumes))}</small>
              <small>{fmtVolume(Math.max(...volumes))}</small>
            </div>
          </div>
        )}
      </div>

      {drawing && (
        <div className="map-hint">
          {vertices.length < 3
            ? "Click on the map to outline your land"
            : "Click the green start point (or press Finish) to close the area"}
        </div>
      )}
    </div>
  );
}
