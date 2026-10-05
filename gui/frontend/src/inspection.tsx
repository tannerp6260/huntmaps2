import { yards } from './units';
import type { ProfileResult } from './types';
export function ProfileChart({ profile }: { profile: ProfileResult | null }) {
  if (!profile)
    return <p>Click the plan map to inspect a target, including ground hidden behind a ridge.</p>;
  if (profile.status === 'unavailable') return <p role="status">{profile.result}</p>;
  const points = profile.points,
    w = 600,
    h = 170,
    known = points.flatMap((p) => [p.ground_m, p.line_m]).filter((v) => v !== null),
    lo = Math.min(...known) - 1,
    hi = Math.max(...known) + 1;
  if (!known.length)
    return <p>Incomplete data: ground or endpoint height is unknown along this path.</p>;
  const x = (d: number) => 25 + (d / profile.distance_m) * (w - 40),
    y = (z: number) => h - 20 - ((z - lo) / (hi - lo)) * (h - 40);
  let paths: string[] = [],
    current = '';
  for (const p of points) {
    if (p.ground_m === null) {
      if (current) paths.push(current);
      current = '';
    } else current += (current ? ' L' : 'M') + x(p.distance_m) + ',' + y(p.ground_m);
  }
  if (current) paths.push(current);
  const first = points[0],
    last = points[points.length - 1],
    block = profile.first_obstruction,
    veg =
      profile.vegetation?.status === 'evaluated'
        ? profile.vegetation.scenarios[profile.vegetation.selected_scenario].first_intersection
        : null;
  return (
    <section className="fp-profile">
      <h3>Inspection target · {yards(profile.distance_m, 1)}</h3>
      <b>{profile.result}</b>
      <p className="hint">
        {profile.source_label}
        {profile.borderline
          ? ' · Within 5 cm of the modeled line: borderline, not an accuracy guarantee.'
          : ''}
      </p>
      <svg
        viewBox={'0 0 ' + w + ' ' + h}
        role="img"
        aria-label="Ground elevation and inspection sightline profile"
      >
        <rect width={w} height={h} fill="#eef2e8" />
        {paths.map((d, i) => (
          <path key={i} d={d} fill="none" stroke="#38634d" strokeWidth="2" />
        ))}
        {first.line_m !== null && last.line_m !== null && (
          <path
            d={`M${x(0)},${y(first.line_m)} L${x(profile.distance_m)},${y(last.line_m)}`}
            stroke="#cf7540"
            strokeWidth="2"
            strokeDasharray="5 3"
          />
        )}
        {block && <circle cx={x(block.distance_m)} cy={y(block.ground_m)} r="5" fill="#bd3643" />}
        {veg && <circle cx={x(veg.distance_m)} cy={y(veg.line_m)} r="5" fill="#8052ad" />}
        <text x="25" y={h - 3} fontSize="11">
          Observer
        </text>
        <text x={w - 75} y={h - 3} fontSize="11">
          Target
        </text>
      </svg>
      <small>
        Green: modeled ground. Orange: inspection line. Purple: selected inferred-vegetation
        intersection. Gaps: unknown ground.{' '}
        {block ? 'First modeled obstruction at ' + yards(block.distance_m, 1) + '.' : ''}{' '}
        {profile.warning}
      </small>
    </section>
  );
}
export function VegetationResult({
  profile,
  enabled,
}: {
  profile: ProfileResult | null;
  enabled: boolean;
}) {
  const v = profile?.vegetation;
  if (!v) return null;
  return (
    <section className="fp-vegetation">
      <h3>Experimental vegetation screen</h3>
      {!enabled && <p>Foliage view is off; screening assumptions are still listed below.</p>}
      {v.status === 'unavailable' ? (
        <p>{v.reason}</p>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Assumption</th>
                <th>Inspection line</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(v.scenarios).map(([name, r]) => (
                <tr key={name}>
                  <td>{name === v.selected_scenario ? <b>{name}</b> : name}</td>
                  <td>
                    {r.result}
                    {r.first_intersection
                      ? ' · first at ' + yards(r.first_intersection.distance_m, 1)
                      : ''}
                    {r.observer_inside ? ' · observer inside modeled foliage' : ''}
                    {r.target_inside ? ' · target inside modeled foliage' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            Nearby screening: {yards(v.evaluated_radius_m)} ·{' '}
            {v.included_cell_count.toLocaleString()} supported cells.{' '}
            {v.farther_vegetation_unevaluated
              ? 'Target extends beyond nearby range; farther vegetation is unevaluated.'
              : 'Vegetation outside this range is unevaluated.'}
          </p>
          {v.unknown_ground && <p>Ground has missing intervals; screening is incomplete.</p>}
          <p>{v.warning}</p>
        </>
      )}
    </section>
  );
}
