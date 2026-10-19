import { inputSignature } from './approach-inputs';
import { useEffect, useRef, useState } from 'react';
export type HabitatSettings = {
  version: number;
  preset: string;
  local_radius_m: number;
  landscape_radius_m: number;
  weights: number[];
  tree_penalty: number;
  shrub_penalty: number;
  habitat_threshold: number;
  glassability_threshold: number;
};
export const fallHabitat = (): HabitatSettings => ({
  version: 1,
  preset: 'fall-mixed',
  local_radius_m: 90,
  landscape_radius_m: 270,
  weights: [0.1, 0.45, 0.25, 0.2],
  tree_penalty: 0.9,
  shrub_penalty: 0.65,
  habitat_threshold: 0.45,
  glassability_threshold: 0.45,
});
export const canonicalHabitat = (value: HabitatSettings | null) => {
  if (!value) return null;
  const total = value.weights.reduce((a, b) => a + b, 0);
  return { ...value, weights: value.weights.map((v) => v / total) };
};
export const habitatSignature = (value: HabitatSettings | null) =>
  inputSignature(canonicalHabitat(value));
export const validHabitat = (value: HabitatSettings | null) =>
  !value ||
  (value.version === 1 &&
    ['fall-mixed', 'custom'].includes(value.preset) &&
    [60, 90, 120].includes(value.local_radius_m) &&
    [180, 270, 360].includes(value.landscape_radius_m) &&
    value.weights.length === 4 &&
    value.weights.every((n) => Number.isFinite(n) && n >= 0 && n <= 1) &&
    value.weights.reduce((a, b) => a + b, 0) > 0 &&
    [
      value.tree_penalty,
      value.shrub_penalty,
      value.habitat_threshold,
      value.glassability_threshold,
    ].every((n) => Number.isFinite(n) && n >= 0 && n <= 1));
export type HabitatMetric = {
  established_current_rank?: number;
  historical_original_rank?: number;
  id: string;
  status: string;
  effective_m2: number | null;
  current_visible_m2: number;
  matching_m2: number;
  scorable_m2: number;
  scorable_fraction: number | null;
  habitat_unknown_m2: number;
  target_filter_unknown_m2?: number;
  high_habitat_m2: number;
  priority_m2: number;
  component_effective_m2: Record<string, number>;
  observation_penalty_m2: number;
  mean_glassability: number | null;
  qualifies: boolean;
  working_revision: string;
};
export type HabitatResult = {
  run_id: string;
  identity: string;
  source_support_m: number;
  profile: { id: string; target_profile: string; settings: HabitatSettings };
  candidates: HabitatMetric[];
  recommendation_ids: string[];
  nearby_ids: Record<string, string[]>;
};
export const adjusted = (m?: number | null) =>
  m == null
    ? 'Insufficient data'
    : `${(m / 4046.8564224).toFixed(1)} quality-adjusted acre equivalents`;
export const acres = (m?: number | null) =>
  m == null ? 'Unknown' : `${(m / 4046.8564224).toFixed(1)} acres`;
