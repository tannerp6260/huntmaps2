# Nearby observer implementation and verification — 2026-10-01

Implemented the approved bounded exploration milestone. Main first-person controls
use Dense screening and the existing 120 m patch. Saved neighborhoods retain their
recorded membership; alternative cards collapse under their actual saved parent.
Other original setups stay visible. No representative is claimed to be best.

## Evidence

- Production TypeScript/Vite build passed; existing bundle-size warnings remain.
- Full backend/engine suite: 90 tests passed in 19.61 s. The nine new checks cover
  supported triangle interpolation against independently solved barycentric weights,
  finite/paired offsets, 30-foot and polygon limits, unknown ground without snapping,
  translated profile endpoints and curvature, missing-triangle gaps, separate storage,
  immutable coordinates during review edits, local mutation guards, mixed GPX/KML
  XML read-back, and explicit deletion. New API checks were rerun after final changes.
- Chrome inspected the actual interface with external requests blocked, using all
  four real pilot scenes. One-foot buttons and keyboard nudges, aerial-map movement,
  separate target selection, heading retention, failed-move retention, reset, saving,
  review edits, reopening, deletion and exact mixed waypoint exports were checked.
- Independent Three.js rays check moved camera ground against rendered fine triangles,
  terrain obstruction presence and foliage intersections against exported surfaces.
  Software agreement tolerances are not physical measurement accuracy.
- Targets outside the saved fine-ground circle return an explicit unavailable result.
  Targets beyond the unchanged foliage patch retain an unevaluated-coverage warning.
- Movement triggers no scene-asset reload, geometry generation or analysis job.
  Dense triangle counts remain 293,428 / 426,724 / 288,136 / 359,776 for
  A0075 / V010 / V008 / A0031, all below the 500,000 surface cap. The original derived
  bundles and source budgets are unchanged. Each inspected scene added zero idle draws.
- Existing first-person, foliage, cluster, general viewer and training browser checks
  passed. They include offline results, individual comparisons, imagery failure,
  keyboard controls, 900 px layout, boundary import/drawing and local terrain 3D.
- All 7,105 files in `.gui/verification/PRESERVED.json` matched their prior hashes.
  Original annotations and job counts stayed unchanged during nearby browser checks;
  only explicitly created verification waypoint records were removed afterward.

Actual screenshots and machine-readable evidence are under
`/tmp/huntmaps-nearby-observer/`, including each pilot scene, grouped setups,
manual-waypoint review, a 900 px view, exact mixed GPX/KML files and `results.json`.
Other regression evidence remains in `/tmp/huntmaps-first-person/`,
`/tmp/huntmaps-clusters/`, `/tmp/huntmaps-gui-browser/` and `/tmp/huntmaps-training-v2/`.
The final nearby results record per-scene measured movement latency and ray agreement.
The final measured movements took 525–928 ms. These are bounded software-rendered
interaction checks, not a frame-rate guarantee.

## Limits and handoff

Launch `./scout gui`; select a prepared Soap Creek setup, open **View from this
setup**, and use **Explore nearby positions**. See [first-use instructions](NEARBY_OBSERVER.md).

Only the four cached pilot scenes support movement, within 30 feet and inside the
original observer area. Source terrain, lidar and photographs remain their saved
acquisitions; vegetation is inferred and assumed opaque, not current verified trees.
The 120 m foliage patch stays at the saved anchor. Nearby waypoints have no recomputed
full-area masks, scores or access conclusions. No new acquisition, broader sampling,
optimization, field validation or route planning was performed.

Reproduce with the GUI running:

```sh
.venv/bin/python -m unittest discover -s tests -v
npm run build --prefix gui/frontend
npm run test:nearby-observer --prefix gui/frontend
```

One-foot movement interpolates the cached 1 m ground grid; it does not add
foot-scale survey accuracy. No new finer source was acquired.
