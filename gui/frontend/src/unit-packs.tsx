import { orderRasterLayers } from './layer-order';
import { useEffect, useState } from 'react';
import type { Map } from 'maplibre-gl';
import { request } from './http';
export type PackSelection = { unit_id: string; version: string; label: string };
type Unit = PackSelection & {
  status: string;
  core?: string;
  detail?: { note: string };
  error?: string;
};
export function UnitChooser({
  selected,
  onSelect,
}: {
  selected: PackSelection | null;
  onSelect: (p: PackSelection | null) => void;
}) {
  const [units, setUnits] = useState<Unit[]>([]),
    [error, setError] = useState(''),
    [progress, setProgress] = useState<{ stage: string; error?: string; next_action?: string }[]>(
      [],
    );
  useEffect(() => {
    let live = true;
    const read = () =>
      request('/api/unit-packs')
        .then((v) => {
          if (!Array.isArray(v.units) || !Array.isArray(v.preparations))
            throw Error(
              'Prepared unit catalog unavailable. Use Custom area or restore the local pack catalog.',
            );
          if (live) {
            setUnits(v.units);
            setProgress(v.preparations);
            setError('');
          }
        })
        .catch((e) => {
          if (live) setError(String(e));
        });
    void read();
    const timer = setInterval(read, 15000);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, []);
  const selectedRow = units.find(
    (u) => u.unit_id === selected?.unit_id && u.version === selected?.version,
  );
  const [pinnedReady, setPinnedReady] = useState(false);
  useEffect(() => {
    let live = true;
    setPinnedReady(false);
    if (selected && !selectedRow)
      void request(`/api/unit-packs/${selected.unit_id}/${selected.version}`)
        .then(() => {
          if (live) setPinnedReady(true);
        })
        .catch((e) => {
          if (live) setError(String(e));
        });
    return () => {
      live = false;
    };
  }, [selected?.unit_id, selected?.version, selectedRow]);
  return (
    <section aria-label="Choose hunting unit" className="unit-chooser">
      <div className="eyebrow">Choose hunting unit</div>
      <label>
        Prepared local data
        <select
          aria-label="Hunting unit"
          value={selected ? `${selected.unit_id}/${selected.version}` : ''}
          onChange={(e) => {
            const p = units.find((u) => `${u.unit_id}/${u.version}` === e.target.value);
            onSelect(p || null);
          }}
        >
          <option value="">Custom area · existing source workflow</option>
          {selected && !selectedRow && (
            <option value={`${selected.unit_id}/${selected.version}`}>
              {selected.label} · pinned {selected.version}
              {pinnedReady ? ' · Core ready locally' : ' · Checking version'}
            </option>
          )}
          {units.map((u) => (
            <option
              key={`${u.unit_id}/${u.version}`}
              disabled={u.status !== 'ready'}
              value={`${u.unit_id}/${u.version}`}
            >
              {u.label} · {u.status === 'ready' ? 'Core ready locally' : 'Unavailable'}
            </option>
          ))}
        </select>
      </label>
      {selected && (
        <>
          <p>
            <b>{selected.label}</b> ·{' '}
            {selectedRow?.status === 'ready' || pinnedReady
              ? 'Core ready locally'
              : 'Core unavailable · review recovery details'}
          </p>
          <small>
            Draw a manageable area within the unit outline. Begin around 10–50 km². Basic terrain
            inspection works offline. Detailed scenes need selected-area preparation.
          </small>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {units
        .filter((u) => u.error)
        .map((u) => (
          <p key={u.unit_id} role="alert">
            {u.label}: {u.error}
          </p>
        ))}
      {!!progress.length && (
        <details>
          <summary>Preparation and recovery</summary>
          {progress.map((p, i) => (
            <p key={i}>
              {p.stage} {p.error} {p.next_action}
            </p>
          ))}
        </details>
      )}
    </section>
  );
}
export function UnitMap({
  map,
  selection,
  onError,
  center = false,
}: {
  map: Map;
  selection: PackSelection | null;
  onError: (s: string) => void;
  center?: boolean;
}) {
  useEffect(() => {
    let live = true;
    map.getContainer().dataset.unitPackReady = 'false';
    if (!selection) {
      delete map.getContainer().dataset.unitPack;
      return;
    }
    let loaded: (() => void) | undefined;
    const base = `/api/unit-packs/${selection.unit_id}/${selection.version}`;
    void request(base)
      .then((v) => {
        if (!live) return;
        map.getContainer().dataset.unitPack = selection.unit_id + '/' + selection.version;
        loaded = () => {
          if (live && map.getSource('unit-relief') && map.isSourceLoaded('unit-relief'))
            map.getContainer().dataset.unitPackReady = 'true';
        };
        map.on('sourcedata', loaded);
        map.once('idle', loaded);
        // Projected extent's exact WGS84 corners are supplied by the pack manifest.
        map.addSource('unit-relief', {
          type: 'image',
          url: base + '/hillshade.png',
          coordinates: v.overview_corners,
        });
        map.addLayer(
          {
            id: 'unit-relief',
            type: 'raster',
            source: 'unit-relief',
            paint: { 'raster-opacity': 0.85, 'raster-fade-duration': 0 },
          },
          'boundary-fill',
        );
        map.addSource('unit-outline', { type: 'geojson', data: v.boundary_geojson });
        map.addLayer({
          id: 'unit-outline',
          type: 'line',
          source: 'unit-outline',
          paint: { 'line-color': '#86dac4', 'line-width': 3, 'line-dasharray': [4, 2] },
        });
        map.addSource('unit-roads', { type: 'geojson', data: v.context_geojson });
        map.addLayer(
          {
            id: 'unit-network-outline',
            type: 'line',
            source: 'unit-roads',
            paint: { 'line-color': '#17221d', 'line-width': 4.5, 'line-opacity': 0.85 },
          },
          'boundary-fill',
        );
        map.addLayer(
          {
            id: 'unit-roads',
            type: 'line',
            source: 'unit-roads',
            filter: ['==', ['get', 'kind'], 'roads'],
            paint: { 'line-color': '#f7d9a0', 'line-width': 2.5 },
          },
          'boundary-fill',
        );
        map.addLayer(
          {
            id: 'unit-trails',
            type: 'line',
            source: 'unit-roads',
            filter: ['==', ['get', 'kind'], 'trails'],
            paint: { 'line-color': '#66e1bc', 'line-width': 2.5, 'line-dasharray': [3, 2] },
          },
          'boundary-fill',
        );
        orderRasterLayers(map);
        if (center)
          map.fitBounds(
            [
              [v.bounds[0], v.bounds[1]],
              [v.bounds[2], v.bounds[3]],
            ],
            { padding: 50, duration: 0 },
          );
      })
      .catch((e) => {
        if (live) onError(String(e));
      });
    return () => {
      live = false;
      if (loaded) {
        map.off('sourcedata', loaded);
        map.off('idle', loaded);
      }
      delete map.getContainer().dataset.unitPack;
      delete map.getContainer().dataset.unitPackReady;
      for (const id of [
        'unit-network-outline',
        'unit-trails',
        'unit-relief',
        'unit-outline',
        'unit-roads',
      ]) {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      }
    };
  }, [map, selection?.unit_id, selection?.version, center]);
  return null;
}
