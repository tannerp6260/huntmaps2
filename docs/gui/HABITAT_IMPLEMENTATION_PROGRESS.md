# Habitat implementation progress

Status: COMPLETE — integrated implementation, focused/integration checks, full normal
release gate, real-area measurements, scientific challenge and protected-file audit
passed. Latest phase entries supersede earlier in-flight command/status entries.

Baseline: clean `main` at `c35f3633c620a72efd13162338f06af99fe55648`;
no tracked or untracked changes before this task. Local checkout is authoritative.
Recovery archive, initial binary patch, untracked inventory and full SHA-256 protected
manifest: `/tmp/huntmaps-habitat-20261018-pqhsgnuw`. Protected scope includes frozen
`glassing`, `configs`, `docs/glassing`, source `data`, `runs`, `results`, `inputs`,
all owner `.gui` files (including scenes/mask revisions) and supplied reports.
Permitted changes: active GUI/service code, focused tests/release tools and docs/gui;
new runtime user habitat profiles/selections and derived caches in separate namespaces.
Implementation/tests never write those namespaces in owner state. All verification
uses disposable Ubuntu state/workspaces and independent servers. No dependencies,
commits, pushes, historical regeneration, partition inspection or deletion.

## Minimal design declared before implementation

One deterministic NumPy habitat module; small source/profile, saved-run and GUI
adapters. Independent immutable habitat profile references the strict existing target
profile. Off preserves established behavior. Source-grid context precedes filters,
viewsheds and observer boundaries. Verified raw RCMAP tree/shrub percentages are
preferred; retain observation year and disclose unknown processing release. At least
30 m information support; no DEM-scale habitat edges. Map coarse continuous H/G
and contributions by nearest transfer to finer saved grids, area aggregation for
coarser grids. Missing samples/boundaries remain unknown.

Initial fixed heuristic: local radius 90 m, landscape radius 270 m, minimum full-disk
known support 0.8, at least three adjacent cells for cover/opening patch context.
Browse response `S/(S+0.15)`; woody cover signal `max(T,S)` (not composition).
Opening signal `T<=0.20`, browse/opening patches also require `S>=0.05`.
Mixed context `min(opening_fraction/0.30,1)*min(cover_fraction/0.30,1)` at 90 m;
cover context supported fraction with `max(T,S)>=0.35` at 270 m, saturating at 0.30.
H = 0.10 + 0.45 browse + 0.25 mixed + 0.20 cover.
G = `(1-0.90*T)*(1-0.65*S)`, bounded 0–1; optical heuristic only.
Priority H>=0.45 and G>=0.45. These thresholds affect summaries, never E/order.
Weights/settings are engineering hypotheses, not fitted deer coefficients.
Refinement permitted if source audit requires it; record before real ranking inspection.

E = sum physical_m2 * visible * hard_match * known * H * G, per cell before
reduction. No averaging/normalization by known area. Insufficient data differs from
known zero. Rank E descending, current matching area descending, current visible
area descending, stable ID; eligibility separately controls recommendations.
Metric identities include source/context/settings, strict hard filters and exact
current mask/revision. Weighted greedy uses packed cropped masks and float64
reduction of newly covered bits, exact saved cells, canonical retained order;
unweighted path remains. No candidate-by-grid cube or vegetation ray engine.
Use bounded single-flight background computation; stale snapshots cannot publish/add.
New-run opt-in uses same objective for refinement/recommendations and explicit
implementation/product provenance. Saved-run preference switches never generate.

## Acceptance cases declared before full implementation

- Independent scalar H*G/area/visibility/filter/unknown oracle; 100 m² cells with
  A four q=.25, B three overlapping, C two disjoint q=1: C then A, increments
  200/100, union 300; duplicate C zero. Priority union independently defined.
- Packed partial bytes/tails/empty windows; grid/CRS/units/origin/bounds rejection;
  source NoData, NaN, sentinel/out-of-range, edges/holes and full-radius support.
- Coarse/fine area invariance, shifted transfer tolerance, isolated patch suppression;
  mosaic vs dense forest, forest retains H with low G, barren/dense shrub challenges.
- Known zero vs insufficient/partial; reconciled known+habitat unknown matching area;
  thresholds leave E/order unchanged; deterministic ties/permutations and unions.
