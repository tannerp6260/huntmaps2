# TrailScout methods and limits

This first release is an interpretable bounded desktop planner, not a deer model,
permission certification, navigation guarantee or proven global optimizer.

## Profiles, movement and clock time

Tanner's background report was roughly 5–8 miles/day and 2,000–3,500 feet of gain
under suitable conditions. His initial limits are 6 miles / 2,200 ft, 2 mph flat
pace, 10 elapsed hours. Dad's difficult Dutton morning involved roughly 3–4 miles /
1,000 ft cumulative gain around 10,000 ft with a guide who walked too fast. That
is not a measured capacity. Dad and Together start at 3 miles / 700 ft, 1.5 mph,
7 elapsed hours, 0.25 off-trail miles / 35 off-trail minutes and gradual grades.
Together uses the limiting participant, never an average. Every limit is editable.

A 25% reserve is subtracted from mileage, cumulative ascent, movement hours and
off-trail distance/time limits. Resting/glassing consumes elapsed clock time and
never resets accumulated effort. A selected condition multiplier can represent a
slower scenario; no current snow, trail condition or forecast is fabricated.

For grade fraction g and entered flat pace P (converted to m/h), speed is
`P × exp(-3.5 × max(0, abs(g+0.05)-0.05)) / condition / brush`.
The directional exponential response is Tobler-shaped but conservatively capped at
flat pace; it is an uncalibrated engineering assumption. Brush is 1 on mapped tread,
`1.5 + 1.5×tree + shrub` off trail, using known fractional cover. Unknown cover does
not become open terrain. Low travel hours sum distance/speed; the conservative
estimate is low hours × the editable 1.35 default margin. There is **no second
climbing-time penalty**. Ascent remains an independent hard guardrail.

To calibrate after an actual outing, use moving time only: an initial adjustment is
`new flat pace = old flat pace × predicted movement hours / observed movement hours`.
Edit flat pace and the condition margin conservatively. This simple comparison
changes no historical coefficients and is not a physiological estimate. Sitting,
breaks and observation time must not be included as observed movement time.

## Along-route profiles and return

Metric computation is EPSG:32613. DEM elevations are metres with recorded NAVD88
source reference; no vertical correction or combination of different datums is
performed. The prepared DEM is 10 m bare earth with mixed source vintages disclosed.

Mapped routes use elevations along their **actual line geometry**. Profiles sample
at 20 m plus exact travel-mode boundaries, with bilinear elevations. Raw samples
remain in JSON alongside a three-sample median profile and a 1.5 m vertical-error
simplification. The latter suppresses small noise reversals while preserving climb
onset/ending within its stated tolerance. Sub-20 m samples at mode boundaries are
not independent fine terrain evidence. There is no nearest-cell staircase ascent.
A 60 m rolling support is used for maximum sustained grade; steep sequences of at
least 60 m and the grade-distance bands are also retained. Shorter details are not
certified by this DEM/profile support.

Surrounding hillside slope is recorded separately from walking grade. A contour
trail across a steep hillside remains eligible under walking-grade limits; its
mapped existence does not establish intact/safe tread. Off-trail edges must meet
both ground-slope and directional-grade limits, tree/shrub limits, known support,
scenario travel domain and exact exclusion geometry. Default off-trail ground limit
is 20° for Dad/Together and 25° for Tanner. Initial route sustained-grade limits are
30% / 40%, respectively; percent is not degrees.

Distance follows the complete traveled chain, including shared approaches, spur
retracing, transitions and return. Line union is never used to count walking.
Ascent/descent sum every actual traversed profile interval. Outbound and reverse
travel have independent directional time estimates and gain/descent. Each candidate
and returned route is checked against the full return-aware limits and reserve.
The UI shows return distance/ascent/descent/time and remaining usable versus held
reserve. No terrain-only connection is relabeled as a complete feasible outing.

## Topology, spurs and candidate search

