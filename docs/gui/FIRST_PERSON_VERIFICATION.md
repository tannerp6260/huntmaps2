# First-person pilot verification — September 30, 2026

Implemented and inspected the actual local application, using saved Soap Creek
A0075, V010, V008 and A0031 observer coordinates. Sources and GUI caches are separate
from protected results. This is a bounded terrain preview, not field validation.

## R0006 preparation memory correction — October 5, 2026

The owner's `scouting-2026-10-06` preparation failed allocating a 28.2 MiB
float64 array for 3,698,058 returns. The limit is **1536 MiB of address space**,
not resident RAM or downloaded-source size. The original implementation retained
decoded chunks while concatenating, copied the full local display population, and
interpolated ground for millions of returns at once. Vegetation preparation added
exact deduplication and another full-population interpolation to these live arrays.

An isolated cached-source replay of the original implementation succeeded at
1369.23 MiB peak virtual memory and 1016.85 MiB peak RSS. Thus the owner's failure
is sensitive to allocation headroom; it did not reproduce on every clean replay.
A controlled replay reserving another 250 MiB of virtual address space failed in
vegetation deduplication. The same reservation and unchanged production limit
allowed the corrected implementation to finish.

Preparation now spools cropped float64 returns to an automatically removed temporary
file before allocating their exact-size array, reads only the native DEM window,
and samples measured-return and vegetation ground eligibility in 100,000-return
batches. Display selection preserves the original global stride across batch
boundaries. No processing points, supported foliage cells, or terrain detail were
discarded. Existing point-count, triangulation, time, download, and cache limits
remain unchanged. Memory failures include the processing stage and full underlying
traceback in the preparation log; prior ready views and sources remain retained.

The corrected R0006 replay processed 3,902,433 cropped returns and finished in
66.29 seconds overall, at 1131.41 MiB peak virtual memory and 778.91 MiB peak RSS. All
**41 scene assets were byte-identical** to the reference; only preparation time
and memory metadata changed. No downloads were made. Temporary validation state
and logs are under `/tmp/huntmaps-memory-{eqc8g8mw,cwe8isw3,l8hu_bjd,ubz8tfrn}`.
The real GUI `Jobs` launcher and storage guard also completed a fresh cached-source
R0006 build in disposable state, with 756.05 MiB peak RSS and the same 41 validated
asset hashes (`/tmp/huntmaps-memory-f9eecm2n`). Owner state was not modified.

Six additional first-person regressions cover source-order/filter preservation and
temporary-file cleanup, DEM window equivalence including native boundary cells,
global display stride, exact vegetation duplicate/support rules across batches,
stage-specific memory diagnostics, and the production address-space limit. The
memory test reproduces failure of the old full-population interpolation with
3,698,058 returns under controlled headroom, then requires bounded interpolation
to retain every eligible return within the same limit.

Focused validation passed: 21 first-person Python tests, seven vegetation-screen
tests, and the disposable GUI harness with first-person, connected-foliage, and
nearby-observer browser checks. Formatting, frontend build, recovery, and owner/
protected-file preservation checks also passed. Harness evidence:
`/tmp/huntmaps-check-g3gve3vb`.

The complete `./gui/check` run passed with exit code 0: **150 Python tests**, Python
and frontend formatting, production build, browser recovery, and all **20 browser
checks**, including coverage-cache, redesign, working waypoints, and first-person/
foliage/nearby-view workflows. Full diagnostics: `/tmp/huntmaps-check-l4mq6kei`.
The final preservation review found no changes to 11,819 protected inventory
files, owner records, or any pre-existing frontend source/browser-check files.
The separate approach-review autosave/confirmation race remains outside this
memory correction. Very dense scenes remain subject to the existing preparation
caps; this change does not promise unlimited lidar capacity or field validation.

## Real data and processing

Five new USGS lidar tiles transferred **314,136,329 bytes** within the 500 MB pilot
cap; an existing checksum-verified 71,291,641-byte A0031 source was reused. Interrupted
transfer bytes were retained and accounted for. All four final scenes have observer
fine ground and approximately **99.8% supported fine-ground coverage** within 300 m.
Coverage is data support, not confidence in visibility through vegetation.

