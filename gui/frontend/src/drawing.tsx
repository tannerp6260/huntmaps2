import { useEffect, useRef, useState } from 'react';
import { LngLatBounds } from 'maplibre-gl';
import type { Map } from 'maplibre-gl';
import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
  TerraDrawModeUndoRedo,
  TerraDrawSessionUndoRedo,
} from 'terra-draw';
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter';

export function Drawing({
  map,
  geometry,
  onSave,
  onInvalidate,
  onRestore,
  onEditing,
  onClear,
}: {
  map: Map;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  onSave: (feature: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon>) => Promise<void>;
  onInvalidate: () => void;
  onRestore: () => void;
  onEditing: (value: boolean) => void;
  onClear: () => void;
}) {
  const instance = useRef<TerraDraw | null>(null),
    polygonMode = useRef<TerraDrawPolygonMode | null>(null),
    backup = useRef<GeoJSON.Polygon | GeoJSON.MultiPolygon | null>(null);
  const [, setMapRevision] = useState(0);
  const [editing, setEditing] = useState(false),
    [closed, setClosed] = useState(false),
    [points, setPoints] = useState(0),
    [saving, setSaving] = useState(false),
    [error, setError] = useState(''),
    [undoable, setUndoable] = useState(false);
  const editingRef = useRef(editing);
  editingRef.current = editing;
  const callbacks = useRef({ onEditing, cancel });
  callbacks.current = { onEditing, cancel };
  useEffect(() => {
    const polygon = new TerraDrawPolygonMode({
      keyEvents: { finish: 'Enter', cancel: 'Escape' },
      showCoordinatePoints: true,
      styles: { fillColor: '#ff9139', outlineColor: '#ff9139' },
    });
    polygonMode.current = polygon;
    const moved = () => setMapRevision((n) => n + 1);
    map.on('moveend', moved);
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && editingRef.current) callbacks.current.cancel();
    };
    map.getCanvas().addEventListener('keyup', escape);
    const draw = new TerraDraw({
      adapter: new TerraDrawMapLibreGLAdapter({ map }),
      modes: [
        polygon,
        new TerraDrawSelectMode({
          flags: {
            polygon: {
              feature: {
                draggable: true,
                coordinates: { draggable: true, midpoints: true, deletable: true },
              },
            },
          },
        }),
      ],
      undoRedo: {
        modeLevel: new TerraDrawModeUndoRedo(),
        sessionLevel: new TerraDrawSessionUndoRedo(),
      },
    });
    instance.current = draw;
    draw.on('change', () => {
      const f = draw
        .getSnapshot()
        .find((f) => f.geometry.type === 'Polygon' && f.properties.mode === 'polygon');
      setPoints(
        f?.geometry.type === 'Polygon' ? Math.max(0, f.geometry.coordinates[0].length - 1) : 0,
      );
      setUndoable(draw.canUndo());
    });
    draw.on('finish', (id) => {
      if (draw.getMode() === 'polygon') {
        setClosed(true);
        draw.selectFeature(id);
      }
    });
    return () => {
      map.off('moveend', moved);
      map.getCanvas().removeEventListener('keyup', escape);
      if (draw.enabled) draw.stop();
      callbacks.current.onEditing(false);
      instance.current = null;
    };
  }, [map]);
  function begin(editExisting = false) {
    const draw = instance.current!;
    backup.current = geometry;
    setError('');
    draw.start();
    draw.clear();
    draw.clearUndoRedoHistory();
    setPoints(0);
    setClosed(editExisting);
    if (editExisting && geometry) {
      if (geometry.type !== 'Polygon') {
        setError('Draw a new polygon to replace this imported multi-polygon.');
        draw.stop();
        return;
      }

      const id = crypto.randomUUID();
      const added = draw.addFeatures([
        { type: 'Feature', id, geometry, properties: { mode: 'polygon' } },
      ]);
      if (added.some((a) => !a.valid)) {
        setError('This boundary cannot be edited here. Draw a new polygon or use import.');
        draw.stop();
        return;
      }
      draw.selectFeature(id);
      const bounds = new LngLatBounds();
      geometry.coordinates[0].forEach((c) => bounds.extend([c[0], c[1]]));
      map.fitBounds(bounds, {
        padding: {
          left: Math.min(240, map.getContainer().clientWidth * 0.4),
          right: 70,
          top: 110,
          bottom: 170,
        },
        duration: 0,
      });
    } else draw.setMode('polygon');
    setEditing(true);
    onEditing(true);
    onInvalidate();
    map.getCanvas().focus();
  }
  function cancel() {
    const d = instance.current!;
    d.clear();
    d.stop();
    setEditing(false);
    setClosed(false);
    onEditing(false);
    onRestore();
    setError('');
  }
  async function useBoundary() {
    const feature = instance
      .current!.getSnapshot()
      .find((f) => f.geometry.type === 'Polygon' && f.properties.mode === 'polygon');
    if (!feature) {
      setError('Finish a polygon with at least three corners first.');
      return;
    }
    setSaving(true);
    try {
      if (feature.geometry.type !== 'Polygon') throw Error('Finish a polygon first');
      await onSave(feature as GeoJSON.Feature<GeoJSON.Polygon>);
      if (instance.current?.enabled) instance.current.stop();
      setEditing(false);
      onEditing(false);
      setError('');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }
  const outline = geometry || backup.current;
  const ring = outline?.type === 'Polygon' ? outline.coordinates[0] : outline?.coordinates[0]?.[0];
  return (
    <div
      className="drawing-tools"
      data-tour="drawing"
      data-vertices={JSON.stringify(
        ring?.slice(0, -1).map((c) => {
          const p = map.project([c[0], c[1]]);
          return [p.x, p.y];
        }) || [],
      )}
    >
      <h3>Draw on the map</h3>
      {!editing ? (
        <div className="row">
          <button disabled={saving} onClick={() => begin()}>
            Draw boundary
          </button>
          {geometry && (
            <>
              <button onClick={() => begin(true)}>Edit vertices</button>
              <button
                onClick={() => {
                  onClear();
                  backup.current = null;
                }}
              >
                Clear boundary
              </button>
            </>
          )}
        </div>
      ) : (
        <>
          <p className="hint">
            {closed
              ? 'Drag the corner handles to adjust the boundary. Confirm this boundary to continue.'
              : 'Click at least three corners on the map. Click your first corner again, or choose Finish shape. Press Escape to cancel.'}
          </p>
          <div className="row">
            <button
              disabled={!undoable || saving}
              onClick={() => {
                instance.current!.undo();
                setClosed(instance.current!.getMode() === 'select');
                setUndoable(instance.current!.canUndo());
              }}
            >
              Undo
            </button>
            {!closed && (
              <button
                onClick={() => {
                  polygonMode.current!.onKeyUp({
                    key: 'Enter',
                    heldKeys: [],
                    preventDefault: () => {},
                  });
                }}
              >
                Finish shape
              </button>
            )}
            <button className="primary" disabled={!closed || saving} onClick={useBoundary}>
              {saving ? 'Checking boundary…' : 'Confirm boundary'}
            </button>
            <button disabled={saving} onClick={cancel}>
              Cancel drawing
            </button>
          </div>
          <small>{points} corners · drawing stays in 2D</small>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

const descriptions = {
  effort:
    'How many possible standing locations we test. Thorough and Deep search more places and take longer. They can find better alternatives, but cannot guarantee the best spot.',
  recommendations:
    'How many suggestions to show first. We spread them across your area so nearby variations do not fill the list. Every tested location is still available in All setups.',
  nearby:
    'How far around a standing location we check mapped vegetation. A larger area looks for a broader opening; a smaller area focuses on the immediate surroundings. This does not measure individual branches.',
  trees:
    'Prefer spots with less mapped tree cover around them. Lower values favor more open surroundings. Tree-cover percentage is an average, not the chance of having a clear view. Shrubs can still obstruct you.',
  separation:
    'Keep main suggestions this far apart. Larger values spread suggestions across more of your area and may return fewer spots. Nearby alternatives remain available. Choose zero to allow clusters.',
  proximity:
    'Only test standing locations within this straight-line distance of a mapped road or trail. This is not the walking distance and does not verify access permission.',
  approach:
    'Compare ways from mapped roads or trails to each shortlisted spot. Distance always matters; preferences add penalties for climbing, steepness and vegetation. These are provisional desktop comparisons, not certified routes or walking times.',
  searchArea:
    'The area where we are allowed to search for approaches. Include your shortlisted spots and the roads or trails you might leave from. It is separate from where you want to stand, and does not establish permission.',
  avoidance:
    'Places the calculation must avoid, such as an area you do not want to cross. Draw or import them yourself; HuntMaps does not infer ownership restrictions.',
  weights:
    'Higher values make the calculation work harder to avoid that feature, even if the alternative is longer. Zero removes that preference. Steepness limits still apply.',
  slope:
    'The steepest terrain allowed in the modeled approach. Lower values can eliminate possible paths. A coarse elevation grid can miss cliffs and other hazards.',

  name: 'A name used to identify this scouting analysis later. Use letters, numbers, hyphens or underscores; existing run names cannot be overwritten.',
  radius:
    'How far from each observer the tool checks terrain visibility within the target area. A larger radius can include more distant terrain and require more data and processing; it does not mean you can identify deer at that distance. Default: 2 km.',
  minutes:
    'An existing scoring assumption used to choose portions of a view that could be inspected within a limited time. It can change inspection scores and rankings, but does not change terrain-visible coverage. It is not a recommended stop duration. Default: 30 minutes.',
  count:
    'How many possible standing locations to check before recommending spots. More locations take longer and may find better options. The number of recommendations is separate; all checked locations remain available.',
  budget:
    'Maximum authorized bulk source downloads for this analysis, in megabytes. Review the acquisition estimate before allowing downloads. This is separate from processing/output limits and online basemap browsing. Default: 600 MB.',
};
export function Help({ topic }: { topic: keyof typeof descriptions }) {
  const [open, setOpen] = useState(false),
    pinned = useRef(false),
    wrap = useRef<HTMLSpanElement>(null),
    [position, setPosition] = useState({ left: 0, top: 0 }),
    button = useRef<HTMLButtonElement>(null);
  const place = () => {
    const r = button.current!.getBoundingClientRect();
    setPosition({
      left: Math.max(8, Math.min(r.left, innerWidth - 288)),
      top: Math.min(r.bottom + 6, innerHeight - 300),
    });
  };
  useEffect(() => {
    if (!open) return;
    const close = () => {
      pinned.current = false;
      setOpen(false);
    };
    const outside = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) close();
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);
  return (
    <span
      ref={wrap}
      className="help-wrap"
      onMouseEnter={() => {
        place();
        setOpen(true);
      }}
      onMouseLeave={() => {
        if (!pinned.current) setOpen(false);
      }}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
          pinned.current = false;
          setOpen(false);
        }
      }}
    >
      <button
        ref={button}
        type="button"
        className="help-icon"
        aria-label={`Help: ${topic}`}
        aria-describedby={'help-' + topic}
        aria-expanded={open}
        onFocus={() => {
          place();
          setOpen(true);
        }}
        onClick={() => {
          place();
          pinned.current = !pinned.current;
          setOpen(pinned.current);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            pinned.current = false;
            setOpen(false);
          }
        }}
      >
        ?
      </button>
      <span
        id={'help-' + topic}
        style={position}
        className={'help-popover ' + (open ? 'help-open' : '')}
        role="tooltip"
      >
        {descriptions[topic]}
      </span>
    </span>
  );
}
