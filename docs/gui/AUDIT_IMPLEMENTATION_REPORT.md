# HuntMaps2 audit implementation report

Completed the authorized initiative. All eleven confirmed findings A01–A11 have
focused corrections and regression coverage; U01–U07 have bounded usability and
documentation improvements. The complete required release gate passes. No confirmed
finding remains blocked. Unconfirmed concerns and verification limits are listed below.

The authoritative findings remain in [AUDIT_2026-10-17.md](AUDIT_2026-10-17.md);
implementation continuity is in
[AUDIT_IMPLEMENTATION_PROGRESS.md](AUDIT_IMPLEMENTATION_PROGRESS.md).

## Implemented corrections

| Priority / finding | Result | Regression evidence |
| --- | --- | --- |
| P1 A01 | Per-point optimistic revisions reject stale saves. The editor prevents overlapping submissions, retains per-area/per-setup/per-tab drafts and their starting revisions, and acknowledges only submitted values. Conflicts show the latest saved review before an explicit replacement decision. Other branches have explicit recovery. | Actual held-save/navigation/reload journey, separate and duplicated tabs, stale reload 409, abandoned-branch recovery, second-editor conflict/recovery, stale-revision API regression. |
| P1 A02 | Failed submission kills/reaps its process group and closes its log. A tracked live process still blocks another launch if its record is damaged. Shutdown stops its own child even when cancellation cannot persist. | Harmless real process-group failures; existing success/failure/cancellation/descendant/restart checks. |
| P1 A03 | Authoritative dependencies validate before warm coverage hits. Cache identity includes inode/ctime for authoritative sources, while recency touches preserve reusable display tiles. Working masks validate against their own publication seal. | Equal-size/equal-mtime target corruption, warm tile reuse/reprojection checks, real updated-waypoint tiles and corrupted working-mask rejection. |
| P1 A04 | A damaged run configuration is skipped independently and reported in Storage; healthy catalog entries remain usable. Damaged bytes remain untouched. | Truncated JSON and invalid-schema catalog regression plus actual saved-run browser journeys. |
| P2 A05 | Required foliage must load and render before inspection is attested. Reload/context loss clears local confirmation readiness. Terrain-only inspection remains supported, and imagery limitations remain explicit. | Required foliage asset failure produces no viewed request; actual terrain-only workflow and existing saved scene journeys. |
| P2 A06 | Restore replaces the GUI snapshot, including files created later. A pre-restore backup retains replaced records. Both raw and versioned records publish atomically per file. | Snapshot restoration, retained recovery copy, identity/coordinate/revision backup checks and actual Storage browser journey. |
| P2 A07 | Shared job validation protects startup, listing, cancellation and waiter handling. Storage reports damage without replacing its bytes. Unknown worker state pauses cleanup and new worker submission. | Invalid types/identity/timestamps/PID, cancellation, waiter, shutdown and cache-diagnostic regressions. |
| P2 A08 | Connection jobs retain their area, and recovery routes to Find for that area. Legacy entries resolve their retained screen token instead of requesting a baseline plan. | Actual connection history recovery, including a legacy entry without its name; no baseline-plan request. |
| P2 A09 | Ranking/filter lookups and list maximums are computed once per render. Hidden lists do not mount candidate cards. Pools above 250 use pages of 100 while search and ordering cover the whole pool. | Synthetic UI pools through 5,000, actual 549-point saved analysis, page/search/ordering and hidden-DOM assertions. |
| P2 A10 | Browser fixtures, active job-detail mocks, visible controls, explicit alternative choices and current limits are restored without forced clicks. Specialist journeys seed their prerequisites through actual services. | 266 backend tests, all 29 mandatory browser journeys and the real 600-location recovery/full workflow passed. |
| P2 A11 | Cold optional browsing requests await provider capacity outside the shared API worker pool. At most two provider calls run; cached tiles bypass a stalled provider queue. | Stalled 40-request burst/status, healthy 16-tile burst and cached-tile latency-bound regressions. |

The browser failures included outdated selectors/disclosures, missing standalone
workflow/network fixtures, stale limits and job-detail mocks, and request interception
that disabled HTTP caching. Repairs use current user actions, explicit prerequisite
services and a local optional-provider fixture. Pixel, ordering, coordinate and
pending-state assertions remain active. The permitted read-only network-resolution
POST is identified explicitly; training also checks that saved workflow records stay
unchanged. The progress log records the individual failures and repairs.

