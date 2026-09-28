# Evidence checkpoint — 2026-09-25

The standalone component passes its offline engineering checks and produces a
real-area terrain baseline. It has not demonstrated better scouting, practical
access, inspectable deer, planning-time savings, or hunting effectiveness.

## Trial and spatial preparation

CPW GMUID=54 was dissolved in EPSG:32613. Its projected centroid was rounded to
10 m, an 8 km square was centred there, and the square intersected with the unit.
The entire square lies inside the supplied unit: 64.000 km². Exact bounds are
E 311500–319500 m, N 4275720–4283720 m; these are derived coordinates, not invented
boundary vertices or recommended locations. The polygon and source checksum are
in [provenance/pilot.json](provenance/pilot.json).

The 10 m analysis grid has 1404 × 1404 cells, with a 3020 m halo on each side.
Bare-earth terrain retains everything in the rectangle, regardless of observer or
target masks. Input NAD83 geographic 1/3 arc-second samples were bilinearly warped
to UTM 13N; masks use cell centres, with no continuous-mask interpolation. Scores
use 100 m² per cell, not pixel counts or slope surface area. Target mask area is
64.000 km². Elevations span 2532.0–3945.9 m; no voids or nonfinite elevations occurred.
NoData is a hard preparation/visibility error, including voids outside target masks.

Selected USGS tile: `USGS_13_n39w108_20220331.tif`, 415,482,393 bytes.
The catalog's tile-specific description states metres, NAVD88 over CONUS, NAD83
horizontal coordinates, and public-domain status. The GeoTIFF itself lacks a
vertical CRS tag; vertical interpretation comes from the provider catalog. The
2022-03-31 publication date is not an acquisition date; acquisition ages within
this seamless tile remain unknown. No vertical datum transformation was performed.
Bilinear resampling cannot restore small ridges or establish sub-metre accuracy.

CPW source geometry is mapped from 1:24,000 sources, with agency attribution and
as-is terms archived in cpw_item.json. It establishes a technical unit subset,
not parcel ownership, current closures, safe footing, or a connected permitted route.

## Engine and correctness

