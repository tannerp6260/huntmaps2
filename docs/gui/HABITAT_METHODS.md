# Experimental habitat-aware glassing

This GUI-only model ranks opt-in views by supported structural habitat preference
multiplied by a target vegetation glassability proxy. It is intended for desktop
review of Colorado GMU 54 in fall, including late October/early November second
rifle. It does not estimate density, encounter probability, mature-buck position,
current snow/forage, legal access or field-verified optical visibility. Historical
analytical coefficients, selective scores, masks and evidence remain unchanged.

## Equations and units

For observer p and exact saved analysis cell i, `E_p = Σ a_i V_pi F_i K_i H_i G_i`.
`a` is projected physical m², `V` the verified current saved terrain-visible mask
(including its radius and base target domain), `F` existing hard target matching,
`K` sufficient valid local vegetation and full-neighborhood support. H and G are
bounded 0–1. The per-cell product is computed before any area reduction. E is
quality-adjusted m², or **quality-adjusted acre equivalents** when divided by
4046.8564224. It is never literal acreage searched. No candidate/run normalization,
mean-of-means product, distance bonus, road-remoteness bonus or approach-cost term.

Physical metrics remain separate: current terrain-visible eligible target area;
current hard-filter matching area; scorable matching area/fraction; H>=0.45 high
habitat area; H>=0.45 AND G>=0.45 priority glassing area; matching habitat/neighborhood
unknown area. Scorable + habitat unknown reconciles to matching area. Existing
filter-unknown reporting is still relative to the visible base mask and can overlap
known exclusions by other criteria; it is not habitat unknown or part of that sum.
A moved point reports current working-mask values and retains historical originals
separately. The base mask need not represent every terrain cell within its radius.

No scorable area yields `insufficient_data` and null E; known zero is `scored` with
E=0. Supported contribution ranks partial coverage without normalizing by known
area. Unknown terrain is never filled as open, average-quality or unsuitable.
Ordering: descending E, descending current matching physical area, descending
current visible physical area, stable point ID. Insufficient rows follow scored
rows. Eligibility remains independent. Only eligible automated points with E>0
are recommended. Saved rankings cover previously evaluated candidates only.

## Fixed v1 responses and engineering assumptions

The fall preset has four nonnegative additive terms, summing to one:

| Term | Response | Default weight |
| --- | --- | ---: |
| Background | 1 | 0.10 |
| Browse structure | S/(S+0.15) | 0.45 |
| Mixed context | min(opening fraction/0.30,1) × min(cover fraction/0.30,1), local disk | 0.25 |
| Potential structural cover | min(landscape cover fraction/0.30,1) | 0.20 |

S is supported shrub fraction and T is supported tree fraction. Browse means
potential woody browse structure, without identified edible species/nutrition.
Opening/browse patches require T<=0.20 and S>=0.05. Cover patches require
max(T,S)>=0.35. Both require at least three four-connected coarse cells. The maximum
is a structural signal, not a sum or normalized composition. No vegetation-class
entropy, edge-length maximization or species classifier is used. The mixed term
requires co-occurrence; the smaller cover term retains possible habitat value in
dense stands without requiring openings. These overlap conceptually and are exposed
through component ablations; they are not independent biological mechanisms.

Local radius defaults to 90 m (choices 60/90/120); landscape radius 270 m (180/270/360).
Circular cell-centre kernels use at least 80% known samples over the **full intended
disk**, including missing outside bounds. Values are normalized only by known samples.
Local tree/shrub samples must also be known. No reflection, wrap, nearest filling or
zero-filled open habitat. Context precedes viewsheds, target filters and observer
boundaries; hidden neighboring cover can affect H but receives no visible-area credit.
These radii, 80%, patch size, thresholds, knots and weights are engineering hypotheses.

`G=(1−0.90T)(1−0.65S)`. Stronger tree and shrub cover each reduce utility; dense
shrubs are not automatically easy to observe. Dense forest retains possible H but
can have poor G. This is not measured transmission, horizontal understory visibility,
leaf-off prediction or intervening obstruction. G is shared across observers within
the existing selected radius. The terrain engine and user-selected elevation/aspect
constraints are unchanged. Imagery/foliage inspections retain their limited actual
coverage and dates. No pilot inspection is extrapolated across a whole area.

