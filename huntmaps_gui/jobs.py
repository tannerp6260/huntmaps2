"""One process group at a time; durable job records, bounded logs and safe cancellation."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import replace
from .catalog import ROOT, STATE, read
from .config import current, configured

ACTIVE = {"running", "cancelling"}
BOOT_ID = (
    __import__("pathlib").Path("/proc/sys/kernel/random/boot_id").read_text().strip()
)


from .storage import write, locked as file_locked


def start_ticks(pid):
    try:
        return (
            (__import__("pathlib").Path(f"/proc/{pid}/stat").read_text())
            .rsplit(")", 1)[1]
            .split()[19]
        )
    except OSError:
        return None


class Jobs:
    def __init__(self, state=None):
        state = state if state is not None else current().state_dir
        self.config = replace(current(), state_dir=state)
        self.folder = state / "jobs"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.process = None
        self.kill_threads = []
        self.wait_threads = []
        self.storage_errors = []
        for p in self.folder.glob("*.json"):
            if p.name.endswith(".progress"):
                continue
            try:
                j = read(p)
                if not isinstance(j, dict) or not all(
                    k in j for k in ("id", "status", "started", "kind")
                ):
                    raise ValueError(
                        f"Damaged job record: {p}. Preserve it and restore a backup."
                    )
            except ValueError as error:
                self.storage_errors.append(str(error))
                continue
            if j["status"] in ACTIVE:
                j.update(
                    status="interrupted",
                    stage="Interrupted after app restart",
                    finished=time.time(),
                    error="The app stopped during this job. Partial files were retained; review the plan before resuming.",
                )
                write(p, j)
                # A stale child may survive a server crash. Kill only its recorded process identity.
                if (
                    j.get("boot_id") == BOOT_ID
                    and j.get("pid")
                    and j.get("ticks")
                    and start_ticks(j["pid"]) == j["ticks"]
                ):
                    try:
                        os.killpg(j["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass

        self.reconcile()

    def logs(self, ident, limit=64000):
        if not __import__("re").fullmatch(r"[a-f0-9]{32}", ident):
            raise ValueError("Unknown job")
        if not (self.folder / (ident + ".json")).exists():
            raise ValueError("Unknown job")
        path = self.folder / (ident + ".log")
        if not path.exists():
            return ""
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - min(64000, max(0, limit))))
            return handle.read(min(64000, max(0, limit))).decode(errors="replace")

    def list(self, include_logs=True):
        with configured(self.config), file_locked(
            self.config.state_dir / "maintenance"
        ), self.lock:
            return self._list(include_logs)

    def _list(self, include_logs=True):
        result = []
        for p in self.folder.glob("*.json"):
            if p.name.endswith(".progress"):
                continue
            try:
                j = read(p)
                if not isinstance(j, dict) or not all(
                    k in j for k in ("id", "status", "started", "kind")
                ):
                    raise ValueError(
                        f"Damaged job record: {p}. Preserve it and restore a backup."
                    )
            except ValueError as error:
                result.append(
                    dict(
                        id=p.stem,
                        kind="damaged-record",
                        status="damaged",
                        stage="Record needs recovery",
                        elapsed_s=0,
                        error=str(error),
                    )
                )
                continue
            try:
                progress = read(self.folder / (j["id"] + ".progress"))
            except ValueError:
                progress = None
            if isinstance(progress, dict):
                j["progress"] = progress
            j.setdefault("stage", "Stage unavailable; inspect the job log")
            j["elapsed_s"] = round((j.get("finished") or time.time()) - j["started"], 1)
            log = self.folder / (j["id"] + ".log")
            if log.exists() and (include_logs or j["status"] in ACTIVE):
                with log.open("rb") as f:
                    f.seek(max(0, log.stat().st_size - 64000))
                    j["logs"] = f.read().decode(errors="replace")
            else:
                j["logs"] = ""
            # Stage records are emitted by the actual wrapper or existing engine, never a percentage.
            stages = [
                line[6:] for line in j["logs"].splitlines() if line.startswith("STAGE ")
            ]
            if stages and j["status"] == "running":
                j["stage"] = stages[-1]
            if j.get("name") and j["status"] == "running" and j["kind"] == "baseline":
                analysis = self.config.workspace / "results" / j["name"] / "analysis"

                def fresh(filename):
                    p = analysis / filename
                    return p.exists() and p.stat().st_mtime >= j["started"]

                if fresh("dem.tif"):
                    j["stage"] = "Prepared terrain and eligibility masks"
                if fresh("pool.json"):
                    j["stage"] = (
                        "Candidate pool saved; evaluating visibility and inspection scores"
                    )
                masks = [
                    p
                    for p in (analysis / "additional_visibility").glob("*.tif")
                    if p.stat().st_mtime >= j["started"]
                ]
                if masks:
                    j["stage"] = (
                        f"Evaluating visibility and inspection scores · {len(masks)} masks saved this job"
                    )
                if fresh("scores.json"):
                    j["stage"] = (
                        "Scores saved; preparing access evidence and review exports"
                    )
                if fresh("approaches.json"):
                    j["stage"] = "Access status saved; building review packet"
                if fresh("review_packet.pdf"):
                    j["stage"] = "Analysis packet saved; creating owner handoff"
            if j.get("name") and j["status"] == "running":
                ex = (
                    self.config.workspace
                    / "results"
                    / j["name"]
                    / "analysis/execution.jsonl"
                )
                if ex.exists():
                    lines = ex.read_text().splitlines()
                    if lines:
                        try:
                            event = json.loads(lines[-1])
                            j["engine_event"] = event
                        except ValueError:
                            pass
            if not include_logs:
                j.pop("logs", None)
                j.pop("command", None)
                for key in ("pid", "ticks", "boot_id"):
                    j.pop(key, None)
            result.append(j)
        return sorted(result, key=lambda j: j.get("started", 0), reverse=True)

    def start(self, command, kind, name=None, plan=None, cwd=None):
        with configured(self.config), file_locked(
            self.config.state_dir / "maintenance"
        ), self.lock:
            if any(j["status"] in ACTIVE for j in self.list(include_logs=False)):
                raise ValueError("Another job is running. Wait or cancel it first.")
            ident = uuid.uuid4().hex
            j = dict(
                id=ident,
                kind=kind,
                name=name,
                plan=plan,
                status="running",
                stage="Starting subprocess",
                started=time.time(),
                command=command,
            )
            log = (self.folder / (ident + ".log")).open("wb")
            env = dict(
                os.environ,
                **self.config.environment(),
                PYTHONUNBUFFERED="1",
                PYTHONPATH=str(self.config.source_dir),
                OPENBLAS_NUM_THREADS="1",
                OMP_NUM_THREADS="1",
                MPLCONFIGDIR=str(self.config.state_dir / "mpl"),
            )
            env["HUNTMAPS_PROGRESS_FILE"] = str(self.folder / (ident + ".progress"))
            self.process = subprocess.Popen(
                [sys.executable, "-u", "-m", "huntmaps_gui.guarded_job", *command],
                cwd=cwd or self.config.source_dir,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            proc = self.process
            j.update(pid=proc.pid, ticks=start_ticks(proc.pid), boot_id=BOOT_ID)
            write(self.folder / (ident + ".json"), j)
            waiter = threading.Thread(
                target=self._wait, args=(ident, proc, log), daemon=True
            )
            self.wait_threads.append(waiter)
            waiter.start()
            return j

    def _wait(self, ident, proc, log):
        code = proc.wait()
        log.close()
        with configured(self.config), file_locked(
            self.config.state_dir / "maintenance"
        ), self.lock:
            path = self.folder / (ident + ".json")
            j = read(path)
            # A restarted manager may already have recorded interruption. A late
            # waiter must not overwrite that durable diagnosis with generic failure.
            if j["status"] not in ACTIVE:
                return
            if j["status"] == "cancelling":
                try:
                    os.killpg(j["pid"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            status = (
                "cancelled"
                if j["status"] == "cancelling"
                else ("complete" if code == 0 else "failed")
            )
            j.update(
                status=status,
                exit_code=code,
                finished=time.time(),
                stage={
                    "complete": "Finished",
                    "cancelled": "Cancelled; partial files retained",
                    "failed": "Failed; see details and log",
                }[status],
            )
            if status == "complete":
                j.pop("error", None)
            if status == "failed":
                lines = (
                    (self.folder / (ident + ".log"))
                    .read_text(errors="replace")
                    .splitlines()
                )
                diagnostics = [
                    line
                    for line in lines
                    if line.startswith(
                        ("SCOUT:", "GUI JOB:", "ValueError:", "FileNotFoundError:")
                    )
                ]
                from .failures import summarize

                j.update(summarize(lines))
            if status == "failed" and j["kind"].startswith("first-person"):
                j["error"] = (
                    (
                        diagnostics[-1] + " "
                        if diagnostics
                        else "First-person preparation failed. "
                    )
                    + "Review the source plan and preparation log in the first-person viewer. Valid bundles and partial source files were retained."
                )
            if status == "failed" and j["kind"] == "waypoint-update":
                j["error"] = (
                    (
                        diagnostics[-1] + " "
                        if diagnostics
                        else "Waypoint update failed. "
                    )
                    + "Previous waypoint and terrain shading retained. Retry Update waypoint after fixing the named source or budget issue."
                )
            if status == "failed" and j["kind"] in ("approach", "network-acquisition"):
                j["error"] = (
                    (diagnostics[-1] if diagnostics else "Scouting job failed.")
                    + " Prior scenarios and sources retained; inspect the job log and explicitly recompute after correcting the named constraint or source."
                )
            write(path, j)
            errors_before = len(self.storage_errors)
            self.reconcile()
            if (
                j["kind"] == "waypoint-update"
                and len(self.storage_errors) > errors_before
            ):
                j.update(
                    status="failed",
                    stage="Waypoint publication needs recovery",
                    error=self.storage_errors[-1],
                )
                write(path, j)
                self.reconcile()

    def reconcile(self):
        from .working_waypoints import publish_completed

        with configured(self.config):
            publish_completed(self)

    def cancel(self, ident):
        with configured(self.config), file_locked(
            self.config.state_dir / "maintenance"
        ), self.lock:
            path = self.folder / (ident + ".json")
            j = read(path)
            if not j or j["status"] not in ACTIVE:
                raise ValueError("Job is not running")
            j["status"] = "cancelling"
            write(path, j)
            if start_ticks(j["pid"]) == j["ticks"]:
                try:
                    os.killpg(j["pid"], signal.SIGTERM)
                except ProcessLookupError:
                    pass
                thread = threading.Thread(target=self._kill, args=(j,), daemon=True)
                self.kill_threads.append(thread)
                thread.start()
            return j

    def _kill(self, j):
        time.sleep(2)
        with configured(self.config), file_locked(
            self.config.state_dir / "maintenance"
        ), self.lock:
            current = read(self.folder / (j["id"] + ".json"))
            if current["status"] not in ACTIVE:
                return
            try:
                os.killpg(j["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass

    def shutdown(self):
        for j in self.list(include_logs=False):
            if j["status"] == "running":
                self.cancel(j["id"])
        for thread in self.kill_threads + self.wait_threads:
            thread.join(timeout=3)
