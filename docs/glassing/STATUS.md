# Status / execution journal

2026-09-25 audit: only two supplied Markdown documents exist; no HuntMaps code,
entrypoints, local data, dependency manifests or tests. `git status --short --branch`
reports not a git repository; .git is an empty read-only directory. No ancestor or
workspace AGENTS.md existed. Supplied methodology report read; no broad research repeated.

Commands: `rg --files --hidden`, `ls -la`, `free -h`, `df -h . /tmp`, `nproc`,
`command -v ...`, interpreter imports, `gdal_viewshed --help`, `grass --version`.
14 GiB RAM total / 11 GiB available, 16 logical CPUs, 30 GiB disk available.
System Python 3.10.12 / GDAL 3.4.1 / NumPy 1.26.4 / SciPy 1.14.1; default Conda
Python 3.13.9 is not the GIS runtime. GRASS failed creating ~/.grass7 (read-only),
then its exception handler failed. GDAL CLI and bindings work. Initial NumPy version
probe had a typo calling a string; corrected probe succeeded.
`python3 -m venv --system-site-packages .venv` failed because ensurepip is absent;
`/usr/bin/python3 -m venv --without-pip --system-site-packages .venv` succeeded.
No packages installed and system Python untouched. Existing native dependencies
are exposed read-only through the local venv; versions will be recorded per run.

Decision: standalone glassing/ package; no unavailable code claimed as audited.
Use GDAL initially: installed working API, simple bounded products, explicitly
verified projected-CRS and NoData requirements. GRASS comparison deferred.
Primary docs checked: https://gdal.org/en/stable/programs/gdal_viewshed.html and CPW
public layer metadata. Local CLI capabilities take precedence over newer online flags.

Next: acquire/freeze pilot inputs, implement and verify pipeline.

## Completed implementation and evidence checkpoint — 2026-09-25

Implemented glassing/acquire.py (bounded checksum/pinned revision acquisition),
core.py (preparation, terrain/background/manual candidates, GDAL visibility, area
scoring, profiles and exports), __main__.py (configuration-driven stages/resource
limits), two configurations and six regression tests. README.md and
NUMERICAL_EVIDENCE.md provide commands, output contracts, measured results and limits.
The supplied reports were preserved. No source repository was initialized, changed,
committed or pushed; .git remains an unusable empty read-only directory. .gitignore
excludes bulk data, runs and environments if this folder is later version-controlled.

Acquisition: public CPW FeatureServer/6 GMUID=54 query succeeded. Its dissolved
projected centroid selected a 64 km² square wholly in GMU 54. Exact polygon, boundary,
provider metadata/license, TNM query/response, source raster metadata and checksums
are archived under docs/glassing/provenance/. The initial adapter erroneously looped
over historical TNM revisions and downloaded four before the 2 GB guard stopped a
fifth. Actual downloaded bytes including metadata: 1,651,433,197 (under 2 GB). This
was corrected to select the pinned 20220331 revision BEFORE downloading; a regression
test now covers the selection. Older downloads are unused. Clean reproduction needs
only the 415,482,393-byte selected tile plus metadata. Source acquisition date is
unknown; publication is 2022-03-31. The tile-specific catalog confirms metres/NAVD88
and public domain; GeoTIFF confirms NAD83 geographic samples but no vertical tag.
A cached acquisition rerun succeeds with 0 new bytes. Initial network wall time was
not measured; no cold-download speed claim is made.

Failures resolved: venv ensurepip absent (use --without-pip); first GDAL binding call
rejected creation-options list (`char **`), fixed with None (uncompressed viewsheds).
The first offline test run exposed that binding failure; after correction geometry
checks passed. Added curvature and pinned-revision tests; final six tests pass in
0.055 seconds. GRASS home-config failure remains irrelevant to chosen GDAL backend.
Matplotlib emits a mixed-install Axes3D warning, but 2D PNG generation and inspection
succeed; system/user package installations were not altered.

Commands actually run:
- `.venv/bin/python -m unittest discover -s tests -v` (six final tests pass).
- `.venv/bin/python -m glassing acquire --config configs/gmu54.json` (success, pinned
  existing terrain, final cached check 0.516 s, 0 new bytes).
