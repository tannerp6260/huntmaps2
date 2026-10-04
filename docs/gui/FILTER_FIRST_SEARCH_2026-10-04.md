# Filter-first setup search — 2026-10-04

## Result

Step 1 now has one calculation budget, **Locations to test**, and a separate **Top spots to recommend** count. An approximate density preview relates the budget to the selected observer area. The default remains 150 locations and 20 suggestions; the calculation budget remains bounded to 12–5,000 locations and recommendations to 1–200, no more than the budget.

Before generation, users can configure target elevation in feet, slope in degrees, hillside facing directions, and tree/shrub cover percentages. Enabled criteria combine; selected facing directions are alternatives. Recommendations and nearby refinement leaders rank by visible matching area, then original visible area and stable ID. Unknown required data cannot match. Zero-match points remain available but are not recommended. Original visibility, inherited engine scores and its optional ranking remain available.

**Avoid standing in dense vegetation** starts off. When enabled, it restricts automated sampling and refinement using the saved neighborhood radius and tree-cover threshold, requiring at least 80% known coverage. This is independent of target criteria and does not change obstruction elevations. Manual coordinates remain exact. A GUI report fallback handles manual-only runs when no automated locations pass, retaining the prior export formats while explicitly omitting unavailable nearest-automated comparisons. The frozen report implementation is unchanged.

Generation progress, errors, cancellation and Open results appear directly in a sticky Step 1 task card. The current generation plan restores after reload within the browser session. Opening results clears that recovery marker. Inspection time remains a saved calculation detail: new runs use the existing 30-minute assumption.

New runs restore their target criteria and matching shading on opening/reload. Explicit review criteria rerank suggestions using saved viewsheds. Deterministic filter identities reuse coverage caches; a bounded two-entry cache retains read-only target/unknown/standing masks. Location changes invalidate review results; shortlist decisions do not discard them.

Saved approaches can be previewed while editing or after becoming outdated. Selecting an approach still requires current inputs and waypoint revision. Input comparison ignores object/set ordering and compares coordinates at eight decimal places; loading a saved scenario resets drawing/edit state. Saved boundary context remains visible alongside drafts.

## Verification

Verification uses disposable workspaces and state, with external browser requests blocked and a companion app monitored for unintended mutation. The test suite exercises known-answer terrain masks, unknown/flat-aspect behavior, vegetation eligibility, spatial recommendations, deterministic checkpoint recovery, unchanged manual coordinates, manual-only reports, filter restoration, zero-match retention, saved-path preview and current-selection gates. It also runs the existing three-stage, recovery, training, export, viewer, source-transfer, cache and maintenance journeys.

A focused real 48-location plus two-manual fixture completed in 2.13 seconds with 220.24 MiB peak RSS and about 1.80 MB outputs. The isolated 600-location recovered browser run measured 5.77 seconds, 207.96 MiB peak RSS and 13.03 MB outputs for its final search worker. These are small local synthetic fixtures, not predictions for larger real terrain or downloads. Existing memory, grid, batch-time, disk and free-space limits remain enforced.

Desktop and 900-pixel settings and saved-path screenshots were inspected. The 900-pixel view retains task controls and uses the setup drawer without horizontal page overflow.

`./gui/check` passed: 143 backend tests across 12 test groups, formatting/type/build checks, all 18 browser acceptance scripts, and the controlled 600-location recovery/three-stage journey. An additional isolated recovery run exercised the strengthened Open results → reload assertions and completed its three-stage journey. A focused nine-test search/criteria run also passed after the manual-only fallback was added.

Final diagnostics: `/tmp/huntmaps-check-8y6ik50q`; stronger recovery acceptance: `/tmp/huntmaps-browser-recovery-ov8te95f`. The preservation audit checked 9,534 protected files and reported no changes, including owner and companion application records. No files under the frozen `glassing/`, `configs/`, `docs/glassing/`, `data/`, `runs/` or `results/` trees were changed by this implementation or verification.

After the complete viewer suite, the disposable API service recorded 1,165 MiB RSS and a 1,194 MiB high-water mark, including existing scene/viewer caches. These are separate from the search worker measurements and its per-job memory limit. The new two-entry criteria-mask cache stores at most about 18 MB of boolean masks at the existing three-million-cell grid limit.

Filtered coverage's real HTTP-cache journey measured 123 ms to select a prepared setup and 88 ms to return to the previous one, with zero additional return tile requests and 236 recorded HTTP cache hits. The cold page/setup load was 6.50 seconds. These measurements use headless Chrome with software rendering and a local synthetic fixture. Pixel assertions confirmed blue coverage remains visible during movement and above opaque imagery, rather than relying on a ready label alone.

## Limits

This is terrain visibility and coarse mapped cover, not verified clear eye-height sightlines, wildlife probability or legal/safe access. More calculations improve sampling density without proving a global optimum. Spatial separation can return fewer suggestions; nearby alternatives and all evaluated points remain available. Flat terrain has no facing direction. No historical analysis or scene has been regenerated, and no field work or itinerary model has been added.
