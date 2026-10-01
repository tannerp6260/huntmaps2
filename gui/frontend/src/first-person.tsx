import {useEffect,useRef,useState} from 'react';
import * as THREE from 'three';
const pilot=['A0075','V010','V008','A0031'];
async function request(path:string,body?:unknown){
 const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-HuntMaps':'local'},body:JSON.stringify(body)});
 if(!r.ok){let v;try{v=(await r.json()).detail}catch{v=r.statusText}throw Error(v)}return r.json();
}
type Target={east_m:number;north_m:number};
function ProfileChart({profile}:{profile:any}){
 if(!profile)return <p>Click the plan map to inspect a target, including ground hidden behind a ridge.</p>;
 const points=profile.points,w=600,h=170,known=points.flatMap((p:any)=>[p.ground_m,p.line_m]).filter((v:any)=>v!==null),lo=Math.min(...known)-1,hi=Math.max(...known)+1;
 if(!known.length)return <p>Incomplete data: ground or endpoint height is unknown along this path.</p>;
 const x=(d:number)=>25+d/profile.distance_m*(w-40),y=(z:number)=>h-20-(z-lo)/(hi-lo)*(h-40);
 let paths:string[]=[],current='';
 for(const p of points){if(p.ground_m===null){if(current)paths.push(current);current=''}else current+=(current?' L':'M')+x(p.distance_m)+','+y(p.ground_m)}
 if(current)paths.push(current);
 const first=points[0],last=points.at(-1),block=profile.first_obstruction;
 return <section className="fp-profile"><h3>Inspection target · {profile.distance_m.toFixed(1)} m</h3><b>{profile.result}</b><p className="hint">{profile.source_label}{profile.borderline?' · Within 5 cm of the modeled line: borderline, not an accuracy guarantee.':''}</p><svg viewBox={'0 0 '+w+' '+h} role="img" aria-label="Ground elevation and inspection sightline profile"><rect width={w} height={h} fill="#eef2e8"/>{paths.map((d,i)=><path key={i} d={d} fill="none" stroke="#38634d" strokeWidth="2"/>)}{first.line_m!==null&&last.line_m!==null&&<path d={`M${x(0)},${y(first.line_m)} L${x(profile.distance_m)},${y(last.line_m)}`} stroke="#cf7540" strokeWidth="2" strokeDasharray="5 3"/>}{block&&<circle cx={x(block.distance_m)} cy={y(block.ground_m)} r="5" fill="#bd3643"/>}<text x="25" y={h-3} fontSize="11">Observer</text><text x={w-75} y={h-3} fontSize="11">Target</text></svg><small>Green: modeled ground. Orange: inspection line. Gaps: unknown ground. {block?'First modeled obstruction at '+block.distance_m.toFixed(1)+' m.':''} {profile.warning}</small></section>
}
function Viewer({meta,url,eye,heading,look,points,target,profile,range,onTarget,onHeading,onLook}:{meta:any;url:string;eye:number;heading:number;look:number;points:boolean;target:Target|null;profile:any;range:number;onTarget:(v:Target)=>void;onHeading:(v:number)=>void;onLook:(v:number)=>void}){
 const container=useRef<HTMLDivElement>(null),plan=useRef<HTMLCanvasElement>(null),runtime=useRef<any>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[imageryStatus,setImageryStatus]=useState('Loading cached aerial imagery…');
 const state=useRef({eye,heading,look,points,target,profile});state.current={eye,heading,look,points,target,profile};
 const callbacks=useRef({onHeading,onLook});callbacks.current={onHeading,onLook};
 const paintPlan=()=>{
  const c=plan.current,rt=runtime.current;if(!c||!rt)return;const ctx=c.getContext('2d')!;ctx.clearRect(0,0,400,400);ctx.fillStyle='#e0e4d8';ctx.fillRect(0,0,400,400);
  const dots=(v:Float32Array,color:string)=>{ctx.fillStyle=color;for(let i=0;i<v.length;i+=3*4){const x=v[i],n=-v[i+2];if(Math.hypot(x,n)>range)continue;ctx.fillRect(200+x/range*190,200-n/range*190,range===300?2:1.5,range===300?2:1.5)}};
  dots(rt.contextPositions,'#9baf99');dots(rt.finePositions,'#577d5c');
  ctx.strokeStyle='#d0783e';ctx.setLineDash([4,3]);ctx.beginPath();ctx.arc(200,200,300/range*190,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
  const s=state.current,theta=s.heading*Math.PI/180;ctx.strokeStyle='#284e7b';ctx.beginPath();ctx.moveTo(200,200);ctx.lineTo(200+Math.sin(theta)*30,200-Math.cos(theta)*30);ctx.stroke();ctx.fillStyle='#233b31';ctx.beginPath();ctx.arc(200,200,5,0,Math.PI*2);ctx.fill();
  const dot=(x:number,n:number,color:string)=>{ctx.fillStyle=color;ctx.beginPath();ctx.arc(200+x/range*190,200-n/range*190,5,0,Math.PI*2);ctx.fill()};
  if(s.target){dot(s.target.east_m,s.target.north_m,'#d0783e');ctx.strokeStyle='#d0783e';ctx.beginPath();ctx.moveTo(200,200);ctx.lineTo(200+s.target.east_m/range*190,200-s.target.north_m/range*190);ctx.stroke()}
  if(s.profile?.first_obstruction){const b=s.profile.first_obstruction;dot(b.east_m,b.north_m,'#bd3643')}
  ctx.fillStyle='#233b31';ctx.font='14px sans-serif';ctx.fillText('N ↑',10,20);ctx.fillText('Observer at centre · '+range+' m radius',10,390);
 };
 useEffect(()=>{
  let alive=true,renderer:THREE.WebGLRenderer|undefined,frame=0;
  const scene=new THREE.Scene();scene.background=new THREE.Color('#dce8ed');scene.fog=new THREE.Fog('#dce8ed',1400,2200);
  const camera=new THREE.PerspectiveCamera(45,1,.03,2400),objects:THREE.Object3D[]=[];
  setError('');setLoading(true);
  const asset=async(name:string,kind:'f'|'u'|'b')=>{const r=await fetch(url+'/assets/'+name);if(!r.ok)throw Error('Scene asset unavailable: '+name);const b=await r.arrayBuffer();return kind==='f'?new Float32Array(b):kind==='u'?new Uint32Array(b):new Uint8Array(b)};
  const validPositions=(v:Float32Array,index:Uint32Array)=>{const used=new Set<number>();for(const i of index)used.add(i);return new Float32Array([...used].flatMap(i=>[v[i*3],v[i*3+1],v[i*3+2]]))};
  async function start(){
   const [fv,fi,cv,ci,pv,cls]=await Promise.all([asset('fine-vertices.bin','f'),asset('fine-indices.bin','u'),asset('context-vertices.bin','f'),asset('context-indices.bin','u'),asset('points.bin','f'),asset('classes.bin','b')]);
   if(!alive)return;
   renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
   container.current!.replaceChildren(renderer.domElement);renderer.domElement.setAttribute('aria-label','Eye-height terrain scene');renderer.domElement.tabIndex=0;
   const addMesh=(v:any,idx:any,color:string)=>{
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(v,3));geometry.setIndex(new THREE.BufferAttribute(idx,1));geometry.computeVertexNormals();
    const material=new THREE.MeshLambertMaterial({color,side:THREE.DoubleSide});
    const mesh=new THREE.Mesh(geometry,material);scene.add(mesh);objects.push(mesh);return mesh;
   };
   const fine=addMesh(fv,fi,'#819165'),context=addMesh(cv,ci,'#9ba38d');
   const uvFor=(mesh:any,v:any,r:number)=>{const uv=new Float32Array(v.length/3*2);for(let i=0;i<v.length/3;i++){uv[i*2]=(v[i*3]+r)/(2*r);uv[i*2+1]=(-v[i*3+2]+r)/(2*r)}mesh.geometry.setAttribute('uv',new THREE.BufferAttribute(uv,2))};
   uvFor(fine,fv,300);uvFor(context,cv,2000);
   const colors=new Float32Array(pv.length);for(let i=0;i<cls.length;i++){const k=cls[i],color=new THREE.Color(k===2?'#b8aea0':k>=3&&k<=5?'#37693c':k===1||k===0?'#dcb664':'#6b9abd');color.toArray(colors,i*3)}
   const pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.BufferAttribute(pv,3));pg.setAttribute('color',new THREE.BufferAttribute(colors,3));
   const cloud=new THREE.Points(pg,new THREE.PointsMaterial({vertexColors:true,size:1.5,sizeAttenuation:false}));scene.add(cloud);objects.push(cloud);
   scene.add(new THREE.HemisphereLight('#f3f7ff','#5e6550',2));const light=new THREE.DirectionalLight('#fff1d9',2);light.position.set(-200,500,150);scene.add(light);
   const markers=new THREE.Group();scene.add(markers);
   const images=[{mesh:fine,image:meta.texture},{mesh:context,image:meta.context_texture}];
   let pending=images.filter(v=>v.image).length,failed=false;
   const finishImage=()=>{if(alive)setImageryStatus(pending?'Loading cached aerial imagery…':!images.some(v=>v.image)?'No cached aerial imagery available; shaded terrain retained.':failed?'Some imagery unavailable; shaded terrain retained.':'Cached aerial imagery shown automatically; shaded terrain marks missing coverage.')};
   finishImage();
   for(const {mesh,image} of images){if(!image)continue;new THREE.TextureLoader().load(url+'/assets/'+image.file,t=>{
    if(!alive){t.dispose();return}t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=Math.min(8,renderer!.capabilities.getMaxAnisotropy());
    // Alpha pixels reveal the existing lit ground, without filling unknown terrain.
    const photo=new THREE.Mesh(mesh.geometry.clone(),new THREE.MeshBasicMaterial({map:t,side:THREE.DoubleSide,transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-1}));scene.add(photo);
    pending--;finishImage();
   },undefined,()=>{if(alive){failed=true;pending--;finishImage()}})}
   const observerGround=meta.fine_observer_available?meta.fine_ground_m:meta.baseline_ground_m;
   const render=()=>{
    if(!alive||!renderer)return;
    const s=state.current,w=container.current!.clientWidth,h=container.current!.clientHeight;
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.fov=THREE.MathUtils.radToDeg(2*Math.atan(Math.tan(Math.PI/6)/camera.aspect));camera.updateProjectionMatrix();
    const bearing=s.heading*Math.PI/180,tilt=s.look*Math.PI/180;
    camera.position.set(0,s.eye,0);camera.lookAt(Math.sin(bearing)*Math.cos(tilt),s.eye+Math.sin(tilt),-Math.cos(bearing)*Math.cos(tilt));
    cloud.visible=s.points;
    renderer.render(scene,camera);
    container.current!.setAttribute('data-camera',JSON.stringify({candidate:meta.candidate,east_m:camera.position.x,north_m:-camera.position.z,eye_m:camera.position.y,ground_m:observerGround,heading:s.heading,look:s.look,loaded:true,imageryPending:pending,imageryFailed:failed,triangles:renderer.info.render.triangles,points:renderer.info.render.points}));
    frame=requestAnimationFrame(render);
   };
   runtime.current={finePositions:validPositions(fv as Float32Array,fi as Uint32Array),contextPositions:validPositions(cv as Float32Array,ci as Uint32Array),scene,markers,ground:observerGround};paintPlan();render();setLoading(false);
  }
  start().catch(e=>{if(alive){setError('First-person rendering unavailable: '+e.message+'. Return to the map or use the terrain profile.');setLoading(false)}});
  const lost=(e:Event)=>{e.preventDefault();setError('Graphics context lost. Close and reopen the viewer; saved results are unchanged.')};
  container.current!.addEventListener('webglcontextlost',lost,true);
  return()=>{alive=false;cancelAnimationFrame(frame);container.current?.removeEventListener('webglcontextlost',lost,true);scene.traverse(o=>{const obj=o as THREE.Mesh;obj.geometry?.dispose();const m=obj.material as THREE.Material;(m as any)?.map?.dispose();m?.dispose()});runtime.current=null;renderer?.dispose();container.current?.replaceChildren()};
 },[url,meta.key]);
 useEffect(()=>{paintPlan();const rt=runtime.current;if(!rt)return;while(rt.markers.children.length){const o=rt.markers.children[0] as THREE.Mesh;o.geometry.dispose();(o.material as THREE.Material).dispose();rt.markers.remove(o)}
  const marker=(x:number,n:number,z:number,color:string)=>{const o=new THREE.Mesh(new THREE.SphereGeometry(.8,10,8),new THREE.MeshBasicMaterial({color}));o.position.set(x,z-rt.ground,-n);rt.markers.add(o)};
  if(profile?.first_obstruction){const b=profile.first_obstruction;marker(b.east_m,b.north_m,b.ground_m,'#bd3643')}
  if(target&&profile?.points.at(-1)?.ground_m!==null){const z=profile?.points.at(-1)?.ground_m;if(z!==undefined)marker(target.east_m,target.north_m,z,'#dc813e')}
 },[target,profile,range,heading,loading]);
 const drag=useRef<{x:number;y:number;heading:number;look:number}|null>(null);
 return <><p role="status">{imageryStatus}</p><div className="fp-scene" ref={container} onPointerDown={e=>{drag.current={x:e.clientX,y:e.clientY,heading,look};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(drag.current){onHeading(((drag.current.heading+(e.clientX-drag.current.x)*.15)%360+360)%360);onLook(Math.max(-70,Math.min(70,drag.current.look-(e.clientY-drag.current.y)*.15)))}}} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();if(e.key==='ArrowLeft')onHeading((heading+355)%360);if(e.key==='ArrowRight')onHeading((heading+5)%360);if(e.key==='ArrowUp')onLook(Math.min(70,look+5));if(e.key==='ArrowDown')onLook(Math.max(-70,look-5))}}} tabIndex={0} aria-label="Look around terrain"/>{loading&&<p>Loading local scene assets…</p>}{error&&<p role="alert">{error}</p>}<canvas ref={plan} width="400" height="400" className="fp-plan" aria-label="Choose inspection target on plan map" onClick={e=>{const b=e.currentTarget.getBoundingClientRect(),x=((e.clientX-b.left)/b.width*400-200)/190*range,y=(200-(e.clientY-b.top)/b.height*400)/190*range;if(Math.hypot(x,y)<=range)onTarget({east_m:x,north_m:y})}}/><small>Orange ring: 300 m fine-data boundary. Distant terrain: separate coarse context with cached photographs where available. Pale gaps mark unknown fine ground and the deliberately unjoined 300–320 m source boundary. Orange target and red obstruction are temporary inspection marks.</small></>;
}
export default function FirstPerson({runId,cid,onSelect,onClose}:{runId:string;cid:string;onSelect:(id:string)=>void;onClose:()=>void}){
 const [meta,setMeta]=useState<any>(null),[error,setError]=useState(''),[eye,setEye]=useState(1.7),[height,setHeight]=useState(.8),[heading,setHeading]=useState(0),[look,setLook]=useState(0),[points,setPoints]=useState(true),[target,setTarget]=useState<Target|null>(null),[profile,setProfile]=useState<any>(null),[range,setRange]=useState(300);
 const completedJob=useRef(''),dialog=useRef<HTMLElement>(null);
 useEffect(()=>{const before=document.activeElement as HTMLElement|null;dialog.current?.querySelector<HTMLButtonElement>('button')?.focus();const key=(e:KeyboardEvent)=>{if(e.key==='Escape'){e.preventDefault();onClose()}if(e.key==='Tab'){const list=Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),summary,[tabindex="0"]')||[]).filter(el=>el.getClientRects().length);const first=list[0],last=list.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}};document.addEventListener('keydown',key);return()=>{document.removeEventListener('keydown',key);before?.focus()}},[]);
 const [planId,setPlanId]=useState(()=>localStorage.getItem('huntmaps-first-person-plan')||''),[plan,setPlan]=useState<any>(null),[job,setJob]=useState<any>(null),[allow,setAllow]=useState(false),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0),[sceneVersion,setSceneVersion]=useState(0);
 const url='/api/runs/'+runId+'/first-person/'+cid;
 useEffect(()=>{let alive=true;setMeta(null);setError('');setTarget(null);setProfile(null);setHeading(0);setLook(0);request(url).then(v=>{if(alive){setMeta(v);setHeading(v.initial_bearing_deg||0)}}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[url,sceneVersion]);
 useEffect(()=>{if(!planId)return;localStorage.setItem('huntmaps-first-person-plan',planId);let alive=true;const poll=async()=>{try{const [p,j]=await Promise.all([request('/api/first-person/plans/'+planId),request('/api/jobs')]);if(!alive)return;setPlan(p);const current=j.find((v:any)=>v.plan===planId);setJob(current||null);if(current&&['complete','failed'].includes(current.status)&&current.kind==='first-person-prepare'&&completedJob.current!==current.id){completedJob.current=current.id;setSceneVersion(v=>v+1)}}catch(e:any){if(alive)setError(e.message)}};poll();const timer=setInterval(poll,1800);return()=>{alive=false;clearInterval(timer)}},[planId,refresh]);
 useEffect(()=>{if(!target||meta?.status!=='ready')return;let alive=true;const timer=setTimeout(()=>request(url+'/profile',{...target,eye_m:eye,target_height_m:height}).then(v=>{if(alive)setProfile(v)}).catch(e=>{if(alive)setError(e.message)}),150);return()=>{alive=false;clearTimeout(timer)}},[url,target,eye,height,meta?.key]);
 const action=async(path:string,body:unknown)=>{setBusy(true);setError('');try{const j=await request(path,body);setPlanId(j.plan);setJob(j);setRefresh(v=>v+1);setAllow(false)}catch(e:any){setError(e.message)}finally{setBusy(false)}};
 const active=job&&['running','cancelling'].includes(job.status);
 return <div className="fp-backdrop"><section ref={dialog} className="fp-dialog" role="dialog" aria-modal="true" aria-label="First-person terrain pilot"><div className="section-title"><h2>View from {cid} · Soap Creek pilot</h2><button onClick={onClose}>Return to map</button></div><p>Terrain-model preview, not a photograph or verified view through trees. Observer location stays fixed. Fine ground covers up to 300 m; distant terrain is coarse context.</p><label>Saved setup<select aria-label="First-person setup" value={cid} onChange={e=>onSelect(e.target.value)}>{pilot.map(v=><option key={v}>{v}</option>)}</select></label>
 {error&&<div role="alert">{error}<button onClick={()=>{setError('');setSceneVersion(v=>v+1)}}>Reload scene</button></div>}
 <details open={meta?.status==='unprepared'} className="fp-preparation"><summary>Prepare local fine terrain and lidar</summary><p>One shared pilot preparation for all four setups. Existing scores and outputs stay unchanged. New source downloads are capped at 500 MB; cached sources are reused.</p><button disabled={busy||active} onClick={()=>action('/api/first-person/plans',{})}>Check source plan</button>
 {plan&&<><p>{plan.prepared?(plan.estimated_new_bytes/1e6).toFixed(1)+' MB estimated new downloads':'Checking catalog metadata…'} · {(plan.already_received_bytes||0)/1e6} MB previously transferred</p>{plan.sources?.map((s:any)=><p key={s.key}><b>{s.cached?'Cached':'New source'}</b> · {s.title} · {(s.bytes/1e6).toFixed(1)} MB · {s.acquisition_date}</p>)}{plan.errors?.map((v:string)=><p className="error" key={v}>{v}</p>)}<p>{plan.source_note}</p><label><input type="checkbox" checked={allow} disabled={active||!plan.prepared||!!plan.errors?.length} onChange={e=>setAllow(e.target.checked)}/>Allow this plan’s source downloads within 500 MB</label><button disabled={busy||active||!plan.prepared} onClick={()=>action('/api/first-person/plans/'+planId+'/start',{download:allow})}>{allow?'Download and prepare pilot':'Prepare using cached sources only'}</button></>}
 {job&&<div className="fp-job" role="status"><b>{job.status}</b> · {job.stage} · {job.elapsed_s||0} s {active&&<button disabled={job.status==='cancelling'} onClick={()=>request('/api/jobs/'+job.id+'/cancel',{}).then(()=>setRefresh(v=>v+1)).catch(e=>{setError(e.message);setRefresh(v=>v+1)})}>Cancel preparation</button>}{job.error&&<p>{job.error}</p>}<details><summary>Actual preparation log</summary><pre>{job.logs}</pre></details></div>}</details>
 {meta?.status==='ready'&&meta.candidate===cid&&<><div className="fp-controls"><label>Eye height: {eye.toFixed(1)} m<input aria-label="First-person eye height" type="range" min=".8" max="2.2" step=".1" value={eye} onChange={e=>setEye(+e.target.value)}/></label><label>Heading: {heading.toFixed(0)}°<input aria-label="First-person heading" type="range" min="0" max="359" value={heading} onChange={e=>setHeading(+e.target.value)}/></label><label>Look up/down: {look.toFixed(0)}°<input aria-label="First-person look angle" type="range" min="-70" max="70" value={look} onChange={e=>setLook(+e.target.value)}/></label><button onClick={()=>{setHeading(meta.initial_bearing_deg||0);setLook(0);setEye(1.7)}}>Reset view</button><label><input type="checkbox" checked={points} onChange={e=>setPoints(e.target.checked)}/>Measured above-ground returns</label></div>
 <p className="notice">{meta.fine_observer_available?'Local lidar-derived ground':'Baseline-only preview: fine ground at the observer is unknown.'} · {(meta.coverage_fraction*100).toFixed(1)}% of the 300 m circle has supported fine ground · {meta.acquisition_date}. {points?'Above-ground returns: green vegetation-class, amber unclassified, blue other classes. Missing returns do not mean empty space.':''} Aerial imagery is always shown where available; photographed canopy lies on ground, not reconstructed trees. Marker size is a display aid; amber returns are unclassified, not confirmed vegetation.</p>
 <div className="fp-workspace"><div><Viewer meta={meta} url={url} eye={eye} heading={heading} look={look} points={points} target={target} profile={profile} range={range} onTarget={setTarget} onHeading={setHeading} onLook={setLook}/></div><aside><h3>Inspect a sightline</h3><p>Drag the scene or use arrow keys to look around. Choose a target on the plan map to inspect terrain hidden behind a rise.</p><label>Plan map radius<select aria-label="Inspection map radius" value={range} onChange={e=>setRange(+e.target.value)}><option value={300}>300 m — fine ground</option><option value={2000}>2 km — separate baseline profile</option></select></label><label>Assumed target height: {height.toFixed(1)} m<input aria-label="Inspection target height" type="range" min="0" max="2.5" step=".1" value={height} onChange={e=>setHeight(+e.target.value)}/></label><ProfileChart profile={profile}/>{target&&profile&&profile?.points[0]?.line_m!==null&&profile?.points.at(-1)?.line_m!==null&&<button onClick={()=>{setHeading((Math.atan2(target.east_m,target.north_m)*180/Math.PI+360)%360);setLook(Math.max(-70,Math.min(70,Math.atan2(profile.points.at(-1).line_m-profile.points[0].line_m,profile.distance_m)*180/Math.PI)))}}>Look toward inspection target</button>}<details><summary>Sources, coverage and technical details</summary><p>{meta.initial_facing_note}</p><p>{meta.ground_interpolation}</p><p>{meta.vertical_note}</p><p>{meta.warning}</p><p>Display: {meta.display_point_count.toLocaleString()} of {meta.above_ground_point_count.toLocaleString()} eligible above-ground returns ({meta.raw_local_point_count.toLocaleString()} total local returns); stride {meta.display_stride}. {meta.point_filter}. Local photo spacing: {meta.texture?.pixel_spacing_m} m; context photo spacing: {meta.context_texture?.pixel_spacing_m?.toFixed(2)} m. Underlying acquisition: {meta.texture?.native_resolution_m?.join(", ")} m. Numerical borderline margin: 5 cm, not measurement accuracy.</p><pre>{JSON.stringify({observer:meta.observer,vertical_reference:meta.vertical_reference,sources:meta.sources,classification_counts:meta.classification_counts,maximum_support_distance_m:meta.maximum_support_distance_m},null,2)}</pre></details></aside></div></>}
 {meta?.status==='unprepared'&&<p>No fine scene has been prepared yet. Check the source plan above; acquisition starts only through its explicit preparation action.</p>}
 </section></div>;
}
