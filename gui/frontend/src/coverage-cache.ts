import type { Map } from 'maplibre-gl';
export const COVERAGE_DISPLAY_VERSION = 2;

// Disk/HTTP preparation, not hundreds of resident GPU sources. Sequential work
// yields to movement and owner jobs; completed immutable tiles survive cancellation.
export function prepareCoverage(
  map: Map,
  run: string,
  ids: string[],
  working: Record<string, { revision: string }>,
  filter: string | undefined,
  report: (message: string) => void,
  wholeArea?: number[][],
) {
  const controller = new AbortController();
  let stopped = false;
  const stop = () => {
    stopped = true;
    controller.abort();
    report('');
  };
  map.on('movestart', stop);
  function tiles(bounds: number[][], z: number): [number, number, number][] {
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
    const result: [number, number, number][] = [];
    const left = x(bounds[0][0]),
      right = x(bounds[1][0]),
      top = y(bounds[1][1]),
      bottom = y(bounds[0][1]);
    if ((right - left + 1) * (bottom - top + 1) > 64) return [];
    for (let tx = left; tx <= right; tx++)
      for (let ty = top; ty <= bottom; ty++) result.push([z, ((tx % n) + n) % n, ty]);
    return result;
  }
  const start = async () => {
    if (stopped || map.isMoving() || !ids.length) return;
    const b = map.getBounds(),
      viewport = [
        [b.getWest(), b.getSouth()],
        [b.getEast(), b.getNorth()],
      ];
    const z = Math.min(20, Math.max(0, Math.round(map.getZoom() + 1)));
    let overview: [number, number, number][] = [];
    if (wholeArea) {
      for (let level = Math.min(z, 15); level >= 0; level--) {
        overview = tiles(wholeArea, level);
        if (overview.length && overview.length <= 16) break;
      }
    }
    const viewTiles = [z, Math.max(0, z - 1), Math.min(20, z + 1)].flatMap((level) =>
      tiles(viewport, level),
    );
    const unique = (v: [number, number, number][]) => [
      ...new globalThis.Map(v.map((t) => [t.join('/'), t])).values(),
    ];
    // Finish nearby views first, then broad coverage for every queued suggestion.
    const tasks = [
      ...ids.slice(0, 3).flatMap((id) => unique(viewTiles).map((t) => ({ id, t }))),
      ...ids.flatMap((id) => unique(overview).map((t) => ({ id, t }))),
    ];
    let done = 0;
    try {
      for (const {
        id,
        t: [level, x, y],
      } of tasks) {
        if (stopped) return;
        report(`Preparing saved coverage · ${done}/${tasks.length} tiles`);
        const route = filter ? `filtered-tiles/${filter}` : working[id] ? 'working-tiles' : 'tiles';
        const response = await fetch(
          `/api/runs/${run}/${route}/visible/${id}/${level}/${x}/${y}.png?color=0&revision=${working[id]?.revision || 'original'}&display=${COVERAGE_DISPLAY_VERSION}`,
          { signal: controller.signal, headers: { 'X-Huntmaps-Prefetch': 'true' } },
        );
        if (!response.ok) {
          report('Background preparation paused; current view remains available');
          return;
        }
        await response.arrayBuffer();
        done++;
        await new Promise((resolve) => window.setTimeout(resolve, 20));
      }
      if (!stopped) report(`Coverage saved ahead for ${ids.length} spots`);
    } catch {
      if (!stopped) report('Background preparation paused');
    }
  };
  const timer = window.setTimeout(start, 500);
  return () => {
    stop();
    clearTimeout(timer);
    map.off('movestart', stop);
  };
}
