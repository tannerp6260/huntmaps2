# Corrective validation checkpoint — 2026-09-26

**Recommendation: simplify the modeling effort and continue only independent geometry,
setup and connected-access review before routes.** The attention defect is corrected in
a separate experimental alternative. C0068 is the only point in all 21 selective-attention
sensitivity top tens, but no candidate has passed the complete geometry/access/field gate.
Rank stability is not evidence of better deer observation. No route optimization was added.

## Control and implementation

The existing standalone component remains suitable for this small experiment. Reused
`compare.components`, `comparison_models` and `core.viewshed` read the frozen 150-point,
64 km² GMU 54 pilot and GDAL bare-earth visibility caches. New files are `attention.py`,
`correct.py`, `correction_geometry.py`, `correction_access.py`, `correction_data.py` and
`correction_packet.py`; old code/configuration/reports/results were not modified.
`FROZEN_CONTROL.json` verifies 3,340 previous files before and after every new command.
Git is unavailable in this workspace; no commit, publish, reset or system installation occurred.

All comparisons use the same original candidates, target masks, 2 km radius, 1.7 m eye,
0.8 m bare-earth target, curvature coefficient 6/7, hypothetical detection curve,
morning light setting and unknown access. Searchability, target perspective and light
remain the old uncalibrated functions. Vegetation obstruction stresses remain OFF.
No new habitat coefficient, calibrated detection rate, pressure estimate, access permission
or deer observation was introduced. The raw terrain control remains exactly reproducible.

## Attention correction and sensitivity

The original uniform formula multiplies whole-view reward by
`min(1, budget_minutes * scan_rate / visible_area)`. A numerical counterexample:

| Available terrain | Unlimited weighted reward | Uniform, 30 min at 0.02 km²/min | Selective, same budget* |
|---|---:|---:|---:|
| 0.6 km², unit relative value | 0.60 | 0.60 | 0.60 |
| Add optional 0.6 km², value 0.1 | 0.66 | **0.33** | **0.60** |

*Simple two-patch demonstration uses zero overhead to isolate the defect. Production
nominal overhead is 0.5 minute per selected patch. These are weighted-area units,
not probabilities, expected animals or calibrated search productivity.

`selective_patch_attention_v1` divides the view into 30° wedges and 500 m radial bands
(48 coherent patches). It chooses whole patches with an exact binary knapsack.
Each costs its **entire geometric footprint** / assumed rate + overhead, rounded UP
to a quarter minute. Hidden, ineligible and low-value parts cannot be cherry-picked
out of a chosen patch's cost. Positive optional patches can be ignored; extra reward
within fixed patches cannot lower achievable value. Synthetic exhaustive-subset and
monotonicity tests check both this property and reported budget/selection consistency.

This is still a surrogate: full-footprint cost may overcharge sparse views; fixed north-
aligned sectors, indivisible patches, an area-based rate and constant switching overhead
are assumptions. Sector travel angles, fatigue, revisit value and actual detection are
not estimated. Additional terrain might impose real distraction costs, but none is
silently imposed here. Width/rate/overhead sensitivity is explicit, not fitted.

The run includes 51 configurations: three attention strategies × five seasonal mixtures
× 15/30/60 minutes, plus six selective width/rate/overhead variations. The no-penalty
strategy intentionally ignores the budget as an upper-bound ablation, not an equal-effort
field competitor. Existing uniform summer/30-minute scores reconstruct within
**4.17e-17** of the frozen control. Nominal selective uses a 50% winter-like mixture,
30 minutes, 30° patches, 0.02 km²/min and 0.5-minute overhead.

| Diagnostic alternative | Nominal selective rank | Rank range over 21 selective cases | Top-ten appearances | Role |
|---|---:|---:|---:|---|
| C0068 | 1 | 1–7 | 21/21 | Most stable attention hypothesis; old distinct habitat nominee |
| C0095 | 2 | 1–16 | 20/21 | Transition/winter-like alternative |
| C0049 | 4 | 3–29 | 16/21 | Preserved old stability nominee; extra diagnostic map |
| C0090 | 5 | 2–59 | 12/21 | Original uniform winner |
| C0025 | 31 | 14–49 | 0/21 | Preserved stratified-random control |
| C0064 | 51 | 12–79 | 0/21 | Raw terrain winner, local geometry concern |

The five explained alternatives in `alternatives.csv` are C0068, C0095, C0090, C0064
and C0025; C0049 remains in the six-position diagnostic packet. Nominal top ten overlap
is **4/10 with old M3**, **1/10 with raw terrain**, **3/10 with matched-transition uniform**
and **2/10 with matched-transition no penalty**. Changing nominal budget to 15/60 minutes
retains 6/8 of ten; halving/doubling assumed rate retains 5/8; 20°/45° wedges retain 8/6;
overhead 0/1 minute retains 9/9. Thus the formula defect is fixed, but effort assumptions
still materially affect selection. The no-penalty ablation still prefers broad views.

## C0064: local geometry, not a full-radius error estimate

