# Workflow acceptance coverage

Run `./gui/check` with the project Python environment. Verification uses disposable workspaces and state; it must not use the owner's server or rewrite historical analyses. A passing test count is not a claim that every workflow has been exercised.

| Behavior | Execution level | Evidence and limits |
| --- | --- | --- |
| Small, narrow, irregular and fragmented observer areas | Real preparation and candidate generation | 150, 600, 2,000 and 5,000 budgets; 16 geometry/budget combinations, eligibility, unique cells, empty eligibility and repeatability. Exhausted and undersized recommendation cases also run scoring. Large-budget generation is not a full 5,000-view performance test. |
| Small-area 600-location search | Real worker plus browser | Submit settings and boundary, approve sources, generate recommendations and report effective spacing. |
| Target criteria and standing eligibility | Known-answer arrays and real search worker | Combined elevation/slope/aspect/tree/shrub criteria, flat and unknown aspects, unknown cover, unchanged DEM, optional clearing eligibility, exact manual coordinates and manual-only report/exports. Matching area drives recommendations and refinement; original scores remain preserved. |
| Filter-first controls and saved approach preview | Real saved viewsheds and browser | Single count input, density preview, automatic matching shading/reload, zero-match retention, changed-criteria reranking, canonical input comparison and enabled saved-path preview with disabled selection while editing. |
| Interrupted transfer and post-download analysis failure | Actual job service, worker, owner and Fetcher | Controlled local provider; faults injected at response reading and scoring. Retry preserves cumulative transferred bytes, partial files and approved requests. |
| Cached retry, changed request and damaged cache | Actual worker | Unchanged requests reuse files; changed URL and corrupt bytes are rejected without replacing evidence. |
| Provider error response and recovery | Actual sampling worker plus focused checks | HTTP 200 XML is retained outside the reusable cache; a matching legacy error entry is recovered, a fresh checksum failure remains visible, and the unchanged plan completes when a local provider supplies a valid TIFF. Also checks HTTP errors, truncated rasters, range errors, extent/unknown-cover rules, transfer ceilings and concurrent publication. Live USGS availability is separate. |
| Consent changes | API and worker guard checks | Settings and allowance changes reject old signatures. API launch is mocked in focused validation tests; these are not complete journeys. |
| Transfer ceiling, storage reserve and ETA | Focused tests | Includes actual fetch instrumentation, durable ledger boundaries and interrupted sources. Provider speed and disk exhaustion are simulated. |
| Reload and recovery | Browser with real worker | Step 1 progress is visible without opening job history; reload after failure and during retry; Open results clears generation recovery and reload retains completed results. Desktop and 900 px screenshots. |
| Find → approaches → scene → confirmation | Browser with actual services | Both the existing fixture and the newly generated/recovered 600-location run use an imported synthetic network and a terrain-only scene. Checks shortlist/dismiss/restore, gates, selection, viewing, confirmation and reload. |
| Coverage display and stale replies | Browser with controlled original/filtered tile timing/errors | Loading/ready/incomplete states, retry, rapid selection and cached reuse. Failure injection must reach the active filtered endpoint. Timing is deliberately controlled. |
| Coverage retention and preparation | Real raster tile benchmark and browser without request interception | Repeat tiles perform no reprojection; explicit batches prepare each setup at its normal selection zoom, retained sources avoid return requests, HTTP caching survives reload, and dismissal/restoration is exercised. Disk-priority, budget and job/storage pause guards have focused tests. |
| Explicit coverage batches | Browser plus helper checks | Displayed ranking, default 10 and 5/20 options, per-setup viewport preparation, one background request at a time, pause/cancel/resume, retained completed URLs, failed-tile retry, ranking invalidation, HTTP cache reuse, desktop and 900 px. |
| Suggested approaches and overrides | Real service/browser and solver checks | Two shortlisted setups automatically receive one recommended path each; reload reuses choices. Explicit alternative mode requires a choice. One-objective path/cost matches the previous Recommended result exactly; barriers still return no path. Manual drawing/copying and preflight guards remain covered. |
| GMU trail visibility | Browser canvas pixel assertion | Retained unit trails remain above opaque imagery; desktop and 900 px captures include unit context in the scouting workflow. |
| Roadless distance overlay | Metric geometry checks and real-pack browser | Exact known-distance sides, offscreen roads, adjacent source tiles, coverage-edge exclusion, trail exclusion, imported roads within GMUs, source corruption and bounded inputs. Browser checks toggle, actual transparent pixels above opaque imagery, distance/opacity changes, reload, empty coverage and desktop/900 px layout. |
| Detailed lidar recovery | Mock transport faults plus actual A0087 acquisition/render | Bounded connection/read retries, exact byte resume, source validators, budgets and non-retryable errors. Actual retained approved A0087 plan completed and rendered fine ground and inferred vegetation; see [evidence](SUGGESTED_APPROACHES_2026-10-20.md). |
| Coverage visible above imagery | Browser canvas pixel assertions | Opaque local online/saved imagery fixtures expose occlusion of actual coverage API tiles. Checks switching and returning, opacity, imagery toggles, comparison entry/exit, desktop and 900 px. Separate from the HTTP-cache journey because routing disables caching. A loaded/ready label alone cannot pass this check. |
| Help dismissal | Browser mouse, keyboard and touch | Hover exit, Escape while focused, click/outside click, Tab and scrolling; desktop and 900 px screenshots. |
| Existing scenes, exports, training and historical controls | Existing backend/browser acceptance | Historical source/output audits; no historical regeneration. Scene acquisition tests include fixtures and mocks, not live lidar acquisition. |