## Highest-value changes

1. Prevent silent note loss and retain unfinished drafts across navigation/reload.
2. Stop workers reliably when submission, persistence or shutdown fails.
3. Treat cached coverage as display data whose authoritative inputs still require validation.
4. Isolate damaged run/job records and preserve actionable recovery diagnostics.
5. Require successful rendering before recording a newly inspected scene.
6. Restore coherent GUI snapshots with an automatic recovery copy.
7. Keep essential APIs and cached context usable during optional provider stalls.
8. Make large candidate pools interactive and leave actual Find results visible.
9. Make the release journeys reproducible with explicit fixture contracts and meaningful assertions.

## Find → Approach → Inspect → Save

U01–U07 are addressed within the existing layout and workflow. Find has tighter
spacing, collapsed optional coverage preparation, compact connection guidance and
bounded lists. Review opinions, shortlisting, export selections and confirmed
collections have distinct controls explained in the editor. Legacy Keep opinions
can advance a setup when no explicit workflow choice exists; that compatibility is
preserved and documented. Drafts persist by area, setup and tab, with explicit
recovery for other retained branches. Optional transportation failures have scoped
feedback/retry, and connection history opens the correct task. A current prepared scene gets the primary open action;
new detail remains a separate explicit preparation choice.

Keyboard navigation/confirmation, dialog focus return and effective 200% zoom are
covered by browser checks. Narrow panes use the available width rather than clipping
one another. Saved comparison controls have an explicit accessible name. Current
workflow/maintenance/testing guidance describes the actual defaults and recovery;
dated evidence reports remain preserved. These are engineering and visual checks,
not a representative-hunter usability study or blanket accessibility certification.

| Opportunity | User benefit and verification |
| --- | --- |
| U01 | Compact Find controls leave actual results visible at 900×900; browser asserts the list is inside the pane, rather than merely checking horizontal overflow. Optional coverage controls stay accessible in a disclosure. |
| U02 | Review, shortlist, export and confirmation controls explain their different effects, including legacy Keep inheritance. Existing workflow, annotation and export assertions remain meaningful. |
| U03 | Navigation/reload retain unfinished notes. Held saves, competing edits, separate/duplicated tabs and explicit recovery verify the persistence policy. |
| U04 | Optional transportation failures have local status/retry; real connection history opens the correct area/task. Controlled 503→200 and legacy history checks passed. |
| U05 | Current scenes offer Open prepared view as the primary action; Improve detail remains explicit. Actual scene journeys retain approval and rendering/confirmation gates. Click-count studies remain future work. |
| U06 | Narrow navigation stays separate, results remain reachable, comparison controls have names, and closing inspection returns focus. Keyboard and effective-200%-zoom checks passed; assistive-technology testing remains separate. |
| U07 | Current guidance uses 2,000 yards, 25°, editable suggested boundaries and explicit Calculate. Historical reports remain unchanged. |

## Performance observations

In the final headless Chromium run, typing 20 characters took approximately 170 ms
at 150 synthetic candidates, 120 ms at 600, 141 ms at 1,500 and 324 ms at 5,000. The
actual saved 549-candidate area took 93 ms, with no hidden candidate cards mounted.
The audit observed about 2,125 ms on that saved area before the correction, during
concurrent verification; these observations are not a controlled A/B speedup estimate.
The large synthetic lists measure UI work, not a full 5,000-location scoring run.

A real coverage tile measured 51.8 ms cold and 0.7 ms warm with one reprojection.
The saved 2.7-million-triangle scene check measured about 7.9 seconds to open and
357 ms for a nearby nudge under software rendering, with zero idle draws and no
additional geometry requests for movement. Hardware/GPU and live-provider performance
are outside these observations. No analytical model or scene-source regeneration
was introduced to obtain these measurements.

## Remaining limits and future checks

All confirmed audit findings have focused corrections; final release status is
recorded below. The original audit's plausible concerns remain distinguished from
verified defects:

- Restore publishes each file atomically and retains a pre-restore backup, but does
  not commit all records as one crash transaction. Inject interruption between files
  before considering a broader transactional design.
