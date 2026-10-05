# Guided approaches and imperial display — 2026-10-04

This milestone changes review presentation and saved workflow state. It does not change the terrain/approach solver, engine ranking, original coordinates, source units, exports, historical analyses or prepared scenes.

## Review behavior

Step 2 visits shortlisted spots in descending matching visible area, falling back to original coverage, then stable ID. An existing review order stays fixed. Restored or newly shortlisted spots append; removed spots leave the retained queue. The focused spot stays visible in the task panel while scrolling. Only shortlisted markers appear in Step 2, and only one alternative is highlighted. Alternative navigation, elevation profiles, point-specific history and provisional exports remain available.

An uncomputed spot starts one comparison after an explicit search boundary and network sources are ready. Copying/importing a boundary requires confirmation. Default weights remain one each and the slope constraint remains 30 degrees. Each submission sends one exact waypoint revision through the existing sequential job service. Cancelled, failed and no-path attempts need an explicit retry. Changes and recalculations affect only the focused spot; prior immutable scenarios stay available. Removed spots' saved comparisons are readable from recovery history without silently shortlisting them.

Use this approach & next spot selects and advances. Dismiss spot & next advances after a successful decision; Undo restores the existing workflow record. Every retained spot must have a current selection before continuing to inspect. At least one retained spot is required. Early viewing stays available, but both the GUI and backend enforce the guided-session final confirmation gate.

Run-scoped version-1 records under the configurable `approach-reviews/` store hold review order, focus, drafts, attempted status, scenario and preview alternative. Writes check review/workflow revisions and the exact waypoint. Backend decisions reject comparisons whose inputs differ from the saved draft. Maintenance backups and protection include the records; reviewed generated-run deletion includes the corresponding record. Historical workflow annotations and analyses are preserved.

## Display and editing

Areas display in square miles; horizontal distances and the map scale use yards; vertical measurements use feet. Preset values convert labels without changing their underlying metric values. Source metadata, calculation logs and exports keep original units. Shared display conversions explicitly retain unknown values and distinguish tiny positive areas from zero.

Raw decimal text is retained while typing, including `.` and `.75`. Incomplete entries disable the affected action instead of replacing the text with NaN. Per-point slope fields reset to that point's saved value when focus changes. During comparison submission, selection and preference controls cannot race the canonical response.

## Verification

`./gui/check` runs disposable state/workspaces and checks protected files and the owner's GUI records. The guided browser journey covers actual single-point workers, custom recalculation, independent settings, reload, marker clicks, 2D/3D shortlist sources, automatic advance, dismissal/Undo, the inspection gate, decimal keystrokes and desktop/900-pixel screenshots. Backend coverage includes stale review/waypoint submissions, draft-to-scenario validation, per-point invalidation and the all-retained gate. Existing full three-stage recovery and scene opening/confirmation remain in the suite.

Final `./gui/check` passed: 144 backend tests, 19 browser checks, formatting/build, and the isolated 600-location recovery journey through all three stages. Diagnostics: `/tmp/huntmaps-check-v9fs6exx`. The protected audit checked 10,353 files and reported no changes. Desktop and 900-pixel screenshots were inspected. The test server reached 1,249.5 MiB peak RSS across the full suite (including multiple terrain/coverage caches); worker measurements below are separate.

## Measured overhead

An isolated three-point synthetic fixture used identical sources, geometry, preferences and solver objectives for a batch and three individual jobs:

| Execution | Total wall time | Worker calculation time | Maximum worker RSS |
| --- | ---: | ---: | ---: |
| One three-point job | 1.736 s | 1.582 s | 168.16 MiB |
| Three individual jobs | 3.616 s | 3.176 s | 168.27 MiB |

Individual wall times were 1.231, 1.170 and 1.216 seconds. Separate jobs expose the first result sooner but approximately doubled total fixture work through repeated grid preparation/startup. A workflow read averaged 0.102 seconds across ten reads. These measurements are fixture-specific, not predictions for a large hunting area. No grid cache or solver changes were introduced. The existing single-job execution, 1536 MiB address-space guard, 900-second worker limit and storage safeguards remain.

Benchmark artifact: `/tmp/huntmaps-guided-benchmark-gt637765/benchmark.json`. No external source download was needed for this benchmark.
