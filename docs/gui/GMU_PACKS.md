# Prepared hunting units

Start HuntMaps2 with `./huntmaps-gui`, choose **New scouting area**, then select
**Colorado GMU 54 · Core ready locally** under **Choose hunting unit**.
The local relief map, official unit outline and mapped roads/trails load immediately.
Draw or import a small observer area inside the outline, then use the established
**Find → Approach → Inspect → Save** workflow. Start around 10–50 km². The existing
3-million-cell buffered grid guard rejects oversized requests before launching a job.
The whole unit is source coverage, not one analysis request.

Satellite/aerial context loads online by default, including with a prepared unit.
Use **Map layers → Online imagery — fill gaps** to turn it off or retry a failed
connection. Your preference is remembered. Satellite imagery is not stored in the
core pack; when offline, the local relief map and unit outline remain usable.

Core preparation, generation, connection screening, basic terrain inspection,
export and reload work offline. The GUI uses yards, feet and square miles; analytical
files retain their recorded metric units and exact coordinates. Unit selection does
not establish legal access or predict wildlife. USFS lines are mapped inventory,
not verified safe/legal routes or an exhaustive inventory of every jurisdiction.
Intrinsic unknown vegetation remains unknown.

**Custom area** retains the existing source-review/acquisition workflow. **Open
existing work** opens old runs without converting or regenerating them. New runs
record an immutable pack version; an update does not move existing runs to another
version. Notes, shortlist decisions, drafts, confirmations, working coordinates and
habitat preferences remain attached to their existing runs.

Basic inspection uses prepared elevation data without source discovery. **Prepare
detailed view** is a separate selected-area action using the existing source review,
local cache reuse, resource guards and approval controls. The core pack does not
claim whole-unit LiDAR, fine ground, measured vegetation or aerial imagery coverage.
A detailed failure keeps the immediate usable Basic fallback and retained diagnostics.

## Location and contract

Default store: `data/unit-packs/`, outside the display cache. Override only through
`HUNTMAPS_PACK_DIR` when starting the app or its workers; retain the existing
source/workspace path containment rule. The store contains:

- `catalog.json`: atomically published unit → current ready version pointers.
- `versions/UNIT/VERSION/pack.json`: immutable contract 1, unit boundary, supported
  extent, datasets, preparation settings, provenance, per-asset sizes/checksums,
  intrinsic unknown counts and separate detail availability.
- `seal.json`: manifest size/checksum. Individual retained sources have explicit
  identities, provider metadata, queries, retrieval dates and checksums.
- `preparing/UNIT-VERSION/`: progress, cumulative transfer ledger, completed pieces
  and interrupted work. This directory is never advertised as ready.

Source packs have a broad buffered extent. The observer polygon must lie inside
the unit; obstruction terrain and target support extend outside it. Persistent
exact aligned local windows under `WORKSPACE/data/pack-windows/` keep ordinary
jobs bounded. Vegetation windows include 480 m for the existing habitat neighborhood
and native-grid support. Their checksums and original pack provenance are separate
from the raw-source import contract. Complete bounded local road/trail imports use
the established verified network store. Raw pack files never masquerade as an
already compatible historical source-cache entry.

The selector validates the sealed version and checks asset identity, including ctime,
so preserving size/mtime cannot hide corruption. Hashes are cached by file identity;
UI interactions do not repeatedly read the whole unit. TIFF file dependencies are
checked explicitly. Missing/corrupt/incompatible assets produce recovery instructions;
no missing terrain is fabricated, and no validation rule is relaxed.

## Preparation, updates and recovery

From the project root, use the project interpreter:

```sh
.venv/bin/python -m huntmaps_gui.pack_builder --unit 54 --version NEW_VERSION
```

Preparation checks the existing 20 GiB reserve and conservative peak headroom, retains
raw provider metadata, works in bounded pieces, and checks query completeness and
raster support. Progress is printed and persisted; the unit selector shows preparation
and actionable failure information under secondary recovery controls. Interrupting
preparation leaves completed pieces available. Repeat the exact command to retry.
Transferred bytes remain cumulative; failed partials remain separate from validated
files. Exhausted resource limits never imply readiness.

To deliberately reuse a verified immutable source snapshot for a new preparation:

```sh
.venv/bin/python -m huntmaps_gui.pack_builder --unit 54 --version NEW_VERSION --reuse-version OLD_VERSION
```

This means reuse of that dated snapshot, not verification that today's provider data
are equivalent. A new build without this option checks current official catalogs.
Versions are sealed/validated before same-filesystem rename, then the catalog pointer
publishes atomically. An old ready version stays usable throughout a failed update.
Repeating an existing valid version also recovers a rename interrupted before catalog
registration. To repair damaged assets, restore exact checked bytes or prepare a
new version; retain the damaged version and existing runs for diagnosis.

The first unit is intentionally Colorado GMU 54. Adding another unit requires its
own authoritative source build and validation; no other unit is advertised ready.
See [implementation evidence](GMU_PACK_REPORT.md) and [progress](GMU_PACK_PROGRESS.md).
