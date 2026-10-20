# TrailScout implementation progress

## Baseline and preservation (2026-10-19)
- Original checkout: `/home/tanner/Desktop/huntmaps2`, branch `main`.
- Actual base HEAD: `c594668152783eb8895c8c76284b10bb5fbfba62` (also externally reviewed reference).
- New branch: `feature/trail-glassing-planner`; worktree: `/tmp/trailscout-worktree`.
- Original index empty; 20 dirty tracked files and 9 untracked sources, primarily prepared-unit support. Inherited source copied by binary patch and explicit untracked-file copy; no owner stash/reset/commit.
- Recoverable patch, index, status, untracked inventory and 35,977 protected file records: `/tmp/trailscout-baseline-20261019/`. Small protected files have SHA-256; large immutable inputs have size/mtime records; source reuse will additionally verify manifests/hashes.
- Listening ports at baseline: 22, 53, 631, 8991, 41115, 34819, 35135. No owner service stopped.
- Hardware: Ryzen 7 5700G, 16 logical CPUs; 14 GiB RAM, ~7 GiB available; 89 GiB free on Ubuntu volume. No other partitions inspected.

## Bounded implementation plan
1. Inspect existing contracts/data; validate real sources; deliver first complete route/viewpoint/return/schedule/save/export vertical slice.
2. Broaden bounded route/candidate comparisons, owner edits, access evidence and browser UX.
3. Independently test numerical/workflow acceptance cases, run actual-service browser journey at desktop/900px, measure cold/warm calculations; fix observed problems.
4. Review diff/UI, verify preservation, write methods and handoff. Only additive task-owned files may be staged/committed.

## Decisions and resource budget, before measurement
- Separate `trail_scout` namespace, local HTTP backend and browser UI. Prefer installed Python/GIS and frontend dependencies read-only; no original environment upgrades.
- Default port 8767; all new state/results/cache under worktree `.trailscout/`, tests in disposable state.
- Read-only source root explicitly `/home/tanner/Desktop/huntmaps2`; no legacy API/worker invoked.
- Initial acquisition cap 250 MiB; derived disk budget 2 GiB; retain 20 GiB free reserve. Reuse prepared sources first. Sequential analytical worker, one active job, bounded candidate/grid budgets; exact limits recorded with each result. No whole-unit fine-grid allocation.
- Terrain, target eligibility, habitat/glassability, observer screening, access evidence and physical effort remain separate.
- Personal profile defaults conservative and explicitly uncalibrated. Return consumes actual traversal effort; rest never resets effort.

## Phase status
Implementation, real-data demonstrations, full release checks, performance measurements and preservation verification complete. Retained worktree: `/home/tanner/Desktop/huntmaps2-trailscout`; task-owned local commit complete.

## Exact next action
Open the retained worktree and run `./trailscout`; review the saved DEMO outings and edit assumptions as needed. No implementation work remains.

## Vertical slice checkpoint
Implemented additive `trail_scout` storage/source/effort/network/spur/visibility/planner/scheduling/export/API modules and React/MapLibre UI, with `./trailscout` launcher. Existing environment used read-only. First headless real Soap Creek comparison: 13 evaluated positions, 5 feasible including 2 new off-trail positions; 14 full route variants evaluated, 10 returned; AM/PM fit individually, combined day fails conservative limits. This early run used 32 maximum candidates, 2.5 km corridor, 1.5 km view radius and 300 m spur envelope; resource limits were not reduced. Terrain source has full requested halo; habitat/context unknowns remain explicit.

Demonstrated defects fixed during the slice: the 20 m spur grid initially extended beyond a 10 m window; explicit inward alignment fixes it. Retracing can produce equal consecutive sampled coordinates with positive traveled chain length; actual traveled distances are now authoritative. Segment-mode boundaries are included in profile samples to preserve exact mapped/off-trail totals. Explicit hunter preset validation initially duplicated a dict keyword; fixed. Installed MapLibre requires its separate worker URL; the initial rendered UI exposed this and now bundles the local worker. A short-climb regression exposed extrema-only smoothing stretching a climb over a preceding flat; replaced with bounded vertical-error simplification preserving climb onset and raw evidence.

Numerical gate: 12 independent tests passed (`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/tanner/Desktop/huntmaps2/.venv/bin/python -m unittest discover -s trail_scout/tests -v`). Fixtures are explicitly synthetic engineering evidence, not real-area recommendations. TypeScript/Vite build passed after worker correction. Initial screenshot was reviewed and its map-worker failure is retained at `/tmp/trailscout-initial-desktop.png`; not represented as a final pass.

Live official service metadata checked: RoadBasic layers 0 roads / 1 motor-closed; TrailNFSPublish layer 0; MVUM_01 and _02 layer 1 roads / 2 trails (layer 0 is a group). NOAA solar equations checked at `https://gml.noaa.gov/grad/solcalc/solareqns.PDF`. New preparation/import path preserves attributed original JSON, bounded queries/counts/metadata, provenance and cumulative bytes in TrailScout state; no owner acquisition worker invoked.

