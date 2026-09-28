# Owner usability milestone — 2026-09-28

Implemented one normal scouting workflow: **`./scout run --area inputs/my-area.geojson`**.
Only the owner-selected observer polygon is required from the owner. Manual waypoints
are optional. No new model, itinerary solver, centroid AOI or synthetic human choices
were introduced. Real-area results remain pending the owner's polygon.

## Audit and scoped changes

The repository was clean at the initial `git status --short --branch`; Git is usable
in this session. Read root AGENTS.md, SPEC/PLAN/STATUS and latest transfer instructions,
implementation and evidence. Existing transfer code was suitable for reuse. Its
blocking usability assumptions were mandatory manual inputs, a historical verification
call before every stage, and a `fetch` adapter requiring preconfigured requests.

- `glassing/owner.py` and executable `scout`: diagnostics, area intake, preparation,
  run/resume, current-run verification and separate archive verification.
- `owner_area.py`: WGS84 GeoJSON/KML/KMZ polygon import, retained original export,
  explicit multi-polygon selection, holes and bounded local ZIP/XML handling.
- `owner_data.py`: coverage/checksum-qualified manifest cache reuse; bounded USGS
  catalog/single-tile DEM, RCMAP and CPW requests with a printed estimate before bulk
  download. Original adapters and their provenance format are reused.
- `owner_results.py`: obvious root results folder, terrain overview with ranked
  positions and observer/target boundaries, readable report with sector bearings,
  existing per-point cards, GPX/KML/GPKG and component/overlap tables.
- `transfer.py`: narrowly adds normal mode and optional manual intake. Frozen
  core/compare/comparison_models/attention implementation files are unchanged.
- `transfer_packet.py`: normal scouting title when no manual points are supplied;
  historical comparison presentation otherwise retained.
- Original transfer source retained byte-for-byte as `transfer_legacy.py`, so the
  earlier adapter identity is still available. No historical hashes were rewritten.
- README and START_HERE now lead with normal use; isolated native-GIS environment
  specification and diagnostics cover a fresh clone without ignored archives.

Normal mode still checks frozen model implementations, all required source hashes,
configuration, runtime, masks and derived products. Its final manifest also seals
all output files, Python implementation files, optional source descriptors and
launcher/environment specification. `verify` is read-only and repeatable. Changed
current inputs are errors; unavailable historical archives are a separate optional
experiment issue. Normal output cannot overlap the old `runs/` tree.

## Verified engineering evidence

Commands actually run:

```bash
./scout doctor
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests -p test_owner.py -v
```

The full suite passed **32 tests** (9.54 s in the recorded full run). After extending
optional-source/runtime sealing, the owner subset was rerun. The owner test copies
only code/configuration/launcher into a temporary workspace, with no `runs/`, `docs/`
archives or cached real data, and invokes the actual `./scout` launcher using the
isolated interpreter override. It checks:

- normal prepare → run without manual points; five alternatives and exports;
- optional manual comparison, exact coordinate preservation and identical automated
  pool regardless of manual inputs;
- archive-free startup and clear failure of optional historical verification;
- repeat verification and detection of altered current exports;
- dependency diagnostics with third-party packages unavailable (`python -S`);
- explicit KML/KMZ polygon selection and original bytes retained;
- over-budget acquisition rejected before Fetcher/bulk transfer;
- cached raster coverage rejection and corrupt-cache rejection.

Synthetic fixtures are conspicuously labeled and never presented as hunting outputs.
Their overview and first PDF card were visually inspected: distinct observer and
expanded target boundaries, point labels, sectors/distance ring, terrain-only imagery
status and pending approach evidence are readable. GPX coordinates, KML polygons and
GeoPackage geometry/CRS read-back are checked by the reused packet pipeline.

Representative isolated measurement (`/tmp/scout-journey-_ofybg3z`):

| Fixture | Primary candidates | Engine wall | Engine peak RSS | Owner analysis + handoff | Results size |
|---|---:|---:|---:|---:|---:|
| Normal | 24 automated | 1.57 s | 208 MiB | 2.42 s | 1.76 MB |
| Optional comparison | 24 automated + 2 artificial manual fixture points | 2.07 s | 218 MiB | 2.95 s | 2.19 MB |

These are small 500 m-radius synthetic checks, **not forecasts for a 2 km real AOI**.
Acquisition in these journeys: 0 bytes, $0. The acquisition provider plan was tested
with mocked catalog metadata and synthetic cache sources; no new real-area bulk
acquisition was attempted without a selected area. Live provider behavior for that
future area is unverified.

Environment measured: Python 3.10.12, GDAL 3.4.1, NumPy 1.26.4, SciPy 1.14.1,
Shapely 2.0.6, Matplotlib 3.9.2; 16 CPUs, ~14 GiB total RAM/~6.3 GiB available,
~26 GiB free disk. Normal defaults: 600 MB bulk-download cap, 3 million raster cells,
1536 MiB analysis address-space cap, 900 s analysis timeout, 800 MB analysis-output
cap. All are configuration values. Fresh conda/micromamba installation is documented
but was **not executed**; archive-free use of the existing interpreter was tested.

An initial `pytest` attempt failed because pytest is not installed. The repository
uses unittest, which was used successfully without changing the environment. During
verification a manifest-invalidating verify side effect was found and fixed: the
owner now calls read-only guards rather than the logging transfer CLI for verification.

## Preserved evidence and limits

`PRESERVED.json` records 6,326 preexisting run/report files captured before edits;
after regression testing all remained byte-identical. The earlier 6,227-file frozen
manifest remains untouched. Real archives were never moved/deleted to simulate a
fresh clone. No commits or pushes were made.

The supported automatic workflow still needs assistance for DEM mosaics crossing
tile boundaries or seasonal source selection outside Colorado. Catalog absence,
service errors, query truncation, corrupt cache and insufficient budgets produce
specific source/configuration instructions rather than false acquisition success.
Single-tile selection is a bounded first implementation, not unit-wide ingestion.

Imagery, documented entries/routes, permissions and restrictions are configured
optional evidence, not automatically fetched here. Missing evidence is printed as
pending; no straight-line approach is invented. No ecological validation, verified
legal access or calibrated detection claims are made. The historical model's seasonal,
light and attention hypotheses remain unchanged and explicit.

**Handoff:** supply only the observer-search polygon at `inputs/my-area.geojson`,
`.kml` or `.kmz`. Start with `./scout doctor`, then the command above. Results appear in
`results/my-area/`. Manual points can be added later in a separately named comparison.
Stop at this usability checkpoint; no further model development or routes started.
