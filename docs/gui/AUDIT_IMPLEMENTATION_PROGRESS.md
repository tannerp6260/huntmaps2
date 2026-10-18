# Audit implementation progress

Authoritative scope: [AUDIT_2026-10-17.md](AUDIT_2026-10-17.md).
All phases are authorized; do not stop at a phase boundary. No pushes.

## Current checkpoint

**COMPLETE — all authorized phases finished.** A01–A11 are resolved with regression
coverage; bounded U01–U07 improvements are implemented and verified. No confirmed
finding is blocked. Remaining unconfirmed risks/future tests are recorded in
[AUDIT_IMPLEMENTATION_REPORT.md](AUDIT_IMPLEMENTATION_REPORT.md).

Final normal `./gui/check` **PASSED** at `/tmp/huntmaps-check-al_w2jzv`: **266 backend
tests, all 29 mandatory browser journeys**, formatting/build, and the actual
600-location interrupted recovery/full scouting workflow. This run includes the
final separate/duplicated-tab draft and stale-reload corrections. Browser/visual
review covers recovery, actual 549-point Find results at 900px and narrow/200% layout.

Final baseline comparison **PASSED**: **30,398 protected/state files byte-identical**,
no added/missing paths; **349 release input files unchanged** during the final gate
(report/progress excluded). Runner audit: 8,502 protected files, owner records and
companion state unchanged. Evidence is linked in the final report and retained in
`/tmp/huntmaps-implementation-20261017-h9m2_u0j/final-preservation.json`.

All pre-existing work is retained. No protected data/model/history/coordinates or
owner records changed; no dependencies updated; no commits or pushes. The owner's
process was not restarted; restart HuntMaps2 to load the backend changes.

**Exact next action:** none for this initiative. Deliver the final report and stop.
Do not begin speculative numerical changes, field collection or later optimization
from the remaining-risk list without new scope. Earlier entries below are a retained
chronological work log, superseded by this completed checkpoint.

## Recoverable baseline

Started from main `68ac7db` with pre-existing connectivity changes in ten tracked
files and nine untracked files. Preserve those changes. Full nonignored worktree,
binary patch, status, source hashes and 30,398 protected/state hashes are retained
at `/tmp/huntmaps-implementation-20261017-h9m2_u0j`. This is separate from the audit
evidence at `/tmp/huntmaps-audit-20261017-9ng51tgv`. No owner server is used for tests.
No historical analyses, model controls, coordinates or owner records are to change.

## Initial status (superseded by current checkpoint)

- Phase 0: inspected current status, audit, maintenance/testing guidance, component
  constraints and application configuration; recoverable snapshot complete.
- Phase 1: in progress. No application edits or new test results yet.
- Phases 2–5: pending.

## Verification and unresolved work

The authoritative audit documents an already failing browser release gate. Those
failures must be diagnosed independently, without weakening assertions or claiming
prior tests establish correctness. Regression tests will precede each defect fix.
Pre-existing work is excluded from any implementation-only commit.

## Initial next action (completed)

Add failing isolated regressions for A02/A07 job launch persistence failure and
invalid job types, then fix launch cleanup and shared job schema validation.
Continue with A04 catalog isolation, A03 cache identity and A01 note revisions.

## Batch 1 — critical reliability corrections

Added `tests/test_gui_audit_regressions.py`. Observed failing reproductions before
fixes: A02 orphaned real sleeper/log after write failure; A07 malformed timestamps,
status, identity and PID; A04 truncated/wrong-schema unrelated catalog entries;
A03 warm display bypassing corrupted target validation; A01 missing save revisions.
All five regressions now pass. Existing storage tests also passed (16 total at
that checkpoint). Added and reproduced A06 snapshot-restore failure and A11 worker
starvation, then fixed them; all seven audit regressions pass.

Changes: transactional job submission kills/reaps its process group and closes logs
on persistence/thread failure; shared job validation preserves damaged bytes;
catalog entries fail independently with Storage diagnostics; display dependencies
validate on cache hits and identities include inode/ctime; annotation saves use
optimistic per-point revisions and frontend in-flight exclusion. Notes retain drafts
by run/candidate and acknowledge only the sent draft. Restore uses snapshot semantics,
atomic file publication and a pre-restore backup. Optional browsing admission rejects
excess requests without waiting inside shared API workers.

A05 viewer readiness now waits for required foliage geometry and a render, and clears
local confirmation readiness on reload/context loss. Browser fault regression pending.
A08 connection jobs carry their run and have task-specific recovery (including legacy
cache lookup); browser coverage pending. A09 repeated sort/filter/max lookups replaced
by indices; hidden card construction deferred; large lists bounded to pages of 100.
Performance measurement and selection/page behavior verification remain pending.

