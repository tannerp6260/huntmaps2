# TrailScout first release

TrailScout is a working separate local browser application with real GMU 54
route comparisons, new mapped/off-trail viewpoints, return-aware effort, habitat-
adjusted visibility, competing-access evidence, AM/PM/combined schedules, owner
edits, immutable saved versions and four export formats. No API key or online
basemap is required. Results remain provisional desktop scenarios.

## Launch, stop, resume, abandon

```bash
cd /home/tanner/Desktop/huntmaps2-trailscout
./trailscout
```

Open **http://127.0.0.1:8767**. Four explicitly labeled **DEMO** saved outings are
available: Soap Creek AM/PM and Flattop Bench AM/PM, dated October 31, 2026 with the
editable conservative Together profile. Open a saved card to inspect or adjust it.
Use **Compare** to compare the saved corridors.

**Stop:** Ctrl+C in that TrailScout terminal. This cancels its own worker and
releases its state lease. **Resume:** run the same command; saved versions remain,
and interrupted jobs have a retry action using compatible completed caches.
Only one writer may use a state directory. If port 8767 is already occupied, choose
`./trailscout serve --port 8768`; do not stop an unrelated server.

**Abandon without deletion:** stop TrailScout and continue using
`/home/tanner/Desktop/huntmaps2` normally. The original checkout is still on `main`;
no checkout/reset/stash/restore is necessary. Leave the new branch, worktree and
state in place for later review. No cleanup/deletion is part of this handoff.

## Checkout and isolation record

| Item | Value |
|---|---|
| Original checkout | `/home/tanner/Desktop/huntmaps2` |
| Original branch and actual base HEAD | `main`, `c594668152783eb8895c8c76284b10bb5fbfba62` |
| New branch | `feature/trail-glassing-planner` |
| Development worktree | `/tmp/trailscout-worktree` |
| Retained worktree | `/home/tanner/Desktop/huntmaps2-trailscout` |
| Default runtime state | Retained worktree's `.trailscout/` |
| Read-only source/interpreter | Original checkout and its `.venv/bin/python` |
| Separate frontend | `trail_scout/web`; existing installed dependencies reused read-only |
| Default server | Loopback `127.0.0.1:8767` |

The actual local HEAD happened to equal the externally reviewed reference. The
owner's newer **20 tracked dirty files and nine untracked sources** were transferred
to the new worktree without changing or committing the original checkout. They
remain distinguishable and unstaged. Task-owned changes are only `.gitignore`,
`trailscout`, `trail_scout/`, and `docs/trail-planner/`. No legacy analytical code,
coefficient, environment, lockfile, user record, dataset or report was edited.

Recovery evidence is retained under `.trailscout/evidence/baseline`: original
identity/status/index, recoverable binary diff, untracked-source inventory and
source copies, protected-file manifest and final verification JSON. The audit
checks original HEAD/branch/index/status/binary diff, all **35,977** protected
size/mtime records plus captured small-file hashes, all **6,227** frozen-control
SHA-256 records, and the inherited untracked-source bytes. All passed with no
changes or missing files. This is evidence beyond branch isolation; no owner
activity was restored or overwritten. Own test/development servers were stopped;
the owner's services were not killed. No Windows/Data partition was inspected.

Local commits contain task-owned files only. Run `git log -1 --oneline` in the
retained worktree for the handoff commit. Inherited work intentionally remains dirty.
No push, merge, publish, deployment, global configuration change or package upgrade
was performed.

## Real-area evidence and initial comparison

See [the short scouting comparison](INITIAL_SCOUTING.md) and the readable
[Soap Creek AM](examples/soap-creek-am.md),
[Flattop Bench AM](examples/flattop-bench-am.md), and
[Flattop Bench PM](examples/flattop-bench-pm.md) field summaries.
All four complete JSON/GPX/GeoJSON/Markdown export sets are in
`.trailscout/exports/`; `.trailscout/handoff.json` identifies their immutable saves.

