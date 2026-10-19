import { adjusted, acres } from './habitat';
import { useEffect, useRef, useState } from 'react';
import { area } from './units';
import type { Workflow } from './workflow';
export type Contribution = {
  id: string;
  habitat_status?: string;
  scorable_m2?: number;
  habitat_unknown_m2?: number;
  total_effective_m2?: number | null;
  additional_effective_m2?: number | null;
  total_priority_m2?: number | null;
  additional_priority_m2?: number | null;
  weighted_overlap_percent?: number | null;
  total_km2: number | null;
  additional_km2: number | null;
  overlap_percent: number | null;
  point: { longitude: number; latitude: number };
};
export type Collection = {
  id: string;
  run_id: string;
  profile: string;
  count: number;
  kept: Contribution[];
  suggestions: Contribution[];
  unknown_ids: string[];
  combined_km2: number;
  habitat_profile?: string;
  habitat_status?: string;
  combined_scorable_m2?: number;
  combined_habitat_unknown_m2?: number;
  combined_effective_m2?: number;
  combined_priority_m2?: number;
  initial_effective_m2?: number;
  initial_priority_m2?: number;
  initial_km2: number;
  separation_m: number;
};
export default function ComplementaryViews({
  run,
  selected,
  profile,
  connectionScreen = '',
  habitatProfile = '',
  signature,
  paused,
  onResult,
  onSelect,
  onAdded,
  onDecision,
  api,
}: {
  run: string;
  selected: string;
  profile: string;
  connectionScreen?: string;
  habitatProfile?: string;
  signature: string;
  paused: boolean;
  onResult: (result: Collection | null, signature: string) => void;
  onSelect: (id: string) => void;
  onAdded: (workflow: Workflow) => void;
  onDecision: (cid: string, action: string) => Promise<boolean>;
  api: (path: string, options?: RequestInit) => Promise<any>;
}) {
  const [count, setCount] = useState(5);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{ value: Collection; signature: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [pendingDecision, setPendingDecision] = useState('');
  async function decide(cid: string, action: string) {
    if (pendingDecision) return;
    setPendingDecision(cid + ':' + action);
    try {
      await onDecision(cid, action);
    } finally {
      setPendingDecision('');
    }
  }
  const [error, setError] = useState('');
  const callbacks = useRef({ onResult, onSelect, onAdded });
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  callbacks.current = { onResult, onSelect, onAdded };
  const currentSignature = useRef(signature);
  currentSignature.current = signature;
  const active =
    result?.signature === signature && result.value.count === count ? result.value : null;
  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    setResult(null);
    setError('');
    callbacks.current.onResult(null, signature);
    if (paused) {
      setBusy(false);
      return;
    }
    setBusy(true);
    api(`/runs/${run}/complementary`, {
      method: 'POST',
      body: JSON.stringify({
        count,
        profile,
        connection_screen: connectionScreen,
        habitat_profile: habitatProfile,
      }),
      signal: controller.signal,
    })
      .then((value: Collection) => {
        if (
          !alive ||
          currentSignature.current !== signature ||
          value.run_id !== run ||
          value.profile !== profile ||
          (value.habitat_profile || '') !== habitatProfile ||
          value.count !== count
        )
          return;
        setResult({ value, signature });
        callbacks.current.onResult(value, signature);
      })
      .catch((e) => {
        if (alive && !controller.signal.aborted) setError(String(e));
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
      controller.abort();
    };
  }, [run, profile, signature, count, retry, paused, connectionScreen, habitatProfile]);
  async function add() {
    if (!active) return;
    setAdding(true);
    setError('');
    const stamp = signature;
    try {
      const state = await api(`/runs/${run}/complementary/${active.id}/add`, { method: 'POST' });
      if (mounted.current && currentSignature.current === stamp) callbacks.current.onAdded(state);
    } catch (e) {
      if (currentSignature.current === stamp) setError(String(e));
    } finally {
      setAdding(false);
    }
  }
  return (
    <section className="complementary-views" aria-label="Complementary views">
      <label>
        Collection size{' '}
        <select
          aria-label="Complementary collection size"
          value={count}
          disabled={adding || !!pendingDecision}
          onChange={(e) => setCount(+e.target.value)}
        >
          {[3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n} positions
            </option>
          ))}
        </select>
      </label>
      <p className="hint">
        Includes your existing shortlist. Adds the most uncovered matching terrain at each step,
        respecting eligibility and spacing. A greedy recommendation, not a proven global optimum or
        visiting order.
      </p>
      {busy && (
        <p role="status">
          <progress aria-label="Calculating complementary coverage" /> Comparing saved analytical
          coverage… The map remains available.
        </p>
      )}
      {paused && (
        <p role="status">Coverage suggestions resume when the current operation finishes.</p>
      )}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button onClick={() => setRetry((n) => n + 1)}>Retry collection</button>
        </div>
      )}
      {active && (
        <>
          <div className="collection-total" role="status">
            <b>
              {habitatProfile
                ? `Unique useful coverage: ${adjusted(active.habitat_status === 'insufficient_data' ? null : active.combined_effective_m2)} · ${acres(active.combined_priority_m2)} priority`
                : `Combined matching terrain: ${area(active.combined_km2)}`}
            </b>
            <small>
              Counted once across {active.kept.length} retained + {active.suggestions.length}{' '}
              suggested positions.
            </small>
          </div>
          {habitatProfile && (
            <small>
              {acres(active.combined_scorable_m2)} scorable matching union ·{' '}
              {acres(active.combined_habitat_unknown_m2)} habitat/neighborhood unknown in the
              matching union.
            </small>
          )}
          {active.unknown_ids.length > 0 && (
            <p className="notice">
              Retained {active.unknown_ids.join(', ')}. No calculated coverage at these current
              coordinates; their contribution is unknown and excluded from the measured total.
            </p>
          )}
          {!!active.kept.length && (
            <details>
              <summary>
                Your retained positions ({active.kept.length}) · {area(active.initial_km2)} known
                coverage
              </summary>
              {active.kept.map((p) => (
                <p key={p.id}>
                  {p.id}:{' '}
                  {habitatProfile &&
                    `${adjusted(p.total_effective_m2)} total · ${adjusted(p.additional_effective_m2)} incremental at inclusion · ${acres(p.total_priority_m2)} total priority · ${acres(p.additional_priority_m2)} incremental priority · ${acres(p.habitat_unknown_m2)} habitat/neighbor unknown. `}{' '}
                  {p.total_km2 === null
                    ? 'Contribution unknown'
                    : area(p.total_km2) + ' total matching terrain'}
                </p>
              ))}
            </details>
          )}
          <div className="collection-suggestions">
            {active.suggestions.map((p) => (
              <div key={p.id} className="collection-suggestion-card">
                <button
                  className="collection-suggestion"
                  onClick={() => onSelect(p.id)}
                  aria-label={'Preview contribution ' + p.id}
                  aria-pressed={selected === p.id}
                >
                  <b>{p.id}</b>
                  <span>Total matching: {area(p.total_km2)}</span>
                  <strong>Additional: {area(p.additional_km2)}</strong>
                  {habitatProfile && (
                    <small>
                      {adjusted(p.total_effective_m2)} total · {adjusted(p.additional_effective_m2)}{' '}
                      incremental at inclusion · {acres(p.total_priority_m2)} total priority ·{' '}
                      {acres(p.additional_priority_m2)} incremental priority ·{' '}
                      {p.weighted_overlap_percent?.toFixed(1)}% weighted overlap (of this member’s
                      E) · {acres(p.habitat_unknown_m2)} habitat/neighbor unknown in matching area
                    </small>
                  )}
                  <small>
                    Overlap: {p.overlap_percent?.toFixed(1)}% of this position’s matching area
                  </small>
                </button>
                <button
                  disabled={adding || !!pendingDecision}
                  onClick={() => void decide(p.id, 'shortlist')}
                >
                  Shortlist {p.id}
                </button>
                <button
                  disabled={adding || !!pendingDecision}
                  onClick={() => void decide(p.id, 'dismiss')}
                >
                  Dismiss {p.id}
                </button>
              </div>
            ))}
          </div>
          <p className="hint">
            Overlap is the fraction of this position’s matching visible area already covered by
            retained positions and earlier suggestions. Cyan shows combined coverage; violet shows
            terrain covered by two or more members; pink shows the focused member’s unique terrain.
          </p>
          {!active.suggestions.length && (
            <p className="notice">
              {active.kept.length >= count
                ? 'Your shortlist already fills this collection size. All retained positions stay included.'
                : 'No further eligible position adds matching terrain under the current criteria and spacing.'}
            </p>
          )}
          <button
            className="wide primary"
            disabled={adding || !active.suggestions.length}
            onClick={() => void add()}
          >
            {adding ? 'Adding suggestions…' : 'Add suggestions to shortlist'}
          </button>
          <small>
            Terrain coverage is provisional. Vegetation, deer presence and legal access remain
            unverified.
          </small>
        </>
      )}
    </section>
  );
}
