// Display conversions only. Engine values and exports retain their recorded metric units.
export const METERS_PER_YARD = 0.9144;
export const METERS_PER_FOOT = 0.3048;
export const KM2_PER_MI2 = 2.589988110336;
function measure(value: unknown, divisor: number, suffix: string, digits = 0) {
  if (value == null || value === '' || !Number.isFinite(Number(value))) return 'unknown';
  const n = Number(value) / divisor;
  return `${n > 0 && n < Math.pow(10, -digits) ? '<' + Math.pow(10, -digits).toFixed(digits) : n.toFixed(digits)} ${suffix}`;
}
export const area = (km2: unknown) => measure(km2, KM2_PER_MI2, 'mi²', 3);
export const yards = (meters: unknown, digits = 0) =>
  measure(meters, METERS_PER_YARD, 'yd', digits);
export const feet = (meters: unknown, digits = 0) => measure(meters, METERS_PER_FOOT, 'ft', digits);
export const imperialNotice = (notice: string) =>
  notice.replace(/20 m ground grid/g, '22 yd ground grid');
