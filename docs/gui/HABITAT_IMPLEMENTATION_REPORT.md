# Habitat implementation report

Status: complete and verified October 18, 2026. The integrated opt-in feature, full
release gate, matched measurements and protected-file comparison all passed.

## Behavior and implementation

Find now has Off, **Fall mixed habitat — experimental**, and Custom. Saved-run
preferences use verified existing RCMAP sources and current DisplayRun revisions,
without acquisition, terrain generation or approach calculation. Habitat-aware new
runs use the same objective for local-refinement leaders, spaced recommendations
and GUI re-ranking. Historical analytical code, coefficients, coordinates, original
metrics, source files and visibility pixels remain preserved.

The deterministic pure module is `huntmaps_gui/habitat.py`; source/profile/cache and
current-mask adaptation is in `habitat_service.py`. Fixed coarse structural features
feed H and shared observer-independent G. The primary score integrates H×G per exact
visible matching cell in quality-adjusted m². Physical matching, high-habitat,
priority, scorable and unknown areas stay separate. Fully unsupported points have
insufficient-data status and null individual E. Target-filter unknowns retain their
existing visible-base-mask denominator; habitat unknowns reconcile within matching area.
See [methods](HABITAT_METHODS.md) for equations, settings, source contracts and evidence.

Two independently traced frontend ranking consumers now use canonical backend habitat
order and current metrics. The connection screen's entire eligible pool is screened
before spacing/count selection. Inspection confirmed inherited original matching/
standing fields can survive a working move; habitat mode overrides them with current
adapter metrics/eligibility. Off keeps the established comparator. Metric indices avoid
quadratic candidate joins. Cards, meters, details, selected summary, comparisons,
nearby alternatives and coverage-batch ordering follow the chosen objective. Existing
approach-review queues and revision-bound tab-specific notes remain separate.
New habitat-generated runs also publish established recommendation/nearby IDs from
the same evaluated pool, so Off works when Show original terrain removes the current
review-filter adapter. Find preferences have a bounded scrollable region, keeping
results visible at 900px during scoring as well as after completion.

The optional priority-visible overlay has its own explicit tile layer, immutable
run/profile/candidate/revision URLs and sealed derived raster. Green means priority,
gray nonpriority matching terrain, amber habitat unknown, hidden transparent.
Original viewshed shading remains available. Context support is 40 m on the actual
resampled RCMAP sources, with no DEM-scale habitat edges or species labels.

Packed complementary windows now support exact float64 weighted reductions over newly
covered bits. Greedy selection counts each analysis cell once, retains existing points
and their spacing/count effects, and stops at zero positive utility. Member totals,
inclusion-step marginals, priority physical area and separately denominated overlaps
are explicit. Known/scorable and habitat unknown union areas are reported. Suggestions
remain previews until the existing explicit stale-snapshot-checked addition.

Profiles and selections are durable independent GUI namespaces. Storage, backup,
restore (including profiles created after a snapshot), protection/deletion previews,
and release preservation inventories include them. Derived contexts, scores and
overlays remain regenerable cache assets outside immutable old analysis directories.
Source/context, scoring settings, target filters, current masks, collection decisions
and connection tokens have separate identities. Source and derived corruption with
preserved size/mtime is rejected. Snapshot checks include Off-to-On changes and restored
missing masks. Background scoring/collections use one dedicated worker and bounded
admission; ordinary viewport bursts have two dedicated tile workers. Lock order is
maintenance before feature publication; map transfer is single-flight and memory bounded.

New-run `Preparation` accepts a strictly validated separate habitat payload.
`api_routes.prepare` explicitly builds it into search settings only when enabled;
Off's legacy shape stays unchanged. Canonical settings round-trip through generation,
recovery and dirty-input checks. New search implementation/checkpoint identities and
worker manifests enumerate both habitat modules and the analytical
`habitat-provenance.json` product. No old checkpoint is reset/migrated. Read-only
inventory found **no incomplete normal search checkpoint** outside completed results;
future attempts with an incompatible old checkpoint receive the existing new-run error.
Evidence: baseline directory `interrupted-checkpoints.json`.

Release checks also exposed an existing non-atomic generation poll: an older plan
reply could be paired with a newly completed job and falsely report incomplete
preparation. That mismatch now gets one fresh plan read and another cancellation
check before the unchanged blockers/signature/start logic. Controlled tests cover
both recovery from the stale reply and refusal of a genuinely incomplete plan.
The separate late-proposal fix preserves an explicitly imported network selection.

New local interfaces:

- GET/PUT `/api/runs/{run}/habitat`: independent per-run selection and immutable profile.
- GET `/api/runs/{run}/habitat/{profile}`: current revision-bound metrics/order.
- GET `/api/runs/{run}/habitat/{profile}/export`: current metrics, units and model/source metadata.
- GET `/api/runs/{run}/habitat-tiles/{profile}/{revision}/{candidate}/{z}/{x}/{y}.png`.
- Optional `habitat_profile` on complementary requests, alongside preserved `connection_screen`.

