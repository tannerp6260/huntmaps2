# Lidar detail recovery — 2026-10-17

The A0265 detail check failed before scene preparation because older cached source
records lack `acquisition`. Best-detail discovery seeded those records unchanged,
then indexed the missing field. The existing A0265 bundle contains no lidar source
hashes, measured points or foliage geometry; it is a terrain preview.

## Repair

Cached metadata is adapted in memory using the same allowlisted USGS URL-to-project
identity as catalog records. Historical manifests are not migrated or rewritten.
Discovery retains checksum verification, checks recorded sizes, excludes unidentified
or conflicting metadata with a reason, and selects a single acquisition. Cached and
catalog duplicates retain each requested setup once. Offline discovery uses the
same normalized, verified entries rather than replacing their setup associations.

Failed checks show Retry Improve detail and unknown estimates instead of a permanent
checking message, NaN allowance or cached-download timing. Starting a new check
detaches the previous plan. Failed preparation retains its open details and existing
scene; successful preparation directly fetches and displays the completed scene.
The viewer reports fine-ground and inferred-foliage availability. Existing measured
support, foliage geometry/thickness, vertical-reference rules, nearby movement limits
and explicit Update waypoint publication are unchanged.

## A0265 source check

An isolated live metadata check for `scouting-2026-10-16222/A0265` now succeeds.
The selected acquisition is `CO_WestCentral_2019_A19/CO_WestCentral_2019`:
one cached tile plus three missing lidar tiles (209,126,735 bytes), with bounded
dated NAIP fine/context imagery (24,537,216 estimated bytes). Total estimated new
payload is **233,663,951 bytes**, with a suggested **290 MB** allowance. Source
availability and estimates can change; the displayed plan remains the approval.

A cached-only preparation in isolated state reads 790,177 local returns and supports
18.7% of the fine grid, but the observer itself lacks supported fine ground. That
scene correctly retains terrain fidelity and disables standing-position refinement.
The missing tiles must be prepared before fine ground can be evaluated at the setup.
No new bulk source payload was downloaded, and no owner scene pointer was changed.
Retained diagnostic state: `/tmp/huntmaps-a0265-source-check-wmcjx53c`.

## Verification

Ninety relevant backend tests pass across legacy recovery (10), source selection
(8), scene storage (8), first person (21), vegetation screening (7), nearby foliage
(6), connected foliage (7), nearby observer (9), working waypoints (7), and workflow
(7). The recovery test decodes an actual synthetic compressed LAS file carrying an
explicit compound CRS, prepares fine ground and nonempty foliage at every supported
range, verifies a nearby observer preview, and preserves the original scene and
legacy source manifest. Other regressions cover mixed manifest versions, duplicate
catalog rows, offline operation, missing metadata, incompatible acquisitions,
payload corruption, changed catalog sizes and unknown transfer timing.

The isolated browser recovery journey passes at desktop and 900 px widths. It injects
a slow failed source check and a failed preparation, retries each, then runs actual cached LAS preparation through the
worker, verifies direct scene replacement, checks 225 supported cells and 10,648
rendered foliage triangles, compares foliage-on/off scene pixels, and moves the
standing-position preview one foot. The failed check retains terrain; no NaN or
false cached estimate appears. Feedback is visible within the 200 ms browser bound.
Frontend build and formatting checks pass. Recovery diagnostics:
`/tmp/huntmaps-check-mm5boi0e`. The historical first-person journey also passes,
including all four saved lidar scenes, imagery, foliage toggling and context-loss
recovery (`/tmp/huntmaps-check-axy2o5r9/screenshots/browser-first-person-check`).
Its request assertion now permits the existing read-only network-resolution POST;
unexpected mutations, annotation changes and added jobs still fail the check.
The connected-foliage browser check also passes for all four historical scenes,
including the older clump bundle, rendered/numerical ray agreement, range budgets,
foliage toggling, idle rendering and 900 px layout. It now chooses a close plan-map
radius explicitly before testing foliage; the new 1,000 yd default otherwise put
its old test click beyond fine-terrain support. Diagnostics:
`/tmp/huntmaps-lidar-cluster-check-final`.

Before/after preservation checks cover 8,032 protected file records and 693 owner
records, with no changes or additions. Existing analyses, coordinates, source
manifests, scores, reports and owner scene bundles remain unchanged.

Restart HuntMaps to load the backend repair, then use **Improve detail → Prepare
views** after reviewing the selected sources and allowance. Inferred foliage appears
only where the prepared lidar provides the existing model's required support.
