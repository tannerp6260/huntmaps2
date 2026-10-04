import { Help } from './drawing';
import TerrainCriteria, {
  defaultCriteria,
  validCriteria,
  type TargetCriteria,
} from './target-criteria';
import { inputSignature } from './approach-inputs';
import DownloadReview from './download-review';
import JobProgress from './job-progress';
import { networkResponse } from './network-response';
import { useEffect, useRef, useState } from 'react';
import type { Map, GeoJSONSource } from 'maplibre-gl';
import { Drawing } from './drawing';
import { useJobs } from './polling';
type Polygon = GeoJSON.Polygon | GeoJSON.MultiPolygon;
type FilterRow = {
  id: string;
  original_km2: number;
  matching_km2: number;
  matching_unknown_km2: number;
  qualifies: boolean;
  access: { status: string; distance_m: number | null; height_m: number | null };
};
export type AppliedFilter = {
  recommendation_ids?: string[];
  nearby_ids?: Record<string, string[]>;
  profile: { id: string };
  candidates: FilterRow[];
};
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
  point_stale?: Record<string, string>;
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
  initialSearch,
  locationStamp,
  recovery,
  runId,
  observerBoundary,
  onApproach,
  onInputsChanged,
  map,
  api,
  onFilter,
  stamp,
  analysisPlan,
  budget,
  planning,
  onPlanning,
}: {
  recovery?: { kind: string; id: string } | null;
  initialSearch?: {
    ranking_version?: number;
    target_filters?: TargetCriteria;
    avoid_dense_vegetation?: boolean;
    nearby_radius_m?: number;
    tree_threshold_percent?: number;
  };
  runId: string;
  observerBoundary?: GeoJSON.FeatureCollection;
  onApproach?: (cid: string, scenario: string, alternative: number) => void;
  onInputsChanged?: (scenario: string) => void;
  map: Map | null;
  api: Api;
  onFilter: (v: AppliedFilter | null) => void;
  stamp: string;
  locationStamp: string;
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
  const [filterTargets, setFilterTargets] = useState<TargetCriteria>(defaultCriteria);
  const [avoidDense, setAvoidDense] = useState(false);
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
      inputSignature({
        area,
        exclusions,
        weights,
        maximum,
        ids: selectedNetworks,
        kinds,
        start: includeWalk && start.trim() ? start.split(',').map(Number) : null,
        pinned: pinned.trim() ? pinned.split(',').map(Number) : null,
      }) !==
        inputSignature({
          area: currentScenario.travel_area,
          exclusions: currentScenario.exclusions,
          weights: currentScenario.weights,
          maximum: currentScenario.maximum_slope_deg,
          ids: currentScenario.network_ids,
          kinds: currentScenario.kinds,
          start: currentScenario.start,
          pinned: currentScenario.pinned,
        }));
  useEffect(() => {
    if (!recovery) return;
    if (recovery.kind === 'approach')
      void api('/approaches/' + recovery.id)
        .then((v) => {
          const s = v.scenario;
          setScenarios((old) => [...old.filter((q) => q.scenario.id !== s.id), v]);
          if (s.run_id !== runId) return;
          setScenarioId(s.id);
          onPlanning(true);
          setArea(s.travel_area);
          setExclusions(s.exclusions);
          setWeights(s.weights);
          setMaximum(s.maximum_slope_deg);
          setSelectedNetworks(s.network_ids);
          setKinds(s.kinds);
          setIncludeWalk(!!s.start);
          setStart(s.start?.join(',') || '');
          setPinned(s.pinned?.join(',') || '');
        })
        .catch((e) => setError(String(e)));
    else
      void api('/network-plans/' + recovery.id)
        .then((v) => {
          setNetworkPlanId(recovery.id);
          setNetworkPlan(v.plan);
        })
        .catch((e) => setError(String(e)));
  }, [recovery?.id]);
  useEffect(() => {
    if (scenarioDirty && scenarioId) onInputsChanged?.(scenarioId);
  }, [scenarioDirty, scenarioId]);
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
    setEditing(false);
    setAlternativesOnMap({});
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
    if (!recovery) onPlanning(false);
  }, [runId]);
  useEffect(() => {
    let alive = true;
    api('/networks')
      .then(networkResponse)
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
    epoch.current++;
    if (applied)
      setError('Saved locations changed. Reapply review filters to use their current coverage.');
    setApplied(null);
    onFilter(null);
  }, [locationStamp]);
  useEffect(() => {
    setDirty(true);
    epoch.current++;
  }, [
    distance,
    miles,
    height,
    filterTargets,
    avoidDense,
    feet,
    kinds.join(','),
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
    const features: GeoJSON.Feature[] = [];
    if (planning && area)
      features.push({ type: 'Feature', geometry: area, properties: { kind: 'travel' } });
    if (planning)
      exclusions.forEach((g) =>
        features.push({ type: 'Feature', geometry: g, properties: { kind: 'exclusion' } }),
      );
    const scenario = scenarios.find((s) => s.scenario.id === scenarioId);
    if (planning && scenario && (scenarioDirty || scenario.stale))
      features.push({
        type: 'Feature',
        geometry: scenario.scenario.travel_area,
        properties: { kind: 'saved-boundary' },
      });
    if (planning && scenario)
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
  const currentFilter = useRef({ criteria: filterTargets, avoidDense, stamp: locationStamp });
  currentFilter.current = { criteria: filterTargets, avoidDense, stamp: locationStamp };
  const initialStamp = JSON.stringify(initialSearch);
  useEffect(() => {
    if (initialSearch?.ranking_version !== 2) return;
    const startingStamp = locationStamp,
      run = runId;
    const criteria = { ...defaultCriteria(), ...initialSearch.target_filters };
    setFilterTargets(criteria);
    setAvoidDense(initialSearch.avoid_dense_vegetation ?? false);
    let alive = true;
    void api(`/runs/${run}/filters`, {
      method: 'POST',
      body: JSON.stringify({
        ...criteria,
        version: undefined,
        avoid_dense_vegetation: initialSearch.avoid_dense_vegetation ?? false,
        nearby_radius_m: initialSearch.nearby_radius_m ?? 30,
        tree_threshold_percent: initialSearch.tree_threshold_percent ?? 10,
      }),
    })
      .then((p) => api(`/runs/${run}/filters/${p.id}`))
      .then((v) => {
        if (
          alive &&
          startingStamp === currentFilter.current.stamp &&
          inputSignature(criteria) === inputSignature(currentFilter.current.criteria) &&
          (initialSearch.avoid_dense_vegetation ?? false) === currentFilter.current.avoidDense &&
          run === runRef.current
        ) {
          setApplied(v);
          onFilter(v);
          setDirty(false);
        }
      })
      .catch((e) => {
        if (alive) setError(String(e));
      });
    return () => {
      alive = false;
    };
  }, [runId, initialStamp]);
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
          ...filterTargets,
          version: undefined,
          avoid_dense_vegetation: avoidDense,
          nearby_radius_m: initialSearch?.nearby_radius_m ?? 30,
          tree_threshold_percent: initialSearch?.tree_threshold_percent ?? 10,
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
        const saved = v.scenario;
        setArea(saved.travel_area);
        setExclusions(saved.exclusions);
        setWeights(saved.weights);
        setMaximum(saved.maximum_slope_deg);
        setSelectedNetworks(saved.network_ids);
        setKinds(saved.kinds);
        setIncludeWalk(!!saved.start);
        setStart(saved.start?.join(',') || '');
        setPinned(saved.pinned?.join(',') || '');
        setEditing(false);
        setScenarioId(saved.id);
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
      <h3>{planning ? 'Compare approaches' : 'Terrain and access filters'}</h3>
      <button
        className="primary wide"
        disabled={!kept.length}
        onClick={() => onPlanning(!planning)}
      >
        Compare approaches ({kept.length} shortlisted)
      </button>
      {!kept.length && <small>Shortlist at least one setup to compare approaches.</small>}
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
              type="text"
              inputMode="decimal"
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
        <TerrainCriteria
          value={filterTargets}
          onChange={(v) => {
            setFilterTargets(v);
            setDirty(true);
          }}
        />
        <label className="source-choice">
          <input
            type="checkbox"
            aria-label="Avoid standing in dense vegetation"
            checked={avoidDense}
            onChange={(e) => {
              setAvoidDense(e.target.checked);
              setDirty(true);
            }}
          />
          Avoid standing in dense vegetation <Help topic="clearing" />
        </label>
        <button disabled={busy || !runId || !validCriteria(filterTargets)} onClick={apply}>
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
          (distance ||
            height ||
            avoidDense ||
            applied ||
            Object.values(filterTargets).some((v) =>
              Array.isArray(v) ? v.length > 0 : v !== null && v !== 1,
            )) && (
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
      <details>
        <summary>Advanced road/trail sources</summary>
        <p className="hint">
          We consider both roads and trails from loaded, verified inventories. Import or select
          sources here only when you need an override.
        </p>
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
          <div role="status" className={networkJob.status === 'failed' ? 'error' : 'hint'}>
            <JobProgress job={networkJob} />
            Network acquisition {networkJob.status}: {networkJob.error || networkJob.stage}
          </div>
        )}
        {networkPlan && (
          <div className="plan">
            <DownloadReview plan={networkPlan} bytes={networkPlan.estimated_bytes ?? null} />
            <p>
              {networkPlan.provider}: up to {(networkPlan.estimated_bytes / 1e6).toFixed(0)} MB ·
              shared {budget} MB cap. {networkPlan.note}
            </p>
            <p className="hint">
              Acquire roads and trails approves this displayed plan and allowance.
            </p>
            <button
              disabled={active || busy || networkPlan.storage?.blocked}
              onClick={() =>
                attempt(async () => {
                  await api(`/network-plans/${networkPlan.id}/start`, {
                    method: 'POST',
                    body: JSON.stringify({ download: true, analysis_plan: analysisPlan || null }),
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
          <h3>
            Compare ways to reach your spots <Help topic="approach" />
          </h3>
          <p className="notice">
            Compare possible ways from mapped roads or trails to each shortlisted spot, accounting
            for distance, climbing, steepness and vegetation. Each spot is compared independently.
          </p>
          <p>
            Approach search area <Help topic="searchArea" /> · Areas to avoid{' '}
            <Help topic="avoidance" />
          </p>
          <ol className="approach-checklist">
            <li>Travel boundary: {editing ? 'confirm edits' : area ? 'saved' : 'required'}</li>
            <li>
              Network sources: {selectedNetworks.length} selected; coverage remains source dependent
            </li>
            <li>
              Optional network start:{' '}
              {includeWalk ? start || 'choose a mapped point' : 'nearby departures'}
            </li>
            <li>
              Preferences: {Object.values(weights).every((v) => v === 1) ? 'balanced' : 'custom'};
              modeled slope limit {maximum}°
            </li>
            <li>Computation: {scenarioJob?.stage || 'ready after the required inputs'}</li>
          </ol>
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
          <button
            onClick={() => {
              const geometries = observerBoundary?.features
                .map((f) => f.geometry)
                .filter((g) => g.type === 'Polygon' || g.type === 'MultiPolygon');
              if (geometries?.length === 1) setArea(geometries[0] as Polygon);
              else
                setError(
                  'Import or draw one explicit travel polygon; the observer area has multiple geometries.',
                );
            }}
          >
            Start from observer boundary
          </button>
          <p>
            Observer area selects standing positions. Travel area bounds the approach search; expand
            it to include departures.
          </p>
          <label>
            Import approach search area
            <input
              aria-label="Import travel area"
              type="file"
              accept=".geojson,.json,.kml,.kmz"
              onChange={(e) => e.target.files?.[0] && importPolygon(e.target.files[0], false)}
            />
          </label>
          <label>
            Import area to avoid
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
            Draw an area to avoid instead of the search area
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
          <details>
            <summary>More options · pinned departure and preferences</summary>
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
              Preferences <Help topic="weights" />. Balanced preferences are one each. Weights are
              relative costs, not walking times or safety predictions. Distance always contributes.
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
              Maximum modeled slope (degrees) <Help topic="slope" />
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
              30° default is a desktop screening threshold. Unknown vegetation receives maximum
              cover penalties when avoidance is enabled.
            </p>
          </details>
          {(!kept.length || !area || editing || active || busy || !selectedNetworks.length) && (
            <p>
              {editing
                ? 'Confirm this boundary to continue.'
                : !area
                  ? 'Confirm an approach search boundary that includes your spots and a road or trail.'
                  : !selectedNetworks.length
                    ? 'Select mapped road/trail sources.'
                    : active || busy
                      ? 'Wait for the current job or cancel it.'
                      : 'Shortlist at least one setup.'}
            </p>
          )}
          <button
            className="primary wide"
            disabled={
              !kept.length || !area || editing || active || busy || !selectedNetworks.length
            }
            onClick={planApproaches}
          >
            Compare approaches
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
              <option value="">Choose a saved comparison…</option>
              {scenarios.map((s) => (
                <option key={s.scenario.id} value={s.scenario.id}>
                  {s.scenario.points.length} spots · slope limit {s.scenario.maximum_slope_deg}° ·{' '}
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
                  {r.message && (
                    <p>
                      {r.message} No path found does not certify inaccessibility. Change the travel
                      boundary/preferences or remove this setup from the shortlist.
                    </p>
                  )}
                  {r.pinned_status && <p>{r.pinned_status}</p>}
                  {r.message && (
                    <>
                      <p className="error">{explainNoPath(r.limiting_evidence)}</p>
                      <details>
                        <summary>Technical evidence</summary>
                        <pre>{JSON.stringify(r.limiting_evidence, null, 2)}</pre>
                      </details>
                      <button
                        onClick={() => {
                          if (map)
                            map.flyTo({ center: [r.point.longitude, r.point.latitude], zoom: 14 });
                        }}
                      >
                        Show this spot and search boundary
                      </button>
                    </>
                  )}
                  {r.alternatives.map((a, j) => (
                    <div className="plan" key={j}>
                      <b>
                        {a.labels.join(' / ')} ·{' '}
                        {number(a.mapped_distance_m + a.offtrail_distance_m)} m total
                      </b>
                      <button
                        className="primary"
                        disabled={
                          scenario.stale || !!scenario.point_stale?.[r.point.id] || scenarioDirty
                        }
                        onClick={() => onApproach?.(r.point.id, scenario.scenario.id, j)}
                      >
                        Use this approach
                      </button>
                      <button disabled={!map} onClick={() => showAlternative(r.point.id, j)}>
                        Show this alternative on map
                      </button>
                      {(scenario.stale || scenario.point_stale?.[r.point.id] || scenarioDirty) && (
                        <p className="hint">
                          Saved approach preview.{' '}
                          {scenario.stale
                            ? scenario.stale_reasons.join('; ')
                            : scenario.point_stale?.[r.point.id] ||
                              'Settings differ from this saved comparison.'}{' '}
                          Recompute or reload its saved settings before selecting it.
                        </p>
                      )}
                      {!map && <p className="hint">The map is still opening.</p>}
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
                      {!scenario.stale && !scenario.point_stale?.[r.point.id] && !scenarioDirty && (
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

export function explainNoPath(raw: unknown) {
  const e = (raw || {}) as Record<string, unknown>;
  const reasons: string[] = [];
  if (e.endpoint_inside_travel_area === false)
    reasons.push(
      'This spot is outside the approach search area. Expand the boundary to include it.',
    );
  if (e.network_lines === 0 || e.departures === 0)
    reasons.push(
      'There are no mapped road or trail departures in the search area. Expand it to include a road or trail, or review source coverage.',
    );
  if (e.endpoint_inside_travel_area !== false && e.endpoint_valid_terrain === false)
    reasons.push(
      'This spot has missing terrain, is in an area to avoid, or exceeds the slope limit. Review those constraints.',
    );
  if (!reasons.length)
    reasons.push(
      'No connected path satisfies this boundary, areas to avoid and slope limit. Expand the search area or adjust preferences; this does not prove the spot is inaccessible.',
    );
  return reasons.join(' ');
}
