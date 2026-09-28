# Codex CLI on Ubuntu: glassing experiment implementation prompts

Prepared 26 September 2026. This is an implementation brief, not a claim that the software or hunting benefit has already been validated.

## Recommended prompting methodology

Use a persistent specification, short repository instructions, and one executable milestone at a time. Each milestone must produce runnable software and inspectable evidence. Keep the broader methodology open to revision when actual data, runtime measurements, or field evidence contradict it.

The initial task should include both a brief repository audit and implementation of a small end-to-end baseline. An audit-only task can waste a session; an unrestricted request to build the complete system invites premature complexity. The best compromise is bounded autonomy: let Codex make routine engineering decisions and finish an agreed milestone, then review its evidence before authorizing the next scope increment.

Separate three kinds of success:

1. **Engineering correctness:** reproducible data preparation, credible visibility calculations, valid exports, measured resource use.
2. **Decision quality:** more independently assessed useful terrain or less planning effort under equal constraints.
3. **Hunting effectiveness:** better effort-adjusted field outcomes. Synthetic tests and the optimizer's own score cannot establish this.

Use the original research report as a design hypothesis and source index. Do not ask Codex to reproduce the entire research study or treat its proposed coefficients as measured ecological facts. Ask for concise decisions and supporting evidence, rather than an exhaustive reasoning transcript.

## Before starting

Open Codex CLI in the actual HuntMaps repository if you want it evaluated. Alternatively, open an empty project directory; the prompt supports a separate implementation. Download this file into that directory. If available, also copy `Mule_Deer_Glassing_Methodology_Decision_Report.md` there or under `docs/`. Files in this conversation are not automatically present on your Ubuntu computer.

Start an interactive session with `codex`. Ask it to read this file and execute **Prompt 1 only**. No special orchestrator, background agent loop, or cloud GIS deployment is required.

Use normal workspace permissions. Public data acquisition requires network access. Install GIS dependencies in a coherent isolated environment that respects GDAL's native-library compatibility; let the audit determine the appropriate existing environment. Do not start by installing every GIS package listed in the research report.

The GIS pipeline should execute locally. Standard hosted Codex model use still involves a remote service; local execution does not make the assistant an offline model. Avoid putting unnecessary sensitive hunting coordinates or credentials into prompts and logs.

## Prompt 1 — Audit and build the terrain baseline

Copy the following block, or instruct Codex to execute it from this file.

