import { Help } from './drawing';
export default function AreaSettings({
  name,
  radius,
  count,
  minutes,
  setName,
  setRadius,
  setCount,
}: {
  name: string;
  radius: number;
  count: number;
  minutes: number;
  setName: (value: string) => void;
  setRadius: (value: number) => void;
  setCount: (value: number) => void;
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
      <p className="hint">
        View radius is the farthest terrain evaluated from each trial location.
      </p>
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
      <details>
        <summary>More options · trial locations</summary>
        <div className="form-grid">
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
            All setups default to terrain-visible area. Original engine ranking remains available.
            Terrain shapes do not certify suitable footing, deer habitat, or legal access.
          </p>
        </details>
        <details>
          <summary>Calculation details</summary>
          <p>
            Saved inspection assumption: {minutes} minutes per setup. This affects inherited
            indices, not terrain-visible area.
          </p>
        </details>
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
