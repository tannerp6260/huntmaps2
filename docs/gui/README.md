# HuntMaps2 local scouting desk

Current interface: [Find → Approach → Inspect → Save](UI_REDESIGN.md).
Workflow evidence and requirements: [Find, reach and inspect setups](WORKFLOW.md).

Current guides: [setup](SETUP.md), this user guide, and
[maintenance/testing](MAINTENANCE.md). Experimental protocols and `*_VERIFICATION.md`
files in this folder record historical evidence; their original claims and limits
remain unchanged. [Cleanup verification](CLEANUP_VERIFICATION.md) records the current
acceptance checks.


From this Ubuntu workspace, launch the installed application:

```sh
./huntmaps-gui
```

It opens `http://127.0.0.1:8765` in your browser. Keep the terminal open; Ctrl+C
stops the server and cancels its active process group. For a different local port,
use `./huntmaps-gui --port 8766`. `--no-browser` starts only the server.
You can restart immediately after Ctrl+C. If the port is still occupied by a
running server, stop that instance in its terminal or choose another port.

The existing `scout` file is hashed into completed-run manifests. It remains
byte-identical; the GUI has its own launcher rather than invalidating historical
verification. Existing CLI commands continue to work.

## First review

1. Open a completed run in the header. The initial Soap Creek neighborhood review
   is explicitly experimental; choose **soap-creek-v1 · baseline** to see the
   unchanged normal analysis. Opening results starts no analysis or source acquisition; enabled online imagery requests display tiles.
2. Expanded-search runs open **Recommended setups**, ordered by visible terrain matching your saved criteria, with spacing between suggestions. **All evaluated setups** retains every calculated location, ordered by terrain-visible area. Existing runs retain their original results. Original
   engine ranking and the historical leading collection remain optional. Select A0075, V010 or V008 to inspect
   coordinates, parent relationship, target area, cover breakdown and uncertainty.
3. **Compare** selects up to three. Colored layers retain each individual saved
   mask. The checkboxes beside their names show/hide individual views without
   removing the comparison. Shared terrain appears below the map. **Setup close-up**
   zooms into the active observer. Saved inspection sectors include hidden terrain;
   tree classes apply to the active setup only.
4. **Shortlist** or **Dismiss** a setup. **Plan approach** opens the focused setup.
   Draw and confirm a boundary containing that setup and a mapped road or trail,
   check the boundary, then explicitly **Calculate approaches**. Select an
   alternative, prepare a view and confirm through Approach → Inspect → Save. Legacy review
   annotations and notes remain separate from these workflow decisions.
5. Check **Export** for the observer setups you want, then click GPX or KML.
   Export coordinates are the saved observer positions, with meaningful names and
   your notes. Target-opening coordinates are deliberately excluded. These are
   provisional waypoints, not navigation routes.

**Prepare coverage** prepares the next 5, 10 or 20 setups in the displayed order,
including the current setup. Ten is the default. Wait for **Coverage prepared**,
then select each setup normally. Preparation can be cancelled and resumed; completed
tiles remain cached. It pauses during map movement, 3D viewing and other jobs.
Zooming beyond the prepared view or cache eviction can require more loading.
The map shows a prominent loading card while a selected view's shading is being
prepared and a retry button if it fails. **Compare** remains a separate display.

Each shortlisted setup gets its own approach boundary and decision. The setup
counter is a review queue. A new setup starts with no boundary; importing or copying
another boundary is an advanced, explicit choice requiring confirmation for that
setup. Boundary checks explain missing mapped departures before calculation.
Terrain constraints can still prevent a path. **Terrain I want to see** belongs to
Find; approach preferences describe climbing, steepness, vegetation and the hard
slope limit. See [coverage and approach verification](COVERAGE_APPROACH_FLOW_2026-10-10.md).

Map controls include zoom, compass rotation/reset, yard scale, imagery and
visibility toggles, opacity sliders, legend and whole-area/close-up buttons.
Online imagery fills gaps behind saved aerial clips by default, fetching visible USGS National Map tiles as you pan and zoom. Turn off **Online imagery — fill gaps** for entirely local viewing; this preference persists in your browser. Provider attribution appears on the map. Online acquisition dates vary and tiles are browsing context, separate from analysis sources and its download cap. There is no offline tile pack. Saved imagery dates and native/export resolutions remain in the source drawer. When online imagery fails, the map keeps cached imagery and local hillshade where covered, with a retry control. No PDF screenshots are used as map layers.

## New scouting area

