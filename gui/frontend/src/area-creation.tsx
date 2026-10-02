import { Help } from './drawing';
export default function AreaSettings({
  name,
  radius,
  count,
  budget,
  minutes,
  setName,
  setRadius,
  setCount,
  setBudget,
  setMinutes,
}: {
  name: string;
  radius: number;
  count: number;
  budget: number;
  minutes: number;
  setName: (value: string) => void;
  setRadius: (value: number) => void;
  setCount: (value: number) => void;
  setBudget: (value: number) => void;
  setMinutes: (value: number) => void;
}) {
  return (
    <div data-tour="run-settings">
      <label>
        New run name <Help topic="name" />
        <input
          aria-label="New run name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="my-glassing-area"
        />
      </label>
      <div className="form-grid">
        <label>
          View radius <Help topic="radius" />
          <select
            aria-label="View radius"
            value={radius}
            onChange={(e) => setRadius(+e.target.value)}
          >
            {[500, 1000, 1500, 2000, 2500, 3000].map((r) => (
              <option value={r} key={r}>
                {r / 1000} km
              </option>
            ))}
          </select>
        </label>
        <label>
          Locations to evaluate <Help topic="count" />
          <input
            aria-label="Locations to evaluate"
            type="number"
            min="12"
            max="200"
            value={count}
            onChange={(e) => setCount(+e.target.value)}
          />
        </label>
        <label>
          Maximum download size (MB) <Help topic="budget" />
          <input
            aria-label="Maximum download size (MB)"
            type="number"
            min="1"
            max="1900"
            value={budget}
            onChange={(e) => setBudget(+e.target.value)}
          />
        </label>
      </div>
      <p className="hint">
        Locations to evaluate means potential glassing spots to test, not the number of best spots
        returned.
      </p>
      <details>
        <summary>How locations are chosen</summary>
        <p>
          The engine samples eligible locations across sections of your observer area, then adds
          samples from terrain resembling benches, shoulders and ridge breaks, plus general
          background locations. It keeps minimum spacing between points and calculates views and
          scores afterward.
        </p>
        <p>
          A fixed random seed makes the same inputs repeatable. More locations means more
          processing, not a guaranteed optimum. If the requested count cannot fit at the required
          spacing, the run stops with an explanation; reduce the count. Nearby refinement
          alternatives may add results beyond this initial sample.
        </p>
        <p>
          Current leading results use the inherited inspection score, not simply the largest
          terrain-visible area. Terrain shapes do not certify suitable footing, deer habitat, or
          legal access.
        </p>
      </details>
      <details className="advanced-scoring">
        <summary>Advanced scoring settings</summary>
        <label>
          Assumed inspection time <Help topic="minutes" />
          <input
            aria-label="Assumed inspection time"
            type="number"
            min="5"
            max="120"
            value={minutes}
            onChange={(e) => setMinutes(+e.target.value)}
          />
        </label>
        <p className="hint">
          An assumption for inspection scores and rankings, not a recommended stop duration.
          Terrain-visible coverage is unchanged.
        </p>
      </details>
      <details className="resource-limits">
        <summary>Processing limits and source details</summary>
        <p className="hint">
          Existing limits: 3 million grid cells, 1536 MiB analysis memory, 900 seconds per engine
          command, 800 MB outputs. Analysis acquisition does not include imagery or legal-access
          data. Online basemap tiles are separate browsing context.
        </p>
      </details>
    </div>
  );
}
