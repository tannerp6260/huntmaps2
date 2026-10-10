# Coverage batches and independent approach setup — 2026-10-10

This change improves normal review of existing results. It does not change candidate
sampling, terrain visibility, target masks, scoring, terrain resolution, approach
costs/objectives, departure limits or historical outputs. Prior uncommitted source
reuse and performance work remains intact.

## Behavior

Find offers explicit preparation of 5, 10 or 20 setups, default 10, including the
current eligible setup and following the displayed ranking. Each setup gets detailed
tiles around its own normal selection view and bounded overview tiles. Work is
sequential, pauses during jobs/movement/3D views, supports cancellation/resume and
retains completed immutable URLs during retry. The normal tile service still checks
sources, resource limits, locking and the display-cache budget. Preparation does not
add GPU sources; normal retention remains capped at eight. Other zooms, expanded
viewports and cache eviction can require more loading. Only selected shading is
rendered; comparison remains a separate feature.

The map's prominent loading card explains missing shading during opening/switching.
Fast cached transitions avoid a flash through a 150 ms presentation delay. Ready is
published after a render event following opacity reveal, with current source-load
checks and disposal guards. Panning uses the compact indicator. Errors offer retry.

Plan approach now presents the boundary/check/calculate/select sequence for a
single shortlisted setup. New drafts start without another setup's boundary;
calculation starts only on an explicit click. Imports and explicit boundary copying
remain advanced options requiring destination-specific confirmation. Primary drawing
cannot bypass unfinished geometry through the imported-boundary confirmation button.
Existing draft/scenario versions, selected approaches and saved evidence stay readable.
Visible-terrain/observer filters stay in Find. Preferences explain ascent, steepness,
tree/shrub penalties and the separate hard slope limit; defaults remain unchanged.

## Interface and validation

`POST /api/runs/{run}/approach-preflight` is read-only. It checks the current
shortlist/waypoint snapshot, usable polygon after exclusions, bounding-grid guard,
selected network geometry and exact existing departure sampling (including the
one-mile limit and pinned/network-start constraints). It returns ready status,
per-setup reasons/departure counts and grid size. It prepares no terrain arrays,
creates no scenario and starts no job. Terrain constraints remain a calculation
check, not a preflight promise of a path.

The current UI adds `preflight_required: true` to existing approach submissions.
The server rechecks readiness under the maintenance lock before creating a scenario
or starting work. Legacy API submissions and historical no-path evidence retain
their existing behavior. No analytical implementation fingerprint changes are needed:
the solver and its results are unchanged.

## Verification

The initial regression reproduced the absent early check (404 for preflight).
Focused backend checks now reject invalid boundaries before creating jobs/scenarios;
cover exclusions, missing/far departures, off-network starts and grid limits; and
compare complete path alternatives and costs exactly with identical legacy inputs.

Browser checks use disposable state/workspaces and block external sources. They cover
loading/error/retry, actual cyan pixels above opaque imagery, exact ranked batches,
bounded requests, pause/cancel/resume, failed-tile retry, HTTP reuse, source retention,
ranking invalidation, keyboard activation and reduced-motion settings. Guided review
covers explicit calculation, independent next-setup boundaries, copy/confirmation,
primary drawing, preferences, reload, dismissal/Undo and the inspection gate.
Screenshots are checked at 1500 and 900 pixels.
Batch preparation also runs at the supplied 1902×862 window size. Geometry checks
cover rotated 4K viewports and asymmetric camera padding without adding GPU sources.

The final complete `./gui/check` passed: 192 backend tests, 21 mandatory browser
journeys, the actual 600-location recovery journey, formatting and production build.
Diagnostics are retained at `/tmp/huntmaps-check-4b0a0_7v`. Its preservation audit
recorded 8,055 historical files with `changed: []`, including separate checks of
saved owner records and a concurrent application instance. No expected hashes were
changed. `git diff --check` also passed.

The first focused runner was interrupted during its last journey, after five
journeys passed; it is not counted as a complete suite. Test-helper import and
transpilation setup errors were corrected before final verification. A full run
timed out in the drawing lesson; its isolated replay passed all assertions. A
delayed practice-camera callback was then guarded during drawing. The new camera
regression initially assumed a fixed initial zoom; diagnostics showed a broader
initial view, and the assertion now checks the actual relative zoom change.
The test also waits for the new-area map snapshot before measuring that change,
because the preceding saved-review idle snapshot can otherwise be stale.
A later convenience runner reusing disposable state was also interrupted; it is
not counted as a complete suite. Final acceptance used fresh isolated state.

## Measurements and limits

Measurements use the existing 24-evaluation synthetic search fixture,
1500×1050 software-WebGL browser, the same saved filters and normal selection zoom.
These are individual observations, not whole-app speedup claims:

| Operation | Prior UI | Updated UI |
| --- | ---: | ---: |
| Initial coverage readiness | 5.510 s | 4.608 s |
| Switch to prepared second setup | 0.119 s | 0.105 s |
| Return to retained first setup | 0.138 s | 0.178 s |
| New requests when returning | 0 | 0 |

The final implementation prepared the five displayed recommendations in 12.494 s
(215 background requests), with 206 HTTP coverage cache hits across the journey.
Browser heap used at the final checkpoint was 19.2 MiB; retained source count was
two, and switching through ten setups stayed within the existing eight-source cap.
The server's peak resident memory across the entire acceptance suite was 1,059.2
MiB; this includes other workflows and is not an isolated coverage-batch peak.
The old queue prepared fewer detailed views, so its preparation time is not comparable.
An early square-viewport prototype took 26.554 s and 467 requests; the final rotated
viewport rectangle avoids that unnecessary work.

The separate 10-setup cancellation/retry journey intentionally delays each request
by 35 ms and injects a failure. It checks one outstanding background request and all
ten ranked setup IDs. Its timing is not an estimate for the owner's selected area or
network: the final 10-setup resumed batch took 36.405 s under that controlled delay.
The final journey also prepares five setups at 1902×862 (249 tiles) before checking
the 900 px layout and keyboard/ranking invalidation.

The benefit is predictable preparation and fast subsequent review, rather than a
change to terrain calculations. Tile preparation still consumes CPU/storage; normal
view changes need imagery independently. Large bounding rectangles and terrain
constraints still affect approach calculation. No additional downloads or hardware
upgrades are required for these controls.