type Api = (path: string, options?: RequestInit) => Promise<any>;
export function useHabitat(run: string, target: string, stamp: string, active: boolean, api: Api) {
  const [settings, setSettings] = useState<HabitatSettings | null>(null),
    [loaded, setLoaded] = useState('');
  const [result, setResult] = useState<{ value: HabitatResult; signature: string } | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [retry, setRetry] = useState(0),
    [loadRetry, setLoadRetry] = useState(0);
  const [overlay, setOverlay] = useState(false);
  const token = useRef(0);
  useEffect(() => {
    let alive = true;
    token.current++;
    setLoaded('');
    setResult(null);
    setError('');
    setOverlay(false);
    if (run && active)
      api(`/runs/${run}/habitat`)
        .then((v) => {
          if (!alive) return;
          setSettings(v.profile_spec?.settings ?? v.initial_settings ?? null);
          setLoaded(run);
        })
        .catch((e) => {
          if (alive) setError(String(e));
        });
    return () => {
      alive = false;
    };
  }, [run, active, loadRetry]);
  const signature = JSON.stringify([run, target, stamp, habitatSignature(settings)]);
  const latest = useRef(signature);
  latest.current = signature;
  useEffect(() => {
    let alive = true;
    const ticket = ++token.current;
    setResult(null);
    setError('');
    if (loaded !== run || !active || !run) return;
    setBusy(true);
    const timer = window.setTimeout(async () => {
      try {
        const old = await api(`/runs/${run}/habitat`);
        if (!alive || ticket !== token.current) return;
        const same =
          habitatSignature(old.profile_spec?.settings ?? null) === habitatSignature(settings) &&
          (!settings || old.profile_spec?.target_profile === target);
        const choice = same
          ? old
          : await api(`/runs/${run}/habitat`, {
              method: 'PUT',
              body: JSON.stringify({ settings, target_profile: target, revision: old.revision }),
            });
        if (!alive || ticket !== token.current || !settings) return;
        const value = await api(`/runs/${run}/habitat/${choice.profile}`);
        if (
          alive &&
          ticket === token.current &&
          latest.current === signature &&
          value.run_id === run &&
          value.profile.target_profile === target
        )
          setResult({ value, signature });
      } catch (e) {
        if (alive && ticket === token.current) setError(String(e));
      } finally {
        if (alive && ticket === token.current) setBusy(false);
      }
    }, 200);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [signature, loaded, active, retry]);
  const value =
    result?.signature === signature &&
    result.value.run_id === run &&
    result.value.profile.target_profile === target
      ? result.value
      : null;
  return {
    settings,
    setSettings,
    result: value,
    busy,
    error,
    overlay,
    setOverlay,
    retry: () => (loaded === run ? setRetry((v) => v + 1) : setLoadRetry((v) => v + 1)),
    enabled: !!settings && loaded === run,
    loading: active && loaded !== run,
    signature,
  };
}
export function HabitatSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: HabitatSettings | null;
  onChange: (v: HabitatSettings | null) => void;
  disabled?: boolean;
}) {
  const custom = (patch: Partial<HabitatSettings>) =>
    onChange({ ...value!, ...patch, preset: 'custom' });
  return (
    <section aria-label="Habitat settings">
      <label>
        Habitat preference{' '}
        <select
          aria-label="Habitat preference"
          disabled={disabled}
          value={value?.preset ?? 'off'}
          onChange={(e) =>
            onChange(e.target.value === 'off' ? null : { ...fallHabitat(), preset: e.target.value })
          }
        >
          <option value="off">Off</option>
          <option value="fall-mixed">Fall mixed habitat — experimental</option>
          <option value="custom">Custom</option>
        </select>
      </label>
      {value && !disabled && (
        <>
          <details>
            <summary>Advanced habitat settings</summary>
            <p>
              Structural habitat and vegetation glassability proxies, not deer probability or
              verified sightlines. Start without extra tree/shrub hard exclusions unless
              intentional.
            </p>
            <p>
              Fixed absolute scales; changing weights changes the experiment. Unknown neighborhoods
              receive no credit.
            </p>
            <label>
              Local context radius (m){' '}
              <select
                value={value.local_radius_m}
                onChange={(e) => custom({ local_radius_m: +e.target.value })}
              >
                {[60, 90, 120].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
            <label>
              Landscape context radius (m){' '}
              <select
                value={value.landscape_radius_m}
                onChange={(e) => custom({ landscape_radius_m: +e.target.value })}
              >
                {[180, 270, 360].map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </label>
            {['Background', 'Browse structure', 'Mixed context', 'Potential cover'].map(
              (name, i) => (
                <label key={name}>
                  {name} weight{' '}
                  <input
                    aria-label={`${name} weight`}
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value={value.weights[i]}
                    onChange={(e) => {
                      const w = [...value.weights];
                      w[i] = +e.target.value;
                      if (w.reduce((a, b) => a + b, 0) > 0) custom({ weights: w });
                    }}
                  />
                </label>
              ),
            )}
            {(
              [
                'tree_penalty',
                'shrub_penalty',
                'habitat_threshold',
                'glassability_threshold',
              ] as const
            ).map((key) => (
              <label key={key}>
                {key.replaceAll('_', ' ')} (0–1){' '}
                <input
                  aria-label={key}
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={value[key]}
                  onChange={(e) => custom({ [key]: +e.target.value })}
                />
              </label>
            ))}
            <small>
              Stronger penalties reduce utility under cover. Priority thresholds change physical
              summaries/overlay, not quality-adjusted ranking.
            </small>
            <button onClick={() => onChange(fallHabitat())}>Reset habitat settings</button>
          </details>
        </>
      )}
    </section>
  );
}
export function HabitatDetails({ metric, rank }: { metric?: HabitatMetric; rank?: number }) {
  if (!metric) return null;
  return (
    <section aria-label="Habitat explanation">
      <b>{adjusted(metric.effective_m2)}</b>
      <p>
        {acres(metric.priority_m2)} priority glassing · {acres(metric.high_habitat_m2)} high habitat
        (including harder cover)
      </p>
      <p>
        {acres(metric.scorable_m2)} scorable of {acres(metric.matching_m2)} matching ·{' '}
        {acres(metric.habitat_unknown_m2)} habitat/neighborhood unknown. Current mask visible
        eligible targets: {acres(metric.current_visible_m2)}.{' '}
        {rank !== undefined &&
          `Established current terrain rank ${metric.established_current_rank ?? rank}; historical original rank ${metric.historical_original_rank ?? 'unknown'}.`}
      </p>
      <p>
        Hard-target-filter unknown: {acres(metric.target_filter_unknown_m2)} of the current visible
        base mask; this diagnostic can overlap known exclusions and is separate from matching
        habitat unknown.
      </p>
      <details>
        <summary>Measured component explanation</summary>
        {Object.entries(metric.component_effective_m2 || {}).map(([k, v]) => (
          <p key={k}>
            {k}: {adjusted(v)}
          </p>
        ))}
        <p>
          Components add to the quality-adjusted total after glassability. Observation penalty:{' '}
          {adjusted(metric.observation_penalty_m2)} removed from habitat-only weighted area. Mean
          proxy G: {metric.mean_glassability?.toFixed(2) ?? 'unknown'}.
        </p>
      </details>
      <small>
        The saved visible mask may already be clipped to base target eligibility. Supported
        contribution is ranked without normalizing away unknown area. Inspect leading views and keep
        conservative observer/approach constraints.
      </small>
    </section>
  );
}
