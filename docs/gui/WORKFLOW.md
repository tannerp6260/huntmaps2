# Find, reach and inspect setups

Launch `./huntmaps-gui`. The numbered stepper stays available while reviewing earlier work. Changing screens keeps later results. At 900 pixels, **Setups** opens the list drawer beside the active task.

1. **Find setups.** Draw or import the observer area: where you would consider standing. **Confirm boundary** saves a drawing; an unfinished drawing cannot authorize preparation. Normal defaults are a 2,187-yard view radius, 150 Locations to test and 20 Top spots to recommend. The count accepts 12–5,000 evaluations; recommendations accept 1–200, bounded by that count. Approximate density relates the count to your observer area. Terrain I want to see configures elevation, slope, facing directions and tree/shrub cover before generation. Avoid standing in dense vegetation is optional and off by default. Manual waypoints are optional. New GUI runs use the existing 30-minute inspection assumption; recovered plans retain saved assumptions.
2. **Review downloads**, then **Generate setups**. Metadata inspection starts no bulk transfer. The reviewed plan shows estimated new bytes, verified cache reuse and included sources. The suggested ceiling is estimated new bytes plus 20%, rounded up to 10 MB, with a 10 MB minimum. It limits transfer, not quality. There is no fixed 1900 MB ceiling: plans must leave 20 GiB free, including temporary source copies and processing headroom. Custom allowances trigger renewed metadata review. Approve the concrete plan before bulk acquisition; changed sources require review again. Partial files and conservative transfer accounting remain retained.
3. New expanded-search runs start with **Recommended setups**. New recommendations rank by visible area matching all enabled target criteria, then original visible area and stable point ID. Zero-match points remain available in All evaluated setups but are not recommended. **All evaluated setups** retains every computed location, ordered by saved terrain-visible area. Existing runs keep their original list and rankings. Applied filters rerank matching visible terrain and suggestions, using original visible area and stable ID for ties. Matching coverage opens automatically for new filter-first runs; Show original terrain restores the full saved view. Original engine ranking and historical leading positions remain available. Cover and unknowns describe evidence, not deer probability or verified access. **Shortlist** advances a setup; **Dismiss** hides it from the default list and offers **Undo**. The **Dismissed** filter offers **Restore**. **Remove from shortlist** keeps a setup available for reconsideration; saved scenes and approach scenarios are preserved. Compare and export select separate collections.
4. **Compare approaches.** Review one shortlisted spot at a time, starting with best matching coverage. Confirm a search area that includes both spots and mapped roads/trails. Copying the observer boundary provides an editable draft that still needs confirmation. The first comparison starts automatically for an uncomputed spot when the area and sources are ready; balanced preferences and a 30° modeled slope limit are defaults. Preview one alternative at a time, including distance, mapped/off-trail portions, climbing, slope, unknown cover and its elevation profile. **Use this approach & next spot** selects and advances. **Dismiss spot & next** removes it with Undo. Change this spot's sliders and **Recalculate approaches** as often as needed; earlier comparisons remain in its history. Failed/cancelled/no-path work requires an explicit retry. No path found describes this bounded model, not proof of inaccessibility. Continue to inspect after every retained spot has a current selection.
5. **Inspect and confirm.** **Prepare views** creates an explicit batch for setups with selected current approaches. Shared sources are deduplicated. Terrain-only preparation uses the existing DEM offline; fine ground and measured vegetation remain unavailable. For lidar, inspect available acquisitions, dates/unknown dates and vertical references, select one acquisition, and review downloads before preparation. Each reviewed batch has its own approved transfer allowance; historical cumulative downloads remain informational. The former 500 MB lifetime cap is removed. Storage checks keep 20 GiB free; existing processing limits remain enforced.
6. Open the scene. **Confirm setup** requires successful rendering, recorded viewing of the current scene and a current selected approach. **Inspect now** is available earlier, but final confirmation keeps the same requirements. The confirmed collection includes scene fidelity, unresolved evidence, destination waypoints and provisional approach exports. There is no itinerary or walking-time prediction.

Scenes are modeled from recorded sources, not live camera feeds. Acquisition bounds do not guarantee ground returns. Terrain-only scenes can satisfy the viewing requirement. Permissions, parking, crossings, footing and current vegetation still require independent review.

Workflow decisions live in versioned `workflows/<run>.json` records in the configured GUI state directory. They do not rewrite historical annotations. Existing Keep annotations appear as legacy candidates. Existing Soap Creek scenes and approach scenarios remain available. Legacy nearby previews use their old anchor scene; prepare an exact waypoint scene before confirming a moved/manual destination.

Coordinate/revision changes invalidate affected approach/viewing confirmations. Changed approach inputs require an explicit current selection again; unchanged scene evidence remains reusable. Replaced scene inputs invalidate viewing. Stale submissions are rejected. Backup includes workflows and ready pointers; maintenance protects workflow definitions, approach results and published scenes. Completed analyses, original coordinates/scores and historical evidence remain unchanged.

