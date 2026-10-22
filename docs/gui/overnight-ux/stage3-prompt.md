# Common brief — bounded hunter workflow UX

Workspace: /home/tanner/Desktop/huntmaps2. Required branch: feature/hunter-workflow-ux.
Base: feature/practical-glassing-plans at 111e2af713a716eecdc4f4f11c20e12e6ba0bd37.
The requested OVERNIGHT_UX.md filename is absent. The original matching workflow is
HuntMaps2_Overnight_UX_Coordinator_Prompt.md, which remains untracked and unchanged;
WORKFLOW.md is a content copy (trailing blank lines normalized). Do not stage the original.

Read AGENTS.md and trail_scout/AGENTS.md, relevant docs/glassing SPEC/PLAN/STATUS/README,
docs/gui/PRACTICAL_PLANS_{IMPLEMENTATION_REPORT,METHODS,USAGE,PROTOCOL}.md and actual code.
This explicit UX authorization supersedes historical milestone scope stops, but never
frozen analytical controls or preservation requirements. Do not touch main, stash,
reset, discard changes, push, merge, global config, dependencies or unrelated mounts.
Never inspect Windows partitions or mounted Data drives. Original source roots are
read-only; owner .gui/.trailscout/data/runs/results, original waypoints/reports/saves
must not be modified. Use scoped /tmp/huntmaps-ux-* disposable test state. Existing
.venv/bin/python/native GIS and installed browser dependencies only. No new API keys,
provider/billing changes, purchases, source downloads or synthetic hunting observations.

Capability verified from code/report: working experimental opt-in timed practical
one/two-stop AM/PM plans with actual stop time and joint scan allocation; established
planning remains; static five-point comparison is separate, not a daily itinerary.
Combined/stay practical plans unavailable. Prepared real GMU54 packages, Soap/Flattop
entries present. Foreground is coarse 40m RCMAP risk, not measured transmission or
clearance; no compatible measured local obstruction. Candidate generation unchanged.
Preserve analytical behavior, habitat/ranking/feasibility policies, exact coordinates,
save/export identities, provenance, uncertainty and experimental labels.
Together nominal 2.5mi/750ft, held25%, usable1.875mi/562.5ft. Do not relax automatically.
Driving/parking/current closures/foot rights/field opening remain conditional.

Goal: party/usable effort -> assumed entry and area -> analysis -> primary recommendation
and a few distinct alternatives -> route/sightline inspection -> save/export. Progressive
advanced controls, readable restrained design, laptop/narrow layout, focus/keyboard,
recovery/cancel/retry/errors/empty/missing packages, input/selection persistence, stale
response protection, map-route-sector agreement. No fabricated progress/ETA, usability
participants, biological improvements or field validation. Ordinary users need no GIS
expertise; experts need no mandatory wizard. Trace displayed values to actual backend.

Execution: you are ONE stage only, not coordinator. Do not invoke another Codex run,
change model/effort, orchestrate stages, or spawn writing helpers. One UI owner. No
coordinator implementation edits occur while you run. Do not commit; leave a reviewable
scoped diff for coordinator verification/commit. Persist compact evidence and handoff
in docs/gui/overnight-ux; large logs/screenshots/state in ignored local/ or scoped /tmp.
Use Playwright and installed /usr/bin/google-chrome following existing checks; serve
with --state in disposable state and an available port, never owner state. Relevant
runners: ./trailscout check and ./gui/check --keep-going; keep failed/full/rerun outcomes
distinct. Existing gate browser patterns: trail_scout/checks/browser.mjs,
practical_glassing/browser.mjs and timed-browser.mjs. Do not weaken test assertions.
Baseline previous tests are historical context only:48 app/50compat/3 browser and
GUI331/34; new claims require actual runs. If required browser, model, human approval,
rate limits or unrecoverable failure blocks acceptance, preserve work, report exact
blocker and stop; never bypass sandboxing/denied actions or retry recursively.

Final JSON handoff MUST conform to handoff-schema.json: stage, status, branch,
source identity (HEAD plus tracked diff SHA256; include untracked implementation
file hashes in artifacts), actual artifacts/checks, findings/blockers/remaining tasks.
Complete only when your stage acceptance is met. Include launched app instructions.
Coordinator will inspect actual diff, artifacts and results before next stage.

