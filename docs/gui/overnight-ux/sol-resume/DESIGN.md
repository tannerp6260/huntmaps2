# Hunter workflow design · Sol High Stage 1

2026-10-22 · `feature/hunter-workflow-ux` · starting HEAD
`6ec6a5510058edb5668fb0ad83596f2c8795caa6`. Product base remains practical plans
`111e2af713a716eecdc4f4f11c20e12e6ba0bd37`. This is design and one implemented
slice, not completion of the full UX workflow or independent review.

## Evidence and design decision

Read the root/TrailScout instructions, glassing SPEC/PLAN/STATUS/README, practical
plan implementation/methods/usage/protocol, original workflow/common brief/schema
and prior blocked report. Inspected the actual React app, map, practical controls,
API, schedule/effort formulas, service/storage, build and browser gates.

The previous baseline is historical evidence only. A fresh unchanged-code browser
baseline used real Flattop Bench, 2026-10-31, Together, default 32 candidates,
practical identify/unknown leaf/no scan cap in disposable state. It completed the
same nine scripted actions: entry, settings disclosure, practical opt-in, calculate,
foreground, schedule, name, save, GPX. Recommendation IDs matched the prior baseline.
The baseline comparison button began at document y=1278.8; selected option y=746.8;
save y=2789.0 at 1366×900. Result timing was 18.881 seconds; this measures script
submission-to-region time, not participant task time. Screenshot inspection shows
the map dominates the first result viewport, while the practical summary starts
near its bottom. A long list of sectors separates selection from schedule/save.

Choose one continuous workspace with a compact input column, one decision panel,
the map and expandable evidence. No required wizard. Keep the warm cream/dark green
palette and use borders/spacing, readable text and plain labels rather than more
badges or decorative cards. A result should first answer: what option, from which
entry, at what walking cost, for which time of day, with what return assumption?

## Layout and flow to complete in Stage 2

Desktop, 1366×900: header identifies TrailScout and provisional context. Left column
holds party, nominal/usable limits, date, vehicle and assumed entry/area; a readily
reachable calculate action follows the essential inputs. Advanced controls remain
in native disclosures. Right side starts with the decision panel, then the map,
selected route/sightline/schedule evidence, save/export and saved history.

820px: retain a compact two-column layout only while labels/controls remain readable;
summary facts form two columns and actions wrap. 390px: stack inputs and workspace,
single-column facts, full-width action buttons. Never hide essential actions or
depend on horizontal scrolling. Keep local overflow only for long evidence tables.
Stage 1 adds scoped responsive styles; restructuring the rest is Stage 2 work.

Essential input copy: **Who is going?**, **Nominal daily limits**, **Usable after
reserve**, **Assumed entry / parking**, **Search area**, **Compare options**.
Together is nominal 2.5 mi / 750 ft with 25% held, usable 1.875 mi / 562.5 ft.
Keep saved overrides; do not replace them with preset defaults on navigation.
Area/corridor is a bounded analysis region, not whole-unit discovery. Advanced
controls expose effort/optics/search, timed practical settings (opt-in), separate
static community comparison, schedule, access and owner edits. Static five-point
collections must never be grouped into the timed itinerary recommendation.

The result panel identifies experimental timed practical vs established mode,
recommended vs selected alternative, period, exact entry/date/profile and full
return-inclusive distance/ascent. It shows movement range, scheduled observation,
scheduled return and usable/held effort after return. Show a few different options
without inventing a new rank: use backend order, suppress duplicate viewpoint sets
for the short list, retain every original preview in the full evidence.

Actions: **Inspect route & sightlines**, **Review schedule**, **Name, save & export**.
Inspection preserves selection; period changes use that period's backend
recommendation. An alternative can return to the recommendation explicitly. The map,
scan support and route must always derive from the same option and period.
Stage 1 retains the existing full preview/evidence layout below the map. Stage 2
should consolidate duplication and progressively disclose long sectors/evidence.

## State contract and recovery

- **Loading sources**: factual checking message, no promise of offline readiness
  until sources are known. **Missing/corrupt package**: name the missing package,
  retain settings/saves, provide preparation/source review or retry; established
  planning can remain available when only the practical package is missing.
- **Ready inputs**: inputs editable without a mandatory ordered walkthrough.
  Draft writes must be serialized/versioned so an earlier response cannot overwrite
  newer work. Distinguish user edits from restoring a draft.
