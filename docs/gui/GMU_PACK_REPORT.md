# Colorado GMU 54 local pack implementation

The integrated unit workflow and real core pack are implemented and verified.
The complete release gate passed with the real registered pack in place.
Instructions: [prepared hunting units](GMU_PACKS.md). Continuity and development
failures: [progress record](GMU_PACK_PROGRESS.md).

## Design and changes

New scouting begins with a prepared-unit selector before the observer polygon.
Colorado GMU 54 supplies local relief, its official outline, roads/trails and checked
source descriptors. The user chooses a local area; no centroid AOI or human-selected
points are manufactured. Core generation, connection screening, Basic inspection,
Save/export/reload use local data. Oversized whole-unit analysis is rejected before
a worker starts. Custom-area scouting and existing runs remain available.

Optional online satellite/aerial context remains available in prepared-unit mode
and loads by default unless the user has turned it off. **Map layers → Online
imagery — fill gaps** controls it. It renders above local relief and below saved
imagery/analysis overlays. Online imagery is display context, not an additional
core-pack dependency; local relief remains usable when disconnected.

Satellite follow-up evidence: a separate real-provider browser rendered GMU 54
with 50 successful USGS tiles and no page errors
(`/tmp/huntmaps-pack-satellite-live/gmu54-satellite.png`). The focused real-pack
gate also passed toggle, rendered stacking, offline fallback and retry. Follow-up
full release checks passed 300 backend tests and 31/32 browser journeys; one existing
imported-network selection assertion timed out, then passed unchanged in isolation.
The full run is recorded as exit 1, not a clean full-suite pass. See the final
[progress entry](GMU_PACK_PROGRESS.md) for both diagnostics and preservation evidence.

A small manifest/catalog contract lives outside evictable display caches. Versions
publish by validated directory rename followed by atomic catalog-pointer replacement.
Incomplete pieces and progress remain in preparation. A failed update leaves the
prior ready version usable; a publication interrupted between rename and registration
can be registered again without rebuilding. SHA-256, size, inode/ctime and explicit
TIFF dependency checks detect corruption without rehashing the unit on every UI
interaction. New runs retain the pack version and manifest seal; recovery restores
that context and exports identify it. Old data/runs/owner records are not migrated.

Exact persistent local windows, including 480 m vegetation-neighborhood padding,
keep the unit source pack out of per-analysis arrays. Road/trail windows go through
the existing verified-network importer. Their data and completeness evidence supply
screening and approaches locally. Derived-window provenance is separate from the
strict exact-byte raw-source reuse contract; `source_reuse.py` validation is unchanged.
No analytical model coefficients, terrain/target masks, historical scores or route
solver were changed. Unit eligibility remains separate from buffered obstruction data.

Implementation: `huntmaps_gui/{unit_packs,pack_builder}.py`, AppConfig/plan/worker/run
adapters, existing network/scene interfaces, `gui/frontend/src/unit-packs.tsx` and
small workflow/layer changes. The CLI planner and frozen glassing engine are unchanged.

## Actual registered pack

Current location:
`data/unit-packs/versions/co-gmu54/20261019-v2/`.
Registration: `data/unit-packs/catalog.json`.
Contract 1; manifest SHA-256:
`82610b2186bc9c7b64a8fe9ec58131194c45132752c082b61597a5a14ad6a4c4`.
V1 is preserved alongside V2. V2 explicitly reuses that verified source snapshot;
it does not pretend to be a newly acquired current-provider snapshot.

