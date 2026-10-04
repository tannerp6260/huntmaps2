import { Help } from './drawing';
export default function AreaSettings({
  name,
  radius,
  count,
  minutes,
  setName,
  setRadius,
  setCount,
  recommendationCount,
  setRecommendationCount,
  nearbyRadius,
  setNearbyRadius,
  separation,
  setSeparation,
  treeThreshold,
  setTreeThreshold,
}: {
  name: string;
  radius: number;
  count: number;
  minutes: number;
  setName: (value: string) => void;
  setRadius: (value: number) => void;
  setCount: (value: number) => void;
  recommendationCount: number;
  setRecommendationCount: (value: number) => void;
  nearbyRadius: number;
  setNearbyRadius: (value: number) => void;
  separation: number;
  setSeparation: (value: number) => void;
  treeThreshold: number;
  setTreeThreshold: (value: number) => void;
}) {
  return (
    <div data-tour="run-settings">
      <div className="notice">
        <strong>How we find places to glass</strong>
        <p>
          We test possible places to stand, check how much terrain each can see, and recommend a
          spread of promising spots. You choose which to inspect.
        </p>
        <p>
          Search thoroughness controls how many places we test. Spots to recommend controls how many
          suggestions you see first. We favor more open surroundings, but trees and branches still
          need inspection.
        </p>
      </div>
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
      <label>
        Search thoroughness <Help topic="effort" />
        <select
          aria-label="Search effort"
          value={[150, 600, 2000].includes(count) ? count : 'custom'}
          onChange={(e) => {
            if (e.target.value !== 'custom') setCount(+e.target.value);
            else setCount(300);
          }}
        >
          <option value="150">Quick · up to 150 locations</option>
          <option value="600">Thorough · up to 600 locations</option>
          <option value="2000">Deep · up to 2,000 locations</option>
          <option value="custom">Custom budget</option>
        </select>
      </label>
      <label>
        Spots to recommend <Help topic="recommendations" />
        <input
          aria-label="Setups recommended"
          type="number"
          min="1"
          max={Math.min(200, count)}
          value={recommendationCount}
          onChange={(e) => setRecommendationCount(+e.target.value)}
        />
      </label>
      <p className="hint">
        Search broadly, then inspect nearby alternatives around leading locations. Prefer low mapped
        tree cover nearby, then greater terrain-visible area. All evaluated locations remain
        available.
      </p>
      <details>
        <summary>Advanced settings</summary>
        <label>
          Spacing between suggestions (metres) <Help topic="separation" />
          <input
            aria-label="Recommendation separation"
            type="text"
            inputMode="decimal"
            value={separation}
            onChange={(e) => setSeparation(+e.target.value)}
          />
        </label>
        <div className="form-grid">
          <label>
            Locations to evaluate <Help topic="count" />
            <input
              aria-label="Locations to evaluate"
              type="number"
              min="12"
              max="5000"
              value={count}
              onChange={(e) => setCount(+e.target.value)}
            />
          </label>
        </div>
        <label>
          Check surrounding vegetation within <Help topic="nearby" />
          <select
            aria-label="Nearby cover radius"
            value={nearbyRadius}
            onChange={(e) => setNearbyRadius(+e.target.value)}
          >
            {[10, 30, 60, 120].map((r) => (
              <option value={r} key={r}>
                {r} metres
              </option>
            ))}
          </select>
        </label>
        <label>
          Prefer surrounding tree cover below (%) <Help topic="trees" />
          <input
            aria-label="Preferred tree cover below"
            type="number"
            min="0"
            max="100"
            value={treeThreshold}
            onChange={(e) => setTreeThreshold(+e.target.value)}
          />
        </label>
        <p className="hint">
          At least 80% of the nearby neighborhood must have known tree cover to qualify. Coarse
          cover cannot locate individual trees or verify a small clearing. Shrubs and ground-level
          branches still require inspection.
        </p>
        <p className="hint">
          Locations to evaluate means potential glassing spots to test, not the number of best spots
          returned.
        </p>
        <details>
          <summary>How this works</summary>
          <p>
            The engine samples eligible locations across sections of your observer area, then adds
            samples from terrain resembling benches, shoulders and ridge breaks, plus general
            background locations. It keeps minimum spacing between points and calculates views and
            scores afterward.
          </p>
          <p>
            A fixed random seed makes the same inputs repeatable. More locations means more
            processing, not a guaranteed optimum. Broad spacing starts at 150 m and decreases for
            smaller areas, down to the analysis grid resolution. Exhausted eligible cells produce
            fewer evaluations with an explanation. Nearby refinement uses up to 20% of the search
            budget; broad sampling uses 80%. A limited area may leave some refinement budget unused.
          </p>
          <p>
            Recommendations prefer nearby low mapped tree cover, then terrain-visible area. All
            evaluated setups can still be ordered by terrain-visible area. Original engine ranking
            remains available. Terrain shapes do not certify suitable footing, deer habitat, or
            legal access.
          </p>
        </details>
        <details>
          <summary>Calculation details</summary>
          <p>
            Historical calculation input: {minutes} minutes allocated to inspecting a view. This is
            not a suggested visit duration. It affects inherited indices, not terrain-visible area.
          </p>
        </details>
      </details>
      <details className="resource-limits">
        <summary>Technical details</summary>
        <p className="hint">
          Existing limits: 3 million grid cells, 1536 MiB analysis memory, 900 seconds per engine
          batch, 800 MB outputs. Analysis acquisition does not include imagery or legal-access data.
          Online basemap tiles are separate browsing context.
        </p>
      </details>
    </div>
  );
}
