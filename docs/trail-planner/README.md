# TrailScout

A separate local browser application for comparing provisional trail portions,
glassing positions and complete return-aware morning/evening outings. It uses real
prepared Colorado GMU 54 data, generates new viewpoints, and saves the choices you
select. It requires no API key, LLM, account, cloud hosting or paid service.

From the TrailScout worktree:

```bash
./trailscout
```

Open **http://127.0.0.1:8767**. The first launch builds its separate browser assets
using installed packages. **Ctrl+C in that terminal stops only TrailScout**. Resume
with the same command; saved plans and completed analytical caches remain on disk.
Never stop the owner's HuntMaps2 server to run this application. Only one server or
headless writer can hold a state directory at a time. Stop your TrailScout terminal
before using headless planning against that same state, or choose another explicit
`--state` directory. A second instance fails without changing live job records.

The retained worktree is `/home/tanner/Desktop/huntmaps2-trailscout`, branch
`feature/trail-glassing-planner`. It began at `/tmp/trailscout-worktree` and was
moved after verification. See [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)
for the preservation evidence and handoff. The original checkout is always
`/home/tanner/Desktop/huntmaps2`, branch `main`.

## Workflow

1. Choose **Colorado GMU 54**, an editable outing date, hunter/group and vehicle.
   Together uses Dad's conservative limits, not an average. The limits are editable
   uncalibrated assumptions; 25% of movement capacity is held in reserve.
2. Choose a supported mapped entry. Parking and the full vehicle approach remain
   unverified. A road's existence never establishes motor permission. Click a
   segment on the map to choose an intended start on that exact line.
3. **Compare route opportunities**. Progress, cancellation, failure and retry are
   explicit. Browsing previous results and saved plans remains available.
4. Review a route preview, full traveled distance, ascent/descent, return leg,
   linked raw/cleaned profile, optional spurs, coverage and competing access.
   Morning, evening, two-trip combined day and one-location stay-all-day variants
   have separate feasibility checks. A single strong viewpoint is valid.
5. Use **Access assumptions & owner edits** to exclude segments or a small map
   rectangle, pin a new exact viewpoint, reject an evaluated point, or record a
   dated foot-access update with provenance. These change calculations. Every
   pinned point must fit; an infeasible pin is explained, not silently dropped.
6. **Save this plan** creates an immutable version. **Save a new version** preserves
   its parent. **Save as a separate plan** starts an independent saved outing.
   Open prior versions in the saved list; Compare displays saved entry/effort/
   coverage evidence side by side. Conflicting parent revisions are rejected.
7. Download **Field summary**, JSON, GPX and GeoJSON. Tracks follow actual computed
   geometry with retracing; GPX never joins waypoints with imaginary straight lines.

Edited inputs mark the displayed comparison stale and disable saving until
recalculation. A date/window edit reuses compatible terrain/habitat/visibility
artifacts. A moved point has its own exact-coordinate visibility identity.
The default map uses only local relief, network and coverage assets. There is no
external imagery requirement or unrestricted imagery downloader.

## Local roots and environments

Defaults are explicit:

- Read-only data/source root: `/home/tanner/Desktop/huntmaps2`.
- Interpreter: that root's `.venv/bin/python`, used without upgrades.
- Frontend dependencies: that root's `gui/frontend/node_modules`, used read-only
  through a worktree-local symlink. No owner package files are changed.
- State, immutable analyses, profiles/draft, jobs, imports and cache:
  **`WORKTREE/.trailscout/`**, separate from `.gui`, `runs`, `results` and owner data.

Overrides for another compatible local installation:

```bash
TRAILSCOUT_SOURCE_ROOT=/absolute/verified-source-root \
TRAILSCOUT_PYTHON=/absolute/compatible-env/bin/python \
TRAILSCOUT_NODE_MODULES=/absolute/installed/node_modules \
./trailscout serve --state /absolute/separate/trailscout-state --port 8767
```

