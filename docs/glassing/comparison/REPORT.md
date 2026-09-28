# Matched comparison checkpoint — 2026-09-26

**The implementation is runnable and reproducible, but the added complexity has not
shown independent benefit.** Summer habitat weighting is nearly redundant with raw
terrain area here. Glassability changes choices markedly, but most change comes from
uncalibrated searchability and inspection assumptions. A targeted fine-terrain check
raises a substantial geometry concern at the leading raw-area candidate. Further work
is justified as a small independent access/geometry/manual review, not a larger model
or a field-ready recommendation system.

## What was held constant and preserved

Original glassing/core.py, configs/gmu54.json and runs/gmu54 remain unchanged. Audit
found no blocking defect in that reproducible control: original six tests and recorded
DEM/candidate/score/CSV/GPX hashes passed. New M1 recomputation differs by at most
4.44e-16 km² (floating arithmetic). Same 64km² pilot, 150 candidate points, target and
technical observer masks, 2km radius, eye 1.7m, target 0.8m, curvature 6/7 and proposed
30-minute observation session are used throughout. No route/hike time was invented.

M1 is the original unbounded terrain-visible area. M2 is habitat-weighted visible area.
M3 adds target searchability, distance/task response, perspective, stipulated light
and an inspection-area surrogate. All export unbounded and **common equal-effort**
scores separately. Thus raw control remains reproducible without pretending its full
visible area can be searched in 30 minutes. Four nominated positions per method mean
four independent 30-minute sessions (120 observation minutes), not a multi-point route.
Reachable positions and follow-up/stalkable targets remain separate evidence fields.

## Inputs and model assumptions

CPW summer and winter ranges are current retrieved agency polygons, with feature edit
dates retained; they are broad use information, not cell occupancy or buck-specific
predictions. Summer range covers 100% of eligible targets and winter range 21.3514%.
One source polygon had nested shells outside the pilot. OGR MakeValid changed its
statewide geometry area but **zero analysis-grid cells**; both raw and repair record
are preserved. First preparation correctly stopped on that invalid geometry.

USGS RCMAP 2023 tree, shrub and total-herb cover are 30m annual estimates served by
USGS EROS WCS. Tree fraction is never interpreted as ray transmittance. The live
service supplied an approximately 30m reprojected subset; nearest sampling aligns it
to the 10m terrain grid. Only 0.05625% of eligible target cells lack cover estimates;
those remain flagged and have neutral plus open/dense sensitivity treatments.
Exact acquisition days are unknown/mixed, not the retrieval date. Terrain, cover and
range vintages differ; recent change, local understory and actual openings are unknown.

The interpretable, deliberately uncalibrated formulas are:

- Habitat: `floor + (1-floor) × (0.6 × seasonal_range + 0.4 × browse)`; default floor
  0.25. Summer browse is clipped `(0.5 × shrub + 0.5 × herb)/0.6`; winter browse uses
  `shrub/0.6`. Background-only, winter and floor 0.1/0.5 alternatives retain unexpected
  use terrain. No slope/aspect/road bonuses or independent multiplication of correlated
  shrub/herb components. These constants express hypotheses, not fitted ecology.
- Target searchability: relative factors 1/0.6/0.25 for tree fraction below 0.1,
  0.1–0.4, or above 0.4; multiplied by 0.75 for shrub fraction above 0.3. This is a
  cover/opening hypothesis, not optical transmission or observed detectability.
- Distance: piecewise curves at 0/500/1000/2000m. Detect `[1,.95,.7,.25]`, classify
  `[1,.75,.3,.05]`, antler judgment `[1,.4,.1,0]`. Scale 0.75/1.25 sensitivities.
  One hypothetical optics/operator profile is shared across methods; no magnification
  or universal optical range is inferred from these values.
- Perspective: target terrain normal dotted with the direction toward the observer,
  bounded below by a relative floor of 0.3. This is not projected deer body area.
- Light: stipulated sun azimuth/elevation 110°/15° morning and 250°/15° evening, not
  calculated sunrise, a dated ephemeris or a deer-behavior forecast. A diffuse floor
  plus normal/sun incidence models illumination; a 25° viewing/sun cone incurs up to
  50% glare penalty. No terrain-horizon shadows, weather or tree shadows are modeled.
- Inspection: multiply by `min(1, minutes × 0.02 km²/min / visible_km²)`. This assumes
  uniform attention over visible terrain. It may reward compact views and penalize
  large views that a skilled observer could selectively search; the rate is arbitrary,
  not calibrated. Raw equal-effort scores have 121 ties. They cannot usefully establish
  which large view is best without attention/dwell evidence.

