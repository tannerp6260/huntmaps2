import { MercatorCoordinate, type Map } from 'maplibre-gl';
export const COVERAGE_DISPLAY_VERSION = 2;
export const COVERAGE_REVIEW_ZOOM = 13.8;
export type CoveragePoint = { id: string; longitude: number; latitude: number };
export type Preparation = {
  phase: 'preparing' | 'paused' | 'ready' | 'cancelled' | 'error';
  completed: number;
  total: number;
  tiles: number;
  totalTiles: number;
  current: string;
  message: string;
};
type Tile = [number, number, number];
function tiles(bounds: number[][], z: number, limit = 64): Tile[] {
  const n = 2 ** z;
  const x = (lon: number) => Math.floor(((lon + 180) / 360) * n);
  const y = (lat: number) =>
    Math.max(
      0,
      Math.min(
        n - 1,
        Math.floor(
          ((1 -
            Math.asinh(Math.tan((Math.max(-85.0511, Math.min(85.0511, lat)) * Math.PI) / 180)) /
              Math.PI) /
            2) *
            n,
        ),
      ),
    );
  const left = x(bounds[0][0]),
    right = x(bounds[1][0]),
    top = y(bounds[1][1]),
    bottom = y(bounds[0][1]);
  if ((right - left + 1) * (bottom - top + 1) > limit)
    throw Error(
      'This view is too large to prepare within the tile limit. Use a smaller map window.',
    );
  const result: Tile[] = [];
  for (let tx = left; tx <= right; tx++)
    for (let ty = top; ty <= bottom; ty++) result.push([z, ((tx % n) + n) % n, ty]);
  return result;
}
// Prepare exact immutable display URLs, without adding resident GPU sources.
// Cover the rotated 2D viewport and camera padding at the normal selection zoom.
export function coverageTasks(
  points: CoveragePoint[],
  width: number,
  height: number,
  wholeArea?: number[][],
  bearing = 0,
  padding = [0, 0],
) {
  const angle = (bearing * Math.PI) / 180;
  const w = width + padding[0],
    h = height + padding[1];
  const scale = 2 * 512 * 2 ** COVERAGE_REVIEW_ZOOM;
  const halfWidth = (Math.abs(Math.cos(angle)) * w + Math.abs(Math.sin(angle)) * h) / scale;
  const halfHeight = (Math.abs(Math.sin(angle)) * w + Math.abs(Math.cos(angle)) * h) / scale;
  let overview: Tile[] = [];
  if (wholeArea)
    for (let z = 14; z >= 0; z--) {
      try {
        overview = tiles(wholeArea, z);
      } catch {
        continue;
      }
      if (overview.length <= 16) break;
    }
  return points.map((p) => {
    const c = MercatorCoordinate.fromLngLat([p.longitude, p.latitude]);
    const a = new MercatorCoordinate(c.x - halfWidth, c.y + halfHeight).toLngLat();
    const b = new MercatorCoordinate(c.x + halfWidth, c.y - halfHeight).toLngLat();
    const bounds = [
      [a.lng, a.lat],
      [b.lng, b.lat],
    ];
    const levels = [13, 14, 15];
    const unique = new globalThis.Map<string, Tile>(
      [...levels.flatMap((z) => tiles(bounds, z, 512)), ...overview].map((t) => [t.join('/'), t]),
    );
    return { id: p.id, tiles: [...unique.values()] };
  });
}
export function prepareCoverage(
  map: Map,
  run: string,
  points: CoveragePoint[],
  working: Record<string, { revision: string }>,
  filter: string | undefined,
  report: (value: Preparation) => void,
  wholeArea?: number[][],
  paused: () => boolean = () => false,
  finished = new Set<string>(),
) {
  const controller = new AbortController();
  let stopped = false;
  let state: Preparation = {
    phase: 'preparing',
    completed: 0,
    total: points.length,
    tiles: 0,
    totalTiles: 0,
    current: '',
    message: '',
  };
  const emit = (phase: Preparation['phase'], message = '') => {
    state = { ...state, phase, message };
    report(state);
  };
  const start = async () => {
    try {
      const padding = map.getPadding();
      const groups = coverageTasks(
        points,
        map.getContainer().clientWidth,
        map.getContainer().clientHeight,
        wholeArea,
        map.getBearing(),
        [
          Math.abs((padding.left ?? 0) - (padding.right ?? 0)),
          Math.abs((padding.top ?? 0) - (padding.bottom ?? 0)),
        ],
      );
      state.totalTiles = groups.reduce((n, g) => n + g.tiles.length, 0);
      for (const group of groups) {
        state.current = group.id;
        for (const [z, x, y] of group.tiles) {
          if (stopped) return;
          const route = filter
            ? `filtered-tiles/${filter}`
            : working[group.id]
              ? 'working-tiles'
              : 'tiles';
          const url = `/api/runs/${run}/${route}/visible/${group.id}/${z}/${x}/${y}.png?color=0&revision=${working[group.id]?.revision || 'original'}&display=${COVERAGE_DISPLAY_VERSION}`;
          while (!stopped && (paused() || map.isMoving())) {
            emit('paused', 'Preparation pauses during map movement, 3D views or other jobs.');
            await new Promise((resolve) => window.setTimeout(resolve, 300));
          }
          if (stopped) return;
          emit('preparing');
          if (!finished.has(url)) {
            const response = await fetch(url, {
              signal: controller.signal,
              headers: { 'X-Huntmaps-Prefetch': 'true' },
            });
            if (!response.ok) {
              const detail = await response
                .json()
                .catch(() => ({ detail: 'Coverage tile could not load.' }));
              throw Error(detail.detail || 'Coverage tile could not load.');
            }
            await response.arrayBuffer();
            if (stopped) return;
            finished.add(url);
          }
          state.tiles++;
          await new Promise((resolve) => window.setTimeout(resolve, 20));
        }
        state.completed++;
        emit('preparing');
      }
      if (!stopped) emit('ready');
    } catch (e) {
      if (!stopped) emit('error', e instanceof Error ? e.message : String(e));
    }
  };
  void start();
  return () => {
    stopped = true;
    controller.abort();
    emit('cancelled', 'Completed tiles remain cached.');
  };
}
