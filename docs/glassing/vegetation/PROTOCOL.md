# Soap Creek bounded vegetation experiment v1

Predeclared before computing new rankings. Preserve original run and derived review.
Existing 150-point pool and all baseline scores remain controls. Audit A0031 against
source cover pixels, exact legacy 7×7 10m-cell square, imagery dates and grid sampling.
Native RCMAP is annual 30m fractional cover, not transmission or individual crowns.

Report target tree classes <10%,10–40%,>=40%, unknown separately, plus shrub cover.
Reuse target searchability once, not multiplied into existing vegetation-weighted
scores. Matched new controls use distance-only attention versus distance×searchability
attention, same 30-minute budget, sector geometry and distance curve; habitat/light/
perspective are excluded from BOTH new arms. Historical composite ranking is shown
separately, so differences from it cannot all be attributed to vegetation.
Unknown cover yields low/high reward bounds, not silently open terrain. Nominal uses
the existing explicit .25 tree/.30 shrub scenario defaults, with flags retained.

Directional observer diagnostic: 30-degree sectors within 10–60m and 60–120m annuli.
Native ~30m resolution cannot establish setup gaps; means are diagnostics, never blockage
probabilities. Optional 20%/40% directional tree-cover screens are sensitivity scenarios,
not access or sightline findings. Sector rewards are never multiplied by cover twice.

Select up to 8 diverse parents: three baseline leaders, three low-cover/high-target-
searchability alternatives separated by >=400m, then spatially distant positions.
Generate at most 64 alternatives on 50m cardinal/diagonal offsets within ~71m, deduplicate
cells and enforce original observer domain. Compute new GDAL bare-earth viewsheds.
No point is designated reachable from ownership, cover or geometry alone.

Coarse obstruction subset: up to 8 diverse original parents plus at most 2 best
alternatives. Up to 96 deterministic sampled visible targets each (seed5403); report
sample sizes, unknowns and broad limits, never full-area vegetation-visible acreage.
Assumed canopy columns: heights5/15m, cover thresholds20/40%; ground endpoints unchanged.
Partition observer 0–30m, intermediate >30m excluding last30m, target last30m; track
unknown separately. Compare screens and relative rank sensitivity, not field performance.

Fine-data cap: 100MB new source downloads; initially query only an 800m A0031 neighborhood.
If a suitable lidar tile fits, acquire ONE tile and inspect a local <=600m square;
no unit-wide products. Derived canopy column scenarios remain approximations, not
vegetation-aware deer visibility: treetops and missing returns do not model under-crown
views. Record date, CRS, vertical references, classification and occupied cells.
Software dependencies isolated from system Python; overall output cap500MB, runtime
900s analysis, memory1536MiB. All imagery reused where possible; no new imagery sweep.

Acceptance: synthetic open, foreground, below/above intermediate ray, obscured endpoint,
unknown and behind-observer cases; endpoint alignment; original hashes unchanged;
component tables, sensitivity/overlap, native-pixel audit and unobscured imagery maps,
neutral exports and concise report. New ranks are hypotheses, not validation.