Phase 2 investigation: `./gui/check` running at `/tmp/huntmaps-check-xv1_a_34`.
Browser harness now supplies deterministic optional transportation imagery in offline
journeys; actual analytical APIs are retained. Updated the obsolete boundary prompt
and three refinement selectors. Storage browser reloads now explicitly dismiss startup.

Exact next action: inspect the current full-suite result, fix consequential failures,
verify frontend build, then add browser regressions for notes/readiness/performance,
compact Find controls, and complete remaining acceptance and preservation checks.
No local commits yet; mixed pre-existing changes remain preserved in the baseline.

## Batch 2 — integration and UX

The first broad attempt exposed a cache-identity regression from recency touching
`ctime`; authoritative inputs now use strong identity while disposable display
recency does not invalidate unchanged PNGs. Six focused job/cache checks passed;
actual tile measured 64.1 ms cold, 0.7 ms warm with one reprojection. Two failures
in that attempt were caused by an overlapping development build removing dist
assets: keep builds and verification sequential. A subsequent full run passed all
158 GUI tests and approach/filter groups, then exposed another legacy test fixture
using a non-UUID job ID; both restart fixtures now use valid IDs. A bounded kill
thread now tolerates disappearance of a disposable test record.

New browser audit journey covers held saves, newer drafts, navigation/reload,
failed required foliage geometry, hidden list DOM and 150/600/1500/5000 synthetic
UI candidate pools. It is mandatory in the release gate. Browser execution pending
at `/tmp/huntmaps-check-*` (current command: audit regressions + workflow only).

Find uses bounded 100-card pages with full-pool filtering/ranking, precomputed
indices, deferred hidden cards and compact spacing. Batch coverage is an optional
disclosure; acceptance tests explicitly open it. Inspection prefers an existing
current prepared view and keeps Improve detail secondary. Transportation provider
errors stay in their own status with retry. Current workflow guidance corrected
for 2000 yd, 25 degrees, suggested draft and explicit Calculate.

Testing infrastructure: optional transportation fixture is served by the isolated
backend (`HUNTMAPS_BROWSING_FIXTURE`), so HTTP-cache journeys retain actual browser
cache behavior. Never use page routing to establish cache-reuse evidence. Specialist
journeys now explicitly seed the required completed workflow through actual services
using `browser-fixture.mjs`; this seeds decisions and is not browser-render evidence.
Transfer progress fixture now serves active job detail polling as well as job lists.

Exact next action: finish focused audit/workflow browser run, inspect screenshots
and timings, correct failures, then execute every browser journey and final complete
release gate. Add dedicated connection recovery/keyboard checks; finish current docs,
review diff against baseline, and compare all protected/owner hashes before reporting.

## Batch 3 — verified browser regressions and broader gate

`/tmp/huntmaps-check-g3u4os8m`: actual full workflow browser journey passed after
selector correction; note regression caught a real implementation mistake comparing
JSON property order instead of draft values. Fixed by comparing acknowledged fields
and the current editor, preserving newer edits even if browser storage fails.

`/tmp/huntmaps-check-6zk78av1`: audit browser regression PASSED (drafts, held save,
required foliage failure and bounded lists), and connectivity PASSED including
legacy-token history recovery with no baseline-plan request. Initial specialist
fixture failed because an absent approach review is null; fixed to explicit revision
zero. UI typing measurements (20 characters, synthetic response pools): 150=381 ms,
600=114 ms, 1500=134 ms, 5000=281 ms. Not a terrain-analysis benchmark or a direct
controlled comparison with earlier audit timing.

Inspected actual 900 px and zoom screenshots. 900 px now displays a candidate rather
than zero; high-zoom screenshot exposed clipping despite an overflow assertion. Added
an effective-width layout that uses full-width task/map panes, and a 450 CSS-pixel,
2x-scale acceptance case. Further condensed Find by moving explanatory connection
text into settings and omitting the disabled empty-shortlist next button.

Nine backend audit regressions now pass, including two additional reproductions:
tracked live worker cannot be bypassed by damaged records, and cancellation rejects
malformed types with a recovery error. Cross-window review conflicts now show the
latest saved review while retaining the draft for an explicit replacement decision.
Current docs distinguish review opinions, shortlist, export selection and collection.

All-browser investigation is RUNNING via `./gui/check --browser-only --keep-going`
at `/tmp/huntmaps-check-amoxq6a7` (exec session 14697). It includes the actual recovery
worker; inspect `browser-results.json` and individual logs as they appear. No additional
builds while this command runs. Changes to source after its build require a later gate.

Exact next action: collect this browser matrix, fix failures using retained diagnostics,
verify the independent fixture helper, inspect updated narrow screenshots, then run
complete `./gui/check`, protected/owner hash comparisons and final implementation report.
Do not stop at this checkpoint. No commits/pushes; all pre-existing work remains intact.

