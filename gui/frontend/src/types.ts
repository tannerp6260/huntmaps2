export type Candidate = {
  name?: string;
  working_revision?: string;
  id: string;
  longitude: number;
  latitude: number;
  parent: string;
  neighborhood: string | null;
  metrics: Record<string, number | string>;
  foreground: Record<string, number>;
  access: unknown;
  diagnostics: unknown;
  alignment?: unknown;
  obstruction_scenarios: Record<string, unknown>[];
  obstruction: string;
};
export type Run = {
  id: string;
  experimental: boolean;
  candidates: Candidate[];
  groups: Record<string, string[]>;
  review_ids: string[];
  synthetic: boolean;
  boundary: GeoJSON.FeatureCollection;
  bounds: [[number, number], [number, number]];
  radius_m: number;
  imagery: { path: string; acquisition_date: string; dates?: string[] }[];
  warning: string;
};
export type Job = {
  id: string;
  name: string;
  kind: string;
  plan: string;
  status: string;
  stage: string;
  elapsed_s: number;
  logs: string;
  error?: string;
  engine_event?: { stage?: string; command?: string; wall_s?: number };
};

export type RunSummary = { id: string; label: string; experimental: boolean };
export type Review = { name?: string; notes: string; status: string };
export type Target = { east_m: number; north_m: number };
export type ObserverPose = Target & {
  anchor: string;
  scene_y_m: number;
  longitude: number;
  latitude: number;
  displacement_m: number;
  scene_key: string;
  ground_m: number;
  run_id?: string;
  id?: string;
  name?: string;
  notes?: string;
};
export type ManualWaypoint = ObserverPose & {
  id: string;
  name: string;
  notes: string;
  status: string;
  analysis: string;
  access: string;
  revision?: never;
  kind: 'provisional-manual-observer';
};
export type WorkingWaypointRecord = Omit<ManualWaypoint, 'kind' | 'revision'> & {
  kind: 'working-waypoint';
  revision: string;
  metrics: Record<string, number>;
  terrain: Record<string, unknown>;
};
export type Overlap = { a: string; b: string; shared_km2: number };
export type ImportedArea = {
  id: string;
  path?: string;
  choices: { number: string; name: string; geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon }[];
};
export type AcquisitionItem = {
  key: string;
  title: string;
  estimated_bytes: number;
  cached?: boolean;
  status?: string;
  provider?: string;
};
export type BaselinePlan = {
  id: string;
  name: string;
  prepared: boolean;
  sources_ready: boolean;
  max_download_mb: number;
  required_data?: string;
  boundary?: GeoJSON.FeatureCollection;
  settings: { radius_m: number; observation_minutes: number; candidate_count: number };
  acquisition?: {
    already_cached_bytes?: number;
    cached_keys?: string[];
    estimated_bytes: number;
    estimate_note: string;
    errors: string[];
    items: AcquisitionItem[];
  };
};
export type FirstPersonPlan = {
  download_cap_bytes: number;
  candidates: string[];
  id: string;
  prepared: boolean;
  estimated_new_bytes: number;
  already_received_bytes: number;
  source_note: string;
  errors: string[];
  sources: {
    key: string;
    title: string;
    cached: boolean;
    bytes: number;
    acquisition_date: string;
    vertical_reference?: string;
  }[];
};
export type Intersection = Target & { distance_m: number; ground_m: number; line_m: number };
export type ProfileResult = {
  status?: string;
  result: string;
  distance_m: number;
  minimum_clearance_m: number | null;
  borderline: boolean;
  source_label: string;
  warning: string;
  first_obstruction: Intersection | null;
  points: { distance_m: number; ground_m: number | null; line_m: number | null }[];
  vegetation?: {
    status: string;
    reason?: string;
    warning?: string;
    selected_scenario: string;
    geometry_identifier?: string;
    included_cell_count: number;
    evaluated_radius_m: number;
    unknown_ground: boolean;
    farther_vegetation_unevaluated?: boolean;
    coverage_exit_distance_m?: number;
    scenarios: Record<
      string,
      {
        result: string;
        blocked: boolean;
        first_intersection: Intersection | null;
        clearance_m?: number;
        intersection_count?: number;
        observer_inside?: boolean;
        target_inside?: boolean;
      }
    >;
  };
};
export type TextureInfo = {
  file: string;
  radius_m: number;
  pixel_spacing_m: number;
  native_resolution_m: number[];
};
export type MeshInfo = {
  vertices_file: string;
  indices_file: string;
  colors_file: string;
  triangle_count: number;
};
export type SceneReady = {
  scene_signature?: Record<string, unknown>;
  fidelity?: string;
  status: 'ready';
  key: string;
  candidate: string;
  acquisition_date: string;
  observer: Candidate;
  ground_m: number;
  fine_ground_m: number;
  baseline_ground_m: number;
  fine_observer_available: boolean;
  initial_bearing_deg: number;
  initial_facing_note: string;
  ground_interpolation: string;
  vertical_note: string;
  warning: string;
  texture?: TextureInfo;
  context_texture?: TextureInfo;
  coverage_fraction: number;
  resolution_m: number;
  vertical_reference: string;
  sources: unknown[];
  classification_counts: Record<string, number>;
  maximum_support_distance_m: number;
  display_point_count: number;
  above_ground_point_count: number;
  raw_local_point_count: number;
  display_stride: number;
  point_filter: string;
  vegetation: {
    warning: string;
    cell_count: number;
    inferred_cell_count: number;
    classified_cell_count: number;
    neighbor_supported_cell_count: number;
    centres_file: string;
    kinds_file: string;
    colors_file: string;
    primitive_file: string;
    geometry_identifier: string;
    display_cap: number;
    default_radius_m: number;
    scenarios: Record<string, number>;
    nearby_counts: Record<string, number>;
    meshes?: Record<
      string,
      {
        sampling_interval_m: number;
        cell_count: number;
        unavailable?: boolean;
        reason?: string;
        scenarios: Record<string, MeshInfo>;
      }
    >;
  };
};
export type Scene =
  | SceneReady
  | { status: 'unprepared'; candidate: string; observer: Candidate; key?: never; reason: string };
