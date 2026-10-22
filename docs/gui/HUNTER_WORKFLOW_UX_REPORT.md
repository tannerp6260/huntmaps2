# Hunter workflow UX — blocked at Stage1

2026-10-22. The prior practical AM/PM plans increment is complete at
`111e2af713a716eecdc4f4f11c20e12e6ba0bd37`, branch
`feature/practical-glassing-plans`. This queued UX workflow created
`feature/hunter-workflow-ux` from that exact state. Its change is documentation,
orchestration and compact evidence only; no UI/analytical implementation changed.

## Actual execution and blocker

`OVERNIGHT_UX.md` was absent. The matching original
`HuntMaps2_Overnight_UX_Coordinator_Prompt.md` was read under the user's direction,
left unchanged and untracked, and copied with trailing blank lines normalized into
[WORKFLOW.md](overnight-ux/WORKFLOW.md). Current instructions/reports, branch/HEAD,
remotes/worktrees and CLI help/version were inspected. No pull/push/merge occurred.

A common brief, three self-contained prompts, strict JSON handoff schema and
recoverable invocation records were prepared. Actual sequential Stage1 launch used:

```sh
codex --no-daemon exec --model gpt-6-astra   -c model_reasoning_effort=ultra --approve-for-me --ephemeral   --output-schema docs/gui/overnight-ux/handoff-schema.json   --output-last-message docs/gui/overnight-ux/stage1-handoff.json -
```

Prompt input came from `stage1-prompt.md`; stdout/stderr were persisted. CLI0.163.0's
header confirmed model `gpt-6-astra`, reasoning `ultra`, OpenAI provider and
workspace-write sandbox. The invocation JSON records the complete arguments.
Two pre-model startup failures are separately retained: conflicting redundant
`--sandbox`/`--approve-for-me` options, then an outer read-only filesystem startup
failure. The corrected startup was approved outside that outer restriction while
Codex's own workspace sandbox remained enabled. No config/provider/auth changes,
new API keys, purchases or permission bypass occurred.

Stage1 operated the existing app in disposable state and recorded a real Flattop
baseline. It then terminated with exit1 and the exact error, reported twice:

> ERROR: Selected model is at capacity. Please try a different model.

The workflow explicitly says to stop on model/rate-limit blockers and forbids silent
substitution. **No accepted Stage1 handoff, design or implementation slice exists.**
Stage2 Sol High and Stage3 Astra High were not started; no repair run was used.
The coordinator's [assessment](overnight-ux/coordinator-assessment.json) is labeled
as coordinator-authored, rather than fabricated model output. Startup parse/init
attempts are distinguished from the single model execution. The raw run is retained
in ignored `overnight-ux/local/stage1.log`; its SHA256 is in the invocation record.

## Evidence and unchanged functionality

[Compact baseline](overnight-ux/baseline-browser-summary.json) records nine scripted
actions on the existing real service: entry, practical opt-in, compare, foreground,
schedule, name, save and GPX export. It captured1366×900 and820×900 layouts, no browser
errors/external requests, and820px document width at820px viewport. Analysis-to-result
region elapsed18.385s. This is a baseline script timing, not user task time or a
before/after improvement. Screenshots and full disposable analysis/save remain in
`/tmp/huntmaps-ux-stage1`; compact hashes are durable here. No biological/field
validation or UX implementation/browser acceptance is claimed.

Fresh before/after hashes cover **45,980 protected files /8,976,127,263bytes**, with
zero changed, missing or added across data/runs/results/owner GUI/TrailScout state.
See [before](overnight-ux/preservation-before.json) and
[after](overnight-ux/preservation-after.json). No original reports, raw sources,
saved points/profiles/exports, other worktree or frozen controls changed. Large
logs, browser screenshots, rasters and owner state are excluded from Git.

`git diff --check` passes. No release gate was rerun because no implementation
changed; the completed practical-plans gate evidence remains in its own report.
The UX acceptance/release gate remains **blocked**, not passed.

## Use and recovery

The completed application still launches with `./trailscout` at
http://127.0.0.1:8767. Enable **Timed practical plans · experimental → Use practical
objective for AM/PM plans**. Together retains nominal2.5mi/750ft, usable1.875mi/562.5ft
after25% reserve. Access/parking/closures and exact foreground openings remain
conditional; the UX attempt adds no new capability.

Common brief/prompts/schema/invocations are in `docs/gui/overnight-ux`. Continuing
requires a later authorized run after model capacity is available; no automatic
fallback/retry or later stage was attempted here. To return to the finished product,
preserve unrelated edits and switch to `feature/practical-glassing-plans`; no data,
state migration/deletion or rebuild is required for this documentation-only branch.
