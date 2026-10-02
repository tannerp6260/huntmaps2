# Scouting filters and provisional approaches — implementation acceptance

Implemented as additive GUI services and subprocess workers. Historical `glassing/`
code, model coefficients, scores, manual coordinates, source controls, supplied
reports and prepared first-person scenes are unchanged. No historical analyses or
first-person bundles were regenerated. All new calculations stop at provisional
independent approach results, not an itinerary or field-validation milestone.

## Contracts and implementation

- `scouting_network.py`: bounded WGS84 GeoJSON/KML/KMZ/GPX lines, preserved original
  bytes and source hashes, derived-geometry verification, retrieval versus unknown
  source dates, bounded USFS EDW roads/trails plans. Each response is limited to
  10 MB; combined reservation is 20 MB. Truncated/error responses fail; no fallback
  provider, paging expansion or automatic terrain expansion is used.
- `scouting_filters.py`: immutable versioned profiles sealed to DEM/network sources;
  exact nearest-segment projections, positive height difference, target elevation,
  slope and compass-aspect masks over saved visibility. Off means original targets;
  restricted aspects exclude flats. Matching areas and overlaps count aligned cells,
  not display pixels. Existing obstruction DEM and original scores stay intact.
- Optional observer sampling writes a separate, aligned eligibility exclusion and
  uses the existing transfer adapter interface. Intake tests prove target support
  and obstruction halo are identical before/after exclusion. The original polygon
  remains unchanged. Unknown required network/elevation does not qualify.
- `approach_search.py`: deterministic reverse directed Dijkstra over 20 m terrain,
  with eight neighbors, no corner cutting, exact travel/exclusion segment tests,
  invalid DEM and maximum cell/step slope exclusions. Network samples every 20 m
  include original vertices, nearest projections and pinned points. More than
  10,000 departures requires narrowing; inventories are never silently truncated.
  The trail graph has a 100,000-location guard and connects only supplied shared
  vertices, never arbitrary crossings or gaps. Interior crossing starts use the
  first source segment deterministically rather than creating a new junction.
- Nonnegative cost is exactly the requested distance, squared-slope, tree/shrub
  and positive-climbing expression. Mapped travel omits vegetation cost. Unknown
  vegetation receives maximum enabled penalties; average known off-trail cover and
  whole-path unknown fraction remain separate. Ground elevations are sampled from
  the modeled grid, without smoothing. Endpoint connections and every exported
  segment are checked; destination coordinates remain exact.
- Independent Recommended, Shortest distance and Brush avoidance objectives;
  coincident paths collapse their labels. A pinned departure is also inspected.
  Coverage remains a reported property, not part of any path objective.
- `approach_service.py` and `scouting_api.py`: immutable versioned scenario records,
  waypoint/source seals, result checksums, stale detection and explicit recomputation.
  The existing single active job service handles sequential kept setups and process
  cancellation. Worker limits remain 1536 MiB address space, 900 seconds, 3 million
  cells; no generated rasters are committed. There is no persistent cost-grid cache.
- New profiles, scenarios/results and source originals use configurable GUI state,
  shared maintenance locking and record backups; cache cleanup protects them. Existing
  display rasters remain regenerable cache. Historical evidence manifests are unchanged.

## Engineering verification

`./gui/check` includes the new approach/filter tests and an offline browser journey,
plus all existing GUI baseline, exports, comparisons, training, owner, vegetation,
working-waypoint/restoration, storage, first-person and neighborhood checks. Python
format, frontend format and TypeScript/production build checks are included.

The new checks exercise:

- exact segment proximity and US/metric conversion, missing network/DEM and positive
  height difference; terrain bands, eight-sector aspect logic and flats;
- exact matching areas, shared overlap and display alpha, retaining original masks;
- distance-versus-brush, steepness and cumulative climbing tradeoffs; a farther
  departure improving cost; network-start walking changing the recommendation;
- barriers, corner cutting, disconnected and crossing networks, unknown cover,
  exact endpoints, deterministic ties, inventory guards and no-path outcomes;
- independent recomputation of distance, gain/loss and every cost contribution,
  plus exported track lengths and exact destination readback;
- actual subprocess completion/cancellation, retained scenario definitions, stale
  decision blocking, offline source reuse, protected storage and backup references;
- displayed preference staleness, plan consent and pre-submission 1900 MB validation,
  desktop and 900-pixel screenshots with the provisional path and departure visible.

The frozen preservation checkpoint originally rejected **added** user runs as changes.
Inspection found zero modified/missing historical checkpoint files and 292 additional
files under four existing user-run folders. The audit now checks every recorded
historical byte without rejecting additions; the original manifest was not rewritten.
The full check still audits all current analysis/source/output files and owner records
before/after each invocation. Recorded successful audit: 7,519 protected files,
zero changes (`/tmp/huntmaps-check-w20nkqx3/protected-audit.json`).

## Measured performance and limits

A synthetic 100 × 100 grid (10,000 cells; 2 × 2 km), explicit travel area, brush stripe,
unknown shrub patch and selected mapped start evaluated 58 departures and produced
2 distinct alternatives. Measured least-cost service: **0.98 s**, **41.5 MiB peak RSS**.
This is an engineering fixture, not a real-area performance guarantee.

