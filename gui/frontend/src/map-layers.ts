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
) {
  let disposed = false;
  for (const l of [...m.getStyle().layers].reverse())
    if (l.id.startsWith('raster-') || l.id.startsWith('sector-')) m.removeLayer(l.id);
  for (const id of Object.keys(m.getStyle().sources))
    if (id.startsWith('raster-') || id.startsWith('sector-')) m.removeSource(id);
  const addRaster = (layer: string, id: string, alpha: number, color = 0) => {
    const key = `raster-${layer}-${id}`;
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
          'raster-opacity': alpha,
          'raster-resampling': layer === 'imagery' ? 'linear' : 'nearest',
          'raster-fade-duration': 0,
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
    if (sectors && !working[id] && (!compare.length || !hiddenViews.includes(id)))
      api(`/runs/${run.id}/sectors/${id}`)
        .then((data) => {
          if (disposed) return;
          const key = 'sector-' + id;
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
  });
  if (classes && selected && !newRun && !activeManual) addRaster('classes', selected, opacity);
  return () => {
    disposed = true;
  };
}
