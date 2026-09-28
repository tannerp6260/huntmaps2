# Reusable transfer adapter

Read [required inputs](INPUTS.md), [fixed comparison protocol](PROTOCOL.md), and
[engineering report](REPORT.md). All commands below are implemented; run from root
using `.venv/bin/python`. Old baseline/scouting commands and outputs remain unchanged.

```sh
# Safe even before hunter files arrive: reports exact missing inputs.
.venv/bin/python -m glassing.transfer intake --config configs/transfer.template.json

# Offline synthetic portability check; NOT a hunting area or human selections.
.venv/bin/python -m glassing.transfer_fixture
.venv/bin/python -m glassing.transfer all --config configs/transfer.fixture.json
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m glassing.transfer verify --config configs/transfer.fixture.json
```

After real inputs and verified sources have been supplied, the same CLI has individual
`prepare`, `candidates`, `score`, `access`, `packet` stages, or `all`. Configuration
changes require prepare and downstream stages again; source/derived checksums prevent
silently mixing inputs. Work directories are owned and checked against frozen paths.

Configuration paths are relative to project root. `epsg` must be an appropriate
projected metric CRS. Templates retain GMU54's known hunt dates, but dates/scenarios,
observation radius, domain/source paths, hiking preferences and work directory are
editable for a transfer. Radius must divide the frozen500m patch tiling. Frozen
coefficient values and model implementations are verified before each CLI command.
Old sun angles are explicitly hypothetical; changing legal dates does not turn those
angles into calculated sunlight. Personal dates/camp remain unspecified.

Data descriptors under `data` require `path`, `sha256`, `provider`, acquisition date,
license/unknown, resolution/unknown and relevant units/datum. `dem` requires explicit
`vertical_units: "m"`; no vertical correction is performed. DEM is bilinearly aligned;
cover is nearest-neighbor aligned, with unknown pixels flagged. `tree`, `shrub`, `herb`
are0–100 percent cover rasters. `summer`/`winter` are authoritative RFC7946 polygons
(known-empty collections are allowed, missing source files are not). Existing frozen
summer/winter mixture, habitat floor, distance/searchability/perspective and attention
functions are reused, with no new coefficients. `imagery` is a list of source-verified
RGB raster descriptors; dates are shown, absent imagery stays pending.

Intake returns metric/WGS84 query bounds for terrain and broader access data. `fetch`
accepts optional exact `downloads` entries (`name,url,sha256,provider,acquisition_date,
license`) and uses the existing bounded Fetcher. It is not an automatic agency/product
chooser. Real source selection and dated restrictions review await the user's AOI.
No data acquisition cost or provider coverage is assumed before that boundary exists.

Access configuration is separate:
- `entries`: verified-source GeoJSON Point descriptor with properties `id,evidence`.
- `routes`: list of GeoJSON line descriptors; optional `id_field,name_field,
  prohibited_field` map source schemas. No arbitrary line-crossing junctions.
- `offtrail_allowed`: explicit allowed-area GeoJSON descriptor; `barriers`: polygon
  descriptors subtracted from it. Ownership alone does not establish connected rights.
- `repair_tolerance_m`, `entry_gap_review_m`, `max_final_leg_m`, `max_slope_deg`,
  `walking_kmh`, `ascent_m_per_hour`: visible assumptions for provisional pedestrian
  witnesses. Unknown/missing data yields pending effort. Longer approach elevation
  coverage must be obtained before reporting complete gain/time.
- `data.approach_evidence` optionally supplies a checksum-verified JSON mapping original
  manual IDs or automated IDs to separately reviewed effort/evidence. It is not invented
  from road proximity. No pilot-specific entry names or coordinates are embedded.

Outputs in the configured work directory: imported originals/provenance, four spatial
domains, aligned rasters, independent pool, component scores, frozen attention patches,
local refinement diagnostics, leading points, overlap CSV, approach evidence, GPX/KML,
GeoPackage and labeled PDF. No claimed field-ready positions; no successful app-import
claim. Synthetic fixture input kind appears on every page and waypoint description.
