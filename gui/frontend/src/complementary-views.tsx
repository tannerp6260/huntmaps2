import { useEffect, useRef, useState } from 'react';
import { area } from './units';
import type { Workflow } from './workflow';
export type Contribution = {
  id: string;
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
  initial_km2: number;
  separation_m: number;
};
export default function ComplementaryViews({
  run,
  selected,
  profile,
  signature,
  paused,
  onResult,
  onSelect,
  onAdded,
  api,
}: {
  run: string;
  selected: string;
  profile: string;
  signature: string;
  paused: boolean;
  onResult: (result: Collection | null, signature: string) => void;
  onSelect: (id: string) => void;
  onAdded: (workflow: Workflow) => void;
  api: (path: string, options?: RequestInit) => Promise<any>;
}) {
  const [count, setCount] = useState(5);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{ value: Collection; signature: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
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
      body: JSON.stringify({ count, profile }),
      signal: controller.signal,
    })
      .then((value: Collection) => {
        if (
          !alive ||
          currentSignature.current !== signature ||
          value.run_id !== run ||
          value.profile !== profile ||
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
  }, [run, profile, signature, count, retry, paused]);
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
          disabled={adding}
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
      {paused && <p role="status">Coverage suggestions resume when the current job finishes.</p>}
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button onClick={() => setRetry((n) => n + 1)}>Retry collection</button>
        </div>
      )}
      {active && (
        <>
          <div className="collection-total" role="status">
            <b>Combined matching terrain: {area(active.combined_km2)}</b>
            <small>
              Counted once across {active.kept.length} retained + {active.suggestions.length}{' '}
              suggested positions.
            </small>
          </div>
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
                  {p.total_km2 === null
                    ? 'Contribution unknown'
                    : area(p.total_km2) + ' total matching terrain'}
                </p>
              ))}
            </details>
          )}
          <div className="collection-suggestions">
            {active.suggestions.map((p) => (
              <button
                className="collection-suggestion"
                key={p.id}
                onClick={() => onSelect(p.id)}
                aria-label={'Preview contribution ' + p.id}
                aria-pressed={selected === p.id}
              >
                <b>{p.id}</b>
                <span>Total matching: {area(p.total_km2)}</span>
                <strong>Additional: {area(p.additional_km2)}</strong>
                <small>
                  Overlap: {p.overlap_percent?.toFixed(1)}% of this position’s matching area
                </small>
              </button>
            ))}
          </div>
          <p className="hint">
            Overlap is the fraction of this position’s matching visible area already covered by
            retained positions and earlier suggestions. Blue shows the combined collection; pink
            shows the selected suggestion’s additional contribution at its selection step.
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
