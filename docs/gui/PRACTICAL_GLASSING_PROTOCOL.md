# Practical glassing experiment 1 — frozen before new rankings

2026-10-21. Engineering comparison, not biological or field validation.
Base: local `48eb71010dc1d24a5214b5bf4976e72d8557fa49`, one TrailScout commit
above public main `c594668152783eb8895c8c76284b10bb5fbfba62`. Existing dirty GMU
pack/approach work is retained separately. Branch: `feature/practical-glassing-opportunity`.
Recoverable original changes and full protected SHA-256 inventory are in
`.gui/practical-glassing-evidence/baseline/`. No pushing or merging.

## Order of implementation

1. Baseline checks and inventory; reuse the existing versioned GMU pack and TrailScout.
2. Add a sealed, content-addressed LANDFIRE 2025 companion package with official
   legends, raw analytical classes, window reads, coverage and explicit unknowns.
3. Pure community/observation/best-view functions and a separate review adapter.
   Keep terrain and fall-mixed v1 unchanged. Extend existing access/profile code
   only for reproduced safety or correctness gaps; no alternative routing stack.
4. Deliver an opt-in practical review in the existing local application: class
   overlays, supported opportunity, distance bands, fixed-budget scan sectors,
   exact complementary static shortlist, saved/exported evidence. Keep existing
   route plans distinct from this static comparison unless fully recomputed.
5. Real comparison, sensitivity, independent numerical/routing checks, browser
   workflow, release gate, performance and final preservation audit.

## Fixed comparison

The claimed 549/500 pools are absent from their expected local paths; do not
search unrelated disks. Check the local catalog. If absent, record replication
blocked and use separately labeled available real saved pools (`2`, `soap-creek-v1`)
and bounded real TrailScout corridors. Preserve exact candidate coordinates,
terrain masks, target/standing filters, radii, count and spacing. Manual/working
revisions must remain explicit. Do not manufacture R0080/R0003 coordinates.

Five arms on common supported cells, with full unknown-area accounting:

1. Established terrain/target comparator and exact union.
2. Untouched fall-mixed H×G and exact weighted union.
3. Community H with v1 G and unlimited attention (observation held fixed).
4. V1 H with practical observation and finite attention (habitat held fixed).
5. Community H with practical observation and best-view complementary selection.

Report individual ranks and up to five positive-marginal locations, same separation.
Evaluate all selections under common terrain, v1 and combined reference policies.
Report physical and weighted overlap/Jaccard, support, distance bands, rank changes,
nearest movement distances, known zeros versus unknowns and negative results.
Saved-pool static collections are NOT feasible daily routes. Route-effort evidence
comes only from actual TrailScout entry/legs/return calculations with independent
distance/ascent limits. Missing entry/permissions means conditional, not feasible.

Separate full-pipeline pilot: equal candidate budgets and corridor/entry settings,
baseline versus practical proposal ranking; never present changed pools as matched
rescoring. If proposal/route integration is unreliable, explicitly defer it and
publish the useful static review rather than claiming a new optimized itinerary.

## Predeclared engineering policy

LANDFIRE release-specific traits: aspen, aspen/conifer, conifer, oak/mountain shrub,
sage/browse, herbaceous meadow, known nonhabitat, otherwise unsupported. Retain raw
class names/codes. All supported browse-capable groups receive equal forage index 1;
meadow 0.5; conifer 0.35 with unknown understory. These are planning assumptions.
H = 0.8 × forage index + 0.2 × nearby cover fraction (90 m, full valid halo).
Known water/developed/barren receive exactly zero; unmapped classes stay unknown.
One bounded juxtaposition mechanism; no repeated edge/pressure bonuses.

Target concealment reuses v1 G once. Default leaf state unknown uses no leaf-off
discount; explicit partial/off scenarios reduce only the deciduous tree component
by 15%/30%, leaving branches/understory/mixed evergreen unknown. No clear-aspen mask.
Distance/task curves are engineering preferences, not detection probabilities;
spot/identify/assess must remain separately labeled. Default identify: knots at
0/500/1000/1500/2000/3000 m with values 1/1/0.6/0.25/0.1/0. No reward beyond radius.
Standing 1.7 m eye and 0.8 m target preserve old masks. Other posture choices require
fresh geometry, never merely a score change. Foreground is unsupported until inspected;
bare-earth views are explicitly conditional on foreground/intervening vegetation.

Attention uses fixed 30°/500 m polar patches and full footprint costs, inherited
0.02 km²/min + 0.5 min overhead, conservative 0.25-min knapsack, 30 min default.
Only selected whole patches contribute. Costs never shrink to visible/high-value
cells. Depth overlap is unresolved; full-footprint cost is conservative, not a
calibrated search rate. Neutral light is default; actual solar logistics remain
separate from habitat and legal hunting hours. No invented sunlight gain.

Best-view utility is sum(area × cellwise maximum visit q); exact float64 reductions.
Duplicate views cannot earn twice. Unknown lower/upper bounds are assumption bounds,
not confidence intervals. No normalization by known area. Streaming per candidate;
no candidate×cell×scenario cube. Tie order is stable by ID.

Sensitivity, before seeing leaders: forage conifer 0.2/0.5; meadow 0.35/0.65;
context 0/90/180 m; uniform distance; spot/assess; 15/30/60 min scan; unknown/partial/
off foliage. Posture, foreground, perspective/light, walking pace and road changes
are separate geometry/route experiments where data supports them, otherwise deferred
explicitly. No tuning to make favored points win.

## Release decision

Default remains established/v1 unless real common-policy comparisons demonstrate a
concrete practical benefit with acceptable support/access/effort tradeoffs. Passing
tests or higher own-objective score is insufficient. No biological superiority,
legal/safe route, calibrated search time or independently validated sightline claim.
Initial transfer cap is the stricter existing 250 MiB per companion acquisition,
20 GiB disk reserve; no optional point-cloud download. Measure actual bytes/time/RSS.
