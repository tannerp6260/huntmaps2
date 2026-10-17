# RCMAP annual-source repair — 2026-10-15

GUI vegetation acquisition now uses the year-specific MRLC WCS layers for 2023:
`rcmap_tree:rcmap_tree_2023`, `rcmap_shrub:rcmap_shrub_2023`, and
`rcmap_herb:rcmap_herbaceous_2023`, under `https://www.mrlc.gov/geoserver/`.
These services are linked from the [MRLC services page](https://www.mrlc.gov/data-services-page).
The previously used time-enabled `dmsdata.cr.usgs.gov` requests returned XML
Java exceptions instead of rasters. Changing WCS protocol versions on that
time-enabled service did not resolve acquisition during investigation.

The adapter is GUI-only. Historical CLI/analysis implementation, source controls,
scores, reports, and prior outputs remain unchanged. Requests retain the original
coordinate system, outward bounds/padding, nearest-neighbor sampling, and requested
30 m resolution. Delivered georeferencing is read rather than assumed. Existing
alignment and unknown-cover handling remain authoritative; NoData is not open cover.

Annual downloads have distinct filenames and record component, observation year,
source policy, URL, retrieval time and checksum. The precise processing-release
identity is explicitly unverified. Neither matching observation years nor a shared
provider establishes equivalence to older sources. Automatic cache reuse checks
request and provenance compatibility; verified explicitly configured sources remain
inputs rather than being replaced opportunistically.

Older prepared acquisition requests are detected by the plan API. Retry refreshes
their source plan before generation and uses its new signature. A snapshot preserves
the exact previous plan/configuration/acquisition records under
`plans/source-history` in GUI state. Original downloads, rejected responses, ledgers,
and logs remain retained. Active jobs prevent concurrent refresh. Completed runs or
runs with numerical analysis require a new name when changing sources.

## Verification

- 46 targeted backend tests passed across annual-source planning/migration,
  acquisition validation, source reuse, interrupted recovery, jobs and search.
- Frontend type checking/build, Python/TypeScript formatting and diff checks passed.
- The isolated browser runner passed the Find flow, including automatic refresh of
  an outdated prepared plan before Retry, caps, cancellation and stale-input guards.
  Its real-worker recovery and complete scouting workflow also passed. Artifacts:
  `/tmp/huntmaps-check-78pgv1yq`.
- Live validation cloned the failed `scouting-2026-10-15` input/state into a separate
  workspace. Its unchanged observer geometry, 600-evaluation budget, road/trail
  proximity restriction and 600 MB cap were retained. All three vegetation rasters
  covered the full required extent; each was 674 × 609 cells and 1,636,274 bytes.
- Each source retained NoData=101. Unknown cover propagated to 11,121 of 2,531,256
  analysis-grid cells (about 0.44%), rather than being converted to zero cover.
- The full run completed 600 evaluations and produced its report, maps and GIS
  exports. Search outputs were about 132 MB, with measured peak RSS about 409 MiB.
  The cumulative transfer ledger, including retained earlier network/error bytes,
  was 7,713,688 bytes against the unchanged 600,000,000-byte ceiling.
- Current-run verification passed; the frozen-control audit reported no changes.
  Original failed-run files and GUI records were not replaced by validation outputs.

Live artifacts and machine-readable coverage/source evidence:
`/tmp/huntmaps-rcmap-live-ss0xboj2/evidence.json`. The completed validation run is
under that workspace's `results/scouting-2026-10-15/` directory.

The initial standalone validation omitted the thread limits normally installed by
GUI Jobs and stopped with a MemoryError in observer-source loading. Repeating with
the standard GUI limits completed successfully without changing memory/time caps.
Observer proximity screening remained the slowest step; its stage is now reported
explicitly instead of retaining a download-stage label.

No automatic ZIP/Earth Engine fallback, year substitution, model coefficients,
approach planning, route optimization or field-validation claims were added.

## Use

Restart the GUI server to load the backend changes, open the failed job through
existing work/Activity, and choose Retry or Generate setups. Old acquisition plans
refresh automatically; the existing download and storage limits still apply.
