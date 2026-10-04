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
      Open saved results
      <select
        aria-label="Run selector"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {!value && <option value="">Choose saved results…</option>}
        {runs.map((r) => (
          <option key={r.id} value={r.id}>
            {r.label}
          </option>
        ))}
      </select>
    </label>
  );
}
