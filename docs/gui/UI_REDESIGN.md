# HuntMaps2 scouting workspace redesign

The desktop workspace now follows **Find → Approach → Inspect → Save**. The map occupies the remaining screen beside a single 326 px scouting panel. Setup details, filters and stage tools share that panel; Expand map temporarily hides it without discarding work.

## Using the workspace

- **Find:** open a saved scouting area or choose **New area** to draw/import an observer boundary. Ranked setups show visible area, a relative coverage bar, nearby cover when recorded, and approach status. The first selected setup matches the leading recommendation or terrain-area ordering. Shortlist promising locations; Compare and Export remain available on each row.
- **Approach:** review each shortlisted setup using its explicit travel boundary and road/trail sources. Saved results bring distance, climbing and maximum slope forward. Boundary settings, preferences, vegetation and calculation details remain expandable. The original computation and review requirements are unchanged.
- **Inspect:** prepare/reuse terrain views, inspect the scene and select a target on the inset plan map. Heading, compass direction, observer identity and eye height remain visible. Source limitations and detailed diagnostics are expandable. The plan map also supports keyboard arrows and Enter.
- **Save:** review confirmed setups separately from the shortlist, inspect their evidence status, and export individual waypoints, provisional approaches, or the confirmed waypoint collection. Confirmation records a desktop review; it does not establish field visibility or safe/legal access.

The selected setup is identified in the list, on the map, and in a bottom contextual bar. The always-visible map key explains active analytical colors. **Map layers** groups base imagery, analytical overlays, and road/trail context. **Activity** contains job history, cancellation/recovery, logs, record backups and cache management. **Learn** and the saved-example lesson remain available.

## Implementation

`workspace-ui.tsx` provides shared icons, workflow navigation, selected-setup summary, collection, empty state and scene failure boundary. `workspace.css` defines the workspace tokens and presentation over retained specialist styles. Existing React state, API contracts, MapLibre sources/layer order, Three.js geometry, scoring and approach algorithms are retained.

Area changes clear transient inspection, search and filter state to avoid carrying another area's context into the new area. The last opened area survives reload. A failed lazy scene module is contained so the scouting workspace remains available. Confirmation buttons show pending and saved states, and prevent duplicate confirmation.

Opening an area in Find selects its leading recommendation, or its largest terrain-visible area when no recommendations exist. The saved approach review's `active_point` is separate: entering Approach restores that review focus. Opening Find does not overwrite it.

## Verification

Before screenshots and the original end-to-end browser journey were captured before implementation. Verification uses disposable GUI state and synthetic calculation fixtures, plus the saved Soap Creek terrain and first-person sources. Owner records and protected analytical outputs are audited by `gui/check`.

The added `browser-redesign-check.mjs` checks 1920×1080, 1440×900 and 1366×768 layouts, viewport overflow, map width, initial ranking/selection, filter navigation, layers, expanded map, empty/confirmed collections, GPX export, area persistence, inspection return, polygon import, and recovery from a failed scene module. Existing journeys cover computation/recovery, guided approaches, coverage ordering/cache, training, first-person controls, vegetation, working waypoints, storage and offline behavior.

Commands:

```sh
./gui/check
# After a passing backend run, repeat the frontend/browser portion:
./gui/check --browser-only
# Focused coverage-cache journey, with the workflow that prepares its review state:
./gui/check --browser-only --browser-check browser-workflow-check --browser-check browser-coverage-cache-check
# Focused comparison/3D controls and training journey:
./gui/check --browser-only --browser-check browser-training-check
```

Screenshot and test output directories are printed by the check runner. Synthetic screenshots demonstrate interaction and rendering only; they are not scouting recommendations.

The coverage-cache run-change check asserts the new area's leading selection, its actual coverage requests, old-source removal in both directions, and restoration of saved approach focus. Its former hardcoded Find expectation of A0001 was invalid after ranked initial selection: the workflow fixture's coverage leader is A0013. Reproduction showed visible `Coverage ready · A0013`, a retained A0013 source belonging only to `workflow-fixture`, and zero browser errors while the unchanged 60-second A0001 wait failed. The corrected check retains that timeout and all HTTP-cache, prefetch and bounded-retention assertions.

Full-suite validation also exposed the comparison panel intercepting the 3D terrain rotation button. Terrain controls now sit above the comparison panel while it is open. The training check asserts separate panel bounds and real rotation clicks at 1500 and 900 px; no forced clicks or longer timeouts are used.

Editing a polygon could also fit its upper-right corner underneath the collapsed Map layers panel, preventing a drag. The edit fit now leaves clearance above and below the handles for map controls. The training check waits for map idle and checks the corner's canvas hit target before performing the drag and asserting changed saved geometry.

The scouting journey now waits for calculation readiness and reopens approach settings before editing preferences, matching the existing collapsed-result presentation. Export invalidation, filter, import and reviewed-download assertions remain intact.

The nearby-observer journey opens Setup details for manual waypoint review and returns to All setups for mixed exports. Its coordinate, ray agreement, persistence and deletion checks are unchanged; the earlier test attempted to edit a hidden details panel.

Nearby movement timing prepares the visible button before starting the timer so scrolling into the controls is setup work. The two-second click-to-pose limit, no-asset-reload assertion and all movement/ray checks remain enforced; click and total movement times are logged separately.

Final validation on 2026-10-05: targeted coverage-cache, training, scouting and nearby-observer journeys passed through the disposable harness. The complete `./gui/check` then exited 0: 144 Python tests, formatting/build, recovery and all 20 browser checks passed. Diagnostics: `/tmp/huntmaps-check-5kee5xkl`. The preservation audit checked 11,494 files and reported no changes. The final working-tree review confirmed the original redesign remains intact, with application edits limited to comparison-control spacing and polygon edit padding. Verification is automated desktop/fixture evidence, not field or live-provider validation.
