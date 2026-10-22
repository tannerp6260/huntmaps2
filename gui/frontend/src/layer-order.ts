import type { Map } from 'maplibre-gl';

export const onlineSource = 'online-imagery';

// Reapply the same stack when sources are created, retained, or toggled.
export function orderRasterLayers(map: Map) {
  if (!map.getLayer('boundary-fill')) return;
  const layers = map.getStyle().layers;
  const roles = [
    (id: string) => id === 'unit-relief',
    (id: string) => id.startsWith('raster-hillshade-'),
    (id: string) => id === onlineSource,
    (id: string) => id.startsWith('raster-imagery-'),
    (id: string) => id.startsWith('raster-visible-'),
    (id: string) => id.startsWith('raster-classes-'),
    (id: string) => id.startsWith('raster-habitat-'),
    (id: string) => id === 'roadless-overlay',
  ];
  for (const matches of roles)
    for (const layer of layers) if (matches(layer.id)) map.moveLayer(layer.id, 'boundary-fill');
  // Unit context must stay above every raster, including asynchronously added imagery.
  for (const id of ['unit-network-outline', 'unit-roads', 'unit-trails'])
    if (map.getLayer(id)) map.moveLayer(id, 'boundary-fill');
}
