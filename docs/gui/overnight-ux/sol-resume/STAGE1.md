# Stage 1 complete · design and recommendation slice

2026-10-22 · actual resumed **gpt-6.1-sol / high** CLI stage. Starting and final HEAD
`6ec6a5510058edb5668fb0ad83596f2c8795caa6`, branch `feature/hunter-workflow-ux`.
No commit, staging, next-stage invocation or helper agent. Original blocked records
are historical and unchanged. No Astra implementation/review is claimed.

## Working slice

Added a compact decision panel before the map using the real backend recommendation,
selected route and period. It shows stop count, exact entry/date/profile, complete
walking distance/ascent, movement range, scheduled observation and scheduled return,
remaining usable effort and held reserve. Experimental and conditional-access/
sightline labels remain explicit. A native period selector shares state with the
existing schedule/save selectors. Up to two alternatives use different viewpoint
sets in backend preview order; all original previews remain below the map.

Inspection, schedule and save actions focus/scroll to the existing working evidence
or name input. Visual review caught and fixed the initial schedule jump that stopped
above its long scan summary. Selection clears transient point/segment/profile
inspection. The panel distinguishes previous-input/running previews, and saving is
blocked during a job or while current settings differ from the retained analysis,
including after cancellation. No analysis, API, candidate generation, ranking,
feasibility, habitat, coordinates or save/export schema changed.

This is deliberately one additive slice. The long essential-input stack and detailed
preview/sector lists remain. [DESIGN.md](DESIGN.md) specifies the complete layout,
states, microcopy, component/value mapping, accessibility and compatibility contract.
[REMAINING.md](REMAINING.md) gives concrete Stage 2 tasks and later review boundaries.

## Actual evidence

Fresh unchanged-code baseline in `/tmp/huntmaps-ux-sol-stage1/baseline` completed the
nine-action real Flattop task (2026-10-31, Together, default32, practical identify /
unknown leaf / no scan cap). It matched prior baseline AM/PM recommendation IDs.
Baseline selected preview began at document y746.8 and save at y2789.0. The new
panel begins at y254.8 at1366×900 with the decision facts and all three primary
actions visible. This is a measured layout change, not a participant/time claim.

Final focused browser run used `/tmp/huntmaps-ux-sol-stage1/final-state`, real
services/packages and installed `/usr/bin/google-chrome`. It passed backend
recommendation IDs, AM/PM selection, a distinct alternative, full preview selection,
actual selected support-image requests/sector counts/coordinates, schedule and save
focus, immutable save, GPX download, dirty save blocking, keyboard jumps, real worker
cancellation and retained stale preview/save blocking afterward. 1366/820/390px
layouts had no horizontal document overflow; no page errors/external requests.

Screenshots were actually viewed: baseline start/result, initial panel and narrow
layouts, final laptop decision panel, final schedule and390px layout. Final artifacts
are under `/tmp/huntmaps-ux-sol-stage1/accepted`, indexed with SHA256 in
[stage1-artifacts.json](stage1-artifacts.json). Compact results and all attempt
outcomes are in [stage1-evidence.json](stage1-evidence.json).

Fresh baseline analysis-to-results was18.881s; accepted browser rerun was5.958s with
warm derived caches. They are different cache conditions. No GIS speedup, task-time
improvement, participant study, biological improvement or field validation is claimed.
Final selected coordinates stayed exactly
`(-106.91477051658299, 38.66483519955249)` and
`(-106.90947795537001, 38.66443940317754)` for the saved AM recommendation.

## Checks and limitations

- Final `./trailscout build`: TypeScript/Vite passed. Existing >500kB bundle warning
  remains; no dependency or bundling-policy change.
- Final Prettier source check and `git diff --check`: passed.
- Focused browser command: passed after the visual schedule fix. Run:
  `TRAILSCOUT_URL=http://127.0.0.1:8793 TRAILSCOUT_SCREENSHOTS=/tmp/huntmaps-ux-sol-stage1/accepted node docs/gui/overnight-ux/sol-resume/stage1-browser.mjs`
  against **disposable** state only. The script resets that state's party to Together,
  creates immutable test saves, exports and cancels a real job.
- Full `TMPDIR=/tmp/huntmaps-ux-sol-stage1/gate ./trailscout check`: exit0, all eight
  gate stages passed:48 app tests,50 legacy compatibility tests, three real browser
  scripts plus format/build. Small frontend refinements occurred while that gate
  ran. It is a development full pass, not final-source release acceptance; final
  build/format/focused browser were rerun afterward. Stage 2 must run full TrailScout
  and `./gui/check --keep-going` against its stable completed source.
- Failed outcomes are retained separately: first browser exact accessible-label
  failure fixed in the component; later added cancellation-test button locator
  omitted its arrow and was corrected using the existing gate's anchored pattern.
  An intermediate browser pass did not catch the visual schedule jump issue; the
  final run asserts focus on the actual selected schedule.

No acceptance blocker for this bounded Stage 1. Missing-package/empty/access-scenario
coverage, comprehensive async/persistence/reload/export identity, all legacy variants,
full accessibility and final release/independent review remain Stage 2/3 work.
The component supports backend doubled movement for established combined trips;
practical combined/stay remain disabled. Static comparison remains separate.

## Preservation and exact source

[stage1-preservation-after.json](stage1-preservation-after.json) freshly verifies
all45,980 protected files /8,976,127,263bytes against the preserved inventory,
including sources, original reports, owner state and saved work. No changed/missing/
added files. Original untracked coordinator prompt still hashes
`6469ac12e84ac948de2004f59f8b14db9eec0d89130bad0698173c6e87ede1e6`.

Final tracked diff (`git diff --binary HEAD`) SHA256:
`4d6a6e5a99d25eabe8e813e5485ed86bf558e933fa7b0de42044dba704703fcb`.
New untracked implementation `trail_scout/web/src/recommendation.tsx` SHA256:
`9df803187d74d14788ebd81d90b2aab572c3deb11568c8c2f90f5b8beb0b4bc5`.
[stage1-source.json](stage1-source.json) records all three runtime file hashes and
the browser script hash. No runtime edits follow accepted-source checks.

## Launch and handoff

Build with `./trailscout build`. For fresh isolated review:
`./trailscout serve --state /tmp/huntmaps-ux-sol-review-stage1 --port 8795`, then
open <http://127.0.0.1:8795>. Choose Flattop Bench, Together, expand **Timed practical
plans · experimental**, enable **Use practical objective for AM/PM plans**, compare.
The already tested service was8793 with `final-state`; it contains test saves and
the deliberately cancelled last job. No owner state was used.

To return to the finished pre-UX code, first preserve this reviewable uncommitted
diff and the new component/documents, then use the retained practical-plans branch
in a clean workspace and build. Do not reset/stash/discard this handoff. There is no
data migration or source/state deletion to reverse. Coordinator verifies/commits;
this stage stops here, without invoking Stage 2 or independent review.