Next action: finish full actual-service browser journey, prepare/compare a second real corridor, independently recompute route and mask union totals, exercise real access snapshots and recovery, measure cold/warm performance, review final UI/diff and preservation.

## Full-workflow checkpoint
The complete gate passed at `/tmp/trailscout-gate-14p61eln`: 27 new backend tests,
31 relevant legacy compatibility tests, formatting/type/build, and the actual-service
browser journey with no fabricated API results. Its browser covers Soap Creek and
Flattop Bench, linked profiles, coverage/access/marginal evidence, morning/evening
and combined rejection, immutable saves/version conflicts, reload and four real
export downloads, pin/reject recalculation, cancellation/retry, delayed real replies,
offline resources and unavailable basemap recovery at desktop/900px. Earlier retained
gate diagnostics include a hidden native-option wait and save-completion test race,
and the deliberately assumed Mill Castle positive result that real data disproved.
Those are not reported as successful field evidence.

A real survey retained negative results for Mill Castle and Beaver Ponds under the
conservative shared profile; no coefficients/screens were relaxed. Flattop Bench
has 14 supported points / 6 route previews, including newly discovered off-trail
points; Sun Creek also yielded a smaller, easier evaluated alternative. Survey
artifacts: `/tmp/trailscout-corridor-survey`; Mill Castle negative evidence:
`/tmp/trailscout-gate-7j0ff92e/browser-state`.

Final review added/fixed: actual elapsed-time arithmetic across fall-back; true
reversed mapped costs in spur search seeds; level-aware topology and exact original
feature endpoints; raw-source/companion checking even on warm habitat-cache hits;
no resealing changed normalized downloads; connected walking evidence to other
entries where supported; alternate pair orders and time-aware dominance; separate
saved outings and explicit stale source/model versions; motor manual restrictions
also update entry eligibility; one live process lease per TrailScout state. The lease
prevents a second launcher on another port from marking a live job interrupted.
Independent corruption regressions failed before their fixes and now pass; evidence
is `/tmp/trailscout-integrity-regression-before.log` and `...core-integrity-after.log`.

Preservation verified after the real/browser work: 35,977 protected records unchanged,
6,227 frozen-control file SHA-256 values matched, original main/HEAD/index/diff/status
identical. Full audit: `/tmp/trailscout-baseline-20261019/verification-before-handoff.json`.

Next action: measure actual cold/warm and edit performance with search settings
unchanged, address measured avoidable cost, run final gate, write final report and
field summaries, then retain the new branch/worktree for review.

## Release verification and measurements
Final full gate passed at `/tmp/trailscout-gate-m9c2z55r` after the restored-preview naming fix: 28 new backend tests, 31 legacy compatibility tests, Black/Prettier/type/build, actual-service desktop/900px browser. The preceding final numerical-code gate also passed at `/tmp/trailscout-gate-kevr21x9`. Retained copies: `.trailscout/evidence/release-gate` and `final-gate`. The explicit travel-area regression now proves mapped travel is bounded independently of target masks; shared candidate legs and entry-region buffers are reused after profiler evidence of redundant work.

Exact commands: `./trailscout check`; `PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/tanner/Desktop/huntmaps2/.venv/bin/python -m trail_scout.checks.performance`; `PYTHONDONTWRITEBYTECODE=1 python3 /tmp/trailscout-preservation-audit.py /tmp/trailscout-worktree /tmp/trailscout-worktree/.trailscout/evidence/baseline/verification-final.json`. Results: Soap Creek cold/warm 6.744/6.287 s; schedule/pace edits 6.271/6.260 s; Flattop Bench cold/warm 11.751/11.453 s; 509.2 MiB peak process RSS. Limits were unchanged. Fresh derived caches, warm OS pages, source validation measured separately (1.657 s). Raw phase timings, grids and candidates retained in `.trailscout/evidence/performance`.

Four explicitly labeled real DEMO outings and sixteen exports saved in the default isolated state. Documentation includes methods, architecture, initial comparison and readable field summaries. Actual desktop and 900px renders reviewed. Final original audit matched all 35,977 protected records and 6,227 frozen file hashes; original HEAD/index/status/diff and copied inherited untracked sources unchanged. Inherited tracked patch in this worktree is byte-identical to baseline when excluding the task-owned `.gitignore` addition. No owner environment/state/control changes. Next action is the concrete relocation/smoke/local-commit finalizer; its receipt will be retained under `.trailscout/evidence/relocation`.

## Handoff complete
Moved the tested worktree to `/home/tanner/Desktop/huntmaps2-trailscout` without overwriting another path. The actual launcher served the four saved real examples there; all sixteen exports and the desktop/900px browser reopen journey passed, including restored preview naming. Stopped only that smoke server. Repeated the original-checkout/protected/frozen audit after relocation: unchanged. Receipt and screenshots: `.trailscout/evidence/relocation/`. Task-owned changes committed locally; inherited work remains unstaged. No implementation work remains. Next user action: `cd /home/tanner/Desktop/huntmaps2-trailscout && ./trailscout`.
