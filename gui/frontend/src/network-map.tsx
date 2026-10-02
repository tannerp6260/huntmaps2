import { networkResponse, type DisplayNetwork } from './network-response';
import { useEffect, useRef, useState } from 'react';
import { Popup, type Map, type GeoJSONSource } from 'maplibre-gl';
import { useJobs } from './polling';
const styles = [
  ['roads:paved', 'Paved road', '#f4da79'],
  ['roads:gravel', 'Gravel road', '#ed994b'],
  ['roads:natural', 'Natural surface road', '#cfa18c'],
  ['roads:other', 'Other road surface', '#ddd5c9'],
  ['roads:unknown', 'Unknown road surface', '#bcbcbc'],
  ['trails:motorized', 'Recorded motorized trail', '#bc8fff'],
  ['trails:nonmotorized', 'Recorded nonmotorized trail', '#66e1bc'],
  ['trails:unknown', 'Unknown trail use', '#9fc4da'],
];
type Api = (path: string, options?: RequestInit) => Promise<any>;
export default function NetworkMap({
  map,
  api,
  bounds,
  geometry,
  budget,
  analysisPlan,
}: {
  map: Map | null;
  api: Api;
  bounds?: number[][];
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  budget: number;
  analysisPlan: string;
}) {
  const jobs = useJobs();
  const stamp = jobs.map((j) => `${j.id}:${j.status}`).join(',');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const refresh = () => setRevision((v) => v + 1);
    window.addEventListener('huntmaps-networks-changed', refresh);
    return () => window.removeEventListener('huntmaps-networks-changed', refresh);
  }, []);
  const [networks, setNetworks] = useState<DisplayNetwork[]>([]);
  const [visible, setVisible] = useState(['roads', 'trails']);
  const [error, setError] = useState('');
  const [networkError, setNetworkError] = useState('');
  const [loadingNetworks, setLoadingNetworks] = useState(true);
  const [plan, setPlan] = useState<any>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const coordinates: number[][] = [];
  const walk = (v: any): void => {
    if (typeof v[0] === 'number') coordinates.push(v);
    else v.forEach(walk);
  };
  if (geometry) walk(geometry.coordinates);
  else if (bounds) coordinates.push(...bounds);
  const extent = coordinates.length
    ? [
        Math.min(...coordinates.map((p) => p[0])),
        Math.min(...coordinates.map((p) => p[1])),
        Math.max(...coordinates.map((p) => p[0])),
        Math.max(...coordinates.map((p) => p[1])),
      ]
    : null;
  const extentStamp = JSON.stringify(extent);
  const requestKey = `${extentStamp}:${budget}:${analysisPlan}`;
  const currentKey = useRef(requestKey);
  currentKey.current = requestKey;
  useEffect(() => {
    setPlan(null);
    setApproved(false);
    setError('');
  }, [extentStamp, budget, analysisPlan]);
  useEffect(() => {
    let alive = true;
    api('/networks')
      .then(networkResponse)
      .then((v) => {
        if (alive) {
          setNetworks(v);
          setNetworkError('');
        }
      })
      .catch((e) => {
        if (alive) setNetworkError(`Could not load road/trail data: ${String(e)}`);
      })
      .finally(() => {
        if (alive) setLoadingNetworks(false);
      });
    return () => {
      alive = false;
    };
  }, [api, stamp, revision]);
  useEffect(() => {
    if (!map) return;
    try {
      const source = 'network-map';
      const features = networks
        .filter((n) => visible.includes(n.kind))
        .flatMap((n) => n.display_features);
      const data: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features };
      if (map.getSource(source)) (map.getSource(source) as GeoJSONSource).setData(data);
      else {
        map.addSource(source, { type: 'geojson', data });
        const before = ['candidate-halo', 'manual-points', 'approach-context-line'].find((id) =>
          map.getLayer(id),
        );
        map.addLayer(
          {
            id: source + '-outline',
            type: 'line',
            source,
            paint: { 'line-color': '#17221d', 'line-width': 5, 'line-opacity': 0.85 },
          },
          before,
        );
        for (const kind of ['roads', 'trails'])
          map.addLayer(
            {
              id: source + '-' + kind,
              type: 'line',
              source,
              filter: ['==', ['get', 'kind'], kind],
              paint: {
                'line-color': [
                  'match',
                  ['concat', ['get', 'kind'], ':', ['get', 'subtype']],
                  ...styles.flatMap(([key, , color]) => [key, color]),
                  '#bcbcbc',
                ] as any,
                'line-width': kind === 'roads' ? 2.5 : 2,
                'line-dasharray': kind === 'roads' ? [1, 0] : [3, 2],
              },
            },
            before,
          );
      }
      let popup: Popup | null = null;
      const clicked = (e: any) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const p = feature.properties;
        const body = document.createElement('div');
        body.style.color = '#17221d';
        for (const [label, key] of [
          ['Name', 'name'],
          ['Number', 'number'],
          ['Recorded type', 'subtype'],
          ['Surface', 'surface'],
          ['Maintenance level', 'maintenance'],
          ['Trail classification', 'classification'],
          ['Source', 'source'],
          ['Source date', 'source_date'],
          ['Retrieved', 'retrieved_utc'],
        ]) {
          const row = document.createElement('div');
          row.textContent = `${label}: ${p[key] || 'unknown'}`;
          body.append(row);
        }
        popup?.remove();
        popup = new Popup({ className: 'network-popup' })
          .setLngLat(e.lngLat)
          .setDOMContent(body)
          .addTo(map);
      };
      for (const kind of ['roads', 'trails']) map.on('click', source + '-' + kind, clicked);
      return () => {
        popup?.remove();
        for (const kind of ['roads', 'trails']) map.off('click', source + '-' + kind, clicked);
        for (const suffix of ['roads', 'trails', 'outline'])
          if (map.getLayer(source + '-' + suffix)) map.removeLayer(source + '-' + suffix);
        if (map.getSource(source)) map.removeSource(source);
      };
    } catch (e) {
      setNetworkError(`Could not display road/trail data: ${String(e)}`);
    }
  }, [map, networks, visible]);
  const covered = (kind: string) =>
    extent &&
    networks.some(
      (n) =>
        n.kind === kind &&
        n.coverage &&
        n.coverage[0] <= extent[0] &&
        n.coverage[1] <= extent[1] &&
        n.coverage[2] >= extent[2] &&
        n.coverage[3] >= extent[3],
    );
  const active = jobs.some((j) => ['running', 'cancelling'].includes(j.status));
  const job = plan && jobs.find((j) => j.plan === plan.id);
  async function review() {
    setBusy(true);
    setError('');
    try {
      const result = await api('/network-plans', {
        method: 'POST',
        body: JSON.stringify({ bounds: extent, max_download_mb: budget }),
      });
      if (currentKey.current !== requestKey) return;
      setPlan(result);
      setApproved(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function download() {
    setBusy(true);
    setError('');
    try {
      await api(`/network-plans/${plan.id}/start`, {
        method: 'POST',
        body: JSON.stringify({ download: approved, analysis_plan: analysisPlan || undefined }),
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="network-map-controls" open>
      <summary>Roads and trails on map</summary>
      {loadingNetworks && <p role="status">Loading road/trail data…</p>}
      {!loadingNetworks && !networks.length && !networkError && (
        <p role="status">No road/trail data loaded. Review a download or import mapped lines.</p>
      )}
      {networkError && (
        <p role="alert" className="error">
          {networkError}
        </p>
      )}
      {['roads', 'trails'].map((kind) => (
        <label key={kind}>
          <input
            type="checkbox"
            checked={visible.includes(kind)}
            onChange={(e) =>
              setVisible((v) => (e.target.checked ? [...v, kind] : v.filter((k) => k !== kind)))
            }
          />
          {kind === 'roads' ? 'Roads' : 'Trails'}
          <small>
            {!networks.some((n) => n.kind === kind && n.display_features.length)
              ? `No ${kind === 'roads' ? 'road' : 'trail'} lines loaded`
              : covered(kind)
                ? 'Mapped query coverage includes this area'
                : 'Complete mapped coverage unconfirmed'}
          </small>
        </label>
      ))}
      <div className="legend">
        {styles
          .filter(
            ([key]) =>
              visible.includes(key.split(':')[0]) &&
              networks.some((n) =>
                n.display_features.some(
                  (f) => `${f.properties?.kind}:${f.properties?.subtype}` === key,
                ),
              ),
          )
          .map(([key, label, color]) => (
            <span key={key}>
              <i
                style={{
                  background: key.startsWith('trails:') ? 'transparent' : color,
                  border: 'none',
                  height: 3,
                  borderTop: key.startsWith('trails:') ? `2px dashed ${color}` : undefined,
                }}
              />
              {label}
            </span>
          ))}
      </div>
      <small>
        Recorded attributes, not current access certification. Click lines for source details.
        Display only; analysis inputs unchanged.
      </small>
      {(!covered('roads') || !covered('trails')) && (
        <button disabled={!extent || busy || active} onClick={review}>
          Review road/trail download
        </button>
      )}
      {!extent && <p>Draw or import an observer area to review a bounded USFS download.</p>}
      {plan && (
        <div className="plan">
          <p>
            {plan.provider}: up to {plan.estimated_bytes / 1000000} MB. {plan.note}
          </p>
          <p>Bounds: {plan.bounds.join(', ')}. Source date unknown until inspected.</p>
          <label>
            <input
              type="checkbox"
              checked={approved}
              onChange={(e) => setApproved(e.target.checked)}
            />
            Approve this reviewed network download
          </label>
          <button disabled={!approved || active || busy} onClick={download}>
            Download mapped roads/trails
          </button>
        </div>
      )}
      {job && (
        <p role="status">
          Network acquisition {job.status}: {job.error || job.stage}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </details>
  );
}
