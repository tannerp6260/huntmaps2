# Stage 2 implementation handoff

Read DESIGN.md, STAGE1.md, stage1-evidence.json and the actual diff/new
`trail_scout/web/src/recommendation.tsx`. The historical blocked report and original
workflow remain unchanged. This Stage 1 is Sol High; no Astra implementation or
review occurred. Coordinator must verify before any next actual sequential CLI run.

1. Finish the essential-input layout. Put party and nominal/usable effort first;
   show Together **2.5 mi / 750 ft nominal → 1.875 mi / 562.5 ft usable** at 25%
   reserve. Preserve edited/saved profiles. Bring entry and calculate within easy
   reach; reduce oversized headings and long preset explanation. Keep expert access
   without requiring a wizard. Retain all area/target/owner-edit controls.
2. Consolidate recommendation/evidence. Stage 1 is additive: the old six-preview
   list and detailed timed summary remain below the new panel. Put full previews
   and long per-stop patch lists behind clear disclosures while keeping exact
   coordinates, sectors, provenance and uncertainty accessible. Preserve existing
   test semantics/assertions or adapt them to real equivalent user interactions.
   Short-list filtering does not rank alternatives; do not invent an easier-plan
   rule or claim geometric separation beyond different viewpoint sets.
3. Complete the state/recovery contract from DESIGN.md. Check missing/corrupt core
   and practical packages, failed jobs, interrupted/cancelled/retry, empty and
   unknown-foot-access scenarios, startup races, stale context/analysis/open-save
   responses and draft-write ordering. Avoid a success-looking header before
   package readiness. Keep submitted inputs distinct from edits during work.
   Stage 1 blocks stale saving via dirty/settings mismatch and active status, but
   does not resolve every asynchronous race in the inherited app.
4. Persist active period/selection appropriately across reload/navigation; inherited
   startup restores AM recommendation rather than the previous selection. Explicitly
   distinguish current preview from immutable saved-version export identity. Verify
   saved version reopening, version parentage, field summary/JSON/GeoJSON/GPX and
   existing version-1 saves without schema/model changes.
5. Finish accessibility: actual tab semantics/keyboard behavior (inherited tab
   buttons use aria-selected without a tablist), focus/error/retry announcements,
   contrast, laptop/narrow layouts and zoom. Stage 1 native select/disclosure,
   focus jumps and 1366/820/390 widths pass; this is not a complete WCAG audit.
6. Run final frontend format/build and the complete `./trailscout check` plus
   `./gui/check --keep-going` on a stable final source. Use only scoped
   `/tmp/huntmaps-ux-sol-*` disposable state (`TMPDIR` can scope gate test state).
   Keep failed/full/rerun outcomes distinct and hash every untracked implementation
   file. Stage 1's full TrailScout pass spans small frontend edits; do not reuse it
   as final-source release acceptance. No full GUI gate was run in Stage 1.
7. Compare baseline/new tasks on identical real inputs. Fresh Stage 1 baseline is
   `/tmp/huntmaps-ux-sol-stage1/baseline`; historical baseline summary remains useful
   only as labeled context. Record UI actions and responsiveness separately from
   cold/warm GIS compute. No participant, biological or field-validation claims.

Stage 3 must independently operate fresh disposable state, including conservative
family planning, access review, missing data, no feasible result, navigation/reload,
save/export and narrow layout. It must inspect final source and reproduce behavior,
not merely repeat this implementer's assertions. At most one bounded repair follows
concrete review findings. Do not start later optimization or field collection.
