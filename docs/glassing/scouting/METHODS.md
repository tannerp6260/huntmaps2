# Actual-hunt scouting scope and methods

Authorized 2026-09-28 for GMU54 second rifle, DIY spike camp. This is a labeled desktop
handoff, not a new blinded validation study or a timed itinerary. Methods/results are
recorded after engineering inspection; no claim of new predeclared human validation.
Read REPORT.md, configs/scouting.json, and the frozen source/control manifests.

Editable preferences: 5–8mi/day, 2000–3500ft/day, remote public land; lower pressure and
mature bucks are preferences, not predictions. SIG Zulu6 16×50, optional Televid77
20–60×; no instrument-specific detection calibration. Legal season Oct24–Nov1, 2026
(CPW brochure PDF page39, printed page29, D-M-054-O2-R). Personal dates/camp/parking null.

Control: all 3,428 prior code/config/report/output files are hashed in
FROZEN_CONTROL.json. Original study is an 8km square centroid crop, not a hunt boundary.
Restored targets are the full2km disk on mapped FS ownership inside official GMU54,
with mapped private conflicts removed. All obstruction terrain remains. Non-FS is
excluded, including potentially usable BLM: the unit-only case is an explicit upper
bound, never eligible land. Mapped ownership still does not verify access or stalkability.
Existing 10m metric grid, 1.7m eye, 0.8m bare-earth target, curvature coefficient6/7,
GDAL viewshed, and candidate pool preserved. No surface placed on tree-top endpoints.

Attention: unchanged correction model, 30° ×500m coherent patches, 30min nominal budget,
0.02km²/min uncalibrated inspection rate,0.5min setup/patch. Same 50:50 seasonal
hypothesis/background and old stipulated morning angles; neither is a fall occupancy
forecast or date-specific sunlight. Raw area and 0–1/1–2km bands remain separate.
No new habitat/pressure/detection coefficients. Vegetation fractions reuse2023 USGS RCMAP30m annual composites (mixed acquisition dates),
nearest-neighbor aligned to the control grid. Canopy<10% is a low-cover target proxy,
not optical transmission or a measured glassable footprint.

Fine check: only C0068,C0095,C0049, original and four20m cardinal offsets. 1m USGS2019
project vs10m control, fixed360m target disk sampled at common10m centres, calculation
radius400m; no full-radius extrapolation, no field-truth claim. Existing C0064 checks
are retained without rerunning its investigation. Image inspection uses dated2019 NAIP:
0.6m native,1m setup export,4m context export. No automated image reading is human validation.

Access: expanded from30km square to50km square; federal and Colorado BLM inventories,
CDOT county roads, CPW documented entry/parking and USFS recreation sites. Queried
intersecting routes retain their full geometry. Exact vertex-segments are deduplicated.
Shared source vertices round to0.01m; no arbitrary crossing noding. Same named/numbered
route endpoints may join vertices/projected segments within5m; Sun Creek/Detour name
continuity additionally limited to2m. Every repair logged. The chosen Steers Gulch
witness uses one repair. Larger/unsupported gaps remain disconnected, not inaccessible.
Entry-to-network symbol/point offsets remain unresolved and are not silently repaired.
Motor eligibility checks high-clearance MVUM date intervals covering the whole legal
season (not only yearlong roads); malformed intervals rejected. BLM motor-class and
county jurisdiction evidence remain conditional, not certification of parking/drivability.

Each candidate's approach is a single witness, not an optimized itinerary. Mapped
pedestrian shortest-distance witness plus bounded terrain-screened final leg, tested
at up to6 departures. 20m ground grid, FS/BLM minus private, <=30° cell/step slope,
no diagonal corner-cutting; mapped waterbodies excluded with20m buffer. Slope search
cost length×(1+(slope/15)²) is an explicit heuristic, not a physiological/safety model.
Streams may cross the leg; counts/names and tree-cover fractions are reported, not
converted into invented passability. Fences, deadfall, snow and microcliffs remain unknown.
Route gain is20m sampled and smoothed by one sample to limit raster noise; no vertical
datum correction is implied. Return effort adds both outward gain and loss. Time range
uses1.5–3km/h plus300–600m/h ascent allowance, excludes glassing/rest/load/snow effects.
Both documented-entry foot and conditional road-end foot effort are shown. An entry
symbol offset is not included as a fabricated connecting path. No campsite selected.

Exports: EPSG32613 GeoPackage/GeoTIFF, WGS84 GPX/KML. GPX waypoints only; no navigation
tracks. Three primary positions, C0090 separate reserve; C0064 analyst control only.
KML10m simplification intersected with original eligible sectors to prevent enlarging
into excluded support. Sectors contain hidden/wooded terrain; actual visible cells
are separate GeoTIFFs. Export coordinates/geometry/CRS are read back and checked.
All new labeled material lives under runs/scouting, apart from previous blinded packet.

Budget:180MB retained downloads,800MB outputs,2GiB address-space,900s per command.
No changes to system Python/dependencies, no paid services/publication or unit-wide fine
terrain. Source snapshot locks fail on changing remote content rather than silently
substituting a different experiment. Prior input acquisition/reproduction is described
in ../README.md. This milestone stops at report/review exports.
