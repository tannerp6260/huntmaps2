# Hunter-area transfer comparison — fixed before a real AOI is supplied

Objective: test engineering transfer and the usefulness of alternative *desktop*
scouting positions. No ecology/detection superiority, independent expert validation,
or timed-route optimization is inferred. Current real-area evaluation is pending.

Preserve old outputs. Use `transfer/FROZEN_CONTROL.json` and
`configs/transfer_model.lock.json`; no coefficient fitting to manual selections.
The new adapter uses existing core terrain candidates/GDAL viewsheds,
comparison components and whole-patch selective attention. Existing entry-specific
scouting modules remain untouched as historical controls.

Design:
- User supplies observer polygon and unchanged manual points before seeing new-area
  automated suggestions. Record any prior exposure; do not call these expert points
  unless independently documented. Preserve all manual points, including duplicates
  in location with distinct source IDs; no rank-based manual filtering.
- Same grid, common target support, eye/target heights, radius, seasonal scenario,
  30min per-position nominal inspection budget and access assumptions for both groups.
  This is a per-position comparison, not unequal-size set totals or a daily itinerary.
- Default150 automated candidates, terrain proxies plus stratified background,
  seeded independently of manual points. No manual seed injection or habitat-maxima
  candidate restriction. At most five automated positions exported, alongside all
  manual positions. Primary ordering is the frozen selective hypothesis; raw area,
  1km distance split and low-tree-cover summary remain separate.
- Targets default to the observer area's radius buffer, optionally intersected with
  explicit target restrictions/exclusions. Terrain retains its additional halo and
  is never erased by target/permission masks. Initial access-data extent is a separate
  10km observer buffer, configurable/expandable after inspecting entry connectivity.
- Local density diagnostic: identical100/150m configurable neighborhood and50m
  offsets around up to two leaders per group, bounded by a stated count budget.
  These refinements never enter the primary automated pool. Report score change
  as density/geometry sensitivity, not independently validated improvement.
- Pairwise full visible-target overlap: intersection km², Jaccard and directional
  fractions, using exactly aligned eligible cells. Spatial proximity alone is only
  a possible recovered setup; inspect overlap and imagery before calling it recovery.
- Human review classifies nearby recovery, materially different opportunity,
  obvious useful misses and questionable high model ranks. Show actual dated imagery
  when available; absent imagery is explicitly pending, never synthesized. Candidate
  source labels are visible, so this is not blinded validation. Agreement with manual
  points is not independent proof of hunting value.
- Access evidence: documented entry points, source-specific route ID/name mapping,
  same-route small-gap repairs and terrain-screened permitted final legs. No hard-coded
  pilot entries. Missing elevation coverage gives missing gain/time, never zero gain.
  Hike preferences are editable and not safety limits. No motorized parking assumed.
- Recommendation after actual review: useful for assisted scouting; needs one named
  correction; or little demonstrated benefit. With missing hunter inputs, no such
  empirical choice is warranted yet. Stop after portability/import handoff.

Keep any subsequent field observations separate and held out from assumption changes.