Original attributed USFS geometries and stable feature identities are retained.
The separate motor-closed inventory is reconciled by feature identity; MVUM matching
requires route identity and at least 95% geometric overlap within 5 m. Shared/duplicate
motor inventories do not create duplicated walking edges.

The walking graph uses exact endpoint contacts and endpoint-to-interior contacts.
Arbitrary crossings, nearby parallel lines and metre-scale gaps are not junctions.
Explicit layer/bridge/tunnel evidence keeps different levels disconnected. A 0.01 mm
numerical coordinate tolerance handles projection/substring roundoff; it is not a
physical gap-repair allowance. Original feature endpoints are preserved exactly.
Conservative topology can miss a real junction: disconnected means unavailable in
this graph, not proof the field connection is impossible.

A selected start names its intended segment. Map selection projects the clicked
position onto that line and reports the click offset. A JSON start must already be
within 0.5 m of that segment; no arbitrary nearest-line connection is invented.
Candidate entries near a supported motor line remain **assumed entries/parking**,
with unresolved gaps labeled; no complete vehicle-navigation route is inferred.

New positions are proposed on return-screened mapped departures and in a surrounding
20 m spur graph. Shared graph/profile work is reused across candidates. Multi-source
spur costs include the mapped round trip and directional off-trail round trip.
Eight-neighbor edges prohibit corner cutting; final exact geometry is screened at
5 m intervals against source-supported slope/cover and exclusions. A 160 m coarse
allocation finds open local topographic alternatives, with 200 m spread; candidates
then receive new exact-coordinate terrain visibility. No saved historical point
pool is required or used as a search seed. This is bounded, approximate search.

The default spur envelope is 300 m. It can be explicitly changed to 1–1.5 km where
source/grid bounds support it. It is a computational envelope, not Dad's acceptable
bushwhack distance: each actual spur still must pass much tighter off-trail effort,
cover, grade and full-return constraints. Candidate counts can be below the budget
when supported positions are exhausted. Pins consume the same bounded budget.

Standing ground is screened independently (25°), with own-cell and 30 m near-
foreground tree/shrub support. At least 80% of near samples must be known; 35% tree /
50% shrub thresholds screen dense mapped cover. These are conservative uncalibrated
eligibility screens, never new biological coefficients or optical clearance. Coarse
annual cover cannot find/certify a tiny clearing, understory or leaf-off sightline.

## Terrain and quality-adjusted coverage

GDAL Edge viewsheds use the existing verified engine settings: 1.7 m eye, 0.8 m target,
curvature coefficient 6/7, explicit circular radius and a full obstruction halo.
No GMU/travel/target mask removes obstruction elevations. Each exact observer gets
its own content-keyed mask; mask shape, origin, cell size and alignment are checked.
New visibility is computed for a moved observer instead of inheriting old scores.

The existing pure `huntmaps_gui.habitat` structural model is reused without changing
its coefficients or ecological interpretation. Raw 2023 RCMAP tree/shrub percent
sources must align and have compatible product/year/unit metadata. Known support
is conservatively averaged to a globally aligned **40 m** context grid, then the
established H/G responses are transferred nearest to the exact 10 m visibility grid.
Full 90/270 m neighborhoods are considered before target/visibility clipping;
80% intended-neighborhood support is required. Missing/outside cover stays unknown.

For cell area a, visible mask V, eligible target F, known habitat K, existing habitat
preference H and glassability G: `E = Σ a × V × F × K × H × G`. E is quality-adjusted
area, not literal acreage searched, deer density, occupancy, encounter/detection
probability or assured optical visibility. Dense cover can retain H while reducing G.
No new species, snow-migration, road-remoteness or detection coefficient is added.
Physical visible/matching, scorable, priority and unsupported areas remain separate.
All areas are projected planimetric m², with 4046.8564224 m² per acre.

Collections union exact aligned analytical cells once. Inclusion-step marginal E is
separate from a member's final exclusive E. AM/PM repeat observation can be useful
but does not create additional unique acreage. No optical distance-response curve
or shooting-distance model is invented for the 16×50 binoculars / 77 mm scope.