```text
Implement the first runnable experiment for a western mule deer glassing planner on this Ubuntu computer.

OBJECTIVE
Build a small, reproducible system that lets us test whether automated observation planning improves on manual scouting. The eventual goal is efficient, useful deer observation within legal access and time constraints. The current milestone is a technically credible terrain-visibility baseline, not a finished hunting recommender.

Read applicable AGENTS.md instructions. Read the methodology decision report if it is present in this project. Treat the report as a researched hypothesis, not proof of hunting effectiveness. Do not repeat broad research; verify primary-source documentation where a concrete implementation decision needs it.

Audit the actual repository and computer before choosing an architecture. HuntMaps may supply reusable ingestion, raster alignment, access, or export functions, but its existence is not a reason to preserve unsuitable architecture. If no HuntMaps code is present, proceed with a small standalone component in this workspace. Do not claim to have audited unavailable code.

WORKING STYLE
Proceed through this milestone without asking permission for routine reversible work already covered here. Make reasonable choices, record assumptions, and keep progress updates concise. Ask only for genuinely blocking information, credentials, permissions, or destructive changes. Respect the actual runtime permission system. Do not stop after proposing a plan.

Preserve unrelated changes. Inspect git status before editing. Do not reset, clean, stash, overwrite user work, publish, push, or use paid services. Do not alter system Python or perform unattended sudo operations. Prefer the existing dependency approach and an isolated environment. Exclude bulk downloaded data and generated rasters from version control.

Keep this experiment small. Start with 100–200 candidate points and a bounded AOI before scaling. Inspect available RAM, CPU, disk, native GIS binaries, Python environment, and relevant package versions. Establish configurable download, disk, memory, and runtime budgets from the actual machine; start with no more than 2 GB of new downloads unless existing inputs make that impractical. Use a smaller AOI if needed. These are initial experiment limits, not requirements of the final system.

DELIVERABLES AND SEQUENCE

1. Brief audit and architectural decision.
   Inspect entry points, data contracts, tests, environment, and reusable modules. Choose: reuse selected HuntMaps modules, add an isolated component, or create a standalone minimal package. Explain the decision with file-level evidence. Avoid broad refactoring.

2. Persistent project context.
   Create or update docs/glassing/SPEC.md, PLAN.md, and STATUS.md, preserving existing content. SPEC holds the objective, model distinctions, data contracts, assumptions, and acceptance criteria. PLAN holds milestones and dependencies. STATUS records commands actually run, outputs, failures, measured resources, and the next action. Add only concise relevant instructions and pointers to AGENTS.md, without overwriting existing rules. Do not put the whole report in AGENTS.md.

3. Reproducible trial inputs.
   Prefer an existing user-defined study polygon and valid local data. Otherwise obtain an authoritative Colorado GMU 54 boundary and define a reproducible 50–100 km² pilot subset, reducing size if needed for resource limits. Record the exact polygon and selection method. This is a technical test area, not an assertion of good hunting or verified access. Do not invent boundary coordinates, trailheads, closures, or permissions.
   Use a roughly 10 m bare-earth DEM initially. Retain the terrain outside the study boundary needed for sightlines. Acquire only necessary datasets. Record provider, URL or API request, acquisition date when known, retrieval date, resolution, CRS, vertical units/datum when available, license, and checksum. Missing metadata must remain explicit.
   If authoritative data cannot be obtained, finish the synthetic-fixture pipeline and acquisition adapter, record the precise blocker, and identify the minimal missing input. Do not substitute synthetic output and describe it as a real-area result.

4. Correct spatial preparation.
   Use a suitable projected metric CRS and a documented common grid. Validate horizontal and vertical units, alignment, NoData handling, and resampling methods. Do not equate reprojection with vertical datum correction. Unknown vertical references must be surfaced and their implications assessed.
   Maintain separate observer-feasibility masks, target masks, and obstruction terrain. Terrain on private land still blocks sightlines. Do not erase it merely because observation or hunting there is excluded. Treat ownership alone as insufficient evidence of legal connected access.

5. Candidate generation and terrain visibility.
   Include terrain-derived candidates such as shoulders, benches, and ridge breaks, plus a spatially distributed background sample and optional manually supplied points. Do not restrict candidates to local summits or habitat-score maxima. Deduplicate nearby points while retaining provenance.
   Start with a configurable 2 km radius; evaluate 1 and 3 km as sensitivity cases if resources allow. These are test settings, not universal optical limits. Use configurable observer eye height and target height above bare earth.
   Prefer an established viewshed engine over writing one from scratch. Consider GRASS r.viewshed and GDAL viewshed; choose one initially based on verified capabilities, correctness checks, existing dependencies, and installation burden. Document curvature/refraction settings. Keep an interface that allows later comparison, without building an elaborate plugin framework.
   Calculate distance-bounded visible target area and retain the underlying masks or reproducible cached products. Account for cell area. Export ranked candidates with visible area, distance bands, and explicit unknowns. Raw visible area must be labeled a terrain baseline, not deer probability or hunting quality.

6. Evidence and useful outputs.
   Provide configuration-driven commands for preparing inputs, generating candidates, computing/scoring visibility, and exporting results. Match existing project conventions where sensible. Commands must actually run; do not present proposed command names as implemented capabilities.
   Produce a GeoPackage readable in QGIS, GeoTIFFs where appropriate, a candidate CSV, GPX waypoints, and a concise run report. GPX is for field-app review, not proof of successful onX import. Include unique IDs, coordinates, parameters, provenance, and reasons each candidate ranks highly. Unknown-access candidates must be visibly labeled and excluded from any claimed field-ready shortlist.
   Provide an offline synthetic example and, when acquisition succeeds, one real-AOI run. Record wall time, observed peak memory where measurable, cache size, and candidate count. Estimate larger-area costs from measured components and state limitations; do not claim unit-scale performance from an unmeasured guess.

MEANINGFUL VERIFICATION
Test synthetic flat terrain, a ridge obstruction, eye/target height effects, NoData, and coordinate/unit failures. Check selected sightlines independently of the primary viewshed engine. Test that changing grid resolution does not silently inflate area scores, and that excluded target areas do not erase obstructions. Verify export coordinates, CRS, and read-back. Inspect a representative real-area result for artifacts. Run the smallest relevant existing regression suite. Avoid large suites of tests that merely repeat implementation logic.

SCIENTIFIC AND SCOPE CONSTRAINTS
Keep terrain visibility, glassability, habitat suitability, seasonal deer use, accessibility, and strategic value conceptually separate. The first milestone implements terrain visibility plus data/feasibility foundations. Do not invent calibrated deer probabilities, trophy-buck likelihood, field sightings, or expert validation.
Do not build a web app, replace field navigation software, add ML, require paid imagery, compute unit-wide 1 m viewsheds, build a voxel forest, or add route optimization in this milestone. Do not call a partial DSM approximation vegetation-aware deer visibility.

DEFINITION OF DONE
A second run can reproduce the baseline from documented commands and configuration; offline correctness checks pass; one real-area run succeeds or a precise external data blocker is documented; outputs are inspectable in QGIS; resource measurements and limitations are recorded. Provide a short audit conclusion, implemented changes, commands and results, output locations, remaining uncertainties, and a recommendation for the next milestone.

Finish this milestone and stop at that evidence checkpoint. Do not silently start later milestones. If interrupted, update STATUS.md so a new session can resume without repeating completed work. Begin now with the repository/environment audit, then implement.
```

