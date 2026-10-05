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

## Verification

Before screenshots and the original end-to-end browser journey were captured before implementation. Verification uses disposable GUI state and synthetic calculation fixtures, plus the saved Soap Creek terrain and first-person sources. Owner records and protected analytical outputs are audited by `gui/check`.

The added `browser-redesign-check.mjs` checks 1920×1080, 1440×900 and 1366×768 layouts, viewport overflow, map width, initial ranking/selection, filter navigation, layers, expanded map, empty/confirmed collections, GPX export, area persistence, inspection return, polygon import, and recovery from a failed scene module. Existing journeys cover computation/recovery, guided approaches, coverage ordering/cache, training, first-person controls, vegetation, working waypoints, storage and offline behavior.

Commands:

```sh
./gui/check
# After a passing backend run, repeat the frontend/browser portion:
./gui/check --browser-only
```

Screenshot and test output directories are printed by the check runner. Synthetic screenshots demonstrate interaction and rendering only; they are not scouting recommendations.
