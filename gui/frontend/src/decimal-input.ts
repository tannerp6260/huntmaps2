// Keep raw input text in state; parse only for validation and canonical payloads.
export function decimalValue(text: string): number | null {
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(text.trim())) return null;
  const n = Number(text);
  return Number.isFinite(n) && n >= 0 ? n : null;
}
