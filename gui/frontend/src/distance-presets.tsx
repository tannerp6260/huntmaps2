import { METERS_PER_YARD } from './units';
export default function DistancePresets({
  label,
  value,
  onChange,
  presets = [500, 1000, 1500, 2000, 2500, 3000],
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  presets?: number[];
}) {
  const options = presets.map((y) => ({ y, m: y * METERS_PER_YARD }));
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {!options.some((o) => Math.abs(o.m - value) < 1e-7) && (
        <option value={value}>
          Saved: {+(value / METERS_PER_YARD).toFixed(6)} yd ({value} m)
        </option>
      )}
      {options.map((o) => (
        <option key={o.y} value={o.m}>
          {o.y.toLocaleString('en-US')} yd
        </option>
      ))}
    </select>
  );
}
