import { useEffect, useRef, useState } from 'react';
import DecimalField from './decimal-field';
import DownloadReview from './download-review';
import { jobSnapshot, subscribePolling, trackJob } from './polling';
import type { Job } from './types';
import type { AppliedFilter } from './scouting-tools';

export type ConnectionEvidence = {
  status: 'connection_found' | 'no_connection' | 'unavailable';
  maximum_slope_deg: number;
  message: string;
  reason: string;
  next_limit_deg?: number;
};
export type ConnectionScreen = {
  id: string;
  run_id: string;
  status: string;
  completed: number;
  total: number;
  maximum_slope_deg: number;
  points: Record<string, ConnectionEvidence>;
  bounds?: number[];
  job?: Job;
  recommendation_pool?: {
    id: string;
    x: number;
    y: number;
    raw_km2?: number;
    matching_km2?: number;
    foreground_category?: string;
    group?: string;
    standing_eligible?: boolean;
  }[];
  recommendation_count?: number;
  separation_m?: number;
};
type Api = (path: string, options?: RequestInit) => Promise<any>;
const mode = (run: string) =>
  (localStorage.getItem('huntmaps-connection-mode:' + run) ||
    localStorage.getItem('huntmaps-connection-mode')) === 'all';
export function connectionLabel(e?: ConnectionEvidence) {
  return !e
    ? 'Connection unchecked'
    : e.status === 'connection_found'
      ? `Modeled connection found · ${e.maximum_slope_deg}°`
      : e.status === 'no_connection'
        ? `No connection at ${e.maximum_slope_deg}°`
        : 'Connection screen unavailable';
}
export function screenedRecommendations(
  screen: ConnectionScreen | null,
  filter: AppliedFilter | null,
) {
  const rows = (screen?.recommendation_pool || [])
    .filter(
      (p) =>
        screen?.points[p.id]?.status === 'connection_found' &&
        p.group !== 'manual' &&
        p.standing_eligible !== false,
    )
    .map((p) => {
      const f = filter?.candidates.find((f) => f.id === p.id);
      return {
        ...p,
        matching_km2: f ? f.matching_km2 : p.matching_km2,
        qualifies: !filter || !!f?.qualifies,
      };
    })
    .filter((p) => p.qualifies && (p.matching_km2 ?? p.raw_km2 ?? 0) > 0);
  const cover: Record<string, number> = {
    'low mapped tree cover': 0,
    'other known cover': 1,
    'insufficient coverage': 2,
  };
  rows.sort((a, b) =>
    a.matching_km2 !== undefined && b.matching_km2 !== undefined
      ? b.matching_km2 - a.matching_km2 ||
        (b.raw_km2 || 0) - (a.raw_km2 || 0) ||
        a.id.localeCompare(b.id)
      : (cover[a.foreground_category || 'insufficient coverage'] ?? 2) -
          (cover[b.foreground_category || 'insufficient coverage'] ?? 2) ||
        (b.raw_km2 || 0) - (a.raw_km2 || 0) ||
        a.id.localeCompare(b.id),
  );
  const selected: typeof rows = [];
  for (const p of rows)
    if (selected.every((q) => Math.hypot(p.x - q.x, p.y - q.y) >= (screen?.separation_m || 0))) {
      selected.push(p);
      if (selected.length >= (screen?.recommendation_count || 20)) break;
    }
  return selected.map((p) => p.id);
}

