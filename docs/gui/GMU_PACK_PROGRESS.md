# GMU local pack implementation progress

Started 2026-10-19. User authorizes a complete local Colorado GMU 54 core pack and
unit-first Find → Approach → Inspect → Save workflow; preserve all existing data,
controls and owner state. No commits/pushes/deletions, partition inspection, model
changes or route optimization. Verification must use isolated application services.

## Baseline and audit

- Initial working tree clean on main; actual checkout includes habitat work.
- Ubuntu filesystem: 234G total, 130G used, 93G available (df, initial measurement).
- Recovery baseline: `.gui/pack-implementation-baseline/` includes initial HEAD,
  status/patch, recoverable source archive and protected SHA-256 inventory.
- Read root AGENTS, START_HERE, glassing SPEC/PLAN/STATUS/usability and GUI testing,
  audit/connectivity, acquisition/first-person recovery and habitat reports.
- Existing source reuse strictly matches product/year/request footprint and imports
  exact verified bytes into persistent `.gui/sources`; display caches are separate.
- Current GUI selects annual RCMAP 2023 via rcmap_sources policy 1. CLI source
  adapters remain frozen. Owner provisioning accepts explicit checked descriptors.
- Terrain halo, observer eligibility and target domains must remain separate.
- Existing scene failure evidence includes dense ground processing limit and stale
  cache inventory; acquisition alone cannot resolve those. Existing repairs retained.

## Decisions / completed work

Audit in progress. Favor immutable pack directory + atomic catalog registration,
explicit checked descriptors for bounded local jobs, and a narrow local network
adapter. Do not weaken existing compatibility checks.

## Verification

Pending. No readiness or acceptance claim yet.

## Blockers

None established. Official boundary/catalog and source support still need checking.

## Exact next action

Finish source/network/scene/API/UI trace; inventory local assets and recent failure
logs; verify official GMU boundary and measure buffered support before acquiring.

## Implementation update

- Captured 31,026 protected files, 5,344,747,854 bytes in baseline.
- CPW current official boundary: 1,513.764662 km², WGS84 bounds
  [-107.424256066236,38.448864897896,-106.845480215162,38.8706450999632].
  Feature EDIT_DATE 2023-12-28; current layer edit metadata retained separately.
- TNM products endpoint returned HTTP 504. Valid fallback is the USGS official
  public staged-products S3 catalog, with exact sizes and tile-specific XML.
- Elevation: compatible verified local n39w108_20220331 (415,482,393 bytes)
  reused; n39w107 current catalog 407,666,304 bytes acquired. NAVD88/metres
  verified from tile metadata; different source vintages explicitly retained.
- 20 GiB reserve unchanged. Pack build cap 1.5 GB cumulative transfers; conservative
  additional headroom 3×cap +4 GiB, checked against measured free space.
- Buffered data envelope: unit bounds +10,440 m aligned at 30 m, covers access
  10 km, visibility ≤3 km, terrain gutter 20 m, habitat neighborhood ≤360 m.
- Habitat full-source processing requires explicit persistent aligned local crops;
  adapter adds 480 m neighborhood/native-grid support without changing values.
- Version/seal/catalog, bounded import adapters, unit selection/map context and
  default offline basic inspection implemented; verification not yet complete.
- New failure log evidence: grid limits, HTTP500, dense vegetation memory; separate
  from provider coverage. Existing scenes and failed records remain untouched.

Next: finish actual build and verify data support, then run real offline areas and
fault regressions, fix demonstrated integration issues, stabilize full ./gui/check.

## Real pack published / first acceptance evidence

- Registered `data/unit-packs/versions/co-gmu54/20261019-v1`, sealed immutable
  contract 1; `data/unit-packs/catalog.json` selects that version.
- Actual transfer ledger: 500,597,188 downloaded bytes, 415,482,393 reused bytes;
  retained pack asset bytes 1,040,004,031 (manifest/seal/progress overhead extra).
- Prepared terrain: EPSG:32613, metres/NAVD88, 7188×6693 at 10 m; zero unknown
  obstruction cells across support [278040,4247850,349920,4314780].
- Cover: 2396×2231 at 30 m, annual 2023 tree/shrub/herb; each has 154,753
  intrinsic unknown cells (about 2.9%). Every padded source piece passed geographic
  footprint checks. Unknowns remain unknown; no open-cover replacement.