Habitat and target searchability use related cover information in distinct causal
roles; a multiplicative interaction remains. Feature ablations expose it rather than
claim independent evidence. Every major factor is switchable; parameters and all
scenario outputs are retained. No weather/pressure behavioral claims are made.

Foreground and intervening canopy stress are **OFF in main M3**. At 32 terrain-visible
targets per candidate, explicit half-cell ray samples preserve both endpoints above
bare earth. Tree cover >=20% is treated as a potential solid 5/15/25m column in a
stress scenario. The first 30m belongs to foreground; last 30m is reserved for
target-side uncertainty; the middle is intervening. No DSM puts the deer on treetops.
This is not measured crown geometry or vegetation-aware deer visibility: canopy
fraction cannot say which ray intersects a crown; solid columns omit under-canopy
windows; target and foreground openings may move by metres. GDAL itself still handles
bare-earth viewsheds; sampled stress rays do not replace it with a validated vegetation
engine. Conditional Wilson intervals describe 32-ray sampling variability only, not
uncertainty in assumed heights, cover errors or deer detection.

## Comparisons and stability

| Comparison against main M3 | Spearman rank correlation | Top-ten overlap |
|---|---:|---:|
| Raw terrain M1 | 0.315 | 0/10 |
| Habitat M2 | 0.322 | 0/10 |
| No habitat weighting | 0.996 | 7/10 |
| No target searchability | 0.646 | 1/10 |
| No distance response | 0.776 | 3/10 |
| No perspective | 0.823 | 6/10 |
| No light | 0.943 | 7/10 |
| No inspection limit | 0.613 | 0/10 |
| Evening light | 0.813 | 4/10 |
| Winter-like use | 0.713 | 5/10 |
| 60-minute dwell | 0.799 | 5/10 |

M1 versus M2 has rho 0.99975 and **10/10** top-ten overlap. Their top four nominations
are identical. This pilot offers little evidence that the summer habitat layer adds
decision value. Larger changes from searchability and inspection are consequences of
the selected formulas, not proof they recover more deer or better views.

The first stratified-random draw is C0025/C0052/C0132/C0006. One point per spatial
quadrant is drawn from the SAME technical common pool; 100 deterministic replicates
are retained. Scores do not affect sampling. Legal feasibility remains pending. This
is a candidate-pool conditional random benchmark, not a uniform draw over all land.

| Nominator (4 × 30-minute sessions) | Mean raw km² | Mean M3 surrogate |
|---|---:|---:|
| M1 / M2 (same positions) | 3.1740 | 0.03187 |
| M3 | 1.2200 | 0.04833 |
| First stratified-random draw | 0.8925 | 0.02770 |

These are model cross-scores, not independent evaluation. An objective favoring its
own selections is expected. Scales cannot be compared across columns. No unique
portfolio coverage, approach time or total hunter-hour benefit was calculated.

Coarse terrain: 30m averaging gives raw rank rho 0.93672 and 7/10 top-ten overlap
against 10m. Centre-cell target rasterization yields 63.6804 versus 64.0000km², a
0.50% boundary-area difference that is reported, not silently normalized away.
The same observer coordinates land in coarser terrain cells; that is part of the test.

Dense reference: a centred 2×2km square, 100m candidate lattice, 400 points, compared
with nine original local points. Best glass surrogate is 0.04277 versus 0.03696,
**15.72% higher**. Best raw area is 2.7844 versus 2.9283km²: the lattice is not a
superset and did not beat the original raw point. This measures score opportunity,
not independently useful coverage or candidate recall in the field. It suggests
candidate spacing can matter under M3 but does not justify unit-wide dense generation.

Exploratory fine terrain: one USGS 2019 1m tile, two 400m-radius checks, common 10m
comparison cells. At C0064 the 1m result covers 0.0659km² versus 0.1266km² in the
control and disagrees on 27.24% of eligible cells; observer ground differs by -1.21m.
At C0090, areas are 0.2799/0.2766km², disagreement 1.20%, ground difference -0.11m.
Independent fine-terrain bilinear rays agree with GDAL on 40/40 sampled rays per point.
Source vintage, surface detail, horizontal realization and sampling are confounded;
1m is not field truth. Both product catalogs state metres/NAVD88; no vertical
transformation was performed. No 2km fine-area ranking or fine-canopy model is claimed.

