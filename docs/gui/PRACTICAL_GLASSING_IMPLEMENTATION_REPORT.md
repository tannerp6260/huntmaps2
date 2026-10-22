# Practical glassing opportunity — implementation report v1

Release decision, 2026-10-21 America/Denver: **ship the local data, conservative
access/profile corrections and experimental static review; retain the established
ranking defaults.** The comparisons demonstrate a substantial change in search
allocation and habitat context. They do not demonstrate better deer encounters,
mature-buck selection or biological superiority. New weighting remains opt-in.

Launch with `./trailscout`, then open http://127.0.0.1:8767. Use **Community & scan
review · experimental** for the new comparison. The existing `./huntmaps-gui`
workflow remains available. [Usage](PRACTICAL_GLASSING_USAGE.md),
[methods/sources](PRACTICAL_GLASSING_METHODS.md), and the
[predeclared protocol](PRACTICAL_GLASSING_PROTOCOL.md) describe the controls.

## Repository and preservation

- Branch: `feature/practical-glassing-opportunity`.
- Audited public main and original local main:
  `c594668152783eb8895c8c76284b10bb5fbfba62`.
- Chosen local base: `48eb71010dc1d24a5214b5bf4976e72d8557fa49`, the newer
  `feature/trail-glassing-planner` commit. This reuses its application, terrain,
  attributed networks, approach measurements, schedules and exports.
- Implementation commits: `a378f03` (protocol), `ef39fd8` (feature), `7b85440`
  (exact canonical v1 ordering), `094fc03` (portable access snapshots). Verified
  implementation head: `094fc03a73317ff1e169386a44820dc4c3d8bdf0`.
  The final report commit follows; its exact HEAD/divergence are recorded after
  commit in `.trailscout/evidence/practical-release/git-final.json`.
- Remote heads were inspected with `git ls-remote --heads origin`: public main
  remained at c594668 and ui-redesign-wip at 8c2d277. The latter was five commits
  behind. The local trail branch was one commit ahead of public main. Both local
  worktrees were inspected; neither missing historical pool was present at its
  corresponding result path in either checkout.

The existing GMU-pack/approach work was uncommitted. Its **49 modified/untracked
files were captured and remain byte-identical**, unstaged and uncommitted by this
task. The original binary diff, status, index, branch/worktree records and source
copies are in `.gui/practical-glassing-evidence/baseline/`. Work occurred on the
new branch; main was not edited, reset or advanced. No stash, clean, unrelated
commit, push or merge was performed. No unrelated mount or Windows/Data drive was
traversed.

Before/after SHA-256 comparison covers **37,702 protected files / 7,858,592,646
bytes**, including original data, historical outputs, owner state, waypoints,
working positions, profiles, recovery records and manifests: **zero changed or
missing**. Frozen correction/scouting/transfer inventories retain 3,340 / 3,428 /
6,227 records respectively; overlapping entries are not added as unique files.
All match their frozen hashes. Five frozen test files outside the broad data
inventory were checked separately. Both supplied root reports and
`environment.scout.yml` match their original clean c594668 bytes. No dependency
installation or global package upgrade occurred.

## Completed behavior and architecture

`practical_glassing/` contains pure trait/observation/coverage functions, bounded
package preparation, adapters, five-arm comparison, sensitivity and offline review
exports. TrailScout integrates opt-in settings, current result order, linked review,
immutable saves and JSON export. Its existing routes and timed previews retain v1.

The new package uses signed analytical LANDFIRE classes, official release legends,
lossless COGs, indexed GeoPackage context and shared SHA-256 source objects. Recipe
2 additionally packages six exact access/ownership snapshots. A normal real corridor
was tested from a source root with **no historical data/scouting, runs, results or
owner archives**, using only the installed core pack and companion. Providers were
blocked. The same source revision, real routes and practical review were produced.
An incomplete/damaged legacy archive is not silently replaced by other bytes.

Shared-party defaults are now **2.5 total walking miles / 750 ft cumulative gain**,
with the existing 25% reserve explicit. Extended family is a separate 3 mile/900 ft
choice; solo is never selected automatically. Stored older profiles keep their
numbers. Access fixes reject malformed dates, require actual side-by-side width for
the over-50-inch motor class, and make prohibitions dominate conflicting records.
Conflicting duplicate inventory records become conditional. Traversed graph segments
retain source attributes, direction and permission evidence in exports.

