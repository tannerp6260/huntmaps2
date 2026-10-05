import type { RunSummary } from './types';
export default function RunSelection({
  runs,
  value,
  disabled,
  onChange,
}: {
  runs: RunSummary[];
  value: string;
  disabled: boolean;
  onChange: (id: string) => void;
}) {
  return (
    <label className="run-picker">
      Scouting area
      <select
        aria-label="Run selector"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {!value && <option value="">Choose a scouting area…</option>}
        {runs.map((r) => (
          <option key={r.id} value={r.id}>
            {r.label}
          </option>
        ))}
      </select>
    </label>
  );
}