## Batch 4 — integration findings during the browser matrix

Current all-browser diagnostic run: `/tmp/huntmaps-check-p3okksnc`, exec session
42386. Explicit script selection skips the separate recovery worker for this
investigation; the final normal release gate must include it. First six journeys
passed. Redesign exposed an actual new layout overlap at 1366×768: the short-height
candidate list's visible overflow let the export disclosure cover Reset result
filters. Removed that overflow override; retain nested scrolling, never force-click.
This source correction requires the next build.

The separate recovery worker's actual 600-location download/retry journey passed
at `/tmp/huntmaps-browser-recovery-_6smrrlz`, but its reused workflow journey could
not select a point on a later page. Workflow acceptance now searches the full pool
and traverses every page for order assertions, preserving the original assertions.
This must be rerun in the normal release gate.

Added a real-worker updated-waypoint tile regression. It reproduced a new regression
from validating a derived working mask against the old manifest. Fixed the adapter
boundary: visibility_path validates its own manifest/publication seal; target/DEM/
cover dependencies still validate before warm hits. Cold/warm working tiles and
corrupted working-mask rejection now pass. Ten audit backend checks pass, including
waiter handling of externally damaged records without an unhandled thread exception.

High-zoom capture also needed a test fix: Playwright full-page screenshots reset a
raw CDP viewport override. The test now uses a fresh 450×450 context at 2x scale.
Inspect its next screenshot before claiming visual acceptance. The audit browser
now additionally measures the actual saved 549-candidate area when available, using
read-only analysis and isolated GUI drafts.

Exact next action: finish matrix 42386, classify and repair remaining failures,
rerun focused failed scripts including narrow screenshots, then complete normal
`./gui/check` and final preservation/report. Do not build while matrix is running.

## Batch 5 — shared guards and fixture classification

`/tmp/huntmaps-check-p3okksnc` matrix has reached coverage render: audit, connection,
lidar, guided full flow, Find, workflow, dismissal, refinement, workflow regressions,
coverage search, coverage batch and actual coverage pixel render passed. Known failures
have focused corrections queued for the next build/run:

- Redesign: actual low-height overlap; fixed scrolling, no forced pointer action.
- Target search: open Saved comparison history and use its labeled select, rather
  than a hidden last select; edited slope now stays within the current valid range.
- Guided approaches: explicitly choose the first rendered alternative; multiple
  valid alternatives make the former unqualified locator ambiguous.
- Transfer: active progress uses job-detail polling. Storage/source plan refresh is
  tested on reopening, rather than assuming a plan fetch on each progress tick.
- Coverage cache: Approach intentionally removes coverage overlays. Replace obsolete
  Coverage ready wait with assertions of hidden status and empty coverage sources;
  retain actual HTTP-cache reuse and all return/reload assertions.

Expanded A07 verification reproduced cache inventory breaking on a malformed job.
Shared has_active_jobs now conservatively pauses cache eviction/maintenance on unknown
worker state, while Storage diagnostics remain available. Submission refuses damaged
job records. Fake terminal-job fixtures now use valid record identities/types. All
23 focused audit+storage checks passed. Also reproduced shutdown aborting on a failed
cancellation write; shutdown now reaps its own tracked process even when persistence
fails. It retains the damaged/failed-to-update record for recovery rather than inventing
successful persistence. This regression passed using a harmless real process group.

Exact next action remains: finish matrix exec 42386, diagnose remaining specialist
scripts, run focused failures independently, inspect the corrected narrow context
screenshot, then full normal release check and final byte-preservation/report. No
concurrent frontend build while the matrix is active. Preserve all baseline work.

Latest matrix checkpoint: complementary also passed. Remaining specialist journeys
are still running under exec 42386. The shared damaged-job cache guard and shutdown
fallback have focused passing tests, but are newer than that server's imported code;
final verification must start a fresh server. Maintain source/test-only scope and do
not commit the pre-existing connectivity changes as implementation work.

## Batch 6 — preservation and optional-provider refinement

Interim preservation PASSED: all **30,398** baseline protected/state files unchanged
byte for byte. Evidence: baseline directory `interim-preservation.json`.

A11 now awaits provider capacity asynchronously before borrowing shared API threads,
with at most two provider calls. A further failing regression showed that simple
nonblocking admission rejected ordinary viewport bursts; asynchronous queuing fixes
that. Another failing regression showed warm optional tiles waiting behind a stalled
provider; cached responses now bypass the provider queue. All **14 audit backend
regressions pass**, covering the original cases and shared cancellation/shutdown/cache
edges. This is newer than the running browser server and needs the final fresh gate.

