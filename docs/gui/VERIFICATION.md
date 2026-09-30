# GUI verification — 2026-09-30

All four requested milestones are implemented. Launch with `./huntmaps-gui`;
[first-use instructions and setup](README.md). Backend: FastAPI in the existing GIS
venv. Frontend: locally built React/TypeScript and MapLibre, including its bundled
worker. Raster layers use a GDAL XYZ tile adapter, not report screenshots.

## Real saved-results evidence

The existing Soap Creek baseline and the specifically scoped decision review open
through read-only adapters. The baseline retains 150 originals; the experiment
retains all 202 original/alternative setups. Initial filtering displays the saved
review positions, without fabricating groupings. The West shortlist contains
A0075/V010/V008 together, as in the supplied decision review.

| Setup | Latitude | Longitude | Saved / mapped terrain-visible km² | Visible 10 m cells |
|---|---:|---:|---:|---:|
| A0075 | 38.689036782664175 | -107.30222216238236 | 1.2567 | 12,567 |
| V010 | 38.688597868286266 | -107.30163328064793 | 1.3155 | 13,155 |
| V008 | 38.68858655533786 | -107.30220772622326 | 1.2937 | 12,937 |

The adapter uses the existing `visible_mask` check: CRS, pixel size, integral origin,
visibility value exactly 1, target intersection, observation radius and area match
at 1e-9 km² tolerance. NoData/background are transparent. Cached mask RGBA rasters
retain the DEM's original transform/CRS; the tests check the alpha cell counts.
Independent Web Mercator tile-pixel coordinate transformations match source-grid
mask cells. Existing saved target-class rasters are checked against their aligned
source classes before display. The tree-class area breakdown sums to raw terrain
area, and recorded experimental breakdowns match independently counted source cells.

The tile adapter warps each source into a precise EPSG:3857 tile extent. Categorical
layers use nearest-neighbor sampling; aerial imagery uses bilinear sampling and
alpha. Coarse context imagery is composed before fine setup clips. Source dates and
native/export resolution are retained in the source drawer. Source metadata/raster
hashes are checked against existing manifests; hash/JSON caches invalidate when file
size or modification time changes. GUI caches are outside protected results.

GPX and KML read-back checks show exact saved double-precision coordinates for all
three selected observers. Names identify neighborhoods and parents; target openings
are excluded from observer exports. Notes and review status persist under `.gui/`
and leave original reports and exports unchanged.

## Browser verification

Playwright drove installed `/usr/bin/google-chrome` headlessly against the actual
localhost application at 1500 × 1050, with software WebGL. This is browser verification,
not a mockup. Actual pages and screenshots were inspected; no browser page errors,
failed asset requests or external frontend requests remained in the final run.

Checked: initial saved results, all three exact setup selections and metrics, three
colored comparison masks, show/hide controls, rejection of a fourth comparison,
vegetation and sector toggles, saved notes after reload, GPX download, baseline-run
selection, hillshade toggle, and KML boundary import. The viewer check confirms the
job count does not change when results are opened or browsed.

For offline viewing, browser routing blocked every non-local origin while allowing
localhost, followed by a reload. The real masks/imagery and stored notes remained
usable. The read-only backend endpoints use only local files; no analysis/download
subprocess is started by them. This was an external-network isolation simulation,
not a physical disconnection of the computer's network interface.

Screenshots are retained outside Git in `.gui/verification/screenshots/`:

- `01-viewer.png`: actual imagery and target-clipped A0075 mask.
- `02-compare.png`: A0075/V010/V008 individual colored masks and shared-area table.
- `03-offline.png`: reloaded local results under external-network blocking.
- `04-import.png`: imported KML observer boundary; historical setups hidden.
- `05-classes-sectors.png`: class legend and saved inspection-sector overlays.
- `06-baseline.png`: unchanged baseline adapter.
- `07-acquisition-plan.png`: actual new-run form and plan.
- `08-job-history.png`: real durable job outcomes.
- `09-hillshade.png`: local terrain fallback.