- Saved cold/warm ranking/tiles cannot acquire or calculate visibility; moved/manual/
  retained/pending masks, current revisions, original rank preserved; byte corruption
  with preserved size/mtime, source/provenance replacement and obsolete publication.
- Both ranking consumers screen the full scored pool before spacing/count; disconnected
  leaders do not remove later connected alternatives. Off comparator unchanged.
- Strict Preparation/recovery round trip; profiles backup/restore/lifecycle; independent
  habitat/connection signatures; notes/drafts/shortlist/review queues unchanged.
- Exact weighted collection/member/priority units, retained exceptions, stale additions;
  UI switch/reload/error/retry/stale tiles and desktop/900px/200% pixel evidence.
- Baseline/focused regressions, full normal ./gui/check with new discovered tests and
  registered browser journey; protected before/after byte and inventory comparison.

Sensitivity predeclared: radii (60,180), (90,270), (120,360); each nonbaseline feature
weight ±20% with all four weights normalized to sum one; G penalties (0.75,0.50),
(0.90,0.65), (0.98,0.80); one-at-a-time feature ablations, fixed baseline term.
Compare collections under common default weights; do not tune for a favored point.

## Commands/evidence

- `git status --short --branch; git rev-parse HEAD`: clean, reviewed HEAD.
- Read AGENTS, glassing SPEC/PLAN/STATUS/README, START_HERE, current audit report/
  progress, workflow/testing, connectivity and first-person recovery reports.
- `.venv/bin/python /tmp/huntmaps-habitat-preserve.py`: recovery archive/protected manifest.
- `./gui/check --skip-browser > /tmp/huntmaps-habitat-baseline.log 2>&1`: running,
  session 60897; result pending. Full normal gate remains required after stabilization.
- Official wildlife/product and primary research pages inspected; evidence table and
  current-plan access limitations will be recorded in HABITAT_METHODS.md.

Exact next action: finish verified source audit and independent failing numerical
regressions, then implement the source-to-current-mask vertical slice.

## Phase 2 — first vertical slice and integration

Implemented pure model, verified percent-source adapter, separate immutable profiles/
selections, sealed context/raster/overlay caches, current DisplayRun scoring, explicit
weighted rank, search/refinement objective, packed weighted union, bounded background
API, UI selector/cards/explanation/overlay, and lifecycle namespace registration.
Read-only actual source audit: `source-audit.json` in the baseline evidence root.
Available real pools: `scouting-2026-10-16222` 549, grid 974×968; current
`scouting-2026-10-18` 500, grid 816×838. A saved 600 pool was not found.

Pre-outcome grid refinement: delivered rectangular 29.9729×30.0397 m RCMAP cells
are conservatively averaged onto globally aligned 40 m square cells (10 m multiples,
at least nominal 30 m and delivered scale). Invalid samples and incomplete coarse
footprints remain missing; supported context transfers nearest to the exact 10 m
visibility grid. Coarser destination grids aggregate precomputed H*G/contributions
and priority fractions, never products of aggregated means. No new halo acquisition.

Commands/results:
- Initial declared numerical tests failed because the module did not yet exist;
  `/tmp/huntmaps-habitat-initial-failure.log` is an availability failure, not a
  reproduction of a legacy numerical defect. Six independent numerical tests passed.
- `./gui/check --skip-browser`: all 12 backend groups passed; formatting then failed
  on the newly edited habitat/complementary files. This run overlaps implementation
  and is not claimed as a frozen pre-change gate. Diagnostics `/tmp/huntmaps-check-6xo1z4e6`.
- `npm run build`: TypeScript/Vite passed; existing bundle-size warning remains.
- Search regressions initially exposed an unwanted `habitat: null` addition to Off's
  config. Fixed by emitting settings only when enabled; four search tests now pass.
- Saved API integration exposed a NumPy integer in source-support metadata. Fixed by
  explicit physical-unit float serialization. Nine habitat tests now pass, including
  real API scoring, no HTTP/viewshed generation, exact independently recomputed union,
  overlay hidden pixels, source corruption and profile snapshot restore/isolation.
- Legacy collection guard exposed an invalid synthetic moved-mask fixture: its lone
  target cell could lie outside the moved observer's radius. Fixture now uses a
  valid existing visible cell; assertions remain. Rerun pending.