Verification: `./gui/check` runs isolated Python, build/format and browser checks, including a new-run three-stage synthetic journey. Its fixtures are engineering checks, not hunting opportunities. See [workflow verification](WORKFLOW_VERIFICATION.md).

Download review shows an approximate transfer-time range. Recent measured provider speed is preferred, followed by a small idle startup probe; the fallback is 20 Mbps (2.5 MB/s). Cached-only plans need no download. Provider behavior, connection changes and retries can extend the estimate; processing time is additional.

Download bars show bytes received against estimated new bytes, measured speed, elapsed job time and approximate remaining transfer time. Progress records are scoped to each job and survive reload. Stalls say Waiting for data; unknown totals use an indeterminate bar. Processing uses item counts where available and an indeterminate bar otherwise. A finished stage does not imply the entire job is finished. Cancel and recover beside the current job.

Capacity is checked at review, job start, transfer writes and source assembly. A monitor checks the workspace, GUI state and temporary filesystem during processing and stops the job group if the reserve is threatened. Output estimates remain approximate; previous results and usable partial sources are retained on failure. Changed source plans or allowances require renewed download approval.


Coverage review shows **Loading coverage**, **Coverage ready** or **Coverage incomplete · Retry** for the selected setup and current map viewport. The blue overlay appears together once its tiles have loaded; panning or zooming can require more tiles. Ready describes display completion, not validation of vegetation or access. Changing opacity reuses the existing map sources; unrelated basemap loading does not hold coverage readiness.

The next three scored, non-dismissed setups in the current list order prepare in the background after the selected coverage is ready. Preparation is sequential, covers only the current map area/zoom (at most 64 tiles per setup), and stops on map movement, selection/input changes, active analysis or less than 20 GiB free. Its tile counter is separate from selected-view readiness. Tile APIs accept the optional `X-Huntmaps-Prefetch: true` header for this bounded preparation; the backend also enforces the job and storage pause guards. Moving to a different area or zoom can still require additional tiles.

Up to eight recent coverage sources remain in the browser, with at most 64 inactive tiles per source. Background preparation works sequentially on likely next views, neighboring zoom levels and whole-area previews, pausing for interaction, active jobs, less than 1 GiB available memory or the 20 GiB free-space reserve. HTTP-cached tiles can survive reloads. The disk cache remains bounded by `HUNTMAPS_DISPLAY_BUDGET_MB` (default 2 GiB), prioritizing viewed, non-dismissed coverage over generic/background assets. Dismissal makes display assets eligible for eviction; it does not delete analytical viewsheds, outputs or history. When the cache fills, even non-dismissed display assets may be regenerated on demand. Restoring a setup reuses any surviving assets.

Help boxes close with Escape, outside click, focus leaving, scrolling or navigation. Hover-only boxes close when the pointer leaves; clicked boxes stay open until dismissed.

Expanded normal GUI search allocates 80% of the automated budget to repeatable, spatially distributed terrain sampling and up to 20% to nearby alternatives within 150 m of up to ten leading points, at 50 m offsets. Broad spacing starts at 150 m, then decreases deterministically through 100, 75, 50, 30 and 20 m down to the analysis grid resolution as needed; local alternatives deliberately test closer positions. Duplicate automated grid cells are not evaluated twice. Manual coordinates remain unchanged and are additional to the automated budget. Exhausted eligible cells finish with fewer evaluations and an explanation; a limited neighborhood can leave refinement budget unused. This is a bounded search, not a global optimum.

Default nearby-cover preference requires mean mapped tree cover below 10% within 30 m, with at least 80% known tree coverage. Radius and threshold are editable. Other known cover follows; insufficient coverage remains last. Shrubs are displayed separately. Coarse cover cannot verify a small clearing, nearby individual trees or eye-height branches. Bare-earth terrain remains the obstruction surface; this preference does not change target masks or numerical terrain scores.

Search calculations run sequentially in batches of at most 20 locations with the existing 1536 MiB memory, 900-second batch time, 3-million-cell grid and 800 MB output guards, plus the free-space reserve. Completed batches are checkpointed for recovery. Processing shows counts and an approximate remaining duration after measured work; preparation and report generation are additional. New runs include SEARCH.md, recommendations.json and search metrics. Original engine leading collections and reports remain available separately. No historical analysis or prepared scene is regenerated.

### Failed-run recovery

Review the failed stage and its originating error beside the task. Identical approved source requests can resume with verified cached files; changing requests, boundary/settings or allowance requires renewed review. Estimates and cached reuse refresh after an acquisition succeeds even if analysis fails. Transfer bytes are cumulative across attempts, including interrupted reads. Legacy approvals require one explicit refresh/review; old unrecorded partial bytes are disclosed as unknown. Completed results appear in the selector after job completion, including after a browser reload.

## Refinements for new users

Settings begin with a short description of finding standing locations. Locations to test controls the calculation budget; Top spots to recommend controls the initial suggestions. These are two different quantities, with one input each. New runs keep main suggestions 150 m apart by default, with adjustable spacing and grouped nearby alternatives. All evaluated points and original scores remain available. Historical recommendation collections are unchanged.

