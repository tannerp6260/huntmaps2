# Practical AM/PM plans · experimental version 1

The completed hunter workspace is described in [Hunter workspace usage](HUNTER_WORKFLOW_UX_USAGE.md). Analytical controls below are unchanged.

Launch from this checkout:

```sh
./trailscout
```

Open http://127.0.0.1:8767 (or `./trailscout serve --port 8768`). Existing sources
are read-only; derived work and immutable saves use TrailScout state. No provider
connection or new download is required for installed GMU 54 operation.

1. Choose GMU 54, outing date, party and mapped entry/assumed parking. Read its
   conditional vehicle/parking evidence. Teryx width must be supplied when relevant.
2. Keep **Together** unless deliberately choosing another profile: nominal 2.5 mi /
   750 ft before 25% reserve; usable **1.875 mi / 562.5 ft**. Travel includes every
   outbound, transition and return traversal. Limits are editable planning assumptions.
3. Open **Timed practical plans · experimental**. Check **Use practical objective
   for AM/PM plans**. Choose search task and assumed leaf state. Blank **Timed scan
   cap** uses each stop's actual scheduled observation time; a number caps useful
   scan minutes separately at each stop. The old static review has its own 30-minute
   policy and separate checkbox; it is not a daily itinerary.
4. Compare route opportunities. The recommendation uses separate AM and PM rankings.
   Choose **Morning/Evening** under Schedule or **Time variant** near Save. Each
   switches to that variant's recommendation. Select another route preview to inspect
   an alternative under **All retained route previews**. Short alternatives and
   inspection/save focus actions are above the map. Combined/stay days are available only with practical planning off.
5. Read the practical summary and expand **Selected scan sectors**: coordinates and stop order, habitat added, supported
   and unknown area, incremental/exclusive opportunity, useful scan minutes and
   unallocated/rest time. Read full walking distance, ascent, return trigger and
   held/remaining reserve in Route/Schedule. Useful units are relative-index m²,
   never literal acres searched or deer probabilities.
6. Amber outlines are selected full scan footprints. Green shows actual selected
   terrain-visible positive opportunity support; orange is selected habitat unknown;
   grey is supported known-zero. Toggle **Show theoretical terrain instead of selected
   search support** for the original terrain view. Terrain hidden inside a footprint
   remains hidden. Bearings are projected UTM grid bearings, not certified compass
   directions. Check a field map.
7. Expand **Foreground inspection** for a finalist. The magenta neighborhood and
   three coarse transects per selected direction describe dated RCMAP cover risk.
   Coarse low cover cannot certify an opening; high cover cannot prove blockage.
   No compatible measured local obstruction/perspective input is registered for the
   demonstrated finalists. Inspection never changes numerical scores. Confirm the
   exact opening, trunks, understory and selected directions in the field. A manually
   relocated/pinned point receives its own route and viewshed; it does not inherit
   the old sightline. This increment does not collect field observations.
8. Save the chosen feasible AM/PM preview. JSON retains settings, identities, timed
   scans and diagnostics. Markdown is a field summary. GeoJSON includes complete
   directed legs, waypoints and selected sectors. GPX tracks follow the actual
   connected provisional route, including return; the static five-point review's
   GPX remains a distinct waypoint-only export. Old saves retain their original
   scores and remain readable/exportable; edited inputs require recalculation.

The easier-plan preference is explicit: within 90% of best utility for that time
variant, consider plans within three minutes of the least conservative movement
and prefer fewer stops, then utility/ascent. It does not alter habitat coefficients.
Selection is best among evaluated positions/routes, with no global or biological
optimality claim. Coarse dense-cover screens and unchanged candidate sampling can
miss useful small openings. Unknown access is never evidence of low pressure.

Missing packages, corrupt sources, disconnected/unsupported routes, pin conflicts
and insufficient data are shown as errors/empty results. No different start, party,
objective or road scenario is substituted. Current foot/area closures, complete drive
access, safe parking, target-side permission, stalk and retrieval remain conditional.
Astronomical light is not legal hunting time. No automatic foreground visibility
correction or whole-unit LiDAR acquisition is included.

Turn the practical-plan checkbox off to return to established planning. No data
migration/deletion is needed. The five-arm static review remains available separately.

Reproduce the engineering comparison in disposable state:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m trail_scout.checks.practical_plans
./trailscout check
./gui/check --keep-going
```
