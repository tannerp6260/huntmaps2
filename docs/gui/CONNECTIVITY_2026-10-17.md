# Terrain connection screening — 2026-10-17

Find now defaults to setups with a modeled terrain connection. **Show all setups**
restores the original pool, including unchecked and disconnected candidates.
Shortlisted setups and manual positions remain available in either mode. This is
an eligibility screen for desktop review, not verified physical or legal access.

## Behavior

- Screening precedes individual recommendation selection and complementary greedy
  selection. Existing visibility scores, ordering criteria, separation rules and
  greedy coverage coefficients remain unchanged.
- New, unreviewed setups use the run's approach preferences, initially 25 degrees.
  Saved spot drafts retain their own limit, boundary, exclusions and network/start
  settings. Applying a new connection limit updates only the run default; it does
  not replace saved drafts. Limits above 35 degrees are rejected.
- Each unreviewed setup is tested against the same suggested 2,000 m boundary,
  clipped to supported obstruction terrain, as approach preflight. This remains
  an unconfirmed proposal. The normal approach workflow still requires confirmation.
- Progress streams from a bounded, cancellable subprocess. Partial results remain
  labeled when cancelled or failed; retry is explicit. Duplicate submissions are
  blocked and pending feedback appears immediately.
- Missing, incomplete or corrupt verified network coverage cannot establish a
  negative result. Such cases remain unavailable, with a bounded source review
  and one explicit preparation approval. A verified partial network can establish
  a positive connection. General browsing overlays never supply analysis lines.
- Failed approaches show a concise diagnostic identifying the endpoint, exclusion,
  departure, mapped-start or terrain-connectivity issue. Connectivity checks at
  30 and then 35 degrees offer **Recalculate at N°** only when a higher limit
  reconnects the same inputs. Settings change only after that explicit click.
  Historical comparisons remain readable and unchanged.

## Implementation and compatibility

`huntmaps_gui/connectivity.py` shares terrain validation and verified network
parsing/projection across the batch. Each exact local boundary has its own terrain
grid and unweighted connected-component query. Different boundaries can have
different grid origins, so a single global raster approximation is not substituted.
The screen uses the solver's cell slope, edge slope, diagonal, exclusion, exact
endpoint/departure connector, departure-distance and mapped-start rules. It does
not calculate weighted terrain paths or route alternatives for every candidate.

`ConnectionGrid` vectorizes cell and edge preparation while preserving geometry
checks for nonconvex boundaries. Source identity and integrity checks remain in
place. Display-cache signatures include implementation, DEM, source metadata/file
identities, exact point revisions and per-spot settings. Completed cache entries
are sealed and participate in the existing display-cache budget. Active status
reads fetch their recorded job directly rather than repeatedly scanning history.

Interfaces added:

- `GET/POST /api/runs/{run}/connectivity-screen`
- `POST /api/approaches/{scenario}/connection-diagnostics`
- Optional `connection_screen` on complementary requests, validated again before
  saving suggestions. Legacy requests and historical results remain supported.

## Verification

The relevant backend suites passed: **251 tests**, including 14 new connection
tests. A final standalone run of those 14 tests passed after the last backend
change. Tests compare exact validity/edge masks and feasibility with the existing
full solver on flat, sloped, blocked, missing-terrain, concave, excluded and seeded
random grids. They also cover explicit network starts, proposed-boundary/grid
parity, saved settings, manual-coordinate invalidation, source corruption, missing
coverage, cache integrity/reuse, cancelled partial work and direct active-job reads.
A patched weighted search raises if called during screening.

Frontend formatting, Python formatting and the production TypeScript/Vite build
passed. Disposable browser journeys cover connection screening, the guided
Find → Approach → Inspect → Save workflow, and complementary review at desktop
and 900 px. The connection journey includes slow submissions, cancellation/retry,
late replies after changing runs, blank editing through polling, the 35-degree
ceiling, provider failure after explicit approval, saved/manual retention and a
real synthetic 28-degree-plane calculation that fails at 25 and succeeds after
an explicit 30-degree retry. Submission feedback is asserted within 200 ms.
The original 25-degree scenario is checked unchanged after the retry.

The combined journey exposed an existing test-order assumption: complementary
shortlisting expected every setup to be unconfirmed after an earlier journey had
confirmed setups. Its assertion now checks that prior confirmations are preserved
and no additional setup is confirmed merely by shortlisting.

Backend diagnostics: `/tmp/huntmaps-check-j3dznq1t`. Final successful combined
browser/build/format run: `/tmp/huntmaps-check-ib8z4fld`, including screenshots
under `screenshots/` and individual journey logs. These are disposable local
verification artifacts and are not committed evidence or saved owner runs.

## Representative 711-location timing

Reproduction helper: `gui/connectivity_performance.py`. Final isolated output:
`/tmp/huntmaps-connectivity-711-verified/timings.json`.

| Measurement | Result |
| --- | ---: |
| Candidate locations | 711 |
| Accumulated network inventory records | 63 |
| Accumulated approach-history records | 81 |
| Fresh background screen | 30.27 s |
| Completed cache read | 0.203 s |
| Found / disconnected / unavailable | 34 / 677 / 0 |
| 24-point connectivity sample | 0.934 s |
| Same sample, full route alternatives | 2.241 s |
| Weighted terrain searches during screening | 0 |

The sample includes 12 positive and 12 negative results and agrees with the full
solver. The connectivity sample was about 2.4 times faster; the fresh batch still
takes tens of seconds and is presented as background work. These are local timings,
not universal performance guarantees. The benchmark uses actual cached terrain
with a synthetic mapped line and completeness fixtures to exercise both outcomes;
its found count is not evidence about real access.

A separate read-only diagnostic of the owner's original R0031 failure found a
connection at 30 degrees under the recorded boundary and exclusions (1.86 s).
Its original 25-degree scenario and results were not changed.

## Preservation

All 8,502 protected analysis/input/report files retained their initial size and
modification time. The frozen byte-level preservation audit also passed. No
coordinates, saved scenes, workflow decisions or historical approach outputs were
changed by implementation or verification; browser and performance jobs used
disposable workspaces/state.

Of 708 pre-existing owner records, 707 retained their hashes. The sole changed
record was job `252e93bbf4bf4fe48dd4e2bba948f8e2`, a lidar preparation already running
before the task snapshot: it started at 13:27:15 UTC, the snapshot was taken at
13:29:07 UTC, and the provider request timed out at 13:30:26 UTC. Its natural
terminal status and retained partial downloads were left intact. This task did
not restart, cancel or rewrite that job. Subsequent isolated verification audits
reported no owner-record changes.
