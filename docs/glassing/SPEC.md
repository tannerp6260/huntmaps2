# Terrain baseline specification

Objective: test a reproducible terrain-visibility foundation for a western mule deer
observation experiment. The supplied methodology report is a hypothesis, not evidence
of improved sightings. This milestone implements neither a hunting recommender nor
an access certification.

Terrain visibility, glassability, habitat suitability, seasonal use, legal/physical
accessibility and strategic value remain distinct. Only terrain visibility is scored.
Unknown access is explicitly retained for desk analysis; the field-ready shortlist
is empty. Ownership alone cannot establish a connected permitted approach.

Contracts: projected north-up square metric grid (EPSG:32613 for the pilot), float32
bare-earth elevations in metres, explicit vertical reference (unknown allowed with
warning), and separate aligned byte study/observer/target masks. NoData or nonfinite
terrain is a hard error. Bilinear DEM reprojection; nearest/centre-in-polygon masks.
No vertical datum correction is implied by horizontal reprojection. Unknown datum
prevents combining vertical datasets; within one DEM constant offsets cancel, but
spatially varying bias and seams can alter marginal sightlines.

150 reproducible candidates: distributed background plus heuristic benches,
shoulders and ridge breaks, with optional manual projected points. These are terrain
proxies, not certified landforms or safe positions. Preserve merged provenance.
GDAL viewshed is the initial engine, explicit 1.7 m eye, 0.8 m target, curvature
coefficient 6/7 (refraction 1/7). Radius 2 km baseline; 1/3 km sensitivities. Retain
terrain at least maximum radius plus two cells beyond the study bounding box.
Score planimetric visible eligible target area using cell area, in 0–1, 1–2, 2–3 km
bands. No slope surface-area inflation or deer weighting.

Initial budgets from audit: <=2,000,000,000 bytes new downloads, 4 GB experiment disk,
2 GB process address space, 900 seconds per command, sequential execution, <=200
candidates, <=3 million grid cells. These are configurable trial guards, not scale claims.

Acceptance: offline flat/ridge/heights/NoData/units tests; independent sightlines;
resolution-area stability; excluded targets retain obstructions; export read-back;
repeatable staged commands; synthetic and real run or precise external blocker;
measured runtime/memory/cache and inspectable QGIS outputs. No field-ready claims.

## Authorized matched-comparison extension — 2026-09-26

The user authorized this milestone after the terrain checkpoint. The original
baseline source/configuration/run remains the read-only control. New code lives in
comparison_data.py, comparison_models.py, compare.py and comparison_review.py.
New configuration: configs/comparison.json; source lock: comparison_sources.lock.json.
Predeclared independent criteria and amendments: comparison/PROTOCOL.md.

Common 150-point pool, AOI, technical masks, 2km radius, 1.7/0.8m endpoints and
curvature are frozen. Every proposed position has a 30-minute observation session;
four nominated positions mean four separate sessions (120 minutes), not a route.
Primary raw terrain and habitat scores remain unbounded geometry/weighted geometry;
all three also export the SAME limited-inspection surrogate for equal effort. Raw
control scores are never relabeled as searchable area. M3 primary includes that
surrogate; leave-one-feature-out analyses expose this important distinction.

Seasonal use uses CPW summer/winter range and one additive shrub/herb browse composite,
with positive background everywhere. No occupancy probabilities or slope/aspect/road
bonuses in habitat. Target searchability, distance task, perspective and stipulated
light are separate, switchable hypotheses. Foreground/path canopy stress tests are
separate from target cover and OFF in main M3. Coarse fraction only flags potential
opaque columns of assumed heights; ground endpoints remain on bare earth. Finite
inspection is an uncalibrated uniform-area allocation surrogate, not human scan skill.

Unknown access remains explicit. Random sampling is stratified within the SAME
technical pool; legal feasibility is pending without connected permitted route evidence.
Optional access constraints apply equally to all arms. Target follow-up evidence is a
separate raster and never removes obstruction terrain. Roadlessness/pressure preferences
are exported separately; no route or measured-pressure model is invented. Expert imports
retain provenance and are evaluated separately; independent expert comparison is pending.

Sensitivity includes fixed feature/season/task/light/budget alternatives, 10 versus
30m terrain, 400-point dense 4km² reference, and two exploratory local 400m 1m checks.
No unit-wide fine terrain or fine vegetation claims. Review protocol reserves spatial
held-out locations and supplies blank equal-effort blinded sheets. Scores/rank changes
are hypotheses, not validation. Stop after the comparison report and reproducibility checks.

## Corrective-validation extension — 2026-09-26