- First disposable actual 549-pool cold score: 6.00 s (single sample before memoization),
  no downloads. This establishes a local baseline, not a general performance claim.

Exact next action: complete new-run/current-revision/geometry regressions, add and
register the real-service browser journey, benchmark independent weighted totals and
predeclared sensitivity, then run the complete normal release gate and preservation.

## Phase 3 — validation refinements and release preparation

Focused habitat suite now **18 tests passed** (9.46 s at its last pre-freeze run),
including actual opt-in owner/search workers, current unknown masks/retained counts,
geometry/reference reductions, derived corruption, concurrent preference rejection,
and healthy 24-request tile bursts. Legacy search (4) and collection (9) suites
passed independently. Extended browser journey passed at
`/tmp/huntmaps-check-ey1s1u9d`, including actual connected-only full-pool ordering,
weighted service, raster pixels, error/retry, unsaved notes with unchanged DOM node,
reload recovery and late profile replies. Further inherited-screen regression rerun
is pending in `/tmp/huntmaps-habitat-focused-final.log`.

Inspection confirmed the inherited-rank concern: connection snapshots copy original
`matching_km2`/`standing_eligible` and only replace keys present in working metrics;
working masks normally supply raw area rather than all old filter/rank fields.
Habitat mode now explicitly uses current habitat adapter matching/eligibility plus
canonical order; Off retains its comparator. Browser acceptance deliberately supplies
stale original ranking fields alongside actual connection evidence to exercise this.

Two diagnostic full-gate attempts overlapped authorized refinements and stopped at
formatting after their backend groups passed. They are NOT final release passes:
`/tmp/huntmaps-check-6xo1z4e6` and `/tmp/huntmaps-check-q4ae3bgd`.
The latter discovered 184 GUI tests at its start; later added zero-roundoff/lock tests
require a fresh gate. Exact output: `/tmp/huntmaps-habitat-full-check.log`.

Refinements from independent review: exact integer patch counts after FFT prevent tiny
false positive rewards; precomputed observation penalties aggregate correctly on
coarser destinations; temporal queries must agree with recorded year; Off previews
also seal habitat selection revisions; missing-mask directory snapshots detect restored
coverage; collection summaries expose unknown habitat area separately. Cache mutation
locks follow maintenance→feature order, and grid transfer is single-flight with one
bounded memory entry. Tile bursts use two dedicated workers rather than exhausting
the three-entry preference/collection admission queue. Existing resource caps stay.

Performance/sensitivity prototype produced `/tmp/huntmaps-habitat-performance.json`.
A first sensitivity follow-up used exact scenario greedy rather than individual top
views. Review found the 549 run's saved hard filters must also be applied consistently
to both ranking arms. Final measurements will use those same strict filters for both
arms and record them explicitly; preliminary outcome numbers are not the final matched
comparison. No preset coefficients were tuned. A fresh final benchmark is required.

Exact next action: finish focused browser rerun, freeze implementation inputs, run
normal `./gui/check` without skipped journeys, rerun matched benchmarks/sensitivity,
inspect screenshots and perform complete protected byte/path comparison.

## Phase 4 — broad release findings and final frozen rerun

The first broad normal run reached `browser-scouting-check` after passing its
backend groups, static/build, real 600-location recovery and preceding browser
journeys. It failed preflight with `network_ids: []` after a successful import.
Evidence: `/tmp/huntmaps-check-2ghykqap`, preservation `files:9067, changed:[]`.
It is a failed diagnostic run, not a release pass; later journeys were not reached.

A fresh unchanged scouting journey passed (`/tmp/huntmaps-check-dua4wcru`). An
independent new scouting fixture then held an actual boundary/source proposal until
after a real network import. It reproduced the exact product defect: the late
proposal unchecked the imported source. Failing command/log:
`./gui/check --browser-only --browser-check browser-scouting-check`,
`/tmp/huntmaps-scouting-race-reproduction.log`. This is a real input-overwrite race,
not justification for weakening preflight or raising slope limits.

