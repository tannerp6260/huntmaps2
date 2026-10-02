import { useEffect, useState } from 'react';
import type { Map } from 'maplibre-gl';
export const onlineSource = 'online-imagery';
export function OnlineImagery({ map }: { map: Map }) {
  const [enabled, setEnabled] = useState(
      () => localStorage.getItem('huntmaps-online-imagery') !== 'off',
    ),
    [failed, setFailed] = useState(false),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    localStorage.setItem('huntmaps-online-imagery', enabled ? 'on' : 'off');
    setFailed(false);
    if (!enabled) return;
    map.addSource(onlineSource, {
      type: 'raster',
      tiles: [
        'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      maxzoom: 16,
      attribution: 'USDA, USGS The National Map: Orthoimagery',
    });
    const anchor = map.getLayer('raster-imagery-base') ? 'raster-imagery-base' : 'boundary-fill';
    map.addLayer(
      {
        id: onlineSource,
        type: 'raster',
        source: onlineSource,
        paint: { 'raster-fade-duration': 0 },
      },
      anchor,
    );
    const error = (e: any) => {
      if (e.sourceId === onlineSource) setFailed(true);
    };
    const loaded = (e: any) => {
      if (e.sourceId === onlineSource && e.tile?.state === 'loaded') setFailed(false);
    };
    map.on('error', error);
    map.on('sourcedata', loaded);
    return () => {
      map.off('error', error);
      map.off('sourcedata', loaded);
      if (map.getLayer(onlineSource)) map.removeLayer(onlineSource);
      if (map.getSource(onlineSource)) map.removeSource(onlineSource);
    };
  }, [map, enabled, retry]);
  return (
    <div className="online-context">
      <label>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Online imagery — fill gaps
      </label>
      <small>
        Online context; acquisition dates vary. Saved imagery stays on top. Browsing tiles uses
        internet separately from the analysis download cap.
      </small>
      {enabled && failed && (
        <div role="status">
          <small>
            Online imagery could not load. Cached imagery and local hillshade remain available where
            covered.
          </small>
          <button onClick={() => setRetry((v) => v + 1)}>Retry online imagery</button>
        </div>
      )}
    </div>
  );
}
