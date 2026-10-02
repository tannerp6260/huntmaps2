# Updating a waypoint and its terrain view

Launch `./scout gui`. Open the saved Soap Creek review and select a prepared setup.
Choose **View from this setup → Explore nearby positions**, then click within the
30-foot circle or use the one-foot buttons. Expand **Update waypoint**, add a name
and notes, and click **Update waypoint**. Wait for the ready message, then **Return
to map**. The marker and terrain shading now represent the updated working stance.
Use **Restore original setup** in the right-hand panel to undo the working change.

An update keeps the same setup identity. It does not create another alternative.
The working location survives a reload, reopens in first person, participates in
individual-mask comparison, and supplies its exact coordinates to GPX/KML exports.
Original files and coordinates remain unchanged. Existing standalone provisional
waypoints remain readable and can be updated through the same workflow.

Moving is a preview and uses existing cached scenes. Only clicking Update starts
one background terrain calculation, using the existing engine and cached baseline
10 m DEM, target mask, 2 km radius, 1.7 m eye height, 0.8 m target height and 6/7
curvature coefficient. There are no downloads. Target clipping, alignment and
NoData handling are preserved. Fresh terrain area and cover breakdowns replace the
working metrics; historical inspection scores and sectors are not reused at a new
position. Small moves may produce the same broad terrain mask at 10 m resolution.
Dense nearby foliage remains a separate inferred first-person inspection model.

State, task specifications, masks and provenance live in `.gui/working-waypoints/`.
A revision-keyed tile URL prevents the old mask being reused. Cache keys include
coordinates, parameters, source hashes, engine hash and GDAL version. A completed
job publishes location and mask together. Failure, cancellation or interruption
retains the prior working state. Restore discards pending publication, including
late job completion. Partial files are separate; original runs are never edited.
The worker has a 900 s time limit, 1536 MiB address-space limit and 800 MB per-run
working-cache budget. There is one analysis job at a time.

Updated locations need field inspection. Terrain visibility does not establish
vegetation visibility, current cover, deer presence, safe footing or legal access.

The movement map centres on the committed waypoint, including immediately after
a successful update. Click coordinates account for this new centre. Previewing
does not pan the map. **Return to current waypoint** discards the preview;
**Restore original setup** removes the working update. The original 30-foot
exploration boundary, 120 m foliage patch and 300 m ground scene do not move.
Repeated updates therefore cannot walk the exploration boundary across the area.
