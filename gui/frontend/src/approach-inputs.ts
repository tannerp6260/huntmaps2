// Ignore millimetre-scale coordinate noise and ignore object/set ordering.
export function inputSignature(value: unknown): string {
  function normalize(v: any, key = ''): any {
    if (typeof v === 'number') return Math.round(v * 1e8) / 1e8;
    if (Array.isArray(v)) {
      const result = v.map((x) => normalize(x));
      return ['ids', 'kinds', 'aspects'].includes(key) ? [...new Set(result)].sort() : result;
    }
    if (v && typeof v === 'object')
      return Object.fromEntries(
        Object.keys(v)
          .sort()
          .map((k) => [k, normalize(v[k], k)]),
      );
    return v;
  }
  return JSON.stringify(normalize(value));
}
