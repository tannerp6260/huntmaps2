# First-person terrain pilot

Launch from the project directory:

```sh
./huntmaps-gui
```

Select **soap-creek-decision-review-v2**, select A0075, V010, V008 or A0031,
and click **View from this setup**. All four have prepared local scenes on this
computer. Opening them requires no source downloads. This pilot is limited to
these saved setups; it does not add a scoring model or arbitrary-area analysis.

## Use the view

Drag the view or use arrow keys to look around. The observer stays at the exact
saved horizontal position. Adjust eye height to represent your viewing posture.
The initial direction faces the first saved inspection sector, solely to give a
useful starting orientation; those sectors can include hidden ground.

**Measured above-ground returns** starts enabled: vegetation classes are green,
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

Click a target on the small plan map, including behind a hill. The profile shows
modeled ground and the inspection line, and identifies the first modeled terrain
obstruction or missing-data intervals. Adjust target height and use **Look toward
inspection target** to orient the camera. Height settings are temporary and do not
alter saved scores or visibility masks.

Fine ground extends 300 m. The 2 km option uses the original coarse terrain model
for its profile. Fine and baseline calculations remain separate, including their
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
