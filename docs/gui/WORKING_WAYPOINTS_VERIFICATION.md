# Working waypoint verification — 2026-10-01

Implemented a GUI working override of the selected setup, with atomic publication
of its coordinates and newly calculated baseline terrain mask. No historical
coordinate, score, output raster or engine calculation was modified.

## Automated evidence

- `.venv/bin/python -m unittest discover -s tests -v`: **97 tests passed**.
  Seven working-waypoint tests use real Soap Creek cached DEM/target sources in
  isolated state directories. They cover alignment/CRS/NoData, target clipping,
  exact area totals, cache reuse, immutable historical reads, exports, local write
  guards, source/mask tampering, one-job gating, review edits, restore, failed and
  cancelled jobs, interrupted jobs and late-completion rejection. A legacy manual
  waypoint retains its identity and original record while acquiring its own mask.
- `npm run build --prefix gui/frontend`: TypeScript and production build passed.
- `npm run test:working-waypoint --prefix gui/frontend`: actual Chrome/Playwright
  update, independent revision-keyed terrain tiles, persistence, first-person
  reopening, three-mask comparison, exact mixed GPX/KML exports and restoration.
  All external requests were blocked. Screenshots and JSON evidence are in
  `/tmp/huntmaps-working-waypoint/`.
- `npm run test:nearby-observer --prefix gui/frontend`: all four prepared scenes
  passed fixed Dense/120 m behavior, exact ground and foliage WebGL/ray agreement,
  boundary rejection, idle rendering, no preview analysis jobs or mesh reloads,
  legacy manual waypoint read/review/reopen/delete and mixed exports. Evidence:
  `/tmp/huntmaps-nearby-observer/`. The legacy creation part now explicitly uses
  the compatible API because the primary UI updates a setup rather than creating
  another standalone waypoint.
- `npm run test:browser --prefix gui/frontend`: viewer, comparison, review notes,
  offline use, export and polygon import passed.
- `npm run test:training --prefix gui/frontend`: lessons, drawing, parameter help,
  terrain 3D and offline checks passed.
- SHA-256 preservation audit: **7,105 protected files, zero changes**.
  Evidence: `/tmp/huntmaps-working-integrity-final.json`.

The real A0075 one-foot-east calculation took **0.356 s worker wall time**,
**267.7 MiB peak worker RSS**, and **170,123 bytes** for the cached mask/provenance.
Its clipped visible area was **1.2567 km²**. These are measurements on this machine,
not general performance promises. Existing user manual records were preserved;
verification working overrides were restored after the browser check.

The main-map screenshot was visually inspected and shows cyan terrain shading
and the updated marker alongside its fresh metrics. A 900-pixel layout was also
inspected. The calculation uses 10 m baseline terrain: sub-cell movement may leave
wide-area shading unchanged, while the finer foreground preview can change. No
new vegetation-visibility area or heuristic score is computed. Coverage remains
the four existing prepared Soap Creek scenes; arbitrary-area fine-scene generation
and additional optimizers are outside this change.