The source adapter validates the existing immutable
`data/unit-packs/versions/co-gmu54/20261019-v2`: real buffered 10 m USGS terrain in
metres/NAVD88, 2023 RCMAP cover, CPW unit target geometry and attributed USFS
inventories. Optional dated raw source snapshots add ownership, MVUM, motor-closed
and entry evidence. Historical experiment archives, saved human points and old
GUI state are not dependencies.

The prepared GMU target covers about 1,514 km², with WGS84 bounds
`[-107.4242561, 38.4488649, -106.8454802, 38.8706451]`. It is **not** one whole-unit
fine-grid search. Demonstrations use separate 2.5 km corridor radii, a 300 m spur
envelope, 1.5 km viewing radius and 32-candidate ceiling. Each obstruction window
is 881 × 881 cells at 10 m; exact UTM grids are in each analysis/export. Habitat
context has 40 m support from approximately 30 m annual cover. Intrinsic unknowns
remain unknown. Other entries or owner-selected corridors can use the same bounded
workflow if the full obstruction/context window is supported.

Soap Creek evaluated 21 exact positions, supported six, and checked 30 complete
route variants. Flattop Bench evaluated 32 positions, supported 14, and checked 52
variants. Six distinct previews per corridor survived screening. Both discovered
new feasible off-trail positions without using old candidate pools. The recommended
AM Soap Creek outing is 0.78 mi / 116 ft gain; Flattop Bench AM is 1.32 mi / 163 ft.
These are supported options among evaluated choices, not global optima or field
validated routes.

Mill Castle and Beaver Ponds also produced genuine **no feasible evaluated plan**
results under conservative settings. The closer Mill Castle candidates failed
observer cover/support screens; supported openings exceeded the usable travel
budget. No thresholds were loosened to manufacture a successful comparison.
Survey evidence is in `.trailscout/evidence/corridor-survey`; earlier failed-browser
diagnostics and that negative case remain in the original `/tmp` evidence paths
recorded in the progress log.

Real motor-closed geometry was exercised through the source/graph tests. It had
unknown foot status: excluded by default, included only as an explicit unknown-
access scenario. A labeled restriction fixture verifies that a foot closure still
excludes it. No verified-foot-use closed road is falsely claimed for the sample
outings. A live official 5 km Soap Creek preparation fetched and validated three
MVUM roads, zero MVUM trails and zero motor-closed inventory records, consuming
101,828 received bytes in about 3 seconds. Verified empty inventory does not certify
absence of current closures. Its original metadata/counts/features/provenance and
ledger are retained in `.trailscout/evidence/official-access-preparation`.

## Verification

The final complete gate passed at `/tmp/trailscout-gate-m9c2z55r` (durable copy:
`.trailscout/evidence/release-gate`); the preceding numerical-code release gate also
passed at `/tmp/trailscout-gate-kevr21x9` (`.trailscout/evidence/final-gate`). Exact
commands, logs, screenshots, actual backend states and downloads are retained.
The complete gate is reproducible from the retained worktree:

```bash
./trailscout check
```

| Check | Result |
|---|---|
| Python Black; frontend Prettier | Passed |
| TypeScript type check and separate Vite production build | Passed |
| New numerical, real-data/API and preparation tests | 28 passed |
| Relevant unchanged habitat/unit-pack compatibility tests | 31 passed |
| Actual-service browser, real GMU sources | Passed |
| Desktop and approximately 900 px rendered UI review | Passed |
| Original checkout/protected/frozen preservation audit | Passed |

The browser exercises profile/start edits, both real corridors, linked elevation
profiles, coverage/access/marginal evidence, AM/PM selection, combined-day rejection,
save/reload/four downloaded exports, version conflicts, real pin/reject recalculation,
cancellation/retry, a delayed actual job reply, offline requests and unavailable-
basemap recovery. It uses real backend results. API response mocks do not substitute
for the analytical journey. A final review corrected restored-preview naming so a
Flattop Bench preview does not inherit a Soap Creek name.