- CPW seasonal queries and USFS roads/trails queries use bounded 18 km pieces,
  independent count queries, exact response-count agreement and retained metadata.
- Interrupted actual preparation was cancelled and restarted; completed pieces
  reused, existing prior data untouched. No incomplete version advertised ready.
- Lifecycle regressions pass (6): bounded crop/known pixels; offline imports;
  same-size/mtime corruption; missing data; failed updates; reserve; cancellation,
  retry, retained partials and cumulative transfer accounting.
- First registered browser journey passed, diagnostics `/tmp/huntmaps-check-xd4bd3r9`:
  real pack selection/map, custom switching, fresh real-data search, desktop/900 px,
  no browser errors or external requests.
- First offline services pass generated two fresh areas and completed screening,
  approach, basic view, confirmation, export/reload. The third screen stopped
  correctly after implementation changed during active development. This is an
  interrupted development check, not final acceptance. Fresh isolated rerun underway.

Exact next action: stabilize code, complete 3-area socket-denied acceptance plus
actual browser Basic render, then full release gate and final byte preservation audit.

## Immutable update and stabilization

- Published `20261019-v2` by explicit reuse of v1 source snapshot. No provider
  requests/new downloads for update; reused 916,079,581 source bytes. v1 remains
  sealed and readable; catalog now selects v2. Real update exercises separate
  preparation and atomic publication while previous ready version remains usable.
- Corrected current east tile date metadata from S3 object-modification timestamp
  to official XML publication date 2026-07-01 (title date 2026-06-30). Actual mixed
  acquisition time period remains explicit; western reused tile is 2022 publication.
- V2 physical bytes 1,040,079,696; retained v1 physical bytes 1,040,056,280.
- Strict validator exposed an inherited `reuse_origin` marker in a derived v2
  window. Explicit adapter v2 records original pack-source provenance separately,
  keeps exact local window checksums, and does not present a crop as an exact raw
  import. Original strict `source_reuse` validation remains unchanged.
- Added successful update, interrupted registration, damaged progress isolation,
  unrecorded raster companion and inherited-provenance regressions. 9 focused tests
  pass. Runtime checks TIFF dependencies before use as well as sealed checksums.
- Saved-run map context now preserves local zoom; new-area selection centers unit.
  Recovery restores pinned unit context. Unit/custom switching retains preferences
  but clears obsolete imported area/results context. Existing owner records untouched.
- Full gate was restarted after stabilization. Current log:
  `/tmp/huntmaps-pack-release-stable.log`; full gate must finish before final claim.
- Final socket-denied v2 acceptance includes a fourth new window crossing the DEM
  source-tile boundary, in addition to western/central/eastern areas. Current log:
  `/tmp/huntmaps-pack-offline-v2-final.log`. Earlier v1 3-area pass is retained.

Exact next action: complete v2 acceptance/browser and full gate; inspect final images,
record source-resolution/coverage/storage measurements, and compare baseline bytes.

## Final acceptance / preservation evidence

- V2 socket-denied acceptance passed all four fresh real areas, including the DEM
  tile seam, with no external attempts during core service workflows. Each new
  475×485 analysis has valid terrain, explicit unknown vegetation, exact metric
  coordinates, selected approach, Basic scene, confirmed state and GPX/KML reload.
  Independent export/coordinate error <1.1e-9 m. Evidence:
  `/tmp/huntmaps-pack-offline-1va4_c5_/`.
- Latest production-build browser also passed held actual unit replies across
  unit→Custom switching, preserved habitat preferences, ready visible coverage,
  current Basic renderer and desktop/900 px. Log `/tmp/huntmaps-pack-browser-final.log`.
  Screenshots `latest-browser-screenshots/` under the same acceptance directory.
- Separate Custom switches deliberately exercise optional generic road browsing:
  252 backend attempts to carto.nationalmap.gov were denied across retained browser
  passes. No live connection succeeded. These are display-context attempts outside
  the ready-pack core journeys, not hidden analytical/source dependencies. Direct
  browser external requests/page errors remain zero. Report distinguishes scopes.
- Pre-close preservation audit: 31,026 original protected files / 5,344,747,854 bytes,
  zero changed/missing, 415 intentional pack additions, zero unexpected additions.
  Evidence `.gui/pack-implementation-baseline/review-preservation.json`.