Choose **New area**, import GeoJSON/KML/KMZ, explicitly select a polygon
(or deliberately combine all), and inspect the orange observer boundary. Historical
candidate layers are hidden in this preview. Cached context belongs to the open
run; it is not proof that new-area data are available.

Review the suggested run name, view distance, locations to test and top spots to recommend.
The explanation above settings introduces these controls. Choose target terrain before calculating; suggestion spacing and surrounding vegetation settings are under Advanced settings. Roads and trails are included by default; proximity sampling starts at 0.5 miles. Inspection minutes are a calculation detail: new GUI runs
use 30; recovered runs retain saved values. Check metadata before choosing the
reviewed download allowance.
The existing hunt context is inherited from the transfer template: GMU54 second
rifle 2026, personal dates unset and light assumptions hypothetical. This small form
does not introduce new coefficients or permit arbitrary shell commands.

Click **Review downloads**. The unchanged owner CLI checks cached data and
can request catalog metadata (up to its existing 5 MB response limit). It does not
perform bulk downloads. Review source items, estimate, cap, errors and required-data
text in the interface. **Generate setups** approves the displayed plan and allowance; there is no separate checkbox and preparing a plan never starts bulk transfer. The existing streaming cap and validation remain authoritative.
If the estimate exceeds the cap or source planning fails, analysis remains blocked.

Preparation also checks project-local raw downloads from previous normal runs and
source caches. Compatible USGS vegetation must match the requested 2023 product,
30 m request and interpolation; CPW responses must match the seasonal layer and
complete query semantics and cover the current analysis extent. Checksums, raster
readability and footprint are verified before importing exact bytes into `.gui/sources`.
Configured sources take precedence; managed imports are preferred over other raw
caches, then paths are considered in sorted order. Unknown vegetation remains unknown.
Original files and prior results are never edited, and later reuse needs only the managed
copy. Source copies retain the 20 GiB free-space reserve and are outside disposable
display-cache cleanup because saved analyses can reference them.

After installing this update, restart HuntMaps2 and use **Refresh plan / recover
partial preparation** on an existing failed plan. Review **Verified local sources**
for original product/retrieval dates and source links, then **Generate setups**.
Changed source selections require a fresh review. Local copies cost no new download
bytes; uncovered areas still need the source services. This does not update old
vegetation products to current conditions or guarantee legal access.

Click **Generate setups**. One background process group runs at a time.
The job panel shows elapsed time, actual wrapper stages, newly saved engine artifacts,
last engine record, and an expandable real subprocess log. Counts of saved masks are
counts, not invented completion percentages. Completed results appear in the run
selector; **Open results** opens them.

Cancellation sends TERM and then KILL to the complete process group, including
children. Partial files remain. After restart, unfinished job records become
**interrupted**, with process identity/boot checks before cleaning up surviving
workers. **Review / resume plan** and **Refresh plan** recover GUI-owned incomplete
runs; completed results cannot be overwritten. A changed acquisition plan must be
prepared/reviewed again before downloads. After a descriptor/source failure, repair
the named source or choose a fresh run; the GUI does not bypass checksum validation.

Existing budget defaults remain: 3 million raster cells, 1536 MiB analysis address
space, 900 seconds per engine batch and 800 MB output budget. GUI transfer allowances
are suggested after metadata review, with no fixed upper MB cap; storage checks
retain 20 GiB free. The form supports radius 500–3000 m in 500 m steps and
12–5,000 locations in expanded GUI search, with a separate 1–200 recommendation count. The default is 150 locations and 20 recommendations. Choose target terrain before calculating; nearby standing-cover eligibility is optional and initially off. Coarse mapping cannot guarantee a clearing. New GUI runs retain the 30-minute engine assumption;
recovered runs preserve saved settings. The engine can reject areas
whose buffered grid or source support exceeds its limits.

## Installation and development

Dependencies are already installed and frontend assets built on this computer.
For a fresh workspace with the GIS environment from START_HERE.md:

```sh
.venv/bin/python -m pip install -r gui/requirements.txt
npm ci --prefix gui/frontend --cache /tmp/huntmaps-npm-cache
npm run build --prefix gui/frontend
./huntmaps-gui
```

Node 22 was used. Frontend dependencies stay under `gui/frontend/node_modules` and
are locked by `package-lock.json`; production serves only built local files, including
MapLibre's bundled worker. No Vite dev server is needed. Backend dependencies install
into the existing GIS venv, never system Python. `SCOUT_PYTHON` can override the
interpreter as with the CLI. No external basemap, cloud hosting or account is used.

