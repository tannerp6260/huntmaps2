# Bounded overnight UX — blocked

Stage1 ran with actual Codex CLI0.163.0, gpt-6-astra and ultra, confirmed by
its CLI header. It stopped with exit1 and exact error:

> ERROR: Selected model is at capacity. Please try a different model.

No structured stage handoff, design brief or implementation slice was completed.
Stages2/3 and optional repair were not invoked. WORKFLOW.md explicitly requires
stopping on model/rate-limit blockers; no model substitution or retry was made.
Before model execution, one argument conflict and an outer sandbox initialization
failure were preserved; approved startup retained child workspace-write sandboxing.

The original practical-plans task remains complete at111e2af. UX work branch is
feature/hunter-workflow-ux, with orchestration/evidence only. No analytical or UI
implementation changed. All protected file hashes remain unchanged; see audit JSON.
Common brief, all3 self-contained prompts, schema, invocation and compact browser
baseline are recoverable here. Full logs/screenshots/script/test state remain in
ignored local/ and /tmp/huntmaps-ux-stage1. No release gates are claimed for UX.
