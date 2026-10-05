# Current maintenance and verification

Run the isolated suite with:

```sh
./gui/check
```

It runs GUI backend tests, synthetic archive-free CLI baseline journeys, Python
format checks, frontend formatting/type checking/build, and offline browser
journeys on a dedicated localhost server. The normal application can stay open.
Tests use temporary GUI records, jobs, imports, derived display assets and masks.
Saved Soap Creek results and prepared bundles are read-only fixtures. No field
validation or online-provider availability is inferred from these checks.

Each invocation retains `/tmp/huntmaps-check-*` with separate logs, screenshots,
performance measurements and the protected-file audit. Failures retain diagnostics
and stop the dedicated server. `--skip-browser` runs the backend and frontend
checks only. The optional provider journey remains separate:

```sh
HUNTMAPS_URL=http://127.0.0.1:8765 node gui/frontend/browser-online-check.mjs
```

The offline real-data suite needs the saved Soap Creek results and prepared pilot
scenes. These are deliberately absent from Git. The archive-free `test_owner.py`
journey works without them. A missing real fixture is a visible failure rather than
a synthetic replacement for real scene evidence.

Open **Storage and recovery** to inspect record diagnostics and cache sizes. Back up
GUI records before maintenance. Restore selects a retained backup; it never changes
saved analysis outputs. Restoring working records clears pending publication tokens
so a late worker cannot authorize an old move. Explicit reset requires typing
`RESET GUI RECORDS`, makes a backup, and resets notes and waypoints. It is separate
from cache cleanup. Invalid records are preserved for diagnosis and are never
silently replaced with empty records. Job-record damage may require restoring the
named JSON file from a known copy while the application is stopped.

Cleanup first presents a preview. Execution rechecks that preview under the shared
maintenance lock, refuses active jobs, and protects current/pending/backup waypoint
revisions, ready scenes and recursively referenced bundles. Authoritative inputs,
imported boundaries, annotations, historical outputs and backups are outside the
cache inventory. Unused display assets, unreferenced masks/bundles and terminal
partials can be regenerated. Display files have a separate 256 MB least-recently-used
budget; scene and analysis budgets retain their original limits.

The byte-level baseline is `docs/gui/CLEANUP_PRESERVED.json` (7,229 files). The suite
hashes it before and after verification. The manifest covers analysis source,
configurations, data, runs, results, experimental evidence and hashed launchers.
It does not authorize editing or regenerating protected files.

Development formatting:

```sh
.venv/bin/python -m black huntmaps_gui gui/check.py gui/preservation.py
npm run format --prefix gui/frontend
```

Black and Prettier versions are pinned. Engine code is excluded. Older `gui/verify_*.py`
and the other browser scripts remain historical or specialist tools; they are not
safe replacements for the isolated runner. Online preparation is intentionally not
part of the offline default suite.

Guided approach review records (`approach-reviews/*.json`) are protected definitions,
covered by backups and the owner's record audit. Cache cleanup does not delete them
or referenced comparisons. Explicit reviewed deletion of an unprotected generated
run includes its review record. The guided journey now exercises independent jobs,
preferences/reload, marker filtering, dismissal/Undo and the all-retained inspection
requirement; see [verification and measurements](GUIDED_APPROACHES_2026-10-04.md).