## Release procedure

1. Add a regression that fails for the reported behavior before fixing it. Record the original failure; avoid treating fixture/setup errors as reproductions.
2. Run focused regressions during development, then the complete required check after changes stabilize.
3. Inspect desktop/900 px screenshots and retain logs, actual worker metrics and preservation audits.
4. Report separately what ran through real services, what used mocked boundaries, what was only inspected visually and what remains untested. Add each discovered defect to the mandatory suite.

External provider responses in the new recovery fixtures are routed to localhost; unexpected external requests fail the fixture. Live catalog availability, production download speeds, field clearing, legal access and a global optimum are not certified. Larger output budgets can still stop at the existing processing/storage guards; bounded search is not a promise that every requested evaluation fits those limits.

## Recovery compatibility

`test_gui_source_reuse.py` exercises real preparation and analysis workers with
network requests forbidden. It covers exact-byte imports, archive-independent reuse,
product/year/query/footprint rejection, corruption, provenance changes, concurrent
publication, interrupted copies, space checks, review refresh, and exact candidates,
scores, rankings and raster masks against identical original raw files. The transfer
browser journey also checks the local-source review dates/links at desktop and 900 px.

Approval version 2 identifies source requests, boundary/settings and allowance independently of estimates and cached byte totals. Older failed plans need one explicit **Refresh plan / recover partial preparation** and review. Verified files are retained. Legacy interrupted bytes that were never recorded cannot be reconstructed; the migration notice discloses that limitation. New plans retain a durable cumulative transfer ledger across retries and allowance reviews.

Checkpoint identity includes sampling version, implementation checksum, prepared inputs and candidate pool. An incompatible checkpoint stops intact instead of being silently reset. An implementation mismatch is checked before preparation rewrites intermediate files; changed inputs require a new run.

## Complementary collection checks

`test_gui_complementary.py` verifies the exact A10/B9/C8-disjoint answer (A+C,
18 cells); identical/zero-gain views; retained and unknown manual positions; rank
and ID ties; eligibility and spacing; partial-byte packed windows; and the byte
cache budget. Disposable real-owner outputs exercise API calculations, exact unions
and incremental areas, explicit atomic additions, retained decisions, dismissal and
restoration, empty filters, pending and published working revisions, missing moved
masks, source corruption with preserved mtime, and stale additions. No historical
analysis is regenerated.

