# First-person pilot verification — September 30, 2026

Implemented and inspected the actual local application, using saved Soap Creek
A0075, V010, V008 and A0031 observer coordinates. Sources and GUI caches are separate
from protected results. This is a bounded terrain preview, not field validation.

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
