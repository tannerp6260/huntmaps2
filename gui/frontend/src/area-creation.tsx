import { area, yards, KM2_PER_MI2 } from './units';
import DecimalField from './decimal-field';
import { Help } from './drawing';
import TerrainCriteria, { type TargetCriteria } from './target-criteria';
export default function AreaSettings({
  onValidity,
  targets,
  setTargets,
  avoidDense,
  setAvoidDense,
  areaKm2,
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
  onValidity: (v: boolean) => void;
  targets: TargetCriteria;
  setTargets: (v: TargetCriteria) => void;
  avoidDense: boolean;
  setAvoidDense: (v: boolean) => void;
  areaKm2: number | null;
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
          Locations to test controls how many standing points we calculate. Top spots to recommend
          controls how many suggestions you see first, ranked by visible terrain matching your
          criteria.
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
              {yards(r)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Locations to test <Help topic="count" />
        <input
          aria-label="Locations to test"
          type="number"
          min="12"
          max="5000"
          value={count}
          onChange={(e) => setCount(+e.target.value)}
        />
      </label>
      {areaKm2 != null && areaKm2 > 0 && (
        <p className="hint" data-testid="search-density">
          Approx. {area(areaKm2)} observer area · {((count / areaKm2) * KM2_PER_MI2).toFixed(0)}{' '}
          locations/mi². Some evaluations refine promising spots; restrictions may leave fewer
          candidates.
        </p>
      )}
      <label>
        Top spots to recommend <Help topic="recommendations" />
        <input
          aria-label="Top spots to recommend"
          type="number"
          min="1"
          max={Math.min(200, count)}
          value={recommendationCount}
          onChange={(e) => setRecommendationCount(+e.target.value)}
        />
      </label>
      <p className="hint">
        Search broadly, then check nearby alternatives around the best matching viewpoints. All
        evaluated locations remain available.
      </p>
      <TerrainCriteria value={targets} onChange={setTargets} />
      <label className="source-choice">
        <input
          aria-label="Avoid standing in dense vegetation"
          type="checkbox"
          checked={avoidDense}
          onChange={(e) => setAvoidDense(e.target.checked)}
        />
        Avoid standing in dense vegetation <Help topic="clearing" />
      </label>
      <details>
        <summary>Advanced settings</summary>
        <label>
          Spacing between suggestions (yards) <Help topic="separation" />
          <DecimalField
            aria-label="Recommendation separation"
            value={separation}
            scale={0.9144}
            onChange={setSeparation}
            onValidity={onValidity}
          />
        </label>
        <label>
          Check surrounding vegetation within <Help topic="nearby" />
          <select
            aria-label="Nearby cover radius"
            value={nearbyRadius}
            onChange={(e) => setNearbyRadius(+e.target.value)}
          >
            {[10, 30, 60, 120].map((r) => (
              <option value={r} key={r}>
                {yards(r)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Require surrounding tree cover below (%) <Help topic="trees" />
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
          Locations to test means potential glassing spots to calculate, not the number of best
          spots returned.
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
            processing, not a guaranteed optimum. Broad spacing starts at 164 yd and decreases for
            smaller areas, down to the analysis grid resolution. Exhausted eligible cells produce
            fewer evaluations with an explanation. Nearby refinement uses up to 20% of the search
            budget; broad sampling uses 80%. A limited area may leave some refinement budget unused.
          </p>
          <p>
            Recommendations rank by matching visible terrain area. The optional nearby vegetation
            restriction applies to where you stand, not what you view. All evaluated setups can
            still be ordered by terrain-visible area. Original engine ranking remains available.
            Terrain shapes do not certify suitable footing, deer habitat, or legal access.
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