## Route tradeoffs and competing access

Single-position out-and-backs are valid. Connected two-position variants retrace
actual shared prefixes and branches; there are no teleports. First-release search
checks pairs among up to eight leading feasible points plus pins, rather than
promising arbitrary loops or an unlimited itinerary optimizer. At most two pins
are supported; this is an explicit search limit, not a requirement for two stops.

Every complete variant sums its measured actual legs and is checked. Identical candidate outbound/return profiles are reused; new transitions are measured along their own traveled geometry. Comparable Pareto screening uses
supported E, conservative movement time, ascent, off-trail distance and visible
country's fraction within 500 m of mapped supported motor access. Access evidence is
kept separate from H/G. Clearly dominated results are removed; highly overlapping
similar-effort alternatives are reduced. The marginal table retains all evaluated
variants with return included so diminishing gains remain inspectable.

For each time variant, find the best supported feasible E; among choices reaching
90% of it, retain those within three movement minutes of the easiest choice and
prefer fewer stops, then coverage and ascent. This explicit heuristic avoids tiny
coverage differences automatically spending substantial effort/observation time.
It is the best supported tradeoff **among evaluated choices**, not a global optimum.

Access evidence includes distance to date/mode-supported motor geometry, other
plausible entries (explicit straight-line lower bounds), shared mapped components
where supported, and visible target country near motor routes. Only <=500 m earns
the descriptive **near mapped motor access** label. Other cases remain completeness-
limited; no missing network earns a remoteness bonus. No hunter counts, solitude
percentages or precise encounter probabilities are predicted. Foot-compatible
motor-closed roads can be walking candidates; emergency/area/foot closure excludes
foot use. Unverified/decommissioned condition remains an explicit uncertainty.

Motor, pedestrian and physical-condition classifications are separate and date
aware. A mapped road is not motor permission. Absence from MVUM is not pedestrian
permission. Missing closure records are not certification. Manual statuses require
provenance and dates; geometry exclusions affect the graph and spurs. Unknown foot
use requires an explicit scenario toggle. An explicitly entered travel polygon bounds both mapped and off-trail travel. The default ownership support limits off-trail scenarios; the target polygon is independent and never automatically clips a supported walking trail. Ownership/GMU polygons never establish
hunting permission. These are desktop access proxies, not legal advice or safe routes.

## Observation schedules

Local sunrise/sunset/civil twilight use the published
[NOAA approximation](https://gml.noaa.gov/grad/solcalc/solareqns.PDF), with
`zoneinfo` America/Denver and date-specific DST offsets. UTC elapsed-time arithmetic
preserves travel durations when crossing a clock transition. An ambiguous entered
local departure uses its first occurrence (fold=0). Mountain horizons, weather,
thermals and animal activity are not modeled.

Default AM window is sunrise to +180 minutes; PM is sunset−180 minutes to sunset.
These are editable logistics windows, separate from legal shooting hours. Setup is
15 minutes/stop, break allowance 20 minutes, minimum worthwhile observation 60
minutes/stop. Dark travel is off by default: movement stays within civil twilight
and entered departure/return bounds. Feasibility uses conservative arrival and
return time, never the optimistic estimate alone. Explicit latest viewpoint-leave
and return triggers are shown. Observation/breaks consume clock time.

Combined trips count both complete outings, accumulate physical effort and include
all clock time between first departure and final return. A one-location stay-put
variant uses one outward/return walk and both observation windows, including waiting
in the elapsed day. No unsupported vehicle relocation is assumed. The advanced
vehicle-transition allowance exists in the validated schedule schema for explicit
scenarios; no transition duration is invented.

Verify the applicable license, dates and legal hours through
[CPW's official big-game page](https://cpw.state.co.us/activities/hunting/big-game)
and current restrictions through [GMUG](https://www.fs.usda.gov/r02/gmug).
These links and service layer metadata were checked October 19 local / October 20
UTC, 2026. Their pages are references, not automatic clearance of a saved plan.
