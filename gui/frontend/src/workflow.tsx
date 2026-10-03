import { useEffect, useRef, useState } from 'react';
export type Workflow = {
  revision: number;
  points: Record<
    string,
    {
      point: { id: string; longitude: number; latitude: number; revision: string };
      shortlisted: boolean;
      legacy: boolean;
      approach: { scenario: string; alternative: number; seal: string } | null;
      viewed: string | null;
      fidelity?: string;
      confirmed: boolean;
      stale: boolean;
    }
  >;
};
export default function WorkflowPanel({
  runId,
  workflow,
  cid,
  inspect,
  onDecision,
  onInspect,
  onApproaches,
  api,
}: {
  runId: string;
  workflow: Workflow | null;
  cid: string;
  inspect: boolean;
  onDecision: (cid: string, action: string, extra?: Record<string, unknown>) => Promise<void>;
  onInspect: () => void;
  onApproaches: () => void;
  api: (path: string, options?: RequestInit) => Promise<any>;
}) {
  const alive = useRef(true);
  useEffect(
    () => () => {
      alive.current = false;
    },
    [],
  );
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [fidelity, setFidelity] = useState('terrain');
  const p = workflow?.points[cid];
  const eligible = Object.values(workflow?.points || {}).filter((p) => p.shortlisted && p.approach);
  async function prepare() {
    setBusy(true);
    setError('');
    try {
      const j = await api('/first-person/plans', {
        method: 'POST',
        body: JSON.stringify({ run_id: runId, ids: eligible.map((p) => p.point.id), fidelity }),
      });
      if (!alive.current) return;
      localStorage.setItem('huntmaps-first-person-plan:' + runId, j.plan);
      onInspect();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workflow-task">
      <h3>{inspect ? 'Inspect and confirm' : 'Setup decision'}</h3>
      {p?.legacy && <small>Legacy Keep candidate; original annotation preserved.</small>}
      <div className="candidate-actions">
        <button onClick={() => onDecision(cid, 'shortlist')} disabled={!cid}>
          {p?.shortlisted ? 'Shortlisted' : 'Shortlist'}
        </button>
        <button onClick={() => onDecision(cid, 'remove')} disabled={!cid}>
          Remove
        </button>
      </div>
      {inspect && (
        <>
          <p>
            Prepare the selected approaches as one batch. Shared sources are reused. Review any new
            download before preparation.
          </p>
          <label>
            Scene fidelity
            <select value={fidelity} onChange={(e) => setFidelity(e.target.value)}>
              <option value="terrain">Terrain-only · existing DEM</option>
              <option value="lidar">Inspect available lidar acquisitions</option>
            </select>
          </label>
          <button className="primary wide" disabled={!eligible.length || busy} onClick={prepare}>
            Prepare views ({eligible.length})
          </button>
          {p?.approach && (
            <p>
              Selected approach: {p.approach.scenario.slice(0, 8)} · alternative{' '}
              {p.approach.alternative + 1}.{' '}
              <a
                href={`/api/approaches/${p.approach.scenario}/export/gpx?waypoint=${cid}&alternative=${p.approach.alternative}`}
              >
                Provisional approach
              </a>
            </p>
          )}
          <button onClick={onInspect} disabled={!cid}>
            Inspect current setup
          </button>
          <button onClick={onApproaches}>Return to approaches</button>
          <button
            className="primary wide"
            disabled={!p?.approach || !p?.viewed}
            onClick={() => onDecision(cid, 'confirm')}
          >
            {p?.confirmed ? 'Setup confirmed' : 'Confirm setup'}
          </button>
          {(!p?.approach || !p?.viewed) && (
            <p>
              {!p?.approach
                ? 'Select a current approach for this setup.'
                : 'Successfully open this setup’s current scene to confirm.'}
            </p>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {inspect && (
        <details open>
          <summary>Confirmed collection</summary>
          {Object.values(workflow?.points || {})
            .filter((p) => p.confirmed)
            .map((p) => (
              <p key={p.point.id}>
                {p.point.id} · {p.fidelity || 'modeled'} scene · permissions, parking and field
                sightlines unresolved.{' '}
                <a href={`/api/runs/${runId}/export/gpx?ids=${p.point.id}`}>Destination waypoint</a>{' '}
                ·{' '}
                <a
                  href={`/api/approaches/${p.approach!.scenario}/export/gpx?waypoint=${p.point.id}&alternative=${p.approach!.alternative}`}
                >
                  Provisional approach
                </a>
              </p>
            ))}
        </details>
      )}
    </section>
  );
}
