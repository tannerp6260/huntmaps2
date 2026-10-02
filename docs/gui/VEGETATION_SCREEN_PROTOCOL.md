# Soap Creek inferred vegetation screen — predeclared pilot

Scope: A0075, V010, V008 and A0031, within 300 m; cached lidar only.
Preserve all historical models and outputs. No new scores, rankings or acreage.

Use full eligible returns, not display-thinned points. Deduplicate identical XYZ.
Eligible classes: 0/1 (inferred) and 3/4/5 (vegetation), non-withheld and non-noise,
with height >0.5 m above supported fine ground. Exclude other known object classes.
Require at least four distinct eligible returns in each fixed 1 m XYZ cell.
Cell lattice uses observer-relative east/north/height (fine observer ground origin).
Support is a filtering assumption, not confidence or vegetation confirmation.
Retain at most 500,000 supported cells; fail explicitly rather than thinning cells.

Opaque green boxes: sparse 1 m side, medium 1.5 m, dense 2 m. Names describe assumed
screening. No invented trunks, crowns or continuous ground-to-canopy columns.
Apply the existing curvature drop to cell centres, store float32 centres, and use
those exact stored centres for rendering and analytic line/box intersections.
Keep source classification provenance, counts and parameters in the bundle.

Default inferred foliage on, Medium selected; measured dots off. Terrain-only
profile remains unchanged. Optional experimental profile returns all three scenarios,
first hit and observer/target inside flags. No hit means no modeled intersection,
not a clear field view. Missing data remain unknown; vegetation beyond 300 m is
unsupported. Mark experimental intersections purple, terrain obstruction red.

Validate duplicates, isolated returns, classes, missing ground, rays above/below/
behind screens, inside endpoints, scenario monotonicity, and independent intersection
geometry. Inspect all four actual scenes offline in Chrome; record resources,
screenshots, scene/target controls, and protected-file hashes. Stop at pilot report.