A full cached-source repeat produced byte-identical scene assets for all four
setups in approximately 114 seconds, with peak process RSS approximately 610 MiB
under the 1536 MiB address-space cap. Initial global triangulation exceeded that cap;
it was replaced with bounded local triangulation and checked for seam continuity.
Each scene remains below the one-million-triangle limit.

## Engineering checks

The complete Python suite passed **59 tests**, including 13 first-person tests for
flat terrain, rises, valleys, curvature, eye/target heights, independent mesh/profile
interpolation, missing data, support gaps, local seams, immutable asset validation,
source budgets and range resumes. Actual subprocess tests cover progress, failure,
cancellation, the single-job lock and restart interruption.

Headless installed Chrome inspected the real Three.js interface with all external
network requests blocked. It checked each pilot setup's saved position and camera
ground reference, eye height, heading, tilt, measured points, texture, fine and
baseline profiles, keyboard controls, close/reopen, a smaller viewport and renderer
context-loss handling. There were no page errors or outside requests; scene review
created no preparation jobs or annotations. The existing training and online-map
browser checks also passed.

A separate browser check exercises the real source-plan form, unchecked download
permission, fully cached sources and cached-only preparation, including the actual
worker's verified-bundle reuse log. Screenshots and machine-readable browser results
are under `/tmp/huntmaps-first-person`; processing repeat evidence is recorded in
`.gui/first-person/verification.json`.

The integrity inventory checked **7,105 protected files with zero changes** after
acquisition, preparation and tests. Existing engine calculations, CLI, source files,
saved candidate positions and historical outputs were preserved. Production frontend
build and whitespace checks passed.

## Practical limits

Fine ground is a 1 m interpolation of historical classified returns, not a promise
of survey accuracy or current near-ground conditions. Points are thinned for display.
There are no generated trees, opaque-canopy model, vegetation sightline conclusions,
photorealistic reconstruction or new ranking. A visible pale source-boundary gap is
explicitly explained in the interface. Coarse terrain supports distant context and
its own separate profile. Arbitrary-area preparation is outside this pilot.

## Automatic imagery upgrade — October 1, 2026

All four scenes were rebuilt from cached sources, without downloading data. Version 3
uses explicit coarse-to-fine valid-pixel mosaicking, a 1200 × 1200 local texture and
a separate 2048 × 2048 context texture. Both photographic squares have full cached
coverage for all four setups. Native aerial acquisition remains 0.6 m; local cached
exports have 0.5 m spacing. Larger textures do not create additional source detail.

Above-ground markers start enabled. Classified ground, returns within 0.5 m of fine
ground and returns over unknown ground are excluded. The display contains between
430,221 and 478,383 measured returns per setup, below the 500,000-point cap. Amber
unclassified returns are explicitly distinguished from vegetation-class returns.
Marker width is a display aid, not branch geometry.

Preparation completed in about 123 seconds; peak process RSS was approximately
981 MiB under the unchanged 1536 MiB address-space limit. All four fine/baseline
height grids and terrain mesh assets are byte-identical to the prior version.
The integrity check again found zero changes among 7,105 protected files.
The complete Python suite passed 61 tests, including new overlapping-image source
priority/alpha/NoData and above-ground eligibility tests. Production build passed.

The updated installed-Chrome browser check passed with outside network requests
blocked. It verified automatic imagery without a texture checkbox, measured returns
on by default, reset and setup switching, all four scene positions, profiles, keyboard
controls, smaller-screen layout, renderer failure and deliberately failed photograph
requests with shaded-terrain fallback. Screenshots were inspected; imagery now
covers distant slopes rather than leaving them uniformly shaded. No annotations or
jobs were created by scene review. Updated evidence and screenshots remain under
`/tmp/huntmaps-first-person`; bundle/resource evidence is in
`.gui/first-person/imagery-upgrade-verification.json`.
