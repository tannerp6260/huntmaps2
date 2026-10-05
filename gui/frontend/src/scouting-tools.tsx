import DecimalField from './decimal-field';
import { area as areaText, yards, feet as feetText, imperialNotice } from './units';
import { decimalValue } from './decimal-input';
import type { Workflow } from './workflow';
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
  workflow,
  focusedId,
  onFocus,
  onDecision,
  onInspectStage,
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
  filterReset,
  stamp,
  analysisPlan,
  budget,
  planning,
  onPlanning,
}: {
  workflow: Workflow | null;
  focusedId: string;
  onFocus: (cid: string) => void;
  onDecision: (cid: string, action: string) => Promise<boolean>;
  onInspectStage: () => void;
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
  onApproach?: (cid: string, scenario: string, alternative: number) => Promise<boolean>;
  onInputsChanged?: (cid: string, scenario: string) => void;
  map: Map | null;
  api: Api;
  onFilter: (v: AppliedFilter | null) => void;
  filterReset: number;
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
    [miles, setMiles] = useState('880'),
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
  const [preferencesValid, setPreferencesValid] = useState(true);
  const [recoveryView, setRecoveryView] = useState<Scenario | null>(null);
  const recoveredId = useRef('');
  const [review, setReview] = useState<any>(null);
  const [hydrated, setHydrated] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const reviewRef = useRef<any>(null);
  const draftCache = useRef<Record<string, any>>({});
  const revisionRef = useRef(workflow?.points[focusedId]?.point.revision);
  revisionRef.current = workflow?.points[focusedId]?.point.revision;
  const focusRef = useRef(focusedId);
  focusRef.current = focusedId;
  const hydrationFocus = useRef('');
  const saving = useRef(Promise.resolve());
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
    recoveredId.current = '';
    if (recovery.kind === 'approach')
      void api('/approaches/' + recovery.id)
        .then((v) => {
          const s = v.scenario;
          setScenarios((old) => [...old.filter((q) => q.scenario.id !== s.id), v]);
          if (s.run_id !== runId) return;
          setRecoveryView(v);
          onPlanning(true);
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
    if (hydrated && scenarioDirty && scenarioId) onInputsChanged?.(focusedId, scenarioId);
  }, [scenarioDirty, scenarioId, focusedId]);
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
  const sortedIds = kept
    .slice()
    .sort((a, b) => {
      const coverage = (p: Kept) =>
        applied?.candidates.find((r) => r.id === p.id)?.matching_km2 ?? p.coverage;
      return (
        (coverage(b) ?? -1) - (coverage(a) ?? -1) ||
        (b.coverage ?? -1) - (a.coverage ?? -1) ||
        a.id.localeCompare(b.id)
      );
    })
    .map((p) => p.id);
  function draft() {
    return {
      travel_area: area,
      exclusions,
      network_ids: selectedNetworks,
      kinds,
      weights,
      maximum_slope_deg: maximum,
      start: includeWalk && start.trim() ? coordinate(start) : null,
      pinned: pinned.trim() ? coordinate(pinned) : null,
      boundary_confirmed: !!area && !editing,
      scenario: scenarioId || null,
      alternative: alternativesOnMap[focusedId] || 0,
      attempted,
    };
  }
  function saveReview(value?: any, cid = focusedId, focus = cid) {
    const run = runId;
    const ids = sortedIds;
    const task = async () => {
      const state = await api(`/runs/${run}/workflow`);
      const retained = Object.entries(state.points)
        .filter(([, p]: any) => p.shortlisted)
        .map(([id]) => id);
      const ordered = [
        ...ids.filter((id) => retained.includes(id)),
        ...retained.filter((id) => !ids.includes(id)),
      ];
      const current = reviewRef.current;
      const v = await api(`/runs/${run}/approach-review`, {
        method: 'PUT',
        body: JSON.stringify({
          revision: current?.revision || 0,
          workflow_revision: state.revision,
          ids: ordered,
          active_point: retained.includes(focus) ? focus : ordered[0] || null,
          ...(value && retained.includes(cid)
            ? { draft: value, point: workflow?.points[cid]?.point || state.points[cid].point }
            : {}),
        }),
      });
      if (run === runRef.current) {
        reviewRef.current = v;
        setReview(v);
      }
    };
    const result = saving.current.catch(() => {}).then(task);
    saving.current = result;
    return result;
  }
  function focusSpot(cid: string) {
    try {
      if (hydrated && hydrationFocus.current === focusedId)
        void saveReview(draftCache.current[focusedId] || draft()).catch((e) => setError(String(e)));
      restoreDraft(cid, reviewRef.current);
      onFocus(cid);
    } catch (e) {
      setError(String(e));
    }
  }
  function restoreDraft(cid: string, v: any) {
    const d = draftCache.current[cid] || v?.drafts[cid];
    if (d) {
      setArea(d.travel_area);
      setExclusions(d.exclusions);
      setWeights(d.weights);
      setMaximum(d.maximum_slope_deg);
      setSelectedNetworks(d.network_ids);
      setKinds(d.kinds);
      setIncludeWalk(!!d.start);
      setStart(d.start?.join(',') || '');
      setPinned(d.pinned?.join(',') || '');
      setEditing(!d.boundary_confirmed);
      setScenarioId(d.scenario || workflow?.points[cid]?.approach?.scenario || '');
      setAlternativesOnMap({ [cid]: d.alternative || 0 });
      setAttempted(!!d.attempted);
    } else {
      setWeights({ slope: 1, gain: 1, tree: 1, shrub: 1 });
      setMaximum(30);
      setScenarioId('');
      setAlternativesOnMap({});
      setAttempted(false);
      setIncludeWalk(false);
      setStart('');
      setPinned('');
      // Reuse the confirmed search area, but retain independent preferences per spot.
      const shared = Object.values(v?.drafts || {}).find((q: any) => q.boundary_confirmed) as any;
      if (shared) {
        setArea(shared.travel_area);
        setExclusions(shared.exclusions);
        setEditing(false);
      }
    }
    setPreferencesValid(true);
    hydrationFocus.current = cid;
    setHydrated(true);
  }
  useEffect(() => {
    if (!planning || !kept.length) return;
    let alive = true;
    setHydrated(false);
    saving.current
      .catch(() => {})
      .then(() => api(`/runs/${runId}/approach-review`))
      .then(async (v) => {
        if (!alive) return;
        reviewRef.current = v;
        setReview(v);
        const order = v?.queue.filter((cid: string) => sortedIds.includes(cid)) || sortedIds;
        let cid = v?.active_point && order.includes(v.active_point) ? v.active_point : order[0];
        if (recovery?.kind === 'approach' && recoveredId.current !== recovery.id) {
          const recovered = await api('/approaches/' + recovery.id);
          if (!alive) return;
          recoveredId.current = recovery.id;
          setRecoveryView(recovered);
          if (recovered.scenario.run_id === runId) {
            const matching = recovered.scenario.points.find((p: Kept) => sortedIds.includes(p.id));
            if (matching) {
              cid = matching.id;
              draftCache.current[cid] = {
                ...recovered.scenario,
                boundary_confirmed: true,
                scenario: recovered.scenario.id,
                alternative: 0,
                attempted: true,
              };
            }
          }
        }
        if (!cid) return;
        onFocus(cid);
        restoreDraft(cid, v);
        await saveReview(undefined, cid);
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
      const pending = pendingDraft.current;
      if (pending)
        void saveReview(draftCache.current[pending.cid] || pending.value, pending.cid).catch(
          () => {},
        );
      setHydrated(false);
      hydrationFocus.current = '';
    };
  }, [planning, runId, kept.length > 0, recovery]);
  const pendingDraft = useRef<{ cid: string; value: any } | null>(null);
  if (hydrated) {
    try {
      pendingDraft.current = { cid: hydrationFocus.current, value: draft() };
      if (hydrationFocus.current === focusedId)
        draftCache.current[focusedId] = pendingDraft.current.value;
    } catch {
      /* incomplete coordinate input */
    }
  }
  useEffect(() => {
    if (
      !planning ||
      !hydrated ||
      !sortedIds.includes(focusedId) ||
      hydrationFocus.current === focusedId
    )
      return;
    const previous = pendingDraft.current;
    if (previous && previous.cid !== focusedId)
      void saveReview(draftCache.current[previous.cid] || previous.value, previous.cid).catch((e) =>
        setError(String(e)),
      );
    restoreDraft(focusedId, reviewRef.current);
    void saveReview(undefined, focusedId).catch((e) => setError(String(e)));
  }, [focusedId, planning, hydrated]);
  useEffect(() => {
    if (!planning || !hydrated || !review) return;
    const retained = sortedIds;
    if (
      retained.some((id) => !review.queue.includes(id)) ||
      review.queue.some((id: string) => !retained.includes(id))
    )
      void saveReview().catch((e) => setError(String(e)));
  }, [planning, hydrated, sortedIds.join(','), workflow?.revision]);
  const draftSignature = JSON.stringify([
    area,
    exclusions,
    selectedNetworks,
    kinds,
    weights,
    maximum,
    includeWalk,
    start,
    pinned,
    editing,
    scenarioId,
    alternativesOnMap,
    attempted,
  ]);
  useEffect(() => {
    if (!planning || !hydrated || hydrationFocus.current !== focusedId) return;
    const timer = setTimeout(() => {
      try {
        void saveReview(draft()).catch((e) => setError(String(e)));
      } catch (e) {
        setError(String(e));
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [draftSignature, focusedId, planning, hydrated]);
  const queue = (review?.queue || sortedIds).filter(
    (cid: string) => workflow?.points[cid]?.shortlisted,
  );
  const hasShortlist = Object.values(workflow?.points || {}).some((p) => p.shortlisted);
  const unresolved = queue.filter((cid: string) => !workflow?.points[cid]?.approach);
  useEffect(() => {
    if (planning && hydrated && queue.length && !queue.includes(focusedId))
      onFocus(unresolved[0] || queue[0]);
  }, [planning, hydrated, focusedId, queue.join(','), workflow?.revision]);
  async function nextSpot(action: 'approach' | 'dismiss', index = 0) {
    try {
      await saveReview(draft());
      const ok =
        action === 'approach'
          ? await onApproach?.(focusedId, scenarioId, index)
          : await onDecision(focusedId, 'dismiss');
      if (!ok) return;
      const next = [
        ...queue.slice(queue.indexOf(focusedId) + 1),
        ...queue.slice(0, queue.indexOf(focusedId)),
      ].find((cid: string) => !workflow?.points[cid]?.approach);
      if (next) onFocus(next);
      else setError('');
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    epoch.current++;
    setApplied(null);
    setDirty(false);
  }, [filterReset]);
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
      scenario.results?.results
        .filter((r) => r.point.id === focusedId)
        .forEach(
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
    focusedId,
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
      else {
        setArea(v[0].geometry);
        setEditing(true);
      }
    });
  }
  async function apply() {
    if (distance && decimalValue(miles) === null) {
      setError('Enter a complete nonnegative distance in yards.');
      return;
    }
    const token = ++epoch.current;
    const run = runId;
    await attempt(async () => {
      const p = await api(`/runs/${run}/filters`, {
        method: 'POST',
        body: JSON.stringify({
          network_ids: selectedNetworks,
          kinds,
          distance_m: distance ? decimalValue(miles)! * 0.9144 : null,
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
      if (!preferencesValid || maximum <= 0 || maximum > 60)
        throw Error('Enter a complete slope limit between 1 and 60 degrees');
      if (!area || editing) throw Error('Save an explicit travel polygon first');
      setAttempted(true);
      await saveReview({ ...draft(), attempted: true });
      const run = runId;
      const cid = focusedId;
      const pointRevision = workflow?.points[cid]?.point.revision;
      const v = await api(`/runs/${run}/approaches`, {
        method: 'POST',
        body: JSON.stringify({
          ids: [focusedId],
          points: [workflow?.points[focusedId]?.point],
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
      draftCache.current[cid] = {
        travel_area: v.scenario.travel_area,
        exclusions: v.scenario.exclusions,
        network_ids: v.scenario.network_ids,
        kinds: v.scenario.kinds,
        weights: v.scenario.weights,
        maximum_slope_deg: v.scenario.maximum_slope_deg,
        start: v.scenario.start,
        pinned: v.scenario.pinned,
        boundary_confirmed: true,
        scenario: v.scenario.id,
        alternative: 0,
        attempted: true,
      };
      if (
        run === runRef.current &&
        cid === focusRef.current &&
        pointRevision === revisionRef.current
      ) {
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
      // Record this point's new scenario even if the user focused another spot meanwhile.
      await saveReview(
        {
          travel_area: v.scenario.travel_area,
          exclusions: v.scenario.exclusions,
          network_ids: v.scenario.network_ids,
          kinds: v.scenario.kinds,
          weights: v.scenario.weights,
          maximum_slope_deg: v.scenario.maximum_slope_deg,
          start: v.scenario.start,
          pinned: v.scenario.pinned,
          boundary_confirmed: true,
          scenario: v.scenario.id,
          alternative: 0,
          attempted: true,
        },
        cid,
        focusRef.current,
      );
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
  useEffect(() => {
    if (
      planning &&
      hydrated &&
      hydrationFocus.current === focusedId &&
      !attempted &&
      !scenarioId &&
      !scenarios.some((s) => s.scenario.points.some((p) => p.id === focusedId)) &&
      area &&
      !editing &&
      selectedNetworks.length &&
      !active &&
      !busy &&
      preferencesValid &&
      maximum > 0 &&
      maximum <= 60 &&
      !workflow?.points[focusedId]?.approach
    ) {
      setAttempted(true);
      void planApproaches();
    }
  }, [
    planning,
    hydrated,
    focusedId,
    attempted,
    scenarioId,
    area,
    editing,
    selectedNetworks.length,
    active,
    busy,
    scenarios,
  ]);
  return (
    <section className="scouting-tools">
      <h3>{planning ? 'Compare approaches' : 'Terrain & access'}</h3>
      <button
        hidden={planning}
        className="primary wide"
        disabled={!kept.length}
        onClick={() => onPlanning(!planning)}
      >
        Compare approaches ({kept.length} shortlisted)
      </button>
      {!kept.length && <small>Shortlist at least one setup to compare approaches.</small>}
      <details open={!planning}>
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
            Yards
            <input
              aria-label="Maximum network distance yards"
              type="text"
              inputMode="decimal"
              value={miles}
              onChange={(e) => setMiles(e.target.value)}
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
        <button
          disabled={
            busy ||
            !runId ||
            !validCriteria(filterTargets) ||
            (distance && decimalValue(miles) === null)
          }
          onClick={apply}
        >
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
      {planning && hasShortlist && (!hydrated || hydrationFocus.current !== focusedId) && (
        <p role="status">Loading your approach review…</p>
      )}
      {planning && !hasShortlist && (
        <div className="notice">
          <p>No spots remain on the shortlist. Restore or shortlist a spot to continue.</p>
          <button onClick={() => onPlanning(false)}>Return to Find setups</button>
        </div>
      )}
      {planning && hasShortlist && hydrated && hydrationFocus.current === focusedId && (
        <div className="approach-controls">
          <p className="hint">
            Compare distance, climbing and cover from mapped roads or trails.{' '}
            <Help topic="approach" />
          </p>
          <div className="guided-focus" role="status">
            <h3>
              Spot {Math.max(1, queue.indexOf(focusedId) + 1)} of {queue.length} · {focusedId}
            </h3>
            <p>
              {queue.length - unresolved.length} selected · {unresolved.length} remaining
            </p>
            <label>
              Focused spot
              <select
                aria-label="Focused approach spot"
                value={focusedId}
                onChange={(e) => void focusSpot(e.target.value)}
              >
                {queue.map((cid: string) => (
                  <option key={cid} value={cid}>
                    {cid}
                    {workflow?.points[cid]?.approach ? ' · selected' : ' · needs review'}
                  </option>
                ))}
              </select>
            </label>
            <button disabled={busy || active} onClick={() => void nextSpot('dismiss')}>
              Dismiss spot &amp; next
            </button>
            <button
              className="primary"
              disabled={busy || active || !queue.length || unresolved.length > 0}
              onClick={onInspectStage}
            >
              Continue to inspect
            </button>
            {!!unresolved.length && (
              <p className="hint">
                Select an approach or dismiss each remaining spot before continuing.
              </p>
            )}
          </div>
          <details className="approach-settings" open={!scenario || editing}>
            <summary>Approach boundary & preferences</summary>
            <h3>
              Where can you approach from? <Help topic="searchArea" />
            </h3>
            <p className="hint">
              Draw or import a search boundary that includes a departure and this setup. Mapped
              access is not verified permission.
            </p>
            <button
              onClick={() => {
                const geometries = observerBoundary?.features
                  .map((f) => f.geometry)
                  .filter((g) => g.type === 'Polygon' || g.type === 'MultiPolygon');
                if (geometries?.length === 1) {
                  setArea(geometries[0] as Polygon);
                  setEditing(true);
                } else
                  setError(
                    'Import or draw one explicit travel polygon; the observer area has multiple geometries.',
                  );
              }}
            >
              Start from observer boundary
            </button>
            {area && editing && (
              <button onClick={() => setEditing(false)}>Confirm approach search boundary</button>
            )}

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
                relative costs, not walking times or safety predictions. Distance always
                contributes.
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
                    disabled={busy}
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
                <DecimalField
                  key={focusedId + ':' + scenarioId}
                  disabled={busy}
                  aria-label="Maximum approach slope"
                  value={maximum}
                  onChange={setMaximum}
                  onValidity={(v) => setPreferencesValid(v)}
                />
              </label>
              <p>
                30° default is a desktop screening threshold. Unknown vegetation receives maximum
                cover penalties when avoidance is enabled.
              </p>
            </details>
            {(!kept.length ||
              !area ||
              editing ||
              active ||
              busy ||
              !selectedNetworks.length ||
              !preferencesValid ||
              maximum <= 0 ||
              maximum > 60) && (
              <p>
                {!preferencesValid || maximum <= 0 || maximum > 60
                  ? 'Enter a complete slope limit between 1 and 60 degrees.'
                  : editing
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
                !kept.length ||
                !area ||
                editing ||
                active ||
                busy ||
                !selectedNetworks.length ||
                !preferencesValid ||
                maximum <= 0 ||
                maximum > 60 ||
                !hydrated ||
                !workflow?.points[focusedId]?.shortlisted
              }
              onClick={planApproaches}
            >
              {scenarioId || attempted
                ? 'Recalculate approaches for ' + focusedId
                : 'Compare approaches'}
            </button>
          </details>
          <JobProgress job={scenarioJob} />
          {scenarioJob && ['running', 'cancelling'].includes(scenarioJob.status) && (
            <button
              disabled={scenarioJob.status === 'cancelling'}
              onClick={() =>
                void api(`/jobs/${scenarioJob.id}/cancel`, { method: 'POST' }).catch((e) =>
                  setError(String(e)),
                )
              }
            >
              Cancel comparison
            </button>
          )}
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
            Saved approach comparisons
            <select
              value={scenarioId}
              onChange={(e) => {
                loadScenario(e.target.value);
              }}
            >
              <option value="">Choose a saved comparison…</option>
              {scenarios
                .filter((s) => s.scenario.points.some((p) => p.id === focusedId))
                .map((s) => (
                  <option key={s.scenario.id} value={s.scenario.id}>
                    {s.scenario.points.length} spots · slope limit {s.scenario.maximum_slope_deg}° ·{' '}
                    comparison{' '}
                    {scenarios.findIndex((item) => item.scenario.id === s.scenario.id) + 1}
                    {s.stale ? ' · stale' : ''}
                  </option>
                ))}
            </select>
          </label>
          {scenario && (
            <div>
              <p className="notice">{imperialNotice(scenario.scenario.notice)}</p>
              {scenario.stale && (
                <p className="error">Stale: {scenario.stale_reasons.join('; ')}</p>
              )}
              {!scenario.results && (
                <p>Results pending; see the active job and its errors below.</p>
              )}
              {scenario.results?.results.map(
                (r, i) =>
                  r.point.id === focusedId && (
                    <article key={r.point.id}>
                      <h4>
                        {r.point.id} · original terrain-visible {areaText(r.point.coverage)}
                      </h4>
                      {r.message && (
                        <p>
                          {r.message} No path found does not certify inaccessibility. Change the
                          travel boundary/preferences or remove this setup from the shortlist.
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
                                map.flyTo({
                                  center: [r.point.longitude, r.point.latitude],
                                  zoom: 14,
                                });
                            }}
                          >
                            Show this spot and search boundary
                          </button>
                        </>
                      )}
                      {!!r.alternatives.length && (
                        <div className="alternative-nav">
                          <p>
                            Alternative {(alternativesOnMap[focusedId] || 0) + 1} of{' '}
                            {r.alternatives.length}
                          </p>
                          <button
                            disabled={(alternativesOnMap[focusedId] || 0) === 0}
                            onClick={() =>
                              showAlternative(focusedId, (alternativesOnMap[focusedId] || 0) - 1)
                            }
                          >
                            Previous alternative
                          </button>
                          <button
                            disabled={
                              (alternativesOnMap[focusedId] || 0) >= r.alternatives.length - 1
                            }
                            onClick={() =>
                              showAlternative(focusedId, (alternativesOnMap[focusedId] || 0) + 1)
                            }
                          >
                            Next alternative
                          </button>
                        </div>
                      )}
                      {r.alternatives.map(
                        (a, j) =>
                          j === (alternativesOnMap[focusedId] || 0) && (
                            <div className="plan" key={j}>
                              <h3 className="approach-name">{a.labels.join(' / ')}</h3>
                              <div className="approach-metrics">
                                <div>
                                  <strong>
                                    {yards(a.mapped_distance_m + a.offtrail_distance_m)}
                                  </strong>
                                  <small>Total distance</small>
                                </div>
                                <div>
                                  <strong>{feetText(a.ascent_m)}</strong>
                                  <small>Climbing</small>
                                </div>
                                <div>
                                  <strong>{number(a.maximum_slope_deg)}°</strong>
                                  <small>Steepest slope</small>
                                </div>
                              </div>
                              <button
                                className="primary"
                                disabled={
                                  busy ||
                                  active ||
                                  !preferencesValid ||
                                  maximum <= 0 ||
                                  maximum > 60 ||
                                  scenario.stale ||
                                  !!scenario.point_stale?.[r.point.id] ||
                                  scenarioDirty
                                }
                                onClick={() => void nextSpot('approach', j)}
                              >
                                Use this approach &amp; next spot
                              </button>
                              <button
                                disabled={!map}
                                onClick={() => showAlternative(r.point.id, j)}
                              >
                                Show this alternative on map
                              </button>
                              {(scenario.stale ||
                                scenario.point_stale?.[r.point.id] ||
                                scenarioDirty) && (
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
                              <p className="approach-surface">
                                <span>━ Mapped {yards(a.mapped_distance_m)}</span>
                                <span>┄ Off-trail {yards(a.offtrail_distance_m)}</span>
                              </p>
                              <details>
                                <summary>Cover, descent & calculation details</summary>
                                <p>
                                  Departure: {a.departure[1].toFixed(7)},{' '}
                                  {a.departure[0].toFixed(7)}
                                </p>
                                <p>
                                  Mapped walk {yards(a.mapped_distance_m)} · off-trail{' '}
                                  {yards(a.offtrail_distance_m)} · ascent {feetText(a.ascent_m)} ·
                                  descent {feetText(a.descent_m)} · max slope{' '}
                                  {number(a.maximum_slope_deg)}°
                                </p>
                                <p>
                                  Average known off-trail tree cover{' '}
                                  {number(a.average_tree === null ? null : a.average_tree * 100)}% ·
                                  shrub{' '}
                                  {number(a.average_shrub === null ? null : a.average_shrub * 100)}%
                                  · path unknown cover{' '}
                                  {number(
                                    a.unknown_cover_fraction === null
                                      ? null
                                      : a.unknown_cover_fraction * 100,
                                  )}
                                  %. Unknown values use maximum penalties.
                                </p>
                                <p>
                                  Cost {number(a.cost)} ·{' '}
                                  {Object.entries(a.cost_contributions)
                                    .map(([k, v]) => `${k}: ${number(v)}`)
                                    .join(' · ')}
                                </p>
                              </details>
                              <Profile
                                points={a.elevation_profile}
                                mappedMeters={a.mapped_distance_m}
                              />
                              <p>
                                Yellow: mapped travel. Pink dashes: off-trail. Provisional approach;
                                verify conditions and permissions.
                              </p>
                              {!scenario.stale &&
                                !scenario.point_stale?.[r.point.id] &&
                                !scenarioDirty && (
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
                                      Provisional approach GPX track + unchanged destination
                                      waypoint
                                    </a>
                                  </p>
                                )}
                            </div>
                          ),
                      )}
                    </article>
                  ),
              )}
            </div>
          )}
        </div>
      )}
      {planning && recoveryView && recoveryView.scenario.id !== scenarioId && (
        <details open className="saved-comparison">
          <summary>Saved comparison · {recoveryView.scenario.id.slice(0, 8)}</summary>
          <p>
            Historical evidence. Return a removed spot to the shortlist before selecting an
            approach.
          </p>
          {recoveryView.results?.results.map((r, i) => (
            <article key={r.point.id}>
              <b>
                {r.point.id} · {areaText(r.point.coverage)}
              </b>
              {r.message && <p>{explainNoPath(r.limiting_evidence)}</p>}
              {r.alternatives.map((a, j) => (
                <p key={j}>
                  {a.labels.join(' / ')} · {yards(a.mapped_distance_m + a.offtrail_distance_m)} ·
                  ascent {feetText(a.ascent_m)} · descent {feetText(a.descent_m)}.
                  <a
                    href={`/api/approaches/${recoveryView.scenario.id}/export/gpx?point=${i}&alternative=${j}`}
                  >
                    Provisional approach export
                  </a>
                </p>
              ))}
            </article>
          ))}
          {!recoveryView.results && (
            <p>This saved computation did not finish. Its job and failure remain in history.</p>
          )}
          <button onClick={() => setRecoveryView(null)}>Close saved comparison</button>
        </details>
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
          0–{yards(end)} distance; {feetText(min)}–{feetText(max)} ground elevation
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
