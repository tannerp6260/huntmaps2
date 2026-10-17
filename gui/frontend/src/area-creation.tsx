import { area, yards, KM2_PER_MI2 } from './units';
import DistancePresets from './distance-presets';
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
      <p className="hint">Find viewpoints with the most visible terrain matching your criteria.</p>
      <label>
        Area name <Help topic="name" />
        <input
          aria-label="New run name"
          autoComplete="off"
          name="terrain-run-identifier"
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
        <DistancePresets label="View radius" value={radius} onChange={setRadius} />
      </label>
      <label>
        Locations to test <Help topic="count" />
        <DecimalField
          aria-label="Locations to test"
          value={count}
          onChange={setCount}
          min={12}
          max={5000}
          integer
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
        <DecimalField
          aria-label="Top spots to recommend"
          value={recommendationCount}
          onChange={setRecommendationCount}
          min={1}
          max={Math.min(200, count)}
          integer
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
          <DecimalField
            aria-label="Preferred tree cover below"
            value={treeThreshold}
            onChange={setTreeThreshold}
            min={0}
            max={100}
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
      </details>
    </div>
  );
}