Narrow correction in `scouting-tools.tsx`: explicit source/boundary choice epochs
prevent late automatic proposals/resolution from replacing newer imports, edits or
restored drafts. Geometry, constraints, solver, preferences and review queues remain.
The regression is part of the existing mandatory scouting journey and uses its own
run (`gui/scouting_fixture.py`) rather than decisions left by previous journeys.
The corrected race/preflight/path assertions passed; its later download-review test
initially used an AOI already covered by the habitat fixture's verified inventories,
so the app correctly hid downloading. That synthetic source-review AOI now lies
outside prior fixture coverage; the same cap/approval/provider-error assertions remain.

Additional closure checks: nineteen focused habitat tests passed; exact scalar default
H/G was independently checked; zero display-cache budget evicts derived arrays while
retaining profiles; explicit NaN NoData has canonical provenance and remains unknown.
Strict per-run selection and profile-version checks are in place. Preference-only
scoring applies the existing cache budget even without tile requests. Custom normalized
weights compare correctly during new-run recovery. Current hard-filter unknowns have
their own clearly denominated diagnostic. Habitat preferences wait for the current run's
selection to load. Actual 549-area desktop/900px habitat screenshots passed in the
focused journey at `/tmp/huntmaps-check-dua4wcru`.

Final focused pair is running in `/tmp/huntmaps-habitat-scouting-final.log`.
Implementation/test/helper input inventory is frozen in `release-inputs-before.json`
in the baseline evidence root. Exact next action: collect the focused pair, run a fresh
normal `./gui/check` with every journey, finish the matched timing/sensitivity evidence,
compare protected hashes and final source inventory, then close the report. No commits,
resets, data/owner-state deletion, dependency changes or owner-server operations.

## Final verification in flight

Focused corrected pair PASSED at `/tmp/huntmaps-check-kvef6rws`: real habitat/connection/
collection/overlay, actual 549-area desktop/900px, preserved notes and late-profile
responses, plus the independent scouting fixture with a held actual proposal and
explicit import preservation. The separate new-area source-review fixture retains
its 600 MB and explicit-failure checks outside already cached inventory coverage.

Final production/test/helper inputs are frozen (214 SHA-256 entries).
`./gui/check > /tmp/huntmaps-habitat-final-gate.log 2>&1` is the fresh required normal
gate, with all browser journeys and the actual recovery worker enabled. No stage is
intentionally skipped. Its counts and outcome remain pending. Final focused numerical
verification is `/tmp/huntmaps-habitat-focused-19.log`, including shifted-grid scalar
alignment/area bounds and independent default H/G expectations.

Exact next action: collect normal gate; if it passes, run the final matched benchmark
with setting-change timing fields, inspect final screenshots, compare all protected
bytes/paths and frozen release inputs, and replace report/progress pending sections
with observed results. Fix a demonstrated failure if one occurs; do not weaken gates.

## Resumed release verification — layout and Off regression

The interrupted normal gate completed all 288 backend tests, formatting/build,
actual recovery worker, habitat and scene-recovery journeys, then failed the existing
900px audit assertion: habitat controls pushed the candidate list below the visible
sidebar. Evidence `/tmp/huntmaps-habitat-final-gate.log`, diagnostics
`/tmp/huntmaps-check-jpaqwupn/screenshots/browser-audit-regressions/failure.png`.
No check was weakened. Find preferences now have a bounded scrollable region, keeping
the selector and all controls available while preserving visible candidate results.
The habitat journey also asserts results are visible at 900px after scoring completes.

Inspection also demonstrated a narrow Off mismatch for a new habitat-generated run
with Show all setups and Show original terrain. Without a review-filter adapter the
fallback recommendations inherited habitat order. New habitat runs now publish
`established_ids` and `established_nearby_ids` from the same evaluated pool using the
existing comparator; Off selects these independently of the habitat results. The
actual new-run test independently sorts matching/raw area and checks the published
control; the browser journey explicitly removes the review filter and checks control
IDs differ from habitat IDs and are actually rendered in Off. No search is rerun.

`.venv/bin/python -m ruff format ...` failed because ruff is not installed. No package
was installed; the existing `.venv/bin/python -m black` formatter was used successfully.
`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python
-m unittest discover -s tests -p test_gui_habitat.py -v` passed 19 tests in 9.777s;
log `/tmp/huntmaps-habitat-off-regression.log`. Focused actual-service browser pair is
running via `./gui/check --browser-only --browser-check browser-habitat-check
--browser-check browser-audit-regressions`, log `/tmp/huntmaps-habitat-layout-check.log`.
Exact next action: collect this pair, freeze final inputs again, run the complete
normal gate; then standalone matched performance and full protected-byte audit.

