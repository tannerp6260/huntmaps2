# Complementary glassing views — 2026-10-10

Find now offers an optional **Complementary views** mode. Choose a collection of
three, four or five positions, default five, including the existing shortlist.
Recommendations add unique matching terrain rather than repeatedly recommending
the largest overlapping individual views. Individual rankings, original scores and
the three-position comparison tool remain available unchanged.

## Behavior and evidence

The initial union contains every retained position with verified coverage at its
current working coordinates. Retained/manual positions are never discarded to fit
the requested size or because current eligibility filters exclude them. Uncalculated
manual positions count toward the collection size and spacing but have unknown
coverage; the UI explains that the measured total excludes their unknown contribution.

At each step the eligible non-dismissed automated position with the largest additional
matching visible area is selected. Ties follow the existing individual ranking and
stable ID. Current observer eligibility/exclusions, applied terrain/access criteria,
working coordinates and configured observer separation apply. Selection stops at
the requested total size or when no eligible position adds a cell. Spacing uses
observer coordinates solely as a spacing constraint, never as an overlap estimate.
This is a deterministic greedy recommendation, not a proven global optimum.

Cards show total matching terrain, additional terrain beyond retained positions and
earlier suggestions, and overlap divided by that position's total matching visible
area. The combined total counts each aligned analytical cell once. The main map
shows blue combined coverage and highlights the selected suggestion's incremental
contribution in pink. Incremental shading refers to its greedy inclusion step, not
the terrain exclusively visible from that position in the final collection. Areas
use the existing square-mile display conversion; saved analytical values remain metric.

Computing and reviewing makes no decisions. **Add suggestions to shortlist** rechecks
the sealed snapshot and atomically adds only the reviewed suggestions. It preserves
every existing point decision, annotation, approach selection and confirmation.
Stale submissions are rejected instead of silently modifying a changed shortlist.
The collection is not a visiting order; each added point still follows the existing
independent approach boundary, preflight, viewing and confirmation workflow.

Use **Find → Recommendation mode → Complementary views**, choose a size, click a
contribution card, and use **Whole area** for an overview. **Prepare coverage** prepares
combined and incremental tiles at normal known-retained/suggested position views and a bounded overview.
Preparation is capped at 20 known positions if the existing shortlist exceeds the
requested collection size; every retained position still counts in analytical coverage.
Click **Add suggestions to shortlist** only when you want the suggested positions.
Select **Individual views** to return to normal single-view review. Applied criteria
are shared; **Show original terrain** clears review criteria for collection coverage too.

## Architecture and resource limits

`huntmaps_gui/complementary.py` is an additive GUI service. It reads the existing
`DisplayRun` mask adapter, including immutable working revisions, and applies the
current target profile. Existing adapter checks enforce original analytical pixels,
CRS, integral origins, cell size, radius, target intersection, saved area and source
hashes. Cover, target and observer grids also have explicit alignment checks. No
screenshots, vector footprints, tiles or bounding rectangles determine the area score.

One unpacked candidate mask is transient. Nonempty candidate windows are trimmed,
aligned to byte columns and packed. A shared LRU has a **32 MiB byte budget** and an 8,192-entry metadata cap; it
streams candidates again if that budget is exceeded. The working union and at most
five incremental masks are packed. It never retains a full-grid boolean mask for
every candidate. Cache identities include verified source hashes/filesystem identities,
profile semantics, immutable point inputs and current working revisions.

Calculation runs in a backend thread with one collection calculation admitted at a
time. It uses the existing three-million-cell guard and free-space reserve. Result
snapshots and up to six compressed RGBA previews are disposable display-cache assets,
subject to the existing budget/eviction system. Files are published atomically; derived
preview hashes are checked before display. Analytical masks and decisions are outside
that cache. Missing previews produce a retry/recalculation path, not invented coverage.

Only combined and selected-contribution layers are active. The existing eight retained
GPU-source limit, two tile reprojection workers, one background preparation request,
HTTP reuse, cancellation/resume, movement/job/memory/storage pauses and write-triggered
cache maintenance remain in use. Collection preparation does not expand comparison to
five independent full-grid sources. Other zooms and cache eviction can require loading.

Run/profile/size and relevant decision/waypoint changes cancel or invalidate the UI
request. Late replies cannot publish into another run, criteria or collection size.
Backend seals include decisions, annotations/manual records, waypoint state, source
identities and profile/network provenance; additions require exact current inputs.
Warm result requests still validate analytical sources. Collection calculations,
size changes and reviewing use saved viewsheds and never acquire sources or invoke
the visibility engine.

## Real-terrain measurements

Three independent process/cache repeats, existing Ubuntu environment and
`.venv/bin/python`. Cold means new process and empty application caches; the OS page
cache was left alone. New sources/downloads: zero. Benchmarks use existing saved
real terrain read-only, with disposable state under `/tmp`. Network acquisition is
forbidden. Some repeats ran alongside acceptance work, so small timing differences
are not isolated CPU claims. Samples are in
[COMPLEMENTARY_VIEWS_2026-10-10.json](COMPLEMENTARY_VIEWS_2026-10-10.json); reproduce with
`.venv/bin/python -m gui.complementary_performance`.