## Matched real-area comparison

The available saved pools are 549 setups (`scouting-2026-10-16222`, 974×968 analysis
cells) and 500 (`scouting-2026-10-18`, 816×838). A real saved 600-location pool was not
found; no substitute was manufactured. Each arm uses the same saved hard target
criteria, exact original evaluated masks and spacing. GUI state is disposable, with
no owner decisions imported. This is a comparison among evaluated candidates,
not a new whole-area search or field validation.

| Observation | 549 area | Current 500 area |
| --- | ---: | ---: |
| Established/habitat top-20 overlap | 18/20 | 17/20 |
| Default habitat greedy unique E, adjusted m² | 1,515,056.75 | 3,593,801.45 |
| Established greedy collection under the same default habitat weights, adjusted m² | 1,488,336.07 | 3,603,922.68 |
| Difference in common-setting E | +1.80% | −0.28% |
| Habitat collection priority physical m² | 3,336,500 | 9,664,500 |
| Established collection priority under common default m² | 3,345,900 | 9,870,700 |

The default habitat 549 collection is A0265, A0071, A0012, A0068, A0470; the established
collection is A0265, A0012, A0071, A0321, A0470. On the current 500 area the habitat
collection is R0080, A0384, A0292, R0003, A0295; established is R0003, R0007, A0003,
A0292, A0035. The small current-area loss is an actual greedy result, not suppressed
or tuned away. Neither objective nor spacing-constrained greedy guarantees a global optimum.

Measured examples illustrate interpretation. A0265 stays first on the 549 area:
1,171,400 matching physical m², all scorable, E=509,211.15 adjusted m² and 1,136,000
priority physical m². Its post-G contributions are 83,401.45 background, 168,834.02
browse, 101,607.29 mixed and 155,368.39 cover; their exact exported values add to E.
Displayed rounded component sums can differ only by rounding.

On the current 500 area R0003 shifts from established first to habitat rank 77.
R0080 shifts from fifth to first. R0003 has more matching terrain (3,029,800 versus
2,846,400 m²), but lower mean mapped G (0.426 versus 0.548), lower supported component
contributions, and more habitat/neighborhood unknown (211,000 versus 74,100 m²).
Its E is 697,910.94 versus 886,380.36 adjusted m². These are proxy measurements,
not a biological explanation of deer presence. R0003's unknown physical area exceeds
the measured E deficit under the loose mathematical q∈[0,1] bound; incomplete support
could matter. No known-area normalization or imputation hides that limitation.
R0080 has 2,681,600 high-habitat physical m² but only 2,552,300 priority physical m²,
demonstrating the distinction between habitat and the stricter glassability intersection.

## Sensitivity and scientific challenge

The predeclared 13 alternatives plus the default include nearby radius pairs,
±20% nonbackground feature weights with whole-profile normalization, milder/stronger
G and each feature ablation. No coefficients were tuned to make a favored point win.
Scenario greedy memberships are evaluated again under the common default settings.

Modest alternatives retain 19–20 of the default top 20 on the 549 area and 18–20 on
the 500 area. Common-default collection E ranges 1,510,255.91–1,515,056.75 and
3,593,801.45–3,605,396.74 m² respectively: about 0.32% spread in either area. Component
ablations can shift more individual ranks (as few as 16/20 retained on the 549 area)
without a comparably large material collection-utility change. The leading current
R0080/R0007 totals differ by only about 0.25%; rank swaps among such alternatives
should not imply confident ecological discrimination. All scenario settings,
rank ranges, IDs, metrics and common-setting totals are retained as machine-readable evidence.

Openness is not equated with habitat: barren H is only the explicit 0.10 background.
Dense shrubs receive a separate glassability penalty. Dense forest retains possible H.
Mixed/cover signals are bounded additive terms and challenged through ablations, not
large repeated edge bonuses. Three-cell patches and integral neighborhood counts
suppress isolated/noisy FFT rewards. Fractional components are never normalized as
exclusive composition and do not identify species. Unknown coverage is explicit;
existing observer and approach constraints remain independent. None of these
engineering checks validates occupancy, mature-buck prediction, optical transmission
or safe/legal access. Current snow migration and annual-product forage conditions
are not inferred. The current CPW D-57 listing was verified; the linked final plan
was not readable and draft/indexed material is not represented as a final-plan review.

## Performance

