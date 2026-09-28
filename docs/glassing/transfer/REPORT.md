# Hunter-selected transfer: portability complete; real comparison pending

The reusable configuration/import work and offline checks are complete. **No hunter
AOI polygon or manual waypoint set was found.** We have not selected a new centroid
crop, invented Soap Creek basins, or treated previous model exports as your choices.
The exact next inputs are described in [INPUTS.md](INPUTS.md).

The existing pilot and all6,227 frozen prior artifacts remain unchanged. There is
no new real-area scouting recommendation yet: usefulness versus manual work requires
your area/points and subsequent imagery/access review. Engineering portability alone
does not establish hunting value.

## Audit and minimal architecture decision

The existing reusable pieces are `glassing/core.py` (metric grids, terrain candidates,
GDAL visibility), `compare.py` (components), `comparison_models.py` (frozen hypotheses),
`attention.py` (whole-patch budget), and `scout_access.py` (network/terrain primitives).
The old scouting driver/packet contains named entries, coordinates, five IDs and paths
specific to its completed pilot. Editing it would also invalidate its frozen controls.

Added thin `transfer.py`, `transfer_access.py` and `transfer_packet.py` adapters using
those functions; no replacement engine, plugin framework or broad refactoring.
`configs/transfer.template.json` supplies AOI, data/work paths, metric CRS, resolution,
radius, scenarios, common observation budget, hiking preferences, access extent/entries
and local refinement budget. `transfer_model.lock.json` freezes existing coefficients
and underlying model implementations. `transfer_fixture.py` is solely an offline test
fixture with an explicitly different metric zone (EPSG32612); default hunt config is32613.

The older expert importer rounds to cell centres. It was preserved, but is not used
for this comparison: new GPX/GeoJSON/CSV imports retain source IDs, exact original
longitude/latitude, projected point locations, attributes, selection provenance and
source checksums. The containing DEM cell and centre offset are recorded separately.
Raster terrain still has finite resolution; unchanged coordinate export is not a
claim of sub-cell viewshed accuracy.

Search included ignored data/runs, spatial formats, JSON and archive names throughout
this workspace; see [inventory](WORKSPACE_SPATIAL_INVENTORY.txt). Available polygons
are agency/experimental inputs, and available waypoints are generated outputs. Git
status remains unavailable (`not a git repository`); no commits/resets/cleanup/pushes.
Observed environment: approximately3.4GiB available RAM and26GiB free disk. Existing
isolated Python/native GIS dependencies were reused without installation.

## Implemented comparison contract

- Observer-search polygon, observation targets, terrain halo and access-data extent
  are separate. Default targets extend one observation radius beyond the search area;
  explicit target restrictions/exclusions are supported without erasing obstruction.
  Initial surrounding access buffer10km is configurable; it is not a connectivity finding.
- Manual locations must lie within the supplied observer domain. Invalid/outside points
  fail explicitly; none is silently moved, dropped or injected into automated generation.
  Terrain-derived and stratified background candidates use a fixed independent seed.
- Both groups receive the same target support, grid, eye/target heights, radius,
  frozen seasonal/cover/distance/perspective/light hypotheses and per-position budget.
  Raw terrain area, distance split, low-tree-cover proxy and selective score are separate.
  Old light angles remain hypothetical. No habitat or pressure coefficients were added.
- Symmetric local refinement around each group's leaders is a bounded density diagnostic,
  excluded from the primary pool. Its score gains do not validate a hunting improvement.
- Leading exports contain at most five automated alternatives and all manual points.
  Pairwise overlap includes shared visible-target km², Jaccard and directional fractions.
  Nearby automated recovery is identified as a setup hypothesis, not ecological agreement.
  Obvious useful misses and questionable ranks await actual imagery/human adjudication.
- Configured entry/route schemas replace pilot-specific access entries. The generic
  adapter uses documented source vertices/small supported gaps and terrain-screened
  final legs. Missing entry/permission sources yield pending effort. Incomplete approach
  elevation yields missing gain/time, never a zero-gain assumption. No parking or timed
  itinerary is inferred. Imported reviewed approach evidence can also be displayed.
- GPX/KML/GeoPackage and a labeled PDF are generated and read back. Actual imagery is
  displayed only from supplied checksum-verified raster sources; absent imagery stays
  visibly pending. Every synthetic page is labeled. This is not a blinded review packet.

See [fixed protocol](PROTOCOL.md) for the comparison and [commands/schema](README.md)
for operational details. Exact provider requests can be pinned through the existing
bounded Fetcher; actual product selection/acquisition awaits the hunter polygon.

## Checks actually run

```sh
.venv/bin/python -m glassing.transfer intake --config configs/transfer.template.json
.venv/bin/python -m glassing.transfer_fixture
.venv/bin/python -m glassing.transfer all --config configs/transfer.fixture.json
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m glassing.transfer verify --config configs/transfer.fixture.json
```

The real-input intake reports exactly these missing files:

```text
inputs/hunter/observer_area.geojson
inputs/hunter/manual_points.gpx
```

The artificial fixture successfully runs24 automated and2 synthetic manual-style
points, symmetric local refinements, seven review positions and21 pairwise overlaps.
It is not a new hunting AOI and contains no human/expert selections. Complete offline
runs take about5.1–5.5s, with observed peakRSS approximately218–219MiB and about1.6MB
outputs. These are fixture measurements, not a performance claim for150 real2km viewsheds.
Acquisition this milestone: **0 bytes downloaded, $0 service spend**. New real-AOI
runtime/data cost remain unmeasured.

**29 tests pass** (22 prior plus7 transfer checks). Added checks cover unchanged
coordinate imports across three formats, invalid coordinates/domains, separated
spatial support, manual edits not altering the automated pool, frozen-path protection,
known-empty versus missing seasonal data, configured synthetic entry/terrain access,
and fixture export/overlap integration. Existing independent sightline, unit/NoData,
area/resolution and attention checks still pass.15 substantive output products are
byte-identical across repeated fixture runs; timestamped containers have semantic
read-back checks. Source/model/derived hashes protect against mixed configurations.

Fixture packet rendering was visually inspected. Existing Matplotlib warns that its
3D projection is unavailable; only working2D plotting is used. No actual new-area
imagery interpretation, legal-access adjudication or field detection check was made.

Fixture artifacts: `runs/transfer_fixture/review_packet.pdf`, `components.csv`,
`overlap.csv`, `comparison_review.json`, `review.gpx`, `sectors.kml`, `comparison.gpkg`,
`refinement.json`, `execution.jsonl` and `repeatability.json`. These are diagnostic
fixtures, **not field exports to use for hunting**. Hunter run directory currently
contains only intake/implementation/resource records identifying missing inputs.

## Stop and handoff

Supply your **observer-search polygon** and **unchanged manual glassing waypoints**.
GeoJSON polygon plus GPX waypoints is the simplest intake; CSV/GeoJSON points also
work. A KML/KMZ polygon can be supplied for an explicit conversion, but direct polygon
KML/KMZ import is not represented as implemented. No camp/trailhead choice is required.
See [precise file instructions](INPUTS.md).

Recommendation at this checkpoint: proceed to the real matched comparison once those
inputs arrive. There is insufficient evidence to choose “useful assisted scouting,”
“one correction needed,” or “little benefit” for the new area yet. Stop here rather
than tuning the old candidates or inventing an area. Field access and detection
performance remain separate, unverified questions.