`browser-complementary-check.mjs` is mandatory in `./gui/check`. It uses an actual
analysis worker and live backend in an independent synthetic run, checks coverage
and contribution pixels, collection preparation, reviewing/changing size, explicit
additions, dismissal/restoration, unchanged individual ranking, and 1500/900 px
layouts. Controlled delayed responses are fetched from the actual backend, then held
to check obsolete size, filter and run responses. These delays are correctness
fixtures, separate from timing measurements. The real-area benchmark command is
`.venv/bin/python -m gui.complementary_performance`; it uses new processes and
disposable caches, verifies the resulting analytical union independently, forbids
source downloads, and reports three-repeat cold/warm/resize medians and peak RSS.

## October 17 audit regressions

`test_gui_audit_regressions.py` covers failed job submission cleanup using an actual
harmless process group; invalid job types without rewriting their bytes; catalog
quarantine; stale annotation revisions; equal-size/equal-mtime target corruption
after warm display generation; snapshot restoration and its retained recovery copy;
and responsive job status under 40 stalled optional browsing requests. Additional
regressions cover damaged cancellation/waiter/shutdown paths, conservative cache
cleanup, healthy tile bursts with bounded provider concurrency, and cache hits
bypassing stalled providers.

`browser-audit-regressions.mjs` exercises per-setup drafts through navigation/reload,
a delayed real save with further editing, separate/duplicated tabs, starting-revision
conflicts after reload, explicit recovery of a closed tab's draft, failed required
foliage, hidden list DOM,
and 150/600/1500/5000 candidate UI pools. The large pools are controlled API response
fixtures for rendering/interaction, not analytical performance measurements.

The release runner serves a deterministic optional transportation image locally.
Analytical coverage and saved scene assets still use actual services. Browser-cache
journeys must avoid Playwright request interception. Specialist journeys explicitly
create their required workflow through `browser-fixture.mjs`, so running them alone
does not require another browser test to have completed. Seeded fixture decisions
are not evidence of browser rendering; the actual full workflow and required-asset
failure journeys verify rendering gates independently.

For investigation, `./gui/check --browser-only --keep-going` runs later journeys
after a browser failure and records `browser-results.json`; its exit status remains
nonzero if any journey fails. Normal `./gui/check` remains the required release gate.

## Dense first-person recovery and compact controls

`test_gui_scene_recovery.py` uses a known plane with more than 800,000 measured
ground returns to verify dense local triangulation, tile seams, support and no
extrapolation. Completed lidar/imagery cache fixtures forbid HTTP, check stale-plan
reuse and current estimates, reject changed identity/corruption, and verify that
approval files and cumulative transfer ledgers remain byte-identical.

`browser-scene-recovery-check.mjs` is mandatory in `./gui/check`. It creates its own
synthetic run, exercises actual download-free basic generation after a controlled
detailed failure, retains the failed detailed diagnostics, and checks that cancelled
jobs, failed basic preparation and replies after dialog closure cannot start more
fallback work. A controlled saved-asset failure exercises **Retry opening view**
without new preparation jobs. Compact controls and 1500/900/450 px layouts are
checked separately from the real A0136 cached-data replay. Live acquisition and
field fidelity remain outside this evidence. See [the recovery report](FIRST_PERSON_RECOVERY_2026-10-18.md).

Browser waits must poll actual job status before checking publication. In particular,
do not use an async `waitForFunction` predicate for API polling: the installed
Playwright predicate path can accept a Promise before its boolean result resolves.
Use explicit request polling with terminal-failure and timeout checks instead.

## Habitat scoring checks

`test_gui_habitat.py` is discovered by the existing `test_gui*.py` release group.
It uses independent scalar/geometry/packed references, known zero versus unknown,
source-boundary and isolated patch checks, strict settings, metric transfer and
visibility alignment, exact weighted unions, actual saved API/overlay services,
source/derived corruption with unchanged size/mtime, current missing retained masks,
profile restore/isolation, stale preference/addition rejection, dedicated tile bursts,
lock ordering and an actual opt-in owner/search worker with provenance products.