- Scene open/close heap and GPU stability across long repeated sessions still need
  a dedicated measurement. Existing disposal, idle-draw and movement checks do not
  establish a leak or prove its absence.
- Synthetic large lists and the real saved 549-point area establish UI behavior;
  full 5,000-view scoring with active filters is not benchmarked here.
- A moved working point's inherited matching rank remains an unconfirmed numerical
  concern from the audit. Check current masks against ranking before proposing a
  model or scoring change.
- Review-save permutations now cover tabs, reloads and held writes. Other mutation
  editors are not exhaustively tested under every request ordering. Live providers,
  physical GPUs, assistive technology and representative hunters need separate checks.

## Final verification and preservation

The final normal **`./gui/check` passed**, artifacts
`/tmp/huntmaps-check-al_w2jzv`. This run includes the final multi-tab draft correction.
An earlier complete gate also passed before that extra regression was added; earlier
diagnostic failures and repairs remain recorded in the progress log.

| Verification | Observed result |
| --- | --- |
| Backend release groups | **266 tests passed** across 12 groups, including 14 new audit regressions and the expanded working-mask tile test. |
| Mandatory browser acceptance | **29/29 passed**, including the expanded audit, actual saved scenes, Storage recovery, training, performance and connectivity. |
| Real recovery and scouting workflow | Actual interrupted-download/retry, reload, 600-location search and Find → Approach → Inspect → Save passed in a disposable workspace. |
| Static/build checks | Black, Prettier, TypeScript and Vite passed; `git diff --check` passed. Existing Matplotlib Axes3D and Vite bundle-size warnings remain nonfatal; no dependency update was used to obtain a pass. |
| Runner preservation | **8,502 protected files unchanged**; owner records and isolated companion state unchanged. |
| Full baseline comparison | **30,398 protected/state files byte-identical**, with **zero added or missing paths**. Includes analytical source, configurations, historical evidence, data, runs/results and GUI state. |
| Release input stability | **349 files unchanged during the final gate**, with zero additions/removals; only this report and the progress log were excluded for final documentation. |
| Browser/visual review | Actual interactions plus desktop, 900px and effective-200%-zoom screenshots; conflict recovery, visible real-area results and nonoverlapping navigation reviewed. |

Evidence: [backend counts](/tmp/huntmaps-check-al_w2jzv/backend-counts.json),
[browser matrix](/tmp/huntmaps-check-al_w2jzv/browser-results.json),
[600-location recovery log](/tmp/huntmaps-check-al_w2jzv/browser-recovery-worker.log),
[runner preservation](/tmp/huntmaps-check-al_w2jzv/protected-audit.json),
[full baseline/source comparison](/tmp/huntmaps-implementation-20261017-h9m2_u0j/final-preservation.json).
Performance evidence: [candidate timings](/tmp/huntmaps-check-al_w2jzv/screenshots/browser-audit-regressions/results.json)
and [scene measurements](/tmp/huntmaps-check-al_w2jzv/screenshots/browser-performance-check/performance.json).
Reviewed screenshots: [900px real area](/tmp/huntmaps-check-al_w2jzv/screenshots/browser-audit-regressions/find-900.png),
[narrow/200% layout](/tmp/huntmaps-check-al_w2jzv/screenshots/browser-audit-regressions/find-200-percent.png),
[draft recovery](/tmp/huntmaps-check-al_w2jzv/screenshots/browser-audit-regressions/draft-branch-recovery.png).

The recoverable initial worktree, binary patch and hashes remain at
`/tmp/huntmaps-implementation-20261017-h9m2_u0j`. Pre-existing work is retained;
related connectivity/UI files received narrow, reviewed changes without discarding
their original functionality. No protected historical output was regenerated, no
analytical model/scoring change was made, and no Windows/Data partition was targeted.
All verification used temporary state/workspaces and local provider fixtures. The
owner's GUI server and saved records were not test targets.

Changes remain uncommitted in the working tree to avoid bundling unrelated
pre-existing work. No dependencies were updated; no commits or pushes were made.

Restart HuntMaps2 before using the changes so the running Python backend loads the
new save/recovery behavior. The owner's process was left alone during verification;
the release runner stopped its own disposable servers.