| Saved real run | Candidates | Cold five | Warm five | Change to three | Change to four | Packed masks | Process peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Soap Creek baseline | 150 | 1.005 s | 0.096 s | 0.258 s | 0.303 s | 1.40 MiB | 236.9 MiB |
| scouting-2026-10-10v4 | 608 | 1.829 s | 0.208 s | 0.293 s | 0.311 s | 1.62 MiB | 214.5 MiB |

These are service wall-time medians, excluding interpreter startup, HTTP/browser
rendering and source download. Process RSS is a cumulative high-water mark, not an
incremental candidate-cache allocation. Soap Creek's analytical grid is 1,155×1,056;
the larger candidate collection uses 665×726 cells. Independently recomputed unions,
per-position totals and increments, and derived alpha rasters match exact saved
analytical cells. A 5,000-candidate real run is not available and was not benchmarked.

## Verification

The known-answer regression uses A=10 cells, B=nine of A's cells, C=eight different
cells. With two selections it returns **A+C and 18 unique cells**. Other checks cover
identical views, zero gain, retained/unknown manual points, rank ties, eligibility,
spacing, byte/window edges and LRU eviction. Actual owner-generated saved masks
exercise backend union/increment calculations, explicit additions, preservation of
retained decisions, dismissal/restoration, filters, pending moves, published working
masks/coordinates, absent moved masks, warm-cache source corruption and stale additions.
The nine focused backend checks passed.

The mandatory browser journey uses a separate synthetic run produced by the actual
analysis worker, live collection/tile/workflow services and no provider downloads.
It verifies contribution cards, rendered coverage, preparation, size changes, explicit
additions, unchanged individual ranking, dismissal/restoration, responsive layouts,
and held actual backend responses for obsolete size/filter/run requests. Pixel checks
prove rendering rather than accepting a Ready label alone. Synthetic interactions
are engineering evidence, not real hunt opportunities.

The final collection browser journey passed. The synthetic five-position calculation
took 1.226 s through HTTP, including 0.351 s in the service; the warm three-position
change took 0.200 s through HTTP. Initial preparation took 16.869 s. A second batch
verified three known retained positions plus two suggestions, without requesting
nonexistent incremental layers for retained positions. Preparation remains bounded
and can be slower than recommendation calculation because it renders view tiles.
Reviewing suggestions made 19 further tile requests across new views; three responses
used the browser HTTP cache. Reviewing did not run visibility or download sources.

The real 608-candidate browser journey, with normal map/display work competing for
resources, recorded 3.390 s in the service and 11.277 s through ready collection
coverage. A zoom click took **82 ms** while calculation was pending; 662 frames rendered
with a maximum observed frame gap of 50.1 ms. These loaded-browser measurements differ
from the isolated service medians above. The journey reported no page errors. Desktop,
900 px and real-terrain screenshots were inspected; the rendered synthetic overview
contained 9,843 pink and 9,110 blue coverage pixels. Held responses verified that old
size, filter and run results do not replace current results.

An earlier full run stopped at the new browser harness because it held both the old
and fresh filtered request. The harness now holds only the intended obsolete response;
the focused repeat and final collection journey passed. This was a test-interception
error, not acceptance of an obsolete recommendation.

The complete **`./gui/check` passed**, exit 0: 201 backend tests, Python/frontend
formatting, production frontend build, actual-worker recovery and all 22 mandatory
browser journeys. Existing approach, working-waypoint, acquisition/recovery, exports,
cache/preparation, first-person, network and nearby-observer journeys passed alongside
the new collection journey. The long suite's server high-water RSS was 1.195 GiB;
that includes all journeys and retained display caches, rather than isolated collection
service memory.

Diagnostics: `/tmp/huntmaps-check-ug6ylh9q`; browser evidence is under
`screenshots/browser-complementary-check`. `protected-audit.json` records **8,065
protected files and zero changes**, including owner records and companion-server state.
The content/hash preservation audit also returned `changed: []`. Final `git diff --check`
passed. Local and remote main remained at the audited `b801235` revision; changes are
left uncommitted for review.

## Limits and preservation

This layer selects among saved, eligible calculated positions. It does not generate
new observers, change visibility, habitat coefficients, approach algorithms or export
coordinates, and cannot account for unknown manual coverage. Strong overlap or spacing
can yield fewer suggestions. A full existing shortlist can yield none. Large pools
beyond the byte cache budget stream masks and can take longer; only 150/608 real pools
were measured. Display preparation remains viewport/zoom/cache dependent.

Terrain-visible matching area is not deer probability, verified clear vegetation,
field validation or legal/safe access. Source ages and existing terrain/vegetation
uncertainties remain. Historical controls, reports, source reuse/recovery, acquisition
review, exports and independent approach/confirmation requirements are preserved.
No field collection, route ordering or later model work is part of this milestone.

Initial audit: clean local `main`; local and remote HEAD both
`b801235c80857c6b23567b9d29edfcdd60b6f46e`. This includes the work newer than externally
reviewed `8c2d277`. No reset, commit or push was performed. All writes stayed in this
Ubuntu project or `/tmp`; Windows and Data partitions were untouched.
