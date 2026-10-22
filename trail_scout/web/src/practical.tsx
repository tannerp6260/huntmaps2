import { RecordValue } from "./api";

export function PracticalSettings({
  value,
  ready,
  change,
}: {
  value: RecordValue | null;
  ready: boolean;
  change: (value: RecordValue | null) => void;
}) {
  return (
    <details>
      <summary>Community & scan review · experimental</summary>
      <div className="detail-body">
        <label>
          <input
            type="checkbox"
            checked={!!value}
            disabled={!ready}
            onChange={(e) =>
              change(
                e.target.checked
                  ? { task: "identify", leaf: "unknown", scan_minutes: 30 }
                  : null,
              )
            }
          />{" "}
          Add practical static comparison
        </label>
        <p className="micro">
          {ready
            ? "LANDFIRE 2025 community data installed locally. Route previews keep the established objective; this adds a separate comparison of useful search sectors."
            : "Community package unavailable. Prepare it with .venv/bin/python -m practical_glassing prepare. Existing scouting remains available."}
        </p>
        {value && (
          <>
            <label>
              Search task
              <select
                aria-label="Search task"
                value={value.task}
                onChange={(e) => change({ ...value, task: e.target.value })}
              >
                <option value="spot">Spot a deer</option>
                <option value="identify">Identify a buck</option>
                <option value="assess">Assess antlers</option>
              </select>
            </label>
            <label>
              Assumed deciduous leaf state
              <select
                aria-label="Assumed deciduous leaf state"
                value={value.leaf}
                onChange={(e) => change({ ...value, leaf: e.target.value })}
              >
                <option value="unknown">Unknown · conservative</option>
                <option value="on">Leaf on</option>
                <option value="partial">Partial leaf loss</option>
                <option value="off">Leaf off</option>
              </select>
            </label>
            <label>
              Useful scan budget · minutes per point
              <input
                type="number"
                min="0"
                max="120"
                value={value.scan_minutes}
                onChange={(e) =>
                  change({ ...value, scan_minutes: Number(e.target.value) })
                }
              />
            </label>
            <p className="micro">
              Task ranges and scan times are planning assumptions. Leaf loss
              leaves branches, mixed conifers and understory. Geometry uses the
              preserved 1.7 m eye / 0.8 m target assumptions; foreground
              clearance needs inspection.
            </p>
          </>
        )}
      </div>
    </details>
  );
}

export function PracticalResult({ review }: { review: RecordValue }) {
  const collection = review.collections.combined;
  const rows = Object.fromEntries(
    review.rows.map((p: RecordValue) => [p.id, p]),
  );
  return (
    <section className="selected-evidence" aria-label="Practical static review">
      <h3>Community & practical scan comparison</h3>
      <p>{review.route_scope}</p>
      <p>
        {collection.ids.length} complementary static locations ·{" "}
        {collection.relative_m2 === null
          ? "Unknown"
          : Math.round(collection.relative_m2).toLocaleString()}{" "}
        relative-index m². Foreground and intervening vegetation are unverified;
        these units are not literal acres searched.
      </p>
      <p className="micro">
        This review uses positions that passed the existing observer and
        approach screens. A coarse dense-cover screen can remove small openings
        before ranking; inspect exact pinned positions in the main workflow.
      </p>
      <ol>
        {collection.ids.map((id: string) => (
          <li key={id}>
            {id.slice(0, 8)} · {rows[id].latitude.toFixed(6)},{" "}
            {rows[id].longitude.toFixed(6)} ·{" "}
            {Math.round((rows[id].support_fraction ?? 0) * 100)}% habitat
            support · {rows[id].scan.minutes_used} assumed scan minutes
          </li>
        ))}
      </ol>
      <a href={review.report_url} target="_blank" rel="noreferrer">
        Open five-model maps, distance bands, scan sectors & exports
      </a>
    </section>
  );
}