- `.venv/bin/python -m glassing all --config configs/synthetic.json` (all five stages
  succeed, 150 candidates / 450 viewsheds, QGIS/CSV/GPX/report outputs).
- `.venv/bin/python -m glassing all --config configs/gmu54.json` (same, real 64 km²).
- `/usr/bin/time -v` on both repeated `all` commands; real 3.42 s / 333380 KiB RSS,
  synthetic 3.04 s / 328536 KiB RSS, no swaps, exit 0.
- `gdalinfo -json` selected tile; native GDAL raster and OGR GeoPackage read-back;
  XML GPX read-back and inverse coordinate transform; SHA-256 before/after comparison.
- `lscpu`, `/etc/os-release`, `df -h .`, `du -sh data runs .venv`: Ryzen 7 5700G,
  Ubuntu 22.04.5, 28 GiB disk free afterward, data 1.6 GiB / runs 514 MiB physical
  including historical downloads and old development caches. Venv 52 KiB.

Final uncached real stage times: prepare 0.593 s, candidates 0.241 s, visibility/scoring
2.718 s, inspection 0.889 s, exports 0.081 s; 4.522 s sum (excludes interpreter startup
and original network acquisition), peak RSS 322.4 MiB. Active cache 84,623,855 bytes;
three radii, 150 candidates each. Synthetic stage sum 4.041 s. Both final second
runs reuse all 450 viewsheds and produce byte-identical DEM, candidates JSON, score
JSON, candidate CSV and GPX. GeoPackage is checked semantically, not binary-hashed
because metadata timestamps may change. Evidence and hashes: evidence_run.json.

Real selected rays: 116/120 random and 41/41 cardinal agreement with independent
quarter-cell bilinear profiles; synthetic 111/120 and 48/48. All observed disagreements
are GDAL-invisible/ray-visible; real minimum ray clearances 1.31–2.38 m. These remain
explicit numerical uncertainty, not asserted engine correctness everywhere. The real
review PNG was visually inspected: continuous terrain relief and full halo, no obvious
voids or tile seams; raster visibility edges follow terrain. Six tests cover flat/ridge,
heights, NoData/NaN, coordinate/units/halo failures, curvature, resolution-area stability,
excluded-target obstructions and the acquisition regression. No prior suite existed.

Outputs: runs/gmu54/ and runs/synthetic/ contain baseline.gpkg, GeoTIFF terrain/masks,
content-keyed visibility products, candidates.csv, review_only.gpx, review.png, REPORT.md,
metrics, sightline diagnostics and export_validation.json. All 150 candidates per run
are UNKNOWN_ACCESS_NOT_FIELD_READY. The field-ready shortlist is empty. Real top
terrain rank C0064 has 3.3936 km² visible targets at 2 km. Top-ten overlaps change to
2/10 at 1 km and 6/10 at 3 km; radius sensitivity is substantial, not an optical rule.

Next action: stop at this completed technical checkpoint. A future authorized
milestone should obtain blinded manual choices and analyst time, verify connected
legal access/closures, and audit discrepant rays and real setup visibility before
adding ecological weighting. No scouting superiority, deer probability, field sightings,
route legality, onX import success, or unit-scale performance has been established.

## Matched-comparison milestone started — 2026-09-25

New user scope explicitly authorizes habitat/glassability comparison. Re-read applicable
AGENTS and SPEC/PLAN/STATUS and inspected code/evidence. Git still unavailable; baseline
DEM, candidates, scores, CSV and GPX hashes match recorded evidence. Existing six tests
pass (0.055 s). Machine has 11 GiB available RAM, 28 GiB disk free. Baseline source
and outputs will remain untouched; new module/config/output root. Predeclared protocol
written to comparison/PROTOCOL.md before new rankings. No independent expert points,
connected permitted routes, closure verification or field observations exist locally.
Primary-source checks underway for CPW seasonal ranges and affordable USGS vegetation.

### Comparison execution through initial evidence — 2026-09-26

