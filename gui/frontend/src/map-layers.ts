import type { Map } from 'maplibre-gl';
import type { Run } from './types';
import { onlineSource } from './online';
const colors = ['#00c0e8', '#ff6782', '#aa6fff'];
type LayerState = {
  run: Run;
  filterId?: string;
  working: Record<string, { revision: string }>;
  imagery: boolean;
  imageOpacity: number;
  newRun: boolean;
  compare: string[];
  activeManual: { id: string } | null;
  selected: string;
  visibility: boolean;
  hiddenViews: string[];
  opacity: number;
  sectors: boolean;
  classes: boolean;
};
export function updateMapLayers(
  m: Map,
  {
    run,
    filterId,
    working,
    imagery,
    imageOpacity,
    newRun,
    compare,
    activeManual,
    selected,
    visibility,
    hiddenViews,
    opacity,
    sectors,
    classes,
  }: LayerState,
  api: (path: string) => Promise<GeoJSON.GeoJSON>,
  setError: (message: string) => void,
  setCoverage: (message: string) => void,
  retry = 0,
) {
  let disposed = false;
  const wanted = new Set<string>();
  const coverage: { key: string; alpha: number }[] = [];
  const addRaster = (layer: string, id: string, alpha: number, color = 0) => {
    const key = `raster-${layer}-${id}-${run.id}-${['visible', 'classes'].includes(layer) ? filterId || 'base' : 'base'}-${working[id]?.revision || 'original'}-${color}-${layer === 'visible' ? retry : 0}`;
    wanted.add(key);
    if (layer === 'visible') coverage.push({ key, alpha });
    if (m.getSource(key)) {
      m.setPaintProperty(key, 'raster-opacity', layer === 'visible' ? 0 : alpha);
      return;
    }
    const useWorking = !!working[id];
    m.addSource(key, {
      type: 'raster',
      tiles: [
        `${location.origin}/api/runs/${run.id}/${filterId && ['visible', 'classes'].includes(layer) ? `filtered-tiles/${filterId}` : useWorking ? 'working-tiles' : 'tiles'}/${layer}/${id}/{z}/{x}/{y}.png?color=${color}&revision=${working[id]?.revision || 'original'}`,
      ],
      tileSize: 256,
      maxzoom: 20,
    });
    m.addLayer(
      {
        id: key,
        type: 'raster',
        source: key,
        paint: {
          'raster-opacity': layer === 'visible' ? 0 : alpha,
          'raster-resampling': layer === 'imagery' ? 'linear' : 'nearest',
          'raster-fade-duration': 0,
          'raster-opacity-transition': { duration: 0, delay: 0 },
        },
      },
      'boundary-fill',
    );
  };
  addRaster('hillshade', 'base', 1);
  if (m.getLayer(onlineSource)) m.moveLayer(onlineSource, 'boundary-fill');
  if (imagery && run.imagery.length) addRaster('imagery', 'base', imageOpacity);
  const ids = newRun
    ? []
    : compare.length
      ? compare
      : activeManual
        ? working[activeManual.id]
          ? [activeManual.id]
          : []
        : selected
          ? [selected]
          : [];
  ids.forEach((id, i) => {
    if (visibility && (!compare.length || !hiddenViews.includes(id)))
      addRaster('visible', id, opacity, i);
    const sectorKey = `sector-${run.id}-${id}`;
    if (sectors && !working[id] && (!compare.length || !hiddenViews.includes(id))) {
      wanted.add(sectorKey);
      if (m.getLayer(sectorKey)) m.setPaintProperty(sectorKey, 'line-color', colors[i]);
      if (!m.getSource(sectorKey))
        api(`/runs/${run.id}/sectors/${id}`)
          .then((data) => {
            if (disposed || m.getSource(sectorKey)) return;
            const key = sectorKey;
            m.addSource(key, { type: 'geojson', data });
            m.addLayer(
              {
                id: key,
                type: 'line',
                source: key,
                paint: { 'line-color': colors[i], 'line-width': 2, 'line-dasharray': [2, 2] },
              },
              'candidate-halo',
            );
          })
          .catch((e) => {
            if (!disposed) setError(e instanceof Error ? e.message : String(e));
          });
    }
  });
  if (classes && selected && !newRun && !activeManual) addRaster('classes', selected, opacity);
  for (const layer of [...m.getStyle().layers].reverse())
    if ((layer.id.startsWith('raster-') || layer.id.startsWith('sector-')) && !wanted.has(layer.id))
      m.removeLayer(layer.id);
  for (const key of Object.keys(m.getStyle().sources))
    if ((key.startsWith('raster-') || key.startsWith('sector-')) && !wanted.has(key))
      m.removeSource(key);
  let failed = false;
  let revealed = false;
  const label = ids.join(', ');
  const pending = () => {
    revealed = false;
    if (!coverage.length) {
      setCoverage('');
      return;
    }
    coverage.forEach(({ key }) => {
      if (m.getLayer(key)) m.setPaintProperty(key, 'raster-opacity', 0);
    });
    setCoverage(`${failed ? 'Coverage incomplete' : 'Loading coverage'} · ${label}`);
  };
  const check = () => {
    if (disposed || revealed || !coverage.length || failed || m.isMoving()) return;
    if (coverage.every(({ key }) => m.getSource(key) && m.isSourceLoaded(key))) {
      revealed = true;
      coverage.forEach(({ key, alpha }) => m.setPaintProperty(key, 'raster-opacity', alpha));
      setCoverage(`Coverage ready · ${label}`);
    }
  };
  const error = (event: unknown) => {
    const sourceId =
      event && typeof event === 'object' && 'sourceId' in event ? String(event.sourceId) : '';
    if (coverage.some(({ key }) => key === sourceId)) {
      failed = true;
      pending();
      setCoverage(`Coverage incomplete · ${label}`);
    }
  };
  const loading = (event: { sourceId?: string }) => {
    if (!failed && coverage.some(({ key }) => key === event.sourceId)) pending();
  };
  pending();
  m.on('movestart', pending);
  m.on('moveend', check);
  m.on('sourcedataloading', loading);
  m.on('sourcedata', check);
  m.on('idle', check);
  m.on('error', error);
  check();
  return () => {
    disposed = true;
    m.off('movestart', pending);
    m.off('moveend', check);
    m.off('sourcedataloading', loading);
    m.off('sourcedata', check);
    m.off('idle', check);
    m.off('error', error);
  };
}