The isolated browser's actual worker with cached real terrain and artificial network/
travel inputs recorded **1.45 s**, **716.9 MiB peak RSS** in the first successful full
check. This includes imports, saved-run/source validation and GIS overhead. The complete
existing browser suite's server peaked at **1,108.8 MiB RSS**; that is cumulative across
all scene, review and maintenance journeys, not an incremental approach allocation.
Per-job metrics are retained under `scouting-metrics/` in configured state. Resource
failures name the limit and recommend narrowing rather than changing model controls.

Screenshots and detailed logs are retained in the printed disposable check directory;
examples: `screenshots/browser-scouting-check/20-scouting-desktop.png` and
`21-scouting-900.png`. Synthetic imported networks in these screenshots are test
fixtures, not mapped approach recommendations.

Live USFS bulk acquisition was not performed during verification. Offline mocked
responses verify consent/budget/truncation behavior; actual agency availability,
coverage, dates and current conditions remain unresolved until an approved user plan
is acquired. No parking, rights, walking-time, safety, ecological or field-validation
claims follow from these engineering checks. Fences, deadfall, water crossings, snow
and sub-grid cliffs remain unmodeled and are stated beside results and exports.

## Default network map overlay — 2026-10-01

Available networks now display by default during creation and review, independently
of filter and approach source selections. Surface/use classification is derived at
read time from preserved original GeoJSON/KML/KMZ/GPX sources; saved geometry,
checksums, IDs and scenarios are unchanged. Unknown classification stays unknown.
The compact legend shows loaded types, and source popups wrap long URLs.

Two full `./gui/check` runs passed. Final diagnostics:
`/tmp/huntmaps-check-yx4oqm_u`. Final elapsed time **7m38.57s**, peak backend RSS
**1,100.7 MiB** across the complete existing regression suite, including first-person
scenes; this is not incremental network-overlay memory. All **7,537 protected files**
were unchanged. Type metadata/multipart imports and seal reuse pass the backend
checks. Browser checks verify default toggles in creation/review, unaffected approach
exports after display toggles, reviewed download consent and a simulated acquisition
failure beside its control. Desktop/900-pixel screenshots were inspected, including
`20-scouting-desktop.png`, `21-scouting-900.png`, and `23-network-download-900.png`.
Live USFS acquisition remains untested in this pass; no bulk downloads occurred.

## Network response compatibility fix — 2026-10-02

Reproduced the owner's white screen against the running localhost backend:
`Cannot read properties of undefined (reading 'some')`. The backend process predated
the display-metadata API update and returned saved line-only inventories, while new
frontend assets assumed `display_features` existed. The approved acquisition itself
completed successfully (2 road segments and 18 trail segments); nothing needs to be
redownloaded.

A shared frontend response adapter now validates all three network-list consumers,
preserves exact geometry and builds unknown-subtype display features for older
responses. Invalid responses and network errors remain local to their controls;
empty lists explicitly show no data loaded. Import notifications now include the
network-type query parameter correctly. Restart guidance is in the GUI README.

Full `./gui/check` passed; diagnostics: `/tmp/huntmaps-check-8x9ib__i`.
Elapsed **7m53.11s**, peak backend RSS **1,372.6 MiB** across the entire suite,
not incremental network display memory. All **7,537 protected files** were unchanged.
The new browser regression simulates a successful approved download followed by
legacy responses, then checks current metadata, empty lists, malformed responses,
network failures and recovery. It independently verifies exact geometry and unchanged
input records. Desktop and 900-pixel screenshots under
`screenshots/browser-network-compat-check/` were inspected. Existing filtering,
approach/export, training, first-person and working-waypoint journeys also passed.
No acquisition or historical analysis was repeated by this fix.

## Observer proximity source correction — 2026-10-02

The owner's `test` (0.5 miles) and `test1` (2 miles) failed before proximity was
evaluated: acquisition rejected an empty per-kind network inventory, and both plans
had empty sampling source IDs. Selecting roads/trails as types did not select the
source datasets displayed on the map. A read-only geometric check of the imported
polygon against its loaded checksum-verified inventories found approximately 91.8%
of polygon area within 0.5 miles of mapped segments, and 100% within 2 miles. These
are buffered geometry checks, not DEM-valid sampling counts or walking distances.

Preparation can now freeze references to covering verified cached inventories with
zero network download reservation. Explicit refresh upgrades an older failed plan's
network review without rewriting its old network definition. Empty acquired inventories
are preserved as bounded query evidence; empty user imports still fail validation.
The worker preserves explicit selected IDs, or binds empty IDs to the reviewed plan's
inventory, validates usable lines before DEM acquisition, and records effective
settings and source checksums in new runs' `observer_sampling.json`.

New forms default to loaded source selections. Source choices and road/trail types
are explained separately, and source URLs use concise USFS labels in the sampling
panel. Missing selections without reviewed acquisition fail before plan submission.
No historical engine, target masks, obstruction terrain or manual coordinates changed.

Seven targeted filter/network tests pass, including fresh acquisition with an empty
road response and a usable trail response, zero-download cache reuse, seal failures,
source binding, a qualifying near-line point, and worker preparation/run integration
using a stub owner engine. Full `./gui/check` passed; diagnostics:
`/tmp/huntmaps-check-xdo5_m2z`. Elapsed **7m45.12s**, peak backend RSS **1,002.2 MiB**
across the whole suite. All **7,555 protected files** were unchanged. The browser
checks assert loaded source checkboxes are selected in a new sampling form; desktop
and 900-pixel scouting screenshots were inspected. No live acquisition or owner
analysis was rerun by this correction; failed partial runs remain available for
explicit refreshed-plan recovery.