Acquired public CPW summer/winter polygons and 2023 USGS RCMAP tree/shrub/herb science
raster subsets through the live dmsdata.cr.usgs.gov WCS (3,188,583 bytes initially).
Older www.mrlc.gov/geoserver WCS links returned 404/timeouts; current linked USGS WMS
host exposes working WCS. No styled RGB images were used for scientific values.
CPW summer polygon had nested shells outside the AOI; first prepare failed explicitly.
OGR MakeValid repaired it, with zero changed analysis-grid cells; source retained.

Added fine DEM after initial ranks (exploratory amendment recorded): one 262,214,898-byte
USGS 2019 1m tile, only two 400m viewsheds; comparison cap increased from 200 to 300 MB.
Combined original and comparison downloads remain below 2GB. Catalog body confirms
bare-earth metres/NAVD88, NAD83 UTM; no vertical datum transformation performed.
Source dates differ, so 1m/10m is not a pure resolution or ground-truth comparison.

First successful run reproduced M1 within 4.45e-16 km²; seasonal range coverage:
summer 100%, winter 21.3514%; unknown vegetation 0.05625% of targets. M1/M2 top tens
identical, rank rho 0.99975. Main M3 top ten has zero overlap with either; inspection
and target searchability drive much of the change. Equal-effort raw surrogate has
121 ties, underscoring that arbitrary scan rate is not a discriminating validated model.
30m raw rank rho 0.93672/top-ten 7/10. Dense 4km², 400-point reference vs nine original
local candidates found +15.72% best glass surrogate opportunity; raw dense best was
4.91% lower (lattice is not a superset, no negative recall claim). Fine local mask
disagreement: C0064 27.24%, C0090 1.20%; independent 1m profiles agree 40/40 each.
No field/imagery adjudication occurred. Comparison and fine maps visually inspected.

Existing six tests plus seven comparison tests pass after changing an exact float
assertion to a tolerance and closing the expert CSV handle. Tests cover positive
background, task ordering, finite budget, face/glare geometry, separate canopy path/
foreground and ground endpoints, unknown cover, switch collapse, access evidence,
expert required provenance and score-blind deterministic stratified sampling.

Latest measured full command before final checks: 12.83 s, 351252 KiB peak RSS,
no swaps. Main scoring/stress 5.08 s, 30m 0.184 s, dense 3.41 s, local fine 0.206 s.
No blockers; remaining: final source-lock/run checks, evidence/report, persistent status.

### Matched-comparison milestone complete — 2026-09-26

Final commands actually run:
- `.venv/bin/python -m unittest discover -s tests -v`: 13 tests pass (0.064 s).
- `.venv/bin/python -m glassing.compare acquire --config configs/comparison.json`:
  cached locked sources succeed, 0 new bytes, 0.430 s.
- `/usr/bin/time -v .venv/bin/python -m glassing.compare all --config configs/comparison.json`:
  final full run 12.58 s / 348468 KiB peak RSS; second 12.55 s / 347284 KiB; no swaps.
  prepare ~1.25 s, scoring/resolution/reference stage ~8.83 s, review/maps ~2.08 s.
- Compared 12 deterministic numerical/CSV/review output hashes across both runs:
  all identical. Five recorded original control hashes still match. Native GeoPackage
  geometry/CRS/count read-back passes. Comparison and local-fine maps visually inspected.
  Evidence saved to comparison/REPRODUCIBILITY.json.

New code: glassing/comparison_data.py, comparison_models.py, compare.py,
comparison_review.py. Source/configuration lock and raster checksum contracts prevent
silent input mixing. Original baseline core/config/run untouched. No blocking baseline
control defect identified; local fine-terrain differences are evidence limits, not
silently corrected source data. A malformed new CPW geometry was repaired with zero
local mask changes. Comparison tests also check explicit denied access is excluded
and unknown access cannot become verified without evidence.

Deliverables: docs/glassing/comparison/{PROTOCOL,README,EXPERT_PROTOCOL,REPORT}.md,
REPRODUCIBILITY.json and small provenance metadata snapshots. runs/comparison contains
component scores, selection cross-scores, 28 scenario rankings, 100 stratified random
replicates, 32-ray/height canopy stress diagnostics, 30m comparison, 400-point dense
reference, two 1m local checks, feature rasters, comparison.gpkg, comparison/fine maps,
five explained alternatives, an empty field-ready shortlist and blank blinded review
packet (nine unique positions / eight patches each). The analyst key is kept in a
separately labeled file; users must not hand it or model score maps to reviewers.