# Stage 3 — Astra High: independent browser review
Read original WORKFLOW/COMMON_BRIEF goals, stage handoffs, actual source and diff; then
independently perform realistic tasks with fresh disposable state. No implementation
edits. Try conservative Together, conditional access, missing data, no feasible result,
navigation/reload, save/export, desktop/narrow keyboard workflow. Validate route/scan/
recommendation identity, preservation, confidence/copy/hidden controls and task clarity.
Use real services; label synthetic error fixtures. Do not trust prior test claims alone.
Write STAGE3_REVIEW.md with prioritized findings, exact reproduction and acceptance
criteria, observed before/after vs judgment. Material fixable findings may get ONE later
Sol High repair run by coordinator; do not invoke it. A completed review may contain
findings; blocked means unable to perform required review, not just defects found.
Finish structured stage=3 handoff including findings, actual checks and source identity.
Stop after this stage; do not start another review/model loop.

# Full authorized workflow

After the current task finishes, carry out this unattended HuntMaps2 UI/UX workflow. This message queues NEW work; it does not cancel or alter the current task.

Act as a lightweight coordinator. Use actual sequential Codex CLI runs with explicit model/reasoning settings for the three stages below. Do not merely describe model switches, simulate another model, or implement all stages yourself.

First establish the current repository/branch/HEAD, status, worktrees, applicable AGENTS.md instructions and recent implementation reports. Preserve all existing work. Inspect the latest code rather than assuming the earlier reviewed 903d47d branch is still current. This request authorizes a focused UX implementation, preserving analytical controls and historical evidence.

Create a new feature/hunter-workflow-ux branch from the just-completed intended feature work. Never modify main, reset/stash/discard work, commit unrelated changes, push or merge. Preserve original data, owner state, saved points, existing analyses and recoverable user work. Never inspect or alter Windows partitions, mounted Data drives or unrelated files. Work only in this project and its designated derived/test state.

Determine whether the practical timed-plan integration is actually available. Design around the real current capability. If it is unfinished or blocked, report that dependency, keep static collections distinct from feasible plans, and improve the usable existing workflow; do not fabricate a working plan solver or expand this UX task into algorithm development.

ORCHESTRATION
- Inspect installed codex --version, codex exec --help and relevant model/config guidance before selecting commands. Reuse the signed-in CLI; no new API keys, billing setup, provider changes or global config edits.
- Write a common brief and three self-contained stage prompts under a dedicated project-local UX handoff directory. Include all preservation rules, branch/path, actual current capability, task goals and acceptance criteria in EVERY stage prompt; fresh exec runs do not inherit this conversation.
- Execute stages strictly sequentially in the same intended feature workspace. No competing writers. Coordinator does not edit implementation files while a child works.
- Use codex exec with explicit --model and -c model_reasoning_effort settings, prompt input from a file/stdin, persisted logs, and --output-last-message. Prefer supported workspace-scoped permissions/automatic approval review. Do not bypass sandboxing, policy or denied actions to avoid a pause.
- Stage 1: gpt-6-astra, model_reasoning_effort=ultra.
- Stage 2: gpt-6.1-sol, model_reasoning_effort=high.
- Stage 3: gpt-6-astra, model_reasoning_effort=high.
- Verify the selected model/effort from CLI evidence where available. If Ultra/model access is unsupported, stop with the exact error; do not silently substitute or call another setting Ultra.
- Require a structured final handoff with stage, status (complete/blocked/failed), branch, tested source identity, artifacts, checks and blockers. Use --output-schema if supported. CLI exit zero alone is not acceptance: inspect the handoff and evidence before continuing.
- One run per stage, plus at most ONE Sol High repair run for concrete review findings. No recursive orchestration, indefinite retry/review loops or automatic purchase/fallback to more expensive models. Ultra may use a small number of read-only helpers when genuinely useful; one owner writes the UI.
- Keep durable progress so interrupted work is recoverable. On rate limits, unavailable browser tools, required human approval or unrecoverable failures, preserve work, record the exact blocker and stop. Never claim blocked acceptance passed.

COMMON PRODUCT GOAL
Make HuntMaps2/TrailScout straightforward for Tanner and his father to use for Colorado GMU 54 second rifle. The core journey is:
party and usable effort budget -> assumed access/start and search area -> analysis -> recommended glassing option -> inspect route/sightlines -> save/export.

Prioritize fewer decisions, understandable results and reliable recovery. Keep advanced habitat/model settings accessible through progressive disclosure. Preserve analytical behavior, source provenance, original controls, compatible saves/exports and experimental labels.

