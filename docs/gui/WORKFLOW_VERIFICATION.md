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