Fine local checks: C0064 observer ground -1.21m relative to control, 27.24% mask
cell disagreement; C0090 -0.11m / 1.20%. Independent fine profiles agree 40/40 each,
but same-source numerical agreement is not field truth. Source vintages and horizontal
realizations remain confounded. Coarse canopy stress is extremely assumption-sensitive
(54.7/92.9/97.8% mean sampled blocking at assumed 5/15/25m), so foreground/path penalties
remain OFF in main M3. No fine-canopy geometry or optical transmission was established.

Inputs total 265,403,481 bytes; experiment generated files ~82,406,594 bytes, excluding
metadata later added to the journal. Combined original/new source transfers ~1.917GB.
Resource caps: 300MB new comparison source cache, 1.5GB experiment disk, 2GiB virtual
memory, 900s per command; serial native processing. No system package changes or paid
services. Git still unavailable; nothing committed, pushed, published or sent externally.

Conclusion and next action: stop. Habitat provides almost no rank differentiation in
this pilot; glassability changes rankings but is not independently validated. Additional
work is justified only as independent connected-access, expert/manual, setup/target
and inspection-time review. Expert comparison and legally feasible random benchmark
are pending verified inputs. No observed hunting or scouting improvement is claimed.
The report explains the equal-effort surrogate's 121 raw-score ties and strong compact-
view bias; it must not be presented as calibrated search coverage or total hunter-hour
performance. Held-out review remains untouched; no observations were invented or tuned.

## Corrective-validation milestone started — 2026-09-26

Read applicable instructions, comparison report and actual scoring/geometry code.
Git still unavailable; no user work reset or overwritten. About 10GiB RAM available,
28GiB disk free. Froze hashes of original runs, code/configuration and report/protocol
in correction/FROZEN_CONTROL.json. New work will use separate correction modules,
configuration and run directory. Uniform-attention formula confirmed in compare.score;
selective attention protocol registered before new scores. No hunt dates/start point
found in configuration; optional asynchronous question sent, independent work continues.

## Corrective-validation checkpoint complete — work 2026-09-26, closeout 2026-09-28

Implemented separate selective whole-patch attention, retained uniform/no-penalty controls,
51 matched configurations on 150 candidates, matched C0064 local geometry and 20m setup
samples, official mapped-access inventory/witnesses/gaps, dated NAIP imagery, QGIS packet,
five explained alternatives and six blank blinded reviews with 48 fixed target patches.
Report: correction/REPORT.md. SPEC, PLAN and README updated; original reports preserved.

Commands actually completed:
- `.venv/bin/python -m glassing.correct attention`: 4.89s, 256MiB peak RSS.
- `.venv/bin/python -m glassing.correct geometry`: 1.03s, 182MiB.
- `.venv/bin/python -m glassing.correct access`: 1.65s, 161MiB.
- `.venv/bin/python -m glassing.correct imagery`: dated setup/context imagery cached.
- `.venv/bin/python -m glassing.correct all`: repeated 13.75/14.20s, 327/331MiB.
- `.venv/bin/python -m glassing.correct acquire`: cached official inventory verified.
- `.venv/bin/python -m unittest discover -s tests -v`: all 17 tests passed.
- `.venv/bin/python -m glassing.correct packet`: final rendering/GIS read-back passed.
- `.venv/bin/python -m glassing.correct verify`: final control/source verification passed.
Eleven substantive outputs byte-identical across repeats (runs/correction/repeatability.json).
All 3,340 frozen controls unchanged. Final generated cache approximately 48.9MB after
map style adjustment; retained new downloads 34,665,732 bytes. Execution measurements
are in runs/correction/execution.jsonl; exact source requests/hashes/dates in
correction/PROVENANCE.json and data/correction/manifest.json.

Failures/limitations recorded: first attention command used incorrect old CSV filename,
fixed to component_scores.csv and rerun successfully; current USFS alerts request HTTP403;
recreation-site query returned zero points; existing mixed Matplotlib installation warns
Axes3D unavailable (only 2D used; no dependency changes). No hunt dates/start point supplied.
C0068 is in all 21 selective sensitivity top tens, but all six review positions retain
unknown legal/physical access. C0064 400m results do not correct its full 2km rank.
Independent imagery/field/expert adjudication remains pending, not fabricated.