The first Off check exposed an inadequate synthetic fixture: its narrow stripes
averaged to identical habitat/terrain leaders, so the deliberately discriminating
assertion failed (`/tmp/huntmaps-habitat-layout-check.log`, diagnostics
`/tmp/huntmaps-check-n1w9sxpp`). The fixture now includes a broad dense stand beside
the mosaic. No preset settings or real-area sources were changed. Both actual-service
journeys then PASSED (`/tmp/huntmaps-habitat-layout-check-v2.log`,
`/tmp/huntmaps-check-lsp_1zsp`). Existing 900px result visibility assertion is unchanged.
Visual review found screenshots could catch a previous layer's ready status before
new overlay rendering. The map now exposes its actual coverage identity/phase on its
container, and the habitat journey waits for the habitat source set's rendered-ready
state, including after resize. These are bounded readiness checks, not timing sleeps.

Final analytical/GUI/test/helper inventory is re-frozen (214 SHA-256 entries).
Fresh full normal command: `./gui/check > /tmp/huntmaps-habitat-release-complete.log
2>&1`; every browser journey and actual recovery worker enabled. Exact next action:
collect that frozen run, then perform standalone final benchmark/sensitivity and
full protected-file comparison, review final rendered screenshots and close docs.

Benchmark-only isolation correction: `gui/habitat_performance.py` now explicitly sets
each real area's disposable workspace as well as disposable state. Earlier diagnostic
measurements used temporary state but the default read-only source workspace; they
are superseded by the final isolated measurements. No generation/acquisition entry
point is allowed in either path. The helper change is outside release-run execution;
its existing Black check passes and it will be executed separately after the gate.
The 214-file final input inventory was refreshed for this helper-only correction;
analytical and UI sources have not changed during this gate.

Final UI contract review found the legacy order selector still said Visible area
under habitat scoring, and list ordinals could look like a confident habitat rank
on an insufficient-data row. The selector now says Quality-adjusted area when active;
an unscorable/unavailable-mask row shows a dash with an explicit unavailable-rank
tooltip. The habitat browser journey asserts the active selector label and uses a
clearly identified UI-response fixture for an insufficient-data card; the numerical
unknown behavior remains independently tested against actual rasters in Python.
No ecological equation, backend ordering or recommendation rule changed.

The active gate's bundle predates these two UI changes. It remains regression
evidence only and will be followed by another full normal gate against the final
bundle. Its strengthened rendered-ready checks already produced actual green
priority pixels on the saved 549 area, including a visually reviewed 900px view.
Exact next action: collect the active gate, run the final isolated benchmark while
the runner is stopped, then freeze final inputs and run the complete final gate.

Independent pending-work responsiveness evidence:
`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.
.venv/bin/python /tmp/habitat-responsive-check.py` passed. Actual FastAPI app with
TestClient in-process transport, new `/tmp/huntmaps-habitat-responsiveness-e7gt9229`
state/workspace, actual 549-location cold scoring (9.350s while the release browser
was active), downloads/viewshed calculation forbidden. All 12 `/api/jobs` requests
completed while scoring was pending; maximum 0.009156s. Evidence:
`/tmp/huntmaps-habitat-responsiveness.json` and `.log`. This measures application
dispatch responsiveness, not real network/provider latency or a real 5,000-point run.

The full normal regression run `/tmp/huntmaps-habitat-release-complete.log` PASSED:
288 backend tests (187 in the GUI discovery group), all 31 browser journeys and
the actual 600-location recovery-worker journey. Diagnostics
`/tmp/huntmaps-check-ioh52yly`; `browser-results.json` is all passed and its protected
audit has 9,067 inventoried source/result paths with zero changes (owner/companion
record digests are additionally checked). This bundle predates only the final selector
wording and unknown-rank badge changes described above; it is not the final-code gate.

Standalone final command is now running, with release servers stopped:
`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python
-m gui.habitat_performance --out /tmp/huntmaps-habitat-final-performance.json`, log
`/tmp/huntmaps-habitat-final-performance.log`. It uses explicit disposable state and
workspaces for each real area. Exact next action: collect/independently reconcile its
results, freeze final inputs, run the full normal gate for the final UI bundle, then
complete protected SHA-256 comparison and final documentation.