Community traits distinguish mapped aspen, aspen/conifer, conifer, mountain shrub,
sage/browse, meadow and policy-zero classes. Raw codes, names, source identities and
uncertainty remain available. Short-canopy aspen is only a height proxy. Equal browse
treatment, a single bounded nearby-cover term, distance/task preferences and leaf
assumptions are engineering policies. Selected mapped bedrock policy zeros do not
establish ecological absence. Natural understory and horizontal transmission remain
unknown. The original H/G, 2023 sources, original masks and 1.7/0.8 m geometry remain
preserved.

The practical view provides separate community, habitat, unknown, terrain-union and
selected-point observation-support maps; distance bands; whole-patch scan sectors;
total/incremental/exclusive opportunity; physical and weighted overlap; and exported
CSV, GeoTIFF, JSON and provisional waypoint-only GPX. Both new presentation consumers
follow backend order. Source corruption and stale package/model revisions prevent
publication/saving as current work. Unknown-only scores are insufficient-data/null;
known policy zero remains zero. Foreground is uninspected, so assumption bounds
include zero and are not confidence intervals.

Best-view utility uses exact cellwise maxima. Shared-weight arms use the unchanged
packed-union reducer and canonical tie order; observer-specific arms use sparse
float64 marginals and bounded swaps. Repeated identical views cannot earn another
copy. Fixed scan-patch costs do not shrink when low-value/occluded cells are hidden.
Quality-adjusted units never stand for literal acres searched.

## Source identities, coverage and storage

| Source | Actual retained identity and limits |
|---|---|
| Core GMU pack | `co-gmu54 / 20261019-v2`, manifest SHA-256 `82610b2186bc9c7b64a8fe9ec58131194c45132752c082b61597a5a14ad6a4c4`. Original v1 and v2 remain sealed. |
| Official GMU boundary | Fresh CPW GMUID=54 query/count reconciled to one feature. GlobalID `8a42463b-364e-4982-ab87-3be9a8679ddb`, EDIT_DATE 2023-12-28. Current and packaged geometry symmetric difference **0 m²**; projected area 1,513.764662 km². Fresh response/IDs retained separately. |
| Terrain | Existing west 3DEP 20220331 and east current n39w107 source bytes retained. East title 2026-06-30/publication 2026-07-01, mixed acquisition period 1958–2020. Metric/NAVD88, 10 m buffered obstruction support. No new DEM download, seam correction or vertical-datum conversion. |
| Structural vegetation | Existing RCMAP 2023 snapshots unchanged. Product release remains unknown where the source cannot establish it. Coarse fractions/context retain their actual 30/40 m support and unknowns. |
| LANDFIRE | LF2025 EVT/EVC/EVH raw S16, EPSG:5070, 30 m, 1,802×1,517 with 600 m unit context padding. **1,681,882 in-unit native cells; zero in-unit NoData in all three products; every returned code exists in its pinned official legend.** Release/update year is not a pixel acquisition date. |
| Access/context | Six exact USFS/BLM source objects, originally retrieved September 28, 2026, copied locally with original checksums/query footprints/attribution. They include MVUM, motor-closed inventory, ownership, surface management and access points. Some original layer licenses are not stated; that gap is retained. Coverage is bounded and incomplete, especially outside original query footprints. It is not a fresh closure/rights inventory. |
| Dated imagery | Two bounded R0080/R0003 clips, locked source IDs, September 13–14, 2019. Native 0.6 m, exported 0.5 m; the latter does not add native detail. Count/unique-ID agreement, extent/CRS and valid returned pixels checked. No claim these are the latest imagery from all providers or evidence of 2026 leaf state. |
| Fine detail/weather | No new LiDAR or point-cloud inventory/download. Existing local detail remains available for separate inspection. Snow uses an explicit time scenario, not remote-sensed 10 m snow or a migration switch. |

Active companion: `64fab3d1b6f354db533b5e88abf9e131ceaada22e308605e53acce0f8ad7796d`.
The initial companion `b1f854…` remains readable. All three raw/legend/COG identities
are equal across these versions; recipe 2 adds portability rather than changing
ecological inputs. Its six copied objects total **13,942,802 bytes**, with **zero new
transfer** for that update. GeoPackage ownership and network indexes are retained.

Measured companion storage, both versions and shared objects: **67,549,156 logical
bytes**. The existing selected core pack is 1,040,079,696 bytes; all retained core
versions/catalog/preparation are 2,080,338,681 bytes. Detailed checksums, native grids,
codes, manifests and provenance are in the package and
`.trailscout/evidence/practical-release/data-audit-final.json` plus portability records.