## Prompt 2 — Compare habitat and glassability models

Use after reviewing the baseline's maps, correctness checks, and measured runtime. This stage is justified by a working technical foundation; it still does not establish hunting benefit.

```text
Read applicable AGENTS.md and docs/glassing/{SPEC,PLAN,STATUS}.md. Inspect the implemented baseline and its run evidence. Correct any blocking baseline defect, then implement the next experiment: matched comparisons of raw terrain visibility, habitat-weighted visibility, and glassability-weighted visibility. Preserve the baseline as a reproducible control.

Use the same AOI, candidate pool, access assumptions, optics settings, and observation budget across comparisons. Keep every new feature separately switchable. Add a feasible stratified-random baseline and support importing expert-selected points. If no independent expert points exist, provide their collection protocol and mark that comparison pending; do not generate points yourself and call them expert selections.

Construct interpretable seasonal relative-use hypotheses from available authoritative range/habitat and vegetation information. Record each assumption and avoid double-counting correlated slope/aspect/cover proxies. A suitability score is not an occupancy probability. Keep a background target component or explicit alternative scenarios so uncertain habitat modeling cannot exclude all unexpected deer-use terrain.

Model target searchability, intervening vegetation obstruction, and observer foreground obstruction separately. Use affordable vegetation/opening data first. Canopy fraction is not optical transmittance; a DSM viewshed with deer endpoints on treetops is invalid. Retain bare-earth endpoint heights. If the chosen engine cannot separate endpoint elevations and obstruction surfaces, label the approximation, quantify its limits, and defer stronger vegetation claims.

Add configurable distance response, target-facing terrain/perspective, and a limited morning/evening light scenario. Distinguish detecting deer, classifying bucks, and judging antlers; use uncalibrated scenario curves until observations support calibration. Include finite inspection time or a clearly labeled coverage surrogate; do not imply that all visible terrain can be searched equally in a fixed dwell period. Penalize glare using sun/target geometry only as a documented hypothesis. Avoid precise behavioral claims from coarse weather or seasonal inputs.

Keep access and actionability explicit. Separate reachable observation positions from target areas that could be stalked or investigated. Road distance is a pressure proxy, not a measured hunter count. Expose preferences for roadlessness, hike/gain limits, and pressure rather than hard-coding them.

Evaluate parameter sensitivity and rank stability. Compare 10 m to a coarser baseline and selectively finer elevation/canopy data only where available and likely to change a decision. Use dense candidate coverage in a small reference area to assess candidate-generation misses. Report computational cost and which features materially change the shortlist; changed ranks alone are not evidence of improvement.

Produce component scores, uncertainty flags, maps, and 3–5 explainable alternatives. Add a field/imagery review sheet with equal-effort blinded comparison where feasible. Predeclare independent evaluation criteria before examining outcomes. Do not tune on all review observations and then report those same observations as validation.

Finish with a comparison report stating what is implemented, what is independently checked, what is still hypothetical, and whether the added complexity deserves further work. Update the persistent project documents and stop at this milestone.
```

## Prompt 3 — Complementary points and timed strategies

Use after the target-value and glassability assumptions are understandable and reasonably stable. If the simpler approach performs as well independently, retain it instead of automatically increasing complexity.

