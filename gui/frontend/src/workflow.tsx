import { useEffect, useRef, useState } from 'react';
export type Workflow = {
  revision: number;
  approach_review?: { active: boolean; ready: boolean; unresolved: string[] };
  points: Record<
    string,
    {
      point: { id: string; longitude: number; latitude: number; revision: string };
      shortlisted: boolean;
      dismissed?: boolean;
      undo_revision?: number;
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
  pending = false,
  onDecision,
  onInspect,
  onApproaches,
  api,
}: {
  runId: string;
  workflow: Workflow | null;
  cid: string;
  inspect: boolean;
  pending?: boolean;
  onDecision: (cid: string, action: string, extra?: Record<string, unknown>) => Promise<boolean>;
  onInspect: () => void;
  onApproaches: () => void;
  api: (path: string, options?: RequestInit) => Promise<any>;
}) {
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
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
      <h3>{inspect ? `Inspect ${cid}` : 'Keep investigating?'}</h3>
      {p?.legacy && <small>Retained from your earlier review.</small>}
      <div className="candidate-actions">
        <button
          onClick={() => onDecision(cid, 'shortlist')}
          disabled={!cid || pending || p?.shortlisted}
        >
          {p?.shortlisted ? 'Shortlisted' : 'Shortlist'}
        </button>
        <button
          onClick={() => onDecision(cid, 'remove')}
          disabled={!cid || pending || !p?.shortlisted}
        >
          Remove from shortlist
        </button>
      </div>
      {inspect && (
        <>
          <p>Explore the view from your selected setups before adding them to your collection.</p>
          <label>
            View detail
            <select value={fidelity} onChange={(e) => setFidelity(e.target.value)}>
              <option value="terrain">Terrain · saved elevation</option>
              <option value="lidar">Detailed ground · check lidar sources</option>
            </select>
          </label>
          <button className="primary wide" disabled={!eligible.length || busy} onClick={prepare}>
            {busy ? 'Checking view sources…' : `Prepare views (${eligible.length})`}
          </button>
          {p?.approach && (
            <p>
              Approach {p.approach.alternative + 1} selected.{' '}
              <a
                href={`/api/approaches/${p.approach.scenario}/export/gpx?waypoint=${cid}&alternative=${p.approach.alternative}`}
              >
                Provisional approach
              </a>
            </p>
          )}
          <button onClick={onInspect} disabled={!cid || pending}>
            Inspect current setup
          </button>
          <button onClick={onApproaches}>Return to approaches</button>
          <button
            className="primary wide"
            disabled={
              pending ||
              p?.confirmed ||
              !p?.approach ||
              !p?.viewed ||
              (workflow?.approach_review?.active && !workflow.approach_review.ready)
            }
            onClick={() => onDecision(cid, 'confirm')}
          >
            {p?.confirmed ? '✓ Saved to collection' : 'Confirm setup'}
          </button>
          {(!p?.approach ||
            !p?.viewed ||
            (workflow?.approach_review?.active && !workflow.approach_review.ready)) && (
            <p>
              {workflow?.approach_review?.active && !workflow.approach_review.ready
                ? 'Finish approach review for every retained spot before confirming.'
                : !p?.approach
                  ? 'Select a current approach for this setup.'
                  : 'Successfully open this setup’s current scene to confirm.'}
            </p>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {inspect && (
        <details>
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
