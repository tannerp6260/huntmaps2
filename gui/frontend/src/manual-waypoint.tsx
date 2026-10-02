import { useState } from 'react';
export default function ManualWaypoint({
  point,
  onSave,
  onDelete,
  onView,
}: {
  point: any;
  onSave: (v: any) => Promise<void>;
  onDelete: () => Promise<void>;
  onView: () => void;
}) {
  const [name, setName] = useState(point.name),
    [notes, setNotes] = useState(point.notes),
    [status, setStatus] = useState(point.status),
    [message, setMessage] = useState(''),
    [busy, setBusy] = useState(false),
    [deleting, setDeleting] = useState(false);
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
    <section className="manual-detail">
      <div className="eyebrow">Provisional manual observer</div>
      <h2>{point.name}</h2>
      <p className="coordinates">
        {point.latitude.toFixed(7)}, {point.longitude.toFixed(7)}
      </p>
      <p>
        {(point.displacement_m / 0.3048).toFixed(1)} ft from {point.anchor} · saved separately
      </p>
      <div className="notice">
        No full-area analysis calculated. Saved setup scores and masks do not describe this
        location. Legal access, footing and field sightlines remain unverified.
      </div>
      <button onClick={onView}>View from this waypoint</button>
      <label>
        Waypoint name
        <input
          maxLength={100}
          aria-label="Saved waypoint name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label>
        Decision
        <select
          aria-label="Waypoint decision"
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
          maxLength={10000}
          aria-label="Saved waypoint notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </label>
      <button disabled={busy} onClick={() => action(() => onSave({ name, notes, status }))}>
        Save waypoint review
      </button>
      <p role="status">{message}</p>
      <details>
        <summary>Waypoint source details</summary>
        <pre>{JSON.stringify(point, null, 2)}</pre>
      </details>
      {deleting ? (
        <div>
          <p>Delete this provisional waypoint: {point.name}?</p>
          <button disabled={busy} onClick={() => action(onDelete)}>
            Delete this waypoint
          </button>
          <button onClick={() => setDeleting(false)}>Keep waypoint</button>
        </div>
      ) : (
        <button onClick={() => setDeleting(true)}>Remove waypoint…</button>
      )}
    </section>
  );
}
