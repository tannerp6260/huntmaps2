import { useEffect, useRef, useState } from 'react';
import type { Map, GeoJSONSource } from 'maplibre-gl';
import { Drawing } from './drawing';
import { useJobs } from './polling';
type Polygon = GeoJSON.Polygon | GeoJSON.MultiPolygon;
type FilterRow = {
  id: string;
  original_km2: number;
  matching_km2: number;
  qualifies: boolean;
  access: { status: string; distance_m: number | null; height_m: number | null };
};
export type AppliedFilter = { profile: { id: string }; candidates: FilterRow[] };
type Network = {
  id: string;
  kind: string;
  source: string;
  source_date: string;
  lines: GeoJSON.LineString[];
  coverage_note: string;
};
type Kept = { id: string; longitude: number; latitude: number; coverage: number | null };
type Alternative = {
  labels: string[];
  departure: number[];
  mapped: number[][];
  offtrail: number[][];
  cost: number;
  cost_contributions: Record<string, number>;
  mapped_distance_m: number;
  offtrail_distance_m: number;
  ascent_m: number;
  descent_m: number;
  maximum_slope_deg: number;
  average_tree: number | null;
  average_shrub: number | null;
  unknown_cover_fraction: number | null;
  elevation_profile: number[][];
};
type Scenario = {
  scenario: {
    id: string;
    notice: string;
    points: Kept[];
    network_ids: string[];
    kinds: string[];
    travel_area: Polygon;
    exclusions: Polygon[];
    weights: { slope: number; gain: number; tree: number; shrub: number };
    maximum_slope_deg: number;
    start: number[] | null;
    pinned: number[] | null;
  };
  stale: boolean;
  stale_reasons: string[];
  results: {
    results: {
      point: Kept;
      alternatives: Alternative[];
      message: string;
      limiting_evidence: unknown;
      pinned_status?: string;
    }[];
  } | null;
};
type Api = (path: string, options?: RequestInit) => Promise<any>;
const aspects = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const number = (v: number | null, d = 1) => (v === null ? 'unknown' : v.toFixed(d));
export default function ScoutingTools({
  runId,
  map,
  api,
  onFilter,
  stamp,
  analysisPlan,
  budget,
  planning,
  onPlanning,
}: {
  runId: string;
  map: Map | null;
  api: Api;
  onFilter: (v: AppliedFilter | null) => void;
  stamp: string;
  analysisPlan: string;
  budget: number;
  planning: boolean;
  onPlanning: (v: boolean) => void;
}) {
  const jobs = useJobs();
  const [networks, setNetworks] = useState<Network[]>([]),
    [selectedNetworks, setSelectedNetworks] = useState<string[]>([]),
    [kind, setKind] = useState('trails'),
    [error, setError] = useState('');
  const [distance, setDistance] = useState(false),
    [miles, setMiles] = useState(0.5),
    [height, setHeight] = useState(false),
    [feet, setFeet] = useState(1000),
    [kinds, setKinds] = useState(['roads', 'trails']);
  const [elevation, setElevation] = useState(false),
    [elevMin, setElevMin] = useState(0),
    [elevMax, setElevMax] = useState(14000),
    [slope, setSlope] = useState(false),
    [slopeMin, setSlopeMin] = useState(0),
    [slopeMax, setSlopeMax] = useState(90),
    [selectedAspects, setSelectedAspects] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false),
    [applied, setApplied] = useState<AppliedFilter | null>(null),
    [busy, setBusy] = useState(false),
    [kept, setKept] = useState<Kept[]>([]);
  const [area, setArea] = useState<Polygon | null>(null),
    [exclusions, setExclusions] = useState<Polygon[]>([]),
    [drawingExclusion, setDrawingExclusion] = useState(false),
    [editing, setEditing] = useState(false);
  const [weights, setWeights] = useState({ slope: 1, gain: 1, tree: 1, shrub: 1 }),
    [maximum, setMaximum] = useState(30),
    [includeWalk, setIncludeWalk] = useState(false),
    [start, setStart] = useState(''),
    [pinned, setPinned] = useState('');
  const [scenarios, setScenarios] = useState<Scenario[]>([]),
    [scenarioId, setScenarioId] = useState(''),
    [networkPlan, setNetworkPlan] = useState<any>(null),
    [download, setDownload] = useState(false),
    [networkPlanId, setNetworkPlanId] = useState('');
  const [pick, setPick] = useState<'start' | 'pinned' | null>(null);
  const [alternativesOnMap, setAlternativesOnMap] = useState<Record<string, number>>({});
  const epoch = useRef(0),
    runRef = useRef(runId);
  runRef.current = runId;
  const currentScenario = scenarios.find((s) => s.scenario.id === scenarioId)?.scenario;
  const scenarioDirty =
    !!currentScenario &&
    (editing ||
      JSON.stringify({
        area,
        exclusions,
        weights,
        maximum,
        ids: selectedNetworks,
        kinds,
        start: includeWalk ? start : '',
        pinned,
      }) !==
        JSON.stringify({
          area: currentScenario.travel_area,
          exclusions: currentScenario.exclusions,
          weights: currentScenario.weights,
          maximum: currentScenario.maximum_slope_deg,
          ids: currentScenario.network_ids,
          kinds: currentScenario.kinds,
          start: currentScenario.start?.join(',') || '',
          pinned: currentScenario.pinned?.join(',') || '',
        }));
  function showAlternative(point: string, index: number) {
    setAlternativesOnMap((v) => ({ ...v, [point]: index }));
    const path = scenarios
      .find((s) => s.scenario.id === scenarioId)
      ?.results?.results.find((r) => r.point.id === point)?.alternatives[index];
    if (map && path) {
      const coords = [...path.mapped, ...path.offtrail];
      if (coords.length)
        map.fitBounds(
          [
            [Math.min(...coords.map((p) => p[0])), Math.min(...coords.map((p) => p[1]))],
            [Math.max(...coords.map((p) => p[0])), Math.max(...coords.map((p) => p[1]))],
          ],
          { padding: 70, maxZoom: 16, duration: 300 },
        );
    }
  }
  function loadScenario(id: string) {
    setScenarioId(id);
    const s = scenarios.find((v) => v.scenario.id === id)?.scenario;
    if (!s) return;
    setArea(s.travel_area);
    setExclusions(s.exclusions);
    setWeights(s.weights);
    setMaximum(s.maximum_slope_deg);
    setSelectedNetworks(s.network_ids);
    setKinds(s.kinds);
    setIncludeWalk(!!s.start);
    setStart(s.start?.join(',') || '');
    setPinned(s.pinned?.join(',') || '');
  }
  const active = jobs.some((j) => ['running', 'cancelling'].includes(j.status));
  const jobStamp = jobs.map((j) => `${j.id}:${j.status}`).join(',');
  useEffect(() => {
    epoch.current++;
    setApplied(null);
    onFilter(null);
    setDirty(false);
    setKept([]);
    setScenarios([]);
    setScenarioId('');
    setArea(null);
    setExclusions([]);
    setError('');
    onPlanning(false);
  }, [runId]);
  useEffect(() => {
    let alive = true;
    api('/networks')
      .then((v) => {
        if (alive) {
          setNetworks(v);
          setSelectedNetworks((old) => (old.length ? old : v.map((n: Network) => n.id)));
        }
      })
      .catch((e) => {
        if (alive) setError(String(e));
      });
    if (runId)
      Promise.all([api(`/runs/${runId}/kept-points`), api(`/runs/${runId}/approaches`)])
        .then(([p, s]) => {
          if (alive) {
            setKept(p);
            setScenarios(s);
          }
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    if (networkPlanId)
      api(`/network-plans/${networkPlanId}`)
        .then((v) => {
          if (alive && v.result) setNetworkPlan(null);
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    return () => {
      alive = false;
    };
  }, [runId, stamp, jobStamp, networkPlanId]);
  useEffect(() => {
    setDirty(true);
    epoch.current++;
  }, [
    distance,
    miles,
    height,
    feet,
    kinds.join(','),
    elevation,
    elevMin,
    elevMax,
    slope,
    slopeMin,
    slopeMax,
    selectedAspects.join(','),
    selectedNetworks.join(','),
  ]);
  useEffect(() => {
    epoch.current++;
  }, [area, exclusions, weights, maximum, includeWalk, start, pinned]);
  useEffect(() => {
    if (!map || !pick || !planning) return;
    const token = epoch.current;
    const clicked = (e: { lngLat: { lng: number; lat: number } }) => {
      const run = runId;
      api(`/runs/${run}/network-point`, {
        method: 'POST',
        body: JSON.stringify({
          coordinates: [e.lngLat.lng, e.lngLat.lat],
          network_ids: selectedNetworks,
          kinds,
        }),
      })
        .then((v) => {
          if (run !== runRef.current || token !== epoch.current) return;
          if (pick === 'start') setStart(v.coordinates.join(','));
          else setPinned(v.coordinates.join(','));
          setPick(null);
        })
        .catch((e) => setError(String(e)));
    };
    map.on('click', clicked);
    map.getCanvas().style.cursor = 'crosshair';
    return () => {
      map.off('click', clicked);
      map.getCanvas().style.cursor = '';
    };
  }, [map, pick, planning, runId, selectedNetworks, kinds]);
  useEffect(() => {
    if (!map) return;
    const name = 'approach-context';
    const features: GeoJSON.Feature[] = networks
      .filter((n) => selectedNetworks.includes(n.id) && kinds.includes(n.kind))
      .flatMap((n) =>
        n.lines.map((g) => ({
          type: 'Feature' as const,
          geometry: g,
          properties: { kind: n.kind },
        })),
      );
    if (planning && area)
      features.push({ type: 'Feature', geometry: area, properties: { kind: 'travel' } });
    if (planning)
      exclusions.forEach((g) =>
        features.push({ type: 'Feature', geometry: g, properties: { kind: 'exclusion' } }),
      );
    const scenario = scenarios.find((s) => s.scenario.id === scenarioId);
    if (planning && !scenarioDirty && scenario && !scenario.stale)
      scenario.results?.results.forEach(
        (r) =>
          r.alternatives[alternativesOnMap[r.point.id] || 0] &&
          ['mapped', 'offtrail'].forEach((mode) => {
            const alternative = r.alternatives[alternativesOnMap[r.point.id] || 0];
            if (mode === 'offtrail')
              features.push({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: alternative.departure },
                properties: { kind: 'departure' },
              });
            const coordinates =
              r.alternatives[alternativesOnMap[r.point.id] || 0][mode as 'mapped' | 'offtrail'];
            if (coordinates.length > 1)
              features.push({
                type: 'Feature',
                geometry: { type: 'LineString', coordinates },
                properties: { kind: mode },
              });
          }),
      );
    const data: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features };
    if (map.getSource(name)) (map.getSource(name) as GeoJSONSource).setData(data);
    else {
      map.addSource(name, { type: 'geojson', data });
      map.addLayer({
        id: name + '-departure',
        type: 'circle',
        source: name,
        filter: ['==', ['get', 'kind'], 'departure'],
        paint: {
          'circle-radius': 6,
          'circle-color': '#ffe56c',
          'circle-stroke-color': '#17221d',
          'circle-stroke-width': 2,
        },
      });
      map.addLayer({
        id: name + '-fill',
        type: 'fill',
        source: name,
        filter: ['==', ['geometry-type'], 'Polygon'],
        paint: {
          'fill-color': ['case', ['==', ['get', 'kind'], 'exclusion'], '#e84b4b', '#ff9139'],
          'fill-opacity': 0.12,
        },
      });
      map.addLayer({
        id: name + '-line',
        type: 'line',
        source: name,
        paint: {
          'line-color': [
            'match',
            ['get', 'kind'],
            'mapped',
            '#ffe56c',
            'offtrail',
            '#ff69cc',
            'exclusion',
            '#e84b4b',
            '#aabf8d',
          ],
          'line-width': [
            'case',
            ['in', ['get', 'kind'], ['literal', ['mapped', 'offtrail']]],
            4,
            1.5,
          ],
          'line-dasharray': [
            'case',
            ['==', ['get', 'kind'], 'offtrail'],
            ['literal', [2, 2]],
            ['literal', [1, 0]],
          ],
        },
      });
    }
    return () => {
      if (map.getLayer(name + '-departure')) map.removeLayer(name + '-departure');
      if (map.getLayer(name + '-line')) map.removeLayer(name + '-line');
      if (map.getLayer(name + '-fill')) map.removeLayer(name + '-fill');
      if (map.getSource(name)) map.removeSource(name);
    };
  }, [
    map,
    networks,
    selectedNetworks,
    kinds,
    planning,
    area,
    exclusions,
    scenarios,
    scenarioId,
    scenarioDirty,
    alternativesOnMap,
  ]);
  async function attempt(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function importNetwork(file: File) {
    await attempt(async () => {
      const form = new FormData();
      form.append('file', file);
      const n = await api(`/networks/import?kind=${kind}`, { method: 'POST', body: form });
      setNetworks((v) => [...v, n]);
      setSelectedNetworks((v) => [...v, n.id]);
    });
  }
  async function importPolygon(file: File, excluded: boolean) {
    await attempt(async () => {
      const form = new FormData();
      form.append('file', file);
      const v = await api('/travel/import', { method: 'POST', body: form });
      if (v.length !== 1)
        throw Error('Import one explicitly selected travel/exclusion polygon per file.');
      if (excluded) setExclusions((p) => [...p, v[0].geometry]);
      else setArea(v[0].geometry);
    });
  }
  async function apply() {
    const token = ++epoch.current;
    const run = runId;
    await attempt(async () => {
      const p = await api(`/runs/${run}/filters`, {
        method: 'POST',
        body: JSON.stringify({
          network_ids: selectedNetworks,
          kinds,
          distance_m: distance ? miles * 1609.344 : null,
          height_m: height ? feet * 0.3048 : null,
          elevation_m: elevation ? [elevMin * 0.3048, elevMax * 0.3048] : null,
          slope_deg: slope ? [slopeMin, slopeMax] : null,
          aspects: selectedAspects,
        }),
      });
      const v = await api(`/runs/${run}/filters/${p.id}`);
      if (token === epoch.current && run === runRef.current) {
        setApplied(v);
        onFilter(v);
        setDirty(false);
      }
    });
  }
  function coordinate(text: string) {
    const p = text.split(',').map(Number);
    if (p.length !== 2 || p.some((v) => !Number.isFinite(v)))
      throw Error('Use longitude,latitude for network points');
    return p;
  }
  async function planApproaches() {
    await attempt(async () => {
      if (!area || editing) throw Error('Save an explicit travel polygon first');
      const run = runId;
      const token = epoch.current;
      const v = await api(`/runs/${run}/approaches`, {
        method: 'POST',
        body: JSON.stringify({
          ids: kept.map((p) => p.id),
          network_ids: selectedNetworks,
          kinds,
          travel_area: area,
          exclusions,
          weights,
          maximum_slope_deg: maximum,
          start: includeWalk ? coordinate(start) : null,
          pinned: pinned.trim() ? coordinate(pinned) : null,
        }),
      });
      if (run === runRef.current && token === epoch.current) {
        setScenarioId(v.scenario.id);
        setScenarios((old) => [
          ...old,
          { scenario: v.scenario, stale: false, stale_reasons: [], results: null },
        ]);
      }
    });
  }
  async function prepareNetwork() {
    await attempt(async () => {
      if (!area) throw Error('Draw/import a bounded travel area for the network query');
      const coords = area.type === 'Polygon' ? area.coordinates.flat() : area.coordinates.flat(2);
      const bounds = [
        Math.min(...coords.map((c) => c[0])),
        Math.min(...coords.map((c) => c[1])),
        Math.max(...coords.map((c) => c[0])),
        Math.max(...coords.map((c) => c[1])),
      ];
      const p = await api('/network-plans', {
        method: 'POST',
        body: JSON.stringify({ bounds, max_download_mb: budget }),
      });
      setNetworkPlan(p);
      setNetworkPlanId(p.id);
      setDownload(false);
    });
  }
  const scenario = scenarios.find((s) => s.scenario.id === scenarioId);
  const scenarioJob = jobs.find((j) => j.kind === 'approach' && j.plan === scenarioId);
  const networkJob = jobs.find((j) => j.kind === 'network-acquisition' && j.plan === networkPlanId);
  return (
    <section className="scouting-tools">
      <h3>Review and keep setups</h3>
      <button
        className="primary wide"
        disabled={!kept.length}
        onClick={() => onPlanning(!planning)}
      >
        Plan approaches ({kept.length} kept)
      </button>
      <details>
        <summary>Observer access and visible-terrain filters</summary>
        <p>
          Defaults are off. Proximity and height above the nearest mapped line screen observer
          setups; terrain bands apply only to saved visible targets.
        </p>
        <label>
          <input
            type="checkbox"
            checked={distance}
            onChange={(e) => setDistance(e.target.checked)}
          />
          Maximum distance from mapped network
        </label>
        {distance && (
          <label>
            Miles
            <input
              aria-label="Maximum network distance miles"
              type="number"
              min="0"
              value={miles}
              onChange={(e) => setMiles(+e.target.value)}
            />
          </label>
        )}
        <label>
          <input type="checkbox" checked={height} onChange={(e) => setHeight(e.target.checked)} />
          Maximum height above nearest trail/road
        </label>
        {height && (
          <label>
            Feet
            <input
              aria-label="Maximum height above network feet"
              type="number"
              min="0"
              value={feet}
              onChange={(e) => setFeet(+e.target.value)}
            />
          </label>
        )}
        {['roads', 'trails'].map((k) => (
          <label key={k}>
            <input
              type="checkbox"
              checked={kinds.includes(k)}
              onChange={(e) =>
                setKinds((v) => (e.target.checked ? [...v, k] : v.filter((x) => x !== k)))
              }
            />
            {k}
          </label>
        ))}
        <label>
          <input
            type="checkbox"
            checked={elevation}
            onChange={(e) => setElevation(e.target.checked)}
          />
          Visible terrain elevation band (feet)
        </label>
        {elevation && (
          <div className="form-grid">
            <input
              aria-label="Minimum target elevation feet"
              type="number"
              value={elevMin}
              onChange={(e) => setElevMin(+e.target.value)}
            />
            <input
              aria-label="Maximum target elevation feet"
              type="number"
              value={elevMax}
              onChange={(e) => setElevMax(+e.target.value)}
            />
          </div>
        )}
        <label>
          <input type="checkbox" checked={slope} onChange={(e) => setSlope(e.target.checked)} />
          Visible terrain slope range (degrees)
        </label>
        {slope && (
          <div className="form-grid">
            <input
              aria-label="Minimum target slope degrees"
              type="number"
              value={slopeMin}
              onChange={(e) => setSlopeMin(+e.target.value)}
            />
            <input
              aria-label="Maximum target slope degrees"
              type="number"
              value={slopeMax}
              onChange={(e) => setSlopeMax(+e.target.value)}
            />
          </div>
        )}
        <p>Target aspects (none selected = unrestricted, including flats)</p>
        <div className="form-grid">
          {aspects.map((a) => (
            <label key={a}>
              <input
                type="checkbox"
                checked={selectedAspects.includes(a)}
                onChange={(e) =>
                  setSelectedAspects((v) =>
                    e.target.checked ? [...v, a] : v.filter((x) => x !== a),
                  )
                }
              />
              {a}
            </label>
          ))}
        </div>
        <button disabled={busy || !runId} onClick={apply}>
          Apply review filters
        </button>
        <button
          onClick={() => {
            epoch.current++;
            setApplied(null);
            onFilter(null);
            setDirty(false);
          }}
        >
          Show original terrain
        </button>
        {dirty &&
          (distance || height || elevation || slope || selectedAspects.length > 0 || applied) && (
            <p role="status">
              Edited filters are unapplied. Apply to update matching areas and shading.
            </p>
          )}
        {applied && (
          <p>
            Applied matching-area order; original scores and coordinates retained. Unknown access
            does not qualify for enabled access filters.
          </p>
        )}
      </details>
      <details open={planning}>
        <summary>Mapped road/trail sources</summary>
        <label>
          Imported network type
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="trails">Trails</option>
            <option value="roads">Roads</option>
          </select>
        </label>
        <label>
          Import line network
          <input
            aria-label="Import road trail network"
            type="file"
            accept=".geojson,.json,.kml,.kmz,.gpx"
            onChange={(e) => e.target.files?.[0] && importNetwork(e.target.files[0])}
          />
        </label>
        {networks.map((n) => (
          <label key={n.id}>
            <input
              type="checkbox"
              checked={selectedNetworks.includes(n.id)}
              onChange={(e) =>
                setSelectedNetworks((v) =>
                  e.target.checked ? [...v, n.id] : v.filter((id) => id !== n.id),
                )
              }
            />
            {n.kind}: {n.source}
            <small>
              Source date: {n.source_date}. {n.coverage_note}
            </small>
          </label>
        ))}
        <button disabled={!area || active || busy} onClick={prepareNetwork}>
          Review bounded USFS download plan
        </button>
        {!area && (
          <p>For automatic USFS acquisition, keep a setup and draw/import the travel area below.</p>
        )}
        {networkJob && (
          <p role="status" className={networkJob.status === 'failed' ? 'error' : 'hint'}>
            Network acquisition {networkJob.status}: {networkJob.error || networkJob.stage}
          </p>
        )}
        {networkPlan && (
          <div className="plan">
            <p>
              {networkPlan.provider}: up to {(networkPlan.estimated_bytes / 1e6).toFixed(0)} MB ·
              shared {budget} MB cap. {networkPlan.note}
            </p>
            <label>
              <input
                type="checkbox"
                checked={download}
                onChange={(e) => setDownload(e.target.checked)}
              />
              Allow this reviewed network download
            </label>
            <button
              disabled={!download || active || busy}
              onClick={() =>
                attempt(async () => {
                  await api(`/network-plans/${networkPlan.id}/start`, {
                    method: 'POST',
                    body: JSON.stringify({ download, analysis_plan: analysisPlan || null }),
                  });
                })
              }
            >
              Acquire USFS roads and trails
            </button>
          </div>
        )}
      </details>
      {planning && (
        <div className="approach-controls">
          <h3>Plan independent provisional approaches</h3>
          {kept.map((p) => (
            <p key={p.id}>
              {p.id}: {p.latitude.toFixed(7)}, {p.longitude.toFixed(7)} · original terrain-visible{' '}
              {number(p.coverage, 3)} km²
            </p>
          ))}
          <p>
            Required travel area defines the search domain; it does not infer permission. Each kept
            setup is planned independently.
          </p>
          <label>
            Import travel polygon
            <input
              aria-label="Import travel area"
              type="file"
              accept=".geojson,.json,.kml,.kmz"
              onChange={(e) => e.target.files?.[0] && importPolygon(e.target.files[0], false)}
            />
          </label>
          <label>
            Import optional exclusion
            <input
              aria-label="Import approach exclusion"
              type="file"
              accept=".geojson,.json,.kml,.kmz"
              onChange={(e) => e.target.files?.[0] && importPolygon(e.target.files[0], true)}
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={drawingExclusion}
              onChange={(e) => setDrawingExclusion(e.target.checked)}
            />
            Draw an exclusion instead of travel area
          </label>
          {map && (
            <Drawing
              key={drawingExclusion ? 'exclusion' : 'travel'}
              map={map}
              geometry={drawingExclusion ? null : area}
              onSave={async (f) => {
                if (drawingExclusion) setExclusions((v) => [...v, f.geometry]);
                else setArea(f.geometry);
              }}
              onInvalidate={() => {
                setEditing(true);
              }}
              onRestore={() => setEditing(false)}
              onEditing={setEditing}
              onClear={() => {
                if (drawingExclusion) setExclusions([]);
                else setArea(null);
              }}
            />
          )}
          <p>
            {area ? 'Travel boundary saved' : 'Travel boundary required'} · {exclusions.length}{' '}
            exclusions
          </p>
          {!!exclusions.length && (
            <button onClick={() => setExclusions([])}>Clear exclusions</button>
          )}
          <label>
            Departure comparison
            <select
              value={includeWalk ? 'walk' : 'nearby'}
              onChange={(e) => setIncludeWalk(e.target.value === 'walk')}
            >
              <option value="nearby">Compare nearby departures (within one mile)</option>
              <option value="walk">Include trail walk from selected network start</option>
            </select>
          </label>
          {pick && (
            <p role="status">
              Click the selected mapped network to set {pick}.{' '}
              <button onClick={() => setPick(null)}>Cancel point selection</button>
            </p>
          )}
          {includeWalk && (
            <button onClick={() => setPick('start')}>Choose network start on map</button>
          )}
          <button onClick={() => setPick('pinned')}>Pin a departure on map</button>
          {includeWalk && (
            <label>
              Network start (longitude,latitude)
              <input
                aria-label="Network starting point"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
          )}
          <label>
            Optional pinned departure (longitude,latitude)
            <input
              aria-label="Pinned network departure"
              value={pinned}
              onChange={(e) => setPinned(e.target.value)}
            />
          </label>
          <p>
            Balanced preferences are one each. Weights are relative costs, not walking times or
            safety predictions. Distance always contributes.
          </p>
          {Object.entries(weights).map(([k, v]) => (
            <label key={k}>
              Avoid{' '}
              {k === 'gain'
                ? 'cumulative climbing'
                : k === 'slope'
                  ? 'steep terrain'
                  : k + ' cover'}
              : {v}
              <input
                aria-label={`Approach ${k} weight`}
                type="range"
                min="0"
                max="5"
                step=".5"
                value={v}
                onChange={(e) => setWeights((w) => ({ ...w, [k]: +e.target.value }))}
              />
            </label>
          ))}
          <label>
            Maximum modeled slope (degrees)
            <input
              aria-label="Maximum approach slope"
              type="number"
              min="1"
              max="60"
              value={maximum}
              onChange={(e) => setMaximum(+e.target.value)}
            />
          </label>
          <p>
            30° default is a desktop screening threshold. Unknown vegetation receives maximum cover
            penalties when avoidance is enabled.
          </p>
          <button
            className="primary wide"
            disabled={
              !kept.length || !area || editing || active || busy || !selectedNetworks.length
            }
            onClick={planApproaches}
          >
            Compute independent approaches
          </button>
          {scenarioJob && (
            <p role="status" className={scenarioJob.status === 'failed' ? 'error' : 'hint'}>
              Approach job {scenarioJob.status}: {scenarioJob.error || scenarioJob.stage}
            </p>
          )}
          {scenarioDirty && scenarioId && (
            <p role="status">
              Approach settings changed. Prior scenario retained; explicitly recompute to use these
              settings.
            </p>
          )}
          <label>
            Saved scenarios
            <select
              value={scenarioId}
              onChange={(e) => {
                loadScenario(e.target.value);
              }}
            >
              <option value="">Choose a saved scenario…</option>
              {scenarios.map((s) => (
                <option key={s.scenario.id} value={s.scenario.id}>
                  {s.scenario.id.slice(0, 8)}
                  {s.stale ? ' · stale' : ''}
                </option>
              ))}
            </select>
          </label>
          {scenario && (
            <div>
              <p className="notice">{scenario.scenario.notice}</p>
              {scenario.stale && (
                <p className="error">Stale: {scenario.stale_reasons.join('; ')}</p>
              )}
              {!scenario.results && (
                <p>Results pending; see the active job and its errors below.</p>
              )}
              {scenario.results?.results.map((r, i) => (
                <article key={r.point.id}>
                  <h4>
                    {r.point.id} · original terrain-visible {number(r.point.coverage, 3)} km²
                  </h4>
                  {r.message && <p>{r.message}</p>}
                  {r.pinned_status && <p>{r.pinned_status}</p>}
                  {r.message && <pre>{JSON.stringify(r.limiting_evidence, null, 2)}</pre>}
                  {r.alternatives.map((a, j) => (
                    <div className="plan" key={j}>
                      <b>{a.labels.join(' / ')}</b>
                      <button
                        disabled={scenario.stale || scenarioDirty}
                        onClick={() => showAlternative(r.point.id, j)}
                      >
                        Show this alternative on map
                      </button>
                      <p>
                        Departure: {a.departure[1].toFixed(7)}, {a.departure[0].toFixed(7)}
                      </p>
                      <p>
                        Mapped walk {number(a.mapped_distance_m)} m · off-trail{' '}
                        {number(a.offtrail_distance_m)} m · ascent {number(a.ascent_m)} m · descent{' '}
                        {number(a.descent_m)} m · max slope {number(a.maximum_slope_deg)}°
                      </p>
                      <p>
                        Average known off-trail tree cover{' '}
                        {number(a.average_tree === null ? null : a.average_tree * 100)}% · shrub{' '}
                        {number(a.average_shrub === null ? null : a.average_shrub * 100)}% · path
                        unknown cover{' '}
                        {number(
                          a.unknown_cover_fraction === null ? null : a.unknown_cover_fraction * 100,
                        )}
                        %. Unknown values use maximum penalties.
                      </p>
                      <p>
                        Cost {number(a.cost)} ·{' '}
                        {Object.entries(a.cost_contributions)
                          .map(([k, v]) => `${k}: ${number(v)}`)
                          .join(' · ')}
                      </p>
                      <Profile points={a.elevation_profile} mappedMeters={a.mapped_distance_m} />
                      <p>
                        Solid yellow = mapped trail; dashed pink = off-trail. Grid resolution: 20 m.{' '}
                        {scenario.scenario.notice}
                      </p>
                      {!scenario.stale && !scenarioDirty && (
                        <p>
                          <a
                            href={`/api/approaches/${scenario.scenario.id}/export/geojson?point=${i}&alternative=${j}`}
                          >
                            Provisional approach GeoJSON
                          </a>{' '}
                          ·{' '}
                          <a
                            href={`/api/approaches/${scenario.scenario.id}/export/gpx?point=${i}&alternative=${j}`}
                          >
                            Provisional approach GPX track + unchanged destination waypoint
                          </a>
                        </p>
                      )}
                    </div>
                  ))}
                </article>
              ))}
            </div>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
function Profile({ points, mappedMeters }: { points: number[][]; mappedMeters: number }) {
  if (!points.length) return null;
  const min = Math.min(...points.map((p) => p[1])),
    max = Math.max(...points.map((p) => p[1]));
  const end = points[points.length - 1][0] || 1;
  return (
    <figure>
      <svg role="img" aria-label="Ground elevation profile" viewBox="0 0 300 110">
        <polyline
          fill="none"
          stroke="#d6af35"
          strokeWidth="2"
          points={points
            .filter((p) => p[0] <= mappedMeters)
            .map((p) => `${10 + (p[0] / end) * 280},${90 - ((p[1] - min) / (max - min || 1)) * 70}`)
            .join(' ')}
        />
        <polyline
          fill="none"
          stroke="#ff69cc"
          strokeWidth="2"
          points={points
            .filter((p) => p[0] >= mappedMeters)
            .map((p) => `${10 + (p[0] / end) * 280},${90 - ((p[1] - min) / (max - min || 1)) * 70}`)
            .join(' ')}
        />
        <text x="10" y="105" fill="currentColor" fontSize="10">
          0–{end.toFixed(0)} m distance; {min.toFixed(0)}–{max.toFixed(0)} m ground elevation
        </text>
      </svg>
    </figure>
  );
}
