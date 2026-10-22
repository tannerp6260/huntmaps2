# Timed practical opportunity 1

This increment leaves the [community/observation policies](PRACTICAL_GLASSING_METHODS.md)
and historical controls unchanged. All values remain planning assumptions, not
estimated selection coefficients, detection probabilities or biological validation.
The opt-in objective evaluates a single AM or PM outing with one or two stops.

## Selection and feasibility

Candidate generation, exact manual pins, intentional exclusions, observer cover
screens and original 1.7 m eye / 0.8 m target terrain masks remain unchanged. Practical
mode removes the old positive-v1-score admission requirement and old top-eight pair
screen. All feasible singles and both orders of all distinct pairs are proposed,
including feasible pins, within the existing maximum 80 proposals (at most 6,320
ordered pairs). Default budget is 32. Shared-prefix route connections use actual
supported geometry: reverse the unmatched first approach, then follow the unmatched
second approach. No missing connection receives a straight line. This remains a
bounded predecessor-route search, not an exhaustive search over all possible paths.

Every actual outbound/transition/return leg is measured directionally. Independent
walking, cumulative ascent, off-trail and grade limits plus held reserve are checked
before scheduling. Existing conservative AM/PM machinery deducts travel, setup,
transitions and rest and checks return/daylight and elapsed time. Each variant is
ranked separately. Combined/stay days are explicitly unavailable in practical mode;
they retain established behavior when that mode is off. No effort multiplier is
inserted into habitat utility and no unknown-access pressure bonus is added.

The versioned `practical-easier-1` preference considers plans with at least 90% of
best practical utility for that variant, keeps those within three minutes of the
least conservative movement time, and prefers fewer stops, then utility/ascent.
The report discloses utility sacrificed for easier travel. Only the best among
evaluated alternatives is claimed. Up to six previews retain recommendations and
alternating AM/PM frontier leaders; they are not a quota of necessary stops.

## Timed search and accounting

Unselected per-cell support retains sorted analytical indices, known/unknown state,
community group, fixed patch ID and q=H×G×D on eligible terrain-visible target cells.
Known nonhabitat remains zero independently of unknown concealment; unknown habitat
is not assigned a generic background. Scores never divide by known area. Unsupported
runs yield no recommendation, with null/insufficient-data scores in diagnostics.

Each fixed 30°/500 m polar patch costs its **entire** footprint at the unchanged
0.02 km²/minute rate plus 0.5 minute overhead, rounded up to 0.25 minutes. Hidden
or low-value cells never make it cheaper. These are uncalibrated task assumptions;
depth-overlapping/occluded terrain remains a limitation. Patch selection is binary.
Per-stop budgets come from that variant's actual observe events, optionally limited
by a separately persisted `search_minutes_cap`. The static review's `scan_minutes`
is rejected inside the timed policy. Longer visits are bounded by available positive
patches, with no 120-minute clamp. Unallocated time is shown as unused/rest, not
additional searched habitat or repeat-detection credit.

One stop uses an exact vectorized quarter-minute knapsack. Pairs retain independent
allocation as a lower bound, try both visit-start orders, and perform three passes
(one marginal initialization plus two coordinate sweeps). Each block solves the
knapsack exactly against the other visit's selected cell values. Only nondecreasing
updates are retained; the best seed wins. This bounded block search is not guaranteed
globally optimal. Tiny independent exhaustive patch/whole-plan fixtures check exact
maxima, budgets and approximation limits without hunting labels.

Utility is area×sum(cellwise maximum selected q). Repeated identical views cannot
earn another copy; better angles add only improvement. Inclusion contributions
sum to total utility. Exclusive improvement subtracts the best values without that
visit. Selected-view overlap equals summed standalone selected values minus union
utility. Float64 accumulation uses 1e-6 relative-index m² absolute reconciliation
tolerance; tiny roundoff near zero is not ecological information.

Theoretical terrain, total habitat support/unknowns, actual selected terrain/support,
positive opportunity support, range bands and relative utility remain distinct.
Assumption bounds permit completely obstructed foreground at the lower end and
maximum unsupported habitat at the upper end; they are not confidence intervals.
Actual selected sectors and support maps drive practical contribution displays;
theoretical terrain is a separate toggle and remains available for comparison.

## Foreground evidence and persistence

Finalist inspection is bounded to eight distinct points among retained alternatives.
It uses a 150 m local neighborhood and three coarse transects across each selected
azimuth in 10–50, 50–150 and 150–500 m bands, independently of target eligibility.
RCMAP 2023 has 40 m analytical information support; sampling it more densely adds
no detail. Diagnostics report valid fractions and the existing coarse cover-screen
threshold exceedance. Neither a canopy fraction nor vertical structure measures
horizontal leaf-off transmission. Low cover never certifies an opening and high
cover does not establish blockage. Unknowns remain unknown. No numerical score is
changed by opening or rendering inspection. No compatible measured local foreground
or matching perspective scene was found for demonstrated finalists; no link or
measured obstruction adjustment is fabricated. Field observations are not collected
in this increment. Dated imagery/point clouds and manual field observations must
remain separate evidence if subsequently added.

Timed settings/results/saves use explicit versions. Immutable version-2 saves retain
the analysis grid, source/package seals, original mask identities, coordinates,
profile/access/route provenance, date/timezone, schedules and selected sectors. Old
version-1 saves are read/exported with original scores, without silent migration.
The separate five-arm static packet and its waypoint-only GPX are preserved.

Sparse support is bounded to 256 MiB across candidates, within existing analysis
cell/state/disk limits. No candidate×whole-unit cube is created. Sealed route-basis
caches reuse complete route and visibility evidence for policy/schedule edits only;
profile/date/entry/access/geometry edits rerun preparation. Cache identities include
version/schema, package/source, grid/coordinate, original visibility and target mask,
and relevant settings. Every raw source and completed dependency remains checked.
Atomic publication markers admit only complete generations. Interrupted generations
are retained separately and recomputed; corrupt completed caches fail visibly.

Expensive five-arm map publication stays separately opt-in. Timed planning renders
only retained plan support/sector diagnostics. Jobs remain asynchronous, cancellable
and deterministic on retry. JSON and GeoJSON preserve backend order/coordinates;
GPX uses actual ordered connected legs including return. The report records measured
performance limits rather than silently dropping cells or pretending all time creates
new utility.
