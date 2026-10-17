# Scene storage policy correction — 2026-10-15

Preparing terrain-only A0306 in `scouting-2026-10-166` failed because all saved
scene bundles and retained partial scenes shared an 800,000,000-byte quota. Their
755 MB total plus a 60 MB reservation exceeded that quota despite ample free disk
space. Repeated preparation could not resolve this condition.

Scene creation and both upgrade paths now preserve the existing 20 GiB free-space
reserve instead of imposing a quota on accumulated scene history. Source-plan
review and preparation start use the same estimate: 60 MB per requested scene,
bounded shared lidar spools when needed, source assembly headroom and the existing
three-copy download allowance. Estimates are conservative; cached reuse can need
less space. Saved bundles and partials are reported separately and are already
accounted for in filesystem free space, rather than added to the required budget.

Workers recheck preflight and check capacity before binary assets, grids, textures
and copies are written, as well as at preparation stages and publication. A low-space
failure keeps the old ready scene and any new partial work. Existing geometry,
point-count, memory, stage-time and download-approval guards remain in force. No
automatic cleanup, scene regeneration, model change or output migration occurs.

Verification:

- Eight scene-storage tests cover history above the former quota; batch/download
  estimates; the exact free-space boundary; separate temporary storage; worker
  preflight; API start and allowance review; full scenes and both upgrades;
  a disk-space drop during preparation; preservation of ready pointers/partials;
  and inventory concurrent with atomic scene publication.
- Existing transfer, first-person and workflow suites: 35 tests passed.
- Frontend typecheck/build and formatting checks passed.
- Browser check verified the usage display, actual terrain-only preparation,
  disabled preparation under a simulated low-space review, and the 900 px layout.
  Artifacts: `/tmp/huntmaps-scene-ui-check-htmp5n5o/browser-scene-storage-check/`.
- A0306 prepared using the exact observer snapshot from the failed plan, in an
  isolated state directory containing 900 MB of sparse test history and 34 MB of
  retained test partials. The normal bounded subprocess completed in 1.07 seconds,
  produced 249,892 terrain triangles, and downloaded no sources. This is a
  terrain-only view; fine ground and measured vegetation remain unavailable.
  Evidence: `/tmp/huntmaps-scene-storage-live-7vivbzg9/evidence.json`.
- Protected-output inventory/hashes and original owner records were unchanged.

Restart the GUI server to load the backend change, then retry **Prepare views**.
The existing source plan remains usable if its source approval and waypoint
snapshot are still current. Existing historical scene reports retain their original
budget statements as records of the earlier implementation.