## Final isolated measurements complete; final-code gate running

Standalone benchmark PASSED. `/tmp/huntmaps-habitat-final-performance.json` contains
both actual pools, all 13 predeclared alternatives, exact independently verified
collections and spatial synthetic 549/1500/5000 pools. Artifacts
`/tmp/huntmaps-habitat-benchmark-p2q0v473`. Warm saved scoring: 0.295–0.298 s (549),
0.260–0.264 s (500); cold 7.837/4.836 s. Exact 5,000-mask weighted greedy:
0.975/0.976/0.977 s; 10,263,066 packed bytes, density 1.223%; process peak 647.54 MiB.
All declared budgets passed. Context, settings-change, overlay and collection timings
are separated in the report; no scoring resolution was reduced.

Final matched IDs/top-20 and collection totals are byte-for-byte equal as JSON values
to the earlier corrected matched comparison; an independent comparison/assertion
command checked them and all timing budgets. No real-area preset tuning occurred.
Final sensitivity ranges and measured greedy loss are retained in methods/report.

Pre-final full SHA-256 audit PASSED: 31,623 protected files, 4.882815708 GiB, zero
changed/added/missing files; all 214 frozen analytical/GUI/test/helper inputs unchanged.
Evidence `pre-final-preservation.json` in the baseline evidence root and
`/tmp/huntmaps-habitat-pre-final-preservation.log`.

Final inputs re-frozen; `./gui/check > /tmp/huntmaps-habitat-verified-final.log 2>&1`
is now running against the final selector wording, unavailable-rank badge, explicit
UI unknown fixture and rendered-ready layer checks. All journeys and the actual
recovery worker are enabled. Exact next action: collect this final-code gate; fix
only a demonstrated failure, otherwise inspect its final screenshots, run final
protected/source snapshot comparison, save final review patch/inventory and close docs.

Final-code gate stopped at `browser-find-flow-check` after all 288 backend tests,
static/build, actual recovery and first six browser journeys passed. Habitat's new
label/unknown-rank assertions and rendered overlay checks PASSED. Existing Find
duplicate-click case timed out waiting for one automatic start (line 126); the same
journey passed in the previous complete gate. Evidence
`/tmp/huntmaps-habitat-verified-final.log`, `/tmp/huntmaps-check-20fw6f86`;
protected audit still has zero changes. No timeout/assertion was weakened.

Added failure-only screenshot/body/state/condition diagnostics to the existing Find
journey and launched `./gui/check --browser-only --browser-check browser-find-flow-check`
into `/tmp/huntmaps-habitat-find-diagnostic.log`. Exact next action: inspect/reproduce
the failed transition, correct any demonstrated generation-input cancellation race,
then rerun affected checks and a full normal gate. No analytical model changes.

The isolated existing journey passed (`/tmp/huntmaps-habitat-find-diagnostic.log`,
`/tmp/huntmaps-check-v0tsmbbw`). Deterministic response-order reproduction then FAILED
as expected: an old unprepared plan paired with a completed preparation job produced
"Source preparation is incomplete", despite the fresh fixture plan being prepared.
Evidence `/tmp/huntmaps-habitat-find-torn-before.log`,
`/tmp/huntmaps-check-cioxg72x/screenshots/browser-find-flow-check/transition-failure.json`
and `.png`. The original timeout lacked this state dump, so its precise internal
cause is not asserted; this reproduces the same missing-start symptom through the
existing non-atomic poll contract.

Narrow `generation-flow.ts` fix: when a completed job accompanies an unprepared plan,
read that plan once more, recheck cancellation, then apply the unchanged blockers,
review-signature and start logic. A genuinely unprepared fresh plan still fails.
Find journey now explicitly checks both torn-read recovery and genuine incomplete
refusal, while keeping duplicate/cancel/input-change/reload/provider/cap checks intact.
No wait timeout or assertion was relaxed. Focused Find + habitat pair is running in
`/tmp/huntmaps-habitat-find-torn-after.log`. Exact next action: collect this pair,
freeze inputs and run another full normal gate; then final protected-file audit and
documentation closure. Scientific/performance outputs are unaffected by this UI poll fix.

