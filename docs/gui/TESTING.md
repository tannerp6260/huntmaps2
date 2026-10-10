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
| Per-setup approach setup | Real service/browser | No inherited boundary or automatic calculation; explicit copying/confirmation and primary drawing. Read-only preflight checks destinations, exclusions, selected networks, one-mile departure limit, network starts and grid guards. Exact paths/costs match legacy inputs. |
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
