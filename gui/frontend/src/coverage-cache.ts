import type { Map } from 'maplibre-gl';

// Bump when coverage display semantics change, independently of frozen analysis outputs.
export const COVERAGE_DISPLAY_VERSION = 1;

// Warm only this viewport, sequentially. Browser HTTP caching survives source removal/reload.
export function prepareCoverage(
  map: Map,
  run: string,
  ids: string[],
  working: Record<string, { revision: string }>,
  filter: string | undefined,
  report: (message: string) => void,
) {
  const controller = new AbortController();
  let stopped = false;
  const stop = () => {
    stopped = true;
    controller.abort();
    report('');
  };
  map.on('movestart', stop);
  const start = async () => {
    if (stopped || map.isMoving() || !ids.length) return;
    // MapLibre uses a 512-pixel camera scale; our raster sources have 256-pixel tiles.
    const z = Math.min(20, Math.max(0, Math.round(map.getZoom() + 1))),
      n = 2 ** z;
    const bounds = map.getBounds();
    const x = (lon: number) => Math.floor(((lon + 180) / 360) * n);
    const y = (lat: number) => {
      const r = (Math.max(-85.0511, Math.min(85.0511, lat)) * Math.PI) / 180;
      return Math.max(
        0,
        Math.min(n - 1, Math.floor(((1 - Math.asinh(Math.tan(r)) / Math.PI) / 2) * n)),
      );
    };
    const tiles: [number, number][] = [];
    for (let tx = x(bounds.getWest()); tx <= x(bounds.getEast()); tx++)
      for (let ty = y(bounds.getNorth()); ty <= y(bounds.getSouth()); ty++) {
        if (tiles.length === 64) return; // Wide views should not create an unbounded queue.
        tiles.push([((tx % n) + n) % n, ty]);
      }
    const total = tiles.length * ids.length;
    let done = 0;
    try {
      for (const id of ids)
        for (const [tx, ty] of tiles) {
          if (stopped) return;
          report(`Preparing next views · ${done}/${total} tiles`);
          const route = filter
            ? `filtered-tiles/${filter}`
            : working[id]
              ? 'working-tiles'
              : 'tiles';
          const revision = working[id]?.revision || 'original';
          const response = await fetch(
            `/api/runs/${run}/${route}/visible/${id}/${z}/${tx}/${ty}.png?color=0&revision=${revision}&display=${COVERAGE_DISPLAY_VERSION}`,
            {
              signal: controller.signal,
              headers: { 'X-Huntmaps-Prefetch': 'true' },
            },
          );
          if (!response.ok) {
            report('Background preparation paused');
            return;
          }
          await response.arrayBuffer();
          done++;
        }
      if (!stopped) report(`Next ${ids.length} views cached for this map area`);
    } catch {
      if (!stopped) report('Background preparation paused');
    }
  };
  const timer = window.setTimeout(start, 500);
  return () => {
    stopped = true;
    controller.abort();
    clearTimeout(timer);
    map.off('movestart', stop);
  };
}