Final standalone evidence: `/tmp/huntmaps-habitat-final-performance.json`, log
`/tmp/huntmaps-habitat-final-performance.log`, derived artifacts in
`/tmp/huntmaps-habitat-benchmark-p2q0v473`. Command:
`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python
-m gui.habitat_performance --out /tmp/huntmaps-habitat-final-performance.json`.
Python 3.10.12, Ubuntu Linux 6.8 x86_64, 16 logical CPUs; BLAS/OpenMP threads fixed
to one. Each area has an explicit disposable workspace and state. Cold means new
derived cache, with OS page cache left intact. Release servers were stopped during
measurement; downloads and terrain visibility generation were forbidden.

Both real areas reuse the verified 474×455 delivered tree/shrub source grid,
356×342 context cells at 40 m information support. Exact analysis masks remain
974×968 and 816×838 at 10 m respectively. Timings are seconds:

| Operation | 549 setups | 500 setups |
| --- | ---: | ---: |
| Context cold / warm | 0.176 / 0.018 | 0.168 / 0.020 |
| Saved candidate score cold | 7.837 | 4.836 |
| Warm scoring, three repetitions | 0.298, 0.295, 0.298 | 0.264, 0.262, 0.260 |
| Setting change: prepare + rescore range, 13 alternatives | 5.757–7.433 | 4.403–4.672 |
| Priority derived raster cold / warm | 0.038 / 0.004 | 0.032 / 0.003 |
| Weighted collection cold / warm, including service validation/publication | 2.496 / 0.272 | 1.990 / 0.239 |
| Scenario greedy reduction after preparation, range | 0.123–0.192 | 0.170–0.189 |
| Mean visible-mask grid density | 0.358% | 2.197% |
| Cumulative packed-mask cache bytes | 4,713,582 | 12,456,536 |

The setting-change totals include prepared raster creation; that part alone ranges
0.434–0.732 s and 0.376–0.611 s. Radii changes rebuild context; ordinary weights/G
changes reuse features. Actual browser tile rendering is checked separately from
these derived-raster timings. Cumulative process peak RSS was **647.54 MiB**.

Spatial synthetic masks use 768×1021 cells, varied centres/ellipse sizes and terrain
shadow patterns, about 1.22% mean density, exact shared floating weights and five
greedy slots. These are not copies of one mask. Every member marginal and union is
independently recomputed on a full boolean grid.

| Candidates | Packed bytes | Mask preparation + individual reductions (s) | Individual packed reductions only (s) | Exact weighted greedy, three repetitions (s) |
| ---: | ---: | ---: | ---: | --- |
| 549 | 1,124,732 | 3.265 | 0.042 | 0.112, 0.112, 0.110 |
| 1,500 | 3,074,068 | 8.937 | 0.113 | 0.296, 0.300, 0.297 |
| 5,000 | 10,263,066 | 29.997 | 0.379 | 0.975, 0.976, 0.977 |

Synthetic preparation timing includes constructing masks; its reduction timing does
not include saved-file integrity checks. The real-area service timings do. All
predeclared practical budgets passed: context cold ≤2 s; saved cold score ≤15 s;
warm ≤2 s; derived overlay cold ≤2 s/warm ≤0.25 s; 5,000-mask greedy ≤30 s. No grid
or visibility reduction was used to meet a timing budget. Existing resource caps stay.
`.venv/bin/python /tmp/habitat-verify-performance.py` passed the separate final budget,
matched-outcome and metric-reconciliation assertions; log
`/tmp/huntmaps-habitat-performance-verification.log`.

Pending-work dispatch evidence is `/tmp/huntmaps-habitat-responsiveness.json` and
`.log`: a separate actual FastAPI app with disposable state/workspace cold-scored
549 locations in 9.350 s while the release browser was active. All 12 `/api/jobs`
requests finished while scoring remained pending, maximum 0.009156 s. This uses
TestClient in-process transport, not external network/provider latency. The release
audit separately tests responsive notes with 5,000 rendered-list inputs; a real
5,000-location saved-source end-to-end run is not claimed.

## Verification and preservation

Nineteen focused habitat tests pass in disposable state, including the actual
opt-in new-run worker, source NaN/NoData provenance, strict preparation request
construction, exact scalar/geometry/union checks, profile restore, source/derived
corruption, current retained missing masks, concurrency, healthy tile bursts and
lock ordering. Existing search and complementary focused regressions passed (4 and 9).
The registered browser journey has passed its synthetic full service path, pixels,
full-pool screening with inherited stale ranking fields, notes DOM preservation,
reload, errors/retries and late profile replies at desktop/900/450 CSS px.

Final full command: `./gui/check --keep-going > /tmp/huntmaps-habitat-final-release.log
2>&1`, **PASSED**, October 18, 18:02–18:28 MDT (about 26m 9s). The flag records all
journeys on failure and never suppresses a failing result. No stage or required journey
was skipped. Observed counts: **288 backend tests**, including **187** in the GUI
discovery group and its **19 habitat tests**; **31/31 browser journeys**; static format,
TypeScript/build, and the actual interrupted 600-location recovery worker plus its
follow-on workflow. That recovery uses controlled synthetic/provider inputs; it is
not an additional real saved hunting-area comparison. The reported pre-enhancement
269-test/30-journey result was a reported baseline, not this run's verification.