The new-run form imported the supplied `inputs/test.kml` and prepared a fresh
GUI-owned plan. Estimated new bulk data: **23,413,616 bytes**, cap **600 MB**;
DEM came from the existing cache. Bulk-download authorization remained unchecked.
No bulk download was performed by verification. Metadata/source planning is still
allowed by the existing CLI's preparation behavior.

## Background-job evidence

`gui/verify_jobs.py` exercised the live HTTP job API using an explicitly synthetic
24-candidate, 500 m-radius fixture in `.gui/fixtures`. The existing owner CLI is
invoked as argument-list subprocesses, unchanged:

1. Intentionally invalid fixture DEM checksum: real source-validation failure.
2. Correct fixture descriptor and refresh: validated cached sources, zero-byte plan.
3. Start and cancel after the actual wrapper emitted its source-checking stage:
   cancelled process group, partial files retained.
4. Resume the same GUI-owned partial run: baseline engine, handoff and exports
   complete; new completed run appears in the selector.

Live observations and job IDs are in `.gui/verification/jobs.json`; the completed
engineering run is `results/synthetic-gui-7f60cbf6/`. All fixture runs are explicitly
labeled synthetic and are not selected hunting areas.

`gui/verify_restart.py` launched a dedicated actual application process, started a
fresh synthetic job, killed the server abruptly, and restarted it. The unfinished
job changed to **interrupted** and the recorded surviving worker stopped. Evidence:
`.gui/verification/restart.json`; partial test run
`results/synthetic-restart-3855c78e/`. Test server was stopped afterwards.

Unit tests also verify one-job serialization, success/failure/cancellation records,
restart recovery, and killing a descendant that deliberately ignores TERM. A cancelled
job is not marked finished until its remaining group is killed. Source budgets and
engine guards remain in the original CLI; no progress percentages are invented.

## Regression and preservation

Commands completed successfully:

```sh
npm run build --prefix gui/frontend
npm audit --prefix gui/frontend --cache /tmp/huntmaps-npm-cache
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests -p test_gui.py -v
./scout verify --name soap-creek-v1
node gui/frontend/browser-check.mjs
node gui/frontend/browser-plan-check.mjs
.venv/bin/python gui/verify_jobs.py
# With the normal server stopped:
.venv/bin/python gui/verify_restart.py
```

The complete suite passed **43 tests in 12.843 seconds**. The GUI subset was rerun
after final source guards. npm audit reports **zero vulnerabilities** for the locked
frontend dependencies. Vite's large-chunk notice is a build-size advisory; all assets
are local and the production build completes.

Before changes, 7,105 existing files under results/runs/data/glassing/configs and
historical report directories, plus the original launcher, were hashed. All remain
byte-identical. Snapshot: `.gui/verification/PRESERVED.json`. No engine source,
configuration control, historical run or supplied report was changed. Existing scout
verification passes. No data, environment, GUI state or generated raster was committed.

Failures found and repaired during verification: positional HTTP response media type,
success-message reset after annotation save, MapLibre worker/shared-module bundling,
frontend dependency advisories, historical layers leaking into new-area preview,
and a temporary GDAL dataset lifetime error in the new test itself. Final checks
passed after these fixes; the original GIS engine was not changed.

## Remaining limits

Adapters cover normal completed owner runs and the saved Soap Creek decision review;
older research archives are not automatically imported. There is no arbitrary-area
experimental vegetation operation. The inherited acquisition adapter still supports
single-tile DEMs and automatic Colorado seasonal sources; unsupported mosaics/custom
sources require assistance outside this simple form. New-area bulk downloads were
not exercised because they were unnecessary for the requested verification. No fresh
OS/GIS installation or unit-wide runtime claim is made. Display caches currently
have no automatic eviction; stop the application before clearing `.gui/cache`.
Legal/safe access, contemporary vegetation and actual ground-level sightlines remain
unverified. Scores remain heuristic indices or terrain-visible area, never deer
probabilities or certified routes.