All central comparisons evaluate the same original eligible 10 m target centres within
400 m. Fine imagery/terrain is retained outside that support. Average-resampled fine
terrain and control have identical 10 m grid transforms. Observer coordinates coincide
with cell centres on every diagnostic grid: E317025, N4279455, EPSG:32613.
There is no observed half-cell observer registration error in these matched products.
This does not prove absolute survey registration.

| Surface / engine sampling | Visible area on common support, km² | Observer ground, m |
|---|---:|---:|
| Original 10 m terrain | 0.1266 | 3135.223 |
| Native-derived 1 m terrain | 0.0659 | 3134.013 |
| Fine source averaged onto exact control 10 m grid | 0.0729 | 3133.375 |
| Averaged 10 m surface bilinearly upsampled to 1 m | 0.1112 | 3133.375 |

The local fine/control difference is approximately −48%, **only within this tested
400 m support**. Most of the difference persists when the fine source is aggregated
to 10 m; nominal resolution alone is therefore an inadequate explanation. Upsampling
also changes visibility substantially despite equal observer elevation: surface
interpolation and engine sampling matter. This factorial comparison does not cleanly
attribute every difference to one cause, and upsampling adds no measured terrain detail.

Fine minus control ground over common support averages −1.625 m, median −1.900 m,
5th/95th percentiles −4.161/+1.952 m. This is not a uniform vertical offset that cancels
from every ray. Both catalog products specify metres/NAVD88; the 1 m product is
CO_WestCentral_2019_A19. The coarse mosaic has mixed/uncertain underlying survey dates.
Horizontal datum realizations, source processing, age and resolution remain confounded.
No vertical datum correction was performed and 1 m is not declared field truth.
See the frozen comparison provenance and new per-grid transforms.

At fixed 400 m support, fine eye heights 1.0/1.7/2.2 m give 0.0609/0.0659/0.0957 km².
Artificial ±1 m horizontal surface shifts give 0.0644–0.0863 km²; these are sensitivity
perturbations, not inferred registration corrections. Four deliberately selected
long disagreement profiles agree with a separate bilinear line-of-sight calculation
on all **12 surface/ray combinations**. This verifies numerical explanations, not
independent field correctness; the profiles were selected after seeing disagreement.

A 3×3 neighborhood of 20 m setup offsets uses one fixed **360 m disk around the original
point**, within 400 m of all nine setups. Original fine setup sees 0.0584 km² on that
support; offsets range 0.0295–0.1842 km². All nine pass the existing 10 m technical
observer mask, but neither fine-scale footing nor legal/physical setup feasibility is
verified. The southwest 20 m offset is the largest local value; it is a review sample,
not a recommended relocation. Locations, maps, profiles and rasters are exported.
No fine full-2-km ranking was computed or silently substituted.

## Seasonal relevance

No hunt dates or preferred access point were supplied/found. Summer-like, winter-like
and 25/50/75% winter mixtures bracket uncertain transition use; these numbers do not
encode migration dates, snow response or precise fall occupancy. Existing CPW summer
range covers 100% of eligible targets and supplies no within-AOI range discrimination;
winter range covers 21.35%. The existing shrub/herb composites still differ by bracket.
The 0.25 background remains positive everywhere. Coarse vegetation fractions represent
cover composition, not optical transmission. No new slope/aspect/cover bonuses were added.

At 30 minutes, summer-like selective top ten retain 7 of nominal ten; winter-like retain
5. C0068 and C0095 remain useful contrasting review hypotheses, but season uncertainty
still matters. Fixed morning/evening geometry belongs to the prior hypothetical light
scenarios, not a sun calculation for an invented hunt date.

## Connected-access evidence and exact gaps

Bounded official USFS EDW queries returned 39 road, 33 trail, 26 closed-road, 3 ownership,
39 MVUM-road and 5 MVUM-trail features. The recreation-points query returned **zero**.
Provider geometry documents the `RAINBOW LAKE TH` road 7724.2A and the Steers Gulch
7726 / Little Mill mapped junction. Derived endpoint coordinates and selection rules
are retained. Neither establishes parking rights or a verified public approach to it;
the latter is explicitly a mapped junction, not an invented trailhead. The named TH
road endpoint is 858.5 m from the closest downloaded trail feature; it was not snapped
to that trail or promoted to a verified trailhead coordinate.

Exact intersections form a graph; gaps are not automatically snapped closed. A deterministic
depth-first connectivity witness is exported, with no route cost optimization. The nearest
network point is split into the graph so a witness ends there, not at an entire road's end.
Only C0064 connects to one of those mapped entries in this bounded inventory: a 4.650 km
mapped witness from the Steers junction, followed by a **2.276 km straight unknown gap**.
That straight line is a diagnostic of missing evidence, not an off-trail proposal.
The other five closest network components lack connection to either chosen entry in this
inventory. This is a data/connectivity result, not proof that physical access is impossible.