Coarse canopy stress blocks, on average, 54.7% / 92.9% / 97.8% of sampled visible
rays at assumed heights 5/15/25m. About 2.23% of sampled paths touch unknown cover.
The 15m path penalty gives rho 0.357/top-ten 3/10 relative to main M3. Such extreme
sensitivity means these assumed columns should not be promoted to a production score;
it does not establish that 93% of actual sightlines are vegetatively blocked.

## Five explained review alternatives

All have unknown access and require independent setup/approach review. They are NOT
field-ready hunting recommendations; the field-ready shortlist remains empty.

| Position | Why it is included | Important limitation |
|---|---|---|
| C0064 | Raw and habitat winner; 3.3936km² visible; shoulder/ridge-break proxy | Only 17.7% of visible area allotted under scan surrogate; large local 1m discrepancy |
| C0068 | Second, distinct habitat alternative; 3.2582km² raw, 2.6046 weighted | Actual habitat winner is also C0064; not misrepresented as a different winner |
| C0090 | Main M3 winner; compact 0.5716km² view, distance factor 0.914, full surrogate inspection allocation | Benefits strongly from assumed compact-view/scan-rate rule; no actual opening check |
| C0025 | Score-blind stratified-random alternative; 1.7801km² raw | Control selection, not a model recommendation; unknown access |
| C0049 | Strong median rank across declared scenarios; 0.7996km² raw, distance factor 0.856 | Robustness is conditional on the chosen scenarios, not ecological confidence |

Component means, ranks, coordinates, provenance and uncertainty flags are in
alternatives.csv. Numerical decomposition makes these choices reviewable; it does
not establish model efficacy.

## Independent checks, review and remaining hypotheses

Thirteen offline tests pass. New checks cover positive habitat background, ordered
uncalibrated task curves, inspection bounds, perspective and glare geometry, separate
foreground/path obstruction with ground endpoints, unknown cover, switches collapsing
to raw, access-evidence behavior and deterministic score-blind random selection.
Native GeoPackage read-back checks CRS, counts and coordinates. Two complete runs
produce identical 12 selected numerical/CSV/review artifacts; the original control
hashes remain unchanged. Source and prepared-raster checksum guards are active.
Comparison and fine-resolution maps were visually inspected for grid/extent issues.
These are engineering checks, not ecological or field validation.

The predeclared protocol exists before new outcomes; geometry repair/unknown-cover
handling and post-ranking local fine checks are explicitly recorded as amendments.
Expert selections are absent, comparison pending. Import support retains author,
timestamp, rationale and original coordinates; no generated point is called expert.
No human imagery adjudication, field observation, sighting or independent deer-use
validation was supplied or manufactured.

Blinded packet contains nine unique nominated positions, eight fixed radial target
patches each, 15-minute imagery review and proposed 30-minute field sessions. Two
positions are in the northern development half and seven in the southern held-out
half. This uneven small sample is not a powered method comparison; do not tune on
held-out reviews. Out-of-study patches are context-only and identified. Reviewers
receive only blank sheets, neutral map and instructions, not scores/arm key. Current
legal access/closures must be verified before visits. Review thresholds—80% usable
setups, no critical access failures, and 15% independently useful-area gain OR 25%
planning-time savings without worse false-visible rate—remain untested.

## Cost and stop decision

One-thread complete run: **12.58 seconds, 348468 KiB peak RSS (~340MiB)**; repeat
12.55 seconds, 347284 KiB, no swaps. Main scoring plus sampled stress ~4.95 seconds;
30m comparison 0.18s; 400-point dense comparison 3.36s; two fine checks 0.21s. These
exclude original network transfer. Inputs total 265,403,481 bytes; generated experiment
outputs about 82.4MB. Combined baseline + new source downloads ~1.917GB, below the
original 2GB ceiling. Fine DEM download used an explicitly amended 300MB comparison
cap. Cached acquisition rerun needed zero new bytes. Existing system dependencies
were reused; no paid services, sudo, publishing or Git changes.

For identical windows and 28 scenario settings, a linear compute-only extrapolation
from main scoring is ~33 seconds per 1,000 candidate evaluations. It excludes data
acquisition, new-area preparation, route legality, review and larger-grid I/O; it is
not a unit-scale performance claim. Current small-grid/command budgets remain in force.

**Stop here.** The added complexity deserves only a limited independent test of the
specific assumptions that change decisions. First adjudicate C0064's local terrain
and actual observer openings, then obtain blinded expert selections and connected
access evidence. Calibrate inspection/searchability only on development observations;
reserve untouched locations for confirmation. Do not add more habitat coefficients,
canopy machinery, routes or detection probabilities until that evidence supports them.
