# HuntMaps2 local scouting desk

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

The existing `scout` file is hashed into completed-run manifests. It remains
byte-identical; the GUI has its own launcher rather than invalidating historical
verification. Existing CLI commands continue to work.

## First review

1. Open a completed run in the header. The initial Soap Creek neighborhood review
   is explicitly experimental; choose **soap-creek-v1 · baseline** to see the
   unchanged normal analysis. Opening results starts no analysis or source acquisition; enabled online imagery requests display tiles.
2. The initial list shows saved review positions. Use the neighborhood filter or
   **All setups** for the full saved pool. Select A0075, V010 or V008 to inspect
   coordinates, parent relationship, target area, cover breakdown and uncertainty.
3. **Compare** selects up to three. Colored layers retain each individual saved
   mask. The checkboxes beside their names show/hide individual views without
   removing the comparison. Shared terrain appears below the map. **Setup close-up**
   zooms into the active observer. Saved inspection sectors include hidden terrain;
   tree classes apply to the active setup only.
4. Mark keep/reject/needs inspection, enter notes and click **Save review**.
   Annotation files are separate from completed results.
5. Check **Export** for the observer setups you want, then click GPX or KML.
   Export coordinates are the saved observer positions, with meaningful names and
   your notes. Target-opening coordinates are deliberately excluded. These are
   provisional waypoints, not navigation routes.

Map controls include zoom, compass rotation/reset, metric scale, imagery and
visibility toggles, opacity sliders, legend and whole-area/close-up buttons.
Online imagery fills gaps behind saved aerial clips by default, fetching visible USGS National Map tiles as you pan and zoom. Turn off **Online imagery — fill gaps** for entirely local viewing; this preference persists in your browser. Provider attribution appears on the map. Online acquisition dates vary and tiles are browsing context, separate from analysis sources and its download cap. There is no offline tile pack. Saved imagery dates and native/export resolutions remain in the source drawer. When online imagery fails, the map keeps cached imagery and local hillshade where covered, with a retry control. No PDF screenshots are used as map layers.

## New baseline run

Choose **New baseline run**, import GeoJSON/KML/KMZ, explicitly select a polygon
(or deliberately combine all), and inspect the orange observer boundary. Historical
candidate layers are hidden in this preview. Cached context belongs to the open
run; it is not proof that new-area data are available.

Enter a new run name, radius, observation minutes, candidate count and download cap.
The existing hunt context is inherited from the transfer template: GMU54 second
rifle 2026, personal dates unset and light assumptions hypothetical. This small form
does not introduce new coefficients or permit arbitrary shell commands.

Click **Prepare acquisition plan**. The unchanged owner CLI checks cached data and
can request catalog metadata (up to its existing 5 MB response limit). It does not
perform bulk downloads. Review source items, estimate, cap, errors and required-data
text in the interface. Only explicitly checking **Allow this plan's bulk downloads**
permits bulk transfer. The existing streaming cap and validation remain authoritative.
If the estimate exceeds the cap or source planning fails, analysis remains blocked.

Click **Start / resume baseline**. One background process group runs at a time.
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
space, 900 seconds per engine command, 800 MB output budget; GUI download cap defaults
to 600 MB. The form supports radius 500–3000 m in 500 m steps, 5–120 minutes,
12–200 primary candidates and 1–1900 MB download caps. The engine can reject areas
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

See [verification evidence](VERIFICATION.md). Repeat engineering checks with:

```sh
.venv/bin/python -m unittest discover -s tests -v
# With the app running:
node gui/frontend/browser-check.mjs
.venv/bin/python gui/verify_jobs.py
node gui/frontend/browser-plan-check.mjs
```

The browser checks use installed `/usr/bin/google-chrome` through Playwright. Fixture
jobs are clearly named **synthetic-gui-...** and are engineering tests, never hunting
recommendations. Each live fixture test creates a fresh run to preserve prior results.

Supported result adapters are completed normal `results/*/scouting.json` owner runs
and the specific saved Soap Creek decision review. Older research archives under
`runs/` and arbitrary third-party GIS projects are not presented as normal runs.
The GUI does not generate arbitrary-area experimental vegetation results. Baseline
new-area acquisition still has the existing single-tile DEM/Colorado seasonal-source
limits; mosaics/custom sources need assistance outside this simple form. Imagery,
legal entry, permissions, current restrictions and safe approach are not acquired
by normal runs. Cached 2019 imagery/2023 vegetation can differ from present conditions.
No new scoring model, automatic grouping, optimizer, timed itinerary or field
validation is claimed. Map tiles resample for display; saved cell counts, not screen
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

**Locations to evaluate** controls initial separated sampling across your polygon, not the number of top results. Open **How locations are chosen** for spatial and terrain sampling details. Too many locations for the area and spacing causes a clear failure. Nearby diagnostic alternatives can add results. **Advanced scoring settings → Assumed inspection time** retains the existing 30-minute assumption; it affects inspection scores and rankings, not raw terrain-visible area or a recommended stop duration. **View radius** is analysis distance, not guaranteed deer identification distance. **Maximum download size (MB)** limits analysis source acquisition, separate from processing limits and online map browsing.

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