- Final build and formatting pass; final implementation/test fingerprint (220 files)
  is stable. Full release log `/tmp/huntmaps-pack-release-verified.log`, diagnostics
  `/tmp/huntmaps-check-q1107p9v`; backend tests and real 600-location recovery passed,
  mandatory browser journeys now running. No completion claim before final gate.

Exact next action: finish all mandatory browser journeys, inspect final diagnostics,
perform final protected/source-input hash comparison and finalize report/archive.

## Default-setting blocker found and corrected

An additional real 150-location/9 km²/default 2,000-yard test with default road
proximity sampling exposed a genuine source/workspace path defect: the sampling
adapter read `results/.../observer.geojson` relative to the source checkout in an
isolated workspace. Source acquisition was already complete; downloading could
not fix it. `scouting_filters.sampling_exclusion` now resolves observer and DEM
paths against AppConfig.workspace without changing cwd or saved config/geometry.
The new regression uses real rasters/network lines and different cwd/workspace.
10 pack regressions and 7 existing scouting-filter regressions pass.

Actual corrected default run `pack-default150-fixed`: 150 generated, 150 screened,
9 km², radius 1828.8 m, output 27,892,846 bytes, analysis 3.759 s, peak RSS 250.113 MiB;
analysis + connection screening 40.492 s (preparation additional), zero external
attempts. `/tmp/huntmaps-pack-offline-1va4_c5_/default150-results.json` and
`/tmp/huntmaps-pack-default150-fixed.log`. This is one bounded observation, not a
unit-wide or 5,000-location performance claim.

The earlier full gate passed backend/recovery and seven initial browser journeys,
then the existing Find controlled fixture exposed a new catalog-response handling
issue: its unknown endpoint replied `{}`, which the new selector treated as an
array-bearing catalog and crashed. The selector now validates response shape and
keeps Custom intake usable with an actionable local error. Original browser
assertions/time limits were not weakened. Focused Find/pack browser rerun underway.

The decisive 4-area acceptance now explicitly includes default road proximity in
all areas, and the mandatory real-pack browser also includes it. Current acceptance
`/tmp/huntmaps-pack-offline-defaults.log`, state `/tmp/huntmaps-pack-offline-c5opa2a2`.
Final complete release was restarted after these demonstrated fixes:
`/tmp/huntmaps-pack-release-final-complete.log`. Prior incomplete gates retained.

Exact next action: finish the defaults acceptance and focused browser checks, then
all stages of the final full gate; refresh final audit/report with those exact results.

## Export closure and final frozen gate

- Destination exports already retained pack identity. Added the same immutable
  identity to approach GPX metadata and GeoJSON properties; track/destination
  coordinates and provisional notices stay exact. A dedicated regression passes,
  plus actual service read-back on all four completed real approaches:
  `/tmp/huntmaps-pack-offline-c5opa2a2/approach-export-validation.json`.
- Sampling path correction also preserves shared historical raster resolution:
  workspace-local inputs resolve first, and absent relative dataset paths resolve
  against the source checkout with exact checksum validation. Existing damaged
  files never trigger a source fallback. The original observer/target/halo regression
  remains intact. Focused pack 11/11 and approach 22/22 passed.
- Focused original Find + real-pack browser gate passed:
  `/tmp/huntmaps-check-xqk2ch4s`.
- Default-proximity 4-area socket-denied acceptance passed:
  `/tmp/huntmaps-pack-offline-c5opa2a2`; independent final pyproj/GPX/KML/DEM and
  sampling read-back passed, max coordinate error 1.0413e-9 m.
- Final implementation/test inputs frozen again after those demonstrated fixes.
  Current mandatory full gate log `/tmp/huntmaps-pack-release-final.log`.

Exact next action: allow all mandatory tests/browser journeys to finish, then only
final documentation, preservation comparison and recoverable review archive.

Final fault closure: missing/malformed seals and catalogs now raise explicit recovery
errors instead of key/type errors; bytes are retained, and explicit pinned-version
resolution still works with a damaged catalog. Added controlled-record corruption
regression; 12/12 focused pack tests pass. Final current complete gate log is
`/tmp/huntmaps-pack-release-complete.log`; source/test fingerprint is frozen.

## Completed handoff

