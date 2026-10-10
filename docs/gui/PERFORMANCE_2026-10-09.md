# Normal-workflow performance — 2026-10-09

The local GUI now uses indexed candidate sampling, verified job-local terrain
arrays, compact atomic checkpoints, a native exact approach solver, write-triggered
display-cache maintenance, shared lidar decoding and verified saved-run metadata
reuse. Historical engine source and
preservation hashes remain unchanged. No candidate count, radius, resolution,
scoring coefficient, access label or scene fidelity was reduced.

Measurements and samples are in [PERFORMANCE_2026-10-09.json](PERFORMANCE_2026-10-09.json).
The baseline was the clean local checkout at
`8c2d277daa05c761124b2cacd5b5b9f1e8ed0674`; its original GUI package was copied to
`/tmp/huntmaps-performance-5yaetjgo/reference` before edits. No changes were pushed.

## Computer and measurement boundaries

The computer has an AMD Ryzen 7 5700G, eight cores / sixteen threads, up to
4.673 GHz, about 14 GiB usable RAM, and a Samsung MZVLW256HEHP 238.5 GiB NVMe
Ubuntu drive. The project filesystem is ext4 with 234 GiB capacity and about
97 GiB available after the disposable measurements. Ubuntu is 22.04.5 LTS.
Hardware was read with `lscpu`, `free`, `df`, `findmnt` and the Ubuntu device's
sysfs model. No Windows/Data filesystem was accessed. No packages were installed
and no system settings or kernel caches were changed.

All Python work uses `.venv/bin/python`. Its existing NumPy 1.26.4, SciPy 1.14.1,
GDAL 3.4.1, laspy/lazrs and Ubuntu C++ compiler were sufficient. The tiny shared
library builds inside configurable GUI state, never into a system directory.

Benchmarks used disposable work/state under `/tmp/huntmaps-performance-5yaetjgo`.
Saved real-area inputs were read only. Downloads were zero; provider availability
and live transfer throughput were not measured. Cold means an empty application
cache/workspace, with the operating-system page cache left alone. Warm means
reusing the same validated checkpoint, tile, native library or scene bundle.
Three unprofiled repeats determine the medians. Search profiling ran a separate
fourth repeat, excluded from timing statistics. Some acceptance checks ran on
other cores during calculation measurements, so CPU-frequency and background-load
variation limit small differences. Final 150/600 comparisons ran baseline and
optimized jobs consecutively with identical settings.

`resource.getrusage` records wall time, CPU time and cumulative peak RSS. CPU
100% means one logical core, not the entire computer. Peak RSS is a process
high-water mark, not an incremental stage allocation. Compiler child usage is
recorded separately. Browser session CPU includes waited test/browser children;
server CPU and `/proc` memory are recorded separately. Short browser interaction
timings do not provide isolated per-frame CPU percentages.
An optional `--browser-cpu-profile` samples live descendant processes every
100 ms, including Chrome renderers that are absent from `getrusage` child totals.
Its RSS sum counts shared pages in each process and is an upper estimate of
physical memory, not an application-worker RSS measurement.

## Before and after

Seconds, median; stage-specific improvements do not imply the same whole-app gain.

| Calculation / cache state | Before | After | Ratio |
| --- | ---: | ---: | ---: |
| Real setup preparation, 150 | 1.096 | 1.150 | approximately unchanged |
| Real candidate generation, 150 | 0.254 | 0.233 | 1.09× |
| Real scoring, 150 total including refinement | 3.285 | 2.840 | 1.16× |
| Real setup preparation, 600 | 1.086 | 1.085 | approximately unchanged |
| Real candidate generation, 600 | 0.700 | 0.267 | 2.62× |
| Real scoring, 600 total including refinement | 16.660 | 9.300 | 1.79× |
| Real checkpoint reuse, 600 | 0.888 | 0.368 | 2.41× |
| Synthetic 4,000-candidate sampling | 43.741 | 0.824 | 53.11× |
| Real coverage tile, first request | 0.253 | 0.219 | 1.15× |
| Real coverage tile, repeated request | 0.202180 | 0.000478 | 423× |
| Real coverage tile, warm switching | 0.213196 | 0.000485 | 440× |
| Real approach grid preparation | 0.062 | 0.065 | approximately unchanged |
| Real approaches, three objectives, warm library | 1.976 | 0.112 | 17.72× |
| Synthetic larger approaches, three objectives | 16.406 | 0.243 | 67.58× |
| Real lidar crop, three observers | 25.505 | 9.513 | 2.68× |
| Terrain-only scene creation, per observer | 2.990 | 3.152 | approximately unchanged |
| Terrain-only cached scene verification | 0.054 | 0.063 | approximately unchanged |
| Full real lidar scenes, three observers | 162.302 | 162.071 | approximately unchanged |
| Real saved-run lookup, warm | 0.0560 | 0.0109 | 5.11× |
| Offline map first load | 11.972 | 6.029 | 1.99× |
| Offline map first visit to another setup | 2.897 | 1.418 | 2.04× |
| Offline map return to retained setup | 0.164 | 0.189 | approximately unchanged |
| Prepared real scene opens, 2.7 million triangles | 24.716 | 6.844 | 3.61× |
| One-foot observer move in that prepared scene | 1.030 | 0.364 | 2.83× |

