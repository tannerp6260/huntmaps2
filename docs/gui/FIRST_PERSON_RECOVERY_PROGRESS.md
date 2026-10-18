# First-person recovery and window cleanup

## Current checkpoint — complete

Dense-ground fix, verified-cache recovery, compact window and guarded basic fallback
are implemented and verified. Actual A0136 preparation/render PASSED (66.28 s,
699.5 MiB peak RSS, zero downloads). Desktop, 900 px and 450 px screenshots inspected.

Final full `./gui/check --keep-going`: **exit 0**, all **269 backend tests** and
**30/30 browser journeys** passed, plus static/build and actual 600-location
recovery/approach/inspection/confirmation. Diagnostics: `/tmp/huntmaps-check-4yaku56v`.

Baseline `/tmp/huntmaps-first-person-20261018-a12o_q65`: source archive/pre-existing
patch/status preserved. **31,618 protected/state files byte-identical** with zero
added/missing paths; **353 frozen release inputs unchanged**. Final comparison in
`final-preservation.json`. No original output or GUI/state writes, dependency/model
changes, commits, pushes, or Windows/Data partition operations. Own servers stopped.

Final report: [FIRST_PERSON_RECOVERY_2026-10-18.md](FIRST_PERSON_RECOVERY_2026-10-18.md).
Exact next action: none for implementation. Owner should restart HuntMaps2 and use
**Retry detailed view** for A0136 to build the original saved setup from verified
cached files. The successful verification scene exists only in temporary state.
The historical checkpoints below record the work and corrected test failures.

## Backend batch

Observed original dense-plane rejection and cached-imagery skip before fixes.
Dense ground now uses bounded local triangulations, with the raw-point, address-space
and timeout guards unchanged. Effective cache estimates are computed without
rewriting approval inventories. Lidar/imagery retries share verified cache lookup.
Both new regressions pass (21.3 s); existing scene/storage tests pass (8 tests).

Actual A0136 replay in progress: exec 19996, isolated state/logs under baseline
`a0136-replay/`, downloads forbidden, unchanged 1536 MiB worker limit.
Window regression-before-fix running in exec 6482. Do not modify/build frontend
concurrently with that runner. Next: inspect both results, then implement compact
scene controls and guarded automatic basic fallback.

## Real A0136 preparation

Isolated replay PASSED with zero downloads: 66.28 s, 699.5 MiB peak RSS; original
1536 MiB address-space limit retained. Worker created its scene only under baseline
`a0136-replay/state`. All four lidar files and cached imagery were referenced read-only.
Rendering is still to verify.

Window regression failed as intended at `/tmp/huntmaps-check-xgekeqss` because the
compact disclosure was absent. Initial cleanup and guarded basic fallback are now
implemented. Focused browser run is exec 62168; do not rebuild/edit frontend until
it completes. Lidar and first-person backend compatibility tests are also running.
Next: inspect those results; expand browser coverage for retry, stale replies,
large/slow transfers and basic failure; repair acceptance selectors to current UI,
render A0136 from temporary state, then final full gate and preservation.

## Initial window verification

Focused browser `/tmp/huntmaps-check-kcpi5v4c` PASSED compact controls, actual basic
fallback generation/rendering, and no fallback after cancellation. Existing 21
first-person tests, 10 lidar recovery tests, and 8 scene/storage tests passed.

Current five-script acceptance run is exec 49845 (source frozen). It exercises new
controls plus existing lidar, Storage, transfer and full workflow acceptance with
updated visible actions. Next: inspect results, finish edge-case coverage and actual
A0136 rendering; then normal full release and baseline preservation.

## Acceptance fixture corrections

Five-script run `/tmp/huntmaps-check-vmrhlfjq`: new recovery and existing lidar
upgrade PASSED. Storage expected a redundant rebuild for an already-ready view;
it now uses an unprepared point and separately tests a blocked detail upgrade.
Transfer now checks the new visible storage warning. Workflow failure traced to
shared fixture seeding before its initial boundary assertions. New recovery journey
now generates an independent synthetic `scene-recovery-fixture`; focused ordering
puts workflow before specialist seeding, matching the normal gate. No meaningful
storage, workflow or pixel assertions removed.

Expanded recovery coverage adds a failed-basic no-loop case and a source reply
after closing the dialog. Four-script run in progress: exec 31821. Source frozen.
Next: inspect results; finish retry/narrow checks and A0136 actual rendering; then
full release and preservation.

## Detailed rendering and recovery edge cases

Actual cached A0136 scene rendered successfully at desktop and 900 px, with no
browser errors: `/tmp/huntmaps-first-person-20261018-a12o_q65/a0136-replay/screenshots`.
Its coordinates are unchanged, fine observer ground is available, and the renderer
reports 2,486,152 total triangles (207,088 vegetation). This verifies rendering,
not field fidelity. No original state or output was written.

Expanded fallback/cancel/basic-failure/closed-dialog journey and workflow pass in
`/tmp/huntmaps-check-h9cg2xnc`; existing lidar upgrade passes in
`/tmp/huntmaps-check-vmrhlfjq`; transfer passes in `/tmp/huntmaps-check-gxc6ub8o`.
Storage exposed an old async Playwright wait that completed before the worker;
replaced with explicit API polling, retaining the actual scene-ready assertion.
Added retained detailed failure diagnostics and current waypoint-revision guard.
Added saved-asset retry with zero new jobs and 900/450 px overflow/screenshot checks.
API regression confirms fresh cache estimates leave approval bytes/signature and
cumulative transfer ledger unchanged (passed).

Next: run focused scene recovery/Storage/lidar browser acceptance, inspect screenshots,
then freeze implementation and run the complete `./gui/check`. Finish report and
compare all 31,618 baseline protected/state hashes and path inventory. No commits.

