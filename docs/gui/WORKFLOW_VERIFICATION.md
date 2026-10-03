# Workflow verification

Implementation verification for the three-stage GUI workflow. All fixtures and browser decisions use disposable state/workspace directories; no historical analyses or prepared owner scenes are regenerated.

## Checks

`./gui/check` **passed** 105 Python tests, format checks, the production frontend build and all **11 isolated browser journeys**. Diagnostics: `/tmp/huntmaps-check-sw26tu7m`. New workflow tests cover backend transition requirements, early terrain inspection, explicit approach selection, confirmation/reload/removal, recomputation, optimistic revisions, changed coordinates, manual points, duplicate waypoint identifiers across runs, acquisition deduplication/selection, transfer allowance boundaries and unsupported record versions. Existing suites exercise partial transfers/cancellation, cache accounting, network compatibility, saved settings, exact waypoint exports, training, first-person scenes, foliage, nearby positions and maintenance.

The new browser journey creates a synthetic completed run, verifies original-area and engine sorting, shortlists a setup, confirms a travel boundary, imports a mapped network, computes and selects an approach, prepares a terrain-only view, successfully renders it, records viewing, confirms and reloads the final decision. It checks stage gates and 900-pixel horizontal fit. Desktop and 900-pixel screenshots were visually inspected. After the final terrain-only copy/control adjustment, formatting and the production build passed again, followed by a fresh isolated three-stage journey (`/tmp/huntmaps-final-presentation/screenshots`) and another clean preservation audit.

## Measurements

The isolated synthetic terrain scene took **0.056 seconds** to prepare, with **298.66 MiB** peak process RSS. These are worker measurements for a small engineering fixture, not estimates for a real hunting area. Browser rendering and job startup are excluded. Existing CPU, memory, triangle, source-transfer and derived-output limits remain enforced.

The final software-rendered historical-scene browser check measured **16.0 seconds** from opening to terrain/imagery readiness, **318 milliseconds** for a one-foot observer move, **28.4 MiB** used JavaScript heap and **78.3 MiB** backing storage. Browser/GPU native memory is excluded from those heap figures. It observed **zero idle redraws** and **zero additional geometry requests** during movement. These are local headless Chrome measurements, not field-device performance guarantees.

The checker server reached **1,052 MiB** peak resident memory across the full historical suite; the ending resident snapshot was **1,029 MiB**. This is distinct from the bounded scene worker and browser heap measurements above.

## Preservation and limitations

The checker inventories protected analysis/configuration/data/run/report files and hashes owner GUI records, including workflows and prepared scenes, before/after verification. The completed audit covered **7,835 protected files**, with **zero changes**, and verified owner GUI records and the companion application state. Historical controls and supplied reports remain unchanged. Generated fixtures and screenshots remain outside the repository under `/tmp`.

The end-to-end new-run scene journey uses the existing DEM with no source transfer. Arbitrary-area lidar acquisition metadata and selection are tested with bounded catalog fixtures; no new live lidar batch or field collection was performed. Existing lidar scenes are exercised by historical browser journeys. This verifies software behavior, not actual hunt opportunities, legal/safe approaches, deer probability or field visibility.

## Refinement verification — 2026-10-03

The final `./gui/check` passed **114 Python tests**, Python/frontend formatting, the production build and **12 isolated browser journeys**. Diagnostics: `/tmp/huntmaps-check-pec2qwey`. The new tests cover Dismiss/Undo/Restore and legacy workflow records, allowances above the former caps, reserve boundaries, partial preservation, parallel progress accounting, measured/assumed time estimates, optional telemetry recovery and stale consent at both API and worker boundaries. The new browser journey uses a synthetic 3 GB plan without acquiring data and verifies custom speed assumptions, live progress/ETA, stalls, indeterminate processing, reload, reserve blocking and the 900-pixel layout. Desktop and 900-pixel screenshots were inspected.

The final isolated terrain scene took **0.059 seconds**, with **197.54 MiB** peak worker RSS. The full checker server peaked at **1,119.6 MiB** resident memory. These fixture measurements are separate from download-time estimates and are not predictions for a real area. Existing processing resource limits remain enforced; fixed transfer caps are replaced by reviewed allowances and storage safeguards.

