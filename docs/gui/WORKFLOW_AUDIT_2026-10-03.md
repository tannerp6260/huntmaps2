# Three-stage workflow code audit — 2026-10-03

Reviewed implementation: `248a829`. This is a review, not a bug-fix release.

**Nine additional defects were confirmed**, including four high-priority defects affecting scene identity, waypoint calculations, independent approaches, and transfer accounting. Passing the existing suite does not establish correctness for these transitions. Findings below distinguish real browser/service reproductions from focused tests with mocked boundaries.

## Findings, ordered by priority

| ID | Priority | Trigger and observed consequence | Code |
| --- | --- | --- | --- |
| W01 | P1 | Replace a prepared scene for the same run/setup. New metadata can accompany old browser-cached geometry and imagery for up to an hour. | `huntmaps_gui/api_routes.py:169`, `gui/frontend/src/scene-viewer.tsx:168`, `gui/frontend/src/position-map.tsx:103` |
| W02 | P1 | Move a setup again after preparing a scene at its revised coordinates. Saved coordinates and the coverage calculation use different origins. Moving an exact manual scene also raises `KeyError`. | `huntmaps_gui/working_waypoints.py:58`, `:152`, `:167`, `:337`; `huntmaps_gui/first_person.py:374` |
| W03 | P1 | Compute approaches for A and B together, select A, then dismiss/remove/move B. A's otherwise unchanged approach becomes stale and unavailable too. | `huntmaps_gui/approach_service.py:181`, `huntmaps_gui/workflow.py:50` |
| W04 | P1 | Retry standalone network acquisition after an interrupted transfer. Each attempt gets a fresh allowance; prior transferred bytes are not deducted. Linked analysis plans also reserve estimates rather than accounting for actual prior transfers. | `huntmaps_gui/scouting_api.py:73`, `:84`, `huntmaps_gui/scouting_network.py:195`, `:217`, `huntmaps_gui/scouting_worker.py:36` |
| W05 | P2 | Apply review filters, then update a waypoint. The UI retains old qualification, matching area and ordering while the backend and coverage tiles use the new point. | `gui/frontend/src/scouting-tools.tsx:215`, `:247`, `:437`, `gui/frontend/src/main.tsx:983` |
| W06 | P2 | Shortlist points outside the active recommendation/group/search/filter selection, then advance to stages 2/3. Those stage lists still intersect the stage-1 restrictions and can appear empty. | `gui/frontend/src/main.tsx:983`, `:1332`, `:1343` |
| W07 | P2 | Save a review and switch runs before the reply arrives. The old run's response updates the new run's annotations and saved-status display. | `gui/frontend/src/main.tsx:820`, `:832` |
| W08 | P2 | Click the history recovery button for an approach or network-acquisition job. The shared handler requests a baseline plan and returns “Unknown plan.” | `gui/frontend/src/job-monitor.tsx:36`, `gui/frontend/src/main.tsx:942` |
| W09 | P2 | Prepare a scene whose saved imagery has a relative path in a configured workspace different from the source directory. The texture adapter resolves it against the source project and fails. | `huntmaps_gui/first_person_worker.py:612`, `:619`; compare `huntmaps_gui/catalog.py:109` |

### W01 — Scene assets have mutable URLs with immutable caching

The scene endpoint follows a ready pointer. Asset URLs contain run/setup/name, but no bundle key. Both binary fetches and image loaders use these URLs. The API advertises `private, max-age=3600`. Changing `meta.key` rebuilds the viewer but does not change its asset request identities.

An actual Chrome journey without request interception fetched `context-vertices.bin`, switched the disposable ready pointer to a second valid bundle with changed vertices and updated hashes, and fetched again. The server returned the new bytes while Chrome returned the first bundle's bytes:

- First/browser-repeat SHA-256: `6cb11d5cb9efe4df03a25438aca87dbba9453921a64fbd588fdb380532ee943b`.
- Current server SHA-256: `031bb4747b863a326d2b912961b7771167f14760aac1eabb4e08d84d3ff64263`.
- Current metadata key: `eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee`.

This can undermine the scene-viewing gate: the frontend records the metadata key after loading assets, without proving that the rendered assets belong to it. That gate consequence is established by tracing the viewer/decision code; the reproduction specifically proves the cache mismatch, not a full confirmation after live lidar replacement.

