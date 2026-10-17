# Guided scouting workflow — 2026-10-16

This change guides provisional desktop scouting through Find → Approach → Inspect →
Save. Existing analyses, original coordinates, scene bundles and historical reports
remain evidence. Mapped departures and modeled approaches do not establish permission,
safe travel, deer presence or field validation. No itinerary solver or new scoring
coefficients are introduced.

## Behavior

- Find has a persistent shortlist-to-approaches action and per-suggestion Shortlist /
  Dismiss controls. Cyan is combined matching terrain, violet is terrain covered by
  at least two collection members, and pink is the focused member's unique terrain.
  These versioned masks use existing analytical masks; greedy selection is unchanged.
  Pending dismissal hides obsolete coverage, supports rollback and Undo, and decision
  notices expire after eight seconds excluding hover/focus time.
- USGS Transportation supplies viewport browsing context through bounded 256 px
  requests and the disposable display cache. It creates no network inventory,
  analysis allowance, observer boundary or target mask. Verified local line layers
  remain interactive above that context. Provider failure leaves local context usable.
- Analysis sources resolve to verified covering inventories, with explicit source
  overrides retained in secondary details. Each new approach spot receives an
  unconfirmed 2,000 m proposal clipped to valid obstruction terrain; exclusions and
  observer/target polygons retain their separate roles. Preflight checks eligible
  mapped departures before calculation.
- New approach calculations default to 25° and reject modeled slope limits above
  35° in the UI and service. Historical scenarios retain their recorded limits.
  Preferences carry to unreviewed spots; reviewed spots restore their own drafts.
  Every distinct alternative has a matching card/route color, with solid mapped
  portions and dashed off-trail portions. Brush avoidance raises tree/shrub weights
  to at least three and never lowers a stronger selected weight. Coincident paths
  remain combined rather than being fabricated as different alternatives.
- Calculate and Use approach show immediate pending states and prevent repeated
  submissions. Submitted settings freeze during calculation. Returned scenario/job
  IDs drive polling and result retrieval. Save failure retains the chosen alternative;
  successful saves advance, and the final approach advances to Inspect.
- Best-available scene preparation selects one acquisition deterministically by
  verified cached coverage, relevant coverage, known acquisition date, transfer and
  stable identity. It never blends acquisitions. Missing detail allows terrain to
  prepare with an explicit limitation. Bounded NAIP plans lock dated source records,
  show their transfer/storage estimate in the same approval, and verify returned
  extent/CRS/size before reuse. Source hashes and context version enter new signatures.
- Inspection starts at 1,000 yd, clamped to the saved supported extent. New best-detail
  bundles prepare context to the evaluated radius within the existing resource guards;
  historical bundles keep their extent. Plan-map targets turn the camera; clicks on
  rendered ground select plan-map targets, while drags rotate. Target, first terrain
  obstruction and inferred vegetation have different symbols/labels. Horizontal and
  modeled line-of-sight distances remain diagnostics, without shooting-distance advice.
  Standing-position refinement retains the 30 ft limit and explicit Update waypoint.
  Confirming advances to the next setup and then Save collection.
- Shared numeric inputs preserve empty/partial text, reject incomplete values, suppress
  autofill and normalize leading zeros after editing. Radius presets are actual
  500–3,000 yd in 500 yd steps; exact legacy metric choices remain visible/readable.
  GUI adapters accept fractional metric radii without modifying frozen engine files.
  The final partial inspection band retains the existing full 500 m patch cost.

## Verification

Backend suites cover source identity/integrity, exact shared/unique masks, slope policy,
explicit confirmation, preference persistence, legacy scenarios, actual fractional-radius
owner execution and report export, missing-provider fallback, dated imagery acquisition,
storage, scene/observer diagnostics, source/target separation and existing workflows.
All 227 backend tests passed across the relevant GUI, approach, owner, scene,
vegetation and workflow suites. The shared-number / Find browser check passed, as did
the desktop and 900 px two-setup guided journey: slow submission feedback, save-failure
retry, preference carry-forward, dismissal/Undo, timed notices, two-way target picking,
drag rotation and automatic final saving. Observed click feedback was 2.1–6.5 ms.
Delayed history and direct-job responses are also injected to verify that they cannot
erase or regress a newly returned job. Retained browser diagnostics: `/tmp/huntmaps-check-41z6nwbq`; its preservation audit
checks 7,418 protected files and reports no changes. Formatting/build and a separate
fresh preservation check passed under `/tmp/huntmaps-check-ns2ipbr_`.

A backend harness run reported a metadata-only preservation failure after the original
mtime of the byte-identical `glassing/transfer.py` was restored during that run.
All its test suites and build had passed; the subsequent fresh audit reports no changes.
The historical content manifest and the start-of-task owner-record hashes also match.
No preservation manifests were rewritten. The existing single-setup workflow also passes
with explicit terrain preparation and final collection saving (`/tmp/huntmaps-check-cowvdiri`).
All browser and worker mutations use isolated state/workspaces.

The 711-location benchmark uses actual cached Soap Creek inputs in a separate `/tmp`
workspace, with 61 network records and 81 comparison definitions (80 accumulated history
fixtures plus the new submission). Its owner run took 16.40 s with no downloads.
The summary-history endpoint took 26–29 ms; active comparison retrieval took 78–83 ms, and direct job
polling took 2.5–3.0 ms. Neither operation validates the full history. Full validation of all historical comparisons remains
an explicit operation and is linear in history size. Benchmark code:
`gui/guided_performance.py`; retained measurements: `/tmp/huntmaps-guided-711-final/timings.json`.

Submission/subprocess timings are recorded on new scenarios/results. Browser display
latency is correlated with the returned job/scenario under isolated `scouting-metrics`.
Performance measurements describe this workspace, not a general runtime guarantee.

Live lidar/NAIP bulk-provider reliability is not inferred from fixture checks. The
source protocol is checked with bounded provider responses, cached reuse and injected
failures; the UI still requires the displayed preparation approval before bulk transfer.

## Provider references

[USGS Transportation service](https://carto.nationalmap.gov/arcgis/rest/services/transportation/MapServer)
and [USGS NAIP ImageServer](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer)
provide browsing and dated scene sources respectively. Browsing data never become
analytical network evidence automatically.
