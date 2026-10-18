import { useEffect, useState } from 'react';
import type { RasterTileSource, Map, ErrorEvent as MapErrorEvent } from 'maplibre-gl';
export default function Transportation({ map }: { map: Map | null }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!map) return;
    const id = 'transportation-context';
    map.addSource(id, {
      type: 'raster',
      tiles: [location.origin + '/api/browsing/transportation/{z}/{x}/{y}.png'],
      tileSize: 256,
      minzoom: 5,
      maxzoom: 16,
      attribution: 'USGS Transportation · browsing context only',
    });
    map.addLayer(
      {
        id,
        type: 'raster',
        source: id,
        paint: { 'raster-opacity': 0.8, 'raster-fade-duration': 0 },
      },
      map.getLayer('network-map-outline')
        ? 'network-map-outline'
        : map.getLayer('candidate-halo')
          ? 'candidate-halo'
          : undefined,
    );
    const error = (e: MapErrorEvent & { sourceId?: string }) => {
      if (e.sourceId === id) setFailed(true);
    };
    map.on('error', error);
    return () => {
      map.off('error', error);
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    };
  }, [map]);
  return (
    <small role="status">
      {failed
        ? 'General roads/trails unavailable from provider. Verified local networks remain available.'
        : 'USGS general roads and trails · browsing context only'}
      {failed && (
        <button
          onClick={() => {
            setFailed(false);
            (map?.getSource('transportation-context') as RasterTileSource | undefined)?.setTiles([
              location.origin + '/api/browsing/transportation/{z}/{x}/{y}.png?retry=' + Date.now(),
            ]);
          }}
        >
          Retry general roads/trails
        </button>
      )}
    </small>
  );
}
