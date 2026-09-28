# Glassing experiment
Read docs/glassing/SPEC.md, PLAN.md and STATUS.md before changing this component.
Use .venv/bin/python; setup instructions are in docs/glassing/README.md.
Keep obstruction terrain separate from observer eligibility and target masks.
Scores are terrain-visible area, never deer probability or verified legal access.
Do not commit data/, runs/, environments or generated rasters. Preserve the supplied reports.
Stop at the terrain-baseline evidence checkpoint; later models need explicit scope.

The user has authorized the next matched-comparison experiment. Preserve the terrain
control; read docs/glassing/comparison/PROTOCOL.md for its predeclared evaluation.
Stop after the comparison report; do not start field collection or later optimization.

The user subsequently authorized a corrective-validation pass before routes.
Use docs/glassing/correction/PROTOCOL.md; preserve frozen prior outputs and stop at
its review packet/recommendation. Mapped access traces are not legal or safe routes.

The user now authorizes a bounded actual-hunt desktop scouting shortlist for GMU 54
second rifle 2026. Preserve all existing controls; use configs/scouting.json and
separate runs/scouting. Produce provisional opportunities and approach evidence;
no timed itinerary or claim of blinded/field validation. Stop at the scouting handoff.

Scouting handoff/methods: docs/glassing/scouting/{REPORT,METHODS}.md. Prior controls
are locked by scouting/FROZEN_CONTROL.json; all field exports remain provisional.

The user authorizes transfer to a hunter-selected AOI and unchanged manual points.
Use docs/glassing/transfer/{INPUTS,PROTOCOL,README}.md and configs/transfer.template.json.
Preserve all prior outputs; no replacement centroid AOI, generated human selections,
new model coefficients or itinerary solver. If hunter files are absent, finish portable
imports/configuration and offline checks, then stop requesting those exact inputs.

The user authorizes a usability milestone: normal scouting needs only an observer
polygon; manual points are optional. Use START_HERE.md and docs/glassing/usability/REPORT.md.
Normal runs must not depend on historical archives. Preserve prior evidence and model
controls; no new scoring model or route optimization.