export function useConnectionScreen(run: string, active: boolean, inputs: string, api: Api) {
  const [screen, setScreen] = useState<ConnectionScreen | null>(null);
  const [showAll, setAll] = useState(() => mode(run));
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [maximum, setMaximum] = useState(25),
    [epoch, setEpoch] = useState(0);
  const [sourcePlan, setSourcePlan] = useState<any>(null);
  const generation = useRef(0),
    submitting = useRef(false);
  const displayedLimit = useRef('');
  const operationError = useRef(false);
  useEffect(() => {
    generation.current++;
    setScreen(null);
    setError('');
    operationError.current = false;
    setAll(mode(run));
    setSourcePlan(null);
  }, [run, inputs]);
  useEffect(() => {
    if (!active || !run) return;
    let alive = true,
      pending = false;
    const ticket = ++generation.current;
    const current = () => alive && generation.current === ticket;
    const read = async () => {
      if (pending || submitting.current) return;
      pending = true;
      try {
        let value: ConnectionScreen = await api(`/runs/${run}/connectivity-screen`);
        if (!current()) return;
        if (
          !showAll &&
          value.status === 'not_started' &&
          !jobSnapshot().some((j) => ['running', 'cancelling'].includes(j.status))
        ) {
          setBusy(true);
          value = await api(`/runs/${run}/connectivity-screen`, { method: 'POST', body: '{}' });
          if (value.job) trackJob(value.job);
          if (!current()) return;
        }
        setScreen(value);
        if (!operationError.current) setError('');
        const marker = run + ':' + value.maximum_slope_deg;
        if (displayedLimit.current !== marker) {
          displayedLimit.current = marker;
          setMaximum(value.maximum_slope_deg);
        }
      } catch (e) {
        if (current()) setError(String(e));
      } finally {
        pending = false;
        if (current()) setBusy(false);
      }
    };
    void read();
    const unsubscribe = subscribePolling(() => void read());
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [run, active, inputs, showAll, epoch]);
  async function start(saveDefault = false) {
    if (submitting.current) return;
    submitting.current = true;
    operationError.current = false;
    const ticket = ++generation.current;
    setBusy(true);
    setError('');
    setScreen(null);
    try {
      const value = await api(`/runs/${run}/connectivity-screen`, {
        method: 'POST',
        body: JSON.stringify(saveDefault ? { maximum_slope_deg: maximum, save_default: true } : {}),
      });
      if (value.job) trackJob(value.job);
      if (generation.current !== ticket) return;
      setScreen(value);
      setEpoch((v) => v + 1);
    } catch (e) {
      if (generation.current === ticket) {
        operationError.current = true;
        setError(String(e));
        setEpoch((v) => v + 1);
      }
    } finally {
      submitting.current = false;
      if (generation.current === ticket) setBusy(false);
    }
  }
  const setShowAll = (value: boolean) => {
    localStorage.setItem('huntmaps-connection-mode:' + run, value ? 'all' : 'screened');
    setAll(value);
  };
  const otherBusy = jobSnapshot().some((j) => ['running', 'cancelling'].includes(j.status));
  return {
    screen: screen?.run_id === run ? screen : null,
    showAll,
    setShowAll,
    busy,
    error,
    maximum,
    setMaximum,
    start,
    otherBusy,
    sourcePlan,
    signature: JSON.stringify([screen?.id, screen?.status, screen?.completed, showAll]),
    async cancel() {
      if (!screen?.job || submitting.current) return;
      submitting.current = true;
      const ticket = generation.current;
      setScreen((old) => (old?.job ? { ...old, job: { ...old.job, status: 'cancelling' } } : old));
      try {
        await api('/jobs/' + screen.job.id + '/cancel', { method: 'POST' });
      } catch (e) {
        if (generation.current === ticket) {
          operationError.current = true;
          setError(String(e));
        }
      } finally {
        submitting.current = false;
        if (generation.current === ticket) setEpoch((v) => v + 1);
      }
    },
    async sources(approve = false) {
      if (submitting.current) return;
      submitting.current = true;
      operationError.current = false;
      setBusy(true);
      setError('');
      const ticket = generation.current;
      try {
        if (approve && sourcePlan) {
          const j = await api('/network-plans/' + sourcePlan.id + '/start', {
            method: 'POST',
            body: JSON.stringify({ download: true }),
          });
          trackJob(j);
          if (generation.current !== ticket) return;
          setSourcePlan(null);
          setEpoch((v) => v + 1);
        } else if (screen?.bounds) {
          const p = await api('/network-plans', {
            method: 'POST',
            body: JSON.stringify({ bounds: screen.bounds, max_download_mb: 20 }),
          });
          if (generation.current === ticket) setSourcePlan(p);
        }
      } catch (e) {
        if (generation.current === ticket) {
          operationError.current = true;
          setError(String(e));
        }
      } finally {
        submitting.current = false;
        if (generation.current === ticket) setBusy(false);
      }
    },
  };
}
export default function ConnectionControls({
  value,
}: {
  value: ReturnType<typeof useConnectionScreen>;
}) {
  const { screen, showAll, busy, error, maximum, otherBusy, sourcePlan } = value;
  const found = Object.values(screen?.points || {}).filter(
    (p) => p.status === 'connection_found',
  ).length;
  const unavailable = Object.values(screen?.points || {}).some(
    (p) => p.reason === 'network_coverage',
  );
  return (
    <section
      className="connection-screen"
      aria-label="Terrain connection screen"
      data-screen-run={screen?.run_id || ''}
    >
      <label>
        <input
          type="checkbox"
          checked={showAll}
          onChange={(e) => value.setShowAll(e.target.checked)}
        />{' '}
        Show all setups
      </label>
      <p role="status">
        {busy
          ? 'Starting connection check…'
          : screen?.status === 'running'
            ? `Checking connections · ${screen.completed}/${screen.total}`
            : !screen || screen.status === 'not_started'
              ? showAll
                ? 'Connections have not been checked.'
                : otherBusy
                  ? 'Waiting for the active job before checking connections.'
                  : 'Checking source coverage…'
              : ['cancelled', 'interrupted', 'failed'].includes(screen.status)
                ? `Connection check ${screen.status} · ${screen.completed}/${screen.total} checked`
                : `${found} setups with modeled connections`}
      </p>
      {screen?.status === 'running' && screen.job && (
        <button
          disabled={busy || screen.job.status === 'cancelling'}
          onClick={() => void value.cancel()}
        >
          {screen.job.status === 'cancelling'
            ? 'Cancelling connection check…'
            : 'Cancel connection check'}
        </button>
      )}
      {screen?.status !== 'running' && (
        <button disabled={busy || otherBusy} onClick={() => void value.start()}>
          {screen?.status === 'complete' ? 'Check connections again' : 'Check connections'}
        </button>
      )}
      {unavailable && (
        <p>
          Some search boundaries need verified roads/trails. Prepare sources or choose Show all.
        </p>
      )}
      {unavailable && screen?.bounds && (
        <button disabled={busy || otherBusy} onClick={() => void value.sources()}>
          Review roads/trails preparation
        </button>
      )}
      {sourcePlan && (
        <div className="notice">
          <p>
            Roads and trails · up to {(sourcePlan.estimated_bytes / 1e6).toFixed(0)} MB new
            transfer.
          </p>
          <DownloadReview plan={sourcePlan} bytes={sourcePlan.estimated_bytes} />
          <button
            disabled={busy || otherBusy || sourcePlan.storage?.blocked}
            onClick={() => void value.sources(true)}
          >
            Approve roads/trails preparation
          </button>
        </div>
      )}
      <details>
        <summary>Connection settings</summary>
        <small>
          {showAll
            ? 'All setups shown, including unchecked spots.'
            : 'Showing modeled connections under each spot’s limit; saved and manual spots remain available.'}
        </small>

        <label>
          Maximum modeled slope (degrees)
          <DecimalField
            aria-label="Connection slope limit"
            value={maximum}
            onChange={value.setMaximum}
            min={1}
            max={35}
            disabled={busy || otherBusy}
          />
        </label>
        <button
          disabled={busy || otherBusy || !Number.isFinite(maximum) || maximum <= 0 || maximum > 35}
          onClick={() => void value.start(true)}
        >
          Apply connection limit
        </button>
        <p>
          Screening checks terrain connections to mapped departures, not distance, climbing effort
          or access permission. Each approach boundary still needs confirmation.
        </p>
      </details>
      {error && <p role="alert">{error}</p>}
      {screen?.status === 'failed' && screen.job?.error && <p role="alert">{screen.job.error}</p>}
    </section>
  );
}
