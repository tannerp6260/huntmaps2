# Sol High Stage 2 completion evidence

2026-10-22 · branch `feature/hunter-workflow-ux` · starting HEAD
`c54f5250c211171e823ae266ab1e44611a58da17`. Product base remains
`111e2af713a716eecdc4f4f11c20e12e6ba0bd37`. This is the actual sequential
**gpt-6.1-sol / high** Stage 2 CLI run; no Astra or helper implementation/review,
no recursive run, commit, staging, push or merge. Original blocked evidence remains
historical and unchanged. Independent Stage 3 is still required.

## Delivered journey

The input column now starts with party, nominal daily limits and exact usable
budget, then date/vehicle and assumed entry. Together displays **1.875 mi / 562.5 ft**
after 25% reserve from **2.5 mi / 750 ft**. Valid zero-valued expert settings remain
zero. Entry evidence is expandable, custom start coordinates stay visible, and the
bounded corridor/nearby/polygon summary precedes calculation. Advanced effort,
optics, habitat/static/timed objectives, schedules, access edits and source/area
imports remain accessible without a wizard.

Stage 1's recommendation panel remains presentation-only. Long retained previews
and per-stop sector lists are now disclosures; all options, original coordinates,
scan sectors and provenance remain accessible. The route/map/support share one
selected option and period. Inspection buttons use a native pressed-button group
instead of invalid tab semantics. Save/export focus and contrast checks are explicit.
Export copy distinguishes the immutable saved version from a changed current preview.

Serialized draft writes and an immediate local pending-draft copy preserve quick
reloads. Browser view state is scoped to the real service state's identity and local
origin. Reload retains period/alternative/name/view/export identity, but a newer
completed calculation takes precedence. Explicit saved/history opening has generation
protection; newer edits/selection/run invalidate delayed opens. History opening checks
source/model staleness. Context responses are guarded, calculation waits for current
entry/date evidence, and context failure offers retry. Job polling avoids overlapping
requests and retains active/save blocking until result hydration completes. Cancellation
waits for worker acknowledgement. Errors and empty results retain prior work and limits.
Core readiness is factual; unavailable community data permits an explicit existing
opt-in off switch, without automatic model substitution.

No backend/API/schema, ranking, feasibility, coefficients, candidate generation,
coordinates, source package, legal-access policy or analytical control changed.
Static collections remain separate; practical combined/stay remain disabled.
Foreground is coarse 40 m RCMAP risk, never measured clearance/transmission.

## Actual browser and comparison evidence

Final browser/source evidence is indexed in `stage2-evidence.json`,
`stage2-source.json` and `stage2-artifacts.json`. Large images, outputs and logs remain
under `/tmp/huntmaps-ux-sol-stage2`; screenshots were actually viewed.

The real Flattop 2026-10-31 Together/default32/identify/unknown-leaf/no-cap task has
identical normalized settings, source revision, recommendations, coordinates,
movement and remaining effort to the fresh Stage 1 baseline. Both completed nine
scripted semantic actions. **No action-count reduction** is claimed. Calculation
moved from document y1278.8 to y879; the decision panel starts at y254.8, with route,
schedule and save focus actions visible. The absolute save control remains below
the evidence (y2846.7 versus baseline y2789); the new focus action reaches it directly.

The baseline script measured18.881s submission-to-region in fresh state. Accepted
new matched task measured6.995s with warm caches, while the earlier fresh-state new
task took21.297s during concurrent gates. These are different cache/load conditions,
not GIS or participant task-time improvements. Two new selection UI transitions
measured27.9/47.2ms separately. See `stage2-comparison.json`; there were no participants,
synthetic hunting observations, biological improvement or field/blinded validation.

Final focused journeys exercise AM/PM recommendations, distinct alternatives, map
option/analysis/period/leg identity, actual requested support imagery, sector counts,
coordinates, observation/return, immutable JSON/summary/GeoJSON/GPX, selected alternative
and saved export identity on reload, immediate edited-budget reload, keyboard focus,
stale saving and real worker cancellation. Recovery checks exercise delayed saved
opening, serialized delayed drafts, delayed context, source/context HTTP failure and
retry, real unknown-foot-access/zero-scan empty result, and party/date/objective reload.
Package checks use genuinely unavailable disposable packages, real failed-job retry,
explicit established fallback, and retained saved GPX with missing core data.

1366/820/683/390px layouts have no document horizontal overflow. 683×450 exercises
reflow equivalent to a 1366×900 display at200%; it is not a full browser-zoom/WCAG audit.
Sampled actual text contrast ratios are11.40,7.43 and5.24; keyboard outline is3px and
focus moves to route/schedule/name. Narrow screenshots were visually inspected.

## Gates, failures and final identity

Gate results and exact source hashes are finalized below before handoff. All failed
complete/isolated attempts are retained separately. The initial full TrailScout gate
passed48 backend/50 compatibility tests and the established browser, then failed
static review hydration: a remembered older UI analysis hid a newly completed API
calculation. The source fix preserves deliberate saved reopening while letting new
completions win; the isolated static browser passed, then a fresh full gate passed. A final one-line guard also invalidates delayed
saved opens for period-only navigation when no recommendation exists. The focused
regression passed and the third full TrailScout run passed on that exact final source.

The initial full GUI gate encountered legacy test guards requiring state directly
under `/tmp/huntmaps-check-*`, incompatible with the required scoped TMPDIR. The
replacement verifies the full disposable root/layout, matching workspace and real
paths without symlinks before fixture writes or worker signals. Original data,
rendering, cancellation and recovery assertions remain intact. The failed full run
and subsequent results stay distinct; no prefix bypass or owner-state execution.

Harness-only intermediate outcomes: the first draft-order probe sampled a transient
2.2 before the queued2.3 settled; the strengthened accepted assertion waits and checks
2.3. One focused rerun inherited an assess/zero-cap draft from recovery and failed the
unchanged recommendation IDs; explicit same-task setup fixed the test. One matched
rerun waited on the already visible prior region and produced invalid71ms timing;
that measurement is excluded. The corrected script waits for a new analysis ID.
The accepted matched result is6.995s. No application assertion was weakened.

## Launch and review boundary

See [usage](../../HUNTER_WORKFLOW_UX_USAGE.md). Build with `./trailscout build`, then
`./trailscout serve --state /tmp/huntmaps-ux-sol-review-stage2 --port 8795`; open
<http://127.0.0.1:8795>. Select Together/Flattop, opt into timed practical AM/PM if
desired, compare and inspect/save/export. Use fresh state for independent review.

No migration or data deletion is needed to revert. Preserve this reviewable diff
and new files, then use the retained pre-UX practical-plans branch in a clean
workspace and build. Do not reset/stash/discard this work. Stage 2 stops at its
handoff; the coordinator must verify and launch a separate fresh Sol High review.
