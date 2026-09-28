# Glassing scout

Supply an area where you want to search for glassing positions. Get provisional
candidates, a terrain overview, inspection sectors, review cards and GPX/KML exports.
Manual glassing points are **optional**. No historical experiment archives are needed.

**[START_HERE.md](START_HERE.md)** covers this Ubuntu workspace and a fresh installation.

```bash
./scout doctor
./scout run --area inputs/my-area.geojson --name my-area
```

KML/KMZ polygons work too. Multiple polygons require `--polygon NUMBER` or an
explicit `--polygon all`. Your original export is retained unchanged.

Start with **results/my-area/REPORT.md** and **overview.png**. Individual review
cards, sectors, exports and source/configuration records live in that same folder.
Cached sources are reused only when their coverage and checksums pass. If data are
missing, the command writes an acquisition plan and exact next steps; it does not
claim an empty fetch acquired data. Repeat with `--download` to execute that plan.

The polygon defines **observer-search positions**, not the distant slopes that may
be viewed. Target support and obstruction terrain extend beyond it. Outputs are
provisional desktop decision support: relative model scores are not deer probabilities,
verified access, detection performance, or hunting-quality measurements. Unknown access
does not prevent reviewing results, but it prevents a field-ready claim.

## Optional comparison and historical experiments

Add `--manual inputs/my-points.gpx` to retain your original points and compare them
with independently generated candidates. No human selections are synthesized.

- [Historical experiment instructions](docs/glassing/README.md)
- [Transfer experiment protocol](docs/glassing/transfer/PROTOCOL.md) (requires manual points for the experiment, **not normal scouting**)
- [Usability implementation and checks](docs/glassing/usability/REPORT.md)
- `./scout verify --name my-area`: current run inputs, model, configuration and outputs.
- `./scout verify-history`: optional archived experiment integrity check.

The old adapter is retained as `python -m glassing.transfer_legacy` for reproducing
previous adapter identities. Historical `runs/` files are intentionally not in Git.
