# Completed vegetation handoff — 2026-09-30

The interrupted session had already produced an ignored v1 experiment. This completion
preserves it and delivers `results/soap-creek-vegetation-v2/REPORT.md`, a25-page
`vegetation_review.pdf`, `fine_lidar_review.png`, component/sensitivity/overlap tables,
masked tree-class rasters and provisional original/alternative GPX/KML waypoints.
The reusable renderer derives conclusions from data; historical review_maps.py now
also computes overlap text instead of embedding Soap Creek candidate conclusions.
Normal scouting scores and frozen model code are unchanged.

Completed150 originals and52 in-domain setup alternatives with recomputed bare-earth
viewsheds. A0031's4.89796% mean reproduces exactly within floating precision from the
legacy70×70m square; maximum source/sample difference2.7e-9. No unit or prepared-grid
sampling mismatch found. This establishes sampling consistency, not product accuracy
or a ground-level opening. Delivered WCS pixels are already reprojected; source dates
2023 cover versus2019 imagery and coarse resolution limit interpretation.

Target-searchability versus matched distance-only arms share2/10 leading original
points. The optional20% directional screen zeros90/150 original scores (40% zeros53).
The leading local alternative isV010 fromA0075; this is an assumption-sensitive
review opportunity, not demonstrated superior hunting performance. Low-cover original
parents outside the prior top five also remain in the review/table. Habitat is excluded
from both matched detectability arms; inherited searchability is applied once.

One cached71,291,641-byte2019 USGS lidar tile supports a local2m return-column
sensitivity. No new bulk source download in this completion. Metadata/point CRS record
NAD83(2011)/Conus Albers + NAVD88 Geoid12B metres. Native point spacing is variable;
2m is a derived grid. The centred301×301 grid spans602m (one2m edge-cell difference
from the protocol's nominal600m bound, explicitly recorded rather than claiming600m).
26.2% of the local grid is unknown. Fifty sampled rays are clear on local ground;
half/full return columns leave9/0 respectively. Solid columns are deliberately
conservative scenarios, not a model of crown gaps or below-canopy optical transmission.
No extrapolation to full2km vegetation-visible acreage is made.

Verification:

- `.venv/bin/python -m unittest discover -s tests -v`:39 tests pass,9.710s.
  Vegetation cases cover open view, nearby obstruction, below/above intermediate
  rays, target concealment, missing data, raised ground and behind-observer trees;
  directional footprints and unknown reward bounds also pass.
- Final available-data command completes in30.89s,723.33MiB peak RSS,42.18MB outputs,
  within900s/1536MiB/500MB caps. Original150 areas match saved scores within1e-9km².
- Fresh-output repeat in `/tmp/soap-creek-vegetation-repeat-20260930`:30.03s,
 731.29MiB. Ten checked numerical/GIS/export files are byte-identical: components,
 directional diagnostics, coarse-ray scenarios, low-tree overlap, GPX, KML, observer
 audit, matched-rank stability and both local ground/column rasters.
- Current114 output hashes and419 immediate baseline/review/v1 preserved-file hashes
  verify. All6,326 earlier usability-preserved historical files remain unchanged.
  `./scout verify --name soap-creek-v1` passes; `git diff --check` is clean.
- GPX read-back checks coordinates within1cm of projected points. All25 map pages
  reviewed as a contact sheet; source audit, leading alternative, directional page
  and fine-data comparison also inspected at larger resolution. Imagery remains
  unobscured in paired panels; additional candidates without cached clips are labeled
  imagery pending. PDF page count confirmed. Matplotlib's existing Axes3D warning
  remains harmless for these successfully rendered2D maps.

Run instructions and full handling audit: README.md. Detailed outcome report:
`results/soap-creek-vegetation-v2/REPORT.md`. No commits/pushes or generated/data files
added to Git. Stop at this desktop handoff. Branches/within-cell openings, longer
sightline crown gaps, current vegetation, actual target detection and legal/physical
approaches remain unresolved; no field validation or route work started.
