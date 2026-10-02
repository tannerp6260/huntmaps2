# Inferred vegetation pilot verification — October 1, 2026

The pilot uses full cached lidar for the four Soap Creek setups. It does not modify
terrain scoring, historical reports, candidate coordinates or saved visibility masks.
See [predeclared assumptions](VEGETATION_SCREEN_PROTOCOL.md).

## Prepared scenes

| Setup | Supported cells | Preparation seconds | Peak process RSS MiB |
|---|---:|---:|---:|
| A0075 | 147,042 | 33.7 | 1,008 |
| V010 | 174,179 | 29.3 | 1,093 |
| V008 | 141,972 | 33.8 | 1,093 |
| A0031 | 195,290 | 38.3 | 1,164 |

Preparation completed in approximately 136 seconds, using cached sources only, under
the existing 1536 MiB address-space limit and 500,000-cell cap. Every supported cell
in these scenes includes unclassified returns and remains explicitly inferred.

## Checks

The full Python suite passed 68 tests, including seven new screening tests covering
supported clusters, duplicate records, excluded object classes, unsupported ground,
cell limits, rays above/below/behind foliage, endpoint containment, grazing boundaries,
scenario monotonicity and independent face-intersection calculations. API tests verify
optional-result compatibility, invalid scenario rejection and baseline scope limits.

Opaque green boxes are approximate screening volumes. Their centres derive from
measured returns, while support threshold, box boundaries and opacity are assumptions.
There is no reconstructed tree geometry, vegetation-visible acreage, new ranking,
field validation or guarantee that present vegetation matches historical lidar.

Installed Chrome passed the updated first-person browser checks with external network
requests blocked: all four setups, default Medium foliage, raw dots off, scenario sizes,
foliage toggling, unchanged observer references, profiles, >300 m scope restriction,
keyboard controls, smaller viewport, graphics failure and imagery fallback. Observed
heading interaction latency was approximately 892 ms in software-rendered headless
Chrome; performance on other hardware is not established.

A targeted check at A0075 heading187°, look−16° captured matched foliage-on/off views,
verified stored cell-centre/size agreement, and exercised a real target with a purple
intersection marker. An example line had no terrain obstruction: Sparse had no modeled
vegetation intersection, while Medium and Dense intersected inferred foliage. This
illustrates sensitivity to assumptions, not a validated field finding. Screenshots
were visually inspected; the foliage deliberately looks like block-shaped volumes.

All eight existing terrain/grid/photo assets per setup are byte-identical to version3.
The protected-file inventory again checked 7,105 files with zero changes. Resource and
bundle evidence is in `.gui/first-person/vegetation-screen-verification.json`; screenshots
and browser results are under `/tmp/huntmaps-first-person`.

Repeat browser checks with the GUI running:

```sh
npm run test:first-person --prefix gui/frontend
npm run test:vegetation --prefix gui/frontend
```