Current matrix additionally passed first-person, scene storage, GUI storage and
all four connected foliage scenes/zero idle draws. Working-waypoint failure matches
the already-fixed derived-mask validation regression. Scouting/network compatibility
failures are closed nested Roads/trails disclosures; added a pointer-driven helper to
open both disclosures. Slope fixtures use the accepted <=35-degree limit. The two
remaining mutation assertions need semantic classification: inventory resolution is
an existing read-only POST (`covering_networks` performs reads/validation only). Tests
now allow that exact lookup, retain write/job assertions, add exact owner-workflow
preservation in practice, and record HTTP diagnostics for the next focused run.
Never allow arbitrary writes to make these assertions pass. Scouting annotation
restoration now supplies the current revision and asserts successful restoration.

Matrix exec 42386 is on the last nearby-observer script. Once it finishes, run a fresh
focused set of failed journeys plus the updated audit/narrow test; inspect diagnostics
and screenshots, then normal complete release gate and final preservation/report.

## Fresh focused rerun checkpoint

`/tmp/huntmaps-check-bgtnikvm` audit browser PASSED, including actual conflict
recovery after a second editor commits and actual owner-analysis UI measurements:
150=152 ms, 600=102 ms, 1500=117 ms, 5000=207 ms; actual saved 549-point area=88 ms
for 20 typed characters. Measured with hidden candidate DOM absent; analysis bytes
are read-only. This is not a controlled A/B with the earlier audit's concurrent load.
Redesign PASSED, including the low-height empty-results reset formerly occluded.

Fresh narrow screenshot showed stage titles overlapping because a zero flex basis
collapsed the navigation beside the toolbar. Explicit full-row flex bases are queued
for the next build, and the audit test now asserts nonoverlapping stage rectangles,
waits for actual results and exercises keyboard selection before capture. Do not
claim narrow visual acceptance until this corrected screenshot is inspected.

A11 healthy-burst and stalled-cache regressions passed after asynchronous provider
admission plus cache bypass; all 14 audit backend regressions pass. The next full
release check must exercise these latest changes in a fresh server.

## Final gate checkpoint and copy review

Normal gate `/tmp/huntmaps-check-wd73wz7i`, exec 49230: all **266 backend tests**,
Python/frontend formatting, TypeScript/build, and the real **600-location recovery
plus full workflow** passed. The 29-browser sequence is now running. Expanded audit
and connectivity passed so far. Leave application/test source frozen until it ends.

Final review found a wording clarification to apply after this run: the new review
hint/docs must not imply Keep can never affect shortlisting. Existing compatibility
behavior in approach_service.point_snapshot inherits Keep when no workflow decision
is stored, and workflow decisions take precedence. Preserve that behavior and owner
records; change only copy to explain Keep may carry a setup into Approach and explicit
Shortlist/Remove controls that choice. Practice notes remain separate. Verify that
copy with formatting/build and the focused review browser journey; do not alter the
analytical/legacy decision implementation to simplify wording.

Then finalize the implementation report from the actual final logs, final byte and
path preservation comparison, current diff review and current progress checkpoint.

## Final draft isolation batch

Confirmed the shared-key failure with two actual tabs before fixing it. The first
new test attempt (`/tmp/huntmaps-check-bstkhr3b`) was a Playwright context-setup
error, not an application reproduction; corrected to an explicit shared context.
`/tmp/huntmaps-check-apfr5sg4` then reproduced the real note replacement.
`review-drafts.ts` retains each tab's draft plus its starting server revision and
uses explicit recovery for other branches. Cross-tab messages contain identities
only. The expanded regression also verifies duplicated-tab sessionStorage copies,
reload after another editor commits, 409 before explicit replacement, abandoned
branch recovery without server mutation, and continued in-flight edits. Focused
audit/training/Storage all passed at `/tmp/huntmaps-check-7rz3f66y`.

No model, source, owner record or historical output changes. The latest copy explains
legacy Keep inheritance accurately. Final normal release verification is next.

Pre-existing untracked work review: six of nine original untracked files remain
byte-identical. Three have narrow initiative changes verified against the archive:
connection job run identity, legacy history regression, and moving explanatory copy
inside the existing settings disclosure. All original files remain present.

Final gate `/tmp/huntmaps-check-al_w2jzv`: all 266 backend tests and format/build
checks passed; real 600-location interrupted recovery and full workflow passed.
Eight mandatory browser scripts have passed so far. Draft recovery and narrow-layout
screenshots were visually reviewed. Source remains frozen. Next: poll session 81350
until the remaining browsers finish, then run final preservation and finalize reports.

## Completion evidence

Final normal gate `/tmp/huntmaps-check-al_w2jzv` exited 0 after all 266 backend
tests, static/build checks, actual 600-location recovery/full workflow and all 29
browser scripts. Final preservation script exited 0: baseline/current 30,398,
changed/added/missing all empty; 349 release input files unchanged with no source
additions/removals. Screenshot review and final diff check passed. The report is
finalized; no required implementation or verification action remains.