Final diagnostics: `/tmp/huntmaps-check-bldwxo4g`. Exact per-group counts are in
`/tmp/huntmaps-habitat-final-counts.json`; every browser outcome is in the diagnostics
`browser-results.json`. The registered habitat journey exercised actual application
ranking, connection, weighted collection and tile services, with controlled response
boundaries for stale fields, errors, late replies and an unscorable UI row. Its
`results.json` reports 20,038 rendered green pixels, no page errors and the real saved
549-area path. Source corruption/current masks/unknown numerics are tested separately
against actual rasters. Existing notes/drafts, scene recovery, source reuse, owner
records and working-waypoint journeys remained enabled.

Final screenshots, visually reviewed with their respective readiness checks:

- [Saved 549 area, desktop](/tmp/huntmaps-check-bldwxo4g/screenshots/browser-habitat-check/actual-549-desktop.png)
- [Saved 549 area, 900px](/tmp/huntmaps-check-bldwxo4g/screenshots/browser-habitat-check/actual-549-900.png)
- [Synthetic habitat view](/tmp/huntmaps-check-bldwxo4g/screenshots/browser-habitat-check/habitat-desktop.png)
- [Synthetic habitat, 900px](/tmp/huntmaps-check-bldwxo4g/screenshots/browser-habitat-check/habitat-900.png)
- [Effective 200% layout](/tmp/huntmaps-check-bldwxo4g/screenshots/browser-habitat-check/habitat-200-percent.png)

Release defects and diagnostic failures are retained in the progress record: 900px
result clipping, an inadequate initially nondiscriminating fixture, late automatic
proposal selection loss and non-atomic plan/job polling. Focused reproductions and
corrections kept the original assertions/time limits. Earlier interrupted/failed
gates are not represented as final passes.

Closing command `.venv/bin/python /tmp/habitat-verify-preservation.py final-preservation`
PASSED: **31,623 protected files / 4.882815708 GiB**, zero changed, added or missing
paths; **214 frozen release inputs**, zero changes. Evidence:
`/tmp/huntmaps-habitat-final-preservation.log` and
`/tmp/huntmaps-habitat-20261018-pqhsgnuw/final-preservation.json`.
The release runner's independent audit also reports 9,067 source/result paths with
zero changes and separately checks owner/companion records. Initial archive, empty
initial patch, source audit/checksums, interrupted-checkpoint inventory and protected
manifest remain in `/tmp/huntmaps-habitat-20261018-pqhsgnuw`.

HEAD remains `c35f3633c620a72efd13162338f06af99fe55648`. All changes are uncommitted:
29 tracked files and 11 new files within GUI/code/tests/documentation. The same
evidence directory contains `final-review.patch`, `final-new-files.tar.gz`,
`final-changes.json` (exact paths/bytes/hashes) and `final-git-status.txt`.
`git diff --check` passed. No commits, pushes, dependency updates, data deletion,
historical regeneration, owner-server operations or partition inspection occurred.
Verification servers used disposable Ubuntu state/workspaces and were stopped by
the runner. The owner's running GUI was not used for acceptance.

Changed files are confined to the active GUI path and its verification/documentation:
new `habitat.py`/`habitat_service.py`; `search`, `requests`, `api_routes`, worker product
and implementation lists; `complementary`, `working_waypoints`, `scouting_api`,
`tiles`, `maintenance`, `run_management`; frontend `habitat.tsx`, `main`,
`candidate-review`, `connection-screen`, `complementary-views`, `map-layers`,
`layer-order`, `types`, `workspace-ui`, `workspace.css`, and the narrow late-proposal
selection fix in `scouting-tools` and completed-job/fresh-plan recheck in `generation-flow`;
release registration, focused tests, isolated
habitat/scouting fixtures and benchmark helper; these three habitat documents and
workflow/testing guidance. The scene renderer, connectivity solver, source-reuse
implementation and review-draft implementation are unchanged.

Live provider availability and field optical/deer-use validation remain untested by
this enhancement. The inaccessible final Gunnison plan, absent verified LANDFIRE
snapshot, missing real 600-location pool and synthetic 5,000-mask boundary are
explicit limits above. They do not prevent local saved-source use of the base model.

## User instructions

Restart HuntMaps2 to load the backend changes, then choose **Fall mixed habitat —
experimental** in Find for the GMU 54 second-rifle use case. Initially avoid extra
tree/shrub hard exclusions unless intentionally restricting targets. Keep conservative
observer/approach constraints and inspect leading views before relying on vegetation
glassability. Off restores established terrain/filter behavior. Re-ranking does not
shortlist, confirm or plan a route.
