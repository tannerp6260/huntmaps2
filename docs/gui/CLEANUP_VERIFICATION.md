# GUI cleanup acceptance

The reviewed prototype is preserved at local commit `aeecf0b`. Subsequent local
commits isolate verification, format GUI code, centralize versioned JSON records,
split and type the frontend, simplify job publication/polling, bound display caches,
and document installation and maintenance. No remote publication was performed.

Final acceptance passed with diagnostics retained at
`/tmp/huntmaps-check-046_yoiu` and an empty protected-file change list.
Preflight and `./scout verify --name soap-creek-v1` also passed.

Run `./gui/check` to repeat the offline acceptance gate. It runs 86 backend tests,
Black and Prettier checks, TypeScript checking/build, and eight browser journeys.
Each journey uses a dedicated localhost server and disposable state/workspace.
A second live app with sentinel records stays open during browser verification;
its files and the owner's durable state are compared byte for byte afterward.
Diagnostics and desktop/900-pixel screenshots are retained under the printed
`/tmp/huntmaps-check-*` directory.

Coverage includes real Soap Creek saved viewing, individual comparison masks,
exact GPX/KML coordinates, annotation persistence, boundary drawing/import,
training, offline imagery fallback and baseline jobs. Synthetic baseline jobs use
the existing CLI in a disposable workspace. Storage tests cover legacy migration,
malformed/versioned records, interrupted replacement, concurrent edits, backup,
reset/restore, reference-aware cleanup, active-job protection and display LRU.
Working-waypoint tests cover completion, cancellation, repeated updates, restore
and preventing late publication. First-person journeys cover Dense120 scenes,
exact ground/foliage ray agreement, movement-map recentering, the unchanged
exploration boundary, update/reopen/reset, original restoration and graphics failure.

The preservation manifest records SHA-256 hashes for 7,229 analysis, configuration,
source-data, historical-output and supplied-evidence files. Acceptance audits found
no changes. The original Soap Creek CLI verification also passes. Git excludes
source data, runs/results, environments, prepared bundles and generated rasters.

## Runtime comparison

The benchmark runs the checkpoint and current GUI against the same prepared A0075
Dense120 scene in disposable state. Chrome uses headless software graphics. These
are individual engineering measurements, not calibrated speed estimates.

| Measurement | Prototype | Cleaned GUI |
| --- | ---: | ---: |
| Scene ready | 9.63 s | 8.49 s |
| Movement interaction | 348 ms | 326 ms |
| JavaScript heap used | 18.56 MiB | 18.56 MiB |
| Server peak resident memory | 348.6 MiB | 349.1 MiB |
| Geometry requests after movement | 0 | 0 |
| Draws during settled idle interval | 0 | 0 |
| Rendered triangles | 2,708,326 | 2,708,326 |

Both loaded eleven binary assets, made no analysis jobs or downloads, and reported
no browser errors. Geometry remains unchanged during movement. Map and scene effects depend on geometry revisions rather than review notes. Desktop and
900-pixel screenshots were inspected; controls remain usable without horizontal
overflow. Reproduce the comparison with `.venv/bin/python gui/benchmark_prototype.py`
and the same command with `--current`.

## Limits and deliberate deviations

The repository's launcher is `./huntmaps-gui`; `./scout gui` was never implemented.
The historical `scout` executable and engine are hashed by saved verification
manifests, so this cleanup preserves them byte for byte. Use the documented GUI
launcher with `--state-dir` or `--preflight` as needed.

Pinned dependencies were installed and preparation imports checked in the existing
GIS environment. A fresh native GIS environment solve was not performed. Optional
online-provider checks and expensive scene regeneration are separate from this
offline acceptance. Existing specialist preparation/verification scripts remain
historical tools because their online coverage is not fully represented here;
use `./gui/check` for safe normal verification. Soap Creek first-person coverage
remains limited to its prepared pilot setups. No model, route optimizer, broader
vegetation coverage, field validation or automatic user-record deletion was added.

See [setup](SETUP.md), [user guide](README.md) and [maintenance/testing](MAINTENANCE.md).