Implementation: `huntmaps_gui/catalog.py` reads completed runs; `tiles.py` serves
GDAL Web Mercator tiles; `server.py` provides bounded local APIs; `jobs.py` manages
process groups; `worker.py` invokes unchanged owner commands using argument lists.
`gui/frontend/src` contains React/TypeScript and MapLibre. Requests bind only to
localhost; mutation requests require the local app header and same-origin checks.

State lives under `.gui/`: imported originals, plans, durable job records/logs,
annotations, derived raster/tile caches and verification evidence. New baseline
outputs go under `results/NEW_NAME` through the original CLI. The GUI neither writes
nor moves historical results. To reclaim display cache space, stop the application
and remove only `.gui/cache`; do not remove `.gui/fixtures` if you want to reopen the
synthetic verification run, whose source descriptors refer there.

## Verification and limits

Run the isolated offline acceptance suite:

```sh
./gui/check
```

The suite starts dedicated localhost servers, uses temporary GUI state and writable
workspaces, and audits protected sources and the owner's records. It can run while
the normal app is open. Diagnostics and screenshots remain in the printed temporary
directory. See [maintenance and testing](MAINTENANCE.md) and
[cleanup acceptance evidence](CLEANUP_VERIFICATION.md). Earlier
[prototype verification evidence](VERIFICATION.md) remains historical.

Supported result adapters are completed normal `results/*/scouting.json` owner runs
and the specific saved Soap Creek decision review. Older research archives under
`runs/` and arbitrary third-party GIS projects are not presented as normal runs.
The GUI does not generate arbitrary-area experimental vegetation results. Baseline
new-area acquisition still has the existing single-tile DEM/Colorado seasonal-source
limits; mosaics/custom sources need assistance outside this simple form. Imagery,
legal entry, permissions, current restrictions and safe approach are not acquired
by normal runs. Cached 2019 imagery/2023 vegetation can differ from present conditions.
No new coverage scoring model, automatic grouping, timed itinerary or field
validation is claimed. Optional independent approach comparisons use the separately
documented cost service below. Map tiles resample for display; saved cell counts, not screen
pixels or Web Mercator surface area, define reported terrain-visible area.

## In-app training

Choose **Learn** for the optional hands-on Soap Creek compare/export lesson,
new-area boundary lesson, and hunter’s task guide. Practice reviews stay separate
from real annotations. See [training instructions](TRAINING.md).

## Drawing and 3D terrain

New baseline run offers **Draw on map** or **Import file**. Drawing validates the
user's exact polygon through the existing import adapter. The revised learning
path teaches reviewing saved results first, then drawing a separate practice area.
Question marks explain the supported settings; resource details are expandable.

Saved-result review offers **3D terrain**, tilt/rotation and a 2D reset. It uses
local saved elevation and imagery, with no extra downloads or change to scoring.
It is terrain context, not vegetation geometry or a field sightline simulation.
Only complete valid local DEM coverage is supported. See [training](TRAINING.md).

## Clearer settings

**Locations to test** controls the calculation budget across your polygon; **Top spots to recommend** controls the initial suggestions. Open **Advanced settings → How this works** for spatial and terrain sampling details. Small areas use denser broad sampling down to grid resolution; exhausted eligible cells finish with fewer evaluations and an explanation. Nearby diagnostic alternatives can add results. **Calculation details → Assumed inspection time** retains the existing 30-minute assumption; it affects inspection scores and rankings, not raw terrain-visible area or a recommended stop duration. **View radius** is analysis distance, not guaranteed deer identification distance. **Maximum download size (MB)** limits analysis source acquisition, separate from processing limits and online map browsing.

Online map regression: with the GUI running, use `cd gui/frontend && npm run test:online`. It verifies live tiles, drawing, settings payload without preparing a real job, offline failure/retry, and 3D within local coverage.

## First-person terrain pilot

For the four prepared Soap Creek review setups, **View from this setup** opens a
terrain preview, measured lidar points and an interactive sightline
profile. See [usage and limits](FIRST_PERSON.md) and
[verification evidence](FIRST_PERSON_VERIFICATION.md). Fine ground covers 300 m;
this is not a photorealistic or vegetation-validated field view.

The current view uses connected, image-colored foliage with **Dense** screening
and the unchanged saved **120 m** patch. **Explore nearby positions** lets you try
stances within 30 feet and update the current working waypoint with its own
terrain shading. Original results remain preserved; updated coordinates can be exported.
See [nearby observer instructions and scope](NEARBY_OBSERVER.md). Saved neighborhood
alternatives are expandable; their individual saved masks remain available.

Scenes stop drawing while idle. The original
[cluster verification](FOLIAGE_CLUSTERS_VERIFICATION.md) describes cached geometry;
[nearby-position verification](NEARBY_OBSERVER_VERIFICATION.md) covers movement,
waypoints, exports and the simplified controls.

