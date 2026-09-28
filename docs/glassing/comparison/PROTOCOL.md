# Predeclared matched comparison protocol — 2026-09-25

Registered before computing any new model rankings. Later amendments must be dated,
justified and distinguished from this declaration. This milestone tests model mechanics
and decision sensitivity; no observed biological or planning benefit is available.

Control: frozen runs/gmu54, same 64 km² study, 150 candidates, 10 m DEM, 2 km radius,
1.7 m observer / 0.8 m target, curvature 6/7. Every arm uses identical technical
observer/target masks, unknown access assumptions and 30-minute dwell budget. No route
or hike time is fabricated. Legal-feasibility and field-actionability comparisons
remain pending without independent connected access evidence.

Arms: M1 raw terrain-visible area (exact original control); M2 relative seasonal
use-weighted visible area; M3 M2 with separately switchable target searchability,
distance-task response, target-facing perspective, simple light/glare and finite
inspection-area surrogate. Report unconstrained score and inspection-limited score,
not probability or a predicted count. Random comparator selects spatially stratified
points from the SAME candidate pool, ignoring all scores. Mark it technically eligible,
not legally feasible until access verified. Expert comparison pending unless independent
points with author/time/rationale are imported; never label generated points experts.

Habitat hypothesis: additive blend of CPW summer/winter range membership and one
vegetation browse/opening composite, with >=0.25 background weight everywhere.
No slope/aspect/road proxy in habitat. Summer-like and winter-like scenarios are
alternatives, not hourly seasonal forecasts. Vegetation affects habitat and searchability
through separate causal hypotheses; ablate each to expose multiplicative interaction.
Do not combine correlated tree/shrub/herb layers as independent evidence probabilities.

Vegetation: target-side cover/opening proxy; separate foreground risk; separate
intervening canopy stress test. Neither canopy fraction nor an area fraction is optical
transmittance. Keep bare-earth endpoints. Coarse cover plus assumed opaque vegetation
heights yields only stress bounds on sampled rays, not vegetation-aware deer visibility.
Main M3 excludes foreground/intervening penalties until independently supported;
explicit on/off stress variants quantify their effects.

Sensitivity fixed now: summer/winter/background-only; habitat floor 0.1/0.25/0.5;
feature leave-one-out; distance scale 0.75/1/1.25; detect/classify/judge tasks;
morning/evening/no-light; 15/30/60-minute inspection budgets; 10 versus 30 m terrain;
100 m dense lattice within the centred 2×2 km reference square. Fine DEM/canopy only
if authoritative coverage, budget and likely decision relevance justify it. Report
Spearman rank correlation, top-ten overlap, and independently defined missed-candidate
score opportunity. Changed ranks do not demonstrate improved scouting.

Independent evaluation criteria (not computable from model weights):
- Geometry: fraction of preselected target patches actually inspectable, severe
  false-visible patches, usable setup fraction, access failures.
- Planning: analyst minutes to an independently reviewed equal-effort plan.
- Later field work: deer/buck encounters per TOTAL hunter-hour, all blank sessions,
  duplicate herd uncertainty; do not treat habitat scores as validation labels.
- Provisional continue gate: >=80% practical setups and no critical access failures;
  >=15% independently inspected useful-area gain OR >=25% planning-time savings,
  without worse false-visible rate. These are decision thresholds, not powered claims.

Blind review: pool unique nominated positions from M1/M2/M3/random; conceal arm/rank
and score in reviewer sheet. Same 15-minute imagery review and proposed 30-minute
field dwell, optics and target-patch count per position. Balance order and morning/
evening visits within spatial blocks; do not expose key until sheets are frozen.
Use northern half for development and southern half held-out confirmation. Do not tune
on held-out observations; if inspected for tuning, label exploratory and reserve new
locations. No review observations are manufactured. Access verification precedes visits.

## Engineering amendments / exploratory extensions

Before first successful score computation: CPW summer geometry failed validity
(nested shells outside the pilot). OGR MakeValid was accepted only after measuring
zero changed raster cells across the complete analysis grid. Original source retained.
Unknown vegetation open/dense stress alternatives were added before inspecting ranks.

After first ranking inspection: finer DEM inventory shows six 1m tiles. Select only
the one covering the raw and main-glass top candidates, and compare their local 400m
terrain masks at 1m and 10m. This is an exploratory foreground/resolution check, not
held-out validation or a 2km fine-scale score. Raise the comparison download cap
from 200 to 300 MB to accommodate the one ~262 MB tile; combined retained downloads
remain below the original 2GB baseline ceiling. No fine canopy product was identified
in the small acquisition inventory; coarse cover stress remains explicitly hypothetical.
