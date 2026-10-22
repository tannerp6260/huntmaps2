# Hunter workspace

Build with `./trailscout build`. For an isolated preview, run:

```sh
./trailscout serve --state /tmp/huntmaps-ux-sol-review-stage2 --port 8795
```

Open <http://127.0.0.1:8795>. This creates separate test state; existing owner saves
and sources stay untouched. Use another available port if needed.

1. Choose **Who is going?**, then review the daily nominal limits and **Usable after
   reserve**. Together defaults are 2.5 miles / 750 ft, with 25% held: **1.875 miles /
   562.5 ft usable**. Edited values persist; changing the party deliberately selects
   that profile's defaults. Limits include the complete walk and return, and never
   relax automatically.
2. Choose the date, vehicle and **Mapped entry / assumed parking**. Expand **Entry
   evidence · parking conditional**. The search summary describes the corridor and
   nearby search, plus any selected travel/target polygons. **Effort, optics & search
   limits** changes its bounds; **Area & source tools** below the workspace imports
   polygons. Driving, safe parking, current closures and connected foot rights need
   review. A custom start stays visibly identified with its coordinates.
3. Established planning is the default. For the experimental timed AM/PM objective,
   expand **Timed practical plans · experimental** and enable **Use practical
   objective for AM/PM plans**. Task, leaf assumption and an optional per-stop scan
   cap remain explicit. The separate **Community & scan review** is a static
   five-point comparison, never a daily itinerary. Combined/stay modes remain
   established-mode-only.
4. **Compare route opportunities**. Progress reports backend work stages, with no
   ETA. **Cancel calculation** waits for acknowledgement; inputs and the previous
   preview remain. Failure/cancellation offers **Retry calculation**. Source or entry
   failures provide their own retry. If community data is unavailable, turn off an
   existing practical opt-in explicitly to use established planning.
5. Read the recommendation's entry/date/party, full return-inclusive effort,
   movement range, observation and scheduled return. **Plan period** chooses AM/PM
   recommendations separately. **Compare a different option** offers different
   viewpoint sets in backend preview order. **All retained route previews** below
   the map retains every full preview; it does not add a new ranking.
6. **Inspect route & sightlines** and **Review schedule** move keyboard focus to the
   selected evidence. Expand **Selected scan sectors** for bearings/ranges and
   **Foreground inspection** for coarse cover evidence. The map, selected support,
   scans and route follow the same selection/period. The theoretical terrain toggle
   is separate. Coarse RCMAP risk cannot certify a clear opening, measured transmission
   or safe/legal access; inspect the actual opening and ground in the field.
7. **Name, save & export** focuses the name. Save the feasible selected option,
   then export its field summary, JSON, GeoJSON or GPX. The export caption identifies
   the immutable saved name/period/version. Changing a preview leaves those files
   tied to that version until another save. Saving an opened version creates a new
   version; **Save as a separate plan** preserves the earlier history independently.

The browser remembers period, selected option, inspection view and plan name on the
same local origin/state. A pending input draft has immediate local recovery plus a
serialized server draft write. A newer completed calculation takes precedence on
reload; opening an earlier saved version intentionally can still be remembered.
Unavailable browser storage falls back to server drafts/saves. Different ports use
different browser storage; use **Saved plans & versions** to reopen a saved version.

Edited inputs label the old calculation and prevent saving until recalculation.
An empty result keeps limits intact and explains the unsupported period/data/pins;
review inputs rather than assuming another entry or party was chosen. Existing
version-1 saves retain original scores and exports. No participant study, improved
biological prediction, field validation or verified access is implied by this UI.
