# Revised training, drawing and terrain verification — 2026-09-30

The production React/TypeScript build passes. Browser automation uses installed
Google Chrome with an isolated browser profile and the actual localhost GUI.
The saved Soap Creek A0075, V010 and V008 results remain the comparison example.

Verified through the browser:

- Numbered recommended learning path; five review steps, without the old opening
  run-selection step or final quiz; independent completion of both lessons.
- Directions, gold highlighting and panel scrolling for observer cards, view
  toggles, right-hand review fields and left-hand export buttons.
- Pause, reload and resume using stable step identifiers.
- Saved practice review and GPX/KML exports with exact candidate coordinates,
  escaped XML notes, and PRACTICE filename/waypoint labels.
- Drawing through actual pointer events, closing and validating a polygon,
  undoing a corner, moving a vertex, saving the changed geometry and cancelling
  edits with Escape, and clearing the saved draft. Practice geometry persists across reloads but is absent from real intake.
- Hover help for supported run settings, and retained KML import behavior.
- Real 3D elevation loaded from the local DEM, tilt and rotation, visibility
  toggling and candidate selection, 2D/reset controls and offline 3D. Simulated
  elevation-request failure returns to 2D and releases the failed terrain source.
- External-network blocking: no external requests, JavaScript errors or failed
  HTTP responses in the main walkthrough; no training analysis jobs or real
  annotation writes. Only practice-area and normal import POSTs were made.
- v1 browser-state migration preserves practice notes and completed lessons.
- Missing example data pauses a restored lesson safely while leaving the guide
  and normal new-run controls usable.
- Screenshots inspected at 1500 × 1050 and a smaller 1000 × 850 desktop window.

All 46 Python unittest tests passed; all 7,105 files in the protected-output hash
inventory match unchanged. The existing browser viewer regression also passed.

Backend checks verify DEM encoding against saved source-cell elevations,
continuous synthetic-plane values and tile seams, edge padding without zero-height
cliffs, NoData rejection, exact drawn coordinates, invalid polygons and refusal to
prepare a real plan from a practice-area import. Existing tests additionally cover
saved masks, area, georeferencing, exports, job failure/cancellation and restart.

Reproduce with the launch command and browser scripts in [TRAINING.md](TRAINING.md).
Screenshots/results live under `/tmp/huntmaps-training-v2`; they are GUI verification
artifacts, separate from supplied reports and original GIS runs.

Limits: this is engineering verification, not a hunter usability study. 3D needs
valid local elevation coverage and suitable browser graphics support. Cached
imagery coverage is limited and its acquisition dates remain relevant. No elevation
or imagery is downloaded automatically; no tree geometry or new hunting model is
introduced. A new area may be easier to import when no local visual context exists.

## Settings explanations and online context — 2026-09-30

Built the production frontend and passed all 46 backend tests. Existing viewer
and revised-training Chrome checks pass with online imagery explicitly disabled,
preserving their offline and zero-external-request assertions.

The new `npm run test:online` Chrome check verifies default-enabled real USGS
imagery tiles, additional requests after location navigation and zooming, provider
attribution, drawing outside Soap Creek, expandable sampling/advanced settings,
keyboard/click help, remembered online-off preference, network failure without a
generic analysis error, retry recovery, and online imagery with local 3D.
The final live run received 194 successful tile responses across 205 distinct
requested URLs (including deliberately blocked requests). Browser JavaScript
errors: zero. Intercepted acquisition preparation verifies unchanged defaults
(radius 2000 m, minutes 30, count 150, cap 600 MB), without starting a real job.
Real annotations and job counts remained unchanged.

Screenshots inspected: `/tmp/huntmaps-online/01-filled-gaps.png`,
`03-small-settings.png`, and `04-offline-fallback.png`; additional screenshots
cover settings and local 3D. Adjusted footer/terrain controls to leave attribution
readable, and made layers scroll within smaller maps. Results are recorded in
`/tmp/huntmaps-online/results.json`. All 7,105 protected hashes match the existing
preservation inventory. Engine calculations, coordinates and historical products
were not changed.

Online imagery is browsing context with varying acquisition dates; it is not a
live photograph or an analysis input. Close zoom overzooms the provider's useful
level-16 tiles. Local 3D remains bounded to saved elevation coverage. Online tiles
have ordinary browser caching but no promised offline tile pack.
