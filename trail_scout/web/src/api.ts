export type RecordValue = Record<string, any>;
export async function api(
  path: string,
  data?: unknown,
  method = "POST",
): Promise<any> {
  const response = await fetch(
    "/api" + path,
    data === undefined
      ? undefined
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
  );
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch {
      /* retain HTTP status */
    }
    throw new Error(detail);
  }
  return response.json();
}
export const miles = (m: number) => (m / 1609.344).toFixed(2);
export const feet = (m: number) => Math.round(m / 0.3048).toLocaleString();
export const acres = (m: number | null) =>
  m === null ? "Unknown" : Math.round(m / 4046.8564224).toLocaleString();
export const clock = (s: string) =>
  new Date(s).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Denver",
    timeZoneName: "short",
  });
export const defaults: RecordValue = {
  date: "2026-10-31",
  profile: { preset: "together" },
  vehicle: "truck",
  start_id: "",
  custom_start: null,
  corridor_m: 2500,
  view_radius_m: 1500,
  search_envelope_m: 300,
  candidate_budget: 32,
  explore_unknown: false,
  excluded_segments: [],
  excluded_areas: [],
  rejected: [],
  pinned: [],
  restrictions: [],
  schedule: {},
  travel_area: null,
  target_area: null,
};