Show one understandable primary recommendation and a small set of meaningfully different alternatives. If only established plans are available, label them accurately. Never present a static five-point collection as a feasible itinerary.

Make the start/parking assumption, complete return distance/ascent, schedule/observation time, distinct habitat/scan sectors, uncertainty and remaining effort understandable. Distinguish nominal 2.5-mile/750-ft family limits from the usable 1.875 miles/562.5 ft after 25% reserve when that profile is active; retain saved profile values and never auto-relax limits.

Provide clear progress, errors, cancellation/retry, missing-package states, empty results and recovery. No fabricated percentages or ETAs. Preserve filled inputs, selected results and saved work across appropriate navigation/reload. Give actions that resolve problems.

Use a restrained, coherent visual system: readable typography, spacing, contrast, consistent controls, sensible map/sidebar hierarchy and accessible focus/keyboard behavior. Avoid ornamental dashboard cards, oversized headers, excessive badges, generic marketing screens and a mandatory wizard for expert users. Fit an ordinary laptop and a narrower window without hidden controls or horizontal overflow. Maintain map, form and recommendation synchronization.

STAGE 1 — ASTRA ULTRA: AUDIT, DESIGN AND ONE VERTICAL SLICE
Operate the real app in the available browser using disposable state and a real GMU example where available. Inspect the actual frontend, services, tests and current workflows. Identify the most consequential friction and establish a reproducible baseline task.

Choose one coherent design autonomously. Produce a concrete implementation brief with screen/state layouts, navigation, component boundaries, microcopy, loading/error/empty states, accessibility and compatibility details. Trace every displayed value to real backend data.

Implement ONE representative working vertical slice in the actual application to establish the design direction, with focused checks and browser screenshots for internal verification. Leave it functional and buildable. Do not spend this stage rebuilding the whole frontend or polishing a disconnected mockup. Carry forward the complete design brief and explicit remaining implementation tasks to Sol. Record what was actually observed versus inferred.

STAGE 2 — SOL HIGH: COMPLETE THE DESIGN
Read the common brief, Astra handoff, actual diff and current code. Complete the highest-value workflow from actual inputs through recommendation/inspection/save/export, retaining expert access and existing functionality.

Refactor frontend structure when justified, rather than stacking fragile CSS and conditionals. Add only necessary API presentation fields with compatibility tests; do not change habitat coefficients, ranking objectives, legal-access conclusions or route feasibility to make the UI look better.

Test meaningful state transitions, errors, stale async responses, cancellation/retry, profile/date/objective changes, map/selection agreement and save/reload/export. Check keyboard/focus/contrast and real desktop/narrow layouts. Run the applicable frontend build/type/format tests, TrailScout gates and full repository release workflow including ./gui/check where applicable. Keep failed full runs distinct from isolated reruns. Fix relevant implementation defects and record all blockers.

Measure the baseline versus new task steps and task completion on identical data; compare UI responsiveness separately from unchanged GIS compute. Do not fabricate usability participants or measured task-time improvements. Hand off working code, actual screenshots/checks, source identity, limitations and launch instructions.

STAGE 3 — ASTRA HIGH: INDEPENDENT BROWSER REVIEW
Read the original goals and source/diff, then independently perform realistic tasks in the implemented app using fresh disposable state. Do not rely solely on the implementer's claims.

Try conservative family planning, an access assumption requiring review, missing data, no feasible result, navigation/reload, save/export and a narrow window. Check recommendation/route/scan identity, preserved inputs, misleading confidence, hidden controls and whether the workflow is actually easier to follow. Distinguish measured before/after facts from design judgment.

Produce prioritized concrete findings with reproduction steps and acceptance criteria. If material fixable findings remain, the coordinator may invoke ONE Sol High repair pass scoped to those findings, followed by relevant tests and a complete gate when implementation changes require it. Record unresolved findings; do not start another Astra loop.

FINISH
Write a concise durable UX implementation/review report identifying base/feature branch and commits/diff hashes, completed changes, before/after task evidence, actual tests and final tested source, preserved functionality/state, unresolved blockers, remaining risks, launch command and how to revert the UX branch. Keep large test artifacts and private/user state out of Git.

Do not claim biological improvement or field validation from a cleaner interface. Do not claim browser validation if no browser was available. Stop when the bounded workflow is complete and report exactly what is ready for me in the morning.
