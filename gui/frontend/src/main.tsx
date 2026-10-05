import { YardScale } from './yard-scale';
import { area as areaText, yards } from './units';
import DownloadReview from './download-review';
import JobProgress from './job-progress';
import { inputSignature } from './approach-inputs';
import {
  defaultCriteria,
  validCriteria,
  observerAreaKm2,
  type TargetCriteria,
} from './target-criteria';
import NetworkMap from './network-map';
import AccessSampling, { type Sampling } from './access-sampling';
import ScoutingTools, { type AppliedFilter } from './scouting-tools';
import { updateMapLayers } from './map-layers';
import { prepareCoverage } from './coverage-cache';
import AreaSettings from './area-creation';
import StoragePanel from './storage-panel';
import RunManagement from './run-management';
import RunSelection from './run-selection';
import JobMonitor from './job-monitor';
import CandidateCard from './candidate-review';
import WorkingWaypoint from './working-waypoint';
import ManualWaypoint from './manual-waypoint';
import React, { useEffect, useRef, useState, lazy, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import * as maplibregl from 'maplibre-gl';
import { Map, GeoJSONSource } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
maplibregl.setWorkerUrl(workerUrl);
import './style.css';
import './workspace.css';
import {
  Icon,
  WorkflowNavigation,
  SceneBoundary,
  SelectedSetup,
  SavedCollection,
  EmptyState,
  type Stage,
} from './workspace-ui';
import { useTraining, Learning, Meaning, practiceExport } from './training';
import { Drawing, Help } from './drawing';
import { TerrainControls } from './terrain';
import { OnlineImagery, onlineSource } from './online';

const FirstPerson = lazy(() => import('./first-person'));
import type {
  Candidate,
  Run,
  Job,
  RunSummary,
  Review,
  ManualWaypoint as ManualWaypointRecord,
  ObserverPose,
  WorkingWaypointRecord,
  Overlap,
  ImportedArea,
  BaselinePlan,
} from './types';
import { useJobs, subscribePolling, refreshPolling } from './polling';
import WorkflowPanel, { type Workflow } from './workflow';
const colors = ['#00c0e8', '#ff6782', '#aa6fff'];
const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
const practiceArea = (geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null) =>
  geometry
    ? { id: 'practice', choices: [{ number: '1', name: 'Practice drawing', geometry }] }
    : null;
async function api(path: string, options: RequestInit = {}) {
  const r = await fetch('/api' + path, {
    ...options,
    headers: {
      'X-HuntMaps': 'local',
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });
  if (!r.ok) {
    let text;
    try {
      text = (await r.json()).detail;
    } catch {
      text = await r.text();
    }
    throw Error(text || r.statusText);
  }
  const value = await r.json();
  if (path.split('?')[0] === '/networks/import')
    window.dispatchEvent(new Event('huntmaps-networks-changed'));
  if (options.method && options.method !== 'GET') void refreshPolling();
  return value;
}
const num = (v: unknown, d = 3) => (typeof v === 'number' ? v.toFixed(d) : 'Not saved');
function App() {
  const jobs = useJobs();
  const [savedStage, setSavedStage] = useState(false);
  const [panelMode, setPanelMode] = useState<'results' | 'details' | 'filters'>('results');
  const [utility, setUtility] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setUtility(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const [workingLoaded, setWorkingLoaded] = useState(false);
  const [filterReset, setFilterReset] = useState(0);
  const [appliedFilter, setAppliedFilter] = useState<AppliedFilter | null>(null);
  const [inspectStage, setInspectStage] = useState(false);
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [listOpen, setListOpen] = useState(false);
  const [recommendationCount, setRecommendationCount] = useState(20);
  const [nearbyRadius, setNearbyRadius] = useState(30);
  const [treeThreshold, setTreeThreshold] = useState(10);
  const [targets, setTargets] = useState<TargetCriteria>(defaultCriteria);
  const [avoidDense, setAvoidDense] = useState(false);
  const [coverageStatus, setCoverageStatus] = useState('');
  const [coveragePreparation, setCoveragePreparation] = useState('');
  const [coverageRetry, setCoverageRetry] = useState(0);
  const [sortMode, setSortMode] = useState('coverage');
  const [planningApproaches, setPlanningApproaches] = useState(false);
  const filterId = appliedFilter?.profile.id || '';
  const [samplingValid, setSamplingValid] = useState(true);
  const [spacingValid, setSpacingValid] = useState(true);
  const [sampling, setSampling] = useState<Sampling | null>({
    network_ids: [],
    kinds: ['roads', 'trails'],
    distance_m: 804.672,
    height_m: null,
  });
  const [recovery, setRecovery] = useState<{ kind: string; id: string } | null>(null);
  const [separation, setSeparation] = useState(150);
  const [includeNetwork, setIncludeNetwork] = useState(true);
  const [preparedOptions, setPreparedOptions] = useState('');
  const [runList, setRunList] = useState<RunSummary[]>([]),
    [runId, setRunId] = useState(''),
    [run, setRun] = useState<Run | null>(null),
    [selected, setSelected] = useState(''),
    [detail, setDetail] = useState<Candidate | null>(null),
    [compare, setCompare] = useState<string[]>([]),
    [compareData, setCompareData] = useState<Candidate[]>([]),
    [overlap, setOverlap] = useState<Overlap[]>([]),
    [exportIds, setExportIds] = useState<string[]>([]),
    [search, setSearch] = useState(''),
    [group, setGroup] = useState('all'),
    [annotations, setAnnotations] = useState<Record<string, Review>>({}),
    [note, setNote] = useState(''),
    [status, setStatus] = useState('unmarked'),
    [saved, setSaved] = useState(''),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(false);
  const training = useTraining();
  const [firstPerson, setFirstPerson] = useState(false);
  const [manualPoints, setManualPoints] = useState<ManualWaypointRecord[]>([]),
    [activeManual, setActiveManual] = useState<ManualWaypointRecord | WorkingWaypointRecord | null>(
      null,
    ),
    [initialObserver, setInitialObserver] = useState<ObserverPose | null>(null);
  const [working, setWorking] = useState<Record<string, WorkingWaypointRecord>>({});
  const manualGeometryStamp = JSON.stringify(
    manualPoints.map((p) => [p.id, p.longitude, p.latitude]),
  );
  const workingStamp = JSON.stringify(working);
  const workingGeometryStamp = JSON.stringify(
    Object.keys(working)
      .sort()
      .map((id) => [id, working[id].revision]),
  );
  const effective = (p: Candidate): Candidate => {
    const w = working[p.id];
    return w
      ? {
          ...p,
          name: w.name,
          longitude: w.longitude,
          latitude: w.latitude,
          metrics: w.metrics,
          foreground: {},
          access: w.access,
          working_revision: w.revision,
        }
      : p;
  };
  const shownCandidates = run?.candidates.map(effective) || [];
  const shownManual = manualPoints.map((p) => (working[p.id] ? { ...p, ...working[p.id] } : p));
  const mapCompare = planningApproaches || inspectStage || savedStage ? [] : compare;
  const collectionSelectionVisible =
    !savedStage || !!workflow?.points[activeManual?.id || selected]?.shortlisted;
  const currentManual = activeManual
    ? working[activeManual.id]
      ? { ...activeManual, ...working[activeManual.id] }
      : activeManual
    : null;
  const workingSelected = working[activeManual?.id || selected];
  const readWorking = async () => {
    const ident = runId;
    const v = await api('/runs/' + ident + '/working-waypoints');
    if (currentRunRef.current === ident) setWorking(v.overrides);
    return v;
  };
  const reviewWorking = async (v: Review) => {
    const ident = runId;
    await api(`/runs/${ident}/working-waypoints/${activeManual?.id || selected}/review`, {
      method: 'PUT',
      body: JSON.stringify(v),
    });
    if (currentRunRef.current === ident) await readWorking();
  };
  const restoreWorking = async () => {
    const ident = runId;
    await api(`/runs/${ident}/working-waypoints/${activeManual?.id || selected}`, {
      method: 'DELETE',
    });
    if (currentRunRef.current === ident) {
      setInitialObserver(null);
      await readWorking();
    }
  };
  const chooseOriginal = (id: string) => {
    setActiveManual(null);
    setInitialObserver(null);
    setSelected(id);
  };
  const chooseManual = (p: ManualWaypointRecord | WorkingWaypointRecord) => {
    setSelected(p.anchor);
    setActiveManual(p);
    setCompare([]);
    setClasses(false);
    setSectors(false);
  };
  const manualChoose = useRef<(p: ManualWaypointRecord | WorkingWaypointRecord) => void>(() => {});
  manualChoose.current = (point) =>
    chooseManual(shownManual.find((p) => p.id === point.id) || point);
  const updateManual = async (v: Review) => {
    if (!activeManual) return;
    const ident = runId;
    const p = await api(`/runs/${runId}/manual-observers/${activeManual.id}`, {
      method: 'PUT',
      body: JSON.stringify(v),
    });
    if (currentRunRef.current !== ident) return;
    setActiveManual((old) => (old?.id === p.id ? p : old));
    setManualPoints((a) => a.map((q) => (q.id === p.id ? p : q)));
  };
  const deleteManual = async () => {
    if (!activeManual) return;
    const ident = runId;
    const id = activeManual.id;
    await api(`/runs/${runId}/manual-observers/${id}`, { method: 'DELETE' });
    if (currentRunRef.current !== ident) return;
    setManualPoints((a) => a.filter((p) => p.id !== id));
    setExportIds((a) => a.filter((p) => p !== id));
    setActiveManual((old) => (old?.id === id ? null : old));
    setInitialObserver((old) => (old?.id === id ? null : old));
  };
  const [runsLoaded, setRunsLoaded] = useState(false);
  useEffect(() => {
    if (
      runsLoaded &&
      training.active &&
      !runList.some((r) => r.id === 'soap-creek-decision-review-v2') &&
      training.progress
    ) {
      training.setProgress({ ...training.progress, paused: true });
      setError(
        'The saved Soap Creek example is unavailable. Practice is paused; the guide and your local results remain available.',
      );
    }
  }, [runsLoaded, runList, training.active]);
  const [hiddenViews, setHiddenViews] = useState<string[]>([]);
  const [imagery, setImagery] = useState(true),
    [visibility, setVisibility] = useState(true),
    [classes, setClasses] = useState(false),
    [sectors, setSectors] = useState(false),
    [opacity, setOpacity] = useState(0.5),
    [imageOpacity, setImageOpacity] = useState(1);
  const [newRun, setNewRun] = useState(training.active && training.progress?.lesson === 'area'),
    [imported, setImported] = useState<ImportedArea | null>(
      training.active && training.progress?.lesson === 'area' ? practiceArea(training.draft) : null,
    ),
    [polygon, setPolygon] = useState(
      training.active && training.progress?.lesson === 'area' && training.draft ? '1' : '',
    ),
    [name, setName] = useState('scouting-' + new Date().toISOString().slice(0, 10)),
    [radius, setRadius] = useState(2000),
    [minutes, setMinutes] = useState(30),
    [count, setCount] = useState(150),
    [budget, setBudget] = useState(600),
    [planId, setPlanId] = useState(''),
    [plan, setPlan] = useState<BaselinePlan | null>(null),
    [download, setDownload] = useState(false),
    [unusedJobs, unusedSetJobs] = useState<Job[]>([]),
    [busy, setBusy] = useState(false);
  const selectedFilter = appliedFilter?.candidates.find((row) => row.id === selected);
  const settingsValid =
    samplingValid &&
    spacingValid &&
    /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(name) &&
    Number.isInteger(count) &&
    count >= 12 &&
    count <= 5000 &&
    validCriteria(targets) &&
    Number.isInteger(recommendationCount) &&
    recommendationCount >= 1 &&
    recommendationCount <= Math.min(200, count) &&
    [10, 30, 60, 120].includes(nearbyRadius) &&
    Number.isFinite(treeThreshold) &&
    treeThreshold >= 0 &&
    treeThreshold <= 100 &&
    Number.isInteger(budget) &&
    budget >= 1 &&
    Number.isSafeInteger(budget) &&
    Number.isFinite(separation) &&
    separation >= 0 &&
    separation <= 2000 &&
    Number.isInteger(minutes) &&
    minutes >= 5 &&
    minutes <= 120;
  useEffect(() => {
    if (plan?.prepared) setBudget(plan.max_download_mb);
  }, [plan?.max_download_mb, plan?.prepared]);
  const planDirty =
    !!plan &&
    (name !== plan.name ||
      radius !== plan.settings?.radius_m ||
      minutes !== plan.settings?.observation_minutes ||
      count !== plan.settings?.candidate_count ||
      inputSignature(targets) !==
        inputSignature({ ...defaultCriteria(), ...plan.settings?.search?.target_filters }) ||
      avoidDense !== (plan.settings?.search?.avoid_dense_vegetation ?? false) ||
      recommendationCount !==
        (plan.settings?.search?.recommendation_count ??
          Math.min(20, plan.settings?.candidate_count ?? count)) ||
      nearbyRadius !== (plan.settings?.search?.nearby_radius_m ?? 30) ||
      treeThreshold !== (plan.settings?.search?.tree_threshold_percent ?? 10) ||
      separation !== (plan.settings?.search?.recommendation_separation_m ?? 150) ||
      budget !== plan.max_download_mb ||
      (!!preparedOptions && preparedOptions !== JSON.stringify({ sampling, includeNetwork })));
  const planJob = jobs.find((j) => j.plan === planId);
  const restoredGeneration = useRef(false);
  useEffect(() => {
    if (restoredGeneration.current || training.active || !jobs.length) return;
    const saved = sessionStorage.getItem('huntmaps-generation-plan');
    if (!saved) {
      restoredGeneration.current = true;
      return;
    }
    const job = jobs.find((j) => j.plan === saved && j.kind === 'baseline');
    if (!job) return;
    restoredGeneration.current = true;
    setPlanId(saved);
    setNewRun(true);
    void jobAction(job, 'review');
  }, [jobs]);
  const planFailed = planJob && ['failed', 'cancelled', 'interrupted'].includes(planJob.status);
  const planComplete = planJob?.kind === 'baseline' && planJob.status === 'complete';
  useEffect(() => {
    setDownload(false);
  }, [name, radius, minutes, count, recommendationCount, nearbyRadius, treeThreshold, budget]);
  const [areaMode, setAreaMode] = useState<'draw' | 'import'>('draw'),
    [drawing, setDrawing] = useState(false),
    [goLat, setGoLat] = useState(''),
    [goLon, setGoLon] = useState('');
  const areaBackup = useRef<ImportedArea | null>(null),
    intakeSession = useRef(0);
  useEffect(() => {
    intakeSession.current++;
  }, [newRun, training.active, areaMode]);
  const mapEl = useRef<HTMLDivElement>(null),
    map = useRef<Map | null>(null),
    [ready, setReady] = useState(false),
    runRef = useRef(run),
    currentRunRef = useRef(runId),
    currentSelectedRef = useRef(selected),
    annotationSaveTicket = useRef(0),
    chooseRef = useRef<(id: string) => void>(() => {});
  runRef.current = run;
  currentRunRef.current = runId;
  currentSelectedRef.current = selected;
  chooseRef.current = (id) => {
    chooseOriginal(id);
    setSaved('');
  };
  useEffect(() => {
    const app = document.querySelector<HTMLElement>('.app')!;
    const resize = () => {
      const height =
        (document.querySelector('header')?.getBoundingClientRect().height || 86) +
        (document.querySelector('.training-coach')?.getBoundingClientRect().height || 0) +
        40;
      app.style.setProperty('--chrome-height', height + 'px');
      map.current?.resize();
    };
    const observer = new ResizeObserver(resize);
    document
      .querySelectorAll('header,.training-coach,.map-pane')
      .forEach((e) => observer.observe(e));
    resize();
    return () => observer.disconnect();
  }, [training.active, training.progress?.step]);
  const refreshRuns = () =>
    api('/runs')
      .then(setRunList)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void api('/speed-probe', { method: 'POST' }).catch(() => {});
    }, 2000);
    return () => window.clearTimeout(timer);
  }, []);
  const completedRunJobs = jobs
    .filter((j) => j.kind === 'baseline' && j.status === 'complete')
    .map((j) => j.id)
    .join(',');
  useEffect(() => {
    if (!completedRunJobs) return;
    let alive = true;
    api('/runs')
      .then((r) => {
        if (alive) setRunList(r);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [completedRunJobs]);
  useEffect(() => {
    api('/runs')
      .then((r) => {
        setRunList(r);
        setRunsLoaded(true);
        if (currentRunRef.current) return;
        setRunId(
          training.active &&
            training.active &&
            r.some((v: RunSummary) => v.id === 'soap-creek-decision-review-v2')
            ? 'soap-creek-decision-review-v2'
            : r.find((v: RunSummary) => v.id === localStorage.getItem('huntmaps-last-area'))?.id ||
                r[0]?.id ||
                '',
        );
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);
  useEffect(() => {
    setWorking({});
    setWorkingLoaded(false);
    if (!runId || training.active) return;
    let alive = true;
    const poll = () =>
      api('/runs/' + runId + '/working-waypoints')
        .then((v) => {
          if (alive) {
            setWorkingLoaded(true);
            setWorking((old) =>
              JSON.stringify(old) === JSON.stringify(v.overrides) ? old : v.overrides,
            );
          }
        })
        .catch((e) => {
          if (alive) setError(e instanceof Error ? e.message : String(e));
        });
    poll();
    const unsubscribe = subscribePolling(poll);
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [runId, training.active]);
  useEffect(() => {
    if (!runId) return;
    let alive = true;
    localStorage.setItem('huntmaps-last-area', runId);
    setLoading(true);
    setPlanningApproaches(recovery?.kind === 'approach');
    setInspectStage(false);
    setSavedStage(false);
    setPanelMode('results');
    setFirstPerson(false);
    setAppliedFilter(null);
    setSearch('');
    setRun(null);
    setAnnotations({});
    setManualPoints([]);
    setActiveManual(null);
    setInitialObserver(null);
    setSelected('');
    setDetail(null);
    setCompare([]);
    setHiddenViews([]);
    setExportIds([]);
    setGroup('all');
    setError('');
    Promise.all([
      api('/runs/' + runId + '/manual-observers'),
      api('/runs/' + runId),
      training.active
        ? Promise.resolve(training.notes[runId] || {})
        : api('/runs/' + runId + '/annotations'),
    ])
      .then(([m, r, a]) => {
        if (alive) {
          setManualPoints(m);
          setRun(r);
          setAnnotations(a);
          setGroup(r.recommendation_ids?.length ? 'recommended' : 'all');
          setSelected(
            r.recommendation_ids?.[0] ||
              (training.active
                ? r.groups.West?.[0]
                : [...r.candidates].sort(
                    (a: Candidate, b: Candidate) =>
                      Number(b.metrics.raw_km2 || 0) - Number(a.metrics.raw_km2 || 0),
                  )[0]?.id) ||
              r.candidates[0]?.id ||
              '',
          );
          if (training.active && training.progress?.lesson === 'area' && !training.draft)
            map.current?.fitBounds(r.bounds, { padding: 60, duration: 0 });
          if (
            training.active &&
            training.progress?.lesson === 'review' &&
            ['separate', 'note', 'export'].includes(training.progress.step)
          )
            setCompare(['A0075', 'V010', 'V008']);
        }
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [runId, training.active]);
  useEffect(() => {
    if (!selected || !runId) return;
    let alive = true;
    setDetail(null);
    setError('');
    api(`/runs/${runId}/${training.active ? 'candidates' : 'working-candidates'}/${selected}`)
      .then((d) => {
        if (alive) setDetail(d);
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    const a = annotations[selected] || {};
    setNote(a.notes || '');
    setStatus(a.status || 'unmarked');
    return () => {
      alive = false;
    };
  }, [selected, runId, workingStamp, training.active]);
  useEffect(() => {
    if (!compare.length) {
      setCompareData([]);
      setOverlap([]);
      return;
    }
    let alive = true;
    Promise.all([
      Promise.all(
        compare.map((i) =>
          api(`/runs/${runId}/${training.active ? 'candidates' : 'working-candidates'}/${i}`),
        ),
      ),
      api(
        filterId && !training.active
          ? `/runs/${runId}/filtered-overlap/${filterId}?ids=${compare.join(',')}`
          : `/runs/${runId}/${training.active ? 'overlap' : 'working-overlap'}?ids=${compare.join(',')}`,
      ),
    ])
      .then(([d, o]) => {
        if (alive) {
          setCompareData(d);
          setOverlap(o);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [compare, runId, workingStamp, training.active, filterId]);
  useEffect(() => {
    if (!planId) return;
    let alive = true;
    api('/plans/' + planId)
      .then((p) => {
        if (alive) setPlan(p);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, [planId, jobs.map((j) => j.status).join(',')]);
  useEffect(() => {
    const m = new maplibregl.Map({
      container: mapEl.current!,
      style: {
        version: 8,
        sources: {},
        layers: [
          { id: 'background', type: 'background', paint: { 'background-color': '#d6ddd0' } },
        ],
      },
      center: [-107.28, 38.7],
      zoom: 12,
      maxZoom: 20,
      maxTileCacheSize: 64,
      attributionControl: false,
    });
    map.current = m;
    m.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    m.addControl(new maplibregl.NavigationControl(), 'top-right');
    m.addControl(new YardScale(), 'bottom-left');
    m.on('load', () => {
      for (const id of ['boundary', 'import', 'candidates', 'manual-observers'])
        m.addSource(id, { type: 'geojson', data: empty });
      m.addLayer({
        id: 'boundary-fill',
        type: 'fill',
        source: 'boundary',
        paint: { 'fill-color': '#f6f1d5', 'fill-opacity': 0.05 },
      });
      m.addLayer({
        id: 'boundary-line',
        type: 'line',
        source: 'boundary',
        paint: { 'line-color': '#fff5bb', 'line-width': 2, 'line-dasharray': [3, 2] },
      });
      m.addLayer({
        id: 'import-fill',
        type: 'fill',
        source: 'import',
        paint: { 'fill-color': '#f39a45', 'fill-opacity': 0.12 },
      });
      m.addLayer({
        id: 'import-line',
        type: 'line',
        source: 'import',
        paint: { 'line-color': '#ff9139', 'line-width': 3 },
      });
      m.addLayer({
        id: 'candidate-halo',
        type: 'circle',
        source: 'candidates',
        paint: {
          'circle-color': ['case', ['boolean', ['get', 'selected'], false], '#e5c888', '#fff'],
          'circle-radius': ['case', ['boolean', ['get', 'selected'], false], 12, 6],
          'circle-opacity': 0.95,
        },
      });
      m.addLayer({
        id: 'candidate-points',
        type: 'circle',
        source: 'candidates',
        paint: {
          'circle-color': ['get', 'color'],
          'circle-radius': ['case', ['boolean', ['get', 'selected'], false], 7, 4],
          'circle-stroke-color': '#133c35',
          'circle-stroke-width': 1,
        },
      });
      m.addLayer({
        id: 'manual-points',
        type: 'circle',
        source: 'manual-observers',
        paint: {
          'circle-color': ['coalesce', ['get', 'color'], '#df7b35'],
          'circle-radius': 7,
          'circle-stroke-color': '#fff',
          'circle-stroke-width': 2,
        },
      });
      m.on('click', 'manual-points', (e) => {
        if (e.features?.[0]) {
          const p = JSON.parse(String(e.features[0].properties?.record));
          manualChoose.current(p);
        }
      });
      m.on('click', 'candidate-points', (e) => {
        if (m.queryRenderedFeatures(e.point, { layers: ['manual-points'] }).length) return;
        if (e.features?.[0]) chooseRef.current(String(e.features[0].properties?.id));
      });
      m.on('mouseenter', 'candidate-points', () => (m.getCanvas().style.cursor = 'pointer'));
      m.on('mouseleave', 'candidate-points', () => (m.getCanvas().style.cursor = ''));
      m.on('click', (e) => {
        if (!runRef.current) return;
        if (m.queryRenderedFeatures(e.point, { layers: ['manual-points'] }).length) return;
        const hits = m.queryRenderedFeatures(e.point, { layers: ['candidate-points'] });
        if (!hits.length) return;
        const id = String(hits[0].properties?.id);
        chooseRef.current(id);
      });
      setReady(true);
    });
    const pending = () =>
      mapEl.current?.setAttribute('data-map-state', JSON.stringify({ loaded: false }));
    m.on('movestart', pending);
    m.on('dataloading', pending);
    m.on('idle', () => {
      mapEl.current?.setAttribute(
        'data-map-state',
        JSON.stringify({
          center: m.getCenter().toArray(),
          zoom: m.getZoom(),
          pitch: m.getPitch(),
          bearing: m.getBearing(),
          terrain: !!m.getTerrain(),
          elevation: m.getTerrain() ? m.queryTerrainElevation(m.getCenter()) : null,
          loaded: m.loaded(),
          candidateIds: (
            (m.getSource('candidates') as GeoJSONSource)?.serialize()
              .data as GeoJSON.FeatureCollection
          )?.features?.map((f) => f.properties?.id),
          candidatePixels: (
            (m.getSource('candidates') as GeoJSONSource)?.serialize()
              .data as GeoJSON.FeatureCollection
          )?.features?.map((f) => {
            const pixel = m.project((f.geometry as GeoJSON.Point).coordinates as [number, number]);
            return { id: f.properties?.id, x: pixel.x, y: pixel.y };
          }),
          manualIds: (
            (m.getSource('manual-observers') as GeoJSONSource)?.serialize()
              .data as GeoJSON.FeatureCollection
          )?.features?.map((f) => f.properties?.id),
        }),
      );
    });
    m.on('error', (e) => {
      if (['local-elevation', onlineSource].includes('sourceId' in e ? String(e.sourceId) : ''))
        return;
      console.error(e.error);
      setError('Map layer could not load: ' + e.error.message);
    });
    return () => m.remove();
  }, []);
  useEffect(() => {
    if (!ready || !run) return;
    const m = map.current!;
    (m.getSource('boundary') as GeoJSONSource).setData(newRun ? empty : run.boundary);
    if (!newRun) m.fitBounds(run.bounds, { padding: 45, duration: 0 });
  }, [ready, run, newRun]);
  useEffect(() => {
    if (!ready || !run) return;
    const m = map.current!;
    (m.getSource('candidates') as GeoJSONSource).setData({
      type: 'FeatureCollection',
      features: (newRun ? [] : shownCandidates)
        .filter(
          (p) =>
            (planningApproaches || inspectStage || savedStage
              ? !!workflow?.points[p.id]?.shortlisted &&
                (!inspectStage || !!workflow?.points[p.id]?.approach)
              : group === 'dismissed'
                ? !!workflow?.points[p.id]?.dismissed
                : !workflow?.points[p.id]?.dismissed) &&
            (planningApproaches ||
              inspectStage ||
              savedStage ||
              group === 'all' ||
              (group === 'recommended' &&
                !!(appliedFilter?.recommendation_ids ?? run?.recommendation_ids)?.includes(p.id)) ||
              group === 'dismissed' ||
              (group === 'review'
                ? run?.review_ids.includes(p.id)
                : group === 'ungrouped'
                  ? !p.neighborhood
                  : p.neighborhood === group) ||
              p.id === selected ||
              mapCompare.includes(p.id)),
        )
        .map((p) => ({
          type: 'Feature' as const,
          properties: {
            id: p.id,
            selected: !activeManual && p.id === selected,
            color: mapCompare.includes(p.id)
              ? colors[mapCompare.indexOf(p.id)]
              : !activeManual && p.id === selected
                ? '#ffdf80'
                : '#31574a',
          },
          geometry: { type: 'Point' as const, coordinates: [p.longitude, p.latitude] },
        })),
    });
  }, [
    ready,
    run,
    selected,
    compare,
    group,
    newRun,
    activeManual?.id,
    workingGeometryStamp,
    workflow?.revision,
    planningApproaches,
    inspectStage,
    savedStage,
    appliedFilter,
  ]);
  useEffect(() => {
    if (ready)
      (map.current!.getSource('manual-observers') as GeoJSONSource).setData({
        type: 'FeatureCollection',
        features: (newRun ? [] : shownManual)
          .filter((p) =>
            planningApproaches || inspectStage || savedStage
              ? !!workflow?.points[p.id]?.shortlisted &&
                (!inspectStage || !!workflow?.points[p.id]?.approach)
              : group === 'dismissed'
                ? workflow?.points[p.id]?.dismissed
                : !workflow?.points[p.id]?.dismissed,
          )
          .map((p) => ({
            type: 'Feature' as const,
            properties: {
              id: p.id,
              record: JSON.stringify(p),
              color: activeManual?.id === p.id ? '#ffdf80' : '#df7b35',
            },
            geometry: { type: 'Point' as const, coordinates: [p.longitude, p.latitude] },
          })),
      });
  }, [
    ready,
    manualGeometryStamp,
    activeManual?.id,
    newRun,
    workingGeometryStamp,
    workflow?.revision,
    group,
    planningApproaches,
    inspectStage,
    savedStage,
  ]);
  useEffect(() => {
    if (!ready || !run || !selected || newRun) return;
    const p = shownCandidates.find((p) => p.id === selected);
    if (p) map.current!.flyTo({ center: [p.longitude, p.latitude], zoom: 13.8, duration: 0 });
  }, [ready, selected, run, newRun, workingGeometryStamp]);
  useEffect(() => {
    if (!ready) return;
    const m = map.current!;
    let fs: GeoJSON.Feature[] = [];
    if (!imported && newRun && plan?.boundary) fs = plan.boundary.features;
    if (imported && newRun) {
      const chosen =
        polygon === 'all' ? imported.choices : imported.choices.filter((c) => c.number === polygon);
      fs = chosen.map((c) => ({
        type: 'Feature' as const,
        properties: { name: c.name },
        geometry: c.geometry,
      }));
    }
    (m.getSource('import') as GeoJSONSource).setData({
      type: 'FeatureCollection',
      features: fs,
    });
    if (fs.length) {
      const bounds = new maplibregl.LngLatBounds();
      const walk = (coords: unknown) => {
        if (!Array.isArray(coords)) return;
        if (typeof coords[0] === 'number') bounds.extend([coords[0], coords[1]]);
        else coords.forEach(walk);
      };
      fs.forEach((f) => {
        if (f.geometry && 'coordinates' in f.geometry) walk(f.geometry.coordinates);
      });
      const fit = (duration: number) =>
        m.fitBounds(bounds, {
          padding: {
            left: Math.min(240, m.getContainer().clientWidth * 0.4),
            right: 70,
            top: 100,
            bottom: 150,
          },
          duration,
        });
      fit(300);
      const resized = () => fit(0);
      m.on('resize', resized);
      return () => {
        m.off('resize', resized);
      };
    }
  }, [ready, imported, polygon, newRun, plan?.id, plan?.prepared]);
  useEffect(() => {
    if (!ready || !run) return;
    const m = map.current!;
    return updateMapLayers(
      m,
      {
        run,
        working,
        filterId,
        imagery,
        imageOpacity,
        newRun,
        compare: mapCompare,
        activeManual: collectionSelectionVisible ? activeManual : null,
        selected: collectionSelectionVisible ? selected : '',
        visibility,
        hiddenViews,
        opacity,
        sectors,
        classes,
        dismissed: Object.values(workflow?.points || {})
          .filter((p) => p.dismissed)
          .map((p) => p.point.id),
      },
      api,
      setError,
      setCoverageStatus,
      coverageRetry,
    );
  }, [
    ready,
    run,
    selected,
    compare,
    imagery,
    visibility,
    classes,
    sectors,
    opacity,
    imageOpacity,
    newRun,
    hiddenViews,
    activeManual?.id,
    workingGeometryStamp,
    coverageRetry,
    savedStage,
    planningApproaches,
    inspectStage,
    collectionSelectionVisible,
    filterId,
    workflow?.revision,
  ]);
  useEffect(() => {
    if (
      !ready ||
      !newRun ||
      !training.active ||
      training.progress?.lesson !== 'area' ||
      training.draft ||
      !run
    )
      return;
    const p = shownCandidates.find((p) => p.id === 'A0075');
    const timer = setTimeout(() => {
      if (p)
        map.current?.flyTo({
          center: [p.longitude, p.latitude],
          zoom: 13.8,
          pitch: 0,
          bearing: 0,
          duration: 0,
        });
    }, 400);
    return () => clearTimeout(timer);
  }, [ready, newRun, training.active, run?.id]);
  const toggleCompare = (id: string) => {
    setActiveManual(null);
    setInitialObserver(null);
    setHiddenViews([]);
    setError('');
    setCompare((a) => {
      if (a.includes(id)) return a.filter((v) => v !== id);
      if (a.length === 3) {
        setError('Compare up to three setups. Remove one to add another.');
        return a;
      }
      return [...a, id];
    });
  };
  const toggleExport = (id: string) =>
    setExportIds((a) => (a.includes(id) ? a.filter((v) => v !== id) : [...a, id]));
  async function save() {
    const ident = runId,
      cid = selected,
      ticket = ++annotationSaveTicket.current;
    if (training.active) {
      training.saveNote(runId, selected, { status, notes: note });
      setAnnotations((a) => ({ ...a, [selected]: { status, notes: note } }));
      setSaved('Practice review saved separately');
      return;
    }
    try {
      await api(`/runs/${runId}/annotations/${selected}`, {
        method: 'PUT',
        body: JSON.stringify({ status, notes: note }),
      });
      if (currentRunRef.current !== ident || ticket !== annotationSaveTicket.current) return;
      setAnnotations((a) => ({ ...a, [cid]: { status, notes: note } }));
      if (currentSelectedRef.current === cid) setSaved('Saved on this computer');
    } catch (e: unknown) {
      if (
        currentRunRef.current === ident &&
        currentSelectedRef.current === cid &&
        ticket === annotationSaveTicket.current
      )
        setError(e instanceof Error ? e.message : String(e));
    }
  }
  async function importFile(file: File) {
    const session = intakeSession.current;
    try {
      setBusy(true);
      setError('');
      const data = new FormData();
      data.append('file', file);
      const i = await api('/imports' + (training.active ? '?practice=true' : ''), {
        method: 'POST',
        body: data,
      });
      if (session !== intakeSession.current) return;
      setImported(i);
      setPolygon(i.choices.length === 1 ? '1' : '');
      setPlanId('');
      setPlan(null);
      if (training.active && i.choices.length === 1) training.setDraft(i.choices[0].geometry);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function saveDrawing(feature: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon>) {
    const session = intakeSession.current;
    const data = new FormData();
    data.append(
      'file',
      new File(
        [
          JSON.stringify({
            type: 'Feature' as const,
            properties: { name: training.active ? 'Practice drawing' : 'Drawn observer area' },
            geometry: feature.geometry,
          }),
        ],
        'drawn-area.geojson',
        { type: 'application/geo+json' },
      ),
    );
    const i = await api('/imports' + (training.active ? '?practice=true' : ''), {
      method: 'POST',
      body: data,
    });
    if (session !== intakeSession.current) return;
    setImported(i);
    setPolygon('1');
    setPlanId('');
    setPlan(null);
    if (training.active) training.setDraft(feature.geometry);
  }
  async function prepare() {
    if (training.active || !settingsValid) return;
    const session = intakeSession.current;
    try {
      setBusy(true);
      setError('');
      const j = await api('/plans', {
        method: 'POST',
        body: JSON.stringify({
          name,
          import_id: imported?.id,
          polygon,
          radius_m: radius,
          observation_minutes: minutes,
          candidate_count: count,
          target_filters: targets,
          avoid_dense_vegetation: avoidDense,
          recommendation_count: recommendationCount,
          recommendation_separation_m: separation,
          nearby_radius_m: nearbyRadius,
          tree_threshold_percent: treeThreshold,
          max_download_mb: budget,
          ...(sampling ? { access_sampling: sampling } : {}),
          ...(includeNetwork ? { include_network: true } : {}),
        }),
      });
      if (session !== intakeSession.current) return;
      setPlanId(j.plan);
      setPreparedOptions(JSON.stringify({ sampling, includeNetwork }));
      setPlan(null);
      setDownload(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function startPlan() {
    if (training.active || planDirty || !settingsValid || busy || running) return;
    try {
      setBusy(true);
      setError('');
      await api(`/plans/${planId}/start`, {
        method: 'POST',
        body: JSON.stringify({ download: true, review_signature: plan?.review_signature }),
      });
      sessionStorage.setItem('huntmaps-generation-plan', planId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function jobAction(j: Job, action: string) {
    if (training.active && action !== 'cancel') return;
    try {
      setError('');
      if (action === 'cancel') await api(`/jobs/${j.id}/cancel`, { method: 'POST' });
      else {
        setUtility(false);
        setSavedStage(false);
        setPanelCollapsed(false);
        setListOpen(false);
        if (j.kind === 'approach') {
          const v = await api('/approaches/' + j.plan);
          setRunId(v.scenario.run_id);
          setNewRun(false);
          setPlanningApproaches(true);
          setInspectStage(false);
          setRecovery({ kind: 'approach', id: j.plan });
          return;
        }
        if (j.kind === 'network-acquisition') {
          const v = await api('/network-plans/' + j.plan);
          if (!v.plan) throw Error('Network plan unavailable; review a new road/trail plan');
          setRecovery({ kind: 'network', id: j.plan });
          setNewRun(false);
          setPlanningApproaches(true);
          setInspectStage(false);
          return;
        }
        const p = await api('/plans/' + j.plan);
        setImported(null);
        setPolygon('');
        setName(p.name);
        setRadius(p.settings.radius_m);
        setMinutes(p.settings.observation_minutes);
        setCount(p.settings.candidate_count);
        setRecommendationCount(
          p.settings.search?.recommendation_count ?? Math.min(20, p.settings.candidate_count),
        );
        setNearbyRadius(p.settings.search?.nearby_radius_m ?? 30);
        setSeparation(p.settings.search?.recommendation_separation_m ?? 150);
        setTreeThreshold(p.settings.search?.tree_threshold_percent ?? 10);
        setTargets({ ...defaultCriteria(), ...p.settings.search?.target_filters });
        setAvoidDense(p.settings.search?.avoid_dense_vegetation ?? false);
        setBudget(p.max_download_mb);
        const recoveredSampling = p.access_sampling
          ? {
              network_ids: p.access_sampling.network_ids,
              kinds: p.access_sampling.kinds,
              distance_m: p.access_sampling.distance_m,
              height_m: p.access_sampling.height_m,
            }
          : null;
        setSampling(recoveredSampling);
        setIncludeNetwork(!!p.include_network);
        setPreparedOptions(
          JSON.stringify({ sampling: recoveredSampling, includeNetwork: !!p.include_network }),
        );
        setPlanId(j.plan);
        setNewRun(true);
        setPlan(p);
        setDownload(false);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  const visibleCandidates =
    shownCandidates.filter(
      (p) =>
        (training.active ||
          (!planningApproaches && !inspectStage) ||
          (inspectStage
            ? !!workflow?.points[p.id]?.approach
            : !!workflow?.points[p.id]?.shortlisted)) &&
        (planningApproaches || inspectStage
          ? !workflow?.points[p.id]?.dismissed
          : group === 'dismissed'
            ? !!workflow?.points[p.id]?.dismissed
            : !workflow?.points[p.id]?.dismissed) &&
        (planningApproaches ||
          inspectStage ||
          group === 'all' ||
          (group === 'recommended' &&
            !!(appliedFilter?.recommendation_ids ?? run?.recommendation_ids)?.includes(p.id)) ||
          group === 'dismissed' ||
          (group === 'review'
            ? run?.review_ids.includes(p.id)
            : group === 'ungrouped'
              ? !p.neighborhood
              : p.neighborhood === group)) &&
        (planningApproaches ||
          inspectStage ||
          `${p.id} ${p.parent} ${p.neighborhood || ''}`
            .toLowerCase()
            .includes(search.toLowerCase())) &&
        (planningApproaches ||
          inspectStage ||
          !appliedFilter ||
          appliedFilter.candidates.find((row) => row.id === p.id)?.qualifies === true),
    ) || [];
  const sorted = [...visibleCandidates].sort((a, b) => {
    const original =
      shownCandidates.findIndex((p) => p.id === a.id) -
      shownCandidates.findIndex((p) => p.id === b.id);
    if (sortMode === 'engine')
      return (
        Number(b.metrics.baseline_score ?? b.metrics.selective_score ?? -1) -
          Number(a.metrics.baseline_score ?? a.metrics.selective_score ?? -1) || original
      );
    if (appliedFilter && !planningApproaches && !inspectStage)
      return (
        (appliedFilter.candidates.find((p) => p.id === b.id)?.matching_km2 ?? -1) -
          (appliedFilter.candidates.find((p) => p.id === a.id)?.matching_km2 ?? -1) ||
        Number(b.metrics.raw_km2 ?? -1) - Number(a.metrics.raw_km2 ?? -1) ||
        a.id.localeCompare(b.id)
      );
    if (group === 'recommended')
      return (
        (run?.recommendation_ids?.indexOf(a.id) ?? 0) -
        (run?.recommendation_ids?.indexOf(b.id) ?? 0)
      );
    return sortMode === 'engine'
      ? Number(b.metrics.baseline_score ?? b.metrics.selective_score ?? -1) -
          Number(a.metrics.baseline_score ?? a.metrics.selective_score ?? -1) || original
      : (typeof b.metrics.raw_km2 === 'number' ? b.metrics.raw_km2 : -1) -
          (typeof a.metrics.raw_km2 === 'number' ? a.metrics.raw_km2 : -1) || original;
  });
  const labelPoint = currentManual || shownCandidates.find((p) => p.id === selected);
  useEffect(() => {
    if (!ready || newRun || !labelPoint || !collectionSelectionVisible) return;
    const label = document.createElement('button');
    label.className = 'map-setup-label';
    label.textContent = labelPoint.id;
    label.title = 'Open selected setup details';
    label.setAttribute('aria-label', 'Selected map setup ' + labelPoint.id);
    label.addEventListener('click', () => {
      setSavedStage(false);
      setPlanningApproaches(false);
      setInspectStage(false);
      setPanelMode('details');
      setPanelCollapsed(false);
    });
    const marker = new maplibregl.Marker({ element: label, anchor: 'bottom', offset: [0, -15] })
      .setLngLat([labelPoint.longitude, labelPoint.latitude])
      .addTo(map.current!);
    return () => {
      marker.remove();
    };
  }, [
    ready,
    newRun,
    labelPoint?.id,
    labelPoint?.longitude,
    labelPoint?.latitude,
    collectionSelectionVisible,
  ]);
  const nextCoverage = sorted
    .slice(Math.max(0, sorted.findIndex((p) => p.id === selected) + 1))
    .filter(
      (p) =>
        p.id !== selected &&
        !workflow?.points[p.id]?.dismissed &&
        typeof p.metrics.raw_km2 === 'number',
    )
    .slice(0, 200)
    .map((p) => p.id);
  useEffect(() => {
    setCoveragePreparation('');
    if (
      !ready ||
      !run ||
      newRun ||
      !visibility ||
      compare.length ||
      activeManual ||
      !coverageStatus.startsWith('Coverage ready') ||
      jobs.some((j) => ['queued', 'running', 'cancelling'].includes(j.status))
    )
      return;
    return prepareCoverage(
      map.current!,
      run.id,
      nextCoverage,
      working,
      filterId,
      setCoveragePreparation,
      run.bounds,
    );
  }, [
    ready,
    run?.id,
    newRun,
    visibility,
    compare.join(','),
    activeManual?.id,
    coverageStatus,
    nextCoverage.join(','),
    workingGeometryStamp,
    filterId,
    jobs.map((j) => j.status).join(','),
  ]);
  useEffect(() => {
    setInspectStage(false);
    setFirstPerson(false);
    setWorkflow(null);
  }, [runId]);
  const refreshWorkflow = async () => {
    const ident = runId;
    const value = await api(`/runs/${ident}/workflow`);
    if (currentRunRef.current === ident) setWorkflow(value);
    return value;
  };
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionFeedback, setDecisionFeedback] = useState('');
  const [undoDecision, setUndoDecision] = useState<{ cid: string; revision: number } | null>(null);
  useEffect(() => {
    setDecisionFeedback('');
    setUndoDecision(null);
  }, [runId]);
  const decisionQueue = useRef<Promise<boolean>>(Promise.resolve(true));
  const decide = (cid: string, action: string, extra: Record<string, unknown> = {}) => {
    const ident = runId;
    const displayed =
      shownManual.find((p) => p.id === cid) || shownCandidates.find((p) => p.id === cid);
    const expectedPoint = workflow?.points[cid]?.point;
    const submit = async () => {
      setDecisionBusy(true);
      try {
        if (currentRunRef.current !== ident) return false;
        const state = await api(`/runs/${ident}/workflow`);
        const current =
          state.points[cid]?.point || (await api(`/runs/${ident}/workflow-point/${cid}`));
        if (currentRunRef.current !== ident) return false;
        if (
          displayed &&
          (displayed.longitude !== current.longitude || displayed.latitude !== current.latitude)
        )
          throw Error('Waypoint changed; reload before submitting this decision.');
        const point = expectedPoint || current;
        const value = await api(`/runs/${ident}/workflow/${cid}`, {
          method: 'PUT',
          body: JSON.stringify({ action, revision: state.revision, point, ...extra }),
        });
        if (currentRunRef.current === ident) {
          setWorkflow((old) => (!old || value.revision >= old.revision ? value : old));
          if (['shortlist', 'dismiss', 'restore', 'remove', 'undo'].includes(action)) {
            setDecisionFeedback(
              `${cid}: ${action === 'dismiss' ? 'dismissed' : action === 'restore' || action === 'undo' ? 'restored' : action === 'remove' ? 'removed from shortlist' : 'shortlisted'}.`,
            );
            setUndoDecision(action === 'dismiss' ? { cid, revision: value.revision } : null);
          }
        }
        return currentRunRef.current === ident;
      } catch (e) {
        if (currentRunRef.current === ident) setError(String(e));
        return false;
      } finally {
        setDecisionBusy(false);
      }
    };
    decisionQueue.current = decisionQueue.current.catch(() => false).then(submit);
    return decisionQueue.current;
  };
  useEffect(() => {
    setWorkflow(null);
    if (!runId || training.active) return;
    let alive = true;
    const poll = () =>
      api(`/runs/${runId}/workflow`)
        .then((v) => {
          if (alive) setWorkflow((old) => (!old || v.revision >= old.revision ? v : old));
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    poll();
    const unsubscribe = subscribePolling(poll);
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [
    runId,
    workingStamp,
    JSON.stringify(annotations),
    JSON.stringify(manualPoints),
    training.active,
  ]);
  const shortlisted = newRun
    ? []
    : Object.values(workflow?.points || {}).filter((p) => p.shortlisted);
  const approached = shortlisted.filter((p) => p.approach);
  const confirmed = approached.filter((p) => p.confirmed);
  const running = jobs.some((j) => ['running', 'cancelling'].includes(j.status));
  const renderCandidate = (p: Candidate) => (
    <CandidateCard
      key={p.id}
      p={p}
      rank={sorted.findIndex((row) => row.id === p.id) + 1}
      bestArea={Math.max(
        ...sorted.map(
          (row) =>
            Number(
              appliedFilter?.candidates.find((f) => f.id === row.id)?.matching_km2 ??
                row.metrics.raw_km2,
            ) || 0,
        ),
        0,
      )}
      approach={!!workflow?.points[p.id]?.approach}
      confirmed={!!workflow?.points[p.id]?.confirmed}
      shortlisted={workflow?.points[p.id]?.shortlisted}
      dismissed={workflow?.points[p.id]?.dismissed}
      busy={decisionBusy}
      onDecision={training.active ? undefined : (action) => decide(p.id, action)}
      matching={appliedFilter?.candidates.find((row) => row.id === p.id)?.matching_km2}
      selected={selected}
      activeManual={!!activeManual}
      compare={compare}
      annotations={annotations}
      exportIds={exportIds}
      chooseOriginal={chooseOriginal}
      toggleCompare={toggleCompare}
      toggleExport={toggleExport}
    />
  );
  const groupedIds = new Set(Object.values(run?.groups || {}).flat());
  const candidateCards = sorted
    .filter((p) => !groupedIds.has(p.id))
    .map((p) => {
      const alternatives =
        group === 'recommended' && !planningApproaches && !inspectStage
          ? shownCandidates.filter(
              (q) =>
                (appliedFilter?.nearby_ids ?? run?.search_summary?.nearby_ids)?.[p.id]?.includes(
                  q.id,
                ) && !workflow?.points[q.id]?.dismissed,
            )
          : [];
      return (
        <div key={p.id}>
          {renderCandidate(p)}
          {!!alternatives.length && (
            <details>
              <summary>Nearby alternatives ({alternatives.length})</summary>
              {alternatives.map(renderCandidate)}
            </details>
          )}
        </div>
      );
    });
  const groupCards = Object.entries(run?.groups || {}).map(([label, ids]) => {
    const members = sorted.filter((p) => ids.includes(p.id));
    if (!members.length) return null;
    const families = new globalThis.Map<string, Candidate[]>();
    members.forEach((p) => {
      const root = p.parent && ids.includes(p.parent) ? p.parent : p.id;
      families.set(root, [...(families.get(root) || []), p]);
    });
    return (
      <section className="setup-group" key={label}>
        <b>{label} · saved neighborhood</b>
        <small>Original setups shown first; no automatic ranking.</small>
        {Array.from(families).map(([root, points]) => {
          const parent = shownCandidates.find((p) => p.id === root) || points[0],
            alternatives = points.filter((p) => p.id !== parent.id);
          return (
            <div key={root}>
              {renderCandidate(parent)}
              {!!alternatives.length && (
                <details
                  open={
                    training.active ||
                    !!search ||
                    alternatives.some(
                      (p) =>
                        p.id === selected || compare.includes(p.id) || exportIds.includes(p.id),
                    )
                  }
                >
                  <summary>
                    {alternatives.length} saved alternative{alternatives.length === 1 ? '' : 's'} to{' '}
                    {parent.id}
                  </summary>
                  {alternatives.map(renderCandidate)}
                </details>
              )}
            </div>
          );
        })}
      </section>
    );
  });

  const stage: Stage = savedStage
    ? 'save'
    : planningApproaches
      ? 'approach'
      : inspectStage
        ? 'inspect'
        : 'find';
  useEffect(() => {
    document.querySelector('.inspector')?.scrollTo(0, 0);
  }, [stage, panelMode, newRun]);
  useEffect(() => {
    const list = document.querySelector('.candidate-list');
    const card = list?.querySelector('.candidate.active');
    if (!list || !card || !card.getClientRects().length) return;
    const container = list.getBoundingClientRect(),
      item = card.getBoundingClientRect();
    if (item.top < container.top) list.scrollBy(0, item.top - container.top);
    else if (item.bottom > container.bottom) list.scrollBy(0, item.bottom - container.bottom);
  }, [selected, activeManual?.id]);
  const changeStage = (next: Stage) => {
    setSavedStage(next === 'save');
    setPlanningApproaches(next === 'approach');
    setInspectStage(next === 'inspect');
    setListOpen(false);
    setPanelCollapsed(false);
    setPanelMode('results');
    if (next !== 'find') setNewRun(false);
    if (next === 'approach' || next === 'inspect' || next === 'save') {
      const points =
        next === 'inspect'
          ? approached
          : next === 'save' && confirmed.length
            ? confirmed
            : shortlisted;
      const id = points.some((p) => p.point.id === (activeManual?.id || selected))
        ? activeManual?.id || selected
        : points[0]?.point.id;
      const manual = shownManual.find((p) => p.id === id);
      if (manual) chooseManual(manual);
      else if (id) chooseOriginal(id);
    }
  };
  const showResults =
    !newRun && !savedStage && (stage === 'find' ? panelMode === 'results' : listOpen);
  const showInspector = !savedStage && !showResults;
  const openDetails = () => {
    setPanelMode('details');
    setPanelCollapsed(false);
    setListOpen(false);
  };

  return (
    <div
      className={
        'app stage-' +
        stage +
        ' panel-' +
        panelMode +
        (panelCollapsed ? ' panel-collapsed' : '') +
        (training.active ? ' is-training' : '') +
        (newRun ? ' is-new-area' : '')
      }
    >
      <header>
        <div className="brand">
          <span className="brand-icon">
            <Icon name="mountain" size={27} />
          </span>
          <div>
            <b>HuntMaps2</b>
            <small>TERRAIN INTELLIGENCE</small>
          </div>
        </div>
        <RunSelection
          runs={runList}
          value={runId}
          disabled={training.active}
          onChange={(value) => {
            sessionStorage.removeItem('huntmaps-generation-plan');
            setRecovery(null);
            setPlanningApproaches(false);
            setRunId(value);
            setNewRun(false);
            setImported(null);
          }}
        />
        {!training.active && (
          <RunManagement
            api={api}
            onChanged={() => {
              setRun(null);
              setRunId('');
              void refreshRuns();
            }}
          />
        )}
        <button onClick={refreshRuns} title="Refresh saved areas" aria-label="Refresh saved areas">
          ↻
        </button>
        <button onClick={() => training.setOpen(true)}>Learn</button>
        <button
          className="primary"
          disabled={training.active}
          onClick={() => {
            setSavedStage(false);
            setPanelCollapsed(false);
            if (!newRun) {
              setMinutes(30);
              setIncludeNetwork(true);
              setTargets(defaultCriteria());
              setAvoidDense(false);
              setSampling({
                network_ids: [],
                kinds: ['roads', 'trails'],
                distance_m: 804.672,
                height_m: null,
              });
              setName('scouting-' + new Date().toISOString().slice(0, 10));
              setPlan(null);
              setPlanId('');
              setImported(null);
              setPolygon('');
              setPlanningApproaches(false);
              setInspectStage(false);
            }
            setNewRun(!newRun);
          }}
        >
          {newRun ? 'Back to review' : '+ New area'}
        </button>
      </header>
      <Learning
        exampleAvailable={runList.some((r) => r.id === 'soap-creek-decision-review-v2')}
        training={training}
        selected={selected}
        compare={compare}
        hiddenViews={hiddenViews}
        exportIds={exportIds}
        status={status}
        note={note}
        saved={saved}
        geometry={imported?.choices?.length === 1 ? imported.choices[0].geometry : null}
        onStart={(lesson) => {
          const sample = runList.find((r) => r.id === 'soap-creek-decision-review-v2');
          if (!sample) {
            setError('The saved Soap Creek example is unavailable.');
            return false;
          }
          setRunId(sample.id);
          setSearch('');
          setGroup('review');
          setCompare([]);
          setHiddenViews([]);
          setExportIds([]);
          setVisibility(true);
          setClasses(false);
          setSectors(false);
          setPlan(null);
          setPlanId('');
          setAreaMode('draw');
          if (lesson === 'review') {
            setNewRun(false);
            setImported(null);
          } else {
            setNewRun(true);
            setImported(practiceArea(training.draft));
            setPolygon(training.draft ? '1' : '');
            if (!training.draft && run && run.id === sample.id)
              map.current?.fitBounds(run.bounds, { padding: 60, duration: 0 });
          }
          return true;
        }}
        onExit={() => {
          setNewRun(false);
          setImported(null);
          setPolygon('');
          setSaved('');
        }}
      />
      <div className="workflow-bar">
        <WorkflowNavigation
          stage={stage}
          shortlisted={shortlisted.length}
          approached={approached.length}
          confirmed={confirmed.length}
          reviewReady={!workflow?.approach_review?.active || workflow.approach_review.ready}
          disabled={training.active || !runId}
          onStage={changeStage}
        />
        <div className="workspace-tools">
          <button
            title="Expand map or show scouting panel"
            aria-label={panelCollapsed ? 'Show scouting panel' : 'Expand map'}
            aria-pressed={panelCollapsed}
            onClick={() => setPanelCollapsed((v) => !v)}
          >
            <Icon name="layers" />
            {panelCollapsed ? 'Show panel' : 'Expand map'}
          </button>
          <button aria-expanded={utility} onClick={() => setUtility((v) => !v)}>
            Activity{running ? ' •' : ''}
          </button>
        </div>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError('')}>
            ×
          </button>
        </div>
      )}
      {decisionFeedback && (
        <p className="decision-toast" role="status">
          {decisionFeedback}{' '}
          <button aria-label="Dismiss update" onClick={() => setDecisionFeedback('')}>
            ×
          </button>
          {undoDecision && (
            <button
              disabled={decisionBusy || workflow?.revision !== undoDecision.revision}
              onClick={() =>
                decide(undoDecision.cid, 'undo', { undo_revision: undoDecision.revision })
              }
            >
              Undo
            </button>
          )}
        </p>
      )}

      <div className="workspace">
        <aside
          className={'sidebar ' + (listOpen ? 'drawer-open' : '')}
          hidden={!showResults && !training.active}
        >
          {newRun ? (
            <>
              <h2>{training.active ? 'Practice observer area' : 'Your new area'}</h2>
              <Meaning topic="area" />
              <p>1. Draw your boundary or import a polygon.</p>
              <p>2. Select one polygon or explicitly combine all.</p>
              <p>3. Review the acquisition plan and download cap.</p>
              <p>4. Start the baseline and follow the actual job log below.</p>
              <div className="notice">
                No candidate setups have been generated for this new area. The map shows your
                boundary over online imagery when enabled and local context where available.
              </div>
              <button
                disabled={training.active}
                onClick={() => {
                  setNewRun(false);
                  setImported(null);
                }}
              >
                Return to saved results
              </button>
            </>
          ) : (
            <>
              <div className="section-title">
                <h2>{stage === 'find' ? 'Glassing setups' : 'Your shortlist'}</h2>
                <span>{`${visibleCandidates.length} / ${run?.candidates.length || 0}`}</span>
              </div>
              <div className="panel-intro">
                {stage === 'find' ? 'Find a view worth the climb.' : 'Choose a setup to continue.'}
              </div>
              {stage !== 'find' && (
                <button onClick={() => setListOpen(false)}>Back to {stage}</button>
              )}
              {run?.search_summary && (
                <details className="search-summary">
                  <summary>
                    Search coverage · {run.search_summary.evaluated_count} locations
                  </summary>
                  <p className="hint">
                    Evaluated {run.search_summary.evaluated_count} of up to{' '}
                    {run.search_summary.budget} locations. Broad spacing:{' '}
                    {yards(run.search_summary.sampling?.spacing_m)}.
                    {run.search_summary.unused_budget > 0 && (
                      <>
                        {' '}
                        {run.search_summary.unused_budget} evaluations unused:{' '}
                        {run.search_summary.exhaustion_reason}.
                      </>
                    )}
                  </p>
                </details>
              )}
              <div className="result-toolbar">
                <button
                  onClick={() => {
                    setPanelMode('filters');
                    setPanelCollapsed(false);
                  }}
                >
                  <Icon name="tune" /> Terrain & access filters{appliedFilter ? ' •' : ''}
                </button>
              </div>
              <div className="result-controls">
                <input
                  aria-label="Find a setup"
                  placeholder="Find a setup…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <select
                  aria-label="Setup order"
                  title="Order setups by"
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value)}
                >
                  <option value="coverage">Visible area</option>
                  <option value="engine">Inspection score</option>
                </select>
              </div>
              {run && (
                <select
                  aria-label="Saved neighborhood"
                  value={group}
                  onChange={(e) => setGroup(e.target.value)}
                >
                  <option value="all">All evaluated setups</option>
                  {(!!run.recommendation_ids?.length || !!appliedFilter) && (
                    <option value="recommended">
                      Recommended setups (
                      {(appliedFilter?.recommendation_ids ?? run.recommendation_ids)?.length ?? 0})
                    </option>
                  )}
                  <option value="dismissed">Dismissed</option>
                  {run.review_ids.length > 0 && (
                    <option value="review">Saved review positions ({run.review_ids.length})</option>
                  )}
                  {Object.keys(run.groups).map((g) => (
                    <option key={g}>{g}</option>
                  ))}
                  <option value="ungrouped">Outside saved shortlist</option>
                </select>
              )}
              {!!run?.search_summary?.recommendation_note && (
                <p className="hint">{run.search_summary.recommendation_note}</p>
              )}
              {appliedFilter?.recommendation_ids?.length === 0 && (
                <p className="notice">
                  No spots have matching visible terrain under these criteria. Adjust the filters or
                  choose All evaluated setups to inspect the original views.
                </p>
              )}
              <div className="ranking-caption">
                <span>
                  {sortMode === 'engine'
                    ? 'Saved inspection score'
                    : appliedFilter || group === 'recommended'
                      ? 'Matching terrain first'
                      : 'Largest terrain view first'}
                </span>
                <span>Area · mi²</span>
              </div>
              <div className="candidate-list" data-tour="observer-list">
                {loading ? (
                  <p>Opening saved results…</p>
                ) : (
                  <>
                    {!sorted.length && (
                      <EmptyState title={run ? 'No matching setups' : 'Your next scouting area'}>
                        {run
                          ? 'Try another group or clear your search and filters.'
                          : 'Choose a saved area above, or use New area to draw where you want to scout.'}
                        {run && (
                          <button
                            className="wide"
                            onClick={() => {
                              setSearch('');
                              setGroup('all');
                              setAppliedFilter(null);
                              setFilterReset((n) => n + 1);
                            }}
                          >
                            Reset result filters
                          </button>
                        )}
                      </EmptyState>
                    )}
                    {['all', 'recommended'].includes(group) && !training.active ? (
                      sorted.map(renderCandidate)
                    ) : (
                      <>
                        {groupCards}
                        {candidateCards}
                      </>
                    )}
                  </>
                )}
              </div>
              {!training.active && manualPoints.length > 0 && (
                <section className="manual-list">
                  <h3>Provisional waypoints</h3>
                  <small>Orange pins · updated positions can have terrain shading</small>
                  {shownManual
                    .filter((p) =>
                      planningApproaches || inspectStage
                        ? inspectStage
                          ? !!workflow?.points[p.id]?.approach
                          : !!workflow?.points[p.id]?.shortlisted
                        : group === 'dismissed'
                          ? workflow?.points[p.id]?.dismissed
                          : !workflow?.points[p.id]?.dismissed,
                    )
                    .map((p) => (
                      <div
                        className={'candidate ' + (activeManual?.id === p.id ? 'active' : '')}
                        key={p.id}
                      >
                        <button
                          className="candidate-select"
                          onClick={() => chooseManual(p)}
                          aria-label={'Select waypoint ' + p.name}
                        >
                          <strong>{p.name}</strong>
                          <span>
                            Near {p.anchor} · {p.status}
                            {p.revision ? ' · terrain view ready' : ''}
                          </span>
                          <small>
                            {p.latitude.toFixed(7)}, {p.longitude.toFixed(7)}
                          </small>
                        </button>
                        {!training.active && (
                          <div className="candidate-actions">
                            <button
                              disabled={decisionBusy || workflow?.points[p.id]?.shortlisted}
                              onClick={() => decide(p.id, 'shortlist')}
                            >
                              {workflow?.points[p.id]?.shortlisted ? 'Shortlisted' : 'Shortlist'}
                            </button>
                            <button
                              disabled={decisionBusy}
                              onClick={() =>
                                decide(
                                  p.id,
                                  workflow?.points[p.id]?.dismissed ? 'restore' : 'dismiss',
                                )
                              }
                            >
                              {workflow?.points[p.id]?.dismissed ? 'Restore' : 'Dismiss'}
                            </button>
                          </div>
                        )}
                        <>
                          {p.revision && (
                            <label>
                              <input
                                type="checkbox"
                                aria-label={'Compare waypoint ' + p.name}
                                checked={compare.includes(p.id)}
                                onChange={() => toggleCompare(p.id)}
                              />
                              Compare
                            </label>
                          )}
                          <label>
                            <input
                              type="checkbox"
                              aria-label={'Export waypoint ' + p.name}
                              checked={exportIds.includes(p.id)}
                              onChange={() => toggleExport(p.id)}
                            />
                            Export
                          </label>
                        </>
                      </div>
                    ))}
                </section>
              )}
              <details
                className="export-box"
                data-tour="export-panel"
                open={exportIds.length > 0 || training.active}
              >
                <summary>Export waypoints · {exportIds.length} selected</summary>
                <div className="row">
                  {['gpx', 'kml'].map((fmt) => (
                    <a
                      className={'button ' + (!exportIds.length ? 'disabled' : '')}
                      key={fmt}
                      href={
                        training.active
                          ? '#'
                          : `/api/runs/${runId}/export/${fmt}?ids=${exportIds.join(',')}`
                      }
                      onClick={(e) => {
                        if (training.active) {
                          e.preventDefault();
                          if (exportIds.length) {
                            practiceExport(
                              fmt,
                              shownCandidates.filter((p) => exportIds.includes(p.id)) || [],
                              training.notes[runId] || {},
                            );
                            training.setExported(true);
                          }
                        }
                      }}
                      download
                    >
                      {fmt.toUpperCase()}
                    </a>
                  ))}
                  <button onClick={() => setExportIds([])}>Clear</button>
                </div>
                <small>
                  {training.active
                    ? 'PRACTICE files: real observer coordinates, separate practice notes.'
                    : 'Provisional waypoints, not routes. Target openings are excluded.'}
                </small>
              </details>
            </>
          )}
        </aside>
        {savedStage && (
          <SavedCollection
            workflow={workflow}
            runId={runId}
            candidates={[
              ...shownCandidates,
              ...shownManual.map((p) => ({
                id: p.id,
                name: p.name,
                metrics: 'metrics' in p ? p.metrics : {},
              })),
            ]}
            selected={activeManual?.id || selected}
            busy={decisionBusy}
            onSelect={(id) => {
              const manual = shownManual.find((p) => p.id === id);
              if (manual) chooseManual(manual);
              else chooseOriginal(id);
            }}
            onStage={changeStage}
            onRemove={(id) => {
              void decide(id, 'remove');
            }}
          />
        )}
        <main className="map-pane" aria-label="Scouting map">
          {!newRun && (loading || (runId && run?.id !== runId)) && (
            <div className="run-opening" role="status">
              Opening {runId}…
            </div>
          )}
          <div ref={mapEl} className="map" />
          {coverageStatus && (
            <div className="coverage-status" role="status" aria-live="polite">
              {coverageStatus.startsWith('Loading') && <progress aria-label="Loading coverage" />}
              <span>
                {coverageStatus}
                {coveragePreparation && (
                  <small className="coverage-preparation" title={coveragePreparation}>
                    {coveragePreparation.startsWith('Preparing')
                      ? ' · Preparing other views'
                      : ' · Other views ready'}
                  </small>
                )}
              </span>
              {coverageStatus.startsWith('Coverage incomplete') && (
                <button
                  onClick={() => {
                    setError('');
                    setCoverageRetry((v) => v + 1);
                  }}
                >
                  Retry coverage
                </button>
              )}
            </div>
          )}
          {ready && run && (
            <TerrainControls map={map.current!} runId={run.id} drawing={drawing} newArea={newRun} />
          )}
          <div className="map-heading" data-tour="view-switches">
            <b>
              {newRun
                ? 'Preview your observer area'
                : !collectionSelectionVisible
                  ? 'Your scouting collection'
                  : activeManual
                    ? currentManual?.name
                    : mapCompare.length
                      ? 'Compare individual saved views'
                      : working[selected]?.name || selected || 'Select an observer setup'}
            </b>
            <span>
              {newRun
                ? 'Orange boundary = where you would stand to glass'
                : activeManual
                  ? workingSelected
                    ? 'Updated terrain-only view'
                    : 'Nearby waypoint · no calculated view'
                  : mapCompare.length
                    ? mapCompare.map((id, i) => (
                        <span className="pill" style={{ borderColor: colors[i] }} key={id}>
                          <label>
                            <input
                              type="checkbox"
                              aria-label={`Show ${id} view`}
                              checked={!hiddenViews.includes(id)}
                              onChange={() =>
                                setHiddenViews((a) =>
                                  a.includes(id) ? a.filter((v) => v !== id) : [...a, id],
                                )
                              }
                            />
                            {id}
                          </label>
                          <button
                            aria-label={`Remove ${id} from comparison`}
                            onClick={() => toggleCompare(id)}
                          >
                            ×
                          </button>
                        </span>
                      ))
                    : workingSelected
                      ? 'Updated terrain-only view'
                      : detail?.parent
                        ? `Alternative to ${detail.parent}`
                        : 'Saved terrain visibility'}
            </span>
            {mapCompare.length > 0 && <button onClick={() => setCompare([])}>Exit compare</button>}
          </div>
          <details className="layers">
            <summary>
              <Icon name="layers" /> Map layers{' '}
              <span className="layer-count">
                {Number(imagery) +
                  Number(visibility && !newRun) +
                  Number(classes && !newRun) +
                  Number(sectors && !newRun)}
              </span>
            </summary>
            <h4 className="layer-group-title">Base map</h4>
            <Meaning topic="layers" />
            {ready && <OnlineImagery map={map.current!} />}
            <label>
              <input
                type="checkbox"
                checked={imagery}
                onChange={(e) => setImagery(e.target.checked)}
              />
              Cached aerial imagery
            </label>
            <input
              aria-label="Imagery opacity"
              type="range"
              min="0"
              max="1"
              step=".05"
              value={imageOpacity}
              onChange={(e) => setImageOpacity(+e.target.value)}
            />
            <h4 className="layer-group-title">Analysis overlays</h4>
            <label>
              <input
                type="checkbox"
                disabled={newRun}
                checked={visibility}
                onChange={(e) => setVisibility(e.target.checked)}
              />
              Terrain-visible target cells
            </label>
            <label>
              <input
                type="checkbox"
                disabled={newRun}
                checked={classes}
                onChange={(e) => setClasses(e.target.checked)}
              />
              Tree-cover classes for active setup
            </label>
            <label>
              <input
                type="checkbox"
                disabled={newRun}
                checked={sectors}
                onChange={(e) => setSectors(e.target.checked)}
              />
              Saved inspection sectors
            </label>
            <label>
              Overlay opacity {Math.round(opacity * 100)}%
              <input
                aria-label="Overlay opacity"
                type="range"
                min="0"
                max="1"
                step=".05"
                value={opacity}
                onChange={(e) => setOpacity(+e.target.value)}
              />
            </label>
            {!training.active && (
              <NetworkMap
                map={ready ? map.current : null}
                api={api}
                bounds={!newRun ? run?.bounds : undefined}
                geometry={
                  newRun && imported
                    ? {
                        type: 'MultiPolygon',
                        coordinates: imported.choices
                          .filter((c) => polygon === 'all' || c.number === polygon)
                          .flatMap((c) =>
                            c.geometry.type === 'Polygon'
                              ? [c.geometry.coordinates]
                              : c.geometry.coordinates,
                          ),
                      }
                    : null
                }
                budget={budget}
                analysisPlan={planId}
              />
            )}
            <div className="legend">
              {(newRun || !collectionSelectionVisible
                ? []
                : mapCompare.length
                  ? mapCompare
                  : activeManual
                    ? workingSelected
                      ? [activeManual.id]
                      : []
                    : [selected]
              )
                .filter(Boolean)
                .map((id, i) => (
                  <span key={id}>
                    <i style={{ background: colors[i] }} />
                    {id} {working[id] ? 'updated' : 'saved'} terrain view{' '}
                    {mapCompare.length > 0 && hiddenViews.includes(id) ? '(hidden)' : ''}
                  </span>
                ))}
              {classes && !newRun && (
                <>
                  <span>Tree classes: {selected}</span>
                  <span>
                    <i style={{ background: '#ffde67' }} />
                    Tree cover &lt;10%
                  </span>
                  <span>
                    <i style={{ background: '#97b459' }} />
                    Tree cover 10–40%
                  </span>
                  <span>
                    <i style={{ background: '#285e40' }} />
                    Tree cover ≥40%
                  </span>
                  <span>
                    <i style={{ background: '#adadad' }} />
                    Unknown cover
                  </span>
                </>
              )}
              <span>
                {newRun ? 'Orange line: imported observer area' : 'Dashed pale line: observer area'}
              </span>
              {sectors && !newRun && <span>Dashed colored sectors include hidden terrain</span>}
            </div>
          </details>
          <div className="map-footer">
            <span>
              {newRun
                ? 'Online context when enabled · cached context where covered · analysis sources pending'
                : imagery && run?.imagery.length
                  ? `Cached aerial imagery: ${[...new Set(run.imagery.flatMap((i) => i.dates || [i.acquisition_date]))].join(', ')} · ${run.id.startsWith('soap-creek') ? 'USGS/USDA NAIP' : 'supplied local imagery'}; online imagery fills gaps when enabled`
                  : 'Terrain hillshade · online imagery fills gaps when enabled'}
            </span>
            <button
              onClick={() => {
                if (run) map.current?.fitBounds(run.bounds, { padding: 45 });
              }}
            >
              Whole area
            </button>
            <button
              disabled={!detail || newRun}
              onClick={() => {
                const p = currentManual || detail;
                if (p) map.current?.flyTo({ center: [p.longitude, p.latitude], zoom: 18 });
              }}
            >
              Setup close-up
            </button>
          </div>
          {!newRun && run && collectionSelectionVisible && (
            <div className="map-key" aria-label="Active map legend">
              <span>
                <i className="key-boundary" />
                Observer area
              </span>
              {visibility && (
                <span>
                  <i className="key-visible" />
                  {appliedFilter ? 'Matching visible terrain' : 'Terrain-visible area'}
                </span>
              )}
              {classes && (
                <span>
                  <i className="key-cover" />
                  Tree cover · see layers
                </span>
              )}
              {sectors && (
                <span>
                  <i className="key-sector" />
                  Inspection sectors
                </span>
              )}
            </div>
          )}
          {!newRun && !training.active && collectionSelectionVisible && (
            <SelectedSetup
              candidate={workingSelected || (activeManual ? null : detail)}
              id={activeManual?.id || selected}
              name={currentManual?.name || working[selected]?.name}
              matching={
                appliedFilter?.candidates.find((p) => p.id === (activeManual?.id || selected))
                  ?.matching_km2
              }
              workflow={workflow}
              busy={decisionBusy}
              onApproach={() => changeStage('approach')}
              onDetails={() => {
                changeStage('find');
                openDetails();
              }}
              onInspect={() => {
                setInitialObserver(workingSelected || currentManual || null);
                setFirstPerson(true);
              }}
              onDecision={(action) => {
                void decide(activeManual?.id || selected, action);
              }}
            />
          )}
        </main>
        <aside className="inspector" hidden={!showInspector && !training.active}>
          {!newRun && (
            <div className="inspector-nav">
              <button
                onClick={() => {
                  if (stage === 'find') setPanelMode('results');
                  else setListOpen(true);
                }}
              >
                ← {stage === 'find' ? 'All setups' : 'Shortlist'}
              </button>
              <span>
                {stage === 'find'
                  ? panelMode === 'filters'
                    ? 'Refine your search'
                    : 'Setup details'
                  : stage === 'approach'
                    ? 'Evaluate access'
                    : 'Inspect the view'}
              </span>
            </div>
          )}
          {newRun ? (
            <>
              <details>
                <summary>Go to location</summary>
                <label>
                  Latitude
                  <input
                    aria-label="Go to latitude"
                    value={goLat}
                    onChange={(e) => setGoLat(e.target.value)}
                  />
                </label>
                <label>
                  Longitude
                  <input
                    aria-label="Go to longitude"
                    value={goLon}
                    onChange={(e) => setGoLon(e.target.value)}
                  />
                </label>
                <button
                  disabled={drawing}
                  onClick={() => {
                    const lat = Number(goLat),
                      lon = Number(goLon);
                    if (
                      !goLat ||
                      !goLon ||
                      !Number.isFinite(lat) ||
                      !Number.isFinite(lon) ||
                      Math.abs(lat) > 85 ||
                      Math.abs(lon) > 180
                    ) {
                      setError('Enter latitude −85 to 85 and longitude −180 to 180.');
                      return;
                    }
                    map.current?.flyTo({ center: [lon, lat], zoom: 13, pitch: 0, bearing: 0 });
                  }}
                >
                  Go to location
                </button>
                <small>
                  Online imagery can provide context beyond cached coverage. Analysis and 3D still
                  require local sources for your real area.
                </small>
              </details>
              <div className="eyebrow">Find places to glass</div>
              <h2>Start with your observer area</h2>
              {planJob && (
                <div className="generation-status" data-testid="generation-status">
                  <JobProgress job={planJob} />
                  {planFailed && (
                    <p role="alert">
                      {planJob.error || 'Files retained. Review or refresh this plan to recover.'}
                    </p>
                  )}
                  {['running', 'cancelling'].includes(planJob.status) && (
                    <button
                      disabled={planJob.status === 'cancelling'}
                      onClick={() =>
                        api(`/jobs/${planJob.id}/cancel`, { method: 'POST' }).catch((e) =>
                          setError(String(e)),
                        )
                      }
                    >
                      Cancel current job
                    </button>
                  )}
                  {planComplete && (
                    <button
                      className="primary wide"
                      onClick={() => {
                        sessionStorage.removeItem('huntmaps-generation-plan');
                        refreshRuns();
                        setRunId(plan!.name);
                        setNewRun(false);
                      }}
                    >
                      Open results
                    </button>
                  )}
                </div>
              )}
              <p>
                Draw where you would stand to glass. Terrain and target support extend beyond this
                boundary.
              </p>
              <div className="row area-modes">
                {areaMode !== 'draw' && (
                  <button onClick={() => setAreaMode('draw')}>Use map drawing</button>
                )}
                <button
                  disabled={training.active || drawing}
                  aria-pressed={areaMode === 'import'}
                  onClick={() => setAreaMode('import')}
                >
                  Import file
                </button>
              </div>
              {areaMode === 'draw' && ready && (
                <Drawing
                  map={map.current!}
                  geometry={imported?.choices?.length === 1 ? imported.choices[0].geometry : null}
                  onEditing={setDrawing}
                  onClear={() => {
                    setImported(null);
                    setPolygon('');
                    setPlanId('');
                    setPlan(null);
                    areaBackup.current = null;
                    if (training.active) training.setDraft(null);
                  }}
                  onSave={saveDrawing}
                  onInvalidate={() => {
                    areaBackup.current = imported;
                    setImported(null);
                    setPolygon('');
                    setPlanId('');
                    setPlan(null);
                  }}
                  onRestore={() => {
                    setImported(areaBackup.current);
                    setPolygon(areaBackup.current?.choices?.length === 1 ? '1' : '');
                  }}
                />
              )}
              {areaMode === 'import' && (
                <label className="upload">
                  Import GeoJSON / KML / KMZ
                  <input
                    aria-label="Import observer polygon"
                    type="file"
                    accept=".geojson,.json,.kml,.kmz"
                    onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])}
                  />
                </label>
              )}
              {imported && (areaMode === 'import' || imported.choices.length > 1) && (
                <label>
                  Polygon selection
                  <select
                    aria-label="Polygon selection"
                    value={polygon}
                    onChange={(e) => {
                      setPolygon(e.target.value);
                      setPlanId('');
                      setPlan(null);
                    }}
                  >
                    <option value="">Choose explicitly…</option>
                    {imported.choices.map((c) => (
                      <option value={c.number} key={c.number}>
                        {c.number}: {c.name}
                      </option>
                    ))}
                    {imported.choices.length > 1 && (
                      <option value="all">All polygons (combine deliberately)</option>
                    )}
                  </select>
                </label>
              )}
              {drawing && <p className="notice">Confirm this boundary to continue.</p>}
              <AreaSettings
                onValidity={setSpacingValid}
                targets={targets}
                setTargets={setTargets}
                avoidDense={avoidDense}
                setAvoidDense={setAvoidDense}
                areaKm2={observerAreaKm2(
                  imported?.choices?.find((c: any) => c.number === polygon)?.geometry ??
                    (imported?.choices?.length === 1
                      ? imported.choices[0].geometry
                      : polygon === 'all'
                        ? {
                            type: 'MultiPolygon',
                            coordinates:
                              imported?.choices.flatMap((c: any) =>
                                c.geometry.type === 'Polygon'
                                  ? [c.geometry.coordinates]
                                  : c.geometry.coordinates,
                              ) || [],
                          }
                        : null),
                )}
                name={name}
                radius={radius}
                count={count}
                minutes={minutes}
                setName={setName}
                setRadius={setRadius}
                setCount={setCount}
                recommendationCount={recommendationCount}
                setRecommendationCount={setRecommendationCount}
                nearbyRadius={nearbyRadius}
                setNearbyRadius={setNearbyRadius}
                treeThreshold={treeThreshold}
                setTreeThreshold={setTreeThreshold}
                separation={separation}
                setSeparation={setSeparation}
              />
              {plan?.settings && !plan.settings.search && (
                <p className="hint">
                  This recovered plan retains its saved sampler. Use a new run name and review a new
                  plan to apply expanded search.
                </p>
              )}
              <details>
                <summary>More options · sampling restrictions</summary>
                <AccessSampling
                  key={planId || 'new'}
                  initialSampling={sampling}
                  onChange={setSampling}
                  onValidity={setSamplingValid}
                  includeNetwork={includeNetwork}
                  onNetwork={setIncludeNetwork}
                />
              </details>
              <button
                className="primary wide"
                hidden={!!plan?.prepared && !planDirty}
                disabled={
                  training.active ||
                  busy ||
                  running ||
                  drawing ||
                  !imported ||
                  !polygon ||
                  !settingsValid
                }
                onClick={prepare}
              >
                Review downloads
              </button>
              <small>
                {training.active
                  ? 'Practice stops at the boundary preview. Exit the lesson to prepare a real acquisition plan.'
                  : 'May request bounded catalog metadata; no bulk downloads.'}
              </small>
              {!settingsValid && (
                <p className="error">
                  Use 12–5,000 evaluations and 1–200 recommendations (no more than evaluations), a
                  0–100% tree-cover threshold, a valid new run name and a positive integer MB
                  transfer ceiling.
                </p>
              )}
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              {planDirty && (
                <p className="notice">
                  Settings are unapplied. Prepare a new plan with a new run name to use changed
                  inputs; unchanged partial runs can still resume.
                </p>
              )}
              {plan && (
                <div className="plan">
                  <h3>{plan.name} acquisition plan</h3>

                  <p className="hint">
                    Prepared settings: {yards(plan.settings?.radius_m)} ·{' '}
                    {plan.settings?.candidate_count} maximum locations to evaluate;{' '}
                    {plan.settings?.search?.recommendation_count ?? 20} setups to recommend. Terrain
                    criteria rank matching visible area. Nearby vegetation eligibility is separate.
                    Starting this plan uses these saved settings.
                  </p>
                  {planFailed && (
                    <p className="error" role="alert">
                      {planJob.status}:{' '}
                      {planJob.error ||
                        'Partial files retained; review or refresh the unchanged plan.'}
                    </p>
                  )}
                  {plan.prepared ? (
                    <>
                      <p>
                        Allowance is a transfer ceiling, not a quality setting. Suggested:{' '}
                        {Math.min(
                          Math.max(
                            10,
                            Math.ceil(((plan.acquisition?.estimated_bytes || 0) * 1.2) / 1e7) * 10,
                          ),
                        )}{' '}
                        MB. Storage checks retain 20 GiB free.
                      </p>
                      <details>
                        <summary>Custom transfer limit</summary>
                        <input
                          aria-label="Maximum download size (MB)"
                          type="number"
                          min="10"
                          value={budget}
                          onChange={(e) => setBudget(+e.target.value)}
                        />
                        <button
                          disabled={running || busy}
                          onClick={async () => {
                            try {
                              const j = await api(`/plans/${planId}/allowance`, {
                                method: 'PUT',
                                body: JSON.stringify({ max_download_mb: budget }),
                              });
                              setPlan(null);
                              setDownload(false);
                            } catch (e) {
                              setError(String(e));
                            }
                          }}
                        >
                          Review updated allowance
                        </button>
                      </details>
                      <b>
                        Estimated new download:{' '}
                        {num((plan.acquisition?.estimated_bytes || 0) / 1e6, 1)} MB estimated ·{' '}
                        {plan.max_download_mb} MB cap
                      </b>
                      {!!plan.transferred_bytes && (
                        <p className="hint">
                          {num(plan.transferred_bytes / 1e6, 1)} MB transferred across this plan's
                          attempts;{' '}
                          {num(
                            Math.max(0, plan.max_download_mb * 1e6 - plan.transferred_bytes) / 1e6,
                            1,
                          )}{' '}
                          MB allowance remains.
                        </p>
                      )}
                      <DownloadReview
                        plan={plan}
                        bytes={plan.acquisition?.estimated_bytes ?? null}
                      />

                      <p>
                        Already cached:{' '}
                        {num((plan.acquisition?.already_cached_bytes || 0) / 1e6, 1)} MB ·{' '}
                        {plan.acquisition?.cached_keys?.join(', ') || 'none recorded'}
                      </p>
                      <ul>
                        {plan.acquisition?.items?.map((i) => (
                          <li key={i.key}>
                            {i.key}: {num(i.estimated_bytes / 1e6, 1)} MB
                          </li>
                        ))}
                      </ul>
                      {!plan.acquisition?.items?.length && (
                        <p>Validated cached sources; no new bulk files planned.</p>
                      )}
                      {plan.acquisition?.errors?.map((e: string) => (
                        <p className="error" key={e}>
                          {e}
                        </p>
                      ))}
                      {(plan.acquisition?.estimated_bytes || 0) > plan.max_download_mb * 1e6 && (
                        <p className="error">
                          Estimate exceeds the cap. Use a new run name with a suitable budget or a
                          smaller area.
                        </p>
                      )}
                      <p className="hint">{plan.acquisition?.estimate_note}</p>
                      <details>
                        <summary>Required data and source details</summary>
                        <pre>{plan.required_data || 'Sources ready.'}</pre>
                        <pre>{JSON.stringify(plan.acquisition, null, 2)}</pre>
                      </details>
                      <p className="hint">
                        Generate setups approves this displayed source plan within{' '}
                        {plan.max_download_mb} MB.
                      </p>
                      <button
                        className="primary wide"
                        disabled={
                          busy ||
                          running ||
                          planDirty ||
                          !settingsValid ||
                          (!planComplete && !!plan.storage?.blocked) ||
                          !!plan.acquisition?.errors?.length ||
                          (plan.acquisition?.estimated_bytes || 0) > plan.max_download_mb * 1e6
                        }
                        hidden={planComplete}
                        onClick={
                          planComplete
                            ? () => {
                                refreshRuns();
                                setRunId(plan.name);
                                setNewRun(false);
                              }
                            : startPlan
                        }
                      >
                        {planComplete ? 'Open results' : 'Generate setups'}
                      </button>
                    </>
                  ) : (
                    <p className={planFailed ? 'error' : ''}>
                      {planFailed
                        ? `${planJob.status}: ${planJob.error || 'Partial preparation retained; refresh unchanged plan to recover.'}`
                        : 'Preparing source plan… progress is shown above.'}
                    </p>
                  )}
                  {plan?.recovery_notice && <p className="hint">{plan.recovery_notice}</p>}
                  <button
                    disabled={running || planDirty}
                    onClick={() =>
                      api(`/plans/${planId}/prepare`, { method: 'POST' }).catch((e) =>
                        setError(e instanceof Error ? e.message : String(e)),
                      )
                    }
                  >
                    Refresh plan / recover partial preparation
                  </button>
                </div>
              )}
            </>
          ) : (
            <>
              <div hidden={inspectStage || (stage === 'find' && panelMode !== 'filters')}>
                {!training.active && runId && (
                  <ScoutingTools
                    key={'tools:' + runId}
                    runId={runId}
                    map={ready ? map.current : null}
                    api={api}
                    initialSearch={workingLoaded ? run?.search_summary?.options : undefined}
                    locationStamp={
                      workingStamp +
                      JSON.stringify(manualPoints.map((p) => [p.id, p.longitude, p.latitude]))
                    }
                    onFilter={setAppliedFilter}
                    filterReset={filterReset}
                    stamp={
                      JSON.stringify(annotations) +
                      workingStamp +
                      JSON.stringify(manualPoints) +
                      workflow?.revision
                    }
                    analysisPlan={planId}
                    budget={budget}
                    observerBoundary={run?.boundary}
                    recovery={recovery}
                    workflow={workflow}
                    focusedId={activeManual?.id || selected}
                    onFocus={(cid) => {
                      const manual = shownManual.find((p) => p.id === cid);
                      if (manual) chooseManual(manual);
                      else chooseOriginal(cid);
                    }}
                    onDecision={(cid, action) => decide(cid, action)}
                    onInspectStage={() => {
                      changeStage('inspect');
                    }}
                    onInputsChanged={(cid, scenario) => {
                      if (workflow?.points[cid]?.approach) void decide(cid, 'unselect');
                    }}
                    onApproach={(cid, scenario, alternative) =>
                      decide(cid, 'approach', { scenario, alternative })
                    }
                    planning={planningApproaches}
                    onPlanning={(v) => changeStage(v ? 'approach' : 'find')}
                  />
                )}
              </div>
              {!training.active && !planningApproaches && panelMode !== 'filters' && (
                <WorkflowPanel
                  key={'workflow:' + runId}
                  runId={runId}
                  workflow={workflow}
                  cid={activeManual?.id || selected}
                  inspect={inspectStage}
                  pending={decisionBusy}
                  onDecision={decide}
                  onInspect={() => setFirstPerson(true)}
                  onApproaches={() => changeStage('approach')}
                  api={api}
                />
              )}
              <div hidden={planningApproaches || inspectStage || panelMode === 'filters'}>
                {workingSelected ? (
                  <WorkingWaypoint
                    key={workingSelected.revision}
                    point={workingSelected}
                    original={activeManual || run?.candidates.find((p) => p.id === selected)}
                    onReview={reviewWorking}
                    onRestore={restoreWorking}
                    onView={() => {
                      setInitialObserver(workingSelected);
                      setFirstPerson(true);
                    }}
                  />
                ) : activeManual ? (
                  <ManualWaypoint
                    key={activeManual.id}
                    point={activeManual}
                    onSave={updateManual}
                    onDelete={deleteManual}
                    onView={() => {
                      setInitialObserver(currentManual);
                      setFirstPerson(true);
                    }}
                  />
                ) : (
                  <>
                    <div className="eyebrow">
                      {run?.synthetic
                        ? 'Synthetic engineering fixture'
                        : run?.experimental
                          ? 'Soap Creek · experimental'
                          : 'Glassing setup'}
                    </div>
                    <h2>{selected || 'Choose a setup'}</h2>
                    {detail ? (
                      <>
                        <p className="coordinates">
                          {detail.latitude.toFixed(7)}, {detail.longitude.toFixed(7)}
                        </p>
                        <p>
                          {detail.parent
                            ? 'Alternative setup to ' + detail.parent
                            : 'Original observer setup'}
                          {detail.neighborhood ? ' · ' + detail.neighborhood + ' neighborhood' : ''}
                        </p>
                        <button
                          disabled={training.active || !selected}
                          onClick={() => {
                            setInitialObserver(working[selected] || null);
                            setFirstPerson(true);
                          }}
                        >
                          Inspect now
                        </button>
                        <div className="metric">
                          <strong>
                            {areaText(
                              appliedFilter?.candidates.find((p) => p.id === selected)
                                ?.matching_km2 ?? detail.metrics.raw_km2,
                            )}
                          </strong>
                          <span>
                            {appliedFilter
                              ? 'matching visible terrain'
                              : 'terrain-visible target area'}
                          </span>
                          {appliedFilter && (
                            <p>
                              {areaText(detail.metrics.raw_km2)} original terrain-visible area ·{' '}
                              {areaText(
                                appliedFilter?.candidates.find((p) => p.id === selected)
                                  ?.matching_unknown_km2 ?? detail.metrics.matching_unknown_km2,
                              )}{' '}
                              with unknown required evidence
                            </p>
                          )}
                        </div>
                        <p className="hint">
                          Terrain alone permits these sightlines. Trees, branches, animal
                          concealment and ground footing still need inspection.
                        </p>
                        {selectedFilter && (
                          <p className="hint">
                            Nearest mapped network:{' '}
                            {selectedFilter.access.distance_m == null
                              ? 'unknown'
                              : (selectedFilter.access.distance_m / 1609.344).toFixed(2) +
                                ' mi'}{' '}
                            · positive height above it:{' '}
                            {selectedFilter.access.height_m == null
                              ? 'unknown'
                              : (selectedFilter.access.height_m / 0.3048).toFixed(0) + ' ft'}
                            . {selectedFilter.access.status} under the applied access limits; not
                            cumulative approach gain.
                          </p>
                        )}
                        <details className="setup-evidence">
                          <summary>Visibility, vegetation & tradeoffs</summary>
                          {typeof detail.metrics.foreground_category === 'string' && (
                            <div className="notice">
                              <strong>
                                Nearby setup cover · {String(detail.metrics.foreground_category)}
                              </strong>
                              <p>
                                {num(
                                  typeof detail.metrics.foreground_tree_mean === 'number'
                                    ? detail.metrics.foreground_tree_mean * 100
                                    : undefined,
                                  1,
                                )}
                                % mapped tree cover ·{' '}
                                {num(
                                  typeof detail.metrics.foreground_shrub_mean === 'number'
                                    ? detail.metrics.foreground_shrub_mean * 100
                                    : undefined,
                                  1,
                                )}
                                % mapped shrub cover ·{' '}
                                {num(Number(detail.metrics.foreground_known_fraction) * 100, 0)}%
                                known tree coverage within{' '}
                                {yards(detail.metrics.foreground_radius_m)}.
                              </p>
                              <small>
                                Potential clearing evidence only. Coarse mapping cannot verify a
                                small opening, eye-height branches or clear sightlines. Blue
                                coverage uses bare-earth terrain.
                              </small>
                            </div>
                          )}
                          <h3>Cover across {appliedFilter ? 'original ' : ''}visible terrain</h3>
                          <div className="breakdown">
                            {[
                              ['Tree cover under 10%', 'tree_lt10_km2'],
                              ['Tree cover 10–40%', 'tree_10to40_km2'],
                              ['Tree cover 40% or more', 'tree_ge40_km2'],
                              ['Unknown tree cover', 'tree_unknown_km2'],
                              ['Shrub cover over 30%', 'shrub_gt30_km2'],
                            ].map(([label, key]) => (
                              <div key={key}>
                                <span>{label}</span>
                                <b>{areaText(detail.metrics[key])}</b>
                              </div>
                            ))}
                          </div>
                          <p className="hint">
                            Shrubs overlap tree classes. Low tree cover does not guarantee visible
                            deer or good habitat.
                          </p>
                          <details>
                            <summary>Inherited inspection indices and calculation details</summary>
                            <h3>Inspection scores</h3>
                            <Meaning topic="scores" />
                            <div className="breakdown">
                              <div>
                                <span>Inherited baseline index</span>
                                <b>
                                  {num(
                                    detail.metrics.baseline_score ?? detail.metrics.selective_score,
                                    4,
                                  )}
                                </b>
                              </div>
                              {run?.experimental && (
                                <>
                                  <div>
                                    <span>Target inspection index</span>
                                    <b>{num(detail.metrics.target_heuristic, 4)}</b>
                                  </div>
                                  <div>
                                    <span>20% / 40% foreground screens</span>
                                    <b>
                                      {num(detail.metrics.directional_20, 4)} /{' '}
                                      {num(detail.metrics.directional_40, 4)}
                                    </b>
                                  </div>
                                </>
                              )}
                            </div>
                            <p className="hint">
                              The inherited index combines cover, distance, seasonal and light
                              assumptions within a fixed inspection budget. The experimental target
                              index omits seasonal/light weighting; its 20% and 40% screens test
                              nearby tree-cover cutoffs. None are acres or deer probabilities.
                            </p>
                          </details>
                          <h3>Foreground & access</h3>
                          <p>
                            {detail.foreground.foreground_cover_mean !== undefined
                              ? `Nearby average tree cover: ${num(detail.foreground.foreground_cover_mean * 100, 1)}%.`
                              : 'No historical foreground average saved for this alternative.'}
                          </p>
                          {detail.foreground.foreground_unknown_fraction !== undefined && (
                            <p className="hint">
                              Nearby cover unknown:{' '}
                              {num(detail.foreground.foreground_unknown_fraction * 100, 1)}%.
                            </p>
                          )}
                          <p className="hint">{detail.obstruction}</p>
                          {!!detail.obstruction_scenarios?.length && (
                            <p className="hint">
                              {detail.obstruction_scenarios.length} saved sampled column scenarios
                              are available in the diagnostics below. These do not measure
                              vegetation-visible acreage.
                            </p>
                          )}
                          <div className="notice">
                            {typeof detail.access === 'string'
                              ? detail.access
                              : 'Mapped approach evidence available; legal and safe access remains unverified. Inspect diagnostics.'}
                          </div>
                        </details>
                        <section data-tour="review-fields">
                          <h3>{training.active ? 'Practice review' : 'Your review'}</h3>
                          <Meaning topic="review" />
                          <label>
                            Decision
                            <select
                              aria-label="Candidate decision"
                              value={status}
                              onChange={(e) => {
                                setStatus(e.target.value);
                                setSaved('');
                              }}
                            >
                              {['unmarked', 'keep', 'reject', 'needs inspection'].map((s) => (
                                <option key={s}>{s}</option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Notes
                            <textarea
                              aria-label="Candidate notes"
                              maxLength={10000}
                              value={note}
                              rows={3}
                              onChange={(e) => {
                                setNote(e.target.value);
                                setSaved('');
                              }}
                              placeholder="Foreground gaps, approach questions, setup checks…"
                            />
                          </label>
                          <button className="primary" onClick={save}>
                            Save review
                          </button>
                          <small role="status">{saved}</small>
                        </section>
                        <details className="technical">
                          <summary>Sources, formulas & technical diagnostics</summary>
                          <p>
                            Raw area counts target-clipped saved visible cells × cell area. Display
                            tiles reproject these cells without smoothing. Inspection sectors are
                            separate full footprints.
                          </p>
                          <p>{run?.warning}</p>
                          <p>
                            Saved inspection index: sum of selected patch rewards under the existing
                            time budget. Patch rewards use the saved distance and cover response
                            functions; baseline also includes its inherited seasonal/light
                            assumptions. Experimental directional screens set patch reward to zero
                            beyond an assumed nearby cover cutoff. These are uncalibrated
                            heuristics.
                          </p>
                          <p>Aerial imagery metadata</p>
                          <pre>{JSON.stringify(run?.imagery, null, 2)}</pre>
                          <p>
                            Saved values, foreground, selected sectors, alignment and access
                            evidence
                          </p>
                          <pre>{JSON.stringify(detail, null, 2)}</pre>
                        </details>
                      </>
                    ) : (
                      <p>{loading ? 'Opening ' + runId + '…' : 'Loading setup…'}</p>
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </aside>
      </div>
      {compare.length > 0 && !newRun && stage === 'find' && (
        <section className="comparison">
          <div className="section-title">
            <h2>Compare setups</h2>
            <span>Each colored layer retains its own visible cells</span>
          </div>
          <div className="compare-grid">
            {compareData.map((p, i) => (
              <div className="compare-card" style={{ borderTopColor: colors[i] }} key={p.id}>
                <button onClick={() => chooseOriginal(p.id)}>
                  <b>{p.id}</b>
                  {p.parent ? ' · alternative to ' + p.parent : ''}
                </button>
                <span>
                  {areaText(
                    appliedFilter?.candidates.find((row) => row.id === p.id)?.matching_km2 ??
                      p.metrics.raw_km2,
                  )}{' '}
                  {appliedFilter ? 'matching terrain' : 'terrain'} ·{' '}
                  {areaText(p.metrics.tree_lt10_km2)} {appliedFilter ? 'original terrain ' : ''}
                  under 10% trees
                </span>
                <small>
                  {p.latitude.toFixed(7)}, {p.longitude.toFixed(7)}
                </small>
              </div>
            ))}
          </div>
          <p>
            {overlap
              .map((o) => `${o.a} / ${o.b}: ${areaText(o.shared_km2)} shared terrain`)
              .join(' · ') || 'Add another setup to compare shared terrain.'}
          </p>
          <small>
            Saved neighborhood groupings only; approaches are independent of coverage comparisons.
          </small>
        </section>
      )}
      <div className="activity-drawer" hidden={!utility}>
        <div className="section-title">
          <h2>Activity & storage</h2>
          <button aria-label="Close activity" onClick={() => setUtility(false)}>
            <Icon name="close" />
          </button>
        </div>
        <details open>
          <summary>Job history and recovery</summary>
          <JobMonitor
            jobs={jobs}
            running={running}
            trainingActive={training.active}
            onAction={jobAction}
            onOpen={(name) => {
              refreshRuns();
              setRunId(name);
              setNewRun(false);
              setImported(null);
            }}
          />
        </details>
        <StoragePanel onRecordsChanged={() => location.reload()} />
      </div>
      {firstPerson && (
        <SceneBoundary onClose={() => setFirstPerson(false)}>
          <Suspense
            fallback={
              <div className="fp-backdrop">
                <p>Loading first-person viewer…</p>
              </div>
            }
          >
            <FirstPerson
              waypointKey={activeManual?.id || selected}
              workingWaypoint={workingSelected}
              globalBusy={running}
              initialObserver={initialObserver}
              onWaypointUpdated={(p) => {
                if (currentRunRef.current === p.run_id) setWorking((a) => ({ ...a, [p.id]: p }));
              }}
              runId={runId}
              cid={activeManual?.id || selected}
              confirmed={!!workflow?.points[activeManual?.id || selected]?.confirmed}
              confirmationPending={decisionBusy}
              viewedSceneKey={workflow?.points[activeManual?.id || selected]?.viewed}
              reviewReady={!workflow?.approach_review?.active || workflow.approach_review.ready}
              approachCurrent={!!workflow?.points[activeManual?.id || selected]?.approach}
              onConfirm={() => decide(activeManual?.id || selected, 'confirm')}
              onViewed={(key) => decide(activeManual?.id || selected, 'viewed', { scene: key })}
              onSelect={chooseOriginal}
              onClose={() => setFirstPerson(false)}
            />
          </Suspense>
        </SceneBoundary>
      )}
      <footer>
        <span>
          <i className="local-dot" /> Local workspace
        </span>
        <span>Provisional scouting · verify access and conditions in the field</span>
        <span>HuntMaps2</span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById('root')!).render(<App />);
