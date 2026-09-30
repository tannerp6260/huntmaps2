# Bounded vegetation experiment

Completed handoff: `results/soap-creek-vegetation-v2/REPORT.md` and
`vegetation_review.pdf`; local fine-data comparison: `fine_lidar_review.png`.
Original Soap Creek scores/review and the interrupted-session v1 are preserved.
Normal `./scout` scoring is unchanged. This experiment is an optional separate CLI.

From the repository root, one command reproduces the experiment into a fresh folder:

```sh
.venv/bin/python -m glassing.vegetation_experiment --config configs/vegetation.soap-creek-v1.json --output results/soap-creek-vegetation-repeat
```

Choose a new output name for another repeat. Completed outputs refuse replacement.
Required inputs are the existing Soap Creek run, its review imagery and pinned model
lock. The configured lidar tile is already cached; the command verifies its hash.
If missing, only that pinned 71.3MB tile is eligible for acquisition within100MB.
No new imagery sweep, route optimization or normal-model change occurs.

Optional fine-data decoding uses laspy2.6.1/lazrs0.7.0 in `.cache/vegetation-deps`;
pyproj is available in the existing GIS interpreter. On a fresh environment, install
these locally rather than into system Python:

```sh
.venv/bin/python -m pip install --target .cache/vegetation-deps laspy==2.6.1 lazrs==0.7.0
```

If decoding dependencies or fine data are absent, the experiment reports that state
and completes coarse diagnostics. Native GIS setup is in ../README.md.

## Vegetation handling audit

- Acquisition: owner_data.py requests USGS/MRLC RCMAP2023 WCS tree/shrub/herb
  percent cover; Soap Creek uses padded/aligned replacements after the documented
  geographic-coverage versus internal-NoData correction. Raw downloads are retained.
  Descriptor/checksum/date records are in the baseline scouting.json and acquisition.json.
- Delivered WCS rasters are already reprojected ~30m pixels. The audit displays
  **delivered source pixels**, not an unreprojected national Landsat grid. Source
  resampling limits remain; an exact original satellite footprint is not inferred.
- transfer.prepare performs nearest-neighbor cover warp to the10m DEM grid,
  accepts only finite0–100 values and divides by100. NoData101/-9999 and invalid
  values become unknown. DEM remains strict valid obstruction ground; observer and
  target masks do not remove obstruction terrain. This experiment additionally checks
  cover dimensions/CRS/transform and viewshed resolution/origin registration.
- comparison_models.searchability assigns tree factors1/.6/.25 at10/40% cover,
  and shrub factor.75 above30%. transfer.evaluate applies it once to target rewards
  along with habitat/distance/perspective/light before attention selection. Nominal
  unknown tree/shrub values are.25/.30, with uncertainty recorded. Herb affects
  historical habitat and its broad unknown flag, not this target detectability arm.
- compare.components computes foreground mean from a square extending three10m
  cells each side plus centre:49 repeated samples spanning70×70m. Its nominal
  “30m radius” parameter does not mean a circular footprint. Foreground mean is
  exported as a diagnostic and does not penalize the normal historical ranking.
- New target/distance matched arms exclude habitat/light/perspective from both.
  Searchability integral and limited-attention index are heuristic weighted measures,
  never literal visible acreage. Known/unknown area partitions and bounds remain
  separate; target cover is not applied again to historical scores.
- Directional diagnostics are annular30-degree sectors at10–60m/60–120m. Prepared
  cells repeat~30m source values; no blockage probability or independent-sample
  interpretation is justified. Optional20/40% screens are sensitivity assumptions.
- Alternatives reuse core.viewshed and observer-domain checks, on50m offsets from
  diverse parents. IDs/parent coordinates are explicit. Original points stay unchanged;
  alternatives use grid centres and independent bare-earth viewsheds. This is a
  bounded local diagnostic, not a global optimizer or access certification.
- Ray tests preserve bare-earth observer+eye and target+deer endpoints. Intervening
  columns are partitioned into observer/intermediate/target diagnostics. Endpoint-cell
  occupancy cannot resolve within-cell gaps; target occupancy is separately flagged.
  Unknown height/ground is unknown. Trees behind the observer are not traversed.
- Fine lidar: ONE2019 USGS tile, selected from an800m local catalog query; recorded
  tile bounds do not cover every local cell. Classified ground is interpolated only
  within5m. All nonnoise returns form columns, not verified vegetation-only crowns.
  Native point clouds have variable spacing; the2m grid is a derived product, not
  a claim of native raster resolution. Shared local-ground scenarios do not mix
  lidar and baseline vertical elevations. Crown gaps/under-canopy views remain unknown.

Exports: components.csv/json (all original points and alternatives), directional_cover.csv,
coarse_ray_scenarios.csv, overlap_low_tree.csv, GPX/KML review points, masked target-class
rasters, PDF/PNGs and a hashed output manifest. Unknown access is retained throughout.
Tests: `.venv/bin/python -m unittest discover -s tests -v`.

The protocol was predeclared in PROTOCOL.md. V2 adds separate shrub/raw maps and
close-up directional footprints, data-driven report text, stronger grid checks and
explicit shrub/searchability unknown bounds; it preserves the prior experiment.
Stop at this desktop handoff. No improved deer detection or field validation is claimed.