- **Submitting / running / cancelling**: disable duplicate submission/save, show
  backend stage and message. No invented percentage or ETA; use determinate progress
  only for a backend total with meaningful units. Cancel transitions to cancelling
  until the worker acknowledges. Preserve edits made during work.
- **Completed**: select backend recommendation for the active period; if edits
  happened since submission, label the result as previous inputs and disable save.
  Use a generation/revision identity for all open/run/context responses.
- **No feasible recommendation**: say which period has no fit. Keep limits unchanged;
  allow schedule/access/input review and explicit recalculation. Show concrete pin,
  route or insufficient-support reasons; never substitute another entry/profile.
- **Failed/interrupted/cancelled**: retained inputs and previous result remain;
  separate previous result from failed attempt and offer explicit retry. Network
  status failure must not claim a job stopped. Never mask corruption as empty success.
- **Save**: focus name, save exact selected option/mode/settings through existing
  immutable API; acknowledge version. Exports stay tied to the saved version even
  if the current preview changes. Make that identity explicit. Reopening/reloading
  should retain compatible inputs, mode and selection, with stale-source disclosure.

Stage 1 implements the panel, existing selection callbacks, focus jumps and previous
input/running warnings. It adds `active` to save disabling. It does not claim the
remaining persistence/error/concurrency contracts above have been completed.

## Component boundaries and actual value mapping

`main.tsx` owns config, dirty/job/result, selected ID, mode, save identity and API
effects. Shared `selectOption` clears transient point/segment/profile inspection;
`selectMode` uses the existing backend recommendation. `recommendation.tsx` is
presentation only: no fetches, analysis, new scoring or save state. It accepts the
same result/option/mode as `ScoutMap` and existing detail components. Keep future
input and save extraction similarly controlled; avoid parallel selection stores.

| Display | Actual backend field / operation |
| --- | --- |
| Recommendation | `result.recommended[mode]`, never frontend score sorting |
| Practical/established label | `result.practical_plan` presence |
| Exact context | `result.start.label`, `result.settings.date/profile.label` |
| Number/order/coordinates of stops | `option.viewpoints`, unchanged |
| Complete effort / movement range | `option.schedules[mode].movement` when present (combined trips), otherwise `option.movement` |
| Observation | Sum of `schedule.events[kind=observe].minutes` (also works for combined) |
| Scheduled return | Last `schedule.events[kind=return].arrival`, formatted America/Denver |
| Return constraint / leave trigger | `schedule.return_by` / `latest_leave_viewpoint`, separate from actual scheduled arrival |
| Usable / held effort | `option.remaining`; for combined only use the same `profiles.remaining` formula against backend doubled movement and result profile |
| Input usable limits | `max_miles/max_gain_ft × (1 - reserve_fraction)`; preserve exact fractional display |
| Short alternative list | First two feasible previews with different unordered viewpoint ID sets, preserving backend order; full previews retained |
| Practical utility and useful scans | `schedule.practical.relative_m2`, `visits.minutes_used/observation_minutes/unused_observation_minutes`, never deer probability |
| Selected sectors / support | `schedule.practical.sectors/coverage_url`; theoretical `option.coverage_url` remains separate toggle |
| Habitat / unknown / foreground | Existing practical visits/support/inspection, no reinterpretation as measured transmission or clearance |
| Save/export | Existing `/api/plans` and saved-version export endpoints; unchanged coordinates, versioning and provenance |

## Accessibility and compatibility

Use semantic section headings and definition lists; native labeled select/details
keep keyboard behavior. Summary actions are ordinary buttons, with visible focus,
at least 42px height and wrapping labels. Jump actions transfer focus as well as
scroll: inspection section is programmatically focusable, save jumps to the name
input. Selected full previews expose `aria-pressed`. Do not claim a full WCAG audit
from a few keyboard checks. Stage 2 must fix any preexisting tab semantics and check
contrast, focus restoration, narrow/zoom layouts and asynchronous announcements.

No backend/settings/schema changes. Established combined/stay remain available;
practical combined/stay remain disabled. No candidate/ranking/habitat/feasibility,
source, export or frozen-control changes. Roads, parking, closures, foot permission,
foreground openings and target-side retrieval stay conditional. UI improvements
are not biological improvement, participant research or field/blinded validation.
