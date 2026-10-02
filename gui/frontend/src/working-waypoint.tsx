import { useState } from 'react';
export default function WorkingWaypoint({
  point,
  original,
  onReview,
  onRestore,
  onView,
}: {
  point: any;
  original: any;
  onReview: (v: any) => Promise<void>;
  onRestore: () => Promise<void>;
  onView: () => void;
}) {
  const [name, setName] = useState(point.name),
    [notes, setNotes] = useState(point.notes),
    [status, setStatus] = useState(point.status),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false);
  const action = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      setMessage('Saved');
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="working-detail" data-working-revision={point.revision}>
      <div className="eyebrow">Updated working setup · terrain-only view</div>
      <h2>{point.name}</h2>
      <p className="coordinates">
        {point.latitude.toFixed(7)}, {point.longitude.toFixed(7)}
      </p>
      <p>
        {(point.displacement_m / 0.3048).toFixed(1)} ft from the original {point.anchor}
      </p>
      <button onClick={onView}>View from this setup</button>
      <div className="metric">
        <strong>{point.metrics.raw_km2.toFixed(3)}</strong>
        <span>km² terrain-visible target area at this waypoint</span>
      </div>
      <p>
        The shading uses the saved 10 m terrain and baseline viewing assumptions. Small stance
        changes may show the same wide-area view. Nearby foliage is inspected separately in first
        person.
      </p>
      <h3>Cover across this visible terrain</h3>
      <div className="breakdown">
        {[
          ['Tree cover under 10%', 'tree_lt10_km2'],
          ['Tree cover 10–40%', 'tree_10to40_km2'],
          ['Tree cover 40% or more', 'tree_ge40_km2'],
          ['Unknown tree cover', 'tree_unknown_km2'],
          ['Shrub cover over 30%', 'shrub_gt30_km2'],
        ].map(([label, key]) => (
          <div key={key}>
            <span>{label}</span>
            <b>{point.metrics[key].toFixed(3)} km²</b>
          </div>
        ))}
      </div>
      <p className="hint">
        Low cover does not guarantee visible deer. Access, footing and actual field sightlines need
        inspection. Original inspection scores are not recalculated for this position.
      </p>
      <label>
        Waypoint name
        <input
          aria-label="Working waypoint name"
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label>
        Decision
        <select
          aria-label="Working waypoint decision"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {['unmarked', 'keep', 'reject', 'needs inspection'].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </label>
      <label>
        Notes
        <textarea
          aria-label="Working waypoint notes"
          maxLength={10000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      <button disabled={busy} onClick={() => action(() => onReview({ name, notes, status }))}>
        Save review
      </button>
      <p role="status">{message}</p>
      <button disabled={busy} onClick={() => action(onRestore)}>
        Restore original setup
      </button>
      <details>
        <summary>Original saved analysis and source details</summary>
        <p>
          These coordinates and metrics belong to the original saved position, not the updated
          waypoint.
        </p>
        <pre>{JSON.stringify(original, null, 2)}</pre>
        <p>Current terrain calculation</p>
        <pre>{JSON.stringify(point.terrain, null, 2)}</pre>
      </details>
    </section>
  );
}
