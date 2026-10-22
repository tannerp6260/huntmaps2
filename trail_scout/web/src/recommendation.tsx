import React from "react";
import { RecordValue, miles, feet, clock } from "./api";

const periods: Record<string, string> = {
  am: "Morning",
  pm: "Evening",
  combined: "AM + PM trips",
  stay: "Stay all day",
};

// Presentation only: backend recommendations, feasibility and order are authoritative.
export function Recommendation({
  result,
  option,
  mode,
  stale,
  pending,
  onMode,
  onSelect,
  onInspect,
  onSave,
}: {
  result: RecordValue;
  option: RecordValue | null;
  mode: string;
  stale: boolean;
  pending: boolean;
  onMode: (mode: string) => void;
  onSelect: (id: string) => void;
  onInspect: (tab: string) => void;
  onSave: () => void;
}) {
  const schedule = option?.schedules[mode];
  const movement = schedule?.movement || option?.movement;
  const remaining =
    mode === "combined" && movement
      ? {
          usable_distance_m:
            result.settings.profile.max_miles *
              1609.344 *
              (1 - result.settings.profile.reserve_fraction) -
            movement.distance_m,
          usable_ascent_m:
            result.settings.profile.max_gain_ft *
              0.3048 *
              (1 - result.settings.profile.reserve_fraction) -
            movement.ascent_m,
          held_distance_m: option?.remaining.held_distance_m,
          held_ascent_m: option?.remaining.held_ascent_m,
        }
      : option?.remaining;
  const recommended = result.recommended[mode];
  const isRecommended = !!option && recommended === option.id;
  const seen = new Set<string>(
    option
      ? [
          option.viewpoints
            .map((p: RecordValue) => p.id)
            .sort()
            .join("|"),
        ]
      : [],
  );
  const alternatives = result.options
    .filter((o: RecordValue) => {
      const key = o.viewpoints
        .map((p: RecordValue) => p.id)
        .sort()
        .join("|");
      if (seen.has(key) || !o.schedules[mode]?.feasible) return false;
      seen.add(key);
      return true;
    })
    .slice(0, 2);
  const returned = schedule?.events
    .filter((e: RecordValue) => e.kind === "return")
    .at(-1);
  const observationMinutes = schedule?.events
    .filter((e: RecordValue) => e.kind === "observe")
    .reduce((sum: number, e: RecordValue) => sum + e.minutes, 0);
  return (
    <section
      className="recommendation"
      aria-labelledby="recommendation-title"
      data-option-id={option?.id || ""}
      data-mode={mode}
    >
      <div className="recommendation-heading">
        <div>
          <div className="eyebrow">
            {result.practical_plan
              ? "TIMED PRACTICAL PLAN · EXPERIMENTAL"
              : "ESTABLISHED PLANNING"}
          </div>
          <h3 id="recommendation-title">
            {isRecommended
              ? "Recommended"
              : option
                ? "Selected alternative"
                : "No preview selected"}
            {option &&
              ` · ${option.viewpoints.length === 1 ? "one glassing stop" : `${option.viewpoints.length} glassing stops`}`}
          </h3>
        </div>
        <label>
          Plan period
          <select
            aria-label="Plan period"
            value={mode}
            onChange={(e) => onMode(e.target.value)}
          >
            {Object.entries(periods).map(([value, label]) => (
              <option
                key={value}
                value={value}
                disabled={
                  !!result.practical_plan &&
                  ["combined", "stay"].includes(value)
                }
              >
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="recommendation-context">
        {result.start.label} · {result.settings.date} ·{" "}
        {result.settings.profile.label}
      </p>
      {stale && (
        <p className="recommendation-warning" role="status">
          Previous calculation. Inputs changed; recalculate before saving. These
          values use the previous inputs.
        </p>
      )}
      {pending && (
        <p className="recommendation-warning" role="status">
          Calculation in progress. This is the previous preview; wait for the
          new result before saving.
        </p>
      )}
      {!recommended && (
        <p className="recommendation-warning">
          No recommendation fits {periods[mode].toLowerCase()}. Review the
          schedule or edit inputs and recalculate; limits have not been relaxed.
        </p>
      )}
      {option && (
        <>
          <dl className="recommendation-facts">
            <div>
              <dt>Complete walk, including return</dt>
              <dd>
                {miles(movement.distance_m)} mi · ↑ {feet(movement.ascent_m)} ft
              </dd>
            </div>
            <div>
              <dt>Conservative movement time</dt>
              <dd>
                {movement.hours_low.toFixed(1)}–{movement.hours_high.toFixed(1)}{" "}
                h
              </dd>
            </div>
            <div>
              <dt>Scheduled observation</dt>
              <dd>
                {schedule?.feasible
                  ? `${Math.round(observationMinutes)} min`
                  : "Does not fit this period"}
              </dd>
            </div>
            <div>
              <dt>Scheduled return to entry</dt>
              <dd>
                {schedule?.feasible && returned
                  ? clock(returned.arrival)
                  : "Unavailable"}
              </dd>
            </div>
          </dl>
          <p className="recommendation-budget">
            After {mode === "combined" ? "both returns" : "return"}:{" "}
            {miles(remaining.usable_distance_m)} mi /{" "}
            {feet(remaining.usable_ascent_m)} ft usable effort left;{" "}
            {miles(remaining.held_distance_m)} mi /{" "}
            {feet(remaining.held_ascent_m)} ft held in reserve.
          </p>
          <p className="recommendation-caveat">
            {result.settings.explore_unknown
              ? "Unknown foot access scenario. "
              : "Provisional desktop plan. "}
            Driving, parking, current foot rights and exact sightlines require
            review.
          </p>
          <div className="recommendation-actions">
            <button onClick={() => onInspect("route")}>
              Inspect route & sightlines
            </button>
            <button onClick={() => onInspect("schedule")}>
              Review schedule
            </button>
            <button onClick={onSave}>Name, save & export</button>
            {!isRecommended && recommended && (
              <button onClick={() => onSelect(recommended)}>
                Back to recommendation
              </button>
            )}
          </div>
        </>
      )}
      {alternatives.length > 0 && (
        <details className="recommendation-alternatives">
          <summary>Compare a different option</summary>
          <p>
            Different viewpoint sets, in backend preview order. Full retained
            previews and evidence are below the map.
          </p>
          <div className="recommendation-actions">
            {alternatives.map((o: RecordValue) => (
              <button key={o.id} onClick={() => onSelect(o.id)}>
                {o.viewpoints.length}{" "}
                {o.viewpoints.length === 1 ? "stop" : "stops"} ·{" "}
                {miles((o.schedules[mode]?.movement || o.movement).distance_m)}{" "}
                mi · ↑{" "}
                {feet((o.schedules[mode]?.movement || o.movement).ascent_m)} ft
                {o.id === recommended ? " · Recommended" : ""}
              </button>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
