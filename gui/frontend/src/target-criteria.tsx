import { Help } from './drawing';
export type TargetCriteria = {
  version: 1;
  elevation_m: number[] | null;
  slope_deg: number[] | null;
  aspects: string[];
  tree_percent: number[] | null;
  shrub_percent: number[] | null;
};
export const defaultCriteria = (): TargetCriteria => ({
  version: 1,
  elevation_m: null,
  slope_deg: null,
  aspects: [],
  tree_percent: null,
  shrub_percent: null,
});
export function validCriteria(v: TargetCriteria) {
  return ['elevation_m', 'slope_deg', 'tree_percent', 'shrub_percent'].every((k) => {
    const a = v[k as keyof TargetCriteria] as number[] | null;
    return (
      a === null ||
      (a.length === 2 &&
        a.every(Number.isFinite) &&
        a[0] <= a[1] &&
        (k === 'elevation_m' || (a[0] >= 0 && a[1] <= (k === 'slope_deg' ? 90 : 100))))
    );
  });
}
export default function TerrainCriteria({
  value,
  onChange,
}: {
  value: TargetCriteria;
  onChange: (v: TargetCriteria) => void;
}) {
  return (
    <section className="target-criteria">
      <h3>
        Terrain I want to see <Help topic="targets" />
      </h3>
      <p className="hint">
        Recommend spots with the most visible terrain matching all enabled criteria. Leave a
        criterion off to include all values.
      </p>
      {(
        [
          ['elevation_m', 'Elevation range (feet)', 0, 14000, 0.3048],
          ['slope_deg', 'Terrain slope range (degrees)', 0, 90, 1],
          ['tree_percent', 'Tree cover range (%)', 0, 100, 1],
          ['shrub_percent', 'Shrub cover range (%)', 0, 100, 1],
        ] as const
      ).map(([key, label, low, high, scale]) => (
        <div key={key}>
          <label className="source-choice">
            <input
              type="checkbox"
              aria-label={label}
              checked={value[key] !== null}
              onChange={(e) =>
                onChange({ ...value, [key]: e.target.checked ? [low * scale, high * scale] : null })
              }
            />
            {label}
          </label>
          {value[key] && (
            <div className="form-grid">
              {['Minimum', 'Maximum'].map((side, i) => (
                <label key={side}>
                  {side}
                  <input
                    aria-label={`${side} ${label}`}
                    type="number"
                    value={
                      Number.isFinite(value[key]![i]) ? +(value[key]![i] / scale).toFixed(5) : ''
                    }
                    onChange={(e) => {
                      const a = [...value[key]!];
                      a[i] = e.target.value === '' ? NaN : +e.target.value * scale;
                      onChange({ ...value, [key]: a });
                    }}
                  />
                </label>
              ))}
            </div>
          )}
        </div>
      ))}
      <p>
        Visible terrain facing direction <Help topic="targets" />
      </p>
      <div className="form-grid">
        {['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'].map((a) => (
          <label className="source-choice" key={a}>
            <input
              type="checkbox"
              aria-label={`Visible terrain faces ${a}`}
              checked={value.aspects.includes(a)}
              onChange={(e) =>
                onChange({
                  ...value,
                  aspects: e.target.checked
                    ? [...value.aspects, a]
                    : value.aspects.filter((x) => x !== a),
                })
              }
            />
            {a}
          </label>
        ))}
      </div>
      <p className="hint">
        No directions selected means any direction. Missing required data does not count as a match.
        This filters the terrain you view, not the route to reach your spot.
      </p>
    </section>
  );
}
export function observerAreaKm2(geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null) {
  if (!geometry) return null;
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  const ring = (points: number[][]) => {
    const latitude = ((points.reduce((n, p) => n + p[1], 0) / points.length) * Math.PI) / 180;
    let sum = 0;
    for (let i = 0; i < points.length; i++) {
      const a = points[i],
        b = points[(i + 1) % points.length];
      sum += a[0] * b[1] - b[0] * a[1];
    }
    return (Math.abs(sum) * 0.5 * ((Math.PI / 180) * 6371008.8) ** 2 * Math.cos(latitude)) / 1e6;
  };
  return polygons.reduce(
    (sum, rings) => sum + ring(rings[0]) - rings.slice(1).reduce((n, r) => n + ring(r), 0),
    0,
  );
}
