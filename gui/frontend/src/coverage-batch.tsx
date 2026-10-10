import { useEffect, useRef, useState } from 'react';
import type { Map } from 'maplibre-gl';
import { prepareCoverage, type CoveragePoint, type Preparation } from './coverage-cache';
export default function CoverageBatch({
  map,
  run,
  points,
  selected,
  working,
  filter,
  wholeArea,
  paused,
}: {
  map: Map;
  run: string;
  points: CoveragePoint[];
  selected: string;
  working: Record<string, { revision: string }>;
  filter?: string;
  wholeArea: number[][];
  paused: boolean;
}) {
  const [count, setCount] = useState(10);
  const [terrainView, setTerrainView] = useState(map.getPitch() > 0);
  const [state, setState] = useState<Preparation | null>(null);
  const cancel = useRef<(() => void) | null>(null);
  const batch = useRef<CoveragePoint[]>([]);
  const finished = useRef(new Set<string>());
  const pausedRef = useRef(paused);
  pausedRef.current = paused || terrainView;
  useEffect(() => {
    const moved = () => setTerrainView(map.getPitch() > 0);
    map.on('moveend', moved);
    return () => {
      map.off('moveend', moved);
    };
  }, [map]);
  const generation = useRef(0);
  const signature = JSON.stringify([
    run,
    filter,
    points.map((p) => [p.id, p.longitude, p.latitude, working[p.id]?.revision]),
  ]);
  useEffect(() => {
    generation.current++;
    cancel.current?.();
    cancel.current = null;
    finished.current.clear();
    batch.current = [];
    setState(null);
    return () => {
      generation.current++;
      cancel.current?.();
      cancel.current = null;
    };
  }, [signature]);
  function start(retry = false) {
    const token = ++generation.current;
    cancel.current?.();
    if (!retry) {
      const index = Math.max(
        0,
        points.findIndex((p) => p.id === selected),
      );
      batch.current = points.slice(index, index + count);
      finished.current.clear();
    }
    cancel.current = prepareCoverage(
      map,
      run,
      batch.current,
      working,
      filter,
      (v) => {
        if (token === generation.current) setState(v);
      },
      wholeArea,
      () => pausedRef.current,
      finished.current,
    );
  }
  const active = state?.phase === 'preparing' || state?.phase === 'paused';
  return (
    <section className="coverage-batch" aria-label="Prepare coverage batch">
      <div className="row">
        <label>
          Prepare next{' '}
          <select
            aria-label="Coverage batch size"
            value={count}
            disabled={active}
            onChange={(e) => setCount(+e.target.value)}
          >
            {[5, 10, 20].map((n) => (
              <option key={n} value={n}>
                {n} setups
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={active || paused || terrainView || !points.length}
          onClick={() => start()}
        >
          Prepare coverage
        </button>
      </div>
      <small>
        Includes this setup, then follows the displayed order. Review one view at a time.
      </small>
      {state && (
        <div
          className="coverage-preparation"
          role="status"
          aria-live="polite"
          data-phase={state.phase}
        >
          <b>
            {state.phase === 'ready'
              ? 'Coverage prepared'
              : state.phase === 'error'
                ? 'Preparation stopped'
                : state.phase === 'cancelled'
                  ? 'Preparation cancelled'
                  : state.phase === 'paused'
                    ? 'Preparation paused'
                    : 'Preparing coverage'}{' '}
            · {state.completed}/{state.total} setups
          </b>
          {active && (
            <progress
              aria-label="Coverage batch progress"
              value={state.tiles}
              max={state.totalTiles || 1}
            />
          )}
          <small>
            {state.tiles}/{state.totalTiles} tiles
            {active && state.current ? ' · ' + state.current : ''}
          </small>
          {state.message && <p>{state.message}</p>}
          {active ? (
            <button
              onClick={() => {
                cancel.current?.();
                cancel.current = null;
              }}
            >
              Cancel preparation
            </button>
          ) : (
            state.phase !== 'ready' && (
              <button onClick={() => start(true)} disabled={paused}>
                Resume preparation
              </button>
            )
          )}
          {state.phase === 'ready' && (
            <small>
              Prepared for normal setup views. Zooming or cache eviction can require more loading.
            </small>
          )}
        </div>
      )}
      {paused && <small>Preparation is available when current jobs finish.</small>}
      {terrainView && <small>Switch to 2D to prepare normal setup views.</small>}
    </section>
  );
}