The final small-search gain is modest: earlier runs varied from roughly 1.8 to
3.2 seconds for optimized scoring as load/frequency changed. Full lidar-scene
runs ranged 150–167 seconds before and 155–178 seconds after. Neither the large
sampling speedup nor the decoding speedup is a claim about total preparation.

Most calculation stages used approximately one core (95–100% CPU). Peak RSS
before/after was 325/347 MiB for the 600-location scoring process, 276/237 MiB
for large sampling, 211/212 MiB for tiles, 150/139 MiB for real approaches,
225/158 MiB for larger approaches, 429/420 MiB for lidar crops, and 785/799 MiB
for full lidar scenes. The first native real-area search took 0.483 seconds
including compilation, versus the 0.112-second warm median. The larger cold
search took 0.639 seconds, with about 155 MiB compiler-child peak RSS.

The browser comparisons use the same frontend, offline saved area, fresh server
state and Chrome/SwiftShader settings. Maps exercise real coverage tiles without
request interception, separating first visits from returns retained in the browser.
The scene journey uses the existing full prepared A0075 geometry: 2,708,326
triangles, 11 initial binary requests, zero extra geometry requests after movement,
zero idle draws and no page errors in every before/after repeat. No geometry or
resolution was reduced. Browser heap and desktop/900 px screenshots are retained.
Server peak RSS was 427/432 MiB before/after. Map-session server CPU fell from
about 123% to 94%, and scene-session CPU from about 102% to 62%. A separate live
Chrome-process profile measured about 697%/847% browser CPU for map/scene sessions
(roughly seven/eight logical cores), with peak summed RSS 1,357/1,770 MiB; shared
pages are counted repeatedly in those sums. This exposes remaining software
rendering work rather than physical GPU performance.

## Fixtures and profiling

Real search preparation reads `results/soap-creek-v1/scouting.json` and its
existing sources and observer polygon: EPSG:32613, 10 m cells, 2,000 m viewshed
radius, seed 5403, 1.7 m eye and 0.8 m target height. Only the disposable work
path, requested 150/600 count and existing search settings are supplied. The
existing nearby-refinement calculation remains enabled: 120 initial plus 30
nearby locations for a 150 budget, and 480 plus 120 for a 600 budget. These are
150/600 total scored locations, not extra evaluations beyond the request.
Normal production jobs
continue to use their own inputs; these saved fixtures are not dependencies.

Real tiles use A0075/V010/V008 from `soap-creek-decision-review-v2`, with 12,000
tiny disposable files representing a long-lived cache below its budget. Real
approaches use the saved DEM/tree/shrub layers on a 4 km square at the existing
20 m solver resolution. The destination is the nearest valid travel cell to the
selected saved location; the initial location exceeded the travel slope limit.
The larger 8 km square fixture retains 20 m resolution, adds unknown cover and
uses the same three objective calculations. The sampling fixture has a
1,000-square 10 m grid, 64 km² eligible interior and 4,000 requested locations
with 100 m spacing. It measures sampling rather than 4,000 viewsheds.

Real lidar uses the existing 71 MB `local_A0031.laz` for A0031/V002/V004, retaining
about 3.2/3.5/3.1 million returns. All three full scenes were prepared from
scratch three times, under the existing 1,536 MiB address-space guard. Initial
zero-point lidar and no-path approach fixture attempts were excluded; corrected
fixtures require nonempty returns and positive paths. Their diagnostic artifacts
remain alongside the measurements.

The original 600-search profile spent most Python time serializing the growing
pretty-printed checkpoint every batch. It also made 635 full DEM-validation
calls and repeatedly loaded layers/gradients. Compact checkpoint encoding removes
most of that repeated Python encoding work. Job-local input reuse removes
per-observer validation reads without changing GDAL's viewshed engine.

