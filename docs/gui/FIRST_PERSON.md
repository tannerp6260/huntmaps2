# First-person modeled views

Launch from the project directory:

```sh
./huntmaps-gui
```

Use **Inspect now** on any completed-run waypoint, or prepare selected approaches
as a batch in **Inspect and confirm**. Review lidar acquisitions before downloads;
terrain-only scenes use the existing DEM offline. See [the workflow guide](WORKFLOW.md).
The four prepared Soap Creek scenes remain available unchanged as historical examples.
The detailed lidar rendering notes below describe their recorded pilot implementation.

## Use the view

Drag the view or use arrow keys to look around. The view starts at the saved position, or its committed working update. **Explore nearby positions** allows
you to try stances within 30 feet using the same cached scene; see
[nearby position instructions](NEARBY_OBSERVER.md). Adjust eye height to represent your viewing posture.
The initial direction faces the first saved inspection sector, solely to give a
useful starting orientation; those sectors can include hidden ground.

**Measured above-ground returns**, in the expandable source details, starts disabled: vegetation classes are green,
unclassified returns amber, and other classes blue. You can switch these markers off.
Classified ground and returns within 0.5 m of supported fine ground are excluded;
unknown-ground returns are excluded too. Eligible returns are uniformly thinned to
at most 500,000, with counts and stride disclosed. Markers are 1.5 display pixels,
not representations of physical branch width.
Missing returns are not evidence of an opening. Cached aerial photographs always appear where available;
a top-down image draped on ground can depict treetops at ground level. The 1200-pixel
local texture preserves 0.5 m cached export spacing, while native acquisition was
0.6 m. A separate 2048-pixel distant texture uses cached context imagery. Sharp valid
pixels override coarse imagery; transparency never erases valid underlying coverage.
Missing photographs retain shaded terrain, with an explicit status message. Increasing
texture size does not invent detail absent from the original photographs.

Click a target on the inspection plan map (separate from the nearby-position map), including behind a hill. The profile shows
modeled ground and the inspection line, and identifies the first modeled terrain
obstruction or missing-data intervals. Adjust target height and use **Look toward
inspection target** to orient the camera. Height settings are temporary and do not
alter saved scores or visibility masks.

Fine ground extends 300 m. At the saved observer, the 2 km option uses the original coarse terrain model
for its profile. A moved observer requires a target within the original 300 m fine-ground circle. Fine and baseline calculations remain separate, including their
observer ground references. Pale gaps mark unknown ground and the deliberately
unjoined 300–320 m boundary between fine ground and distant context. They are not
physical openings. Expand source details to inspect dates, support and checksums.

## What fidelity means here

This is a stylized terrain and measured-point inspection tool, not a photograph
or a verified view through trees. The source lidar is from 2019. A 1 m display grid
does not establish 1 m survey accuracy or prove that today's shrubs, deadfall,
snow or tree cover match the model. Vegetation returns do not establish continuous
opaque canopy, and are not used to declare vegetation sightlines clear or blocked.
No field validation, deer probability or legal access is implied.

Ground uses classified, non-withheld lidar returns, one measured return per
0.25 m bin. Local triangulation uses 60 m tiles with 10 m halos and rejects triangles
with edges longer than 5 m. It does not extrapolate into unsupported areas.
Profiles interpolate the same fixed-diagonal triangles shown in the terrain mesh.
Curvature is applied consistently. Recorded vertical references are required;
coarse context is only joined conceptually when compatible NAVD88 references are
available, without inventing a datum adjustment.

## Preparation and recovery

Open **Prepare local fine terrain and lidar**, then **Check source plan**. This
checks catalog metadata and lists source dates, sizes and cached status. The source
download checkbox starts unchecked. **Prepare using cached sources only** cannot
bulk-download missing lidar. Review the plan before explicitly enabling downloads.

The pilot cap is 500 MB of new source payload cumulatively, including bytes from
interrupted attempts. Complete cached sources are checksum-verified. Partial range
receipts support safe continuation; cancellation retains partial files and valid
published scenes. After restart, unfinished jobs become interrupted. Review the
source plan and run preparation again. One preparation or analysis job runs at a
time. The panel shows actual stages, elapsed time and an expandable subprocess log,
without invented percentages.