| Input | Identity, dates and preparation |
| --- | --- |
| Official boundary | Current [CPW administrative GMU service](https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/ArcGIS/rest/services/CPWAdminData/FeatureServer/6), GMUID=54. Feature EDIT_DATE 2023-12-28; current service edit metadata retained. CPW publishes its GIS context through [Maps and GIS](https://cpw.state.co.us/maps-and-gis). Area 1,513.764662 km². |
| West elevation | Verified local USGS 3DEP `USGS_13_n39w108_20220331.tif`, 415,482,393 bytes, publication 2022-03-31; actual mixed source acquisition dates remain unknown. Original source retained. |
| East elevation | Official USGS staged-products `USGS_13_n39w107.tif`, 407,666,304 bytes. Retained tile XML identifies title date 2026-06-30, publication 2026-07-01, source time period 1958–2020. S3 object modification 2026-07-02 is recorded separately. [Official tile metadata](https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n39w107/USGS_13_n39w107.xml). |
| Prepared terrain | Both sources are NAD83 geographic, metre elevations/NAVD88. Bilinear mosaic to EPSG:32613, 10 m, 7188×6693 cells. All 48,109,284 support cells valid. Different source vintages are retained; no vertical correction, hole filling or terrain clipping at the unit boundary. |
| Vegetation | USGS RCMAP 2023 annual tree/shrub/herbaceous percent cover, current annual WCS snapshot at acquisition. Product release unknown, observation year explicit. [MRLC data-service documentation](https://www.mrlc.gov/data-services-page). Sixteen padded pieces per component; delivered grids are about 30 m, nearest-neighbor aligned preparation at 30 m. Source NoData=101; prepared NoData=-9999. Each component has 154,753 unknown cells among 5,345,476 (2.895%). |
| Seasonal ranges | [CPW summer range](https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/99) and [winter range](https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/CPWSpeciesData/FeatureServer/105), retrieved 2026-10-19. Independent query counts matched every bounded response. Raw responses/metadata retained; normalized WGS84 geometry and recorded make-valid preparation. These are mapped seasonal-range hypotheses, not current occupancy. |
| Roads/trails | Official [USFS road inventory](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RoadBasic_01/MapServer/0) and [USFS trail inventory](https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0), retrieved 2026-10-19. Sixteen bounded pieces for each; count/response agreement, raw attributes and coverage bounds retained. Complete agency responses do not imply every jurisdiction's road/trail, current closures, public permission or safe passage. |
| Local context | Official boundary, simplified display-only mapped lines and local terrain-derived relief. No external basemap is required. |

WGS84 unit bounds are
[-107.424256066236, 38.448864897896, -106.845480215162, 38.8706450999632].
Projected support is [278040, 4247850, 349920, 4314780], EPSG:32613: the unit
bounding envelope plus at least 10,440 m, aligned at 30 m. This covers the existing
10 km access query domain, visibility radii up to 3 km, 20 m terrain gutter,
habitat neighborhoods up to 360 m and native/grid padding. All padded vegetation
pieces passed footprint checks; intrinsic unknown cover was preserved honestly.

Basic terrain readiness covers the unit. **Whole-unit Detailed readiness is not
claimed.** Detailed ground, measured vegetation and imagery remain selected-area
preparations through the existing source/cache mechanisms. This pack does not
require or download whole-unit LiDAR. The retained older detailed caches/scenes
remain available to their established workflow; no original scene was regenerated.

## Resources and acquisition evidence

Initial Ubuntu measurement: 93 GiB available on the 234G Ubuntu filesystem.
No Windows/Data partitions were inspected. The existing **20 GiB reserve** remains.
The builder used a 1.5 GB cumulative-transfer cap and conservative peak headroom
of **8,794,967,296 bytes** (three source-copy allowances plus 4 GiB processing/
publication headroom), in addition to the reserve. This is a conservative bound,
not measured peak usage. Actual headroom remained ample; about 90 GiB was available
at the post-implementation check.

- V1 acquisition ledger: **500,597,188 bytes downloaded**, **415,482,393 reused**.
- V2 update: **0 new download bytes**, **916,079,581 verified source bytes copied**
  from V1. Data dates remain those of the retained snapshot.
- Current V2 physical file bytes: **1,040,079,696** (about 0.969 GiB).
- Preserved V1 physical file bytes: **1,040,056,280**; both versions total about
  **2.08 GB / 1.94 GiB**. Initial retained discovery probes add 202,637 bytes.
- Transfer ledgers count response payloads, not HTTP/TLS overhead; initial small
  discovery requests are separate from the core-build ledger.

The normal TNM catalog request returned HTTP 504. The valid bounded fallback was
the official USGS public staged-products catalog, with exact object sizes and
independent tile-specific XML, before downloading the missing east tile. No paid
source or LiDAR bulk download was used. Actual preparation was interrupted and
restarted; completed pieces were reused and cumulative accounting was retained.
Logs: `/tmp/huntmaps-pack-build.log`, `/tmp/huntmaps-pack-update.log`.

Recent original failures were classified separately: incompatible local vegetation
footprints were correctly refused; a preparation HTTP500 is recorded without enough
request detail to name its exact provider; grid-budget failures required smaller
areas; R0018 detailed vegetation exceeded the retained memory bound. Downloading
more sources does not fix those processing limits. The pack adds early area checks,
bounded input windows and immediate Basic inspection. Existing detailed processing
limits and all old failure records remain intact.

## Verification completed

Decisive socket-denied acceptance:
`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m gui.pack_acceptance`.
Evidence root: `/tmp/huntmaps-pack-offline-c5opa2a2/`;
log `/tmp/huntmaps-pack-offline-defaults.log`. All four areas include default
880-yard road proximity sampling.

A separate real server and its workers had external socket/DNS connections blocked
from startup. Four fresh 24-location areas used the real V2 pack: west, central,
east and a source-tile seam near longitude -107°. None replayed a prepared run.
All completed Find → connection screening → selected Approach → Basic Inspect →
confirmation/Save → GPX/KML export → reload. One used the existing experimental
habitat preference. Whole-unit intake failed before worker launch. External socket
attempts during the four core service workflows: **zero**. Each analysis grid was
475×485 at 10 m with complete terrain;
independent coordinate round trips were below 1.1×10⁻⁹ m, and exported GPX/KML
coordinates matched the chosen saved points. Vegetation unknowns remained present.
Evidence: `acceptance.json`, `outcomes.json`, `independent-coordinate-validation.json`,
per-area screen reports, exports and retained actual job logs. Approach GPX/GeoJSON
metadata and exact destinations also passed actual service read-back on all four
saved approaches (`approach-export-validation.json`).

The accompanying browser opened a confirmed Basic scene and waited for
renderer readiness. A separate socket-denied server/browser then opened all four
new Basic scenes, matched every candidate ID, and recorded zero page errors or
external browser requests (`all-areas-rendered/results.json`). The main browser
checked unit/custom/existing-run switching, desktop/900 px
layouts, no overflow, no browser errors and no direct external browser requests. Deliberate
Custom-area switches separately attempted the established optional transportation
browsing service; 149 requests during the final Custom switches were denied by
the socket guard. They were all `carto.nationalmap.gov` display context, with no
provider catalog, source-download or analytical dependency. Core pack selection
disables that optional context, and all four new core workflows completed before
those browser switches with zero external attempts. No live connection was allowed.
Images:
[unit selection](/tmp/huntmaps-pack-offline-c5opa2a2/screenshots/unit-selection-desktop.png),
[900px unit selection](/tmp/huntmaps-pack-offline-c5opa2a2/screenshots/unit-selection-900.png),
[actual Basic scene](/tmp/huntmaps-pack-offline-c5opa2a2/screenshots/pack-confirmed-desktop.png).

Twelve focused lifecycle regressions passed: bounded exact pixels; explicit derived
provenance; offline verified networks; outside/oversized rejection; corruption with
same size/mtime; missing assets/companions; workspace-relative sampling; approach
export identity; malformed/missing integrity records; reserve; failed/successful
updates;
interrupted registration; damaged progress; cancellation/retry with retained partials
and cumulative bytes. These use synthetic sources and controlled faults, separately
from the real four-area workflow. `test_gui_unit_packs.py` is registered through the
mandatory GUI discovery group; `browser-unit-packs-check.mjs` is in the mandatory
release list. The latter also holds a real unit-context response across a switch
to Custom and checks that it cannot restore stale layers or clear habitat preferences.

Final full command `./gui/check --keep-going` **passed with exit 0**. No required
stage or assertion was skipped; keep-going records failures without suppressing
them, and this run had none. Evidence root `/tmp/huntmaps-check-irdt1d4n`, log
`/tmp/huntmaps-pack-release-complete.log`:

- **300 backend tests** across 12 release groups, including 199 GUI tests and the
  12 new pack regressions. Exact counts: `backend-counts.json`.
- **32/32 browser journeys**, including the new real-pack/default-proximity/stale-
  response journey and all existing habitat, notes/drafts, approach, scene, detailed
  LiDAR recovery, waypoint, training, storage, coverage and performance assertions.
  Exact results: `browser-results.json`.
- The existing actual interrupted **600-location recovery** and follow-on workflow
  passed in separate disposable state. This uses controlled provider/synthetic data,
  separately from the real GMU pack four-area and 150-location evidence above.
- Black, Prettier, TypeScript, Vite and `git diff --check` passed.
- The runner's independent source/result audit reports **8,270 paths unchanged**;
  owner/companion preservation checks passed.

Final release screenshots are under `screenshots/browser-unit-packs-check/`; the
unit selection, current coverage and actual four-area Basic views were visually
inspected at desktop/900 px. All 55 raw and prepared pack rasters separately passed
explicit single-file dependency checks (`all-raster-dependencies.json` in the earlier
`/tmp/huntmaps-pack-offline-1va4_c5_` evidence root).
Earlier development interruptions and a corrected syntax error are retained in the
progress/logs, not represented as passing gates. The full existing assertions remain.

An additional actual 9 km² run used the normal 150-location budget, 2,000-yard
radius and default 880-yard road proximity. All 150 locations generated and all
150 were connection-screened offline. Analysis measured 3.759 s, 250.113 MiB peak
RSS and 27,892,846 output bytes; analysis plus screening took 40.492 s, with source
preparation additional. Evidence:
`/tmp/huntmaps-pack-offline-1va4_c5_/default150-results.json`. This exposed and
verified the correction of a source/workspace-relative observer-path defect in
sampling; the fix preserves cwd, config, original polygon and source bytes. The
pack browser and repeated four-area acceptance now include default road proximity.

The existing Find browser fixture also exposed invalid catalog-response handling.
The unit selector now validates response shape and keeps Custom intake usable,
with an actionable catalog error, rather than crashing. Tests retain their original
assertions and limits.

## Preservation and remaining limits

Recoverable baseline: `.gui/pack-implementation-baseline/`, including initial
HEAD/status/patch, source archive and SHA-256 inventory. An additional recoverable
archive holds 1,146 original owner metadata records, and both supplied root reports
match the initial clean HEAD byte for byte. Current comparison passed:
**31,026 protected files / 5,344,747,854 bytes**, zero changed, zero missing and
zero unexpected additions. The 415 new protected-scope files are intentional pack
files/registration and retained discovery evidence. Final post-release audit:
`.gui/pack-implementation-baseline/final-preservation.json`. All **220 frozen
implementation/test files** remained unchanged during the final gate; original
HEAD is unchanged. Final patch, new-file archive and exact status are retained
beside the baseline for review. No requested implementation work remains.

No commits, pushes, resets, stashes, source deletion, historical regeneration,
model changes, owner-server testing or partition inspection occurred. Existing
analytical results, coordinates, masks, scenes, source datasets and owner decisions
remain preserved. Test state and servers are separate and disposable.

The local pack is a dated desktop source snapshot. It does not certify wildlife
probability, field sightlines, optics, land permission, safety or current closures.
USFS coverage is agency inventory coverage, not universal route completeness.
Detailed coverage is selected-area only. GDAL emitted a palette-copy diagnostic when
converting scientific cover to Float32; all output pixels/NoData and dependencies
were validated. Existing Matplotlib Axes3D and Vite bundle warnings remain nonfatal.
