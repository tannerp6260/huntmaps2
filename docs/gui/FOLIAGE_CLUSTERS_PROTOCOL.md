# Connected foreground foliage — bounded GUI upgrade

Preserve prior rounded-clump/box bundles and all engine results. Soap Creek pilot
only: A0075, V010, V008, A0031. Cached sources only; no rankings or field claims.

Keep distinct XYZ returns, classes 0/1/3/4/5, supported fine ground and height >0.5 m.
Original strong cells have >=4 returns. Admit cells with 2/3 returns only beside
at least two original strong cells in the immediate 26-neighborhood. No recursive
growth or single-return admission. Read sources out to 122 m for the 120 m view
and support halo; original terrain/photos remain unchanged.

Union rounded boxes centered on admitted 1 m cells. Sparse/Medium/Dense widths
1/1.5/2 m; corner radius0.25 m; Medium default. No trunks, component bounding-box
fill or ground-to-canopy columns. Shared indexed surface is both display and
numerical geometry. Export float32 vertices with existing curvature convention.

Marching cubes on global lattices in8 m tiles with2 m halos, weld seams. Sampling
0.25/0.5/1 m: choose the finest level fitting all scenarios for a range under
500,000 triangles each. Never discard supported cells. Disclose coarser sampling;
if even1 m cannot fit, range unavailable and prior usable bundle retained.
Keep30/60/120 m choices, default120. Selection is by cell centre; volumes extend
slightly outside that boundary. Farther vegetation remains unevaluated.

Retain1536MiB process address limit,900s stage limit,800MB derived cache cap,
cancellable single-job execution, demand rendering and30fps interaction ceiling.
Reference checksummed immutable base assets rather than duplicate them. Version6
bundle and atomic ready pointer; old bundles stay available on preparation failure.

Verify support admission, disconnected gaps, tile seams, nesting, deterministic
meshes, caps/coarsening, independent triangle checks, endpoint containment,
view/check agreement, offline all4 scenes, screenshots, idle draws/resources,
failure/cancellation/restart, existing tests and protected hashes. Stop at report.

## Numerical contact correction before final acceptance

Zero-level surfaces at exact cell contacts can be singular. Use a1 mm positive
signed-distance contour margin and include that margin when enumerating touched
tiles. Extract owned grid cells, not overlapping halo triangles; calculate shared
edge crossings in float64 and weld only tile-boundary vertices. Refuse publication
unless every mesh edge has two incident faces. This numerical margin is not a claim
of millimetre source accuracy. Initial failed GUI prototypes are archived outside
the bounded cache; frozen box/clump controls remain in place.