Actual response-body transfer total is **28,398,234 bytes**: 18,054,337 companion
preparation, 343,919 initial probes, 7,722 NAIP schema check, 21,148 finalist catalog
checks, 9,834,514 finalist imagery, and 136,594 fresh boundary verification. Optional
imagery is below 10 MB. These totals exclude transport headers and ordinary web
page browsing. No full-unit imagery/LiDAR, credentials or paid service was required.
Source licensing/attribution follows the original records: USGS/USFS LANDFIRE,
USGS 3DEP, CPW, USDA/USFS/BLM and USGS/USDA NAIP; unknown licensing is not invented.

## Five-arm comparison and practical significance

The reported 549/500-point pools are **unavailable locally**. Their replication and
their quoted overlaps/gains are blocked; no 600-point replacement was manufactured.
Separate actual saved pools are `2` (**731 points**) and `soap-creek-v1` (**150**).
They use their exact original coordinates, masks, filters, radii and spacing. Live
owner manual/working edits remain untouched. Both reproduce v1 scores within
**2.3283064365386963e-10 adjusted m²**, and their full canonical v1 orders match.

Review packets:
[731-point actual pool](../../.trailscout/reviews/run2-release/review.html),
[150-point Soap Creek actual pool](../../.trailscout/reviews/soap-release/review.html).
These are static comparisons with no entry or daily-route feasibility inference.
Each includes source/unknown overlays, actual coordinates, distance bands, marginals,
exclusive contributions, overlap/Jaccard and movement between collection positions.

All collections below are evaluated under the **same** three reference policies.
Only physical area is literal m²; the other columns are relative-index m².

| Pool / selection arm | Unique physical m² | Common v1 | Common combined |
|---|---:|---:|---:|
| 731: terrain/target | 8,108,100 | 2,820,079 | 592,585 |
| 731: unchanged fall-mixed v1 | 7,958,600 | 2,925,985 | 624,746 |
| 731: community, fixed observation | 7,532,900 | 2,863,787 | 694,887 |
| 731: observation, fixed habitat | 5,393,200 | 2,153,901 | 759,384 |
| 731: combined static | 4,643,800 | 1,845,369 | 810,544 |
| 150: terrain/target | 16,382,600 | 5,097,278 | 451,862 |
| 150: unchanged fall-mixed v1 | 16,024,400 | 5,438,839 | 535,710 |
| 150: community, fixed observation | 15,849,800 | 5,194,760 | 527,531 |
| 150: observation, fixed habitat | 8,851,400 | 3,077,182 | 682,889 |
| 150: combined static | 7,666,200 | 2,675,473 | 826,792 |

Compared with the v1 collection, combined gains **29.74% / 54.34% under its own
reference policy**, while losing **41.65% / 52.16% physical coverage** and
**36.93% / 50.81% common-v1 opportunity**. V1/combined top-20 overlap is 0/20 and
5/20; collection physical Jaccard is approximately .152 and .135. This is a major
policy tradeoff, not evidence of better hunting. It prevents default promotion.

On the current 731 pool, R0080 is at **38.5544966133, −107.2474335540** and changes
v1 rank 92→combined 290; R0003 is **38.5553640695, −107.2491818211**, rank 45→155.
Those IDs are not asserted to identify the unavailable historical 500-point pool.
Examples A0156 104→559 and A0065 531→33 illustrate large demotion/promotion; actual
point maps and source support accompany the packet. The dated finalist images show
openings beside substantial tree cover; they cannot resolve ground-level screening.

Thirteen predeclared alternatives challenge forage traits, context radii, task,
uniform distance, 15/60 minute scanning and partial/off foliage. They retain 14–20
of combined's top 20 on the 731 pool while changing collection membership. All
selections are cross-scored under the common default; no weights were tuned to
make preferred points win. Perspective/light, posture geometry and measured
foreground ablations remain unavailable/deferred rather than fabricated.

Seven real mapped examples cover aspen, mixed aspen/conifer, short-canopy-aspen proxy,
dense conifer, taller oak/shrub, low-dominant-cover shrub and meadow/cover transition.
Their coordinates, raw labels, counts and maps are in `mapped-cases/` under release
evidence. They are automated map examples, not deer observations or expert labels.