Fix asset identity end to end. Serve assets by immutable bundle key, or validate an explicitly requested scene key and use it in every binary/image URL. A query parameter alone is insufficient if the backend still silently follows the newest pointer. Reject stale requests or serve the exact retained bundle. Add a no-interception browser test that prepares/replaces a scene and verifies asset hashes and rendered geometry before recording viewing.

### W02 — Revised scene origins are not carried into waypoint calculations

`first_person.observer()` measures offsets from the exact prepared scene's current origin. `working_waypoints.signature()` instead looks up `Run.points[anchor]`, the original immutable location, and adds those offsets. The calculation worker repeats this assumption. Thus an original point moved 3 m east, then moved another 3 m east from its exact revised scene, can save a waypoint 6 m east with a mask calculated 3 m east.

A focused service-boundary reproduction supplied that exact-scene pose and called the actual `working_waypoints.start()` against a real generated 3 m mask. It returned `status=complete, cached=True` with waypoint easting `450130.9999999997`, but mask provenance easting `450128.0`: a **3 m mismatch**. This is a reuse/correctness defect, not simply a stale label. The fine-ground pose and scene lookup were mocked; the signature, cache validation and returned working record were real.

For an existing manual record, the same exact-scene branch sets `anchor` to its manual ID. The subsequent immutable `Run` has no such point, producing `KeyError: 'manual-audit'` before a job can start. The reproduction exercised `start()` with a real manual record and mocked fine-ground pose.

Resolve calculation coordinates from the validated absolute pose, retain the original anchor separately for provenance and movement bounds, and record the scene/revision used to derive the pose. Validate the worker against that exact task instead of reinterpreting offsets relative to whatever scene pointer is current. Test two successive moves with scene preparation between them, exact manual-scene movement, restore, and absolute coordinate/mask/export agreement. Also test that repeated scene recentering cannot silently expand the original 30 ft movement domain.

### W03 — One point invalidates every independent result in its batch

`approach_service.status()` combines all point mismatches into one scenario-wide `stale` flag. `workflow.selection()` rejects any selection from a stale scenario. Shared network/terrain changes should invalidate the batch, but a changed or dismissed destination should invalidate its own independent result.

The reproduction used a real two-point scenario, local synthetic network and actual approach solver. Both points had one alternative. A's approach was selected; dismissing B changed A's resolved selection from present to absent. The only stale reason was `Waypoint changed/restored or no longer kept: A0002`. This also blocks A's confirmation/export even though A and its sources did not change.

Track shared-source freshness separately from per-point freshness. Enforce the chosen point's revision in selection/export. Preserve the evidence and all unaffected selections. Add multi-point tests covering dismissal, removal, movement, deletion, no-path results, and shared-source changes.

### W04 — Standalone network retries escape the reviewed transfer ceiling

The integrated baseline worker installs `HUNTMAPS_TRANSFER_LEDGER`; standalone network jobs launched by `scouting_api.network_start()` do not. `scouting_network.acquire()` starts `used=0` on every invocation. Responses are retained for publication only after both providers complete, so a failed second response causes the first response to be downloaded again on retry.

With controlled in-memory provider responses, two failed attempts each transferred an 8 MB roads response; a third attempt transferred 8 MB roads and 8 MB trails and completed. **32 MB were read under the same 20 MB allowance.** No external download occurred. Existing storage guards remain; this finding concerns consent/accounting, not a demonstrated disk-exhaustion failure.

Use a durable ledger for the network plan, deduct prior reads before each retry, and charge linked analysis/network work to the same reviewed ledger. Retain verified response files for reuse where feasible. Test failure after the first source, mid-response interruption, retry/restart, cached-only completion and renewed allowance approval. The same tests should audit first-person per-plan retry accounting, which currently relies on a global source ledger plus a fresh `spent + allowance` limit.

### W05 — Applied filters do not refresh when the point changes

The `stamp` effect refreshes kept points and approaches, but not `applied` filter results. Main-list qualification/order uses the old returned rows. Tile requests already carry the current waypoint revision and calculate the current filtered mask.

In a real browser/API journey, a 61 m network-distance filter accepted A0001 at 60 m. A generated and validated 3 m working revision moved it to 63 m. The current filter API returned `qualifies=false`, but the UI still listed it as qualifying and displayed **0.664 km² matching** against **0.663 km² current total coverage**. The corrected reproduction had zero page errors. Publication of the generated revision was simulated by writing disposable working state, rather than running the fine-ground movement UI.

