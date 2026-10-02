# Current GUI setup

Launch the installed workspace with `./huntmaps-gui`. Use
`./huntmaps-gui --preflight --port 8766` to check setup without starting a server.
`--port`, `--no-browser`, and `--state-dir /absolute/path` work together. The
server listens only on localhost.

For a fresh installation, first create the native GIS environment described in
`START_HERE.md` using the unchanged `environment.scout.yml`. Then install Python
packages and the locked frontend into that environment:

```sh
export SCOUT_PYTHON="$PWD/.scout-env/bin/python"
"$SCOUT_PYTHON" -m pip install -r gui/requirements-dev.txt
npm ci --prefix gui/frontend
npm run build --prefix gui/frontend
./huntmaps-gui --preflight
./huntmaps-gui
```

For this existing workspace use `.venv/bin/python`. Runtime and development
requirements live in `gui/requirements.txt` and `gui/requirements-dev.txt`.
Lidar decoding and the foliage mesher are installed in the selected interpreter;
there is no dependency directory injected into Python's search path. Native GDAL
comes from the GIS environment, rather than a pip wheel. The existing environment
was verified with GDAL 3.4.1 and Python 3.10.12; a fresh native environment solve
has not been performed during this cleanup.

Chrome/Chromium is needed for browser checks. Set `HUNTMAPS_BROWSER` to its executable
when it is not `/usr/bin/google-chrome`. The GUI can run with `--no-browser` and be
opened manually. Missing optional preparation dependencies affect preparing new
first-person bundles; existing prepared scenes remain viewable.

The source locations, writable workspace and GUI state are separate in
`huntmaps_gui.config.AppConfig`. Worker subprocesses inherit the same configuration.
Normal use defaults to this project and `.gui`. Internal tests use temporary state
and a temporary workspace; historical source files and prepared scene bundles are
read through adapters. `HUNTMAPS_DISPLAY_BUDGET_MB` sets the regenerable display-cache
budget (256 MB by default). It does not increase analysis or scene-preparation budgets.

`scout` is byte-identical to the reviewed prototype because completed-run manifests
hash it. The plan's `./scout gui` launch assumption did not match this repository;
changing the existing hashed launcher would invalidate historical verification.
Use `./huntmaps-gui`; the original CLI commands remain available through `./scout`.