Closeout audit on 2026-09-28 confirmed the final packet and verification had completed;
the previous turn had not appended this completion record or delivered its final handoff.
No credit/billing diagnosis is available. Recommendation: simplify model development,
complete independent access/setup/target reviews before routes. STOP at this checkpoint;
no route optimization or field collection initiated.

## Actual-hunt scouting milestone started — 2026-09-28

Read instructions, persistent documents, corrective report/code/configuration and overview.
Git remains unavailable. Available RAM ~6.4GiB, free disk ~26GiB. Frozen all previous
baseline/comparison/correction artifacts and code/configuration under scouting/FROZEN_CONTROL.json.
New configuration records GMU54 second-rifle 2026, supplied optics, editable 5–8mi /
2000–3500ft preferences; personal dates, camp and parking remain unspecified. New budget:
180MB downloads, 800MB outputs, 2GiB address space, 900s per command. Separate outputs only.

## Actual-hunt scouting implementation and evidence — 2026-09-28

Separate implementation: glassing/scout.py (control/support/fine/CLI), scout_data.py
(locked official acquisition), scout_access.py (mapped witnesses + bounded terrain
legs), scout_packet.py (labeled review exports), configs/scouting*.json and5 new
meaningful tests. Reuses core.viewshed/compare.components and correction attention;
prior engine/modules/configurations/results are unchanged. Git status still fails:
not a git repository; no commits/resets/stashes/publication performed.

Completed work:
- Official CPW2026 brochure confirms Oct24–Nov1 GMU54 buck second rifle (PDF39,
  printed29). Personal dates/camp/parking remain null. Full2km support restored only
  on FS/GMU minus mapped private conflicts, with explicit unresolved upper bound.
- Expanded official access to50km; USFS recreation inventory17 sites screened,
  Colorado BLM981 routes, CDOT106 local roads fill missing connections. Five entry
  options retained. Same-route endpoint/segment repairs<=5m, Sun Creek/Detour<=2m;
  no arbitrary crossing noding. Entry symbol offsets remain unresolved.
- Shared conditional CR726/FS7726–April Gulch approach to three primary setups;
  high-clearance MVUM July1–Dec31 dates cover legal season. Road condition/parking
  unverified. Documented parking-foot returns22–24mi exceed daily preference.
- Waterbody/private exclusion and30°/20m slope-screened legs; NHD streams/cover
  reported separately. C0049 crosses named Beaver Creek; C0090 fallback is wooded
  and crosses seven mapped stream features. Neither is certified passable.
- Dated2019 NAIP setup/context review and18 matched local fine-terrain cases for
  C0068/C0095/C0049. Existing C0064 investigation not rerun. Three primary exports,
  C0090 separate reserve, C0064 control only; randomC0025 preserved.
- Overview within actualGMU, five cards/six-pagePDF, field GPX/KML,17-layerGPKG,
  visible-targetGeoTIFFs and component tables. Labeled packet separate from blinded.

Commands actually run and observed results:
- `.venv/bin/python -m glassing.scout acquire`:50 locked source files verified,
  zero repeat-download bytes,0.78s/~123MiB peakRSS. Initial official source retrievals
  used Fetcher/query adapters; exact requests/checksums retained in source lock.
- `... scout support`: initial2.44s/~275MiB. Raw km² old→restored:
  C0068 3.2582→3.2929; C0095 1.9875→2.7613; C0049 .7996→2.4784;
  C0090 .5716→.7418; C0064 3.3936 unchanged; C0025 1.7801 unchanged.
- `... scout fine`:18 cases,initial1.17s/~180MiB; common360m target disk.
- `... scout access`: successful final witnesses approximately17s/~527MiB.
- `... scout all`: completed repeatedly; final measured35.13s and34.39s,
  ~596MiB observed peakRSS.23 substantive files byte-identical across those runs.
- `... scout packet`: regenerated and export read-back passed; overview and primary
  cards visually inspected. Final rendering uses tight bounding boxes to retain text.
