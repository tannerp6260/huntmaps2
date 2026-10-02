# Current-waypoint movement controls — 2026-10-01

The small observer movement map now centres on the committed working waypoint or
legacy provisional waypoint. Its white marker identifies that current waypoint;
orange identifies an unsaved preview. The pale allowed-movement circle and small
original-setup cross remain anchored to the original setup. Untouched setups use
a 30 m map span; moved waypoints use 40 m so the entire original circle fits.
Image cropping, click translation and marker positions share the same transform.

**Return to current waypoint** restores the committed stance. A successful update
recentres immediately; previews, failures and cancellation do not change the
committed centre. Preview displacement is relative to the current waypoint.
Backend coordinates, movement validation, scene geometry and coverage are unchanged.
No new API, scene generation, acquisition or extra movement job was introduced.

Verification:

- TypeScript and production build passed.
- Nine nearby-observer and seven working-waypoint backend tests passed.
- Actual Chrome with external requests blocked passed waypoint update/reopen,
  centred map-click translation, stationary centre during preview, exact one-foot
  steps, reset, unchanged boundary rejection, immediate second-update recentering,
  comparison, exports and restore. Mutation testing used an isolated localhost
  server on port 8766 with temporary GUI state, preserving the user's A0075 update.
- Four-scene nearby regression passed exact terrain/foliage ray agreement,
  unchanged Dense120 coverage, no preview jobs/assets, legacy review/reopening,
  exports and deletion.
- A separate read-only Chrome check opened the user's existing A0075 update and
  verified the exact movement centre, with saved state unchanged. Its movement-map
  screenshot was visually inspected: `/tmp/huntmaps-recentred-user-map.png`.
- Legacy provisional waypoint centring and reset were separately tested in
  temporary GUI state.
- Protected-file SHA-256 audit: 7,105 files checked, zero changes.

Logs: `/tmp/huntmaps-recentre-{browser,backend,working-tests,nearby,user,legacy}.log`.
Screenshots: `/tmp/huntmaps-working-waypoint/recentred-controls.png` and
`/tmp/huntmaps-recentred-user-map.png`.

Repeated updates cannot advance the exploration boundary. The 120 m foliage patch
and 300 m fine-ground circle remain centred on the original scene, preserving
existing validation and performance limits.