The retained C-series report, imagery and actual approach geometry were also read.
C0095's lower-entry geometry independently measures **22.154 miles return**, consistent
with its old 22.2-mile record; gain is recorded as 3,861 ft. Its conditional road-end
alternative is 1.8 miles / **820 ft**, with unverified parking. Both fail the new
shared-party premise; the conditional gain exceeds 750 ft even before reserve.
That shortcut is not carried into a new primary family recommendation. C0068/C0049/
C0090 conditions and C0064's terrain-control role remain preserved.

## Equal-budget real pipeline and timing

Separate 32-budget Soap Creek and Flattop Bench runs use the same entry/profile and
proposal settings. Baseline versus opt-in review retains **identical candidate
coordinates**. This verifies integration; it does not claim a new sampler/refinement
improvement. New trail/opening-aware sampling remains deferred.

Existing v1 AM previews under conservative defaults include Soap Creek at about
**0.779 mile / 116 ft**, one stop and 160.6 available observation minutes, and a
Flattop Bench two-stop alternative at **1.324 miles / 161 ft**, 132.1 observation
minutes. These are measured complete returns from assumed entries, with conditional
parking/vehicle approaches and unverified sightlines. The new five-point collection
is not a feasible five-stop day. A snow-affected **time assumption** was exercised;
an all-motor-closed scenario was refused explicitly, without scenario averaging.

Machine: Ryzen 7 5700G, 16 logical CPUs, Linux 6.8, Python 3.10.12, GDAL 3.4.1,
NumPy 1.26.4, SciPy 1.14.1, pyproj 3.7.0. BLAS/OpenMP threads were held to one.
Cold means fresh derived state with OS cache retained. Analysis used no provider
network. Some measurements overlapped release validation, recorded in their logs. The major
retained task diagnostic roots measured about 964 MB allocated before the final
portable gate; this subtotal excludes additional per-test temporary directories.
Disk headroom remained above 90 GB and the existing 20 GiB reserve was retained.

| Actual operation | Seconds |
|---|---:|
| Initial companion acquisition + compilation | 14.72 |
| Offline portable package update, no transfer | 3.66 |
| 731-pool five-arm scoring / complete packet | 14.13 / 32.71 |
| 731 complete CLI including legacy validation/preparation | 50.9–56.7 |
| 150-pool scoring / packet; complete CLI | 4.19 / 14.14; 17.5–19.9 |
| 731 pure default score/selection cold / warm | 5.68 / 4.93 |
| Sealed saved-report read, not rescoring | .024–.031 |
| Soap Creek baseline cold / warm / practical with warm geometry | 7.42 / 6.65 / 9.74 |
| Flattop baseline cold / warm / practical with warm geometry | 12.76 / 12.00 / 14.92 |

Largest observed comparison RSS was about **1.10 GiB**; bounded real planner peak
was **709 MiB**. Each corridor obstruction grid was 881×881 cells at 10 m. The saved
731 grid is 1,542×1,314; its exact cells were retained. Final browser probes during
real work stayed below the 250 ms p95 target: the final 86 probes measured
47.6 ms p95 and 71.6 ms maximum. No 5,000-location or whole-unit
end-to-end performance claim is made.

The full saved-pool CLI and ≤2 s warm-rescore target are **not met**. Profiling found
repeated decompression of all arms in the sparse LRU; loading only the requested arm
and retaining the original packed shared-weight path reduced the initial ~91 s run
to ~51–57 s complete. Normal work remains bounded/asynchronous; 32-budget corridor
reviews complete below 30 s. No cells were dropped or downsampled to meet a timing
target. Initial cold acquisition did not instrument a separate network/compute
duration; the 14.72 s total and exact transferred bytes are reported without inventing
that split. Existing stricter cell/storage/free-space guards remain in force.

## Verification and defects corrected

Actual commands and retained logs are under `.trailscout/evidence/practical-release/`:

```sh
./gui/check --keep-going
./trailscout check
.venv/bin/python -m unittest discover -s tests -p test_gui_practical_glassing.py -v
.venv/bin/python -m practical_glassing compare --run 2 --out .trailscout/reviews/run2-release
.venv/bin/python -m practical_glassing compare --run soap-creek-v1 --out .trailscout/reviews/soap-release
.venv/bin/python -m practical_glassing.sensitivity .trailscout/reviews/run2-final --out .trailscout/reviews/run2-sensitivity-final.json
```