Waypoint updates: [working locations and terrain shading](WORKING_WAYPOINTS.md).
Verification: [working waypoint evidence](WORKING_WAYPOINTS_VERIFICATION.md).

## Storage and recovery

Use the Storage and recovery panel below the workspace to make a record backup,
restore a selected backup, or preview and execute cache cleanup. Cleanup keeps ready
scenes and referenced waypoint masks available offline. It does not reset notes or
waypoints. Reset has a separate typed confirmation and retains a backup. The panel
shows damaged-record diagnostics instead of silently emptying your records.

## Create results → review and keep → plan approaches

The workflow bar stays visible above the map. Preparation reviews sources and budgets;
bulk downloads require the displayed consent. Edited run settings are marked unapplied:
use a new plan and name for changed inputs. Unchanged partial jobs can still resume.
Preparation failures show their job status and error beside the plan. Download review
shows estimated transfer time and storage headroom. Larger allowances require concrete
plan approval and sufficient storage; byte-based progress and processing stages remain
visible during work. See [the current workflow](WORKFLOW.md).

**Observer access and visible-terrain filters** starts off. Enable maximum proximity
(default 0.5 miles, roads and trails) or maximum height above the nearest mapped line
(default 1,000 feet). Distances project onto actual segments. Height is positive
observer elevation minus elevation at that nearest point, never cumulative climbing.
Unknown network/elevation does not qualify for an enabled requirement. Sources and
mapped lines remain visible; a missing mapped line does not establish lack of access.

Import WGS84 road/trail lines as GeoJSON, KML/KMZ or GPX tracks/routes. Alternatively,
include bounded USFS roads/trails in a new run's reviewed acquisition plan, or draw a
travel area and review its USFS plan in the approach panel. Responses are capped at
10 MB per network, 20 MB combined, with no provider substitution. Combined terrain
and network acquisition must fit the displayed cap. USFS dates remain unknown unless
source attributes supply them; retrieval dates do not establish current conditions.
Network queries over 0.05 square degrees require a smaller explicit area.

Optional new-run access sampling uses loaded networks and the engine's existing
observer-exclusion interface. It preserves the imported polygon, target support and
obstruction terrain. It changes which observer cells can be sampled, not coverage
scores. Review filters also apply to saved setups without running analysis again.

Elevation bands, slope ranges and eight compass aspects apply to saved visible
**target** terrain. Apply to update matching areas, map shading and shared overlap.
Original area and scores stay visible. Matching-area sorting uses original order for
ties. Aspect restrictions exclude flats and unknown aspect; unrestricted aspect keeps
flats. Edited filters remain unapplied until Apply. Coordinates remain exact.

Shortlist at least one setup to enable **Plan approach**. Draw and confirm a
separate search boundary for each setup, including its destination and a mapped
road/trail departure. Geometry/departure checks run before an explicit calculation.
Imports, boundary copying and exclusion polygons are advanced options; copied
boundaries require confirmation for their destination. Existing saved definitions
remain available.
The travel polygon is a search domain, not inferred permission. Departures within one
mile are compared independently for each kept setup. **Include trail walk** adds a
network start; use **Choose network start on map** or exact longitude,latitude.
**Pin a departure on map** inspects another mapped departure. Map picks project onto
the nearest selected segment within 100 m, and display the resulting coordinates.
Shared supplied vertices connect network travel; arbitrary crossings and gaps do not.

Distance always contributes. The four 0–5 avoidance preferences control steepness,
climbing, trees and shrubs; balanced defaults are one each. The separate 30° default
maximum modeled slope is a desktop screening threshold. Unknown vegetation receives
maximum avoidance penalties. The new deterministic 20 m grid service reports modeled
ascent/descent, separate mapped/off-trail distance, maximum slope, average known
cover, unknown coverage, cost components and a ground profile. It retains coverage
scores; coverage does not reward detours or affect path cost.

Review Recommended, Shortest distance and Brush avoidance alternatives; identical
geometry is collapsed. **Show this alternative on map** fits that path. Solid yellow
is mapped travel, dashed pink is off-trail. No-path results describe constraints and
coverage rather than proving inaccessibility. Every endpoint connector and exported
segment stays inside travel geometry and outside exclusions; paths are not smoothed.

Exports are explicitly **provisional approach** GeoJSON and GPX tracks with unchanged
destination waypoints. Fences, deadfall, sub-grid cliffs, water crossings, snow,
permissions and parking remain unmodeled. There is no time prediction, itinerary,
legal certification or field validation. Changed destinations/sources mark scenarios
stale; changed preferences/boundaries require explicit recomputation. Previous scenarios
remain available in the selector, which loads their recorded definitions for review.