- `.venv/bin/python -m unittest discover -s tests -v`: all22 tests pass,0.081s test
  runner; original17 retained plus5 new topology/barrier/date/support/export checks.

Source retention138,208,384 bytes (~138MB), below180MB limit; output cache ~54MB,
below800MB.2GiB address-space/900s runtime caps enforced. No dependency/system Python
changes. Exact final commands/measurements in runs/scouting/execution.jsonl.

Failures and corrections: initial access inventory falsely appeared disconnected;
adding county roads and supported endpoint-to-segment continuity resolved primary
witnesses. First diagnostic helper lacked PYTHONPATH, corrected. MVUM contains malformed
calendar dates: first parser failed, fixed to reject invalid intervals conservatively.
Initial yearlong-only motor filter missed July–December eligibility, corrected with
whole-hunt-window checks. NHD initiallyHTTP504 succeeded on retry. USFS alerts/Gold
Creek/West Elk pages initiallyHTTP403 succeeded on retry; Gold Creek order is road771,
March17–July3, not a Steers Gulch fall closure. County GIS downloads required login;
used official CDOT inventory. Duplicate current brochure transfer blocked before
exceeding budget; accepted official state-library2026 CPW copy retained. Existing
Matplotlib Axes3D warning only; 2D output works. Provider-returned map extent prevents
aspect-ratio registration error; color/label/layout defects corrected during inspection.

Handoff: docs/glassing/scouting/REPORT.md and METHODS.md; runs/scouting/analyst and
field_review. RecommendationA: review/exportC0095,C0068,C0049 provisionally. Road-end
parking/conditions, foreground openings and stream crossings are the material pending
human checks. C0090 reserve, C0064 control. No field observation/expert selection or
blinded validation fabricated. No itinerary or complementary optimizer implemented.

Final closeout: `... scout verify` passed in0.75s; all3,428 frozen files and50 locked
new source files verified. Final packet17.44s/~564MiB, final output54,024,171 bytes.
All23 substantive repeat hashes still match after the layout-only correction; report
local links resolve. Final C0095 card visually checked for unclipped coordinates/text.
Milestone COMPLETE at the provisional desktop handoff. Next action is the five human
checks in scouting/REPORT.md. Stop here; no later optimization or field collection.

## Hunter-selected transfer — portability pass, 2026-09-28

Read project/persistent instructions and prior evidence. Full spatial-file search
included ignored data/runs plus JSON/archive checks: no hunter-supplied AOI/manual
waypoints. Only agency source layers and generated experiments found. Parent instruction
files absent. Git remains unavailable. Measured ~3.4GiB availableRAM,26GiB free disk;
new config caps1536MiB address space,900s/stage,250MB downloads,800MB outputs.
No downloads/dependency changes this milestone.

Frozen6,227 previous artifacts (including prior tests/code/configs/reports/runs) in
transfer/FROZEN_CONTROL.json. Created transfer_model.lock.json from existing assumptions;
no prior implementations changed. New transfer.py is an adapter using core.generate,
core.viewshed/compare.components and attention.select. transfer_access.py reuses existing
network/terrain primitives with configured sources/entries. transfer_packet.py emits
matched review products; transfer_fixture.py makes explicitly artificial inputs.

Manual GPX/GeoJSON/CSV IDs/coordinates/records preserved (older expert importer snaps;
it remains frozen, and the new path does not use it). Automated generation excludes
manual seeds. Common target buffer avoids observer-boundary clipping; explicit target
restrictions do not erase obstruction terrain. Source/derived/model/config hashes and
path ownership guard against mixed runs or overwriting old outputs. Runtime versions
recorded. Local refinements are symmetric and diagnostic. No actual hunting AOI chosen.

Transfer closeout — unblocked portability COMPLETE; real comparison WAITING FOR INPUTS.
Commands actually completed:
- `.venv/bin/python -m glassing.transfer intake --config configs/transfer.template.json`:
  WAITING_FOR_HUNTER_INPUTS, exact polygon/GPX paths reported, ~1.1s/~126MiB.
- `.venv/bin/python -m glassing.transfer_fixture`: generated explicitly synthetic
  EPSG32612 fixtures (24 auto,2 artificial manual-style points), no real AOI chosen.