Baseline GUI gate passed **312 backend tests, 34 browser journeys, actual interrupted
600-location engineering recovery**, formatting and production build. Final full GUI
gate passed **328 backend tests and all 34 browser journeys**, plus recovery/build:
`/tmp/huntmaps-check-lklnv_nl`, 28m28s, exit 0. Its backend stage collected the first
16 new tests. Subsequent focused/final TrailScout gates cover all **19** completed
new numerical, real-data, portability and API tests. TrailScout's complete gate also
runs its original **28** tests, habitat/unit-pack compatibility and both real-service
browser journeys. No required assertion or timeout was relaxed. The final complete TrailScout gate passed at `/tmp/trailscout-gate-gzjar8vq`: 28 application tests, 50 compatibility/new tests, both real-service browser journeys, formatting and build. Exact counts and outputs are stored in `verification.json`.

New checks cover decoding, release mismatches, policy zero versus unknown, valid
halos and nested windows, categorical integrity, old union equivalence, sparse/full
max equivalence, duplicate/better views, retained/spacing/fewer-than-quota semantics,
fixed-budget monotonicity, radius boundaries, corruption with preserved size/mtime,
malformed/conflicting access dates, vehicle width, exact original order, offline
real routes, separate distance/gain/return limits, save/export/restart, artifact
corruption and an actual archive-free workflow. Existing route tests exercise
asymmetry, shared/repeated travel, junctions versus crossings, gaps/overpasses,
directional budgets, closure/foot distinctions, conservative schedules and DST.
The unchanged frozen baseline/acquisition/comparison/correction/scouting modules
also passed **22 tests** in five explicit commands.

Relevant fixes discovered during implementation: official LANDFIRE export assets
use an additional USGS host; older saved configurations need validated default
aspects; source/profile adapters require run IDs; GDAL approximate categorical
reprojection differed by one nested-window cell; explicit control ranking needed
the original matching/raw-area tie order; the real NAIP field is resolution_value;
and the package needed portable access objects rather than historical archive
dependencies. A new browser locator timeout was corrected with proper accessible
labels. One development test failed because code changed during its stale-model
check; frozen reruns passed. Earlier failed diagnostics remain retained. Matplotlib
Axes3D/AnyIO and Vite bundle warnings are nonfatal and were not suppressed.

## Completed versus deferred

| Phase | Release status |
|---|---|
| A / phase 0 | Audit, branch, protected snapshots, baseline, protocol and preserved controls complete. Missing historical-pool replication explicitly blocked. |
| E / phase 1 | Working installed-unit/corridor/offline slice with immutable base dependency, companion COGs/GeoPackage/source objects, data status and archive-free verification. No database server. |
| F / phase 2 | Existing route stack reused; conservative profiles, source attributes, date/conflict/width correctness and complete-return evidence implemented. Full drive-to-parking/rights integration, reliable-versus-rough-road certification and multiobjective route alternatives remain deferred. |
| G / phase 3 | Community traits, task/range/foliage assumptions, finite search patches, unknown accounting and actual map review implemented experimentally. Foreground/intervening inspection integration, perspective/light, posture recomputation and validated transmission remain deferred. |
| H / phase 4 | Exact best-view complementary **static fallback** complete. Existing v1 one/two-stop schedules remain available. New joint timed/beam planning, daily robust scenario optimization and stalk/retrieval models are deferred. |
| I / phase 5 | Five arms on available real pools, sensitivities, actual equal-budget integration, maps, integrity, regression and measured performance completed. New proposal sampling/refinement comparison and unavailable original-pool replication remain uncompleted. |

The principal remaining evidence gaps are current vehicle/parking/foot/area orders,
other-jurisdiction rights, foreground clearance, actual foliage/snow and actionable
target/stalk/retrieval access. Sparse community/structure data cannot supply local
mature-male selection or encounter labels. Developer desktop review is not blinded
independent or field validation. These gaps explain the static fallback and opt-in
release decision.

## Use and clean reversion

`./trailscout` launches the prepared-unit workflow. Set party/date/start, inspect
the conditional approach and full return, then optionally enable the practical
review and export its evidence. Use current official
[GMUG orders](https://www.fs.usda.gov/r02/gmug/alerts) and appropriate rights/maps
before treating an approach as usable. No legal hunting-hours calculation is offered.

Turn the experiment off to retain the established route objective, or continue
with `./huntmaps-gui`. Code reversion consists of reverting this branch's scoped
feature/fix commits in a suitable checkout; do not reset/clean the inherited dirty
workspace. `.gui`, data, runs, results and `.trailscout` are not deleted or rewritten
by a feature revert. Saved new-model records need the feature for recomputation;
their JSON/CSV/GPX evidence remains retained. No push or merge is part of this release.
