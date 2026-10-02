# Nearby rounded foliage upgrade — October 1, 2026

The four Soap Creek pilot scenes use the same supported cell centres as the previous
box experiment. The new shared 20-face rounded primitive is used by both rendering
and convex-polyhedron line intersection. Sparse/Medium/Dense diameters are1/1.5/2 m.
Opacity remains an assumption, not validated vegetation transmission.

## Lightweight defaults

| Setup | Clumps30 m | Clumps60 m | Clumps120 m |
|---|---:|---:|---:|
| A0075 | 812 | 2,462 | 9,695 |
| V010 | 431 | 2,832 | 20,002 |
| V008 | 136 | 1,079 | 11,637 |
| A0031 | 365 | 2,667 | 16,744 |

Default range is30 m, with a25,000-clump display/screening limit and no silent thinning.
Raw measured markers share the same distance filter. Full terrain context remains
available. Targets beyond nearby range explicitly have farther vegetation unevaluated.

Cached cells and photographs were reused to prepare all four bundles in about2.3 s,
with peak process RSS approximately201 MiB. No lidar cropping, triangulation or source
downloads were repeated. Cell centres and original grids/photos remain unchanged.
All clump colors have valid cached image samples: median RGB in a3×3 neighborhood,
blended75% photograph/25% green. Colors are display aids, not classification.

The complete Python suite passed74 tests, including six new tests for primitive faces,
independent ray/triangle agreement, inside endpoints, monotonicity, range boundaries,
cell caps, farther-screen exclusion, color alignment/alpha fallback and determinism.
Production frontend build passed.

Repeat browser checks with the application running:

```sh
npm run test:first-person --prefix gui/frontend
npm run test:nearby-foliage --prefix gui/frontend
npm run test:vegetation --prefix gui/frontend
```

The prior full box-model protocol and verification report are retained as historical
experimental controls. No new ranking, vegetation-visible acreage or field claim is
made. Rounded masses do not reconstruct individual trees, and photographic colors
are historical top-down appearance rather than observed foliage from eye height.

Installed Chrome verified all four setups at30/60/120 m with outside network requests
blocked. Instance counts matched the prepared range counts, the shared primitive had
20 faces, and raw-marker positions stayed within the chosen radius. Each setup had
zero additional draw calls during the measured one-second idle interval. It also
verified the default30 m scope and explicit farther-vegetation warning on a real target.
Matching-camera screenshots at heading187°, look−16° were visually inspected.
Evidence and screenshots are under `/tmp/huntmaps-nearby-foliage`.

The existing first-person browser regression also passed, including scenarios,
observer position, profiles, offline review, keyboard control, smaller-screen layout,
graphics failure and missing-imagery fallback. The protected inventory checked7,105
files with zero changes. Eleven prior control assets per setup—grids, meshes,
photographs and cell-centre/provenance/count files—are byte-identical. Resource and
control evidence is in `.gui/first-person/nearby-foliage-verification.json`.

Measured heading interaction latency was481 ms in software-rendered headless Chrome.
This is a local engineering measurement, not a hardware-independent frame-rate claim.
The primitive replaces box screening, so some previously intersecting box corners
no longer obstruct the experimental line; the historical box bundles are preserved.

## Larger default after user feedback

The current default was increased from30 to120 m. Choices30/60/120 and the25,000-clump
cap remain unchanged. All four120 m subsets fit the cap, with9,695–20,002 clumps.
The scene adapter and omitted-radius screening API both report120 m; no stored cell,
terrain, photograph or historical bundle needed rewriting or reprocessing. Frontend
build,13 targeted tests and the updated offline nearby-foliage browser check passed.