Refresh applied result rows on waypoint/source freshness changes or invalidate them visibly until reapplied. Associate responses with point revisions and suppress older replies. Test filter → move → restore, including access qualification, matching-area bounds, ordering and tile agreement. An earlier incomplete test fixture lacked required cover metrics and crashed; that harness error is not counted as a product finding.

### W06 — Stage-1 list restrictions leak into the later stages

The list predicate first restricts to shortlisted/approached points, then also applies recommendation membership, neighborhood, search text and review-filter qualification. Stage navigation does not choose an appropriate later-stage list scope.

A browser journey with two nonrecommended shortlisted points entered stage 2 with `group=recommended`. The stage count said two shortlisted while the setup-card list was empty. The right-side computation checklist still listed the points; computation itself remained possible. Stage 3 has the same predicate structure.

Give each stage its own list scope or make inherited restrictions explicit and easily clearable. Show all shortlisted/currently approached points by default in their stages while preserving the stage-1 search/group/filter state for returning. Test nonrecommended points, dismissed/group/search selections, applied filters and manual points at both desktop and 900 px.

### W07 — Late review saves cross run boundaries in the frontend

Other mutations use `currentRunRef`; the legacy annotation `save()` does not. After awaiting the PUT, it merges the captured candidate ID/status/notes into whichever run is now displayed.

A browser journey held a real PUT response for search-fixture/A0001, switched to workflow-fixture, then released the reply. Workflow-fixture's A0001 card displayed `keep`, while its actual annotation API returned `{}`. The response did not directly write the second run's backend data. It nevertheless presents another run's decision/notes as current and can carry them into a subsequent review save after reselection.

Capture run/candidate identity and a mutation ticket, and guard success, error and saved-status updates. Add delayed success/failure tests for both candidate switches and run switches. Verify the frontend and durable records together.

### W08 — Recovery is dispatched as if every job were a baseline job

JobMonitor gives approach and network-acquisition jobs the generic resume button. `jobAction()` unconditionally calls `/plans/{job.plan}` for it. Those jobs have scenario/network-plan IDs, not baseline-plan IDs.

A real browser journey with a synthetic failed approach job clicked “Review / resume plan” and received **Unknown plan**. The same mismatch is present for network jobs by code trace; it was not separately clicked in a browser.

Dispatch by job kind. Reopen the correct run/scenario or network source review, retain original definitions and explicitly launch the appropriate retry/recomputation after any required review. Test every visible history action for every job kind and terminal status, including interrupted/cancelled jobs.

### W09 — Scene imagery ignores the configured run source root

Catalog resolves and validates imagery using the selected run's source root. The texture worker instead joins relative paths to global `ROOT`. This fails for a completed run in a separate `HUNTMAPS_WORKSPACE` with workspace-relative imagery.

A focused adapter reproduction supplied a workspace-relative image descriptor and observed resolution to `/home/tanner/Desktop/huntmaps2/audit-only.png` rather than `/tmp/huntmaps-check-_s12utew/workspace/audit-only.png`. The failure occurred before mosaic generation; no full photo-textured scene was generated for this case.

Use the run's path resolver for all scene sources. Test absolute and relative imagery paths in a separate workspace, including multiple runs with duplicate filenames. Verify the resulting texture/source hashes, not only successful scene metadata.

## Additional behavior and test gaps

- **Confirmation restoration policy:** a service test confirmed `confirmed=true → false while moved → true after restoring the original`, without a new confirmation action. Working-location changes do not permanently invalidate the stored workflow decision; matching the old identity resurrects it. Restoring original evidence can be intentional, so this is documented separately from the nine defects. Decide explicitly whether restore may reinstate confirmation or must require reselection/reconfirmation; encode that policy in tests.
- **Many-point performance:** workflow retrieval resolves each selected approach separately, even when selections share a scenario, and each viewed scene rehashes the baseline through `digest()`. Existing one/few-point fixtures do not bound repeated polling work for a large confirmed collection. Measure a 20–50 point collection before claiming responsive batch review.
- **Record/payload hardening:** workflow nested records and approach/network bodies have uneven schema validation. Add malformed nested records, missing fields and invalid types, checking actionable recovery rather than uncaught `KeyError`/`TypeError` or a blank frontend. The incomplete filter fixture demonstrated the frontend's lack of an error boundary, but is not evidence that a normal generated working record lacks these metrics.
- **Scene identity completeness:** signatures include baseline/lidar/waypoint inputs but omit imagery inputs. Immutable run validation reduces exposure, but explicit source-key tests are needed for scenes acquiring/replacing recorded imagery in future.
- **Actual lidar acquisition variants:** the reviewed code checks overlapping acquisitions, vertical units/references, fine-ground gaps and source checksums. Tests still need a complete two-revision scene journey with synthetic LAS fixtures and browser cache enabled. Live provider availability, live transfer speed and field visibility are outside this audit's verification.

