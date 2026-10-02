# Nearby foliage appearance and screening — predeclared upgrade

Preserve the four pilot cell sets, box-model bundles, original terrain and scores.
Reuse cached cells and photographs. No new acquisition or tree reconstruction.
Default horizontal centre range30 m, choices30/60/120; at most25,000 displayed cells.
Reject an oversized range rather than silently thinning. Filter raw markers too.

Use one normalized 20-face icosahedron with float32 vertices and outward triangle
faces, shared between rendering and convex-plane intersection. Sparse/Medium/Dense
are diameters1/1.5/2 m; defaultMedium. Preserve stored centres/curvature. No rotations,
trunks, leaf textures, animated foliage or shadows. Smooth shading is cosmetic.

Sample median valid RGB from a3x3 pixel neighborhood beneath each cell in the cached
local aerial texture. Blend75% photograph and25% existing green in sRGB. Missing
coverage uses the original inferred/classified green. Color is not classification.

Use chosen range for both view and experimental screening. Targets beyond it have
farther vegetation explicitly unevaluated; preserve full terrain profile. No modeled
intersection is not a verified clear view. Idle scenes stop drawing; interaction
renders at most30 fps. Version bundles and record all assumptions.

Validate colors/alpha/alignment/determinism, ranges/caps, independent mesh intersections,
view/check agreement, no continuous idle draws, all four scenes offline, same-camera
screenshots, resources and protected hashes. Stop at the upgrade report.