User-authorized bounded correction, documented in correction/PROTOCOL.md and REPORT.md.
Frozen control: correction/FROZEN_CONTROL.json (3,340 prior files). New code/config/runs
remain separate. Selective attention uses whole polar patches with fixed full-footprint
cost, nonnegative rewards, explicit overhead and conservative quarter-minute knapsack.
Optional terrain must not decrease achievable value; uniform and unlimited ablations remain.
Undated seasonal mixtures reuse existing hypotheses and retain positive background.
C0064 geometry comparisons use common 400m target support; nearby setups share 360m support.
These local values never replace the unchanged 2km ranks. Both catalog vertical references
are NAVD88/metres; source processing/age/datum realization remain uncertain, not corrected.
Access geometry is mapped evidence, with unmapped gaps separate from connectivity witnesses;
no witness is a navigation route or legal/physical certification. Dated imagery and blank
blinded review materials are separate from analyst ranks and keys. Acceptance requires
monotonicity/exact-budget tests, matched spatial checks, frozen control verification,
repeated stable scores, GIS read-back and explicit unresolved human evidence. Achieved for
engineering only; no field-readiness or observation-effectiveness claim is accepted.

## Authorized actual-hunt provisional scouting extension — 2026-09-28

GMU54 second-rifle2026, DIY spike camp, supplied optics and editable5–8mi /
2000–3500ft daily preference. Personal dates, camp and parking are unspecified.
Preserve all previous controls and blinded materials. Separate full2km mapped-FS/GMU
support from the centroid crop; retain bare-earth obstruction everywhere. Review
C0068,C0095,C0049; retainC0090 reserve,C0064 sensitivity control and randomC0025.
Produce documented-entry/conditional-road and terrain-screened single-approach evidence,
not a full itinerary. No new habitat coefficients, pressure forecasts or mature-buck
probabilities. Observe unknown parking/permissions, vegetation and stream crossings.
Acceptance: dated imagery/setup cards, overview/actual-GMU context, GPX/KML/GPKG,
component table, targeted correctness/export read-back and frozen controls verified.
Scope/methods: scouting/METHODS.md; final evidence/recommendation: scouting/REPORT.md.
Stop at provisional scouting handoff; labeled user review is not blinded validation.

## Hunter-selected AOI transfer — authorized 2026-09-28

Reusable adapter over existing core/compare/attention, preserving all6,227 prior
artifacts and frozen model assumptions. Independent terrain/background automated pool;
manual coordinates/IDs/source records remain unchanged. Observer domain, observation
targets, terrain halo and access extent are separate. Same per-position observation
settings/budget for both groups; raw area/distance/open-cover/selective scores remain
separate. Bounded symmetric local refinement is diagnostic, never added to the primary
pool. At most five automated alternatives plus all manual points; overlap table and
validated GPX/KML/GPKG/PDF. Access evidence is configured, never pilot-specific.
Required real inputs: hunter observer polygon and manual waypoints. Neither exists;
synthetic fixtures demonstrate engineering only. No Soap Creek boundary chosen.
See transfer/INPUTS.md, PROTOCOL.md and REPORT.md; stop at missing-input handoff.

## Owner usability milestone (2026-09-28; supersedes required-manual normal intake)

Normal scouting requires only an owner-selected observer-search polygon. Manual
points are optional comparison inputs; historical matched experiments retain their
original protocol. `./scout` is the entry point; see START_HERE.md. Observer, target,
terrain-halo and access extents remain separate. GeoJSON/KML/KMZ import must preserve
originals and require explicit selection for multiple polygons. Normal analysis
must work without historical ignored runs, while validating current sources,
configuration, frozen model implementation, runtime and derived outputs. Historical
verification stays opt-in; archive hashes must not be rewritten. Output is provisional
and inspectable without field validation. Bulk source plans show an estimate and cap;
unsupported acquisition must name the missing source/configuration field. No new
scoring model or route optimization. Acceptance: isolated no-manual, optional-manual,
archive-free and corrupt-current-input tests pass, with clear maps/reports/exports.

Acquisition validity clarification (Soap Creek real-run regression): source geographic
coverage and valid-data coverage are distinct. Obstruction DEM must remain valid;
vegetation NoData must propagate through the existing unknown-cover mask, never be
reclassified as open/zero cover. WCS boundary padding must not change owner/target
polygons. Replacements and agency normalization/geometry repairs retain raw sources,
checksums and explicit provenance; unrecognized CRS or incomplete responses still fail.

Derived review maps must display actual evaluated visibility separately from attention
footprints, verify transform alignment and mapped area against saved scores, and retain
imagery dates/native versus exported resolution. Derived packets use separate integrity
records; original numerical results and packets remain unchanged.