Versioned profiles, source originals and sealed approach definitions/results live in
configured GUI state, are included in record backups, and are protected during cache
cleanup. Future intermediate grids are regenerable cache, not source evidence.
See [implementation and acceptance evidence](SCOUTING_VERIFICATION.md).

Roads and trails appear by default in both area creation and result review when
cached or imported networks are available. The map controls are independent of
network selections used for access filters and approaches. Solid roads distinguish
recorded paved, gravel, natural, other and unknown surfaces; dashed trails distinguish
recorded motorized, nonmotorized and unknown use. Click a line for name, maintenance
level, trail classification, source and dates. Unknown attributes stay unknown;
these records do not certify current vehicle suitability, legal access or safety.

Draw/import an observer area or open a run to use **Review road/trail download**
when coverage is unconfirmed. Review the bounded USFS query, then explicitly approve
its download. Existing 20 MB network response limits, the reviewed shared allowance,
the 20 GiB storage reserve, single active job, cancellation and no-provider-fallback rules apply. Large areas
must be narrowed. Saved lines work offline; line presence does not establish full
coverage, and missing lines do not establish absence of access.
The compact type legend lists classifications present in loaded networks. Layer
controls scroll when needed on smaller screens; setup markers and proposed
approaches remain above the road/trail overlay.

After a GUI update, stop the old server with Ctrl+C, run `./huntmaps-gui` again,
and refresh the browser so frontend and backend use the same version. Downloaded
networks remain saved; no repeat download is needed. The frontend also accepts an
older backend's line-only response: roads/trails still display, with unknown subtype
labels until the backend is restarted. Empty overlays explicitly say no data is
loaded. Invalid network responses and loading failures appear inside the controls
without replacing the scouting screen.

Observer proximity uses the source datasets selected in the sampling panel, not the
map visibility toggles. New forms select currently loaded sources by default. If
none are selected, enable reviewed USFS acquisition: sampling then uses that plan's
acquired or checksum-verified covering cached inventories. Source kinds (roads and
trails) remain independent type choices. An empty road response does not discard
available trail lines. Effective source IDs/checksums and limits are recorded in
new runs' `observer_sampling.json`. No selected usable lines is a data/source error,
not evidence that a distance threshold found no qualifying terrain.

For an existing failed preparation, restart the GUI, use **Refresh plan / recover
partial preparation**, review the updated estimate and start/resume. Covering cached
networks are reused without another download; prior completed runs are preserved.

Coverage appears together once the selected setup’s current viewport tiles are loaded and rendered. Opening an uncached setup shows a prominent map loading card; failures show Retry. Panning uses the compact status. **Prepare next** offers 5, 10 or 20 setups (default 10), including the current setup and following the displayed ranking. Detailed tiles are prepared around each setup at the normal selection zoom, with bounded overview tiles. Preparation is sequential, pauses during jobs/map movement, and retains completed tiles after cancellation or retry. Only selected coverage is rendered; retained GPU sources remain capped at eight. Different zooms, expanded viewports or cache eviction can need more loading. See [workflow guidance](WORKFLOW.md) for expanded search, checkpoints and resource guards.

## Recovery and testing

Small observer areas now use denser automated sampling down to grid resolution. Results disclose effective spacing and unused evaluation budget. Approved sources remain approved when they become verified cached files; retries retain cumulative transfer accounting. Older failed plans require one explicit refresh and review, preserving downloaded files. See [TESTING.md](TESTING.md) for the execution-level coverage matrix and acceptance procedure.

Provider errors identify the requested source. Invalid responses are retained with
their provenance under the run's `downloads/rejected/` directory and are excluded
from reusable downloads. Retry reacquires rejected sources when the provider is
available, while reusing validated files and retaining cumulative transfer accounting.
See [source acquisition recovery](ACQUISITION_RECOVERY_2026-10-10.md).

### Filter-first viewpoint search

Use Locations to test for the calculation budget and Top spots to recommend for the initial collection. Set Terrain I want to see before reviewing downloads. Recommendations maximize matching visible area while preserving total visibility and all evaluated locations. Avoid standing in dense vegetation is optional and off by default. Generation progress is shown directly in Step 1; saved approaches can be previewed while their selection requirements are unmet. See [WORKFLOW.md](WORKFLOW.md) for details.

Implementation and verification evidence: [filter-first search report](FILTER_FIRST_SEARCH_2026-10-04.md).
