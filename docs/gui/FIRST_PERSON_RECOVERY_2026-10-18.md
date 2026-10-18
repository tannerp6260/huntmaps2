# First-person recovery and compact scene controls — October 18, 2026

Implemented and verified. A0136 now prepares and renders from cached sources;
the scene window opens saved views automatically and hides technical preparation
controls. See [the completed progress log](FIRST_PERSON_RECOVERY_PROGRESS.md).

## Confirmed cause and focused correction

A0136 in `scouting-2026-10-18` supplied 3,563,990 local accepted returns, including
914,731 classified-ground returns. Selecting the existing first measured return
per 0.25 m bin retained 867,348 ground inputs. The old blanket 800,000 limit rejected
this cloud before the existing tiled triangulation ran. The largest actual tile
needed only 22,816 inputs. The Matplotlib Axes3D warning was unrelated to that
explicit rejection.

The blanket limit is replaced by a local bin-occupancy bound: at most 100,489
inputs per full 60 m tile plus its 10 m halo. Point selection/order, interpolation,
5 m maximum triangle edges, support/unknown masks, curvature and coordinate
handling are unchanged. The eight-million-return guard, 1536 MiB process address
space and 900-second stage guards remain. This addresses this demonstrated dense
cloud; it does not promise that arbitrary source collections fit those budgets.

A second confirmed defect affected retries: completed imagery could be skipped by
a cached-only attempt, or downloaded again, when the original approved inventory
still said `cached: false`. Lidar and imagery now resolve verified complete entries
from their cache metadata, checking source identity and SHA-256. The API exposes
current remaining bytes and cached keys without rewriting the approved inventory,
review signature or cumulative transfer history. Corrupt/different sources fail
visibly with their bytes retained.

Implementation touchpoints: [local ground meshing](../../huntmaps_gui/first_person_worker.py),
[verified source reuse](../../huntmaps_gui/scene_sources.py),
[current cache/storage estimates](../../huntmaps_gui/scene_storage.py),
[plan API](../../huntmaps_gui/api_routes.py),
[scene controls and fallback](../../gui/frontend/src/first-person.tsx), and
[renderer retry](../../gui/frontend/src/scene-viewer.tsx). No analytical engine,
model coefficient, historical result or source coordinate was edited.

## Window behavior

Saved scenes open automatically. The header identifies Basic or Detailed terrain.
One relevant preparation/retry action shows remaining size and approximate download
time. Detailed failure or unavailable lidar produces a labeled, download-free basic
scene only when there is no valid saved scene. Cancellation does not launch fallback;
a failed basic attempt does not loop. Replies for an obsolete/closed dialog cannot
start fallback. Current working-waypoint revisions are checked before displaying a
retained plan.

**Retry opening view** appears after a loading/rendering failure and reopens saved
assets; it does not rebuild the scene or approve downloads. **Retry detailed view**
checks sources and starts a cached-only preparation when no downloads are needed.
New transfers still require the displayed preparation approval.

Source inventories, original detailed failure diagnostics, logs, cumulative bytes,
storage estimates and the optional download limit live under collapsed **Details
and settings**. Warnings remain prominent for at least 1 GB, an ETA reaching
30 minutes, or projected remaining storage less than 5 GiB above the protected
20 GiB reserve. A single-option saved-setup selector and redundant refinement
preparation button are removed. Existing multi-setup pilot selection is retained.

## Actual A0136 evidence

Replay used original cached sources read-only, a disposable plan/state, and an HTTP
ban. No source downloads or original scene preparation were performed.

| Observation | Result |
| --- | --- |
| Full preparation | Exit 0, 66.28 seconds wall time |
| Peak RSS | 699.5 MiB, with unchanged 1536 MiB address-space limit |
| Observer | x 304385, y 4286045, EPSG:32613; unchanged |
| Geographic coordinate | -107.24949723248817, 38.70141634425285; unchanged |
| Fine ground at observer | Available, elevation 3376.72900390625 m |
| Actual browser render | Loaded; no page errors, no pending/failed imagery |
| Rendered geometry | 2,486,152 total triangles; 207,088 vegetation triangles |
| Visually inspected layouts | Desktop and 900 px |

Evidence root: `/tmp/huntmaps-first-person-20261018-a12o_q65/a0136-replay`:
`metrics.json`, `prepare.log`, and `screenshots/render.json`.
Screenshots: [desktop](/tmp/huntmaps-first-person-20261018-a12o_q65/a0136-replay/screenshots/a0136-detailed-desktop.png),
[900 px](/tmp/huntmaps-first-person-20261018-a12o_q65/a0136-replay/screenshots/a0136-detailed-900.png).
Preparation time is a single cached local replay, not a general benchmark or download
estimate. Modeled vegetation and terrain retain all existing limitations; successful
rendering establishes neither field accuracy nor a clear sightline through trees.

## Regression and release evidence

Focused backend evidence: dense-plane regression passed in 21.3 seconds; original
cached-imagery skip was reproduced and fixed; existing 21 first-person, 10 lidar
recovery and eight scene/storage tests passed. An additional API regression checks
zero remaining bytes while original plan bytes/signature and cumulative ledger stay
unchanged. Final suite and preservation results are below.

