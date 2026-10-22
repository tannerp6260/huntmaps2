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
            disabled={!ready && !value}
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

export function PracticalPlanSettings({
  value,
  ready,
  change,
}: {
  value: RecordValue | null;
  ready: boolean;
  change: (v: RecordValue | null) => void;
}) {
  const policy = value?.policy || {};
  return (
    <details>
      <summary>Timed practical plans · experimental</summary>
      <div className="detail-body">
        <label>
          <input
            type="checkbox"
            checked={!!value}
            disabled={!ready && !value}
            onChange={(e) =>
              change(
                e.target.checked
                  ? {
                      version: 1,
                      policy: { task: "identify", leaf: "unknown" },
                      search_minutes_cap: null,
                    }
                  : null,
              )
            }
          />{" "}
          Use practical objective for AM/PM plans
        </label>
        <p className="micro">
          {ready
            ? "Ranks feasible single stops and connected pairs using actual stop time and complementary scan sectors. Combined/stay days remain established-mode-only. Source access and parking remain conditional."
            : "Installed community package required. Established planning remains available."}
        </p>
        {value && (
          <>
            <label>
              Timed search task
              <select
                aria-label="Timed search task"
                value={policy.task || "identify"}
                onChange={(e) =>
                  change({
                    ...value,
                    policy: { ...policy, task: e.target.value },
                  })
                }
              >
                <option value="spot">Spot a deer</option>
                <option value="identify">Identify a buck</option>
                <option value="assess">Assess antlers</option>
              </select>
            </label>
            <label>
              Timed leaf assumption
              <select
                aria-label="Timed leaf assumption"
                value={policy.leaf || "unknown"}
                onChange={(e) =>
                  change({
                    ...value,
                    policy: { ...policy, leaf: e.target.value },
                  })
                }
              >
                {["unknown", "on", "partial", "off"].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Timed scan cap · minutes per stop (blank uses available time)
              <input
                aria-label="Timed scan cap"
                type="number"
                min="0"
                max="720"
                value={value.search_minutes_cap ?? ""}
                onChange={(e) =>
                  change({
                    ...value,
                    search_minutes_cap:
                      e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </label>
            <p className="micro">
              Separate from static review's 30-minute budget. Whole sectors cost
              their full footprint. Additional time may search new sectors;
              repeated coverage earns no extra credit. Eye 1.7 m / target 0.8 m;
              foreground remains conditional. Candidate placement and coarse
              dense-cover exclusions are unchanged.
            </p>
          </>
        )}
      </div>
    </details>
  );
}

export function TimedResult({
  option,
  mode,
}: {
  option: RecordValue;
  mode: string;
}) {
  const p = option.schedules[mode]?.practical;
  if (!p) return null;
  return (
    <section className="selected-evidence" aria-label="Timed practical plan">
      <h3>Practical {mode.toUpperCase()} scan plan · experimental</h3>
      <p>
        {Math.round(p.relative_m2 || 0).toLocaleString()} relative-index m² ·{" "}
        {Math.round((p.supported_fraction || 0) * 100)}% habitat support ·{" "}
        {Math.round(p.unknown_m2).toLocaleString()} m² habitat unknown. These
        are provisional desktop sectors, not verified sightlines or literal
        acres searched.
      </p>
      <p>
        Selected-view overlap:{" "}
        {Math.round(p.overlap_relative_m2).toLocaleString()} relative-index m².
        Terrain coverage below remains a separate theoretical view.
      </p>
      {p.visits.map((v: RecordValue, i: number) => (
        <div key={i}>
          <h4>
            Stop {i + 1} · {option.viewpoints[i].latitude.toFixed(6)},{" "}
            {option.viewpoints[i].longitude.toFixed(6)}
          </h4>
          <p>
            {v.minutes_used.toFixed(1)} useful scan minutes of{" "}
            {v.observation_minutes.toFixed(1)} available;{" "}
            {v.unused_observation_minutes.toFixed(1)} minutes unallocated/rest.
            Adds {Math.round(v.marginal_relative_m2).toLocaleString()}{" "}
            relative-index m²; exclusive improvement{" "}
            {Math.round(v.exclusive_relative_m2).toLocaleString()}.
          </p>
          <p>
            {Object.entries(v.community_relative_m2)
              .filter(([, n]) => Number(n) > 0)
              .map(
                ([name, n]) =>
                  `${name.replaceAll("_", " ")}: ${Math.round(Number(n)).toLocaleString()}`,
              )
              .join(" · ")}
          </p>
          <details className="scan-sectors">
            <summary>
              Selected scan sectors ({v.patches.length}) · bearings & ranges
            </summary>
            <ol>
              {v.patches.map((s: RecordValue) => (
                <li key={s.id}>
                  Grid bearing {s.azimuth_start}–{s.azimuth_end}° · {s.inner_m}–
                  {s.outer_m} m · {s.minutes.toFixed(2)} min
                </li>
              ))}
            </ol>
          </details>
          <details>
            <summary>
              Foreground inspection ·{" "}
              {option.inspection?.[i]?.status || "unknown/uninspected"}
            </summary>
            <p>{option.inspection?.[i]?.source}</p>
            <p>
              Within 150 m:{" "}
              {option.inspection?.[i]?.valid_fraction == null
                ? "unknown"
                : `${Math.round(option.inspection[i].valid_fraction * 100)}%`}{" "}
              coarse-source coverage;{" "}
              {option.inspection?.[i]?.elevated_cover_fraction == null
                ? "unknown"
                : `${Math.round(option.inspection[i].elevated_cover_fraction * 100)}%`}{" "}
              of supported samples exceed the existing 35% tree / 50% shrub
              screen. This is cover evidence, not a fraction of blocked
              sightlines.
            </p>
            <ul aria-label="Coarse foreground directions">
              {v.patches
                .filter(
                  (s: RecordValue, n: number, all: RecordValue[]) =>
                    all.findIndex(
                      (p) => p.azimuth_start === s.azimuth_start,
                    ) === n,
                )
                .map((s: RecordValue) => (
                  <li key={s.azimuth_start}>
                    Grid {s.azimuth_start}–{s.azimuth_end}°:{" "}
                    {s.foreground_transects
                      ?.map(
                        (t: RecordValue) =>
                          `${t.from_m}–${t.to_m} m: ${Math.round(t.valid_fraction * 100)}% source coverage, ${t.elevated_cover_fraction == null ? "unknown" : Math.round(t.elevated_cover_fraction * 100) + "%"} above cover screen`,
                      )
                      .join("; ") || "unknown/uninspected"}
                    .
                  </li>
                ))}
            </ul>
            <p>{option.inspection?.[i]?.note}</p>
            <p>{option.inspection?.[i]?.measured_obstruction}</p>
            <p>
              No clear-opening certification or numerical score adjustment.
              Check the exact opening, trunks/understory, terrain and current
              access in the field. The map shows full scan footprints; hidden
              terrain within them remains hidden.
            </p>
          </details>
        </div>
      ))}
    </section>
  );
}