The protected-file audit reported no changes, and the checker verified unchanged owner records and companion-app records. Historical analyses and prepared owner scenes were not regenerated. Earlier verification measurements above describe their original runs.


## Expanded search and coverage completion — 2026-10-03

`./gui/check` passed **120 Python tests**, formatting/build checks and **13 isolated browser journeys**. Diagnostics: `/tmp/huntmaps-check-pjmoc642`. After the final legacy-recovery copy/default adjustment, the production build and targeted coverage/search browser journey passed again (`/tmp/huntmaps-final-coverage-v2`). Desktop and 900-pixel loading, incomplete/retry, ready and search-control screenshots were inspected.

New checks cover persisted search settings, maximum-budget validation, repeatable broad/local search, duplicate automated cells, unchanged exact manual coordinates, interrupted batch recovery, output-limit checkpoints, missing/edge vegetation coverage, separate shrub evidence and clearance preference ordering. Search settings participate in reviewed download signatures. Tile concurrency tests verify duplicate coalescing, at most two reprojections, pinned-source eviction protection and consistent maintenance/GDAL lock ordering with 3D elevation tiles. The 3D training and moved-waypoint comparison journeys pass; the coverage status no longer blocks comparison controls.

The synthetic expanded-search run evaluated 24 automated locations and recommended five: **1.537 seconds**, **209.26 MiB** peak worker RSS and **1,187,077 bytes** of analysis outputs. A separate 48-automated/two-manual fixture verifies interruption and reproducibility. These are small engineering fixtures, not time or memory predictions for a real area. Existing memory, grid, batch-time, output and storage-reserve guards remain enforced.

The final synthetic coverage browser journey reported **11.535 seconds** from run selection to initial coverage readiness while deliberately delaying each coverage request by 600 ms and running alongside the larger suite. This measures feedback completion under injected delays, not a production speed claim. It checks opacity changes cause no extra coverage requests, incomplete tiles produce Retry, outdated point responses do not replace current status, comparison can be exited, and the 900-pixel layout fits.

Historical scene software rendering measured **20.111 seconds** to readiness, **524 ms** for a one-foot observer move, **28.29 MiB** used JavaScript heap and **78.24 MiB** backing storage, with **zero idle redraws** and **zero additional geometry requests**. An additional coverage browser ran concurrently during part of this check; these figures are not directly comparable to the earlier single-browser measurements. The full checker server peaked at **1,249.51 MiB** RSS and ended at **1,129.03 MiB** RSS.

The checker verified unchanged protected files, owner records and companion-app records. Frozen terrain/model implementations, historical analyses, supplied reports and prepared owner scenes were not regenerated or modified. Expanded search is a separate normal-GUI adapter; the original engine leading collection and inspection indices remain available separately from recommendations. Low mapped nearby tree cover is potential clearing evidence, not verified eye-height visibility or a global optimum.

## Search and recovery acceptance — 2026-10-03

Final `./gui/check` passed **125 backend tests and 15 browser journeys**, with diagnostics in `/tmp/huntmaps-check-fodhwm_m`. The mandatory recovery acceptance creates a fresh, small observer area with Thorough search, downloads a controlled source, fails after downloading, reloads, retries using cached files, and completes approach selection, terrain-only viewing and confirmation for that same recovered run. Its desktop and 900 px screenshots are in `/tmp/huntmaps-browser-recovery-kmjrg0vm`; these were visually inspected.

The search evaluated **600 distinct automated locations**, recommended 10, and reduced broad spacing from 150 m to **20 m**. Its measured worker time was **5.233 seconds**, peak RSS **207.07 MiB**, and generated analysis size **12.87 MB**. The terrain-only scene worker took **0.056 seconds** with **206.29 MiB** peak RSS. These measurements describe small synthetic engineering fixtures, not expected performance for a hunting area or a live provider. The full checker server peaked at **1,089.79 MiB RSS** and ended at **1,065.48 MiB**.

New regressions cover 16 boundary/preset combinations, exhausted and empty eligibility, recommendations exceeding available locations, unchanged manual coordinates, interrupted transfer accounting, post-download failure/retry, genuine request and checksum changes, stale consent on cached-only starts, configurable-workspace paths, and rejection of incompatible checkpoints without changing their files. Browser checks also caught and fixed a stale saved-results selector after reload and misleading terminal progress labels.

