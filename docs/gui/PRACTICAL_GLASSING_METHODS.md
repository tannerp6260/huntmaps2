# Practical opportunity 1: methods and source interpretation

The predeclared [protocol](PRACTICAL_GLASSING_PROTOCOL.md) fixes the comparison before
new leaders. All numbers below are transparent engineering choices, not fitted
habitat-selection or detection coefficients. There are no hunting observations,
synthetic deer labels, mature-buck locations or biological validation in this model.

## Separate quantities

The original terrain/target comparator and `rcmap-structure-v1` implementations are
preserved. V1 retains its weights [0.10, 0.45, 0.25, 0.20], 90/270 m neighborhoods
and shared G=(1−0.90T)(1−0.65S), including its actual coarse source support. Old WCS
products that became 40 m information support are not described as 10 m habitat.

The new companion supplies **LF2025** EVT/EVC/EVH at native 30 m, EPSG:5070. Its
600 m buffered unit export preserves neighborhood support across unit edges.
Job windows use exact reprojection, nearest categorical sampling, explicit NoData
and conservative halos. A regression exposed one categorical disagreement under
GDAL's default approximate transform; errorThreshold=0 and no automatic overview
selection make nested window reads consistent. DEM/observer/target/access domains
remain separate. Excluding a target cannot remove obstruction terrain or its NoData.

`practical_glassing/traits_lf2025.json` records exact class codes, official names,
lifeforms and a small release-specific trait grouping. A changed class meaning or
foreign legend fails. Unsupported natural/agricultural classes remain unknown.
Known mapped water, developed and selected mapped barren/bedrock classes have zero
opportunity. A source with complete pixels can still have incomplete trait support.
Raw EVT/EVC/EVH values, names and pinned legend identities remain inspectable.

Supported browse-capable aspen, aspen/conifer, mountain-shrub and sage/browse groups
share forage index 1. Meadow is 0.5 and conifer 0.35, with conifer understory explicitly
uncertain. H=0.8×forage+0.2×nearby mapped cover-community fraction in one 90 m disk.
The full disk is the denominator. No repeated edge/diversity/security bonus applies.
Whole required context must be supported; known nonhabitat remains zero independently
of missing neighboring habitat. This is a policy, not a nutrition or mature-male
selection measurement. Predeclared alternatives challenge these values and radii.

EVC168 means the pinned label **Tree Cover = 68%**. EVH204 means **Shrub Height =
0.4 meter**. Labels are decoded, not code magnitudes. EVC is dominant-lifeform
canopy cover, not forest understory shrub fraction. Tree-height classes of 1–5 m in
mapped aspen flag a short-canopy proxy only; neither age nor dense regeneration is
inferred. RCMAP components remain overlapping estimates and are never normalized
to exclusive composition. LF2025 community and 2023 RCMAP structure are explicitly
different dated hypotheses, not contemporaneous measurements.

## Observation and unique opportunity

Default target concealment reuses v1 G once. Distance preferences at
0/500/1000/1500/2000/3000 m are:

| Task | Relative preference |
|---|---|
| Spot | 1, 1, .85, .60, .35, 0 |
| Identify a buck | 1, 1, .60, .25, .10, 0 |
| Antler assessment | 1, .70, .25, .08, .02, 0 |
| Distance ablation | 1 throughout the analysis radius |

These distinguish preferred working range from possible detection, without implying
probabilities or shooting suitability. Physical and supported area/opportunity bands
are exported separately. Bearings use the projected UTM grid; confirm true compass
bearings in a field map. Preserved geometry is 1.7 m eye / 0.8 m target. This feature
does not offer score-only posture changes; changed geometry requires new viewsheds.

Unknown/on foliage applies no discount. Partial/off scenarios reduce only the assumed
deciduous part of the tree penalty by 15%/30%; mixed aspen/conifer receives only half
that deciduous assumption. Trunks, branches, evergreen admixture, shrub concealment
and unknown understory persist. These are stress tests, not verified leaf conditions.
Neutral light is used. No aerial sightability coefficient, opaque canopy-column
assumption, missing-return-as-clear-air rule, or duplicate habitat penalty applies.