Advanced permits four finite weights 0–1 with positive total, normalized once for
the entire profile; radii above; penalties/priority thresholds 0–1. Altered settings
require Custom. Preset/version/unknown keys are strictly validated. No per-cell
weight renormalization. Component quality-adjusted sums are integrated after G and
add exactly to E; the observation penalty is ΣaVFKH(1−G). Priority thresholds affect
physical summaries and overlay only, not E or its tie-breaks.

## Verified source contract and grids

Base mode uses only existing local raw RCMAP tree and shrub percent rasters and
recorded provenance. Annual observation year stays pinned; processing release stays
unknown where the original annual WCS source never established it. A checksum-
verified snapshot is retained without claiming it matches a later release. Product,
component, year/query, raw units, actual delivered CRS/transform, shape, NoData and
bytes are checked. Components must align exactly; a genuinely ambiguous identity,
missing source, year disagreement or incompatible grid is rejected. Raw percent
0–100 is distinct from prepared cover 0–1 used by existing hard filters. NaN,
NoData, sentinels and out-of-range cover are missing before aggregation. Explicit
NoData is honored even if numerically inside the valid cover range.

Observed actual 2023 inputs in the available 549/500 pools: UTM 13N, approximately
29.972888×30.039699 m delivered cells, NoData 101, exact source hashes/provenance
in the preserved `source-audit.json`. These are resampled WCS cells, not exact native
Landsat pixels. Context conservatively averages onto a globally aligned square grid
at the next 10 m multiple no finer than 30 m or either delivered dimension: 40 m
for these inputs. No fine DEM habitat texture is inferred. Coarse cells require
complete delivered footprints and virtually complete valid contributing support;
internal gaps and partial edge footprints remain missing. This extra conservatism
can increase unknown area. Existing 120 m request padding does not guarantee 270 m
context; no larger halo is downloaded during re-ranking.

Coarse H/G, adjusted component products, priority and known support transfer nearest
to finer exact saved analysis grids. This preserves piecewise-constant source
support. For coarser grids, average **precomputed adjusted products**, high/priority
fractions and known support; an incompletely known destination remains unknown.
Metric north-up projected grids are required; rotated/nonmetric grids fail explicitly.
Visibility is never interpolated, downsampled or replaced with a priority mask.
Shifted fine grids can differ at coarse boundaries by their cell-centre sampling;
aligned subdivisions conserve area. Overview display pixels do not supply finer
biological information. Overlay: green priority, gray nonpriority matching terrain,
amber habitat unknown, transparent hidden/nonmatching terrain.

Herbaceous cover and CPW seasonal range polygons remain available as existing
source evidence but do not enter v1. Nested RCMAP components are not exclusive
classes and need not sum to one. Tree/shrub fractions identify neither aspen, oak,
sagebrush nor conifer. No compatible verified local LANDFIRE type/legend snapshot
was established for this bounded feature, so no extra-input subsystem is added.
A future type extension needs a versioned release-specific grouping and validated
legend plus consistent whole-profile data mode; it cannot change equations cell by cell.

## Ecological evidence, separate from coefficients

Sources checked October 18, 2026. Dates below are publication/page dates, not
vegetation acquisition dates. Relationships inform conservative structure only;
none supplies coefficients calibrated to GMU 54 fall bucks.

