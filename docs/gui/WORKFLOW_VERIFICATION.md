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