Two initial suspicions were not counted: scene publication already writes to a unique partial directory and replaces the final bundle only after metadata/assets are written; explicit selection of an older retained scenario can be legitimate when restoring its recorded inputs.

## Review coverage and validation

The review traced the stage transitions and their supporting code across these areas:

| Area | Components reviewed | Principal checks |
| --- | --- | --- |
| Stage 1 intake/search | drawing, main intake/recovery, settings, sampling, request models, API preparation/start, owner/search workers | Boundary confirmation, option identity, review signatures, checkpoints, fixed settings, sampling/target separation |
| Review/display | catalog, candidate/manual/working panels, map layers/order, raster/display caches, coverage preparation, terrain controls | Coverage identity, mask alignment, opacity/layer order, revisions, cache retention, qualification/sorting, run switches |
| Stage 2 | scouting tools/API/network/filter adapters, approach service/search | Explicit travel area, exact destination, no-path evidence, weights/slope/exclusions, independent results, selection, exports |
| Stage 3 | workflow panel/records, first-person API/worker, viewer/position/profile adapters | Exact point/scene identity, cached assets, viewing/confirmation gates, early inspection, manual/revised positions, source coverage |
| Cross-stage support | polling, jobs/progress/recovery, downloads/guarded workers, storage/maintenance/export adapters | Single-job/cancellation guards, partial accounting, response ordering, preservation, recovery dispatch, referenced assets |

The unchanged implementation's last full required check passed **128 backend tests and 17 isolated browser journeys** (`/tmp/huntmaps-check-_s12utew`). It was not rerun merely to repeat those results: this review changed no application code and instead ran new targeted reproductions for the uncovered transitions.

New evidence is retained in `/tmp/huntmaps-workflow-review`:

- `backend-results.json`: actual two-point approach invalidation, coordinate-signature/path checks; explicit older-scenario reselection is not counted as a defect.
- `movement-results.json`: actual working-start/cache path with mocked exact-scene pose; wrong-mask reuse and manual `KeyError`.
- `browser-results.json`: real Chrome asset caching and later-stage empty list.
- `race-results.json`: delayed note reply/run switch and failed approach recovery.
- `filter-results.json`, `filter-stale.png`: real API/renderer against a generated working mask; stale filter rows and zero page errors.
- `network-results.json`: actual acquisition/accounting code with controlled in-memory responses and two failures.
- `restore-results.json`: the documented confirmation-restoration behavior.
- Reproduction scripts and desktop screenshots are retained alongside these results. They use disposable state/workspaces and never the owner's server.

The read-only preservation check verified **7,229 locked baseline files with zero checksum changes**. The application implementation and owner records were not changed; historical analyses/scenes were not regenerated. No Windows device or `/media/tanner` path was accessed. Temporary review-server state and generated masks/scenes are isolated under `/tmp`.

## Fix and regression order

1. Fix W01/W02 first: exact scene assets and absolute waypoint calculation coordinates. Require asset-hash, geometry, mask and exported-coordinate agreement.
2. Fix W03/W04: per-point approach freshness and durable shared transfer accounting. Require multi-point removal/movement and actual interrupted-response retries.
3. Fix W05–W09: revision-aware filters, stage-scoped lists, response guards, recovery dispatch and workspace paths.
4. Resolve restoration policy and add large-collection polling measurements and record-hardening regressions.
5. Run the focused failing-before/passing-after cases, the complete `./gui/check`, a multi-point 1 → 2 → 3 journey with scene replacement/recovery, desktop/900 px visual inspection, and protected/owner-state audits before release.

Keep cache-preservation tests unintercepted. Use controlled local providers for deterministic transfer errors. Every test must assert the displayed/durable outcome and its point/scene/source identity, not only a ready label or HTTP 200.
