import JobLogs from './job-logs';
import { useEffect, useRef, useState } from 'react';
import PositionMap from './position-map';
import { ProfileChart, VegetationResult } from './inspection';
import Viewer from './scene-viewer';
import { request } from './http';
import type {
  Target,
  Scene,
  ObserverPose,
  WorkingWaypointRecord,
  Job,
  FirstPersonPlan,
  ProfileResult,
} from './types';
import { subscribePolling, jobSnapshot } from './polling';
const pilot = ['A0075', 'V010', 'V008', 'A0031'];
export default function FirstPerson({
  runId,
  cid,
  onSelect,
  onClose,
  initialObserver,
  onWaypointUpdated,
  waypointKey,
  workingWaypoint,
  globalBusy,
}: {
  runId: string;
  cid: string;
  onSelect: (id: string) => void;
  onClose: () => void;
  initialObserver?: ObserverPose | null;
  onWaypointUpdated?: (v: WorkingWaypointRecord) => void;
  waypointKey?: string;
  workingWaypoint?: WorkingWaypointRecord;
  globalBusy?: boolean;
}) {
  const [meta, setMeta] = useState<Scene | null>(null),
    [error, setError] = useState(''),
    [eye, setEye] = useState(1.7),
    [height, setHeight] = useState(0.8),
    [heading, setHeading] = useState(0),
    [look, setLook] = useState(0),
    [points, setPoints] = useState(false),
    [foliage, setFoliage] = useState(true),
    [target, setTarget] = useState<Target | null>(null),
    [profile, setProfile] = useState<ProfileResult | null>(null),
    [range, setRange] = useState(300);
  const scenario = 'dense',
    nearby = 120;
  const [observer, setObserver] = useState<ObserverPose | null>(null),
    [explore, setExplore] = useState(false),
    [moving, setMoving] = useState(false),
    [moveError, setMoveError] = useState(''),
    [waypointName, setWaypointName] = useState(''),
    [waypointNotes, setWaypointNotes] = useState(''),
    [waypointSaved, setWaypointSaved] = useState(''),
    [savingWaypoint, setSavingWaypoint] = useState(false);
  const [updateJob, setUpdateJob] = useState<Job | null>(null);
  const updateDelivered = useRef('');
  const updating = savingWaypoint || ['running', 'cancelling'].includes(updateJob?.status || '');
  const entityKey = waypointKey || cid;
  const committed =
    workingWaypoint?.anchor === cid
      ? workingWaypoint
      : initialObserver?.anchor === cid
        ? initialObserver
        : null;
  const previewDistance = Math.hypot(
    (observer?.east_m || 0) - (committed?.east_m || 0),
    (observer?.north_m || 0) - (committed?.north_m || 0),
  );
  const moveTicket = useRef(0);
  const completedJob = useRef(''),
    dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
      if (e.key === 'Tab') {
        const list = Array.from(
          dialog.current?.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary,[tabindex="0"]',
          ) || [],
        ).filter((el) => el.getClientRects().length);
        const first = list[0],
          last = list.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('keydown', key);
      before?.focus();
    };
  }, []);
  const [planId, setPlanId] = useState(
      () => localStorage.getItem('huntmaps-first-person-plan') || '',
    ),
    [plan, setPlan] = useState<FirstPersonPlan | null>(null),
    [job, setJob] = useState<Job | null>(null),
    [allow, setAllow] = useState(false),
    [busy, setBusy] = useState(false),
    [refresh, setRefresh] = useState(0),
    [sceneVersion, setSceneVersion] = useState(0);
  const url = '/api/runs/' + runId + '/first-person/' + cid;
  const move = async (p: Target) => {
    if (updating) return;
    const ticket = ++moveTicket.current;
    setMoving(true);
    setMoveError('');
    setWaypointSaved('');
    try {
      const v = await request(url + '/observer', {
        observer_east_m: p.east_m,
        observer_north_m: p.north_m,
      });
      if (ticket === moveTicket.current) {
        setObserver(v);
        setProfile(null);
      }
    } catch (e: unknown) {
      if (ticket === moveTicket.current) setMoveError(e instanceof Error ? e.message : String(e));
    } finally {
      if (ticket === moveTicket.current) setMoving(false);
    }
  };
  const returnPosition = () => {
    if (updating) return;
    if (committed) {
      move({ east_m: committed.east_m, north_m: committed.north_m });
      return;
    }
    moveTicket.current++;
    setObserver(null);
    setProfile(null);
    setMoving(false);
    setMoveError('');
    setWaypointSaved('');
  };
  useEffect(() => {
    if (meta?.status === 'ready' && initialObserver?.anchor === cid) {
      setExplore(true);
      move({ east_m: initialObserver.east_m, north_m: initialObserver.north_m });
    }
  }, [meta?.key, initialObserver?.id]);
  useEffect(() => {
    setWaypointName(workingWaypoint?.name || initialObserver?.name || entityKey || cid);
    setWaypointNotes(workingWaypoint?.notes || initialObserver?.notes || '');
    setWaypointSaved('');
    setUpdateJob(null);
  }, [entityKey]);
  useEffect(() => {
    if (!updateJob?.id || !['running', 'cancelling'].includes(updateJob.status)) return;
    let alive = true;
    const poll = async () => {
      try {
        const [jobs, snapshot] = await Promise.all([
          Promise.resolve(jobSnapshot()),
          request('/api/runs/' + runId + '/working-waypoints'),
        ]);
        if (!alive) return;
        const j = jobs.find((v) => v.id === updateJob.id);
        if (!j) return;
        setUpdateJob(j);
        if (j.status === 'complete') {
          const p = snapshot.overrides[entityKey];
          if (p && updateDelivered.current !== j.id) {
            updateDelivered.current = j.id;
            onWaypointUpdated?.(p);
            setWaypointSaved('Waypoint updated; terrain shading is ready on the main map.');
          }
        } else if (!['running', 'cancelling'].includes(j.status))
          setMoveError(j.error || 'Waypoint unchanged. Retry Update waypoint.');
      } catch (e: unknown) {
        if (alive) setMoveError(e instanceof Error ? e.message : String(e));
      }
    };
    poll();
    const unsubscribe = subscribePolling(poll);
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [updateJob?.id, updateJob?.status, entityKey, runId]);
  const saveWaypoint = async () => {
    if (!observer || moving || updating) return;
    setSavingWaypoint(true);
    setMoveError('');
    try {
      const v = await request('/api/runs/' + runId + '/working-waypoints/' + entityKey, {
        observer_east_m: observer.east_m,
        observer_north_m: observer.north_m,
        name: waypointName || entityKey,
        notes: waypointNotes,
      });
      if (v.status === 'complete') {
        onWaypointUpdated?.(v.waypoint);
        setWaypointSaved('Waypoint updated; cached terrain shading is ready on the main map.');
      } else setUpdateJob(v.job);
    } catch (e: unknown) {
      setMoveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSavingWaypoint(false);
    }
  };

  useEffect(() => {
    let alive = true;
    setMeta(null);
    setObserver(null);
    setExplore(false);
    setMoveError('');
    setWaypointSaved('');
    moveTicket.current++;
    setMoving(false);
    setError('');
    setTarget(null);
    setProfile(null);
    setHeading(0);
    setLook(0);
    request(url)
      .then((v) => {
        if (alive) {
          setMeta(v);
          setHeading(v.initial_bearing_deg || 0);
          if (v.vegetation?.meshes?.['120']?.unavailable)
            setError(
              'The saved 120 m foliage patch is unavailable. Return to the map and review source preparation.',
            );
        }
      })
      .catch((e) => {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      alive = false;
    };
  }, [url, sceneVersion]);
  useEffect(() => {
    if (!planId) return;
    localStorage.setItem('huntmaps-first-person-plan', planId);
    let alive = true;
    const poll = async () => {
      try {
        const [p, j] = await Promise.all([
          request('/api/first-person/plans/' + planId),
          Promise.resolve(jobSnapshot()),
        ]);
        if (!alive) return;
        setPlan(p);
        const current = j.find((v) => v.plan === planId);
        setJob(current || null);
        if (
          current &&
          ['complete', 'failed'].includes(current.status) &&
          current.kind === 'first-person-prepare' &&
          completedJob.current !== current.id
        ) {
          completedJob.current = current.id;
          setSceneVersion((v) => v + 1);
        }
      } catch (e: unknown) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    };
    poll();
    const unsubscribe = subscribePolling(poll);
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [planId, refresh]);
  useEffect(() => {
    setProfile(null);
    if (!target || meta?.status !== 'ready') return;
    let alive = true;
    const timer = setTimeout(
      () =>
        request(url + '/profile', {
          ...target,
          eye_m: eye,
          target_height_m: height,
          vegetation_scenario: scenario,
          vegetation_radius_m: nearby,
          ...(observer
            ? { observer_east_m: observer.east_m, observer_north_m: observer.north_m }
            : {}),
        })
          .then((v) => {
            if (alive) setProfile(v);
          })
          .catch((e) => {
            if (alive) setError(e instanceof Error ? e.message : String(e));
          }),
      150,
    );
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [url, target, eye, height, scenario, nearby, meta?.key, observer]);
  const action = async (path: string, body: unknown) => {
    setBusy(true);
    setError('');
    try {
      const j = await request(path, body);
      setPlanId(j.plan);
      setJob(j);
      setRefresh((v) => v + 1);
      setAllow(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const active = !!job && ['running', 'cancelling'].includes(job.status);
  return (
    <div className="fp-backdrop">
      <section
        ref={dialog}
        className="fp-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="First-person terrain pilot"
      >
        <div className="section-title">
          <h2>View from {cid} · Soap Creek pilot</h2>
          <button onClick={onClose}>Return to map</button>
        </div>
        <p>
          Terrain-model preview, not a photograph or verified view through trees. Explore nearby
          positions to try another stance within 30 ft. Fine ground covers up to 300 m; distant
          terrain is coarse context.
        </p>
        <label>
          Saved setup
          <select
            aria-label="First-person setup"
            disabled={updating}
            value={cid}
            onChange={(e) => onSelect(e.target.value)}
          >
            {pilot.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        {error && (
          <div role="alert">
            {error}
            <button
              onClick={() => {
                setError('');
                setSceneVersion((v) => v + 1);
              }}
            >
              Reload scene
            </button>
          </div>
        )}
        <details open={meta?.status === 'unprepared'} className="fp-preparation">
          <summary>Prepare local fine terrain and lidar</summary>
          <p>
            One shared pilot preparation for all four setups. Existing scores and outputs stay
            unchanged. New source downloads are capped at 500 MB; cached sources are reused.
          </p>
          <button disabled={busy || active} onClick={() => action('/api/first-person/plans', {})}>
            Check source plan
          </button>
          {plan && (
            <>
              <p>
                {plan.prepared
                  ? (plan.estimated_new_bytes / 1e6).toFixed(1) + ' MB estimated new downloads'
                  : 'Checking catalog metadata…'}{' '}
                · {(plan.already_received_bytes || 0) / 1e6} MB previously transferred
              </p>
              {plan.sources?.map((s) => (
                <p key={s.key}>
                  <b>{s.cached ? 'Cached' : 'New source'}</b> · {s.title} ·{' '}
                  {(s.bytes / 1e6).toFixed(1)} MB · {s.acquisition_date}
                </p>
              ))}
              {plan.errors?.map((v: string) => (
                <p className="error" key={v}>
                  {v}
                </p>
              ))}
              <p>{plan.source_note}</p>
              <label>
                <input
                  type="checkbox"
                  checked={allow}
                  disabled={active || !plan.prepared || !!plan.errors?.length}
                  onChange={(e) => setAllow(e.target.checked)}
                />
                Allow this plan’s source downloads within 500 MB
              </label>
              <button
                disabled={busy || active || !plan.prepared}
                onClick={() =>
                  action('/api/first-person/plans/' + planId + '/start', { download: allow })
                }
              >
                {allow ? 'Download and prepare pilot' : 'Prepare using cached sources only'}
              </button>
            </>
          )}
          {job && (
            <div className="fp-job" role="status">
              <b>{job.status}</b> · {job.stage} · {job.elapsed_s || 0} s{' '}
              {active && (
                <button
                  disabled={job.status === 'cancelling'}
                  onClick={() =>
                    request('/api/jobs/' + job.id + '/cancel', {})
                      .then(() => setRefresh((v) => v + 1))
                      .catch((e) => {
                        setError(e instanceof Error ? e.message : String(e));
                        setRefresh((v) => v + 1);
                      })
                  }
                >
                  Cancel preparation
                </button>
              )}
              {job.error && <p>{job.error}</p>}
              <JobLogs id={job.id} label="Actual preparation log" />
            </div>
          )}
        </details>
        {meta?.status === 'ready' && meta.candidate === cid && (
          <>
            <div className="fp-controls">
              <label>
                Eye height: {eye.toFixed(1)} m
                <input
                  aria-label="First-person eye height"
                  type="range"
                  min=".8"
                  max="2.2"
                  step=".1"
                  value={eye}
                  onChange={(e) => setEye(+e.target.value)}
                />
              </label>
              <label>
                Heading: {heading.toFixed(0)}°
                <input
                  aria-label="First-person heading"
                  type="range"
                  min="0"
                  max="359"
                  value={heading}
                  onChange={(e) => setHeading(+e.target.value)}
                />
              </label>
              <label>
                Look up/down: {look.toFixed(0)}°
                <input
                  aria-label="First-person look angle"
                  type="range"
                  min="-70"
                  max="70"
                  value={look}
                  onChange={(e) => setLook(+e.target.value)}
                />
              </label>
              <button
                onClick={() => {
                  setHeading(meta.initial_bearing_deg || 0);
                  setLook(0);
                  setEye(1.7);
                }}
              >
                Reset view
              </button>
              <label>
                <input
                  type="checkbox"
                  checked={foliage}
                  onChange={(e) => setFoliage(e.target.checked)}
                />
                Inferred vegetation
              </label>
              <span>Dense foliage · saved 120 m patch</span>
            </div>
            <p className="notice">
              {meta.fine_observer_available
                ? 'Local lidar-derived ground'
                : 'Baseline-only preview: fine ground at the observer is unknown.'}{' '}
              · {(meta.coverage_fraction * 100).toFixed(1)}% of the 300 m circle has supported fine
              ground · {meta.acquisition_date}.{' '}
              {points
                ? 'Above-ground returns: green vegetation-class, amber unclassified, blue other classes. Missing returns do not mean empty space.'
                : ''}{' '}
              Aerial imagery is always shown where available; photographed canopy lies on ground,
              not reconstructed trees. Foliage clusters infer vegetation from returns; shape,
              thickness and opacity are assumptions. Weaker measurements are included where nearby
              stronger measurements support a patch. Colors follow cached photographs, not
              vegetation identification. Only centres within {nearby} m are screened; farther
              vegetation is unevaluated. Missing returns do not prove open space. Amber diagnostic
              markers are unclassified.
            </p>
            {meta.vegetation.meshes && (
              <p className="hint">
                Cluster surface detail:{' '}
                {meta.vegetation.meshes[String(nearby)]?.sampling_interval_m} m sampling
                {meta.vegetation.meshes[String(nearby)]?.sampling_interval_m > 0.25
                  ? ' · reduced detail to stay within the lightweight rendering budget'
                  : ''}
                . {meta.vegetation.neighbor_supported_cell_count.toLocaleString()} cells added
                through neighboring support across the prepared 120 m area. Missing measurements do
                not establish a clear view.
              </p>
            )}
            <div className="fp-workspace">
              <div>
                <Viewer
                  observer={observer}
                  meta={meta}
                  url={url}
                  eye={eye}
                  heading={heading}
                  look={look}
                  points={points}
                  foliage={foliage}
                  scenario={scenario}
                  nearby={nearby}
                  target={target}
                  profile={profile}
                  range={range}
                  onTarget={setTarget}
                  onHeading={setHeading}
                  onLook={setLook}
                />
              </div>
              <aside>
                <section className="fp-nearby">
                  <h3>Explore nearby positions</h3>
                  <p>
                    Try another stance within 30 ft of {cid}, using the same cached scene. Click
                    Update waypoint to apply your stance and calculate its terrain shading. The
                    original setup remains available.
                  </p>
                  <button onClick={() => setExplore((v) => !v)}>
                    {explore ? 'Hide position controls' : 'Explore nearby positions'}
                  </button>
                  {explore && (
                    <>
                      <h4>Move the observer</h4>
                      <p>
                        Click inside the pale circle, or use arrow keys for one-foot steps. White
                        centre: current waypoint; orange: preview. Pale circle: allowed movement
                        around the original setup. Small cross: original setup. Positions must
                        remain inside your observer area.
                      </p>
                      <PositionMap
                        meta={meta}
                        url={url}
                        pose={observer}
                        centre={committed}
                        onMove={move}
                      />
                      <div className="row">
                        {[
                          ['North', 0, 0.3048],
                          ['South', 0, -0.3048],
                          ['West', -0.3048, 0],
                          ['East', 0.3048, 0],
                        ].map(([label, e, n]) => (
                          <button
                            key={label}
                            disabled={moving || updating}
                            aria-label={'Move observer one foot ' + String(label).toLowerCase()}
                            onClick={() =>
                              move({
                                east_m: (observer?.east_m || 0) + Number(e),
                                north_m: (observer?.north_m || 0) + Number(n),
                              })
                            }
                          >
                            {label} 1 ft
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                  {moving && <p role="status">Checking supported ground…</p>}
                  {moveError && <p role="alert">{moveError}</p>}
                  {observer && (
                    <>
                      <p className="notice" data-preview-position={JSON.stringify(observer)}>
                        Nearby preview: {observer.latitude.toFixed(7)},{' '}
                        {observer.longitude.toFixed(7)} · {(previewDistance / 0.3048).toFixed(1)} ft
                        from the current waypoint.{' '}
                        {previewDistance > 1e-8
                          ? 'Preview only until you click Update waypoint.'
                          : 'At the current waypoint.'}
                      </p>
                      <p>
                        Foliage coverage stays centred on {cid}. Moving does not extend the saved
                        120 m patch. Farther vegetation is unevaluated.
                      </p>
                      <button disabled={updating} onClick={returnPosition}>
                        Return to current waypoint
                      </button>
                      <details>
                        <summary>Update waypoint</summary>
                        <label>
                          Waypoint name
                          <input
                            aria-label="Waypoint name"
                            maxLength={100}
                            value={waypointName}
                            onChange={(e) => setWaypointName(e.target.value)}
                            placeholder={cid + ' nearby observer'}
                          />
                        </label>
                        <label>
                          Field notes
                          <textarea
                            aria-label="Waypoint notes"
                            maxLength={10000}
                            value={waypointNotes}
                            onChange={(e) => setWaypointNotes(e.target.value)}
                          />
                        </label>
                        <p>
                          Updates this working setup, marks it “needs inspection”, and calculates a
                          terrain-only view using cached sources. No downloads. Original scores
                          remain historical.
                        </p>
                        <button
                          disabled={moving || updating || globalBusy || !!waypointSaved}
                          onClick={saveWaypoint}
                        >
                          Update waypoint
                        </button>
                        <p role="status">{waypointSaved}</p>
                        {globalBusy && !updating && (
                          <p>Another analysis job is running. Wait or cancel it before updating.</p>
                        )}
                        {updateJob && (
                          <section className="fp-update-job" role="status">
                            <b>{updateJob.status}</b> · {updateJob.stage} ·{' '}
                            {updateJob.elapsed_s || 0} s{' '}
                            {['running', 'cancelling'].includes(updateJob.status) && (
                              <button
                                disabled={updateJob.status === 'cancelling'}
                                onClick={() =>
                                  request('/api/jobs/' + updateJob.id + '/cancel', {})
                                    .then((v) => setUpdateJob(v))
                                    .catch((e) =>
                                      setMoveError(e instanceof Error ? e.message : String(e)),
                                    )
                                }
                              >
                                Cancel waypoint update
                              </button>
                            )}
                            <JobLogs id={updateJob.id} label="Actual waypoint update log" />
                          </section>
                        )}
                      </details>
                    </>
                  )}
                </section>
                <h3>Inspect a sightline</h3>
                <p>
                  Drag the scene or use arrow keys to look around. Choose a target on the plan map
                  to inspect terrain hidden behind a rise.
                </p>
                <label>
                  Plan map radius
                  <select
                    aria-label="Inspection map radius"
                    value={range}
                    onChange={(e) => setRange(+e.target.value)}
                  >
                    <option value={300}>300 m — fine ground</option>
                    <option value={2000}>2 km — separate baseline profile</option>
                  </select>
                </label>
                <label>
                  Assumed target height: {height.toFixed(1)} m
                  <input
                    aria-label="Inspection target height"
                    type="range"
                    min="0"
                    max="2.5"
                    step=".1"
                    value={height}
                    onChange={(e) => setHeight(+e.target.value)}
                  />
                </label>
                <ProfileChart profile={profile} />
                <VegetationResult profile={profile} enabled={foliage} />
                {target &&
                  (profile?.points?.length || 0) > 0 &&
                  profile?.points?.[0]?.line_m !== null &&
                  profile?.points?.at(-1)?.line_m !== null && (
                    <button
                      onClick={() => {
                        setHeading(
                          ((Math.atan2(
                            target.east_m - (observer?.east_m || 0),
                            target.north_m - (observer?.north_m || 0),
                          ) *
                            180) /
                            Math.PI +
                            360) %
                            360,
                        );
                        setLook(
                          Math.max(
                            -70,
                            Math.min(
                              70,
                              (Math.atan2(
                                (profile?.points.at(-1)?.line_m ?? 0) -
                                  (profile?.points[0].line_m ?? 0),
                                profile?.distance_m || 1,
                              ) *
                                180) /
                                Math.PI,
                            ),
                          ),
                        );
                      }}
                    >
                      Look toward inspection target
                    </button>
                  )}
                <details>
                  <summary>Sources, coverage and technical details</summary>
                  <label>
                    <input
                      type="checkbox"
                      checked={points}
                      onChange={(e) => setPoints(e.target.checked)}
                    />
                    Measured above-ground returns
                  </label>
                  <p>{meta.initial_facing_note}</p>
                  <p>{meta.ground_interpolation}</p>
                  <p>{meta.vertical_note}</p>
                  <p>{meta.warning}</p>
                  <p>{meta.vegetation?.warning}</p>
                  <p>
                    Vegetation cells: {meta.vegetation?.cell_count.toLocaleString()} · inferred:{' '}
                    {meta.vegetation?.inferred_cell_count.toLocaleString()} · classified support:{' '}
                    {meta.vegetation?.classified_cell_count.toLocaleString()}. Foliage colors sample
                    aerial imagery; missing imagery uses green. Colors do not indicate
                    classification. No vegetation model beyond 300 m.
                  </p>
                  <p>
                    Display: {meta.display_point_count.toLocaleString()} of{' '}
                    {meta.above_ground_point_count.toLocaleString()} eligible above-ground returns (
                    {meta.raw_local_point_count.toLocaleString()} total local returns); stride{' '}
                    {meta.display_stride}. {meta.point_filter}. Local photo spacing:{' '}
                    {meta.texture?.pixel_spacing_m} m; context photo spacing:{' '}
                    {meta.context_texture?.pixel_spacing_m?.toFixed(2)} m. Underlying acquisition:{' '}
                    {meta.texture?.native_resolution_m?.join(', ')} m. Numerical borderline margin:
                    5 cm, not measurement accuracy.
                  </p>
                  <pre>
                    {JSON.stringify(
                      {
                        observer: meta.observer,
                        vertical_reference: meta.vertical_reference,
                        sources: meta.sources,
                        classification_counts: meta.classification_counts,
                        vegetation: meta.vegetation,
                        maximum_support_distance_m: meta.maximum_support_distance_m,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </aside>
            </div>
          </>
        )}
        {meta?.status === 'unprepared' && (
          <p>
            No fine scene has been prepared yet. Check the source plan above; acquisition starts
            only through its explicit preparation action.
          </p>
        )}
      </section>
    </div>
  );
}