A separate real A0031 scene profile took 61.8 profiled seconds: connected-foliage
enrichment 31.9 s (surface construction 29.1 s), crop/decode/transform 11.6 s,
and fine-ground triangulation 9.8 s. These profiled values locate work and are
not used for the before/after table. Remaining cold-scene cost is primarily
geometry preparation. Final search cost includes visibility-mask processing,
unchanged model components and final human-readable exports.

Actual browser timings exposed another repeated operation: every `Run`
construction resolved roughly 500 manifest paths. Its warm constructor originally
took about 55 ms, with 1,023 path-resolution calls in a profiled lookup. Reusing
verified manifest path maps cuts that to about 11 ms while retaining path safety
checks. The final standalone catalog benchmark compares the complete summary,
three measured candidate breakdowns and all resolved integrity records: exact
across four before/after outputs. Its cold construction is a single diagnostic
sample (0.156/0.115 s), rather than a repeated cold timing claim.

## Implementation and integrity

- `display_cache.py` skips inventory/priority reads/sorting on ordinary cached
  hits. New assets, first use, changed budgets, other-process write markers and
  deferred pressure trigger maintenance. Inventory returns immediately below
  budget. Existing maintenance locking, pins, active-job pause, dismissal/viewing
  priorities and LRU behavior remain. Pinned over-budget files cause a later
  retry. All display writers signal growth.
  Write markers are announced before allocating assets, so failed writers leave
  a maintenance signal; explicit nanosecond marker times avoid coincident coarse
  filesystem ticks. The existing configured budget (2 GiB default) is unchanged.
- `sampling.py` uses spacing-width buckets and selects the lowest accepted
  matching index across neighboring buckets. RNG calls, strict spacing,
  acceptance order, provenance merging, IDs and exhaustion messages match the
  frozen generator. Smoothing, gradients and categories are reused across spacing
  retries. Obstruction DEM, observer eligibility and target masks remain separate.
- `evaluation.py` loads verified terrain, layers and gradients once per job.
  It executes the frozen component function with a job-local viewshed boundary;
  there is no global engine monkeypatch. Initial full hashes, aligned grids,
  per-batch inode/size/mtime/ctime checks and final full derived-input hashes
  prevent stale publication. Existing worker source/product integrity guards
  remain. Checkpoints retain atomic replacement, fsync and recovery semantics;
  only their JSON whitespace changes.
- `approach_dijkstra.cpp` runs the existing directed reverse Dijkstra with the
  same double arithmetic, libm operations, neighbor order and heap ties. Barriers,
  corner restrictions, exclusions, directed climb costs and unknown-cover
  penalties remain. Bounded native steps return to Python for cancellation.
  Builds are locked, atomic, source/flag/architecture keyed and checksum verified.
  Missing compiler or unsupported float32 arithmetic uses the retained Python
  implementation. Corrupt libraries stop intact.
- `lidar_batch.py` decodes/transforms each shared source once and preserves return
  order in anonymous temporary observer spools. The aggregate spool cap is
  384 MiB; exceeded capacity falls back to unchanged sequential preparation.
  Source mutations never fall back. Classes, units, datum checks, support radius,
  eight-million-point guard and scene meshes remain. Cancellation closes spools.
  Scenes still prepare sequentially within existing memory/time/storage limits.
- `catalog.py` reuses resolved manifest paths, not mutable `Run` instances or
  unverified source arrays. Small manifest contents are read on every lookup and
  are part of the exact cache key. Parent directory and leaf inode/type checks
  invalidate changed paths; existing symlinks use uncached resolution. Selected
  source checks remain, with device/inode/ctime added to their checksum-cache keys.
  Scene and waypoint file verification use the same stronger keys.

New checkpoint, saved approach and new shared-crop scene identities fingerprint
their implementations. New result manifests seal the added helpers. Incompatible
checkpoints stop before rewriting their work; retain them and start a new run.
Previously published results and scenes remain readable. Verified current-version
scene bundles can retain their original identity/assets rather than being rebuilt
solely because the crop implementation changed. The preserved engine source,
manifest and expected hashes were not rewritten.

## Correctness and verification

All three before/after repeats matched exactly for candidate JSON bytes, real
150/600 pools/scores/patches/recommendations/overlap, every visibility TIFF hash,
complete real/synthetic approach results, ordered lidar return hashes/histograms/
vertical references, and every generated full-scene asset hash/ground value/class
count. The three real coverage PNGs also match byte for byte. There is no numerical
tolerance hiding a difference.