Acceptance investigation also exposed fixture coupling and outdated action labels.
Specialist tests now use unprepared points where they require preparation, select
the intended setup after reload, and preserve meaningful storage/source/rendering
assertions. The scene recovery journey creates an independent run. Storage's old
async `waitForFunction` accepted its Promise before the preparation job completed;
explicit API polling now checks completion, failures and timeouts before asserting
that the scene is ready. No production publication change was needed for that issue.

The first full gate also exposed a connectivity cancellation timing assumption:
the real screen worker completed in 1.55 seconds before cancellation took effect,
so the UI correctly showed its completed state. The journey now pauses only its
owned disposable job process group before displaying the launch response, resumes
after the real Cancel endpoint, and asserts actual cancelled status before retry.
It also retains screenshot/text diagnostics on failure. This controls timing without
mocking cancellation, weakening assertions or adding production test hooks.
The corrected standalone journey passed in `/tmp/huntmaps-check-0t955xl5`.

The guided journey replaced its obsolete single-option dropdown lookup with real
renderer readiness, shortlisted-candidate membership, exact observer coordinates
and matching visible heading. Its target and confirmation assertions remain intact.
A keep-going batch passed 25/26 remaining journeys; it caught a regression in this
follow-up where a successful waypoint revision unnecessarily reloaded the scene,
clearing its success message/refinement state. The metadata effect now loads by
scene URL/entity/retry rather than revision; preparation replies still use revision
guards. The existing two-save, exact-coordinate, reload/export/restore journey is
retained unchanged to verify this correction.

## Final release results

`./gui/check --keep-going` completed with **exit 0** using the final frozen inputs.
No required stage or assertion was skipped; keep-going only collects failures if
one occurs. The final run had none.

| Check | Observed result |
| --- | --- |
| Backend release groups | **269 tests passed**, 12 groups, including three new dense/cache/API regressions |
| Main browser acceptance | **30/30 passed**, including recovery, lidar, guided workflow, required assets, Storage, waypoint updates, coverage, performance, clusters and nearby observers |
| Real recovery workflow | Interrupted-download/retry, 600-location search, reload, approach/inspection/confirmation and 900 px passed in isolated state |
| Static/build | Black, Prettier, TypeScript and Vite passed; `git diff --check` passed |
| Runner preservation | **9,067 files unchanged**; owner records and concurrent companion state unchanged |
| Complete follow-up baseline | **31,618 protected/state files byte-identical**, zero added or missing paths |
| Gate input stability | **353 files unchanged**, zero added or missing paths; only progress/report excluded |
| Visual/browser checks | Real A0136 desktop/900 px inspected; compact controls, fallback and 450 px screenshots inspected; no horizontal overflow at 900/450 px |
| Process cleanup | No verification processes remain for the final runner or A0136 replay |

The existing saved-scene performance journey measured zero idle redraws, zero
additional geometry requests during interaction, and no browser errors. Its single
local run recorded 7.55 s to ready and 365 ms movement latency with 2,708,326
triangles. These are regression observations on the test browser, not a claimed
speed improvement. For A0136 the measured improvement is successful bounded
preparation/rendering instead of the original deterministic rejection.

Final diagnostics: `/tmp/huntmaps-check-4yaku56v`:
[backend counts](/tmp/huntmaps-check-4yaku56v/backend-counts.json),
[browser matrix](/tmp/huntmaps-check-4yaku56v/browser-results.json),
[real recovery log](/tmp/huntmaps-check-4yaku56v/browser-recovery-worker.log),
[runner preservation](/tmp/huntmaps-check-4yaku56v/protected-audit.json),
[performance](/tmp/huntmaps-check-4yaku56v/screenshots/browser-performance-check/performance.json),
[recovery policy checks](/tmp/huntmaps-check-4yaku56v/screenshots/browser-scene-recovery-check/results.json),
[450 px screenshot](/tmp/huntmaps-check-4yaku56v/screenshots/browser-scene-recovery-check/compact-view-450.png),
[complete baseline/input comparison](/tmp/huntmaps-first-person-20261018-a12o_q65/final-preservation.json).

## Preservation and remaining limits

A recoverable source archive, pre-existing patch/status and 31,618 protected/state
SHA-256 records were captured before this follow-up in
`/tmp/huntmaps-first-person-20261018-a12o_q65`. Existing audit/connectivity changes
remain preserved. No dependency updates, analytical/scoring changes, commits or
pushes are part of this follow-up. No Windows/Data partitions were touched.

There are no remaining known blockers for this implementation. Existing Matplotlib
Axes3D and Vite bundle-size warnings remain nonfatal; no dependency changes were
made. Live provider availability/download speeds, field fidelity and arbitrary
point clouds beyond the retained budgets were not validated. These checks do not
reconstruct fine terrain or vegetation where measurements are missing.

The owner process and failed original A0136 state are intentionally untouched; after restarting the
application with this code, use **Retry detailed view** to prepare the saved setup
from verified cached data. This verification created its successful scene only in
temporary state.
