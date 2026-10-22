# Practical glassing review, version 1

From `/home/tanner/Desktop/huntmaps2` on `feature/practical-glassing-opportunity`:

```sh
./trailscout
```

Open http://127.0.0.1:8767. If that port belongs to another application, use
`./trailscout serve --port 8768`. Stop this application with Ctrl+C in its terminal.
The existing `./huntmaps-gui` application and its saved owner records remain available.

1. Check **Colorado GMU 54**, the installed source version and the outing date.
2. Choose the party. **Together** starts at 2.5 total walking miles and 750 ft
   cumulative gain, with 25% held in reserve. These editable assumptions are below
   the reported difficult morning; they are not measured physiological limits.
   **Extended family** is an explicit 3 mile/900 ft alternative. Solo is never
   selected automatically. Existing saved profiles keep their stored numbers.
3. Select a mapped entry or an explicit reviewed start. Parking and the complete
   vehicle approach remain conditional. For a Teryx, supply its actual width;
   an ATV designation does not establish side-by-side eligibility.
4. Set off-trail limits and useful observation windows. The app measures outbound,
   transitions and return separately. Read both distance and cumulative gain, the
   conservative time range, breaks and daylight reserve.
5. Optionally open **Community & scan review · experimental** and enable the
   practical static comparison. Choose spot/identify/assess, an assumed leaf state,
   and useful scan minutes. Unknown leaf state is the conservative default.
6. Compare route opportunities. Read the existing route previews and their full
   return totals. The additional community shortlist is a **separate static
   collection**; it has no combined daily route or time feasibility.
7. Open the five-model review. Switch community/habitat/unknown/unique coverage
   maps; inspect a point for coordinates, habitat classes, distance bands, scan
   sectors and available individual approach evidence. Orange is habitat unknown.
   Foreground and intervening vegetation remain uninspected throughout.
8. Save a feasible route preview through the existing Save action. Its JSON export
   also includes the static review. The review supplies CSV, analytical GeoTIFF,
   full JSON and a separate provisional **waypoint-only** GPX. Restarting retains
   these records. Never interpret the static GPX as a connected route.

All analytical core work uses local sources. Online map display is optional;
none is needed for the local relief, analysis or review. New weighting is opt-in.
Relative-index m² are not literal acres searched, deer probabilities or a measure
of antler size. Mapped use designations, source inventory, ownership, foot permission,
driveability and parking are different evidence.

## Installed community data and recovery

```sh
.venv/bin/python -m practical_glassing status
```

The separate package lives under `.trailscout/community`. It depends on the existing
immutable `co-gmu54 / 20261019-v2` core pack. Its source objects, official LF2025
legends, categorical COGs, indexed GeoPackage and sealed manifest are retained.
Older terrain/RCMAP sources and historical products are not rewritten.

If the companion is absent, ordinary scouting still works; its experimental control
is disabled with an explanation. Explicit preparation is:

```sh
.venv/bin/python -m practical_glassing prepare
```

This bounded CLI reports progress; Ctrl+C retains completed source objects and the
transfer ledger. Repeating the command reuses exact requests and completed bytes.
Provider errors or unsupported values fail visibly. It does not substitute RGB
imagery for classes or require cloud credentials. A corrupt published package must
be restored to its exact sealed bytes or replaced with a separate version; do not
reseal edited scientific rasters or delete interrupted evidence.

Saved-pool review is separate from the ordinary corridor workflow:

```sh
.venv/bin/python -m practical_glassing compare --run 2
```

It prints a new review path under `.trailscout/reviews`. Open its `review.html` in a
browser. This examines the exact original saved pool; live manual/working edits are
left untouched. It has no entry/route feasibility claim. The two previously reported
549/500-point pools are missing locally; this is not their replication.

## Material limits

- A local 10 m terrain model cannot establish foreground clearance. The existing
  GUI first-person, foliage and bounded LiDAR tools remain useful finalist inspection
  tools; this new review does not convert them into a whole-unit transmission model.
- Existing dense-cover/standing and approach screens act before this review. They
  can exclude small openings. New trail sampling and an opening-aware replacement
  screen are deferred; exact manual points and prior exclusions are preserved.
- Current emergency/area/foot closures, road conditions, rights across other
  ownerships, target-side hunt permission, stalk and retrieval remain review tasks.
  Use the current [GMUG orders](https://www.fs.usda.gov/r02/gmug/alerts) and official
  maps. A motor closure alone does not establish foot permission.
- Astronomical light windows use the existing NOAA calculation and America/Denver.
  Terrain shadows and legal hunting hours are separate. Practical scoring uses
  neutral light; actual glare/perspective/foreground/posture scenarios are deferred.
- Existing routing checks real traversed geometry and independent budgets, but is
  bounded by its network and predecessor paths. A failed evaluated route does not
  prove that all possible approaches are infeasible.

To stop using this feature, leave the experimental checkbox off or stop TrailScout
and continue with `./huntmaps-gui`. No data deletion, profile migration or historical
regeneration is necessary. See the implementation report for scoped code reversion.