The final audit covered **8,184 protected files with zero changes**, alongside unchanged owner GUI records and companion-app state. Historical analyses and prepared scenes were not regenerated. One early disposable harness incorrectly reached a live DEM endpoint; its isolation was corrected and its generated 360 MB temporary download removed, with logs retained. The final recovery fixtures route source responses to localhost and reject uncontrolled external requests.

See [TESTING.md](TESTING.md) for the execution-level coverage matrix, mocked boundaries and remaining limitations. Legacy failed plans require one explicit refresh/review before reuse; incompatible older calculation checkpoints require a new run name and remain intact.


## Coverage retention and help dismissal — 2026-10-03

Final `./gui/check` passed **128 backend tests and 16 isolated browser journeys**. Diagnostics: `/tmp/huntmaps-check-w5iu2oiu`. Its audit covered **8,409 protected files with zero changes**, plus unchanged owner GUI records and companion-app state. No historical analyses or prepared scenes were regenerated.

The help regression checks hover exit, focused Escape, click/outside click, Tab, scrolling and touch. Desktop and 900 px coverage screenshots, the background tile counter and the open 900 px help box were visually inspected. Full-page screenshots intentionally resize the viewport and dismiss help, so the open-box screenshot uses the actual viewport.

A real saved-raster benchmark generated one cold tile in **49.0 ms**, served the same bytes in **0.8 ms**, and verified only one GDAL reprojection. The separate browser cache journey uses no request interception (Playwright routing disables HTTP caching). It measured **4.985 seconds** from run selection to initial readiness, **827 ms** to a prefetched setup and **797 ms** to a returned setup, including map movement. Returning requested **zero additional coverage tiles**. CDP recorded **191 coverage-image cache hits**, with assertions for the exact prefetched and reloaded setups. Warming fetched 90 local tiles for the next three setups; it acquired no new source data.

The journey also visits ten setups to enforce the eight-source limit, switches runs, reloads and dismisses/restores a setup. Focused backend tests verify dismissal-aware eviction, retention under budget pressure, pinned sources, duplicate request coalescing and preparation pauses for active jobs or the 20 GiB reserve. Existing filter, comparison, revised waypoint, failure/retry and stale-response journeys remain mandatory.

After the coverage stress journey, JavaScript used **13.95 MiB**, with **1.80 MiB** backing storage; this is a snapshot, not a peak or total browser/GPU memory measurement. The full checker server peaked at **1,167.17 MiB RSS** and ended at **1,151.11 MiB RSS**. The final display cache's apparent size was **12.84 MiB**, below its 256 MiB budget. These are engineering fixtures and software-rendered browser measurements, not production timing guarantees.

Cache retention is best effort under the configured budget. Saved analytical viewsheds remain permanent; only regenerable display files become eviction candidates. Renderer version, run, point revision, filter and color separate browser identities; native source fingerprints separate disk assets.

## Coverage occluded by imagery — 2026-10-03

Retained coverage was hidden when online imagery was moved above it; the ready label only checked loading. A new canvas-pixel regression reproduced the failure with just 24 cyan pixels before the fix. Shared ordering now keeps hillshade, online imagery, saved imagery, coverage, cover classes and boundaries in that order, including reuse and imagery toggles.

Final `./gui/check` passed **128 backend tests and 17 isolated browser journeys**; diagnostics are in `/tmp/huntmaps-check-_s12utew`. The audit covered **8,634 protected files with zero changes**, including unchanged owner records and companion state. Historical analyses and scenes were not regenerated.

The mandatory rendering journey uses opaque local imagery fixtures and actual saved coverage API tiles. Switching, returning, opacity changes, imagery toggles and comparison entry/exit all produced visible cyan pixels; opacity zero removed them. Desktop and 900 px screenshots were inspected. This verifies rendering, not live provider availability. The independent, unintercepted cache journey measured initial readiness at **5.058 seconds**, prefetched selection at **832 ms**, and return at **813 ms**, with **zero additional return tile requests** and 180 HTTP coverage cache hits.

The checker server peaked at **1,127.14 MiB RSS** and ended at **1,091.78 MiB RSS**. Cache-journey JavaScript used **18.17 MiB** with **1.93 MiB** backing storage (snapshot, not peak or GPU memory). Cache limits and analytical calculations are unchanged.