GDAL 3.4.1 `ViewshedGenerate`, GVM_Edge, sequential execution; eye 1.7 m, target
0.8 m, curvature coefficient 6/7 (refraction coefficient 1/7). Local bindings reject
creation-option lists for this call; passing None works. Viewshed TIFFs are therefore
uncompressed, while preparation rasters use DEFLATE. No claim of agreement with
GRASS is made. The narrow `viewshed` function is the replacement boundary.
[GDAL's primary documentation](https://gdal.org/en/stable/programs/gdal_viewshed.html)
explains the projected-coordinate requirement, input NoData caveat, endpoint heights
and curvature convention. Newer cumulative-mode flags are not used with local 3.4.1.

Six tests pass (`.venv/bin/python -m unittest discover -s tests -v`):

- Flat terrain and 10/20 m grids agree with circle area to stated tolerances; changing
  resolution does not multiply area scores.
- A ridge blocks a target behind it, while a nearer target remains visible; raising
  either endpoint restores visibility. Independent bilinear profiles verify these rays.
- Excluding ridge cells from the target mask retains ridge obstruction.
- Explicit curvature changes the zero-height flat-terrain result.
- NoData, NaN, geographic CRS, horizontal feet, vertical feet, out-of-grid observer
  coordinates and insufficient halo fail explicitly.
- Acquisition selects only the pinned revision from a catalog containing historical
  alternatives (regression for this session's download error).

Independent real-terrain checks: 116/120 randomly sampled rays agree with GDAL;
41/41 cardinal rays agree. Combined: 157/161. Synthetic example: 111/120 random
and 48/48 cardinal, combined 159/168. All observed disagreements are GDAL-invisible
versus ray-visible, with real profile minimum clearances 1.31–2.38 m. The ray model
samples bilinear terrain at quarter-cell intervals and applies curvature independently;
it is a diagnostic, not ground truth. Different inter-cell surface/horizon treatments
are a plausible explanation, not a proven diagnosis. Keep these disagreements as
an uncertainty requiring a second engine or finer terrain check before field use.

Native OGR export read-back verifies 150 points, EPSG:32613 geometry, and GPX WGS84
coordinate round trips within 0.01 m. This tests serialization, not positional accuracy.
Both examples have identical DEM, candidate JSON, score JSON, CSV and GPX SHA-256
values on the repeated run. All 450 cached viewsheds were reused and verified.
GeoPackage binary equality is not required: its timestamps can differ; its native
geometry, CRS and counts pass read-back. There was no existing regression suite.

The real review image was visually inspected: ridge/valley relief is continuous,
the full buffer is present, no obvious void streaks or tile seams appear, and the
representative visibility pattern follows surrounding terrain. Jagged visibility
edges remain a raster-model limitation. This is not a field or imagery validation.

## Measurements and sensitivity

AMD Ryzen 7 5700G, 8 cores / 16 threads; Ubuntu 22.04.5; about 11 GiB RAM available
and 30 GiB disk free at audit. One worker, no GPU. Times below are final uncached
viewshed generations on already-local inputs, with the OS file cache potentially warm.
Raw measurements and repeat-run hashes are in [evidence_run.json](evidence_run.json).

| Component | Real pilot | Synthetic |
|---|---:|---:|
| Prepare | 0.593 s | 0.233 s |
| Generate 150 candidates | 0.241 s | 0.234 s |
| Visibility + score, 450 evaluations | 2.718 s | 2.636 s |
| Independent checks + PNG | 0.889 s | 0.859 s |
| Export + read-back | 0.081 s | 0.079 s |
| Sum of measured stages | 4.522 s | 4.041 s |
| Peak RSS across these stages | 322.4 MiB | 318.6 MiB |
| Active visibility cache | 84.624 MB | 84.624 MB |

GNU `/usr/bin/time -v` measured the complete repeated commands (including startup)
at 3.42 s / 333380 KiB peak RSS for real terrain and 3.04 s / 328536 KiB for synthetic.
No swap was observed. Initial network transfer time was not instrumented; do not
include the cached acquisition check (0.516 s, zero new bytes) as a download benchmark.
The supplied source tile is 415.5 MB. This session retained 1.651 GB of downloads
because the initial adapter fetched four historical versions before its guard stopped
it. Only the selected tile is used. Old development visibility caches are also retained;
physical disk usage was about 1.6 GiB data plus 514 MiB runs at final review, below
4 GB. Fresh reproduction uses about 416 MB inputs plus approximately 92 MB per run.

Real visibility/scoring time for 150 candidates was 0.498 s at 1 km, 0.820 s at 2 km,
and 1.364 s at 3 km. Corresponding raw masks occupy 6.121, 24.195 and 54.278 MB.
At the same grid/window conditions, a compute-only linear extrapolation to 1,000
2 km candidate evaluations is about 5.5 s and 161 MB of raw masks. Ten independently
processed pilot-sized batches would nominally cost about 45 seconds of measured
stages and 846 MB of masks across all three radii. These are extrapolations, not
unit-scale benchmarks: acquisition, startup, tile seams, larger candidate preparation,
slow disks and source changes are excluded. The current maximum-grid guard rejects
a large unpartitioned unit. No scalability claim or unit-wide run was made.

The highest 2 km terrain-area candidate is C0064, 3.3936 km², with shoulder/ridge-break
proxy provenance. The top ten overlap only 2/10 with the 1 km ranking and 6/10 with
3 km. Thus radius choice materially changes this baseline; these distances are
experimental settings, not universal optical limits. Minimum candidate separation
is 151.3 m real / 152.6 m synthetic; the algorithm retains terrain and background
provenance after deduplication. No manual planner points were supplied.

## Next evidence gate

Stop implementation here. Before adding habitat, glassability or optimization,
collect blinded manual choices and time spent on this same polygon, resolve connected
access and closures for a small review set, and independently audit the discrepant
terrain rays and actual setup/target visibility. Use equal access and time budgets
for a later comparison. All current candidates are UNKNOWN ACCESS and the field-ready
shortlist is empty. No field observations, calibrated deer probabilities or hunting
benefit have been inferred.