- `.venv/bin/python -m glassing.transfer all --config configs/transfer.fixture.json`:
  ~5.1–5.5s/~218–219MiB, ~1.6MB outputs,47 local refinement evaluations; seven review
  positions and21 overlap pairs.15 substantive outputs repeat byte-identically.
- `.venv/bin/python -m unittest discover -s tests -v`:29 tests passed,1.230s runner;
  original22 plus7 transfer checks, including manual-change independence and configured
  synthetic-entry approach witness. No old tests or data changed.
- `... transfer verify --config configs/transfer.fixture.json`: preservation/model,
  source/config/runtime and derived-product checks pass.6,227 prior artifacts unchanged.

Acquisition0bytes/$0; no paid or external service used. Real-area acquisition cost and
runtime are unmeasured, not inferred from fixture performance. Synthetic PDF first page
visually checked: explicit fixture label, terrain-only/pending-imagery label, pending
access rather than invented entry effort. Existing 2D Matplotlib works despite Axes3D
warning. Documentation links and final repeat hashes checked. Prior source reports,
pilot maps, five candidates and blinded packets remain untouched; no itinerary solver.

Next action: user supplies observer-search polygon and unchanged manual waypoints per
transfer/INPUTS.md. No trailhead/camp or user-prepared DEM required to submit them.
GeoJSON polygon + GPX waypoints preferred; CSV/GeoJSON points supported. KML/KMZ polygon
can be supplied for explicit conversion, not currently claimed as direct intake.
Stop here. Source acquisition, actual imagery/entry checks and a usefulness-vs-manual
recommendation require the real inputs. Soap Creek remains only a candidate area.

## Latest: owner usability milestone, 2026-09-28

Normal entry point is now `./scout`; README and START_HERE.md supersede the older
required-two-file normal-use instructions. Manual points remain optional; only the
owner-selected observer-search polygon is missing. No replacement AOI was selected.
Implementation, scope, commands, measurements and acquisition limits are in
usability/REPORT.md. Initial Git status clean; Git worked in this session.

Ran `./scout doctor`: Python3.10.12/GDAL3.4.1/NumPy1.26.4/SciPy1.14.1/
Shapely2.0.6/Matplotlib3.9.2 ready. `free -h`, `nproc`, `df -h .`: ~14GiB RAM,
~6.3GiB available, 16 CPUs, ~26GiB disk free. Default acquisition cap600MB, analysis
memory1536MiB/runtime900s/grid3million cells retained/configurable.

Ran `.venv/bin/python -m unittest discover -s tests -v`: 32 passed, 9.54s.
Owner-only tests also run after final integrity changes. Isolated actual launcher
journeys used `/tmp/scout-journey-*`, no historical runs/docs or real cached inputs.
Normal no-manual and matched optional-manual journeys succeed; points remain unchanged
and auto pools match. GPX/KML/GPKG read-back passes. Startup with missing dependencies
prints setup instructions; missing historical archives do not affect normal operation.
Verification is read-only; tampered current outputs fail. Import selection, cache
coverage/checksum and download-budget checks pass. Initial pytest invocation failed
because pytest is absent; used existing unittest without installation.

Representative fixture normal engine1.57s/208MiB peak, owner analysis+handoff2.42s,
1.76MB results; matched2.07s/218MiB, handoff2.95s/2.19MB. Download0bytes/$0.
These are synthetic500m checks, not measured real-AOI performance. Overview and PDF
card visually inspected with explicit synthetic/imagery-pending/access-pending labels.
After tests, all6,326 files in usability/PRESERVED.json unchanged; no historical hashes
rewritten, real archives moved, commits or pushes. Fresh environment solve/install and
new-area live acquisition remain untested; documented honestly.

Next action: owner supplies only `inputs/my-area.geojson` (or KML/KMZ). Run
`./scout run --area inputs/my-area.geojson --name my-area`; results under
`results/my-area/`. If data are missing, read DATA_REQUIRED.md/download_plan.json and
repeat with --download within the stated cap. Optional manual comparison uses --manual
and a separate completed-run name. No further research-model or route work authorized
by this handoff. Stop here pending the polygon.

## Latest: actual Soap Creek acquisition failure resolved

