# Architecture and reuse

TrailScout is additive: one separate FastAPI/Uvicorn service on loopback port 8767,
a React/TypeScript/MapLibre browser app, immutable JSON/NPZ files, and one cancellable
analytical/preparation worker thread. No database/service/account is required.

- `sources.py`: explicitly read-only prepared-pack and dated supplemental-source
  adapters. Verify original attributed GeoJSON and sealed raster identities; never
  import the owner's geometry-only network records or invoke a legacy worker.
- `effort.py`, `network.py`: actual route-grade profiles, directional costs,
  conservative topology, travel chains with every traversal retained.
- `analysis.py`: bounded context, new off-trail discovery, exact observer screening,
  content-keyed GDAL masks and weighted aligned coverage unions.
- `planner.py`, `profiles.py`, `schedule.py`: guardrails, complete alternatives,
  Pareto/tradeoff explanations, conservative observation and return schedules.
- `storage.py`: explicit roots, atomic writes/seals, exact source/cache identities,
  disk budgets, immutable analysis/save versions and implementation fingerprints.
- `preparation.py`: bounded original attributed imports, official live metadata/
  count/feature validation, cumulative transfer ledger and atomic publication.
- `app.py`: separate API, bounded job admission, duplicate prevention, cancellation,
  restart recovery, revision-checked saving, local assets and exports.
- `render.py`: local terrain/coverage images and exact-geometry field/GPX/GeoJSON
  exports. Images reproject to Web Mercator for display; analytical grids remain
  metric and unchanged. The coarse 100 m unit overview is display context only.
- `web/`: compact controls, route/schedule/coverage/access/marginal inspection,
  linked profile/map, owner edits, immutable saved versions and visible recovery.
- `gate.py`, `tests/`, `checks/`: independent numerical fixtures, actual real-data
  API/worker checks, local HTTP failure fixture, actual-service browser and bounded
  real-corridor performance helper. Engineering fixtures are labeled separately.

The only reused analytical runtime module is pure `huntmaps_gui.habitat.py`; its
coefficients, support/unknown contract and interpretation are unchanged. The GDAL
visibility calls/settings follow the verified existing core/evaluation primitive;
no historical run, mask, point coordinate or model lock is mutated or required.
Installed GIS/FastAPI and React/MapLibre/tooling dependencies are reused read-only.
The app uses a separate frontend source/build namespace; no framework rewrite.

Inspection of the existing complementary/evaluation/search/sampling/target-filter/
working-waypoint/catalog modules established the visibility/grid/habitat/source
contracts. Existing complementary greedy selection is a set-coverage calculation,
not visiting order. TrailScout therefore implements its own actual travel chains.
Existing approach/native/C++/preflight/connectivity modules established why mapped
travel must not inherit ground-cell hillside slope as walking grade. They remain
unchanged. Existing `scouting_network`, source reuse/RCMAP/acquisition/config/jobs/
downloads/storage and tile adapters informed the explicit attribute/provenance,
20 GiB reserve, isolation and display alignment contracts. Their mutating API,
worker/state/cache paths are never invoked by TrailScout. The inherited uncommitted
unit-pack work is preserved separately from all task-owned changes.

Analysis identity includes normalized inputs, source revision, implementation,
coordinate/model/settings and aligned grids. DEM masks are independently keyed by
DEM identity, exact coordinates, grid, radius, endpoint heights, curvature and GDAL
version. Habitat context is keyed by raw tree/shrub products/years/settings and grid,
independent of schedules/access edits. Schedule/date/profile edits do not silently
reuse an incompatible completed result; compatible expensive masks remain reusable.

Jobs publish progress and deterministic checkpoints atomically. Cancellation keeps
completed independently sealed work; retry reevaluates the deterministic planner
while reusing compatible source/context/mask caches. There is no false resume of an
incompatible job. Restart marks in-progress records interrupted and retains saved
work. A corrupt analytical artifact fails visibly instead of becoming an empty
success. Saved-plan publication checks current inputs, implementation/source revision,
mode feasibility and parent head. A late job reply cannot replace newer owner edits.

The bounded worker shares process memory with the service, while ordinary handlers
run independently. Grid/candidate/graph limits bound memory and there is no unbounded
candidate×full-grid cube. This release intentionally avoids a process farm or task
queue service. An operating-system kill cannot be caught; restart recovery and
atomic artifacts preserve the last good saved work.

A filesystem lease admits only one live server/headless writer per state, regardless
of port. A second instance fails before touching job recovery. Graceful shutdown
cancels/waits for its own worker before releasing the lease; the OS releases it on
process exit. Corrupt raw dependencies and new raster companions cannot be hidden
by a warm analytical cache. Normalized acquisition pieces are compared with their
verified originals and prior seals before retry publication.
