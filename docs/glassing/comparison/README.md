# Run the matched comparison

Use the same local environment as the baseline, from the project root:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m glassing.compare acquire --config configs/comparison.json
.venv/bin/python -m glassing.compare all --config configs/comparison.json
```

Acquisition is cached and checksum-locked. A fresh copy needs ~265.4 MB of new inputs,
including one selected 1m tile, plus the original baseline inputs. `all` runs offline
and never writes to runs/gmu54 or modifies the original core/configuration. Commands
`prepare`, `run` and `review` are also individually callable in that order, using the
same `--config` argument. No new package installation, system modifications or paid
services are required. Command memory cap is 2 GiB, runtime cap 900 seconds, source
cap 300 MB, experiment disk cap 1.5 GB; computation is single-threaded. Disk is checked
between stages; fixed 150 common/400 dense-point tasks keep intermediate output small.

Inputs: same 64km² AOI and original 150-point pool. CPW seasonal polygons and USGS
2023 RCMAP cover are locked in configs/comparison_sources.lock.json. Requests,
retrieval dates, acquisition-date qualifications, CRS, units, terms and SHA-256 values
are in data/comparison/manifest.json and the small provenance snapshot here. A changed
live science source fails the lock; retain cached inputs or explicitly register a new
experiment. The WCS returns percent-cover science rasters; nearest resampling onto
10m alignment does not turn 30m estimates into 10m tree maps.

Outputs in runs/comparison:

- `component_scores.csv/json`: all candidates/scenarios, individual factors, access/
  actionability flags, unbounded and equal-effort scores and ranks.
- `selection_comparison.json`: four nominations per method, four separate 30-minute
  sessions each; cross-scores are model diagnostics, not validation or route plans.
- `sensitivity.json`, `random_baseline.json`, `canopy_stress.json`: feature/range/task/
  effort ablations, score-blind spatial samples and sampled canopy stress bounds.
- `resolution.json`, `dense_reference.json`, `fine_resolution.json`: 30m, 100m dense
  candidate lattice and two local 1m comparisons. Fine ray checks are separate JSONs.
- `comparison.gpkg`, `comparison.png`, feature GeoTIFFs, `fine_comparison.png`:
  QGIS-readable products and static comparison maps.
- `alternatives.csv/json`: five distinct review positions with arm ranks, component
  means and explanations. They are NOT a field-ready shortlist.
- `BLINDED_REVIEW.csv`, `BLINDED_TARGETS.csv`, `BLINDED_MAP.png`,
  `REVIEW_INSTRUCTIONS.md`: reviewer packet with blank observation fields.
- `DO_NOT_SHARE_REVIEW_KEY.json`: analyst-only mapping; do not give this or model
  scores/maps to blinded reviewers. This is workflow separation, not file security.
- `COMPARISON_REPORT.md`, `component_timings.json`, `metrics.jsonl`: generated run
  summary and measurements. The interpreted checkpoint report is REPORT.md here.

Every major factor has a `features` on/off switch. `season`, `habitat_floor`,
`distance_curves`, `task`, `distance_scale`, `perspective_floor`, `light`,
`sun_scenarios`, `glare_strength`, `observation_minutes`, `scan_km2_per_minute`,
`canopy_heights_m`, `canopy_threshold` and `foreground_stress_penalty` expose scenario
assumptions. Set glare_strength to zero to remove glare while retaining illumination.
For an altered experiment, copy the configuration and use a different work directory;
rerun all stages. No calibration is performed from review data. Prepared raster
checksums, source/config/code identities and baseline checksums prevent silent mixing.

See EXPERT_PROTOCOL.md for expert CSV and verified-access/follow-up inputs. No expert
coordinates or human review evidence are supplied. Without access evidence the random
benchmark is only technically eligible; no legally feasible benchmark is claimed.
