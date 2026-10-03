import type { Map } from 'maplibre-gl';

export const onlineSource = 'online-imagery';

// Reapply the same stack when sources are created, retained, or toggled.
export function orderRasterLayers(map: Map) {
  if (!map.getLayer('boundary-fill')) return;
  const layers = map.getStyle().layers;
  const roles = [
    (id: string) => id.startsWith('raster-hillshade-'),
    (id: string) => id === onlineSource,
    (id: string) => id.startsWith('raster-imagery-'),
    (id: string) => id.startsWith('raster-visible-'),
    (id: string) => id.startsWith('raster-classes-'),
  ];
  for (const matches of roles)
    for (const layer of layers) if (matches(layer.id)) map.moveLayer(layer.id, 'boundary-fill');
}