Roads and trails are included and reused automatically in new reviewed plans. Proximity sampling starts at 880 yards in straight-line distance, which is neither walking distance nor permission. Source overrides are advanced controls. Visible terrain facing direction filters coverage only; approaches use steepness, not slope facing direction.

Generate setups, Acquire roads and trails, and Prepare views approve their displayed source plan and transfer allowance. Updated plans must be reviewed again. Time estimates prefer recent actual provider transfer rates, then a small interruptible startup probe (at most 2 MB or 5 seconds), then a 20 Mbps default. Failed probes keep the default; no manual speed measurement is required. All transfer allowances remain cumulative across retries.

Loaded coverage stays visible when the map moves; additional tiles load around it. A loading or incomplete label distinguishes missing tiles from a complete view. Changing setup, revision or filters cannot reuse another setup's shading. Imagery requests still depend on provider/network performance; missing terrain remains a gap.

Manage saved results supports archive/unarchive and permanent deletion preview. Archived results are hidden from the normal selector but remain accessible. Deletion is offered only for generated, unprotected runs with no retained run depending on their outputs. It requires idle jobs and a matching preview token. Shared sources, supplied inputs, prepared bundles and frozen historical controls remain retained; no old result is deleted automatically.

Approach search area bounds where the calculation searches; include both destinations and a mapped departure. Areas to avoid are optional user-supplied exclusions. No-path messages explain missing geometry, source coverage or model constraints before exposing technical evidence. One changed destination invalidates its independent approach only. Moving/restoring coordinates never silently restores final confirmation.

## Filter-first search and visible progress

Target criteria restrict eligible visible cells, never the obstruction DEM. Enabled ranges combine; any selected facing direction qualifies, and no selected direction means any aspect. Flat terrain has no aspect. Required unknown data cannot match and is reported separately. Optional nearby-cover eligibility uses the saved radius/tree threshold and at least 80% known neighborhood coverage, excluding automated standing points before sampling and refinement. Manual coordinates remain unchanged and retain their eligibility evidence.

The current generation task appears in a sticky status card in Step 1, with progress, cancellation, errors and Open results. The current plan is retained for reload in the browser session. Historical job details remain secondary.

Saved approach previews remain available while editing another comparison, including outdated paths clearly labeled as saved evidence. Selecting an approach still requires current sources, current point revision and unchanged normalized inputs. Input comparison ignores object/set ordering and compares coordinates at eight decimal places.

## Guided review and display units

The GUI shows areas in square miles, distances in yards, and elevations/heights/climbing in feet. Preset radii retain their original values; engine calculations, saved measurements, source metadata and exports keep their recorded units. Decimal distance inputs accept `.75`; unfinished entries such as `.` remain editable and disable the affected action with an explanation.

Review order, focused spot, individual settings, previewed alternative and latest scenario are saved per run in `approach-reviews`. An existing order stays stable; new/restored spots append in coverage order. Reloads and back navigation preserve the review. Marker clicks in Step 2 show only shortlisted points; Step 3 shows points with selected approaches. Editing one spot does not invalidate selections for other spots, including selections from older multi-spot comparisons. Coordinate/source changes reopen affected requirements. A guided session's final confirmation requires all retained spots to have current approaches; early inspection remains available.

Maintenance protects review definitions and existing approach results. Reviewed permanent run deletion explicitly includes that run's review record; it retains shared data and protected evidence. See [guided review verification](GUIDED_APPROACHES_2026-10-04.md) for tests and measured per-point overhead.

## Coverage batches and per-setup approach boundaries

In Find, **Prepare next** prepares 5, 10 or 20 views in the displayed order,
including the selected setup. This prepares display tiles, not additional terrain
analysis. Cancel or resume while retaining successful tiles. Jobs and map movement
pause preparation. Ranking/filter/revision changes invalidate the displayed batch.
A loading card explains missing shading until the active coverage has rendered;
map panning retains the smaller status. Preparation covers normal setup views,
not every zoom or future cache eviction.

**Plan approach** opens a separate review for each shortlisted setup. The queue
number counts setups needing a decision, not itinerary stops or path alternatives.
Draw and confirm a boundary for that setup, check the mapped departures inside it,
then explicitly calculate alternatives and select an approach. New setups do not
inherit another boundary or start calculation automatically. Existing saved
boundaries/results remain readable. Boundary copying and imports are advanced,
explicit actions requiring confirmation; exclusions remain optional.

Visible-terrain and observer filters stay in Find. Approach preferences affect path
costs: climbing means total ascent; steepness adds a penalty below the hard slope
limit; tree and shrub preferences penalize mapped cover. Zero removes a preference;
distance always contributes. Defaults and the 20 m calculation grid are unchanged.
Nearby departure mode starts where you leave a mapped road/trail within one mile;
including network travel also needs an explicit network start. Smaller boundaries
reduce the grid's bounding rectangle, but must retain room for credible detours.
Preflight checks geometry and departures; terrain constraints can still prevent a
modeled path. Mapped access does not establish permission.
