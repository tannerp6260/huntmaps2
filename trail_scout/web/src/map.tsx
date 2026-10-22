import React, { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import { Map as MapGL, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
maplibregl.setWorkerUrl(workerUrl);
import { RecordValue } from "./api";

const fc = (features: any[] = []) => ({
  type: "FeatureCollection" as const,
  features,
});
export function ScoutMap({
  context,
  mode,
  result,
  option,
  starts,
  onSegment,
  onPoint,
  onMapPoint,
  editMode,
  profilePoint,
  excludedAreas,
}: {
  mode: string;
  excludedAreas: any[];
  context: RecordValue | null;
  result: RecordValue | null;
  option: RecordValue | null;
  starts: RecordValue[];
  onSegment: (p: any) => void;
  onPoint: (p: any) => void;
  onMapPoint: (lon: number, lat: number) => void;
  editMode: string;
  profilePoint: RecordValue | null;
}) {
  const container = useRef<HTMLDivElement>(null),
    map = useRef<MapGL | null>(null);
  const handlers = useRef({ onSegment, onPoint, onMapPoint, editMode });
  handlers.current = { onSegment, onPoint, onMapPoint, editMode };
  const [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [terrainOnly, setTerrainOnly] = useState(false);
  useEffect(() => {
    const m = new maplibregl.Map({
      container: container.current!,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: "base",
            type: "background",
            paint: { "background-color": "#d8dfd0" },
          },
        ],
      },
      center: [-107.23, 38.68],
      zoom: 10,
      attributionControl: false,
    });
    map.current = m;
    m.addControl(
      new maplibregl.NavigationControl({ showCompass: true }),
      "top-right",
    );
    m.on("load", () => {
      for (const name of [
        "sectors",
        "inspection",
        "network",
        "spurs",
        "route",
        "points",
        "entries",
        "profile",
        "unit",
        "edits",
      ])
        m.addSource(name, { type: "geojson", data: fc() });
      m.addLayer({
        id: "sectors",
        type: "fill",
        source: "sectors",
        paint: { "fill-color": "#e1a128", "fill-opacity": 0.16 },
      });
      m.addLayer({
        id: "sector-outline",
        type: "line",
        source: "sectors",
        paint: {
          "line-color": "#ad7411",
          "line-width": 1.3,
          "line-dasharray": [3, 2],
        },
      });
      m.addLayer({
        id: "inspection",
        type: "line",
        source: "inspection",
        paint: {
          "line-color": "#9d446e",
          "line-width": 2,
          "line-dasharray": [2, 2],
        },
      });
      m.addLayer({
        id: "unit",
        type: "line",
        source: "unit",
        paint: {
          "line-color": "#5c6251",
          "line-width": 1.5,
          "line-dasharray": [5, 4],
        },
      });
      m.addLayer({
        id: "network",
        type: "line",
        source: "network",
        paint: {
          "line-color": [
            "case",
            ["==", ["get", "motor"], "supported"],
            "#467c91",
            ["==", ["get", "foot"], "closed"],
            "#ae4a37",
            ["==", ["get", "kind"], "closed-road"],
            "#ad813a",
            ["==", ["get", "kind"], "trails"],
            "#6b5941",
            "#8a8a76",
          ],
          "line-width": [
            "case",
            ["==", ["get", "motor"], "supported"],
            2.7,
            1.8,
          ],
          "line-opacity": 0.85,
        },
      });
      m.addLayer({
        id: "uncertain",
        type: "line",
        source: "network",
        filter: ["==", ["get", "foot"], "unknown"],
        paint: {
          "line-color": "#c49847",
          "line-width": 2,
          "line-dasharray": [2, 2],
        },
      });
      m.addLayer({
        id: "spurs",
        type: "line",
        source: "spurs",
        paint: {
          "line-color": "#865a9c",
          "line-width": 3,
          "line-dasharray": [2, 2],
        },
      });
      m.addLayer({
        id: "route",
        type: "line",
        source: "route",
        paint: { "line-color": "#f7f4da", "line-width": 7 },
      });
      m.addLayer({
        id: "route-center",
        type: "line",
        source: "route",
        paint: { "line-color": "#193f39", "line-width": 3.5 },
      });
      m.moveLayer("uncertain");
      m.moveLayer("spurs");
      m.addLayer({
        id: "entries",
        type: "circle",
        source: "entries",
        paint: {
          "circle-color": "#457c92",
          "circle-radius": 6,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 2,
        },
      });
      m.addLayer({
        id: "points",
        type: "circle",
        source: "points",
        paint: {
          "circle-color": ["case", ["get", "selected"], "#eea23f", "#f7f4e8"],
          "circle-radius": ["case", ["get", "selected"], 8, 5],
          "circle-stroke-color": "#26483d",
          "circle-stroke-width": 2,
        },
      });
      m.addLayer({
        id: "profile",
        type: "circle",
        source: "profile",
        paint: {
          "circle-color": "#e46b36",
          "circle-radius": 9,
          "circle-stroke-color": "white",
          "circle-stroke-width": 3,
        },
      });
      m.addLayer({
        id: "edits",
        type: "fill",
        source: "edits",
        paint: { "fill-color": "#b63d2b", "fill-opacity": 0.25 },
      });
      m.on("click", (e) => {
        if (handlers.current.editMode) {
          handlers.current.onMapPoint(e.lngLat.lng, e.lngLat.lat);
          return;
        }
        const hit = m.queryRenderedFeatures(e.point, {
          layers: ["points", "network"],
        })[0];
        if (!hit) return;
        if (hit.layer.id === "points") handlers.current.onPoint(hit.properties);
        else
          handlers.current.onSegment({
            ...hit.properties,
            click_longitude: e.lngLat.lng,
            click_latitude: e.lngLat.lat,
          });
      });
      m.on("mousemove", (e) => {
        m.getCanvas().style.cursor = handlers.current.editMode
          ? "crosshair"
          : m.queryRenderedFeatures(e.point, { layers: ["points", "network"] })
                .length
            ? "pointer"
            : "";
      });
      setReady(true);
    });
    m.on("error", (e) => setError(e.error.message));
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    const update = (name: string, data: any) =>
      (m.getSource(name) as GeoJSONSource).setData(data);
    update(
      "entries",
      fc(
        starts.map((p) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [p.longitude, p.latitude] },
          properties: { id: p.id },
        })),
      ),
    );
    if (context && !m.getSource("overview")) {
      m.addSource("overview", {
        type: "image",
        url: context.map.relief_url,
        coordinates: context.map.corners,
      });
      m.addLayer(
        {
          id: "overview",
          type: "raster",
          source: "overview",
          paint: { "raster-opacity": 1, "raster-fade-duration": 0 },
        },
        "unit",
      );
    }
    const r = result || context;
    if (!r) return;
    if (m.getSource("relief")) {
      m.removeLayer("relief");
      m.removeSource("relief");
    }
    m.addSource("relief", {
      type: "image",
      url: r.map.relief_url,
      coordinates: r.map.corners,
    });
    m.addLayer(
      {
        id: "relief",
        type: "raster",
        source: "relief",
        paint: { "raster-opacity": 1, "raster-fade-duration": 0 },
      },
      "unit",
    );
    m.moveLayer("sectors", "network");
    m.moveLayer("sector-outline", "network");
    m.moveLayer("inspection", "network");
    update("unit", fc([r.map.target_boundary]));
    update(
      "network",
      fc(
        r.map.network.features.map((f: any) => ({
          ...f,
          properties: {
            ...f.properties,
            foot: f.properties.access.foot,
            motor: f.properties.access.motor,
          },
        })),
      ),
    );
    const corners = r.map.corners;
    m.fitBounds([corners[3], corners[1]], { padding: 30, duration: 0 });
  }, [result, context, ready, starts]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !result) return;
    (m.getSource("sectors") as GeoJSONSource).setData(
      option?.schedules[mode]?.practical?.sectors || fc(),
    );
    (m.getSource("inspection") as GeoJSONSource).setData(
      fc(option?.inspection?.map((p: any) => p.context).filter(Boolean) || []),
    );
    (m.getSource("route") as GeoJSONSource).setData(
      fc(
        option?.legs.map((leg: any) => ({
          type: "Feature",
          geometry: leg.geometry,
          properties: {},
        })) || [],
      ),
    );
    (m.getSource("points") as GeoJSONSource).setData(
      fc(
        result.candidates
          .filter((p: any) => p.feasible)
          .map((p: any) => ({
            type: "Feature",
            geometry: { type: "Point", coordinates: [p.longitude, p.latitude] },
            properties: {
              id: p.id,
              selected: !!option?.viewpoints.some((v: any) => v.id === p.id),
            },
          })),
      ),
    );
    (m.getSource("spurs") as GeoJSONSource).setData(
      fc(
        result.map.spurs.features.filter(
          (p: any) => p.properties.option === option?.id,
        ),
      ),
    );
    if (m.getSource("coverage")) {
      m.removeLayer("coverage");
      m.removeSource("coverage");
    }
    if (option) {
      m.addSource("coverage", {
        type: "image",
        url:
          (!terrainOnly && option.schedules[mode]?.practical?.coverage_url) ||
          option.coverage_url,
        coordinates: result.map.corners,
      });
      m.addLayer(
        {
          id: "coverage",
          type: "raster",
          source: "coverage",
          paint: { "raster-opacity": 0.75, "raster-fade-duration": 0 },
        },
        "network",
      );
    }
  }, [option, result, ready, mode, terrainOnly]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    (m.getSource("profile") as GeoJSONSource).setData(
      fc(
        profilePoint
          ? [
              {
                type: "Feature",
                geometry: {
                  type: "Point",
                  coordinates: [profilePoint.longitude, profilePoint.latitude],
                },
                properties: {},
              },
            ]
          : [],
      ),
    );
  }, [profilePoint, ready]);
  useEffect(() => {
    const m = map.current;
    if (!ready || !m) return;
    (m.getSource("edits") as GeoJSONSource).setData(
      fc(
        excludedAreas.map((g) => ({
          type: "Feature",
          geometry: g.geometry || g,
          properties: {},
        })),
      ),
    );
  }, [excludedAreas, ready]);
  return (
    <div className="map-shell">
      <div
        className="map"
        ref={container}
        data-scan-sectors={
          option?.schedules[mode]?.practical?.sectors?.features.length || 0
        }
        role="img"
        aria-label="Offline terrain, access, route and glassing coverage map"
      />
      <div className="map-label">
        LOCAL TERRAIN <span>10 m ground · 40 m vegetation support</span>
      </div>
      {editMode && (
        <div className="map-instruction">
          {editMode === "pin"
            ? "Click an exact new viewpoint"
            : "Click two opposite corners of a small exclusion"}
        </div>
      )}
      <div className="legend">
        {option?.schedules[mode]?.practical && (
          <label>
            <input
              type="checkbox"
              checked={terrainOnly}
              onChange={(e) => setTerrainOnly(e.target.checked)}
            />{" "}
            Show theoretical terrain instead of selected search support
          </label>
        )}
        {option?.schedules[mode]?.practical && (
          <span>
            Amber sectors · selected scan footprints / magenta · coarse
            inspection
          </span>
        )}
        <span>
          <i className="motor" />
          Motor evidence
        </span>
        <span>
          <i className="trail" />
          Walking
        </span>
        <span>
          <i className="closed" />
          Motor closed / unknown foot
        </span>
        <span>
          <i className="spur" />
          Spur
        </span>
        <span>
          <i className="cover" />
          Theoretical visible targets
        </span>
      </div>
      {error && (
        <div className="map-error">
          Map display unavailable: {error}. Saved plans and exports remain
          available.{" "}
          <button onClick={() => location.reload()}>Reload map</button>
        </div>
      )}
    </div>
  );
}
