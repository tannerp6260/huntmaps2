# Suggested approaches, GMU trails and detailed download recovery

Normal Approach review uses the terrain-supported local search boundary and the
existing slope, distance, climbing and cover preferences. It calculates only the
existing Recommended objective, selects a successful result, and advances through
the shortlist. Continue to inspect becomes available when the retained setups have
current approaches. Existing selected paths are reused on reload. A failed check
does not select a path or relax the slope limit.

**Explore alternatives or edit approach** opens the established boundary,
exclusion, source, departure and preference controls. Calculating alternatives is
explicit and retains the prior scenarios; choosing an alternative remains explicit.
Saved explicit alternative-mode drafts keep their earlier workflow. Older mode-less
drafts adopt suggestions while retaining geometry and preferences. **Use suggested
approach mode** returns from the override without discarding a selected path.
The single-path objective and hard constraints are unchanged; no itinerary or new
scoring model is introduced.
Paths remain provisional mapped/terrain evidence, not permission or safe passage.

GMU context lines now render above relief, satellite, saved imagery and coverage
rasters. Roads use solid cream lines and trails use dashed mint lines with dark
outlines. The entire retained unit context remains available while drawing and
through Find, Approach, Inspect and Save. This is all trails in the retained USFS
inventory, not an assertion of exhaustive coverage across agencies or current
closures. No pack, source snapshot or historical output is regenerated.

Detailed lidar transfers use at most three simultaneous requests. Transient
connection/read failures retry at most three times per piece, resuming saved
bytes. Content-Range includes the exact expected total; provider ETag/date are
retained and checked across ranges/retries. Changed sources, invalid ranges,
ordinary HTTP errors and exhausted transfer/storage limits fail without retries.
Successful partials and cumulative transfer accounting survive failure. The
existing 900-second stage, memory, source review and storage limits remain.

The supplied A0087 failure was a USGS connection timeout. The Matplotlib Axes3D
warning is unrelated to the browser renderer. The existing approved source plan
`e808fc23dc5c43b58239829a0547958d` completed for run `2`, A0087, with job
`f5357813a0d048798e970c8681f5315b` and published scene
`102d94f3166e0a05531e7093aa4c3dd3`. All three reviewed LAZ sources were validated.
Provider acquisition remained slow: the retry took about 31 minutes overall;
the scene itself took 25.6 seconds to build. The finished sources and scene are
cached, so reopening this view needs no repeat acquisition.

The scene has 1 m fine ground, 99.85% coverage of the fine patch and a supported
observer position. Actual browser rendering loaded 2,418,297 triangles including
37,304 inferred vegetation cells, with no failed assets or page errors. Desktop and
900 px captures and the browser record are at
`/tmp/huntmaps-a0087-render-e_kjcga8/screenshots/`. Verification used an isolated
workflow state while reading the real published scene, preserving owner decisions.
The fine imagery export encountered HTTP 502; the retained context imagery supplied
both textures. The existing deliberately unjoined fine/coarse source boundary is
still visible as a pale band; no terrain blending or vertical correction was added.

Focused validation passed: single-search equality with the existing recommendation;
connection timeout, partial read, source identity and transfer-budget regressions;
default browser selection, reload and explicit override; and visible mint trail
pixels above opaque imagery.

Final verification (closed out 2026-10-21): all 306 backend tests, formatting and
the production build passed. All 33 mandatory browser journeys passed across the
full run and focused reruns. The full run's remaining 30 journeys completed while
the session was interrupted. Its three initial failures were a test reloading
before the preference save, a legacy test looking for controls before opening
the new override, and a startup test overlapping an asset rebuild. The first two
tests were corrected and passed through the standard isolated runner; the startup
test passed unchanged against stable assets. No application changes followed the
tested build.

Evidence: `/tmp/huntmaps-check-xmmu2q5s/` contains the full run and its original
failures; `/tmp/huntmaps-check-swic7chm/` contains the corrected suggestion and
connection checks; `/tmp/huntmaps-suggested-ui-zld8zpfb/` contains the startup rerun.
Both standard-run preservation audits report zero changed files across the 8,673
protected workspace files and the separately hashed owner/companion records.
Existing selected approaches, historical reports and frozen controls remain intact.