Missing roots fail visibly; no empty replacement data/environment is created.
The Python dependencies are the already installed GIS stack and FastAPI/Uvicorn
listed in `gui/requirements.txt`; no new Python dependency was installed.
The separate `trail_scout/web/package.json` pins the reused frontend versions.
On a new machine, use an isolated compatible GIS environment following the
repository setup, and install frontend dependencies only in the new app directory.
A new-machine environment solve has not been claimed as tested here.

## Sources and bounded preparation

TrailScout verifies the registered immutable unit-pack manifest/seal and every
consumed asset, then checks actual DEM CRS/grid/units/NoData and source integrity.
Core pack: `data/unit-packs/versions/co-gmu54/20261019-v2`, buffered 10 m 3DEP,
2023 RCMAP cover, official CPW unit boundary and attributed USFS network pieces.
Compatible dated `data/scouting` GeoJSON sources supply optional MVUM, motor-closed,
entry and ownership evidence through a read-only adapter. Historical experiment
runs, saved viewpoints and owner `.gui` records are never runtime dependencies.

**Sources, coverage limits & bounded preparation** shows the data index, exact
unit bounds, support/resolution, limitations and source links. Other unit corridors
use the same pack with a selected entry or owner start and explicit bounded limits.
Terrain support is validated for the entire requested obstruction halo. Intrinsic
vegetation NoData stays unknown. Observer travel, hunting targets, habitat context,
obstruction terrain and competing-access extents remain distinct.

**Prepare fresh official access · 5 km around entry** downloads only bounded
USFS motor-closed and MVUM road/trail snapshots around the current entry/custom
start. It inspects live layer identities, queries an independent count, requires a
complete bounded response, retains metadata/original attributes/provenance, and
publishes all snapshots atomically. Failed/cancelled preparation retains pieces,
transfer accounting and its retry action. An incompatible request requires a new
preparation. A successful empty *verified inventory* is distinguished from provider
failure; it still cannot certify there are no closures or roads.

You can also paste an attributed WGS84 GeoJSON FeatureCollection and dated source
provenance to import `closed_roads`, `mvum_roads` or `mvum_trails`. Originals and
unknown properties are retained. Requests are limited to 2 MB / 2,000 features /
150,000 coordinates. Import/publish never changes owner sources. A bounded official
snapshot supersedes intersecting old supplemental records only within its stated
query region; all source versions remain retained.

Paste a WGS84 Polygon/Feature to set a scenario travel area or target area. Neither
polygon establishes permission. Explicit segment/area/foot closures exclude travel;
unknown foot access appears only under **Explore unknown foot access as a scenario**.
A GMU is a target boundary, never an obstruction or automatic walking boundary.

Predeclared defaults: one analytical/preparation worker, at most 80 candidate views
(including pins), at most 2 million terrain cells, 250 MiB cumulative preparation
transfer ceiling, 2 GiB TrailScout state ceiling and the existing **20 GiB free-space
reserve**. Preparation pieces have timeouts and atomic publication. A larger view or
corridor that exceeds support/resource bounds is rejected; precision is not silently
reduced. There is no whole-unit fine-grid analysis or national database requirement.

## Verification and headless use

```bash
./trailscout check
./trailscout inventory
./trailscout plan --inputs /absolute/inputs.json --out /absolute/result.json
```

The complete new-app gate runs Python formatting, frontend formatting/type/build,
new numerical/real-data/API tests, relevant legacy compatibility suites, then an
actual-service browser journey in disposable state on a dedicated ephemeral port.
It retains its logs, screenshots, downloads and state under `/tmp/trailscout-gate-*`.
No owner API/worker/server is used. Real-data test sources must be present; there is
no synthetic fallback labeled as GMU readiness.

`inputs.json` uses the same validated API/core settings as the browser. Run the
inventory/start endpoints or save a browser plan to obtain exact supported IDs.
Performance helper:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/tanner/Desktop/huntmaps2/.venv/bin/python -m trail_scout.checks.performance
```

The [methods](METHODS.md), [architecture](ARCHITECTURE.md), and
[implementation report](IMPLEMENTATION_REPORT.md) distinguish engineering checks,
real-source demonstrations and unresolved field evidence.