Owner supplied inputs/test.kml and authorized diagnosis/resume of soap-creek-v1.
Initial Git status was clean. Read the failed notices, configuration, request plan,
actual downloaded raster and acquisition adapter. Root cause: covers() conflated
internal vegetation NoData101 with missing geographic coverage; all four failing
coarse-probe samples were interior. Full 10m grid also exposed WCS crop/alignment
edge artifacts. Separate geographic coverage from data validity; keep DEM strict,
vegetation unknown explicit. Aligned/padded WCS replacements retain original tree.tif
and provenance; no polygon or scoring change. CPW explicit4326 legacy CRS and invalid
summer nested shells were further blockers; normalized copies and recorded make_valid
repair resolved them, with zero changed summer-mask cells locally. Original sources
retained. Full report: usability/ACQUISITION_FIX.md.

Resumed exact command through completion: ./scout run --area ./inputs/test.kml
--name soap-creek-v1 --download. Engine5.30s/243.65MiB peak; owner6.35s;150 candidates,
5 leading alternatives,16 KML polygons. Total downloads2,368,910bytes including failed
original, below600MB. .venv/bin/python -m unittest discover -s tests -v:34pass/9.85s.
./scout verify --name soap-creek-v1:passed. git diff --check clean;6,326 prior evidence
hashes unchanged. Overview visually inspected. Current results:results/soap-creek-v1/
REPORT.md,overview.png,review_packet.pdf,review.gpx,sectors.kml,comparison.gpkg.
No remaining engineering blocker for this run; imagery/access/field claims remain
pending as labeled. Next action is owner desktop review, not further model changes.

## Latest: Soap Creek derived visibility/imagery review, 2026-09-29

User authorized visualization only. Preserved existing acquisition-fix changes and
all original soap-creek-v1 files. Added glassing/review_maps.py and targeted alignment
regression; no scoring, masks, rankings or original packet changed. New outputs are in
results/soap-creek-v1-review-v2/ (separate derived manifest/provenance).

Ran .venv/bin/python -m glassing.review_maps --download, then --download --redraw using
checked image cache for final percentage/native-resolution labels. Downloaded31,533,624
bytes under120MB cap: ten coverage-validated NAIP clips, 0.6m source dated2019-09-13/14.
Context exports4.4m; setup exports0.5m are resampling, not extra detail. Packet12pages:
overview, five context maps, five setup close-ups, existing pairwise overlap table.
Cyan actual target-clipped visibility versus orange attention footprints; grid north,
lat/lon, labeled distance rings, bearings, rounded cover percentages and caveats.

Verified source/analysis CRS, pixel scale and integral origins; all five mapped areas
match original raw_km2 exactly (tolerance1e-9km²), pairwise shared areas also match.
Ran unittest test_review_maps.py:1pass (target/radius clipping and registration failure).
Rendered all12 PDF pages with pdftoppm and visually inspected them; no missing imagery.
./scout verify --name soap-creek-v1 passed. Opened finished PDF via xdg-open (exit0).
Original packet/integrity files remain unchanged. Pending human review: tree/opening
interpretation, local setup adjustments; field checks: ground sightlines/footing,
connected legal approach, vegetation changes since2019 and actual detection.
Stop at this visualization handoff; no modeling or itinerary work.

## Bounded Soap Creek vegetation experiment completed — 2026-09-30

Recovered the interrupted-session v1 and preserved it. Final separate handoff is
results/soap-creek-vegetation-v2/REPORT.md and vegetation_review.pdf, plus local lidar
review, components/sensitivity/overlap and original/alternative GPX/KML exports.
150 original positions and52 nearby alternatives; no frozen/normal scoring changes.
A0031 coarse4.9% sampling reproduced, ground-level setup still unresolved. One cached
2019 lidar tile gives bounded column sensitivity, not measured deer visibility.
39 tests pass; repeated numerical/GIS exports identical;6,326 earlier historical
files plus419 immediate source/review/v1 files unchanged. Original scout verify passes.
Runtime30.89s/723.33MiB/output42.18MB; zero new bulk downloads. Detailed audit,
reproduction, evidence and limitations: vegetation/{README,REPORT}.md. Stop here.
