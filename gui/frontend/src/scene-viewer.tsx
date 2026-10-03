import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { request } from './http';
import type { Target, SceneReady, ObserverPose, ProfileResult } from './types';
export default function Viewer({
  meta,
  url,
  eye,
  heading,
  look,
  points,
  foliage,
  scenario,
  nearby,
  observer,
  target,
  profile,
  range,
  onTarget,
  onHeading,
  onLook,
  onOpened,
}: {
  meta: SceneReady;
  url: string;
  eye: number;
  heading: number;
  look: number;
  points: boolean;
  foliage: boolean;
  scenario: string;
  nearby: number;
  observer: ObserverPose | null;
  target: Target | null;
  profile: ProfileResult | null;
  range: number;
  onTarget: (v: Target) => void;
  onHeading: (v: number) => void;
  onLook: (v: number) => void;
  onOpened?: () => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    plan = useRef<HTMLCanvasElement>(null),
    runtime = useRef<{
      finePositions: Float32Array;
      contextPositions: Float32Array;
      scene: THREE.Scene;
      markers: THREE.Group;
      ground: number;
      invalidate: () => void;
    } | null>(null),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(true),
    [imageryStatus, setImageryStatus] = useState('Loading cached aerial imagery…');
  const state = useRef({
    eye,
    heading,
    look,
    points,
    foliage,
    scenario,
    nearby,
    observer,
    target,
    profile,
  });
  state.current = {
    eye,
    heading,
    look,
    points,
    foliage,
    scenario,
    nearby,
    observer,
    target,
    profile,
  };
  const callbacks = useRef({ onHeading, onLook });
  callbacks.current = { onHeading, onLook };
  const paintPlan = () => {
    const c = plan.current,
      rt = runtime.current;
    if (!c || !rt) return;
    const ctx = c.getContext('2d')!;
    ctx.clearRect(0, 0, 400, 400);
    ctx.fillStyle = '#e0e4d8';
    ctx.fillRect(0, 0, 400, 400);
    const dots = (v: Float32Array, color: string) => {
      ctx.fillStyle = color;
      for (let i = 0; i < v.length; i += 3 * 4) {
        const x = v[i],
          n = -v[i + 2];
        if (Math.hypot(x, n) > range) continue;
        ctx.fillRect(
          200 + (x / range) * 190,
          200 - (n / range) * 190,
          range === 300 ? 2 : 1.5,
          range === 300 ? 2 : 1.5,
        );
      }
    };
    dots(rt.contextPositions, '#9baf99');
    dots(rt.finePositions, '#577d5c');
    ctx.strokeStyle = '#d0783e';
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.arc(200, 200, (300 / range) * 190, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    const s = state.current;
    ctx.strokeStyle = '#486c35';
    ctx.setLineDash([2, 3]);
    ctx.beginPath();
    ctx.arc(200, 200, (s.nearby / range) * 190, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    const ox = 200 + ((s.observer?.east_m || 0) / range) * 190,
      oy = 200 - ((s.observer?.north_m || 0) / range) * 190;
    const theta = (s.heading * Math.PI) / 180;
    ctx.strokeStyle = '#284e7b';
    ctx.beginPath();
    ctx.moveTo(ox, oy);
    ctx.lineTo(ox + Math.sin(theta) * 30, oy - Math.cos(theta) * 30);
    ctx.stroke();
    ctx.fillStyle = '#233b31';
    ctx.beginPath();
    ctx.arc(ox, oy, 5, 0, Math.PI * 2);
    ctx.fill();
    const dot = (x: number, n: number, color: string) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(200 + (x / range) * 190, 200 - (n / range) * 190, 5, 0, Math.PI * 2);
      ctx.fill();
    };
    if (s.target) {
      dot(s.target.east_m, s.target.north_m, '#d0783e');
      ctx.strokeStyle = '#d0783e';
      ctx.beginPath();
      ctx.moveTo(ox, oy);
      ctx.lineTo(200 + (s.target.east_m / range) * 190, 200 - (s.target.north_m / range) * 190);
      ctx.stroke();
    }
    if (s.foliage && s.profile?.vegetation?.status === 'evaluated') {
      const b = s.profile.vegetation.scenarios[s.scenario].first_intersection;
      if (b) dot(b.east_m, b.north_m, '#8052ad');
    }
    if (s.profile?.first_obstruction) {
      const b = s.profile.first_obstruction;
      dot(b.east_m, b.north_m, '#bd3643');
    }
    ctx.fillStyle = '#233b31';
    ctx.font = '14px sans-serif';
    ctx.fillText('N ↑', 10, 20);
    ctx.fillText('Saved patch at centre · ' + range + ' m radius', 10, 390);
  };
  useEffect(() => {
    let alive = true,
      renderer: THREE.WebGLRenderer | undefined,
      frame = 0;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#dce8ed');
    scene.fog = new THREE.Fog('#dce8ed', 1400, 2200);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.03, 2400),
      objects: THREE.Object3D[] = [];
    setError('');
    setLoading(true);
    const asset = async (name: string, kind: 'f' | 'u' | 'b') => {
      const r = await fetch(url + '/assets/' + name);
      if (!r.ok) throw Error('Scene asset unavailable: ' + name);
      const b = await r.arrayBuffer();
      return kind === 'f'
        ? new Float32Array(b)
        : kind === 'u'
          ? new Uint32Array(b)
          : new Uint8Array(b);
    };
    const validPositions = (v: Float32Array, index: Uint32Array) => {
      const used = new Set<number>();
      for (const i of index) used.add(i);
      return new Float32Array([...used].flatMap((i) => [v[i * 3], v[i * 3 + 1], v[i * 3 + 2]]));
    };
    async function start() {
      const [fv, fi, cv, ci, pv, cls] = await Promise.all([
        asset('fine-vertices.bin', 'f'),
        asset('fine-indices.bin', 'u'),
        asset('context-vertices.bin', 'f'),
        asset('context-indices.bin', 'u'),
        asset('points.bin', 'f'),
        asset('classes.bin', 'b'),
      ]);
      const vc = (await asset(meta.vegetation.centres_file, 'f')) as Float32Array,
        vk = (await asset(meta.vegetation.kinds_file, 'b')) as Uint8Array,
        vcolors = meta.vegetation.meshes
          ? new Uint8Array()
          : ((await asset(meta.vegetation.colors_file, 'b')) as Uint8Array);
      const shape = meta.vegetation.meshes
        ? { identifier: meta.vegetation.geometry_identifier, vertices: [], faces: [] }
        : await request(url + '/assets/' + meta.vegetation.primitive_file);
      if (!alive) return;
      renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      container.current!.replaceChildren(renderer.domElement);
      renderer.domElement.setAttribute('aria-label', 'Eye-height terrain scene');
      renderer.domElement.tabIndex = 0;
      const addMesh = (
        v: Float32Array | Uint32Array | Uint8Array,
        idx: Float32Array | Uint32Array | Uint8Array,
        color: string,
      ) => {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(v, 3));
        geometry.setIndex(new THREE.BufferAttribute(idx, 1));
        geometry.computeVertexNormals();
        const material = new THREE.MeshLambertMaterial({ color, side: THREE.DoubleSide });
        const mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);
        objects.push(mesh);
        return mesh;
      };
      const fine = addMesh(fv, fi, '#819165'),
        context = addMesh(cv, ci, '#9ba38d');
      const uvFor = (mesh: THREE.Mesh, v: Float32Array | Uint32Array | Uint8Array, r: number) => {
        const uv = new Float32Array((v.length / 3) * 2);
        for (let i = 0; i < v.length / 3; i++) {
          uv[i * 2] = (v[i * 3] + r) / (2 * r);
          uv[i * 2 + 1] = (-v[i * 3 + 2] + r) / (2 * r);
        }
        mesh.geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
      };
      uvFor(fine, fv, 300);
      uvFor(context, cv, 2000);
      const pointColors = new Float32Array(pv.length);
      for (let i = 0; i < cls.length; i++) {
        const k = cls[i],
          color = new THREE.Color(
            k >= 3 && k <= 5 ? '#37693c' : k === 1 || k === 0 ? '#dcb664' : '#6b9abd',
          );
        color.toArray(pointColors, i * 3);
      }
      const pg = new THREE.BufferGeometry();
      const cloud = new THREE.Points(
        pg,
        new THREE.PointsMaterial({ vertexColors: true, size: 1.5, sizeAttenuation: false }),
      );
      scene.add(cloud);
      const primitive = new THREE.BufferGeometry();
      primitive.setAttribute(
        'position',
        new THREE.Float32BufferAttribute(shape.vertices.flat(), 3),
      );
      primitive.setIndex(shape.faces.flat());
      primitive.computeVertexNormals();
      let vegetation: THREE.Mesh | undefined,
        lastNearby = 0,
        lastScenario = '',
        requestedKey = '',
        generation = 0,
        firstCentre: number[] = [],
        pointMax = 0,
        draws = 0,
        foliageTriangles = 0,
        samplingInterval = 0;
      const material = new THREE.MeshLambertMaterial({
        color: '#ffffff',
        side: THREE.DoubleSide,
        vertexColors: !!meta.vegetation.meshes,
      });
      const rebuild = async (radius: number, scenarioName: string) => {
        const ticket = ++generation,
          diameter = meta.vegetation.scenarios[scenarioName];
        const selected: number[] = [];
        for (let i = 0; i < vk.length; i++)
          if (Math.hypot(vc[i * 3], vc[i * 3 + 2]) <= radius) selected.push(i);
        let replacement: THREE.Mesh;
        if (meta.vegetation.meshes) {
          const info = meta.vegetation.meshes[String(radius)];
          if (!info || info.unavailable) throw Error(info?.reason || 'Cluster range unavailable');
          const entry = info.scenarios[scenarioName];
          const [v, f, c] = await Promise.all([
            asset(entry.vertices_file, 'f'),
            asset(entry.indices_file, 'u'),
            asset(entry.colors_file, 'b'),
          ]);
          if (!alive || ticket !== generation) return;
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute('position', new THREE.BufferAttribute(v as Float32Array, 3));
          geometry.setIndex(new THREE.BufferAttribute(f as Uint32Array, 1));
          geometry.computeVertexNormals();
          const colors = new Float32Array(c.length);
          for (let i = 0; i < c.length; i += 3)
            new THREE.Color()
              .setRGB(c[i] / 255, c[i + 1] / 255, c[i + 2] / 255, THREE.SRGBColorSpace)
              .toArray(colors, i);
          geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
          replacement = new THREE.Mesh(geometry, material);
          foliageTriangles = entry.triangle_count;
          samplingInterval = info.sampling_interval_m;
        } else {
          if (selected.length > meta.vegetation.display_cap)
            throw Error('Range exceeds lightweight foliage limit; choose a smaller range.');
          const instances = new THREE.InstancedMesh(primitive, material, selected.length),
            matrix = new THREE.Matrix4();
          for (let j = 0; j < selected.length; j++) {
            const i = selected[j];
            matrix.makeScale(diameter / 2, diameter / 2, diameter / 2);
            matrix.setPosition(vc[i * 3], vc[i * 3 + 1], vc[i * 3 + 2]);
            instances.setMatrixAt(j, matrix);
            instances.setColorAt(
              j,
              new THREE.Color().setRGB(
                vcolors[i * 3] / 255,
                vcolors[i * 3 + 1] / 255,
                vcolors[i * 3 + 2] / 255,
                THREE.SRGBColorSpace,
              ),
            );
          }
          instances.instanceMatrix.needsUpdate = true;
          if (instances.instanceColor) instances.instanceColor.needsUpdate = true;
          instances.computeBoundingSphere();
          replacement = instances;
          foliageTriangles = selected.length * 20;
        }
        if (vegetation) {
          scene.remove(vegetation);
          if (meta.vegetation.meshes) vegetation.geometry.dispose();
          else (vegetation as THREE.InstancedMesh).dispose();
        }
        vegetation = replacement;
        scene.add(vegetation);
        lastNearby = radius;
        lastScenario = scenarioName;
        dirty = true;
        setLoading(false);
        setError('');
        firstCentre = selected.length
          ? Array.from(vc.slice(selected[0] * 3, selected[0] * 3 + 3))
          : [];
        const pointIndex: number[] = [];
        for (let i = 0; i < cls.length; i++)
          if (Math.hypot(pv[i * 3], pv[i * 3 + 2]) <= radius) pointIndex.push(i);
        pointMax = pointIndex.reduce(
          (max, i) => Math.max(max, Math.hypot(pv[i * 3], pv[i * 3 + 2])),
          0,
        );
        pg.dispose();
        pg.setAttribute(
          'position',
          new THREE.Float32BufferAttribute(
            pointIndex.flatMap((i) => [pv[i * 3], pv[i * 3 + 1], pv[i * 3 + 2]]),
            3,
          ),
        );
        pg.setAttribute(
          'color',
          new THREE.Float32BufferAttribute(
            pointIndex.flatMap((i) => [
              pointColors[i * 3],
              pointColors[i * 3 + 1],
              pointColors[i * 3 + 2],
            ]),
            3,
          ),
        );
        pg.computeBoundingSphere();
      };
      scene.add(new THREE.HemisphereLight('#f3f7ff', '#5e6550', 2));
      const light = new THREE.DirectionalLight('#fff1d9', 2);
      light.position.set(-200, 500, 150);
      scene.add(light);
      const markers = new THREE.Group();
      scene.add(markers);
      const images = [
        { mesh: fine, image: meta.texture },
        { mesh: context, image: meta.context_texture },
      ];
      let pending = images.filter((v) => v.image).length,
        failed = false,
        dirty = true,
        lastKey = '',
        lastDraw = 0;
      const finishImage = () => {
        dirty = true;
        if (alive)
          setImageryStatus(
            pending
              ? 'Loading cached aerial imagery…'
              : !images.some((v) => v.image)
                ? 'No cached aerial imagery available; shaded terrain retained.'
                : failed
                  ? 'Some imagery unavailable; shaded terrain retained.'
                  : 'Cached aerial imagery shown automatically; shaded terrain marks missing coverage.',
          );
      };
      finishImage();
      for (const { mesh, image } of images) {
        if (!image) continue;
        new THREE.TextureLoader().load(
          url + '/assets/' + image.file,
          (t) => {
            if (!alive) {
              t.dispose();
              return;
            }
            t.colorSpace = THREE.SRGBColorSpace;
            t.anisotropy = Math.min(8, renderer!.capabilities.getMaxAnisotropy());
            // Alpha pixels reveal the existing lit ground, without filling unknown terrain.
            const photo = new THREE.Mesh(
              mesh.geometry.clone(),
              new THREE.MeshBasicMaterial({
                map: t,
                side: THREE.DoubleSide,
                transparent: true,
                depthWrite: false,
                polygonOffset: true,
                polygonOffsetFactor: -1,
                polygonOffsetUnits: -1,
              }),
            );
            scene.add(photo);
            pending--;
            finishImage();
          },
          undefined,
          () => {
            if (alive) {
              failed = true;
              pending--;
              finishImage();
            }
          },
        );
      }
      const observerGround = meta.fine_observer_available
        ? meta.fine_ground_m
        : meta.baseline_ground_m;
      const render = (now = performance.now()) => {
        const host = container.current;
        if (!alive || !renderer || !host) return;
        const s = state.current,
          w = host.clientWidth,
          h = host.clientHeight;
        frame = requestAnimationFrame(render);
        const key = JSON.stringify([
          s.eye,
          s.heading,
          s.look,
          s.points,
          s.foliage,
          s.scenario,
          s.nearby,
          s.observer,
          w,
          h,
          pending,
          failed,
        ]);
        if (!dirty && key === lastKey) return;
        if (now - lastDraw < 1000 / 30) return;
        lastDraw = now;
        lastKey = key;
        dirty = false;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(Math.PI / 6) / camera.aspect));
        camera.updateProjectionMatrix();
        const bearing = (s.heading * Math.PI) / 180,
          tilt = (s.look * Math.PI) / 180;
        camera.position.set(
          s.observer?.east_m || 0,
          (s.observer?.scene_y_m || 0) + s.eye,
          -(s.observer?.north_m || 0),
        );
        camera.lookAt(
          camera.position.x + Math.sin(bearing) * Math.cos(tilt),
          camera.position.y + Math.sin(tilt),
          camera.position.z - Math.cos(bearing) * Math.cos(tilt),
        );
        cloud.visible = s.points;
        const desired = s.nearby + ':' + s.scenario;
        if (requestedKey !== desired) {
          requestedKey = desired;
          setLoading(true);
          rebuild(s.nearby, s.scenario).catch((e) => {
            if (alive) {
              setError(e.message);
              setLoading(false);
            }
          });
        }
        if (vegetation)
          vegetation.visible = s.foliage && lastNearby === s.nearby && lastScenario === s.scenario;
        renderer.render(scene, camera);
        draws++;
        container.current!.setAttribute(
          'data-camera',
          JSON.stringify({
            candidate: meta.candidate,
            east_m: camera.position.x,
            north_m: -camera.position.z,
            eye_m: s.eye,
            scene_camera_y_m: camera.position.y,
            ground_m: s.observer?.ground_m ?? observerGround,
            heading: s.heading,
            look: s.look,
            loaded: !!vegetation && lastNearby === s.nearby && lastScenario === s.scenario,
            imageryPending: pending,
            imageryFailed: failed,
            triangles: renderer.info.render.triangles,
            points: renderer.info.render.points,
            vegetationVisible: vegetation?.visible || false,
            vegetationScenario: lastScenario,
            vegetationSide: meta.vegetation.scenarios[lastScenario],
            vegetationCells: meta.vegetation.nearby_counts[String(lastNearby)] || 0,
            vegetationTriangles: foliageTriangles,
            samplingInterval,
            vegetationFirstCentre: firstCentre,
            vegetationRadius: lastNearby,
            geometryIdentifier: shape.identifier,
            primitiveTriangles: shape.faces.length,
            rawPointRadiusMax: pointMax,
            draws,
          }),
        );
      };
      runtime.current = {
        finePositions: validPositions(fv as Float32Array, fi as Uint32Array),
        contextPositions: validPositions(cv as Float32Array, ci as Uint32Array),
        scene,
        markers,
        ground: observerGround,
        invalidate: () => {
          dirty = true;
        },
      };
      paintPlan();
      render();
      if (alive && container.current) onOpened?.();
    }
    start().catch((e) => {
      if (alive) {
        setError(
          'First-person rendering unavailable: ' +
            e.message +
            '. Return to the map or use the terrain profile.',
        );
        setLoading(false);
      }
    });
    const lost = (e: Event) => {
      e.preventDefault();
      setError('Graphics context lost. Close and reopen the viewer; saved results are unchanged.');
    };
    container.current!.addEventListener('webglcontextlost', lost, true);
    return () => {
      alive = false;
      cancelAnimationFrame(frame);
      container.current?.removeEventListener('webglcontextlost', lost, true);
      scene.traverse((o) => {
        const obj = o as THREE.Mesh;
        if ((obj as THREE.InstancedMesh).isInstancedMesh) (obj as THREE.InstancedMesh).dispose();
        obj.geometry?.dispose();
        const m = obj.material as THREE.Material;
        (m as THREE.MeshLambertMaterial)?.map?.dispose();
        m?.dispose();
      });
      runtime.current = null;
      renderer?.dispose();
      container.current?.replaceChildren();
    };
  }, [url, meta.key]);
  useEffect(() => {
    paintPlan();
    const rt = runtime.current;
    if (!rt) return;
    while (rt.markers.children.length) {
      const o = rt.markers.children[0] as THREE.Mesh;
      o.geometry.dispose();
      (o.material as THREE.Material).dispose();
      rt.markers.remove(o);
    }
    const marker = (x: number, n: number, z: number, color: string) => {
      const o = new THREE.Mesh(
        new THREE.SphereGeometry(0.8, 10, 8),
        new THREE.MeshBasicMaterial({ color }),
      );
      o.position.set(x, z - rt.ground, -n);
      rt.markers.add(o);
    };
    if (foliage && profile?.vegetation?.status === 'evaluated') {
      const b = profile.vegetation.scenarios[scenario].first_intersection;
      if (b) marker(b.east_m, b.north_m, b.line_m, '#8052ad');
    }
    if (profile?.first_obstruction) {
      const b = profile.first_obstruction;
      marker(b.east_m, b.north_m, b.ground_m, '#bd3643');
    }
    if (target && profile?.points?.at(-1)?.ground_m !== null) {
      const z = profile?.points?.at(-1)?.ground_m;
      if (z !== undefined && z !== null) marker(target.east_m, target.north_m, z, '#dc813e');
    }
    rt.invalidate();
  }, [target, profile, range, heading, loading, foliage, scenario, nearby, observer]);
  const drag = useRef<{ x: number; y: number; heading: number; look: number } | null>(null);
  return (
    <>
      <p role="status">{imageryStatus}</p>
      <div
        className="fp-scene"
        ref={container}
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY, heading, look };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (drag.current) {
            onHeading(
              (((drag.current.heading + (e.clientX - drag.current.x) * 0.15) % 360) + 360) % 360,
            );
            onLook(
              Math.max(-70, Math.min(70, drag.current.look - (e.clientY - drag.current.y) * 0.15)),
            );
          }
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
        onKeyDown={(e) => {
          if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
            e.preventDefault();
            if (e.key === 'ArrowLeft') onHeading((heading + 355) % 360);
            if (e.key === 'ArrowRight') onHeading((heading + 5) % 360);
            if (e.key === 'ArrowUp') onLook(Math.min(70, look + 5));
            if (e.key === 'ArrowDown') onLook(Math.max(-70, look - 5));
          }
        }}
        tabIndex={0}
        aria-label="Look around terrain"
      />
      {loading && <p>Loading local scene assets…</p>}
      {error && <p role="alert">{error}</p>}
      <canvas
        ref={plan}
        width="400"
        height="400"
        className="fp-plan"
        aria-label="Choose inspection target on plan map"
        onClick={(e) => {
          const b = e.currentTarget.getBoundingClientRect(),
            x = ((((e.clientX - b.left) / b.width) * 400 - 200) / 190) * range,
            y = ((200 - ((e.clientY - b.top) / b.height) * 400) / 190) * range;
          if (Math.hypot(x, y) <= range) onTarget({ east_m: x, north_m: y });
        }}
      />
      <small>
        Green ring: unchanged 120 m foliage patch centred on the saved setup. Dark marker: current
        observer. Orange ring: 300 m fine-data boundary. Distant terrain: separate coarse context
        with cached photographs where available. Pale gaps mark unknown fine ground and the
        deliberately unjoined 300–320 m source boundary. Orange target, red terrain obstruction and
        purple inferred-vegetation intersection are temporary inspection marks.
      </small>
    </>
  );
}
