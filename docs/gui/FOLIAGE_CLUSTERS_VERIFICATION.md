# Connected foreground foliage verification

Implemented the [predeclared upgrade](FOLIAGE_CLUSTERS_PROTOCOL.md) for the four
Soap Creek pilot setups. Version 6 geometry `rounded-cell-union-v2` joins supported
cell volumes and admits two/three-return cells only beside two original strong
cells. Single-return cells and recursive growth remain excluded. Terrain, observer
coordinates, imagery and saved engine outputs are unchanged.

## Real data and resources

All ranges 30/60/120 m and all scenarios are prepared. Surface sampling is 0.25 m
at 30 m, 0.5 m at 60 m and 1 m at 120 m for every setup. Defaults remain 120 m/Medium.
All 36 exported meshes passed closed-surface validation and the 500,000-triangle cap.
Shared boundaries use a global lattice and float64 edge interpolation; a 1 mm
contact margin avoids singular zero-thickness contacts. This is numerical
regularization, not source accuracy or measured vegetation opacity.

The 120 m Medium surfaces have fewer triangles than the prior isolated 20-face
clumps, despite admitting substantially more measured support:

| Setup | Strong cells | Neighbor-supported additions | New Medium triangles | Prior Medium triangles | Preparation seconds |
|---|---:|---:|---:|---:|---:|
| A0075 | 9,695 | 15,027 | 191,540 | 193,900 | 41.1 |
| V010 | 20,002 | 27,166 | 332,448 | 400,040 | 42.0 |
| V008 | 11,637 | 16,292 | 202,652 | 232,740 | 36.1 |
| A0031 | 16,744 | 20,207 | 259,392 | 334,880 | 45.6 |

Worker high-water RSS reached 350.15 MiB;
1536 MiB address-space and 900 s stage guards remained active. Bundles plus retained
partials total 737,521,119 bytes, below 800,000,000. No new lidar or imagery downloads.
Pinned meshing packages were installed only in `.cache/vegetation-deps`; system
NumPy/SciPy were unchanged. New bundles reference verified existing terrain and
photographs rather than duplicate them.

## Tests and actual interface

- 81 backend/engine tests passed. New coverage checks distinct-return admission,
  neighboring support without chaining, unknown ground, tile corners/contact
  geometry, closed surfaces, gaps, deterministic generation, nested assumptions,
  endpoint containment, independent ray intersections, range/cap/coarsening and
  safe immutable asset references.
- Bounded synthetic cluster jobs demonstrate actual stages, budget failure,
  cancellation with partial mesh retention and interrupted-job detection. A restart
  race was repaired: mark interruption before killing and preserve that diagnosis
  against a late subprocess waiter.
- Production TypeScript/Vite build passed. Existing build-size warnings remain.
- Headless Chrome inspected all four real setups and 36 range/scenario combinations.
  External requests were blocked; none occurred. Scene opening left annotations
  and job counts unchanged. Camera/geometry counts matched metadata, raw returns
  stayed within range, and idle scenes drew zero additional frames.
- Independent Three.js raycasting against exported triangles agreed with backend
  first intersections within 0.0001 m for the inspected real target; this tolerance
  tests software agreement, not physical accuracy. All three assumptions were checked.
- Heading update latency was 26 ms in the software-rendered test.
  This is one interaction measurement, not a continuous-frame-rate guarantee.
- Existing first-person browser checks passed for camera height/location, keyboard,
  selection, foliage/point controls, terrain profiles, image failure, context loss,
  and 900 px layout. Existing vegetation checks passed for changed rendered images
  and the purple intersection marker.
- All 7,105 integrity-protected files were unchanged. Every
  referenced base asset and new mesh asset was also checksum-verified.

Same-camera screenshots were inspected at 187° heading/−16° look angle, 120 m/Medium.
Before/after A0075 and all four new scenes are in `/tmp/huntmaps-clusters`; browser
measurements and structured evidence are in
`.gui/first-person/foliage-clusters-verification.json`.

## Repairs and limitations

Initial zero-level/contact meshes failed closure checks and were not accepted as
final geometry. Their GUI-only prototypes are archived in
`/tmp/huntmaps-clusters-prototypes`; historical box/clump controls remain in their
original cache locations. One test-harness restart interrupted preparation, and
stopping the prior GUI server marked another completed-output job cancelled. A
fresh cached-only job then verified all four repaired bundles and completed normally.

Connected masses remain opaque inferred foliage, not reconstructed trees. At 120 m,
coarser sampling produces visibly angular patches and can change narrow openings;
the exact same coarse geometry is used for numerical screening. Sparse/Medium/Dense
are thickness assumptions, not observed forest density. Photographs remain draped
on ground; imagery age, missing returns and unknown ground remain unresolved.
The deliberate 300–320 m terrain-source gap is unchanged. This bounded Soap Creek
pilot establishes software consistency, not field fidelity or general performance.

## First use

Run `./huntmaps-gui`, open the Soap Creek saved review, select A0075/V010/V008/A0031,
and click **View from this setup**. Fuller clusters appear automatically. Keep the
120 m default or choose 60/30 m for finer nearby shapes; compare thickness assumptions
and click the plan map to inspect a temporary target. No preparation/download is
needed for these already prepared scenes.
