# Verified local source reuse — 2026-10-10

The normal GUI now discovers compatible raw USGS vegetation and CPW seasonal-range
downloads in project-local source caches and earlier normal runs. Exact bytes are
imported into an independent `.gui/sources` store. The protected owner engine,
historical inputs/results and expected preservation hashes are unchanged.

## Behavior and review

Explicit configuration takes precedence. Managed sources are considered first,
then raw manifests in sorted path order. USGS request semantics must match the
existing product, 2023 time slice, 30 m request, CRS and nearest-neighbor setting;
CPW seasonal layer, filtering, full geometry and original query extent must match
the requested use. Source SHA256, readability and the actual analytical footprint
are checked. Rasters with unrecorded companion files are rejected instead of losing
their metadata during a single-file import. Vegetation NoData stays unknown under
the existing rules. Validation scratch files stay in GUI state; donor directories
remain read-only.

Imports use locked, atomic publication, bounded copy buffers and the existing
20 GiB free-space reserve. Invalid donors are retained and skipped; already selected
managed inputs whose bytes/provenance change stop processing. Partial copies are
not source entries. Published copies do not depend on the original archive.
Display-cache cleanup does not evict these analytical inputs.

The acquisition review includes original source links, product dates and retrieval
dates. Approval binds the imported checksum and full provenance, including raw
CPW responses behind normal geometry normalization. A prior approval for a remote
crop cannot silently become approval for another local source. Refresh/review is
required. Remaining missing sources keep the ordinary bounded download workflow.

## Verification

Before implementation, the real-owner preparation regression failed with missing
tree data despite a compatible local raw download. It now passes, including a
second preparation after the donor archive is removed.

Focused regressions cover wrong product/year/query/resolution, insufficient extent,
unreadable/corrupt data, incomplete CPW responses, explicit-source priority,
deterministic selection, changed source/provenance, concurrent imports, interrupted
copies, mutations during validation, escaped paths, storage failure and approval
refresh. Real synthetic analysis workers compare candidates, scores, leading and
recommendation rankings, every prepared raster, and every visibility raster against
the identical original raw files. Raster arrays and geotransforms match exactly.

The latest real area (`70ae9ae06f4b4537b9095e6e5dcf91d9`,
`scouting-2026-10-10v3`) was reproduced in
`/tmp/huntmaps-source-reuse-nxedu4ny/real-workspace`, with disposable state and all
network requests forbidden. Preparation found compatible 2023 tree/shrub/herb
sources and complete CPW summer/winter responses. The existing verified DEM was
supplied unchanged. Source download estimate and transferred bytes were zero.
All 620 evaluations at 1,500 m radius completed, including the report and GIS
exports, in one 13.85 s run. Optional road/trail acquisition and observer-access
sampling were excluded from that initial check.

The final replay included the user's unchanged cached roads/trails and observer
access limits (457.2 m from mapped lines, 152.4 m above the nearest line point).
Preparation took 3.71 s and the full run took 142.79 s; all 620 evaluations at
1,500 m and report/GIS exports completed, with zero source or network transfer.
Logs and settings evidence are in `real-final-metrics.json` and
`real-final-run-job-environment.log` in the same artifact directory. Network
requests remained forbidden. These are functional checks, not repeated timing
benchmarks; observer-access filtering remains a substantial calculation stage.

An initial direct-worker invocation omitted the normal job's bounded BLAS/OpenMP
environment and stopped before observer sampling with empty exception text. The
replay used the existing `Jobs` environment (`OPENBLAS_NUM_THREADS=1`,
`OMP_NUM_THREADS=1`) and passed. No memory limit or other processing guard changed.

This verifies reuse of the recorded local observations, not equivalence to an
unavailable new remote crop or current vegetation conditions. No new live-provider
availability claim is made. Logs, selected source hashes/provenance and real-area
evidence remain under `/tmp/huntmaps-source-reuse-nxedu4ny`.

Final `./gui/check` passed in `/tmp/huntmaps-check-d7kfygly`: 189 backend tests,
Python/frontend formatting, TypeScript/build, the real 600-evaluation recovery
worker and all 20 offline browser journeys. The source-review browser check
verified original dates/links at desktop and 900 px; screenshots were inspected.
The earlier complete run `/tmp/huntmaps-check-982gi6tr` also passed; the final
rerun includes the last companion-file and read-only-validation guards.

The final protected audit found zero changes across 11,858 files. The independent
before/after audit also found zero changes to those files and all 508 existing
owner records. No protected engine, source/configuration/control hashes, saved
results, annotations, manual coordinates or prepared scenes were changed. No
production plan was started or rewritten; all mutating verification used disposable
state/workspaces. `git diff --check` passed; changes remain local and uncommitted.

## Owner steps

Restart HuntMaps2, open the failed plan, select **Refresh plan / recover partial
preparation**, review **Verified local sources** and any remaining downloads, then
select **Generate setups**. No manual file copying, allowance increase, settings
change or new run name is needed for this acquisition failure. A completed run
still requires a new name; incompatible existing analysis checkpoints remain intact
and retain their normal recovery instructions.
