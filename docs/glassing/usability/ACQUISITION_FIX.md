# Soap Creek acquisition correction

The actual command `./scout run --area ./inputs/test.kml --name soap-creek-v1 --download`
now completes. Current-run verification passes. The owner polygon, all non-data
configuration, scoring coefficients and historical evidence remain unchanged.

## Diagnosis from the real response

Required analysis bounds in EPSG:32613 were `[296770,4280330,307330,4291880]`,
1056 × 1155 cells at 10 m. The original WCS request used these same bounds and
requested 30 m pixels, EPSG:32613. The response was 371 × 403 cells with origin
`296475.2541474934,4292142.792798241`, pixel size
`30.0102401981,-29.9618043324` m. Returned outer bounds were
`[296475.2541,4280068.1857,307609.0533,4292142.7928]` in the correct CRS.
Thus its rectangular footprint already enclosed the analysis grid. A containing
rectangle is not evidence of complete valid samples.

The byte raster declares **NoData=101**, outside valid percent-cover values 0–100.
It had 8,040 source NoData cells. Of the source cell centres within the requested
rectangle, 754 were NoData: 71 connected to the source boundary and 683 internal.
On the analysis grid, 6,792 cells were unknown; edge counts (north/south/west/east)
were 9/51/47/83. The old 32×32 `covers()` probe found four missing samples, at
rows/columns (3,24), (5,19), (12,17), (20,25): **all interior probe locations**.
It therefore rejected internal vegetation NoData as though the source failed to
cover the area. That was the immediate acquisition failure.

WCS reprojection/alignment also leaves boundary artifacts. A separate request,
aligned outward to 30 m and padded by 120 m, was obtained to keep the required area
away from the service's crop/reprojection boundary. It returned 381 × 412 cells,
origin `296338.16677628004,4292279.516445677`, pixels
`29.96639731049,-29.99516015093` m and bounds
`[296338.1668,4279921.5105,307755.3642,4292279.5164]`. The service does not return an
exact requested 30 m grid; local preparation still establishes the common 10 m grid.

The padded tree response has 6,705 unknown analysis cells (0.5497%); edge counts
are 0/18/0/0. It still fails the old probe (five missing samples), confirming that
padding alone does not solve internal NoData. The two responses have different
sampling grids, so the net 87-cell change cannot all be attributed to clipping.
Internal source gaps are retained without inventing their cause or assigning zero
cover. Shrub and herb have the same 6,705-cell unknown footprint. The prepared
unknown mask has 4,841 unknown cells among 918,842 target cells (~0.527%). Prepared
vegetation retains -9999 there. Existing scoring's explicit unknown flags and
preexisting nonzero scenario defaults remain unchanged; unknown is not open terrain.

## Small acquisition-adapter correction

`owner_data.coverage()` reports CRS, source dimensions/geotransform/bounds, declared
NoData, required grid, geographic footprint, full-grid unknown counts/fraction and
boundary counts. Geographic footprint coverage is checked independently from pixel
validity. DEM checks still require valid obstruction data; vegetation can have
explicit unknowns. Download diagnostics print in the terminal and persist as
`tree_coverage.json`, `shrub_coverage.json`, `herb_coverage.json`.

New WCS filenames are `*_padded120.tif`, so the failed `tree.tif` is never silently
reused or overwritten. It remains in `downloads/`, with its original manifest entry.
Replacement URLs, bounds/padding, retrieval timestamps, byte sizes and SHA256 hashes
are recorded in `downloads/manifest.json` and source descriptors. The original failure
notices/configuration/plan and first-resume log are retained in `diagnosis-original/`.
Fetcher counts the retained failed response against the same 600 MB budget.

## Additional real-source blockers resolved

CPW responses explicitly declare legacy `crs: EPSG:4326`, rejected by the strict
RFC7946 polygon importer. The acquisition adapter now writes separate WGS84-normalized
copies only for that explicitly recognized CRS; unfamiliar CRSs still fail. Raw agency
responses and their checksums are retained as nested source provenance.

The summer response additionally contained invalid nested MultiPolygon shells.
GEOS `make_valid` repairs are recorded with their reason and before/after planar
area diagnostics; those degree² values are not habitat-area scores. Only valid
polygonal results are accepted. Rasterizing raw and repaired summer geometry on this
run's grid changed **zero cells**. The winter service returned a valid empty collection,
retained as an agency response, not fabricated winter habitat. No owner geometry was
repaired, shrunk or altered.

## Completed evidence

- Successful resumed analysis: 150 automated candidates, zero manual points;
  five exported alternatives: A0031, A0075, A0140, A0081, A0139.
- Engine wall time **5.30 s**, observed peak RSS **243.65 MiB**; analysis + owner handoff
  **6.35 s**. No claim about field performance.
- New successful acquisition **1,778,140 bytes**. Including the preserved original
  590,770-byte tree response, total retained downloads **2,368,910 bytes**, $0,
  below the unchanged **600,000,000-byte** cap. Final acquisition.json reports zero
  *additional bytes on the final resume*; prior attempt costs are in
  diagnosis-original/padded-acquisition.json and downloads/manifest.json.
- GPX/GeoPackage read-back and KML geometry checks pass: five points, sixteen sector
  polygons, EPSG:32613 analysis layers.
- `./scout verify --name soap-creek-v1`: **passed**.
- `.venv/bin/python -m unittest discover -s tests -v`: **34 passed**, 9.85 s.
  New regression tests cover NoData=101 versus missing geography, strict DEM gaps,
  preserved unknown cover, explicit agency CRS normalization, retained raw bytes,
  nested-shell repair and rejection of unknown CRSs.
- All 6,326 earlier evidence hashes unchanged; `git diff --check` clean.
- Actual overview inspected: owner polygon and expanded target support remain distinct.
  Imagery and documented access remain explicitly pending, not fabricated.

Outputs: `results/soap-creek-v1/REPORT.md`, `overview.png`, `review_packet.pdf`,
`review.gpx`, `sectors.kml`, `comparison.gpkg`, component and overlap CSVs. Full
analysis masks, source provenance and per-point diagnostics remain under that folder.
