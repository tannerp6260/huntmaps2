import { useEffect, useRef } from 'react';
import type { Target, SceneReady, ObserverPose } from './types';
export default function PositionMap({
  meta,
  url,
  pose,
  centre,
  onMove,
}: {
  meta: SceneReady;
  url: string;
  pose: ObserverPose | null;
  centre: ObserverPose | null;
  onMove: (p: Target) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    photo = useRef<HTMLImageElement | null>(null);
  const east = centre?.east_m || 0,
    north = centre?.north_m || 0,
    span = east || north ? 40 : 30;
  const px = (x: number) => 200 + ((x - east) / span) * 400,
    py = (y: number) => 200 - ((y - north) / span) * 400;
  const paint = () => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext('2d')!;
    ctx.fillStyle = '#dce3d5';
    ctx.fillRect(0, 0, 400, 400);
    const image = photo.current;
    if (image) {
      const scale = image.width / 600;
      ctx.drawImage(
        image,
        (300 + east - span / 2) * scale,
        (300 - north - span / 2) * scale,
        span * scale,
        span * scale,
        0,
        0,
        400,
        400,
      );
    }
    ctx.strokeStyle = '#fff6b5';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(px(0), py(0), (9.144 / span) * 400, 0, Math.PI * 2);
    ctx.stroke();
    if (east || north) {
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(px(0) - 5, py(0));
      ctx.lineTo(px(0) + 5, py(0));
      ctx.moveTo(px(0), py(0) - 5);
      ctx.lineTo(px(0), py(0) + 5);
      ctx.stroke();
    }
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    ctx.arc(200, 200, 5, 0, Math.PI * 2);
    ctx.fill();
    if (Math.hypot((pose?.east_m || 0) - east, (pose?.north_m || 0) - north) > 1e-8) {
      ctx.fillStyle = '#ce6b29';
      ctx.beginPath();
      ctx.arc(px(pose?.east_m || 0), py(pose?.north_m || 0), 6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = '#fff';
    ctx.font = '14px sans-serif';
    ctx.fillText('N ↑ · ' + span + ' m across', 10, 22);
  };
  const repaint = useRef(paint);
  repaint.current = paint;
  useEffect(() => {
    let alive = true;
    photo.current = null;
    repaint.current();
    if (meta.texture) {
      const im = new Image();
      im.onload = () => {
        if (alive) {
          photo.current = im;
          repaint.current();
        }
      };
      im.src = url + '/assets/' + meta.texture.file;
    }
    return () => {
      alive = false;
    };
  }, [url, meta.key]);
  useEffect(paint, [pose, east, north]);
  return (
    <canvas
      ref={canvas}
      width={400}
      height={400}
      className="fp-position-map"
      data-movement-centre={JSON.stringify({
        east_m: east,
        north_m: north,
        span_m: span,
        boundary_east_m: 0,
        boundary_north_m: 0,
      })}
      aria-label="Choose nearby observer position"
      tabIndex={0}
      onClick={(e) => {
        const b = e.currentTarget.getBoundingClientRect();
        onMove({
          east_m: east + ((e.clientX - b.left) / b.width - 0.5) * span,
          north_m: north + (0.5 - (e.clientY - b.top) / b.height) * span,
        });
      }}
      onKeyDown={(e) => {
        const d: Record<string, Target> = {
          ArrowUp: { east_m: 0, north_m: 0.3048 },
          ArrowDown: { east_m: 0, north_m: -0.3048 },
          ArrowLeft: { east_m: -0.3048, north_m: 0 },
          ArrowRight: { east_m: 0.3048, north_m: 0 },
        };
        if (d[e.key]) {
          e.preventDefault();
          onMove({
            east_m: (pose?.east_m || 0) + d[e.key].east_m,
            north_m: (pose?.north_m || 0) + d[e.key].north_m,
          });
        }
      }}
    />
  );
}
