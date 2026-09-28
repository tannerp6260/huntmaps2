# Run the terrain experiment

From `/home/tanner/Desktop/huntmaps2`, using the installed Ubuntu GIS stack:

```bash
/usr/bin/python3 -m venv --without-pip --system-site-packages .venv
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m glassing all --config configs/synthetic.json
.venv/bin/python -m glassing acquire --config configs/gmu54.json
.venv/bin/python -m glassing all --config configs/gmu54.json
```

No package installation is necessary on this computer. This environment reuses
installed GIS libraries, including existing user-site scientific packages; it is
isolated for project changes, not a hermetic binary distribution. No changes to
system Python or sudo are required. Known runtime: Python 3.10.12, GDAL/OGR 3.4.1,
NumPy 1.26.4, SciPy 1.14.1, Matplotlib 3.9.2. GDAL's Python bindings must match its
native library. Matplotlib is only needed for the inspection PNG. A harmless
Axes3D import warning reflects mixed installed Matplotlib distributions; the 2D
render succeeds. The default Conda Python is not the tested interpreter.

`all` runs these actual independently callable stages, in order:

```bash
.venv/bin/python -m glassing prepare --config configs/gmu54.json
.venv/bin/python -m glassing candidates --config configs/gmu54.json
.venv/bin/python -m glassing visibility --config configs/gmu54.json
.venv/bin/python -m glassing inspect --config configs/gmu54.json
.venv/bin/python -m glassing export --config configs/gmu54.json
```

`all` does not download. After acquisition every analysis stage runs offline.
Use a different `work` directory for comparisons. Changing configuration requires
preparation and downstream stages again; stale inputs are rejected. Viewsheds use
content-keyed caches with individual checksums. Repeating the same `all` command
recreates deterministic candidates and scores and reuses verified viewsheds.
Metrics append to `metrics.jsonl`; process peak RSS is a cumulative high-water mark,
not incremental memory per stage. The CLI caps virtual address space and command
runtime and checks source/work disk usage. Acquisition caps retained source bytes
plus new transfers; per-stage disk checks allow bounded overshoot within a stage.
The grid/candidate caps bound the trial's raster output well below the disk limit.
Native thread pools are set to one; no multiprocessing is used.

Outputs in `runs/gmu54/` and `runs/synthetic/`:

- `baseline.gpkg`: projected candidates and exact study polygon, readable in QGIS.
- `dem.tif`: 10 m bare-earth obstruction grid including the halo.
- `study.tif`, `target.tif`, `observer.tif`: aligned byte masks; 1 included, 0 excluded.
- `access.tif`: 2 unknown access, 0 outside/excluded; no cells certified accessible.
- `visibility/<content-key>/Cxxxx_<radius>.tif`: raw terrain masks, 1 visible, 0
  invisible/outside radius, 255 reserved NoData. Intersect with target.tif for scored
  area; raw visibility outside the study is deliberately retained.
- `candidates.csv`, `review_only.gpx`: ranks, area, distance bands, coordinates,
  endpoint settings, provenance and prominent unknown-access labeling.
- `field_ready_shortlist.json`: empty because no legal connected access was verified.
- `REPORT.md`, `review.png`, `sightline_checks.json`, `export_validation.json`,
  `visibility_metrics.json`, `metrics.jsonl`: evidence and diagnostics.

In QGIS add the GeoPackage and DEM, then load a candidate's radius TIFF and style
value 1 with transparency for 0. GPX uses WGS84 latitude/longitude; review imports
in your field app yourself. No onX import or field navigation certification is claimed.

Configuration paths are relative to the working directory. `manual_points` accepts
objects `{ "x": 315000, "y": 4280000, "name": "desk_choice" }` in configured projected
metres (example coordinates describe syntax, not a recommended waypoint). Points
snap to DEM cell centres; out-of-domain points fail. Manual labels survive spatial
deduplication. `observer_exclusions` and `target_exclusions` accept arrays of GeoJSON
geometry objects **in the configured grid CRS**, not standard longitude/latitude.
These modify their own masks only. No ownership/access inference is made.

Acquisition uses the public CPW GMUID=54 query and a USGS TNM product query, pins the
boundary and one 2022 1/3-arc-second tile by SHA-256, and checks all cached bytes.
The exact technical 64 km² pilot is archived in `provenance/pilot.json`; the boundary,
catalog, license text, source raster metadata and manifest are also archived there.
If the live boundary or pinned tile changes, acquisition fails rather than silently
changing this experiment. Existing verified cached inputs remain usable offline.
A fresh acquisition needs about 416 MB; this session's first adapter mistakenly
fetched extra historical revisions (1.651 GB total), documented in STATUS.md.
Those extra tiles are unused and are not required for reproduction.

No hunting-quality result is implemented. Review NUMERICAL_EVIDENCE.md and STATUS.md
before treating any terrain rank as a reason to visit a location.

The next authorized milestone is now implemented separately. See
[matched-comparison instructions](comparison/README.md) and
[its evidence checkpoint](comparison/REPORT.md). The baseline commands and original
control outputs above remain unchanged.

Corrective-validation checkpoint: see [report](correction/REPORT.md) and
[preregistered protocol](correction/PROTOCOL.md). With archived control runs present:
`.venv/bin/python -m glassing.correct all` repeats the offline corrective experiment.
New acquisition and dated imagery are explicit `acquire` / `imagery` stages; run `attention`
before first `imagery`. QGIS packet: `runs/correction/review.gpkg`. Give independent
reviewers only `runs/correction/blinded/`; analyst method keys are kept separately.

## Actual-hunt provisional scouting packet

Read [scouting report](scouting/REPORT.md) and [methods](scouting/METHODS.md).
Use `configs/scouting.json`; previous controls/configurations stay unchanged.
With the retained baseline/comparison/correction inputs, from the project root:

```sh
.venv/bin/python -m glassing.scout acquire
.venv/bin/python -m glassing.scout all
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m glassing.scout verify
```

Individual implemented stages: `support`, `fine`, `access`, `packet`.
`acquire` reconstructs/verifies `configs/scouting_sources.lock.json`, rejecting changed
remote content; archived snapshots may be needed when an official service changes.
`all` is offline and regenerates only `runs/scouting`. Configuration budgets cover
retained downloads/output disk/memory/runtime; existing environments are reused.

Start with `runs/scouting/analyst/review_packet.pdf` or `analyst/overview.png`.
QGIS: `runs/scouting/scouting.gpkg` plus `C*_restored_visible.tif`; analyst decision CSV
and support comparisons accompany them. Field review: `field_review/opportunities.gpx`,
`viewing_sectors.kml`, `entry_options.gpx`; `reserve_C0090.gpx` is separate. These are
provisional waypoints/sectors, not certified routes/parking or a tested onX import.
C0064 remains an analyst control, not a primary field waypoint. No campsite selected.

## Hunter-selected transfer

Use [transfer input instructions](transfer/INPUTS.md), [fixed protocol](transfer/PROTOCOL.md)
and [portability report](transfer/REPORT.md). New `glassing.transfer` CLI/configuration
wraps the existing terrain/scoring pipeline without modifying prior controls. The real
comparison awaits your observer polygon and manual points; no Soap Creek boundary or
replacement centroid crop has been selected. Offline verification commands and exact
source/access schemas are in [transfer README](transfer/README.md).