`browser-habitat-check.mjs` is registered both as `test:habitat` and in the release
runner's explicit browser list. Its independent synthetic source/run tests the real
source→search→ranking→connection→collection→tile path. Actual connection exclusions
block the highest-ranked setups; all connected alternatives must still be selected
from the full pool. A controlled response fixture supplies stale original individual
ranking fields alongside actual connection evidence. It checks actual priority pixels,
Off/on/reload, a retained unsaved draft and the same mounted notes editor, actual
weighted totals, error/retry, late old-profile replies, 1500/900/450 CSS px layouts,
and unchanged decisions. Off is checked after removing the review-filter adapter on
a habitat-generated run, against its separately published established recommendations.
The order selector identifies quality-adjusted area explicitly; an independent UI
response fixture checks that an insufficient-data card has no numbered habitat rank.
The actual saved 549-area path is exercised read-only when available. Results must
remain visible at 900px while scoring and after completion; Find preferences scroll
within a bounded region. Controlled delays/errors are engineering fixtures, not live
provider or wildlife validation. Existing scene recovery and multi-tab draft journeys
remain mandatory in the normal release gate.

The existing scouting journey uses an independent disposable fixture. It holds an
actual automatic proposal across an explicit network import, then verifies the late
proposal cannot clear that selection. Its download-only AOI is outside already cached
fixture inventory, so the original download-cap/approval assertions exercise a genuine
uncovered area even after earlier source-reuse journeys.

Find's generation journey also delivers an older unprepared plan alongside a newly
completed job. It must re-read the plan and start exactly once; a genuinely unprepared
fresh plan must still fail without a start. Transition failures retain condition,
fixture state, body and screenshot diagnostics. Existing duplicate/cancel/stale-input/
reload/provider/cap assertions and their time limits remain intact.

Read-only measurement helper:
`.venv/bin/python -m gui.habitat_performance --out /tmp/habitat-performance.json`.
It uses disposable state, forbids downloads/visibility generation, applies the same
saved hard filters to both arms, independently recomputes weighted collection totals,
and reports context, scoring, setting-change, overlay and collection timings. Exact
scenario greedy collections are evaluated under common default settings. Spatially
varying synthetic packed pools include 549/1500/5000 masks, with densities, bytes,
three repetitions and cumulative process peak RSS. Synthetic packed-reduction timing
excludes saved-mask validation; real-area scoring includes that service boundary.
A saved 600-location real pool is not substituted if unavailable. Protected sources,
owner records, prepared scenes and historical masks must be byte/path-audited separately.

The completed habitat release evidence, observed counts, exact commands, screenshots,
performance and preservation audit are in
[HABITAT_IMPLEMENTATION_REPORT.md](HABITAT_IMPLEMENTATION_REPORT.md); counts are
observations for that release, not fixed discovery targets for future checks.

## GMU local packs

`test_gui_unit_packs.py` is in the mandatory GUI discovery group. Its twelve focused
regressions cover atomic publication, bounded exact pixel windows, separate derived
provenance, offline network imports, oversized/outside observer rejection, corruption
with unchanged size/mtime, missing assets, TIFF companions, insufficient storage,
failed and successful updates, interrupted registration, damaged progress, cancellation,
retained partials, retry and cumulative transfer accounting. Artificial source bytes
in those tests are engineering fixtures, not evidence of real GMU readiness.

`browser-unit-packs-check.mjs` is registered in the mandatory release list. It selects
the actual registered GMU 54 pack, loads local relief/context, checks unit/custom/old
run switching, generates a fresh real-data search, and checks desktop/900 px layouts
with browser errors and external requests forbidden. A missing real local pack is a
failed prerequisite, not a simulated ready badge.
In a separate page, controlled colored satellite tiles verify default-on imagery
above the real unit relief, the off preference across unit/custom switching,
scoped offline failure and retry. Those tiles test display composition only;
the core workflow phase still forbids external requests.

The decisive standalone command is `.venv/bin/python -m gui.pack_acceptance`. It
starts a separate server and all child workers with external socket/DNS connections
blocked from startup, uses disposable state/workspaces, generates four new real areas
including a DEM tile seam, completes screening/Approach/Basic Inspect/Save/export/reload,
rejects a whole-unit request before launch, and opens the actual saved Basic scene in
the browser. It also exercises the existing habitat preference on one new area.
No owner server is used. See [pack report](GMU_PACK_REPORT.md) for final artifact paths
and the distinction between real workflow evidence and synthetic fault injections.