Each visit selects fixed 30°/500 m polar patches under an exact quarter-minute
binary knapsack. Full projected footprints cost 0.02 km²/min plus 0.5 min overhead;
costs do not shrink with visible or high-value cells. Search rate is uncalibrated.
Occluded/depth-overlapping terrain does not make a patch cheaper. Optional positive
reward cannot reduce the best achievable per-visit value. The default is 30 useful
minutes, with 15/60 minute alternatives. Scan order sorts selected patches by value;
it is approximate field guidance, not a measured human search schedule.

For each visit, q=L×F×H×V×D. Unique utility is sum(area×max_visits(q)) using exact
float64 cellwise maxima. Repeated identical visits add nothing. Better views add
only their improvement. The first three shared-weight comparison arms use the
unchanged packed-union greedy, including canonical tie order. Observer-specific
arms use sparse exact marginal gains, stable IDs, spacing and a bounded swap pass
for the combined objective. There is no global-optimum guarantee. Tiny full-array
and exhaustive cases independently check the reducers and routing contracts.

Unknown-only individual scores are null/insufficient-data; known zero stays zero.
There is no normalization by known area or per-cell imputation. Scores are conditional
on uninspected foreground/intervening vegetation. A loose assumption envelope includes
complete obstruction (lower 0) and maximum unsupported habitat; it is not a confidence
interval. Physical, scorable, habitat unknown and foreground unknown areas remain
distinct. Quality-adjusted m² are not literal searched acres.

## Access and planning scope

This release reuses TrailScout's attributed network, conservative endpoint topology,
terrain/spur checks, directed time measurements, complete outbound/transition/return
geometry and separate distance/gain/off-trail budgets. Source attributes now follow
traversed segments into result evidence. Conflicting MVUM records and active
prohibitions cannot be reopened by record ordering. Malformed dates stay unknown;
actual side-by-side width is required for the over-50-inch motor class. A motor closure
does not imply foot permission. Duplicate conflicting inventory features become
conditional rather than silently replacing one another. Current data has no such
duplicate conflict among its 647 parsed records.

The existing limited route/Pareto previews and AM/PM logistics remain under v1.
The practical complementary collection is a static fallback, never a timed plan.
New multiobjective route alternatives, joint time/dwell/sector optimization, full
drive-to-parking routes, current closure geometry, target permission and stalk/retrieval
models are deferred. Scoring cannot average a road-infeasible case into feasibility.
Pressure remains inventory-limited diagnostic evidence, without a strong multiplier.

## Research basis and limits

[Rodgers et al. 2021, DOI 10.1002/jwmg.21988](https://www.usgs.gov/publications/sex-specific-behaviors-hunted-mule-deer-during-rifle-season)
supports context-dependent male security-habitat use away from motor routes and the
importance of weather/migration history. It supplies no local GMU54 mature-buck
coefficients. [Brown et al. 2020, DOI 10.1002/jwmg.21916](https://research.fs.usda.gov/treesearch/63736)
studied adult females during buck hunts at Starkey; it is not male late-October
calibration. [Morano et al. 2019, DOI 10.1002/ecs2.2811](https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=175090)
concerns female summer shrub-steppe selection. [Anton et al. 2025](https://link.springer.com/article/10.1186/s40462-025-00540-x)
studied female autumn migration with variable timing; it does not justify a universal
snow threshold or hunting-triggered migration switch.

Retain the [Colorado Plateau habitat guidelines](https://www.fs.usda.gov/biology/resources/pubs/wildlife/cpe_muledeer_hab_guidelines.pdf)
and [USFS mule-deer synthesis](https://research.fs.usda.gov/feis/species-reviews/odhe)
as broad ecological context. The former endpoint returned 403 during this pass;
no fresh full-document review is claimed. [Aerial sightability, DOI 10.1002/jwmg.21143](https://doi.org/10.1002/jwmg.21143)
describes a different observation mechanism; its coefficients are not used here.
These sources motivate separation of habitat, presence and searchability. They do
not validate relative scores, antler predictions, actual sightlines or encounter rates.

Source details and measured release evidence are in the implementation report and
the ignored immutable package manifests. The [LANDFIRE release description](https://landfire.gov/data/lf2025)
states LF2025 updates disturbances through fiscal 2025 and is released in 2026;
that label is not an individual pixel acquisition date. Analytical service requests
use raw signed class exports and official release CSVs, consistent with the
[WCS/WMS distinction](https://landfire.gov/data/lf_wcs_wms).
