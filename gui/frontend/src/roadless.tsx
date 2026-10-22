import { useEffect, useState } from 'react';
import type { GeoJSONSource, Map } from 'maplibre-gl';
import type { PackSelection } from './unit-packs';
import { orderRasterLayers } from './layer-order';
import { useJobs } from './polling';

const source = 'roadless-overlay';
const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
const key = 'huntmaps-roadless-overlay';
function saved() {
  try {
    const v = JSON.parse(localStorage.getItem(key) || '{}');
    return {
      enabled: v.enabled === true,
      miles: typeof v.miles === 'number' && v.miles >= 0 && v.miles <= 10 ? v.miles : 1,
      opacity: typeof v.opacity === 'number' && v.opacity >= 0 && v.opacity <= 1 ? v.opacity : 0.3,
    };
  } catch {
    return { enabled: false, miles: 1, opacity: 0.3 };
  }
}

export default function Roadless({
  map,
  unitPack,
  contextKey,
  onVisible,
}: {
  map: Map;
  unitPack: PackSelection | null;
  contextKey: string;
  onVisible: (visible: boolean) => void;
}) {
  const [settings, setSettings] = useState(saved);
  const [distanceText, setDistanceText] = useState(String(settings.miles));
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const jobs = useJobs();
  const stamp = jobs
    .filter((j) => j.status === 'complete')
    .map((j) => j.id)
    .join(',');
  const valid =
    distanceText.trim() !== '' &&
    Number.isFinite(Number(distanceText)) &&
    Number(distanceText) >= 0 &&
    Number(distanceText) <= 10;
  const { enabled, miles, opacity } = settings;
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(settings));
    onVisible(enabled);
  }, [settings, onVisible]);
  useEffect(() => () => onVisible(false), [onVisible]);
  useEffect(() => {
    const refresh = () => setRevision((v) => v + 1);
    window.addEventListener('huntmaps-networks-changed', refresh);
    return () => window.removeEventListener('huntmaps-networks-changed', refresh);
  }, []);
  useEffect(() => {
    if (!enabled) return;
    map.addSource(source, { type: 'geojson', data: empty });
    map.addLayer(
      {
        id: source,
        type: 'fill',
        source,
        paint: { 'fill-color': '#c58df2', 'fill-opacity': opacity },
      },
      'boundary-fill',
    );
    orderRasterLayers(map);
    return () => {
      if (map.getLayer(source)) map.removeLayer(source);
      if (map.getSource(source)) map.removeSource(source);
      delete map.getContainer().dataset.roadless;
    };
  }, [map, enabled]);
  useEffect(() => {
    if (map.getLayer(source)) map.setPaintProperty(source, 'fill-opacity', opacity);
  }, [map, enabled, opacity]);
  useEffect(() => {
    if (!enabled) return;
    let live = true,
      timer: ReturnType<typeof setTimeout>,
      controller: AbortController | undefined;
    const update = () => {
      clearTimeout(timer);
      controller?.abort();
      (map.getSource(source) as GeoJSONSource | undefined)?.setData(empty);
      delete map.getContainer().dataset.roadless;
      setError('');
      if (!valid) {
        setStatus('Enter a distance between 0 and 10 miles.');
        return;
      }
      setStatus('Finding land away from mapped roads…');
      timer = setTimeout(async () => {
        const request = new AbortController();
        controller = request;
        const b = map.getBounds();
        try {
          const response = await fetch('/api/roadless-overlay', {
            method: 'POST',
            signal: request.signal,
            headers: { 'Content-Type': 'application/json', 'X-HuntMaps': 'local' },
            body: JSON.stringify({
              bounds: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
              distance_m: miles * 1609.344,
              unit_pack: unitPack,
            }),
          });
          const value = await response.json();
          if (!response.ok) throw Error(value.detail || 'Could not load road distance');
          if (!live || request.signal.aborted) return;
          (map.getSource(source) as GeoJSONSource | undefined)?.setData(value);
          orderRasterLayers(map);
          map.getContainer().dataset.roadless = JSON.stringify({
            status: value.status,
            distance_m: value.distance_m,
            features: value.features.length,
            coverage_fraction: value.coverage_fraction,
          });
          setStatus(value.message);
        } catch (e) {
          if (live && !request.signal.aborted) {
            setStatus('');
            setError(String(e));
          }
        }
      }, 300);
    };
    update();
    map.on('moveend', update);
    return () => {
      live = false;
      clearTimeout(timer);
      controller?.abort();
      map.off('moveend', update);
    };
  }, [
    map,
    enabled,
    miles,
    valid,
    unitPack?.unit_id,
    unitPack?.version,
    contextKey,
    revision,
    stamp,
  ]);
  return (
    <section className="roadless-controls" aria-label="Roadless overlay controls">
      <label>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setSettings((v) => ({ ...v, enabled: e.target.checked }))}
        />
        Roadless distance overlay
      </label>
      {enabled && (
        <>
          <label>
            Farther from roads than (miles)
            <input
              aria-label="Minimum road distance (miles)"
              type="number"
              min="0"
              max="10"
              step="0.25"
              value={distanceText}
              aria-invalid={!valid}
              onChange={(e) => {
                setDistanceText(e.target.value);
                const n = Number(e.target.value);
                if (e.target.value.trim() !== '' && Number.isFinite(n) && n >= 0 && n <= 10)
                  setSettings((v) => ({ ...v, miles: n }));
              }}
            />
          </label>
          <label>
            Roadless opacity: {Math.round(opacity * 100)}%
            <input
              aria-label="Roadless overlay opacity"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={opacity}
              onChange={(e) => setSettings((v) => ({ ...v, opacity: Number(e.target.value) }))}
            />
          </label>
          <small>
            <i
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                background: '#c58df2',
                marginRight: 5,
              }}
            />
            Purple: beyond this straight-line distance from mapped roads. Trails do not count as
            roads. This is a map overlay, not an official roadless designation.
          </small>
          {status && <small role="status">{status}</small>}
          {error && (
            <>
              <p role="alert">{error}</p>
              <button onClick={() => setRevision((v) => v + 1)}>Retry roadless overlay</button>
            </>
          )}
        </>
      )}
    </section>
  );
}
