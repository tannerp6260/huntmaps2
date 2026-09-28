# What to supply next

No hunter-selected polygon or manual point set was found in this workspace. Existing
GPX/GeoPackages are model outputs; agency GMU/range polygons are not your chosen AOI.
Soap Creek has not been selected or given an invented boundary.

Supply **two files**, preferably together, before reviewing new automated results:

1. **Observer-search polygon**: a valid WGS84 / EPSG:4326 GeoJSON Polygon or
   MultiPolygon (`observer_area.geojson`). Draw the area where you actually want to
   consider glassing setups, including your manual positions. It need not follow a
   square or include distant target slopes. Do not draw it as a target-visibility
   clipping boundary. A disconnected MultiPolygon is supported. Start bounded—roughly
   10–50 km² if practical; intake checks the resulting buffered grid against the budget.
2. **Your manual glassing waypoints**, exported unchanged as a GPX waypoint file
   (`manual_points.gpx`, not just a track), GeoJSON Points, or CSV. Each waypoint needs
   a unique name/ID. CSV requires `id,longitude,latitude` (WGS84 decimal degrees,
   longitude first; western Colorado longitudes are negative). Extra columns such as
   selection date, rationale and anticipated approach are retained. Do not rename
   model-generated points and call them manual selections.

If your app supplies a KML/KMZ polygon instead, send that original file and identify
which polygon is the intended search area. It will need an explicit geometry-only
conversion to GeoJSON before the current intake command; KML/KMZ polygon import is
not claimed as implemented. Keep the original export for provenance. A screenshot
alone is insufficient to define a reproducible study boundary.

No trailhead, camp or personal trip dates are required to submit the area. Optional:
include target restrictions/permission polygons and any *documented* entry options
that matter. Keep ownership, observation permission and follow-up/stalking permission
separate. You do not need to prepare DEMs, vegetation rasters or imagery yourself;
source acquisition is the next task once your actual boundary is known.

For files placed directly in the workspace:

```text
inputs/hunter/observer_area.geojson
inputs/hunter/manual_points.gpx
```

Then run from `/home/tanner/Desktop/huntmaps2`:

```sh
.venv/bin/python -m glassing.transfer intake --config configs/transfer.template.json
```

For CSV or GeoJSON points, edit only `manual_points` in a copy of that config. Record
who selected the points and any known selection date in `manual_provenance`; unknown
is acceptable. The importer retains original IDs, coordinates, attributes and source
checksums. Points outside the chosen observer domain cause an explicit error rather
than being snapped/moved or silently dropped. Original manual coordinates are kept
in GPX/GPKG; DEM ground is still discretized at the configured resolution.

Intake writes `runs/hunter_transfer/intake.json` and, when both files exist,
`manual_import.json`. It separates observer domain, buffered observation targets,
terrain halo and a broader access-data query extent. It does not download data or
assume Soap Creek is better than another area. After intake, the data acquisition
step will fill the source descriptors and obtain surrounding entry/access evidence.

**Exact current blocker:** your observer-search polygon and your manual waypoints.
No new-area runtime, imagery review, access result or manual-versus-automated hunting
benefit can be reported before those inputs arrive.