| Position | Closest mapped road/trail gap | Mapped entry connection |
|---|---:|---|
| C0064 | 2,276.1 m | Witness only; entry approach and final gap unverified |
| C0090 | 78.2 m | Not established |
| C0068 | 705.5 m | Not established |
| C0025 | 2,136.0 m | Not established |
| C0049 | 526.6 m | Not established |
| C0095 | 109.8 m | Not established |

All six points fall in the mapped FS category. This is insufficient evidence of connected
legal access. The ownership service distinguishes FS/NON-FS, not private/public permission
classes. Full provider road/trail/MVUM attributes are retained in source files and traced
segment details. Motor designations are not pedestrian-rights certifications. Source
acquisition/edit dates were not supplied per feature; retrieval was 2026-09-26. USFS
service copyright/license strings are blank and remain unspecified in the manifest.

The [2025 Gunnison MVUM](https://www.fs.usda.gov/sites/nfs/files/r02/gmug/publication/Gunnison%20RD%20North%20Final%20MVUM%202025%20March%20Update.pdf)
was inspected as dated motor-use context, not 2026 closure clearance. The
[current forest alerts page](https://www.fs.usda.gov/r02/gmug/alerts) returned HTTP 403.
Current orders, public approach/parking evidence, rights through non-FS segments,
trip dates and physical final-gap review remain exact missing inputs. No hike/gain
preferences were supplied. No field-ready candidate or actionable target was certified.

## Review packet and verification

Open `runs/correction/review.gpkg` in QGIS: all 150 points, chosen attention patches,
distance bands, access witnesses/gaps/entries, provider roads/trails/closed roads,
FS/NON-FS ownership, study support and nearby C0064 setups. Component scores and scenario
CSV rows accompany it. Existing obstruction terrain remains intact outside excluded targets.

`analyst/` contains overview, access, matched geometry, profiles and local setup maps,
plus the separate method/rank key. **Give reviewers only `blinded/`.** It contains six
neutral imagery maps, six blank setup reviews and 48 fixed score-independent target
patches. Each gets the predeclared 15-minute imagery review and proposed 30-minute field
dwell with unchanged optics; the prior north-development/south-held-out split and
continue criteria are retained. The earlier full comparison packet remains untouched.
Do not tune on held-out reviews or count these selected diagnostic profiles as validation.

[USGS/USDA NAIP source records](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer)
identify imagery acquired **2019-09-14**, native 0.6 m. Locked source IDs were exported
at 1 m for 600 m setup windows and 4 m for 4 km context. Exact requests, timestamps,
source records and checksums are retained. This dated aerial imagery cannot establish
current foreground vegetation, ground sightlines, deer detection or antler judgment.
Automated inspection checked map rendering/alignment only; no human ratings were fabricated.

Verification: **17 tests passed**, including the previous 13; synthetic optional-terrain
monotonicity, exact knapsack vs exhaustive subsets, fixed patch area/cost and disconnected
network gaps are added. GPKG read-back checks all 150 coordinates and EPSG:32613.
Matched-grid/source checks and selected independent LOS profiles passed. Eleven substantive
output files are byte-identical across repeated runs, including scores, geometry/profile
CSVs, access details and blank review sheets. All 3,340 old controls still match hashes.

Two complete runs took **13.75 / 14.20 seconds**, observed peak RSS **327 / 331 MiB**;
final output cache about **49.5 MB**. New retained downloads total **34,665,732 bytes**.
Initial attention-only run was 4.89 s; local geometry 1.03 s; access 1.65 s; rendering
accounts for much of the remainder. Caps: 75 MB download, 600 MB generated data, 2 GiB
address space, 900 seconds/command. Existing 1 m input was reused. Measurements apply
only to this cached 150-candidate pilot, not unit-wide performance. Current environment
uses its existing system-site-enabled venv; Matplotlib reports unavailable Axes3D due
to mixed installations, but this experiment uses only inspected 2D output. No packages changed.

## Reproduction and next evidence

From this workspace with the preserved baseline/comparison inputs and outputs:

```bash
.venv/bin/python -m glassing.correct acquire
.venv/bin/python -m glassing.correct attention
.venv/bin/python -m glassing.correct imagery
.venv/bin/python -m glassing.correct all
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m glassing.correct verify
```

All stages accept `--config configs/correction.json`. `all` is an offline cached-input
run of attention, geometry, access and packet; acquisition/imagery are explicit network
stages. `geometry`, `access` and `packet` also run independently after their documented
inputs exist. Downloads are checksum-verified and cached. `verify` checks frozen controls
and new source checksums; it does not rerun tests or assert human correctness. Exact frozen
snapshot reproduction requires these archived controls; newly generated timestamped GIS
files on another computer are not silently accepted as the original control.

Before any itinerary, obtain actual dates and an independently documented public starting
point/parking approach; resolve current orders and final access gaps; independently review
C0064 and adjacent setups plus C0068/C0095; then complete blinded setup/target reviews with
blank/failed sessions retained. Expert selections remain pending the earlier collection
protocol. No observations were used to tune this pass. The next useful evidence is legal,
usable setups and independently inspectable targets, not additional model coefficients.
This milestone is complete at the engineering evidence checkpoint; routes remain stopped.