## Focused acceptance complete

`/tmp/huntmaps-check-k7iycwld`: recovery, Storage and lidar-upgrade browser journeys
all PASSED, plus Black/Prettier/TypeScript/build and runner preservation. Recovery
also verifies retained detailed diagnostics and saved-asset retry creates zero jobs.
Desktop/basic fallback and 450 px screenshots visually inspected; no horizontal
overflow at 900 or 450 px. Storage now waits for actual successful publication.

Full release gate next. Implementation inputs will be hashed before launch and
compared after; do not edit/build frontend concurrently with the browser runner.

Full gate running as exec session `69495`; diagnostics root
`/tmp/huntmaps-check-bz1qwifm`. Frozen input manifest:
`/tmp/huntmaps-first-person-20261018-a12o_q65/release-inputs.json` (353 files,
excluding only this progress document and the final recovery report).

Gate backend milestone: all 269 tests passed across 12 groups; Black, Prettier,
TypeScript and Vite passed. Real recovery worker is running before browser acceptance.
Backend count evidence: `/tmp/huntmaps-check-bz1qwifm/backend-counts.json`.

## Full-gate cancellation race (fixture)

First full run `/tmp/huntmaps-check-bz1qwifm` passed 269 backend tests, static/build,
real 600-location recovery, new scene recovery and broad audit browser journeys.
Connectivity timed out after Cancel: retained real job finished successfully in
1.55 s before cancellation took effect, so UI correctly offered the completed-state
`Check connections again` rather than expected cancelled-state `Check connections`.
No application cancellation change is justified by that evidence.

Connectivity acceptance now pauses only its first owned/disposable worker before
returning the launch response, resumes after the real cancellation endpoint, and
asserts actual cancelled status before retry. No fake terminal status or weakened
assertion. Adds failure screenshot/text diagnostics. Implementation otherwise frozen.
Next: verify this focused journey, re-freeze inputs, rerun full gate. Final baseline
hash comparison remains required; source freeze from the first run will be superseded.

Connectivity focused correction PASSED: `/tmp/huntmaps-check-0t955xl5`, actual
cancelled worker and successful explicit retry, source-error persistence and explicit
25-to-30-degree retry; no browser errors. Full gate restarting with refreshed source
freeze (same 353 files). Prior full run retained for failure evidence.
Second full gate: exec session `42248`. Implementation remains frozen; only the
progress log and final report may be edited. Read the latest `/tmp/huntmaps-check-*`
log directory and this checkpoint before resuming after interruption.

Second full gate diagnostics: `/tmp/huntmaps-check-h98asy4i`. All backend groups,
static/build and real 600-location interrupted-download/retry/reload/three-stage
workflow passed. New scene recovery and broad audit browsers passed; connectivity
is now running. No further implementation changes since re-freezing inputs.

Second full run passed scene/audit/connectivity/lidar browsers, then guided flow
expected the removed single-option setup dropdown. Replaced that stale selector
with actual renderer-ready/candidate checks, shortlist membership, exact API
observer coordinates and matching visible heading. Pixel, target interaction and
confirmation assertions remain. Next: run the remaining 26 browser journeys with
keep-going to gather all outstanding failures before another final gate. No app
code changed; full backend results remain valid but final normal gate still required.

## Remaining browser compatibility and save feedback

26-journey keep-going batch `/tmp/huntmaps-check-0d_v62yi`: 25 passed, one failed.
Guided flow now passes without the removed single-option dropdown, checking actual
renderer candidate/ready state, shortlist membership and exact coordinates instead.
All coverage, transfer, Storage, performance, clusters and nearby-observer journeys
passed. The only failure is a regression introduced by the new metadata-effect
revision dependency: successful waypoint save changed revision and unnecessarily
reloaded the existing scene, clearing completion feedback and exploration state.
Actual job completed and stored the correct position. Removed only that revision
reload dependency; preparation actions/polling retain revision and stale-response
guards, scene loads remain scoped to URL/entity/retry. Existing exact-coordinate,
second-save/reload/export/restore regression is retained unchanged.

Next: focused working-waypoint + new scene recovery journeys, then freeze the final
inputs and run normal full `./gui/check --keep-going` (no skips). Baseline/hash
comparison and final report remain required. No original state writes or commits.

Final focused run `/tmp/huntmaps-check-9fkxgiw1` PASSED unchanged working-waypoint
regression plus scene recovery (both browser journeys, static/build, preservation).
Re-froze final 353 inputs. Starting complete normal release suite with keep-going;
this option changes failure collection only and skips/weakens no required checks.
Final full run exec session `69243`; discover diagnostics from the newest check
directory if interrupted. App and test inputs are frozen against release-inputs.json.
Final full run diagnostics: `/tmp/huntmaps-check-4yaku56v`. Final source scope is
recorded in baseline `followup-changes.json`: 18 modified existing source/docs/test
files and two new test files (plus this progress log and final report). All other
pre-existing source files are identical to the initial follow-up baseline.

Final gate milestone: all 269 backend tests passed (12 groups), format/type/build
passed, real 600-location recovery/three-stage browser workflow passed. First 17/30
main browser journeys passed through coverage batches; no failures. Evidence root
`/tmp/huntmaps-check-4yaku56v`, with `backend-counts.json` and live browser matrix.

## Completion

Full release and preservation completed successfully. `git diff --check` passes.
Final source/application/test files stayed frozen throughout the successful gate;
only this log and the final report were finalized afterward. No unresolved confirmed
implementation defects from this follow-up remain. Retained resource limits,
provider/field validation exclusions, exact evidence paths, test repairs and the
waypoint-feedback regression correction are documented in the final report.
