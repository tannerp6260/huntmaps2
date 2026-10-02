# Nearby observer exploration

Launch `./scout gui`, open the saved Soap Creek review, select a prepared setup,
and click **View from this setup → Explore nearby positions**. The small aerial
map moves your stance; the separate larger plan map chooses an inspection target.
Click within the 30-foot circle, use its arrow keys, or use the one-foot direction
buttons. **Return to current waypoint** restores your committed stance without
changing the eye height or heading. The white centre is the current waypoint; an
orange dot marks an unsaved preview. After an update, this small map recentres
on the new waypoint. Its pale movement boundary remains centred on the original
setup, shown as a small cross. The map spans 40 m for moved waypoints so that the
entire allowed boundary stays visible (30 m for an untouched setup).

The main view always uses Dense foliage and the existing 120 m patch. The green
inspection-map circle stays centred on the original setup. Moving does not extend
this coverage. Distant terrain remains viewable, but nearby-position profiles are
limited to the saved 300 m fine-ground circle; vegetation beyond the 120 m patch
is explicitly unevaluated. Positions outside the observer polygon or on unknown
ground are rejected, without snapping or moving the current view.

To apply a position, expand **Update waypoint**, give it a name and field notes,
then update. Wait for its terrain calculation to complete. Back on the main map,
the current setup has the updated marker and its own terrain shading. Use its
Export checkbox for GPX/KML or **Restore original setup** to undo the change.
See [Working waypoints](WORKING_WAYPOINTS.md) for persistence and calculation details.

Saved neighborhood cards show an original setup first. Expand **saved alternatives**
to compare their individual masks or export them. These are existing groupings;
the original is not an automatically chosen best representative.

## Implementation and scope

Only the four prepared Soap Creek pilot scenes are supported. All positions use
anchor-relative projected east/north metres, limited to 9.144 m. Longitude/latitude
are derived on the backend using the run's projection, with no coordinate snap.
Camera ground and translated profiles interpolate exactly the float32 fixed-diagonal
triangles rendered by WebGL, retaining the scene's original curvature correction.
Targets and foliage intersections share that unchanged anchor coordinate system.
No analysis command, download, extra source acquisition or mesh generation is
triggered by movement. Dense120 uses existing cached surfaces and rendering budgets.

Working updates live under `.gui/working-waypoints/`; legacy standalone records remain
under `.gui/manual-observers/`, never in
protected run folders. Each records its original setup, offsets, exact coordinates,
scene key, assumed foliage and review notes. Saving validates the point again.
Review updates cannot move its coordinates. GPX/KML resolve stored IDs on the server,
rather than accepting coordinates from the export request.

Vegetation is inferred from 2019 measurements, with assumed opaque cluster shapes;
it is not a current measured eye-height vegetation reconstruction. A nearby stance
can change foreground screening without substantially changing the broad terrain
view. Explicit waypoint updates calculate baseline terrain visibility; no new ranking,
sampling or route optimization is added.

One-foot nudges interpolate the saved 1 m ground grid. They let you investigate
modelled foreground changes without implying foot-scale survey accuracy.
