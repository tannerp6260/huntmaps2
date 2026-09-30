# Soap Creek neighborhood decision review

Completed review: `results/soap-creek-decision-review-v2/REPORT.md` and
`decision_review.pdf`. This derived review reuses the completed vegetation v2
calculations, preserving all experiment outputs. No model or score was added.

Three neighborhoods retain historical, target-searchability and cross-threshold
leaders. Western setups are alternatives within one neighborhood. A0075, V010 and
V008 appear together on `06_A0075_V010_V008_setup.png`, with fine unobscured imagery,
exact coordinates and each point's separately mapped saved visibility. All setup
close-ups use covering cached 0.5 m clips, with dates/native resolution recorded.

From the repository root, reproduce into a **fresh** directory:

```sh
MPLCONFIGDIR=/tmp/glassing-decision-mpl .venv/bin/python -m glassing.decision_review --source results/soap-creek-vegetation-v2 --out results/soap-creek-decision-review-repeat
xdg-open results/soap-creek-decision-review-v2/decision_review.pdf
cat results/soap-creek-decision-review-v2/REPORT.md
mkdir -p /tmp/soap-creek-shortlist-export
cp results/soap-creek-decision-review-v2/shortlist.gpx results/soap-creek-decision-review-v2/shortlist.kml results/soap-creek-decision-review-v2/shortlist.csv results/soap-creek-decision-review-v2/target_openings.csv /tmp/soap-creek-shortlist-export/
```

`shortlist.csv` contains coordinates, separate component indices/ranks and threshold
retention. `target_openings.csv` records representative visible cells in contiguous
known low-tree target areas, with bearings/distances/areas. `overlap.csv` contains
raw and known low-tree pair overlap. Foreground and sampled obstruction remain in
separate diagnostic files; neither is a new selection score. Source-preservation,
visibility alignment, imagery selection and export checks are recorded beside the
report. Access is unresolved separately; exports are provisional waypoints, not routes.