| Source, date and direct link | Population/season/geography and supported relationship | Limit |
| --- | --- | --- |
| [CPW deer management listing](https://cpw.state.co.us/activities/hunting/big-game/hunting-deer/deer-conservation-and-management), current undated page | Colorado herd management; finalized Southwest listing explicitly identifies D-57 replacing D-21/D-22/D-25 | Current status listing verified; its linked [asset share](https://cpw.widencollective.com/assets/share/asset/u9mjtqggbp) returned no readable plan. Final Gunnison plan contents were not fully reviewed. |
| [Southwest draft HMP](https://cpw.state.co.us/sites/default/files/dam/8sqrmcstjg/item.25.10_consent_draft_sw_deer_hmps_march_2024.pdf), March 2024 | Draft D-57 material identifies Gunnison Basin GMUs 54/55/66/67/551 | Explicitly draft/indexed excerpt; no final-plan or current occupancy claim derived. |
| [Historical D-21 plan supplied](https://hermes.cde.state.co.us/islandora/object/co%3A29294/datastream/OBJ/download/Data_analysis_unit_D-21_deer_management_plan__game_management_unit_54.pdf); [2013 West Elk plan index](https://hermes.cde.state.co.us/islandora/object/co%3A29253/datastream/OBJ/download/Mule_deer_herd_management_plan_data_analysis_unit_D-21_west_elk_herd_game_management_unit_54.pdf), January 2013 | Historical GMU 54/West Elk herd context | Both full PDF fetches failed/timed out; indexed executive summary is not a full review. No current migration timing/coefficients inferred. |
| [CPW Mule Deer](https://cpw.state.co.us/species/mule-deer), undated | Colorado species and habitat-treatment research summaries | Broad management evidence, not a fall buck selection function. |
| [Utah DWR habitat guidance](https://wildlife.utah.gov/deer/habitat), undated | Utah general seasonal diet: fall shift toward shrubs and mixed plant communities | Fractions cannot identify forage species, quality or present phenology; not Colorado buck calibration. |
| Rodgers et al., [Sex-specific behaviors of hunted mule deer during rifle season](https://www.usgs.gov/publications/sex-specific-behaviors-hunted-mule-deer-during-rifle-season), February 1, 2021, DOI 10.1002/jwmg.21988 | Male/female mule deer, rifle season, south-central Wyoming, 2016–2018; sex-specific hunting responses and weather-associated migration | Do not translate disturbance into a primary road-remoteness bonus or assume snow migration has occurred in GMU 54. |
| Sorensen et al., [Mule deer habitat selection following vegetation thinning treatments in New Mexico](https://www.usgs.gov/publications/mule-deer-habitat-selection-following-vegetation-thinning-treatments-new-mexico), February 6, 2020, DOI 10.1002/wsb.1062 | 48 adult females, north-central New Mexico 2011–2013, summer/winter; treatment-age/season-specific selection and moderately open mixed structure | Female, region and treatment-specific; no transplanted aspect/elevation or canopy coefficients. |
| Cain et al., [Mule deer (Odocoileus hemionus) resource selection: trade-offs between forage and predation risk](https://www.frontiersin.org/journals/ecology-and-evolution/articles/10.3389/fevo.2024.1121439/full), April 4, 2024, DOI 10.3389/fevo.2024.1121439 | Adult females in a nonmigratory herd near Corona, central New Mexico, and mountain lions; spring/summer/fall–winter forage/predation trade-offs | Sex, movement strategy and region differ from GMU 54 fall bucks. Structural cover is not automatically security/bedding habitat; no risk or nutrition inferred from RCMAP. |
| USGS, [Rangeland Condition Monitoring Assessment and Projection (RCMAP) fractional component time series](https://www.usgs.gov/data/rangeland-condition-monitoring-assessment-and-projection-rcmap-fractional-component-time-3), May 4, 2026 | Western North America Landsat fractional-component time series through 2025 | Product overview is newer than pinned observation year; it does not establish the saved WCS processing release. |
| LANDFIRE [Existing Vegetation Type (EVT)](https://www.landfire.gov/vegetation/evt), [Existing Vegetation Cover (EVC)](https://www.landfire.gov/vegetation/evc), [Existing Vegetation Height (EVH)](https://www.landfire.gov/vegetation/evh), current undated documentation | Distinct type/cover/height products and release legends | No verified local release added; fractions cannot stand in for these products. |

Dense timber, hunting disturbance, nutrition, migration and predation can change
real habitat use in ways this annual structural proxy does not observe. Elevation
and aspect remain user choices. Range polygons are mapped seasonal evidence, not
current occupancy. A reproducible heuristic does not establish ecological validity.

## Exact complementary coverage and state

For shared q=H×G, `E(S)=ΣaFKq·1(any member V=1)`. Greedy chooses the largest
positive exact marginal at each inclusion, with canonical individual-order ties.
Packed cropped windows reduce only newly covered bits using float64 shared weights;
priority physical area uses an independent corresponding union. No quantization,
candidate×grid cube, spacing-derived overlap or summed candidate totals. Retained
positions count toward size and spacing even if ineligible or missing a mask;
unknown retained coverage is explicit. Manual points follow existing retention rules.
Per-member total and incremental E/priority are distinct from final exclusive area.
Weighted overlap denominator is that member's E; physical overlap denominator its
matching visible area. This deterministic greedy method is not a proven global optimum
or a visiting order. Adding suggestions remains a separate snapshot-checked action.

Both Find consumers use canonical backend habitat order. Connection screening uses
the full scored pool before count/spacing selection; unavailable/partial evidence
and retained/manual exceptions remain available under established semantics. Habitat
changes neither slope limits nor connectivity inputs, source plans or approach queues.
Off retains strict existing filters and historical ranking versions; Show original
terrain independently disables the hard-target profile.
New habitat runs retain separately computed established recommendations from their
evaluated pool for this Off comparison. Switching objectives never regenerates the
pool; a habitat-refined pool can differ from a separate terrain-only search.

Profiles and per-run selections are separate user records, included in Storage,
backup/restore/deletion previews and release preservation. Contexts, derived score
rasters and overlays are regenerable GUI caches, never historical manifest entries.
Dependencies distinguish source/context, scoring/thresholds, exact masks/hard filters,
and collection decisions/count/spacing/connection token. Source/derived seals and
filesystem identities are checked before cache reuse; publication rechecks sources,
working revisions and preferences. Background admission is bounded to one analytical
GUI worker with a bounded queue; API workers remain available.

Opt-in new runs record settings, habitat implementation modules and a new
`habitat-provenance.json` sidecar in new-run products/manifests. The same objective
selects refinement leaders and spaced recommendations. Broad sampling, exact manual
coordinates, budgets and terrain engine are retained. Old interrupted checkpoints
remain incompatible under existing implementation guards; use a new run rather
than resetting/migrating their history. Completed-run changes use derived scoring.

## Sensitivity and challenges

Predeclared before real outcome inspection: local/landscape radii 60/180,90/270,
120/360 m; each nonbackground component ±20% with whole-profile normalization;
one-at-a-time component ablations; G penalties 0.75/0.50,0.90/0.65,0.98/0.80.
Default component weights and thresholds were not tuned to a favored setup.
Common-default collection utility is used for scenario comparisons, rather than
comparing differently scaled raw E across profiles. Actual findings and artifacts
are recorded in [the implementation report](HABITAT_IMPLEMENTATION_REPORT.md).
On the saved 549/500 pools the established/default-habitat top-20 overlap is 18/20
and 17/20. Modest alternatives retain 19–20 and 18–20 default leaders. Their greedy
collections differ by about 0.32% in common-default useful coverage; component
ablations cause larger individual rank shifts. Near-equal leader totals can exchange
ranks without material coverage changes. Default habitat greedy improves common-
setting E by 1.80% on the 549 pool but loses 0.28% on the 500 pool against established
greedy; the measured loss is retained, not tuned away. This does not validate deer
use or demonstrate a globally optimal collection. Unknown support can exceed the
measured deficit between individual candidates and must remain visible.

Engineering challenges include openness bias (background is small, bare ground is
not rewarded), dense-shrub bias (G separately decreases with shrubs), duplicated
context bonuses (bounded additive weights and ablations), fragmentation (supported
three-cell patches and coarse context), coverage bias (unknown explicitly exposed,
no known-area normalization), and impractical observers (existing eligibility and
conservative approach screening remain independent). None resolves missing field
observation or validates deer use.