Ten new regressions exercise the frozen sampling/evaluation oracles, earliest
matching-neighbor provenance, multiple seeds, strict spacing, exhaustion,
same-size/same-mtime corruption, layer changes, cached hits, other-process growth,
budget/pin release, all native distances/successors/complete pinned paths,
rough/flat ties and unknown cover, concurrent builds, cancellation and recovery,
compiler/float32 fallback, binary corruption, multi-source/chunk lidar order,
capacity fallback, cancelled spool cleanup, changed sources and immutable scene
reuse/corruption. Manifest content changes, introduced escaping symlinks,
independent mutable copies and same-mtime atomic file replacement are also covered.
The new regression initially exposed coincident filesystem timestamp ticks;
manifest cache identity now includes exact bytes, and the file-cache ctime fixture
advances past one tick before changing its bytes. Existing search interruption tests still inject actual batch
failures and verify checkpoint recovery.
The cache-crash fixture initially expected a 300 MiB sparse partial to exceed
the budget; the current default is 2 GiB, so that fixture failed. It now exceeds
the actual configured budget using a sparse file, without lowering the production
budget or writing bulk data. The ordinary cached hit enforces cleanup afterward.

`./gui/check` passed all 20 offline browser journeys, 160 backend tests, formatting,
type checking/build and the actual isolated 600-location recovery worker through
all three workflow stages. Final full-suite diagnostics:
`/tmp/huntmaps-check-ii5t7xud`. Following the additional cache-crash verification,
`./gui/check --skip-browser` passed all 160 backend tests and formatting/build:
`/tmp/huntmaps-check-8ijfh6an`. New benchmark scripts also passed Black, Node
syntax and Prettier checks. Desktop/900 px map and scene screenshots were inspected.
Both isolated suites reported zero protected changes across 11,819 inventoried
files. The existing Matplotlib installation emits an Axes3D import warning;
these workflows and checks passed without needing that projection.

A separate final full-content comparison against the startup snapshot found
zero changes across 11,821 protected files (including launchers) and 500 owner
record/bundle files. The original preservation manifest audit also returned no
changes. `./scout verify --name soap-creek-v1` passed. Evidence:
`/tmp/huntmaps-performance-5yaetjgo/preservation-final.json`. Engine code,
historical results, imported/manual coordinates, annotations and prepared scenes
remain intact. No unavailable required fixture or failed final check was hidden.

## Remaining work and hardware

Setup clipping/warping was already short and remains essentially unchanged.
Retained map returns were already fast, and their 25 ms difference is not an
improvement claim. Final exports, vegetation/ground geometry, source-path checks
and software rendering still consume CPU. Additional worker
processes were not added: the measured full-scene worker approaches 800 MiB RSS,
so two concurrent meshes could exceed the existing aggregate guard. Deterministic
native work and removal of redundant decoding provide bounded gains first.

These measurements do not justify buying more RAM or replacing the Ubuntu SSD:
the application has ample available memory/storage and its largest tested worker
remains below 800 MiB RSS. A faster CPU could reduce remaining geometry work, but
the observed gains primarily came from algorithms and redundant work. Headless
browser scene rendering uses SwiftShader, so it does not establish whether a
physical GPU upgrade would help the normal desktop. No purchase recommendation
is supported by these tests.

To reproduce offline measurements with existing saved fixtures:

```sh
.venv/bin/python gui/performance.py search --count 600 --repeats 3 --output /tmp/huntmaps-perf-new-search
.venv/bin/python gui/performance.py sampling --repeats 3 --output /tmp/huntmaps-perf-new-sampling
.venv/bin/python gui/performance.py approach --repeats 3 --output /tmp/huntmaps-perf-new-approach
.venv/bin/python gui/performance.py tiles --repeats 3 --output /tmp/huntmaps-perf-new-tiles
.venv/bin/python gui/performance.py lidar --repeats 3 --output /tmp/huntmaps-perf-new-lidar
.venv/bin/python gui/performance.py scene-lidar --repeats 3 --output /tmp/huntmaps-perf-new-scenes
.venv/bin/python gui/performance.py browser --repeats 3 --output /tmp/huntmaps-perf-new-browser
.venv/bin/python gui/performance.py catalog --repeats 3 --output /tmp/huntmaps-perf-new-catalog
./gui/check
```

Use a fresh output directory per invocation. `--package PATH` selects an original
GUI snapshot for baseline comparisons; protected engine code stays in this project.
No real-area source is downloaded by this harness. Missing saved fixtures fail
visibly rather than being replaced with synthetic evidence.