Focused corrected Find + habitat pair PASSED at `/tmp/huntmaps-check-8b259gqp`;
log `/tmp/huntmaps-habitat-find-torn-after.log`. Final 214 code/test/helper inputs are
re-frozen. Full normal release gate is running as `./gui/check --keep-going >
/tmp/huntmaps-habitat-final-release.log 2>&1`. The flag keeps all journeys observable
if one fails; any failure still makes the gate fail. All backend/static/build/recovery
stages and all 31 registered browser journeys remain enabled. Exact next action:
collect this gate, inspect final evidence, compare protected bytes and frozen source
inputs, save the final review patch/untracked inventory and close report/progress.

## COMPLETE — final verified handoff

All routine phases are complete: baseline/preservation; evidence/data audit; declared
design/acceptance; saved-run vertical slice; opted-in normal search/refinement;
weighted complementary/UI/overlay/persistence/exports; numerical/integration/browser
regressions; matched real-area/sensitivity/performance evaluation; release and
protected-state closure.

Final full command `./gui/check --keep-going > /tmp/huntmaps-habitat-final-release.log
2>&1` PASSED, October 18, 2026, 18:02–18:28 MDT. Diagnostics:
`/tmp/huntmaps-check-bldwxo4g`. All 288 backend tests, including 187 GUI-discovered
tests and 19 habitat tests; all 31 registered browser journeys; static formatting,
TypeScript/build; actual 600-location interrupted recovery and follow-on workflow
passed. No required stage/journey was skipped. Per-group/browser/protection counts:
`/tmp/huntmaps-habitat-final-counts.json`, diagnostics `browser-results.json` and
`protected-audit.json`. The extra keep-going flag never converts a failure to a pass.
Final Find checks cover both stale-plan/new-job recovery and genuine-incomplete refusal
with unchanged duplicate/cancel/input/reload/provider/cap assertions and time limits.

Final habitat journey reports 20,038 green rendered pixels, no page errors, actual
549-area service/overlay use, full-pool connection ranking, exact weighted totals,
Off restoration, unknown-rank refusal, draft DOM preservation, reload/error/retry and
late-reply rejection. Its desktop/900/effective-200% screenshots and actual 549 desktop/
900 images were visually reviewed. Paths are linked from the implementation report.
The synthetic/provider boundaries and field-validation limits remain explicit.

Final independent measurement assertions:
`.venv/bin/python /tmp/habitat-verify-performance.py` PASSED; log
`/tmp/huntmaps-habitat-performance-verification.log`. Both matched area outcomes are
unchanged; all budgets, 13 alternatives per area, known+unknown/area/component
reconciliation and independently recomputed synthetic unions pass.

Closing `.venv/bin/python /tmp/habitat-verify-preservation.py final-preservation`
PASSED: 31,623 files / 4.882815708 GiB, zero changed/added/missing protected paths;
214 final analytical/GUI/test/helper files, zero changes during the gate. Log
`/tmp/huntmaps-habitat-final-preservation.log`; baseline evidence directory
`final-preservation.json`. Release audit independently reports no source/result or
owner/companion record changes. Frozen code, controls, source data, reports, saved
results, coordinates, owner records, prepared scenes and existing masks are preserved.

`git diff --check` PASSED. HEAD remains the original reviewed
`c35f3633c620a72efd13162338f06af99fe55648`; 29 tracked changes and 11 new files, all
within the authorized GUI/test/documentation paths. No commits, pushes, dependency
changes, owner-server operations, data deletion, historical regeneration or partition
inspection. Disposable release servers were stopped by the runner.

Final recoverable review artifacts are refreshed with
`.venv/bin/python /tmp/habitat-final-review-artifacts.py` in
`/tmp/huntmaps-habitat-20261018-pqhsgnuw`: `final-review.patch`,
`final-new-files.tar.gz`, `final-changes.json` with exact paths/bytes/hashes, and
`final-git-status.txt`. The original pre-edit archive/inventory/manifest remain intact.
Methods, report, workflow and testing guidance are complete.

Exact next action: no implementation/verification work remains. Restart the GUI to
load the changes, select Fall mixed habitat — experimental, initially avoid additional
tree/shrub hard exclusions unless intentional, keep conservative observer/approach
constraints and inspect leading views before relying on the glassability proxy.
