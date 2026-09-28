# Start here

## Existing Ubuntu workspace

Open a terminal in `/home/tanner/Desktop/huntmaps2`:

```bash
./scout doctor
mkdir -p inputs
```

Save your hunting-area polygon as **inputs/my-area.geojson**, `.kml`, or `.kmz`.
Draw where you would consider **standing to glass**, not a clipping boundary around
every target slope. Terrain and target support extend up to the observation radius
beyond observer positions. Begin with a bounded area, roughly 10–50 km²; buffered
raster size is limited to 3 million cells by default. No area is selected for you.

```bash
./scout run --area inputs/my-area.geojson --name my-area
```

For multiple polygons, the command lists names and numbers. Repeat with
`--polygon 2`, for example, or `--polygon all` to deliberately combine them.
Originals are copied without alteration to `results/my-area/originals/`.

Existing authoritative data in `data/**/manifest.json` are checked for coverage and
checksum. If incomplete, read **results/my-area/DATA_REQUIRED.md** and
**download_plan.json**, then repeat:

```bash
./scout run --area inputs/my-area.geojson --name my-area --download
```

The estimated bulk size prints before downloads; the default cap is 600 MB, below
2 GB. Catalog metadata requests can occur without `--download` (at most 5 MB per
catalog response); bulk data require that flag. `--max-download-mb 900` changes the
cap explicitly. Partial runs can resume using the same area and name. Completed
runs are preserved: choose a different name for another analysis.

No paid service is used. Supported automatic sources are single-tile USGS 3DEP
1/3 arc-second DEM, USGS RCMAP 2023 tree/shrub/herb cover, and Colorado CPW summer/
winter range polygons. Agency query truncation and corrupt inputs fail visibly.
Multi-tile DEM mosaics and non-Colorado seasonal source selection still need an
explicit source descriptor. Service failure is a data problem, not a closure finding.
No bulk acquisition has been validated for your area until you supply that polygon.

## Results

Open **results/my-area/REPORT.md**, **overview.png**, and **review_packet.pdf**.
The PDF has one card per leading opportunity: selected sectors, 500 m bands,
visible area, cover/foreground proxies and explicit unknowns. It uses actual imagery
only when supplied; otherwise it says **IMAGERY PENDING** and shows terrain.

- `review.gpx`: provisional observer waypoints, not routes.
- `sectors.kml`: simplified viewing/inspection footprints, including hidden terrain.
- `comparison.gpkg`: analysis layers for QGIS, with observer and target roles separate.
- `components.csv`, `overlap.csv`: separate scores and pairwise shared terrain.
- `scouting.json`, `acquisition.json`, `analysis/execution.jsonl`: configuration,
  source cost and measured runtime/peak memory.

Imagery, ownership/entries/routes and legal-access evidence are **not automatically
acquired** by this entry point. They are optional checked inputs. Without them,
approach effort is pending and no field-ready access claim is made. Provisional
terrain opportunities remain available for review.

```bash
./scout verify --name my-area
```

This checks only the current run and its sources/code, never ignored historical
archives. A corrupt current file is an error; missing old archives are irrelevant.

## Optional manual comparison and settings

```bash
./scout run --area inputs/my-area.geojson --manual inputs/my-points.gpx --name comparison
```

Manual points can be GPX waypoints, WGS84 GeoJSON Points or CSV with
`id,longitude,latitude`. Use unique IDs; points must lie inside your observer area.
Their coordinates and provenance are retained. Automated candidates are generated
without using manual points as seeds. Agreement is not independent proof of value.

For editable settings, use:

```bash
./scout prepare --area inputs/my-area.geojson --name configured
```

Edit `results/configured/scouting.json`, then run the same area/name with `run`
instead of `prepare`. Configuration exposes radius (multiples of 500 m), season,
observation minutes, hiking preferences, resource caps and source locations. The
inherited hunt context is GMU 54 second rifle 2026; personal trip dates remain unset.
Old sun angles remain hypothetical. No new model coefficients are introduced.
To start from another configuration use `--source-config path/to/config.json`.
Paths are relative to the project root; the launcher always uses that root.

Required `data.dem/tree/shrub/herb/summer/winter` descriptors contain `path`,
`sha256`, `provider`, `acquisition_date`, `license`; DEM also requires
`vertical_units: "m"` and `vertical_datum`. Unknown metadata must be stated, not
invented. Use `sha256sum path/to/file` to get a checksum. Vegetation is percent cover;
range polygons are WGS84 GeoJSON. `data.imagery` is a list of checked raster
descriptors with acquisition dates. Access schema details remain in
[transfer INPUTS](docs/glassing/transfer/INPUTS.md); that document's mandatory-manual
rule applies only to the historical matched experiment.

## Fresh clone without historical runs

Do not copy `runs/`, system GIS libraries or the old `.venv`. Install an isolated
native GIS environment using an existing conda/micromamba installation:

```bash
micromamba create -p "$PWD/.scout-env" -f environment.scout.yml
export SCOUT_PYTHON="$PWD/.scout-env/bin/python"
./scout doctor
"$SCOUT_PYTHON" -m unittest discover -s tests -p test_owner.py -v
```

See the [official micromamba installation guide](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)
if it is not installed. Installation is an explicit user action, with no sudo or
system Python changes. Conda can use the same environment file. The environment
file permits GDAL 3.4–3.x; record the resolved version per run. A new solver/install
has not been performed on this workstation. The isolated archive-free journey was
verified with the existing interpreter. `doctor` checks imports, Shapely's required
API and GDAL viewshed/GeoTIFF/GeoPackage support rather than assuming availability.

Only the owner test is archive-independent; historical regression tests can require
ignored fixture runs. Synthetic test artifacts in `/tmp/scout-journey-*` are engineering
fixtures, not real-area recommendations. After tests, supply **your polygon** and
follow the same run/download steps above. No centroid crop is substituted.
