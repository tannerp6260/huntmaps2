# Bounded corrective validation — registered 2026-09-26 before new rankings

Preserve both prior runs and their implementation/configuration via FROZEN_CONTROL.json.
No route optimization, habitat coefficient expansion, field observations or automated
image interpretation presented as validation. Compare the same original 150 candidates.

Attention: demonstrate optional-low-value nonmonotonicity of uniform attention. Add
`selective_patch_attention_v1`: nonnegative rewards in fixed polar patches (30° bearings,
500m radial bands, 2km extent). Each patch costs its FULL geometric area / 0.02km²/min
plus 0.5min overhead. Hidden/ineligible portions still incur search cost; no isolated
cell cherry-picking. Exact binary knapsack with conservative quarter-minute cost rounding.
Optional patches may be ignored; additional nonnegative reward or an optional new patch
cannot lower optimum. Retain no-penalty and uniform controls at 15/30/60 minutes.
Test 20/30/45° patch widths, rate 0.01/0.02/0.04 and overhead 0/0.5/1 minute. These
are uncalibrated attention assumptions, not detection rates. No multi-view route solver.

Season: no dates found in current configuration; ask optionally while proceeding.
Use summer-like and winter-like brackets and explicit 25/50/75% winter-like transition
mixtures of the EXISTING two habitat hypotheses. Mixtures are scenario weights, not
fall occupancy estimates or event timing. No new habitat coefficients. Keep background.

Geometry: investigate C0064 with fixed target support and matching coordinates. Compare
existing 10m, native-derived 1m, same-source 1m aggregated onto original 10m grid, and
upsampled aggregated control. Check pixel centre/transform consistency, local elevations,
profiles, observer eye 1/1.7/2.2m and small registration shifts ±1m. Compare a 3×3 setup
neighborhood at 20m offsets, technically sampled but not certified safe/legal. Keep
400m findings separate from full 2km rankings. No vertical datum correction or claim
that 1m is truth. Select profiles to explain disagreement, not count them as held-out
validation; report sample selection explicitly.

Access: acquire bounded official USFS roads/trails, ownership, recreation access points,
MVUM restrictions and current alert evidence. Trace mapped network connectivity from
provider-documented sites; distinguish endpoint snaps and any unmapped final gap.
Do not invent an off-trail approach or infer rights from ownership. No route cost
optimization, driving instructions or legal certification. Any candidate lacking full
approach/permission/restriction/setup evidence remains out of field-ready shortlist.

Packet: five original alternatives plus selected corrected hypotheses; maps/sector
geometry/distance bands/profiles/dated imagery if available. Keep method key and ranks
apart from blinded sheets. Preserve earlier evaluation criteria and held-out review;
none of these automated checks constitutes a human/field validation observation.