Final full `./gui/check --keep-going`: exit 0. 300 backend tests across 12 groups;
32/32 mandatory browser journeys; all formatting/build checks; actual interrupted
600-location recovery and follow-on workflow; original assertions/time limits intact.
Diagnostics `/tmp/huntmaps-check-irdt1d4n`, log `/tmp/huntmaps-pack-release-complete.log`.
Runner's independent source/result audit: 8,270 paths unchanged; owner/companion
records unchanged. Final separate byte audit: 31,026 original protected files /
5,344,747,854 bytes unchanged; 415 authorized pack additions; no unexpected paths.
Both supplied reports unchanged from original HEAD; 1,146 original owner metadata
records archived. All 220 final implementation/test fingerprints and HEAD unchanged.

Actual registered core pack: `co-gmu54 / 20261019-v2`; persistent root
`data/unit-packs/versions/co-gmu54/20261019-v2`. V1 retained. Four newly generated
real areas completed the full offline service workflow with default proximity,
and all four actual Basic scenes rendered in a separate socket-denied browser.
Additional real default 150-location generation + screening passed offline.
Current detailed readiness remains selected-area; no whole-unit LiDAR claim.

Handoff: `docs/gui/GMU_PACKS.md` (start/recovery instructions),
`docs/gui/GMU_PACK_REPORT.md` (datasets, dates, support, storage and verification).
No commits/pushes, original-data deletion, historical regeneration, owner-server
operations, Windows/Data partition inspection, field collection or model/itinerary
optimization. Changes remain uncommitted for review.

Exact next action: no further implementation is required. Restart HuntMaps2 with
`./huntmaps-gui`, choose New scouting area → Colorado GMU 54, then draw/import a
manageable local observer area and use Find → Approach → Inspect → Save.

## Satellite context follow-up

User screenshot exposed that unit mode suppressed the existing optional online
imagery component entirely. Restored that component for prepared units, respecting
the stored on/off preference and existing raster order (online imagery above local
relief, below saved imagery and analytical overlays). Core pack assets are unchanged;
offline relief remains available. Recoverable pre-fix code/docs and diff are under
`.gui/pack-implementation-baseline/satellite-followup/`.

Focused isolated gate passed (`/tmp/huntmaps-check-42xqmpx0`): real new pack run
still resolves locally with zero browser external requests while imagery is off;
separate default-on display check verifies rendered tile pixels above relief,
off preference across unit/custom switching, scoped offline fallback and retry.
Controlled tile responses test display composition only. A separate real-provider
browser successfully loaded 50 USGS aerial tiles at GMU 54 with no page errors;
screenshot `/tmp/huntmaps-pack-satellite-live/gmu54-satellite.png`.

The old implementation baseline comparison identifies two owner metadata changes
and 94 cache/job additions, all predating this follow-up's recoverable code baseline
(latest 00:40:56 UTC, baseline 00:41:03 UTC). Those user-session changes are retained.
A current protected-file snapshot (31,535 paths) and that classification are saved
under `satellite-followup/`; no historical metadata is restored over live owner work.

Follow-up verification completed:
- Focused pack browser gate passed, including real local generation and the new
  default-on imagery/toggle/fallback/retry assertions.
- Actual online GMU 54 imagery rendered: 50 successful USGS tiles, zero page errors.
- Full `./gui/check --keep-going` ran all checks: 300 backend tests passed;
  formatting/build passed; 31/32 browser journeys passed. Its exit was 1 due to
  `browser-scouting-check` timing out at the original 30-second imported-network
  selection assertion while an approach suggestion was intentionally held.
  Log `/tmp/huntmaps-pack-satellite-release.log`, state `/tmp/huntmaps-check-xfbmbsfv`.
- The exact unchanged scouting check passed in a separate fresh-state gate:
  `/tmp/huntmaps-check-1s7kks_u`, log `/tmp/huntmaps-satellite-scouting-focused.log`.
  This intermittent failure was not reproduced there; its cause is unproven.
  Assertions/timeouts were not relaxed, and scouting implementation was not changed.
- Both gate preservation checks report 8,270 protected paths and owner records
  unchanged. Separate follow-up snapshot comparison: 31,535 files unchanged,
  no missing files or additions. Pack bytes/versions are unchanged.

Exact next action: refresh the browser to load the rebuilt UI; select GMU 54 and
leave **Map layers → Online imagery — fill gaps** enabled for aerial context.
The reported satellite defect is fixed. The intermittent broader-suite network
selection timeout remains a recorded testing limitation, with both outcomes retained.