Preparation has a 1536 MiB address-space limit, 900 seconds per preparation stage
and an 800 MB derived-cache budget. Sources, plans and immutable scene bundles live
under `.gui/first-person`; jobs and logs remain under `.gui/jobs`. Historical runs,
coordinates, terrain controls, scores and reports are not rewritten.

## Setup and checks

The GIS environment and frontend are already installed here. For a fresh checkout,
follow the existing GIS setup, GUI setup in [README](README.md), and install the
isolated lidar readers:

```sh
.venv/bin/python -m pip install --target .cache/vegetation-deps laspy==2.6.1 lazrs==0.7.0
npm ci --prefix gui/frontend --cache /tmp/huntmaps-npm-cache
npm run build --prefix gui/frontend
```

Three.js and its types are pinned in the frontend lockfile. Built assets are served
locally. No account or cloud service is required. WebGL failure leaves the plan-map
and profile available with an explicit renderer error.

```sh
.venv/bin/python -m unittest discover -s tests -q
# With ./huntmaps-gui running:
npm run test:first-person --prefix gui/frontend
node gui/frontend/browser-first-person-preparation-check.mjs
```

See [verification evidence](FIRST_PERSON_VERIFICATION.md).

## Inferred vegetation screening

**Inferred vegetation** starts on with fixed **Dense** thickness and the saved
**120 m** patch. Raw measured dots start off. Nearby movement does not extend
this patch. The earlier adjustable-screening experiment is described in the
linked protocols; those controls are no longer in the main interface.

Full cached lidar supplies1 m cells. Cells with four distinct eligible returns
provide strong support. Cells with two or three returns are included only beside
two original strong cells in the immediate3D neighborhood. There is no recursive
expansion, single-return admission, invented trunk or ground-to-canopy column.
Known object classes other than vegetation and unclassified returns are excluded;
unknown fine ground is excluded. Current pilot support is inferred from
unclassified returns, not identified trees.

Adjacent supported cells form connected rounded surfaces. Sparse/Medium/Dense use
1/1.5/2 m cell widths,0.25 m rounded corners and a1 mm numerical contact margin.
These are assumed thicknesses, not measured forest density or confidence.
Colors sample cached aerial photographs, with green fallback; color is not
vegetation identification. Original box and separate-clump bundles remain controls.

Automatic surface sampling is0.25/0.5/1 m, selecting the finest level that keeps
all three scenarios below500,000 triangles each. The interface displays the chosen
level and reduced-detail notice. No supported cells are silently dropped; a range
that cannot fit is unavailable. This sampling interval is not source accuracy.
Only cells with centres within the selected range contribute; their modeled
surfaces can extend slightly outside it. Farther vegetation remains unevaluated.

Click the plan map to inspect a target. **Experimental vegetation screen** lists
all three assumptions separately from the unchanged terrain result. Purple marks
the selected surface's first intersection. Observer/target containment is shown.
The viewer and numerical check use exactly the same exported vertices and triangles.
A missing intersection does not establish an open field sightline. Unknown ground
remains unknown. Targets beyond300 m use baseline terrain without vegetation checks.

New versioned GUI bundles reference verified prior terrain/photo assets rather
than duplicate them. Failed/cancelled preparation retains prior usable scenes.
The four Soap Creek setups do not establish general performance or field fidelity.

For isolated meshing dependencies (system NumPy/SciPy stay unchanged):

```sh
.venv/bin/python -m pip install --target .cache/vegetation-deps --no-deps scikit-image==0.25.2 lazy-loader==0.4
npm run test:clusters --prefix gui/frontend
```

See the [cluster protocol](FOLIAGE_CLUSTERS_PROTOCOL.md) and
[cluster verification report](FOLIAGE_CLUSTERS_VERIFICATION.md). Historical
[nearby protocol](NEARBY_FOLIAGE_PROTOCOL.md),
[rounded-clump verification](NEARBY_FOLIAGE_VERIFICATION.md) and
[box-model verification](VEGETATION_SCREEN_VERIFICATION.md) remain preserved.