Independent tests include contour walking grade versus off-trail hillside slope;
repeated hills/noise/short climbs; excessive uphill return; farther open versus
nearer brushy spurs; exact retraced geometry and scalar weighted coverage unions;
date/mode/foot closures; crossings/gaps/overpasses; other-access graph evidence;
combined effort and conservative time windows; NOAA reference/DST including travel
across fall-back; edits/pins/infeasibility; exact coordinates/export tracks; corrupt
sources and warm caches; interrupted/duplicate writers; and provider failure/retry
with retained originals. Explicit travel polygons constrain mapped and off-trail
travel independently of target boundaries.

No failed legacy check is hidden. Existing Matplotlib/AnyIO warnings and the Vite
MapLibre bundle-size warning are retained in logs; these were not failing checks.
Earlier genuine development failures and their fixes are recorded in
[IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md).

## Measured performance and bounds

Machine: AMD Ryzen 7 5700G, 16 logical CPUs, 14 GiB reported RAM, Ubuntu filesystem
with approximately 89 GiB free at baseline. One analytical worker, BLAS/OpenMP
limited to one thread. Existing Python 3.10.12/GDAL 3.4.1/NumPy 1.26.4 stack reused.
The predeclared 20 GiB reserve, 250 MiB acquisition cap, 2 GiB state budget,
2 million terrain-cell maximum and 80-candidate maximum were retained.

Measured command:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
/home/tanner/Desktop/huntmaps2/.venv/bin/python -m trail_scout.checks.performance
```

| Calculation | Seconds |
|---|---:|
| Source pack validation, separately measured | 1.66 |
| Soap Creek fresh derived cache | 6.74 |
| Soap Creek warm | 6.29 |
| Soap Creek observation-window edit | 6.27 |
| Soap Creek pace edit | 6.26 |
| Flattop Bench fresh derived cache | 11.75 |
| Flattop Bench warm | 11.45 |

Peak planner process RSS was 509.2 MiB. Each corridor used 776,161 terrain cells;
candidate/support/variant counts are above. Warm runs reused all six/fourteen
compatible visibility masks. These wall times include bounded terrain/network/spur
analysis, coverage, scheduling, local rendering and JSON publication; exclude
downloading, browser rendering and separately measured source initialization.
“Cold” means fresh derived caches; OS page cache was not flushed. RSS is the
cumulative process peak, not simultaneous whole-system memory.

Profiling exposed repeated complex-boundary buffering and repeated measurement of
identical candidate legs; both were removed without changing analysis limits.
Schedule/profile edits currently still rebuild bounded route/candidate assembly,
so warm wall times remain similar even though expensive masks are retained.
There is no claim of whole-unit performance. In the final release browser
run, 505 live job/status probes stayed at or below 508.1 ms, with no browser errors
or external resource requests. Raw measurements and stage boundaries are retained
under `.trailscout/evidence/performance`.

## Material limits and next use

- Start/parking and complete vehicle approach remain assumptions requiring review.
  Current foot/area/emergency closures, intact tread, brush, snow, safe crossings,
  legal hunting permission and shooting hours are not certified by these sources.
- Annual coarse cover cannot certify foreground clearance. Soap Creek has about
  59 acres of visible matching terrain with unsupported vegetation/context.
- Competing access is inventory-limited. Flattop Bench has strong nearby motor and
  other-entry evidence; no missing network produces a remoteness bonus.
- Search supports out-and-backs and bounded two-position connected variants,
  with at most two pins. No arbitrary loop solver, vehicle relocation optimizer,
  first-person foliage rendering, terrain-shadow or animal-activity model is claimed.
- The app is tested against the existing local environment/data. Fresh-machine
  dependency installation and additional GMUs are not claimed as verified.
- No field collection or later biological optimization was started. The next user
  action is to open the saved examples, review access assumptions and select/edit
  a bounded outing. The implementation task itself is complete.

Workflow, preparation/import and environment instructions are in [README.md](README.md);
analytical assumptions in [METHODS.md](METHODS.md); reuse/isolation details in
[ARCHITECTURE.md](ARCHITECTURE.md). Durable evidence lives in the retained worktree's
ignored `.trailscout/evidence/`; generated data and environments are not committed.
