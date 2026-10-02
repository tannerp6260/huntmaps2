import { useEffect, useRef, useState } from 'react';
import type { Map, GeoJSONSource } from 'maplibre-gl';
type TerrainInfo = {
  available: boolean;
  reason: string;
  bounds: [number, number, number, number];
  coverage: any;
  minzoom: number;
  maxzoom: number;
  encoding: 'terrarium';
};
export function TerrainControls({
  map,
  runId,
  drawing,
  newArea,
  onFlat,
}: {
  map: Map;
  runId: string;
  drawing: boolean;
  newArea: boolean;
  onFlat?: () => void;
}) {
  const [info, setInfo] = useState<TerrainInfo | null>(null),
    [active, setActive] = useState(false),
    [pitch, setPitch] = useState(50),
    [message, setMessage] = useState(''),
    [outside, setOutside] = useState(false),
    activeRef = useRef(false);
  activeRef.current = active;
  const flat = () => {
    activeRef.current = false;
    map.setTerrain(null);
    if (map.getSource('local-elevation')) map.removeSource('local-elevation');
    map.setMaxBounds(null);
    map.setMinZoom(0);
    map.easeTo({ pitch: 0, bearing: 0, duration: 350 });
    setActive(false);
    onFlat?.();
    if (map.getLayer('terrain-outside'))
      map.setLayoutProperty('terrain-outside', 'visibility', 'none');
  };
  const flatRef = useRef(flat);
  flatRef.current = flat;
  useEffect(() => {
    let alive = true;
    flatRef.current();
    setInfo(null);
    setMessage('');
    fetch(`/api/runs/${runId}/terrain`)
      .then(async (r) => {
        if (!r.ok) throw Error('Local elevation unavailable');
        return r.json();
      })
      .then((v) => {
        if (alive) setInfo(v);
      })
      .catch((e) => {
        if (alive) setMessage(e.message + '; use 2D.');
      });
    return () => {
      alive = false;
    };
  }, [runId, map]);
  useEffect(() => {
    if (drawing || newArea) {
      flatRef.current();
      if (newArea) setMessage('');
    }
  }, [drawing, newArea]);
  useEffect(() => {
    const check = () => {
      const c = map.getCenter(),
        b = info?.bounds;
      setOutside(!!b && (c.lng < b[0] || c.lng > b[2] || c.lat < b[1] || c.lat > b[3]));
    };
    check();
    map.on('moveend', check);
    return () => {
      map.off('moveend', check);
    };
  }, [map, info]);
  useEffect(() => {
    const failed = (e: any) => {
      if (activeRef.current && e.sourceId === 'local-elevation') {
        flatRef.current();
        setMessage('3D elevation could not load. Returned to 2D; saved results are unchanged.');
      }
    };
    map.on('error', failed);
    return () => {
      map.off('error', failed);
      map.setTerrain(null);
      map.setMaxBounds(null);
      map.setMinZoom(0);
      if (map.getLayer('terrain-outside')) map.removeLayer('terrain-outside');
      if (map.getSource('terrain-coverage')) map.removeSource('terrain-coverage');
      if (map.getSource('local-elevation')) map.removeSource('local-elevation');
    };
  }, [map]);
  function enable() {
    if (!info?.available) return;
    try {
      map.setTerrain(null);
      if (map.getSource('local-elevation')) map.removeSource('local-elevation');
      map.addSource('local-elevation', {
        type: 'raster-dem',
        tiles: [`${location.origin}/api/runs/${runId}/terrain/{z}/{x}/{y}.png`],
        bounds: info.bounds,
        tileSize: 256,
        minzoom: info.minzoom,
        maxzoom: info.maxzoom,
        encoding: 'terrarium',
      });
      const outer = [
          [-180, -85],
          [180, -85],
          [180, 85],
          [-180, 85],
          [-180, -85],
        ],
        hole = info.coverage.coordinates[0];
      const coverage = {
        type: 'Feature',
        properties: {},
        geometry: { type: 'Polygon', coordinates: [outer, hole] },
      } as any;
      if (!map.getSource('terrain-coverage')) {
        map.addSource('terrain-coverage', { type: 'geojson', data: coverage });
        map.addLayer({
          id: 'terrain-outside',
          type: 'fill',
          source: 'terrain-coverage',
          paint: { 'fill-color': '#d6ddd0', 'fill-opacity': 1 },
        });
      } else {
        (map.getSource('terrain-coverage') as GeoJSONSource).setData(coverage);
        map.setLayoutProperty('terrain-outside', 'visibility', 'visible');
      }
      map.setMaxBounds([
        [info.bounds[0], info.bounds[1]],
        [info.bounds[2], info.bounds[3]],
      ]);
      map.setMinZoom(info.minzoom);
      map.setTerrain({ source: 'local-elevation', exaggeration: 1 });
      map.easeTo({
        pitch,
        bearing: map.getBearing(),
        zoom: Math.max(map.getZoom(), info.minzoom),
        duration: 400,
      });
      setActive(true);
      setMessage('');
    } catch {
      flat();
      setMessage('3D is unavailable in this browser. Use the 2D map.');
    }
  }
  return (
    <div className="terrain-controls" data-mode={active ? '3d' : '2d'}>
      <div className="row">
        <button aria-pressed={!active} onClick={flat}>
          2D
        </button>
        <button
          aria-pressed={active}
          disabled={!info?.available || drawing || newArea}
          onClick={enable}
        >
          3D terrain
        </button>
        <button
          onClick={() => {
            flat();
            if (info)
              map.fitBounds(
                [
                  [info.bounds[0], info.bounds[1]],
                  [info.bounds[2], info.bounds[3]],
                ],
                { padding: 55, duration: 400 },
              );
          }}
        >
          Reset view
        </button>
      </div>
      {active && (
        <>
          <label>
            Tilt
            <input
              aria-label="Terrain tilt"
              type="range"
              min="15"
              max="60"
              value={pitch}
              onChange={(e) => {
                const v = +e.target.value;
                setPitch(v);
                map.setPitch(v);
              }}
            />
          </label>
          <div className="row">
            <button
              aria-label="Rotate terrain left"
              onClick={() => map.setBearing(map.getBearing() - 30)}
            >
              ↶ Rotate
            </button>
            <button
              aria-label="Rotate terrain right"
              onClick={() => map.setBearing(map.getBearing() + 30)}
            >
              Rotate ↷
            </button>
          </div>
          <small>
            True-scale bare-earth terrain · outside coverage hidden · not an eye-level sightline
          </small>
        </>
      )}
      {(message || (info && !info.available)) && (
        <small role="status">{message || info?.reason}</small>
      )}
      {newArea && (
        <small>
          {outside
            ? 'Outside local elevation coverage: online imagery can provide context; local 3D is unavailable here.'
            : 'Draw in 2D. 3D requires a completed run’s local elevation.'}
        </small>
      )}
    </div>
  );
}
