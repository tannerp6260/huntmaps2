# Learn HuntMaps2

Launch with `./huntmaps-gui`, then choose **Learn**. The numbered learning path
recommends lesson 1 first. No prior analysis run is needed: lessons open the
completed local Soap Creek example automatically.

## Lesson 1 — Review the saved example

Five steps teach the actual controls:

1. Select A0075 in the observer cards on the **left**. Read its saved coordinates,
   visible area and cover in the **right** details panel.
2. Check **Compare** inside the left-hand A0075, V010 and V008 cards.
3. Toggle V010 inside **Compare individual saved views**, above the map.
   This hides its overlay without removing it from the comparison.
4. In **Practice review** on the right, choose **needs inspection** in Decision,
   write a field question and Save review.
5. Check **Export** inside the left-hand observer cards. Use **GPX/KML below the
   list** to download practice waypoints.

The relevant controls receive a gold outline and scroll into view. The current
instruction stays visible above the map. Detailed explanations appear within each
step; there is no final quiz. The quick reference includes separate side-view and
map-view illustrations rather than mixing sightline and sector geometry.

Practice exports start with **PRACTICE** in filenames and waypoint names. Their
coordinates are the saved observer coordinates; their notes belong to practice.
These files contain observers, not target openings or routes.

## Lesson 2 — Draw your own area

Practice over cached Soap Creek imagery, without creating a run:

1. Choose **Draw boundary** on the right. Click at least three corners on the map.
   Click the first corner again, press Enter, or choose **Finish shape**. Then
   choose **Use this boundary** to validate it.
2. **Edit vertices** allows dragging corner handles. **Undo**, **Cancel drawing**
   or Escape help correct mistakes; **Clear boundary** removes the shape.
3. Hover over, focus or click the question marks beside settings to understand
   run name, view radius, inspection minutes, candidate count and download cap.
4. Learn acquisition planning and actual job monitoring, then finish practice.

Practice geometry lives in the browser and `.gui/practice-areas`, separate from
real imports and results. The backend cannot use a practice import ID to prepare
a real plan. Finishing the lesson never transfers its example shape to a real run.

For your actual area, choose **New baseline run → Draw on map**. Draw, edit and
validate your own boundary, or choose **Import file** for GeoJSON/KML/KMZ. Imported
multiple polygons still require deliberate selection. **Go to location** accepts
latitude/longitude without a geocoding service. Optional online imagery supplies context beyond cached coverage as you pan and zoom. Local elevation and analysis still require your real area’s sources. Turn off **Online imagery — fill gaps** for offline viewing.

Give the run a unique name, prepare its acquisition plan and inspect estimates,
source details and download cap. Only authorize bulk downloads explicitly when
ready. Practice disables planning and analysis; it does not simulate percentages
or pretend an analysis has completed.

## 3D terrain

In saved-result review, choose **3D terrain**. Use **Tilt**, the rotation buttons
or map gestures. **2D** returns to a top-down view; **Reset view** also restores the
local coverage overview. Drawing remains in 2D.

Terrain comes from the saved local DEM at true scale. Imagery, visible-target
cells and sectors drape over it; changing the camera never changes analysis,
coordinates or scores. Hillshade remains where imagery is unavailable. Navigation
is bounded to local elevation coverage and the area outside it is hidden. Runs
with incomplete/unsupported elevation stay in 2D; elevation-loading errors return
to 2D with an explanation. There are no 3D trees, new downloads or observer-eye
visibility simulation.

## Progress, offline use and meaning

Pause and resume either lesson. Completion is tracked separately for each lesson.
Practice notes and the last validated practice drawing persist across reloads in
this browser profile under `huntmaps-training-v2`. Existing v1 notes and completed
lessons migrate; unfinished old lessons restart at the revised first step. Clearing
browser storage removes browser practice state. Real reviews remain separately on
disk. Cached results, help, drawing practice and local 3D work without outside
network access when the example/data are available.

Colored cells mean **terrain permits a sightline**, not guaranteed visible deer,
clear vegetation, legal access or a safe approach. Inspection sectors include
hidden ground. Soap Creek’s experiments have not been shown to generalize elsewhere.

## Developer verification

From `gui/frontend`, with the localhost application running:

```sh
npm run build
npm run test:training
npm run test:browser
```

Training screenshots and results are written to `/tmp/huntmaps-training-v2`.
Installation details: [README.md](README.md). Evidence and limits:
[TRAINING_VERIFICATION.md](TRAINING_VERIFICATION.md).

Settings help now distinguishes initial locations to evaluate from shortlist size. Open **How locations are chosen** to understand sampling, then **Advanced scoring settings** for the assumed inspection time. This assumption changes inspection scores, not visible terrain or a recommended stay at each spot. The maximum download size applies to analysis acquisition; online imagery browsing is separate.
