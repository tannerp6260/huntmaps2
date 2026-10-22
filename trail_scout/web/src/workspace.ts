import { RecordValue } from "./api";

// Presentation state only. Analytical settings/results still pass through the API.
// A pending draft survives reload before the debounced server write completes.
const key = "trailscout-workspace-v1";
export function readWorkspace(): RecordValue | null {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "null");
    if (!value || typeof value !== "object" || Array.isArray(value))
      return null;
    if (value.mode && !["am", "pm", "combined", "stay"].includes(value.mode))
      return null;
    return { ...value, mode: value.mode || "am" };
  } catch {
    return null;
  }
}
export function writeWorkspace(patch: RecordValue) {
  try {
    localStorage.setItem(key, JSON.stringify({ ...readWorkspace(), ...patch }));
  } catch {
    /* Server drafts and immutable saves still work with storage disabled. */
  }
}
