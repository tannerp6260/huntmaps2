# Workflow refinement — 2026-10-04

The three-stage workflow now explains the search before its settings, keeps reviews scoped to the selected run, preserves coverage while moving the map, and supports managing saved results.

## Behavior

- New runs include roads and trails and default to sampling within 0.5 mile of their mapped network. Detailed source overrides remain available. Proximity means straight-line distance, not a verified route or permission.
- Search thoroughness controls the evaluation budget; spots to recommend controls presentation. A configurable 150 m separation spreads the main recommendations; nearby evaluated alternatives remain grouped and all original scores remain available. Existing saved search settings remain unchanged.
- Parameter help covers nearby vegetation, search effort, separation, approach boundaries and preferences. Drawing has one initiating action. Checkbox hit areas follow their visible labels; proximity accepts decimal miles without spinner arrows.
- Generate setups, Acquire roads and trails, and Prepare views approve the displayed source plan. Metadata review never starts bulk acquisition. Changed plans still require review; transfer and storage safeguards remain enforced.
- Download estimates prefer actual provider transfers, then an interruptible startup probe of at most 2 MB or 5 seconds, then 20 Mbps. Processing time is separate.
- Coverage remains visible while additional tiles load. Sequential prefetch prioritizes nearby list entries, neighboring zoom levels and bounded previews for up to 200 likely points. The display cache defaults to 2 GiB; background work pauses for active jobs or low available memory/storage. External imagery is not speculatively downloaded.
- Saved results can be archived and restored. Permanent deletion requires a current inventory preview and an idle job service. Protected historical controls, shared inputs and prepared bundles are retained. No owner results were deleted during implementation.

## Correctness fixes

The nine findings in [the workflow audit](WORKFLOW_AUDIT_2026-10-03.md) are addressed: scene asset URLs carry immutable scene identity; movements use absolute coordinates; stale points no longer invalidate unaffected approaches in a batch; source retries retain cumulative accounting and verified response reuse; saved-location changes invalidate applied display filters; earlier filters do not hide later-stage points; annotation responses cannot cross runs; recovery opens the correct task and scenario; textures resolve against the run workspace.

Final confirmations are cleared on coordinate changes, including restore. Restoring old geometry can reuse compatible evidence but does not restore a final confirmation automatically. Scene identities now include recorded imagery checksums. Earlier scenes remain readable.

## Measured evidence

The isolated coverage fixture measured 5.497 s for the first view, 115 ms for a prefetched view and 73 ms to return to a viewed point, with zero additional coverage requests on return. JavaScript heap used 15.3 MB; allocated heap was 70.4 MB. These are local synthetic-fixture measurements using software graphics, not guarantees for large real scenes.

An independent pixel check counted 38,760 cyan pixels during a drag and 35,687 at 900 pixels wide. Explicit zero opacity reduced the count to 168. This verifies the rendered canvas rather than relying on a status label.

The large first-person fixture opened in 16.96 s, moved the observer in 360 ms, reused all 11 binary geometry requests, and produced zero idle draws. Its JavaScript heap used 23.2 MB with 82 MB of backing storage.

A separate 24-point shortlist polling benchmark took 76–105 ms per retrieval. That benchmark did not include prepared scenes or selected approaches for every point. Shared scenario validation is cached within each workflow retrieval.

Cold coverage calculation, uncached imagery, provider/network latency and terrain gaps remain observable limits. Existing data gaps are not filled with fabricated terrain. All exported approaches remain provisional; no itinerary or walking-time prediction was introduced.

## Verification

See the final check evidence recorded below. Tests use disposable workspaces and state. Historical analyses and prepared scenes were not regenerated.

Final `./gui/check` passed with 138 backend tests, 17 browser journeys, controlled worker failure/recovery and reload checks, Python formatting, frontend formatting and production build. Evidence: `/tmp/huntmaps-check-tn1u8o8d`. Desktop and 900-pixel screenshots were inspected. The final audit recorded 8,859 protected files with zero changes, including owner workflow/job records. The server's process high-water resident memory was 1,246.6 MiB after the full suite, including the large historical scene journeys; this is not the baseline-only footprint. The synthetic baseline worker measured 1.6 s and about 209 MiB peak RSS.

Additional focused evidence is retained under `/tmp/huntmaps-render-fixed`, `/tmp/huntmaps-performance-final`, `/tmp/huntmaps-clusters-fixed`, `/tmp/huntmaps-nearby-final`, and `/tmp/huntmaps-poll-benchmark-wydx84ii`. These artifacts are outside the repository and are not committed.