```text
Read the project instructions and current experiment evidence. Implement complementary observation selection and a small time-budgeted route experiment using the existing, inspectable target-value and viewing-quality model.

Start with F(S) = sum_j w_j * max_{i in S} q_ij, where w_j is nonnegative target mass including patch/cell area, and q_ij is the fixed nonnegative viewing-quality score from point i to target j for the scenario. Keep units and normalization explicit. Implement greedy marginal-gain selection for fixed point counts and verify small cases against exhaustive selection. Do not claim its cardinality approximation guarantee applies unchanged to route constraints or other modified objectives.

Report total and marginal useful coverage, overlap, and sensitivity. Describe percentages as fractions of a defined modeled target surface, not probabilities of finding deer. Do not multiply repeated observation probabilities under an unsupported independence assumption.

Then represent observation actions as point, time window, and dwell duration. Enforce approach + transfers + observation + return + reserve within the budget. Include directional travel costs, gain, closures, permissions, and daylight/darkness assumptions. Unknown access cannot become a field-ready route. Compare spending longer at one point with moving to another. Use simple insertion/swap heuristics and exact checks on small instances before considering more elaborate solvers.

Produce a small set of Pareto-relevant plans, such as lower effort, more unique useful coverage, and more robust access. Prefer interpretable alternatives over an arbitrary single weighted winner. Explain when morning/evening choices differ and which uncertain assumptions cause the change.

Export GPX points/tracks and simplified KML observation sectors alongside analysis files. Validate file contents and document an actual field-app import test as a separate manual acceptance item; do not claim a successful import without observing it. Clearly distinguish a modeled route from a physically verified safe approach.

Update the field experiment protocol to compare manual selection, terrain-only, habitat weighting, glassability, and multi-point plans under matched time/access budgets. Record observation effort, conditions, setup viability, deer sightings, duplicate groups, and human pressure; retain non-detections. Estimate sample requirements from pilot variability rather than inventing a guaranteed effect size.

Finish with runnable commands, measured runtime, independent optimization checks, illustrative plans labeled as unvalidated, and a continue/simplify/stop recommendation. Do not add a new application frontend or large-area infrastructure unless measurements establish the need.
```

## Reusable continuation and review prompts

**Resume after interruption or in a new CLI session:**

```text
Read AGENTS.md and docs/glassing/{SPEC,PLAN,STATUS}.md. Inspect git status and the latest outputs. Identify the last verified milestone and the unfinished work already authorized. Continue that work without repeating completed research or changing the objective. Run targeted verification, update STATUS.md, and report evidence and blockers. Do not advance into an unauthorized later milestone.
```

**Review before trusting a milestone:**

```text
Review the current glassing experiment as a skeptical GIS engineer and experimentalist. This pass is read-only. Prioritize errors that change rankings or falsely imply hunting validity: CRS/vertical units, NoData and boundary halos, endpoint heights, vegetation approximations, cell-area weighting, candidate misses, inaccessible points, overlap, effort budgets, and circular evaluation. Trace findings to code and actual outputs. Distinguish observed defects from hypotheses and missing field evidence. Recommend the smallest fixes and the simplest adequate method.
```

A fresh review session can reduce reliance on the implementation narrative, but it is not independent ecological or field validation. Follow the review with a specific fix request, rather than an open-ended instruction to keep improving forever.

## Why this division is appropriate

| Prompt choice | Purpose |
|---|---|
| Audit followed by a running baseline | Uses real repository evidence without getting stuck in planning |
| Baseline retained through later work | Reveals whether sophistication provides measurable value |
| Fixed comparison inputs and budgets | Prevents unfair comparisons from masquerading as algorithm improvement |
| Short AGENTS.md plus explicit specification paths | Keeps persistent guidance usable and detailed context discoverable |
| Checkpoint files with actual commands/results | Supports long work across sessions without trusting conversational memory |
| Local CPU implementation first | Lets measured bottlenecks justify acceleration or cloud work |
| Human imagery/access review and field evaluation | Covers facts software cannot infer reliably from available layers |

This is a project-specific engineering recommendation, not an experimentally proven universal optimum for prompting. It aims to minimize wasted development while making incorrect assumptions visible early.

## Official Codex references

Checked 26 September 2026:

- [Codex CLI](https://developers.openai.com/codex/cli): Linux installation and running Codex from a project directory.
- [Prompting guidance](https://developers.openai.com/codex/prompting): goals, context, outputs, boundaries, explicit file context, and verification.
- [AGENTS.md instructions](https://developers.openai.com/codex/guides/agents-md): persistent repository guidance and discovery rules. Keep this file concise; reference the experiment documents explicitly in task prompts.

The implementation requirements and experimental structure above are tailored to the glassing research study; they are not claims made by the Codex documentation.
